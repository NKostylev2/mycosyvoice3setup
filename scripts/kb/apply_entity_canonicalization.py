from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"

RESULT_FILE = (
    ROOT
    / "knowledge"
    / "canonical"
    / "entity_canonicalization_results.json"
)


ALLOWED_TYPES = {
    "CREATURE",
    "MONSTER",
    "SUPERNATURAL_ENTITY",
    "ORGANIZATION",
    "LOCATION",
    "OBJECT",
}


def make_entity_id(
    entity_type: str,
    canonical_name: str,
) -> str:
    """
    Build a stable human-readable entity ID.
    """

    value = canonical_name.lower().strip()

    value = value.replace("&", "and")

    value = re.sub(
        r"[^\w\s-]",
        "",
        value,
        flags=re.UNICODE,
    )

    value = re.sub(
        r"[-\s]+",
        "_",
        value,
    )

    value = value.strip("_")

    return f"{entity_type.lower()}_{value}"


def main() -> None:

    data = json.loads(
        RESULT_FILE.read_text(
            encoding="utf-8"
        )
    )

    results = data.get(
        "results",
        []
    )

    conn = sqlite3.connect(DB)
    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    try:

        conn.execute("BEGIN")

        imported = 0
        skipped_false_positive = 0
        skipped_low_confidence = 0

        for item in results:

            candidate_name = item[
                "candidate_name"
            ]

            decision = item[
                "decision"
            ]

            entity_type = item[
                "entity_type"
            ]

            confidence = item[
                "confidence"
            ]

            canonical_name = item.get(
                "canonical_name"
            )

            name_ru = item.get(
                "name_ru"
            )

            description = item.get(
                "description",
                ""
            )

            aliases = item.get(
                "aliases",
                []
            )

            reason = item.get(
                "reason",
                ""
            )

            # ----------------------------------------------------
            # FALSE POSITIVE
            # ----------------------------------------------------

            if (
                decision == "FALSE_POSITIVE"
                or entity_type == "FALSE_POSITIVE"
            ):
                skipped_false_positive += 1
                continue

            if entity_type not in ALLOWED_TYPES:
                raise RuntimeError(
                    f"Invalid entity type "
                    f"for {candidate_name}: "
                    f"{entity_type}"
                )

            if confidence < 0.90:
                skipped_low_confidence += 1
                continue

            if not canonical_name:
                raise RuntimeError(
                    f"Missing canonical_name "
                    f"for {candidate_name}"
                )

            entity_id = make_entity_id(
                entity_type,
                canonical_name,
            )

            metadata = {
                "source_candidate": candidate_name,
                "classification_confidence": confidence,
                "classification_reason": reason,
                "aliases": aliases,
            }

            conn.execute(
                """
                INSERT INTO entities (
                    entity_id,
                    entity_type,
                    name_original,
                    name_ru,
                    description,
                    status,
                    metadata_json
                )
                VALUES (
                    ?, ?, ?, ?, ?, 'discovered', ?
                )
                ON CONFLICT(entity_id)
                DO UPDATE SET
                    entity_type = excluded.entity_type,
                    name_original = excluded.name_original,
                    name_ru = excluded.name_ru,
                    description = excluded.description,
                    metadata_json = excluded.metadata_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    entity_id,
                    entity_type,
                    canonical_name,
                    name_ru,
                    description,
                    json.dumps(
                        metadata,
                        ensure_ascii=False,
                    ),
                ),
            )

            imported += 1

        conn.commit()

        # --------------------------------------------------------
        # Validation
        # --------------------------------------------------------

        entity_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM entities
            """
        ).fetchone()[0]

        print(
            "[OK] Entity canonicalization applied"
        )
        print()

        print(
            f"Classification results : "
            f"{len(results)}"
        )

        print(
            f"Entities imported      : "
            f"{imported}"
        )

        print(
            f"FALSE_POSITIVE skipped : "
            f"{skipped_false_positive}"
        )

        print(
            f"Low-confidence skipped : "
            f"{skipped_low_confidence}"
        )

        print(
            f"Total entities in DB   : "
            f"{entity_count}"
        )

        print()
        print(
            "Entities by type:"
        )

        rows = conn.execute(
            """
            SELECT
                entity_type,
                COUNT(*)
            FROM entities
            GROUP BY entity_type
            ORDER BY entity_type
            """
        ).fetchall()

        for entity_type, count in rows:
            print(
                f"  {entity_type:24s}: "
                f"{count}"
            )

        print()
        print(
            "Entities:"
        )

        rows = conn.execute(
            """
            SELECT
                entity_id,
                entity_type,
                name_original,
                name_ru
            FROM entities
            ORDER BY entity_type, name_original
            """
        ).fetchall()

        for row in rows:
            print(
                f"  {row[0]:45s} "
                f"{row[2]} "
                f"({row[3]})"
            )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()