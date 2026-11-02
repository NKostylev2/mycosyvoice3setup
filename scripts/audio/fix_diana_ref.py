import soundfile as sf
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, r"E:\AI-Dubbing\scripts\audio")
from build_tight_references import trim_and_tighten

slices_dir = Path(r"E:\AI-Dubbing\work\S01E01\rvc_dataset\diana_lombard")
out_ref = Path(r"E:\AI-Dubbing\alltalk_tts\voices\diana_lombard.wav")

# Use strictly pure female Diana utterances (no multi-speaker!)
# U0009: 4.5s (calm, sarcastic, clear female voice)
# U0111: 3.56s (demanding, high pitched, clear female voice)
# U0004: 3.16s (playful, teasing female voice)
pure_uids = ["U0004", "U0009", "U0111"]
chunks = []
sr_ref = None

for uid in pure_uids:
    p = slices_dir / f"{uid}.wav"
    if p.exists():
        data, sr = sf.read(str(p))
        sr_ref = sr
        clean = trim_and_tighten(data, sr, max_pause_sec=0.08)
        chunks.append(clean)
        chunks.append(np.zeros(int(0.12 * sr), dtype=np.float32))

if chunks:
    chunks.pop()
    final_audio = np.concatenate(chunks)
    peak = np.max(np.abs(final_audio))
    if peak > 1e-5:
        final_audio = final_audio * ((10 ** (-1.0 / 20.0)) / peak)
    sf.write(str(out_ref), final_audio, sr_ref, subtype="PCM_16")
    dur = len(final_audio) / sr_ref
    print(f"Saved pure Diana reference: {out_ref} ({dur:.2f}s)")
