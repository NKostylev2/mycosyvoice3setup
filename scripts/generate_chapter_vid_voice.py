import os
import sys
import time
import json
import logging
import subprocess
import urllib.request
import urllib.error
import argparse
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

# Setup root paths
ROOT_DIR = r"E:\AI-Dubbing"
COSY_DIR = os.path.join(ROOT_DIR, "CosyVoice")
OUT_DIR = Path(r"E:\AI-Dubbing\output\chapter_01_vid_voice")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR = OUT_DIR / "segments"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = OUT_DIR / "generation.log"
STATUS_FILE = OUT_DIR / "status.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("ChapterVIDGenerator")

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if COSY_DIR not in sys.path:
    sys.path.insert(0, COSY_DIR)
matcha_dir = os.path.join(COSY_DIR, "third_party", "Matcha-TTS")
if matcha_dir not in sys.path:
    sys.path.insert(0, matcha_dir)

import re
import torch
import torchaudio
from cosyvoice.cli.cosyvoice import AutoModel
from fanfic_pipeline.segmenter import SentenceSegmenter

FFMPEG_EXE = Path(r"E:\AI-Dubbing\vendor\ffmpeg\bin\ffmpeg.exe")
VOICE_FILE = r"E:\AI-Dubbing\alltalk_tts\voices\VID_20261101_122350_289.wav"
VOICE_NAME = "VID_20261101_122350_289"
CHAPTER_TEXT_PATH = r"M:\dev\Telegram Remote Control\%D0%93%D0%BB%D0%B0%D0%B2%D0%B0_1_%D0%BF%D0%BE%D0%BB%D0%BD%D1%8B%D0%B9.docx"

def load_paragraphs(file_path: str) -> list:
    p = Path(file_path)
    if p.suffix.lower() == ".docx":
        z = zipfile.ZipFile(str(p))
        tree = ET.fromstring(z.read("word/document.xml"))
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        paras = []
        for p_node in tree.iterfind('.//w:p', namespaces):
            texts = [node.text for node in p_node.iterfind('.//w:t', namespaces) if node.text]
            if texts:
                t = "".join(texts).strip()
                if t:
                    paras.append(t)
        return paras
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.read().splitlines() if line.strip()]

def get_telegram_config():
    token = None
    proxy = "http://127.0.0.1:1372"
    env_file = Path(r"M:\dev\Telegram Remote Control\.env")
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip("\"'")
                elif line.startswith("TELEGRAM_PROXY="):
                    proxy = line.split("=", 1)[1].strip("\"'")

    chat_id = 373648438
    db_file = Path(r"M:\dev\Telegram Remote Control\data\tasks.sqlite3")
    if db_file.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_file))
            cur = conn.cursor()
            cur.execute("SELECT chat_id FROM tasks WHERE chat_id IS NOT NULL ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row and row[0]:
                chat_id = row[0]
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to read chat_id from sqlite: {e}")

    return token, chat_id, proxy

def get_telegram_opener(proxy: str = None):
    if proxy:
        proxy_handler = urllib.request.ProxyHandler({"https": proxy, "http": proxy})
        return urllib.request.build_opener(proxy_handler)
    return urllib.request.build_opener()

def send_telegram_message(text: str, token: str, chat_id: int, proxy: str = None) -> bool:
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Telegram-Progress-Reporter/1.0"},
    )
    opener = get_telegram_opener(proxy)
    try:
        with opener.open(req, timeout=15) as resp:
            return True
    except Exception as e:
        logger.warning(f"Failed to send telegram message: {e}")
        return False

def send_telegram_file(file_path: Path, caption: str, token: str, chat_id: int, proxy: str = None, is_audio: bool = True, title: str = None) -> bool:
    if not token or not file_path.exists():
        return False

    url = f"https://api.telegram.org/bot{token}/{'sendAudio' if is_audio else 'sendDocument'}"
    boundary = "----WebKitFormBoundaryAudio" + str(int(time.time()))
    file_bytes = file_path.read_bytes()
    filename = file_path.name
    field_name = "audio" if is_audio else "document"

    body_parts = []
    body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    body_parts.append(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode("utf-8"))
    if is_audio:
        track_title = title if title else "Audiobook"
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(f'Content-Disposition: form-data; name="title"\r\n\r\n{track_title}\r\n'.encode("utf-8"))
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(f'Content-Disposition: form-data; name="performer"\r\n\r\nCosyVoice 3 ({VOICE_NAME})\r\n'.encode("utf-8"))
    if caption:
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode("utf-8"))
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(f'Content-Disposition: form-data; name="parse_mode"\r\n\r\nHTML\r\n'.encode("utf-8"))
    body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    body_parts.append(
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: audio/mpeg\r\n\r\n".encode("utf-8")
    )
    body_parts.append(file_bytes)
    body_parts.append(b"\r\n")
    body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))

    payload = b"".join(body_parts)
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "Telegram-Voice-Sender/1.0",
        },
    )
    opener = get_telegram_opener(proxy)
    try:
        with opener.open(req, timeout=180) as resp:
            logger.info(f"Telegram upload OK: {filename}")
            return True
    except Exception as e:
        logger.warning(f"Upload failed for {filename}: {e}")
        return False

def update_status(data: dict):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Could not write status file: {e}")

def main():
    global OUT_DIR, CACHE_DIR, LOG_FILE, STATUS_FILE

    parser = argparse.ArgumentParser()
    parser.add_argument("--text-path", default=CHAPTER_TEXT_PATH)
    parser.add_argument("--voice-file", default=VOICE_FILE)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--title", default=None)
    parser.add_argument("--clean-cache", action="store_true")
    args = parser.parse_args()

    text_path = args.text_path
    if not os.path.exists(text_path):
        alt_path = r"M:\dev\Telegram Remote Control\Глава_1_полный.docx"
        if os.path.exists(alt_path):
            text_path = alt_path

    voice_file = args.voice_file
    voice_name = Path(voice_file).stem

    # Dynamic output directory
    if args.output_dir:
        OUT_DIR = Path(args.output_dir)
    else:
        stem = Path(text_path).stem
        if "Пролог" in stem or "%D0%9F%D1%80%D0%BE%D0%BB%D0%BE%D0%B3" in stem or "Prolog" in stem:
            OUT_DIR = Path(ROOT_DIR) / "output" / "prologue_02_vid_voice"
        elif "Глава_1" in stem or "%D0%93%D0%BB%D0%B0%D0%B2%D0%B0_1" in stem or "chapter_01" in stem:
            OUT_DIR = Path(ROOT_DIR) / "output" / "chapter_01_vid_voice"
        else:
            safe_name = re.sub(r'[^\w\-_\.]', '_', stem)
            OUT_DIR = Path(ROOT_DIR) / "output" / safe_name

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR = OUT_DIR / "segments"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE = OUT_DIR / "generation.log"
    STATUS_FILE = OUT_DIR / "status.json"

    file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)

    # Determine chapter title
    if args.title:
        chapter_title = args.title
    elif "Пролог" in str(text_path) or "%D0%9F%D1%80%D0%BE%D0%BB%D0%BE%D0%B3" in str(text_path):
        chapter_title = "Пролог II"
    elif "Глава_1" in str(text_path) or "%D0%93%D0%BB%D0%B0%D0%B2%D0%B0_1" in str(text_path):
        chapter_title = "Глава 1: Философский камень"
    else:
        chapter_title = Path(text_path).stem

    if args.clean_cache:
        for f in CACHE_DIR.glob("*.wav"):
            try:
                f.unlink()
            except Exception:
                pass

    logger.info(f"=== Starting Full Chapter Generation Pipeline ({voice_name}) -> {OUT_DIR} ===")
    token, chat_id, proxy = get_telegram_config()
    logger.info(f"Telegram Config: Token Present={bool(token)}, ChatID={chat_id}, Proxy={proxy}")

    if not os.path.exists(voice_file):
        logger.error(f"Voice reference file missing: {voice_file}")
        update_status({"state": "failed", "error": f"Voice missing: {voice_file}"})
        return

    if not os.path.exists(text_path):
        logger.error(f"Chapter text file missing: {text_path}")
        update_status({"state": "failed", "error": f"Chapter text missing: {text_path}"})
        return

    # 1. Load CosyVoice Model first to get tokenizer
    model_dir = os.path.join(COSY_DIR, "pretrained_models", "Fun-CosyVoice3-0.5B")
    logger.info(f"Loading CosyVoice 3 model from {model_dir}...")
    t0 = time.time()
    cosyvoice = AutoModel(model_dir=model_dir)
    logger.info(f"Model loaded in {time.time() - t0:.2f}s. Sample rate: {cosyvoice.sample_rate}")

    # Load reference transcript
    ref_txt_path = Path(voice_file).with_suffix(".reference.txt")
    ref_text = ""
    if ref_txt_path.exists():
        ref_text = ref_txt_path.read_text(encoding="utf-8").strip()
    prompt_text = f"You are a helpful assistant.<|endofprompt|>{ref_text}"

    # 2. Read & Segment Chapter with Token-Aware Segmenter (60-80 tokens per block)
    paragraphs = load_paragraphs(text_path)
    segmenter = SentenceSegmenter(
        tokenizer=cosyvoice.frontend.tokenizer,
        min_tokens=60,
        max_tokens=85,
        min_block_tokens=35
    )
    segments = segmenter.segment_chapter(paragraphs)

    total_segs = len(segments)
    logger.info(f"Chapter text segmented from {text_path}: {len(paragraphs)} paragraphs, {total_segs} blocks (60-80 tokens each).")

    # Send Telegram start announcement
    start_msg = (
        f"🎙 <b>Генерация {chapter_title} запущена</b>\n"
        f"👤 Голос: <code>{voice_name}</code>\n"
        f"⚙️ Режим: <code>zero-shot</code> (text_frontend=False)\n"
        f"📑 Всего блоков: <b>{total_segs}</b> (60–80 токенов/блок)\n"
        f"🛡️ Защита окончаний и хвостов: <b>+500 мс</b>"
    )
    send_telegram_message(start_msg, token, chat_id, proxy)

    status = {
        "state": "running",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_segments": total_segs,
        "completed_segments": 0,
        "voice": voice_name,
        "chapter": Path(text_path).stem,
    }
    update_status(status)

    silence_sentence = torch.zeros((1, int(cosyvoice.sample_rate * 0.20))) # 200 ms
    silence_para = torch.zeros((1, int(cosyvoice.sample_rate * 0.50)))     # 500 ms
    silence_tail = torch.zeros((1, int(cosyvoice.sample_rate * 0.50)))     # 500 ms tail digital silence

    audio_chunks = []
    t_start_synth = time.time()

    for s_idx, seg in enumerate(segments):
        seg_wav_path = CACHE_DIR / f"seg_{s_idx:04d}.wav"
        text = seg["text"].strip()
        if not text:
            continue

        # Check existing cached segment
        if seg_wav_path.exists() and seg_wav_path.stat().st_size > 1000:
            wav_chunk, sr = torchaudio.load(str(seg_wav_path))
            if sr != cosyvoice.sample_rate:
                resampler = torchaudio.transforms.Resample(sr, cosyvoice.sample_rate)
                wav_chunk = resampler(wav_chunk)
        else:
            torch.manual_seed(2026 + s_idx)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(2026 + s_idx)

            t_seg = time.time()
            # Non-streaming zero-shot inference without frontend text mutilation
            outputs = list(cosyvoice.inference_zero_shot(
                tts_text=text,
                prompt_text=prompt_text,
                prompt_wav=voice_file,
                stream=False,
                speed=1.0,
                text_frontend=False
            ))
            if outputs and outputs[0]['tts_speech'].shape[1] > 0:
                wav_chunk = torch.concat([o['tts_speech'] for o in outputs], dim=1)
                torchaudio.save(str(seg_wav_path), wav_chunk, cosyvoice.sample_rate)
                seg_dur = wav_chunk.shape[1] / cosyvoice.sample_rate
                logger.info(f"[{s_idx+1}/{total_segs}] Synth OK ({seg_dur:.2f}s in {time.time()-t_seg:.2f}s): {text[:45]}...")
            else:
                logger.warning(f"[{s_idx+1}/{total_segs}] Empty output for segment: {text}")
                continue

        if wav_chunk.dim() == 1:
            wav_chunk = wav_chunk.unsqueeze(0)
        elif wav_chunk.shape[0] > 1:
            wav_chunk = wav_chunk.mean(dim=0, keepdim=True)

        audio_chunks.append(wav_chunk)
        if seg.get("is_last_in_p", False):
            audio_chunks.append(silence_para)
        else:
            audio_chunks.append(silence_sentence)

        status["completed_segments"] = s_idx + 1
        elapsed = time.time() - t_start_synth
        avg_per_seg = elapsed / (s_idx + 1)
        remaining = (total_segs - (s_idx + 1)) * avg_per_seg
        status["progress_pct"] = round((s_idx + 1) / total_segs * 100, 1)
        status["eta_seconds"] = round(remaining, 1)
        status["eta_minutes"] = round(remaining / 60, 1)
        if (s_idx + 1) % 5 == 0 or (s_idx + 1) == total_segs:
            update_status(status)

        # Telegram progress report every ~10% (or at least every 40 blocks)
        step_notify = max(25, total_segs // 10)
        if (s_idx + 1) % step_notify == 0:
            prog_text = (
                f"⏳ <b>{chapter_title}: синтезировано {s_idx + 1}/{total_segs} ({status['progress_pct']}%)</b>\n"
                f"⏱️ Прошло: {elapsed / 60:.1f} мин. | Осталось: ~{status['eta_minutes']} мин."
            )
            send_telegram_message(prog_text, token, chat_id, proxy)

    if not audio_chunks:
        logger.error("No audio chunks synthesized!")
        status["state"] = "failed"
        update_status(status)
        return

    # 3. Assemble Master Audio with trailing digital silence
    logger.info("Concatenating all audio segments with 500ms safety tail silence...")
    audio_chunks.append(silence_tail)
    full_wav = torch.cat(audio_chunks, dim=1)
    safe_out_stem = OUT_DIR.name
    master_wav = OUT_DIR / f"{safe_out_stem}.wav"
    torchaudio.save(str(master_wav), full_wav, cosyvoice.sample_rate)
    total_dur_s = full_wav.shape[1] / cosyvoice.sample_rate
    logger.info(f"Full WAV generated: {master_wav} (Duration: {total_dur_s/60:.1f} min)")

    # 4. Encode to MP3
    final_mp3 = OUT_DIR / f"{safe_out_stem}.mp3"
    if FFMPEG_EXE.exists():
        cmd = [
            str(FFMPEG_EXE),
            "-y",
            "-i", str(master_wav),
            "-codec:a", "libmp3lame",
            "-b:a", "128k",
            "-ar", "24000",
            str(final_mp3),
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info(f"Standard MP3 encoded: {final_mp3} (Size: {final_mp3.stat().st_size / 1024 / 1024:.2f} MB)")
    else:
        final_mp3 = master_wav

    # 5. Telegram delivery (ensure file size <= 48 MB for Telegram Bot API)
    mp3_to_send = final_mp3
    if final_mp3.exists() and final_mp3.stat().st_size > 48 * 1024 * 1024 and FFMPEG_EXE.exists():
        # Compress to 48k mono to fit within standard 50 MB Telegram limit
        compact_mp3 = OUT_DIR / f"{safe_out_stem}_telegram.mp3"
        subprocess.run([
            str(FFMPEG_EXE), "-y", "-i", str(master_wav),
            "-codec:a", "libmp3lame", "-b:a", "48k", "-ac", "1", "-ar", "24000",
            str(compact_mp3)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if compact_mp3.exists() and compact_mp3.stat().st_size <= 49 * 1024 * 1024:
            mp3_to_send = compact_mp3

    caption = (
        f"🎧 <b>{chapter_title}</b>\n"
        f"🎙️ Голос: <code>{voice_name}</code>\n"
        f"⏱️ Длительность: {total_dur_s / 60:.1f} мин. ({int(total_dur_s)} сек.)\n"
        f"📑 Сегментов: {total_segs}"
    )

    upload_ok = send_telegram_file(mp3_to_send, caption, token, chat_id, proxy=proxy, is_audio=True, title=chapter_title)
    if not upload_ok:
        upload_ok = send_telegram_file(mp3_to_send, caption, token, chat_id, proxy=proxy, is_audio=False, title=chapter_title)

    status["state"] = "completed"
    status["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    status["duration_minutes"] = round(total_dur_s / 60, 2)
    status["mp3_path"] = str(final_mp3)
    status["telegram_uploaded"] = upload_ok
    update_status(status)

    logger.info(f"=== Generation Completed Successfully! Telegram Sent: {upload_ok} ===")

if __name__ == "__main__":
    main()
