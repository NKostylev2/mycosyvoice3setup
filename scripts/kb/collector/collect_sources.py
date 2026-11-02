from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "knowledge" / "raw"


COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0 Safari/537.36 "
        "AI-Dubbing-SourceCollector/0.3"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


SOURCES: dict[str, dict[str, Any]] = {

    # --------------------------------------------------------
    # epguides
    # --------------------------------------------------------
    "epguides": {
        "method": "html",
        "url": "https://epguides.com/MartinMystery/",
        "filename": "page.html",

        "min_size": 10_000,

        "required_any": [
            "Martin Mystery",
            "Titles",
            "Air Date",
        ],

        "episode_patterns": [
            r"\d+\.\s+1-\d+",
            r"\d+\.\s+2-\d+",
            r"\d+\.\s+3-\d+",
            r"Martin Mystery",
        ],

        "retry_statuses": [429, 500, 502, 503, 504],
    },

    # --------------------------------------------------------
    # TheTVDB
    # --------------------------------------------------------
    "thetvdb": {
        "method": "html",
        "url": "https://thetvdb.com/series/martin-mystery",
        "filename": "page.html",

        "min_size": 20_000,

        "required_any": [
            "Martin Mystery",
            "Episodes",
            "TheTVDB",
        ],

        "episode_patterns": [
            r"Season\s+1",
            r"Season\s+2",
            r"Season\s+3",
            r"Martin Mystery",
        ],

        "retry_statuses": [429, 500, 502, 503, 504],
    },

    # --------------------------------------------------------
    # IMDb
    # --------------------------------------------------------
    #
    # Пока НЕ считаем HTML-страницу обязательным источником.
    # Если IMDb отдаёт challenge / минимальный HTML,
    # сохраняем ответ как invalid и не ломаем pipeline.
    #
    "imdb": {
        "method": "html",
        "url": "https://www.imdb.com/title/tt0374419/episodes/",
        "filename": "page.html",

        "min_size": 5_000,

        "required_any": [
            "Martin Mystery",
            "Episodes",
            "IMDb",
        ],

        "episode_patterns": [
            r"S\d+\.E\d+",
            r"Episode",
            r"Martin Mystery",
        ],

        "retry_statuses": [429, 500, 502, 503, 504],
    },

    # --------------------------------------------------------
    # Wikipedia
    # --------------------------------------------------------
    #
    # Используем официальный MediaWiki API вместо HTML.
    #
    "wikipedia": {
        "method": "mediawiki_api",

        "url": "https://en.wikipedia.org/w/api.php",

        "params": {
            "action": "parse",
            "page": "List_of_Martin_Mystery_episodes",
            "prop": "text|wikitext",
            "format": "json",
            "formatversion": "2",
        },

        "filename": "page.json",

        "min_size": 10_000,

        "required_any": [
            "Martin Mystery",
            "List of Martin Mystery episodes",
        ],

        "episode_patterns": [
            r"Season\s+[123]",
            r"Episode",
            r"Martin Mystery",
        ],

        "retry_statuses": [429, 500, 502, 503, 504],
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def decode_bytes(data: bytes) -> str:
    """
    Декодируем полученные данные.

    Для HTML предпочтителен UTF-8.
    Для остальных случаев используем fallback.
    """
    for encoding in (
        "utf-8",
        "utf-8-sig",
        "cp1252",
        "latin-1",
    ):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    return data.decode(
        "utf-8",
        errors="replace",
    )


def normalize_text(text: str) -> str:
    """
    Приводим HTML к приблизительно читаемому тексту
    для проверки содержимого.
    """
    text = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        text,
        flags=re.I | re.S,
    )

    text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        text,
        flags=re.I | re.S,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    replacements = {
        "&nbsp;": " ",
        "&amp;": "&",
        "&quot;": '"',
        "&#39;": "'",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def mediawiki_json_to_text(data: bytes) -> str:
    """
    Извлекаем содержимое MediaWiki API из JSON.
    """
    payload = json.loads(
        decode_bytes(data)
    )

    chunks: list[str] = []

    parse_data = payload.get("parse")

    if not parse_data:
        return ""

    title = parse_data.get("title")

    if isinstance(title, str):
        chunks.append(title)

    text = parse_data.get("text")

    if isinstance(text, str):
        chunks.append(text)

    wikitext = parse_data.get("wikitext")

    if isinstance(wikitext, str):
        chunks.append(wikitext)

    return "\n".join(chunks)


def count_patterns(
    text: str,
    patterns: list[str],
) -> dict[str, int]:

    result: dict[str, int] = {}

    for pattern in patterns:
        try:
            result[pattern] = len(
                re.findall(
                    pattern,
                    text,
                    flags=re.I,
                )
            )
        except re.error:
            result[pattern] = -1

    return result


def validate(
    *,
    data: bytes,
    content_type: str,
    config: dict[str, Any],
) -> dict[str, Any]:

    method = config["method"]

    raw_text = decode_bytes(data)

    if method == "mediawiki_api":
        try:
            search_text = mediawiki_json_to_text(data)
        except json.JSONDecodeError:
            search_text = raw_text
    else:
        search_text = raw_text

    visible_text = normalize_text(search_text)

    min_size_ok = (
        len(data) >= config["min_size"]
    )

    if method == "mediawiki_api":
        content_type_ok = (
            "json" in content_type.lower()
        )

        format_ok = (
            raw_text.lstrip().startswith("{")
        )

    else:
        content_type_ok = (
            "text/html" in content_type.lower()
            or "application/xhtml+xml"
            in content_type.lower()
        )

        format_ok = (
            "<html" in raw_text.lower()
            or "<!doctype html"
            in raw_text.lower()
        )

    marker_checks: dict[str, bool] = {}

    for marker in config["required_any"]:
        marker_checks[marker] = (
            marker.lower()
            in visible_text.lower()
        )

    marker_hits = sum(
        marker_checks.values()
    )

    source_markers_ok = (
        marker_hits >= 1
    )

    pattern_counts = count_patterns(
        visible_text,
        config["episode_patterns"],
    )

    episode_pattern_hits = sum(
        value
        for value in pattern_counts.values()
        if value > 0
    )

    episode_markers_ok = (
        episode_pattern_hits > 0
    )

    # Не проверяем просто наличие слова "captcha".
    #
    # Оно может встречаться в реальной странице,
    # документации, шаблоне или служебном JS.
    #
    # Ищем именно типичные признаки challenge.
    lower_raw = raw_text.lower()

    challenge_markers = [
        "cf-chl-captcha",
        "captcha challenge",
        "challenge-form",
        "verify you are human",
        "access denied",
        "unusual traffic",
    ]

    challenge_hits = [
        marker
        for marker in challenge_markers
        if marker in lower_raw
    ]

    anti_bot_ok = (
        len(challenge_hits) == 0
    )

    reasons: list[str] = []

    if not min_size_ok:
        reasons.append(
            f"response too small: "
            f"{len(data)} < {config['min_size']} bytes"
        )

    if not content_type_ok:
        reasons.append(
            "unexpected content-type: "
            f"{content_type or '<missing>'}"
        )

    if not format_ok:
        reasons.append(
            f"response format does not match "
            f"method={method}"
        )

    if not source_markers_ok:
        reasons.append(
            "source-specific markers not found"
        )

    if not episode_markers_ok:
        reasons.append(
            "episode-related markers not found"
        )

    if not anti_bot_ok:
        reasons.append(
            "possible anti-bot challenge: "
            + ", ".join(challenge_hits)
        )

    valid = (
        min_size_ok
        and content_type_ok
        and format_ok
        and source_markers_ok
        and episode_markers_ok
        and anti_bot_ok
    )

    return {
        "valid": valid,

        "size_bytes": len(data),

        "content_type": content_type,

        "method": method,

        "checks": {
            "min_size": min_size_ok,
            "content_type": content_type_ok,
            "format": format_ok,
            "source_markers": source_markers_ok,
            "episode_markers": episode_markers_ok,
            "anti_bot": anti_bot_ok,
        },

        "required_markers": marker_checks,

        "required_marker_hits": marker_hits,

        "required_marker_total": len(
            config["required_any"]
        ),

        "episode_pattern_counts": pattern_counts,

        "episode_pattern_total_hits":
            episode_pattern_hits,

        "anti_bot_hits": challenge_hits,

        "reasons": reasons,
    }


def build_request(
    name: str,
    config: dict[str, Any],
) -> Request:

    method = config["method"]

    if method == "html":

        return Request(
            config["url"],
            headers=COMMON_HEADERS,
        )

    if method == "mediawiki_api":

        query = urlencode(
            config["params"]
        )

        url = (
            config["url"]
            + "?"
            + query
        )

        headers = {
            **COMMON_HEADERS,
            "Accept": "application/json",
        }

        return Request(
            url,
            headers=headers,
        )

    raise ValueError(
        f"Unsupported method for {name}: {method}"
    )


def download(
    name: str,
    config: dict[str, Any],
) -> tuple[bytes, str, int]:

    retries = 3

    retry_statuses = set(
        config.get(
            "retry_statuses",
            [],
        )
    )

    last_error: Exception | None = None

    for attempt in range(
        1,
        retries + 1,
    ):
        request = build_request(
            name,
            config,
        )

        try:
            with urlopen(
                request,
                timeout=30,
            ) as response:

                data = response.read()

                content_type = (
                    response.headers.get(
                        "Content-Type",
                        "",
                    )
                )

                status = getattr(
                    response,
                    "status",
                    200,
                )

                return (
                    data,
                    content_type,
                    status,
                )

        except HTTPError as exc:

            last_error = exc

            print(
                f"          HTTP {exc.code}"
            )

            if (
                exc.code not in retry_statuses
                or attempt == retries
            ):
                raise

            delay = 2 ** (
                attempt - 1
            )

            print(
                f"          retry in {delay}s..."
            )

            time.sleep(delay)

        except URLError as exc:

            last_error = exc

            print(
                f"          network error: "
                f"{exc.reason}"
            )

            if attempt == retries:
                raise

            delay = 2 ** (
                attempt - 1
            )

            print(
                f"          retry in {delay}s..."
            )

            time.sleep(delay)

    raise RuntimeError(
        f"Unable to download {name}: "
        f"{last_error}"
    )


def save_source(
    name: str,
    config: dict[str, Any],
) -> dict[str, Any]:

    source_dir = (
        RAW_DIR / name
    )

    source_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        source_dir
        / config["filename"]
    )

    metadata_path = (
        source_dir
        / "metadata.json"
    )

    print("=" * 60)
    print(f"[DOWNLOAD] {name}")
    print(f"           method: {config['method']}")
    print(f"           {config['url']}")

    retrieved_at = utc_now()

    try:
        data, content_type, http_status = download(
            name,
            config,
        )

    except HTTPError as exc:

        result = {
            "collector_version": "0.3.0",
            "source": name,
            "url": config["url"],
            "method": config["method"],
            "retrieved_at": retrieved_at,
            "status": "error",
            "error_type": "http",
            "http_status": exc.code,
            "error": str(exc),
        }

        write_json(
            metadata_path,
            result,
        )

        print(
            f"[ERROR] HTTP {exc.code}"
        )

        return result

    except URLError as exc:

        result = {
            "collector_version": "0.3.0",
            "source": name,
            "url": config["url"],
            "method": config["method"],
            "retrieved_at": retrieved_at,
            "status": "error",
            "error_type": "network",
            "error": str(exc.reason),
        }

        write_json(
            metadata_path,
            result,
        )

        print(
            f"[ERROR] Network: "
            f"{exc.reason}"
        )

        return result

    except Exception as exc:

        result = {
            "collector_version": "0.3.0",
            "source": name,
            "url": config["url"],
            "method": config["method"],
            "retrieved_at": retrieved_at,
            "status": "error",
            "error_type": "unknown",
            "error": str(exc),
        }

        write_json(
            metadata_path,
            result,
        )

        print(
            f"[ERROR] {exc}"
        )

        return result

    validation = validate(
        data=data,
        content_type=content_type,
        config=config,
    )

    file_hash = sha256_bytes(data)

    if validation["valid"]:

        output_path.write_bytes(
            data
        )

        status = "accepted"

        print(
            f"[ACCEPTED] "
            f"{len(data):,} bytes"
        )

        print(
            f"           "
            f"{validation['episode_pattern_total_hits']}"
            f" episode-pattern hits"
        )

    else:

        rejected_path = (
            source_dir
            / (
                "rejected.json"
                if config["method"]
                == "mediawiki_api"
                else "rejected.html"
            )
        )

        rejected_path.write_bytes(
            data
        )

        status = "invalid"

        print(
            f"[INVALID] "
            f"{len(data):,} bytes"
        )

        for reason in validation["reasons"]:
            print(
                f"          - {reason}"
            )

    metadata = {
        "collector_version": "0.3.0",

        "source": name,

        "url": config["url"],

        "method": config["method"],

        "retrieved_at": retrieved_at,

        "http_status": http_status,

        "status": status,

        "sha256": file_hash,

        "validation": validation,
    }

    if status == "accepted":
        metadata["filename"] = str(
            output_path.relative_to(
                PROJECT_ROOT
            )
        )

    write_json(
        metadata_path,
        metadata,
    )

    return metadata


def main() -> int:

    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = []

    for index, (
        name,
        config,
    ) in enumerate(
        SOURCES.items()
    ):

        result = save_source(
            name,
            config,
        )

        results.append(
            result
        )

        if index < len(SOURCES) - 1:
            time.sleep(2)

    accepted = sum(
        1
        for result in results
        if result.get(
            "status"
        ) == "accepted"
    )

    invalid = sum(
        1
        for result in results
        if result.get(
            "status"
        ) == "invalid"
    )

    errors = sum(
        1
        for result in results
        if result.get(
            "status"
        ) == "error"
    )

    manifest = {
        "collector_version": "0.3.0",

        "retrieved_at": utc_now(),

        "summary": {
            "total": len(results),
            "accepted": accepted,
            "invalid": invalid,
            "errors": errors,
        },

        "results": results,
    }

    manifest_path = (
        RAW_DIR / "manifest.json"
    )

    write_json(
        manifest_path,
        manifest,
    )

    print()
    print("=" * 60)
    print("COLLECTION SUMMARY")
    print("=" * 60)

    print(
        f"Accepted : {accepted}"
    )

    print(
        f"Invalid  : {invalid}"
    )

    print(
        f"Errors   : {errors}"
    )

    print()
    print(
        f"Manifest: {manifest_path}"
    )

    return (
        0
        if accepted == len(results)
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
