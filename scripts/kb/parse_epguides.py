from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "knowledge"
    / "raw"
    / "epguides"
    / "page.html"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "knowledge"
    / "canonical"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "episodes_epguides.json"
)


DATE_PATTERN = re.compile(
    r"(?P<day>\d{1,2})\s+"
    r"(?P<month>[A-Za-z]{3})\s+"
    r"(?P<year>\d{2,4})"
)


EPISODE_PATTERN = re.compile(
    r"^(?P<absolute>\d+)\.\s*"
    r"(?P<season>\d+)-(?P<episode>\d+)$"
)


def parse_date(value: str) -> str | None:
    match = DATE_PATTERN.search(value)

    if not match:
        return None

    day = int(match.group("day"))
    month = match.group("month")
    year = int(match.group("year"))

    if year < 100:
        year += 2000

    months = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }

    month_number = months.get(month)

    if month_number is None:
        return None

    return (
        f"{year:04d}-"
        f"{month_number:02d}-"
        f"{day:02d}"
    )


def clean_text(value: str) -> str:
    return " ".join(
        value.replace("\xa0", " ")
        .split()
    ).strip()


def parse_episode_rows(
    soup: BeautifulSoup,
) -> list[dict]:

    episodes: list[dict] = []

    current_season: int | None = None

    # epguides currently renders its episode table
    # as a simple table-like structure. We therefore
    # inspect rows rather than relying on fragile CSS classes.
    rows = soup.find_all("tr")

    for row in rows:
        cells = row.find_all(
            ["td", "th"]
        )

        if not cells:
            continue

        texts = [
            clean_text(cell.get_text(" ", strip=True))
            for cell in cells
        ]

        joined = " | ".join(texts)

        # --------------------------------------------------
        # Season detection
        # --------------------------------------------------

        season_match = re.search(
            r"\bSeason\s+(\d+)\b",
            joined,
            flags=re.I,
        )

        if season_match:
            current_season = int(
                season_match.group(1)
            )

        # --------------------------------------------------
        # Episode detection
        # --------------------------------------------------

        if len(texts) < 4:
            continue

        absolute = None
        season_episode = None
        air_date = None
        title = None

        for text in texts:

            # Example:
            # "1." + "1-1"
            absolute_match = re.match(
                r"^(\d+)\.$",
                text
            )

            if absolute_match:
                absolute = int(
                    absolute_match.group(1)
                )

            season_episode_match = re.match(
                r"^(\d+)-(\d+)$",
                text
            )

            if season_episode_match:
                season_episode = (
                    int(season_episode_match.group(1)),
                    int(season_episode_match.group(2)),
                )

            parsed_date = parse_date(text)

            if parsed_date:
                air_date = parsed_date

        # Иногда absolute number и season/episode
        # находятся в одном текстовом блоке.
        if absolute is None:

            match = re.search(
                r"(\d+)\.\s+(\d+)-(\d+)",
                joined
            )

            if match:
                absolute = int(
                    match.group(1)
                )

                season_episode = (
                    int(match.group(2)),
                    int(match.group(3)),
                )

        if (
            air_date is None
            or season_episode is None
            or absolute is None
        ):
            continue

        season_number, episode_number = (
            season_episode
        )

        # Название обычно находится в последней
        # непустой ячейке строки.
        #
        # Но сначала ищем ссылку — epguides
        # помещает название в <a>.
        links = row.find_all("a")

        if links:
            candidates = [
                clean_text(
                    link.get_text(
                        " ",
                        strip=True
                    )
                )
                for link in links
            ]

            candidates = [
                value
                for value in candidates
                if value
                and "tvmaze" not in value.lower()
            ]

            if candidates:
                title = candidates[-1]

        if not title:
            # Fallback.
            for text in reversed(texts):
                if (
                    text
                    and not DATE_PATTERN.search(text)
                    and not re.match(
                        r"^\d+\.$",
                        text
                    )
                    and not re.match(
                        r"^\d+-\d+$",
                        text
                    )
                    and not re.search(
                        r"Season\s+\d+",
                        text,
                        flags=re.I,
                    )
                ):
                    title = text
                    break

        if not title:
            continue

        episode = {
            "episode_id": (
                f"martin_mystery_"
                f"{absolute:03d}"
            ),

            "absolute_number": absolute,

            "season_number": season_number,

            "episode_number": episode_number,

            "title_original": title,

            "air_date": air_date,

            "source": "epguides",

            "source_url": (
                "https://epguides.com/"
                "MartinMystery/"
            ),
        }

        episodes.append(episode)

    return episodes


def validate_episodes(
    episodes: list[dict],
) -> None:

    if len(episodes) != 66:
        raise RuntimeError(
            "Expected 66 episodes, "
            f"but parsed {len(episodes)}."
        )

    absolute_numbers = [
        episode["absolute_number"]
        for episode in episodes
    ]

    expected = list(
        range(1, 67)
    )

    if sorted(absolute_numbers) != expected:
        raise RuntimeError(
            "Absolute episode numbering is invalid."
        )

    episode_ids = [
        episode["episode_id"]
        for episode in episodes
    ]

    if len(episode_ids) != len(
        set(episode_ids)
    ):
        raise RuntimeError(
            "Duplicate episode IDs detected."
        )

    season_counts: dict[int, int] = {}

    for episode in episodes:
        season = episode[
            "season_number"
        ]

        season_counts[season] = (
            season_counts.get(season, 0)
            + 1
        )

    expected_counts = {
        1: 26,
        2: 14,
        3: 26,
    }

    if season_counts != expected_counts:
        raise RuntimeError(
            "Unexpected season distribution: "
            f"{season_counts}"
        )


def main() -> int:

    if not INPUT_FILE.exists():
        print(
            f"Input not found: {INPUT_FILE}",
            file=sys.stderr,
        )
        return 1

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    html = INPUT_FILE.read_text(
        encoding="utf-8",
        errors="replace",
    )

    soup = BeautifulSoup(
        html,
        "lxml",
    )

    episodes = parse_episode_rows(
        soup
    )

    episodes.sort(
        key=lambda item:
            item["absolute_number"]
    )

    try:
        validate_episodes(
            episodes
        )
    except RuntimeError as exc:
        print(
            f"[ERROR] {exc}",
            file=sys.stderr,
        )

        print(
            f"Parsed episodes: "
            f"{len(episodes)}"
        )

        return 1

    OUTPUT_FILE.write_text(
        json.dumps(
            {
                "source": "epguides",

                "source_url": (
                    "https://epguides.com/"
                    "MartinMystery/"
                ),

                "parser_version": "0.1.0",

                "episode_count": len(
                    episodes
                ),

                "episodes": episodes,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        f"[OK] Parsed "
        f"{len(episodes)} episodes."
    )

    print()
    print(
        "Season distribution:"
    )

    for season in (1, 2, 3):
        count = sum(
            1
            for episode in episodes
            if episode["season_number"]
            == season
        )

        print(
            f"  Season {season}: "
            f"{count}"
        )

    print()
    print(
        "First episode:"
    )

    print(
        json.dumps(
            episodes[0],
            indent=2,
            ensure_ascii=False,
        )
    )

    print()
    print(
        "Last episode:"
    )

    print(
        json.dumps(
            episodes[-1],
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