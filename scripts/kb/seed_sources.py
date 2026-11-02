from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DB_FILE = ROOT / "database" / "dubbing.db"


SOURCES = [
    {
        "source_name": "TheTVDB",
        "source_type": "website",
        "url": "https://thetvdb.com/series/martin-mystery",
    },
    {
        "source_name": "IMDb",
        "source_type": "website",
        "url": "https://www.imdb.com/title/tt0346938/",
    },
    {
        "source_name": "Wikipedia",
        "source_type": "website",
        "url": "https://en.wikipedia.org/wiki/List_of_Martin_Mystery_episodes",
    },
    {
        "source_name": "epguides",
        "source_type": "website",
        "url": "https://epguides.com/MartinMystery/",
    },
]


def main() -> None:
    conn = sqlite3.connect(DB_FILE)

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN")

        for source in SOURCES:
            conn.execute(
                """
                INSERT INTO sources (
                    source_name,
                    source_type,
                    url
                )
                VALUES (?, ?, ?)
                ON CONFLICT(source_name, url)
                DO UPDATE SET
                    source_type = excluded.source_type
                """,
                (
                    source["source_name"],
                    source["source_type"],
                    source["url"],
                ),
            )

        conn.commit()

        print("Sources seeded successfully:")

        rows = conn.execute(
            """
            SELECT
                id,
                source_name,
                source_type,
                url
            FROM sources
            ORDER BY id
            """
        ).fetchall()

        for row in rows:
            print(
                f"  id: {row[0]:2d} | "
                f"{row[1]:10s} | "
                f"{row[3]}"
            )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()