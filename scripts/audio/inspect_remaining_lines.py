import json

with open(r"E:\AI-Dubbing\work\S01E01\speaker_casting.json", "r", encoding="utf-8") as f:
    casting = json.load(f)

target_speakers = {"character_nelly", "character_ians_mother", "character_townsperson", "java", "monster_bogeyman", "billy"}

for u in casting["utterances"]:
    spk = u.get("speaker_id")
    if spk in target_speakers:
        uid = u["uid"]
        en = u.get("source_en", "")
        ru = u.get("text_ru", "")
        print(f"[{spk}] {uid}:")
        print(f"  EN: {en}")
        print(f"  RU: {ru}")
