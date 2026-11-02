from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "database" / "dubbing.db"


def seed_series(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO series (
            series_id,
            title_original,
            title_ru,
            description
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(series_id) DO UPDATE SET
            title_original = excluded.title_original,
            title_ru = excluded.title_ru,
            description = excluded.description,
            updated_at = CURRENT_TIMESTAMP;
        """,
        (
            "martin_mystery",
            "Martin Mystery",
            "Мартин Мистери",
            "Animated television series about teenage paranormal investigators Martin Mystery and Diana Lombard."
        ),
    )


def main() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}\n"
            "Run init_db.py first."
        )

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        seed_series(connection)
        connection.commit()

        row = connection.execute(
            """
            SELECT
                id,
                series_id,
                title_original,
                title_ru
            FROM series
            WHERE series_id = ?
            """,
            ("martin_mystery",),
        ).fetchone()

    print("Series seeded successfully:")
    print(f"  id:              {row[0]}")
    print(f"  series_id:       {row[1]}")
    print(f"  title_original:  {row[2]}")
    print(f"  title_ru:        {row[3]}")


if __name__ == "__main__":
    main()