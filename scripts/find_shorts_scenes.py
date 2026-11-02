import os, json, soundfile as sf

sections = [
    ('sec_00_bella', r'E:\AI-Dubbing\work\wide_awake\chapter_01_robsten\sec_00_bella'),
    ('sec_01_edward', r'E:\AI-Dubbing\work\wide_awake\chapter_01_robsten\sec_01_edward'),
    ('sec_02_bella', r'E:\AI-Dubbing\work\wide_awake\chapter_01_robsten\sec_02_bella'),
    ('sec_03_edward', r'E:\AI-Dubbing\work\wide_awake\chapter_01_robsten\sec_03_edward'),
]

curr_time = 0.0
all_segs = []

for sec_name, sec_dir in sections:
    intro_wav = os.path.join(sec_dir, 'intro_announcement.wav')
    if os.path.exists(intro_wav):
        curr_time += sf.info(intro_wav).duration + 0.5
    
    seg_json = os.path.join(sec_dir, 'segments.json')
    with open(seg_json, 'r', encoding='utf-8') as f:
        segs = json.load(f)
    
    seg_dir = os.path.join(sec_dir, 'audio_segments')
    wavs = sorted([f for f in os.listdir(seg_dir) if f.endswith('.wav')])
    
    for i, w in enumerate(wavs):
        wp = os.path.join(seg_dir, w)
        dur = sf.info(wp).duration
        txt = segs[i]['text'] if i < len(segs) else ''
        all_segs.append({
            'sec': sec_name,
            'idx': i,
            'seg_file': w,
            'start': curr_time,
            'end': curr_time + dur,
            'duration': dur,
            'text': txt
        })
        curr_time += dur + 0.25

print(f"Total mapped segments: {len(all_segs)}, end time: {curr_time:.2f}s ({curr_time/60:.2f}m)")

keywords = [
    'не могу спать',
    'собственной крови',
    'русской книги',
    'сгорающего заживо',
    'отыметь',
    'Брэндон',
    'Ньютон',
    'Шизанутая Новая Кузина',
    'колыбельная',
    'Получи',
    'крики',
    'дезодорант'
]

for kw in keywords:
    matches = [s for s in all_segs if kw.lower() in s['text'].lower()]
    for m in matches:
        start_m, start_s = int(m['start'] // 60), int(m['start'] % 60)
        end_m, end_s = int(m['end'] // 60), int(m['end'] % 60)
        print(f"[{m['sec']}|#{m['idx']:03d}] {start_m:02d}:{start_s:02d}-{end_m:02d}:{end_s:02d} ({m['duration']:.1f}s) | {m['text'][:90]}")
