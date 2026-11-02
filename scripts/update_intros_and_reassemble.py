import os
import sys
import time
import torch
import torchaudio
import subprocess

BASE_DIR = r"E:\AI-Dubbing"
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fanfic_pipeline.config import WORK_DIR, OUTPUT_DIR, POV_PROFILES
from fanfic_pipeline.tts_worker import CosyVoiceWorker
from fanfic_pipeline.robsten_scraper import get_chapter_sections
from fanfic_pipeline.number_words import get_section_announcement
from fanfic_pipeline.dual_pipeline import process_section_tts, assemble_multi_section_chapter
from fanfic_pipeline.batch_runner import merge_chapters, FFMPEG_EXE

CHAPTERS = list(range(1, 11))

def main():
    print("=" * 70)
    print("UPDATING CHAPTER INTROS (NUMBER + TITLE + PART + POV)")
    print(f"Target chapters: {CHAPTERS}")
    print("Video rendering: SKIPPED (user will supply new images)")
    print("=" * 70)

    t0_start = time.time()
    worker = CosyVoiceWorker()

    chapter_wavs = []
    chapter_mp3s = []

    # 1. Update each chapter
    for ch_num in CHAPTERS:
        print("\n" + "=" * 70)
        print(f"UPDATING CHAPTER {ch_num}")
        print("=" * 70)

        data = get_chapter_sections(ch_num, apply_censor=True)
        title = data["title"]
        sections = data["sections"]

        ch_work_dir = os.path.join(WORK_DIR, f"chapter_{ch_num:02d}_robsten")
        sections_data = []

        for i, s in enumerate(sections):
            sec_dir = os.path.join(ch_work_dir, f"sec_{i:02d}_{s['pov']}")
            paragraphs = [p.strip() for p in s["text"].split("\n\n") if p.strip()]

            # Announcement includes chapter title for sec_idx == 0
            announcement_text = get_section_announcement(ch_num, i, s["pov"], chapter_title=title)

            segs, files, intro_file = process_section_tts(
                sec_idx=i,
                pov=s["pov"],
                paragraphs=paragraphs,
                sec_dir=sec_dir,
                worker=worker,
                announcement_text=announcement_text,
                force_tts=False,  # Reuses all cached text segments!
            )
            sections_data.append((s, segs, files, intro_file))

        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title).strip()
        final_wav = os.path.join(OUTPUT_DIR, f"Chapter_{ch_num:02d}_{safe_title}.wav")

        assemble_multi_section_chapter(
            sections_data=sections_data,
            final_wav_path=final_wav,
            sample_rate=worker.sample_rate,
        )

        mp3_path = os.path.splitext(final_wav)[0] + ".mp3"
        chapter_wavs.append(final_wav)
        chapter_mp3s.append(mp3_path)
        print(f"Chapter {ch_num} updated -> WAV: {final_wav}, MP3: {mp3_path}")

    # 2. Re-merge chapter pairs (1-2, 3-4, 5-6, 7-8, 9-10)
    print("\n" + "=" * 70)
    print("RE-MERGING 2-CHAPTER PAIRS")
    print("=" * 70)
    for pair_start in range(1, 11, 2):
        pair_end = pair_start + 1
        pair_wavs = [chapter_wavs[pair_start - 1], chapter_wavs[pair_end - 1]]
        pair_base = f"Wide_Awake_Chapters_{pair_start:02d}_{pair_end:02d}"
        pair_wav = os.path.join(OUTPUT_DIR, f"{pair_base}.wav")
        merge_chapters(pair_wavs, pair_wav, pause_between_chapters_sec=3.0)

    # 3. Re-merge master 01-10
    print("\n" + "=" * 70)
    print("RE-MERGING MASTER 01-10 RELEASE")
    print("=" * 70)
    master_wav = os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_01_10.wav")
    merge_chapters(chapter_wavs, master_wav, pause_between_chapters_sec=3.0)

    total_time = time.time() - t0_start
    print("\n" + "=" * 70)
    print(f"ALL 10 CHAPTERS AND COMBINED AUDIOS UPDATED in {total_time / 60:.2f} minutes!")
    print("=" * 70)

if __name__ == "__main__":
    main()
