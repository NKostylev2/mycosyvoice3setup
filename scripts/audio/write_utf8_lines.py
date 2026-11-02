import json

with open(r'E:\AI-Dubbing-Subtitles\output\S01E01.timeline.final.json', 'r', encoding='utf-8') as f:
    tl_data = json.load(f)

records = tl_data['records']

with open(r'E:\AI-Dubbing\work\timeline_all_lines.txt', 'w', encoding='utf-8') as out:
    for i, r in enumerate(records):
        d_id = r.get('dialogue_id')
        en = r.get('source', {}).get('text', '')
        start = r.get('source', {}).get('start', 0)
        end = r.get('source', {}).get('end', 0)
        dur = end - start
        out.write(f"[{i:03d}] {d_id} ({start:7.2f}-{end:7.2f}, dur={dur:4.2f}s): {en}\n")

print("Written utf-8 file.")
