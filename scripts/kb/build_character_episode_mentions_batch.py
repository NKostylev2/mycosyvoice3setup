from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"

OUTPUT = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_episode_mentions_batch.json"
)

MAX_CONTEXTS_PER_CHARACTER = 10


def normalize(value: str) -> str:
    value = value.lower()
    value = value.replace("’", "'")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def make_context(
    synopsis: str,
    candidate_name: str,
) -> str:
    if not synopsis:
        return ""

    text = synopsis.strip()

    pos = normalize(text).find(
        normalize(candidate_name)
    )

    if pos == -1:
        return text[:1000]

    start = max(
        0,
        pos - 350,
    )

    end = min(
        len(text),
        pos + len(candidate_name) + 700,
    )

    context = text[start:end]

    return re.sub(
        r"\s+",
        " ",
        context,
    ).strip()


def main() -> None:
    conn = sqlite3.connect(DB)

    # ------------------------------------------------------------
    # Characters
    # ------------------------------------------------------------

    character_rows = conn.execute(
        """
        SELECT
            id,
            character_id,
            name_original,
            name_ru
        FROM characters
        ORDER BY id
        """
    ).fetchall()

    # ------------------------------------------------------------
    # Episodes
    # ------------------------------------------------------------

    episode_rows = conn.execute(
        """
        SELECT
            id,
            episode_id,
            absolute_number,
            title_original,
            synopsis_detailed
        FROM episodes
        ORDER BY absolute_number
        """
    ).fetchall()

    batch = []

    for (
        character_db_id,
        character_id,
        name_original,
        name_ru,
    ) in character_rows:

        mentions = []

        aliases = [
            row[0]
            for row in conn.execute(
                """
                SELECT alias
                FROM character_aliases
                WHERE character_id = ?
                """,
                (character_db_id,),
            ).fetchall()
        ]

        names_to_search = [
            name_original,
            *aliases,
        ]

        seen_episodes = set()

        for episode in episode_rows:

            (
                episode_db_id,
                episode_id,
                absolute_number,
                title_original,
                synopsis,
            ) = episode

            normalized_synopsis = normalize(
                synopsis or ""
            )

            matched_name = None

            for name in names_to_search:

                if not name:
                    continue

                if normalize(name) in normalized_synopsis:
                    matched_name = name
                    break

            if matched_name is None:
                continue

            if episode_id in seen_episodes:
                continue

            seen_episodes.add(
                episode_id
            )

            mentions.append(
                {
                    "episode_id": episode_id,
                    "absolute_number": absolute_number,
                    "episode_title": title_original,
                    "matched_name": matched_name,
                    "context": make_context(
                        synopsis or "",
                        matched_name,
                    ),
                }
            )

            if len(mentions) >= MAX_CONTEXTS_PER_CHARACTER:
                break

        batch.append(
            {
                "character_id": character_id,
                "name_original": name_original,
                "name_ru": name_ru,
                "aliases": aliases,
                "mention_candidates": mentions,
            }
        )

    output = {
        "schema_version": "0.1",

        "task": (
            "Determine character presence and role "
            "within Martin Mystery episodes."
        ),

        "role_types": [
            "PRIMARY",
            "APPEARS",
            "MENTIONED",
            "BACKGROUND",
            "FALSE_POSITIVE",
        ],

        "rules": [
            "Use only the supplied episode context.",
            "Do not invent appearances.",
            "PRIMARY means the character is a central participant in the episode.",
            "APPEARS means the character directly participates or appears.",
            "MENTIONED means the character is explicitly referenced but presence is not proven.",
            "BACKGROUND means incidental presence.",
            "FALSE_POSITIVE means the text match does not actually refer to this character.",
            "Do not infer appearance solely from a similar name.",
            "Use the matched context as evidence.",
            "confidence must be between 0.0 and 1.0.",
        ],

        "character_count": len(batch),

        "characters": batch,
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    total_candidates = sum(
        len(item["mention_candidates"])
        for item in batch
    )

    print(
        "[OK] Character-episode mention batch built"
    )
    print()
    print(
        f"Characters        : {len(batch)}"
    )
    print(
        f"Context candidates: {total_candidates}"
    )
    print()

    for item in batch:
        print(
            f"  {item['name_original']:30s} "
            f"candidates={len(item['mention_candidates'])}"
        )

    print()
    print(f"Output: {OUTPUT}")

    conn.close()


if __name__ == "__main__":
    main()