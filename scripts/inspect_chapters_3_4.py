import sys, os, json, re
sys.path.insert(0, r'E:\AI-Dubbing')

from fanfic_pipeline.robsten_scraper import get_chapter_sections
from fanfic_pipeline.number_words import get_section_announcement
from fanfic_pipeline.censor import censor_text

sys.stdout.reconfigure(encoding='utf-8')

report = {}

for ch in [3, 4]:
    data = get_chapter_sections(ch, apply_censor=False)
    sections_info = []
    
    total_chars = 0
    total_censored = 0
    all_reps = []

    for i, s in enumerate(data['sections']):
        pov = s['pov']
        raw_text = s['text']
        total_chars += len(raw_text)
        
        # Check censor
        cleaned, reps = censor_text(raw_text)
        total_censored += len(reps)
        all_reps.extend(reps)
        
        ann = get_section_announcement(ch, i, pov)
        
        sections_info.append({
            'section_num': i + 1,
            'pov': pov,
            'announcement': ann,
            'char_count': len(raw_text),
            'start_sample': raw_text[:150].strip().replace('\n', ' '),
            'end_sample': raw_text[-150:].strip().replace('\n', ' '),
            'censor_replacements': reps
        })
        
    report[f'chapter_{ch}'] = {
        'header': data['header'],
        'title': data['title'],
        'num_sections': len(data['sections']),
        'total_chars': total_chars,
        'estimated_segments': total_chars // 100,
        'estimated_minutes': round((total_chars // 100) * 1.8 / 60, 1),
        'total_censored_count': total_censored,
        'unique_replacements': list(set(all_reps)),
        'sections': sections_info
    }

out_path = r'E:\AI-Dubbing\output\wide_awake\inspect_ch3_ch4.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"Report generated successfully: {out_path}")
