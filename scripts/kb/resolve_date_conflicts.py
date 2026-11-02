from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Literal

from google import genai
from pydantic import BaseModel, Field


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "knowledge"
    / "canonical"
    / "episodes.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "knowledge"
    / "canonical"
    / "date_conflict_resolution.json"
)


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_NAME = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.8-flash",
)

BATCH_SIZE = 10

API_DELAY_SECONDS = 1.0


# ============================================================
# STRUCTURED OUTPUT SCHEMA
# ============================================================


class Evidence(BaseModel):
    source: str = Field(
        description="Source name."
    )

    claim: str = Field(
        description=(
            "What this source says about the air date."
        )
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Confidence in the reliability of this evidence."
        )
    )


class Resolution(BaseModel):
    episode_id: str

    season_number: int

    episode_number: int

    title_en: str | None

    title_fr: str | None

    decision: Literal[
        "accept_source_date",
        "accept_consensus",
        "accept_external_date",
        "unresolved",
    ]

    canonical_date: str | None

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reasoning: str

    evidence: list[Evidence]

    requires_human_review: bool


class ResolutionBatch(BaseModel):
    resolutions: list[Resolution]


# ============================================================
# LOAD DATA
# ============================================================


def load_json(
    path: Path,
) -> dict:

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


# ============================================================
# FIND CONFLICTS
# ============================================================


def collect_conflicts(
    data: dict,
) -> list[dict]:

    conflicts = []

    for episode in data["episodes"]:

        status = episode[
            "air_date"
        ][
            "status"
        ]

        if status not in {
            "majority_consensus",
            "unresolved_conflict",
        }:
            continue

        conflicts.append(
            episode
        )

    return conflicts


# ============================================================
# PROMPT
# ============================================================


def build_prompt(
    episodes: list[dict],
) -> str:

    episode_json = json.dumps(
        episodes,
        indent=2,
        ensure_ascii=False,
    )

    return f"""
You are the Date Conflict Resolver Agent for a
knowledge base of the animated series "Martin Mystery".

Your task is to determine the most defensible canonical
original air date for each episode listed below.

IMPORTANT RULES:

1. Do NOT assume that a source is correct merely because
   it is listed first.

2. These sources can contain broadcast-order differences,
   regional differences, database mistakes, or transcription
   errors.

3. Treat the local episode data below as evidence, not truth.

4. When the available local evidence is insufficient,
   use web search to independently verify the date.

5. Prefer primary or highly reliable sources when available:
   - official broadcaster/archive information
   - established television databases
   - contemporary listings
   - reliable episode guides

6. Wikipedia is useful evidence but must not automatically
   override other sources.

7. epguides is useful evidence but must not automatically
   override other sources.

8. TheTVDB is useful evidence but must not automatically
   override other sources.

9. Distinguish:
   - original air date
   - production date
   - DVD date
   - streaming date
   - regional broadcast date
   - rerun date

10. We are interested in the ORIGINAL AIR DATE represented
    by the episode's canonical historical ordering.

11. If two or more sources agree and external evidence
    supports them, confidence should be high.

12. If sources disagree because they represent different
    broadcast regions or orderings, explicitly explain this.

13. If no defensible answer can be established, return:
       decision = "unresolved"
       canonical_date = null
       requires_human_review = true

14. Never invent a date.

15. Return dates only in ISO format:
       YYYY-MM-DD

16. Keep the reasoning concise but specific.

17. You MUST return structured JSON conforming to the
    requested schema.

LOCAL EVIDENCE:

{episode_json}
"""


# ============================================================
# GEMINI CALL
# ============================================================


def resolve_batch(
    client: genai.Client,
    episodes: list[dict],
) -> ResolutionBatch:

    prompt = build_prompt(
        episodes
    )

    response = client.interactions.create(
        model=MODEL_NAME,

        input=prompt,

        tools=[
            {
                "type": "google_search"
            }
        ],

        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema":
                ResolutionBatch.model_json_schema(),
        },
    )

    output_text = response.output_text

    if not output_text:
        raise RuntimeError(
            "Gemini returned empty output."
        )

    try:
        return ResolutionBatch.model_validate_json(
            output_text
        )

    except Exception as exc:

        raise RuntimeError(
            "Gemini returned invalid structured output.\n"
            f"{output_text}"
        ) from exc


# ============================================================
# VALIDATION
# ============================================================


def validate_resolution(
    resolution: Resolution,
    source_episodes: dict[str, dict],
) -> None:

    if (
        resolution.episode_id
        not in source_episodes
    ):

        raise RuntimeError(
            "Agent returned unknown episode: "
            f"{resolution.episode_id}"
        )

    if (
        resolution.canonical_date
        is not None
    ):

        parts = (
            resolution.canonical_date
            .split("-")
        )

        if len(parts) != 3:
            raise RuntimeError(
                "Invalid date format: "
                f"{resolution.canonical_date}"
            )

        if any(
            not part.isdigit()
            for part in parts
        ):
            raise RuntimeError(
                "Invalid date format: "
                f"{resolution.canonical_date}"
            )

    if (
        resolution.decision
        == "unresolved"
        and not resolution.requires_human_review
    ):

        raise RuntimeError(
            "Unresolved result must require "
            "human review."
        )


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:

        print(
            "GEMINI_API_KEY environment variable "
            "is not set.",
            file=sys.stderr,
        )

        return 1

    try:

        data = load_json(
            INPUT_FILE
        )

    except (
        FileNotFoundError,
        json.JSONDecodeError,
    ) as exc:

        print(
            f"[ERROR] {exc}",
            file=sys.stderr,
        )

        return 1

    conflicts = collect_conflicts(
        data
    )

    if not conflicts:

        print(
            "No date conflicts require resolution."
        )

        return 0

    print(
        f"Date conflicts to resolve: "
        f"{len(conflicts)}"
    )

    source_episodes = {
        episode[
            "episode_id"
        ]: episode
        for episode
        in data["episodes"]
    }

    try:

        client = genai.Client(
            api_key=api_key
        )

    except Exception as exc:

        print(
            f"[ERROR] Could not initialize Gemini client: "
            f"{exc}",
            file=sys.stderr,
        )

        return 1

    all_resolutions: list[
        Resolution
    ] = []

    total_batches = (
        len(conflicts)
        + BATCH_SIZE
        - 1
    ) // BATCH_SIZE

    for batch_index in range(
        total_batches
    ):

        start = (
            batch_index
            * BATCH_SIZE
        )

        end = min(
            start + BATCH_SIZE,
            len(conflicts),
        )

        batch = conflicts[
            start:end
        ]

        print()
        print(
            f"[AGENT] Batch "
            f"{batch_index + 1}/"
            f"{total_batches} "
            f"({len(batch)} episodes)"
        )

        try:

            result = resolve_batch(
                client,
                batch,
            )

        except Exception as exc:

            print(
                f"[ERROR] Agent failed: "
                f"{exc}",
                file=sys.stderr,
            )

            return 1

        returned_ids = {
            resolution.episode_id
            for resolution
            in result.resolutions
        }

        expected_ids = {
            episode[
                "episode_id"
            ]
            for episode
            in batch
        }

        if returned_ids != expected_ids:

            missing = sorted(
                expected_ids
                - returned_ids
            )

            extra = sorted(
                returned_ids
                - expected_ids
            )

            print(
                "[ERROR] Agent response "
                "does not match batch.",
                file=sys.stderr,
            )

            print(
                f"Missing: {missing}",
                file=sys.stderr,
            )

            print(
                f"Extra: {extra}",
                file=sys.stderr,
            )

            return 1

        for resolution in (
            result.resolutions
        ):

            try:

                validate_resolution(
                    resolution,
                    source_episodes,
                )

            except RuntimeError as exc:

                print(
                    f"[ERROR] Invalid agent result: "
                    f"{exc}",
                    file=sys.stderr,
                )

                return 1

            all_resolutions.append(
                resolution
            )

        time.sleep(
            API_DELAY_SECONDS
        )

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    accepted = sum(
        1
        for result in all_resolutions
        if result.decision
        in {
            "accept_source_date",
            "accept_consensus",
            "accept_external_date",
        }
    )

    unresolved = sum(
        1
        for result in all_resolutions
        if result.decision
        == "unresolved"
    )

    human_review = sum(
        1
        for result in all_resolutions
        if result.requires_human_review
    )

    output = {
        "agent_version": "0.1.0",

        "model": MODEL_NAME,

        "created_at":
            __import__(
                "datetime"
            )
            .datetime.now(
                __import__(
                    "datetime"
                ).timezone.utc
            )
            .isoformat(),

        "input_file":
            str(
                INPUT_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),

        "summary": {
            "conflicts": len(
                conflicts
            ),

            "resolved": accepted,

            "unresolved": unresolved,

            "human_review":
                human_review,
        },

        "resolutions": [
            result.model_dump()
            for result
            in all_resolutions
        ],
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "=" * 60
    )

    print(
        "CONFLICT RESOLUTION COMPLETE"
    )

    print(
        "=" * 60
    )

    print(
        f"Conflicts:       {len(conflicts)}"
    )

    print(
        f"Resolved:        {accepted}"
    )

    print(
        f"Unresolved:      {unresolved}"
    )

    print(
        f"Human review:    {human_review}"
    )

    print()

    print(
        f"Output: {OUTPUT_FILE}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())