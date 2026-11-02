import json

with open(r'E:\AI-Dubbing\scripts\all_chapter1_timed_segments.json', 'r', encoding='utf-8') as f:
    segs = json.load(f)

with open(r'E:\AI-Dubbing\scripts\inspect_intro_options.txt', 'w', encoding='utf-8') as out:
    out.write("=== EARLY BELLA (0-20) ===\n")
    for s in segs[:22]:
        idx = s.get('idx', -1)
        st = f"{int(s['start']//60):02d}:{s['start']%60:04.1f}"
        et = f"{int(s['end']//60):02d}:{s['end']%60:04.1f}"
        out.write(f"[{idx}] ({st} - {et}) {s['text']}\n")

    out.write("\n=== BELLA COOKIES & ALICE (36-65) ===\n")
    for s in segs[35:70]:
        if s.get('sec') == 'sec_00_bella':
            idx = s.get('idx', -1)
            st = f"{int(s['start']//60):02d}:{s['start']%60:04.1f}"
            et = f"{int(s['end']//60):02d}:{s['end']%60:04.1f}"
            out.write(f"[{idx}] ({st} - {et}) {s['text']}\n")

    out.write("\n=== EARLY EDWARD (sec_01 0-25) ===\n")
    for s in segs:
        if s.get('sec') == 'sec_01_edward' and s.get('idx', 999) < 25:
            idx = s.get('idx', -1)
            st = f"{int(s['start']//60):02d}:{s['start']%60:04.1f}"
            et = f"{int(s['end']//60):02d}:{s['end']%60:04.1f}"
            out.write(f"[{idx}] ({st} - {et}) {s['text']}\n")
