import sys, os, json
sys.path.insert(0, r'E:\AI-Dubbing')
from fanfic_pipeline.robsten_scraper import get_chapter_sections
from fanfic_pipeline.censor import censor_text

results = {}
for ch in [1, 2]:
    data = get_chapter_sections(ch)
    ch_reps = []
    for s_idx, sec in enumerate(data['sections']):
        cleaned, reps = censor_text(sec['text'])
        if reps:
            ch_reps.append({
                'sec_idx': s_idx + 1,
                'pov': sec['pov'],
                'replacements': reps
            })
    results[f'chapter_{ch}'] = ch_reps

with open(r'E:\AI-Dubbing\output\wide_awake\censor_replacements.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("Saved to censor_replacements.json")
