import subprocess

FFMPEG = r'E:\AI-Dubbing\models\Applio\ffmpeg.exe'
VOCALS = r'E:\AI-Dubbing\work\S01E01\audio\english_vocals.wav'
MP4 = r'E:\AI-Dubbing-Subtitles\input\S01E01.mp4'

# Extract first 15s of both
subprocess.run([FFMPEG, '-y', '-ss', '0', '-t', '15', '-i', MP4, '-ar', '16000', '-ac', '1', r'E:\AI-Dubbing\work\test_slices\mp4_start.wav'], check=True)
subprocess.run([FFMPEG, '-y', '-ss', '0', '-t', '15', '-i', VOCALS, '-ar', '16000', '-ac', '1', r'E:\AI-Dubbing\work\test_slices\vocals_start.wav'], check=True)
print("Start clips extracted.")
