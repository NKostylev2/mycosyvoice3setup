import os
import sys
import shutil
import subprocess
from pathlib import Path
import soundfile as sf
import numpy as np

PROJECT_ROOT = Path(r"E:\AI-Dubbing")
WORK_DIR = PROJECT_ROOT / "work" / "S01E01"
VOCALS_PATH = WORK_DIR / "audio" / "english_vocals.wav"
DATASET_BASE_DIR = WORK_DIR / "rvc_dataset"
VOICES_DIR = PROJECT_ROOT / "alltalk_tts" / "voices"

DEEP_FILTER_EXE = PROJECT_ROOT / "models" / "Applio" / "assets" / "audio-cleanup" / "0.5.6" / "deep-filter-0.5.6-x86_64-pc-windows-msvc.exe"
DEEP_FILTER_MODEL = PROJECT_ROOT / "models" / "Applio" / "assets" / "audio-cleanup" / "0.5.6" / "DeepFilterNet3_onnx.tar.gz"

OFFSET = 11.824

def trim_and_tighten(audio_data, sr, max_pause_sec=0.10, energy_thresh=0.015, min_speech_sec=0.08):
    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)

    frame_len = int(0.01 * sr)
    num_frames = len(audio_data) // frame_len
    if num_frames == 0:
        return audio_data

    energies = np.array([
        np.sqrt(np.mean(audio_data[i*frame_len : (i+1)*frame_len]**2))
        for i in range(num_frames)
    ])

    is_speech = energies > energy_thresh
    smoothed = np.copy(is_speech)
    for i in range(len(smoothed) - 5):
        if is_speech[i]:
            smoothed[i:i+6] = True

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

    max_pause_samples = int(max_pause_sec * sr)
    assembled = []
    prev_end = None

    for s_start, s_end in segments:
        chunk = audio_data[s_start:s_end]
        if prev_end is not None:
            gap = np.zeros(max_pause_samples, dtype=np.float32)
            assembled.append(gap)
        assembled.append(chunk.astype(np.float32))
        prev_end = s_end

    return np.concatenate(assembled)

def process_character(char_id, spans, out_voice_name):
    print(f"\n==========================================")
    print(f" Processing: {char_id} -> {out_voice_name}")
    print(f"==========================================")
    
    target_dir = DATASET_BASE_DIR / char_id
    target_dir.mkdir(parents=True, exist_ok=True)
    
    with sf.SoundFile(str(VOCALS_PATH)) as master_sf:
        sr = master_sf.samplerate
        total_frames = master_sf.frames
        raw_files = []
        
        for idx, (s_start, s_end, desc) in enumerate(spans):
            dur = s_end - s_start
            start_v = s_start + OFFSET
            end_v = s_end + OFFSET
            
            start_samp = max(0, int(start_v * sr))
            end_samp = min(total_frames, int(end_v * sr))
            frames_to_read = end_samp - start_samp
            
            master_sf.seek(start_samp)
            chunk = master_sf.read(frames_to_read, dtype="float32")
            if chunk.ndim > 1:
                chunk = np.mean(chunk, axis=1)
                
            peak = np.max(np.abs(chunk))
            if peak > 1e-5:
                chunk = chunk * ((10 ** (-1.0 / 20.0)) / peak)
                
            out_file = target_dir / f"{char_id}_span_{idx+1:02d}.wav"
            sf.write(str(out_file), chunk.astype(np.float32), sr)
            raw_files.append(out_file)
            print(f"  Span {idx+1}: [{s_start:.2f}-{s_end:.2f}s] ({dur:.2f}s) - {desc}")
            
    # Denoise with DeepFilterNet3
    if DEEP_FILTER_EXE.exists() and DEEP_FILTER_MODEL.exists() and raw_files:
        temp_clean = DATASET_BASE_DIR / f"{char_id}_df_temp"
        temp_clean.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(DEEP_FILTER_EXE),
            "-m", str(DEEP_FILTER_MODEL),
            "-o", str(temp_clean)
        ] + [str(p) for p in raw_files]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0:
            for f in temp_clean.glob("*.wav"):
                shutil.move(str(f), str(target_dir / f.name))
            shutil.rmtree(str(temp_clean), ignore_errors=True)
            print("  [SUCCESS] DeepFilterNet3 denoising applied.")
        else:
            print(f"  [WARNING] DeepFilterNet exited with {res.returncode}")

    # Build tight reference
    ref_chunks = []
    for rf in raw_files:
        d, s_rate = sf.read(str(rf))
        tight_d = trim_and_tighten(d, s_rate, max_pause_sec=0.10, energy_thresh=0.015)
        if len(tight_d) / s_rate >= 0.15:
            ref_chunks.append(tight_d)
            ref_chunks.append(np.zeros(int(0.12 * s_rate), dtype=np.float32))

    if ref_chunks:
        ref_chunks.pop()
        combined_ref = np.concatenate(ref_chunks)
        peak = np.max(np.abs(combined_ref))
        if peak > 1e-5:
            combined_ref = combined_ref * ((10 ** (-1.0 / 20.0)) / peak)
            
        final_voice_file = VOICES_DIR / f"{out_voice_name}.wav"
        sf.write(str(final_voice_file), combined_ref.astype(np.float32), sr)
        print(f"  [SAVED] {final_voice_file}")
        print(f"  Final voice reference duration: {len(combined_ref)/sr:.2f}s (sampling rate: {sr} Hz)")
        
        # Also save to dataset root
        sf.write(str(DATASET_BASE_DIR / f"{char_id}_combined.wav"), combined_ref.astype(np.float32), sr)

def main():
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    DATASET_BASE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. BOGEYMAN SPANS (real sinister villain voice)
    bogeyman_spans = [
        (944.20, 948.60, "You're here because you're naughty children, and you're never going to leave."),
        (953.10, 957.20, "A very naughty young lady who forgot to do her history homework!"),
        (959.70, 960.70, "I know all!")
    ]
    process_character("monster_bogeyman", bogeyman_spans, "monster_bogeyman")

    # 2. JAVA SPANS (deep Neanderthal caveman voice)
    java_spans = [
        (180.20, 181.25, "Massage! Good!"),
        (550.00, 551.00, "Not cold!"),
        (1253.70, 1254.60, "Massage."),
        (1308.00, 1309.50, "Java run now!"),
        (1314.90, 1315.40, "Mmm!"),
        (1317.35, 1317.65, "Ooh!"),
        (1319.20, 1321.40, "Deep caveman chuckle / laugh")
    ]
    process_character("java", java_spans, "java")

if __name__ == "__main__":
    main()
