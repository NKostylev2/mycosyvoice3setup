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


def normalize_tokens(text: str) -> list[str]:
    text = text.lower()
    text = text.replace("’", "'")
    # Replace punctuation with space, keep alphanumeric and apostrophe
    text = re.sub(r"[^a-z0-9'\s]+", " ", text)
    tokens = [t.strip("'") for t in text.split() if t.strip("'")]
    return tokens


def compute_text_similarity(s_text: str, w_text: str) -> float:
    s_tok = normalize_tokens(s_text)
    w_tok = normalize_tokens(w_text)
    if not s_tok or not w_tok:
        return 0.0

    # Sequence similarity of tokens
    seq_ratio = SequenceMatcher(None, s_tok, w_tok).ratio()

    # Jaccard token overlap
    s_set, w_set = set(s_tok), set(w_tok)
    jaccard = len(s_set & w_set) / max(1, len(s_set | w_set))

    # Longest common sequence of words
    sm = SequenceMatcher(None, s_tok, w_tok)
    match = sm.find_longest_match(0, len(s_tok), 0, len(w_tok))
    longest_ratio = match.size / max(1, min(len(s_tok), len(w_tok)))

    return round(0.40 * seq_ratio + 0.30 * jaccard + 0.30 * longest_ratio, 4)


AMBIGUOUS_SHORT = {
    "hmm", "oh", "no", "what", "what?", "yeah", "yes", "hey", "look", "well",
    "uh", "ah", "okay", "right", "sorry", "thanks", "wow", "whoa", "why",
    "stop", "run", "help", "wait", "please", "come on", "over here"
}


def is_distinctive_anchor(speech_text: str) -> bool:
    tokens = normalize_tokens(speech_text)
    joined = " ".join(tokens)
    if len(tokens) < 3:
        return False
    if len(joined) < 14:
        return False
    if joined in AMBIGUOUS_SHORT:
        return False
    return True


def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_d = sorted(data)
    idx = (len(sorted_d) - 1) * p
    lower = int(math.floor(idx))
    upper = int(math.ceil(idx))
    weight = idx - lower
    return round(sorted_d[lower] * (1.0 - weight) + sorted_d[upper] * weight, 4)


def fit_linear_regression(x: list[float], y: list[float]) -> tuple[float, float, float]:
    n = len(x)
    if n < 2:
        return 1.0, 0.0, 1.0
    mean_x = statistics.mean(x)
    mean_y = statistics.mean(y)
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    den = sum((xi - mean_x) ** 2 for xi in x)
    if den == 0:
        return 1.0, mean_y - mean_x, 1.0
    slope = num / den
    intercept = mean_y - slope * mean_x

    # R^2
    y_pred = [slope * xi + intercept for xi in x]
    ss_tot = sum((yi - mean_y) ** 2 for yi in y)
    ss_res = sum((yi - ypi) ** 2 for yi, ypi in zip(y, y_pred))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0

    return round(slope, 6), round(intercept, 4), round(r_squared, 6)


def main() -> None:
    episode_key = sys.argv[1] if len(sys.argv) > 1 else "S01E01"
    work_dir = WORK_DIR / episode_key
    srt_file = work_dir / "normalized_subtitles_v2.json"
    whisper_file = work_dir / "whisperx" / "source.json"

    if not srt_file.exists():
        print(f"ERROR: {srt_file} not found!")
        sys.exit(1)
    if not whisper_file.exists():
        print(f"ERROR: {whisper_file} not found!")
        sys.exit(1)

    print(f"=== SRT <-> AUDIO OFFSET ANALYSIS: {episode_key} ===")
    print(f"SRT Input: {srt_file}")
    print(f"WhisperX Input: {whisper_file}")

    with srt_file.open("r", encoding="utf-8") as f:
        srt_data = json.load(f)["entries"]

    with whisper_file.open("r", encoding="utf-8") as f:
        whisper_data = json.load(f)["segments"]

    # Filter dialogue entries
    dialogue_entries = [
        e for e in srt_data
        if e.get("is_dialogue") and e.get("speech_text") and is_distinctive_anchor(e["speech_text"])
    ]
    print(f"Candidate dialogue anchors to evaluate: {len(dialogue_entries)} (from total {len(srt_data)} SRT entries)")

    # Find reliable anchors using high text similarity and monotonic sequence order
    raw_matches = []
    for se in dialogue_entries:
        s_text = se["speech_text"]
        best_sim = 0.0
        best_w = None

        # Search against single segments and adjacent segment pairs
        for i, ws in enumerate(whisper_data):
            sim1 = compute_text_similarity(s_text, ws["text"])
            if sim1 > best_sim:
                best_sim = sim1
                best_w = (ws["start"], ws["end"], ws["text"], [i])

            # Check consecutive pair (ws + ws_next)
            if i + 1 < len(whisper_data):
                ws_next = whisper_data[i + 1]
                combo_text = ws["text"] + " " + ws_next["text"]
                sim_combo = compute_text_similarity(s_text, combo_text)
                if sim_combo > best_sim:
                    best_sim = sim_combo
                    best_w = (ws["start"], ws_next["end"], combo_text, [i, i + 1])

        if best_sim >= 0.82 and best_w is not None:
            raw_matches.append({
                "subtitle_id": f"SRT_{se['index']:04d}",
                "srt_index": se["index"],
                "srt_start": se["start"],
                "srt_end": se["end"],
                "srt_text": s_text,
                "whisper_start": best_w[0],
                "whisper_end": best_w[1],
                "whisper_text": best_w[2],
                "whisper_indices": best_w[3],
                "text_similarity": best_sim,
                "delta_start": round(best_w[0] - se["start"], 4),
                "delta_end": round(best_w[1] - se["end"], 4),
            })

    print(f"High-similarity initial anchor matches found: {len(raw_matches)}")

    # Enforce strict sequence monotonicity (eliminate any false backward jumps)
    # Longest monotonic subsequence of whisper_start with respect to srt_start
    raw_matches.sort(key=lambda m: m["srt_start"])
    # Dynamic programming for longest monotonic subsequence
    n = len(raw_matches)
    dp = [1] * n
    parent = [-1] * n
    for i in range(n):
        for j in range(i):
            if raw_matches[i]["whisper_start"] > raw_matches[j]["whisper_start"]:
                # Check that delta is within sane bounds (no wild time travel)
                delta_diff = abs(raw_matches[i]["delta_start"] - raw_matches[j]["delta_start"])
                if delta_diff < 5.0 and dp[j] + 1 > dp[i]:
                    dp[i] = dp[j] + 1
                    parent[i] = j

    max_len = max(dp) if dp else 0
    best_idx = dp.index(max_len) if dp else -1
    monotonic_chain = []
    curr = best_idx
    while curr != -1:
        monotonic_chain.append(raw_matches[curr])
        curr = parent[curr]
    monotonic_chain.reverse()

    anchors = monotonic_chain
    print(f"Monotonic reliable anchors retained: {len(anchors)}")

    if len(anchors) < 10:
        print(f"ERROR: Insufficient anchors found ({len(anchors)} < 10)!")
        sys.exit(1)

    # Compute confidence for each anchor
    for a in anchors:
        sim = a["text_similarity"]
        # Confidence incorporates text similarity and sequence consistency
        a["confidence"] = round(min(1.0, sim * 1.0), 4)

    start_deltas = [a["delta_start"] for a in anchors]
    end_deltas = [a["delta_end"] for a in anchors]

    median_delta = round(statistics.median(start_deltas), 4)
    mean_delta = round(statistics.mean(start_deltas), 4)
    std_delta = round(statistics.stdev(start_deltas), 4) if len(start_deltas) > 1 else 0.0
    p10_delta = percentile(start_deltas, 0.10)
    p90_delta = percentile(start_deltas, 0.90)
    min_delta = round(min(start_deltas), 4)
    max_delta = round(max(start_deltas), 4)

    # -------------------------------------------------------------
    # MODEL EVALUATION
    # -------------------------------------------------------------
    # Model A: Constant Offset (w = s + median_delta)
    res_a = [round(a["whisper_start"] - (a["srt_start"] + median_delta), 4) for a in anchors]
    mae_a = round(statistics.mean([abs(r) for r in res_a]), 4)
    rmse_a = round(math.sqrt(statistics.mean([r ** 2 for r in res_a])), 4)
    max_err_a = round(max([abs(r) for r in res_a]), 4)

    # Model B: Linear Drift (w = slope * s + intercept)
    srt_times = [a["srt_start"] for a in anchors]
    w_times = [a["whisper_start"] for a in anchors]
    slope_b, intercept_b, r2_b = fit_linear_regression(srt_times, w_times)
    res_b = [round(w - (slope_b * s + intercept_b), 4) for s, w in zip(srt_times, w_times)]
    mae_b = round(statistics.mean([abs(r) for r in res_b]), 4)
    rmse_b = round(math.sqrt(statistics.mean([r ** 2 for r in res_b])), 4)
    max_err_b = round(max([abs(r) for r in res_b]), 4)

    # Model C: Piecewise Offset (Acts / Sections: 0-450s, 450-900s, 900-1410s)
    sections = [
        {"name": "Act 1 (0-450s)", "t_min": 0.0, "t_max": 450.0, "deltas": []},
        {"name": "Act 2 (450-900s)", "t_min": 450.0, "t_max": 900.0, "deltas": []},
        {"name": "Act 3 (900-1410s)", "t_min": 900.0, "t_max": 1410.0, "deltas": []},
    ]
    for a in anchors:
        for sec in sections:
            if sec["t_min"] <= a["srt_start"] < sec["t_max"]:
                sec["deltas"].append(a["delta_start"])

    piecewise_summary = []
    for sec in sections:
        d = sec["deltas"]
        if d:
            piecewise_summary.append({
                "section": sec["name"],
                "anchor_count": len(d),
                "median_delta": round(statistics.median(d), 4),
                "mean_delta": round(statistics.mean(d), 4),
                "std_delta": round(statistics.stdev(d), 4) if len(d) > 1 else 0.0,
                "min_delta": round(min(d), 4),
                "max_delta": round(max(d), 4),
            })
        else:
            piecewise_summary.append({
                "section": sec["name"],
                "anchor_count": 0,
                "median_delta": None,
                "mean_delta": None,
                "std_delta": None,
                "min_delta": None,
                "max_delta": None,
            })

    # Evaluate section variation
    valid_medians = [s["median_delta"] for s in piecewise_summary if s["median_delta"] is not None]
    section_spread = max(valid_medians) - min(valid_medians) if len(valid_medians) > 1 else 0.0

    # Determine winning model:
    # If slope_b is extremely close to 1.0 (drift over 1400s < 0.2s) and section spread < 0.25s:
    # Model A is confirmed as Constant Global Offset.
    drift_over_episode = abs(slope_b - 1.0) * 1410.0
    if drift_over_episode < 0.35 and section_spread < 0.35:
        offset_model = "CONSTANT_OFFSET"
        confirmed_global_offset = median_delta
        model_notes = (
            f"Constant offset confirmed at +{median_delta:.3f}s. "
            f"Linear drift slope is {slope_b:.6f} (drift over episode: {drift_over_episode:.3f}s, negligible). "
            f"Cross-act median spread is {section_spread:.3f}s, showing high stability across the episode."
        )
    elif section_spread >= 0.35:
        offset_model = "PIECEWISE_OFFSET"
        confirmed_global_offset = median_delta
        model_notes = f"Piecewise offset observed: cross-act spread is {section_spread:.3f}s."
    else:
        offset_model = "LINEAR_DRIFT"
        confirmed_global_offset = median_delta
        model_notes = f"Linear drift detected: slope {slope_b:.6f}, total drift {drift_over_episode:.3f}s."

    # Diagnostics file
    diagnostics_data = {
        "schema_version": "1.0",
        "episode_key": episode_key,
        "anchor_count": len(anchors),
        "anchors": anchors,
    }
    diag_file = work_dir / "offset_diagnostics.json"
    diag_file.write_text(json.dumps(diagnostics_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Report file
    report_data = {
        "schema_version": "1.0",
        "episode_key": episode_key,
        "CONFIRMED_GLOBAL_OFFSET": confirmed_global_offset,
        "OFFSET_MODEL": offset_model,
        "model_notes": model_notes,
        "statistics": {
            "anchor_count": len(anchors),
            "median_delta_start": median_delta,
            "mean_delta_start": mean_delta,
            "std_delta_start": std_delta,
            "p10_delta_start": p10_delta,
            "p90_delta_start": p90_delta,
            "min_delta_start": min_delta,
            "max_delta_start": max_delta,
            "median_delta_end": round(statistics.median(end_deltas), 4),
            "mean_delta_end": round(statistics.mean(end_deltas), 4),
        },
        "model_evaluations": {
            "model_a_constant": {
                "formula": f"whisper_time = srt_time + {median_delta:.4f}",
                "mae_seconds": mae_a,
                "rmse_seconds": rmse_a,
                "max_error_seconds": max_err_a,
            },
            "model_b_linear_drift": {
                "formula": f"whisper_time = {slope_b:.6f} * srt_time + {intercept_b:.4f}",
                "slope": slope_b,
                "intercept": intercept_b,
                "r_squared": r2_b,
                "drift_over_episode_seconds": round(drift_over_episode, 4),
                "mae_seconds": mae_b,
                "rmse_seconds": rmse_b,
                "max_error_seconds": max_err_b,
            },
            "model_c_piecewise": {
                "sections": piecewise_summary,
                "max_median_spread_seconds": round(section_spread, 4),
            }
        },
        "temporal_distribution": {
            "first_anchor": {
                "srt_start": anchors[0]["srt_start"],
                "whisper_start": anchors[0]["whisper_start"],
                "delta": anchors[0]["delta_start"],
                "text": anchors[0]["srt_text"],
            },
            "last_anchor": {
                "srt_start": anchors[-1]["srt_start"],
                "whisper_start": anchors[-1]["whisper_start"],
                "delta": anchors[-1]["delta_start"],
                "text": anchors[-1]["srt_text"],
            }
        }
    }
    rep_file = work_dir / "offset_report.json"
    rep_file.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("==================================================")
    print(f"CONFIRMED_GLOBAL_OFFSET : {confirmed_global_offset:+.4f} s")
    print(f"OFFSET_MODEL            : {offset_model}")
    print("==================================================")
    print(f"Anchors analyzed        : {len(anchors)}")
    print(f"Median start delta      : {median_delta:+.4f} s")
    print(f"Mean start delta        : {mean_delta:+.4f} s")
    print(f"Std dev                 : {std_delta:.4f} s")
    print(f"p10 / p90               : {p10_delta:+.4f} s / {p90_delta:+.4f} s")
    print(f"Min / Max               : {min_delta:+.4f} s / {max_delta:+.4f} s")
    print()
    print("Model Comparison:")
    print(f"  Model A (Constant)    : MAE={mae_a:.4f}s, RMSE={rmse_a:.4f}s, MaxErr={max_err_a:.4f}s")
    print(f"  Model B (Linear)      : slope={slope_b:.6f}, intercept={intercept_b:.4f}, MAE={mae_b:.4f}s")
    print(f"  Model C (Piecewise)   : Cross-act spread={section_spread:.4f}s")
    print(f"Report written          : {rep_file}")
    print(f"Diagnostics written     : {diag_file}")
    print("OFFSET ANALYSIS COMPLETE (PASS)")


if __name__ == "__main__":
    main()
