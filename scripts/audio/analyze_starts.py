import soundfile as sf
import numpy as np

y_mp4, sr = sf.read(r'E:\AI-Dubbing\work\test_slices\mp4_start.wav')
y_voc, _ = sf.read(r'E:\AI-Dubbing\work\test_slices\vocals_start.wav')

print(f"MP4 start RMS: {np.sqrt(np.mean(y_mp4**2)):.6f}")
print(f"Vocals start RMS: {np.sqrt(np.mean(y_voc**2)):.6f}")

# Find first non-zero in vocals
non_zero_voc = np.where(np.abs(y_voc) > 1e-4)[0]
print(f"First sound in vocals: {non_zero_voc[0]/sr:.3f}s" if len(non_zero_voc) > 0 else "Vocals first 15s is complete silence!")

non_zero_mp4 = np.where(np.abs(y_mp4) > 1e-4)[0]
print(f"First sound in MP4: {non_zero_mp4[0]/sr:.3f}s" if len(non_zero_mp4) > 0 else "MP4 first 15s is complete silence!")
