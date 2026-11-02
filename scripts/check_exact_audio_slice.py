import json

with open(r"E:\AI-Dubbing\scripts\all_chapter1_timed_segments.json", "r", encoding="utf-8") as f:
    segs = json.load(f)

for s in segs:
    if s.get("sec") == "sec_00_bella" and s.get("idx") in [52, 53, 54, 55, 56, 57, 58]:
        st = f"{int(s['start']//60):02d}:{s['start']%60:04.1f}"
        et = f"{int(s['end']//60):02d}:{s['end']%60:04.1f}"
        print(f"[{s['idx']}] {st} ({s['start']:.3f}s) -> {et} ({s['end']:.3f}s) | {s['text'][:60]}")
