import soundfile as sf
import numpy as np

VOCALS = r'E:\AI-Dubbing\work\S01E01\audio\english_vocals.wav'

with sf.SoundFile(VOCALS) as f:
    sr = f.samplerate
    # 956.196s to 960.234s
    start_sec = 944.372 + 11.824
    end_sec = 948.410 + 11.824
    f.seek(int(start_sec * sr))
    data = f.read(int((end_sec - start_sec) * sr))

if data.ndim > 1:
    data = data.mean(axis=1)

sf.write(r'E:\AI-Dubbing\work\test_slices\bogey_vocals_d0187.wav', data, sr)
print(f"Extracted bogey_vocals_d0187.wav: sr={sr}, dur={len(data)/sr:.2f}s, max_amp={np.max(np.abs(data)):.4f}")
