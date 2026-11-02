from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"

CANDIDATES_FILE = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_candidates.json"
)

OUTPUT = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_classification_input.json"
)


KNOWN_CHARACTER_IDS = {
    "martin_mystery",
    "diana_lombard",
    "java",
    "billy",
    "mom",
}


def normalize_entity_name(value: str) -> str:
    value = value.strip()

    value = value.replace("’", "'")

    # Удаляем possessive
    value = re.sub(
        r"'s\b",
        "",
        value,
        flags=re.IGNORECASE,
    )

    # Для сравнения M.O.M. == M.O.M
    value = value.rstrip(".")

    # Схлопываем пробелы
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def is_sentence_fragment(value: str) -> bool:
    """
    Отбрасывает явно повреждённые regex-кандидаты:
        Carlin. Now Java
        Java. Martin
        M.O.M. Martin
        Center. She
    """

    # Несколько предложений внутри одного кандидата.
    if "." in value.rstrip("."):
        # Исключение: аббревиатуры вроде M.O.M.
        compact = value.replace(".", "")
        if not compact.isupper():
            return True

    first_word = value.split()[0].lower()

    fragment_starters = {
        "after",
        "and",
        "before",
        "but",
        "can",
        "due",
        "famous",
        "however",
        "meanwhile",
        "now",
        "she",
        "soon",
        "that",
        "the",
        "they",
        "this",
        "when",
        "while",
        "what",
        "with",
    }

    return first_word in fragment_starters

def get_known_aliases(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT
            c.name_original,
            a.alias
        FROM characters c
        LEFT JOIN character_aliases a
            ON a.character_id = c.id
        WHERE c.character_id IN (
            'martin_mystery',
            'diana_lombard',
            'java',
            'billy',
            'mom'
        )
        """
    ).fetchall()

    aliases: set[str] = set()

    for name_original, alias in rows:

        if name_original:
            aliases.add(
                normalize_entity_name(
                    name_original
                ).lower()
            )

        if alias:
            aliases.add(
                normalize_entity_name(
                    alias
                ).lower()
            )

    return aliases


def main() -> None:
    candidate_data = json.loads(
        CANDIDATES_FILE.read_text(
            encoding="utf-8"
        )
    )

    candidates = candidate_data.get(
        "candidates",
        []
    )

    conn = sqlite3.connect(DB)

    known_aliases = get_known_aliases(conn)

    # Загружаем synopsis всех эпизодов один раз.
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

    episode_data = {
        row[0]: {
            "episode_id": row[0],
            "absolute_number": row[1],
            "title_original": row[2],
            "synopsis_detailed": row[3] or "",
        }
        for row in rows
    }

    result = []

    skipped_known = 0

    for candidate in candidates:

        name = candidate["name"]

        normalized_name = normalize_entity_name(
            name
        )

        name_lower = normalized_name.lower()

        if name_lower in known_aliases:
            skipped_known += 1
            continue

        if is_sentence_fragment(name):
            skipped_known += 1
            continue

        contexts = []

        for episode_ref in candidate.get(
            "episodes",
            []
        ):

            episode_id = episode_ref["episode_id"]

            episode = episode_data.get(
                episode_id
            )

            if episode is None:
                continue

            synopsis = episode[
                "synopsis_detailed"
            ]

            # Ищем позицию имени в synopsis.
            pos = synopsis.lower().find(
                name_lower
            )

            if pos >= 0:

                # Даём модели локальный контекст,
                # а также полный synopsis.
                context_start = max(
                    0,
                    pos - 300
                )

                context_end = min(
                    len(synopsis),
                    pos + len(name) + 500
                )

                local_context = synopsis[
                    context_start:context_end
                ]
            else:
                local_context = synopsis[
                    :800
                ]

            contexts.append(
                {
                    "episode_id": episode_id,
                    "absolute_number": episode[
                        "absolute_number"
                    ],
                    "episode_title": episode[
                        "title_original"
                    ],
                    "local_context": local_context,
                    "full_synopsis": synopsis,
                }
            )

        result.append(
            {
                "candidate_name": name,
                "mention_count": candidate[
                    "mention_count"
                ],
                "classification": None,
                "confidence": None,
                "canonical_name": None,
                "name_ru": None,
                "aliases": [],
                "contexts": contexts,
            }
        )

    result.sort(
        key=lambda item: (
            -item["mention_count"],
            item["candidate_name"].lower(),
        )
    )

    output = {
        "schema_version": "0.1",

        "classification_labels": [
            "PERSON",
            "CREATURE",
            "MONSTER",
            "SUPERNATURAL_ENTITY",
            "ORGANIZATION",
            "LOCATION",
            "OBJECT",
            "ALIAS",
            "FALSE_POSITIVE"
        ],

        "instructions": {
            "language": "English",
            "identify_entities_from_context": True,
            "do_not_invent_entities": True,
            "preserve_original_name": True,
            "alias_requires_known_character": True,
            "unknown_entities_should_not_be_forced_into_PERSON": True
        },

        "candidate_count": len(result),

        "statistics": {
            "original_candidates":
                len(candidates),
            "known_aliases_skipped":
                skipped_known,
            "classification_candidates":
                len(result)
        },

        "candidates": result
    }

    OUTPUT.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        "[OK] Character classification input built"
    )
    print()
    print(
        f"Original candidates    : "
        f"{len(candidates)}"
    )
    print(
        f"Known aliases skipped  : "
        f"{skipped_known}"
    )
    print(
        f"LLM candidates         : "
        f"{len(result)}"
    )
    print()

    print("Candidates:")
    for item in result[:50]:
        print(
            f"  {item['candidate_name']:35s} "
            f"mentions={item['mention_count']}"
        )

    print()
    print(f"Output: {OUTPUT}")

    conn.close()


if __name__ == "__main__":
    main()
