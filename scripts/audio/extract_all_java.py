import soundfile as sf
import numpy as np

VOCALS = r'E:\AI-Dubbing\work\S01E01\audio\english_vocals.wav'
OFFSET = 11.824

def extract_clip(t_start, t_end, out_name):
    with sf.SoundFile(VOCALS) as f:
        sr = f.samplerate
        s_idx = int((t_start + OFFSET) * sr)
        e_idx = int((t_end + OFFSET) * sr)
        f.seek(s_idx)
        chunk = f.read(e_idx - s_idx)
        if chunk.ndim > 1:
            chunk = chunk.mean(axis=1)
        sf.write(f'E:\\AI-Dubbing\\work\\test_slices\\{out_name}.wav', chunk, sr)
        print(f"Saved {out_name}.wav: dur={len(chunk)/sr:.2f}s, max={np.max(np.abs(chunk)):.4f}")

# 1. D0019: Massage, good
extract_clip(179.7, 181.3, "java_d0019_massage_good")

# 2. Simulator: Java grunting / attacking
extract_clip(280.0, 287.0, "java_simulator_combat")

# 3. D0104: Not cold
extract_clip(549.8, 551.2, "java_d0104_not_cold")

# 4. In bog world fight
extract_clip(978.0, 988.0, "java_bog_fight")

# 5. D0199: Massage
extract_clip(1253.4, 1254.8, "java_d0199_massage")

# 6. D0216: Java run now
extract_clip(1307.8, 1309.8, "java_d0216_run")

# 7. D0220-D0223: Mmm, Ooh, Laugh
extract_clip(1314.8, 1321.6, "java_d0220_laugh")
