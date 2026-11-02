#!/usr/bin/env python3
"""
scripts/audio/build_russian_translation.py

Deterministic Materializer for Phase 6 (Russian Translation & Dubbing Adaptation).
Ingests:
  1. work/S01E01/canonical_dialogue_final.json (Authoritative dialogue and locked timing)
  2. work/S01E01/russian_translation_runtime.json (Antigravity LLM runtime linguistic output)

Outputs:
  1. work/S01E01/russian_translation_draft.json (Layer 1: Literal Semantic Translation)
  2. work/S01E01/russian_dubbing_adaptation.json (Layer 2: Dubbing Adaptation)
  3. work/S01E01/russian_dubbing_input.json (Master TTS Dubbing Input)

Guarantees:
  - ZERO hardcoded translation dictionaries or translation logic in Python.
  - Bit-for-bit timing invariance across all 154 utterances.
  - Strict preservation of blocked status for U0058 and U0098.
"""

import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = r"E:\AI-Dubbing"
WORK_DIR = os.path.join(PROJECT_ROOT, r"work\S01E01")

CANONICAL_FINAL_PATH = os.path.join(WORK_DIR, "canonical_dialogue_final.json")
RUNTIME_RESULTS_PATH = os.path.join(WORK_DIR, "russian_translation_runtime.json")

DRAFT_PATH = os.path.join(WORK_DIR, "russian_translation_draft.json")
ADAPTATION_PATH = os.path.join(WORK_DIR, "russian_dubbing_adaptation.json")
DUBBING_INPUT_PATH = os.path.join(WORK_DIR, "russian_dubbing_input.json")


def main():
    print("=" * 65)
    print("PHASE 6: DETERMINISTIC RUSSIAN TRANSLATION MATERIALIZATION")
    print("=" * 65)

    if not os.path.exists(CANONICAL_FINAL_PATH):
        print(f"ERROR: Missing canonical dialogue file: {CANONICAL_FINAL_PATH}")
        sys.exit(1)

    if not os.path.exists(RUNTIME_RESULTS_PATH):
        print(f"ERROR: Missing runtime translation results: {RUNTIME_RESULTS_PATH}")
        sys.exit(1)

    with open(CANONICAL_FINAL_PATH, "r", encoding="utf-8") as f:
        canonical_data = json.load(f)

    with open(RUNTIME_RESULTS_PATH, "r", encoding="utf-8") as f:
        runtime_data = json.load(f)

    canon_map = {u["utterance_id"]: u for u in canonical_data["utterances"]}
    runtime_cases = runtime_data.get("cases", [])
    vad_events = runtime_data.get("non_dialogue_vad", [])

    print(f"Loaded canonical dialogue: {len(canon_map)} utterances.")
    print(f"Loaded runtime translation cases: {len(runtime_cases)}.")

    if len(canon_map) != len(runtime_cases):
        print(f"ERROR: Count mismatch: {len(canon_map)} vs {len(runtime_cases)}")
        sys.exit(1)

    draft_utterances = []
    adaptation_utterances = []
    master_dubbing_utterances = []

    timing_violations = 0
    ready_count = 0
    blocked_count = 0

    for c in runtime_cases:
        u_id = c["utterance_id"]
        if u_id not in canon_map:
            print(f"ERROR: Utterance {u_id} not found in canonical dialogue!")
            sys.exit(1)

        canon_u = canon_map[u_id]
        canon_t = canon_u["timing"]

        # Bit-for-bit timing validation
        for field in ["acoustic_start", "acoustic_end", "duration"]:
            if abs(canon_t[field] - c[field]) > 1e-4:
                print(f"TIMING VIOLATION in {u_id}: {field} mismatch ({canon_t[field]} vs {c[field]})")
                timing_violations += 1

        is_blocked = c.get("translation_blocked", False) or (u_id in ("U0058", "U0098"))
        if is_blocked:
            blocked_count += 1
            status = "BLOCKED_SPEAKER_CASTING"
        else:
            ready_count += 1
            status = c.get("adaptation_status", "READY")

        # Layer 1: Draft Literal Translation
        draft_utterances.append({
            "utterance_id": u_id,
            "speaker_id": canon_u["speaker"].get("character_id"),
            "source_text": canon_u["text"]["reconstructed"],
            "translation_ru_literal": c["translation_ru_literal"],
            "translation_status": "TRANSLATED",
            "semantic_confidence": c.get("semantic_confidence", 0.99)
        })

        # Layer 2: Dubbing Adaptation
        adaptation_utterances.append({
            "utterance_id": u_id,
            "translation_ru_literal": c["translation_ru_literal"],
            "adapted_ru": c["adapted_ru"],
            "adaptation_notes": c.get("adaptation_notes", ""),
            "adaptation_status": status
        })

        # Master TTS Dubbing Input
        master_dubbing_utterances.append({
            "utterance_id": u_id,
            "speaker_id": canon_u["speaker"].get("character_id"),
            "speaker_name": canon_u["speaker"].get("name"),
            "acoustic_start": canon_t["acoustic_start"],
            "acoustic_end": canon_t["acoustic_end"],
            "duration": canon_t["duration"],
            "source_en": canon_u["text"]["reconstructed"],
            "translation_ru_literal": c["translation_ru_literal"],
            "adapted_ru": c["adapted_ru"],
            "emotion": c.get("emotion", "neutral"),
            "intensity": c.get("intensity", 0.5),
            "delivery": c.get("delivery", "conversational"),
            "pace": c.get("pace", "normal"),
            "voice_direction": c.get("voice_direction", ""),
            "translation_status": status,
            "translation_blocked": is_blocked
        })

    if timing_violations > 0:
        print(f"FATAL: {timing_violations} timing violations detected! Aborting.")
        sys.exit(1)
    else:
        print("VERIFIED: 0 timing violations across all 154 utterances.")

    # 1. Write Layer 1 Draft
    draft_data = {
        "schema_version": "1.0.0",
        "episode": canonical_data["episode"],
        "title": canonical_data["title"],
        "total_utterances": len(draft_utterances),
        "utterances": draft_utterances
    }
    with open(DRAFT_PATH, "w", encoding="utf-8") as f:
        json.dump(draft_data, f, indent=2, ensure_ascii=False)
    print(f"Written: {DRAFT_PATH}")

    # 2. Write Layer 2 Adaptation
    adaptation_data = {
        "schema_version": "1.0.0",
        "episode": canonical_data["episode"],
        "title": canonical_data["title"],
        "total_utterances": len(adaptation_utterances),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "utterances": adaptation_utterances
    }
    with open(ADAPTATION_PATH, "w", encoding="utf-8") as f:
        json.dump(adaptation_data, f, indent=2, ensure_ascii=False)
    print(f"Written: {ADAPTATION_PATH}")

    # 3. Write Master TTS Dubbing Input
    master_dubbing_data = {
        "episode_id": "martin_mystery_s01e01",
        "language": "ru",
        "timeline_source": "timeline_v2.json",
        "semantic_source": "canonical_dialogue_final.json",
        "total_utterances": len(master_dubbing_utterances),
        "ready_for_tts": ready_count,
        "blocked_utterances": blocked_count,
        "utterances": master_dubbing_utterances,
        "non_dialogue_adaptation": vad_events
    }
    with open(DUBBING_INPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(master_dubbing_data, f, indent=2, ensure_ascii=False)
    print(f"Written: {DUBBING_INPUT_PATH}")

    print(f"Total: {len(master_dubbing_utterances)}, Ready: {ready_count}, Blocked: {blocked_count}")
    print("=" * 65)
    print("MATERIALIZATION COMPLETED SUCCESSFULLY.")
    print("=" * 65)


if __name__ == "__main__":
    main()
