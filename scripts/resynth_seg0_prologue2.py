import os
import sys
import time
import torch
import torchaudio
import subprocess
from pathlib import Path

ROOT_DIR = r"E:\AI-Dubbing"
COSY_DIR = os.path.join(ROOT_DIR, "CosyVoice")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if COSY_DIR not in sys.path:
    sys.path.insert(0, COSY_DIR)
matcha_dir = os.path.join(COSY_DIR, "third_party", "Matcha-TTS")
if matcha_dir not in sys.path:
    sys.path.insert(0, matcha_dir)

from cosyvoice.cli.cosyvoice import AutoModel
from scripts.generate_chapter_vid_voice import get_telegram_config, send_telegram_file, send_telegram_message

OUT_DIR = Path(r"E:\AI-Dubbing\output\prologue_02_vid_voice")
CACHE_DIR = OUT_DIR / "segments"
SEG0_PATH = CACHE_DIR / "seg_0000.wav"
SEG0_OLD_BACKUP = CACHE_DIR / "seg_0000_old_prologue2.wav"

VOICE_FILE = r"E:\AI-Dubbing\alltalk_tts\voices\VID_20261101_122350_289.wav"
REF_TXT_FILE = r"E:\AI-Dubbing\alltalk_tts\voices\VID_20261101_122350_289.reference.txt"
FFMPEG_EXE = Path(r"E:\AI-Dubbing\vendor\ffmpeg\bin\ffmpeg.exe")

NEW_TEXT = (
    "Глава вторая. "
    "Что-то тяжёлое приземлилось Гарри на живот. "
    "Он резко сел, вскинув руку, чтобы защитить лицо, и на мгновение, ещё не совсем проснувшись, "
    "был уверен, что его нашёл Дадли."
)

def main():
    print("=" * 60)
    print("Resynthesizing seg_0000.wav for Prologue 2 / Chapter 2")
    print("=" * 60)

    # 1. Backup old seg_0000.wav if not already backed up
    if SEG0_PATH.exists() and not SEG0_OLD_BACKUP.exists():
        import shutil
        shutil.copy2(SEG0_PATH, SEG0_OLD_BACKUP)
        print(f"Backed up old seg_0000.wav to {SEG0_OLD_BACKUP}")

    # 2. Load model
    print("Loading CosyVoice 3 model...")
    model_dir = os.path.join(COSY_DIR, "pretrained_models", "Fun-CosyVoice3-0.5B")
    cosyvoice = AutoModel(model_dir=model_dir)
    sr = cosyvoice.sample_rate

    # 3. Read prompt
    ref_text = ""
    if os.path.exists(REF_TXT_FILE):
        with open(REF_TXT_FILE, "r", encoding="utf-8") as f:
            ref_text = f.read().strip()
    prompt_text = f"You are a helpful assistant.<|endofprompt|>{ref_text}"

    # 4. Synthesize new seg_0000
    print(f"Synthesizing new seg_0000: '{NEW_TEXT}'")
    torch.manual_seed(2026)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(2026)

    t0 = time.time()
    outputs = list(cosyvoice.inference_zero_shot(
        tts_text=NEW_TEXT,
        prompt_text=prompt_text,
        prompt_wav=VOICE_FILE,
        stream=False,
        speed=1.0,
        text_frontend=False
    ))

    assert outputs and outputs[0]["tts_speech"].shape[1] > 0, "Synthesis failed, empty output!"
    wav_chunk = torch.concat([o["tts_speech"] for o in outputs], dim=1)
    torchaudio.save(str(SEG0_PATH), wav_chunk, sr)
    dur = wav_chunk.shape[1] / sr
    print(f"seg_0000.wav synthesized OK: {dur:.2f}s in {time.time() - t0:.2f}s")

    # 5. Verify transcription with Whisper
    os.environ["PATH"] = str(FFMPEG_EXE.parent) + os.pathsep + os.environ.get("PATH", "")
    try:
        import whisper
        wmodel = whisper.load_model("base")
        res = wmodel.transcribe(str(SEG0_PATH), language="ru")
        print(f"Whisper check: '{res['text'].strip()}'")
    except Exception as e:
        print(f"Whisper check error: {e}")

    # 6. Reassemble the entire chapter audio
    print("\nReassembling full chapter audio...")
    from fanfic_pipeline.segmenter import SentenceSegmenter
    from scripts.generate_chapter_vid_voice import load_paragraphs

    text_file = r"M:\Downloads\Пролог_II_для_озвучивания_v2.txt"
    paras = load_paragraphs(text_file)
    # Update first paragraph in memory if needed
    if paras and "Пролог" in paras[0]:
        paras[0] = paras[0].replace("Пролог II", "Глава вторая.").strip()

    seg_model = SentenceSegmenter(tokenizer=cosyvoice.frontend.tokenizer, min_tokens=60, max_tokens=85, min_block_tokens=35)
    segments = seg_model.segment_chapter(paras)
    total_segs = len(segments)
    print(f"Total chapter segments: {total_segs}")

    silence_sentence = torch.zeros((1, int(sr * 0.20))) # 200 ms
    silence_para = torch.zeros((1, int(sr * 0.50)))     # 500 ms
    silence_tail = torch.zeros((1, int(sr * 0.50)))     # 500 ms tail digital silence

    audio_chunks = []
    for s_idx in range(total_segs):
        p = CACHE_DIR / f"seg_{s_idx:04d}.wav"
        if not p.exists():
            print(f"Warning: {p} missing!")
            continue
        chunk, chunk_sr = torchaudio.load(str(p))
        if chunk_sr != sr:
            resampler = torchaudio.transforms.Resample(chunk_sr, sr)
            chunk = resampler(chunk)
        if chunk.dim() == 1:
            chunk = chunk.unsqueeze(0)
        elif chunk.shape[0] > 1:
            chunk = chunk.mean(dim=0, keepdim=True)

        audio_chunks.append(chunk)
        is_last = segments[s_idx].get("is_last_in_p", False) if s_idx < len(segments) else False
        if is_last:
            audio_chunks.append(silence_para)
        else:
            audio_chunks.append(silence_sentence)

    audio_chunks.append(silence_tail)
    full_wav = torch.cat(audio_chunks, dim=1)
    master_wav = OUT_DIR / "prologue_02_vid_voice.wav"
    torchaudio.save(str(master_wav), full_wav, sr)
    total_dur_s = full_wav.shape[1] / sr
    print(f"Master WAV reassembled: {master_wav} (Duration: {total_dur_s/60:.2f} min)")

    # 7. Encode MP3
    final_mp3 = OUT_DIR / "prologue_02_vid_voice.mp3"
    if FFMPEG_EXE.exists():
        cmd = [
            str(FFMPEG_EXE), "-y", "-i", str(master_wav),
            "-codec:a", "libmp3lame", "-b:a", "128k", "-ar", "24000",
            str(final_mp3),
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Standard MP3 encoded: {final_mp3} (Size: {final_mp3.stat().st_size / 1024 / 1024:.2f} MB)")

    # 8. Encode Telegram compact MP3
    compact_mp3 = OUT_DIR / "prologue_02_vid_voice_telegram.mp3"
    if FFMPEG_EXE.exists():
        subprocess.run([
            str(FFMPEG_EXE), "-y", "-i", str(master_wav),
            "-codec:a", "libmp3lame", "-b:a", "48k", "-ac", "1", "-ar", "24000",
            str(compact_mp3)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Telegram compact MP3 encoded: {compact_mp3} (Size: {compact_mp3.stat().st_size / 1024 / 1024:.2f} MB)")

    # 9. Send to Telegram
    token, chat_id, proxy = get_telegram_config()
    caption = (
        f"🎧 <b>Глава вторая (обновлено)</b>\n"
        f"🎙️ Голос: <code>VID_20261101_122350_289</code>\n"
        f"⏱️ Длительность: {total_dur_s / 60:.1f} мин. ({int(total_dur_s)} сек.)\n"
        f"📑 Сегментов: {total_segs}\n"
        f"✏️ <i>Исправлено вступление: «Глава вторая.» вместо «Пролог II»</i>"
    )
    mp3_to_send = compact_mp3 if compact_mp3.exists() else final_mp3
    print("Uploading updated chapter to Telegram...")
    ok = send_telegram_file(mp3_to_send, caption, token, chat_id, proxy=proxy, is_audio=True)
    if not ok:
        ok = send_telegram_file(mp3_to_send, caption, token, chat_id, proxy=proxy, is_audio=False)
    print(f"Telegram upload result: {ok}")

    # 10. Update text file M:\Downloads\Пролог_II_для_озвучивания_v2.txt
    if os.path.exists(text_file):
        with open(text_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if lines and "Пролог" in lines[0]:
            lines[0] = lines[0].replace("Пролог II", "Глава вторая.")
            with open(text_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"Updated {text_file} (replaced 'Пролог II' with 'Глава вторая.')")

    print("\nAll done!")

if __name__ == "__main__":
    main()
