"""
Batch Runner for Wide Awake audiobook generation.
Synthesizes specified chapters, merges them into a combined audio file,
and generates Full HD 1080p MP4 videos with cover art using NVENC GPU acceleration.
Keeps CosyVoice model resident in GPU memory across all chapters.
"""

import os
import sys
import json
import time
import argparse
import subprocess
import torch
import torchaudio
from typing import List, Dict, Tuple, Optional

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
    BASE_DIR,
)
from fanfic_pipeline.tts_worker import CosyVoiceWorker
from fanfic_pipeline.robsten_scraper import get_chapter_sections
from fanfic_pipeline.number_words import get_section_announcement
from fanfic_pipeline.dual_pipeline import process_section_tts, assemble_multi_section_chapter

FFMPEG_EXE = os.path.join(BASE_DIR, "vendor", "ffmpeg", "bin", "ffmpeg.exe")
DEFAULT_COVER_IMAGE = r"M:\Downloads\UrRVpx9R5CAAqDSJgvmv8shjPtIu-TbFeqghSsG0R0xOu2GPjvck_qcRwF8Dhg5b0MvHrAjKQy_K_hs0Qv72s5Pv.jpg"


def render_video_1080p(audio_path: str, image_path: str, output_mp4: str) -> bool:
    """Render 1080p Full HD MP4 video with cover image and audio using h264_nvenc."""
    if not os.path.exists(audio_path):
        print(f"[Video Error] Audio file not found: {audio_path}")
        return False
    if not os.path.exists(image_path):
        print(f"[Video Error] Image file not found: {image_path}")
        return False

    print(f"\n[Video] Rendering Full HD 1080p MP4: {output_mp4}...")
    t0 = time.time()
    cmd = [
        FFMPEG_EXE,
        "-y",
        "-loop", "1",
        "-framerate", "2",
        "-i", image_path,
        "-i", audio_path,
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-c:v", "h264_nvenc",
        "-b:v", "1500k",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_mp4
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    dur = time.time() - t0

    if os.path.exists(output_mp4) and os.path.getsize(output_mp4) > 10000:
        size_mb = os.path.getsize(output_mp4) / (1024 * 1024)
        print(f"[Video] Done in {dur:.1f}s! File: {output_mp4} ({size_mb:.2f} MB)")
        return True
    else:
        print(f"[Video] Failed! Returncode: {res.returncode}")
        print(res.stderr.decode("utf-8", errors="ignore")[-400:])
        return False


def run_single_chapter(chapter_num: int, worker: CosyVoiceWorker, force_tts: bool = False) -> Tuple[str, str]:
    """Synthesize a chapter using the resident worker, returns (wav_path, mp3_path)."""
    print("\n" + "=" * 70)
    print(f"BATCH RUNNER: PROCESSING CHAPTER {chapter_num}")
    print("=" * 70)

    data = get_chapter_sections(chapter_num, apply_censor=True)
    title = data["title"]
    sections = data["sections"]

    print(f"Chapter {chapter_num}: {data['header']} - {title}")
    print(f"Total sections: {len(sections)}")
    for i, s in enumerate(sections):
        reps = s.get("censor_reps", [])
        reps_str = f" | Censored: {len(reps)}" if reps else ""
        print(f"  Sec {i+1} [{s['pov']}]: {s['char_count']} chars{reps_str} | Starts: {s['text'][:50]}...")

    ch_work_dir = os.path.join(WORK_DIR, f"chapter_{chapter_num:02d}_robsten")
    os.makedirs(ch_work_dir, exist_ok=True)

    sections_data = []
    for i, s in enumerate(sections):
        sec_dir = os.path.join(ch_work_dir, f"sec_{i:02d}_{s['pov']}")
        paragraphs = [p.strip() for p in s["text"].split("\n\n") if p.strip()]

        announcement_text = get_section_announcement(chapter_num, i, s["pov"], chapter_title=title)

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

    mp3_path = os.path.splitext(final_wav)[0] + ".mp3"
    print(f"Chapter {chapter_num} complete -> WAV: {final_wav}, MP3: {mp3_path}")
    return final_wav, mp3_path


def merge_chapters(chapter_wavs: List[str], final_combined_wav: str, pause_between_chapters_sec: float = 3.0) -> str:
    """Concatenate chapter wav files with an inter-chapter silence pause and encode to MP3."""
    print("\n" + "=" * 70)
    print(f"[MERGE] Combining {len(chapter_wavs)} chapters into {final_combined_wav}...")
    print("=" * 70)

    sr = 24000
    inter_chapter_silence = torch.zeros((1, int(sr * pause_between_chapters_sec)))
    combined_chunks = []

    for i, ch_wav in enumerate(chapter_wavs):
        print(f"  Loading Chapter {i+1}: {ch_wav}")
        wav, in_sr = torchaudio.load(ch_wav)
        if in_sr != sr:
            wav = torchaudio.functional.resample(wav, in_sr, sr)
        if wav.dim() == 1:
            wav = wav.unsqueeze(0)
        elif wav.shape[0] > 1:
            wav = wav.mean(dim=0, keepdim=True)
        combined_chunks.append(wav)

        if i < len(chapter_wavs) - 1:
            print(f"  [Adding {pause_between_chapters_sec}s silence between chapters]")
            combined_chunks.append(inter_chapter_silence)

    full_wav = torch.cat(combined_chunks, dim=1)
    os.makedirs(os.path.dirname(os.path.abspath(final_combined_wav)), exist_ok=True)
    torchaudio.save(final_combined_wav, full_wav, sr)

    total_sec = full_wav.shape[1] / sr
    print(f"[MERGE] Combined WAV saved! Duration: {total_sec / 60:.2f} min ({total_sec:.1f}s)")

    if os.path.exists(FFMPEG_EXE):
        final_mp3 = os.path.splitext(final_combined_wav)[0] + ".mp3"
        print(f"[MERGE] Converting combined audio to MP3: {final_mp3}...")
        cmd = [FFMPEG_EXE, "-y", "-i", final_combined_wav, "-codec:a", "libmp3lame", "-b:a", "192k", final_mp3]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(final_mp3):
            print(f"[MERGE] Combined MP3 ready: {final_mp3}")
            return final_mp3

    return final_combined_wav


def main():
    cli = argparse.ArgumentParser(description="Batch Fanfic Dubbing and Video Production")
    cli.add_argument("--chapters", type=int, nargs="+", default=[3, 4], help="Chapter numbers to process")
    cli.add_argument("--force_tts", action="store_true", help="Force re-synthesis")
    cli.add_argument("--image", type=str, default=DEFAULT_COVER_IMAGE, help="Cover image path for MP4 video")
    cli.add_argument("--skip_video", action="store_true", help="Skip MP4 video generation")
    args = cli.parse_args()

    start_time = time.time()
    chapters_str = ", ".join(str(c) for c in args.chapters)
    print("=" * 70)
    print(f"STARTING BATCH SYNTHESIS: CHAPTERS [{chapters_str}]")
    print(f"Cover Image: {args.image}")
    print(f"Generate Videos: {not args.skip_video}")
    print("=" * 70)

    # Initialize CosyVoice once
    worker = CosyVoiceWorker()

    chapter_wavs = []
    chapter_mp3s = []
    chapter_mp4s = []

    # 1. Process each chapter
    for ch_num in args.chapters:
        ch_wav, ch_mp3 = run_single_chapter(ch_num, worker, force_tts=args.force_tts)
        chapter_wavs.append(ch_wav)
        chapter_mp3s.append(ch_mp3)

        # Generate chapter video
        if not args.skip_video and os.path.exists(args.image):
            ch_mp4 = os.path.splitext(ch_wav)[0] + ".mp4"
            ok = render_video_1080p(ch_wav, args.image, ch_mp4)
            if ok:
                chapter_mp4s.append(ch_mp4)

    # 2. Merge chapters into combined file
    if len(args.chapters) > 1:
        first_ch = min(args.chapters)
        last_ch = max(args.chapters)
        combined_base = f"Wide_Awake_Chapters_{first_ch:02d}_{last_ch:02d}"
        combined_wav = os.path.join(OUTPUT_DIR, f"{combined_base}.wav")
        combined_mp3 = merge_chapters(chapter_wavs, combined_wav, pause_between_chapters_sec=3.0)

        # Generate combined video
        if not args.skip_video and os.path.exists(args.image):
            combined_mp4 = os.path.join(OUTPUT_DIR, f"{combined_base}.mp4")
            render_video_1080p(combined_wav, args.image, combined_mp4)
    else:
        combined_mp3 = chapter_mp3s[0]
        combined_mp4 = chapter_mp4s[0] if chapter_mp4s else None

    total_time = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"ALL DONE in {total_time / 60:.2f} minutes!")
    for i, ch_num in enumerate(args.chapters):
        print(f"  Chapter {ch_num} MP3: {chapter_mp3s[i]}")
        if i < len(chapter_mp4s):
            print(f"  Chapter {ch_num} MP4: {chapter_mp4s[i]}")
    if len(args.chapters) > 1:
        print(f"  Combined MP3: {combined_mp3}")
        if not args.skip_video:
            print(f"  Combined MP4: {combined_mp4}")
    print("=" * 70)


if __name__ == "__main__":
    main()
