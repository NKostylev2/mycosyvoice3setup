from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "database" / "dubbing.db"

RESOLUTION_FILE = (
    ROOT
    / "knowledge"
    / "canonical"
    / "title_resolutions.json"
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
            canonical_title = item["canonical_title_en"]
            resolution = item["resolution"]
            confidence = item["confidence"]

            source_variants = item.get(
                "source_variants",
                {}
            )

            row = conn.execute(
                """
                SELECT id, title_original
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
            current_title = row[1]

            if current_title != canonical_title:
                raise RuntimeError(
                    f"Canonical title mismatch for {episode_id}: "
                    f"DB={current_title!r}, "
                    f"resolution={canonical_title!r}"
                )

            for source_name, variant in source_variants.items():

                existing = conn.execute(
                    """
                    SELECT id
                    FROM knowledge_conflicts
                    WHERE entity_type = 'episode'
                      AND entity_id = ?
                      AND field_name = 'title_original'
                      AND source_a = ?
                      AND value_a = ?
                    LIMIT 1
                    """,
                    (
                        episode_id,
                        source_name,
                        variant,
                    ),
                ).fetchone()

                if existing:
                    continue

                conn.execute(
                    """
                    INSERT INTO knowledge_conflicts (
                        entity_type,
                        entity_id,
                        field_name,
                        source_a,
                        value_a,
                        source_b,
                        value_b,
                        resolution,
                        resolved_value,
                        status,
                        resolved_at
                    )
                    VALUES (
                        'episode',
                        ?,
                        'title_original',
                        ?,
                        ?,
                        'canonical',
                        ?,
                        ?,
                        ?,
                        'resolved',
                        CURRENT_TIMESTAMP
                    )
                    """,
                    (
                        episode_id,
                        source_name,
                        variant,
                        canonical_title,
                        (
                            f"{resolution}; "
                            f"confidence={confidence}"
                        ),
                        canonical_title,
                    ),
                )

            applied += 1

        conn.commit()

        resolved = conn.execute(
            """
            SELECT COUNT(*)
            FROM knowledge_conflicts
            WHERE entity_type = 'episode'
              AND field_name = 'title_original'
              AND status = 'resolved'
            """
        ).fetchone()[0]

        print("[OK] Title resolutions applied")
        print()
        print(f"Resolution records : {len(resolutions)}")
        print(f"Applied             : {applied}")
        print(f"Resolved conflicts  : {resolved}")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()