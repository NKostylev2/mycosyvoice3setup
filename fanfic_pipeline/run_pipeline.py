import os
import sys
import json
import argparse
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure workspace root is in sys.path
BASE_DIR = r"E:\AI-Dubbing"
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fanfic_pipeline.config import (
    WORK_DIR,
    OUTPUT_DIR,
    DEFAULT_VOICE,
    VOICES_DIR,
    POV_PROFILES,
)
from fanfic_pipeline.pdf_parser import FanficPDFParser
from fanfic_pipeline.translator import ChapterTranslator
from fanfic_pipeline.segmenter import SentenceSegmenter

def resolve_voice_path(voice_arg: str, default_voice: str = DEFAULT_VOICE) -> str:
    if not voice_arg:
        return default_voice
    if os.path.isabs(voice_arg) and os.path.exists(voice_arg):
        return voice_arg
    candidate = os.path.join(VOICES_DIR, voice_arg)
    if os.path.exists(candidate):
        return candidate
    candidate_wav = os.path.join(VOICES_DIR, f"{voice_arg}.wav")
    if os.path.exists(candidate_wav):
        return candidate_wav
    # Aliases
    if voice_arg.lower() in ["female3", "female_3"]:
        return os.path.join(VOICES_DIR, "female_03.wav")
    if voice_arg.lower() in ["male5", "male_5"]:
        return os.path.join(VOICES_DIR, "male_05.wav")
    return default_voice

def process_chapter(
    chapter_num: int = 1,
    limit_paragraphs: int = None,
    pov: str = "bella",
    voice: str = None,
    steps: str = "all",
    force_tts: bool = False,
):
    profile = POV_PROFILES.get(pov.lower(), POV_PROFILES["bella"])
    default_voice = profile["voice"]
    voice_path = resolve_voice_path(voice, default_voice)
    tts_instruct = profile["tts_instruct"]

    print("=" * 60)
    print(f"FANFIC PIPELINE: Chapter {chapter_num}")
    print(f"POV Narrator: {profile['pov_desc']}")
    print(f"Reference voice: {voice_path}")
    print("=" * 60)

    ch_dir = os.path.join(WORK_DIR, f"chapter_{chapter_num:02d}")
    os.makedirs(ch_dir, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. EXTRACT FROM PDF
    parser = FanficPDFParser()
    info, full_text_en = parser.extract_chapter_text(chapter_num)
    paragraphs = full_text_en.split("\n\n")
    if limit_paragraphs:
        paragraphs = paragraphs[:limit_paragraphs]
        print(f"[Extractor] Limited to first {limit_paragraphs} paragraphs for testing.")

    with open(os.path.join(ch_dir, "chapter_info.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    with open(os.path.join(ch_dir, "original_en.txt"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(paragraphs))

    print(f"[Extractor] Chapter {chapter_num}: '{info['title']}'")
    print(f"[Extractor] Total paragraphs: {len(paragraphs)}, chars: {sum(len(p) for p in paragraphs)}")

    if steps == "extract":
        return

    # 2. TRANSLATE TO RUSSIAN
    cache_file = os.path.join(ch_dir, "translation_cache.json")
    translated_txt_file = os.path.join(ch_dir, "translated_ru.txt")

    translator = ChapterTranslator(pov=pov)
    translated_paragraphs = translator.translate_paragraphs(paragraphs, cache_file=cache_file)

    with open(translated_txt_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(translated_paragraphs))

    print(f"[Translator] Translation complete. Saved to {translated_txt_file}")

    if steps == "translate":
        return

    # 3. SEGMENT INTO SENTENCES
    segments_file = os.path.join(ch_dir, "segments.json")
    segmenter = SentenceSegmenter()
    segments = segmenter.segment_chapter(translated_paragraphs)

    with open(segments_file, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    print(f"[Segmenter] Total sentence segments: {len(segments)}")

    if steps == "segment":
        return

    # 4. SYNTHESIZE WITH COSYVOICE 3
    from fanfic_pipeline.tts_worker import CosyVoiceWorker
    worker = CosyVoiceWorker(voice_path=voice_path, instruct=tts_instruct)

    audio_segments_dir = os.path.join(ch_dir, "audio_segments")
    if force_tts and os.path.exists(audio_segments_dir):
        import shutil
        shutil.rmtree(audio_segments_dir)
        os.makedirs(audio_segments_dir, exist_ok=True)

    segment_files = worker.synthesize_segments(segments, audio_segments_dir, skip_existing=not force_tts)

    if steps == "tts":
        return

    # 5. ASSEMBLE
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in info['title']).strip()
    final_wav = os.path.join(OUTPUT_DIR, f"Chapter_{chapter_num:02d}_{safe_title}.wav")
    final_output = worker.assemble_audio(segments, segment_files, final_wav)
    print("\n" + "=" * 60)
    print(f"PIPELINE COMPLETED! Chapter audio: {final_output}")
    print("=" * 60)

if __name__ == "__main__":
    cli_parser = argparse.ArgumentParser(description="Fanfic Dubbing Pipeline")
    cli_parser.add_argument("--chapter", type=int, default=1, help="Chapter number (default: 1)")
    cli_parser.add_argument("--limit_paragraphs", type=int, default=None, help="Limit paragraphs for fast test")
    cli_parser.add_argument("--pov", type=str, default="bella", choices=["bella", "edward"], help="POV character (bella or edward)")
    cli_parser.add_argument("--voice", type=str, default=None, help="Voice name or WAV path (default depends on POV)")
    cli_parser.add_argument("--steps", type=str, default="all", choices=["all", "extract", "translate", "segment", "tts", "assemble"])
    cli_parser.add_argument("--force_tts", action="store_true", help="Force re-synthesis of all segments")
    args = cli_parser.parse_args()

    process_chapter(
        chapter_num=args.chapter,
        limit_paragraphs=args.limit_paragraphs,
        pov=args.pov,
        voice=args.voice,
        steps=args.steps,
        force_tts=args.force_tts,
    )
