from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from html import unescape


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "knowledge"
    / "raw"
    / "wikipedia"
    / "page.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "knowledge"
    / "canonical"
    / "episodes_wikipedia.json"
)

SOURCE_URL = (
    "https://en.wikipedia.org/wiki/"
    "List_of_Martin_Mystery_episodes"
)

EXPECTED_SEASONS = {
    1: 26,
    2: 14,
    3: 26,
}


def clean_wikitext(value: str) -> str:
    if not value:
        return ""

    value = re.sub(
        r"\[\[([^|\]]+)\|([^\]]+)\]\]",
        r"\2",
        value,
    )

    value = re.sub(
        r"\[\[([^\]]+)\]\]",
        r"\1",
        value,
    )

    value = re.sub(
        r"'{2,5}",
        "",
        value,
    )

    value = re.sub(
        r"\{\{[^{}]*\}\}",
        "",
        value,
    )

    value = re.sub(
        r"<!--.*?-->",
        "",
        value,
        flags=re.S,
    )

    value = unescape(value)

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def parse_date(value: str) -> str | None:
    match = re.search(
        r"\{\{\s*start\s+date\s*\|\s*"
        r"(\d{4})\s*\|\s*"
        r"(\d{1,2})\s*\|\s*"
        r"(\d{1,2})"
        r"(?:\|[^}]*)?"
        r"\}\}",
        value,
        flags=re.I,
    )

    if not match:
        return None

    return (
        f"{int(match.group(1)):04d}-"
        f"{int(match.group(2)):02d}-"
        f"{int(match.group(3)):02d}"
    )


def parse_fields(
    block: str,
) -> dict[str, str]:

    fields: dict[str, str] = {}

    for line in block.splitlines():

        line = line.strip()

        if not line.startswith("|"):
            continue

        line = line[1:]

        if "=" not in line:
            continue

        key, value = line.split(
            "=",
            1,
        )

        fields[key.strip()] = value.strip()

    return fields


def split_episode_blocks(
    section: str,
) -> list[str]:

    matches = list(
        re.finditer(
            r"\{\{\s*Episode\s+list\b",
            section,
            flags=re.I,
        )
    )

    blocks: list[str] = []

    for index, match in enumerate(
        matches
    ):

        start = match.start()

        if index + 1 < len(matches):
            end = matches[
                index + 1
            ].start()
        else:
            end = len(section)

        blocks.append(
            section[start:end]
        )

    return blocks


def parse_episode_block(
    block: str,
    season: int,
) -> dict | None:

    fields = parse_fields(
        block
    )

    episode_overall = fields.get(
        "EpisodeNumber"
    )

    episode_in_season = fields.get(
        "EpisodeNumber2"
    )

    # Используем именно номер в сезоне.
    # Это важно для общей нумерации 1..66.
    if not episode_in_season:
        return None

    match = re.search(
        r"\d+",
        episode_in_season,
    )

    if not match:
        return None

    episode_number = int(
        match.group()
    )

    if not (
        1
        <= episode_number
        <= EXPECTED_SEASONS[season]
    ):
        return None

    title = clean_wikitext(
        fields.get(
            "Title",
            "",
        )
    )

    if not title:
        return None

    writer = clean_wikitext(
        fields.get(
            "WrittenBy",
            "",
        )
    )

    villain = clean_wikitext(
        fields.get(
            "Aux2",
            "",
        )
    )

    summary = clean_wikitext(
        fields.get(
            "ShortSummary",
            "",
        )
    )

    air_date = parse_date(
        fields.get(
            "OriginalAirDate",
            "",
        )
    )

    overall_number = None

    if episode_overall:

        overall_match = re.search(
            r"\d+",
            episode_overall,
        )

        if overall_match:
            overall_number = int(
                overall_match.group()
            )

    return {
        "episode_id": (
            f"martin_mystery_s"
            f"{season:02d}e"
            f"{episode_number:02d}"
        ),

        "absolute_number":
            overall_number,

        "season_number":
            season,

        "episode_number":
            episode_number,

        "title_original":
            title,

        "air_date":
            air_date,

        "writer":
            writer,

        "villains_monsters":
            villain,

        "description":
            summary,

        "source":
            "wikipedia",

        "source_url":
            SOURCE_URL,
    }


def extract_season_sections(
    wikitext: str,
) -> dict[int, str]:

    """
    Возвращает только три настоящих сезона.

    В частности, не включает:
        ===Totally Spies! crossover (2007)===
    """

    matches = list(
        re.finditer(
            r"^===\s*Season\s+([123])\s*.*?===\s*$",
            wikitext,
            flags=re.I | re.M,
        )
    )

    if len(matches) != 3:
        raise RuntimeError(
            "Expected exactly 3 season headings, "
            f"found {len(matches)}."
        )

    sections: dict[int, str] = {}

    for index, match in enumerate(matches):

        season = int(
            match.group(1)
        )

        start = match.end()

        # Ищем следующий заголовок уровня 3 ИЛИ выше.
        next_heading = re.search(
            r"^={2,3}.*?={2,3}\s*$",
            wikitext[start:],
            flags=re.M,
        )

        if next_heading:
            end = (
                start
                + next_heading.start()
            )
        else:
            end = len(
                wikitext
            )

        sections[season] = wikitext[
            start:end
        ]

    return sections


def parse_wikipedia(
    wikitext: str,
) -> list[dict]:

    sections = extract_season_sections(
        wikitext
    )

    episodes: list[dict] = []

    for season in (
        1,
        2,
        3,
    ):

        section = sections[
            season
        ]

        blocks = split_episode_blocks(
            section
        )

        print(
            f"Season {season}: "
            f"{len(blocks)} Episode list templates"
        )

        for block in blocks:

            episode = parse_episode_block(
                block,
                season,
            )

            if episode:
                episodes.append(
                    episode
                )

    # Убираем дубликаты.
    unique: dict[
        tuple[int, int],
        dict,
    ] = {}

    for episode in episodes:

        key = (
            episode["season_number"],
            episode["episode_number"],
        )

        if key not in unique:
            unique[key] = episode

    result = list(
        unique.values()
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

    if counts != EXPECTED_SEASONS:
        raise RuntimeError(
            "Invalid season distribution: "
            f"{counts}"
        )

    expected = {
        (
            season,
            episode_number,
        )
        for season, count
        in EXPECTED_SEASONS.items()
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

        print(
            "Missing:",
            sorted(expected - actual)
        )

        print(
            "Extra:",
            sorted(actual - expected)
        )

        raise RuntimeError(
            "Episode numbering mismatch."
        )

    # Проверяем абсолютную нумерацию.
    absolute = [
        episode["absolute_number"]
        for episode in episodes
    ]

    if all(
        number is not None
        for number in absolute
    ):

        expected_absolute = list(
            range(1, 67)
        )

        if sorted(absolute) != expected_absolute:
            raise RuntimeError(
                "Invalid absolute numbering."
            )


def load_wikitext() -> str:

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input not found: {INPUT_FILE}"
        )

    data = json.loads(
        INPUT_FILE.read_text(
            encoding="utf-8"
        )
    )

    parse = data.get(
        "parse"
    )

    if not isinstance(
        parse,
        dict,
    ):
        raise RuntimeError(
            "Missing 'parse' object."
        )

    wikitext = parse.get(
        "wikitext"
    )

    if not isinstance(
        wikitext,
        str,
    ):
        raise RuntimeError(
            "Wikipedia wikitext not found."
        )

    return wikitext


def main() -> int:

    try:

        wikitext = load_wikitext()

        episodes = parse_wikipedia(
            wikitext
        )

        validate(
            episodes
        )

    except (
        FileNotFoundError,
        RuntimeError,
        json.JSONDecodeError,
    ) as exc:

        print(
            f"[ERROR] {exc}",
            file=sys.stderr,
        )

        return 1

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "source": "wikipedia",

        "source_url": SOURCE_URL,

        "parser_version": "0.3.0",

        "episode_count":
            len(episodes),

        "episodes":
            episodes,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()

    print(
        f"[OK] Parsed "
        f"{len(episodes)} episodes."
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
