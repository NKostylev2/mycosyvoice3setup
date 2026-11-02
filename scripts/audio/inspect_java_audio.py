import soundfile as sf
import numpy as np

VOCALS = r'E:\AI-Dubbing\work\S01E01\audio\english_vocals.wav'
OFFSET = 11.824

# Let's inspect known Java moments in video time:
# 1. D0019: 179.80 - 181.30s ("Massage, good.")
# 2. Virtual combat simulator: 275.0 - 290.0s (Java fighting/roaring)
# 3. Swamp inspection: 540.0 - 565.0s ("Not cold" / grunts)
# 4. Library / monster battle: 1120.0 - 1150.0s
# 5. Ending: 1253.0 - 1255.0s ("Massage.")
# 6. Ending: 1307.5 - 1310.0s ("Jog a lot now!")
# 7. Ending: 1314.5 - 1321.5s (Mmm, Ooh, Ha-ha-ha-ha)

candidates = [
    ("D0019_massage_good", 179.80, 181.30),
    ("sim_combat", 278.0, 287.0),
    ("swamp_investigation", 545.0, 560.0),
    ("ending_massage", 1253.0, 1255.0),
    ("ending_run", 1307.5, 1310.0),
    ("ending_enjoyment_laugh", 1314.5, 1321.5)
]

with sf.SoundFile(VOCALS) as f:
    sr = f.samplerate
    for name, v_start, v_end in candidates:
        start_sample = int((v_start + OFFSET) * sr)
        dur_samples = int((v_end - v_start) * sr)
        f.seek(start_sample)
        chunk = f.read(dur_samples)
        if chunk.ndim > 1:
            chunk = chunk.mean(axis=1)
        amp = np.max(np.abs(chunk))
        rms = np.sqrt(np.mean(chunk**2))
        out_path = f'E:\\AI-Dubbing\\work\\test_slices\\java_{name}.wav'
        sf.write(out_path, chunk, sr)
        print(f"[{name}] {v_start:.2f}-{v_end:.2f}s ({v_end-v_start:.2f}s): max={amp:.4f}, rms={rms:.4f}")
