from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DB_FILE = ROOT / "database" / "dubbing.db"
CANONICAL_FILE = (
    ROOT / "knowledge" / "canonical" / "episodes_canonical.json"
)

EXPECTED_EPISODES = 66

SOURCE_NAMES = {
    "wikipedia": "Wikipedia",
    "epguides": "epguides",
    "thetvdb": "TheTVDB",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_source_id(
    conn: sqlite3.Connection,
    source_name: str,
) -> int:

    row = conn.execute(
        """
        SELECT id
        FROM sources
        WHERE source_name = ?
        ORDER BY id
        LIMIT 1
        """,
        (source_name,),
    ).fetchone()

    if row is None:
        raise RuntimeError(
            f"Источник не найден в БД: {source_name}"
        )

    return int(row[0])


def reset_series_data(
    conn: sqlite3.Connection,
    series_db_id: int,
) -> None:

    # Поскольку это первоначальная canonical seed-загрузка,
    # полностью удаляем старый набор эпизодов этой серии.
    #
    # CASCADE очистит связанные:
    # episode_source_records
    # episode_sources
    # broadcast_events
    # episode_facts
    # scenes -> dialogue
    #
    # jobs имеют ON DELETE SET NULL.
    conn.execute(
        """
        DELETE FROM episodes
        WHERE series_id = ?
        """,
        (series_db_id,),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Полностью пересоздать canonical episodes этой серии",
    )
    args = parser.parse_args()

    data = load_json(CANONICAL_FILE)

    episodes = data.get("episodes", [])

    if len(episodes) != EXPECTED_EPISODES:
        raise RuntimeError(
            f"Ожидалось {EXPECTED_EPISODES} эпизодов, "
            f"получено {len(episodes)}"
        )

    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        conn.execute("BEGIN")

        # --------------------------------------------------------
        # SERIES
        # --------------------------------------------------------

        series = conn.execute(
            """
            SELECT id
            FROM series
            WHERE series_id = ?
            """,
            ("martin_mystery",),
        ).fetchone()

        if series is None:
            raise RuntimeError(
                "Серия martin_mystery отсутствует в БД. "
                "Сначала выполните seed.py."
            )

        series_db_id = int(series[0])

        # --------------------------------------------------------
        # SOURCES
        # --------------------------------------------------------

        source_ids = {
            key: get_source_id(conn, source_name)
            for key, source_name in SOURCE_NAMES.items()
        }

        # --------------------------------------------------------
        # RESET
        # --------------------------------------------------------

        if args.reset:
            print("[RESET] Removing existing episodes...")
            reset_series_data(conn, series_db_id)

        # --------------------------------------------------------
        # EPISODES
        # --------------------------------------------------------

        episode_db_ids: dict[str, int] = {}

        for episode in episodes:

            episode_id = episode["episode_id"]

            cursor = conn.execute(
                """
                INSERT INTO episodes (
                    series_id,
                    episode_id,
                    absolute_number,
                    season_number,
                    episode_number,
                    production_number,
                    title_original,
                    title_ru,
                    title_alt,
                    air_date,
                    synopsis_short,
                    synopsis_detailed,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(episode_id)
                DO UPDATE SET
                    series_id = excluded.series_id,
                    absolute_number = excluded.absolute_number,
                    season_number = excluded.season_number,
                    episode_number = excluded.episode_number,
                    production_number = excluded.production_number,
                    title_original = excluded.title_original,
                    title_alt = excluded.title_alt,
                    air_date = excluded.air_date,
                    synopsis_short = excluded.synopsis_short,
                    synopsis_detailed = excluded.synopsis_detailed,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    series_db_id,
                    episode_id,
                    episode.get("absolute_number"),
                    episode.get("season_number"),
                    episode.get("episode_number"),
                    episode.get("production_number"),
                    episode["title_original"],
                    episode.get("title_ru"),
                    episode.get("title_alt"),
                    episode.get("air_date"),
                    episode.get("synopsis_short"),
                    episode.get("synopsis_detailed"),
                    episode.get("status", "discovered"),
                ),
            )

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
                    f"Не удалось получить DB id для {episode_id}"
                )

            episode_db_id = int(row[0])
            episode_db_ids[episode_id] = episode_db_id

            # ----------------------------------------------------
            # IDENTITY FACTS
            # ----------------------------------------------------

            identity = episode.get("identity", {})

            facts = [
                (
                    "identity",
                    "identity_confidence",
                    identity.get("confidence"),
                ),
                (
                    "identity",
                    "identity_status",
                    identity.get("status"),
                ),
                (
                    "identity",
                    "thetvdb_match_type",
                    identity.get("thetvdb_match_type"),
                ),
                (
                    "metadata",
                    "writer",
                    episode.get("writer"),
                ),
                (
                    "metadata",
                    "villains_monsters",
                    episode.get("villains_monsters"),
                ),
            ]

            for fact_type, fact_key, fact_value in facts:

                if fact_value is None:
                    continue

                if isinstance(fact_value, (dict, list)):
                    fact_value = json.dumps(
                        fact_value,
                        ensure_ascii=False,
                    )

                confidence = identity.get("confidence")

                if confidence is None:
                    confidence = 1.0

                conn.execute(
                    """
                    INSERT INTO episode_facts (
                        episode_id,
                        fact_type,
                        fact_key,
                        fact_value,
                        confidence,
                        verified,
                        notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        episode_db_id,
                        fact_type,
                        fact_key,
                        str(fact_value),
                        float(confidence),
                        0,
                        "Imported from identity mapping",
                    ),
                )

            # ----------------------------------------------------
            # SOURCE RECORDS
            # ----------------------------------------------------

            for record in episode.get(
                "source_records",
                [],
            ):

                source_key = record["source"]

                if source_key not in source_ids:
                    raise RuntimeError(
                        f"Неизвестный source: {source_key}"
                    )

                source_db_id = source_ids[source_key]

                source_record_id = record.get(
                    "source_record_id"
                )

                # source_record_id должен быть уникален
                # внутри конкретного источника.
                if not source_record_id:
                    source_record_id = (
                        f"{episode_id}:{source_key}:"
                        f"{record.get('season_number')}:"
                        f"{record.get('episode_number')}"
                    )

                metadata = record.get("metadata", {})

                if not isinstance(metadata, dict):
                    metadata = {
                        "raw_metadata": metadata
                    }

                metadata["canonical_episode_id"] = episode_id

                conn.execute(
                    """
                    INSERT INTO episode_source_records (
                        episode_id,
                        source_id,
                        source_record_id,
                        season_number,
                        episode_number,
                        absolute_number,
                        title_original,
                        air_date_raw,
                        source_url,
                        match_type,
                        confidence,
                        matched,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id, source_record_id)
                    DO UPDATE SET
                        episode_id = excluded.episode_id,
                        season_number = excluded.season_number,
                        episode_number = excluded.episode_number,
                        absolute_number = excluded.absolute_number,
                        title_original = excluded.title_original,
                        air_date_raw = excluded.air_date_raw,
                        source_url = excluded.source_url,
                        match_type = excluded.match_type,
                        confidence = excluded.confidence,
                        matched = excluded.matched,
                        metadata_json = excluded.metadata_json
                    """,
                    (
                        episode_db_id,
                        source_db_id,
                        str(source_record_id),
                        record.get("season_number"),
                        record.get("episode_number"),
                        record.get("absolute_number"),
                        record.get("title_original"),
                        record.get("air_date_raw"),
                        record.get("source_url"),
                        record.get("match_type"),
                        record.get("confidence"),
                        1 if record.get("matched", True) else 0,
                        json.dumps(
                            metadata,
                            ensure_ascii=False,
                        ),
                    ),
                )

        # --------------------------------------------------------
        # COMMIT
        # --------------------------------------------------------

        conn.commit()

        # --------------------------------------------------------
        # VALIDATION
        # --------------------------------------------------------

        episode_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM episodes
            WHERE series_id = ?
            """,
            (series_db_id,),
        ).fetchone()[0]

        source_record_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM episode_source_records r
            JOIN episodes e
              ON e.id = r.episode_id
            WHERE e.series_id = ?
            """,
            (series_db_id,),
        ).fetchone()[0]

        tvdb_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM episode_source_records r
            JOIN episodes e
              ON e.id = r.episode_id
            JOIN sources s
              ON s.id = r.source_id
            WHERE e.series_id = ?
              AND s.source_name = 'TheTVDB'
            """,
            (series_db_id,),
        ).fetchone()[0]

        print()
        print("[OK] Canonical seed completed")
        print()
        print(f"Episodes              : {episode_count}")
        print(f"Source records        : {source_record_count}")
        print(f"TheTVDB records       : {tvdb_count}")
        print()

        if episode_count != EXPECTED_EPISODES:
            raise RuntimeError(
                f"В БД должно быть {EXPECTED_EPISODES} "
                f"эпизодов, найдено {episode_count}"
            )

        if tvdb_count != 66:
            raise RuntimeError(
                f"Ожидалось 66 записей TheTVDB, "
                f"получено {tvdb_count}"
            )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
