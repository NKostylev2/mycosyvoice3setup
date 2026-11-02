import json

with open(r'E:\AI-Dubbing-Subtitles\output\S01E01.timeline.final.json', 'r', encoding='utf-8') as f:
    tl_data = json.load(f)

print("=== ALL RECORDS MENTIONING BOGEYMAN OR JAVA OR MONSTER IN VD OR TEXT ===")
for i, r in enumerate(tl_data['records']):
    vd = r.get('translation', {}).get('voice_direction', '') or ''
    en = r.get('source', {}).get('text', '') or ''
    ru = r.get('final_text', '') or ''
    start = r.get('source', {}).get('start', 0)
    end = r.get('source', {}).get('end', 0)
    d_id = r.get('dialogue_id')
    combined = (vd + ' ' + en + ' ' + ru).lower()
    
    # check for bogeyman / java / monster / creature
    triggers = ['bogey', 'boogey', 'бугим', 'java', 'ява', 'джава', 'jabba', 'monster', 'монстр', 'чудовищ', 'грозн', 'рык', 'хрип', 'пещерн']
    if any(t in combined for t in triggers):
        print(f"[{i:03d}] {d_id} ({start:7.2f}-{end:7.2f}s | work_approx: {start+11.824:7.2f}-{end+11.824:7.2f}s)")
        print(f"      EN: {en}")
        print(f"      RU: {ru}")
        print(f"      VD: {vd}")
        print()
