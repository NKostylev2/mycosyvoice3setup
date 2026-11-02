"""
scripts/audio/extract_rvc_dataset.py

Extracts isolated character speech slices from episode audio based on speaker casting timestamps.
Uses the cleaned vocal stem (english_vocals.wav) if available, falling back to english.wav.
Optionally applies DeepFilterNet to remove any residual room reverb / noise.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
import soundfile as sf
import numpy as np

PROJECT_ROOT = Path(r"E:\AI-Dubbing")
WORK_DIR = PROJECT_ROOT / "work" / "S01E01"
VOCALS_PATH = WORK_DIR / "audio" / "english_vocals.wav"
FALLBACK_AUDIO_PATH = WORK_DIR / "audio" / "english.wav"
CASTING_PATH = WORK_DIR / "speaker_casting.json"
DATASET_BASE_DIR = WORK_DIR / "rvc_dataset"

DEEP_FILTER_EXE = PROJECT_ROOT / "models" / "Applio" / "assets" / "audio-cleanup" / "0.5.6" / "deep-filter-0.5.6-x86_64-pc-windows-msvc.exe"
DEEP_FILTER_MODEL = PROJECT_ROOT / "models" / "Applio" / "assets" / "audio-cleanup" / "0.5.6" / "DeepFilterNet3_onnx.tar.gz"

def extract_character_dataset(character_id: str = "martin_mystery", denoise: bool = True):
    audio_source = VOCALS_PATH if VOCALS_PATH.exists() else FALLBACK_AUDIO_PATH
    target_dir = DATASET_BASE_DIR / character_id

    # If old dataset exists and was noisy, backup once
    backup_dir = DATASET_BASE_DIR / f"{character_id}_original_noisy"
    if target_dir.exists() and not backup_dir.exists():
        print(f"Backing up original slices to {backup_dir}...")
        shutil.copytree(str(target_dir), str(backup_dir))

    target_dir.mkdir(parents=True, exist_ok=True)

    with open(CASTING_PATH, "r", encoding="utf-8") as f:
        casting_data = json.load(f)

    print(f"\n[INFO] Source audio: {audio_source}")
    with sf.SoundFile(str(audio_source)) as master_sf:
        sr = master_sf.samplerate
        total_frames = master_sf.frames
        total_duration = total_frames / sr
        print(f"Master audio: {total_duration:.2f}s ({total_duration/60:.2f} min), Sample rate: {sr} Hz")

        character_utts = [
            u for u in casting_data.get("utterances", [])
            if u.get("speaker_id") == character_id
        ]

        print(f"Found {len(character_utts)} utterances for character '{character_id}'.")
        extracted_count = 0
        total_speech_len = 0.0

        raw_files = []
        for u in character_utts:
            uid = u["uid"]
            start_sec = u["acoustic_start"]
            end_sec = u["acoustic_end"]
            duration = end_sec - start_sec

            if duration < 0.4:
                continue

            start_samp = max(0, int(start_sec * sr))
            end_samp = min(total_frames, int(end_sec * sr))
            frames_to_read = end_samp - start_samp

            master_sf.seek(start_samp)
            chunk = master_sf.read(frames_to_read, dtype="float32")

            # Convert stereo to mono if needed
            if chunk.ndim > 1:
                chunk = np.mean(chunk, axis=1)

            # Normalize headroom to -1 dBFS
            peak = np.max(np.abs(chunk))
            if peak > 1e-5:
                target_amp = 10 ** (-1.0 / 20.0)
                chunk = chunk * (target_amp / peak)

            out_file = target_dir / f"{uid}.wav"
            sf.write(str(out_file), chunk.astype(np.float32), sr)
            raw_files.append(out_file)
            extracted_count += 1
            total_speech_len += duration

    print(f"\n[DONE] Extracted {extracted_count} slices to: {target_dir}")
    print(f"Total training dataset duration: {total_speech_len:.2f} seconds ({total_speech_len/60:.2f} minutes)")

    # Run DeepFilterNet if requested and available
    if denoise and DEEP_FILTER_EXE.exists() and DEEP_FILTER_MODEL.exists():
        print("\n[INFO] Running DeepFilterNet3 to eliminate background noise and room reverb...")
        temp_clean_dir = DATASET_BASE_DIR / f"{character_id}_cleaned_temp"
        temp_clean_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            str(DEEP_FILTER_EXE),
            "-m", str(DEEP_FILTER_MODEL),
            "-o", str(temp_clean_dir)
        ] + [str(p) for p in raw_files]

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0:
            for f in temp_clean_dir.glob("*.wav"):
                shutil.move(str(f), str(target_dir / f.name))
            shutil.rmtree(str(temp_clean_dir), ignore_errors=True)
            print("[SUCCESS] DeepFilterNet3 applied to all slices! Dataset is crystal clean.")
        else:
            print(f"[WARNING] DeepFilterNet exited with code {res.returncode}. Keeping standard slices.")

    return target_dir

if __name__ == "__main__":
    extract_character_dataset("martin_mystery", denoise=True)
