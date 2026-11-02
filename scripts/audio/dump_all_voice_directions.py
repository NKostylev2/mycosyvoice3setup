import json

with open(r'E:\AI-Dubbing-Subtitles\output\S01E01.timeline.final.json', 'r', encoding='utf-8') as f:
    tl_data = json.load(f)

print("Searching for Bogeyman and Java in all 223 records...")
for i, r in enumerate(tl_data['records']):
    vd = r.get('translation', {}).get('voice_direction', '')
    en = r.get('source', {}).get('text', '')
    ru = r.get('final_text', '')
    start = r.get('source', {}).get('start', 0)
    end = r.get('source', {}).get('end', 0)
    d_id = r.get('dialogue_id')
    facts = str(r.get('context', {}).get('episode_facts', []))
    
    # print all records with voice direction
    print(f"[{i:03d}] {d_id} ({start:.2f}-{end:.2f}s): {en}")
    print(f"      VD: {vd}")
    print(f"      RU: {ru}")
