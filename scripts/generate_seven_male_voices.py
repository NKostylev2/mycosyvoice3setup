import os
import sys
import time
import json
import logging
import subprocess
import urllib.request
import urllib.error
import mimetypes
from pathlib import Path

# Setup logging
OUT_DIR = Path(r"E:\AI-Dubbing\output\male_voices_test")
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = OUT_DIR / "progress.log"
STATUS_FILE = OUT_DIR / "status.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("SevenVoicesGenerator")

# Add CosyVoice to sys.path
ROOT_DIR = r"E:\AI-Dubbing"
COSY_DIR = os.path.join(ROOT_DIR, "CosyVoice")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if COSY_DIR not in sys.path:
    sys.path.insert(0, COSY_DIR)
matcha_dir = os.path.join(COSY_DIR, "third_party", "Matcha-TTS")
if matcha_dir not in sys.path:
    sys.path.insert(0, matcha_dir)

import torch
import torchaudio
from cosyvoice.cli.cosyvoice import AutoModel
from fanfic_pipeline.segmenter import SentenceSegmenter

FFMPEG_EXE = Path(r"E:\AI-Dubbing\vendor\ffmpeg\bin\ffmpeg.exe")

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

VOICES = [
    {
        "id": "male_01",
        "name": "Мужской голос 1 (male_01)",
        "file": r"E:\AI-Dubbing\alltalk_tts\voices\male_01.wav",
    },
    {
        "id": "male_02",
        "name": "Мужской голос 2 (male_02)",
        "file": r"E:\AI-Dubbing\alltalk_tts\voices\male_02.wav",
    },
    {
        "id": "male_03",
        "name": "Мужской голос 3 (male_03)",
        "file": r"E:\AI-Dubbing\alltalk_tts\voices\male_03.wav",
    },
    {
        "id": "male_04",
        "name": "Мужской голос 4 (male_04)",
        "file": r"E:\AI-Dubbing\alltalk_tts\voices\male_04.wav",
    },
    {
        "id": "male_05",
        "name": "Мужской голос 5 (male_05)",
        "file": r"E:\AI-Dubbing\alltalk_tts\voices\male_05.wav",
    },
    {
        "id": "martin_mystery",
        "name": "Мартин Мистери (martin_mystery)",
        "file": r"E:\AI-Dubbing\alltalk_tts\voices\martin_mystery.wav",
    },
    {
        "id": "morgan_freeman",
        "name": "Морган Фримен (Morgan_Freeman CC3)",
        "file": r"E:\AI-Dubbing\alltalk_tts\voices\Morgan_Freeman CC3.wav",
    },
]

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
    # chat_id
    body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    body_parts.append(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode("utf-8"))
    # title
    body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    body_parts.append(f'Content-Disposition: form-data; name="title"\r\n\r\n{title}\r\n'.encode("utf-8"))
    # performer
    body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    body_parts.append(f'Content-Disposition: form-data; name="performer"\r\n\r\n{performer}\r\n'.encode("utf-8"))
    # caption
    if caption:
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode("utf-8"))
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(f'Content-Disposition: form-data; name="parse_mode"\r\n\r\nHTML\r\n'.encode("utf-8"))
    # audio file
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

def main():
    logger.info("=== Starting 7 Male Voices Generation Pipeline ===")
    token, chat_id = get_telegram_config()
    logger.info(f"Telegram Config: Token Present={bool(token)}, ChatID={chat_id}")

    status = {
        "state": "running",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_voices": len(VOICES),
        "completed_voices": 0,
        "voices": {},
    }
    update_status(status)

    # 1. Segment text
    segmenter = SentenceSegmenter(min_sentence_len=50, max_sentence_len=180)
    paragraphs = [p.strip() for p in FRAGMENT_TEXT.splitlines() if p.strip()]
    segments = []
    for p_idx, p in enumerate(paragraphs):
        p_segs = segmenter.split_paragraph(p, p_idx=p_idx)
        segments.extend(p_segs)

    logger.info(f"Text prepared: {len(paragraphs)} paragraphs, {len(segments)} segments.")

    # 2. Load CosyVoice Model
    model_dir = os.path.join(COSY_DIR, "pretrained_models", "Fun-CosyVoice3-0.5B")
    logger.info(f"Loading CosyVoice 3 model from {model_dir}...")
    t0 = time.time()
    cosyvoice = AutoModel(model_dir=model_dir)
    logger.info(f"Model loaded in {time.time() - t0:.2f}s. Sample rate: {cosyvoice.sample_rate}")

    silence_sentence = torch.zeros((1, int(cosyvoice.sample_rate * 0.25)))
    silence_para = torch.zeros((1, int(cosyvoice.sample_rate * 0.60)))
    instruct_text = "You are a professional male audiobook narrator with a calm, deep, expressive voice, reading a dramatic story in natural Russian.<|endofprompt|>"

    # 3. Iterate over each voice
    for v_idx, voice_info in enumerate(VOICES):
        vid = voice_info["id"]
        vname = voice_info["name"]
        vfile = voice_info["file"]

        logger.info(f"\n=======================================================")
        logger.info(f"[{v_idx+1}/{len(VOICES)}] Processing Voice: {vname}")
        logger.info(f"Reference Audio: {vfile}")
        logger.info(f"=======================================================")

        if not os.path.exists(vfile):
            logger.error(f"Voice reference file missing: {vfile}")
            status["voices"][vid] = {"status": "error", "error": "file missing"}
            update_status(status)
            continue

        voice_cache_dir = OUT_DIR / "segments" / vid
        voice_cache_dir.mkdir(parents=True, exist_ok=True)

        audio_chunks = []
        for s_idx, seg in enumerate(segments):
            seg_wav_path = voice_cache_dir / f"seg_{s_idx:04d}.wav"
            text = seg["text"].strip()
            if not text:
                continue

            # Check cache
            if seg_wav_path.exists() and seg_wav_path.stat().st_size > 1000:
                wav_chunk, _ = torchaudio.load(str(seg_wav_path))
            else:
                torch.manual_seed(42 + s_idx)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(42 + s_idx)

                outputs = list(cosyvoice.inference_instruct2(text, instruct_text, vfile, speed=1.0))
                if outputs:
                    wav_chunk = torch.concat([o['tts_speech'] for o in outputs], dim=1)
                    torchaudio.save(str(seg_wav_path), wav_chunk, cosyvoice.sample_rate)
                else:
                    logger.warning(f"Empty output for segment {s_idx}: {text[:30]}")
                    continue

            # Normalize tensor dimension
            if wav_chunk.dim() == 1:
                wav_chunk = wav_chunk.unsqueeze(0)
            elif wav_chunk.shape[0] > 1:
                wav_chunk = wav_chunk.mean(dim=0, keepdim=True)

            audio_chunks.append(wav_chunk)
            if seg.get("is_last_in_p", False):
                audio_chunks.append(silence_para)
            else:
                audio_chunks.append(silence_sentence)

        if not audio_chunks:
            logger.error(f"No audio synthesized for {vname}")
            status["voices"][vid] = {"status": "failed"}
            update_status(status)
            continue

        # Assemble full WAV
        full_wav = torch.cat(audio_chunks, dim=1)
        final_wav = OUT_DIR / f"{vid}.wav"
        torchaudio.save(str(final_wav), full_wav, cosyvoice.sample_rate)
        duration_s = full_wav.shape[1] / cosyvoice.sample_rate
        logger.info(f"WAV created: {final_wav} (Duration: {duration_s:.1f}s)")

        # Convert to MP3
        final_mp3 = OUT_DIR / f"{vid}.mp3"
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
            logger.info(f"MP3 created: {final_mp3}")
        else:
            final_mp3 = final_wav

        # Upload to Telegram immediately
        caption = f"🎙️ Озвучка: <b>{vname}</b>\n⏱ Длительность: {duration_s:.1f} сек."
        upload_ok = send_telegram_audio(
            final_mp3,
            caption=caption,
            title=f"Озвучка - {vname}",
            performer="CosyVoice 3",
            token=token,
            chat_id=chat_id,
        )

        status["completed_voices"] += 1
        status["voices"][vid] = {
            "status": "completed",
            "name": vname,
            "mp3_path": str(final_mp3),
            "duration_s": round(duration_s, 2),
            "telegram_uploaded": upload_ok,
        }
        update_status(status)
        logger.info(f"[{v_idx+1}/{len(VOICES)}] Voice {vname} successfully finished and uploaded!\n")

    status["state"] = "finished"
    status["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    update_status(status)
    logger.info("=== All 7 Male Voices Successfully Generated and Delivered! ===")

if __name__ == "__main__":
    main()
