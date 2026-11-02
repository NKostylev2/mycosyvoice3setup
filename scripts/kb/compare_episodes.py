from __future__ import annotations

import json
import sys
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

REPORT_FILE = (
    PROJECT_ROOT
    / "knowledge"
    / "canonical"
    / "episode_comparison.json"
)


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def index_episodes(
    data: dict,
) -> dict[tuple[int, int], dict]:

    result = {}

    for episode in data["episodes"]:

        key = (
            episode["season_number"],
            episode["episode_number"],
        )

        if key in result:
            raise RuntimeError(
                f"Duplicate episode: {key}"
            )

        result[key] = episode

    return result


def compare_title(
    epguides: dict,
    thetvdb: dict,
) -> dict:

    title_a = epguides.get(
        "title_original"
    )

    title_b = thetvdb.get(
        "title_original"
    )

    if not title_a or not title_b:
        return {
            "status": "missing"
        }

    if title_a == title_b:
        return {
            "status": "match",
            "epguides": title_a,
            "thetvdb": title_b,
        }

    return {
        "status": "different",
        "epguides": title_a,
        "thetvdb": title_b,
    }


def compare_date(
    epguides: dict,
    thetvdb: dict,
) -> dict:

    date_a = epguides.get(
        "air_date"
    )

    date_b = thetvdb.get(
        "air_date"
    )

    if not date_a or not date_b:
        return {
            "status": "missing",
            "epguides": date_a,
            "thetvdb": date_b,
        }

    if date_a == date_b:
        return {
            "status": "match",
            "epguides": date_a,
            "thetvdb": date_b,
        }

    return {
        "status": "different",
        "epguides": date_a,
        "thetvdb": date_b,
    }


def main() -> int:

    try:
        epguides_data = load_json(
            EPGUIDES_FILE
        )

        thetvdb_data = load_json(
            THETVDB_FILE
        )

    except (
        FileNotFoundError,
        json.JSONDecodeError,
    ) as exc:

        print(
            f"[ERROR] {exc}",
            file=sys.stderr,
        )

        return 1

    epguides = index_episodes(
        epguides_data
    )

    thetvdb = index_episodes(
        thetvdb_data
    )

    all_keys = sorted(
        set(epguides)
        | set(thetvdb)
    )

    report = []

    summary = {
        "total": len(all_keys),
        "both_present": 0,
        "missing_epguides": 0,
        "missing_thetvdb": 0,
        "title_match": 0,
        "title_different": 0,
        "date_match": 0,
        "date_different": 0,
        "date_missing": 0,
    }

    for season, episode_number in all_keys:

        key = (
            season,
            episode_number,
        )

        epg = epguides.get(key)
        tvdb = thetvdb.get(key)

        if epg and tvdb:
            summary[
                "both_present"
            ] += 1

        elif epg:
            summary[
                "missing_thetvdb"
            ] += 1

        elif tvdb:
            summary[
                "missing_epguides"
            ] += 1

        title_result = {}

        date_result = {}

        if epg and tvdb:

            title_result = compare_title(
                epg,
                tvdb,
            )

            date_result = compare_date(
                epg,
                tvdb,
            )

            if title_result[
                "status"
            ] == "match":

                summary[
                    "title_match"
                ] += 1

            elif title_result[
                "status"
            ] == "different":

                summary[
                    "title_different"
                ] += 1

            if date_result[
                "status"
            ] == "match":

                summary[
                    "date_match"
                ] += 1

            elif date_result[
                "status"
            ] == "different":

                summary[
                    "date_different"
                ] += 1

            elif date_result[
                "status"
            ] == "missing":

                summary[
                    "date_missing"
                ] += 1

        report.append(
            {
                "season_number": season,
                "episode_number":
                    episode_number,

                "key": (
                    f"S{season:02d}"
                    f"E{episode_number:02d}"
                ),

                "epguides": epg,

                "thetvdb": tvdb,

                "comparison": {
                    "title": title_result,
                    "air_date": date_result,
                },
            }
        )

    output = {
        "comparison_version": "0.1.0",

        "sources": [
            "epguides",
            "thetvdb",
        ],

        "summary": summary,

        "episodes": report,
    }

    REPORT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        "Episode comparison"
    )

    print(
        "------------------"
    )

    print(
        f"Total:              "
        f"{summary['total']}"
    )

    print(
        f"Both present:       "
        f"{summary['both_present']}"
    )

    print(
        f"Missing epguides:   "
        f"{summary['missing_epguides']}"
    )

    print(
        f"Missing TheTVDB:    "
        f"{summary['missing_thetvdb']}"
    )

    print()

    print(
        "Titles:"
    )

    print(
        f"  Match:            "
        f"{summary['title_match']}"
    )

    print(
        f"  Different:        "
        f"{summary['title_different']}"
    )

    print()

    print(
        "Air dates:"
    )

    print(
        f"  Match:            "
        f"{summary['date_match']}"
    )

    print(
        f"  Different:        "
        f"{summary['date_different']}"
    )

    print(
        f"  Missing:           "
        f"{summary['date_missing']}"
    )

    print()

    print(
        f"Report: {REPORT_FILE}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())