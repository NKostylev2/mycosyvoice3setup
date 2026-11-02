import soundfile as sf
import numpy as np

for char_id in ['monster_bogeyman', 'java']:
    print(f"\n--- {char_id} raw spans ---")
    p = f'E:\\AI-Dubbing\\work\\S01E01\\rvc_dataset\\{char_id}'
    import os
    for f in sorted(os.listdir(p)):
        if f.endswith('.wav') and 'span' in f:
            y, sr = sf.read(os.path.join(p, f))
            amp = np.max(np.abs(y))
            rms = np.sqrt(np.mean(y**2))
            print(f"  {f}: dur={len(y)/sr:.2f}s, max={amp:.3f}, rms={rms:.4f}")
