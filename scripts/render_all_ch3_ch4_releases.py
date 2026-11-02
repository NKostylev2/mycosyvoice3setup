import os
import sys
import time
import subprocess
import soundfile as sf

BASE_DIR = r"E:\AI-Dubbing"
FFMPEG_EXE = os.path.join(BASE_DIR, "vendor", "ffmpeg", "bin", "ffmpeg.exe")
OUTPUT_DIR = os.path.join(BASE_DIR, "output", "wide_awake")

IMG3 = r"M:\Downloads\Глава 3_ Сливочное рандеву на двоих.png"
IMG4 = r"M:\Downloads\Глава 4_ Панацея из арахисового масла.png"

WAV3 = os.path.join(OUTPUT_DIR, "Chapter_03_Сливочное Рандеву На Двоих.wav")
WAV4 = os.path.join(OUTPUT_DIR, "Chapter_04_Панацея Из Арахисового масла.wav")
COMBINED_WAV = os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_03_04.wav")

MP4_CH3 = os.path.join(OUTPUT_DIR, "Chapter_03_Сливочное_Рандеву_На_Двоих.mp4")
MP4_CH4 = os.path.join(OUTPUT_DIR, "Chapter_04_Панацея_Из_Арахисового_масла.mp4")
MP4_COMBINED = os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_03_04.mp4")


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


def render_combined_3_4():
    print("\n" + "=" * 70)
    print("RENDERING COMBINED VIDEO: Chapters 03-04 (with image transition)")
    print("=" * 70)

    info3 = sf.info(WAV3)
    info4 = sf.info(WAV4)
    info_comb = sf.info(COMBINED_WAV)

    d3 = info3.duration
    d4 = info4.duration
    total_dur = info_comb.duration

    # Switch in middle of 3.0s pause between chapters
    switch_t = d3 + 1.5
    dur4 = total_dur - switch_t

    print(f"Chapter 3 duration: {d3:.2f}s ({d3/60:.2f} min)")
    print(f"Chapter 4 duration: {d4:.2f}s ({d4/60:.2f} min)")
    print(f"Total duration:     {total_dur:.2f}s ({total_dur/60:.2f} min)")
    print(f"Cover switch time:  {switch_t:.2f}s ({switch_t/60:.2f} min)")
    print(f"Output:             {MP4_COMBINED}")

    filter_str = (
        f"[0:v]loop=loop=-1:size=1:start=0,scale=1920:1080:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=2,trim=duration={switch_t:.3f}[v0];"
        f"[1:v]loop=loop=-1:size=1:start=0,scale=1920:1080:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=2,trim=duration={dur4:.3f}[v1];"
        f"[v0][v1]concat=n=2:v=1:a=0[v]"
    )

    cmd = [
        FFMPEG_EXE,
        "-y",
        "-i", IMG3,
        "-i", IMG4,
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

    # 1. Chapter 3
    s3 = render_single_video(WAV3, IMG3, MP4_CH3, "Chapter 03: Сливочное Рандеву На Двоих")
    if not s3:
        sys.exit(1)

    # 2. Chapter 4
    s4 = render_single_video(WAV4, IMG4, MP4_CH4, "Chapter 04: Панацея Из Арахисового масла")
    if not s4:
        sys.exit(1)

    # 3. Combined Chapters 3 & 4
    sc = render_combined_3_4()
    if not sc:
        sys.exit(1)

    total_time = time.time() - t_start
    print("\n" + "=" * 70)
    print(f"ALL VIDEOS FOR CHAPTERS 3 & 4 COMPLETED in {total_time:.1f}s ({total_time/60:.2f} min)!")
    print("=" * 70)


if __name__ == "__main__":
    main()
