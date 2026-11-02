import soundfile as sf
import numpy as np

y, sr = sf.read(r'E:\AI-Dubbing\work\test_slices\mp4_942_952.wav')
duration = len(y) / sr
print(f"Slice 942-952s: duration={duration:.2f}s, max_amp={np.max(np.abs(y)):.4f}, rms={np.sqrt(np.mean(y**2)):.4f}")

# D0187 starts at 944.372s, which is 2.372s into this slice!
# and ends at 948.410s, which is 6.410s into this slice!
start_sample = int(2.372 * sr)
end_sample = int(6.410 * sr)
bogey_line = y[start_sample:end_sample]

sf.write(r'E:\AI-Dubbing\work\test_slices\bogey_isolated_d0187.wav', bogey_line, sr)
print(f"Isolated D0187: duration={len(bogey_line)/sr:.2f}s, max_amp={np.max(np.abs(bogey_line)):.4f}")
