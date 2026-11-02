import json
from collections import defaultdict

with open(r"E:\AI-Dubbing\work\S01E01\speaker_casting.json", "r", encoding="utf-8") as f:
    casting = json.load(f)

character_spans = defaultdict(list)

for u in casting.get("utterances", []):
    spans = u.get("speaker_spans", [])
    if spans:
        for s in spans:
            spk = s.get("speaker_id")
            character_spans[spk].append({
                "span_id": s.get("span_id", u["uid"]),
                "start": s.get("acoustic_start", u["acoustic_start"]),
                "end": s.get("acoustic_end", u["acoustic_end"]),
                "duration": s.get("duration", s.get("acoustic_end", 0) - s.get("acoustic_start", 0)),
                "text_en": s.get("source_en", ""),
                "text_ru": s.get("text_ru", "")
            })
    else:
        spk = u.get("speaker_id")
        character_spans[spk].append({
            "span_id": u["uid"],
            "start": u["acoustic_start"],
            "end": u["acoustic_end"],
            "duration": u["duration"],
            "text_en": u.get("source_en", ""),
            "text_ru": u.get("text_ru", "")
        })

print("=" * 60)
print("  All Characters in S01E01")
print("=" * 60)
for spk, items in sorted(character_spans.items(), key=lambda x: len(x[1]), reverse=True):
    tot_dur = sum(x["duration"] for x in items)
    print(f"{spk:25s} | {len(items):3d} spans | {tot_dur:6.2f}s ({tot_dur/60:4.2f} min)")
