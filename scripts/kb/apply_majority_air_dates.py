from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"
ANALYSIS_FILE = (
    ROOT
    / "knowledge"
    / "canonical"
    / "air_date_analysis.json"
)


def main() -> None:
    data = json.loads(
        ANALYSIS_FILE.read_text(
            encoding="utf-8"
        )
    )

    episodes = data.get("episodes", [])

    majority = [
        item
        for item in episodes
        if item.get("category") == "MAJORITY_2_TO_1_OR_MORE"
        and item.get("consensus_date")
    ]

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        conn.execute("BEGIN")

        applied = 0
        skipped = 0

        for item in majority:

            episode_id = item["episode_id"]
            canonical_date = item["consensus_date"]
            consensus_sources = item.get(
                "consensus_sources",
                [],
            )

            row = conn.execute(
                """
                SELECT id, air_date
                FROM episodes
                WHERE episode_id = ?
                """,
                (episode_id,),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    f"Episode not found: {episode_id}"
                )

            episode_db_id = row[0]
            current_date = row[1]

            # Если ранее установлена такая же дата,
            # просто обновляем resolution.
            if current_date == canonical_date:
                skipped += 1
            else:
                conn.execute(
                    """
                    UPDATE episodes
                    SET
                        air_date = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        canonical_date,
                        episode_db_id,
                    ),
                )

            sources_text = ", ".join(
                consensus_sources
            )

            resolution_text = (
                "MAJORITY_OF_SOURCES; "
                f"consensus={sources_text}; "
                "external_verification_status=not_performed"
            )

            # Закрываем только конфликты этого эпизода,
            # для которых resolved_value совпадает
            # с majority date.
            conn.execute(
                """
                UPDATE knowledge_conflicts
                SET
                    resolution = ?,
                    resolved_value = ?,
                    status = 'resolved',
                    resolved_at = CURRENT_TIMESTAMP
                WHERE entity_type = 'episode'
                  AND entity_id = ?
                  AND field_name = 'air_date'
                  AND status = 'open'
                """,
                (
                    resolution_text,
                    canonical_date,
                    episode_id,
                ),
            )

            applied += 1

        conn.commit()

        # --------------------------------------------------------
        # Validation
        # --------------------------------------------------------

        total_episodes = conn.execute(
            """
            SELECT COUNT(*)
            FROM episodes
            """
        ).fetchone()[0]

        with_dates = conn.execute(
            """
            SELECT COUNT(*)
            FROM episodes
            WHERE air_date IS NOT NULL
            """
        ).fetchone()[0]

        open_conflicts = conn.execute(
            """
            SELECT COUNT(*)
            FROM knowledge_conflicts
            WHERE entity_type = 'episode'
              AND field_name = 'air_date'
              AND status = 'open'
            """
        ).fetchone()[0]

        resolved_conflicts = conn.execute(
            """
            SELECT COUNT(*)
            FROM knowledge_conflicts
            WHERE entity_type = 'episode'
              AND field_name = 'air_date'
              AND status = 'resolved'
            """
        ).fetchone()[0]

        print("[OK] Majority air-date resolutions applied")
        print()
        print(f"Majority episodes        : {len(majority)}")
        print(f"Applied                   : {applied}")
        print(f"Already had same date    : {skipped}")
        print(f"Total episodes            : {total_episodes}")
        print(f"Episodes with air_date   : {with_dates}")
        print(f"Resolved conflicts        : {resolved_conflicts}")
        print(f"Open conflicts            : {open_conflicts}")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
