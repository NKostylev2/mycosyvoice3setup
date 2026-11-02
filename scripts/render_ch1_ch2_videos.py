import os
import sys
import time

BASE_DIR = r"E:\AI-Dubbing"
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fanfic_pipeline.batch_runner import render_video_1080p

OUTPUT_DIR = r"E:\AI-Dubbing\output\wide_awake"

tasks = [
    (
        os.path.join(OUTPUT_DIR, "Chapter_01_Рыжие Сдобные Зомби.wav"),
        r"M:\Downloads\Глава 1_ Рыжие сдобные зомби.png",
        os.path.join(OUTPUT_DIR, "Chapter_01_Рыжие Сдобные Зомби.mp4"),
    ),
    (
        os.path.join(OUTPUT_DIR, "Chapter_02_Чертовы Ньютоны.wav"),
        r"M:\Downloads\Глава 2_ Малиновые печенья Ньютона.png",
        os.path.join(OUTPUT_DIR, "Chapter_02_Чертовы Ньютоны.mp4"),
    ),
]

print("=" * 70)
print("RENDERING VIDEOS FOR CHAPTERS 1 AND 2")
print("=" * 70)

t0_all = time.time()
for wav_path, img_path, mp4_path in tasks:
    print(f"\nProcessing: {os.path.basename(mp4_path)}")
    print(f"  Image: {img_path}")
    print(f"  Audio: {os.path.basename(wav_path)}")
    success = render_video_1080p(wav_path, img_path, mp4_path)
    if not success:
        print(f"FAILED rendering {mp4_path}")
        sys.exit(1)

total_dur = time.time() - t0_all
print("\n" + "=" * 70)
print(f"ALL VIDEOS RENDERED SUCCESSFULLY in {total_dur:.1f}s ({total_dur/60:.2f} min)!")
print("=" * 70)
