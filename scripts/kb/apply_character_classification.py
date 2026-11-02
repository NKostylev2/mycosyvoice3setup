from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"

RESULT_FILE = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_classification_results.json"
)

REVIEW_FILE = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_classification_review.json"
)


ALLOWED = {
    "PERSON",
    "CREATURE",
    "MONSTER",
    "SUPERNATURAL_ENTITY",
    "ORGANIZATION",
    "LOCATION",
    "OBJECT",
    "ALIAS",
    "FALSE_POSITIVE",
}


KNOWN_CHARACTER_IDS = {
    "martin_mystery",
    "diana_lombard",
    "java",
    "billy",
    "mom",
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    result_data = load_json(RESULT_FILE)
    review_data = load_json(REVIEW_FILE)

    results = result_data["results"]
    reviews = review_data["reviews"]

    review_map = {
        item["candidate_name"]: item
        for item in reviews
    }

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        conn.execute("BEGIN")

        imported_persons = 0
        imported_aliases = 0
        false_positives = 0
        non_character_entities = 0
        low_confidence_blocked = 0

        for item in results:

            candidate_name = item["candidate_name"]

            classification = item["classification"]
            confidence = item["confidence"]

            if classification not in ALLOWED:
                raise RuntimeError(
                    f"Invalid classification: {classification}"
                )

            # ----------------------------------------------------
            # Apply explicit review override
            # ----------------------------------------------------

            review = review_map.get(
                candidate_name
            )

            if review:
                classification = review[
                    "new_classification"
                ]

                confidence = review[
                    "new_confidence"
                ]

                canonical_name = review.get(
                    "canonical_name"
                )

                name_ru = review.get(
                    "name_ru"
                )

                alias_of = review.get(
                    "alias_of"
                )

                reason = review.get(
                    "reason",
                    "Reviewed by Antigravity",
                )

            else:
                canonical_name = item.get(
                    "canonical_name"
                )

                name_ru = item.get(
                    "name_ru"
                )

                alias_of = item.get(
                    "alias_of"
                )

                reason = item.get(
                    "reason",
                    "",
                )

            # ----------------------------------------------------
            # FALSE POSITIVE
            # ----------------------------------------------------

            if classification == "FALSE_POSITIVE":

                false_positives += 1
                continue

            # ----------------------------------------------------
            # ALIAS
            # ----------------------------------------------------

            if classification == "ALIAS":

                if alias_of not in KNOWN_CHARACTER_IDS:
                    raise RuntimeError(
                        f"Invalid alias_of for "
                        f"{candidate_name}: "
                        f"{alias_of}"
                    )

                row = conn.execute(
                    """
                    SELECT id
                    FROM characters
                    WHERE character_id = ?
                    """,
                    (alias_of,),
                ).fetchone()

                if row is None:
                    raise RuntimeError(
                        f"Alias target not found: "
                        f"{alias_of}"
                    )

                character_db_id = row[0]

                alias_value = candidate_name

                conn.execute(
                    """
                    INSERT INTO character_aliases (
                        character_id,
                        alias,
                        language
                    )
                    VALUES (?, ?, 'en')
                    ON CONFLICT(
                        character_id,
                        alias,
                        language
                    )
                    DO NOTHING
                    """,
                    (
                        character_db_id,
                        alias_value,
                    ),
                )

                imported_aliases += 1
                continue

            # ----------------------------------------------------
            # PERSON
            # ----------------------------------------------------

            if classification == "PERSON":

                if confidence < 0.90:
                    low_confidence_blocked += 1
                    continue

                if not canonical_name:
                    canonical_name = candidate_name

                character_id = (
                    "character_"
                    + canonical_name.lower()
                )

                # Normalize ID
                character_id = (
                    character_id
                    .replace(" ", "_")
                    .replace("-", "_")
                    .replace(".", "")
                    .replace("'", "")
                )

                conn.execute(
                    """
                    INSERT INTO characters (
                        character_id,
                        name_original,
                        name_ru,
                        description,
                        status
                    )
                    VALUES (?, ?, ?, ?, 'discovered')
                    ON CONFLICT(character_id)
                    DO UPDATE SET
                        name_original = excluded.name_original,
                        name_ru = excluded.name_ru,
                        description = excluded.description,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        character_id,
                        canonical_name,
                        name_ru,
                        reason,
                    ),
                )

                row = conn.execute(
                    """
                    SELECT id
                    FROM characters
                    WHERE character_id = ?
                    """,
                    (character_id,),
                ).fetchone()

                if row is None:
                    raise RuntimeError(
                        f"Character insert failed: "
                        f"{canonical_name}"
                    )

                character_db_id = row[0]

                conn.execute(
                    """
                    INSERT INTO character_aliases (
                        character_id,
                        alias,
                        language
                    )
                    VALUES (?, ?, 'en')
                    ON CONFLICT(
                        character_id,
                        alias,
                        language
                    )
                    DO NOTHING
                    """,
                    (
                        character_db_id,
                        candidate_name,
                    ),
                )

                imported_persons += 1
                continue

            # ----------------------------------------------------
            # Everything else
            # ----------------------------------------------------

            non_character_entities += 1

        conn.commit()

        # --------------------------------------------------------
        # Validation
        # --------------------------------------------------------

        total_characters = conn.execute(
            """
            SELECT COUNT(*)
            FROM characters
            """
        ).fetchone()[0]

        total_aliases = conn.execute(
            """
            SELECT COUNT(*)
            FROM character_aliases
            """
        ).fetchone()[0]

        print("[OK] Character classification applied")
        print()

        print(
            f"Classification results : "
            f"{len(results)}"
        )

        print(
            f"Review overrides       : "
            f"{len(reviews)}"
        )

        print(
            f"PERSON imported        : "
            f"{imported_persons}"
        )

        print(
            f"ALIAS imported         : "
            f"{imported_aliases}"
        )

        print(
            f"FALSE_POSITIVE        : "
            f"{false_positives}"
        )

        print(
            f"Other entities held   : "
            f"{non_character_entities}"
        )

        print(
            f"Low-confidence blocked: "
            f"{low_confidence_blocked}"
        )

        print()

        print(
            f"Total characters in DB : "
            f"{total_characters}"
        )

        print(
            f"Total aliases in DB    : "
            f"{total_aliases}"
        )

        # --------------------------------------------------------
        # Important verification
        # --------------------------------------------------------

        print()
        print("Important characters:")

        for character_id in (
            "martin_mystery",
            "diana_lombard",
            "java",
            "billy",
            "mom",
        ):

            row = conn.execute(
                """
                SELECT
                    character_id,
                    name_original,
                    name_ru
                FROM characters
                WHERE character_id = ?
                """,
                (character_id,),
            ).fetchone()

            print(
                f"  {row}"
            )

        print()
        print("Ganthar alias:")

        row = conn.execute(
            """
            SELECT
                c.character_id,
                c.name_original,
                a.alias
            FROM character_aliases a
            JOIN characters c
                ON c.id = a.character_id
            WHERE a.alias = 'Ganthar'
            """
        ).fetchone()

        print(
            f"  {row}"
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
