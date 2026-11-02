import soundfile as sf
import numpy as np

VOCALS = r'E:\AI-Dubbing\work\S01E01\audio\english_vocals.wav'
OFFSET = 11.824

with sf.SoundFile(VOCALS) as f:
    sr = f.samplerate
    s_idx = int((405.0 + OFFSET) * sr)
    e_idx = int((411.0 + OFFSET) * sr)
    f.seek(s_idx)
    chunk = f.read(e_idx - s_idx)
    if chunk.ndim > 1:
        chunk = chunk.mean(axis=1)
    sf.write(r'E:\AI-Dubbing\work\test_slices\sniff_405_411.wav', chunk, sr)
    print("Saved sniff_405_411.wav")
