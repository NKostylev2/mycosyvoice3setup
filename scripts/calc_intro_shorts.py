import json

with open(r"E:\AI-Dubbing\scripts\all_chapter1_timed_segments.json", "r", encoding="utf-8") as f:
    segs = json.load(f)

def get_clip(sec, s_idx, e_idx):
    matched = [s for s in segs if s.get('sec') == sec and s_idx <= s.get('idx', -1) <= e_idx]
    if not matched: return None
    t0 = matched[0]['start']
    t1 = matched[-1]['end']
    fmt0 = f"{int(t0//60):02d}:{t0%60:04.1f}"
    fmt1 = f"{int(t1//60):02d}:{t1%60:04.1f}"
    text = " ".join([m['text'] for m in matched])
    return {
        'sec': sec,
        's_idx': s_idx,
        'e_idx': e_idx,
        't0': t0,
        't1': t1,
        'fmt0': fmt0,
        'fmt1': fmt1,
        'dur': t1 - t0,
        'text': text
    }

options = [
    ("Опция 1: Уютный ночной ритуал Беллы (Кухня в Форксе)", "sec_00_bella", 10, 18),
    ("Опция 2: Утро Беллы (Рыжие сдобные зомби)", "sec_00_bella", 53, 57),
    ("Опция 3: Контраст сестер (Интроверт Белла и энерджайзер Элис)", "sec_00_bella", 61, 68),
    ("Опция 4: Ночной Форкс и балкон Эдварда (Паршивая русская книга)", "sec_01_edward", 19, 24),
    ("Опция 5: Знакомство с семьей Калленов (Карлайл и сироты)", "sec_01_edward", 8, 15),
    ("Опция 6: Начало истории (Комната и дом Калленов напротив)", "sec_00_bella", 0, 7),
]

for title, sec, s_i, e_i in options:
    c = get_clip(sec, s_i, e_i)
    print(f"\n{title}")
    print(f"  Таймкод: {c['fmt0']} - {c['fmt1']} (Длительность: {c['dur']:.1f}с)")
    print(f"  Текст: {c['text'][:150]}...")
