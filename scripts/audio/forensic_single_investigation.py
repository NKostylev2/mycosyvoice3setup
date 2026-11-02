import os
import sys
import time
from pathlib import Path
import numpy as np
import soundfile as sf
import torch

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(r"E:\AI-Dubbing")
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.audio import runtime_bootstrap

ref_path = PROJECT_ROOT / "work" / "S01E01" / "voice_profiles" / "vp_librarian" / "selected" / "reference.wav"
out_dir = PROJECT_ROOT / "work" / "S01E01" / "tts_forensics"
out_dir.mkdir(parents=True, exist_ok=True)

test_text = "Не уходи из виду, Нелли."

print(f"Loading XTTS-v2 pipeline...")
tts, _ = runtime_bootstrap.init_xtts_pipeline(gpu=True)
model = tts.synthesizer.tts_model

print(f"\n--- TEST A: TTS API tts_to_file ---")
out_a = out_dir / "test_api.wav"
t0 = time.time()
tts.tts_to_file(
    text=test_text,
    speaker_wav=str(ref_path),
    language="ru",
    file_path=str(out_a),
    split_sentences=False,
)
print(f"API generated in {time.time() - t0:.2f}s")
data_a, sr_a = sf.read(out_a)
dur_a = len(data_a) / sr_a
print(f"API audio duration: {dur_a:.3f}s, shape: {data_a.shape}")

print(f"\n--- TEST B: Direct model.full_inference ---")
out_b = out_dir / "test_direct.wav"
t0 = time.time()
res_b = model.full_inference(
    text=test_text,
    ref_audio_path=str(ref_path),
    language="ru",
    temperature=0.75,
    length_penalty=1.0,
    repetition_penalty=5.0,
    top_k=50,
    top_p=0.85,
    do_sample=True,
)
wav_b = res_b["wav"]
sf.write(str(out_b), wav_b, 24000)
print(f"Direct generated in {time.time() - t0:.2f}s")
dur_b = len(wav_b) / 24000
print(f"Direct audio duration: {dur_b:.3f}s, shape: {wav_b.shape}")

print(f"\n--- Running Faster-Whisper ASR ---")
from faster_whisper import WhisperModel
print("Loading Whisper model: medium...")
asr = WhisperModel("medium", device="cuda", compute_type="float16")

for label, p in [("API (test_api.wav)", out_a), ("Direct (test_direct.wav)", out_b), ("Previous (single_test.wav)", out_dir / "single_test.wav")]:
    if p.exists():
        segments, info = asr.transcribe(str(p), language="ru", beam_size=5)
        text_asr = " ".join([s.text.strip() for s in segments])
        print(f"\n[{label}] ASR Language: {info.language} (prob: {info.language_probability:.2f})")
        print(f"[{label}] ASR Text: \"{text_asr}\"")
        for s in segments:
            print(f"    [{s.start:.2f}s -> {s.end:.2f}s]: {s.text}")
