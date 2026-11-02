import soundfile as sf
import numpy as np

VOCALS = r'E:\AI-Dubbing\work\S01E01\audio\english_vocals.wav'
OFFSET = 11.824

# Let's inspect library investigation 365s to 420s
with sf.SoundFile(VOCALS) as f:
    sr = f.samplerate
    # scan 360s to 430s in 5s windows
    for t in range(360, 430, 5):
        s_idx = int((t + OFFSET) * sr)
        e_idx = int((t + 5 + OFFSET) * sr)
        f.seek(s_idx)
        chunk = f.read(e_idx - s_idx)
        if chunk.ndim > 1:
            chunk = chunk.mean(axis=1)
        amp = np.max(np.abs(chunk))
        rms = np.sqrt(np.mean(chunk**2))
        if rms > 0.02:
            print(f"Vocals window {t}-{t+5}s: max={amp:.3f}, rms={rms:.3f}")
