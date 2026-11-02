from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"

OUTPUT = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_candidates.json"
)


# Уже подтвержденные основные сущности.
KNOWN_ENTITIES = {
    "Martin Mystery",
    "Diana Lombard",
    "Java",
    "Billy",
    "M.O.M.",
    "The Center",
}


# Слова, которые часто встречаются с заглавной буквы,
# но сами по себе персонажами обычно не являются.
STOPWORDS = {
    "After",
    "Almost",
    "All",
    "Alpha",
    "And",
    "Andromeda",
    "An",
    "Around",
    "At",
    "Before",
    "Both",
    "British",
    "But",
    "Can",
    "Canadian",
    "Center",
    "Center's",
    "Christmas",
    "Chinese",
    "Earth",
    "England",
    "Europe",
    "French",
    "France",
    "However",
    "If",
    "In",
    "It",
    "North",
    "Now",
    "Once",
    "Ontario",
    "Soon",
    "She",
    "The",
    "They",
    "This",
    "That",
    "Torrington",
    "Torrington's",
    "United",
    "When",
    "While",
    "With",
}


# Географические / локационные слова.
LOCATION_WORDS = {
    "Alberta",
    "Badlands",
    "British",
    "Brunei",
    "Canada",
    "Canadian",
    "Caribbean",
    "Cap",
    "Ferrat",
    "China",
    "France",
    "French",
    "Ontario",
    "Pacific",
    "Torrington",
    "Earth",
    "Galaxy",
}


def normalize_name(value: str) -> str:
    value = value.strip()

    # Убираем possessive:
    # Martin's -> Martin
    # Billy's -> Billy
    if value.endswith("'s"):
        value = value[:-2]

    return value.strip()


def looks_like_location(value: str) -> bool:
    words = {
        word.strip(".,'\"")
        for word in value.split()
    }

    return bool(words & LOCATION_WORDS)


def looks_like_sentence_fragment(value: str) -> bool:
    words = value.split()

    if not words:
        return True

    # Предложения обычно начинаются такими словами.
    if words[0] in STOPWORDS:
        return True

    # Длинные фрагменты предложений.
    if len(words) >= 4:
        return True

    return False


def extract_candidates(text: str) -> set[str]:
    if not text:
        return set()

    # Ищем от 1 до 3 слов,
    # каждое начинается с заглавной буквы.
    pattern = re.compile(
        r"\b"
        r"[A-Z][A-Za-z.'-]+"
        r"(?:\s+[A-Z][A-Za-z.'-]+){0,2}"
        r"\b"
    )

    candidates: set[str] = set()

    for match in pattern.finditer(text):

        value = normalize_name(match.group(0))

        if not value:
            continue

        if value in KNOWN_ENTITIES:
            continue

        words = value.split()

        # Одиночные слова из очевидного стоп-листа.
        if value in STOPWORDS:
            continue

        # Удаляем фрагменты вроде:
        # When Martin
        # After Martin
        # Can Martin
        if looks_like_sentence_fragment(value):
            continue

        # Географические названия.
        if looks_like_location(value):
            continue

        # Не берём слишком короткие сущности.
        if len(value) < 3:
            continue

        # Убираем очевидные местоимения.
        if value in {
            "He",
            "She",
            "Him",
            "Her",
            "His",
            "Their",
        }:
            continue

        # Для однословных кандидатов разрешаем только
        # достаточно «именные» формы.
        if len(words) == 1:

            word = words[0]

            if word in STOPWORDS:
                continue

            if word.endswith(
                (
                    "ing",
                    "ed",
                    "ly",
                )
            ):
                continue

        candidates.add(value)

    return candidates


def main() -> None:
    conn = sqlite3.connect(DB)

    rows = conn.execute(
        """
        SELECT
            episode_id,
            absolute_number,
            title_original,
            synopsis_detailed
        FROM episodes
        ORDER BY absolute_number
        """
    ).fetchall()

    candidates = defaultdict(
        lambda: {
            "mention_count": 0,
            "episodes": [],
        }
    )

    for (
        episode_id,
        absolute_number,
        title_original,
        synopsis,
    ) in rows:

        found = extract_candidates(
            synopsis or ""
        )

        for name in found:

            candidates[name]["mention_count"] += 1

            candidates[name]["episodes"].append(
                {
                    "episode_id": episode_id,
                    "absolute_number": absolute_number,
                    "title_original": title_original,
                }
            )

    result = []

    for name, data in candidates.items():

        result.append(
            {
                "name": name,
                "mention_count": data[
                    "mention_count"
                ],
                "episodes": sorted(
                    data["episodes"],
                    key=lambda x: x["absolute_number"],
                ),
            }
        )

    result.sort(
        key=lambda x: (
            -x["mention_count"],
            x["name"].lower(),
        )
    )

    output = {
        "schema_version": "0.2",
        "episode_count": len(rows),
        "candidate_count": len(result),
        "candidates": result,
    }

    OUTPUT.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("[OK] Character candidate extraction complete")
    print()
    print(f"Episodes   : {len(rows)}")
    print(f"Candidates : {len(result)}")
    print()
    print("Top candidates:")

    for item in result[:50]:

        print(
            f"  {item['name']:35s} "
            f"mentions={item['mention_count']}"
        )

    print()
    print(f"Report: {OUTPUT}")

    conn.close()


if __name__ == "__main__":
    main()