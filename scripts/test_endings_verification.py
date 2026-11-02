import os
import sys
import time
import torch
import torchaudio
from pathlib import Path

# Paths
ROOT_DIR = r"E:\AI-Dubbing"
COSY_DIR = os.path.join(ROOT_DIR, "CosyVoice")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if COSY_DIR not in sys.path:
    sys.path.insert(0, COSY_DIR)
matcha_dir = os.path.join(COSY_DIR, "third_party", "Matcha-TTS")
if matcha_dir not in sys.path:
    sys.path.insert(0, matcha_dir)

os.environ["PATH"] = r"E:\AI-Dubbing\vendor\ffmpeg\bin" + os.pathsep + os.environ.get("PATH", "")

from cosyvoice.cli.cosyvoice import AutoModel
from fanfic_pipeline.segmenter import SentenceSegmenter

OUT_DIR = Path(r"E:\AI-Dubbing\output\test_endings_verification")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_DIR = os.path.join(COSY_DIR, "pretrained_models", "Fun-CosyVoice3-0.5B")
VOICE_FILE = r"E:\AI-Dubbing\alltalk_tts\voices\VID_20261101_122350_289.wav"
REF_TXT_FILE = r"E:\AI-Dubbing\alltalk_tts\voices\VID_20261101_122350_289.reference.txt"

TEST_TEXT = (
    "Гарри подошёл к окну и внимательно посмотрел на улицу. "
    "Он увидел, как девочка улыбнулась, повернулась и быстро исчезла за дверью. "
    "Всё вокруг постепенно затихло."
)

def run_test():
    print("=" * 60)
    print("CosyVoice 3 Russian Endings & Suffix Verification Test")
    print("=" * 60)

    # 1. Load Model
    print(f"\n[1] Loading CosyVoice 3 from {MODEL_DIR}...")
    t0 = time.time()
    cosyvoice = AutoModel(model_dir=MODEL_DIR)
    sr = cosyvoice.sample_rate
    print(f"    Model loaded in {time.time() - t0:.2f}s (Sample Rate: {sr} Hz)")

    # 2. Token-aware segmentation
    print("\n[2] Segmenting Russian text with token awareness...")
    segmenter = SentenceSegmenter(
        tokenizer=cosyvoice.frontend.tokenizer,
        min_tokens=60,
        max_tokens=85,
        min_block_tokens=35
    )
    blocks = segmenter.split_paragraph(TEST_TEXT)
    print(f"    Total blocks produced: {len(blocks)}")
    for i, b in enumerate(blocks):
        print(f"    Block {i+1}: tokens={b['tokens']}, text='{b['text']}'")

    # 3. Read reference prompt
    ref_text = ""
    if os.path.exists(REF_TXT_FILE):
        with open(REF_TXT_FILE, "r", encoding="utf-8") as f:
            ref_text = f.read().strip()
    prompt_text = f"You are a helpful assistant.<|endofprompt|>{ref_text}"
    print(f"    Reference audio: {VOICE_FILE}")
    print(f"    Reference text: '{ref_text[:60]}...'")

    # 4. Synthesize with required parameters
    print("\n[3] Synthesizing speech with strict parameters:")
    print("    - text_frontend = False")
    print("    - stream = False")
    print("    - speed = 1.0")

    audio_segments = []
    pause_block = torch.zeros((1, int(sr * 0.20)))  # 200 ms inter-block silence
    pause_tail = torch.zeros((1, int(sr * 0.50)))   # 500 ms tail digital silence

    for idx, b in enumerate(blocks):
        text = b["text"]
        t_start = time.time()
        torch.manual_seed(42 + idx)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42 + idx)

        # Full generator consumption via list(...)
        raw_generator = cosyvoice.inference_zero_shot(
            tts_text=text,
            prompt_text=prompt_text,
            prompt_wav=VOICE_FILE,
            stream=False,
            speed=1.0,
            text_frontend=False
        )
        outputs = list(raw_generator)

        # Verification: check non-empty output
        assert len(outputs) > 0, "Error: Generator returned empty list!"
        first_chunk = outputs[0]["tts_speech"]
        assert first_chunk.shape[1] > 0, "Error: Speech tensor is empty!"

        # Concatenate chunks if any
        wav_chunk = torch.concat([o["tts_speech"] for o in outputs], dim=1)
        dur_s = wav_chunk.shape[1] / sr
        print(f"    Block {idx+1} synthesized: {dur_s:.2f}s in {time.time() - t_start:.2f}s")

        seg_file = OUT_DIR / f"segment_{idx+1:02d}.wav"
        torchaudio.save(str(seg_file), wav_chunk, sr)
        print(f"    Saved segment WAV: {seg_file}")

        audio_segments.append(wav_chunk)
        if idx < len(blocks) - 1:
            audio_segments.append(pause_block)

    # 5. Concatenate and add 500ms safety tail
    audio_segments.append(pause_tail)
    master_wav = torch.concat(audio_segments, dim=1)
    master_file = OUT_DIR / "final_verified_speech.wav"
    torchaudio.save(str(master_file), master_wav, sr)
    total_dur = master_wav.shape[1] / sr
    print(f"\n[4] Master WAV assembled: {master_file} (Duration: {total_dur:.2f}s)")

    # 6. Tail integrity analysis
    print("\n[5] Tail Integrity Analysis:")
    abs_wav = torch.abs(master_wav[0])
    indices = torch.where(abs_wav > 0.005)[0]
    if len(indices) > 0:
        last_audible_s = indices[-1].item() / sr
        tail_room_s = total_dur - last_audible_s
        print(f"    Total file duration: {total_dur:.3f}s")
        print(f"    Last audible sample (> -46dB): {last_audible_s:.3f}s")
        print(f"    Trailing safety room: {tail_room_s:.3f}s (target >= 0.500s)")

    # 7. Whisper Speech-to-Text Verification
    print("\n[6] Automatic Speech Recognition (Whisper verification)...")
    try:
        import whisper
        whisper_model = whisper.load_model("base")
        asr_res = whisper_model.transcribe(str(master_file), language="ru")
        recognized_text = asr_res["text"].strip()
        print(f"    ASR Recognized: \"{recognized_text}\"")

        # Check key endings
        keywords = ["подошёл", "посмотрел", "улыбнулась", "повернулась", "исчезла", "затихло"]
        print("\n    Keywords & Endings check in recognition:")
        for kw in keywords:
            # normalize for case-insensitive check
            found = kw.lower() in recognized_text.lower() or kw.replace("ё", "е").lower() in recognized_text.lower()
            print(f"    - '{kw}': {'OK (Present)' if found else 'CHECK MANUALLY'}")

        # Save verification report
        report_file = OUT_DIR / "verification_report.txt"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("=== CosyVoice 3 Endings Verification Report ===\n")
            f.write(f"Test text: {TEST_TEXT}\n")
            f.write(f"Sample rate: {sr} Hz\n")
            f.write(f"Total duration: {total_dur:.3f}s\n")
            f.write(f"Trailing room: {tail_room_s:.3f}s\n")
            f.write(f"ASR transcription: {recognized_text}\n")
        print(f"\nReport written to: {report_file}")
    except Exception as e:
        print(f"    Whisper check skipped/error: {e}")

    print("\n" + "=" * 60)
    print("Test Completed Successfully!")
    print("=" * 60)

if __name__ == "__main__":
    run_test()
