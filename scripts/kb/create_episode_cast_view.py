
from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "database" / "dubbing.db"
SQL_PATH = ROOT / "scripts" / "kb" / "create_episode_cast_view.sql"


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    if not SQL_PATH.exists():
        raise FileNotFoundError(f"SQL file not found: {SQL_PATH}")

    sql = SQL_PATH.read_text(encoding="utf-8")

    conn = sqlite3.connect(DB_PATH)

    try:
        conn.executescript(sql)
        conn.commit()

        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM episode_cast
            """
        ).fetchone()

        total = row[0]

        print("=== EPISODE CAST VIEW ===")
        print()
        print("View created : episode_cast")
        print(f"Rows         : {total}")
        print()

        # Проверка количества эпизодов,
        # для которых вообще есть персонажи.
        episodes = conn.execute(
            """
            SELECT COUNT(DISTINCT episode_id)
            FROM episode_cast
            """
        ).fetchone()[0]

        print(f"Episodes with cast : {episodes}")

        # Распределение по ролям
        print()
        print("=== ROLE DISTRIBUTION ===")

        rows = conn.execute(
            """
            SELECT
                role_type,
                COUNT(*)
            FROM episode_cast
            GROUP BY role_type
            ORDER BY role_type
            """
        ).fetchall()

        for role, count in rows:
            print(f"{role:<18}: {count}")

        # Персонажи по количеству эпизодов
        print()
        print("=== CHARACTER COVERAGE ===")

        rows = conn.execute(
            """
            SELECT
                character_id,
                character_name_original,
                COUNT(DISTINCT episode_id) AS episode_count
            FROM episode_cast
            GROUP BY character_id, character_name_original
            ORDER BY episode_count DESC, character_name_original
            """
        ).fetchall()

        for character_id, name, count in rows:
            print(f"{character_id:<35} {name:<30} {count}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
