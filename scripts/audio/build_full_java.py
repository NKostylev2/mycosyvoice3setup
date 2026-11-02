import soundfile as sf
import numpy as np

clips = [
    r'E:\AI-Dubbing\work\test_slices\exact_java_massage_good.wav',
    r'E:\AI-Dubbing\work\test_slices\exact_java_not_cold.wav',
    r'E:\AI-Dubbing\work\test_slices\exact_java_massage_2.wav',
    r'E:\AI-Dubbing\work\test_slices\exact_java_run_now.wav',
    r'E:\AI-Dubbing\work\test_slices\exact_java_mmm.wav',
    r'E:\AI-Dubbing\work\test_slices\exact_java_ooh.wav',
    r'E:\AI-Dubbing\work\test_slices\exact_java_laugh.wav'
]

combined = []
sr = None
for c in clips:
    data, sr = sf.read(c)
    # Add a short 100ms pause between utterances
    pause = np.zeros(int(0.1 * sr), dtype=data.dtype)
    combined.append(data)
    combined.append(pause)

full_java = np.concatenate(combined)
out_path = r'E:\AI-Dubbing\work\test_slices\java_full_reference.wav'
sf.write(out_path, full_java, sr)
print(f"Combined Java reference saved: {out_path}, dur={len(full_java)/sr:.2f}s, sr={sr}")
