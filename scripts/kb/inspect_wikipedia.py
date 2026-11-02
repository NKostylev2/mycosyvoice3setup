from __future__ import annotations

import json
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

    print("TOP LEVEL:")
    for key, value in data.items():
        print(
            f"  {key}: {type(value).__name__}"
        )

    parse = data.get("parse")

    print()
    print("PARSE:")
    print(
        f"  type: {type(parse).__name__}"
    )

    if isinstance(parse, dict):

        for key, value in parse.items():

            if isinstance(value, str):
                print(
                    f"  {key}: str "
                    f"({len(value):,} chars)"
                )

            elif isinstance(value, dict):
                print(
                    f"  {key}: dict "
                    f"keys={list(value.keys())[:20]}"
                )

            elif isinstance(value, list):
                print(
                    f"  {key}: list "
                    f"items={len(value)}"
                )

            else:
                print(
                    f"  {key}: "
                    f"{type(value).__name__}"
                )

    print()

    # Покажем первые 2000 символов предполагаемого
    # содержимого статьи.
    candidates = []

    if isinstance(parse, dict):

        for key in (
            "text",
            "wikitext",
        ):

            value = parse.get(key)

            if isinstance(value, str):
                candidates.append(
                    (key, value)
                )

            elif isinstance(value, dict):

                for subkey, subvalue in value.items():

                    if isinstance(
                        subvalue,
                        str,
                    ):
                        candidates.append(
                            (
                                f"{key}.{subkey}",
                                subvalue,
                            )
                        )

    for name, value in candidates:

        print("=" * 60)
        print(
            f"CONTENT: {name}"
        )
        print("=" * 60)
        print(
            value[:2000]
        )
        print()


if __name__ == "__main__":
    main()