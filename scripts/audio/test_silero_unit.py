"""
scripts/audio/test_silero_unit.py
Synthesizes U0003 with Silero TTS v4 in normal and pacing-adapted modes.
"""

import time
import torch
import soundfile as sf
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(r"E:\AI-Dubbing")
WORK_DIR = PROJECT_ROOT / "work" / "S01E01"
MODEL_PATH = PROJECT_ROOT / "models" / "silero" / "v4_ru.pt"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Loading Silero TTS model on {device}...")
model = torch.package.PackageImporter(str(MODEL_PATH)).load_pickle("tts_models", "model")
model.to(device)

text_raw = "Десерты — это ключ к этой классной атмосфере."
target_dur = 2.653  # seconds from tts_preparation.json

# 1. Standard Aidar (normal rate)
audio_standard = model.apply_tts(text=text_raw, speaker="aidar", sample_rate=48000)
dur_standard = len(audio_standard) / 48000
out_standard = WORK_DIR / "U0003_donor_standard.wav"
sf.write(str(out_standard), audio_standard.cpu().numpy(), 48000)
print(f"Standard audio: {dur_standard:.2f}s -> {out_standard}")

# 2. Paced Aidar using SSML rate
# Target is 2.653s, standard is ~3.21s -> speedup ~ 121%
rate_pct = int(round((dur_standard / target_dur) * 100))
ssml_text = f'<speak><prosody rate="{rate_pct}%">{text_raw}</prosody></speak>'
audio_paced = model.apply_tts(ssml_text=ssml_text, speaker="aidar", sample_rate=48000)
dur_paced = len(audio_paced) / 48000
out_paced = WORK_DIR / "U0003_donor_paced.wav"
sf.write(str(out_paced), audio_paced.cpu().numpy(), 48000)
print(f"Paced audio ({rate_pct}%): {dur_paced:.2f}s (target: {target_dur}s) -> {out_paced}")

# Also generate with speaker 'eugene' for comparison
audio_eugene = model.apply_tts(text=text_raw, speaker="eugene", sample_rate=48000)
dur_eugene = len(audio_eugene) / 48000
out_eugene = WORK_DIR / "U0003_donor_eugene.wav"
sf.write(str(out_eugene), audio_eugene.cpu().numpy(), 48000)
print(f"Eugene audio: {dur_eugene:.2f}s -> {out_eugene}")
