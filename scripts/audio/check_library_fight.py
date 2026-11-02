import subprocess
from faster_whisper import WhisperModel

FFMPEG = r'E:\AI-Dubbing\models\Applio\ffmpeg.exe'
MP4 = r'E:\AI-Dubbing-Subtitles\input\S01E01.mp4'

subprocess.run([FFMPEG, '-y', '-ss', '1180', '-t', '60', '-i', MP4, '-ar', '16000', '-ac', '1', r'E:\AI-Dubbing\work\test_slices\library_fight_1180_1240.wav'], check=True)

model = WhisperModel("base", device="cpu", compute_type="int8")
segments, _ = model.transcribe(r"E:\AI-Dubbing\work\test_slices\library_fight_1180_1240.wav", language="en")
for seg in segments:
    print(f"[{1180 + seg.start:.2f}s - {1180 + seg.end:.2f}s]: {seg.text}")
