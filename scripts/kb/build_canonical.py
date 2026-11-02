from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CANONICAL_DIR = ROOT / "knowledge" / "canonical"

MAPPING_FILE = CANONICAL_DIR / "episode_identity_mapping.json"
OUTPUT_FILE = CANONICAL_DIR / "episodes_canonical.json"

EXPECTED_EPISODES = 66


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_date(value: Any) -> str | None:
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    # Уже ISO
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value

    formats = [
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass

    return None


def get_mapping_records(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return raw

    if isinstance(raw, dict):
        for key in ("episodes", "mapping", "records", "items"):
            value = raw.get(key)
            if isinstance(value, list):
                return value

    raise ValueError(
        "episode_identity_mapping.json имеет неизвестную структуру. "
        "Ожидался список или объект с episodes/mapping/records/items."
    )


def safe_source_record(
    source_name: str,
    source: dict[str, Any] | None,
    canonical: dict[str, Any],
) -> dict[str, Any] | None:

    if not source or not source.get("matched", True):
        return None

    if source_name == "thetvdb":
        records = source.get("records", [])

        if not isinstance(records, list):
            records = [records]

        result = []

        for record in records:
            if not isinstance(record, dict):
                continue

            result.append(
                {
                    "source": "thetvdb",
                    "source_record_id": record.get("episode_id"),
                    "season_number": record.get("season_number"),
                    "episode_number": record.get("episode_number"),
                    "absolute_number": record.get(
                        "absolute_number",
                        canonical.get("absolute_number"),
                    ),
                    "title_original": record.get("title_original"),
                    "air_date_raw": record.get("air_date"),
                    "air_date": normalize_date(record.get("air_date")),
                    "source_url": record.get("thetvdb_url")
                    or record.get("source_url"),
                    "match_type": source.get("match_type"),
                    "confidence": source.get(
                        "confidence",
                        canonical.get("confidence"),
                    ),
                    "matched": True,
                    "metadata": {},
                }
            )

        return result

    return {
        "source": source_name,
        "source_record_id": source.get("episode_id"),
        "season_number": source.get("season_number"),
        "episode_number": source.get("episode_number"),
        "absolute_number": source.get(
            "absolute_number",
            canonical.get("absolute_number"),
        ),
        "title_original": source.get("title_original"),
        "air_date_raw": source.get("air_date"),
        "air_date": normalize_date(source.get("air_date")),
        "source_url": source.get("source_url"),
        "match_type": "MATCH",
        "confidence": canonical.get("confidence"),
        "matched": True,
        "metadata": {},
    }


def choose_canonical_air_date(
    wikipedia: dict[str, Any] | None,
    epguides: dict[str, Any] | None,
) -> tuple[str | None, str]:

    wiki_date = normalize_date(
        wikipedia.get("air_date") if wikipedia else None
    )
    epguides_date = normalize_date(
        epguides.get("air_date") if epguides else None
    )

    if wiki_date and epguides_date and wiki_date == epguides_date:
        return wiki_date, "WIKIPEDIA_EPGUIDES_AGREE"

    # ВАЖНО:
    # При конфликте дату пока НЕ выбираем автоматически.
    return None, "DATE_CONFLICT_OR_INCOMPLETE"


def build() -> None:
    raw_mapping = load_json(MAPPING_FILE)
    mappings = get_mapping_records(raw_mapping)

    print(f"Identity mappings loaded: {len(mappings)}")

    if len(mappings) != EXPECTED_EPISODES:
        raise RuntimeError(
            f"Ожидалось {EXPECTED_EPISODES} mapping-записей, "
            f"получено {len(mappings)}"
        )

    episodes: list[dict[str, Any]] = []

    seen_ids: set[str] = set()

    for item in mappings:
        canonical_id = item.get("canonical_episode_id")

        if not canonical_id:
            raise RuntimeError(
                "Найдена запись без canonical_episode_id"
            )

        if canonical_id in seen_ids:
            raise RuntimeError(
                f"Дублирующий canonical_episode_id: {canonical_id}"
            )

        seen_ids.add(canonical_id)

        absolute_number = item.get("absolute_number")
        season_number = item.get("season_number")
        episode_number = item.get("episode_number")

        title_en = (
            item.get("canonical_title_en")
            or item.get("title_original")
        )

        title_fr = item.get("canonical_title_fr")

        sources = item.get("sources", {})

        wikipedia = sources.get("wikipedia")
        epguides = sources.get("epguides")
        thetvdb = sources.get("thetvdb")

        canonical_air_date, air_date_status = choose_canonical_air_date(
            wikipedia,
            epguides,
        )

        synopsis = None

        if wikipedia:
            synopsis = wikipedia.get("description")

        if not synopsis and epguides:
            synopsis = epguides.get("description")

        writers = None

        if wikipedia:
            writers = wikipedia.get("writer")

        villains = None

        if wikipedia:
            villains = wikipedia.get("villains_monsters")

        source_records: list[dict[str, Any]] = []

        wiki_record = safe_source_record(
            "wikipedia",
            wikipedia,
            item,
        )

        if wiki_record:
            source_records.append(wiki_record)

        epguides_record = safe_source_record(
            "epguides",
            epguides,
            item,
        )

        if epguides_record:
            source_records.append(epguides_record)

        tvdb_records = safe_source_record(
            "thetvdb",
            thetvdb,
            item,
        )

        if tvdb_records:
            if isinstance(tvdb_records, list):
                source_records.extend(tvdb_records)
            else:
                source_records.append(tvdb_records)

        episode = {
            "episode_id": canonical_id,

            # Физическая идентичность
            "absolute_number": absolute_number,

            # Канонические координаты.
            # Это НЕ идентификатор физического эпизода.
            "season_number": season_number,
            "episode_number": episode_number,

            "production_number": None,

            "title_original": title_en,
            "title_ru": None,
            "title_alt": title_fr,

            # Дату сознательно оставляем NULL при конфликте.
            "air_date": canonical_air_date,
            "air_date_status": air_date_status,

            "synopsis_short": None,
            "synopsis_detailed": synopsis,

            "writer": writers,
            "villains_monsters": villains,

            "status": "discovered",

            "identity": {
                "confidence": item.get("confidence"),
                "status": item.get("status"),
                "thetvdb_match_type": item.get("thetvdb_match_type"),
                "reordering": item.get("reordering"),
                "evidence": item.get("evidence", []),
            },

            "source_records": source_records,
        }

        episodes.append(episode)

    episodes.sort(
        key=lambda x: (
            x["absolute_number"]
            if x["absolute_number"] is not None
            else 10**9
        )
    )

    # Финальная проверка
    absolute_numbers = [
        episode["absolute_number"]
        for episode in episodes
    ]

    if len(set(absolute_numbers)) != EXPECTED_EPISODES:
        raise RuntimeError(
            "absolute_number содержит дубликаты или NULL"
        )

    expected_numbers = list(range(1, EXPECTED_EPISODES + 1))

    if sorted(absolute_numbers) != expected_numbers:
        raise RuntimeError(
            f"Ожидались absolute_number 1..{EXPECTED_EPISODES}, "
            f"получено: {sorted(absolute_numbers)}"
        )

    tvdb_record_count = 0

    for episode in episodes:
        for record in episode["source_records"]:
            if record["source"] == "thetvdb":
                tvdb_record_count += 1

    output = {
        "schema_version": "0.3",
        "identity_source": "episode_identity_mapping.json",
        "episode_count": len(episodes),
        "episodes": episodes,
        "statistics": {
            "episodes": len(episodes),
            "thetvdb_source_records": tvdb_record_count,
            "episodes_with_unresolved_air_date": sum(
                1
                for e in episodes
                if e["air_date"] is None
            ),
        },
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("[OK] Canonical file created")
    print(f"     {OUTPUT_FILE}")
    print()
    print(f"Episodes                  : {len(episodes)}")
    print(f"TheTVDB source records    : {tvdb_record_count}")
    print(
        "Episodes without resolved "
        f"air_date                  : {output['statistics']['episodes_with_unresolved_air_date']}"
    )
    print()

    print("First 5:")
    for episode in episodes[:5]:
        print(
            f"  #{episode['absolute_number']:02d} "
            f"S{episode['season_number']:02d}E{episode['episode_number']:02d} "
            f"{episode['title_original']}"
        )

    print()
    print("Last 5:")
    for episode in episodes[-5:]:
        print(
            f"  #{episode['absolute_number']:02d} "
            f"S{episode['season_number']:02d}E{episode['episode_number']:02d} "
            f"{episode['title_original']}"
        )


if __name__ == "__main__":
    build()
