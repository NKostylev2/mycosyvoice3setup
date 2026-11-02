import json, sys

def get_range_text(sec, start, end):
    path = f"E:\\AI-Dubbing\\work\\wide_awake\\chapter_01_robsten\\{sec}\\segments.json"
    with open(path, 'r', encoding='utf-8') as f:
        segs = json.load(f)
    lines = [f"=== {sec} ({start} to {end}) ==="]
    for i in range(start, min(end, len(segs))):
        t = segs[i]['text']
        lines.append(f"[{i:02d}] {t}")
    return "\n".join(lines)

with open(r"E:\AI-Dubbing\scripts\candidates_out_utf8.txt", "w", encoding="utf-8") as out:
    out.write("BIOLOGY LAB SCENE:\n")
    out.write(get_range_text("sec_03_edward", 8, 32) + "\n\n")

    out.write("BELLA INSOMNIA & TRAUMA:\n")
    out.write(get_range_text("sec_00_bella", 22, 36) + "\n\n")

    out.write("EDWARD NIGHT & FIRE GUILT:\n")
    out.write(get_range_text("sec_01_edward", 19, 30) + "\n\n")
    out.write(get_range_text("sec_01_edward", 55, 65) + "\n\n")

    out.write("RUMORS ABOUT BELLA:\n")
    out.write(get_range_text("sec_01_edward", 95, 112) + "\n\n")

    out.write("CARLISLE & DEODORANT:\n")
    out.write(get_range_text("sec_03_edward", 32, 48) + "\n\n")

