import json

with open(r'E:\AI-Dubbing-Subtitles\output\S01E01.timeline.final.json', 'r', encoding='utf-8') as f:
    tl_data = json.load(f)
records = tl_data.get('records', [])

print("=== 800s to 1250s (Bogeyman encounter & battle) ===")
for i, r in enumerate(records):
    start = r.get('source', {}).get('start', 0.0)
    end = r.get('source', {}).get('end', 0.0)
    en = r.get('source', {}).get('text', '')
    ru = r.get('final_text', '')
    if 800.0 <= start <= 1250.0:
        d_id = r.get('dialogue_id')
        print(f"[{i:03d}] {d_id} ({start:7.2f}-{end:7.2f}): EN: {en}")
        print(f"      RU: {ru}")
