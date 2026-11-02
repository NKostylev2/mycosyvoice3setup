import soundfile as sf
import numpy as np

VOCALS = r'E:\AI-Dubbing\work\S01E01\audio\english_vocals.wav'
OFFSET = 11.824

# The 3 segments in timeline/video coordinates:
# Seg 1: 944.20s - 948.60s
# Seg 2: 953.10s - 957.20s
# Seg 3: 959.70s - 960.70s

segments_video = [
    (944.20, 948.60, "You're here because you're naughty children, and you're never going to leave."),
    (953.10, 957.20, "A very naughty young lady who forgot to do her history homework!"),
    (959.70, 960.70, "I know all!")
]

with sf.SoundFile(VOCALS) as f:
    sr = f.samplerate
    audio_parts = []
    for s_start, s_end, desc in segments_video:
        start_v = s_start + OFFSET
        end_v = s_end + OFFSET
        f.seek(int(start_v * sr))
        chunk = f.read(int((end_v - start_v) * sr))
        if chunk.ndim > 1:
            chunk = chunk.mean(axis=1)
        audio_parts.append(chunk)
        print(f"Extracted [{s_start:.2f}-{s_end:.2f}s] ({len(chunk)/sr:.2f}s): {desc}")

combined = np.concatenate(audio_parts)
print(f"Combined Bogeyman total duration: {len(combined)/sr:.2f}s, max_amp: {np.max(np.abs(combined)):.4f}")

sf.write(r'E:\AI-Dubbing\work\test_slices\bogeyman_real_reference.wav', combined, sr)
