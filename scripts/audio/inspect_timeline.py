import json

path = r"E:\AI-Dubbing-Subtitles\output\S01E01.timeline.final.json"
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

print("Keys in top level:", list(data.keys()))
print("Record count:", len(data.get("records", [])))

records = data.get("records", [])

# Let's inspect what fields records have
for i in range(min(5, len(records))):
    r = records[i]
    print(f"\n--- Record {i} ({r.get('dialogue_id')}) ---")
    for k, v in r.items():
        if k in ("source", "whisperx", "character", "context", "translation", "final_text"):
            print(f"  {k}: {v}")

# Let's search for "Java" or "Bogeyman" across all records
print("\n--- Searching for keywords across all records ---")
for i, r in enumerate(records):
    raw_str = json.dumps(r, ensure_ascii=False).lower()
    for kw in ["bogeyman", "boogeyman", "бугимен", "java", "ява"]:
        if kw in raw_str:
            print(f"Record {i} ({r.get('dialogue_id')}): kw='{kw}' | start={r.get('source', {}).get('start')} | text_en='{r.get('source', {}).get('text')}' | text_ru='{r.get('final_text', r.get('translation', {}).get('ru_adapted'))}'")
