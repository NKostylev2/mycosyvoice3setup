"""
Voice Profile Reference Audio Extraction and Normalization Pipeline
Martin Mystery S01E01 - Phase 8: TTS Preparation & Voice Profile Implementation
Architectural Rule: Python performs deterministic extraction, normalization, and hashing.
"""

import json
import hashlib
from pathlib import Path
import numpy as np
import soundfile as sf
import scipy.signal

ROOT_DIR = Path(r"E:\AI-Dubbing")
WORK_DIR = ROOT_DIR / "work" / "S01E01"
AUDIO_PATH = WORK_DIR / "audio" / "english.wav"
TTS_PREP_PATH = WORK_DIR / "tts_preparation.json"
VP_BASE_DIR = WORK_DIR / "voice_profiles"

TARGET_SR = 24000
TARGET_PEAK_DB = -1.0
TARGET_PEAK_AMP = 10 ** (TARGET_PEAK_DB / 20.0)  # ~0.89125


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_audio_stats(audio: np.ndarray, sr: int):
    duration = len(audio) / sr
    peak = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0
    rms = float(np.sqrt(np.mean(audio ** 2))) if len(audio) > 0 else 0.0
    rms_db = float(20 * np.log10(rms)) if rms > 1e-9 else -100.0
    peak_db = float(20 * np.log10(peak)) if peak > 1e-9 else -100.0
    return {
        "duration_seconds": round(duration, 4),
        "sample_rate": sr,
        "channels": 1,
        "peak_amplitude": round(peak, 5),
        "peak_db": round(peak_db, 2),
        "rms_db": round(rms_db, 2),
    }


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    # DC offset removal
    audio = audio - np.mean(audio)
    peak = np.max(np.abs(audio))
    if peak > 1e-6:
        audio = audio * (TARGET_PEAK_AMP / peak)
    return audio.astype(np.float32)


def resample_to_target(audio: np.ndarray, orig_sr: int, target_sr: int = TARGET_SR) -> np.ndarray:
    if orig_sr == target_sr:
        return audio
    # resample using gcd rational fractions
    gcd = np.gcd(orig_sr, target_sr)
    up = target_sr // gcd
    down = orig_sr // gcd
    resampled = scipy.signal.resample_poly(audio, up, down)
    return resampled.astype(np.float32)


# Candidates configuration per profile
PROFILE_CANDIDATE_CONFIG = {
    "vp_martin_mystery": {
        "character_id": "martin_mystery",
        "canonical_name": "Martin Mystery",
        "profile_type": "MAIN_CHARACTER",
        "gender": "male",
        "age": "16",
        "primary_selection": "candidate_01",
        "candidates": [
            {"unit_id": "U0051-S01", "role": "Investigator exposition", "candidate_id": "candidate_01"},
            {"unit_id": "U0010-S01", "role": "Playful banter with Diana", "candidate_id": "candidate_02"},
            {"unit_id": "U0063-S01", "role": "Analytical questioning", "candidate_id": "candidate_03"},
            {"unit_id": "U0031-S01", "role": "Classic intro declaration", "candidate_id": "candidate_04"},
        ],
    },
    "vp_diana_lombard": {
        "character_id": "diana_lombard",
        "canonical_name": "Diana Lombard",
        "profile_type": "MAIN_CHARACTER",
        "gender": "female",
        "age": "16",
        "primary_selection": "candidate_01",
        "candidates": [
            {"unit_id": "U0009-S01", "role": "Pragmatic sarcastic challenge", "candidate_id": "candidate_01"},
            {"unit_id": "U0122-S01", "role": "Defiant emotional confrontational", "candidate_id": "candidate_02"},
            {"unit_id": "U0111-S01", "role": "Challenging Martin's deduction", "candidate_id": "candidate_03"},
            {"unit_id": "U0116-S01", "role": "Analytical realization", "candidate_id": "candidate_04"},
        ],
    },
    "vp_billy": {
        "character_id": "billy",
        "canonical_name": "Billy",
        "profile_type": "MAIN_CHARACTER",
        "gender": "male",
        "age": "unknown",
        "primary_selection": "candidate_01",
        "candidates": [
            {"unit_id": "U0028-S01", "role": "Playful urgency / alien banter", "candidate_id": "candidate_01"},
            {"unit_id": "U0016-S01", "role": "Quirky ice cream vendor", "candidate_id": "candidate_02"},
            {"unit_id": "U0015-S01", "role": "Inquisitive offer", "candidate_id": "candidate_03"},
            {"unit_id": "U0014-S01", "role": "Cheerful greeting", "candidate_id": "candidate_04"},
        ],
    },
    "vp_mom": {
        "character_id": "mom",
        "canonical_name": "M.O.M.",
        "profile_type": "MAIN_CHARACTER",
        "gender": "female",
        "age": "adult",
        "primary_selection": "candidate_01",
        "candidates": [
            {"unit_id": "U0021-S01", "role": "Authoritative mission briefing", "candidate_id": "candidate_01"},
            {"unit_id": "U0143-S01", "role": "Composed congratulatory debrief", "candidate_id": "candidate_02"},
            {"unit_id": "U0026-S01", "role": "Stern reprimand", "candidate_id": "candidate_03"},
            {"unit_id": "U0017-S01", "role": "Technical explanation", "candidate_id": "candidate_04"},
        ],
    },
    "vp_librarian": {
        "character_id": "character_librarian",
        "canonical_name": "Librarian / Nelly's Father",
        "profile_type": "SECONDARY_CHARACTER",
        "gender": "male",
        "age": "middle-aged adult",
        "primary_selection": "candidate_01",
        "candidates": [
            {"unit_id": "U0097-S01", "role": "Distressed town skeptic", "candidate_id": "candidate_01"},
            {"unit_id": "U0148-S01", "role": "Grateful civic speech", "candidate_id": "candidate_02"},
            {"unit_id": "U0036-S01", "role": "Worried narrative recount", "candidate_id": "candidate_03"},
            {"unit_id": "U0037-S01", "role": "Despairing recollection", "candidate_id": "candidate_04"},
        ],
    },
    "vp_nelly": {
        "character_id": "character_nelly",
        "canonical_name": "Nelly",
        "profile_type": "SECONDARY_CHARACTER",
        "gender": "female",
        "age": "young girl",
        "primary_selection": "candidate_01",
        "candidates": [
            {"unit_id": "U0123-S01", "role": "Indignant precocious declaration", "candidate_id": "candidate_01"},
            {"unit_id": "U0150-S01", "role": "Affectionate goodbye to Martin", "candidate_id": "candidate_02"},
        ],
    },
    "vp_ians_mother": {
        "character_id": "character_ians_mother",
        "canonical_name": "Ian's Mother",
        "profile_type": "MINOR_CHARACTER",
        "gender": "female",
        "age": "adult",
        "primary_selection": "concatenated",
        "candidates": [
            {"unit_id": "U0056-S01", "role": "Frantic distress over missing son", "candidate_id": "candidate_01"},
            {"unit_id": "U0057-S01", "role": "Panicked accusation against monster", "candidate_id": "candidate_02"},
        ],
    },
    "vp_townsperson": {
        "character_id": "character_townsperson",
        "canonical_name": "Townsperson",
        "profile_type": "MINOR_CHARACTER",
        "gender": "male",
        "age": "adult",
        "primary_selection": "candidate_01",
        "candidates": [
            {"unit_id": "U0098-S01", "role": "Skeptical questioning of Martin", "candidate_id": "candidate_01"},
            {"unit_id": "U0058-S01", "role": "Terrified exclamation", "candidate_id": "candidate_02"},
        ],
    },
    "vp_java": {
        "character_id": "java",
        "canonical_name": "Java",
        "profile_type": "MAIN_CHARACTER",
        "gender": "male",
        "age": "200,000 years",
        "primary_selection": "concatenated",
        "candidates": [
            {"unit_id": "U0069-S01", "role": "Guttural laconic response ('Not cold.')", "candidate_id": "candidate_01"},
            {"unit_id": "U0142-S01", "role": "Contented caveman remark ('Massage.')", "candidate_id": "candidate_02"},
        ],
    },
    "vp_monster_bogeyman": {
        "character_id": "monster_bogeyman",
        "canonical_name": "Bogeyman",
        "profile_type": "CREATURE",
        "gender": "male / creature",
        "age": "ancient",
        "primary_selection": "candidate_01",
        "candidates": [
            {"unit_id": "U0133-S01", "role": "Sinister raspy creature utterance", "candidate_id": "candidate_01"},
        ],
    },
}


def main():
    print("=" * 70)
    print("Phase 8: Voice Profile Audio Extraction and Normalization Pipeline")
    print("=" * 70)

    # 1. Load tts_preparation.json
    with open(TTS_PREP_PATH, "r", encoding="utf-8") as f:
        tts_prep_data = json.load(f)

    tts_units_by_id = {u["unit_id"]: u for u in tts_prep_data["tts_units"]}

    # 2. Load audio track
    print(f"Loading full source audio: {AUDIO_PATH}")
    full_audio, orig_sr = sf.read(AUDIO_PATH)
    if full_audio.ndim > 1:
        full_audio = np.mean(full_audio, axis=1)
    print(f"Loaded audio: {len(full_audio)} samples, {orig_sr} Hz ({len(full_audio)/orig_sr:.2f} s)")

    profiles_manifest = {
        "episode_id": "S01E01",
        "phase": "8",
        "status": "EXTRACTED_AND_NORMALIZED",
        "target_sample_rate": TARGET_SR,
        "target_format": "WAV 24kHz Mono 16-bit PCM",
        "profiles_count": len(PROFILE_CANDIDATE_CONFIG),
        "profiles": {},
    }

    voice_profiles_catalog = {}

    for vp_id, conf in PROFILE_CANDIDATE_CONFIG.items():
        print(f"\nProcessing Voice Profile: {vp_id} ({conf['canonical_name']})")
        vp_dir = VP_BASE_DIR / vp_id
        cand_dir = vp_dir / "candidates"
        sel_dir = vp_dir / "selected"
        cand_dir.mkdir(parents=True, exist_ok=True)
        sel_dir.mkdir(parents=True, exist_ok=True)

        extracted_candidates = []
        candidate_audio_map = {}

        for cand_info in conf["candidates"]:
            u_id = cand_info["unit_id"]
            c_id = cand_info["candidate_id"]
            unit = tts_units_by_id[u_id]

            start_s = unit["acoustic_start"]
            end_s = unit["acoustic_end"]
            start_samp = int(start_s * orig_sr)
            end_samp = int(end_s * orig_sr)

            # Extract slice
            clip = full_audio[start_samp:end_samp]
            # Resample to 24000 Hz
            clip_resampled = resample_to_target(clip, orig_sr, TARGET_SR)
            # Normalize
            clip_norm = normalize_audio(clip_resampled)

            # Save candidate
            cand_filename = f"{c_id}_{u_id.replace('-', '_')}.wav"
            cand_filepath = cand_dir / cand_filename
            sf.write(cand_filepath, clip_norm, TARGET_SR, subtype="PCM_16")

            cand_stats = compute_audio_stats(clip_norm, TARGET_SR)
            cand_hash = compute_sha256(cand_filepath)

            cand_entry = {
                "candidate_id": c_id,
                "unit_id": u_id,
                "file_name": cand_filename,
                "relative_path": f"voice_profiles/{vp_id}/candidates/{cand_filename}",
                "role": cand_info["role"],
                "source_en": unit["source_en"],
                "acoustic_start": start_s,
                "acoustic_end": end_s,
                "duration_seconds": cand_stats["duration_seconds"],
                "sample_rate": TARGET_SR,
                "channels": 1,
                "peak_amplitude": cand_stats["peak_amplitude"],
                "peak_db": cand_stats["peak_db"],
                "rms_db": cand_stats["rms_db"],
                "sha256": cand_hash,
            }
            extracted_candidates.append(cand_entry)
            candidate_audio_map[c_id] = clip_norm
            print(f"  Extracted {c_id} ({u_id}): {cand_stats['duration_seconds']}s, peak {cand_stats['peak_db']} dBFS, RMS {cand_stats['rms_db']} dBFS")

        # Create Selected Reference
        sel_mode = conf["primary_selection"]
        sel_filename = "reference.wav"
        sel_filepath = sel_dir / sel_filename

        if sel_mode == "concatenated":
            # Concatenate with 0.3s silence
            silence = np.zeros(int(0.3 * TARGET_SR), dtype=np.float32)
            parts = []
            for i, cand in enumerate(conf["candidates"]):
                if i > 0:
                    parts.append(silence)
                parts.append(candidate_audio_map[cand["candidate_id"]])
            combined_audio = np.concatenate(parts)
            combined_audio = normalize_audio(combined_audio)
            sf.write(sel_filepath, combined_audio, TARGET_SR, subtype="PCM_16")
            sel_stats = compute_audio_stats(combined_audio, TARGET_SR)
            sel_desc = f"Concatenated multi-span reference ({' + '.join(c['unit_id'] for c in conf['candidates'])})"
        else:
            primary_cand_audio = candidate_audio_map[sel_mode]
            sf.write(sel_filepath, primary_cand_audio, TARGET_SR, subtype="PCM_16")
            sel_stats = compute_audio_stats(primary_cand_audio, TARGET_SR)
            sel_desc = f"Single span reference ({conf['candidates'][0]['unit_id']}: {conf['candidates'][0]['role']})"

        sel_hash = compute_sha256(sel_filepath)

        selected_entry = {
            "file_name": sel_filename,
            "relative_path": f"voice_profiles/{vp_id}/selected/{sel_filename}",
            "selection_strategy": sel_mode,
            "description": sel_desc,
            "duration_seconds": sel_stats["duration_seconds"],
            "sample_rate": TARGET_SR,
            "channels": 1,
            "peak_amplitude": sel_stats["peak_amplitude"],
            "peak_db": sel_stats["peak_db"],
            "rms_db": sel_stats["rms_db"],
            "sha256": sel_hash,
        }
        print(f"  --> Selected reference created: {sel_stats['duration_seconds']}s, SHA-256: {sel_hash[:12]}...")

        # Build Per-Profile Manifest
        profile_manifest = {
            "voice_profile_id": vp_id,
            "character_id": conf["character_id"],
            "canonical_name": conf["canonical_name"],
            "profile_type": conf["profile_type"],
            "gender": conf["gender"],
            "age": conf["age"],
            "status": "READY_FOR_TEST_SYNTHESIS",
            "selected_reference": selected_entry,
            "candidates": extracted_candidates,
            "tts_engine": "XTTS-v2",
            "conditioning_mode": "speaker_wav",
            "notes": "Creature raspy profile; documented limitations" if conf["profile_type"] == "CREATURE" else "Standard character profile",
        }

        profile_manifest_path = vp_dir / "manifest.json"
        with open(profile_manifest_path, "w", encoding="utf-8") as pf:
            json.dump(profile_manifest, pf, indent=2, ensure_ascii=False)

        profiles_manifest["profiles"][vp_id] = profile_manifest

        # Catalog entry
        voice_profiles_catalog[vp_id] = {
            "voice_profile_id": vp_id,
            "character_id": conf["character_id"],
            "canonical_name": conf["canonical_name"],
            "profile_type": conf["profile_type"],
            "gender": conf["gender"],
            "age": conf["age"],
            "status": "READY_FOR_TEST_SYNTHESIS",
            "reference_audio_path": f"voice_profiles/{vp_id}/selected/{sel_filename}",
            "reference_duration_s": sel_stats["duration_seconds"],
            "reference_sha256": sel_hash,
            "total_candidates": len(extracted_candidates),
        }

    # Save episode-level manifests
    manifest_path = WORK_DIR / "voice_profile_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(profiles_manifest, f, indent=2, ensure_ascii=False)
    print(f"\nSaved episode voice profile manifest: {manifest_path}")

    catalog_path = WORK_DIR / "voice_profiles.json"
    catalog_full = {
        "episode_id": "S01E01",
        "phase": "8",
        "status": "VOICE_PROFILES_IMPLEMENTED",
        "total_profiles": len(voice_profiles_catalog),
        "target_sample_rate": TARGET_SR,
        "profiles": voice_profiles_catalog,
    }
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog_full, f, indent=2, ensure_ascii=False)
    print(f"Saved voice profiles catalog: {catalog_path}")

    # Ensure tests dir exists
    (VP_BASE_DIR / "tests").mkdir(parents=True, exist_ok=True)
    print("\nExtraction & Normalization Complete for all 10 profiles!")


if __name__ == "__main__":
    main()
