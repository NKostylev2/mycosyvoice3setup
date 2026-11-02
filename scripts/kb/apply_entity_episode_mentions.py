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
    / "entity_episode_mentions_results.json"
)


ALLOWED_MENTION_TYPES = {
    "PRIMARY",
    "APPEARS",
    "MENTIONED",
    "BACKGROUND",
}


def main() -> None:
    data = json.loads(
        RESULT_FILE.read_text(
            encoding="utf-8"
        )
    )

    results = data.get("results", [])

    if not results:
        raise RuntimeError(
            "No entity-episode mention results found."
        )

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        conn.execute("BEGIN")

        imported = 0
        updated = 0

        for item in results:

            entity_name = item[
                "entity_candidate_name"
            ]

            canonical_name = item[
                "canonical_name"
            ]

            episode_id = item[
                "episode_id"
            ]

            mention_type = item[
                "mention_type"
            ]

            confidence = item[
                "confidence"
            ]

            reason = item.get(
                "reason",
                ""
            )

            # ----------------------------------------------------
            # Validate mention type
            # ----------------------------------------------------

            if mention_type not in ALLOWED_MENTION_TYPES:
                raise RuntimeError(
                    f"Invalid mention_type for "
                    f"{entity_name} / {episode_id}: "
                    f"{mention_type}"
                )

            if not 0.0 <= confidence <= 1.0:
                raise RuntimeError(
                    f"Invalid confidence for "
                    f"{entity_name} / {episode_id}: "
                    f"{confidence}"
                )

            # ----------------------------------------------------
            # Find entity
            # ----------------------------------------------------

            entity_row = conn.execute(
                """
                SELECT
                    id,
                    entity_type,
                    name_original
                FROM entities
                WHERE name_original = ?
                """,
                (canonical_name,),
            ).fetchone()

            if entity_row is None:
                raise RuntimeError(
                    f"Entity not found: "
                    f"{canonical_name}"
                )

            entity_db_id = entity_row[0]

            # ----------------------------------------------------
            # Find episode
            # ----------------------------------------------------

            episode_row = conn.execute(
                """
                SELECT
                    id,
                    absolute_number,
                    title_original
                FROM episodes
                WHERE episode_id = ?
                """,
                (episode_id,),
            ).fetchone()

            if episode_row is None:
                raise RuntimeError(
                    f"Episode not found: "
                    f"{episode_id}"
                )

            episode_db_id = episode_row[0]

            # ----------------------------------------------------
            # Insert / update
            # ----------------------------------------------------

            existing = conn.execute(
                """
                SELECT id
                FROM entity_episode_mentions
                WHERE entity_id = ?
                  AND episode_id = ?
                  AND mention_type = ?
                """,
                (
                    entity_db_id,
                    episode_db_id,
                    mention_type,
                ),
            ).fetchone()

            conn.execute(
                """
                INSERT INTO entity_episode_mentions (
                    entity_id,
                    episode_id,
                    mention_type,
                    evidence,
                    confidence
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(
                    entity_id,
                    episode_id,
                    mention_type
                )
                DO UPDATE SET
                    evidence = excluded.evidence,
                    confidence = excluded.confidence
                """,
                (
                    entity_db_id,
                    episode_db_id,
                    mention_type,
                    reason,
                    confidence,
                ),
            )

            if existing:
                updated += 1
            else:
                imported += 1

        conn.commit()

        # --------------------------------------------------------
        # Validation
        # --------------------------------------------------------

        total = conn.execute(
            """
            SELECT COUNT(*)
            FROM entity_episode_mentions
            """
        ).fetchone()[0]

        print(
            "[OK] Entity-episode mentions applied"
        )
        print()
        print(
            f"Input results : {len(results)}"
        )
        print(
            f"Inserted      : {imported}"
        )
        print(
            f"Updated       : {updated}"
        )
        print(
            f"Total in DB   : {total}"
        )

        print()
        print("By mention type:")

        rows = conn.execute(
            """
            SELECT
                mention_type,
                COUNT(*)
            FROM entity_episode_mentions
            GROUP BY mention_type
            ORDER BY mention_type
            """
        ).fetchall()

        for mention_type, count in rows:
            print(
                f"  {mention_type:12s}: {count}"
            )

        print()
        print("Entity usage:")

        rows = conn.execute(
            """
            SELECT
                e.entity_type,
                e.name_original,
                COUNT(m.id)
            FROM entities e
            JOIN entity_episode_mentions m
                ON m.entity_id = e.id
            GROUP BY
                e.id
            ORDER BY
                e.entity_type,
                e.name_original
            """
        ).fetchall()

        for entity_type, name, count in rows:
            print(
                f"  {entity_type:22s} "
                f"{name:35s} "
                f"episodes={count}"
            )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()