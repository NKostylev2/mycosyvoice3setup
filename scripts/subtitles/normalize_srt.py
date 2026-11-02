from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "input"
WORK_DIR = ROOT / "work"

TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
)

# Known character / role speaker indicators
KNOWN_SPEAKERS = {
    "martin", "diana", "java", "billy", "m.o.m.", "mom", "marvin", "jenni", "jenny",
    "gerard", "kaitlin", "clifford", "darla", "evan prince", "morcan", "octavia paine",
    "octavia", "samson", "bogeyman", "barok", "carlin", "venoso", "zook", "shaman",
    "narrator", "man", "woman", "boy", "girl", "teacher", "principal", "student",
    "students", "guard", "guards", "police", "officer", "announcer", "voice",
    "voiceover", "everyone", "all", "both", "crowd", "agent", "alien", "monster",
    "clerk", "receptionist", "doctor", "nurse", "reporter", "host", "child",
    "children", "kid", "kids", "captain", "mayor", "priest", "father", "mother",
    "dad", "nelson", "nelly", "billy & java", "martin & diana"
}

# Sound / Music / Applause / Non-speech vocabulary & patterns
MUSIC_KEYWORDS = {
    "music", "theme song", "theme music", "instrumental", "song", "singing",
    "rock music", "eerie music", "dramatic music", "upbeat music", "melody",
    "tune", "orchestral music", "pop music", "techno music", "jazz music"
}

APPLAUSE_KEYWORDS = {
    "applause", "cheering", "cheers", "crowd cheering", "applause and cheers",
    "clapping", "crowd applauds", "ovation"
}

NON_SPEECH_KEYWORDS = {
    "silence", "inaudible", "unintelligible", "pause", "static", "no audio",
    "muffled", "fade to black", "scene ends"
}

# Verbs / sound words that represent SFX rather than speakers
SFX_WORDS = {
    "laughter", "laughs", "laughing", "laugh", "giggle", "giggles", "giggling",
    "snicker", "snickers", "snickering", "chuckle", "chuckles", "chuckling",
    "gasp", "gasps", "gasping", "pant", "pants", "panting",
    "scream", "screams", "screaming", "shriek", "shrieks", "shrieking",
    "growl", "growls", "growling", "snarl", "snarls", "snarling",
    "roar", "roars", "roaring", "howl", "howls", "howling",
    "bark", "barks", "barking", "whimper", "whimpers", "whimpering",
    "sigh", "sighs", "sighing", "groan", "groans", "groaning",
    "grunt", "grunts", "grunting", "moan", "moans", "moaning",
    "sob", "sobs", "sobbing", "cry", "cries", "crying", "weep", "weeps", "weeping",
    "yell", "yells", "yelling", "shout", "shouts", "shouting",
    "cough", "coughs", "coughing", "sneeze", "sneezes", "sneezing",
    "throat clears", "clears throat", "gulp", "gulps", "gulping",
    "snort", "snorts", "snorting", "yawn", "yawns", "yawning",
    "whisper", "whispers", "whispering", "mutter", "mutters", "muttering",
    "door slams", "door closes", "door opens", "door creaks", "door knocks",
    "slam", "slams", "slamming", "creak", "creaks", "creaking",
    "knock", "knocks", "knocking", "footsteps", "footsteps approaching",
    "running", "explosion", "gunshot", "gunshots", "blast", "crash",
    "thud", "bang", "boom", "clatter", "thump",
    "phone rings", "phone ringing", "telephone rings", "cell phone rings",
    "alarm rings", "alarm blares", "bell rings", "bell dings", "siren wails",
    "tires screech", "screech", "screeches", "screeching",
    "car engine", "horn honks", "engine revs", "engine starts",
    "thunder", "lightning", "wind howls", "wind blowing", "splash", "splashing",
    "dripping", "bubbles", "bubbling", "glass breaks", "glass shatters",
    "rumble", "rumbling", "rattle", "rattling", "chirp", "chirping",
    "buzz", "buzzing", "whoosh", "squelch", "hiss", "hisses", "hissing",
    "beep", "beeps", "beeping", "ticking", "taps", "tapping",
    "rustle", "rustles", "rustling", "metal clangs"
}


def timestamp_to_seconds(value: str) -> float:
    value = value.replace(",", ".")
    h, m, s = value.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def clean_markup(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # HTML formatting
    text = re.sub(r"<\/?(?:i|b|u|s|font|span)(?:\s[^>]*)?>", "", text, flags=re.IGNORECASE)
    # ASS braces
    text = re.sub(r"\{[^}]*\}", "", text)
    # Consecutive whitespaces
    text = re.sub(r"[ \t]+", " ", text)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines).strip()


def is_sfx_token(token: str) -> bool:
    clean = token.strip().lower().strip(".,:;!?")
    if clean in SFX_WORDS:
        return True
    # Two-word phrases like "door slams", "tires screech", "wind blowing", "water dripping"
    words = clean.split()
    if len(words) == 2 and (words[1] in SFX_WORDS or words[1].endswith("s") or words[1].endswith("ing")):
        return True
    return False


def is_music_token(token: str) -> bool:
    clean = token.strip().lower().strip(".,:;!?")
    if "♪" in token or "♫" in token:
        return True
    if clean in MUSIC_KEYWORDS:
        return True
    for kw in MUSIC_KEYWORDS:
        if kw in clean:
            return True
    return False


def is_applause_token(token: str) -> bool:
    clean = token.strip().lower().strip(".,:;!?")
    if clean in APPLAUSE_KEYWORDS:
        return True
    for kw in APPLAUSE_KEYWORDS:
        if kw in clean:
            return True
    return False


def is_non_speech_token(token: str) -> bool:
    clean = token.strip().lower().strip(".,:;!?")
    if clean in NON_SPEECH_KEYWORDS:
        return True
    return False


def is_speaker_candidate(token: str) -> bool:
    clean = token.strip().lower().strip(".,:;!?")
    if is_music_token(token) or is_applause_token(token) or is_non_speech_token(token) or is_sfx_token(token):
        return False
    if clean in KNOWN_SPEAKERS:
        return True
    # Single capitalized token (e.g. "Billy", "Martin", "Diana", "Java", "Officer")
    if re.match(r"^[A-Z][a-zA-Z0-9_.\-]*$", token.strip()):
        return True
    # Short capitalized name or title (e.g. "Mr. Smith", "Captain Blood", "Evan Prince")
    if len(clean.split()) <= 3 and all(w[0].isupper() for w in token.strip().split() if w):
        return True
    return False


def classify_entry(raw_text: str) -> dict[str, Any]:
    cleaned = clean_markup(raw_text)
    if not cleaned:
        return {
            "raw_text": raw_text,
            "speech_text": "",
            "speaker_tag": None,
            "annotation": None,
            "event_type": "UNKNOWN",
            "is_dialogue": False,
            "is_hi_annotation": False,
            "is_sound_effect": False,
        }

    # Music note enclosure ♪ ... ♪
    if cleaned.startswith("♪") and cleaned.endswith("♪"):
        return {
            "raw_text": raw_text,
            "speech_text": "",
            "speaker_tag": None,
            "annotation": cleaned,
            "event_type": "MUSIC",
            "is_dialogue": False,
            "is_hi_annotation": True,
            "is_sound_effect": True,
        }

    # Check colon-based speaker prefix: e.g. "Billy: Hey! Over here!"
    colon_match = re.match(r"^([A-Za-z0-9_.\s\-]{1,30})\s*:\s*(.+)$", cleaned, re.DOTALL)
    if colon_match:
        cand_spk = colon_match.group(1).strip()
        rest_text = colon_match.group(2).strip()
        if is_speaker_candidate(cand_spk):
            # Recursively check rest_text for annotations
            sub_res = classify_entry(rest_text)
            return {
                "raw_text": raw_text,
                "speech_text": sub_res["speech_text"],
                "speaker_tag": cand_spk,
                "annotation": sub_res["annotation"],
                "event_type": "DIALOGUE_WITH_ANNOTATION" if sub_res["annotation"] else "DIALOGUE",
                "is_dialogue": True,
                "is_hi_annotation": sub_res["is_hi_annotation"],
                "is_sound_effect": sub_res["is_sound_effect"],
            }

    # Find all brackets [...] or (...)
    bracket_patterns = list(re.finditer(r"(\[([^\]]+)\]|\(([^)]+)\))", cleaned))

    # If the ENTIRE text is a single bracketed expression:
    if len(bracket_patterns) == 1 and bracket_patterns[0].start() == 0 and bracket_patterns[0].end() == len(cleaned):
        token_content = (bracket_patterns[0].group(2) or bracket_patterns[0].group(3)).strip()
        if is_music_token(token_content):
            return {
                "raw_text": raw_text,
                "speech_text": "",
                "speaker_tag": None,
                "annotation": cleaned,
                "event_type": "MUSIC",
                "is_dialogue": False,
                "is_hi_annotation": True,
                "is_sound_effect": True,
            }
        if is_applause_token(token_content):
            return {
                "raw_text": raw_text,
                "speech_text": "",
                "speaker_tag": None,
                "annotation": cleaned,
                "event_type": "APPLAUSE",
                "is_dialogue": False,
                "is_hi_annotation": True,
                "is_sound_effect": True,
            }
        if is_non_speech_token(token_content):
            return {
                "raw_text": raw_text,
                "speech_text": "",
                "speaker_tag": None,
                "annotation": cleaned,
                "event_type": "NON_SPEECH",
                "is_dialogue": False,
                "is_hi_annotation": True,
                "is_sound_effect": False,
            }
        if is_sfx_token(token_content):
            return {
                "raw_text": raw_text,
                "speech_text": "",
                "speaker_tag": None,
                "annotation": cleaned,
                "event_type": "SFX",
                "is_dialogue": False,
                "is_hi_annotation": True,
                "is_sound_effect": True,
            }
        # If not SFX, check if it's speaker alone (unusual, but e.g. [narrator])
        if is_speaker_candidate(token_content):
            return {
                "raw_text": raw_text,
                "speech_text": "",
                "speaker_tag": token_content,
                "annotation": None,
                "event_type": "UNKNOWN",
                "is_dialogue": False,
                "is_hi_annotation": False,
                "is_sound_effect": False,
            }
        # Fallback for other bracketed expressions: treat as SFX
        return {
            "raw_text": raw_text,
            "speech_text": "",
            "speaker_tag": None,
            "annotation": cleaned,
            "event_type": "SFX",
            "is_dialogue": False,
            "is_hi_annotation": True,
            "is_sound_effect": True,
        }

    # If text has brackets and remaining text:
    speaker_tag = None
    annotations = []
    speech_parts = []
    has_sound_effect = False
    has_hi_annotation = False

    last_idx = 0
    for match in bracket_patterns:
        start_idx, end_idx = match.span()
        # Text before bracket
        pre_text = cleaned[last_idx:start_idx].strip()
        if pre_text:
            speech_parts.append(pre_text)

        token = (match.group(2) or match.group(3)).strip()
        # Is this bracket at the very start acting as speaker tag?
        if last_idx == 0 and start_idx == 0 and is_speaker_candidate(token):
            speaker_tag = token
        else:
            # It's an annotation / SFX
            annotations.append(match.group(0))
            has_hi_annotation = True
            if is_music_token(token) or is_applause_token(token) or is_sfx_token(token):
                has_sound_effect = True
        last_idx = end_idx

    post_text = cleaned[last_idx:].strip()
    if post_text:
        speech_parts.append(post_text)

    speech_text = " ".join(speech_parts).strip()
    annotation_str = " ".join(annotations).strip() if annotations else None

    # Determine event_type
    if speech_text:
        if annotation_str:
            event_type = "DIALOGUE_WITH_ANNOTATION"
        else:
            event_type = "DIALOGUE"
        is_dialogue = True
    else:
        # No speech text extracted
        is_dialogue = False
        if any(is_music_token(a) for a in annotations):
            event_type = "MUSIC"
            has_sound_effect = True
        elif any(is_applause_token(a) for a in annotations):
            event_type = "APPLAUSE"
            has_sound_effect = True
        elif any(is_sfx_token(a) for a in annotations):
            event_type = "SFX"
            has_sound_effect = True
        elif any(is_non_speech_token(a) for a in annotations):
            event_type = "NON_SPEECH"
        else:
            event_type = "UNKNOWN"

    return {
        "raw_text": raw_text,
        "speech_text": speech_text,
        "speaker_tag": speaker_tag,
        "annotation": annotation_str,
        "event_type": event_type,
        "is_dialogue": is_dialogue,
        "is_hi_annotation": has_hi_annotation or (annotation_str is not None),
        "is_sound_effect": has_sound_effect,
    }


def parse_srt(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", raw.strip())
    entries = []

    for block_index, block in enumerate(blocks, start=1):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        ts_match = None
        ts_idx = None
        for i, line in enumerate(lines):
            m = TIMESTAMP_RE.search(line)
            if m:
                ts_match = m
                ts_idx = i
                break
        if not ts_match:
            continue

        start_str = ts_match.group("start")
        end_str = ts_match.group("end")
        start = timestamp_to_seconds(start_str)
        end = timestamp_to_seconds(end_str)
        raw_text = "\n".join(lines[ts_idx + 1:])

        cls_info = classify_entry(raw_text)

        entry = {
            "index": len(entries) + 1,
            "source_block": block_index,
            "start": start,
            "end": end,
            "duration": round(end - start, 3),
            "source_timestamp": f"{start_str} --> {end_str}",
            "raw_text": cls_info["raw_text"],
            "speech_text": cls_info["speech_text"],
            "speaker_tag": cls_info["speaker_tag"],
            "annotation": cls_info["annotation"],
            "event_type": cls_info["event_type"],
            "is_dialogue": cls_info["is_dialogue"],
            "is_hi_annotation": cls_info["is_hi_annotation"],
            "is_sound_effect": cls_info["is_sound_effect"],
        }
        entries.append(entry)

    return entries


def main() -> None:
    episode_key = sys.argv[1] if len(sys.argv) > 1 else "S01E01"
    srt_path = INPUT_DIR / f"{episode_key}.en.hi.srt"
    work_dir = WORK_DIR / episode_key
    work_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = work_dir / "media_manifest.json"
    video_duration = 0.0
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        video_duration = float(manifest.get("media", {}).get("duration_seconds", 0.0))

    print(f"=== SRT NORMALIZATION 2.0: {episode_key} ===")
    print(f"Input SRT: {srt_path}")

    entries = parse_srt(srt_path)
    if not entries:
        print("ERROR: No entries parsed from SRT!")
        sys.exit(1)

    print(f"Parsed {len(entries)} entries.")

    # Validation and Report Gathering
    event_counts: dict[str, int] = {}
    speaker_counts: dict[str, int] = {}
    pure_sfx_count = 0
    dialogue_with_annotations_count = 0
    empty_speech_dialogue = []
    short_duration_entries = []
    malformed_entries = []
    overlaps = []

    prev_end = None
    for e in entries:
        ev = e["event_type"]
        event_counts[ev] = event_counts.get(ev, 0) + 1

        if e["speaker_tag"]:
            spk = e["speaker_tag"]
            speaker_counts[spk] = speaker_counts.get(spk, 0) + 1

        if ev == "SFX":
            pure_sfx_count += 1
        elif ev == "DIALOGUE_WITH_ANNOTATION":
            dialogue_with_annotations_count += 1

        if e["is_dialogue"] and not e["speech_text"]:
            empty_speech_dialogue.append(e["index"])

        if e["duration"] < 0.2:
            short_duration_entries.append({"index": e["index"], "duration": e["duration"]})

        if e["end"] <= e["start"] or e["start"] < 0:
            malformed_entries.append({"index": e["index"], "start": e["start"], "end": e["end"]})

        if prev_end is not None and e["start"] < prev_end:
            overlaps.append({"index": e["index"], "prev_end": prev_end, "start": e["start"]})
        prev_end = e["end"]

    # Output files
    output_normalized = work_dir / "normalized_subtitles_v2.json"
    output_report = work_dir / "subtitle_report_v2.json"

    payload = {
        "schema_version": "2.0",
        "episode_key": episode_key,
        "source_file": str(srt_path.relative_to(ROOT)),
        "language": "en",
        "hearing_impaired": True,
        "entry_count": len(entries),
        "entries": entries,
    }

    report = {
        "schema_version": "2.0",
        "episode_key": episode_key,
        "entry_count": len(entries),
        "first_start": entries[0]["start"],
        "last_end": entries[-1]["end"],
        "covered_duration": round(entries[-1]["end"] - entries[0]["start"], 3),
        "video_duration": video_duration,
        "event_counts": event_counts,
        "speaker_counts": speaker_counts,
        "pure_sfx_count": pure_sfx_count,
        "dialogue_with_annotations_count": dialogue_with_annotations_count,
        "overlaps_count": len(overlaps),
        "overlaps": overlaps,
        "malformed_entries": malformed_entries,
        "suspiciously_short_duration_entries": short_duration_entries,
        "empty_speech_dialogue_entries": empty_speech_dialogue,
    }

    output_normalized.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Normalized subtitles v2 written: {output_normalized}")
    print(f"Subtitle report v2 written: {output_report}")
    print("Event distribution:")
    for ev, c in sorted(event_counts.items()):
        print(f"  {ev}: {c}")
    print(f"Speaker tags detected: {len(speaker_counts)} unique ({sum(speaker_counts.values())} occurrences)")
    print(f"Overlaps count: {len(overlaps)}")
    print(f"Malformed entries: {len(malformed_entries)}")
    print("SRT NORMALIZATION 2.0 COMPLETE (PASS)")


if __name__ == "__main__":
    main()