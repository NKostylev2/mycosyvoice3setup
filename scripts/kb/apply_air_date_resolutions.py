from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"
RESOLUTION_FILE = (
    ROOT / "knowledge" / "canonical" / "air_date_resolutions.json"
)


def main() -> None:
    data = json.loads(
        RESOLUTION_FILE.read_text(
            encoding="utf-8"
        )
    )

    resolutions = data.get("resolutions", [])

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        conn.execute("BEGIN")

        applied = 0

        for item in resolutions:

            episode_id = item["episode_id"]
            canonical_date = item["canonical_date"]
            confidence = item["confidence"]
            resolution = item["resolution"]

            verification_sources = ", ".join(
                item.get("verification_sources", [])
            )

            # ----------------------------------------------------
            # Получаем DB episode ID
            # ----------------------------------------------------

            row = conn.execute(
                """
                SELECT id
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

            # ----------------------------------------------------
            # Записываем canonical air_date
            # ----------------------------------------------------

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

            # ----------------------------------------------------
            # Помечаем соответствующие конфликты resolved
            # ----------------------------------------------------

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
                    (
                        f"{resolution}; "
                        f"verification_sources={verification_sources}; "
                        f"confidence={confidence}"
                    ),
                    canonical_date,
                    episode_id,
                ),
            )

            applied += 1

        conn.commit()

        # --------------------------------------------------------
        # Validation
        # --------------------------------------------------------

        resolved = conn.execute(
            """
            SELECT COUNT(*)
            FROM knowledge_conflicts
            WHERE entity_type = 'episode'
              AND field_name = 'air_date'
              AND status = 'resolved'
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

        dates_filled = conn.execute(
            """
            SELECT COUNT(*)
            FROM episodes
            WHERE air_date IS NOT NULL
            """
        ).fetchone()[0]

        print("[OK] Air-date resolutions applied")
        print()
        print(f"Resolutions loaded       : {len(resolutions)}")
        print(f"Resolutions applied      : {applied}")
        print(f"Episodes with air_date   : {dates_filled}")
        print(f"Resolved conflicts       : {resolved}")
        print(f"Open conflicts           : {open_conflicts}")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()