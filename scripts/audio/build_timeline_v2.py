from __future__ import annotations

import json
import math
import re
import statistics
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[2]
WORK_DIR = ROOT / "work"


def norm_tokens(text: str) -> list[str]:
    text = text.lower().replace("’", "'")
    text = re.sub(r"[^a-z0-9'\s]+", " ", text)
    return [t.strip("'") for t in text.split() if t.strip("'")]


def compute_text_score(s_text: str, w_text: str) -> float:
    s_tok = norm_tokens(s_text)
    w_tok = norm_tokens(w_text)
    if not s_tok or not w_tok:
        return 0.0
    seq_ratio = SequenceMatcher(None, s_tok, w_tok).ratio()
    s_set, w_set = set(s_tok), set(w_tok)
    jaccard = len(s_set & w_set) / max(1, len(s_set | w_set))
    sm = SequenceMatcher(None, s_tok, w_tok)
    m = sm.find_longest_match(0, len(s_tok), 0, len(w_tok))
    longest = m.size / max(1, min(len(s_tok), len(w_tok)))
    char_ratio = SequenceMatcher(None, " ".join(s_tok), " ".join(w_tok)).ratio()
    return round(0.35 * seq_ratio + 0.25 * jaccard + 0.20 * longest + 0.20 * char_ratio, 4)


def compute_time_score(dt: float) -> float:
    if dt > 15.0:
        return 0.0
    return round(math.exp(-0.5 * (dt / 3.0) ** 2), 4)


def compute_vad_score(start: float, end: float, vad_intervals: list[dict]) -> float:
    dur = end - start
    if dur <= 0:
        return 0.0
    tot_overlap = 0.0
    for iv in vad_intervals:
        ov = max(0.0, min(end, iv["end"]) - max(start, iv["start"]))
        tot_overlap += ov
    cov = tot_overlap / dur
    if cov >= 0.5:
        return 1.0
    elif cov >= 0.2:
        return 0.7
    elif cov > 0.0:
        return 0.4
    return 0.0


def main() -> None:
    episode_key = sys.argv[1] if len(sys.argv) > 1 else "S01E01"
    work_dir = WORK_DIR / episode_key

    srt_file = work_dir / "normalized_subtitles_v2.json"
    whisper_file = work_dir / "whisperx" / "source.json"
    vad_file = work_dir / "audio" / "vad.json"
    offset_file = work_dir / "offset_report.json"
    offset_diag_file = work_dir / "offset_diagnostics.json"

    for f_path in [srt_file, whisper_file, vad_file, offset_file, offset_diag_file]:
        if not f_path.exists():
            print(f"ERROR: Required input file missing: {f_path}")
            sys.exit(1)

    print(f"=== BUILDING TIMELINE V2: {episode_key} ===")
    with srt_file.open("r", encoding="utf-8") as f:
        all_srt = json.load(f)["entries"]
        srt_dialogue = [e for e in all_srt if e.get("is_dialogue")]

    with whisper_file.open("r", encoding="utf-8") as f:
        whisper_segments = json.load(f)["segments"]

    with vad_file.open("r", encoding="utf-8") as f:
        vad_data = json.load(f)
        vad_intervals = vad_data.get("intervals", vad_data.get("speech_segments", []))

    with offset_file.open("r", encoding="utf-8") as f:
        offset_info = json.load(f)
        confirmed_offset = float(offset_info["CONFIRMED_GLOBAL_OFFSET"])
        offset_model = offset_info.get("OFFSET_MODEL", "CONSTANT_OFFSET")

    with offset_diag_file.open("r", encoding="utf-8") as f:
        anchors_list = json.load(f)["anchors"]

    print(f"Dialogue SRT entries : {len(srt_dialogue)}")
    print(f"Whisper segments     : {len(whisper_segments)}")
    print(f"VAD intervals        : {len(vad_intervals)}")
    print(f"Global Offset        : {confirmed_offset:+.4f} s ({offset_model})")
    print(f"Anchors              : {len(anchors_list)}")

    # Anchor lookup by srt_index
    anchor_by_sidx = {a["srt_index"]: a for a in anchors_list}

    # Identify anchor indices in srt_dialogue list
    anchor_dialogue_indices = [
        i for i, se in enumerate(srt_dialogue)
        if se["index"] in anchor_by_sidx
    ]

    # Calculate Whisper search bounds [min_w, max_w] for each dialogue entry
    w_bounds = []
    for i in range(len(srt_dialogue)):
        prev_a = max([idx for idx in anchor_dialogue_indices if idx <= i], default=None)
        next_a = min([idx for idx in anchor_dialogue_indices if idx >= i], default=None)

        min_w = anchor_by_sidx[srt_dialogue[prev_a]["index"]]["whisper_indices"][0] if prev_a is not None else 0
        max_w = anchor_by_sidx[srt_dialogue[next_a]["index"]]["whisper_indices"][-1] if next_a is not None else len(whisper_segments) - 1
        w_bounds.append((min_w, max_w))

    # Perform Anchor-Bounded Monotonic Sequence Alignment
    records = []
    current_w_cursor = 0
    split_counter = 1
    merge_counter = 1

    for i, se in enumerate(srt_dialogue):
        s_idx = se["index"]
        s_text = se["speech_text"]
        exp_time = se["start"] + confirmed_offset
        min_w, max_w = w_bounds[i]

        search_start = max(current_w_cursor, min_w)
        search_end = max_w

        if s_idx in anchor_by_sidx:
            anc = anchor_by_sidx[s_idx]
            w_indices = anc["whisper_indices"]
            t_score = anc["text_similarity"]
            dt = abs(anc["whisper_start"] - exp_time)
            tm_score = compute_time_score(dt)
            v_score = compute_vad_score(anc["whisper_start"], anc["whisper_end"], vad_intervals)

            if v_score == 0.0:
                status = "REVIEW"
                split_grp = None
            elif len(w_indices) > 1:
                status = "SPLIT"
                split_grp = f"SPLIT_{split_counter:04d}"
                split_counter += 1
            elif t_score >= 0.80:
                status = "EXACT"
                split_grp = None
            else:
                status = "CLOSE"
                split_grp = None

            words_combo = []
            for wi in w_indices:
                words_combo.extend(whisper_segments[wi].get("words", []))

            w_word_range = None
            if words_combo:
                w_word_range = {
                    "start_word_index": 0,
                    "end_word_index": len(words_combo) - 1,
                    "start_word": words_combo[0]["word"],
                    "end_word": words_combo[-1]["word"],
                    "word_count": len(words_combo),
                }

            rec = {
                "dialogue_id": f"D{i + 1:04d}",
                "source_subtitle_index": s_idx,
                "srt_start": se["start"],
                "srt_end": se["end"],
                "speech_text": s_text,
                "speaker_tag": se["speaker_tag"],
                "aligned_start": anc["whisper_start"],
                "aligned_end": anc["whisper_end"],
                "duration": round(anc["whisper_end"] - anc["whisper_start"], 3),
                "alignment_status": status,
                "alignment_confidence": round(0.55 * t_score + 0.25 * tm_score + 0.15 * v_score + 0.05 * 1.0, 4),
                "text_score": t_score,
                "time_score": tm_score,
                "vad_score": v_score,
                "speaker_score": 1.0,
                "candidate_margin": round(t_score - 0.20, 4),
                "whisper_segment_indices": w_indices,
                "whisper_word_range": w_word_range,
                "split_group_id": split_grp,
                "merge_group_id": None,
                "notes": "Verified anchor match"
            }
            records.append(rec)
            current_w_cursor = max(w_indices)
        else:
            best_cand = None
            best_comp = -1.0
            second_comp = -1.0

            # 1. Check MERGE with previous record if previous record matched a segment in bounds and within 8 seconds
            if records and records[-1]["whisper_segment_indices"]:
                prev_rec = records[-1]
                prev_w_idx = prev_rec["whisper_segment_indices"][-1]
                prev_ws = whisper_segments[prev_w_idx]
                dt_merge = abs(prev_ws["start"] - exp_time)
                if dt_merge <= 8.0:
                    combo_sub = prev_rec["speech_text"] + " " + s_text
                    t_merge = compute_text_score(combo_sub, prev_ws["text"])
                    if t_merge >= 0.60:
                        tm_merge = compute_time_score(dt_merge)
                        v_merge = compute_vad_score(prev_ws["start"], prev_ws["end"], vad_intervals)
                        comp_merge = 0.55 * t_merge + 0.25 * tm_merge + 0.15 * v_merge + 0.05 * 1.0
                        best_comp = comp_merge
                        best_cand = {
                            "indices": [prev_w_idx],
                            "start": prev_ws["start"],
                            "end": prev_ws["end"],
                            "words": prev_ws.get("words", []),
                            "text_score": t_merge,
                            "time_score": tm_merge,
                            "vad_score": v_merge,
                            "composite": comp_merge,
                            "is_split": False,
                            "is_merge": True,
                        }

            # 2. Check candidate segments within bounded search range
            for w_i in range(search_start, search_end + 1):
                ws = whisper_segments[w_i]
                dt = abs(ws["start"] - exp_time)
                if dt > 15.0:
                    continue
                t_sc = compute_text_score(s_text, ws["text"])
                tm_sc = compute_time_score(dt)
                v_sc = compute_vad_score(ws["start"], ws["end"], vad_intervals)
                comp = 0.55 * t_sc + 0.25 * tm_sc + 0.15 * v_sc + 0.05 * 1.0

                if comp > best_comp:
                    second_comp = best_comp
                    best_comp = comp
                    best_cand = {
                        "indices": [w_i],
                        "start": ws["start"],
                        "end": ws["end"],
                        "words": ws.get("words", []),
                        "text_score": t_sc,
                        "time_score": tm_sc,
                        "vad_score": v_sc,
                        "composite": comp,
                        "is_split": False,
                        "is_merge": False,
                    }
                elif comp > second_comp:
                    second_comp = comp

                # Check SPLIT (ws + ws_next)
                if w_i + 1 <= search_end:
                    ws2 = whisper_segments[w_i + 1]
                    combo_w = ws["text"] + " " + ws2["text"]
                    t_sc2 = compute_text_score(s_text, combo_w)
                    if t_sc2 > t_sc + 0.12:
                        dt2 = abs(ws["start"] - exp_time)
                        tm_sc2 = compute_time_score(dt2)
                        v_sc2 = compute_vad_score(ws["start"], ws2["end"], vad_intervals)
                        comp2 = 0.55 * t_sc2 + 0.25 * tm_sc2 + 0.15 * v_sc2 + 0.05 * 1.0
                        if comp2 > best_comp:
                            second_comp = best_comp
                            best_comp = comp2
                            combo_words = ws.get("words", []) + ws2.get("words", [])
                            best_cand = {
                                "indices": [w_i, w_i + 1],
                                "start": ws["start"],
                                "end": ws2["end"],
                                "words": combo_words,
                                "text_score": t_sc2,
                                "time_score": tm_sc2,
                                "vad_score": v_sc2,
                                "composite": comp2,
                                "is_split": True,
                                "is_merge": False,
                            }

            # Classify candidate or apply reject logic
            margin = max(0.0, round(best_comp - max(0.0, second_comp), 4))
            if best_cand is None or best_cand["text_score"] < 0.35:
                # Explicit reject: No candidate within time window with text score >= 0.35
                rec = {
                    "dialogue_id": f"D{i + 1:04d}",
                    "source_subtitle_index": s_idx,
                    "srt_start": se["start"],
                    "srt_end": se["end"],
                    "speech_text": s_text,
                    "speaker_tag": se["speaker_tag"],
                    "aligned_start": None,
                    "aligned_end": None,
                    "duration": None,
                    "alignment_status": "NO_MATCH",
                    "alignment_confidence": 0.0,
                    "text_score": best_cand["text_score"] if best_cand else 0.0,
                    "time_score": best_cand["time_score"] if best_cand else 0.0,
                    "vad_score": 0.0,
                    "speaker_score": 1.0,
                    "candidate_margin": 0.0,
                    "whisper_segment_indices": [],
                    "whisper_word_range": None,
                    "split_group_id": None,
                    "merge_group_id": None,
                    "notes": "Rejected: No candidate within time window with text score >= 0.35"
                }
                records.append(rec)
            else:
                bc = best_cand
                t_sc = bc["text_score"]
                v_sc = bc["vad_score"]

                # If this candidate shares any segment with previous record, it is a merge
                prev_matched_indices = records[-1]["whisper_segment_indices"] if records else []
                is_sharing_with_prev = bool(set(bc["indices"]) & set(prev_matched_indices))

                if bc["is_merge"] or is_sharing_with_prev:
                    status = "MERGE"
                    merge_grp = records[-1].get("merge_group_id")
                    if not merge_grp:
                        merge_grp = f"MERGE_{merge_counter:04d}"
                        merge_counter += 1
                        records[-1]["merge_group_id"] = merge_grp
                        records[-1]["alignment_status"] = "MERGE"
                    split_grp = None
                    shared_indices = sorted(list(set(records[-1]["whisper_segment_indices"] + bc["indices"])))
                    records[-1]["whisper_segment_indices"] = shared_indices
                    bc["indices"] = shared_indices
                elif bc["is_split"]:
                    status = "SPLIT"
                    split_grp = f"SPLIT_{split_counter:04d}"
                    split_counter += 1
                    merge_grp = None
                elif v_sc == 0.0 or t_sc < 0.48:
                    status = "REVIEW"
                    split_grp = None
                    merge_grp = None
                elif t_sc >= 0.80:
                    status = "EXACT"
                    split_grp = None
                    merge_grp = None
                elif t_sc >= 0.65:
                    status = "CLOSE"
                    split_grp = None
                    merge_grp = None
                else:
                    status = "PARTIAL"
                    split_grp = None
                    merge_grp = None

                words = bc.get("words", [])
                w_range = None
                if words:
                    w_range = {
                        "start_word_index": 0,
                        "end_word_index": len(words) - 1,
                        "start_word": words[0]["word"],
                        "end_word": words[-1]["word"],
                        "word_count": len(words),
                    }

                rec = {
                    "dialogue_id": f"D{i + 1:04d}",
                    "source_subtitle_index": s_idx,
                    "srt_start": se["start"],
                    "srt_end": se["end"],
                    "speech_text": s_text,
                    "speaker_tag": se["speaker_tag"],
                    "aligned_start": bc["start"],
                    "aligned_end": bc["end"],
                    "duration": round(bc["end"] - bc["start"], 3),
                    "alignment_status": status,
                    "alignment_confidence": round(bc["composite"], 4),
                    "text_score": t_sc,
                    "time_score": bc["time_score"],
                    "vad_score": v_sc,
                    "speaker_score": 1.0,
                    "candidate_margin": margin,
                    "whisper_segment_indices": bc["indices"],
                    "whisper_word_range": w_range,
                    "split_group_id": split_grp,
                    "merge_group_id": merge_grp,
                    "notes": "Acoustic match with VAD validation"
                }
                records.append(rec)
                current_w_cursor = max(current_w_cursor, bc["indices"][0])

    # Partition words and non-overlapping timestamps for all MERGE groups
    merge_groups = {}
    for r in records:
        if r.get("merge_group_id"):
            merge_groups.setdefault(r["merge_group_id"], []).append(r)

    for gid, grecs in merge_groups.items():
        all_seg_indices = sorted(list(set(wi for r in grecs for wi in r["whisper_segment_indices"])))
        all_words = []
        for wi in all_seg_indices:
            all_words.extend(whisper_segments[wi].get("words", []))

        if not all_words:
            continue

        total_words = len(all_words)
        token_counts = [max(1, len(norm_tokens(r["speech_text"]))) for r in grecs]
        total_tokens = sum(token_counts)

        M = len(grecs)
        if total_words >= M:
            boundaries = [0]
            cur = 0
            for k in range(M - 1):
                prop = token_counts[k] / total_tokens
                w_alloc = max(1, round(total_words * prop))
                cur += w_alloc
                rem = M - 1 - k
                cur = max(k + 1, min(cur, total_words - rem))
                boundaries.append(cur)
            boundaries.append(total_words)

            for k, rec in enumerate(grecs):
                s_w = boundaries[k]
                e_w = boundaries[k + 1] - 1
                w_slice = all_words[s_w:e_w + 1]
                rec["aligned_start"] = w_slice[0]["start"]
                rec["aligned_end"] = w_slice[-1]["end"]
                rec["duration"] = round(rec["aligned_end"] - rec["aligned_start"], 3)
                rec["whisper_word_range"] = {
                    "start_word_index": s_w,
                    "end_word_index": e_w,
                    "start_word": w_slice[0]["word"],
                    "end_word": w_slice[-1]["word"],
                    "word_count": len(w_slice),
                }
                v_sc = compute_vad_score(rec["aligned_start"], rec["aligned_end"], vad_intervals)
                rec["vad_score"] = v_sc
                if v_sc == 0.0:
                    rec["alignment_status"] = "REVIEW"
                else:
                    rec["alignment_status"] = "MERGE"
        else:
            for rec in grecs:
                rec["aligned_start"] = all_words[0]["start"]
                rec["aligned_end"] = all_words[-1]["end"]
                rec["duration"] = round(rec["aligned_end"] - rec["aligned_start"], 3)
                rec["whisper_word_range"] = {
                    "start_word_index": 0,
                    "end_word_index": total_words - 1,
                    "start_word": all_words[0]["word"],
                    "end_word": all_words[-1]["word"],
                    "word_count": total_words,
                }
                rec["alignment_status"] = "REVIEW"

    # Compile report statistics
    status_counts = {}
    for r in records:
        st = r["alignment_status"]
        status_counts[st] = status_counts.get(st, 0) + 1

    matched_records = [r for r in records if r["aligned_start"] is not None]
    avg_conf = statistics.mean([r["alignment_confidence"] for r in matched_records]) if matched_records else 0.0
    avg_text = statistics.mean([r["text_score"] for r in matched_records]) if matched_records else 0.0
    avg_time = statistics.mean([r["time_score"] for r in matched_records]) if matched_records else 0.0
    avg_vad = statistics.mean([r["vad_score"] for r in matched_records]) if matched_records else 0.0

    timeline_payload = {
        "schema_version": "2.0",
        "episode_key": episode_key,
        "record_count": len(records),
        "alignment_parameters": {
            "confirmed_offset_seconds": confirmed_offset,
            "offset_model": offset_model,
            "max_search_distance_seconds": 15.0,
            "min_text_score_threshold": 0.35,
        },
        "records": records,
    }

    report_payload = {
        "schema_version": "2.0",
        "episode_key": episode_key,
        "record_count": len(records),
        "status_distribution": status_counts,
        "metrics": {
            "matched_count": len(matched_records),
            "no_match_count": status_counts.get("NO_MATCH", 0),
            "review_count": status_counts.get("REVIEW", 0),
            "split_count": status_counts.get("SPLIT", 0),
            "merge_count": status_counts.get("MERGE", 0),
            "exact_count": status_counts.get("EXACT", 0),
            "close_count": status_counts.get("CLOSE", 0),
            "partial_count": status_counts.get("PARTIAL", 0),
            "mean_confidence": round(avg_conf, 4),
            "mean_text_score": round(avg_text, 4),
            "mean_time_score": round(avg_time, 4),
            "mean_vad_score": round(avg_vad, 4),
        },
        "merge_groups_count": len(merge_groups),
        "split_groups_count": split_counter - 1,
    }

    out_timeline = work_dir / "timeline_v2.json"
    out_report = work_dir / "timeline_v2_report.json"

    out_timeline.write_text(json.dumps(timeline_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_report.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Timeline v2 written: {out_timeline}")
    print(f"Timeline report v2 written: {out_report}")
    print("Status distribution:")
    for st, c in sorted(status_counts.items()):
        print(f"  {st:12}: {c}")
    print(f"Merge groups: {len(merge_groups)}, Split groups: {split_counter - 1}")
    print(f"Average confidence: {avg_conf:.4f}, Average text score: {avg_text:.4f}")
    print("BUILD TIMELINE V2 COMPLETE (PASS)")


if __name__ == "__main__":
    main()
