import os
import sys
import time
import torch
import torchaudio
import subprocess

BASE_DIR = r"E:\AI-Dubbing"
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fanfic_pipeline.batch_runner import FFMPEG_EXE, render_video_1080p

OUTPUT_DIR = r"E:\AI-Dubbing\output\wide_awake"
IMAGE_PATH = r"M:\Downloads\Сумерки_ Неспящие — главы 1–10.png"

CHAPTER_WAVS = [
    os.path.join(OUTPUT_DIR, "Chapter_01_Рыжие Сдобные Зомби.wav"),
    os.path.join(OUTPUT_DIR, "Chapter_02_Чертовы Ньютоны.wav"),
    os.path.join(OUTPUT_DIR, "Chapter_03_Сливочное Рандеву На Двоих.wav"),
    os.path.join(OUTPUT_DIR, "Chapter_04_Панацея Из Арахисового масла.wav"),
    os.path.join(OUTPUT_DIR, "Chapter_05_Маниакальная Мята.wav"),
    os.path.join(OUTPUT_DIR, "Chapter_06_Карамельный Комфорт.wav"),
    os.path.join(OUTPUT_DIR, "Chapter_07_Горько-Сладкие Ириски.wav"),
    os.path.join(OUTPUT_DIR, "Chapter_08_Сумерки с Тройной Карамелью.wav"),
    os.path.join(OUTPUT_DIR, "Chapter_09_ШОКоладная Крошка.wav"),
    os.path.join(OUTPUT_DIR, "Chapter_10_Гневные Ореховые Помадки.wav"),
]

FINAL_WAV = os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_01_10.wav")
FINAL_MP3 = os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_01_10.mp3")
FINAL_MP4 = os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_01_10.mp4")

def main():
    print("=" * 70)
    print("PRODUCING FULL RELEASE: CHAPTERS 01 - 10")
    print(f"Cover Image: {IMAGE_PATH}")
    print("=" * 70)

    # 1. Verify inputs
    for idx, path in enumerate(CHAPTER_WAVS, 1):
        if not os.path.exists(path):
            print(f"[Error] Missing chapter {idx}: {path}")
            sys.exit(1)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  [OK] Chapter {idx:02d}: {os.path.basename(path)} ({size_mb:.1f} MB)")

    if not os.path.exists(IMAGE_PATH):
        print(f"[Error] Image not found: {IMAGE_PATH}")
        sys.exit(1)

    t0_start = time.time()

    # 2. Merge WAVs
    sr = 24000
    pause_sec = 3.0
    silence = torch.zeros((1, int(sr * pause_sec)))
    chunks = []

    print(f"\n[Merge] Loading and concatenating 10 chapter WAVs with {pause_sec}s silence...")
    for idx, path in enumerate(CHAPTER_WAVS, 1):
        print(f"  Loading chapter {idx:02d}...")
        wav, in_sr = torchaudio.load(path)
        if in_sr != sr:
            wav = torchaudio.functional.resample(wav, in_sr, sr)
        if wav.dim() == 1:
            wav = wav.unsqueeze(0)
        elif wav.shape[0] > 1:
            wav = wav.mean(dim=0, keepdim=True)
        chunks.append(wav)
        if idx < len(CHAPTER_WAVS):
            chunks.append(silence)

    print("  Concatenating in memory...")
    full_wav = torch.cat(chunks, dim=1)
    del chunks

    total_samples = full_wav.shape[1]
    total_sec = total_samples / sr
    total_min = total_sec / 60
    total_hrs = total_min / 60
    print(f"[Merge] Full audio duration: {total_sec:.1f}s ({total_min:.2f} min / {total_hrs:.2f} hours)")

    print(f"[Merge] Saving combined WAV: {FINAL_WAV}...")
    torchaudio.save(FINAL_WAV, full_wav, sr)
    del full_wav
    print(f"[Merge] Combined WAV saved! ({os.path.getsize(FINAL_WAV)/(1024*1024):.1f} MB)")

    # 3. Encode to MP3 192k
    print(f"\n[MP3] Encoding 192k MP3: {FINAL_MP3}...")
    t_mp3_start = time.time()
    cmd_mp3 = [
        FFMPEG_EXE,
        "-y",
        "-i", FINAL_WAV,
        "-codec:a", "libmp3lame",
        "-b:a", "192k",
        FINAL_MP3
    ]
    res_mp3 = subprocess.run(cmd_mp3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if res_mp3.returncode == 0 and os.path.exists(FINAL_MP3):
        dur_mp3 = time.time() - t_mp3_start
        print(f"[MP3] Done in {dur_mp3:.1f}s! Size: {os.path.getsize(FINAL_MP3)/(1024*1024):.1f} MB")
    else:
        print("[MP3 Error] MP3 encoding failed!")
        sys.exit(1)

    # 4. Render Full HD 1080p MP4 with NVENC
    print(f"\n[Video] Rendering Full HD 1080p video with NVENC...")
    t_video_start = time.time()
    ok_video = render_video_1080p(FINAL_WAV, IMAGE_PATH, FINAL_MP4)
    if not ok_video:
        print("[Video Error] Video rendering failed!")
        sys.exit(1)

    total_elapsed = time.time() - t0_start
    print("\n" + "=" * 70)
    print(f"FULL PRODUCTION COMPLETE in {total_elapsed:.1f}s ({total_elapsed/60:.2f} minutes)!")
    print(f"  Duration: {total_hrs:.2f} hours ({total_min:.1f} minutes)")
    print(f"  MP3: {FINAL_MP3} ({os.path.getsize(FINAL_MP3)/(1024*1024):.1f} MB)")
    print(f"  MP4: {FINAL_MP4} ({os.path.getsize(FINAL_MP4)/(1024*1024):.1f} MB)")
    print("=" * 70)

if __name__ == "__main__":
    main()
