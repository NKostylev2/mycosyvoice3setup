"""
Batch TTS Generation Pipeline for Martin Mystery S01E01 (Phase 9)
Synthesizes 159 TTS units using project-local XTTS-v2.

Key Features:
- Deterministic project-local runtime (via runtime_bootstrap)
- Sequential GPU inference with memory cleanup between units
- Idempotency (skips valid existing WAVs matching manifest)
- Headroom normalization to -1.0 dBFS to guarantee 0 clipping
- Rigorous post-generation audio quality validation
- Checkpointing manifest after every unit
- Support for debug sample (--sample) and full batch (--batch)
"""

import os
import sys
import json
import time
import hashlib
import argparse
from pathlib import Path
import numpy as np
import soundfile as sf
import torch

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# Initialize project-local runtime environment
PROJECT_ROOT = Path(r"E:\AI-Dubbing")
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.audio import runtime_bootstrap

WORK_DIR = PROJECT_ROOT / "work" / "S01E01"
PREPARATION_FILE = WORK_DIR / "tts_preparation.json"
VOICE_PROFILES_FILE = WORK_DIR / "voice_profiles.json"
TTS_OUTPUT_DIR = WORK_DIR / "tts"
MANIFEST_FILE = TTS_OUTPUT_DIR / "manifest.json"

REPRESENTATIVE_SAMPLE_UNITS = [
    "U0001-S01",
    "U0067-S01",
    "U0073-S01",
    "U0073-S02",
    "U0150-S01"
]

DEFAULT_PARAMS = {
    "temperature": 0.75,
    "length_penalty": 1.0,
    "repetition_penalty": 5.0,
    "top_k": 50,
    "top_p": 0.85,
    "split_sentences": False,
    "target_headroom_dbfs": -1.0,
    "target_sample_rate": 24000,
    "target_channels": 1,
    "target_subtype": "PCM_16"
}


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def validate_wav(file_path: Path):
    """
    Validates audio properties:
    - Exists and readable
    - Duration > 0.3s
    - Sample rate == 24000
    - Channels == 1
    - No NaN / Inf
    - Samples at or above 0 dBFS == 0
    - Not silent (RMS > -80 dBFS)
    Returns: (is_valid, metrics_dict, error_msg)
    """
    if not file_path.exists():
        return False, {}, "File does not exist"
    
    try:
        data_f, sr = sf.read(file_path, dtype="float32")
        data_i, _ = sf.read(file_path, dtype="int16")
    except Exception as e:
        return False, {}, f"Cannot read WAV: {e}"

    if data_f.ndim > 1:
        return False, {}, f"Audio has {data_f.ndim} channels, expected mono"

    dur = len(data_f) / sr
    if dur < 0.3:
        return False, {}, f"Duration too short ({dur:.3f}s < 0.3s)"

    if sr != 24000:
        return False, {}, f"Sample rate {sr} != 24000 Hz"

    if np.isnan(data_f).any() or np.isinf(data_f).any():
        return False, {}, "Audio contains NaN or Inf values"

    peak = float(np.max(np.abs(data_f)))
    rms = float(np.sqrt(np.mean(data_f ** 2)))
    
    if rms < 1e-5:
        return False, {}, f"Audio is completely silent (RMS={rms})"

    rms_db = float(20 * np.log10(rms)) if rms > 1e-9 else -100.0
    peak_db = float(20 * np.log10(peak)) if peak > 1e-9 else -100.0
    
    samples_0db = int(np.sum(np.abs(data_i) >= 32767))
    clipping = samples_0db > 0

    if clipping:
        return False, {}, f"Clipping detected: {samples_0db} samples at full-scale int16"

    metrics = {
        "duration_seconds": round(dur, 4),
        "sample_rate": sr,
        "channels": 1,
        "actual_peak": round(peak, 6),
        "peak_dbfs": round(peak_db, 4),
        "rms_dbfs": round(rms_db, 2),
        "samples_at_0dBFS": samples_0db,
        "clipping_detected": False,
        "subtype": "PCM_16"
    }
    return True, metrics, ""


def load_manifest():
    if MANIFEST_FILE.exists():
        try:
            with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "episode_id": "S01E01",
        "phase": "9",
        "engine": "XTTS-v2",
        "language": "ru",
        "parameters": DEFAULT_PARAMS,
        "units_total": 159,
        "units_completed": 0,
        "units_failed": 0,
        "units_skipped": 0,
        "units": {}
    }


def save_manifest(manifest):
    temp_path = MANIFEST_FILE.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    # Atomic replace
    if MANIFEST_FILE.exists():
        MANIFEST_FILE.unlink()
    temp_path.rename(MANIFEST_FILE)


def synthesize_unit(tts, unit, voice_profiles, attempt=1):
    """
    Synthesizes a single TTS unit with XTTS, applies -1.0 dBFS normalization,
    and returns job record.
    """
    unit_id = unit["unit_id"]
    utterance_id = unit["utterance_id"]
    speaker_id = unit["speaker_id"]
    vp_id = unit["voice_profile_id"]
    text_ru = unit["text_ru"]
    target_dur = unit["target_duration"]

    out_path = TTS_OUTPUT_DIR / f"{unit_id}.wav"
    ref_rel = voice_profiles[vp_id]["reference_audio_path"]
    ref_path = (WORK_DIR / ref_rel).resolve()

    if not ref_path.exists():
        return {
            "unit_id": unit_id,
            "status": "FAILED",
            "error_type": "INVALID_REFERENCE",
            "error": f"Reference file not found: {ref_path}"
        }

    job = {
        "unit_id": unit_id,
        "utterance_id": utterance_id,
        "span_index": unit.get("span_index", 0),
        "speaker_id": speaker_id,
        "voice_profile_id": vp_id,
        "reference_audio_path": str(ref_path.relative_to(PROJECT_ROOT)),
        "text_ru": text_ru,
        "target_duration": target_dur,
        "emotion": unit.get("emotion", "neutral"),
        "intensity": unit.get("intensity", 0.5),
        "delivery": unit.get("delivery", "standard"),
        "pace": unit.get("pace", "normal"),
        "voice_direction": unit.get("voice_direction", ""),
        "attempt": attempt,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "FAILED",
        "error_type": None,
        "error": None
    }

    t_start = time.time()
    try:
        tts.tts_to_file(
            text=text_ru,
            speaker_wav=str(ref_path),
            language="ru",
            file_path=str(out_path),
            split_sentences=False,
        )
        synth_time = time.time() - t_start

        # Headroom normalization to -1.0 dBFS
        audio_raw, out_sr = sf.read(out_path)
        peak_raw = np.max(np.abs(audio_raw))
        if peak_raw > 0:
            target_peak = 10 ** (-1.0 / 20.0)  # ~0.89125
            audio_norm = audio_raw * (target_peak / peak_raw)
            sf.write(out_path, audio_norm.astype(np.float32), 24000, subtype="PCM_16")

        # Validate
        valid, metrics, err = validate_wav(out_path)
        if not valid:
            job["error_type"] = "AUDIO_OUTPUT_ERROR"
            job["error"] = err
            return job

        gen_dur = metrics["duration_seconds"]
        delta = round(gen_dur - target_dur, 4)
        out_hash = compute_sha256(out_path)

        job.update({
            "status": "COMPLETED",
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "inference_duration_seconds": round(synth_time, 2),
            "output_path": str(out_path.relative_to(PROJECT_ROOT)),
            "output_sha256": out_hash,
            "generated_duration": gen_dur,
            "duration_delta": delta,
            "audio_metrics": metrics
        })
        return job

    except torch.cuda.OutOfMemoryError as e:
        torch.cuda.empty_cache()
        job["error_type"] = "OUT_OF_MEMORY"
        job["error"] = str(e)
        return job
    except Exception as e:
        job["error_type"] = "MODEL_ERROR"
        job["error"] = str(e)
        return job
    finally:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()


def run_pipeline(mode="sample", specific_unit=None, force=False):
    TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("PHASE 9 — BATCH TTS GENERATION PIPELINE")
    print(f"Mode: {mode.upper()}" + (f" (Unit: {specific_unit})" if specific_unit else ""))
    if force:
        print("FORCE FLAG: Enabled (bypassing idempotency cache)")
    print("=" * 80)

    # 1. Load frozen input
    with open(PREPARATION_FILE, "r", encoding="utf-8") as f:
        prep_data = json.load(f)
    tts_units = prep_data.get("tts_units", [])
    print(f"Loaded {len(tts_units)} canonical TTS units from tts_preparation.json")

    with open(VOICE_PROFILES_FILE, "r", encoding="utf-8") as f:
        vp_data = json.load(f)
    voice_profiles = vp_data["profiles"]

    # 2. Select target units
    if specific_unit:
        target_units = [u for u in tts_units if u["unit_id"] == specific_unit]
        if not target_units:
            print(f"ERROR: Unit {specific_unit} not found in tts_units!")
            sys.exit(1)
    elif mode == "sample":
        target_units = [u for u in tts_units if u["unit_id"] in REPRESENTATIVE_SAMPLE_UNITS]
    else:  # batch
        target_units = tts_units

    print(f"Target units for this run: {len(target_units)}")

    # 3. Load existing manifest
    manifest = load_manifest()
    manifest_invalidated = manifest.get("status") == "INVALIDATED_BY_GENERATION_PIPELINE_CHANGE"
    if manifest_invalidated:
        print("NOTICE: Manifest marked as INVALIDATED_BY_GENERATION_PIPELINE_CHANGE.")

    # 4. Check idempotency & filter units needing work
    units_to_run = []
    skipped_count = 0
    for u in target_units:
        uid = u["unit_id"]
        out_path = TTS_OUTPUT_DIR / f"{uid}.wav"
        
        # Check if already completed and valid
        existing_job = manifest["units"].get(uid)
        is_cache_valid = not force and not manifest_invalidated
        if is_cache_valid and existing_job and existing_job.get("status") == "COMPLETED" and out_path.exists():
            valid, _, _ = validate_wav(out_path)
            if valid and existing_job.get("output_sha256") == compute_sha256(out_path):
                skipped_count += 1
                continue
        units_to_run.append(u)

    print(f"Idempotency Check: {skipped_count} units already completed & valid (SKIP).")
    print(f"Units to generate: {len(units_to_run)}")

    if not units_to_run:
        print("\nAll target units are already synthesized and validated!")
        return

    # 5. Initialize XTTS model on GPU
    print("\nInitializing XTTS-v2 pipeline...")
    t_load_start = time.time()
    tts, resolved_paths = runtime_bootstrap.init_xtts_pipeline(gpu=True)
    print(f"XTTS-v2 loaded in {time.time() - t_load_start:.2f}s on GPU")

    # 6. Execute units sequentially
    print("\nBeginning sequential TTS generation...")
    completed_in_run = 0
    failed_in_run = 0

    for idx, unit in enumerate(units_to_run, 1):
        uid = unit["unit_id"]
        vp_id = unit["voice_profile_id"]
        txt = unit["text_ru"]
        print(f"\n[{idx}/{len(units_to_run)}] Unit: {uid} | Speaker: {unit['speaker_id']} ({vp_id})")
        print(f"  Text: \"{txt}\"")
        print(f"  Target duration: {unit['target_duration']:.3f}s")

        job = None
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            print(f"  Attempt {attempt}/{max_attempts}...")
            job = synthesize_unit(tts, unit, voice_profiles, attempt=attempt)
            if job["status"] == "COMPLETED":
                break
            print(f"  WARNING: Attempt {attempt} failed ({job.get('error_type')}: {job.get('error')})")
            time.sleep(1.0)

        # Update manifest
        manifest["units"][uid] = job
        if job["status"] == "COMPLETED":
            completed_in_run += 1
            print(f"  SUCCESS! Generated: {job['generated_duration']:.2f}s (delta: {job['duration_delta']:+.2f}s) | Peak: {job['audio_metrics']['peak_dbfs']} dBFS | Time: {job['inference_duration_seconds']}s")
        else:
            failed_in_run += 1
            print(f"  FAILED unit {uid}: {job['error']}")

        # Recount manifest totals
        manifest["units_completed"] = sum(1 for j in manifest["units"].values() if j.get("status") == "COMPLETED")
        manifest["units_failed"] = sum(1 for j in manifest["units"].values() if j.get("status") == "FAILED")
        manifest["units_skipped"] = skipped_count
        save_manifest(manifest)

    print("\n" + "=" * 80)
    print(f"RUN SUMMARY: Completed: {completed_in_run} | Failed: {failed_in_run} | Previously Skipped: {skipped_count}")
    print(f"Total Completed in Manifest: {manifest['units_completed']}/{manifest['units_total']}")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 9 Batch TTS Generation")
    parser.add_argument("--mode", choices=["sample", "batch", "unit"], default="sample", help="Generation mode")
    parser.add_argument("--unit", type=str, default=None, help="Specific unit ID to run")
    parser.add_argument("--force", action="store_true", help="Force re-generation of existing units")
    args = parser.parse_args()

    run_pipeline(mode=args.mode, specific_unit=args.unit, force=args.force)
