from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"

INPUT_FILE = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_classification_input.json"
)

OUTPUT = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_classification_batch.json"
)

MAX_CONTEXTS_PER_CANDIDATE = 3


def compact_context(text: str, max_length: int = 1000) -> str:
    if not text:
        return ""

    text = " ".join(text.split())

    if len(text) <= max_length:
        return text

    return text[:max_length].rstrip() + "..."


def main() -> None:
    data = json.loads(
        INPUT_FILE.read_text(
            encoding="utf-8"
        )
    )

    source_candidates = data.get(
        "candidates",
        []
    )

    conn = sqlite3.connect(DB)

    # Получаем известные character_id.
    known_rows = conn.execute(
        """
        SELECT
            character_id,
            name_original
        FROM characters
        ORDER BY id
        """
    ).fetchall()

    known_characters = [
        {
            "character_id": row[0],
            "name_original": row[1],
        }
        for row in known_rows
    ]

    batch = []

    for candidate in source_candidates:

        contexts = []

        for context in candidate.get(
            "contexts",
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
                    "context": compact_context(
                        context.get(
                            "local_context",
                            ""
                        )
                    ),
                }
            )

            if len(contexts) >= MAX_CONTEXTS_PER_CANDIDATE:
                break

        batch.append(
            {
                "candidate_name": candidate[
                    "candidate_name"
                ],
                "mention_count": candidate[
                    "mention_count"
                ],
                "classification": None,
                "confidence": None,
                "canonical_name": None,
                "name_ru": None,
                "alias_of": None,
                "aliases": [],
                "reason": None,
                "contexts": contexts,
            }
        )

    output = {
        "schema_version": "0.2",

        "task": (
            "Classify named entities extracted from "
            "Martin Mystery episode synopses."
        ),

        "known_characters": known_characters,

        "classification_labels": [
            "PERSON",
            "CREATURE",
            "MONSTER",
            "SUPERNATURAL_ENTITY",
            "ORGANIZATION",
            "LOCATION",
            "OBJECT",
            "ALIAS",
            "FALSE_POSITIVE"
        ],

        "candidate_count": len(batch),

        "statistics": {
            "input_candidates":
                len(source_candidates),
            "output_candidates":
                len(batch),
            "total_contexts":
                sum(
                    len(item["contexts"])
                    for item in batch
                )
        },

        "candidates": batch
    }

    OUTPUT.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        "[OK] Character classification batch rebuilt"
    )
    print()
    print(
        f"Input candidates : {len(source_candidates)}"
    )
    print(
        f"Batch candidates : {len(batch)}"
    )
    print(
        "Contexts         : "
        f"{sum(len(item['contexts']) for item in batch)}"
    )
    print()

    print("Known characters:")
    for character in known_characters:
        print(
            f"  {character['character_id']:20s} "
            f"{character['name_original']}"
        )

    print()
    print("Candidates:")

    for item in batch:
        print(
            f"  {item['candidate_name']:35s} "
            f"mentions={item['mention_count']} "
            f"contexts={len(item['contexts'])}"
        )

    print()
    print(f"Output: {OUTPUT}")

    conn.close()


if __name__ == "__main__":
    main()