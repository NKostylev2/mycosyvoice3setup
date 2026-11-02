
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np
import torch


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]
WORK_DIR = ROOT / "work"


# ============================================================
# HELPERS
# ============================================================

def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def read_pcm_wav(wav_path: Path) -> tuple[np.ndarray, int]:
    """
    Read a PCM WAV without torchaudio/TorchCodec.

    Expected format:
        PCM signed 16-bit
        mono
        16000 Hz
    """

    with wave.open(str(wav_path), "rb") as wf:
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        frame_count = wf.getnframes()
        compression = wf.getcomptype()

        if compression != "NONE":
            fail(
                f"WAV must be uncompressed PCM. "
                f"Got compression: {compression}"
            )

        if sample_rate != 16000:
            fail(
                f"Expected sample rate 16000 Hz, "
                f"got {sample_rate} Hz"
            )

        if channels != 1:
            fail(
                f"Expected mono WAV, "
                f"got {channels} channels"
            )

        if sample_width != 2:
            fail(
                f"Expected 16-bit PCM, "
                f"got {sample_width * 8}-bit PCM"
            )

        raw_audio = wf.readframes(frame_count)

    audio = np.frombuffer(
        raw_audio,
        dtype=np.int16,
    ).copy()

    return audio, sample_rate


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    # --------------------------------------------------------
    # Arguments
    # --------------------------------------------------------

    if len(sys.argv) != 2:
        fail(
            "Usage: python scripts\\audio\\run_vad.py S01E01"
        )

    episode_key = sys.argv[1]

    # --------------------------------------------------------
    # Paths
    # --------------------------------------------------------

    episode_dir = WORK_DIR / episode_key
    audio_dir = episode_dir / "audio"

    wav_path = audio_dir / "source.wav"
    manifest_path = audio_dir / "audio_manifest.json"
    output_path = audio_dir / "vad.json"

    if not wav_path.exists():
        fail(f"WAV not found: {wav_path}")

    if not manifest_path.exists():
        fail(f"Audio manifest not found: {manifest_path}")

    audio_dir.mkdir(parents=True, exist_ok=True)

    print("=== SILERO VAD ===")
    print(f"Input WAV  : {wav_path}")
    print(f"Output JSON: {output_path}")

    # --------------------------------------------------------
    # Device
    # --------------------------------------------------------

    if torch.cuda.is_available():

        device = torch.device("cuda")

        gpu_name = torch.cuda.get_device_name(0)

        print(f"Device     : CUDA ({gpu_name})")

    else:

        device = torch.device("cpu")

        print("Device     : CPU")

    # --------------------------------------------------------
    # Load Silero VAD
    # --------------------------------------------------------

    print("Loading Silero VAD...")

    model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        force_reload=False,
        trust_repo=True,
    )

    model = model.to(device)

    (
        get_speech_timestamps,
        _save_audio,
        _read_audio,
        _VADIterator,
        _collect_chunks,
    ) = utils

    # --------------------------------------------------------
    # Read WAV directly
    # --------------------------------------------------------

    print("Reading audio...")

    audio_np, sample_rate = read_pcm_wav(wav_path)

    duration = len(audio_np) / sample_rate

    print(f"Sample rate: {sample_rate} Hz")
    print("Channels   : 1")
    print("Format     : PCM s16le")
    print(f"Duration   : {duration:.3f} s")

    # --------------------------------------------------------
    # Convert int16 -> float32
    # --------------------------------------------------------

    audio_float = (
        audio_np.astype(np.float32) / 32768.0
    )

    wav = torch.from_numpy(audio_float)

    # Move audio to selected device.
    wav = wav.to(device)

    # --------------------------------------------------------
    # Detect speech
    # --------------------------------------------------------

    print()
    print("Detecting speech...")

    speech_timestamps = get_speech_timestamps(
        wav,
        model,
        sampling_rate=16000,

        # Probability threshold.
        threshold=0.5,

        # Ignore extremely short speech fragments.
        min_speech_duration_ms=120,

        # Join nearby fragments separated by short silence.
        min_silence_duration_ms=180,

        # Add small padding around detected speech.
        speech_pad_ms=80,

        # Return seconds instead of sample indexes.
        return_seconds=True,
    )

    # --------------------------------------------------------
    # Normalize intervals
    # --------------------------------------------------------

    intervals = []

    for item in speech_timestamps:

        start = float(item["start"])
        end = float(item["end"])

        # Clamp to actual audio duration.
        start = max(0.0, min(start, duration))
        end = max(0.0, min(end, duration))

        if end <= start:
            continue

        intervals.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
            }
        )

    # --------------------------------------------------------
    # Calculate statistics
    # --------------------------------------------------------

    total_speech = sum(
        interval["duration"]
        for interval in intervals
    )

    speech_ratio = (
        total_speech / duration
        if duration > 0
        else 0.0
    )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    result = {
        "schema_version": "1.0",

        "episode_key": episode_key,

        "audio": {
            "sample_rate": sample_rate,
            "channels": 1,
            "codec": "pcm_s16le",
            "duration": round(duration, 3),
        },

        "vad": {
            "model": "silero_vad",

            "threshold": 0.5,

            "min_speech_duration_ms": 120,

            "min_silence_duration_ms": 180,

            "speech_pad_ms": 80,
        },

        "device": {
            "type": device.type,
            "name": (
                torch.cuda.get_device_name(0)
                if device.type == "cuda"
                else "CPU"
            ),
        },

        "statistics": {
            "speech_interval_count": len(intervals),

            "speech_duration": round(
                total_speech,
                3,
            ),

            "speech_ratio": round(
                speech_ratio,
                6,
            ),

            "silence_duration": round(
                max(0.0, duration - total_speech),
                3,
            ),
        },

        "intervals": intervals,
    }

    # --------------------------------------------------------
    # Save JSON
    # --------------------------------------------------------

    output_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if not intervals:
        fail(
            "Silero VAD detected no speech intervals."
        )

    previous_end = 0.0

    for index, interval in enumerate(intervals):

        start = interval["start"]
        end = interval["end"]

        if start < 0:
            fail(
                f"Invalid interval #{index}: "
                f"negative start"
            )

        if end <= start:
            fail(
                f"Invalid interval #{index}: "
                f"end <= start"
            )

        if start < previous_end:
            fail(
                f"Overlapping VAD intervals "
                f"around #{index}"
            )

        if end > duration + 0.001:
            fail(
                f"Interval #{index} exceeds "
                f"audio duration"
            )

        previous_end = end

    # --------------------------------------------------------
    # Final output
    # --------------------------------------------------------

    print()
    print("=== RESULT ===")
    print(f"Duration           : {duration:.3f} s")
    print(f"Speech intervals   : {len(intervals)}")
    print(f"Speech duration    : {total_speech:.3f} s")
    print(f"Speech ratio       : {speech_ratio * 100:.2f}%")
    print(
        f"Silence duration   : "
        f"{max(0.0, duration - total_speech):.3f} s"
    )
    print(f"Manifest           : {output_path}")
    print()
    print("VAD PASSED")


if __name__ == "__main__":
    main()