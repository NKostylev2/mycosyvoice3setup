import json

with open(r'E:\AI-Dubbing-Subtitles\output\S01E01.timeline.final.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

records = data.get('records', [])
print(f"Total records in timeline: {len(records)}")

for i, r in enumerate(records):
    d_id = r.get('dialogue_id', f'D{i:04d}')
    src = r.get('source', {})
    start = src.get('start', 0.0)
    end = src.get('end', 0.0)
    en_text = src.get('text', '')
    ru_text = r.get('final_text', '')
    print(f"[{i:03d}] {d_id} ({start:7.2f}s - {end:7.2f}s, len={end-start:4.2f}s): {en_text}")
