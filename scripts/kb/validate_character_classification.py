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
    / "character_classification_batch.json"
)

RESULT_FILE = (
    ROOT
    / "knowledge"
    / "canonical"
    / "character_classification_results.json"
)


ALLOWED_CLASSIFICATIONS = {
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


KNOWN_CHARACTERS = {
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
    batch = load_json(BATCH_FILE)
    result = load_json(RESULT_FILE)

    input_candidates = batch.get("candidates")
    results = result.get("results")

    if not isinstance(input_candidates, list):
        raise RuntimeError(
            "character_classification_batch.json: "
            "'candidates' is not a list"
        )

    if not isinstance(results, list):
        raise RuntimeError(
            "character_classification_results.json: "
            "'results' is not a list"
        )

    input_names = [
        item["candidate_name"]
        for item in input_candidates
    ]

    result_names = [
        item.get("candidate_name")
        for item in results
    ]

    print("=== BASIC VALIDATION ===")
    print(
        f"Input candidates : {len(input_names)}"
    )
    print(
        f"Results          : {len(result_names)}"
    )

    if len(input_names) != 78:
        raise RuntimeError(
            f"Expected 78 input candidates, "
            f"got {len(input_names)}"
        )

    if len(result_names) != 78:
        raise RuntimeError(
            f"Expected 78 results, "
            f"got {len(result_names)}"
        )

    if len(set(input_names)) != len(input_names):
        raise RuntimeError(
            "Duplicate candidate names in input"
        )

    if len(set(result_names)) != len(result_names):
        raise RuntimeError(
            "Duplicate candidate names in results"
        )

    if set(input_names) != set(result_names):
        missing = set(input_names) - set(result_names)
        extra = set(result_names) - set(input_names)

        raise RuntimeError(
            f"Candidate mismatch. "
            f"Missing={sorted(missing)} "
            f"Extra={sorted(extra)}"
        )

    errors = []

    low_confidence = []

    classification_counts = {}

    alias_results = []

    false_positive_results = []

    for item in results:

        name = item.get(
            "candidate_name"
        )

        classification = item.get(
            "classification"
        )

        confidence = item.get(
            "confidence"
        )

        canonical_name = item.get(
            "canonical_name"
        )

        name_ru = item.get(
            "name_ru"
        )

        alias_of = item.get(
            "alias_of"
        )

        aliases = item.get(
            "aliases"
        )

        reason = item.get(
            "reason"
        )

        if classification not in ALLOWED_CLASSIFICATIONS:
            errors.append(
                f"{name}: invalid classification "
                f"{classification!r}"
            )
            continue

        if not isinstance(
            confidence,
            (int, float),
        ):
            errors.append(
                f"{name}: confidence is not numeric"
            )

        elif not 0.0 <= confidence <= 1.0:
            errors.append(
                f"{name}: confidence outside 0..1"
            )

        elif confidence < 0.90:
            low_confidence.append(
                item
            )

        if not isinstance(
            aliases,
            list,
        ):
            errors.append(
                f"{name}: aliases is not a list"
            )

        if not isinstance(
            reason,
            str,
        ):
            errors.append(
                f"{name}: reason is not a string"
            )

        classification_counts[
            classification
        ] = (
            classification_counts.get(
                classification,
                0,
            )
            + 1
        )

        if classification == "ALIAS":

            alias_results.append(item)

            if not alias_of:
                errors.append(
                    f"{name}: ALIAS without alias_of"
                )

            elif alias_of not in KNOWN_CHARACTERS:
                errors.append(
                    f"{name}: alias_of references "
                    f"unknown character {alias_of!r}"
                )

        if classification == "FALSE_POSITIVE":

            false_positive_results.append(item)

            if canonical_name is not None:
                errors.append(
                    f"{name}: FALSE_POSITIVE has "
                    f"canonical_name"
                )

            if name_ru is not None:
                errors.append(
                    f"{name}: FALSE_POSITIVE has "
                    f"name_ru"
                )

            if alias_of is not None:
                errors.append(
                    f"{name}: FALSE_POSITIVE has "
                    f"alias_of"
                )

            if aliases:
                errors.append(
                    f"{name}: FALSE_POSITIVE has aliases"
                )

    print()

    print("=== CLASSIFICATIONS ===")

    for classification in sorted(
        classification_counts
    ):
        print(
            f"{classification:24s}: "
            f"{classification_counts[classification]}"
        )

    print()

    print(
        "Low-confidence results:",
        len(low_confidence),
    )

    for item in sorted(
        low_confidence,
        key=lambda x: (
            x["confidence"],
            x["candidate_name"].lower(),
        ),
    ):
        print()
        print(
            f"  {item['candidate_name']}"
        )
        print(
            f"    classification = "
            f"{item['classification']}"
        )
        print(
            f"    confidence    = "
            f"{item['confidence']}"
        )
        print(
            f"    canonical     = "
            f"{item['canonical_name']}"
        )
        print(
            f"    name_ru       = "
            f"{item['name_ru']}"
        )
        print(
            f"    alias_of      = "
            f"{item['alias_of']}"
        )
        print(
            f"    reason        = "
            f"{item['reason']}"
        )

    print()

    print("=== ALIASES ===")

    if not alias_results:
        print("  NONE")
    else:
        for item in alias_results:
            print(
                f"  {item['candidate_name']} "
                f"-> {item['alias_of']}"
            )

    print()

    print("=== FALSE POSITIVES ===")
    print(
        f"Count: {len(false_positive_results)}"
    )

    print()

    # ------------------------------------------------------------
    # Check candidate names that look suspiciously important.
    # ------------------------------------------------------------

    suspicious_names = {
        "Ganthar",
        "Billy",
        "Martin",
        "Diana",
        "Java",
        "M.O.M.",
        "Marvin",
        "Kaitlin",
        "Octavia Paine",
        "Gerard",
        "Jenni",
        "Jenny",
    }

    print("=== IMPORTANT NAME CHECK ===")

    for item in results:

        if item["candidate_name"] in suspicious_names:

            print(
                f"  {item['candidate_name']:20s} "
                f"{item['classification']:22s} "
                f"confidence={item['confidence']} "
                f"alias_of={item['alias_of']}"
            )

    print()

    # ------------------------------------------------------------
    # Database validation
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

    conn.close()

    print("=== DATABASE ===")

    for character_id in sorted(
        KNOWN_CHARACTERS
    ):
        if character_id in db_characters:
            print(
                f"  OK      {character_id}"
            )
        else:
            errors.append(
                f"Known character missing from DB: "
                f"{character_id}"
            )
            print(
                f"  MISSING {character_id}"
            )

    print()

    # ------------------------------------------------------------
    # Final result
    # ------------------------------------------------------------

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