import json

with open(r'E:\AI-Dubbing-Subtitles\output\S01E01.timeline.final.json', 'r', encoding='utf-8') as f:
    tl_data = json.load(f)

for r in tl_data['records']:
    start = r.get('source', {}).get('start', 0)
    if 940 <= start <= 975:
        print(f"[{r.get('dialogue_id')}] ({start:.2f} - {r.get('source',{}).get('end',0):.2f}) EN: {r.get('source',{}).get('text')}")
        print(f"       RU: {r.get('final_text')}")
