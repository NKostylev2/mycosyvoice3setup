import os
import sys
from pathlib import Path
import subprocess
import time
import soundfile as sf
import numpy as np

# Ensure working directory is AI-Dubbing
BASE_DIR = Path(r"E:\AI-Dubbing")
OUT_DIR = BASE_DIR / "output" / "chapter_01_vid_voice"
CACHE_DIR = OUT_DIR / "segments"
TITLE_WAV = BASE_DIR / "output" / "test_title" / "takes" / "take_777.wav"
SEG0_WAV = CACHE_DIR / "seg_0000.wav"
SEG0_BACKUP = CACHE_DIR / "seg_0000_original_before_intro.wav"
FFMPEG_EXE = BASE_DIR / "vendor" / "ffmpeg" / "bin" / "ffmpeg.exe"

def main():
    print("=== Adding Title Intro to Chapter 1 ===")
    assert TITLE_WAV.exists(), f"Missing title take: {TITLE_WAV}"
    assert SEG0_WAV.exists(), f"Missing chapter 1 seg 0: {SEG0_WAV}"

    # 1. Backup original seg_0000 if not already backed up
    if not SEG0_BACKUP.exists():
        import shutil
        shutil.copy2(SEG0_WAV, SEG0_BACKUP)
        print(f"Backed up original seg_0000 to {SEG0_BACKUP.name}")

    # Copy title take to chapter folder for persistent record
    import shutil
    shutil.copy2(TITLE_WAV, OUT_DIR / "title_intro.wav")

    # 2. Load audio
    title_data, sr = sf.read(str(TITLE_WAV))
    orig_seg0, orig_sr = sf.read(str(SEG0_BACKUP))
    assert sr == orig_sr == 24000, f"SR mismatch: {sr} vs {orig_sr}"

    # 3. Splice
    # Title part: "Змея, лев и выдра, философский камень, глава первая." (5.60s)
    part_title = title_data.copy()

    # Pause: 500 ms digital silence
    pause = np.zeros(int(0.50 * sr), dtype=np.float32)

    # Narrative part: from 2.30s (silence right before "Если за всё время...")
    # In original seg_0000, "Философский камень" was at 0.0 - 1.95s, silence 1.95 - 2.32s
    cut_story_start = int(2.30 * sr)
    part_story = orig_seg0[cut_story_start:].copy()

    # Smooth 10ms fade-in
    fade_len = int(0.01 * sr)
    part_story[:fade_len] *= np.linspace(0.0, 1.0, fade_len)

    # Concatenate
    spliced_seg0 = np.concatenate([part_title, pause, part_story])
    sf.write(str(SEG0_WAV), spliced_seg0, sr)
    print(f"Updated seg_0000.wav saved. Duration: {len(spliced_seg0)/sr:.2f}s")

    # 4. Verify with Whisper
    os.environ["PATH"] = str(FFMPEG_EXE.parent) + os.pathsep + os.environ.get("PATH", "")
    try:
        import whisper
        wmodel = whisper.load_model("base")
        res = wmodel.transcribe(str(SEG0_WAV), language="ru")
        print(f"Whisper transcription of new seg_0000.wav:\n  '{res['text'].strip()}'")
    except Exception as e:
        print(f"Whisper check error: {e}")

    # 5. Reassemble full chapter (376 segments)
    print("\nReassembling full Chapter 1 audio (376 segments)...")
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    from transformers import AutoTokenizer
    from fanfic_pipeline.segmenter import SentenceSegmenter
    from scripts.generate_chapter_vid_voice import load_paragraphs

    tok = AutoTokenizer.from_pretrained(r"E:\AI-Dubbing\CosyVoice\pretrained_models\Fun-CosyVoice3-0.5B\CosyVoice-BlankEN")
    docx_path = r"M:\dev\Telegram Remote Control\%D0%93%D0%BB%D0%B0%D0%B2%D0%B0_1_%D0%BF%D0%BE%D0%BB%D0%BD%D1%8B%D0%B9.docx"
    paras = load_paragraphs(docx_path)
    seg_model = SentenceSegmenter(tokenizer=tok, min_tokens=60, max_tokens=85, min_block_tokens=35)
    segments = seg_model.segment_chapter(paras)
    total_segs = len(segments)
    print(f"Total chapter segments from segmenter: {total_segs}")

    silence_sentence = np.zeros((int(sr * 0.20),), dtype=np.float32) # 200 ms
    silence_para = np.zeros((int(sr * 0.50),), dtype=np.float32)     # 500 ms
    silence_tail = np.zeros((int(sr * 0.50),), dtype=np.float32)     # 500 ms tail

    all_chunks = []
    for s_idx in range(total_segs):
        p = CACHE_DIR / f"seg_{s_idx:04d}.wav"
        if not p.exists():
            print(f"Warning: {p} missing!")
            continue
        c_data, c_sr = sf.read(str(p))
        if c_sr != sr:
            import resampy
            c_data = resampy.resample(c_data, c_sr, sr)
        if c_data.ndim > 1:
            c_data = c_data.mean(axis=1)

        all_chunks.append(c_data)
        is_last = segments[s_idx].get("is_last_in_p", False) if s_idx < len(segments) else False
        if is_last:
            all_chunks.append(silence_para)
        else:
            all_chunks.append(silence_sentence)

    all_chunks.append(silence_tail)
    full_wav_data = np.concatenate(all_chunks)
    master_wav = OUT_DIR / "chapter_01_VID_voice.wav"
    sf.write(str(master_wav), full_wav_data, sr)
    chapter_dur_s = len(full_wav_data) / sr
    print(f"Master WAV assembled: {master_wav} (Duration: {chapter_dur_s/60:.2f} min / {chapter_dur_s:.1f}s)")

    # 6. Encode MP3 (128k)
    final_mp3 = OUT_DIR / "chapter_01_VID_voice.mp3"
    if FFMPEG_EXE.exists():
        subprocess.run([
            str(FFMPEG_EXE), "-y", "-i", str(master_wav),
            "-codec:a", "libmp3lame", "-b:a", "128k", "-ar", "24000",
            str(final_mp3),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Standard MP3 encoded: {final_mp3} ({final_mp3.stat().st_size / 1024 / 1024:.2f} MB)")

    # 7. Encode compact MP3 (48k mono)
    compact_mp3 = OUT_DIR / "chapter_01_VID_voice_telegram.mp3"
    if FFMPEG_EXE.exists():
        subprocess.run([
            str(FFMPEG_EXE), "-y", "-i", str(master_wav),
            "-codec:a", "libmp3lame", "-b:a", "48k", "-ac", "1", "-ar", "24000",
            str(compact_mp3),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Telegram compact MP3 encoded: {compact_mp3} ({compact_mp3.stat().st_size / 1024 / 1024:.2f} MB)")

    print("\nNOTE: Telegram sending skipped as requested by user.")
    print("All files updated locally and ready.")

if __name__ == "__main__":
    main()
