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

out_dir = r"E:\AI-Dubbing\alltalk_tts\outputs"
os.makedirs(out_dir, exist_ok=True)

tests = [
    {
        "out_file": "test_bogeyman_final.wav",
        "voice": r"E:\AI-Dubbing\alltalk_tts\voices\monster_bogeyman.wav",
        "text": "Вы здесь, потому что вы непослушные дети, и вы никогда отсюда не уйдёте.",
        "instruct": "Sinister, menacing, deep, raspy nursery bogeyman monster voice, dark, chilling, native Russian speech without English accent.",
        "speed": 0.95
    },
    {
        "out_file": "test_java_d0019_final.wav",
        "voice": r"E:\AI-Dubbing\alltalk_tts\voices\java.wav",
        "text": "Массаж, хорошо.",
        "instruct": "Deep, low, rough, primitive Neanderthal caveman voice, slow and guttural, native Russian pronunciation.",
        "speed": 0.95
    },
    {
        "out_file": "test_java_d0104_final.wav",
        "voice": r"E:\AI-Dubbing\alltalk_tts\voices\java.wav",
        "text": "Не холодный.",
        "instruct": "Deep, low, rough, primitive Neanderthal caveman voice, slow and guttural, native Russian pronunciation.",
        "speed": 1.0
    },
    {
        "out_file": "test_java_d0216_final.wav",
        "voice": r"E:\AI-Dubbing\alltalk_tts\voices\java.wav",
        "text": "Ява бежать сейчас!",
        "instruct": "Excited, deep, booming caveman shout, low pitch, native Russian pronunciation.",
        "speed": 1.05
    }
]

for t in tests:
    print(f"\n==========================================")
    print(f"Generating: {t['out_file']}")
    print(f"Voice ref: {t['voice']}")
    print(f"Text: {t['text']}")
    print(f"Instruct: {t['instruct']}")
    print(f"==========================================")
    
    instruct_prompt = f"You are a helpful assistant. {t['instruct']}<|endofprompt|>"
    outputs = list(cosyvoice.inference_instruct2(t['text'], instruct_prompt, t['voice'], speed=t['speed']))
    
    if outputs:
        wav_tensor = torch.concat([o['tts_speech'] for o in outputs], dim=1)
        out_path = os.path.join(out_dir, t['out_file'])
        torchaudio.save(out_path, wav_tensor, cosyvoice.sample_rate)
        print(f"  [SUCCESS] Saved: {out_path} ({wav_tensor.shape[1]/cosyvoice.sample_rate:.2f}s, SR: {cosyvoice.sample_rate})")
    else:
        print(f"  [ERROR] Failed to generate {t['out_file']}")

print("\nAll tests completed!")
