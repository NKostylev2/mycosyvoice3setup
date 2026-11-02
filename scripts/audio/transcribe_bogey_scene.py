import os
import sys

# Try importing faster_whisper or whisper
try:
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, info = model.transcribe(r"E:\AI-Dubbing\work\test_slices\bogey_scene_920_1020.wav", language="en")
    print("Detected language:", info.language)
    for seg in segments:
        print(f"[{920 + seg.start:.2f}s - {920 + seg.end:.2f}s]: {seg.text}")
except Exception as e:
    print("Error:", e)
