#!/usr/bin/env python3
"""
scripts/audio/extract_translation_packages.py

Deterministic Fact Extractor for Phase 6 (Translation & Dubbing Adaptation).
Assembles objective translation packages for all 154 canonical dialogue utterances
and 10 non-dialogue VAD events in S01E01.

Guarantees:
  - Purely deterministic extraction of facts and conversational context.
  - ZERO translation text, decisions, or subjective assumptions.
  - Generates work/S01E01/translation_packages.json.
"""

import os
import sys
import json
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = r"E:\AI-Dubbing"
WORK_DIR = os.path.join(PROJECT_ROOT, r"work\S01E01")
DB_PATH = os.path.join(PROJECT_ROOT, r"database\dubbing.db")

CANONICAL_FINAL_PATH = os.path.join(WORK_DIR, "canonical_dialogue_final.json")
OUTPUT_PACKAGES_PATH = os.path.join(WORK_DIR, "translation_packages.json")


def load_canonical_db_terms():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    characters = {}
    for r in cur.execute("SELECT character_id, name_original, name_ru, description FROM characters").fetchall():
        characters[r["character_id"]] = {
            "name_original": r["name_original"],
            "name_ru": r["name_ru"],
            "description": r["description"]
        }

    entities = {}
    for r in cur.execute("SELECT entity_id, entity_type, name_original, name_ru, description FROM entities").fetchall():
        entities[r["entity_id"]] = {
            "entity_type": r["entity_type"],
            "name_original": r["name_original"],
            "name_ru": r["name_ru"],
            "description": r["description"]
        }

    conn.close()
    return characters, entities


def main():
    print("=" * 60)
    print("PHASE 6: EXTRACTING OBJECTIVE TRANSLATION PACKAGES")
    print("=" * 60)

    if not os.path.exists(CANONICAL_FINAL_PATH):
        print(f"ERROR: Missing canonical dialogue file: {CANONICAL_FINAL_PATH}")
        sys.exit(1)

    with open(CANONICAL_FINAL_PATH, 'r', encoding='utf-8') as f:
        canonical_data = json.load(f)

    db_characters, db_entities = load_canonical_db_terms()
    utterances = canonical_data.get("utterances", [])
    print(f"Loaded {len(utterances)} canonical utterances.")

    packages = []
    for i, u in enumerate(utterances):
        u_id = u["utterance_id"]
        speaker = u["speaker"]
        char_id = speaker.get("character_id")
        speaker_name = speaker.get("name")
        canonical_text = u["text"]["reconstructed"]
        timing = u["timing"]

        # Conversational context
        prev_ctx = None
        if i > 0:
            p_u = utterances[i - 1]
            prev_ctx = {
                "utterance_id": p_u["utterance_id"],
                "speaker": p_u["speaker"]["name"],
                "text": p_u["text"]["reconstructed"]
            }

        next_ctx = None
        if i < len(utterances) - 1:
            n_u = utterances[i + 1]
            next_ctx = {
                "utterance_id": n_u["utterance_id"],
                "speaker": n_u["speaker"]["name"],
                "text": n_u["text"]["reconstructed"]
            }

        is_blocked = (u_id in ("U0058", "U0098")) or (u["semantic"]["status"] == "AMBIGUOUS")

        # Check for canonical terms mentioned
        terms_in_utterance = []
        lower_text = canonical_text.lower()
        for ent_id, ent_info in db_entities.items():
            if ent_info["name_original"].lower() in lower_text:
                terms_in_utterance.append({
                    "entity_id": ent_id,
                    "original": ent_info["name_original"],
                    "canonical_ru": ent_info["name_ru"]
                })

        for c_id, c_info in db_characters.items():
            if c_info["name_original"].lower() in lower_text:
                terms_in_utterance.append({
                    "character_id": c_id,
                    "original": c_info["name_original"],
                    "canonical_ru": c_info["name_ru"]
                })

        pkg = {
            "utterance_id": u_id,
            "speaker_id": char_id,
            "speaker_name": speaker_name,
            "speaker_status": speaker.get("status"),
            "canonical_text": canonical_text,
            "acoustic_start": timing["acoustic_start"],
            "acoustic_end": timing["acoustic_end"],
            "duration": timing["duration"],
            "context_previous": prev_ctx,
            "context_next": next_ctx,
            "matched_terms": terms_in_utterance,
            "translation_blocked": is_blocked,
            "semantic_status": u["semantic"]["status"]
        }
        packages.append(pkg)

    # Extract the 10 VAD Non-Dialogue events
    unmatched_vad = []
    for e in canonical_data.get("unmatched_source_events", []):
        if e.get("review_status") == "RESOLVED_AS_VAD_NON_DIALOGUE":
            meta = e.get("review_metadata", {})
            unmatched_vad.append({
                "dialogue_id": e["dialogue_id"],
                "srt_text": e.get("speech_text", ""),
                "speaker": meta.get("speaker"),
                "reasoning": meta.get("reasoning"),
                "evidence_used": meta.get("evidence_used"),
                "srt_start": e.get("srt_start"),
                "srt_end": e.get("srt_end")
            })

    print(f"Extracted {len(packages)} dialogue packages and {len(unmatched_vad)} VAD events.")

    output_data = {
        "schema_version": "1.0.0",
        "episode": canonical_data["episode"],
        "title": canonical_data["title"],
        "total_utterances": len(packages),
        "total_vad_events": len(unmatched_vad),
        "db_canonical_characters": db_characters,
        "db_canonical_entities": db_entities,
        "packages": packages,
        "vad_events": unmatched_vad
    }

    with open(OUTPUT_PACKAGES_PATH, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"Successfully written: {OUTPUT_PACKAGES_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
