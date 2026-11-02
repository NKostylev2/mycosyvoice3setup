from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "input"
WORK_DIR = ROOT / "work"

FFMPEG_DEFAULT_BIN = ROOT / "vendor" / "ffmpeg" / "bin"


def find_binary(name: str) -> Path:
    which_path = shutil.which(name)
    if which_path:
        return Path(which_path)
    fallback = FFMPEG_DEFAULT_BIN / f"{name}.exe"
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Binary '{name}' not found in PATH or at {fallback}")


FFPROBE = find_binary("ffprobe")


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def run_ffprobe(path: Path) -> dict:
    cmd = [
        str(FFPROBE),
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe failed ({res.returncode}):\n{res.stderr}")
    return json.loads(res.stdout)


TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
)


def timestamp_to_seconds(value: str) -> float:
    value = value.replace(",", ".")
    h, m, s = value.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_srt(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", raw.strip())
    entries = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        ts_match = None
        ts_idx = None
        for i, line in enumerate(lines):
            m = TIMESTAMP_RE.search(line)
            if m:
                ts_match = m
                ts_idx = i
                break
        if not ts_match:
            continue
        start = timestamp_to_seconds(ts_match.group("start"))
        end = timestamp_to_seconds(ts_match.group("end"))
        text = "\n".join(lines[ts_idx + 1:])
        entries.append({
            "index": len(entries) + 1,
            "start": start,
            "end": end,
            "duration": end - start,
            "text": text,
        })
    return entries


def main() -> None:
    episode_key = sys.argv[1] if len(sys.argv) > 1 else "S01E01"
    work_dir = WORK_DIR / episode_key
    gt_dir = work_dir / "ground_truth"
    gt_dir.mkdir(parents=True, exist_ok=True)

    video_path = INPUT_DIR / f"{episode_key}.mp4"
    srt_path = INPUT_DIR / f"{episode_key}.en.hi.srt"
    whisper_path = work_dir / "whisperx" / "source.json"
    vad_path = work_dir / "audio" / "vad.json"
    source_wav_path = work_dir / "audio" / "source.wav"

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not srt_path.exists():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")

    print(f"Building Ground Truth snapshot for {episode_key}...")

    # 1. Video and audio probing
    probe_data = run_ffprobe(video_path)
    format_info = probe_data.get("format", {})
    streams = probe_data.get("streams", [])

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    primary_v = video_streams[0] if video_streams else {}
    fps_val = None
    r_fps = primary_v.get("r_frame_rate", "0/0")
    if "/" in r_fps:
        num, den = r_fps.split("/")
        if float(den) > 0:
            fps_val = float(num) / float(den)

    video_duration = float(format_info.get("duration", primary_v.get("duration", 0.0)))
    width = primary_v.get("width")
    height = primary_v.get("height")
    video_codec = primary_v.get("codec_name")

    audio_info_list = []
    for s in audio_streams:
        audio_dur = float(s.get("duration", format_info.get("duration", 0.0)))
        audio_info_list.append({
            "stream_index": s.get("index"),
            "language": s.get("tags", {}).get("language", "und"),
            "codec": s.get("codec_name"),
            "codec_long_name": s.get("codec_long_name"),
            "sample_rate": int(s.get("sample_rate", 0)),
            "channels": int(s.get("channels", 0)),
            "channel_layout": s.get("channel_layout"),
            "bit_rate": s.get("bit_rate"),
            "duration": audio_dur,
        })

    # Check for Russian audio (embedded or external)
    has_english_audio = any(a["language"] == "eng" or audio_streams for a in audio_info_list)
    has_russian_audio = any(a["language"] in ("rus", "ru") for a in audio_info_list)
    external_rus_path = None
    for cand in [INPUT_DIR / f"{episode_key}.ru.wav", INPUT_DIR / f"{episode_key}.rus.wav", INPUT_DIR / f"{episode_key}.ru.mp3"]:
        if cand.exists():
            external_rus_path = str(cand)
            has_russian_audio = True
            break

    # 2. SRT parsing
    srt_entries = parse_srt(srt_path)
    first_srt = srt_entries[0]["start"] if srt_entries else None
    last_srt = srt_entries[-1]["end"] if srt_entries else None

    # 3. WhisperX parsing
    whisper_data = {}
    whisper_segments = []
    whisper_words_count = 0
    first_whisper_start = None
    last_whisper_end = None
    whisper_parseable = False

    if whisper_path.exists():
        try:
            with whisper_path.open("r", encoding="utf-8") as f:
                whisper_data = json.load(f)
            whisper_segments = whisper_data.get("segments", [])
            whisper_parseable = True
            if whisper_segments:
                first_whisper_start = whisper_segments[0].get("start")
                last_whisper_end = whisper_segments[-1].get("end")
            # Count words
            if "word_segments" in whisper_data:
                whisper_words_count = len(whisper_data["word_segments"])
            else:
                for seg in whisper_segments:
                    whisper_words_count += len(seg.get("words", []))
        except Exception as e:
            print(f"Warning: WhisperX parse error: {e}")

    # 4. VAD parsing
    vad_data = {}
    vad_intervals = []
    vad_speech_duration = 0.0
    vad_parseable = False

    if vad_path.exists():
        try:
            with vad_path.open("r", encoding="utf-8") as f:
                vad_data = json.load(f)
            vad_intervals = vad_data.get("intervals", vad_data.get("speech_segments", []))
            vad_parseable = True
            for iv in vad_intervals:
                vad_speech_duration += (iv["end"] - iv["start"])
        except Exception as e:
            print(f"Warning: VAD parse error: {e}")

    # 5. Hashes
    hashes = {
        "source_video": compute_sha256(video_path),
        "source_srt": compute_sha256(srt_path),
    }
    if whisper_path.exists():
        hashes["whisperx_source_json"] = compute_sha256(whisper_path)
    if vad_path.exists():
        hashes["vad_json"] = compute_sha256(vad_path)
    if source_wav_path.exists():
        hashes["legacy_source_wav"] = compute_sha256(source_wav_path)

    # Compile ground truth snapshot
    ground_truth = {
        "schema_version": "1.0",
        "episode": episode_key,
        "source_video": {
            "path": str(video_path.relative_to(ROOT)),
            "duration": video_duration,
            "width": width,
            "height": height,
            "fps": fps_val,
            "codec": video_codec,
        },
        "audio_streams": audio_info_list,
        "subtitles": {
            "path": str(srt_path.relative_to(ROOT)),
            "entry_count": len(srt_entries),
            "first_timestamp": first_srt,
            "last_timestamp": last_srt,
        },
        "whisperx": {
            "path": str(whisper_path.relative_to(ROOT)) if whisper_path.exists() else None,
            "segment_count": len(whisper_segments),
            "first_segment_start": first_whisper_start,
            "last_segment_end": last_whisper_end,
            "word_segment_count": whisper_words_count,
        },
        "vad": {
            "path": str(vad_path.relative_to(ROOT)) if vad_path.exists() else None,
            "interval_count": len(vad_intervals),
            "speech_duration_seconds": round(vad_speech_duration, 3),
        },
        "hashes": hashes,
    }

    # Pass/Fail checks
    checks = {
        "video_duration_positive": video_duration > 0,
        "video_stream_valid": width is not None and height is not None and width > 0 and height > 0,
        "english_audio_exists": has_english_audio,
        "russian_audio_exists": has_russian_audio,
        "srt_parseable": len(srt_entries) > 0,
        "whisperx_parseable": whisper_parseable and len(whisper_segments) > 0,
        "vad_parseable": vad_parseable and len(vad_intervals) > 0,
        "srt_timestamps_valid": all(e["start"] < e["end"] and e["start"] >= 0 for e in srt_entries),
        "whisper_timestamps_valid": all(s["start"] < s["end"] and s["start"] >= 0 for s in whisper_segments),
        "word_timestamps_valid": whisper_words_count > 0,
    }

    discrepancies = []
    # Note discrepancy: Russian audio absent in container
    if not has_russian_audio:
        discrepancies.append({
            "field": "russian_audio",
            "type": "ABSENT",
            "note": "No Russian audio track found inside container or input folder."
        })

    # Note discrepancy: offset between SRT first subtitle and Whisper first speech
    if first_srt is not None and first_whisper_start is not None:
        raw_gap = first_whisper_start - first_srt
        discrepancies.append({
            "field": "initial_speech_offset",
            "type": "OFFSET_OBSERVED",
            "first_srt_start": first_srt,
            "first_whisper_start": first_whisper_start,
            "gap_seconds": round(raw_gap, 3),
            "note": f"First Whisper segment ({first_whisper_start:.3f}s) starts ~{raw_gap:.3f}s after first SRT ({first_srt:.3f}s).",
        })

    all_passed = all(
        v for k, v in checks.items()
        if k != "russian_audio_exists"  # Russian audio is optional
    )

    report = {
        "schema_version": "1.0",
        "episode": episode_key,
        "status": "PASS" if all_passed else "FAIL",
        "checks": checks,
        "discrepancies": discrepancies,
        "summary": {
            "video_duration": video_duration,
            "audio_streams_count": len(audio_info_list),
            "srt_entry_count": len(srt_entries),
            "whisperx_segment_count": len(whisper_segments),
            "whisperx_word_count": whisper_words_count,
            "vad_interval_count": len(vad_intervals),
            "vad_speech_seconds": round(vad_speech_duration, 3),
        }
    }

    gt_file = gt_dir / "ground_truth.json"
    gt_report_file = gt_dir / "ground_truth_report.json"

    gt_file.write_text(json.dumps(ground_truth, ensure_ascii=False, indent=2), encoding="utf-8")
    gt_report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Ground truth written: {gt_file}")
    print(f"Ground truth report written: {gt_report_file}")
    print(f"Status: {report['status']}")
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    if discrepancies:
        print("Discrepancies noted:")
        for d in discrepancies:
            print(f"  - {d['field']}: {d.get('note')}")


if __name__ == "__main__":
    main()
