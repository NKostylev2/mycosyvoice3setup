import os
import sys
import time
import subprocess
import torchaudio

BASE_DIR = r"E:\AI-Dubbing"
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fanfic_pipeline.batch_runner import FFMPEG_EXE

OUTPUT_DIR = r"E:\AI-Dubbing\output\wide_awake"
IMG1 = r"M:\Downloads\Глава 1_ Рыжие сдобные зомби.png"
IMG2 = r"M:\Downloads\Глава 2_ Малиновые печенья Ньютона.png"

WAV1 = os.path.join(OUTPUT_DIR, "Chapter_01_Рыжие Сдобные Зомби.wav")
WAV2 = os.path.join(OUTPUT_DIR, "Chapter_02_Чертовы Ньютоны.wav")
COMBINED_WAV = os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_01_02.wav")
OUTPUT_MP4 = os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_01_02.mp4")

# Check durations
w1, sr1 = torchaudio.load(WAV1)
d1 = w1.shape[1] / sr1
w2, sr2 = torchaudio.load(WAV2)
d2 = w2.shape[1] / sr2
wc, src = torchaudio.load(COMBINED_WAV)
total_dur = wc.shape[1] / src

# Switch in middle of 3.0s silence
switch_t = d1 + 1.5
dur2 = total_dur - switch_t

print("=" * 70)
print("COMBINING CHAPTERS 1 AND 2 INTO FULL HD VIDEO")
print(f"Chapter 1 duration: {d1:.2f}s ({d1/60:.2f} min)")
print(f"Switch to Chapter 2 image at: {switch_t:.2f}s ({switch_t/60:.2f} min)")
print(f"Total video duration: {total_dur:.2f}s ({total_dur/60:.2f} min)")
print(f"Output: {OUTPUT_MP4}")
print("=" * 70)

# Filter complex to scale both images to 1080p, trim them, and concatenate video streams
# Stream 0: img1 trimmed to switch_t
# Stream 1: img2 trimmed to dur2
filter_str = (
    f"[0:v]loop=loop=-1:size=1:start=0,scale=1920:1080:force_original_aspect_ratio=decrease,"
    f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=2,trim=duration={switch_t:.3f}[v0];"
    f"[1:v]loop=loop=-1:size=1:start=0,scale=1920:1080:force_original_aspect_ratio=decrease,"
    f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=2,trim=duration={dur2:.3f}[v1];"
    f"[v0][v1]concat=n=2:v=1:a=0[v]"
)

cmd = [
    FFMPEG_EXE,
    "-y",
    "-i", IMG1,
    "-i", IMG2,
    "-i", COMBINED_WAV,
    "-filter_complex", filter_str,
    "-map", "[v]",
    "-map", "2:a",
    "-c:v", "h264_nvenc",
    "-b:v", "1500k",
    "-c:a", "aac",
    "-b:a", "192k",
    "-shortest",
    OUTPUT_MP4
]

t0 = time.time()
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
dur = time.time() - t0

if res.returncode == 0 and os.path.exists(OUTPUT_MP4) and os.path.getsize(OUTPUT_MP4) > 100000:
    size_mb = os.path.getsize(OUTPUT_MP4) / (1024 * 1024)
    print(f"\n[Video] Done in {dur:.1f}s! File: {OUTPUT_MP4} ({size_mb:.2f} MB)")
else:
    print(f"\n[Video Error] Returncode: {res.returncode}")
    print(res.stderr.decode("utf-8", errors="ignore")[-800:])
    sys.exit(1)
