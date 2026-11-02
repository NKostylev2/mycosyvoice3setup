from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "database" / "dubbing.db"


def main() -> None:
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")

        series = connection.execute(
            """
            SELECT id
            FROM series
            WHERE series_id = ?
            """,
            ("martin_mystery",),
        ).fetchone()

        if series is None:
            raise RuntimeError(
                "Martin Mystery is not seeded. "
                "Run seed.py first."
            )

        series_db_id = series[0]

        connection.execute(
            """
            INSERT INTO episodes (
                series_id,
                episode_id,
                absolute_number,
                season_number,
                episode_number,
                title_original,
                air_date,
                synopsis_short,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(episode_id) DO UPDATE SET
                title_original = excluded.title_original,
                air_date = excluded.air_date,
                synopsis_short = excluded.synopsis_short,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (
                series_db_id,
                "martin_mystery_001",
                1,
                1,
                1,
                "It Came from the Bog",
                "2003-10-01",
                (
                    "Martin, Diana and Java are sent to France "
                    "to investigate mysterious child disappearances "
                    "linked to the Bogeyman."
                ),
                "discovered",
            ),
        )

        connection.commit()

        row = connection.execute(
            """
            SELECT
                episode_id,
                absolute_number,
                season_number,
                episode_number,
                title_original,
                air_date,
                status
            FROM episodes
            WHERE episode_id = ?
            """,
            ("martin_mystery_001",),
        ).fetchone()

    print("Episode:")
    print(f"  ID:        {row[0]}")
    print(f"  Absolute:  {row[1]}")
    print(f"  Season:    {row[2]}")
    print(f"  Episode:   {row[3]}")
    print(f"  Title:     {row[4]}")
    print(f"  Air date:  {row[5]}")
    print(f"  Status:    {row[6]}")


if __name__ == "__main__":
    main()