import subprocess
import json

FFMPEG = r'E:\AI-Dubbing\models\Applio\ffmpeg.exe'
MP4 = r'E:\AI-Dubbing-Subtitles\input\S01E01.mp4'

# Extract 920s to 1020s (100 seconds)
subprocess.run([FFMPEG, '-y', '-ss', '920', '-t', '100', '-i', MP4, '-ar', '16000', '-ac', '1', r'E:\AI-Dubbing\work\test_slices\bogey_scene_920_1020.wav'], check=True)
print("Extracted bogey scene audio.")
