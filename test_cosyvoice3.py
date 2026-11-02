import sys
import os

ROOT_DIR = r"E:\AI-Dubbing\CosyVoice"
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "third_party", "Matcha-TTS"))

import torch
import torchaudio
from cosyvoice.cli.cosyvoice import AutoModel

print("PyTorch:", torch.__version__)
print("CUDA Available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("Device:", torch.cuda.get_device_name(0))

model_dir = os.path.join(ROOT_DIR, "pretrained_models", "Fun-CosyVoice3-0.5B")
cosyvoice = AutoModel(model_dir=model_dir)
print("AutoModel loaded successfully! SR:", cosyvoice.sample_rate)

output_dir = r"E:\AI-Dubbing\alltalk_tts\outputs"
os.makedirs(output_dir, exist_ok=True)

test_phrase = "Три миллиона? Мошенник! Твой магазин - сплошное надувательство!"

# Test 1: Cross-lingual with male_01.wav
prompt_wav = r"E:\AI-Dubbing\alltalk_tts\voices\male_01.wav"
print("\n--- Test 1: Cross-lingual with male_01.wav ---")
tts_text = f"You are a helpful assistant.<|endofprompt|>{test_phrase}"
outputs = list(cosyvoice.inference_cross_lingual(tts_text, prompt_wav, stream=False))
if outputs:
    wav_tensor = torch.concat([o['tts_speech'] for o in outputs], dim=1)
    out_file = os.path.join(output_dir, "phrase_cosyvoice3_crosslingual_male01.wav")
    torchaudio.save(out_file, wav_tensor, cosyvoice.sample_rate)
    print("Saved:", out_file)

# Test 2: Instruct mode (angry / expressive) with male_01.wav
print("\n--- Test 2: Instruct mode (angry) with male_01.wav ---")
instruct_text = "You are a helpful assistant. 请非常生气地说一句话。<|endofprompt|>"
outputs_instruct = list(cosyvoice.inference_instruct2(test_phrase, instruct_text, prompt_wav, stream=False))
if outputs_instruct:
    wav_tensor = torch.concat([o['tts_speech'] for o in outputs_instruct], dim=1)
    out_file = os.path.join(output_dir, "phrase_cosyvoice3_instruct_angry_male01.wav")
    torchaudio.save(out_file, wav_tensor, cosyvoice.sample_rate)
    print("Saved:", out_file)

# Test 3: Cross-lingual with Arnold.wav
arnold_wav = r"E:\AI-Dubbing\alltalk_tts\voices\Arnold.wav"
if os.path.exists(arnold_wav):
    print("\n--- Test 3: Cross-lingual with Arnold.wav ---")
    outputs_arnold = list(cosyvoice.inference_cross_lingual(tts_text, arnold_wav, stream=False))
    if outputs_arnold:
        wav_tensor = torch.concat([o['tts_speech'] for o in outputs_arnold], dim=1)
        out_file = os.path.join(output_dir, "phrase_cosyvoice3_crosslingual_Arnold.wav")
        torchaudio.save(out_file, wav_tensor, cosyvoice.sample_rate)
        print("Saved:", out_file)

print("\nAll CosyVoice 3 tests completed successfully!")
