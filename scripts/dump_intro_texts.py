import json

with open(r"E:\AI-Dubbing\scripts\all_chapter1_timed_segments.json", "r", encoding="utf-8") as f:
    segs = json.load(f)

def get_clip_text(sec, s_idx, e_idx):
    matched = [s for s in segs if s.get('sec') == sec and s_idx <= s.get('idx', -1) <= e_idx]
    return " ".join([m['text'] for m in matched])

with open(r"E:\AI-Dubbing\scripts\intro_texts_utf8.txt", "w", encoding="utf-8") as f:
    f.write("=== ОПЦИЯ 1: Ночная кухня и переезд в Форкс (01:09 - 02:09, 60 сек) ===\n")
    f.write(get_clip_text("sec_00_bella", 10, 18) + "\n\n")

    f.write("=== ОПЦИЯ 2: 'Рыжие сдобные зомби' и утро (06:38 - 07:22, 43 сек) ===\n")
    f.write(get_clip_text("sec_00_bella", 53, 57) + "\n\n")

    f.write("=== ОПЦИЯ 3: Белла vs Элис - две противоположности (07:37 - 08:28, 50 сек) ===\n")
    f.write(get_clip_text("sec_00_bella", 61, 68) + "\n\n")

    f.write("=== ОПЦИЯ 4: Эдвард на балконе в Форксе (12:12 - 13:00, 48 сек) ===\n")
    f.write(get_clip_text("sec_01_edward", 19, 24) + "\n\n")

    f.write("=== ОПЦИЯ 5: Знакомство с домом Калленов (10:57 - 11:49, 52 сек) ===\n")
    f.write(get_clip_text("sec_01_edward", 8, 15) + "\n\n")

    f.write("=== ОПЦИЯ 6: Первая минута истории (00:06 - 00:55, 48 сек) ===\n")
    f.write(get_clip_text("sec_00_bella", 0, 7) + "\n\n")
