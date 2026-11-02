import json
from pathlib import Path

casting_file = Path(r"E:\AI-Dubbing\work\S01E01\speaker_casting.json")
with open(casting_file, "r", encoding="utf-8") as f:
    data = json.load(f)

print("Librarian / Nelly's Father utterances:")
for u in data.get("utterances", []):
    if u.get("speaker_id") == "character_librarian":
        print(f"  {u['uid']}: [{u['acoustic_start']:.2f} - {u['acoustic_end']:.2f}] ({u['duration']:.2f}s) \"{u['source_en']}\"")
