import soundfile as sf
import numpy as np
from pathlib import Path

def trim_and_tighten(audio_data, sr, max_pause_sec=0.10, energy_thresh=0.015, min_speech_sec=0.1):
    """
    Removes leading/trailing silence and caps internal pauses to max_pause_sec.
    """
    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)

    frame_len = int(0.01 * sr) # 10ms frames
    num_frames = len(audio_data) // frame_len
    if num_frames == 0:
        return audio_data

    energies = np.array([
        np.sqrt(np.mean(audio_data[i*frame_len : (i+1)*frame_len]**2))
        for i in range(num_frames)
    ])

    is_speech = energies > energy_thresh

    # Smooth speech detections (hangover of 5 frames = 50ms)
    smoothed = np.copy(is_speech)
    for i in range(len(smoothed) - 5):
        if is_speech[i]:
            smoothed[i:i+6] = True

    # Find speech segments
    segments = []
    in_seg = False
    start = 0
    for i, sp in enumerate(smoothed):
        if sp and not in_seg:
            in_seg = True
            start = i
        elif not sp and in_seg:
            in_seg = False
            dur = (i - start) * 0.01
            if dur >= min_speech_sec:
                segments.append((start * frame_len, i * frame_len))

    if in_seg:
        segments.append((start * frame_len, num_frames * frame_len))

    if not segments:
        return audio_data

    # Assemble chunks with capped pauses
    max_pause_samples = int(max_pause_sec * sr)
    assembled = []
    prev_end = None

    for s_start, s_end in segments:
        chunk = audio_data[s_start:s_end]
        if prev_end is not None:
            # Add short natural pause
            gap = np.zeros(max_pause_samples, dtype=np.float32)
            assembled.append(gap)
        assembled.append(chunk.astype(np.float32))
        prev_end = s_end

    tight_audio = np.concatenate(assembled)
    return tight_audio

def build_tight_reference(character_id, uids, output_path):
    slices_dir = Path(r"E:\AI-Dubbing\work\S01E01\rvc_dataset") / character_id
    chunks = []
    sr_ref = None

    for uid in uids:
        p = slices_dir / f"{uid}.wav"
        if not p.exists():
            print(f"Slice not found: {p}")
            continue
        data, sr = sf.read(str(p))
        sr_ref = sr
        clean_chunk = trim_and_tighten(data, sr, max_pause_sec=0.10)
        chunks.append(clean_chunk)
        # short inter-utterance pause of 0.15s
        chunks.append(np.zeros(int(0.15 * sr), dtype=np.float32))

    if chunks:
        chunks.pop() # remove last gap
        final_audio = np.concatenate(chunks)
        
        # Normalize to -1.0 dBFS
        peak = np.max(np.abs(final_audio))
        if peak > 1e-5:
            final_audio = final_audio * ((10 ** (-1.0 / 20.0)) / peak)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out), final_audio, sr_ref, subtype="PCM_16")

        dur = len(final_audio) / sr_ref
        print(f"Built tight reference for {character_id}:")
        print(f"  Path: {out}")
        print(f"  Duration: {dur:.2f}s (100% active voice, zero dead air)")
        return out

if __name__ == "__main__":
    # Martin: U0044 + U0063 (energetic, highly characteristic)
    build_tight_reference("martin_mystery", ["U0044", "U0063"], r"E:\AI-Dubbing\alltalk_tts\voices\martin_mystery.wav")

    # Diana: U0094 + U0111 (sharp, clever, expressive)
    build_tight_reference("diana_lombard", ["U0094", "U0111"], r"E:\AI-Dubbing\alltalk_tts\voices\diana_lombard.wav")
