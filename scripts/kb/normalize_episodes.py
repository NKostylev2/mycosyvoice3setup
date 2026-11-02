from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

EPGUIDES_FILE = (
    PROJECT_ROOT
    / "knowledge"
    / "canonical"
    / "episodes_epguides.json"
)

THETVDB_FILE = (
    PROJECT_ROOT
    / "knowledge"
    / "canonical"
    / "episodes_thetvdb.json"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "knowledge"
    / "canonical"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "episodes_normalized.json"
)


EXPECTED_SEASONS = {
    1: 26,
    2: 14,
    3: 26,
}


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON in {path}: {exc}"
        ) from exc


def normalize_date(
    value: str | None,
) -> str | None:
    """
    Приводит дату к ISO YYYY-MM-DD.

    Поддерживаем форматы, которые уже встретились
    в наших источниках.
    """

    if not value:
        return None

    value = value.strip()

    # Уже ISO.
    try:
        parsed = datetime.strptime(
            value,
            "%Y-%m-%d",
        )

        return parsed.strftime(
            "%Y-%m-%d"
        )
    except ValueError:
        pass

    # TheTVDB:
    # September 15, 2004
    for fmt in (
        "%B %d, %Y",
        "%b %d, %Y",
    ):
        try:
            parsed = datetime.strptime(
                value,
                fmt,
            )

            return parsed.strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            continue

    # Иногда встречается дата внутри строки.
    match = re.search(
        r"\b"
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)"
        r"\s+\d{1,2},\s+\d{4}"
        r"\b",
        value,
        flags=re.I,
    )

    if match:
        try:
            parsed = datetime.strptime(
                match.group(0),
                "%B %d, %Y",
            )

            return parsed.strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            pass

    return None


def make_source_record(
    *,
    source: str,
    episode: dict,
) -> dict:

    return {
        "source": source,

        "title": episode.get(
            "title_original"
        ),

        "air_date": normalize_date(
            episode.get("air_date")
        ),

        "source_episode_id":
            episode.get("episode_id"),

        "source_url":
            episode.get(
                "source_url"
            ),

        "thetvdb_url":
            episode.get(
                "thetvdb_url"
            ),
    }


def choose_canonical_date(
    dates: dict[str, str | None],
) -> tuple[str | None, str]:

    available = {
        source: value
        for source, value in dates.items()
        if value is not None
    }

    if not available:
        return None, "none"

    unique_dates = set(
        available.values()
    )

    # Все источники согласны.
    if len(unique_dates) == 1:
        return (
            next(iter(unique_dates)),
            "consensus",
        )

    # Пока не разрешаем конфликт молча.
    return None, "conflict"


def build_episode(
    *,
    key: tuple[int, int],
    epguides: dict | None,
    thetvdb: dict | None,
) -> dict:

    season, episode_number = key

    absolute_number = None

    if epguides:
        absolute_number = epguides.get(
            "absolute_number"
        )

    # Если абсолютный номер есть только
    # в одном источнике — сохраняем его.
    if absolute_number is None:
        absolute_number = (
            epguides or {}
        ).get(
            "absolute_number"
        )

    dates = {
        "epguides": (
            normalize_date(
                epguides.get("air_date")
            )
            if epguides
            else None
        ),

        "thetvdb": (
            normalize_date(
                thetvdb.get("air_date")
            )
            if thetvdb
            else None
        ),
    }

    canonical_date, date_status = (
        choose_canonical_date(
            dates
        )
    )

    titles: dict[str, str] = {}

    if epguides:
        title = epguides.get(
            "title_original"
        )

        if title:
            titles["en"] = title

    if thetvdb:
        title = thetvdb.get(
            "title_original"
        )

        if title:
            titles["fr"] = title

    sources = []

    if epguides:
        sources.append(
            make_source_record(
                source="epguides",
                episode=epguides,
            )
        )

    if thetvdb:
        sources.append(
            make_source_record(
                source="thetvdb",
                episode=thetvdb,
            )
        )

    return {
        "episode_id": (
            f"martin_mystery_"
            f"{absolute_number:03d}"
            if absolute_number is not None
            else (
                f"martin_mystery_s"
                f"{season:02d}e"
                f"{episode_number:02d}"
            )
        ),

        "identity": {
            "absolute_number":
                absolute_number,

            "season_number":
                season,

            "episode_number":
                episode_number,
        },

        "titles": titles,

        "air_dates": dates,

        "canonical": {
            "air_date":
                canonical_date,

            "air_date_status":
                date_status,

            "title":
                titles.get("en"),
        },

        "sources": sources,
    }


def index_by_season_episode(
    data: dict,
) -> dict[tuple[int, int], dict]:

    result = {}

    for episode in data.get(
        "episodes",
        [],
    ):

        season = episode.get(
            "season_number"
        )

        number = episode.get(
            "episode_number"
        )

        if season is None or number is None:
            raise RuntimeError(
                "Episode without season/episode number."
            )

        key = (
            int(season),
            int(number),
        )

        if key in result:
            raise RuntimeError(
                f"Duplicate episode: {key}"
            )

        result[key] = episode

    return result


def validate_source(
    name: str,
    indexed: dict[tuple[int, int], dict],
) -> None:

    counts: dict[int, int] = {}

    for season, _ in indexed:
        counts[season] = (
            counts.get(season, 0) + 1
        )

    if len(indexed) != 66:
        raise RuntimeError(
            f"{name}: expected 66 episodes, "
            f"got {len(indexed)}."
        )

    if counts != EXPECTED_SEASONS:
        raise RuntimeError(
            f"{name}: invalid season "
            f"distribution: {counts}"
        )


def main() -> int:

    try:
        epguides_data = load_json(
            EPGUIDES_FILE
        )

        thetvdb_data = load_json(
            THETVDB_FILE
        )

        epguides = index_by_season_episode(
            epguides_data
        )

        thetvdb = index_by_season_episode(
            thetvdb_data
        )

        validate_source(
            "epguides",
            epguides,
        )

        validate_source(
            "thetvdb",
            thetvdb,
        )

    except (
        FileNotFoundError,
        RuntimeError,
    ) as exc:

        print(
            f"[ERROR] {exc}",
            file=sys.stderr,
        )

        return 1

    all_keys = sorted(
        set(epguides)
        | set(thetvdb)
    )

    normalized = []

    summary = {
        "total": len(all_keys),
        "both_sources": 0,
        "only_epguides": 0,
        "only_thetvdb": 0,
        "date_consensus": 0,
        "date_conflict": 0,
        "date_missing": 0,
    }

    for key in all_keys:

        epg = epguides.get(key)
        tvdb = thetvdb.get(key)

        if epg and tvdb:
            summary[
                "both_sources"
            ] += 1

        elif epg:
            summary[
                "only_epguides"
            ] += 1

        else:
            summary[
                "only_thetvdb"
            ] += 1

        episode = build_episode(
            key=key,
            epguides=epg,
            thetvdb=tvdb,
        )

        date_status = episode[
            "canonical"
        ][
            "air_date_status"
        ]

        if date_status == "consensus":
            summary[
                "date_consensus"
            ] += 1

        elif date_status == "conflict":
            summary[
                "date_conflict"
            ] += 1

        else:
            summary[
                "date_missing"
            ] += 1

        normalized.append(
            episode
        )

    # --------------------------------------------------------
    # Проверяем абсолютную нумерацию, если она есть.
    # --------------------------------------------------------

    absolute_numbers = [
        item["identity"]["absolute_number"]
        for item in normalized
        if item["identity"]["absolute_number"]
        is not None
    ]

    if len(absolute_numbers) == 66:

        expected_absolute = list(
            range(1, 67)
        )

        if sorted(
            absolute_numbers
        ) != expected_absolute:

            raise RuntimeError(
                "Invalid absolute numbering."
            )

    output = {
        "normalization_version": "0.1.0",

        "series_id": "martin_mystery",

        "source_files": {
            "epguides":
                str(
                    EPGUIDES_FILE.relative_to(
                        PROJECT_ROOT
                    )
                ),

            "thetvdb":
                str(
                    THETVDB_FILE.relative_to(
                        PROJECT_ROOT
                    )
                ),
        },

        "summary": summary,

        "episodes": normalized,
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        "Episode normalization"
    )
    print(
        "---------------------"
    )

    print(
        f"Total:              "
        f"{summary['total']}"
    )

    print(
        f"Both sources:       "
        f"{summary['both_sources']}"
    )

    print(
        f"Only epguides:      "
        f"{summary['only_epguides']}"
    )

    print(
        f"Only TheTVDB:       "
        f"{summary['only_thetvdb']}"
    )

    print()

    print(
        "Air dates:"
    )

    print(
        f"  Consensus:         "
        f"{summary['date_consensus']}"
    )

    print(
        f"  Conflicts:         "
        f"{summary['date_conflict']}"
    )

    print(
        f"  Missing:           "
        f"{summary['date_missing']}"
    )

    print()

    print(
        "Example:"
    )

    print(
        json.dumps(
            normalized[0],
            indent=2,
            ensure_ascii=False,
        )
    )

    print()

    print(
        f"Output: {OUTPUT_FILE}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())