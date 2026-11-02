import os
import sys
from pathlib import Path
import subprocess
import time
import soundfile as sf
import numpy as np

# Ensure working directory is AI-Dubbing
BASE_DIR = Path(r"E:\AI-Dubbing")
OUT_DIR = BASE_DIR / "output" / "prologue_02_vid_voice"
CACHE_DIR = OUT_DIR / "segments"
OLD_SEG0_PATH = CACHE_DIR / "seg_0000_old_prologue2.wav"
NEW_SEG0_PATH = CACHE_DIR / "seg_0000.wav"
BACKUP_SWALLOWED_PATH = CACHE_DIR / "seg_0000_swallowed_ending.wav"
FFMPEG_EXE = BASE_DIR / "vendor" / "ffmpeg" / "bin" / "ffmpeg.exe"

# Telegram helper
sys.path.insert(0, str(BASE_DIR))
from scripts.generate_chapter_vid_voice import get_telegram_config, send_telegram_file

def main():
    print("=== Remontage of seg_0000.wav ===")
    assert OLD_SEG0_PATH.exists(), f"Missing old segment: {OLD_SEG0_PATH}"
    assert NEW_SEG0_PATH.exists(), f"Missing new segment: {NEW_SEG0_PATH}"

    # 1. Backup current seg_0000 (which had swallowed ending 'Да' instead of 'Дадли')
    if not BACKUP_SWALLOWED_PATH.exists():
        import shutil
        shutil.copy2(NEW_SEG0_PATH, BACKUP_SWALLOWED_PATH)
        print(f"Backed up swallowed ending segment to {BACKUP_SWALLOWED_PATH.name}")

    old_data, sr = sf.read(str(OLD_SEG0_PATH))
    new_data, sr_new = sf.read(str(NEW_SEG0_PATH))
    assert sr == sr_new == 24000, f"Sample rate mismatch: {sr} vs {sr_new}"

    # 2. Extract 'Глава вторая.' from new_data
    # In new_data, speech ends around 1.55s, silence from 1.56s to 2.16s
    cut_new_end = int(1.65 * sr)
    part_new = new_data[:cut_new_end].copy()
    fade_len = int(0.01 * sr) # 10 ms
    part_new[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)

    # 3. Chapter title pause
    pause_sec = 0.35  # 350 ms silence
    pause = np.zeros(int(pause_sec * sr), dtype=np.float32)

    # 4. Extract 'Что-то тяжёлое...' through '...нашёл Дадли.' from old_data
    # In old_data, silence is between 1.39s and 1.51s, 'Что-то...' starts at 1.51s
    cut_old_start = int(1.46 * sr)
    part_old = old_data[cut_old_start:].copy()
    part_old[:fade_len] *= np.linspace(0.0, 1.0, fade_len)

    # 5. Concatenate
    spliced = np.concatenate([part_new, pause, part_old])
    sf.write(str(NEW_SEG0_PATH), spliced, sr)
    total_dur_s = len(spliced) / sr
    print(f"Remontaged seg_0000.wav saved successfully. Duration: {total_dur_s:.2f}s")

    # 6. Verify with Whisper
    os.environ["PATH"] = str(FFMPEG_EXE.parent) + os.pathsep + os.environ.get("PATH", "")
    try:
        import whisper
        wmodel = whisper.load_model("base")
        res = wmodel.transcribe(str(NEW_SEG0_PATH), language="ru")
        transcription = res["text"].strip()
        print(f"Whisper transcription of remontaged seg_0000.wav:\n  '{transcription}'")
    except Exception as e:
        print(f"Whisper check error: {e}")
        transcription = ""

    # 7. Reassemble full chapter audio using segmenter metadata
    print("\nReassembling full chapter audio (323 segments)...")
    from transformers import AutoTokenizer
    from fanfic_pipeline.segmenter import SentenceSegmenter
    from scripts.generate_chapter_vid_voice import load_paragraphs

    tok = AutoTokenizer.from_pretrained(r"E:\AI-Dubbing\CosyVoice\pretrained_models\Fun-CosyVoice3-0.5B\CosyVoice-BlankEN")
    text_file = r"M:\Downloads\Пролог_II_для_озвучивания_v2.txt"
    paras = load_paragraphs(text_file)
    seg_model = SentenceSegmenter(tokenizer=tok, min_tokens=60, max_tokens=85, min_block_tokens=35)
    segments = seg_model.segment_chapter(paras)
    total_segs = len(segments)
    print(f"Total chapter segments: {total_segs}")

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
    master_wav = OUT_DIR / "prologue_02_vid_voice.wav"
    sf.write(str(master_wav), full_wav_data, sr)
    chapter_dur_s = len(full_wav_data) / sr
    print(f"Master WAV assembled: {master_wav} (Duration: {chapter_dur_s/60:.2f} min / {chapter_dur_s:.1f}s)")

    # 8. Encode MP3 (128k)
    final_mp3 = OUT_DIR / "prologue_02_vid_voice.mp3"
    if FFMPEG_EXE.exists():
        subprocess.run([
            str(FFMPEG_EXE), "-y", "-i", str(master_wav),
            "-codec:a", "libmp3lame", "-b:a", "128k", "-ar", "24000",
            str(final_mp3),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Standard MP3 encoded: {final_mp3} ({final_mp3.stat().st_size / 1024 / 1024:.2f} MB)")

    # 9. Encode Telegram compact MP3 (48k mono)
    compact_mp3 = OUT_DIR / "prologue_02_vid_voice_telegram.mp3"
    if FFMPEG_EXE.exists():
        subprocess.run([
            str(FFMPEG_EXE), "-y", "-i", str(master_wav),
            "-codec:a", "libmp3lame", "-b:a", "48k", "-ac", "1", "-ar", "24000",
            str(compact_mp3),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Telegram compact MP3 encoded: {compact_mp3} ({compact_mp3.stat().st_size / 1024 / 1024:.2f} MB)")

    # 10. Send to Telegram
    token, chat_id, proxy = get_telegram_config()
    caption = (
        f"🎧 <b>Глава вторая (перемонтировано seg_0000)</b>\n"
        f"🎙️ Голос: <code>VID_20261101_122350_289</code>\n"
        f"⏱️ Длительность: {chapter_dur_s / 60:.1f} мин. ({int(chapter_dur_s)} сек.)\n"
        f"📑 Вступление: <i>«Глава вторая» бесшовно вмонтировано вместо «Пролог II»</i>\n"
        f"✅ Окончание абзаца: <i>«...был уверен, что его нашёл Дадли.» (сохранено полностью)</i>"
    )
    mp3_to_send = compact_mp3 if compact_mp3.exists() else final_mp3
    print("Uploading remontaged chapter to Telegram...")
    ok = send_telegram_file(mp3_to_send, caption, token, chat_id, proxy=proxy, is_audio=True)
    if not ok:
        ok = send_telegram_file(mp3_to_send, caption, token, chat_id, proxy=proxy, is_audio=False)
    print(f"Telegram upload result: {ok}")

    print("\nRemontage complete!")

if __name__ == "__main__":
    main()
