import os
import sys
import json
import sqlite3
from typing import Dict, List, Any, Optional

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = r"E:\AI-Dubbing"
TIMELINE_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\timeline_v2.json")
NORMALIZED_SUBS_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\normalized_subtitles_v2.json")
WHISPER_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\whisperx\source.json")
VAD_PATH = os.path.join(PROJECT_ROOT, r"work\S01E01\audio\vad.json")
DB_PATH = os.path.join(PROJECT_ROOT, r"database\dubbing.db")
EPISODE_CONTEXT_PATH = os.path.join(PROJECT_ROOT, r"knowledge\canonical\episode_context\martin_mystery_001.json")

OUTPUT_CANONICAL = os.path.join(PROJECT_ROOT, r"work\S01E01\canonical_dialogue.json")
OUTPUT_REVIEW_QUEUE = os.path.join(PROJECT_ROOT, r"work\S01E01\semantic_review_queue.json")
SCRIPT_COPY_PATH = os.path.join(PROJECT_ROOT, r"scripts\audio\build_canonical_dialogue.py")

# Explicit Speaker mapping by dialogue_id or merge_group_id
SPEAKER_KNOWLEDGE = {
    # Teaser Scene (Library abduction)
    "D0001": ("character_librarian", "Librarian / Nelly's Father", "INFERRED"),
    "D0002": ("character_librarian", "Librarian / Nelly's Father", "INFERRED"),
    
    # Torrington Cafeteria (Bet Scene)
    "MERGE_0001": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0002": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0013": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0015": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0003": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0018": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0004": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0005": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0006": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0025": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0026": ("martin_mystery", "Martin Mystery", "INFERRED"),
    
    # The Center: Billy Ice Cream & Mission Briefing
    "D0027": ("billy", "Billy", "INFERRED"),
    "D0028": ("billy", "Billy", "INFERRED"),
    "MERGE_0007": ("billy", "Billy", "INFERRED"),
    "D0034": ("mom", "M.O.M.", "INFERRED"),
    "D0035": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0036": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0037": ("mom", "M.O.M.", "INFERRED"),
    "MERGE_0008": ("mom", "M.O.M.", "INFERRED"),
    "D0040": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0009": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0043": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0044": ("mom", "M.O.M.", "INFERRED"),
    "D0045": ("mom", "M.O.M.", "INFERRED"),
    "D0046": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0010": ("billy", "Billy", "INFERRED"),
    "D0050": ("martin_mystery", "Martin Mystery", "INFERRED"),
    
    # Arrival in France (Investigation of Library)
    "MERGE_0011": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0012": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0055": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0056": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0057": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0058": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0013": ("character_librarian", "Librarian / Nelly's Father", "INFERRED"),
    "MERGE_0014": ("character_librarian", "Librarian / Nelly's Father", "INFERRED"),
    "D0063": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0064": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0065": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0066": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0067": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0015": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0016": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0017": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0074": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0018": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0077": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0019": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0080": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0020": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0083": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0021": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0022": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0088": ("diana_lombard", "Diana Lombard", "INFERRED"),
    
    # Investigation & Ian's Mother
    "MERGE_0023": ("character_ians_mother", "Ian's Mother", "INFERRED"),
    "D0091": ("character_ians_mother", "Ian's Mother", "INFERRED"),
    "D0092": (None, "Townsperson", "AMBIGUOUS"),
    "D0093": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0094": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0024": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0025": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0026": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0102": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0027": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0105": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0028": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0029": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0110": ("java", "Java", "INFERRED"),
    "D0111": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0112": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0113": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0114": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0030": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0117": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0031": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0120": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0121": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0122": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0123": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0032": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0126": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0127": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0128": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0033": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0131": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0034": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0035": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0137": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0036": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0140": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0141": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0142": ("martin_mystery", "Martin Mystery", "INFERRED"),
    
    # Baiting the Bogeyman (Town meeting / Bedroom)
    "MERGE_0037": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0147": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0148": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0038": ("character_librarian", "Librarian / Nelly's Father", "INFERRED"),
    "MERGE_0039": (None, "Townsperson / Parent", "AMBIGUOUS"),
    "D0153": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0154": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0040": ("character_librarian", "Librarian / Nelly's Father", "INFERRED"),
    "D0157": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0158": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0159": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0160": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0161": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0162": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0163": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0164": ("diana_lombard", "Diana Lombard", "INFERRED"),
    
    # In the Bogeyman Realm
    "D0169": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0041": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0042": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0175": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0176": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0043": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0044": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0181": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0182": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0183": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0184": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0045": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0046": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0047": ("character_nelly", "Nelly", "INFERRED"),
    "D0194": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0195": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0048": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0198": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0049": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0050": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0203": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0051": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0206": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0210": ("monster_bogeyman", "Bogeyman", "INFERRED"),
    "D0211": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0052": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0215": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0053": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0218": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0054": ("martin_mystery", "Martin Mystery", "INFERRED"),
    
    # Resolution & Epilogue
    "D0230": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0231": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0233": ("java", "Java", "INFERRED"),
    "MERGE_0055": ("mom", "M.O.M.", "INFERRED"),
    "MERGE_0056": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0238": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0239": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "D0240": ("diana_lombard", "Diana Lombard", "INFERRED"),
    "MERGE_0057": ("character_librarian", "Librarian / Nelly's Father", "INFERRED"),
    "D0243": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0058": ("character_nelly", "Nelly", "INFERRED"),
    "D0247": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0248": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "MERGE_0059": ("martin_mystery", "Martin Mystery", "INFERRED"),
    "D0251": ("martin_mystery", "Martin Mystery", "INFERRED"),
}

# Scene Boundary markers by dialogue ID
SCENE_BOUNDARIES = {
    "D0001": ("CONFIRMED", "NONE"),      # Teaser start
    "D0002": ("NONE", "CONFIRMED"),      # Teaser end -> Intro title
    "D0007": ("CONFIRMED", "NONE"),      # Torrington cafeteria start
    "D0026": ("NONE", "CONFIRMED"),      # Torrington cafeteria end
    "D0027": ("CONFIRMED", "NONE"),      # Center briefing room start
    "D0050": ("NONE", "CONFIRMED"),      # Center briefing room end
    "D0051": ("CONFIRMED", "NONE"),      # Arrival in France start
    "D0164": ("NONE", "CONFIRMED"),      # Abduction to Bogeyman realm
    "D0169": ("CONFIRMED", "NONE"),      # In Bogeyman realm start
    "D0221": ("NONE", "CONFIRMED"),      # Escaping Bogeyman realm
    "D0230": ("CONFIRMED", "NONE"),      # Epilogue in France
    "D0251": ("NONE", "CONFIRMED"),      # Final punchline
}

def load_data():
    with open(TIMELINE_PATH, 'r', encoding='utf-8') as f:
        timeline = json.load(f)
    with open(NORMALIZED_SUBS_PATH, 'r', encoding='utf-8') as f:
        normalized_subs = json.load(f)
    with open(WHISPER_PATH, 'r', encoding='utf-8') as f:
        whisper = json.load(f)
    with open(VAD_PATH, 'r', encoding='utf-8') as f:
        vad = json.load(f)
    with open(EPISODE_CONTEXT_PATH, 'r', encoding='utf-8') as f:
        ep_context = json.load(f)
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    characters = [dict(r) for r in cur.execute("SELECT * FROM characters").fetchall()]
    entities = [dict(r) for r in cur.execute("SELECT * FROM entities").fetchall()]
    conn.close()
    
    return timeline, normalized_subs, whisper, vad, ep_context, characters, entities

def reconstruct_text(srt_texts: List[str], whisper_texts: List[str], key_id: str) -> Dict[str, Any]:
    full_srt = " ".join(srt_texts).strip()
    full_whisper = " ".join(whisper_texts).strip()
    
    # Specific targeted decisions
    if key_id == "D0240":
        return {
            "srt": full_srt,
            "whisper": full_whisper,
            "reconstructed": "Huh, that's a laugh.",
            "decision": "WHISPER_PREFERRED",
            "confidence": 0.98,
            "reason": "SRT 'that's allowed' is an obvious phonetic transcription error for 'that's a laugh'."
        }
    if key_id == "D0239":
        return {
            "srt": full_srt,
            "whisper": full_whisper,
            "reconstructed": "Anything yourself?",
            "decision": "WHISPER_PREFERRED",
            "confidence": 0.90,
            "reason": "Whisper transcription captures the skeptical question responding to Martin."
        }
    if key_id in ["D0182", "D0183"]:
        return {
            "srt": full_srt,
            "whisper": full_whisper,
            "reconstructed": full_whisper if full_whisper else full_srt,
            "decision": "WHISPER_PREFERRED",
            "confidence": 0.98,
            "reason": "Whisper captures proper casing and exclamation punctuation."
        }
    if key_id == "D0131":
        return {
            "srt": full_srt,
            "whisper": full_whisper,
            "reconstructed": "U-Watch activated.",
            "decision": "MERGED_FROM_BOTH",
            "confidence": 0.99,
            "reason": "Canon gadget name is U-Watch (transcribed as 'you want' in SRT, 'You watch' in Whisper)."
        }
    if key_id == "D0251":
        return {
            "srt": full_srt,
            "whisper": full_whisper,
            "reconstructed": "A deal's a deal, Di.",
            "decision": "MERGED_FROM_BOTH",
            "confidence": 0.95,
            "reason": "Martin addresses Diana by nickname 'Di' (transcribed as 'Dye' in Whisper, 'guy' in SRT)."
        }
    if key_id == "MERGE_0034":
        return {
            "srt": full_srt,
            "whisper": full_whisper,
            "reconstructed": "According to the Legendex, he's a mythological nursery monster from 19th century England.",
            "decision": "MERGED_FROM_BOTH",
            "confidence": 0.99,
            "reason": "Canon gadget name is Legendex (transcribed as 'legend x' in SRT, 'legendex' in Whisper)."
        }
        
    # General rule: if whisper text is clean and matches or exceeds SRT completeness
    if full_whisper and len(full_whisper) >= len(full_srt) * 0.7:
        return {
            "srt": full_srt,
            "whisper": full_whisper,
            "reconstructed": full_whisper,
            "decision": "WHISPER_PREFERRED" if full_whisper.lower() != full_srt.lower() else "SRT_PREFERRED",
            "confidence": 0.95 if full_whisper.lower() == full_srt.lower() else 0.92,
            "reason": "Whisper audio transcript provides accurate punctuation and complete phrasing."
        }
    else:
        return {
            "srt": full_srt,
            "whisper": full_whisper,
            "reconstructed": full_srt if full_srt else full_whisper,
            "decision": "SRT_PREFERRED",
            "confidence": 0.85,
            "reason": "SRT retained as primary guide for phrasing where Whisper was partially truncated."
        }

def build():
    timeline, normalized_subs, whisper, vad, ep_context, characters, entities = load_data()
    
    whisper_segments = whisper.get('segments', [])
    vad_intervals = vad.get('intervals', [])
    records = timeline['records']
    
    # Separate matched vs unmatched
    matched_records = [r for r in records if r['alignment_status'] != 'NO_MATCH']
    unmatched_records = [r for r in records if r['alignment_status'] == 'NO_MATCH']
    
    # Form logical units (grouping merge groups)
    units = []
    curr_mg = None
    curr_group = []
    
    for r in matched_records:
        mg = r.get('merge_group_id')
        if mg:
            if curr_mg == mg:
                curr_group.append(r)
            else:
                if curr_group:
                    units.append(('MERGE', curr_mg, curr_group))
                curr_mg = mg
                curr_group = [r]
        else:
            if curr_group:
                units.append(('MERGE', curr_mg, curr_group))
                curr_mg = None
                curr_group = []
            units.append(('SINGLE', r['dialogue_id'], [r]))
            
    if curr_group:
        units.append(('MERGE', curr_mg, curr_group))
        
    print(f"Reconstructed {len(units)} logical units from {len(matched_records)} matched records.")
    
    utterances = []
    review_queue = []
    
    for idx, (utype, key_id, recs) in enumerate(units):
        u_id = f"U{idx+1:04d}"
        d_ids = [r['dialogue_id'] for r in recs]
        srt_event_ids = [r['source_subtitle_index'] for r in recs]
        
        # Timing bounds
        srt_start = min(r['srt_start'] for r in recs)
        srt_end = max(r['srt_end'] for r in recs)
        acoustic_start = min(r['aligned_start'] for r in recs)
        acoustic_end = max(r['aligned_end'] for r in recs)
        
        # Whisper segment indices & word ranges
        w_indices = sorted(list(set(s for r in recs for s in r.get('whisper_segment_indices', []))))
        w_words = []
        w_texts = []
        for s_idx in w_indices:
            if s_idx < len(whisper_segments):
                seg = whisper_segments[s_idx]
                w_texts.append(seg['text'].strip())
                if 'words' in seg:
                    w_words.extend(seg['words'])
                    
        # Precise word range from first and last record
        first_wr = recs[0].get('whisper_word_range')
        last_wr = recs[-1].get('whisper_word_range')
        if first_wr and last_wr:
            whisper_word_range = {
                "start_word_index": first_wr['start_word_index'],
                "end_word_index": last_wr['end_word_index'],
                "start_word": first_wr['start_word'],
                "end_word": last_wr['end_word'],
                "word_count": sum(r.get('whisper_word_range', {}).get('word_count', 0) for r in recs)
            }
        else:
            whisper_word_range = None
            
        srt_texts = [r['speech_text'] for r in recs]
        text_info = reconstruct_text(srt_texts, w_texts, key_id)
        
        # Speaker determination
        spk_info = SPEAKER_KNOWLEDGE.get(key_id) or SPEAKER_KNOWLEDGE.get(d_ids[0])
        if spk_info:
            char_id, spk_name, spk_status = spk_info
        else:
            char_id, spk_name, spk_status = (None, None, "UNKNOWN")
            
        # Alignment score composite
        mean_conf = sum(r.get('alignment_confidence', 0.0) for r in recs) / len(recs)
        
        # Scene boundaries
        first_d = d_ids[0]
        last_d = d_ids[-1]
        boundary_before = SCENE_BOUNDARIES.get(first_d, ("NONE", "NONE"))[0]
        boundary_after = SCENE_BOUNDARIES.get(last_d, ("NONE", "NONE"))[1]
        
        # Semantic status
        has_review = any(r.get('alignment_status') == 'REVIEW' for r in recs)
        has_partial = any(r.get('alignment_status') == 'PARTIAL' for r in recs)
        if spk_status in ["UNKNOWN", "AMBIGUOUS"]:
            semantic_status = "AMBIGUOUS"
        elif has_review or text_info['decision'] in ['MERGED_FROM_BOTH', 'AMBIGUOUS'] or text_info['confidence'] < 0.90:
            semantic_status = "REVIEW"
        elif mean_conf >= 0.90 and spk_status in ["EXPLICIT", "INFERRED"]:
            semantic_status = "CONFIRMED"
        else:
            semantic_status = "HIGH_CONFIDENCE"
            
        # Link entities and characters
        knowledge_links = {
            "characters": [char_id] if char_id and char_id in [c['character_id'] for c in characters] else [],
            "entities": [],
            "facts": []
        }
        rec_txt_lower = text_info['reconstructed'].lower()
        if "bogeyman" in rec_txt_lower or "boogeyman" in rec_txt_lower:
            knowledge_links["entities"].append("monster_bogeyman")
        if "center" in rec_txt_lower:
            knowledge_links["entities"].append("organization_the_center")
        if "legendex" in rec_txt_lower:
            knowledge_links["entities"].append("object_legendex")
        if "u-watch" in rec_txt_lower or "you watch" in rec_txt_lower:
            knowledge_links["entities"].append("object_u_watch")
            
        utterance_record = {
            "utterance_id": u_id,
            "speaker": {
                "character_id": char_id,
                "name": spk_name,
                "status": spk_status
            },
            "timing": {
                "srt_start": round(srt_start, 3),
                "srt_end": round(srt_end, 3),
                "acoustic_start": round(acoustic_start, 3),
                "acoustic_end": round(acoustic_end, 3),
                "duration": round(acoustic_end - acoustic_start, 3)
            },
            "source": {
                "dialogue_ids": d_ids,
                "srt_event_ids": srt_event_ids,
                "whisper_segment_indices": w_indices,
                "whisper_word_range": whisper_word_range,
                "alignment_statuses": [r['alignment_status'] for r in recs]
            },
            "text": {
                "raw_srt": " ".join(srt_texts),
                "srt_fragments": srt_texts,
                "whisper": " ".join(w_texts),
                "whisper_segments": w_texts,
                "reconstructed": text_info['reconstructed'],
                "decision": text_info['decision'],
                "confidence": text_info['confidence'],
                "reason": text_info['reason']
            },
            "alignment": {
                "status": "MERGE" if utype == 'MERGE' else recs[0]['alignment_status'],
                "confidence": round(mean_conf, 4)
            },
            "semantic": {
                "status": semantic_status,
                "scene_boundary_before": boundary_before,
                "scene_boundary_after": boundary_after
            },
            "knowledge": knowledge_links
        }
        
        utterances.append(utterance_record)
        
        # Add to review queue if not CONFIRMED or if review criteria met
        if semantic_status in ["REVIEW", "AMBIGUOUS"]:
            review_queue.append({
                "utterance_id": u_id,
                "dialogue_ids": d_ids,
                "semantic_status": semantic_status,
                "speaker": utterance_record['speaker'],
                "timing": utterance_record['timing'],
                "text": utterance_record['text'],
                "issue_type": "SPEAKER_UNCERTAINTY" if spk_status in ["UNKNOWN", "AMBIGUOUS"] else "TEXT_OR_ALIGNMENT_REVIEW",
                "notes": text_info['reason']
            })
            
    # Process unmatched source events (32 NO_MATCH)
    unmatched_events = []
    for r in unmatched_records:
        d_id = r['dialogue_id']
        s_start = r['srt_start']
        s_end = r['srt_end']
        exp_start = s_start + 12.0280
        exp_end = s_end + 12.0280
        
        # Check VAD
        has_vad = any(not (v['end'] < exp_start - 0.5 or v['start'] > exp_end + 0.5) for v in vad_intervals)
        
        # Check nearby whisper
        nearby_w = [w['text'].strip() for w in whisper_segments if abs(w['start'] - exp_start) < 3.5]
        
        if "came from the bog" in r['speech_text']:
            reason = "NON_DIALOGUE"
            notes = "Episode title screen card graphic, no acoustic speech."
        elif not has_vad:
            reason = "NO_ACOUSTIC_EVIDENCE"
            notes = "No acoustic speech detected by Silero VAD or WhisperX in expected time window."
        elif has_vad and not nearby_w:
            reason = "WHISPER_MISSED"
            notes = "VAD detected acoustic voice activity, but WhisperX omitted transcription (likely background scream/noise)."
        elif has_vad and nearby_w:
            reason = "VAD_ONLY"
            notes = f"VAD detected speech; nearby Whisper segments ({', '.join(nearby_w)}) rejected due to low text similarity."
        else:
            reason = "AMBIGUOUS"
            notes = "Unmatched dialogue candidate requiring audio review."
            
        unm_record = {
            "dialogue_id": d_id,
            "source_subtitle_index": r['source_subtitle_index'],
            "srt_start": round(s_start, 3),
            "srt_end": round(s_end, 3),
            "speech_text": r['speech_text'],
            "reason": reason,
            "vad_presence": has_vad,
            "nearby_whisper": nearby_w,
            "notes": notes
        }
        unmatched_events.append(unm_record)
        
        # Add VAD-present unmatched events to review queue
        if has_vad or reason in ["WHISPER_MISSED", "VAD_ONLY"]:
            review_queue.append({
                "dialogue_id": d_id,
                "source_subtitle_index": r['source_subtitle_index'],
                "issue_type": "UNMATCHED_SPEECH_IN_AUDIO",
                "speech_text": r['speech_text'],
                "reason": reason,
                "timing": {"srt_start": s_start, "srt_end": s_end, "expected_acoustic_start": round(exp_start, 3)},
                "notes": notes
            })
            
    # Process non-dialogue events from normalized_subtitles_v2
    entries = normalized_subs.get('entries', [])
    non_dialogue_events = []
    for e in entries:
        if e.get('event_type') != 'DIALOGUE':
            non_dialogue_events.append({
                "source_srt_event_id": e['index'],
                "source_block": e['source_block'],
                "event_type": e['event_type'],
                "srt_start": e['start'],
                "srt_end": e['end'],
                "raw_text": e['raw_text']
            })
            
    # Final Canonical Dialogue Document
    canonical_doc = {
        "schema_version": "1.0",
        "episode": "S01E01",
        "title": ep_context.get("title_original", "It Came from the Bog"),
        "global_offset": {
            "seconds": 12.0280,
            "model": "CONSTANT_OFFSET"
        },
        "summary": {
            "total_dialogue_records": len(records),
            "matched_dialogue_records": len(matched_records),
            "unmatched_dialogue_records": len(unmatched_records),
            "canonical_utterances_count": len(utterances),
            "non_dialogue_events_count": len(non_dialogue_events),
            "status_counts": {
                "CONFIRMED": sum(1 for u in utterances if u['semantic']['status'] == 'CONFIRMED'),
                "HIGH_CONFIDENCE": sum(1 for u in utterances if u['semantic']['status'] == 'HIGH_CONFIDENCE'),
                "REVIEW": sum(1 for u in utterances if u['semantic']['status'] == 'REVIEW'),
                "AMBIGUOUS": sum(1 for u in utterances if u['semantic']['status'] == 'AMBIGUOUS')
            },
            "speaker_distribution": {
                "martin_mystery": sum(1 for u in utterances if u['speaker']['character_id'] == 'martin_mystery'),
                "diana_lombard": sum(1 for u in utterances if u['speaker']['character_id'] == 'diana_lombard'),
                "java": sum(1 for u in utterances if u['speaker']['character_id'] == 'java'),
                "billy": sum(1 for u in utterances if u['speaker']['character_id'] == 'billy'),
                "mom": sum(1 for u in utterances if u['speaker']['character_id'] == 'mom'),
                "character_librarian": sum(1 for u in utterances if u['speaker']['character_id'] == 'character_librarian'),
                "character_ians_mother": sum(1 for u in utterances if u['speaker']['character_id'] == 'character_ians_mother'),
                "character_nelly": sum(1 for u in utterances if u['speaker']['character_id'] == 'character_nelly'),
                "monster_bogeyman": sum(1 for u in utterances if u['speaker']['character_id'] == 'monster_bogeyman'),
                "AMBIGUOUS / OTHER": sum(1 for u in utterances if u['speaker']['status'] in ['AMBIGUOUS', 'UNKNOWN'])
            }
        },
        "utterances": utterances,
        "unmatched_source_events": unmatched_events,
        "non_dialogue_events": non_dialogue_events
    }
    
    with open(OUTPUT_CANONICAL, 'w', encoding='utf-8') as f:
        json.dump(canonical_doc, f, indent=2, ensure_ascii=False)
    print(f"Wrote canonical dialogue to {OUTPUT_CANONICAL} ({len(utterances)} utterances).")
    
    review_queue_doc = {
        "schema_version": "1.0",
        "episode": "S01E01",
        "queue_count": len(review_queue),
        "items": review_queue
    }
    with open(OUTPUT_REVIEW_QUEUE, 'w', encoding='utf-8') as f:
        json.dump(review_queue_doc, f, indent=2, ensure_ascii=False)
    print(f"Wrote semantic review queue to {OUTPUT_REVIEW_QUEUE} ({len(review_queue)} items).")

    # Also copy script to E:\AI-Dubbing\scripts\audio\build_canonical_dialogue.py
    os.makedirs(os.path.dirname(SCRIPT_COPY_PATH), exist_ok=True)
    with open(__file__, 'r', encoding='utf-8') as src_f:
        code = src_f.read()
    with open(SCRIPT_COPY_PATH, 'w', encoding='utf-8') as dst_f:
        dst_f.write(code)
    print(f"Copied build script to {SCRIPT_COPY_PATH}")

if __name__ == '__main__':
    build()
