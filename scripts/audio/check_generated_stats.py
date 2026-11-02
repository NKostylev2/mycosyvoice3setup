import os
import soundfile as sf
import numpy as np

files = [
    r'E:\AI-Dubbing\alltalk_tts\outputs\test_bogeyman_final.wav',
    r'E:\AI-Dubbing\alltalk_tts\outputs\test_java_d0019_final.wav',
    r'E:\AI-Dubbing\alltalk_tts\outputs\test_java_d0104_final.wav',
    r'E:\AI-Dubbing\alltalk_tts\outputs\test_java_d0216_final.wav'
]

for f in files:
    d, sr = sf.read(f)
    amp = np.max(np.abs(d))
    rms = np.sqrt(np.mean(d**2))
    print(f"{os.path.basename(f)}: dur={len(d)/sr:.2f}s, peak={amp:.3f}, rms={rms:.4f}")
