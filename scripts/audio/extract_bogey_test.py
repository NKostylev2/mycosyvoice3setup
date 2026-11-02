import subprocess
import soundfile as sf
import os

FFMPEG = r'E:\AI-Dubbing\models\Applio\ffmpeg.exe'
VOCALS = r'E:\AI-Dubbing\work\S01E01\audio\english_vocals.wav'
MP4 = r'E:\AI-Dubbing-Subtitles\input\S01E01.mp4'

out_dir = r'E:\AI-Dubbing\work\test_slices'
os.makedirs(out_dir, exist_ok=True)

# 1. Extract from MP4 at 940s - 955s
cmd1 = [FFMPEG, '-y', '-ss', '942', '-t', '10', '-i', MP4, '-ar', '24000', '-ac', '1', os.path.join(out_dir, 'mp4_942_952.wav')]
subprocess.run(cmd1, check=True)

# 2. Extract from vocals at 954s - 964s (+11.82s)
cmd2 = [FFMPEG, '-y', '-ss', '954', '-t', '10', '-i', VOCALS, '-ar', '24000', '-ac', '1', os.path.join(out_dir, 'vocals_954_964.wav')]
subprocess.run(cmd2, check=True)

print("Extracted test clips successfully!")
