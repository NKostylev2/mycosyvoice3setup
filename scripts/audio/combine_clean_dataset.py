"""
scripts/audio/combine_clean_dataset.py

Combines clean character utterances into a single continuous master WAV file.
Inserts a 0.4s natural silence gap between utterances and normalizes headroom to -1.0 dBFS.
Also exports a dedicated reference sample for AllTalk / CosyVoice TTS voice cloning.
"""

import json
from pathlib import Path
import soundfile as sf
import numpy as np

PROJECT_ROOT = Path(r"E:\AI-Dubbing")
WORK_DIR = PROJECT_ROOT / "work" / "S01E01"
CASTING_PATH = WORK_DIR / "speaker_casting.json"
DATASET_BASE_DIR = WORK_DIR / "rvc_dataset"
ALLTALK_VOICES_DIR = PROJECT_ROOT / "alltalk_tts" / "voices"

REFERENCE_CANDIDATES = {
    "martin_mystery": ["U0010", "U0011"],
    "diana_lombard": ["U0129", "U0094"]
}

def combine_character(character_id: str = "martin_mystery", gap_seconds: float = 0.4):
    print("=" * 60)
    print(f"  Combining Clean Slices into Master WAV: {character_id}")
    print("=" * 60)

    slices_dir = DATASET_BASE_DIR / character_id
    combined_file = DATASET_BASE_DIR / f"{character_id}_combined.wav"
    single_dir = DATASET_BASE_DIR / f"{character_id}_single"

    with open(CASTING_PATH, "r", encoding="utf-8") as f:
        casting_data = json.load(f)

    # Filter and sort character utterances chronologically
    character_utts = sorted(
        [u for u in casting_data.get("utterances", []) if u.get("speaker_id") == character_id],
        key=lambda x: x["acoustic_start"]
    )

    audio_chunks = []
    target_sr = None
    processed_count = 0
    total_speech_duration = 0.0

    silence_gap = None

    for u in character_utts:
        uid = u["uid"]
        slice_path = slices_dir / f"{uid}.wav"
        if not slice_path.exists():
            continue

        data, sr = sf.read(str(slice_path))
        if target_sr is None:
            target_sr = sr
            silence_gap = np.zeros(int(gap_seconds * sr), dtype=np.float32)

        # Convert to mono if needed
        if data.ndim > 1:
            data = np.mean(data, axis=1)

        # Ensure float32
        data = data.astype(np.float32)

        audio_chunks.append(data)
        audio_chunks.append(silence_gap)
        processed_count += 1
        total_speech_duration += len(data) / sr

    if not audio_chunks:
        print(f"[ERROR] No audio chunks found for {character_id} in {slices_dir}!")
        return

    # Remove the trailing silence gap
    audio_chunks.pop()

    # Concatenate all chunks
    combined_audio = np.concatenate(audio_chunks)
    total_combined_duration = len(combined_audio) / target_sr

    # Normalize headroom to -1.0 dBFS
    peak = np.max(np.abs(combined_audio))
    if peak > 1e-5:
        target_amp = 10 ** (-1.0 / 20.0)
        combined_audio = combined_audio * (target_amp / peak)

    # 1. Save main combined file
    sf.write(str(combined_file), combined_audio, target_sr, subtype="PCM_16")
    print(f"\n[DONE] Saved combined master file: {combined_file}")
    print(f"- Slices combined: {processed_count}")
    print(f"- Net speech duration: {total_speech_duration:.2f}s ({total_speech_duration/60:.2f} min)")
    print(f"- Total duration with pauses: {total_combined_duration:.2f}s ({total_combined_duration/60:.2f} min)")
    print(f"- Sample rate: {target_sr} Hz, Format: 16-bit PCM WAV (Mono)")

    # 2. Save into dedicated single-file directory for easy Applio selection
    single_dir.mkdir(parents=True, exist_ok=True)
    single_dest = single_dir / f"{character_id}_clean_all.wav"
    sf.write(str(single_dest), combined_audio, target_sr, subtype="PCM_16")
    print(f"[DONE] Saved copy to single-file folder: {single_dest}")

    # 3. Export prime reference voice sample for AllTalk / CosyVoice
    if ALLTALK_VOICES_DIR.exists() and character_id in REFERENCE_CANDIDATES:
        ref_chunks = []
        for uid in REFERENCE_CANDIDATES[character_id]:
            p = slices_dir / f"{uid}.wav"
            if p.exists():
                d, _ = sf.read(str(p))
                if d.ndim > 1:
                    d = np.mean(d, axis=1)
                ref_chunks.append(d.astype(np.float32))
                ref_chunks.append(silence_gap)

        if ref_chunks:
            ref_chunks.pop()
            ref_audio = np.concatenate(ref_chunks)
            ref_peak = np.max(np.abs(ref_audio))
            if ref_peak > 1e-5:
                ref_audio = ref_audio * ((10 ** (-1.0 / 20.0)) / ref_peak)
            alltalk_ref_path = ALLTALK_VOICES_DIR / f"{character_id}.wav"
            sf.write(str(alltalk_ref_path), ref_audio, target_sr, subtype="PCM_16")
            print(f"[DONE] Saved AllTalk/CosyVoice voice reference: {alltalk_ref_path} ({len(ref_audio)/target_sr:.2f}s)")

if __name__ == "__main__":
    combine_character("martin_mystery")
    combine_character("diana_lombard")
