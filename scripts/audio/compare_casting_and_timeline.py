import json

with open(r'E:\AI-Dubbing\work\S01E01\speaker_casting.json', 'r', encoding='utf-8') as f:
    cast_data = json.load(f)

with open(r'E:\AI-Dubbing-Subtitles\output\S01E01.timeline.final.json', 'r', encoding='utf-8') as f:
    tl_data = json.load(f)

print("=== SPEAKER CASTING: JAVA ===")
for u in cast_data.get('utterances', []):
    if 'java' in u.get('speaker_id', '').lower():
        print(f"{u['uid']}: {u['acoustic_start']:.2f} - {u['acoustic_end']:.2f} ({u['duration']:.2f}s) | {u.get('source_en')}")

print("\n=== SPEAKER CASTING: BOGEYMAN / MONSTER ===")
for u in cast_data.get('utterances', []):
    if any(k in u.get('speaker_id', '').lower() for k in ['bogey', 'monster']):
        print(f"{u['uid']}: {u['acoustic_start']:.2f} - {u['acoustic_end']:.2f} ({u['duration']:.2f}s) | {u.get('source_en')}")

print("\n=== TIMELINE FINAL: ALL 223 RECORDS (SCANNING FOR JAVA / BOGEYMAN CONTENT) ===")
# Let's inspect where Java or Bogeyman might be speaking in the episode!
records = tl_data.get('records', [])
for i, r in enumerate(records):
    d_id = r.get('dialogue_id', f'D{i:04d}')
    src = r.get('source', {})
    start = src.get('start', 0.0)
    end = src.get('end', 0.0)
    en = src.get('text', '')
    ru = r.get('final_text', '')
    # Check if context or characters or keywords suggest Java or Bogeyman
    print(f"[{i:03d}] {d_id} ({start:.2f}-{end:.2f}s | work_approx: {start+11.814:.2f}-{end+11.814:.2f}s): {en}")
