import json

with open(r'E:\AI-Dubbing-Subtitles\output\S01E01.timeline.final.json', 'r', encoding='utf-8') as f:
    tl_data = json.load(f)

records = tl_data.get('records', [])
print(f"Total timeline records: {len(records)}")

for i, r in enumerate(records):
    d_id = r.get('dialogue_id', f'D{i:04d}')
    src = r.get('source', {})
    start = src.get('start', 0.0)
    end = src.get('end', 0.0)
    en = src.get('text', '')
    ru = r.get('final_text', '')
    print(f"[{i:03d}] {d_id} ({start:7.2f} - {end:7.2f}) EN: {en}")
    print(f"      RU: {ru}")
