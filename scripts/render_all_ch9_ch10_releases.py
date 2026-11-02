import os
import sys
import time
import subprocess
import soundfile as sf

BASE_DIR = r"E:\AI-Dubbing"
FFMPEG_EXE = os.path.join(BASE_DIR, "vendor", "ffmpeg", "bin", "ffmpeg.exe")
OUTPUT_DIR = os.path.join(BASE_DIR, "output", "wide_awake")

IMG9 = r"M:\Downloads\Шоколадная крошка_ глава 9.png"
IMG10 = r"M:\Downloads\Глава 10_ Ореховые шоколадные помадки.png"

WAV9 = os.path.join(OUTPUT_DIR, "Chapter_09_ШОКоладная Крошка.wav")
WAV10 = os.path.join(OUTPUT_DIR, "Chapter_10_Гневные Ореховые Помадки.wav")
COMBINED_WAV = os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_09_10.wav")

MP4_CH9 = os.path.join(OUTPUT_DIR, "Chapter_09_ШОКоладная Крошка.mp4")
MP4_CH10 = os.path.join(OUTPUT_DIR, "Chapter_10_Гневные Ореховые Помадки.mp4")
MP4_COMBINED = os.path.join(OUTPUT_DIR, "Wide_Awake_Chapters_09_10.mp4")


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


def render_combined_9_10():
    print("\n" + "=" * 70)
    print("RENDERING COMBINED VIDEO: Chapters 09-10 (with image transition)")
    print("=" * 70)

    info9 = sf.info(WAV9)
    info10 = sf.info(WAV10)
    info_comb = sf.info(COMBINED_WAV)

    d9 = info9.duration
    d10 = info10.duration
    total_dur = info_comb.duration

    # Switch in middle of 3.0s pause between chapters
    switch_t = d9 + 1.5
    dur10 = total_dur - switch_t

    print(f"Chapter 9 duration:  {d9:.2f}s ({d9/60:.2f} min)")
    print(f"Chapter 10 duration: {d10:.2f}s ({d10/60:.2f} min)")
    print(f"Total duration:      {total_dur:.2f}s ({total_dur/60:.2f} min)")
    print(f"Cover switch time:   {switch_t:.2f}s ({switch_t/60:.2f} min)")
    print(f"Output:              {MP4_COMBINED}")

    filter_str = (
        f"[0:v]loop=loop=-1:size=1:start=0,scale=1920:1080:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=2,trim=duration={switch_t:.3f}[v0];"
        f"[1:v]loop=loop=-1:size=1:start=0,scale=1920:1080:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fps=2,trim=duration={dur10:.3f}[v1];"
        f"[v0][v1]concat=n=2:v=1:a=0[v]"
    )

    cmd = [
        FFMPEG_EXE,
        "-y",
        "-i", IMG9,
        "-i", IMG10,
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

    # 1. Chapter 9
    s9 = render_single_video(WAV9, IMG9, MP4_CH9, "Chapter 09: ШОКоладная Крошка")
    if not s9:
        sys.exit(1)

    # 2. Chapter 10
    s10 = render_single_video(WAV10, IMG10, MP4_CH10, "Chapter 10: Гневные Ореховые Помадки")
    if not s10:
        sys.exit(1)

    # 3. Combined Chapters 9 & 10
    sc = render_combined_9_10()
    if not sc:
        sys.exit(1)

    total_time = time.time() - t_start
    print("\n" + "=" * 70)
    print(f"ALL VIDEOS FOR CHAPTERS 9 & 10 COMPLETED in {total_time:.1f}s ({total_time/60:.2f} min)!")
    print("=" * 70)


if __name__ == "__main__":
    main()
