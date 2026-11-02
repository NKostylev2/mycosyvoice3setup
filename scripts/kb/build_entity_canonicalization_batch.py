from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"

RESULT_FILE = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_classification_results.json"
)

REVIEW_FILE = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_classification_review.json"
)

OUTPUT = (
    ROOT
    / "knowledge"
    / "canonical"
    / "entity_canonicalization_batch.json"
)

ENTITY_TYPES = {
    "CREATURE",
    "MONSTER",
    "SUPERNATURAL_ENTITY",
    "ORGANIZATION",
    "LOCATION",
    "OBJECT",
}


def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def main() -> None:
    classification = load_json(
        RESULT_FILE
    )

    review = load_json(
        REVIEW_FILE
    )

    # ------------------------------------------------------------
    # Apply review overrides
    # ------------------------------------------------------------

    review_map = {
        item["candidate_name"]: item
        for item in review.get(
            "reviews",
            []
        )
    }

    candidates = []

    for item in classification.get(
        "results",
        []
    ):

        candidate_name = item[
            "candidate_name"
        ]

        current_classification = item[
            "classification"
        ]

        current_confidence = item[
            "confidence"
        ]

        if candidate_name in review_map:

            reviewed = review_map[
                candidate_name
            ]

            current_classification = reviewed[
                "new_classification"
            ]

            current_confidence = reviewed[
                "new_confidence"
            ]

        if current_classification not in ENTITY_TYPES:
            continue

        candidates.append(
            {
                "candidate_name": candidate_name,
                "classification": current_classification,
                "confidence": current_confidence,
                "canonical_name": item.get(
                    "canonical_name"
                ),
                "name_ru": item.get(
                    "name_ru"
                ),
                "reason": item.get(
                    "reason"
                ),
                "reviewed": (
                    candidate_name in review_map
                ),
            }
        )

    # ------------------------------------------------------------
    # Get contexts from SQLite
    # ------------------------------------------------------------

    conn = sqlite3.connect(DB)

    episodes = {
        row[0]: {
            "episode_id": row[0],
            "absolute_number": row[1],
            "title_original": row[2],
            "synopsis": row[3] or "",
        }
        for row in conn.execute(
            """
            SELECT
                episode_id,
                absolute_number,
                title_original,
                synopsis_detailed
            FROM episodes
            ORDER BY absolute_number
            """
        )
    }

    # Candidate -> contexts
    classification_batch = load_json(
        ROOT
        / "knowledge"
        / "canonical"
        / "character_classification_batch.json"
    )

    context_map = {
        item["candidate_name"]: item.get(
            "contexts",
            []
        )
        for item in classification_batch.get(
            "candidates",
            []
        )
    }

    output_candidates = []

    for candidate in candidates:

        name = candidate[
            "candidate_name"
        ]

        contexts = []

        for context in context_map.get(
            name,
            []
        ):

            contexts.append(
                {
                    "episode_id": context[
                        "episode_id"
                    ],
                    "absolute_number": context[
                        "absolute_number"
                    ],
                    "episode_title": context[
                        "episode_title"
                    ],
                    "context": context.get(
                        "local_context",
                        context.get(
                            "context",
                            "",
                        ),
                    ),
                }
            )

        output_candidates.append(
            {
                "candidate_name": name,

                "initial_type": candidate[
                    "classification"
                ],

                "initial_confidence": candidate[
                    "confidence"
                ],

                "initial_canonical_name": candidate.get(
                    "canonical_name"
                ),

                "initial_name_ru": candidate.get(
                    "name_ru"
                ),

                "classification_reason": candidate.get(
                    "reason"
                ),

                "contexts": contexts,
            }
        )

    output = {
        "schema_version": "0.1",

        "task": (
            "Canonicalize non-character named entities "
            "from Martin Mystery episode synopses."
        ),

        "entity_types": [
            "CREATURE",
            "MONSTER",
            "SUPERNATURAL_ENTITY",
            "ORGANIZATION",
            "LOCATION",
            "OBJECT",
        ],

        "rules": [
            "Use only evidence from the supplied contexts.",
            "Do not invent entities.",
            "Preserve candidate_name exactly.",
            "Determine whether the candidate is actually a named entity.",
            "Generic nouns and accidental capitalized words should become FALSE_POSITIVE.",
            "Do not create entities for ordinary geographic mentions unless they are useful named entities in the series knowledge base.",
            "Do not convert every place mentioned in a synopsis into a knowledge entity.",
            "For a named monster use MONSTER.",
            "For a named supernatural being use SUPERNATURAL_ENTITY.",
            "For a named organization, institute, society or agency use ORGANIZATION.",
            "For a named place, building, region or geographic entity use LOCATION.",
            "For a named artifact or physical item use OBJECT.",
            "For a living non-human named entity that is not functioning primarily as a monster use CREATURE.",
            "When uncertain, use FALSE_POSITIVE rather than inventing an entity.",
            "confidence must be between 0.0 and 1.0.",
        ],

        "output_schema": {
            "candidate_name": "string",
            "decision": "KEEP|FALSE_POSITIVE|RECLASSIFY",
            "entity_type": "CREATURE|MONSTER|SUPERNATURAL_ENTITY|ORGANIZATION|LOCATION|OBJECT|FALSE_POSITIVE",
            "confidence": "number between 0 and 1",
            "canonical_name": "string or null",
            "name_ru": "string or null",
            "aliases": "array of strings",
            "description": "string",
            "reason": "string"
        },

        "candidate_count": len(
            output_candidates
        ),

        "candidates": output_candidates,
    }

    OUTPUT.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "[OK] Entity canonicalization batch built"
    )
    print()
    print(
        f"Candidates: {len(output_candidates)}"
    )

    for item in output_candidates:
        print(
            f"  {item['candidate_name']:35s} "
            f"type={item['initial_type']:24s} "
            f"confidence={item['initial_confidence']}"
        )

    print()
    print(f"Output: {OUTPUT}")

    conn.close()


if __name__ == "__main__":
    main()