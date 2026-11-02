#!/usr/bin/env python3
"""
scripts/audio/build_semantic_evidence.py

Step A of Phase 5B Re-Architecture:
Deterministic Python script that gathers objective evidence facts for all cases in
work/S01E01/semantic_review_queue.json.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. Python contains ONLY deterministic fact extraction.
2. NO canonical text generation.
3. NO speaker decisions or assignments.
4. NO lore interpretation or corrections.
5. NO case-specific hardcoded overrides.

Author: Antigravity
"""

import os
import sys
import json
import sqlite3
from typing import Dict, List, Any

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = r"E:\AI-Dubbing"
CANONICAL_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\canonical_dialogue.json")
QUEUE_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\semantic_review_queue.json")
TIMELINE_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\timeline_v2.json")
NORMALIZED_SUBS_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\normalized_subtitles_v2.json")
WHISPER_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\whisperx\source.json")
VAD_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\audio\vad.json")
OFFSET_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\offset_report.json")
DB_PATH = os.path.join(PROJECT_ROOT, r"database\dubbing.db")
EPISODE_CONTEXT_PATH = os.path.join(PROJECT_ROOT, r"knowledge\canonical\episode_context\martin_mystery_001.json")

OUTPUT_PACKAGES_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\semantic_evidence_packages.json")
DEST_SCRIPT_PATH = os.path.join(PROJECT_ROOT, r"scripts\audio\build_semantic_evidence.py")

def build_evidence():
    print("=== BUILDING SEMANTIC EVIDENCE PACKAGES (DETERMINISTIC FACT GATHERING) ===")
    
    # 1. Load data
    with open(CANONICAL_PATH, 'r', encoding='utf-8') as f:
        canonical = json.load(f)
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        queue = json.load(f)
    with open(TIMELINE_PATH, 'r', encoding='utf-8') as f:
        timeline = json.load(f)
    with open(NORMALIZED_SUBS_PATH, 'r', encoding='utf-8') as f:
        norm_subs = json.load(f)
    with open(WHISPER_PATH, 'r', encoding='utf-8') as f:
        whisper = json.load(f)
    with open(VAD_PATH, 'r', encoding='utf-8') as f:
        vad = json.load(f)
    with open(OFFSET_PATH, 'r', encoding='utf-8') as f:
        offset_doc = json.load(f)
    with open(EPISODE_CONTEXT_PATH, 'r', encoding='utf-8') as f:
        ep_context = json.load(f)
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    characters = [dict(r) for r in cur.execute("SELECT character_id, name_original, name_ru, description FROM characters").fetchall()]
    entities = [dict(r) for r in cur.execute("SELECT entity_id, entity_type, name_original, name_ru, description FROM entities").fetchall()]
    conn.close()
    
    whisper_segments = whisper.get('segments', [])
    vad_intervals = vad.get('intervals', [])
    timeline_records = {r['dialogue_id']: r for r in timeline['records']}
    subs_entries = {e['index']: e for e in norm_subs.get('entries', [])}
    
    utterances_list = canonical['utterances']
    utterance_map = {u['utterance_id']: u for u in utterances_list}
    utterance_idx_map = {u['utterance_id']: idx for idx, u in enumerate(utterances_list)}
    
    global_offset = offset_doc.get('CONFIRMED_GLOBAL_OFFSET', 12.0280)
    
    queue_items = queue['items']
    print(f"Loaded {len(queue_items)} items from review queue.")
    
    evidence_packages = []
    
    for idx, item in enumerate(queue_items):
        case_id = f"CASE_{idx+1:03d}"
        u_id = item.get('utterance_id')
        
        if u_id:
            # Utterance review case
            u = utterance_map[u_id]
            u_idx = utterance_idx_map[u_id]
            prev_u = utterances_list[u_idx - 1] if u_idx > 0 else None
            next_u = utterances_list[u_idx + 1] if u_idx < len(utterances_list) - 1 else None
            
            d_ids = u['source']['dialogue_ids']
            srt_event_ids = u['source']['srt_event_ids']
            w_indices = u['source']['whisper_segment_indices']
            
            # Extract raw SRT blocks
            srt_blocks = []
            for s_id in srt_event_ids:
                if s_id in subs_entries:
                    se = subs_entries[s_id]
                    srt_blocks.append({
                        "subtitle_index": se['index'],
                        "source_block": se.get('source_block'),
                        "start": se['start'],
                        "end": se['end'],
                        "duration": se['duration'],
                        "raw_text": se['raw_text']
                    })
                    
            # Extract timeline records
            tl_recs = []
            for d_id in d_ids:
                if d_id in timeline_records:
                    tr = timeline_records[d_id]
                    tl_recs.append({
                        "dialogue_id": tr['dialogue_id'],
                        "alignment_status": tr['alignment_status'],
                        "text_score": tr.get('text_score'),
                        "vad_score": tr.get('vad_score'),
                        "time_score": tr.get('time_score'),
                        "candidate_margin": tr.get('candidate_margin'),
                        "notes": tr.get('notes'),
                        "whisper_word_range": tr.get('whisper_word_range')
                    })
                    
            # Extract Whisper segments and words
            w_segs_extracted = []
            for s_idx in w_indices:
                if s_idx < len(whisper_segments):
                    ws = whisper_segments[s_idx]
                    w_segs_extracted.append({
                        "segment_index": s_idx,
                        "start": ws['start'],
                        "end": ws['end'],
                        "text": ws['text'].strip(),
                        "words": ws.get('words', [])
                    })
                    
            # Extract overlapping VAD intervals
            a_start = u['timing']['acoustic_start']
            a_end = u['timing']['acoustic_end']
            overlapping_vad = [v for v in vad_intervals if not (v['end'] < a_start - 0.2 or v['start'] > a_end + 0.2)]
            
            package = {
                "case_id": case_id,
                "case_type": "utterance",
                "utterance_id": u_id,
                "dialogue_ids": d_ids,
                "review_issue_type": item.get('issue_type'),
                "timing": {
                    "srt_start": u['timing']['srt_start'],
                    "srt_end": u['timing']['srt_end'],
                    "acoustic_start": a_start,
                    "acoustic_end": a_end,
                    "duration": u['timing']['duration'],
                    "expected_offset_start": round(u['timing']['srt_start'] + global_offset, 3)
                },
                "source_evidence": {
                    "srt_blocks": srt_blocks,
                    "timeline_records": tl_recs,
                    "whisper_segments": w_segs_extracted,
                    "vad_intervals": overlapping_vad
                },
                "conversational_context": {
                    "prev_utterance": {
                        "utterance_id": prev_u['utterance_id'],
                        "timing": f"{prev_u['timing']['acoustic_start']:.2f}-{prev_u['timing']['acoustic_end']:.2f}s",
                        "text": prev_u['text']['reconstructed'],
                        "speaker_candidate": prev_u['speaker']['name']
                    } if prev_u else None,
                    "current_utterance_raw": {
                        "srt_raw_text": u['text']['raw_srt'],
                        "whisper_raw_text": u['text']['whisper'],
                        "initial_speaker_candidate": u['speaker']['name']
                    },
                    "next_utterance": {
                        "utterance_id": next_u['utterance_id'],
                        "timing": f"{next_u['timing']['acoustic_start']:.2f}-{next_u['timing']['acoustic_end']:.2f}s",
                        "text": next_u['text']['reconstructed'],
                        "speaker_candidate": next_u['speaker']['name']
                    } if next_u else None
                },
                "reference_knowledge": {
                    "episode_title": ep_context.get('title_original'),
                    "characters": [c['character_id'] for c in characters],
                    "entities": [e['entity_id'] for e in entities]
                }
            }
            evidence_packages.append(package)
            
        else:
            # Unmatched VAD case
            d_id = item['dialogue_id']
            s_idx = item['source_subtitle_index']
            se = subs_entries.get(s_idx, {})
            tr = timeline_records.get(d_id, {})
            
            s_start = item['timing']['srt_start']
            s_end = item['timing']['srt_end']
            exp_a_start = round(s_start + global_offset, 3)
            exp_a_end = round(s_end + global_offset, 3)
            
            # VAD overlap around expected acoustic window
            overlapping_vad = [v for v in vad_intervals if not (v['end'] < exp_a_start - 0.5 or v['start'] > exp_a_end + 0.5)]
            
            # Nearby whisper segments within 4 seconds
            nearby_w = []
            for s_idx_w, ws in enumerate(whisper_segments):
                if abs(ws['start'] - exp_a_start) < 4.0 or abs(ws['end'] - exp_a_end) < 4.0:
                    nearby_w.append({
                        "segment_index": s_idx_w,
                        "start": ws['start'],
                        "end": ws['end'],
                        "text": ws['text'].strip()
                    })
                    
            package = {
                "case_id": case_id,
                "case_type": "unmatched_vad",
                "dialogue_id": d_id,
                "source_subtitle_index": s_idx,
                "timing": {
                    "srt_start": s_start,
                    "srt_end": s_end,
                    "expected_acoustic_start": exp_a_start,
                    "expected_acoustic_end": exp_a_end
                },
                "source_evidence": {
                    "srt_text": item['speech_text'],
                    "raw_subtitle_block": se,
                    "timeline_record": tr,
                    "vad_intervals": overlapping_vad,
                    "nearby_whisper_segments": nearby_w
                },
                "reference_knowledge": {
                    "episode_title": ep_context.get('title_original')
                }
            }
            evidence_packages.append(package)
            
    evidence_doc = {
        "schema_version": "1.0",
        "episode": "S01E01",
        "total_packages": len(evidence_packages),
        "global_offset": global_offset,
        "packages": evidence_packages
    }
    
    with open(OUTPUT_PACKAGES_PATH, 'w', encoding='utf-8') as f:
        json.dump(evidence_doc, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(evidence_packages)} evidence packages to {OUTPUT_PACKAGES_PATH}")
    
    # Copy to destination script
    os.makedirs(os.path.dirname(DEST_SCRIPT_PATH), exist_ok=True)
    with open(__file__, 'r', encoding='utf-8') as src_f:
        code = src_f.read()
    with open(DEST_SCRIPT_PATH, 'w', encoding='utf-8') as dst_f:
        dst_f.write(code)
    print(f"Copied script to {DEST_SCRIPT_PATH}")

if __name__ == '__main__':
    build_evidence()
