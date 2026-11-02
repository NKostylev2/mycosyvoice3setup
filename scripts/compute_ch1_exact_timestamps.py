import os, json, soundfile as sf

sample_rate = 24000
pause_sentence_s = 0.250
pause_para_s = 0.650
pause_intro_s = 0.850
pause_pov_s = 1.500

sections = [
    ('sec_00_bella', r'E:\AI-Dubbing\work\wide_awake\chapter_01_robsten\sec_00_bella'),
    ('sec_01_edward', r'E:\AI-Dubbing\work\wide_awake\chapter_01_robsten\sec_01_edward'),
    ('sec_02_bella', r'E:\AI-Dubbing\work\wide_awake\chapter_01_robsten\sec_02_bella'),
    ('sec_03_edward', r'E:\AI-Dubbing\work\wide_awake\chapter_01_robsten\sec_03_edward'),
]

curr_t = 0.0
all_segs = []

for s_idx, (sec_name, sec_dir) in enumerate(sections):
    intro_wav = os.path.join(sec_dir, 'intro_announcement.wav')
    if os.path.exists(intro_wav):
        dur = sf.info(intro_wav).duration
        all_segs.append({
            'type': 'intro',
            'sec': sec_name,
            'start': curr_t,
            'end': curr_t + dur,
            'text': f"INTRO: {sec_name}"
        })
        curr_t += dur + pause_intro_s
    
    with open(os.path.join(sec_dir, 'segments.json'), 'r', encoding='utf-8') as f:
        segs = json.load(f)
    
    seg_dir = os.path.join(sec_dir, 'audio_segments')
    wavs = sorted([f for f in os.listdir(seg_dir) if f.endswith('.wav')])
    
    for i, w in enumerate(wavs):
        wp = os.path.join(seg_dir, w)
        dur = sf.info(wp).duration
        seg_meta = segs[i] if i < len(segs) else {}
        is_last = seg_meta.get('is_last_in_p', False)
        all_segs.append({
            'type': 'story',
            'sec': sec_name,
            'idx': i,
            'seg_file': w,
            'start': curr_t,
            'end': curr_t + dur,
            'duration': dur,
            'is_last_in_p': is_last,
            'text': seg_meta.get('text', '')
        })
        curr_t += dur + (pause_para_s if is_last else pause_sentence_s)
    
    if s_idx < len(sections) - 1:
        curr_t += pause_pov_s

final_wav = r"E:\AI-Dubbing\output\wide_awake\Chapter_01_Рыжие Сдобные Зомби.wav"
actual_dur = sf.info(final_wav).duration
print(f"Calculated end time: {curr_t:.2f}s, Actual WAV duration: {actual_dur:.2f}s (Diff: {abs(curr_t - actual_dur):.3f}s)")

with open(r"E:\AI-Dubbing\scripts\all_chapter1_timed_segments.json", "w", encoding="utf-8") as f:
    json.dump(all_segs, f, ensure_ascii=False, indent=2)
