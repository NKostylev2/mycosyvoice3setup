#!/usr/bin/env python3
"""
scripts/audio/validate_translation_semantics.py

Independent Quality & Architecture Validator for Phase 6B:
Bidirectional Semantic Equivalence Audit.

Checks:
  1. Static Code Analysis: Verifies zero hardcoded translation dictionaries or translation APIs in Python scripts.
  2. Full 154/154 Pipeline Invariance:
     - canonical_dialogue_final.json
     - russian_translation_draft.json
     - russian_dubbing_adaptation.json
     - russian_dubbing_input.json
     - russian_bidirectional_semantic_audit.json
  3. Bit-for-bit Acoustic Timing Invariance (0 deviations in start, end, duration).
  4. Speaker Binding & Casting Invariance (100% agreement with canonical speaker IDs).
  5. Translation Blocking Integrity (U0058 and U0098 strictly blocked as BLOCKED_SPEAKER_CASTING).
  6. Bidirectional Equivalence Metrics:
     - 154/154 records evaluated
     - 0 information_added
     - 0 information_lost
     - 0 type_shifts
     - 0 time_place_loss
     - 0 entity_loss
     - modal_shift == False
     - negation_shift == False
     - question_shift == False
     - semantic_equivalence == True
     - status == PASS
  7. Final Gate:
     TOTAL = 154
     PASS = 154
     REVIEW_REQUIRED = 0
     REWRITE_REQUIRED = 0
     PHASE_6B_BIDIRECTIONAL_SEMANTICS = PASS
     READY_FOR_TTS = YES
"""

import os
import sys
import json
import re

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = r"E:\AI-Dubbing"
WORK_DIR = os.path.join(PROJECT_ROOT, r"work\S01E01")
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, r"scripts\audio")

CANONICAL_FINAL_PATH = os.path.join(WORK_DIR, "canonical_dialogue_final.json")
DRAFT_PATH = os.path.join(WORK_DIR, "russian_translation_draft.json")
ADAPTATION_PATH = os.path.join(WORK_DIR, "russian_dubbing_adaptation.json")
DUBBING_INPUT_PATH = os.path.join(WORK_DIR, "russian_dubbing_input.json")
AUDIT_PATH = os.path.join(WORK_DIR, "russian_bidirectional_semantic_audit.json")

ACTIVE_SCRIPTS = [
    os.path.join(SCRIPTS_DIR, "extract_translation_packages.py"),
    os.path.join(SCRIPTS_DIR, "build_russian_translation.py")
]


def check_static_code_purity(script_path):
    violations = []
    if not os.path.exists(script_path):
        return [f"Script not found: {script_path}"]

    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()

    forbidden_patterns = [
        (r'\bTRANSLATION_MAP\s*=', "Hardcoded TRANSLATION_MAP dictionary detected"),
        (r'\bRUSSIAN_TEXTS\s*=', "Hardcoded RUSSIAN_TEXTS dictionary detected"),
        (r'\bADAPTED_TEXTS\s*=', "Hardcoded ADAPTED_TEXTS dictionary detected"),
        (r'["\']U00[0-9]{2}["\']\s*:\s*["\']', "Hardcoded Utterance translation mapping detected"),
        (r'import\s+openai', "Forbidden external API import: openai"),
        (r'import\s+google\.generativeai', "Forbidden external API import: google.generativeai"),
        (r'import\s+googletrans', "Forbidden external API import: googletrans"),
        (r'import\s+deepl', "Forbidden external API import: deepl")
    ]

    for pattern, desc in forbidden_patterns:
        matches = re.findall(pattern, content)
        if matches:
            violations.append(f"{desc} ({len(matches)} match(es)) in {os.path.basename(script_path)}")

    return violations


def main():
    print("=" * 70)
    print("PHASE 6B: BIDIRECTIONAL SEMANTIC EQUIVALENCE VALIDATOR")
    print("=" * 70)

    errors = []

    # 1. Static Code Analysis
    print("\n[CHECK 1] Static Code Analysis (No hardcoded translation maps in Python):")
    for sp in ACTIVE_SCRIPTS:
        v = check_static_code_purity(sp)
        if v:
            for err in v:
                print(f"  ❌ FAIL: {err}")
                errors.append(err)
        else:
            print(f"  ✅ PASS: {os.path.basename(sp)} (Architecture clean)")

    # 2. File Existence & Coverage
    print("\n[CHECK 2] File Existence & Pipeline Integrity:")
    files = [
        (CANONICAL_FINAL_PATH, "canonical_dialogue_final.json"),
        (DRAFT_PATH, "russian_translation_draft.json"),
        (ADAPTATION_PATH, "russian_dubbing_adaptation.json"),
        (DUBBING_INPUT_PATH, "russian_dubbing_input.json"),
        (AUDIT_PATH, "russian_bidirectional_semantic_audit.json")
    ]
    for p, name in files:
        if not os.path.exists(p):
            errors.append(f"Missing expected file: {name}")
            print(f"  ❌ Missing {name}")
        else:
            print(f"  ✅ Found {name}")

    if errors:
        print("Fatal: Missing files. Halting verification.")
        return 1

    with open(CANONICAL_FINAL_PATH, "r", encoding="utf-8") as f:
        canon_data = json.load(f)
    with open(DRAFT_PATH, "r", encoding="utf-8") as f:
        draft_data = json.load(f)
    with open(ADAPTATION_PATH, "r", encoding="utf-8") as f:
        adapt_data = json.load(f)
    with open(DUBBING_INPUT_PATH, "r", encoding="utf-8") as f:
        dubbing_data = json.load(f)
    with open(AUDIT_PATH, "r", encoding="utf-8") as f:
        audit_data = json.load(f)

    c_utts = canon_data.get("utterances", [])
    d_utts = draft_data.get("utterances", [])
    a_utts = adapt_data.get("utterances", [])
    m_utts = dubbing_data.get("utterances", [])
    audit_recs = audit_data.get("audit_records", [])

    counts = [len(c_utts), len(d_utts), len(a_utts), len(m_utts), len(audit_recs)]
    if not all(c == 154 for c in counts):
        errors.append(f"Utterance counts mismatch (expected 154 across all): {counts}")
        print(f"  ❌ Utterance counts mismatch: {counts}")
    else:
        print(f"  ✅ 100% coverage: Exactly 154 utterances in canonical, draft, adaptation, dubbing input, and audit")

    # 3. Acoustic Timing Invariance
    print("\n[CHECK 3] Bit-for-bit Acoustic Timing Invariance:")
    timing_violations = 0
    for cu, mu in zip(c_utts, m_utts):
        ct = cu["timing"]
        for field in ["acoustic_start", "acoustic_end", "duration"]:
            if abs(ct[field] - mu[field]) > 1e-4:
                timing_violations += 1
                print(f"  ❌ Timing deviation in {cu['utterance_id']}: {field} {ct[field]} != {mu[field]}")

    if timing_violations == 0:
        print("  ✅ PASS: 0 timing differences across all 154 utterances")
    else:
        errors.append(f"{timing_violations} timing violations detected")

    # 4. Speaker Binding
    print("\n[CHECK 4] Speaker Binding & Casting Invariance:")
    speaker_violations = 0
    for cu, mu in zip(c_utts, m_utts):
        if cu["speaker"].get("character_id") != mu.get("speaker_id"):
            speaker_violations += 1
            print(f"  ❌ Speaker mismatch in {cu['utterance_id']}")

    if speaker_violations == 0:
        print("  ✅ PASS: 100% speaker binding preserved from canonical dialogue")
    else:
        errors.append(f"{speaker_violations} speaker mismatches detected")

    # 5. Blocked Utterances Audit
    print("\n[CHECK 5] Blocked Utterances Audit (U0058, U0098):")
    blocked_found = [u["utterance_id"] for u in m_utts if u.get("translation_blocked")]
    if set(blocked_found) != {"U0058", "U0098"}:
        errors.append(f"Blocked utterances mismatch: expected {{'U0058', 'U0098'}}, got {set(blocked_found)}")
        print(f"  ❌ Blocked utterances mismatch: {blocked_found}")
    else:
        print("  ✅ PASS: U0058 and U0098 strictly maintained as translation_blocked")

    # 6. Bidirectional Equivalence Audit Records
    print("\n[CHECK 6] Bidirectional Semantic Equivalence Audit Records:")
    pass_count = 0
    review_required_count = 0
    rewrite_required_count = 0
    field_violations = 0

    required_empty_lists = [
        "information_added",
        "information_lost",
        "type_shifts",
        "time_place_loss",
        "entity_loss"
    ]
    required_false_flags = [
        "modal_shift",
        "negation_shift",
        "question_shift"
    ]

    for rec in audit_recs:
        uid = rec.get("utterance_id")
        status = rec.get("status")
        equiv = rec.get("semantic_equivalence")

        if status == "PASS":
            pass_count += 1
        elif status == "REVIEW_REQUIRED":
            review_required_count += 1
        elif status == "REWRITE_REQUIRED":
            rewrite_required_count += 1

        if not equiv:
            field_violations += 1
            print(f"  ❌ {uid}: semantic_equivalence is False")

        for fld in required_empty_lists:
            if rec.get(fld):
                field_violations += 1
                print(f"  ❌ {uid}: {fld} not empty: {rec.get(fld)}")

        for fld in required_false_flags:
            if rec.get(fld) is not False:
                field_violations += 1
                print(f"  ❌ {uid}: {fld} is not False: {rec.get(fld)}")

    print(f"  - Total Audited:    {len(audit_recs)}")
    print(f"  - PASS:             {pass_count}")
    print(f"  - REVIEW_REQUIRED:  {review_required_count}")
    print(f"  - REWRITE_REQUIRED: {rewrite_required_count}")
    print(f"  - Field Violations: {field_violations}")

    if pass_count == 154 and review_required_count == 0 and rewrite_required_count == 0 and field_violations == 0:
        print("  ✅ PASS: All 154 utterances achieve 100% bidirectional semantic equivalence")
    else:
        errors.append(f"Audit status failure: pass={pass_count}, review={review_required_count}, rewrite={rewrite_required_count}, violations={field_violations}")

    # 7. Final Gate
    print("\n" + "=" * 70)
    print("PHASE 6B GATE VERDICTS")
    print("=" * 70)
    print(f"TOTAL = {len(audit_recs)}")
    print(f"PASS = {pass_count}")
    print(f"REVIEW_REQUIRED = {review_required_count}")
    print(f"REWRITE_REQUIRED = {rewrite_required_count}")

    if not errors and pass_count == 154 and review_required_count == 0 and rewrite_required_count == 0:
        print("PHASE_6B_BIDIRECTIONAL_SEMANTICS = PASS")
        print("READY_FOR_TTS = YES")
        print("=" * 70)
        print("SUCCESS: Phase 6B Bidirectional Semantic Equivalence Audit is COMPLETE.")
        return 0
    else:
        print("PHASE_6B_BIDIRECTIONAL_SEMANTICS = FAIL")
        print("READY_FOR_TTS = NO")
        print("=" * 70)
        print(f"FAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
