import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from collections import defaultdict
import soundfile as sf
import numpy as np

PROJECT_ROOT = Path(r"E:\AI-Dubbing")
WORK_DIR = PROJECT_ROOT / "work" / "S01E01"
VOCALS_PATH = WORK_DIR / "audio" / "english_vocals.wav"
CASTING_PATH = WORK_DIR / "speaker_casting.json"
DATASET_BASE_DIR = WORK_DIR / "rvc_dataset"
VOICES_DIR = PROJECT_ROOT / "alltalk_tts" / "voices"

DEEP_FILTER_EXE = PROJECT_ROOT / "models" / "Applio" / "assets" / "audio-cleanup" / "0.5.6" / "deep-filter-0.5.6-x86_64-pc-windows-msvc.exe"
DEEP_FILTER_MODEL = PROJECT_ROOT / "models" / "Applio" / "assets" / "audio-cleanup" / "0.5.6" / "DeepFilterNet3_onnx.tar.gz"

def trim_and_tighten(audio_data, sr, max_pause_sec=0.10, energy_thresh=0.015, min_speech_sec=0.08):
    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)

    frame_len = int(0.01 * sr)
    num_frames = len(audio_data) // frame_len
    if num_frames == 0:
        return audio_data

    energies = np.array([
        np.sqrt(np.mean(audio_data[i*frame_len : (i+1)*frame_len]**2))
        for i in range(num_frames)
    ])

    is_speech = energies > energy_thresh
    smoothed = np.copy(is_speech)
    for i in range(len(smoothed) - 5):
        if is_speech[i]:
            smoothed[i:i+6] = True

    segments = []
    in_seg = False
    start = 0
    for i, sp in enumerate(smoothed):
        if sp and not in_seg:
            in_seg = True
            start = i
        elif not sp and in_seg:
            in_seg = False
            dur = (i - start) * 0.01
            if dur >= min_speech_sec:
                segments.append((start * frame_len, i * frame_len))

    if in_seg:
        segments.append((start * frame_len, num_frames * frame_len))

    if not segments:
        return audio_data

    max_pause_samples = int(max_pause_sec * sr)
    assembled = []
    prev_end = None

    for s_start, s_end in segments:
        chunk = audio_data[s_start:s_end]
        if prev_end is not None:
            gap = np.zeros(max_pause_samples, dtype=np.float32)
            assembled.append(gap)
        assembled.append(chunk.astype(np.float32))
        prev_end = s_end

    return np.concatenate(assembled)

def extract_all():
    print("=" * 65)
    print("  Extracting & Denoising Secondary Characters from Vocal Master")
    print("=" * 65)

    with open(CASTING_PATH, "r", encoding="utf-8") as f:
        casting = json.load(f)

    # Collect spans grouped by speaker_id
    speaker_spans = defaultdict(list)
    for u in casting.get("utterances", []):
        spans = u.get("speaker_spans", [])
        if spans:
            for s in spans:
                spk = s.get("speaker_id")
                speaker_spans[spk].append({
                    "span_id": s.get("span_id", u["uid"]),
                    "start": s.get("acoustic_start", u["acoustic_start"]),
                    "end": s.get("acoustic_end", u["acoustic_end"]),
                    "duration": s.get("duration", s.get("acoustic_end", 0) - s.get("acoustic_start", 0)),
                    "text_en": s.get("source_en", ""),
                    "text_ru": s.get("text_ru", "")
                })
        else:
            spk = u.get("speaker_id")
            speaker_spans[spk].append({
                "span_id": u["uid"],
                "start": u["acoustic_start"],
                "end": u["acoustic_end"],
                "duration": u["duration"],
                "text_en": u.get("source_en", ""),
                "text_ru": u.get("text_ru", "")
            })

    characters_to_process = [
        spk for spk in speaker_spans.keys()
        if spk not in ("martin_mystery", "diana_lombard")
    ]

    print(f"Characters to extract: {characters_to_process}")

    with sf.SoundFile(str(VOCALS_PATH)) as master_sf:
        sr = master_sf.samplerate
        total_frames = master_sf.frames
        print(f"Master vocals loaded: {sr} Hz, {total_frames / sr:.1f}s")

        for character_id in characters_to_process:
            spans = speaker_spans[character_id]
            target_dir = DATASET_BASE_DIR / character_id
            target_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n--- Processing: {character_id} ({len(spans)} spans) ---")
            raw_files = []
            total_duration = 0.0

            for s in spans:
                span_id = s["span_id"]
                start_sec = s["start"]
                end_sec = s["end"]
                dur = end_sec - start_sec

                if dur < 0.2:
                    continue

                start_samp = max(0, int(start_sec * sr))
                end_samp = min(total_frames, int(end_sec * sr))
                frames_to_read = end_samp - start_samp

                master_sf.seek(start_samp)
                chunk = master_sf.read(frames_to_read, dtype="float32")

                if chunk.ndim > 1:
                    chunk = np.mean(chunk, axis=1)

                peak = np.max(np.abs(chunk))
                if peak > 1e-5:
                    chunk = chunk * ((10 ** (-1.0 / 20.0)) / peak)

                out_file = target_dir / f"{span_id}.wav"
                sf.write(str(out_file), chunk.astype(np.float32), sr)
                raw_files.append(out_file)
                total_duration += dur

            print(f"  Extracted {len(raw_files)} slices ({total_duration:.2f}s total)")

            # Denoise with DeepFilterNet3
            if DEEP_FILTER_EXE.exists() and DEEP_FILTER_MODEL.exists() and raw_files:
                temp_clean = DATASET_BASE_DIR / f"{character_id}_temp"
                temp_clean.mkdir(parents=True, exist_ok=True)
                cmd = [
                    str(DEEP_FILTER_EXE),
                    "-m", str(DEEP_FILTER_MODEL),
                    "-o", str(temp_clean)
                ] + [str(p) for p in raw_files]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode == 0:
                    for f in temp_clean.glob("*.wav"):
                        shutil.move(str(f), str(target_dir / f.name))
                    shutil.rmtree(str(temp_clean), ignore_errors=True)
                    print("  [SUCCESS] DeepFilterNet3 denoising applied.")
                else:
                    print(f"  [WARNING] DeepFilterNet exited with {res.returncode}")

            # Assemble clean tight reference for TTS/voice cloning
            ref_chunks = []
            for rf in raw_files:
                d, s_rate = sf.read(str(rf))
                tight_d = trim_and_tighten(d, s_rate, max_pause_sec=0.10)
                if len(tight_d) / s_rate >= 0.15:
                    ref_chunks.append(tight_d)
                    ref_chunks.append(np.zeros(int(0.12 * s_rate), dtype=np.float32))

            if ref_chunks:
                ref_chunks.pop()
                combined_ref = np.concatenate(ref_chunks)
                peak = np.max(np.abs(combined_ref))
                if peak > 1e-5:
                    combined_ref = combined_ref * ((10 ** (-1.0 / 20.0)) / peak)

                voice_file = VOICES_DIR / f"{character_id}.wav"
                sf.write(str(voice_file), combined_ref, sr, subtype="PCM_16")
                comb_file = DATASET_BASE_DIR / f"{character_id}_combined.wav"
                sf.write(str(comb_file), combined_ref, sr, subtype="PCM_16")

                ref_dur = len(combined_ref) / sr
                print(f"  [READY] Created voice reference: {voice_file} ({ref_dur:.2f}s active speech)")

    print("\n" + "=" * 65)
    print("  [DONE] All character slices and references extracted successfully!")
    print("=" * 65)

if __name__ == "__main__":
    extract_all()
