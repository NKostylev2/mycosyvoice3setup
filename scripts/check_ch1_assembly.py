import os, json, soundfile as sf

# Let's inspect Chapter_01_Рыжие Сдобные Зомби.wav or the exact concatenation
wav_path = r"E:\AI-Dubbing\output\wide_awake\Chapter_01_Рыжие Сдобные Зомби.wav"
if os.path.exists(wav_path):
    print("Found chapter 1 wav, duration:", sf.info(wav_path).duration)

# Let's find how Chapter 1 was assembled in batch_runner or dual_pipeline
