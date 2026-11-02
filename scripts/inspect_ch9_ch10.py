import sys
import json
from fanfic_pipeline.robsten_scraper import get_chapter_sections

res = {}
for c in [9, 10]:
    d = get_chapter_sections(c)
    res[c] = {
        "title": d["title"],
        "sections": [
            {
                "pov": s["pov"],
                "chars": len(s["text"]),
                "preview": s["text"][:120],
                "end": s["text"][-120:]
            }
            for s in d["sections"]
        ]
    }

with open("E:/AI-Dubbing/output/wide_awake/inspect_ch9_ch10.json", "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)

print("Saved inspect_ch9_ch10.json")
