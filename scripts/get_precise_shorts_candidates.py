import json

with open(r"E:\AI-Dubbing\scripts\all_chapter1_timed_segments.json", "r", encoding="utf-8") as f:
    segs = json.load(f)

def find_range(sec, start_idx, end_idx):
    matched = [s for s in segs if s.get('sec') == sec and start_idx <= s.get('idx', -1) <= end_idx]
    if not matched:
        return None
    t_start = matched[0]['start']
    t_end = matched[-1]['end']
    dur = t_end - t_start
    text = " ".join([m['text'] for m in matched])
    
    start_fmt = f"{int(t_start//60):02d}:{t_start%60:04.1f}"
    end_fmt = f"{int(t_end//60):02d}:{t_end%60:04.1f}"
    return {
        'sec': sec,
        'start_idx': start_idx,
        'end_idx': end_idx,
        't_start_s': t_start,
        't_end_s': t_end,
        'start_fmt': start_fmt,
        'end_fmt': end_fmt,
        'dur': dur,
        'text': text
    }

candidates = [
    ("Short 1: Кошмар на биологии (Крики Беллы)", "sec_03_edward", 21, 30),
    ("Short 1b: Кошмар на биологии (Короткая версия - Дрожь и крик)", "sec_03_edward", 26, 30),
    ("Short 2: Правда о бессоннице Беллы (Сны о маме в крови)", "sec_00_bella", 20, 26),
    ("Short 3: Ночной ад Эдварда (Отец в огне)", "sec_01_edward", 57, 62),
    ("Short 3b: Эдвард на балконе (Ночь как паршивая русская книга)", "sec_01_edward", 20, 27),
    ("Short 4: Слухи о новенькой (Ньютон и паническая атака)", "sec_01_edward", 95, 105),
    ("Short 4b: Появление Беллы у школы (Капюшон и уставшие ноги)", "sec_01_edward", 101, 109),
    ("Short 5: Мантра изгоя (Капюшон на голову, глаза вниз)", "sec_02_bella", 17, 28),
    ("Short 6: Эдвард троллит Джаспера (Оттрахай его до потери пульса)", "sec_01_edward", 83, 92),
    ("Short 7: Карлайл, Эммет и дезодорант", "sec_03_edward", 33, 47),
]

results = []
for name, sec, s_i, e_i in candidates:
    info = find_range(sec, s_i, e_i)
    if info:
        info['name'] = name
        results.append(info)
        print(f"{name}:")
        print(f"  Таймкод: {info['start_fmt']} - {info['end_fmt']} (Длительность: {info['dur']:.1f}с)")
        print(f"  Текст: {info['text'][:120]}...\n")

with open(r"E:\AI-Dubbing\scripts\shorts_timed_summary.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
