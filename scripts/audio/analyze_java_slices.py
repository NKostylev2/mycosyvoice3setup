import os
import soundfile as sf
import numpy as np
from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")

clips = [
    "java_d0019_massage_good.wav",
    "java_simulator_combat.wav",
    "java_d0104_not_cold.wav",
    "java_bog_fight.wav",
    "java_d0199_massage.wav",
    "java_d0216_run.wav",
    "java_d0220_laugh.wav"
]

for c in clips:
    path = os.path.join(r"E:\AI-Dubbing\work\test_slices", c)
    y, sr = sf.read(path)
    dur = len(y) / sr
    segs, _ = model.transcribe(path, language="en", word_timestamps=True)
    words = []
    for s in segs:
        for w in s.words:
            words.append(f"{w.word}({w.start:.2f}-{w.end:.2f})")
    print(f"{c} ({dur:.2f}s): {' '.join(words) if words else '[NO SPEECH TRANSCRIBED]'}")
