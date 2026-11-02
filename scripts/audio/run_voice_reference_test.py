import os
import sys
import time
import json
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
import torch.nn.functional as F
from faster_whisper import WhisperModel

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(r"E:\AI-Dubbing")
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.audio import runtime_bootstrap

WORK_DIR = PROJECT_ROOT / "work" / "S01E01"
FORENSICS_DIR = WORK_DIR / "tts_forensics"
TTS_DIR = WORK_DIR / "tts"

text_ru = "Не уходи из виду, Нелли."

print("Initializing XTTS-v2 pipeline...")
tts, _ = runtime_bootstrap.init_xtts_pipeline(gpu=True)
model = tts.synthesizer.tts_model

print("Loading Faster-Whisper ASR...")
asr = WhisperModel("medium", device="cuda", compute_type="float16")

references_to_test = [
    {
        "id": "scene1_direct_father",
        "description": "Original father voice from Scene 1 (U0001 + U0002)",
        "ref_path": FORENSICS_DIR / "ref_scene1_father.wav",
        "out_wav": TTS_DIR / "U0001-S01_ref_scene1.wav"
    },
    {
        "id": "scene4_emotional_father",
        "description": "Father voice recounting Nelly disappearance (U0036)",
        "ref_path": WORK_DIR / "voice_profiles" / "vp_librarian" / "candidates" / "candidate_03_U0036_S01.wav",
        "out_wav": TTS_DIR / "U0001-S01_ref_u0036.wav"
    },
    {
        "id": "canonical_vp_librarian",
        "description": "Canonical vp_librarian profile reference (U0097)",
        "ref_path": WORK_DIR / "voice_profiles" / "vp_librarian" / "selected" / "reference.wav",
        "out_wav": TTS_DIR / "U0001-S01_ref_canonical.wav"
    }
]

def get_speaker_emb(file_path):
    d, sr = sf.read(file_path)
    t = torch.tensor(d, dtype=torch.float32).unsqueeze(0)
    emb = model.get_speaker_embedding(t, sr)
    return emb.squeeze()

# Original father embedding from episode
orig_emb = get_speaker_emb(FORENSICS_DIR / "u0001_original_clip.wav")

results = []

for r in references_to_test:
    rid = r["id"]
    ref_path = r["ref_path"]
    out_wav = r["out_wav"]
    print(f"\n--- Synthesizing with reference: {r['description']} ---")
    print(f"Ref path: {ref_path}")
    t0 = time.time()
    tts.tts_to_file(
        text=text_ru,
        speaker_wav=str(ref_path),
        language="ru",
        file_path=str(out_wav),
        split_sentences=False,
    )
    synth_time = time.time() - t0

    # Apply -1.0 dBFS normalization
    raw_audio, sr = sf.read(out_wav)
    peak = np.max(np.abs(raw_audio))
    if peak > 0:
        target_amp = 10 ** (-1.0 / 20.0)
        norm_audio = raw_audio * (target_amp / peak)
        sf.write(str(out_wav), norm_audio.astype(np.float32), 24000, subtype="PCM_16")

    # Metrics
    data_f, sr = sf.read(out_wav, dtype="float32")
    data_i, _ = sf.read(out_wav, dtype="int16")
    dur = len(data_f) / sr
    peak_val = float(np.max(np.abs(data_f)))
    peak_db = float(20 * np.log10(peak_val)) if peak_val > 0 else -100.0
    rms_val = float(np.sqrt(np.mean(data_f ** 2)))
    rms_db = float(20 * np.log10(rms_val)) if rms_val > 0 else -100.0
    samples_0db = int(np.sum(np.abs(data_i) >= 32767))

    # ASR
    segs, info = asr.transcribe(str(out_wav), language="ru", beam_size=5)
    rec_text = " ".join([s.text.strip() for s in segs])

    # Voice similarity to original episode father
    gen_emb = get_speaker_emb(out_wav)
    sim_to_orig = F.cosine_similarity(orig_emb, gen_emb, dim=0).item()

    rec = {
        "reference_id": rid,
        "description": r["description"],
        "ref_path": str(ref_path),
        "output_wav": str(out_wav),
        "synth_time_seconds": round(synth_time, 2),
        "duration_seconds": round(dur, 4),
        "peak_dbfs": round(peak_db, 4),
        "rms_dbfs": round(rms_db, 2),
        "samples_at_0dBFS": samples_0db,
        "clipping": samples_0db > 0,
        "asr_text": rec_text,
        "asr_lang_prob": round(info.language_probability, 3),
        "cosine_similarity_to_original_father": round(sim_to_orig, 4)
    }
    results.append(rec)
    print(f"  Generated Duration: {dur:.3f}s | Peak: {peak_db:.2f} dBFS | Time: {synth_time:.2f}s")
    print(f"  ASR: \"{rec_text}\"")
    print(f"  Cosine Similarity to Original Father Voice: {sim_to_orig:.4f}")

# Also overwrite production U0001-S01.wav with the highest-fidelity reference output (or keep canonical)
# If scene1 reference gives highest similarity and perfect speech, copy to U0001-S01.wav as primary production candidate
best = max(results, key=lambda x: x["cosine_similarity_to_original_father"])
print(f"\nHighest voice similarity to original character achieved by: {best['description']} ({best['cosine_similarity_to_original_father']:.4f})")

# Copy the best to U0001-S01_best_clone.wav
best_out = TTS_DIR / "U0001-S01_best_clone.wav"
sf.write(str(best_out), sf.read(best["output_wav"])[0], 24000, subtype="PCM_16")

out_summary_file = FORENSICS_DIR / "voice_reference_comparison.json"
with open(out_summary_file, "w", encoding="utf-8") as f:
    json.dump({"test_text": text_ru, "results": results, "best": best}, f, indent=2, ensure_ascii=False)
print(f"Summary written to: {out_summary_file}")
