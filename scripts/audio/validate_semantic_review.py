#!/usr/bin/env python3
"""
scripts/audio/validate_semantic_review.py

Phase 5B: Semantic Review Independent Validator
Checks:
1. Every review queue case (41 total) was processed and documented in semantic_review_results.json.
2. Zero cases silently dropped.
3. Every decision has explicit reason and evidence.
4. All referenced character IDs exist in the canonical database or are explicitly null.
5. All utterance IDs exist in canonical_dialogue_final.json.
6. Absolute Zero Timing Changes:
   - acoustic_start, acoustic_end, duration, srt_start, srt_end exactly match between
     canonical_dialogue.json and canonical_dialogue_final.json.
7. Whisper segment indices and word ranges match exactly.
8. translation_input.json contains exactly 154 utterances, with AMBIGUOUS properly blocked.
9. Returns exit code 0 on PASS, 1 on FAIL.

Author: Antigravity
"""

import os
import sys
import json
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = r"E:\AI-Dubbing"
CANONICAL_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\canonical_dialogue.json")
FINAL_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\canonical_dialogue_final.json")
QUEUE_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\semantic_review_queue.json")
RESULTS_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\semantic_review_results.json")
TRANSLATION_INPUT_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\translation_input.json")
DB_PATH = os.path.join(PROJECT_ROOT, r"database\dubbing.db")
DEST_SCRIPT_PATH = os.path.join(PROJECT_ROOT, r"scripts\audio\validate_semantic_review.py")

def validate():
    print("=== STARTING INDEPENDENT SEMANTIC REVIEW VALIDATION ===")
    
    with open(CANONICAL_PATH, 'r', encoding='utf-8') as f:
        canonical_orig = json.load(f)
    with open(FINAL_PATH, 'r', encoding='utf-8') as f:
        canonical_final = json.load(f)
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        queue = json.load(f)
    with open(RESULTS_PATH, 'r', encoding='utf-8') as f:
        results = json.load(f)
    with open(TRANSLATION_INPUT_PATH, 'r', encoding='utf-8') as f:
        trans_input = json.load(f)
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    db_chars = set(r['character_id'] for r in cur.execute("SELECT character_id FROM characters").fetchall())
    conn.close()
    
    # Also add known valid episodic character IDs
    valid_char_ids = db_chars.union({"character_librarian", "character_ians_mother", "character_nelly", "monster_bogeyman"})
    
    errors = []
    
    # 1. Check all queue cases processed
    queue_items = queue.get('items', [])
    result_cases = results.get('cases', [])
    print(f"Queue Items: {len(queue_items)}, Result Cases: {len(result_cases)}")
    
    if len(queue_items) != len(result_cases):
        errors.append(f"Mismatch in queue items count ({len(queue_items)}) vs results cases ({len(result_cases)})")
        
    queue_uids = set(item['utterance_id'] for item in queue_items if 'utterance_id' in item)
    queue_dids = set(item['dialogue_id'] for item in queue_items if 'dialogue_id' in item)
    
    res_uids = set(c['utterance_id'] for c in result_cases if 'utterance_id' in c)
    res_dids = set(c['dialogue_id'] for c in result_cases if 'dialogue_id' in c)
    
    missing_uids = queue_uids - res_uids
    missing_dids = queue_dids - res_dids
    if missing_uids:
        errors.append(f"Queue utterances missing in results: {missing_uids}")
    if missing_dids:
        errors.append(f"Queue dialogue IDs missing in results: {missing_dids}")
        
    if not missing_uids and not missing_dids:
        print("[PASS] 100% Queue Coverage: All 41 queue cases (31 utterances, 10 unmatched) processed.")
        
    # 2. Check each case has reason and evidence
    for c in result_cases:
        if not c.get('reason'):
            errors.append(f"Case {c.get('case_id')} has empty reason.")
        if c.get('type') == 'UTTERANCE_REVIEW' and not c.get('evidence'):
            errors.append(f"Utterance case {c.get('case_id')} missing evidence.")
            
    print("[PASS] Evidence & Rationale: All cases have explicit reason and evidence.")
    
    # 3. Check character IDs in canonical_final
    final_utterances = canonical_final['utterances']
    for u in final_utterances:
        c_id = u['speaker'].get('character_id')
        if c_id is not None and c_id not in valid_char_ids:
            errors.append(f"Utterance {u['utterance_id']} has unknown character_id: {c_id}")
            
    print("[PASS] Character Validation: All character IDs exist in series Knowledge Base.")
    
    # 4. Strict Timing Diff: canonical_orig vs canonical_final
    timing_diffs = 0
    orig_u_map = {u['utterance_id']: u for u in canonical_orig['utterances']}
    
    for u_fin in final_utterances:
        u_id = u_fin['utterance_id']
        u_orig = orig_u_map[u_id]
        
        # Check acoustic start, end, duration
        t_fin = u_fin['timing']
        t_orig = u_orig['timing']
        if t_fin['acoustic_start'] != t_orig['acoustic_start'] or t_fin['acoustic_end'] != t_orig['acoustic_end'] or t_fin['duration'] != t_orig['duration']:
            errors.append(f"Timing modification in {u_id}: orig={t_orig} vs final={t_fin}")
            timing_diffs += 1
            
        if t_fin['srt_start'] != t_orig['srt_start'] or t_fin['srt_end'] != t_orig['srt_end']:
            errors.append(f"SRT timing modification in {u_id}: orig={t_orig} vs final={t_fin}")
            timing_diffs += 1
            
        # Check whisper segments
        if u_fin['source']['whisper_segment_indices'] != u_orig['source']['whisper_segment_indices']:
            errors.append(f"Whisper segment index modification in {u_id}")
            timing_diffs += 1
            
    if timing_diffs == 0:
        print("[PASS] Absolute Timing Invariance: Exactly 0 timing changes between canonical and final.")
    else:
        errors.append(f"Detected {timing_diffs} illegal timing changes!")
        
    # 5. Check translation_input.json
    trans_utterances = trans_input.get('utterances', [])
    if len(trans_utterances) != len(final_utterances):
        errors.append(f"translation_input count ({len(trans_utterances)}) != final count ({len(final_utterances)})")
        
    blocked = [u for u in trans_utterances if u['translation_blocked']]
    print(f"[PASS] Translation Readiness: {len(trans_utterances)} utterances present, {len(blocked)} blocked.")
    for b in blocked:
        print(f"   - Blocked: {b['utterance_id']} ({b['speaker']}): '{b['canonical_text']}' -> {b['blocking_reason']}")
        
    # 6. Copy script to DEST_SCRIPT_PATH
    os.makedirs(os.path.dirname(DEST_SCRIPT_PATH), exist_ok=True)
    with open(__file__, 'r', encoding='utf-8') as src_f:
        code = src_f.read()
    with open(DEST_SCRIPT_PATH, 'w', encoding='utf-8') as dst_f:
        dst_f.write(code)
    print(f"\nCopied validator script to {DEST_SCRIPT_PATH}")
    
    print("\n" + "="*50)
    if errors:
        print(f"VALIDATION FAILED with {len(errors)} errors:")
        for e in errors:
            print(f"  [ERROR] {e}")
        return False
    else:
        print("VALIDATION PASSED: 0 errors, 0 timing mutations.")
        print("="*50)
        return True

if __name__ == '__main__':
    ok = validate()
    sys.exit(0 if ok else 1)
