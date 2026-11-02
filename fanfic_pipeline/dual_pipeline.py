"""
Dual-Voice Fanfic Dubbing Pipeline (Wide Awake).
Alternates between Bella Swan (female_03.wav) and Edward Cullen (male_05.wav)
with natural pauses (sentence: 250ms, paragraph: 650ms, POV switch: 1500ms, intro: 850ms).
Includes spoken character announcements:
  - First section of chapter: "Глава первая, часть первая. Белла."
  - Subsequent sections: "Часть вторая. Эдвард."
"""

import os
import sys
import json
import argparse
import time
import subprocess
from typing import List, Dict, Tuple, Optional
import torch
import torchaudio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = r"E:\AI-Dubbing"
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fanfic_pipeline.config import (
    WORK_DIR,
    OUTPUT_DIR,
    POV_PROFILES,
    BASE_DIR,
)
from fanfic_pipeline.segmenter import SentenceSegmenter
from fanfic_pipeline.tts_worker import CosyVoiceWorker
from fanfic_pipeline.robsten_scraper import get_chapter_sections
from fanfic_pipeline.number_words import get_section_announcement

FFMPEG_EXE = os.path.join(BASE_DIR, "vendor", "ffmpeg", "bin", "ffmpeg.exe")


def process_section_tts(
    sec_idx: int,
    pov: str,
    paragraphs: List[str],
    sec_dir: str,
    worker: CosyVoiceWorker,
    announcement_text: Optional[str] = None,
    force_tts: bool = False,
) -> Tuple[List[Dict], List[str], Optional[str]]:
    profile = POV_PROFILES[pov]
    os.makedirs(sec_dir, exist_ok=True)

    # Configure worker for this section's voice and prompt
    worker.voice_path = profile["voice"]
    worker.instruct = profile["tts_instruct"]

    with open(os.path.join(sec_dir, "paragraphs.txt"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(paragraphs))

    print(f"\n" + "=" * 60)
    print(f"[SEC {sec_idx + 1:02d} - {pov.upper()}] {profile['pov_desc']}")
    print(f"Voice: {os.path.basename(profile['voice'])}")
    if announcement_text:
        print(f"Intro Announcement: '{announcement_text}'")
    print(f"Paragraphs: {len(paragraphs)}, chars: {sum(len(p) for p in paragraphs)}")
    print("=" * 60)

    # 1. Synthesize announcement if provided
    announcement_file = None
    if announcement_text:
        announcement_file = os.path.join(sec_dir, "intro_announcement.wav")
        announcement_txt = os.path.join(sec_dir, "intro_announcement.txt")
        text_matches = False
        if os.path.exists(announcement_txt):
            try:
                with open(announcement_txt, "r", encoding="utf-8") as f:
                    text_matches = (f.read().strip() == announcement_text.strip())
            except Exception:
                text_matches = False

        if force_tts or not text_matches or not os.path.exists(announcement_file) or os.path.getsize(announcement_file) < 1000:
            print(f"[Announcement] Synthesizing: {announcement_text}")
            worker.synthesize_sentence(announcement_text, announcement_file)
            with open(announcement_txt, "w", encoding="utf-8") as f:
                f.write(announcement_text.strip())
        else:
            print(f"[Announcement] Reusing existing: {announcement_file}")

    # 2. Segment sentences into 50-160 char speech breath groups
    segments_file = os.path.join(sec_dir, "segments.json")
    segmenter = SentenceSegmenter()
    segments = segmenter.segment_chapter(paragraphs)

    with open(segments_file, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    print(f"[SEC {sec_idx + 1:02d} - {pov.upper()}] Total segments: {len(segments)}")

    # 3. Synthesize with CosyVoice 3
    audio_dir = os.path.join(sec_dir, "audio_segments")
    if force_tts and os.path.exists(audio_dir):
        import shutil
        shutil.rmtree(audio_dir)
    os.makedirs(audio_dir, exist_ok=True)

    segment_files = worker.synthesize_segments(segments, audio_dir, skip_existing=not force_tts)
    return segments, segment_files, announcement_file


def assemble_multi_section_chapter(
    sections_data: List[Tuple[Dict, List[Dict], List[str], Optional[str]]],
    final_wav_path: str,
    sample_rate: int = 24000,
    pause_sentence_ms: int = 250,
    pause_paragraph_ms: int = 650,
    pause_intro_ms: int = 850,
    pause_pov_transition_ms: int = 1500,
) -> str:
    print(f"\n[Assembly] Merging {len(sections_data)} POV sections into {final_wav_path}...")
    os.makedirs(os.path.dirname(os.path.abspath(final_wav_path)), exist_ok=True)

    silence_sentence = torch.zeros((1, int(sample_rate * pause_sentence_ms / 1000)))
    silence_para = torch.zeros((1, int(sample_rate * pause_paragraph_ms / 1000)))
    silence_intro = torch.zeros((1, int(sample_rate * pause_intro_ms / 1000)))
    silence_pov = torch.zeros((1, int(sample_rate * pause_pov_transition_ms / 1000)))

    audio_chunks = []

    for s_idx, (sec_meta, segs, files, intro_file) in enumerate(sections_data):
        print(f"  Adding Section {s_idx + 1}/{len(sections_data)} ({sec_meta['pov']}): {len(files)} files")

        # 1. Add intro announcement if present
        if intro_file and os.path.exists(intro_file):
            w_intro, sr_in = torchaudio.load(intro_file)
            if sr_in != sample_rate:
                w_intro = torchaudio.functional.resample(w_intro, sr_in, sample_rate)
            if w_intro.dim() == 1:
                w_intro = w_intro.unsqueeze(0)
            elif w_intro.shape[0] > 1:
                w_intro = w_intro.mean(dim=0, keepdim=True)
            audio_chunks.append(w_intro)
            audio_chunks.append(silence_intro)

        # 2. Add story segments
        for seg, fpath in zip(segs, files):
            if not os.path.exists(fpath):
                continue
            wav, sr = torchaudio.load(fpath)
            if sr != sample_rate:
                wav = torchaudio.functional.resample(wav, sr, sample_rate)
            if wav.dim() == 1:
                wav = wav.unsqueeze(0)
            elif wav.shape[0] > 1:
                wav = wav.mean(dim=0, keepdim=True)
            audio_chunks.append(wav)
            if seg.get("is_last_in_p", False):
                audio_chunks.append(silence_para)
            else:
                audio_chunks.append(silence_sentence)

        # 3. Add POV transition pause between sections
        if s_idx < len(sections_data) - 1:
            print("  [POV Switch Silence: 1.5s]")
            audio_chunks.append(silence_pov)

    full_wav = torch.cat(audio_chunks, dim=1)
    torchaudio.save(final_wav_path, full_wav, sample_rate)
    total_sec = full_wav.shape[1] / sample_rate
    print(f"[Assembly] Complete! Total duration: {total_sec / 60:.2f} min ({total_sec:.1f}s)")

    if os.path.exists(FFMPEG_EXE):
        mp3_path = os.path.splitext(final_wav_path)[0] + ".mp3"
        print(f"[Assembly] Converting to MP3: {mp3_path}...")
        cmd = [FFMPEG_EXE, "-y", "-i", final_wav_path, "-codec:a", "libmp3lame", "-b:a", "192k", mp3_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(mp3_path):
            print(f"[Assembly] MP3 ready: {mp3_path}")
            return mp3_path

    return final_wav_path


def run_robsten_chapter(chapter_num: int, force_tts: bool = False, max_sections: int = None):
    print("=" * 65)
    print(f"ROBSTEN DUAL-POV PIPELINE: Chapter {chapter_num}")
    print("=" * 65)

    data = get_chapter_sections(chapter_num, apply_censor=True)
    title = data["title"]
    sections = data["sections"]
    if max_sections:
        sections = sections[:max_sections]

    print(f"Chapter {chapter_num}: {data['header']} - {title}")
    print(f"Total sections: {len(sections)}")
    for i, s in enumerate(sections):
        reps = s.get("censor_reps", [])
        reps_str = f" | Censored: {len(reps)}" if reps else ""
        print(f"  Sec {i+1} [{s['pov']}]: {s['char_count']} chars{reps_str} | Starts: {s['text'][:50]}...")
        if reps:
            print(f"    Replacements: {', '.join(reps)}")

    ch_work_dir = os.path.join(WORK_DIR, f"chapter_{chapter_num:02d}_robsten")
    os.makedirs(ch_work_dir, exist_ok=True)

    # Initialize worker once (keeps model resident in VRAM)
    worker = CosyVoiceWorker()

    sections_data = []
    for i, s in enumerate(sections):
        sec_dir = os.path.join(ch_work_dir, f"sec_{i:02d}_{s['pov']}")
        paragraphs = [p.strip() for p in s["text"].split("\n\n") if p.strip()]

        # Generate character announcement:
        # Sec 0 (start of chapter): "Глава первая, часть первая. Белла."
        # Sec > 0: "Часть вторая. Эдвард."
        announcement_text = get_section_announcement(chapter_num, i, s["pov"])

        segs, files, intro_file = process_section_tts(
            sec_idx=i,
            pov=s["pov"],
            paragraphs=paragraphs,
            sec_dir=sec_dir,
            worker=worker,
            announcement_text=announcement_text,
            force_tts=force_tts,
        )
        sections_data.append((s, segs, files, intro_file))

    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title).strip()
    final_wav = os.path.join(OUTPUT_DIR, f"Chapter_{chapter_num:02d}_{safe_title}.wav")
    final_output = assemble_multi_section_chapter(
        sections_data=sections_data,
        final_wav_path=final_wav,
        sample_rate=worker.sample_rate,
    )

    print("\n" + "=" * 65)
    print(f"CHAPTER {chapter_num} COMPLETED! Audio: {final_output}")
    print("=" * 65)
    return final_output


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Multi-POV Fanfic Dubbing (Robsten / Dual Voice)")
    cli.add_argument("--chapter", type=int, required=True, help="Chapter number")
    cli.add_argument("--force_tts", action="store_true", help="Force re-synthesis")
    cli.add_argument("--max_sections", type=int, default=None, help="Limit number of sections to process")
    args = cli.parse_args()

    run_robsten_chapter(chapter_num=args.chapter, force_tts=args.force_tts, max_sections=args.max_sections)
