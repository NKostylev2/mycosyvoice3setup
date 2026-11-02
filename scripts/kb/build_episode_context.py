
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB_PATH = ROOT / "database" / "dubbing.db"
OUTPUT_DIR = ROOT / "knowledge" / "canonical" / "episode_context"


def safe_json_load(value: str | None) -> dict | list | None:
    if not value:
        return None

    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        episodes = conn.execute(
            """
            SELECT
                id,
                episode_id,
                absolute_number,
                season_number,
                episode_number,
                title_original,
                title_ru,
                air_date
            FROM episodes
            ORDER BY absolute_number
            """
        ).fetchall()

        if len(episodes) != 66:
            raise ValueError(
                f"Expected 66 episodes, found {len(episodes)}"
            )

        generated = 0
        character_mentions_total = 0
        entity_mentions_total = 0

        for episode in episodes:

            episode_db_id = episode["id"]

            # ------------------------------------------------
            # Character mentions
            # ------------------------------------------------

            character_rows = conn.execute(
                """
                SELECT
                    c.character_id,
                    c.name_original,
                    c.name_ru,
                    cem.role_type,
                    cem.confidence,
                    cem.evidence
                FROM character_episode_mentions cem
                JOIN characters c
                    ON c.id = cem.character_id
                WHERE cem.episode_id = ?
                ORDER BY
                    CASE cem.role_type
                        WHEN 'PRIMARY' THEN 1
                        WHEN 'APPEARS' THEN 2
                        WHEN 'MENTIONED' THEN 3
                        WHEN 'BACKGROUND' THEN 4
                        ELSE 99
                    END,
                    c.name_original
                """,
                (episode_db_id,),
            ).fetchall()

            characters = []

            for row in character_rows:
                characters.append(
                    {
                        "character_id": row["character_id"],
                        "name_original": row["name_original"],
                        "name_ru": row["name_ru"],
                        "role_type": row["role_type"],
                        "confidence": row["confidence"],
                        "evidence": row["evidence"],
                    }
                )

            # ------------------------------------------------
            # Entity mentions
            # ------------------------------------------------

            entity_rows = conn.execute(
                """
                SELECT
                    en.entity_id,
                    en.entity_type,
                    en.name_original,
                    en.name_ru,
                    en.description,
                    eem.mention_type,
                    eem.confidence,
                    eem.evidence
                FROM entity_episode_mentions eem
                JOIN entities en
                    ON en.id = eem.entity_id
                WHERE eem.episode_id = ?
                ORDER BY
                    en.entity_type,
                    en.name_original
                """,
                (episode_db_id,),
            ).fetchall()

            entities = []

            for row in entity_rows:
                entities.append(
                    {
                        "entity_id": row["entity_id"],
                        "entity_type": row["entity_type"],
                        "name_original": row["name_original"],
                        "name_ru": row["name_ru"],
                        "description": row["description"],
                        "mention_type": row["mention_type"],
                        "confidence": row["confidence"],
                        "evidence": row["evidence"],
                    }
                )

            # ------------------------------------------------
            # Build context
            # ------------------------------------------------

            context = {
                "schema_version": "1.0",
                "episode_id": episode["episode_id"],
                "absolute_number": episode["absolute_number"],
                "season_number": episode["season_number"],
                "episode_number": episode["episode_number"],
                "title_original": episode["title_original"],
                "title_ru": episode["title_ru"],
                "air_date": episode["air_date"],

                # IMPORTANT:
                # These are evidence-based mentions,
                # NOT a complete cast list.
                "character_mentions": characters,

                "entities": entities,

                "notes": [
                    "character_mentions are evidence-based "
                    "knowledge records, not an exhaustive cast list",
                    "actual speakers must be determined from "
                    "audio analysis and diarization"
                ]
            }

            # ------------------------------------------------
            # Save
            # ------------------------------------------------

            output_path = (
                OUTPUT_DIR
                / f"{episode['episode_id']}.json"
            )

            output_path.write_text(
                json.dumps(
                    context,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            generated += 1
            character_mentions_total += len(characters)
            entity_mentions_total += len(entities)

        print("=== EPISODE CONTEXT BUILD ===")
        print()
        print(f"Episodes generated      : {generated}")
        print(
            f"Character mentions      : "
            f"{character_mentions_total}"
        )
        print(
            f"Entity mentions         : "
            f"{entity_mentions_total}"
        )
        print(f"Output directory        : {OUTPUT_DIR}")
        print()
        print("BUILD PASSED")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
