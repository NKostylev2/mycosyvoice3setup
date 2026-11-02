from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"

RELATIONSHIPS_FILE = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_relationships_main.json"
)


def get_character_id(
    conn: sqlite3.Connection,
    character_id: str,
) -> int:
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
            f"Character not found: {character_id}"
        )

    return row[0]


def main() -> None:
    data = json.loads(
        RELATIONSHIPS_FILE.read_text(
            encoding="utf-8"
        )
    )

    relationships = data.get(
        "relationships",
        []
    )

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        conn.execute("BEGIN")

        for relationship in relationships:

            character_a_id = get_character_id(
                conn,
                relationship["character_a"],
            )

            character_b_id = get_character_id(
                conn,
                relationship["character_b"],
            )

            conn.execute(
                """
                INSERT INTO character_relationships (
                    character_a_id,
                    character_b_id,
                    relationship_type,
                    description
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(
                    character_a_id,
                    character_b_id,
                    relationship_type
                )
                DO UPDATE SET
                    description = excluded.description
                """,
                (
                    character_a_id,
                    character_b_id,
                    relationship["relationship_type"],
                    relationship.get("description"),
                ),
            )

        conn.commit()

        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM character_relationships
            """
        ).fetchone()[0]

        print("[OK] Character relationships seeded")
        print()
        print(f"Relationships: {count}")
        print()

        rows = conn.execute(
            """
            SELECT
                a.name_original,
                r.relationship_type,
                b.name_original
            FROM character_relationships r
            JOIN characters a
                ON a.id = r.character_a_id
            JOIN characters b
                ON b.id = r.character_b_id
            ORDER BY a.id, b.id
            """
        ).fetchall()

        for row in rows:
            print(
                f"  {row[0]} "
                f"--[{row[1]}]--> "
                f"{row[2]}"
            )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()