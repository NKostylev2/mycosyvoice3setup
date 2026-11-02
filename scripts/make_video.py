import os
import sys
import subprocess
import time

FFMPEG_EXE = r"E:\AI-Dubbing\vendor\ffmpeg\bin\ffmpeg.exe"
IMAGE_PATH = r"M:\Downloads\UrRVpx9R5CAAqDSJgvmv8shjPtIu-TbFeqghSsG0R0xOu2GPjvck_qcRwF8Dhg5b0MvHrAjKQy_K_hs0Qv72s5Pv.jpg"
OUTPUT_DIR = r"E:\AI-Dubbing\output\wide_awake"

tasks = [
    {
        "name": "Combined Chapters 01-02",
        "audio": os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_01_02.wav"),
        "output": os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_01_02.mp4")
    },
    {
        "name": "Chapter 01",
        "audio": os.path.join(OUTPUT_DIR, "Chapter_01_Рыжие Сдобные Зомби.wav"),
        "output": os.path.join(OUTPUT_DIR, "Chapter_01_Рыжие_Сдобные_Зомби.mp4")
    },
    {
        "name": "Chapter 02",
        "audio": os.path.join(OUTPUT_DIR, "Chapter_02_Чертовы Ньютоны.wav"),
        "output": os.path.join(OUTPUT_DIR, "Chapter_02_Чертовы_Ньютоны.mp4")
    }
]

for t in tasks:
    print("\n" + "=" * 60)
    print(f"Creating Video: {t['name']}")
    print(f"Audio source:  {t['audio']}")
    print(f"Output video:  {t['output']}")
    print("=" * 60)

    if not os.path.exists(t["audio"]):
        # fallback to mp3 if wav not found
        mp3_alt = os.path.splitext(t["audio"])[0] + ".mp3"
        if os.path.exists(mp3_alt):
            t["audio"] = mp3_alt
        else:
            print(f"[Error] Audio file not found: {t['audio']}")
            continue

    cmd = [
        FFMPEG_EXE,
        "-y",
        "-loop", "1",
        "-framerate", "2",
        "-i", IMAGE_PATH,
        "-i", t["audio"],
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

    if os.path.exists(t["output"]):
        size_mb = os.path.getsize(t["output"]) / (1024 * 1024)
        print(f"-> SUCCESS in {duration:.1f}s! Size: {size_mb:.2f} MB")
    else:
        print(f"-> FAILED!")
        print(res.stderr.decode('utf-8', errors='ignore')[-500:])

print("\nALL VIDEOS CREATED SUCCESSFULLY!")
