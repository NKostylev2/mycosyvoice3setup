import os
import sys
import time
import subprocess
import soundfile as sf

BASE_DIR = r"E:\AI-Dubbing"
FFMPEG_EXE = os.path.join(BASE_DIR, "vendor", "ffmpeg", "bin", "ffmpeg.exe")
OUTPUT_DIR = os.path.join(BASE_DIR, "output", "wide_awake")

IMG7 = r"M:\Downloads\Горько-сладкие ириски при свечах.png"
IMG8 = r"M:\Downloads\Сумерки с тройной карамелью.png"

WAV7 = os.path.join(OUTPUT_DIR, "Chapter_07_Горько-Сладкие Ириски.wav")
WAV8 = os.path.join(OUTPUT_DIR, "Chapter_08_Сумерки с Тройной Карамелью.wav")
COMBINED_WAV = os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_07_08.wav")

MP4_CH7 = os.path.join(OUTPUT_DIR, "Chapter_07_Горько-Сладкие Ириски.mp4")
MP4_CH8 = os.path.join(OUTPUT_DIR, "Chapter_08_Сумерки с Тройной Карамелью.mp4")
MP4_COMBINED = os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_07_08.mp4")


def render_single_video(audio_path, image_path, output_mp4, title):
    print("\n" + "=" * 70)
    print(f"RENDERING: {title}")
    print(f"Audio: {os.path.basename(audio_path)}")
    print(f"Cover: {os.path.basename(image_path)}")
    print(f"Output: {output_mp4}")
    print("=" * 70)

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

    if res.returncode == 0 and os.path.exists(output_mp4) and os.path.getsize(output_mp4) > 100000:
        size_mb = os.path.getsize(output_mp4) / (1024 * 1024)
        print(f"-> SUCCESS in {dur:.1f}s! Size: {size_mb:.2f} MB")
        return True
    else:
        print(f"-> FAILED! Returncode: {res.returncode}")
        print(res.stderr.decode("utf-8", errors="ignore")[-400:])
        return False


def render_combined_7_8():
    print("\n" + "=" * 70)
    print("RENDERING COMBINED VIDEO: Chapters 07-08 (with image transition)")
    print("=" * 70)

    info7 = sf.info(WAV7)
    info8 = sf.info(WAV8)
    info_comb = sf.info(COMBINED_WAV)

    d7 = info7.duration
    d8 = info8.duration
    total_dur = info_comb.duration

    # Switch in middle of 3.0s pause between chapters
    switch_t = d7 + 1.5
    dur8 = total_dur - switch_t

    print(f"Chapter 7 duration: {d7:.2f}s ({d7/60:.2f} min)")
    print(f"Chapter 8 duration: {d8:.2f}s ({d8/60:.2f} min)")
    print(f"Total duration:     {total_dur:.2f}s ({total_dur/60:.2f} min)")
    print(f"Cover switch time:  {switch_t:.2f}s ({switch_t/60:.2f} min)")
    print(f"Output:             {MP4_COMBINED}")

    filter_str = (
        f"[0:v]loop=loop=-1:size=1:start=0,scale=1920:1080:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=2,trim=duration={switch_t:.3f}[v0];"
        f"[1:v]loop=loop=-1:size=1:start=0,scale=1920:1080:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=2,trim=duration={dur8:.3f}[v1];"
        f"[v0][v1]concat=n=2:v=1:a=0[v]"
    )

    cmd = [
        FFMPEG_EXE,
        "-y",
        "-i", IMG7,
        "-i", IMG8,
        "-i", COMBINED_WAV,
        "-filter_complex", filter_str,
        "-map", "[v]",
        "-map", "2:a",
        "-c:v", "h264_nvenc",
        "-b:v", "1500k",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        MP4_COMBINED
    ]

    t0 = time.time()
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    dur = time.time() - t0

    if res.returncode == 0 and os.path.exists(MP4_COMBINED) and os.path.getsize(MP4_COMBINED) > 100000:
        size_mb = os.path.getsize(MP4_COMBINED) / (1024 * 1024)
        print(f"-> SUCCESS in {dur:.1f}s! Size: {size_mb:.2f} MB")
        return True
    else:
        print(f"-> FAILED! Returncode: {res.returncode}")
        print(res.stderr.decode("utf-8", errors="ignore")[-400:])
        return False


def main():
    t_start = time.time()

    # 1. Chapter 7
    s7 = render_single_video(WAV7, IMG7, MP4_CH7, "Chapter 07: Горько-Сладкие Ириски")
    if not s7:
        sys.exit(1)

    # 2. Chapter 8
    s8 = render_single_video(WAV8, IMG8, MP4_CH8, "Chapter 08: Сумерки с Тройной Карамелью")
    if not s8:
        sys.exit(1)

    # 3. Combined Chapters 7 & 8
    sc = render_combined_7_8()
    if not sc:
        sys.exit(1)

    total_time = time.time() - t_start
    print("\n" + "=" * 70)
    print(f"ALL VIDEOS FOR CHAPTERS 7 & 8 COMPLETED in {total_time:.1f}s ({total_time/60:.2f} min)!")
    print("=" * 70)


if __name__ == "__main__":
    main()
