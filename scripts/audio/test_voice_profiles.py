"""
Voice Profile Test Synthesis Pipeline
Martin Mystery S01E01 - Phase 8: TTS Preparation & Voice Profile Implementation
Architectural Rule: Python performs deterministic GPU inference, validation, and serialization.
"""

import os
import sys
import json
import time
import hashlib
from pathlib import Path
import numpy as np
import soundfile as sf
import torch

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure Coqui license is agreed
os.environ["COQUI_TOS_AGREED"] = "1"

ROOT_DIR = Path(r"E:\AI-Dubbing")
WORK_DIR = ROOT_DIR / "work" / "S01E01"
VP_BASE_DIR = WORK_DIR / "voice_profiles"
TESTS_DIR = VP_BASE_DIR / "tests"
CATALOG_PATH = WORK_DIR / "voice_profiles.json"
RESULTS_PATH = VP_BASE_DIR / "test_synthesis_results.json"

TEST_PHRASE = "Это тестовая запись голосового профиля для дубляжа."

# Character-specific prompts if desired, or standardized prompt:
CHARACTER_TEST_PHRASES = {
    "vp_martin_mystery": "Это тестовая запись Мартина Мистери для дубляжа.",
    "vp_diana_lombard": "Это тестовая запись Дианы Ломбард для дубляжа.",
    "vp_billy": "Это тестовая запись Билли для дубляжа.",
    "vp_mom": "Это тестовая запись Эм О Эм для дубляжа.",
    "vp_librarian": "Это тестовая запись библиотекаря для дубляжа.",
    "vp_nelly": "Это тестовая запись Нелли для дубляжа.",
    "vp_ians_mother": "Это тестовая запись мамы Иэна для дубляжа.",
    "vp_townsperson": "Это тестовая запись жителя городка для дубляжа.",
    "vp_java": "Это тестовая запись Явы для дубляжа.",
    "vp_monster_bogeyman": "Это тестовая запись Бугимэна для дубляжа.",
}


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def validate_test_audio(audio_path: Path):
    if not audio_path.exists():
        return False, "File does not exist"
    
    # Read float32 and int16
    data_f, sr = sf.read(audio_path, dtype="float32")
    data_i, _ = sf.read(audio_path, dtype="int16")
    
    if data_f.ndim > 1:
        data_f = np.mean(data_f, axis=1)
        data_i = np.mean(data_i, axis=1).astype(np.int16)
        
    duration = len(data_f) / sr
    if duration < 0.4:
        return False, f"Duration too short ({duration:.2f}s < 0.4s)"
        
    if np.isnan(data_f).any() or np.isinf(data_f).any():
        return False, "Audio contains NaN or Inf values"
        
    peak = float(np.max(np.abs(data_f)))
    rms = float(np.sqrt(np.mean(data_f ** 2)))
    
    if rms < 1e-4:
        return False, f"Audio is silent (RMS={rms})"
        
    rms_db = float(20 * np.log10(rms)) if rms > 1e-9 else -100.0
    peak_db = float(20 * np.log10(peak)) if peak > 1e-9 else -100.0
    
    max_i = int(np.max(np.abs(data_i)))
    samples_at_0 = int(np.sum(np.abs(data_i) >= 32767))
    clipping_detected = samples_at_0 > 0
    
    stats = {
        "duration_seconds": round(duration, 4),
        "sample_rate": sr,
        "actual_peak": round(peak, 6),
        "peak_dbfs": round(peak_db, 4),
        "rms_dbfs": round(rms_db, 2),
        "max_int16": max_i,
        "full_scale_int16": 32767,
        "samples_at_or_above_0_dBFS": samples_at_0,
        "clipping_detected": clipping_detected,
    }
    return True, stats


def main():
    print("=" * 70)
    print("Phase 8: Voice Profile Test Synthesis Pipeline")
    print("=" * 70)

    # 1. Check GPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Inference Device: {device}")
    if device == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"GPU: {gpu_name} ({vram_gb:.2f} GB VRAM)")
    else:
        print("WARNING: CUDA not available, using CPU fallback (not recommended)")

    # 2. Load TTS model
    print("\nInitializing XTTS-v2 model...")
    from TTS.api import TTS
    t0 = time.time()
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=(device == "cuda"))
    print(f"XTTS-v2 loaded in {time.time() - t0:.2f}s")

    # 3. Load catalog
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog_data = json.load(f)

    profiles = catalog_data["profiles"]
    TESTS_DIR.mkdir(parents=True, exist_ok=True)

    test_results = {
        "episode_id": "S01E01",
        "phase": "8",
        "model": "XTTS-v2",
        "device": device,
        "gpu_name": torch.cuda.get_device_name(0) if device == "cuda" else "CPU",
        "total_profiles_tested": len(profiles),
        "passed_tests": 0,
        "failed_tests": 0,
        "profiles": {},
    }

    print(f"\nBeginning sequential test synthesis for {len(profiles)} profiles...")

    for vp_id, prof_info in profiles.items():
        print(f"\n--- Testing Profile: {vp_id} ({prof_info['canonical_name']}) ---")
        ref_path = WORK_DIR / prof_info["reference_audio_path"]
        if not ref_path.exists():
            print(f"ERROR: Reference audio not found at {ref_path}")
            test_results["failed_tests"] += 1
            test_results["profiles"][vp_id] = {"status": "FAIL", "error": "Reference audio not found"}
            continue

        test_out_path = TESTS_DIR / f"{vp_id}_test.wav"
        test_text = CHARACTER_TEST_PHRASES.get(vp_id, TEST_PHRASE)
        print(f"  Ref: {ref_path.name} ({ref_path})")
        print(f"  Text: '{test_text}'")
        print(f"  Target Output: {test_out_path.name}")

        # Measure inference time and VRAM
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.empty_cache()

        t_start = time.time()
        try:
            tts.tts_to_file(
                text=test_text,
                speaker_wav=str(ref_path),
                language="ru",
                file_path=str(test_out_path),
                split_sentences=False,
            )
            dur_synth = time.time() - t_start

            # Headroom normalization to -1.0 dBFS to eliminate any clipping risk
            audio_raw, out_sr = sf.read(test_out_path)
            peak_raw = np.max(np.abs(audio_raw))
            if peak_raw > 0:
                target_peak = 10 ** (-1.0 / 20.0) # ~0.89125
                audio_norm = audio_raw * (target_peak / peak_raw)
                sf.write(test_out_path, audio_norm.astype(np.float32), out_sr, subtype="PCM_16")

            # Check VRAM
            peak_vram_mb = 0.0
            if device == "cuda":
                peak_vram_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)

            # Validate generated audio
            valid, stats_or_err = validate_test_audio(test_out_path)
            if not valid:
                print(f"  FAILED validation: {stats_or_err}")
                test_results["failed_tests"] += 1
                test_results["profiles"][vp_id] = {
                    "status": "FAIL",
                    "error": stats_or_err,
                    "synthesis_time_s": round(dur_synth, 2),
                }
            else:
                out_hash = compute_sha256(test_out_path)
                print(f"  PASSED! Duration: {stats_or_err['duration_seconds']}s, Peak: {stats_or_err['peak_db']} dBFS, RMS: {stats_or_err['rms_db']} dBFS")
                print(f"  Inference Time: {dur_synth:.2f}s, Peak VRAM: {peak_vram_mb:.1f} MB")
                test_results["passed_tests"] += 1
                test_results["profiles"][vp_id] = {
                    "status": "PASS",
                    "test_phrase": test_text,
                    "output_file": f"voice_profiles/tests/{test_out_path.name}",
                    "synthesis_time_s": round(dur_synth, 2),
                    "peak_vram_mb": round(peak_vram_mb, 1),
                    "sha256": out_hash,
                    "audio_metrics": stats_or_err,
                }
        except Exception as e:
            print(f"  EXCEPTION during synthesis: {e}")
            test_results["failed_tests"] += 1
            test_results["profiles"][vp_id] = {
                "status": "ERROR",
                "error": str(e),
            }

        # Clear VRAM cache between runs
        if device == "cuda":
            torch.cuda.empty_cache()

    # Save results
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(test_results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved test synthesis results: {RESULTS_PATH}")

    # Print summary
    print("=" * 70)
    print(f"TEST SYNTHESIS SUMMARY: {test_results['passed_tests']}/{test_results['total_profiles_tested']} PASS")
    if test_results["failed_tests"] == 0:
        print("ALL 10 VOICE PROFILES VALIDATED SUCCESSFULLY!")
    else:
        print(f"WARNING: {test_results['failed_tests']} PROFILES FAILED!")
    print("=" * 70)


if __name__ == "__main__":
    main()
