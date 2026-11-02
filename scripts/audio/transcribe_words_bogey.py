from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")
segments, info = model.transcribe(r"E:\AI-Dubbing\work\test_slices\bogey_scene_vocals_942_962.wav", language="en", word_timestamps=True)

for seg in segments:
    print(f"[{seg.start:.2f}s - {seg.end:.2f}s]: {seg.text}")
    for w in seg.words:
        print(f"   {w.start:.2f}-{w.end:.2f}: {w.word} (p={w.probability:.2f})")
