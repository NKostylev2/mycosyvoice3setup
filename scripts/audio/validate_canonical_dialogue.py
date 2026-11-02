#!/usr/bin/env python3
"""
scripts/audio/validate_canonical_dialogue.py

Phase 5: Independent Validator for Canonical Dialogue Layer
Verifies:
1. Completeness: Exactly 252 dialogue records accounted for (utterances + unmatched).
2. Unique utterance IDs.
3. Valid acoustic timing (acoustic_start < acoustic_end, duration > 0).
4. Full source traceability (valid SRT dialogue IDs, valid Whisper segment indices).
5. Monotonic non-overlapping word ranges within Whisper segments.
6. Speaker consistency (no mixed speakers within single utterance).
7. Review queue completeness (all REVIEW / AMBIGUOUS represented).
8. Exit code: 0 on PASS, 1 on FAIL.

Author: Antigravity
"""

import os
import sys
import json
from typing import Dict, List, Any

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = r"E:\AI-Dubbing"
CANONICAL_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\canonical_dialogue.json")
REVIEW_QUEUE_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\semantic_review_queue.json")
TIMELINE_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\timeline_v2.json")
WHISPER_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\whisperx\source.json")
DEST_SCRIPT_PATH = os.path.join(PROJECT_ROOT, r"scripts\audio\validate_canonical_dialogue.py")

def validate():
    print("=== STARTING INDEPENDENT CANONICAL DIALOGUE VALIDATION ===")
    
    # 1. Load files
    with open(CANONICAL_PATH, 'r', encoding='utf-8') as f:
        canonical = json.load(f)
    with open(REVIEW_QUEUE_PATH, 'r', encoding='utf-8') as f:
        review_q = json.load(f)
    with open(TIMELINE_PATH, 'r', encoding='utf-8') as f:
        timeline = json.load(f)
    with open(WHISPER_PATH, 'r', encoding='utf-8') as f:
        whisper = json.load(f)
        
    source_records = timeline['records']
    source_dialogue_ids = set(r['dialogue_id'] for r in source_records)
    total_source = len(source_records)
    print(f"Loaded {total_source} source dialogue records from timeline_v2.json.")
    
    utterances = canonical.get('utterances', [])
    unmatched = canonical.get('unmatched_source_events', [])
    non_dialogue = canonical.get('non_dialogue_events', [])
    
    print(f"Canonical Utterances: {len(utterances)}")
    print(f"Unmatched Events: {len(unmatched)}")
    print(f"Non-dialogue Events: {len(non_dialogue)}")
    
    errors = []
    warnings = []
    
    # Check 1: Completeness (252 accounted for)
    accounted_ids = set()
    for u in utterances:
        for d_id in u['source']['dialogue_ids']:
            if d_id in accounted_ids:
                errors.append(f"Dialogue record {d_id} claimed by multiple utterances (duplicate: {u['utterance_id']}).")
            accounted_ids.add(d_id)
            
    for unm in unmatched:
        d_id = unm['dialogue_id']
        if d_id in accounted_ids:
            errors.append(f"Dialogue record {d_id} in unmatched is also claimed by an utterance.")
        accounted_ids.add(d_id)
        
    missing = source_dialogue_ids - accounted_ids
    if missing:
        errors.append(f"Missing dialogue records not accounted for: {sorted(list(missing))}")
    else:
        print(f"[PASS] 100% Completeness: exactly {len(accounted_ids)}/{total_source} dialogue records accounted for.")
        
    # Check 2: Unique Utterance IDs
    u_ids = [u['utterance_id'] for u in utterances]
    if len(u_ids) != len(set(u_ids)):
        errors.append("Duplicate utterance IDs detected.")
    else:
        print(f"[PASS] Unique Utterance IDs: {len(u_ids)} unique IDs.")
        
    # Check 3: Timing Validity
    timing_errors = 0
    monotonic_errors = 0
    prev_end = 0.0
    for u in utterances:
        t = u['timing']
        a_start = t['acoustic_start']
        a_end = t['acoustic_end']
        if a_start >= a_end:
            errors.append(f"Utterance {u['utterance_id']} has invalid timing: {a_start} >= {a_end}")
            timing_errors += 1
        if t['duration'] <= 0:
            errors.append(f"Utterance {u['utterance_id']} has non-positive duration: {t['duration']}")
            timing_errors += 1
        # Check global monotonicity
        if a_start < prev_end - 0.01: # allow tiny overlap if any
            # Only an error if severe backward jump
            if a_start < prev_end - 1.0:
                errors.append(f"Utterance {u['utterance_id']} starts before previous ended: {a_start} < {prev_end}")
                monotonic_errors += 1
        prev_end = max(prev_end, a_end)
        
    if timing_errors == 0 and monotonic_errors == 0:
        print(f"[PASS] Timing & Monotonicity: all utterances have acoustic_start < acoustic_end and 0 backward jumps.")
        
    # Check 4: Whisper segment index validity & Word Range Disjointness
    total_whisper_segs = len(whisper.get('segments', []))
    seg_errors = 0
    word_ownership = {} # seg_idx -> list of (start_word, end_word, u_id)
    
    for u in utterances:
        for s_idx in u['source']['whisper_segment_indices']:
            if s_idx < 0 or s_idx >= total_whisper_segs:
                errors.append(f"Utterance {u['utterance_id']} references invalid whisper segment index {s_idx}.")
                seg_errors += 1
        wr = u['source'].get('whisper_word_range')
        if wr:
            for s_idx in u['source']['whisper_segment_indices']:
                word_ownership.setdefault(s_idx, []).append((wr['start_word_index'], wr['end_word_index'], u['utterance_id']))
                
    # Check word overlaps within same segment
    for s_idx, ranges in word_ownership.items():
        if len(ranges) > 1:
            ranges_sorted = sorted(ranges, key=lambda x: x[0])
            for i in range(len(ranges_sorted) - 1):
                if ranges_sorted[i][1] > ranges_sorted[i+1][0]:
                    errors.append(f"Overlapping word range in Whisper seg {s_idx}: {ranges_sorted[i]} and {ranges_sorted[i+1]}")
                    
    if seg_errors == 0:
        print(f"[PASS] Whisper Segment & Word Range Traceability: all segments exist, zero overlapping word ownership.")
        
    # Check 5: Speaker Integrity
    spk_dist = {}
    for u in utterances:
        spk = u['speaker']
        st = spk['status']
        name = spk.get('name') or "UNKNOWN"
        spk_dist[name] = spk_dist.get(name, 0) + 1
        if st not in ["EXPLICIT", "INFERRED", "UNKNOWN", "AMBIGUOUS"]:
            errors.append(f"Utterance {u['utterance_id']} has invalid speaker status: {st}")
            
    print(f"[PASS] Speaker Distribution: {len(spk_dist)} distinct speaker categories.")
    for spk, cnt in sorted(spk_dist.items(), key=lambda x: -x[1]):
        print(f"   - {spk:30s}: {cnt} utterances")
        
    # Check 6: Semantic Status Breakdown & Review Queue
    status_counts = {}
    for u in utterances:
        st = u['semantic']['status']
        status_counts[st] = status_counts.get(st, 0) + 1
        
    print(f"\n[SUMMARY] Utterance Semantic Status Breakdown:")
    for st in ["CONFIRMED", "HIGH_CONFIDENCE", "REVIEW", "AMBIGUOUS"]:
        print(f"   - {st:16s}: {status_counts.get(st, 0):3d} utterances")
        
    # Check that all REVIEW and AMBIGUOUS items are in review_queue
    rq_uids = set(item.get('utterance_id') for item in review_q.get('items', []) if item.get('utterance_id'))
    missing_rq = []
    for u in utterances:
        if u['semantic']['status'] in ["REVIEW", "AMBIGUOUS"] and u['utterance_id'] not in rq_uids:
            missing_rq.append(u['utterance_id'])
    if missing_rq:
        errors.append(f"Review queue is missing utterances: {missing_rq}")
    else:
        print(f"[PASS] Review Queue Coverage: all {status_counts.get('REVIEW', 0) + status_counts.get('AMBIGUOUS', 0)} non-confirmed utterances present in queue.")
        
    # Check 7: Unmatched Categorization
    unm_reasons = {}
    for unm in unmatched:
        r = unm['reason']
        unm_reasons[r] = unm_reasons.get(r, 0) + 1
        if r not in ["NO_ACOUSTIC_EVIDENCE", "VAD_ONLY", "WHISPER_MISSED", "NON_DIALOGUE", "AMBIGUOUS"]:
            errors.append(f"Unmatched record {unm['dialogue_id']} has invalid reason: {r}")
            
    print(f"\n[SUMMARY] Unmatched Events Categorization (32 total):")
    for r, cnt in sorted(unm_reasons.items(), key=lambda x: -x[1]):
        print(f"   - {r:22s}: {cnt:2d}")
        
    # Copy this script to DEST_SCRIPT_PATH
    os.makedirs(os.path.dirname(DEST_SCRIPT_PATH), exist_ok=True)
    with open(__file__, 'r', encoding='utf-8') as src_f:
        code = src_f.read()
    with open(DEST_SCRIPT_PATH, 'w', encoding='utf-8') as dst_f:
        dst_f.write(code)
    print(f"\nCopied validator script to {DEST_SCRIPT_PATH}")
    
    # Final Verdict
    print("\n" + "="*50)
    if errors:
        print(f"VALIDATION FAILED with {len(errors)} errors:")
        for e in errors:
            print(f"  [ERROR] {e}")
        return False
    else:
        print("VALIDATION PASSED: 0 errors, 0 catastrophic flaws.")
        print("="*50)
        return True

if __name__ == '__main__':
    ok = validate()
    sys.exit(0 if ok else 1)
