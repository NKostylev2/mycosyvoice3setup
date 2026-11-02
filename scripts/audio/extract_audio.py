from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


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


FFMPEG = find_binary("ffmpeg")
FFPROBE = find_binary("ffprobe")


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def run_command(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def probe_media(video: Path) -> dict:
    cmd = [
        str(FFPROBE),
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video),
    ]
    res = run_command(cmd)
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe failed:\n{res.stderr}")
    return json.loads(res.stdout)


def validate_wav(path: Path, expected_sample_rate: int = 16000, expected_channels: int = 1) -> dict:
    cmd = [
        str(FFPROBE),
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels,channel_layout,duration",
        "-of", "json",
        str(path),
    ]
    res = run_command(cmd)
    if res.returncode != 0:
        raise RuntimeError(f"Could not validate {path}:\n{res.stderr}")
    data = json.loads(res.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise ValueError(f"No audio streams found in output WAV {path}")
    st = streams[0]
    codec = st.get("codec_name")
    sr = int(st.get("sample_rate", 0))
    ch = int(st.get("channels", 0))
    dur = float(st.get("duration", 0.0))

    errors = []
    if codec != "pcm_s16le":
        errors.append(f"unexpected codec: {codec}")
    if sr != expected_sample_rate:
        errors.append(f"unexpected sample rate: {sr} (expected {expected_sample_rate})")
    if ch != expected_channels:
        errors.append(f"unexpected channels: {ch} (expected {expected_channels})")
    if dur <= 0:
        errors.append(f"invalid duration: {dur}")
    if errors:
        raise ValueError(f"Validation failed for {path}:\n- " + "\n- ".join(errors))

    return {
        "codec": codec,
        "sample_rate": sr,
        "channels": ch,
        "channel_layout": st.get("channel_layout"),
        "duration": dur,
        "size_bytes": path.stat().st_size,
        "sha256": compute_sha256(path),
    }


def main() -> None:
    episode_key = sys.argv[1] if len(sys.argv) > 1 else "S01E01"
    video = INPUT_DIR / f"{episode_key}.mp4"
    work = WORK_DIR / episode_key
    audio_dir = work / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    english_wav = audio_dir / "english.wav"
    russian_wav = audio_dir / "russian.wav"
    legacy_source_wav = audio_dir / "source.wav"

    if not video.exists():
        print(f"ERROR: Video not found: {video}")
        sys.exit(1)

    print(f"=== AUTOMATIC AUDIO EXTRACTION: {episode_key} ===")
    print(f"Input video: {video}")

    probe_data = probe_media(video)
    streams = probe_data.get("streams", [])
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    if not audio_streams:
        print("ERROR: No audio streams found in video!")
        sys.exit(1)

    print(f"Detected {len(audio_streams)} audio stream(s):")
    for s in audio_streams:
        lang = s.get("tags", {}).get("language", "und")
        title = s.get("tags", {}).get("title", "")
        print(f"  Stream #{s['index']} ({s['codec_name']}): lang={lang}, channels={s.get('channels')}, sr={s.get('sample_rate')}, title='{title}'")

    # 1. Identify English stream
    eng_stream = None
    for s in audio_streams:
        lang = s.get("tags", {}).get("language", "").lower()
        if lang in ("eng", "en"):
            eng_stream = s
            break

    if eng_stream is None:
        # Fallback: if single audio stream, assume English
        if len(audio_streams) == 1:
            print("Notice: Only 1 audio stream found without explicit 'eng' tag, selecting as English track.")
            eng_stream = audio_streams[0]
        else:
            # First audio stream as default English
            eng_stream = audio_streams[0]
            print(f"Notice: Selecting first audio stream #{eng_stream['index']} as English track.")

    print(f"Selected English track: Stream #{eng_stream['index']} ({eng_stream.get('codec_name')})")

    # 2. Identify Russian stream (in container or external)
    rus_stream = None
    for s in audio_streams:
        lang = s.get("tags", {}).get("language", "").lower()
        if lang in ("rus", "ru"):
            rus_stream = s
            break

    external_rus_file = None
    if rus_stream is None:
        for ext in [".ru.wav", ".rus.wav", ".ru.mp3", ".rus.mp3", ".ru.m4a"]:
            cand = INPUT_DIR / f"{episode_key}{ext}"
            if cand.exists():
                external_rus_file = cand
                break

    # 3. Extract English Audio (16 kHz mono PCM for WhisperX)
    print(f"Extracting English audio to: {english_wav} ...")
    cmd_eng = [
        str(FFMPEG),
        "-hide_banner",
        "-y",
        "-i", str(video),
        "-map", f"0:{eng_stream['index']}",
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(english_wav),
    ]
    res = run_command(cmd_eng)
    if res.returncode != 0:
        print(f"ERROR: FFmpeg English extraction failed:\n{res.stderr}")
        sys.exit(1)

    eng_meta = validate_wav(english_wav, expected_sample_rate=16000, expected_channels=1)
    print(f"English audio verified: {eng_meta['duration']:.3f}s, {eng_meta['size_bytes']} bytes, sha256={eng_meta['sha256'][:16]}...")

    # 4. Extract Russian Audio if found
    rus_meta = None
    if rus_stream is not None:
        print(f"Extracting embedded Russian audio stream #{rus_stream['index']} to: {russian_wav} ...")
        cmd_rus = [
            str(FFMPEG),
            "-hide_banner",
            "-y",
            "-i", str(video),
            "-map", f"0:{rus_stream['index']}",
            "-vn",
            "-c:a", "pcm_s16le",
            str(russian_wav),
        ]
        res = run_command(cmd_rus)
        if res.returncode != 0:
            print(f"WARNING: Russian audio extraction failed:\n{res.stderr}")
        else:
            rus_meta = validate_wav(russian_wav, expected_sample_rate=int(rus_stream.get("sample_rate", 44100)), expected_channels=int(rus_stream.get("channels", 2)))
    elif external_rus_file is not None:
        print(f"Extracting external Russian audio from: {external_rus_file} ...")
        cmd_rus = [
            str(FFMPEG),
            "-hide_banner",
            "-y",
            "-i", str(external_rus_file),
            "-vn",
            "-c:a", "pcm_s16le",
            str(russian_wav),
        ]
        res = run_command(cmd_rus)
        if res.returncode == 0:
            rus_meta = validate_wav(russian_wav)
    else:
        print("Notice: No Russian audio track found in container or input folder. Skipping russian.wav.")

    # 5. Check legacy source.wav
    legacy_info = None
    if legacy_source_wav.exists():
        legacy_hash = compute_sha256(legacy_source_wav)
        matches_english = (legacy_hash == eng_meta["sha256"])
        legacy_info = {
            "path": str(legacy_source_wav.relative_to(ROOT)),
            "sha256": legacy_hash,
            "size_bytes": legacy_source_wav.stat().st_size,
            "matches_english_wav": matches_english,
        }
        print(f"Legacy source.wav exists (matches english.wav: {matches_english})")

    # 6. Build audio_tracks_manifest.json
    manifest = {
        "schema_version": "2.0",
        "episode_key": episode_key,
        "source_video": str(video.relative_to(ROOT)),
        "tracks": {
            "english": {
                "status": "EXTRACTED",
                "source_stream_index": eng_stream["index"],
                "source_codec": eng_stream.get("codec_name"),
                "source_sample_rate": eng_stream.get("sample_rate"),
                "source_channels": eng_stream.get("channels"),
                "extracted_file": str(english_wav.relative_to(ROOT)),
                "format": "wav",
                "codec": eng_meta["codec"],
                "sample_rate": eng_meta["sample_rate"],
                "channels": eng_meta["channels"],
                "duration": eng_meta["duration"],
                "size_bytes": eng_meta["size_bytes"],
                "sha256": eng_meta["sha256"],
                "role": "ASR_INPUT_WHISPERX",
            },
            "russian": {
                "status": "AVAILABLE" if rus_meta else "NOT_FOUND",
                "extracted_file": str(russian_wav.relative_to(ROOT)) if rus_meta else None,
                "metadata": rus_meta,
                "role": "SEPARATE_DUBBING_REFERENCE",
            },
        },
        "legacy": legacy_info,
    }

    manifest_path = audio_dir / "audio_tracks_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifest written: {manifest_path}")
    print("AUDIO EXTRACTION COMPLETE (PASS)")


if __name__ == "__main__":
    main()