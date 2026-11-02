from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"

BATCH_FILE = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_episode_mentions_batch.json"
)

RESULT_FILE = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_episode_mentions_results.json"
)


ALLOWED_ROLE_TYPES = {
    "PRIMARY",
    "APPEARS",
    "MENTIONED",
    "BACKGROUND",
    "FALSE_POSITIVE",
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    batch = load_json(BATCH_FILE)
    result = load_json(RESULT_FILE)

    batch_characters = batch.get(
        "characters",
        []
    )

    results = result.get(
        "results",
        []
    )

    # ------------------------------------------------------------
    # Build expected mention keys
    # ------------------------------------------------------------

    expected = []

    for character in batch_characters:

        character_id = character[
            "character_id"
        ]

        for mention in character.get(
            "mention_candidates",
            []
        ):

            expected.append(
                (
                    character_id,
                    mention["episode_id"],
                )
            )

    actual = []

    for item in results:

        actual.append(
            (
                item["character_id"],
                item["episode_id"],
            )
        )

    expected_set = set(expected)
    actual_set = set(actual)

    errors = []

    # ------------------------------------------------------------
    # Basic checks
    # ------------------------------------------------------------

    print("=== BASIC VALIDATION ===")
    print(
        f"Batch characters : "
        f"{len(batch_characters)}"
    )
    print(
        f"Expected mentions: "
        f"{len(expected)}"
    )
    print(
        f"Results          : "
        f"{len(results)}"
    )

    if len(results) != len(expected):
        errors.append(
            "Result count does not match "
            "input mention count."
        )

    if len(actual) != len(actual_set):
        errors.append(
            "Duplicate character_id + episode_id "
            "pairs detected."
        )

    missing = expected_set - actual_set
    extra = actual_set - expected_set

    if missing:
        errors.append(
            f"Missing pairs: {sorted(missing)}"
        )

    if extra:
        errors.append(
            f"Unexpected pairs: {sorted(extra)}"
        )

    # ------------------------------------------------------------
    # Database IDs
    # ------------------------------------------------------------

    conn = sqlite3.connect(DB)

    db_characters = {
        row[0]
        for row in conn.execute(
            """
            SELECT character_id
            FROM characters
            """
        )
    }

    db_episodes = {
        row[0]
        for row in conn.execute(
            """
            SELECT episode_id
            FROM episodes
            """
        )
    }

    # ------------------------------------------------------------
    # Validate individual results
    # ------------------------------------------------------------

    role_counts = {}
    low_confidence = []

    for item in results:

        character_id = item.get(
            "character_id"
        )

        episode_id = item.get(
            "episode_id"
        )

        role_type = item.get(
            "role_type"
        )

        confidence = item.get(
            "confidence"
        )

        reason = item.get(
            "reason"
        )

        if character_id not in db_characters:
            errors.append(
                f"Unknown character_id: "
                f"{character_id}"
            )

        if episode_id not in db_episodes:
            errors.append(
                f"Unknown episode_id: "
                f"{episode_id}"
            )

        if role_type not in ALLOWED_ROLE_TYPES:
            errors.append(
                f"Invalid role_type for "
                f"{character_id}/{episode_id}: "
                f"{role_type}"
            )

        if not isinstance(
            confidence,
            (int, float),
        ):
            errors.append(
                f"Invalid confidence for "
                f"{character_id}/{episode_id}"
            )

        elif not 0.0 <= confidence <= 1.0:
            errors.append(
                f"Confidence outside [0,1] for "
                f"{character_id}/{episode_id}: "
                f"{confidence}"
            )

        elif confidence < 0.90:
            low_confidence.append(item)

        if not isinstance(
            reason,
            str,
        ):
            errors.append(
                f"Missing/invalid reason for "
                f"{character_id}/{episode_id}"
            )

        role_counts[role_type] = (
            role_counts.get(
                role_type,
                0,
            )
            + 1
        )

    # ------------------------------------------------------------
    # Print role distribution
    # ------------------------------------------------------------

    print()
    print("=== ROLE DISTRIBUTION ===")

    for role_type in sorted(
        ALLOWED_ROLE_TYPES
    ):
        print(
            f"{role_type:16s}: "
            f"{role_counts.get(role_type, 0)}"
        )

    print()
    print(
        "Low-confidence results:",
        len(low_confidence),
    )

    for item in low_confidence:

        print(
            f"  {item['character_id']:25s} "
            f"{item['episode_id']:22s} "
            f"{item['role_type']:12s} "
            f"{item['confidence']}"
        )

    # ------------------------------------------------------------
    # Important consistency checks
    # ------------------------------------------------------------

    print()
    print("=== IMPORTANT CHARACTER CHECK ===")

    important = {
        "martin_mystery",
        "diana_lombard",
        "java",
        "billy",
        "mom",
        "character_marvin",
        "character_kaitlin",
        "character_gerard_mystery",
        "character_jenni",
        "character_jenny",
        "character_vivian_michelle",
        "character_octavia_paine",
    }

    for character_id in sorted(
        important
    ):

        count = sum(
            1
            for item in results
            if item["character_id"]
            == character_id
        )

        if character_id in db_characters:
            print(
                f"  {character_id:25s} "
                f"candidates={count}"
            )

    # ------------------------------------------------------------
    # Specific semantic checks
    # ------------------------------------------------------------

    print()
    print("=== SEMANTIC CHECKS ===")

    ganthar_alias = conn.execute(
        """
        SELECT COUNT(*)
        FROM character_aliases
        WHERE character_id = (
            SELECT id
            FROM characters
            WHERE character_id = 'billy'
        )
        AND alias = 'Ganthar'
        """
    ).fetchone()[0]

    print(
        f"  Ganthar -> Billy alias: "
        f"{'OK' if ganthar_alias else 'MISSING'}"
    )

    jenni_41 = [
        item
        for item in results
        if item["character_id"]
        == "character_jenni"
        and item["episode_id"]
        == "martin_mystery_041"
    ]

    if jenni_41:
        print(
            "  Jenni Ep41: "
            f"{jenni_41[0]['role_type']}"
        )

    jenny_36 = [
        item
        for item in results
        if item["character_id"]
        == "character_jenny"
        and item["episode_id"]
        == "martin_mystery_036"
    ]

    if jenny_36:
        print(
            "  Jenny Ep36: "
            f"{jenny_36[0]['role_type']}"
        )

    vivian_59 = [
        item
        for item in results
        if item["character_id"]
        == "character_vivian_michelle"
        and item["episode_id"]
        == "martin_mystery_059"
    ]

    if vivian_59:
        print(
            "  Vivian Ep59: "
            f"{vivian_59[0]['role_type']}"
        )

    conn.close()

    # ------------------------------------------------------------
    # Final result
    # ------------------------------------------------------------

    print()

    if errors:

        print(
            "=== VALIDATION FAILED ==="
        )

        for error in errors:
            print(
                f"ERROR: {error}"
            )

        raise SystemExit(1)

    print(
        "=== VALIDATION PASSED ==="
    )


if __name__ == "__main__":
    main()