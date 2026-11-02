import os
import sys

root_dir = r"E:\AI-Dubbing"
cosy_dir = os.path.join(root_dir, "CosyVoice")
sys.path.insert(0, cosy_dir)
sys.path.insert(0, os.path.join(cosy_dir, "third_party", "Matcha-TTS"))

import torch
import torchaudio
from cosyvoice.cli.cosyvoice import AutoModel

model_dir = os.path.join(cosy_dir, "pretrained_models", "Fun-CosyVoice3-0.5B")
print(f"Loading CosyVoice 3 from {model_dir}...")
cosyvoice = AutoModel(model_dir=model_dir)
print("CosyVoice 3 loaded successfully!")

martin_voice = r"E:\AI-Dubbing\alltalk_tts\voices\martin_mystery.wav"
diana_voice = r"E:\AI-Dubbing\alltalk_tts\voices\diana_lombard.wav"
out_dir = r"E:\AI-Dubbing\alltalk_tts\outputs"

tests = [
    (
        "test_martin_tight_ref.wav",
        martin_voice,
        "Привет! Меня зовут Мартин Мистери, и я расследую паранормальные явления."
    ),
    (
        "test_martin_line_u0010.wav",
        martin_voice,
        "Да легко! Но тот, кто проиграет — а это точно будешь ты, — делает Яве массаж ног!"
    ),
    (
        "test_diana_line_u0009.wav",
        diana_voice,
        "Ладно, спорим, ты не сможешь продержаться совершенно чистым хотя бы один день?"
    )
]

for filename, voice, text in tests:
    print(f"\n--- Generating: {filename} ---")
    print(f"Text: {text}")
    print(f"Voice prompt: {voice}")
    
    tts_text = f"You are a helpful assistant.<|endofprompt|>{text}"
    outputs = list(cosyvoice.inference_cross_lingual(tts_text, voice, speed=1.0))
    
    if outputs:
        wav_tensor = torch.concat([o['tts_speech'] for o in outputs], dim=1)
        out_path = os.path.join(out_dir, filename)
        torchaudio.save(out_path, wav_tensor, cosyvoice.sample_rate)
        print(f"Saved: {out_path} (SR: {cosyvoice.sample_rate})")
    else:
        print(f"Failed to generate {filename}")

print("\nAll CosyVoice 3 tests completed successfully!")
