
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

INPUT_DIR = ROOT / "input"
WORK_DIR = ROOT / "work"

# Installed by ffmpeg-downloader
FFMPEG_DEFAULT_BIN = ROOT / "vendor" / "ffmpeg" / "bin"
FFMPEG_BIN = FFMPEG_DEFAULT_BIN

FFPROBE = FFMPEG_BIN / "ffprobe.exe"
FFMPEG = FFMPEG_BIN / "ffmpeg.exe"


def check_tools() -> None:
    if not FFPROBE.exists():
        raise FileNotFoundError(
            f"ffprobe.exe not found:\n{FFPROBE}"
        )

    if not FFMPEG.exists():
        raise FileNotFoundError(
            f"ffmpeg.exe not found:\n{FFMPEG}"
        )


def run_ffprobe(path: Path) -> dict:
    command = [
        str(FFPROBE),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed for:\n{path}\n\n"
            f"{result.stderr}"
        )

    return json.loads(result.stdout)


def rational_to_float(value: str | None) -> float | None:
    if not value or "/" not in value:
        return None

    numerator, denominator = value.split("/", 1)

    try:
        numerator = float(numerator)
        denominator = float(denominator)

        if denominator == 0:
            return None

        return numerator / denominator

    except ValueError:
        return None


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Usage:\n"
            "  python scripts\\media\\inspect_media.py S01E01"
        )
        sys.exit(1)

    episode_key = sys.argv[1]

    check_tools()

    video_path = INPUT_DIR / f"{episode_key}.mp4"
    subtitle_path = INPUT_DIR / f"{episode_key}.en.hi.srt"

    if not video_path.exists():
        raise FileNotFoundError(
            f"Video not found:\n{video_path}"
        )

    if not subtitle_path.exists():
        raise FileNotFoundError(
            f"Subtitle not found:\n{subtitle_path}"
        )

    print("=== MEDIA INSPECTION ===")
    print()
    print(f"Video    : {video_path}")
    print(f"Subtitle : {subtitle_path}")
    print()
    print(f"FFprobe  : {FFPROBE}")
    print()

    probe = run_ffprobe(video_path)

    streams = probe.get("streams", [])
    format_info = probe.get("format", {})

    video_streams = [
        s
        for s in streams
        if s.get("codec_type") == "video"
    ]

    audio_streams = [
        s
        for s in streams
        if s.get("codec_type") == "audio"
    ]

    subtitle_streams = [
        s
        for s in streams
        if s.get("codec_type") == "subtitle"
    ]

    if not video_streams:
        raise RuntimeError("No video stream found.")

    main_video = video_streams[0]

    duration = float(
        format_info.get("duration", 0)
    )

    fps = rational_to_float(
        main_video.get("avg_frame_rate")
    )

    video_info = {
        "codec": main_video.get("codec_name"),
        "codec_long_name": main_video.get("codec_long_name"),
        "width": main_video.get("width"),
        "height": main_video.get("height"),
        "fps": fps,
        "pix_fmt": main_video.get("pix_fmt"),
        "profile": main_video.get("profile"),
        "level": main_video.get("level"),
    }

    audio_info = []

    for stream in audio_streams:
        tags = stream.get("tags", {})

        audio_info.append(
            {
                "index": stream.get("index"),
                "codec": stream.get("codec_name"),
                "codec_long_name": stream.get("codec_long_name"),
                "channels": stream.get("channels"),
                "sample_rate": stream.get("sample_rate"),
                "language": tags.get("language"),
                "title": tags.get("title"),
                "channel_layout": stream.get("channel_layout"),
            }
        )

    embedded_subtitles = []

    for stream in subtitle_streams:
        tags = stream.get("tags", {})

        embedded_subtitles.append(
            {
                "index": stream.get("index"),
                "codec": stream.get("codec_name"),
                "language": tags.get("language"),
                "title": tags.get("title"),
            }
        )

    manifest = {
        "schema_version": "1.0",
        "episode_key": episode_key,

        "input": {
            "video": str(video_path.relative_to(ROOT)),
            "external_subtitle": str(
                subtitle_path.relative_to(ROOT)
            ),
        },

        "media": {
            "duration_seconds": duration,
            "video": video_info,
            "audio_tracks": audio_info,
            "embedded_subtitles": embedded_subtitles,
        },

        "external_subtitle": {
            "format": "srt",
            "language": "en",
            "hearing_impaired": True,
            "path": str(
                subtitle_path.relative_to(ROOT)
            ),
        },
    }

    episode_work_dir = WORK_DIR / episode_key

    episode_work_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        episode_work_dir
        / "media_manifest.json"
    )

    output_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=== VIDEO ===")
    print(
        f"Codec      : "
        f"{video_info['codec']}"
    )
    print(
        f"Resolution : "
        f"{video_info['width']}x"
        f"{video_info['height']}"
    )
    print(
        f"FPS        : "
        f"{video_info['fps']}"
    )
    print(
        f"Duration   : "
        f"{duration:.3f} s"
    )

    print()
    print("=== AUDIO TRACKS ===")

    if not audio_info:
        print("No audio tracks found.")
    else:
        for track in audio_info:
            print(
                f"index={track['index']} "
                f"codec={track['codec']} "
                f"channels={track['channels']} "
                f"language={track['language']}"
            )

    print()
    print("=== EMBEDDED SUBTITLES ===")

    if not embedded_subtitles:
        print("None")
    else:
        for track in embedded_subtitles:
            print(
                f"index={track['index']} "
                f"codec={track['codec']} "
                f"language={track['language']}"
            )

    print()
    print("=== EXTERNAL SUBTITLE ===")
    print("Format           : SRT")
    print("Language         : English")
    print("Hearing impaired : YES")

    print()
    print(f"Manifest : {output_path}")
    print()
    print("INSPECTION PASSED")


if __name__ == "__main__":
    main()
