import sys, os, json
sys.path.insert(0, r'E:\AI-Dubbing')

from fanfic_pipeline.robsten_scraper import get_chapter_sections
from fanfic_pipeline.number_words import get_section_announcement
from fanfic_pipeline.censor import censor_text

sys.stdout.reconfigure(encoding='utf-8')

for ch in [7, 8]:
    print("=" * 60)
    data = get_chapter_sections(ch, apply_censor=True)
    print(f"CHAPTER {ch}: {data['header']} - {data['title']}")
    print(f"Total sections: {len(data['sections'])}")
    for i, s in enumerate(data['sections']):
        ann = get_section_announcement(ch, i, s['pov'])
        reps = s.get('censor_reps', [])
        print(f"\n--- Section {i+1} [{s['pov'].upper()}] ---")
        print(f"  Announcement: \"{ann}\"")
        print(f"  Char count: {s['char_count']}")
        print(f"  Starts: {repr(s['text'][:100])}")
        print(f"  Ends:   {repr(s['text'][-100:])}")
        if reps:
            print(f"  Censored ({len(reps)}): {', '.join(reps)}")
