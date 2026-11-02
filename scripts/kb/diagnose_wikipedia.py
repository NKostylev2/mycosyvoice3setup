from __future__ import annotations

import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "knowledge"
    / "raw"
    / "wikipedia"
    / "page.json"
)


def main() -> None:
    data = json.loads(
        INPUT_FILE.read_text(
            encoding="utf-8"
        )
    )

    wikitext = data["parse"]["wikitext"]

    print("=" * 70)
    print("SEASON HEADINGS")
    print("=" * 70)

    headings = re.findall(
        r"^=+\s*Season.*$",
        wikitext,
        flags=re.I | re.M,
    )

    for index, heading in enumerate(
        headings,
        start=1,
    ):
        print(
            f"{index}: {heading}"
        )

    print()
    print(
        f"Season headings found: {len(headings)}"
    )

    print()
    print("=" * 70)
    print("EPISODE LIST TEMPLATES")
    print("=" * 70)

    matches = list(
        re.finditer(
            r"\{\{\s*Episode\s+list\b",
            wikitext,
            flags=re.I,
        )
    )

    print(
        f"Episode list templates found: "
        f"{len(matches)}"
    )

    print()
    print("=" * 70)
    print("EPISODE COUNTS BY SEASON MARKER")
    print("=" * 70)

    season_positions = []

    for match in re.finditer(
        r"^=+\s*Season\s+([123]).*$",
        wikitext,
        flags=re.I | re.M,
    ):
        season_positions.append(
            (
                int(match.group(1)),
                match.start(),
                match.group(0),
            )
        )

    for index, (
        season,
        start,
        heading,
    ) in enumerate(
        season_positions
    ):

        if index + 1 < len(
            season_positions
        ):
            end = season_positions[
                index + 1
            ][1]
        else:
            end = len(
                wikitext
            )

        section = wikitext[
            start:end
        ]

        count = len(
            re.findall(
                r"\{\{\s*Episode\s+list\b",
                section,
                flags=re.I,
            )
        )

        print(
            f"Season {season}: {count}"
        )

    print()
    print("=" * 70)
    print("FIRST EPISODE MARKERS")
    print("=" * 70)

    for match in list(
        re.finditer(
            r"\|\s*EpisodeNumber\s*=\s*([0-9]+)",
            wikitext,
            flags=re.I,
        )
    )[:10]:

        print(
            f"EpisodeNumber = "
            f"{match.group(1)}"
        )

    print()
    print("=" * 70)
    print("SEASON 2 AREA")
    print("=" * 70)

    season2 = re.search(
        r"^=+\s*Season\s+2.*$",
        wikitext,
        flags=re.I | re.M,
    )

    if season2:

        start = season2.start()

        print(
            wikitext[
                start:start + 5000
            ]
        )

    else:
        print(
            "Season 2 heading NOT FOUND"
        )


if __name__ == "__main__":
    main()