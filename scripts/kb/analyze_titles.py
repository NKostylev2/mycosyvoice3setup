from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict, Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"

OUTPUT = (
    ROOT
    / "knowledge"
    / "canonical"
    / "title_analysis.json"
)


def normalize_title(title: str | None) -> str | None:
    """
    Normalizes cosmetic title differences only.

    Examples:
        "It's Alive - Part 1"
        "It's Alive Part 1"
        "it's alive: part 1"

    become equivalent for comparison.
    """

    if not title:
        return None

    value = title.strip().lower()

    # Normalize apostrophes
    value = value.replace("’", "'")

    # Normalize ampersand
    value = value.replace("&", "and")

    # Replace punctuation with spaces
    value = re.sub(r"[-:–—_/]+", " ", value)

    # Remove remaining punctuation
    value = re.sub(r"[^\w\s']", " ", value, flags=re.UNICODE)

    # Collapse whitespace
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def source_language(source_name: str) -> str:
    if source_name == "TheTVDB":
        return "fr"

    if source_name in ("Wikipedia", "epguides"):
        return "en"

    return "unknown"


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    query = """
    SELECT
        e.id AS episode_db_id,
        e.episode_id,
        e.absolute_number,
        e.season_number,
        e.episode_number,

        e.title_original AS canonical_title_en,
        e.title_alt AS canonical_title_fr,

        s.source_name,
        r.title_original AS source_title,
        r.season_number AS source_season,
        r.episode_number AS source_episode,
        r.absolute_number AS source_absolute,
        r.source_record_id,
        r.confidence

    FROM episodes e

    JOIN episode_source_records r
        ON r.episode_id = e.id

    JOIN sources s
        ON s.id = r.source_id

    ORDER BY
        e.absolute_number,
        s.source_name,
        r.id
    """

    rows = conn.execute(query).fetchall()

    by_episode = defaultdict(
        lambda: {
            "episode_id": None,
            "absolute_number": None,
            "season_number": None,
            "episode_number": None,
            "canonical_title_en": None,
            "canonical_title_fr": None,
            "sources": defaultdict(list),
        }
    )

    for row in rows:
        episode = by_episode[row["episode_id"]]

        episode["episode_id"] = row["episode_id"]
        episode["absolute_number"] = row["absolute_number"]
        episode["season_number"] = row["season_number"]
        episode["episode_number"] = row["episode_number"]
        episode["canonical_title_en"] = row["canonical_title_en"]
        episode["canonical_title_fr"] = row["canonical_title_fr"]

        episode["sources"][row["source_name"]].append(
            {
                "source_title": row["source_title"],
                "source_season": row["source_season"],
                "source_episode": row["source_episode"],
                "source_absolute": row["source_absolute"],
                "source_record_id": row["source_record_id"],
                "confidence": row["confidence"],
            }
        )

    analysis = []

    counters = Counter()

    for episode in by_episode.values():

        source_titles = {}

        for source_name, records in episode["sources"].items():

            titles = []

            for record in records:

                title = record["source_title"]

                if not title:
                    continue

                normalized = normalize_title(title)

                if normalized is None:
                    continue

                titles.append(
                    {
                        "raw": title,
                        "normalized": normalized,
                        "language": source_language(
                            source_name
                        ),
                        "source_record_id": record[
                            "source_record_id"
                        ],
                        "source_season": record[
                            "source_season"
                        ],
                        "source_episode": record[
                            "source_episode"
                        ],
                    }
                )

            source_titles[source_name] = titles

        # --------------------------------------------------------
        # ENGLISH SOURCES
        # --------------------------------------------------------

        english_values = {}

        for source_name in ("Wikipedia", "epguides"):

            titles = source_titles.get(
                source_name,
                [],
            )

            if titles:
                english_values[source_name] = sorted(
                    {
                        title["normalized"]
                        for title in titles
                    }
                )

        # --------------------------------------------------------
        # Canonical EN
        # --------------------------------------------------------

        canonical_en = episode[
            "canonical_title_en"
        ]

        canonical_en_normalized = normalize_title(
            canonical_en
        )

        english_matches = {}

        for source_name, values in english_values.items():

            english_matches[source_name] = (
                canonical_en_normalized in values
                if canonical_en_normalized
                else False
            )

        # --------------------------------------------------------
        # Classify English title consistency
        # --------------------------------------------------------

        unique_english_titles = set()

        for values in english_values.values():
            unique_english_titles.update(values)

        if not unique_english_titles:
            english_category = "NO_ENGLISH_SOURCE_TITLE"

        elif len(unique_english_titles) == 1:
            english_category = "ENGLISH_UNANIMOUS"

        elif canonical_en_normalized in unique_english_titles:
            english_category = (
                "ENGLISH_VARIANT_OR_SOURCE_DISAGREEMENT"
            )

        else:
            english_category = (
                "ENGLISH_CANONICAL_NOT_IN_SOURCES"
            )

        # --------------------------------------------------------
        # French source variants
        # --------------------------------------------------------

        french_titles = source_titles.get(
            "TheTVDB",
            [],
        )

        unique_french = sorted(
            {
                title["raw"]
                for title in french_titles
            }
        )

        if not french_titles:
            french_category = "NO_FRENCH_SOURCE_TITLE"

        elif len(unique_french) == 1:
            french_category = "FRENCH_SINGLE"

        else:
            french_category = "FRENCH_SOURCE_VARIANTS"

        # --------------------------------------------------------
        # Canonical French consistency
        # --------------------------------------------------------

        canonical_fr = episode[
            "canonical_title_fr"
        ]

        canonical_fr_present = (
            canonical_fr in unique_french
            if canonical_fr
            else False
        )

        # --------------------------------------------------------
        # Overall category
        # --------------------------------------------------------

        if (
            english_category == "ENGLISH_UNANIMOUS"
            and french_category != "FRENCH_SOURCE_VARIANTS"
        ):
            overall = "CLEAN"

        elif french_category == "FRENCH_SOURCE_VARIANTS":
            overall = "REVIEW_FRENCH_VARIANTS"

        else:
            overall = "REVIEW_ENGLISH"

        counters[overall] += 1
        counters[english_category] += 1
        counters[french_category] += 1

        analysis.append(
            {
                "episode_id": episode["episode_id"],
                "absolute_number": episode[
                    "absolute_number"
                ],
                "season_number": episode[
                    "season_number"
                ],
                "episode_number": episode[
                    "episode_number"
                ],

                "canonical_title_en": canonical_en,
                "canonical_title_en_normalized":
                    canonical_en_normalized,

                "canonical_title_fr": canonical_fr,

                "english_category": english_category,
                "english_matches_canonical":
                    english_matches,

                "french_category": french_category,
                "canonical_french_present":
                    canonical_fr_present,

                "source_titles": {
                    source: titles
                    for source, titles in sorted(
                        source_titles.items()
                    )
                },

                "unique_english_titles": sorted(
                    unique_english_titles
                ),

                "unique_french_titles": unique_french,

                "overall_category": overall,
            }
        )

    analysis.sort(
        key=lambda item: item["absolute_number"]
    )

    output = {
        "schema_version": "0.1",
        "episode_count": len(analysis),
        "statistics": dict(counters),
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

    print("[OK] Title analysis complete")
    print()
    print(f"Episodes: {len(analysis)}")
    print()

    print("Overall:")
    for category, count in counters.items():
        if category in (
            "CLEAN",
            "REVIEW_FRENCH_VARIANTS",
            "REVIEW_ENGLISH",
        ):
            print(
                f"  {category:34s}: {count}"
            )

    print()
    print("English:")
    print(
        f"  ENGLISH_UNANIMOUS                   : "
        f"{counters['ENGLISH_UNANIMOUS']}"
    )
    print(
        f"  ENGLISH_VARIANT_OR_SOURCE_DISAGREEMENT: "
        f"{counters['ENGLISH_VARIANT_OR_SOURCE_DISAGREEMENT']}"
    )
    print(
        f"  ENGLISH_CANONICAL_NOT_IN_SOURCES    : "
        f"{counters['ENGLISH_CANONICAL_NOT_IN_SOURCES']}"
    )
    print(
        f"  NO_ENGLISH_SOURCE_TITLE              : "
        f"{counters['NO_ENGLISH_SOURCE_TITLE']}"
    )

    print()
    print("French:")
    print(
        f"  FRENCH_SINGLE                        : "
        f"{counters['FRENCH_SINGLE']}"
    )
    print(
        f"  FRENCH_SOURCE_VARIANTS              : "
        f"{counters['FRENCH_SOURCE_VARIANTS']}"
    )
    print(
        f"  NO_FRENCH_SOURCE_TITLE               : "
        f"{counters['NO_FRENCH_SOURCE_TITLE']}"
    )

    print()
    print("=" * 110)
    print("EPISODES REQUIRING REVIEW")
    print("=" * 110)

    review_count = 0

    for item in analysis:

        if item["overall_category"] == "CLEAN":
            continue

        review_count += 1

        print()
        print(
            f"#{item['absolute_number']:02d} "
            f"{item['episode_id']} "
            f"{item['canonical_title_en']}"
        )

        print(
            f"  Overall       : "
            f"{item['overall_category']}"
        )

        print(
            f"  EN category   : "
            f"{item['english_category']}"
        )

        print(
            f"  FR category   : "
            f"{item['french_category']}"
        )

        print(
            f"  Canonical FR  : "
            f"{item['canonical_title_fr']}"
        )

        for source, titles in item[
            "source_titles"
        ].items():

            raw_titles = [
                title["raw"]
                for title in titles
            ]

            print(
                f"  {source:10s}: "
                f"{' | '.join(raw_titles)}"
            )

    print()
    print(
        f"Review episodes: {review_count}"
    )
    print()
    print(f"Report: {OUTPUT}")

    conn.close()


if __name__ == "__main__":
    main()