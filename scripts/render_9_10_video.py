import os
import sys
import time

BASE_DIR = r"E:\AI-Dubbing"
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fanfic_pipeline.batch_runner import render_video_1080p

IMAGE_PATH = r"M:\Downloads\Сумерки_ Неспящие — главы 9–10.png"
OUTPUT_DIR = r"E:\AI-Dubbing\output\wide_awake"

tasks = [
    ("Chapter_09_ШОКоладная Крошка.wav", "Chapter_09_ШОКоладная Крошка.mp4"),
    ("Chapter_10_Гневные Ореховые Помадки.wav", "Chapter_10_Гневные Ореховые Помадки.mp4"),
    ("Wide_Awake_Chapters_09_10.wav", "Wide_Awake_Chapters_09_10.mp4"),
]

print("=" * 70)
print(f"RENDERING VIDEOS FOR CHAPTERS 9 & 10")
print(f"Cover Image: {IMAGE_PATH}")
print("=" * 70)

t0_all = time.time()
for wav_name, mp4_name in tasks:
    wav_path = os.path.join(OUTPUT_DIR, wav_name)
    mp4_path = os.path.join(OUTPUT_DIR, mp4_name)
    print(f"\nProcessing: {mp4_name}")
    success = render_video_1080p(wav_path, IMAGE_PATH, mp4_path)
    if not success:
        print(f"FAILED rendering {mp4_name}")
        sys.exit(1)

total_dur = time.time() - t0_all
print("\n" + "=" * 70)
print(f"ALL 3 VIDEOS RENDERED SUCCESSFULLY in {total_dur:.1f}s ({total_dur/60:.2f} min)!")
print("=" * 70)
