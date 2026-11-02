import json
import soundfile as sf
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r"E:\AI-Dubbing")
WORK_DIR = PROJECT_ROOT / "work" / "S01E01"
CASTING_PATH = WORK_DIR / "speaker_casting.json"
VOICES_DIR = PROJECT_ROOT / "alltalk_tts" / "voices"

with open(CASTING_PATH, "r", encoding="utf-8") as f:
    casting = json.load(f)

u_map = {u["uid"]: u for u in casting["utterances"]}

print("Martin candidates:")
for uid in ["U0010", "U0044", "U0051", "U0062", "U0063", "U0087", "U0153"]:
    u = u_map.get(uid, {})
    print(f"  {uid}: '{u.get('source_en', u.get('text_en'))}' -> '{u.get('text_ru')}'")

print("\nDiana candidates:")
for uid in ["U0009", "U0030", "U0043", "U0094", "U0111", "U0122", "U0141"]:
    u = u_map.get(uid, {})
    print(f"  {uid}: '{u.get('source_en', u.get('text_en'))}' -> '{u.get('text_ru')}'")
