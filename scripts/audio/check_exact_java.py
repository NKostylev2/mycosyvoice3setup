import soundfile as sf
import numpy as np

VOCALS = r'E:\AI-Dubbing\work\S01E01\audio\english_vocals.wav'
OFFSET = 11.824

def check_segment(start_s, end_s, name):
    with sf.SoundFile(VOCALS) as f:
        sr = f.samplerate
        s_idx = int((start_s + OFFSET) * sr)
        e_idx = int((end_s + OFFSET) * sr)
        f.seek(s_idx)
        chunk = f.read(e_idx - s_idx)
        if chunk.ndim > 1:
            chunk = chunk.mean(axis=1)
        amp = np.max(np.abs(chunk))
        rms = np.sqrt(np.mean(chunk**2))
        print(f"[{name}] {start_s:.2f}-{end_s:.2f}s (dur={end_s-start_s:.2f}s): max={amp:.4f}, rms={rms:.4f}")
        sf.write(f'E:\\AI-Dubbing\\work\\test_slices\\exact_{name}.wav', chunk, sr)

# Java exact timestamps in timeline:
# D0019: 180.20 - 181.20s ("Massage! Good!")
check_segment(180.20, 181.25, "java_massage_good")

# D0104: 550.00 - 551.00s ("Not cold!")
check_segment(550.00, 551.00, "java_not_cold")

# D0199: 1253.70 - 1254.60s ("Massage.")
check_segment(1253.70, 1254.60, "java_massage_2")

# D0216: 1308.00 - 1309.50s ("Java run now!")
check_segment(1308.00, 1309.50, "java_run_now")

# D0220: 1314.94 - 1315.30s ("Mmm!")
check_segment(1314.90, 1315.40, "java_mmm")

# D0221: 1317.35 - 1317.65s ("Ooh!")
check_segment(1317.35, 1317.65, "java_ooh")

# D0222: 1319.20 - 1321.40s (Deep caveman laughter)
check_segment(1319.20, 1321.40, "java_laugh")
