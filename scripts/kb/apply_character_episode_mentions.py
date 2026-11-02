from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB_PATH = ROOT / "database" / "dubbing.db"
RESULTS_PATH = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_episode_mentions_results.json"
)

VALID_ROLES = {
    "PRIMARY",
    "APPEARS",
    "MENTIONED",
    "BACKGROUND",
}

FALSE_POSITIVE = "FALSE_POSITIVE"


def load_results() -> list[dict]:
    """Load and validate Antigravity result file."""

    if not RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"Results file not found:\n{RESULTS_PATH}"
        )

    with RESULTS_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, dict):
        raise ValueError(
            "Root JSON must be an object."
        )

    schema_version = payload.get("schema_version")

    if schema_version != "0.1":
        raise ValueError(
            f"Unsupported schema_version: {schema_version!r}"
        )

    results = payload.get("results")

    if not isinstance(results, list):
        raise ValueError(
            "JSON field 'results' must be an array."
        )

    return results


def get_character_db_id(
    conn: sqlite3.Connection,
    character_id: str,
) -> int | None:

    row = conn.execute(
        """
        SELECT id
        FROM characters
        WHERE character_id = ?
        """,
        (character_id,),
    ).fetchone()

    return row[0] if row else None


def get_episode_db_id(
    conn: sqlite3.Connection,
    episode_id: str,
) -> int | None:

    row = conn.execute(
        """
        SELECT id
        FROM episodes
        WHERE episode_id = ?
        """,
        (episode_id,),
    ).fetchone()

    return row[0] if row else None


def main() -> None:

    print("=== CHARACTER EPISODE MENTIONS IMPORT ===")
    print()

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found:\n{DB_PATH}"
        )

    results = load_results()

    print(f"Results loaded : {len(results)}")
    print()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    inserted = 0
    already_exists = 0
    false_positive = 0
    invalid_records = 0
    invalid_roles = 0
    missing_characters = 0
    missing_episodes = 0

    try:
        conn.execute("BEGIN")

        for index, item in enumerate(results, start=1):

            if not isinstance(item, dict):
                print(
                    f"[ERROR] Result #{index} is not a JSON object."
                )
                invalid_records += 1
                continue

            character_id = item.get("character_id")
            episode_id = item.get("episode_id")
            role_type = item.get("role_type")
            confidence = item.get("confidence")

            # Antigravity uses "reason".
            # Database schema uses "evidence".
            evidence = item.get("reason")

            # ------------------------------------------------
            # Required fields
            # ------------------------------------------------

            if not character_id:
                print(
                    f"[ERROR] Result #{index}: "
                    "missing character_id."
                )
                invalid_records += 1
                continue

            if not episode_id:
                print(
                    f"[ERROR] Result #{index}: "
                    "missing episode_id."
                )
                invalid_records += 1
                continue

            if not role_type:
                print(
                    f"[ERROR] Result #{index}: "
                    "missing role_type."
                )
                invalid_records += 1
                continue

            # ------------------------------------------------
            # FALSE POSITIVE
            # ------------------------------------------------

            if role_type == FALSE_POSITIVE:
                false_positive += 1
                continue

            # ------------------------------------------------
            # Validate role
            # ------------------------------------------------

            if role_type not in VALID_ROLES:
                print(
                    f"[ERROR] Result #{index}: "
                    f"unknown role_type={role_type!r}"
                )
                invalid_roles += 1
                continue

            # ------------------------------------------------
            # Find character
            # ------------------------------------------------

            character_db_id = get_character_db_id(
                conn,
                character_id,
            )

            if character_db_id is None:
                print(
                    f"[ERROR] Character not found: "
                    f"{character_id}"
                )
                missing_characters += 1
                continue

            # ------------------------------------------------
            # Find episode
            # ------------------------------------------------

            episode_db_id = get_episode_db_id(
                conn,
                episode_id,
            )

            if episode_db_id is None:
                print(
                    f"[ERROR] Episode not found: "
                    f"{episode_id}"
                )
                missing_episodes += 1
                continue

            # ------------------------------------------------
            # Idempotency check
            # ------------------------------------------------

            existing = conn.execute(
                """
                SELECT id
                FROM character_episode_mentions
                WHERE character_id = ?
                  AND episode_id = ?
                  AND role_type = ?
                """,
                (
                    character_db_id,
                    episode_db_id,
                    role_type,
                ),
            ).fetchone()

            if existing is not None:
                already_exists += 1
                continue

            # ------------------------------------------------
            # Insert
            # ------------------------------------------------

            conn.execute(
                """
                INSERT INTO character_episode_mentions (
                    character_id,
                    episode_id,
                    role_type,
                    evidence,
                    confidence
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    character_db_id,
                    episode_db_id,
                    role_type,
                    evidence,
                    confidence,
                ),
            )

            inserted += 1

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    # ========================================================
    # DATABASE VERIFICATION
    # ========================================================

    conn = sqlite3.connect(DB_PATH)

    try:
        total = conn.execute(
            """
            SELECT COUNT(*)
            FROM character_episode_mentions
            """
        ).fetchone()[0]

        role_distribution = conn.execute(
            """
            SELECT
                role_type,
                COUNT(*)
            FROM character_episode_mentions
            GROUP BY role_type
            ORDER BY role_type
            """
        ).fetchall()

    finally:
        conn.close()

    # ========================================================
    # REPORT
    # ========================================================

    print()
    print("=== IMPORT COMPLETE ===")
    print()

    print(f"Results loaded          : {len(results)}")
    print(f"Inserted                : {inserted}")
    print(f"Already existed         : {already_exists}")
    print(f"FALSE_POSITIVE skipped : {false_positive}")
    print(f"Invalid records         : {invalid_records}")
    print(f"Invalid roles           : {invalid_roles}")
    print(f"Missing characters      : {missing_characters}")
    print(f"Missing episodes        : {missing_episodes}")
    print(f"DB total mentions       : {total}")

    print()
    print("=== DB ROLE DISTRIBUTION ===")

    if role_distribution:
        for role, count in role_distribution:
            print(f"{role:<18}: {count}")
    else:
        print("No records.")

    # ========================================================
    # FINAL CONSISTENCY CHECK
    # ========================================================

    expected_importable = len(results) - false_positive
    processed = inserted + already_exists

    print()
    print("=== CONSISTENCY CHECK ===")
    print()

    print(
        f"Expected importable : {expected_importable}"
    )
    print(
        f"Processed           : {processed}"
    )

    if (
        invalid_records == 0
        and invalid_roles == 0
        and missing_characters == 0
        and missing_episodes == 0
        and processed == expected_importable
    ):
        print("CONSISTENCY CHECK: PASSED")
    else:
        print("CONSISTENCY CHECK: FAILED")


if __name__ == "__main__":
    main()