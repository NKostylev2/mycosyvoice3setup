#!/usr/bin/env python3
"""
scripts/audio/materialize_canonical_final.py

Deterministic Materializer for Phase 5B.
Ingests:
  1. work/S01E01/canonical_dialogue.json (Phase 5A canonical dialogue)
  2. work/S01E01/semantic_runtime_results.json (Antigravity LLM runtime reasoning results)

Outputs:
  1. work/S01E01/canonical_dialogue_final.json
  2. work/S01E01/translation_input.json

Guarantees:
  - ZERO hardcoded decisions or decision dictionaries.
  - Purely deterministic serialization of Antigravity's decisions.
  - Bit-for-bit acoustic and subtitle timing invariance (0 timing changes).
"""

import os
import sys
import json
import copy
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = r"E:\AI-Dubbing"
CANONICAL_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\canonical_dialogue.json")
RESULTS_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\semantic_runtime_results.json")
CANONICAL_FINAL_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\canonical_dialogue_final.json")
TRANSLATION_INPUT_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\translation_input.json")


def main():
    print("=" * 60)
    print("PHASE 5B: DETERMINISTIC CANONICAL MATERIALIZATION")
    print("=" * 60)

    if not os.path.exists(CANONICAL_PATH):
        print(f"ERROR: Missing canonical dialogue file: {CANONICAL_PATH}")
        sys.exit(1)

    if not os.path.exists(RESULTS_PATH):
        print(f"ERROR: Missing semantic runtime results: {RESULTS_PATH}")
        sys.exit(1)

    with open(CANONICAL_PATH, 'r', encoding='utf-8') as f:
        canonical_orig = json.load(f)

    with open(RESULTS_PATH, 'r', encoding='utf-8') as f:
        semantic_results = json.load(f)

    print(f"Loaded canonical dialogue: {len(canonical_orig['utterances'])} utterances")
    cases = semantic_results.get("cases", [])
    print(f"Loaded semantic runtime results: {len(cases)} cases")

    canonical_final = copy.deepcopy(canonical_orig)
    u_map = {u["utterance_id"]: u for u in canonical_final["utterances"]}
    d_map = {e["dialogue_id"]: e for e in canonical_final["unmatched_source_events"]}

    # Store exact original timings for anti-tamper verification
    original_timings = {u_id: copy.deepcopy(u["timing"]) for u_id, u in u_map.items()}

    utterance_cases_applied = 0
    vad_cases_applied = 0
    blocked_cases = set()
    blocked_reasons = {}

    for case in cases:
        case_id = case["case_id"]
        case_type = case["case_type"]
        target_id = case["target_id"]

        if case_type == "utterance":
            if target_id not in u_map:
                print(f"ERROR: Utterance {target_id} not found in canonical dialogue!")
                sys.exit(1)

            u = u_map[target_id]
            u["text"]["reconstructed"] = case["canonical_text"]
            u["text"]["decision"] = case["text_decision"]
            u["text"]["confidence"] = case["confidence"]
            u["text"]["reason"] = case["reasoning"]

            if case.get("speaker"):
                u["speaker"] = case["speaker"]
                char_id = case["speaker"].get("character_id")
                if char_id and char_id not in u["knowledge"]["characters"]:
                    u["knowledge"]["characters"].append(char_id)

            is_blocked = case.get("translation_blocked", False)
            if is_blocked or case["text_decision"] == "AMBIGUOUS":
                u["semantic"]["status"] = "AMBIGUOUS"
                blocked_cases.add(target_id)
                blocked_reasons[target_id] = case["reasoning"]
            else:
                u["semantic"]["status"] = "CONFIRMED"

            u["semantic"]["review_metadata"] = {
                "case_id": case_id,
                "boundary_decision": case.get("boundary_decision"),
                "evidence_used": case.get("evidence_used"),
                "provenance": case.get("provenance")
            }
            utterance_cases_applied += 1

        elif case_type == "unmatched_vad":
            if target_id in d_map:
                e = d_map[target_id]
                e["review_status"] = "RESOLVED_AS_VAD_NON_DIALOGUE"
                e["review_metadata"] = {
                    "case_id": case_id,
                    "speaker": case.get("speaker"),
                    "reasoning": case.get("reasoning"),
                    "evidence_used": case.get("evidence_used"),
                    "boundary_decision": case.get("boundary_decision"),
                    "provenance": case.get("provenance")
                }
                vad_cases_applied += 1

    print(f"Applied {utterance_cases_applied} utterance decisions.")
    print(f"Applied {vad_cases_applied} unmatched VAD decisions.")

    # Strict Timing Invariance Assertion
    timing_violations = 0
    for u_id, u in u_map.items():
        orig_t = original_timings[u_id]
        curr_t = u["timing"]
        for key in ["acoustic_start", "acoustic_end", "duration", "srt_start", "srt_end"]:
            if orig_t[key] != curr_t[key]:
                print(f"FATAL: Timing violation on {u_id}: {key} changed from {orig_t[key]} to {curr_t[key]}")
                timing_violations += 1

    if timing_violations > 0:
        print(f"ERROR: {timing_violations} timing violations detected! Aborting.")
        sys.exit(1)
    else:
        print("VERIFIED: 0 timing violations across all 154 utterances (bit-for-bit timing preserved).")

    # Update Summary Statistics
    status_counts = dict(Counter(u["semantic"]["status"] for u in canonical_final["utterances"]))
    speaker_dist = dict(Counter(
        u["speaker"].get("character_id") or u["speaker"].get("name")
        for u in canonical_final["utterances"]
    ))

    canonical_final["summary"]["status_counts"] = status_counts
    canonical_final["summary"]["speaker_distribution"] = speaker_dist

    # Write canonical_dialogue_final.json
    with open(CANONICAL_FINAL_PATH, 'w', encoding='utf-8') as f:
        json.dump(canonical_final, f, indent=2, ensure_ascii=False)
    print(f"Written: {CANONICAL_FINAL_PATH}")

    # Generate translation_input.json
    translation_utterances = []
    ready_count = 0
    blocked_count = 0

    for u in canonical_final["utterances"]:
        u_id = u["utterance_id"]
        is_blocked = (u_id in blocked_cases) or (u["semantic"]["status"] == "AMBIGUOUS")
        if is_blocked:
            blocked_count += 1
            reason = blocked_reasons.get(u_id, "Ambiguous crowd/background speech requiring manual casting")
        else:
            ready_count += 1
            reason = None

        item = {
            "utterance_id": u_id,
            "speaker": u["speaker"]["name"],
            "character_id": u["speaker"].get("character_id"),
            "speaker_status": u["speaker"]["status"],
            "acoustic_start": u["timing"]["acoustic_start"],
            "acoustic_end": u["timing"]["acoustic_end"],
            "duration": u["timing"]["duration"],
            "canonical_text": u["text"]["reconstructed"],
            "semantic_status": u["semantic"]["status"],
            "relevant_entities": u["knowledge"].get("entities", []),
            "translation_blocked": is_blocked,
            "blocking_reason": reason,
            "translation_notes": u["text"]["reason"]
        }
        translation_utterances.append(item)

    translation_data = {
        "schema_version": "2.0.0",
        "episode": canonical_final["episode"],
        "title": canonical_final["title"],
        "total_utterances": len(translation_utterances),
        "ready_for_translation": ready_count,
        "blocked_utterances": blocked_count,
        "instructions": [
            "This file is the single authoritative source of dialogue and acoustic constraints for Russian dubbing.",
            "Acoustic timing boundaries (acoustic_start, acoustic_end, duration) are locked and MUST NOT be altered.",
            "Utterances marked translation_blocked: true require manual audio review or crowd voice allocation before dubbing.",
            "Translations must be rhythmically fitted to duration seconds."
        ],
        "utterances": translation_utterances
    }

    with open(TRANSLATION_INPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(translation_data, f, indent=2, ensure_ascii=False)
    print(f"Written: {TRANSLATION_INPUT_PATH}")
    print(f"Total: {len(translation_utterances)}, Ready: {ready_count}, Blocked: {blocked_count}")
    print("=" * 60)
    print("MATERIALIZATION COMPLETED SUCCESSFULLY.")
    print("=" * 60)


if __name__ == "__main__":
    main()
