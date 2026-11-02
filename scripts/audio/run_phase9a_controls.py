import os
import sys
import time
import json
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
import transformers

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(r"E:\AI-Dubbing")
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.audio import runtime_bootstrap

WORK_DIR = PROJECT_ROOT / "work" / "S01E01"
FORENSICS_DIR = WORK_DIR / "tts_forensics"
FORENSICS_DIR.mkdir(parents=True, exist_ok=True)

VOICE_PROFILES_FILE = WORK_DIR / "voice_profiles.json"
with open(VOICE_PROFILES_FILE, "r", encoding="utf-8") as f:
    vp_data = json.load(f)

vp_librarian_ref = WORK_DIR / vp_data["profiles"]["vp_librarian"]["reference_audio_path"]
vp_martin_ref = WORK_DIR / vp_data["profiles"]["vp_martin_mystery"]["reference_audio_path"]

print(f"Transformers version: {transformers.__version__}")
print(f"Loading XTTS-v2 pipeline...")
tts, resolved_paths = runtime_bootstrap.init_xtts_pipeline(gpu=True)
model = tts.synthesizer.tts_model

print(f"Loading Faster-Whisper ASR...")
from faster_whisper import WhisperModel
asr = WhisperModel("medium", device="cuda", compute_type="float16")


def compute_audio_metrics(file_path):
    data_f, sr = sf.read(file_path, dtype="float32")
    data_i, _ = sf.read(file_path, dtype="int16")
    dur = len(data_f) / sr
    peak = float(np.max(np.abs(data_f)))
    rms = float(np.sqrt(np.mean(data_f ** 2)))
    rms_db = float(20 * np.log10(rms)) if rms > 1e-9 else -100.0
    peak_db = float(20 * np.log10(peak)) if peak > 1e-9 else -100.0
    samples_0db = int(np.sum(np.abs(data_i) >= 32767))
    return {
        "duration_seconds": round(dur, 4),
        "sample_rate": sr,
        "channels": 1 if data_f.ndim == 1 else data_f.shape[1],
        "actual_peak": round(peak, 6),
        "peak_dbfs": round(peak_db, 4),
        "rms_dbfs": round(rms_db, 2),
        "samples_at_0dBFS": samples_0db,
        "clipping": samples_0db > 0,
        "has_nan": bool(np.isnan(data_f).any()),
        "has_inf": bool(np.isinf(data_f).any()),
    }


def transcribe_audio(file_path, lang=None):
    segments, info = asr.transcribe(str(file_path), language=lang, beam_size=5)
    seg_list = []
    text_parts = []
    for s in segments:
        text_parts.append(s.text.strip())
        seg_list.append({
            "start": round(s.start, 2),
            "end": round(s.end, 2),
            "text": s.text.strip(),
            "avg_logprob": round(s.avg_logprob, 3),
            "no_speech_prob": round(s.no_speech_prob, 3),
        })
    return {
        "language": info.language,
        "language_prob": round(info.language_probability, 3),
        "text": " ".join(text_parts),
        "segments": seg_list
    }


results = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "transformers_version": transformers.__version__,
    "test_runs": {}
}

# --- 1. THREE CANONICAL CONTROL TEXTS ---
control_tests = [
    {
        "test_id": "TEST_1",
        "name": "General phonetics check",
        "text": "Это тестовая запись.",
        "lang": "ru",
        "ref": vp_librarian_ref,
        "target_dur": 1.5,
        "out_file": FORENSICS_DIR / "control_test_1.wav"
    },
    {
        "test_id": "TEST_2",
        "name": "Character greeting phonetics",
        "text": "Привет, Мартин.",
        "lang": "ru",
        "ref": vp_librarian_ref,
        "target_dur": 1.2,
        "out_file": FORENSICS_DIR / "control_test_2.wav"
    },
    {
        "test_id": "TEST_3",
        "name": "Target replica U0001-S01",
        "text": "Не уходи из виду, Нелли.",
        "lang": "ru",
        "ref": vp_librarian_ref,
        "target_dur": 1.302,
        "out_file": FORENSICS_DIR / "control_test_3.wav"
    }
]

print("\n" + "=" * 80)
print("RUNNING 3 CANONICAL CONTROL TEXTS")
print("=" * 80)

for ct in control_tests:
    tid = ct["test_id"]
    print(f"\n--- {tid}: {ct['name']} ---")
    print(f"Text: \"{ct['text']}\"")
    t0 = time.time()
    tts.tts_to_file(
        text=ct["text"],
        speaker_wav=str(ct["ref"]),
        language=ct["lang"],
        file_path=str(ct["out_file"]),
        split_sentences=False,
    )
    synth_time = time.time() - t0
    metrics = compute_audio_metrics(ct["out_file"])
    asr_res = transcribe_audio(ct["out_file"], lang=ct["lang"])

    print(f"Synthesized in: {synth_time:.2f}s | Duration: {metrics['duration_seconds']:.3f}s")
    print(f"ASR ({asr_res['language']}): \"{asr_res['text']}\"")

    results["test_runs"][tid] = {
        "text": ct["text"],
        "target_duration": ct["target_dur"],
        "synth_time_seconds": round(synth_time, 2),
        "output_file": str(ct["out_file"].relative_to(PROJECT_ROOT)),
        "audio_metrics": metrics,
        "asr": asr_res
    }

# --- 2. CROSS-LANGUAGE CONTROL TEST ---
print("\n" + "=" * 80)
print("RUNNING CROSS-LANGUAGE CONTROL TEST (Section 23)")
print("=" * 80)

cross_tests = [
    {
        "test_id": "CROSS_EN",
        "name": "English text with English ref",
        "text": "Don't wander off, Nelly.",
        "lang": "en",
        "ref": vp_librarian_ref,
        "out_file": FORENSICS_DIR / "cross_en.wav"
    },
    {
        "test_id": "CROSS_RU",
        "name": "Russian text with English ref",
        "text": "Не уходи из виду, Нелли.",
        "lang": "ru",
        "ref": vp_librarian_ref,
        "out_file": FORENSICS_DIR / "cross_ru.wav"
    }
]

for ct in cross_tests:
    tid = ct["test_id"]
    print(f"\n--- {tid}: {ct['name']} ---")
    print(f"Text: \"{ct['text']}\" (lang={ct['lang']})")
    t0 = time.time()
    tts.tts_to_file(
        text=ct["text"],
        speaker_wav=str(ct["ref"]),
        language=ct["lang"],
        file_path=str(ct["out_file"]),
        split_sentences=False,
    )
    synth_time = time.time() - t0
    metrics = compute_audio_metrics(ct["out_file"])
    asr_res = transcribe_audio(ct["out_file"], lang=ct["lang"])

    print(f"Synthesized in: {synth_time:.2f}s | Duration: {metrics['duration_seconds']:.3f}s")
    print(f"ASR ({asr_res['language']}): \"{asr_res['text']}\"")

    results["test_runs"][tid] = {
        "text": ct["text"],
        "language": ct["lang"],
        "synth_time_seconds": round(synth_time, 2),
        "output_file": str(ct["out_file"].relative_to(PROJECT_ROOT)),
        "audio_metrics": metrics,
        "asr": asr_res
    }

# --- 3. COMPARISON AUDIO SET (DIRECT, API, WRAPPER, ORIGINAL REF) ---
print("\n" + "=" * 80)
print("RUNNING COMPARISON AUDIO SET")
print("=" * 80)

# A. control_direct_ru.wav (Direct model.full_inference)
out_direct = FORENSICS_DIR / "control_direct_ru.wav"
print("\n--- Generating control_direct_ru.wav (Direct model.full_inference) ---")
t0 = time.time()
res_dir = model.full_inference(
    text="Не уходи из виду, Нелли.",
    ref_audio_path=str(vp_librarian_ref),
    language="ru",
    temperature=0.75,
    length_penalty=1.0,
    repetition_penalty=5.0,
    top_k=50,
    top_p=0.85,
    do_sample=True,
)
sf.write(str(out_direct), res_dir["wav"], 24000)
synth_time = time.time() - t0
metrics_direct = compute_audio_metrics(out_direct)
asr_direct = transcribe_audio(out_direct, lang="ru")
print(f"Direct Duration: {metrics_direct['duration_seconds']:.3f}s | ASR: \"{asr_direct['text']}\"")
results["test_runs"]["control_direct_ru"] = {
    "output_file": str(out_direct.relative_to(PROJECT_ROOT)),
    "synth_time_seconds": round(synth_time, 2),
    "audio_metrics": metrics_direct,
    "asr": asr_direct
}

# B. control_api_ru.wav (TTS API tts_to_file)
out_api = FORENSICS_DIR / "control_api_ru.wav"
print("\n--- Generating control_api_ru.wav (TTS API tts_to_file) ---")
t0 = time.time()
tts.tts_to_file(
    text="Не уходи из виду, Нелли.",
    speaker_wav=str(vp_librarian_ref),
    language="ru",
    file_path=str(out_api),
    split_sentences=False,
)
synth_time = time.time() - t0
metrics_api = compute_audio_metrics(out_api)
asr_api = transcribe_audio(out_api, lang="ru")
print(f"API Duration: {metrics_api['duration_seconds']:.3f}s | ASR: \"{asr_api['text']}\"")
results["test_runs"]["control_api_ru"] = {
    "output_file": str(out_api.relative_to(PROJECT_ROOT)),
    "synth_time_seconds": round(synth_time, 2),
    "audio_metrics": metrics_api,
    "asr": asr_api
}

# C. control_wrapper_ru.wav (batch pipeline wrapper logic with -1.0 dBFS normalization)
out_wrapper = FORENSICS_DIR / "control_wrapper_ru.wav"
print("\n--- Generating control_wrapper_ru.wav (Pipeline Wrapper with -1 dBFS norm) ---")
t0 = time.time()
tts.tts_to_file(
    text="Не уходи из виду, Нелли.",
    speaker_wav=str(vp_librarian_ref),
    language="ru",
    file_path=str(out_wrapper),
    split_sentences=False,
)
# apply -1.0 dBFS normalization
raw_w, _ = sf.read(out_wrapper)
peak_w = np.max(np.abs(raw_w))
if peak_w > 0:
    target_peak = 10 ** (-1.0 / 20.0)
    norm_w = raw_w * (target_peak / peak_w)
    sf.write(str(out_wrapper), norm_w.astype(np.float32), 24000, subtype="PCM_16")
synth_time = time.time() - t0
metrics_wrapper = compute_audio_metrics(out_wrapper)
asr_wrapper = transcribe_audio(out_wrapper, lang="ru")
print(f"Wrapper Duration: {metrics_wrapper['duration_seconds']:.3f}s | ASR: \"{asr_wrapper['text']}\"")
results["test_runs"]["control_wrapper_ru"] = {
    "output_file": str(out_wrapper.relative_to(PROJECT_ROOT)),
    "synth_time_seconds": round(synth_time, 2),
    "audio_metrics": metrics_wrapper,
    "asr": asr_wrapper
}

# D. control_original_reference_ru.wav
out_orig_ref = FORENSICS_DIR / "control_original_reference_ru.wav"
print("\n--- Generating control_original_reference_ru.wav ---")
t0 = time.time()
tts.tts_to_file(
    text="Не уходи из виду, Нелли.",
    speaker_wav=str(vp_librarian_ref),
    language="ru",
    file_path=str(out_orig_ref),
    split_sentences=False,
)
synth_time = time.time() - t0
metrics_orig_ref = compute_audio_metrics(out_orig_ref)
asr_orig_ref = transcribe_audio(out_orig_ref, lang="ru")
print(f"Orig Ref Duration: {metrics_orig_ref['duration_seconds']:.3f}s | ASR: \"{asr_orig_ref['text']}\"")
results["test_runs"]["control_original_reference_ru"] = {
    "output_file": str(out_orig_ref.relative_to(PROJECT_ROOT)),
    "synth_time_seconds": round(synth_time, 2),
    "audio_metrics": metrics_orig_ref,
    "asr": asr_orig_ref
}

# Save complete results JSON
results_file = FORENSICS_DIR / "phase9a_control_results.json"
with open(results_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("\n" + "=" * 80)
print(f"ALL CONTROL RUNS COMPLETED. Results written to: {results_file}")
print("=" * 80)
