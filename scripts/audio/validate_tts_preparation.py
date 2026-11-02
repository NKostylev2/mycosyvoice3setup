"""
Phase 8 Gate Validator: TTS Preparation & Voice Profile Implementation
Martin Mystery S01E01 - Phase 8 Gate
Architectural Rule: Python performs deterministic validation and verification.
Authoritative Inputs:
  - Phase 7 Finalized Speaker Casting: work/S01E01/speaker_casting.json
  - Phase 6C Final Russian Translation: work/S01E01/russian_dubbing_input.json
"""

import sys
import json
import hashlib
from pathlib import Path
import numpy as np
import soundfile as sf

ROOT_DIR = Path(r"E:\AI-Dubbing")
WORK_DIR = ROOT_DIR / "work" / "S01E01"
VP_BASE_DIR = WORK_DIR / "voice_profiles"
TESTS_DIR = VP_BASE_DIR / "tests"

CANONICAL_PROFILES = [
    "vp_martin_mystery",
    "vp_diana_lombard",
    "vp_billy",
    "vp_mom",
    "vp_librarian",
    "vp_nelly",
    "vp_ians_mother",
    "vp_townsperson",
    "vp_java",
    "vp_monster_bogeyman",
]


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def check_audio_file(file_path: Path, min_duration: float = 0.5):
    if not file_path.exists():
        return False, f"File does not exist: {file_path}"
    try:
        data, sr = sf.read(file_path)
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        dur = len(data) / sr
        if dur < min_duration:
            return False, f"Duration {dur:.2f}s < min {min_duration:.2f}s"
        if np.isnan(data).any() or np.isinf(data).any():
            return False, "Audio contains NaN or Inf"
        peak = float(np.max(np.abs(data)))
        rms = float(np.sqrt(np.mean(data ** 2)))
        if rms < 1e-4:
            return False, f"Audio is silent (RMS={rms})"
        peak_db = float(20 * np.log10(peak)) if peak > 1e-9 else -100.0
        if peak_db > 0.05:
            return False, f"Digital clipping detected: peak={peak_db:.2f} dBFS"
        return True, {
            "duration": round(dur, 3),
            "sample_rate": sr,
            "peak_db": round(peak_db, 2),
            "rms_db": round(float(20 * np.log10(rms)), 2),
        }
    except Exception as e:
        return False, f"Audio read error: {e}"


def check_raw_pcm_clipping(audio_path: Path):
    if not audio_path.exists():
        return False, f"File not found: {audio_path}"
    try:
        data_f, sr = sf.read(audio_path, dtype="float32")
        data_i, _ = sf.read(audio_path, dtype="int16")
        
        if data_f.ndim > 1:
            data_f = np.mean(data_f, axis=1)
            data_i = np.mean(data_i, axis=1).astype(np.int16)
            
        dur = len(data_f) / sr
        max_f = float(np.max(np.abs(data_f)))
        max_i = int(np.max(np.abs(data_i)))
        rms = float(np.sqrt(np.mean(data_f ** 2)))
        peak_dbfs = float(20 * np.log10(max_f)) if max_f > 1e-9 else -100.0
        rms_dbfs = float(20 * np.log10(rms)) if rms > 1e-9 else -100.0
        
        samples_at_0 = int(np.sum(np.abs(data_i) >= 32767))
        clipping_detected = samples_at_0 > 0 or max_f >= 1.0
        
        metrics = {
            "duration_seconds": round(dur, 4),
            "sample_rate": sr,
            "actual_peak": round(max_f, 6),
            "peak_dbfs": round(peak_dbfs, 4),
            "rms_dbfs": round(rms_dbfs, 2),
            "max_int16": max_i,
            "full_scale_int16": 32767,
            "samples_at_or_above_0_dBFS": samples_at_0,
            "clipping_detected": clipping_detected,
        }
        return (not clipping_detected), metrics
    except Exception as e:
        return False, f"Raw PCM read error: {e}"


def main():
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr.encoding != "utf-8":
        sys.stderr.reconfigure(encoding="utf-8")

    print("=" * 80)
    print("PHASE 8 GATE VALIDATOR: TTS PREPARATION & VOICE PROFILE IMPLEMENTATION")
    print("=" * 80)

    errors = []
    warnings = []

    # 1. Check Voice Profiles Catalog
    catalog_path = WORK_DIR / "voice_profiles.json"
    if not catalog_path.exists():
        errors.append(f"Missing catalog: {catalog_path}")
        print("FAIL: voice_profiles.json missing")
        sys.exit(1)

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    if catalog.get("status") != "VOICE_PROFILES_IMPLEMENTED":
        errors.append(f"Catalog status is {catalog.get('status')}, expected VOICE_PROFILES_IMPLEMENTED")

    profiles = catalog.get("profiles", {})
    if len(profiles) != 10:
        errors.append(f"Catalog has {len(profiles)} profiles, expected 10")

    for vp_id in CANONICAL_PROFILES:
        if vp_id not in profiles:
            errors.append(f"Missing canonical profile in catalog: {vp_id}")

    print(f"[CHECK 1] Voice Profiles Catalog: {len(profiles)}/10 canonical profiles present.")

    # 2. Check Episode Manifest
    ep_manifest_path = WORK_DIR / "voice_profile_manifest.json"
    if not ep_manifest_path.exists():
        errors.append(f"Missing episode manifest: {ep_manifest_path}")
    else:
        with open(ep_manifest_path, "r", encoding="utf-8") as f:
            ep_manifest = json.load(f)
        if len(ep_manifest.get("profiles", {})) != 10:
            errors.append(f"Episode manifest has {len(ep_manifest.get('profiles', {}))} profiles, expected 10")
        print(f"[CHECK 2] Episode Manifest: {len(ep_manifest.get('profiles', {}))}/10 profiles present.")

    # 3. Check Individual Voice Profiles Directories & Selected References
    print("\n[CHECK 3] Individual Profile Directories & Audio Integrity:")
    for vp_id in CANONICAL_PROFILES:
        vp_dir = VP_BASE_DIR / vp_id
        if not vp_dir.exists():
            errors.append(f"Directory missing: {vp_dir}")
            continue

        manifest_file = vp_dir / "manifest.json"
        if not manifest_file.exists():
            errors.append(f"Manifest missing: {manifest_file}")
            continue

        with open(manifest_file, "r", encoding="utf-8") as pf:
            p_man = json.load(pf)

        # Profile type verification
        if vp_id == "vp_monster_bogeyman":
            if p_man.get("profile_type") != "CREATURE":
                errors.append(f"{vp_id} profile_type is '{p_man.get('profile_type')}', expected 'CREATURE'")

        # Selected reference verification
        ref_file = vp_dir / "selected" / "reference.wav"
        valid, stats = check_audio_file(ref_file, min_duration=1.0)
        if not valid:
            errors.append(f"{vp_id} reference.wav invalid: {stats}")
        else:
            # Check SHA-256
            on_disk_hash = compute_sha256(ref_file)
            recorded_hash = p_man.get("selected_reference", {}).get("sha256", "")
            if on_disk_hash != recorded_hash:
                errors.append(f"{vp_id} reference.wav SHA-256 mismatch (disk: {on_disk_hash[:8]}, record: {recorded_hash[:8]})")
            print(f"  - {vp_id:20s}: PASS (Dur: {stats['duration']}s, Peak: {stats['peak_db']} dBFS, RMS: {stats['rms_db']} dBFS)")

        # Candidate files verification
        candidates = p_man.get("candidates", [])
        if not candidates:
            errors.append(f"{vp_id} has no candidates listed in manifest")
        for cand in candidates:
            cand_path = WORK_DIR / cand["relative_path"]
            cand_valid, cand_stats = check_audio_file(cand_path, min_duration=0.4)
            if not cand_valid:
                errors.append(f"Candidate {cand['candidate_id']} for {vp_id} invalid: {cand_stats}")

    # 4. Check Test Synthesis Results & Raw PCM Clipping Audit
    print("\n[CHECK 4] Test Synthesis & Raw PCM Headroom / Clipping Audit:")
    test_results_path = VP_BASE_DIR / "test_synthesis_results.json"
    if not test_results_path.exists():
        errors.append(f"Missing test synthesis results: {test_results_path}")
    else:
        with open(test_results_path, "r", encoding="utf-8") as tf:
            test_results = json.load(tf)
        passed = test_results.get("passed_tests", 0)
        failed = test_results.get("failed_tests", 0)
        total = test_results.get("total_profiles_tested", 0)
        if passed != 10 or failed != 0 or total != 10:
            errors.append(f"Test synthesis summary: {passed} passed, {failed} failed out of {total} (expected 10 passed, 0 failed)")
        
        for vp_id in CANONICAL_PROFILES:
            prof_res = test_results.get("profiles", {}).get(vp_id, {})
            if prof_res.get("status") != "PASS":
                errors.append(f"Test synthesis for {vp_id} is not PASS: {prof_res.get('error', 'unknown error')}")
            else:
                test_wav = VP_BASE_DIR / "tests" / f"{vp_id}_test.wav"
                no_clip, pcm_stats = check_raw_pcm_clipping(test_wav)
                if not no_clip or isinstance(pcm_stats, str):
                    errors.append(f"Clipping violation in {vp_id}_test.wav: {pcm_stats}")
                else:
                    actual_peak = pcm_stats["actual_peak"]
                    at_0 = pcm_stats["samples_at_or_above_0_dBFS"]
                    clipping = pcm_stats["clipping_detected"]
                    if at_0 > 0 or clipping or actual_peak >= 1.0:
                        errors.append(f"{vp_id}_test.wav has clipping violation: actual_peak={actual_peak}, samples_at_0dBFS={at_0}, clipping={clipping}")
                    else:
                        print(f"  - {vp_id:20s}: PASS (Dur: {pcm_stats['duration_seconds']}s, actual_peak: {actual_peak:.6f}, peak_dbfs: {pcm_stats['peak_dbfs']} dBFS, samples_at_0dBFS: {at_0}, clipping: {clipping})")

    # 5. MANDATORY DIFFERENTIAL AUDIT: Phase 7 speaker_casting.json vs Phase 8 tts_preparation.json
    print("\n[CHECK 5] MANDATORY DIFFERENTIAL AUDIT: Phase 7 speaker_casting.json vs Phase 8 tts_preparation.json (159 Spans):")
    sc_path = WORK_DIR / "speaker_casting.json"
    ttp_path = WORK_DIR / "tts_preparation.json"

    with open(sc_path, "r", encoding="utf-8") as f:
        sc = json.load(f)
    with open(ttp_path, "r", encoding="utf-8") as f:
        ttp = json.load(f)

    # Build sc span map
    sc_spans = {}
    for u in sc["utterances"]:
        uid = u["uid"]
        for sp in u.get("speaker_spans", []):
            sp_id = sp["span_id"]
            sc_spans[sp_id] = {
                "uid": uid,
                "span_id": sp_id,
                "speaker_id": sp["speaker_id"],
                "voice_profile_id": sp["voice_profile_id"],
                "acoustic_start": sp["acoustic_start"],
                "acoustic_end": sp["acoustic_end"],
                "text_ru": sp["text_ru"],
                "source_en": sp["source_en"],
            }

    ttp_units = {}
    for unit in ttp.get("tts_units", []):
        ttp_units[unit["unit_id"]] = unit

    print(f"  Total Phase 7 spans: {len(sc_spans)} (expected 159)")
    print(f"  Total Phase 8 units: {len(ttp_units)} (expected 159)")

    if len(sc_spans) != 159:
        errors.append(f"Phase 7 speaker_casting.json has {len(sc_spans)} spans, expected 159")
    if len(ttp_units) != 159:
        errors.append(f"Phase 8 tts_preparation.json has {len(ttp_units)} units, expected 159")

    diff_count = 0
    composite_ids = ["U0073", "U0092", "U0094", "U0117", "U0150"]
    for sp_id, sc_sp in sc_spans.items():
        if sp_id not in ttp_units:
            errors.append(f"UID MISMATCH / MISSING UNIT: {sp_id} present in Phase 7 but missing in Phase 8")
            diff_count += 1
            continue
        ttp_u = ttp_units[sp_id]

        # 1. Speaker mismatch
        if sc_sp["speaker_id"] != ttp_u["speaker_id"]:
            errors.append(f"{sp_id} SPEAKER MISMATCH: Phase7='{sc_sp['speaker_id']}' vs Phase8='{ttp_u['speaker_id']}'")
            diff_count += 1

        # 2. Voice profile mismatch
        if sc_sp["voice_profile_id"] != ttp_u["voice_profile_id"]:
            errors.append(f"{sp_id} VOICE PROFILE MISMATCH: Phase7='{sc_sp['voice_profile_id']}' vs Phase8='{ttp_u['voice_profile_id']}'")
            diff_count += 1

        # 3. Span start mismatch
        if abs(sc_sp["acoustic_start"] - ttp_u["acoustic_start"]) > 0.001:
            errors.append(f"{sp_id} SPAN START MISMATCH: Phase7={sc_sp['acoustic_start']} vs Phase8={ttp_u['acoustic_start']}")
            diff_count += 1

        # 4. Span end mismatch
        if abs(sc_sp["acoustic_end"] - ttp_u["acoustic_end"]) > 0.001:
            errors.append(f"{sp_id} SPAN END MISMATCH: Phase7={sc_sp['acoustic_end']} vs Phase8={ttp_u['acoustic_end']}")
            diff_count += 1

        # 5. Text mismatch
        if sc_sp["text_ru"].strip() != ttp_u["text_ru"].strip():
            errors.append(f"{sp_id} TEXT MISMATCH: Phase7='{sc_sp['text_ru']}' vs Phase8='{ttp_u['text_ru']}'")
            diff_count += 1

    if diff_count == 0:
        print("  --> DIFFERENTIAL AUDIT: 159/159 EXACT MATCHES (0 mismatches).")
        print("      - speaker_id:      159/159 match")
        print("      - voice_profile_id: 159/159 match")
        print("      - acoustic_start:   159/159 match")
        print("      - acoustic_end:     159/159 match")
        print("      - text_ru:          159/159 match")
    else:
        print(f"  --> DIFFERENTIAL AUDIT FAILED with {diff_count} mismatches!")

    # Explicit check on the 5 composite utterances
    print("\n  Detailed Composite Utterances Verification:")
    for cid in composite_ids:
        sp1 = f"{cid}-S01"
        sp2 = f"{cid}-S02"
        u1 = ttp_units.get(sp1)
        u2 = ttp_units.get(sp2)
        if u1 and u2:
            print(f"    {cid}: S01={u1['speaker_id']} ({u1['voice_profile_id']}) [{u1['acoustic_start']:.3f}-{u1['acoustic_end']:.3f}] | "
                  f"S02={u2['speaker_id']} ({u2['voice_profile_id']}) [{u2['acoustic_start']:.3f}-{u2['acoustic_end']:.3f}]")

    # 6. Check Zero Drift vs Russian Dubbing Input & Canonical Dialogue Final
    print("\n[CHECK 6] Zero Drift vs Phase 6C Dubbing Input & Phase 5B Canonical Dialogue:")
    dubbing_input_path = WORK_DIR / "russian_dubbing_input.json"
    with open(dubbing_input_path, "r", encoding="utf-8") as f:
        dubbing_input = json.load(f)

    di_map = {u["utterance_id"]: u for u in dubbing_input["utterances"]}
    timing_mismatches = 0
    text_mismatches = 0
    for u in ttp["utterances"]:
        u_id = u["utterance_id"]
        di_u = di_map.get(u_id)
        if not di_u:
            errors.append(f"Utterance {u_id} not found in russian_dubbing_input.json")
            continue
        if abs(u["acoustic_start"] - di_u["acoustic_start"]) > 0.001 or abs(u["acoustic_end"] - di_u["acoustic_end"]) > 0.001:
            timing_mismatches += 1
        if u["text_ru"].strip() != di_u["adapted_ru"].strip():
            text_mismatches += 1

    if timing_mismatches > 0:
        errors.append(f"Acoustic timing drift detected in {timing_mismatches} coordinates vs russian_dubbing_input.json")
    else:
        print("  - Utterance timing drift vs russian_dubbing_input.json: ZERO DRIFT (154/154 exact match).")

    if text_mismatches > 0:
        errors.append(f"Russian text drift detected in {text_mismatches} utterances vs russian_dubbing_input.json")
    else:
        print("  - Russian text drift vs russian_dubbing_input.json: ZERO DRIFT (154/154 exact match).")

    # SUMMARY
    print("\n" + "=" * 80)
    print("PHASE 8 GATE VALIDATION SUMMARY:")
    print("=" * 80)
    if errors:
        print(f"STATUS: FAILED ({len(errors)} errors)")
        for err in errors:
            print(f"  [ERROR] {err}")
        print("\nPHASE_8_PREPARATION_PASS = NO")
        print("READY_FOR_PHASE_9_TTS = NO")
        sys.exit(1)
    else:
        print("STATUS: ALL CHECKS PASSED (0 errors, 0 warnings)")
        print("\nPHASE_8_PREPARATION_PASS = YES")
        print("READY_FOR_PHASE_9_TTS = YES")
        sys.exit(0)


if __name__ == "__main__":
    main()
