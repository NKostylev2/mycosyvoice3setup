# Transcribe test slice with faster_whisper or inspect words
import json
with open(r'E:\AI-Dubbing-Subtitles\output\S01E01.timeline.final.json', 'r', encoding='utf-8') as f:
    tl_data = json.load(f)

for r in tl_data['records']:
    if r.get('dialogue_id') == 'D0187':
        print("Record D0187 details:")
        print(json.dumps(r, ensure_ascii=False, indent=2))
