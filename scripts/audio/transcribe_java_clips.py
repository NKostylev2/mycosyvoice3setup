import os
from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")

clips = [
    "java_D0019_massage_good.wav",
    "java_sim_combat.wav",
    "java_swamp_investigation.wav",
    "java_ending_massage.wav",
    "java_ending_run.wav",
    "java_ending_enjoyment_laugh.wav"
]

for c in clips:
    path = os.path.join(r"E:\AI-Dubbing\work\test_slices", c)
    segs, _ = model.transcribe(path, language="en", word_timestamps=True)
    print(f"\n--- {c} ---")
    has_words = False
    for s in segs:
        print(f"[{s.start:.2f}-{s.end:.2f}]: {s.text}")
        has_words = True
    if not has_words:
        print("(No speech transcribed - likely grunt / non-verbal vocalization)")
