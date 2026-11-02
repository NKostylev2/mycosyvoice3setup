import os
import sys
import subprocess
import time

FFMPEG_EXE = r"E:\AI-Dubbing\vendor\ffmpeg\bin\ffmpeg.exe"
IMAGE_PATH = r"M:\Downloads\3-4.jpg"
OUTPUT_DIR = r"E:\AI-Dubbing\output\wide_awake"

tasks = [
    {
        "name": "Combined Chapters 03-04",
        "audio": os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_03_04.wav"),
        "output": os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_03_04.mp4")
    },
    {
        "name": "Chapter 03",
        "audio": os.path.join(OUTPUT_DIR, "Chapter_03_Сливочное Рандеву На Двоих.wav"),
        "output": os.path.join(OUTPUT_DIR, "Chapter_03_Сливочное_Рандеву_На_Двоих.mp4")
    },
    {
        "name": "Chapter 04",
        "audio": os.path.join(OUTPUT_DIR, "Chapter_04_Панацея Из Арахисового масла.wav"),
        "output": os.path.join(OUTPUT_DIR, "Chapter_04_Панацея_Из_Арахисового_масла.mp4")
    }
]

for t in tasks:
    print("\n" + "=" * 60)
    print(f"Creating Video: {t['name']}")
    print(f"Audio source:  {t['audio']}")
    print(f"Output video:  {t['output']}")
    print("=" * 60)

    audio_src = t["audio"]
    if not os.path.exists(audio_src):
        mp3_alt = os.path.splitext(audio_src)[0] + ".mp3"
        if os.path.exists(mp3_alt):
            audio_src = mp3_alt
        else:
            print(f"[Error] Audio file not found: {audio_src}")
            continue

    cmd = [
        FFMPEG_EXE,
        "-y",
        "-loop", "1",
        "-framerate", "2",
        "-i", IMAGE_PATH,
        "-i", audio_src,
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-c:v", "h264_nvenc",
        "-b:v", "1500k",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        t["output"]
    ]

    t0 = time.time()
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    duration = time.time() - t0

    if os.path.exists(t["output"]) and os.path.getsize(t["output"]) > 10000:
        size_mb = os.path.getsize(t["output"]) / (1024 * 1024)
        print(f"-> SUCCESS in {duration:.1f}s! Size: {size_mb:.2f} MB")
    else:
        print(f"-> FAILED!")
        print(res.stderr.decode('utf-8', errors='ignore')[-500:])

print("\nALL VIDEOS FOR CHAPTERS 3-4 CREATED SUCCESSFULLY!")
