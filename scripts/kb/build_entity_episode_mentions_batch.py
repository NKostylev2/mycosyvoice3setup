from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"

ENTITY_RESULTS = (
    ROOT
    / "knowledge"
    / "canonical"
    / "entity_canonicalization_results.json"
)

CLASSIFICATION_BATCH = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_classification_batch.json"
)

OUTPUT = (
    ROOT
    / "knowledge"
    / "canonical"
    / "entity_episode_mentions_batch.json"
)


MAX_EPISODE_CONTEXTS = 10


def normalize_name(value: str) -> str:
    value = value.lower()
    value = value.replace("’", "'")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def make_context(
    synopsis: str,
    name: str,
) -> str:
    if not synopsis:
        return ""

    text = synopsis.strip()

    pos = normalize_name(text).find(
        normalize_name(name)
    )

    if pos == -1:
        return text[:1000]

    start = max(
        0,
        pos - 300,
    )

    end = min(
        len(text),
        pos + len(name) + 700,
    )

    return re.sub(
        r"\s+",
        " ",
        text[start:end],
    ).strip()


def main() -> None:
    entity_data = json.loads(
        ENTITY_RESULTS.read_text(
            encoding="utf-8"
        )
    )

    entities = [
        item
        for item in entity_data["results"]
        if item["decision"] != "FALSE_POSITIVE"
        and item["entity_type"] != "FALSE_POSITIVE"
    ]

    classification_batch = json.loads(
        CLASSIFICATION_BATCH.read_text(
            encoding="utf-8"
        )
    )

    # Кандидаты уже содержат episode contexts.
    context_by_name = {
        item["candidate_name"]: item.get(
            "contexts",
            []
        )
        for item in classification_batch[
            "candidates"
        ]
    }

    conn = sqlite3.connect(DB)

    rows = conn.execute(
        """
        SELECT
            episode_id,
            absolute_number,
            title_original,
            synopsis_detailed
        FROM episodes
        ORDER BY absolute_number
        """
    ).fetchall()

    episodes = {
        row[0]: {
            "episode_id": row[0],
            "absolute_number": row[1],
            "title_original": row[2],
            "synopsis": row[3] or "",
        }
        for row in rows
    }

    batch = []

    for entity in entities:

        candidate_name = entity[
            "candidate_name"
        ]

        canonical_name = entity.get(
            "canonical_name"
        )

        if not canonical_name:
            canonical_name = candidate_name

        candidate_contexts = (
            context_by_name.get(
                candidate_name,
                []
            )
        )

        mentions = []

        seen_episodes = set()

        for context in candidate_contexts:

            episode_id = context[
                "episode_id"
            ]

            if episode_id in seen_episodes:
                continue

            episode = episodes.get(
                episode_id
            )

            if episode is None:
                continue

            seen_episodes.add(
                episode_id
            )

            mentions.append(
                {
                    "episode_id": episode_id,
                    "absolute_number": episode[
                        "absolute_number"
                    ],
                    "episode_title": episode[
                        "title_original"
                    ],
                    "context": context.get(
                        "local_context",
                        context.get(
                            "context",
                            ""
                        )
                    ),
                }
            )

            if len(mentions) >= MAX_EPISODE_CONTEXTS:
                break

        batch.append(
            {
                "entity_candidate_name": candidate_name,
                "canonical_name": canonical_name,
                "entity_type": entity[
                    "entity_type"
                ],
                "classification_confidence": entity[
                    "confidence"
                ],
                "mentions": mentions,
            }
        )

    output = {
        "schema_version": "0.1",

        "task": (
            "Determine which episodes contain meaningful "
            "mentions or appearances of canonical entities."
        ),

        "mention_types": [
            "PRIMARY",
            "APPEARS",
            "MENTIONED",
            "BACKGROUND",
            "FALSE_POSITIVE"
        ],

        "rules": [
            "Use only the supplied episode context.",
            "Do not invent episode appearances.",
            "An entity mentioned by name in a synopsis is a valid MENTIONED.",
            "An entity central to the episode should be PRIMARY.",
            "An entity physically appearing but not central should be APPEARS.",
            "If the evidence is only incidental, use BACKGROUND.",
            "If the candidate is not actually an entity in the context, use FALSE_POSITIVE.",
            "confidence must be between 0.0 and 1.0.",
        ],

        "candidate_count": len(batch),

        "candidates": batch,
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
        "[OK] Entity-episode mention batch built"
    )
    print()
    print(
        f"Entities: {len(batch)}"
    )

    total_mentions = sum(
        len(item["mentions"])
        for item in batch
    )

    print(
        f"Contexts: {total_mentions}"
    )

    print()
    for item in batch:
        print(
            f"  {item['canonical_name']:40s} "
            f"type={item['entity_type']:22s} "
            f"episodes={len(item['mentions'])}"
        )

    print()
    print(
        f"Output: {OUTPUT}"
    )

    conn.close()


if __name__ == "__main__":
    main()