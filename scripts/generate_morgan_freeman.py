import os
import sys
import time
import json
import logging
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

# Setup paths
ROOT_DIR = r"E:\AI-Dubbing"
COSY_DIR = os.path.join(ROOT_DIR, "CosyVoice")
OUT_DIR = Path(r"E:\AI-Dubbing\output\male_voices_test")
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = OUT_DIR / "morgan_freeman.log"
STATUS_FILE = OUT_DIR / "morgan_freeman_status.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("MorganFreemanGenerator")

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
import razdel
from cosyvoice.cli.cosyvoice import AutoModel

FFMPEG_EXE = Path(r"E:\AI-Dubbing\vendor\ffmpeg\bin\ffmpeg.exe")
VOICE_FILE = r"E:\AI-Dubbing\alltalk_tts\voices\Morgan_Freeman CC3.wav"
VOICE_NAME = "Морган Фримен (Morgan_Freeman CC3)"
VOICE_ID = "morgan_freeman"

FRAGMENT_TEXT = """Он сел поверх покрывала и достал два полученных письма. Письмо Гермионы занимало шесть страниц.
Первые четыре она написала ещё до того, как прилетела Букля. Гарри без труда определил место, где до неё дошли новости: ровные строчки сменялись более тёмными, резкими, наклонёнными вправо буквами.
Гарри!
Нельзя писать «не паникуй» сразу после сообщения о том, что ты среди ночи сбежал из дома родственников.
Так инструкции не работают.
Я рада, что у тебя есть палочка и что ты добрался до «Дырявого котла». Мама уже связалась с Томом через министерскую службу для гостей, чтобы убедиться, что ты приехал. Она говорит, что это было лишним, поскольку в твоей записке были доказательства, но всё равно позвонила ему дважды.
Что случилось?
Ты написал, что вы поссорились. Из-за чего? Кто-нибудь пострадал? Дядя пытался помешать тебе уйти? Та собака опять появлялась?
В субботу мы едем в Лондон. Папа хотел приехать сегодня утром, но в Министерстве говорят, что ты в безопасности, а мама считает, что если мы явимся раньше, чем ты проснёшься, ты решишь, будто устроил катастрофу.
Ты не устроил никакой катастрофы. И перестань себя принижать.
Эта фраза была дважды подчёркнута.
Пожалуйста, не уходи из Косого переулка до нашего приезда. Пожалуйста, позавтракай. И попроси Тома дать тебе другую комнату, если дверь плохо запирается.
Люблю,
Гермиона
Гарри слегка улыбнулся, аккуратно сложил письмо и положил его на тумбочку. Письмо Драконии начиналось куда более резко.
Поттер!
Если ты ещё хоть раз напишешь «Не волнуйся, я разбираюсь» после сообщения о том, что сбежал из дома посреди ночи, я сама тебя найду.
Мать подтвердила, что ты получил комнату, что постоялый двор защищён чарами и что в здании находятся двое сотрудников Министерства, приставленных к тебе. Отец пытается выяснить, почему министр магии счёл личную встречу с тобой более важным делом, чем поимку опасного беглеца, который, по всей видимости, пересёк пол-Британии так, что его никто не заметил.
Мы приедем в субботу. Я просила приехать сегодня, но у отца сначала дела.
Отец сказал что-то о том, что нельзя провоцировать Министерство. Мать сказала кое-что потише, и он передумал, однако мы всё равно приедем в субботу.
Твой дядя причинил тебе вред?
Гарри уставился на вопрос. Он представил Вернона, загораживающего лестницу. Пальцы Мардж, сжавшие его запястье. Петунью, спрашивающую, что они скажут соседям.
Никто его не бил. Значит, правильный ответ был очевиден. Гарри прочитал дальше.
Не отвечай на вопрос наспех только потому, что тебе неприятно на него отвечать.
Гарри посмотрел на Буклю.
— Она становится невыносимо хороша в таких вопросах.
Сова продолжала спать. Внизу Дракония приписала:
Я рада, что ты от них ушёл, но больше так не делай. Я всё ещё злюсь из-за того, как именно ты это устроил.
Гарри вздохнул и положил письмо Драконии рядом с письмом Гермионы."""

def get_telegram_config():
    token = None
    env_file = Path(r"M:\dev\Telegram Remote Control\.env")
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip("\"'")

    chat_id = 373648438
    db_file = Path(r"M:\dev\Telegram Remote Control\data\tasks.sqlite3")
    if db_file.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_file))
            cur = conn.cursor()
            cur.execute("SELECT chat_id FROM tasks ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row and row[0]:
                chat_id = row[0]
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to read chat_id from sqlite: {e}")

    return token, chat_id

def send_telegram_audio(audio_path: Path, caption: str, title: str, performer: str, token: str, chat_id: int) -> bool:
    if not token:
        logger.error("No Telegram token available.")
        return False
    if not audio_path.exists():
        logger.error(f"File not found: {audio_path}")
        return False

    url = f"https://api.telegram.org/bot{token}/sendAudio"
    boundary = "----WebKitFormBoundaryAudio" + str(int(time.time()))
    file_bytes = audio_path.read_bytes()
    filename = audio_path.name

    body_parts = []
    body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    body_parts.append(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode("utf-8"))
    body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    body_parts.append(f'Content-Disposition: form-data; name="title"\r\n\r\n{title}\r\n'.encode("utf-8"))
    body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    body_parts.append(f'Content-Disposition: form-data; name="performer"\r\n\r\n{performer}\r\n'.encode("utf-8"))
    if caption:
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode("utf-8"))
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(f'Content-Disposition: form-data; name="parse_mode"\r\n\r\nHTML\r\n'.encode("utf-8"))
    body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    body_parts.append(
        f'Content-Disposition: form-data; name="audio"; filename="{filename}"\r\n'
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

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read().decode("utf-8")
            logger.info(f"Telegram sendAudio OK: {filename}")
            return True
    except Exception as e:
        logger.warning(f"sendAudio failed ({e}), attempting sendDocument fallback...")

    # Fallback to sendDocument
    doc_url = f"https://api.telegram.org/bot{token}/sendDocument"
    doc_parts = []
    doc_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    doc_parts.append(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode("utf-8"))
    if caption:
        doc_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        doc_parts.append(f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode("utf-8"))
        doc_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        doc_parts.append(f'Content-Disposition: form-data; name="parse_mode"\r\n\r\nHTML\r\n'.encode("utf-8"))
    doc_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    doc_parts.append(
        f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
        f"Content-Type: audio/mpeg\r\n\r\n".encode("utf-8")
    )
    doc_parts.append(file_bytes)
    doc_parts.append(b"\r\n")
    doc_parts.append(f"--{boundary}--\r\n".encode("utf-8"))

    req_doc = urllib.request.Request(
        doc_url,
        data=b"".join(doc_parts),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "Telegram-Voice-Sender/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req_doc, timeout=120) as resp:
            logger.info(f"Telegram sendDocument OK: {filename}")
            return True
    except Exception as e:
        logger.error(f"Telegram sendDocument failed for {filename}: {e}")
        return False

def update_status(data: dict):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Could not write status file: {e}")

def prepare_segments(text: str):
    # 1. Clean and merge signature
    norm_text = text.replace("Люблю,\nГермиона", "Люблю, Гермиона.")
    raw_paragraphs = [p.strip() for p in norm_text.splitlines() if p.strip()]

    segments = []
    for p_idx, p in enumerate(raw_paragraphs):
        sents = [s.text.strip() for s in razdel.sentenize(p) if s.text.strip()]
        for s_idx, s in enumerate(sents):
            clean_s = s.replace("—", " — ").replace("«", '"').replace("»", '"')
            clean_s = re.sub(r'[ \t]+', ' ', clean_s).strip()
            # Ensure appropriate punctuation
            if not re.search(r'[\.\?!…":;]$', clean_s):
                clean_s += "."
            # Clean duplicate punctuation like ',.' or ':.'
            clean_s = re.sub(r'[,:;]+\.+$', '.', clean_s)
            
            is_last = (s_idx == len(sents) - 1)
            segments.append({
                "p_idx": p_idx,
                "s_idx": s_idx,
                "text": clean_s,
                "is_last_in_p": is_last,
            })
    return segments

def main():
    logger.info("=== Starting Morgan Freeman Voice Regeneration Pipeline ===")
    token, chat_id = get_telegram_config()
    logger.info(f"Telegram Config: Token Present={bool(token)}, ChatID={chat_id}")

    if not os.path.exists(VOICE_FILE):
        logger.error(f"Voice reference file missing: {VOICE_FILE}")
        update_status({"state": "failed", "error": f"File missing: {VOICE_FILE}"})
        return

    segments = prepare_segments(FRAGMENT_TEXT)
    logger.info(f"Prepared {len(segments)} segments for synthesis.")

    status = {
        "state": "running",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_segments": len(segments),
        "completed_segments": 0,
        "voice": VOICE_NAME,
    }
    update_status(status)

    # Load CosyVoice Model
    model_dir = os.path.join(COSY_DIR, "pretrained_models", "Fun-CosyVoice3-0.5B")
    logger.info(f"Loading CosyVoice 3 model from {model_dir}...")
    t0 = time.time()
    cosyvoice = AutoModel(model_dir=model_dir)
    logger.info(f"Model loaded in {time.time() - t0:.2f}s. Sample rate: {cosyvoice.sample_rate}")

    silence_sentence = torch.zeros((1, int(cosyvoice.sample_rate * 0.25)))
    silence_para = torch.zeros((1, int(cosyvoice.sample_rate * 0.55)))

    cache_dir = OUT_DIR / "segments" / "morgan_freeman_v2"
    cache_dir.mkdir(parents=True, exist_ok=True)

    audio_chunks = []
    t_start_synth = time.time()

    for s_idx, seg in enumerate(segments):
        seg_wav_path = cache_dir / f"seg_{s_idx:04d}.wav"
        text = seg["text"].strip()
        if not text:
            continue

        tts_text = f"You are a helpful assistant.<|endofprompt|>{text}"

        torch.manual_seed(2026 + s_idx)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(2026 + s_idx)

        t_seg = time.time()
        # Use cross-lingual inference with canonical prefix - no prompt leakage, clean prosody
        outputs = list(cosyvoice.inference_cross_lingual(tts_text, VOICE_FILE, speed=1.0))
        if outputs:
            wav_chunk = torch.concat([o['tts_speech'] for o in outputs], dim=1)
            torchaudio.save(str(seg_wav_path), wav_chunk, cosyvoice.sample_rate)
            seg_dur = wav_chunk.shape[1] / cosyvoice.sample_rate
            logger.info(f"[{s_idx+1}/{len(segments)}] Synth OK ({seg_dur:.2f}s in {time.time()-t_seg:.2f}s): {text[:50]}")
        else:
            logger.warning(f"[{s_idx+1}/{len(segments)}] Empty output for: {text}")
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
        update_status(status)

    if not audio_chunks:
        logger.error("No audio chunks synthesized!")
        status["state"] = "failed"
        update_status(status)
        return

    # Combine full WAV
    full_wav = torch.cat(audio_chunks, dim=1)
    final_wav = OUT_DIR / f"{VOICE_ID}.wav"
    torchaudio.save(str(final_wav), full_wav, cosyvoice.sample_rate)
    duration_s = full_wav.shape[1] / cosyvoice.sample_rate
    logger.info(f"Full WAV assembled: {final_wav} (Duration: {duration_s:.1f}s, Time: {time.time()-t_start_synth:.1f}s)")

    # Convert to MP3
    final_mp3 = OUT_DIR / f"{VOICE_ID}.mp3"
    if FFMPEG_EXE.exists():
        cmd = [
            str(FFMPEG_EXE),
            "-y",
            "-i", str(final_wav),
            "-codec:a", "libmp3lame",
            "-b:a", "192k",
            str(final_mp3),
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info(f"MP3 encoded: {final_mp3}")
    else:
        final_mp3 = final_wav

    # Send to Telegram
    caption = f"🎙️ Озвучка: <b>{VOICE_NAME}</b>\n⏱ Длительность: {duration_s:.1f} сек."
    upload_ok = send_telegram_audio(
        final_mp3,
        caption=caption,
        title=f"Озвучка - Морган Фримен",
        performer="CosyVoice 3",
        token=token,
        chat_id=chat_id,
    )

    status["state"] = "finished"
    status["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    status["duration_s"] = round(duration_s, 2)
    status["mp3_path"] = str(final_mp3)
    status["telegram_uploaded"] = upload_ok
    update_status(status)

    logger.info(f"=== Morgan Freeman Generation Complete! Telegram Uploaded={upload_ok} ===")

if __name__ == "__main__":
    main()
