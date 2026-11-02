import soundfile as sf
import numpy as np
import json
import sys
from pathlib import Path
import torch
from faster_whisper import WhisperModel

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

p = Path(r"E:\AI-Dubbing\work\S01E01\tts\U0001-S01.wav")
data_f, sr = sf.read(p, dtype="float32")
data_i, _ = sf.read(p, dtype="int16")

dur = len(data_f) / sr
peak = float(np.max(np.abs(data_f)))
peak_db = float(20 * np.log10(peak)) if peak > 0 else -100.0
rms = float(np.sqrt(np.mean(data_f ** 2)))
rms_db = float(20 * np.log10(rms)) if rms > 0 else -100.0
samples_0db = int(np.sum(np.abs(data_i) >= 32767))
has_nan = bool(np.isnan(data_f).any())
has_inf = bool(np.isinf(data_f).any())

print("=" * 60)
print("U0001-S01 AUDIO METRICS")
print("=" * 60)
print(f"File: {p}")
print(f"Duration: {dur:.4f} s")
print(f"Sample Rate: {sr} Hz")
print(f"Channels: {data_f.ndim}")
print(f"Subtype: PCM_16")
print(f"Actual Peak: {peak:.6f}")
print(f"Peak dBFS: {peak_db:.4f} dBFS")
print(f"RMS dBFS: {rms_db:.2f} dBFS")
print(f"Samples at 0 dBFS: {samples_0db}")
print(f"Clipping Detected: {samples_0db > 0}")
print(f"Has NaN: {has_nan}, Has Inf: {has_inf}")

print("\n" + "=" * 60)
print("REVERSE ASR (Faster-Whisper medium)")
print("=" * 60)
asr = WhisperModel("medium", device="cuda", compute_type="float16")
segments, info = asr.transcribe(str(p), language="ru", beam_size=5)
rec = " ".join([s.text.strip() for s in segments])
print(f"ASR Language: {info.language} (prob: {info.language_probability:.3f})")
print(f"ASR Recognized Text: \"{rec}\"")
for s in segments:
    print(f"  [{s.start:.2f}s -> {s.end:.2f}s] logprob={s.avg_logprob:.3f}, no_speech={s.no_speech_prob:.3f}: \"{s.text}\"")

# Return structured dict
out_meta = {
    "file": str(p),
    "metrics": {
        "duration_seconds": round(dur, 4),
        "sample_rate": sr,
        "channels": data_f.ndim,
        "peak_dbfs": round(peak_db, 4),
        "rms_dbfs": round(rms_db, 2),
        "samples_at_0dBFS": samples_0db,
        "clipping": samples_0db > 0,
        "has_nan": has_nan,
        "has_inf": has_inf
    },
    "asr": {
        "language": info.language,
        "language_prob": round(info.language_probability, 3),
        "recognized_text": rec,
        "segments": [
            {
                "start": round(s.start, 2),
                "end": round(s.end, 2),
                "text": s.text.strip(),
                "avg_logprob": round(s.avg_logprob, 3),
                "no_speech_prob": round(s.no_speech_prob, 3)
            }
            for s in segments
        ]
    }
}
out_json = Path(r"E:\AI-Dubbing\work\S01E01\tts_forensics\u0001_production_validation.json")
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(out_meta, f, indent=2, ensure_ascii=False)
print(f"\nWrote validation results to: {out_json}")
