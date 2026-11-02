import os
import soundfile as sf
import numpy as np

def trim_tight(audio, sr, energy_thresh=0.008, max_pause=0.10):
    frame_len = int(0.01 * sr)
    num_frames = len(audio) // frame_len
    energies = np.array([
        np.sqrt(np.mean(audio[i*frame_len : (i+1)*frame_len]**2))
        for i in range(num_frames)
    ])
    is_speech = energies > energy_thresh
    # smooth
    for i in range(len(is_speech) - 6):
        if is_speech[i]:
            is_speech[i:i+7] = True
            
    segments = []
    in_seg = False
    start = 0
    for i, sp in enumerate(is_speech):
        if sp and not in_seg:
            in_seg = True
            start = i
        elif not sp and in_seg:
            in_seg = False
            if (i - start) * 0.01 >= 0.08:
                segments.append((start * frame_len, i * frame_len))
    if in_seg:
        segments.append((start * frame_len, num_frames * frame_len))
        
    assembled = []
    prev_end = None
    for s_start, s_end in segments:
        chunk = audio[s_start:s_end]
        if prev_end is not None:
            assembled.append(np.zeros(int(max_pause * sr), dtype=np.float32))
        assembled.append(chunk)
        prev_end = s_end
        
    return np.concatenate(assembled) if assembled else audio

# Bogeyman
p_bogey = r'E:\AI-Dubbing\work\S01E01\rvc_dataset\monster_bogeyman'
bogey_chunks = []
for f in ['monster_bogeyman_span_01.wav', 'monster_bogeyman_span_02.wav']:
    d, sr = sf.read(f"{p_bogey}\\{f}")
    peak = np.max(np.abs(d))
    if peak > 0:
        d = d * (0.89 / peak) # normalize to -1 dB
    tight = trim_tight(d, sr)
    bogey_chunks.append(tight)
    bogey_chunks.append(np.zeros(int(0.12 * sr), dtype=np.float32))

full_bogey = np.concatenate(bogey_chunks[:-1])
print(f"Bogeyman tightened duration: {len(full_bogey)/sr:.2f}s")
sf.write(r'E:\AI-Dubbing\alltalk_tts\voices\monster_bogeyman.wav', full_bogey, sr)

# Java
p_java = r'E:\AI-Dubbing\work\S01E01\rvc_dataset\java'
java_chunks = []
for f in sorted(os.listdir(p_java)):
    if f.endswith('.wav') and 'span' in f:
        d, sr = sf.read(f"{p_java}\\{f}")
        peak = np.max(np.abs(d))
        if peak > 0:
            d = d * (0.89 / peak)
        tight = trim_tight(d, sr)
        if len(tight)/sr >= 0.15:
            java_chunks.append(tight)
            java_chunks.append(np.zeros(int(0.12 * sr), dtype=np.float32))

full_java = np.concatenate(java_chunks[:-1])
print(f"Java tightened duration: {len(full_java)/sr:.2f}s")
sf.write(r'E:\AI-Dubbing\alltalk_tts\voices\java.wav', full_java, sr)
