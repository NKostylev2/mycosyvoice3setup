from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "database" / "dubbing.db"
OUTPUT = ROOT / "knowledge" / "canonical" / "air_date_analysis.json"


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    query = """
    SELECT
        e.id AS episode_db_id,
        e.episode_id,
        e.absolute_number,
        e.title_original,

        s.source_name,
        r.air_date_raw,
        r.season_number AS source_season,
        r.episode_number AS source_episode

    FROM episodes e

    JOIN episode_source_records r
        ON r.episode_id = e.id

    JOIN sources s
        ON s.id = r.source_id

    WHERE r.air_date_raw IS NOT NULL
      AND TRIM(r.air_date_raw) <> ''

    ORDER BY
        e.absolute_number,
        s.source_name,
        r.id
    """

    rows = conn.execute(query).fetchall()

    episodes: dict[str, dict] = {}

    for row in rows:
        episode_id = row["episode_id"]

        if episode_id not in episodes:
            episodes[episode_id] = {
                "episode_id": episode_id,
                "absolute_number": row["absolute_number"],
                "title_original": row["title_original"],
                "sources": defaultdict(list),
            }

        episodes[episode_id]["sources"][
            row["source_name"]
        ].append(
            {
                "air_date_raw": row["air_date_raw"],
                "source_season": row["source_season"],
                "source_episode": row["source_episode"],
            }
        )

    analysis = []

    category_counter = Counter()

    for episode in episodes.values():

        source_dates = {}

        for source_name, records in episode["sources"].items():

            dates = sorted(
                {
                    get_normalized_date(record["air_date_raw"])
                    for record in records
                    if get_normalized_date(record["air_date_raw"])
                }
            )

            if dates:
                source_dates[source_name] = dates

        # Нормализованные даты всех источников.
        all_dates = []

        for dates in source_dates.values():
            all_dates.extend(dates)

        unique_dates = sorted(set(all_dates))

        # --------------------------------------------------------
        # Классификация
        # --------------------------------------------------------

        if len(unique_dates) == 1:
            category = "UNANIMOUS"

            consensus_date = unique_dates[0]
            consensus_sources = list(source_dates.keys())

        elif len(unique_dates) == 2:

            # Собираем голоса по источникам.
            votes = Counter()

            for source_name, dates in source_dates.items():

                # У одного источника может быть несколько записей.
                # Каждая уникальная дата считается присутствующей.
                for date in set(dates):
                    votes[date] += 1

            max_votes = max(votes.values())

            winners = sorted(
                date
                for date, count in votes.items()
                if count == max_votes
            )

            if max_votes >= 2 and len(winners) == 1:
                category = "MAJORITY_2_TO_1_OR_MORE"
                consensus_date = winners[0]

                consensus_sources = [
                    source_name
                    for source_name, dates in source_dates.items()
                    if consensus_date in dates
                ]

            else:
                category = "TWO_DATE_CONFLICT"
                consensus_date = None
                consensus_sources = []

        else:
            category = "THREE_OR_MORE_DATES"
            consensus_date = None
            consensus_sources = []

        category_counter[category] += 1

        analysis.append(
            {
                "episode_id": episode["episode_id"],
                "absolute_number": episode["absolute_number"],
                "title_original": episode["title_original"],
                "category": category,
                "consensus_date": consensus_date,
                "consensus_sources": sorted(consensus_sources),
                "source_dates": {
                    source: dates
                    for source, dates in sorted(
                        source_dates.items()
                    )
                },
            }
        )

    analysis.sort(
        key=lambda item: item["absolute_number"]
    )

    output = {
        "schema_version": "0.1",
        "episode_count": len(analysis),
        "categories": dict(category_counter),
        "episodes": analysis,
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

    # ------------------------------------------------------------
    # Console report
    # ------------------------------------------------------------

    print("[OK] Air-date analysis complete")
    print()
    print(f"Episodes: {len(analysis)}")
    print()

    print("Categories:")
    for category, count in category_counter.most_common():
        print(f"  {category:28s}: {count}")

    print()
    print("=" * 110)
    print("EPISODES REQUIRING REVIEW")
    print("=" * 110)

    for item in analysis:

        if item["category"] == "UNANIMOUS":
            continue

        n = item["absolute_number"]

        print()
        print(
            f"#{n:02d} "
            f"{item['episode_id']} "
            f"{item['title_original']}"
        )

        print(
            f"  Category  : {item['category']}"
        )

        print(
            f"  Consensus : "
            f"{item['consensus_date'] or 'NONE'}"
        )

        for source, dates in item["source_dates"].items():
            print(
                f"  {source:10s}: "
                f"{', '.join(dates)}"
            )

    conn.close()

    print()
    print("=" * 110)
    print(f"Report: {OUTPUT}")


def get_normalized_date(value: str | None) -> str | None:
    """
    Нормализация дат, уже существующих в episode_source_records.
    Здесь дублируем минимально необходимую логику,
    чтобы отчёт был автономным.
    """

    if not value:
        return None

    from datetime import datetime

    value = value.strip()

    formats = (
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
        "%m/%d/%Y",
    )

    for fmt in formats:
        try:
            return datetime.strptime(
                value,
                fmt,
            ).date().isoformat()
        except ValueError:
            continue

    return None


if __name__ == "__main__":
    main()