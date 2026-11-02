import sqlite3
from pathlib import Path


DB = Path("database/dubbing.db")


def main() -> None:
    conn = sqlite3.connect(DB)

    query = """
    SELECT
        e.absolute_number,
        e.episode_id,
        e.title_original,

        MAX(
            CASE
                WHEN s.source_name = 'Wikipedia'
                THEN r.air_date_raw
            END
        ) AS wikipedia_date,

        MAX(
            CASE
                WHEN s.source_name = 'epguides'
                THEN r.air_date_raw
            END
        ) AS epguides_date,

        GROUP_CONCAT(
            CASE
                WHEN s.source_name = 'TheTVDB'
                THEN r.air_date_raw
            END,
            ' | '
        ) AS thetvdb_dates

    FROM episodes e

    JOIN episode_source_records r
        ON r.episode_id = e.id

    JOIN sources s
        ON s.id = r.source_id

    GROUP BY e.id

    ORDER BY e.absolute_number
    """

    rows = conn.execute(query).fetchall()

    conflicts = 0

    print("DATE DIFFERENCES: Wikipedia vs epguides")
    print("=" * 100)

    for row in rows:
        absolute_number = row[0]
        episode_id = row[1]
        title = row[2]
        wiki = row[3]
        epguides = row[4]
        tvdb = row[5]

        if wiki != epguides:
            conflicts += 1

            print(
                f"#{absolute_number:02d} "
                f"{episode_id}"
            )
            print(f"  Title     : {title}")
            print(f"  Wikipedia : {wiki}")
            print(f"  epguides  : {epguides}")
            print(f"  TheTVDB   : {tvdb}")
            print()

    print("=" * 100)
    print(f"Conflicts: {conflicts}")
    print(f"Total episodes: {len(rows)}")

    conn.close()


if __name__ == "__main__":
    main()