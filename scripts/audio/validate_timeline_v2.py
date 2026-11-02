from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORK_DIR = ROOT / "work"


def main() -> None:
    episode_key = sys.argv[1] if len(sys.argv) > 1 else "S01E01"
    work_dir = WORK_DIR / episode_key

    timeline_file = work_dir / "timeline_v2.json"
    offset_file = work_dir / "offset_report.json"

    if not timeline_file.exists():
        print(f"ERROR: {timeline_file} not found!")
        sys.exit(1)

    print(f"=== VALIDATING TIMELINE V2: {episode_key} ===")
    with timeline_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    with offset_file.open("r", encoding="utf-8") as f:
        offset_info = json.load(f)
        confirmed_offset = float(offset_info["CONFIRMED_GLOBAL_OFFSET"])

    records = data.get("records", [])
    print(f"Loaded {len(records)} timeline records.")

    errors = []
    catastrophic_matches = []
    warnings = []

    # 1. Unique and sequential dialogue IDs
    seen_ids = set()
    for idx, r in enumerate(records, start=1):
        d_id = r.get("dialogue_id")
        expected_id = f"D{idx:04d}"
        if not d_id:
            errors.append(f"Record #{idx} missing dialogue_id")
        elif d_id in seen_ids:
            errors.append(f"Duplicate dialogue_id: {d_id}")
        elif d_id != expected_id:
            errors.append(f"Non-sequential dialogue_id at #{idx}: expected {expected_id}, got {d_id}")
        seen_ids.add(d_id)

    # 2. Timestamps and duration
    for r in records:
        d_id = r["dialogue_id"]
        st = r["alignment_status"]
        if st == "NO_MATCH":
            if r["aligned_start"] is not None or r["aligned_end"] is not None:
                errors.append(f"{d_id}: NO_MATCH must have aligned_start=None and aligned_end=None")
        else:
            a_start = r["aligned_start"]
            a_end = r["aligned_end"]
            dur = r["duration"]
            if a_start is None or a_end is None or dur is None:
                errors.append(f"{d_id}: Matched record ({st}) missing aligned timestamps")
            else:
                if a_start < 0:
                    errors.append(f"{d_id}: Negative start timestamp: {a_start}")
                if a_end <= a_start:
                    errors.append(f"{d_id}: Non-positive duration: start={a_start}, end={a_end}")
                if dur <= 0:
                    errors.append(f"{d_id}: Duration must be positive: {dur}")

    # 3. Monotonicity and Catastrophic Jump Detection
    prev_w_max = -1
    for r in records:
        d_id = r["dialogue_id"]
        indices = r.get("whisper_segment_indices", [])
        if not indices:
            continue
        min_i = min(indices)
        max_i = max(indices)

        if min_i < prev_w_max:
            # Check if this is a legitimate MERGE sharing segment
            if not r.get("merge_group_id"):
                cat_err = {
                    "type": "BACKWARD_INDEX_JUMP",
                    "dialogue_id": d_id,
                    "segment_index": min_i,
                    "previous_max_index": prev_w_max,
                    "message": f"{d_id}: Whisper segment index {min_i} jumped backwards after {prev_w_max} without merge group"
                }
                catastrophic_matches.append(cat_err)
                errors.append(cat_err["message"])

        # Check time distance > 20s from expected offset time
        if r.get("aligned_start") is not None:
            exp_time = r["srt_start"] + confirmed_offset
            dist = abs(r["aligned_start"] - exp_time)
            if dist > 20.0 and r.get("text_score", 0.0) < 0.85:
                cat_err = {
                    "type": "EXCESSIVE_TIME_DISTANCE",
                    "dialogue_id": d_id,
                    "time_distance": round(dist, 3),
                    "text_score": r.get("text_score"),
                    "message": f"{d_id}: Candidate time distance {dist:.2f}s > 20.0s with weak sequence evidence"
                }
                catastrophic_matches.append(cat_err)
                errors.append(cat_err["message"])

        prev_w_max = max(prev_w_max, max_i)

    # 4. Duplicate Whisper assignment without MERGE group
    whisper_to_records = {}
    for r in records:
        for wi in r.get("whisper_segment_indices", []):
            whisper_to_records.setdefault(wi, []).append(r)

    for wi, recs in whisper_to_records.items():
        if len(recs) > 1:
            # All must belong to the same merge group
            merge_gids = set(r.get("merge_group_id") for r in recs)
            if None in merge_gids or len(merge_gids) > 1:
                errors.append(f"Whisper segment #{wi} assigned to multiple records without consistent merge_group_id: {[r['dialogue_id'] for r in recs]}")

    # 5. Split Groups Validation
    split_groups = {}
    for r in records:
        if r.get("split_group_id"):
            split_groups.setdefault(r["split_group_id"], []).append(r)
            if len(r["whisper_segment_indices"]) < 2:
                errors.append(f"{r['dialogue_id']}: SPLIT status must have >= 2 whisper segments, got {r['whisper_segment_indices']}")

    # 6. Merge Groups Validation
    merge_groups = {}
    for r in records:
        if r.get("merge_group_id"):
            merge_groups.setdefault(r["merge_group_id"], []).append(r)

    for gid, grecs in merge_groups.items():
        if len(grecs) < 2:
            errors.append(f"Merge group {gid} contains only {len(grecs)} record (must have at least 2)")
        # Check that records in merge group have non-overlapping word ranges
        for i in range(len(grecs) - 1):
            r1 = grecs[i]
            r2 = grecs[i + 1]
            w1 = r1.get("whisper_word_range")
            w2 = r2.get("whisper_word_range")
            if w1 and w2:
                if w1["end_word_index"] >= w2["start_word_index"]:
                    errors.append(f"Merge group {gid}: Word range overlap between {r1['dialogue_id']} ({w1['start_word_index']}-{w1['end_word_index']}) and {r2['dialogue_id']} ({w2['start_word_index']}-{w2['end_word_index']})")

    # 7. Word ranges validity
    for r in records:
        wr = r.get("whisper_word_range")
        if wr:
            if wr["start_word_index"] > wr["end_word_index"]:
                errors.append(f"{r['dialogue_id']}: Impossible word range: start {wr['start_word_index']} > end {wr['end_word_index']}")
            if wr["word_count"] <= 0:
                errors.append(f"{r['dialogue_id']}: Non-positive word count: {wr['word_count']}")
            if not wr["start_word"] or not wr["end_word"]:
                errors.append(f"{r['dialogue_id']}: Missing word text in range")

    # 8. VAD validation consistency
    for r in records:
        if r["alignment_status"] != "NO_MATCH":
            v_sc = r.get("vad_score")
            if v_sc is None or not (0.0 <= v_sc <= 1.0):
                errors.append(f"{r['dialogue_id']}: Invalid vad_score: {v_sc}")
            elif v_sc == 0.0 and r["alignment_status"] not in ("REVIEW", "NO_MATCH"):
                errors.append(f"{r['dialogue_id']}: vad_score is 0.0 but status is {r['alignment_status']} (must be REVIEW or NO_MATCH)")

    # Status distribution summary
    status_counts = {}
    for r in records:
        st = r["alignment_status"]
        status_counts[st] = status_counts.get(st, 0) + 1

    print("\n--- VALIDATION RESULTS ---")
    print(f"Total dialogue records       : {len(records)}")
    print(f"EXACT matches                : {status_counts.get('EXACT', 0)}")
    print(f"CLOSE matches                : {status_counts.get('CLOSE', 0)}")
    print(f"SPLIT matches                : {status_counts.get('SPLIT', 0)}")
    print(f"MERGE matches                : {status_counts.get('MERGE', 0)}")
    print(f"PARTIAL matches              : {status_counts.get('PARTIAL', 0)}")
    print(f"REVIEW matches               : {status_counts.get('REVIEW', 0)}")
    print(f"NO_MATCH records             : {status_counts.get('NO_MATCH', 0)}")
    print(f"Catastrophic match count     : {len(catastrophic_matches)}")
    print(f"Total validation errors      : {len(errors)}")

    if catastrophic_matches:
        print("\n*** HARD FAILURE: CATASTROPHIC MATCHES DETECTED ***")
        for cm in catastrophic_matches:
            print(f"  CRITICAL: {cm['message']}")
        sys.exit(1)

    if errors:
        print("\n*** VALIDATION FAILED: ERRORS DETECTED ***")
        for err in errors[:20]:
            print(f"  ERROR: {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors.")
        sys.exit(1)

    print("\n>>> ALL VALIDATION CHECKS PASSED SUCCESSFULLY (0 ERRORS, 0 CATASTROPHIC MATCHES) <<<")


if __name__ == "__main__":
    main()
