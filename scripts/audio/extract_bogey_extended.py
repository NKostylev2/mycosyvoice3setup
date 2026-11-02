import soundfile as sf
import numpy as np

FFMPEG = r'E:\AI-Dubbing\models\Applio\ffmpeg.exe'
VOCALS = r'E:\AI-Dubbing\work\S01E01\audio\english_vocals.wav'
# vocals offset is +11.824s
# 944s in video = 955.824s in vocals

with sf.SoundFile(VOCALS) as f:
    sr = f.samplerate
    # let's extract 942 + 11.824 = 953.824 to 962 + 11.824 = 973.824
    start_sec = 942 + 11.824
    dur_sec = 20.0
    f.seek(int(start_sec * sr))
    data = f.read(int(dur_sec * sr))

if data.ndim > 1:
    data = data.mean(axis=1)

sf.write(r'E:\AI-Dubbing\work\test_slices\bogey_scene_vocals_942_962.wav', data, sr)
print(f"Saved bogey_scene_vocals_942_962.wav ({len(data)/sr:.2f}s)")
