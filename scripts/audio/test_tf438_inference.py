import os
import sys
import time
from pathlib import Path
import soundfile as sf
import torch
import transformers

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

print("Transformers version:", transformers.__version__)

PROJECT_ROOT = Path(r"E:\AI-Dubbing")
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.audio import runtime_bootstrap

tts, _ = runtime_bootstrap.init_xtts_pipeline(gpu=True)
model = tts.synthesizer.tts_model

ref_path = PROJECT_ROOT / "work" / "S01E01" / "voice_profiles" / "vp_librarian" / "selected" / "reference.wav"
text = "Не уходи из виду, Нелли."

out_dir = PROJECT_ROOT / "work" / "S01E01" / "tts_forensics"
out_path = out_dir / "test_tf438_direct.wav"

t0 = time.time()
res = model.full_inference(
    text=text,
    ref_audio_path=str(ref_path),
    language="ru",
    temperature=0.75,
    length_penalty=1.0,
    repetition_penalty=5.0,
    top_k=50,
    top_p=0.85,
    do_sample=True,
)
wav = res["wav"]
sf.write(str(out_path), wav, 24000)
dur = len(wav) / 24000
print(f"Synthesized in {time.time() - t0:.2f}s, duration: {dur:.3f}s")

# Run Whisper
from faster_whisper import WhisperModel
print("Loading Whisper medium on CUDA...")
asr = WhisperModel("medium", device="cuda", compute_type="float16")
segments, info = asr.transcribe(str(out_path), language="ru", beam_size=5)
rec_text = " ".join([s.text.strip() for s in segments])
print(f"ASR Language: {info.language} (prob: {info.language_probability:.2f})")
print(f"ASR Recognized: \"{rec_text}\"")
for s in segments:
    print(f"  [{s.start:.2f}s -> {s.end:.2f}s]: {s.text}")
