from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "knowledge"
    / "raw"
    / "thetvdb"
    / "page.html"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "knowledge"
    / "canonical"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "episodes_thetvdb.json"
)

BASE_URL = "https://thetvdb.com"

SOURCE_URL = (
    "https://thetvdb.com/"
    "series/martin-mystery"
)

SEASON_EXPECTED = {
    1: 26,
    2: 14,
    3: 26,
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0 Safari/537.36 "
        "AI-Dubbing-TheTVDBParser/0.3"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def clean_text(value: str) -> str:
    return " ".join(
        value.replace("\xa0", " ").split()
    ).strip()


def download(url: str) -> str:
    request = Request(
        url,
        headers=HEADERS,
    )

    with urlopen(
        request,
        timeout=30,
    ) as response:
        return response.read().decode(
            "utf-8",
            errors="replace",
        )


def find_season_urls(
    soup: BeautifulSoup,
) -> dict[int, str]:

    result: dict[int, str] = {}

    for link in soup.find_all(
        "a",
        href=True,
    ):
        text = clean_text(
            link.get_text(
                " ",
                strip=True,
            )
        )

        match = re.fullmatch(
            r"Season\s+([123])",
            text,
            flags=re.I,
        )

        if not match:
            continue

        season = int(
            match.group(1)
        )

        result[season] = urljoin(
            BASE_URL,
            link["href"],
        )

    return result


def extract_episode_from_container(
    container,
    season: int,
) -> dict | None:

    text = clean_text(
        container.get_text(
            " ",
            strip=True,
        )
    )

    match = re.search(
        rf"\bS0*{season}E0*(\d{{1,2}})\b",
        text,
        flags=re.I,
    )

    if not match:
        return None

    episode_number = int(
        match.group(1)
    )

    if not (
        1
        <= episode_number
        <= SEASON_EXPECTED[season]
    ):
        return None

    # Ищем ссылки внутри контейнера.
    links = container.find_all(
        "a",
        href=True,
    )

    episode_link = None

    for link in links:
        href = link.get("href", "")

        if "/episode/" in href.lower():
            episode_link = link
            break

    # Fallback: в случае отличающейся разметки
    # берём ссылку, текст которой не похож на служебный.
    if episode_link is None:

        for link in links:
            link_text = clean_text(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

            if not link_text:
                continue

            if re.fullmatch(
                r"S\d+E\d+",
                link_text,
                flags=re.I,
            ):
                continue

            episode_link = link
            break

    if episode_link is None:
        return None

    title = clean_text(
        episode_link.get_text(
            " ",
            strip=True,
        )
    )

    if not title:
        return None

    href = episode_link["href"]

    episode_url = urljoin(
        BASE_URL,
        href,
    )

    # Дата вида:
    # September 15, 2004
    date_match = re.search(
        r"\b"
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)"
        r"\s+\d{1,2},\s+\d{4}"
        r"\b",
        text,
        flags=re.I,
    )

    air_date = (
        date_match.group(0)
        if date_match
        else None
    )

    return {
        "episode_id": (
            f"martin_mystery_s"
            f"{season:02d}e"
            f"{episode_number:02d}"
        ),

        "season_number": season,

        "episode_number": episode_number,

        "title_original": title,

        "air_date": air_date,

        "thetvdb_url": episode_url,

        "source": "thetvdb",

        "source_url": SOURCE_URL,
    }


def parse_season_page(
    html: str,
    season: int,
) -> list[dict]:

    soup = BeautifulSoup(
        html,
        "lxml",
    )

    episodes: dict[
        tuple[int, int],
        dict,
    ] = {}

    # ---------------------------------------------------------
    # Важное изменение:
    #
    # Мы НЕ предполагаем конкретный CSS-класс.
    # Ищем любой контейнер, содержащий SxxExx,
    # затем поднимаемся по DOM до разумного блока.
    # ---------------------------------------------------------

    markers = soup.find_all(
        string=re.compile(
            rf"\bS0*{season}E\d+\b",
            flags=re.I,
        )
    )

    for marker in markers:

        parent = marker.parent

        if parent is None:
            continue

        candidates = []

        # Проверяем несколько уровней вверх.
        current = parent

        for _ in range(5):

            if current is None:
                break

            candidates.append(
                current
            )

            current = current.parent

        parsed = None

        for container in candidates:

            parsed = (
                extract_episode_from_container(
                    container,
                    season,
                )
            )

            if parsed is not None:
                break

        if parsed is None:
            continue

        key = (
            parsed["season_number"],
            parsed["episode_number"],
        )

        episodes[key] = parsed

    result = list(
        episodes.values()
    )

    result.sort(
        key=lambda item: (
            item["season_number"],
            item["episode_number"],
        )
    )

    return result


def validate(
    episodes: list[dict],
) -> None:

    if len(episodes) != 66:
        raise RuntimeError(
            "Expected 66 episodes, "
            f"got {len(episodes)}."
        )

    counts: dict[int, int] = {}

    for episode in episodes:

        season = episode[
            "season_number"
        ]

        counts[season] = (
            counts.get(season, 0)
            + 1
        )

    if counts != SEASON_EXPECTED:
        raise RuntimeError(
            "Unexpected season distribution: "
            f"{counts}"
        )

    expected = {
        (
            season,
            episode_number,
        )
        for season, count
        in SEASON_EXPECTED.items()
        for episode_number
        in range(
            1,
            count + 1,
        )
    }

    actual = {
        (
            episode["season_number"],
            episode["episode_number"],
        )
        for episode in episodes
    }

    if actual != expected:

        missing = sorted(
            expected - actual
        )

        extra = sorted(
            actual - expected
        )

        raise RuntimeError(
            "Episode numbering mismatch.\n"
            f"Missing: {missing}\n"
            f"Extra: {extra}"
        )

    titles_missing = [
        episode
        for episode in episodes
        if not episode["title_original"]
    ]

    if titles_missing:
        raise RuntimeError(
            "Some episodes have no title."
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

    season_urls = find_season_urls(
        soup
    )

    print(
        "Season pages found:"
    )

    for season in sorted(
        season_urls
    ):
        print(
            f"  Season {season}: "
            f"{season_urls[season]}"
        )

    missing = (
        set(SEASON_EXPECTED)
        - set(season_urls)
    )

    if missing:

        print(
            "Missing season pages: "
            f"{sorted(missing)}",
            file=sys.stderr,
        )

        return 1

    all_episodes: list[dict] = []

    for season in (
        1,
        2,
        3,
    ):

        print()
        print(
            f"[DOWNLOAD] Season {season}"
        )

        try:
            season_html = download(
                season_urls[season]
            )

        except Exception as exc:

            print(
                f"[ERROR] {exc}",
                file=sys.stderr,
            )

            return 1

        parsed = parse_season_page(
            season_html,
            season,
        )

        print(
            f"[PARSED] Season {season}: "
            f"{len(parsed)} episodes"
        )

        all_episodes.extend(
            parsed
        )

    all_episodes.sort(
        key=lambda item: (
            item["season_number"],
            item["episode_number"],
        )
    )

    try:
        validate(
            all_episodes
        )

    except RuntimeError as exc:

        print(
            f"[ERROR] {exc}",
            file=sys.stderr,
        )

        return 1

    OUTPUT = {
        "source": "thetvdb",

        "source_url": SOURCE_URL,

        "parser_version": "0.3.0",

        "episode_count": len(
            all_episodes
        ),

        "episodes": all_episodes,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            OUTPUT,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print(
        f"[OK] Parsed "
        f"{len(all_episodes)} episodes."
    )

    print(
        "Season distribution:"
    )

    for season in (
        1,
        2,
        3,
    ):

        count = sum(
            1
            for episode
            in all_episodes
            if episode["season_number"]
            == season
        )

        print(
            f"  Season {season}: "
            f"{count}"
        )

    print()
    print(
        "First 3 episodes:"
    )

    for episode in all_episodes[:3]:
        print(
            f"  "
            f"S{episode['season_number']:02d}"
            f"E{episode['episode_number']:02d} "
            f"- "
            f"{episode['title_original']}"
        )

    print()
    print(
        f"Output: {OUTPUT_FILE}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
