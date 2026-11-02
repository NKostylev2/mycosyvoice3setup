from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "database" / "dubbing.db"


SOURCES = [
    {
        "name": "TheTVDB",
        "type": "episode_database",
        "url": "https://thetvdb.com/series/martin-mystery",
    },
    {
        "name": "IMDb",
        "type": "episode_database",
        "url": "https://www.imdb.com/title/tt0374419/episodes/",
    },
    {
        "name": "Wikipedia",
        "type": "encyclopedia",
        "url": "https://en.wikipedia.org/wiki/List_of_Martin_Mystery_episodes",
    },
    {
        "name": "epguides",
        "type": "episode_database",
        "url": "https://epguides.com/MartinMystery/",
    },
]


def main() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")

        for source in SOURCES:
            connection.execute(
                """
                INSERT INTO sources (
                    source_name,
                    source_type,
                    url
                )
                VALUES (?, ?, ?)
                ON CONFLICT(source_name, url) DO NOTHING;
                """,
                (
                    source["name"],
                    source["type"],
                    source["url"],
                ),
            )

        connection.commit()

        rows = connection.execute(
            """
            SELECT id, source_name, source_type, url
            FROM sources
            ORDER BY id;
            """
        ).fetchall()

    print("Registered sources:")
    for row in rows:
        print(f"  [{row[0]}] {row[1]} ({row[2]})")
        print(f"      {row[3]}")


if __name__ == "__main__":
    main()