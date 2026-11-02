from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"

CHARACTERS_FILE = (
    ROOT
    / "knowledge"
    / "canonical"
    / "characters_main.json"
)


def main() -> None:
    data = json.loads(
        CHARACTERS_FILE.read_text(
            encoding="utf-8"
        )
    )

    characters = data.get("characters", [])

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        conn.execute("BEGIN")

        character_db_ids: dict[str, int] = {}

        for character in characters:

            character_id = character["character_id"]

            conn.execute(
                """
                INSERT INTO characters (
                    character_id,
                    name_original,
                    name_ru,
                    description,
                    gender,
                    age_description,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(character_id)
                DO UPDATE SET
                    name_original = excluded.name_original,
                    name_ru = excluded.name_ru,
                    description = excluded.description,
                    gender = excluded.gender,
                    age_description = excluded.age_description,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    character_id,
                    character["name_original"],
                    character.get("name_ru"),
                    character.get("description"),
                    character.get("gender"),
                    character.get("age_description"),
                    character.get("status", "active"),
                ),
            )

            row = conn.execute(
                """
                SELECT id
                FROM characters
                WHERE character_id = ?
                """,
                (character_id,),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    f"Character not found after upsert: {character_id}"
                )

            character_db_id = row[0]

            character_db_ids[character_id] = character_db_id

            # ----------------------------------------------------
            # ALIASES
            # ----------------------------------------------------

            for alias in character.get("aliases", []):

                conn.execute(
                    """
                    INSERT INTO character_aliases (
                        character_id,
                        alias,
                        language
                    )
                    VALUES (?, ?, ?)
                    ON CONFLICT(character_id, alias, language)
                    DO NOTHING
                    """,
                    (
                        character_db_id,
                        alias["alias"],
                        alias.get("language", "en"),
                    ),
                )

        conn.commit()

        # --------------------------------------------------------
        # VALIDATION
        # --------------------------------------------------------

        character_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM characters
            WHERE character_id IN (
                'martin_mystery',
                'diana_lombard',
                'java',
                'billy',
                'mom'
            )
            """
        ).fetchone()[0]

        alias_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM character_aliases
            WHERE character_id IN (
                SELECT id
                FROM characters
                WHERE character_id IN (
                    'martin_mystery',
                    'diana_lombard',
                    'java',
                    'billy',
                    'mom'
                )
            )
            """
        ).fetchone()[0]

        print("[OK] Main characters seeded")
        print()
        print(f"Main characters : {character_count}")
        print(f"Aliases         : {alias_count}")
        print()

        rows = conn.execute(
            """
            SELECT
                c.character_id,
                c.name_original,
                c.name_ru,
                COUNT(a.id) AS aliases
            FROM characters c
            LEFT JOIN character_aliases a
                ON a.character_id = c.id
            WHERE c.character_id IN (
                'martin_mystery',
                'diana_lombard',
                'java',
                'billy',
                'mom'
            )
            GROUP BY c.id
            ORDER BY c.id
            """
        ).fetchall()

        for row in rows:
            print(
                f"  {row[0]:18s} "
                f"{row[1]:24s} "
                f"aliases={row[3]}"
            )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()