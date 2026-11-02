import os
import sys
import torch
import torchaudio

ROOT_DIR = r"E:\AI-Dubbing\CosyVoice"
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "third_party", "Matcha-TTS"))

from cosyvoice.cli.cosyvoice import AutoModel

model_dir = os.path.join(ROOT_DIR, "pretrained_models", "Fun-CosyVoice3-0.5B")
cosyvoice = AutoModel(model_dir=model_dir)

voice_path = r"E:\AI-Dubbing\alltalk_tts\voices\female_03.wav"
out_dir = r"E:\AI-Dubbing\alltalk_tts\outputs\timbre_test"
os.makedirs(out_dir, exist_ok=True)

instruct = "You are a professional female audiobook narrator reading a novel with a calm, steady, clear voice and even, natural pacing.<|endofprompt|>"

# Compare 3 phrases:
# 1. First sentence
# 2. Short sentence alone
# 3. Merged sentence (2 + 3)

p1 = "Я ненавидела эту комнату с глубинной, огненной страстью миллиона адов."
p2_short = "Но это был факт."
p2_merged = "Я не хотела быть склонной к излишней драме, правда, но это был факт."

def synth(text, name, use_instruct=True, seed=42):
    if seed is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    
    if use_instruct:
        outputs = list(cosyvoice.inference_instruct2(text, f"You are a helpful assistant. {instruct}", voice_path, speed=1.0))
    else:
        tts_text = f"You are a helpful assistant.<|endofprompt|>{text}"
        outputs = list(cosyvoice.inference_cross_lingual(tts_text, voice_path, speed=1.0))

    if outputs:
        wav = torch.concat([o['tts_speech'] for o in outputs], dim=1)
        out_f = os.path.join(out_dir, f"{name}.wav")
        torchaudio.save(out_f, wav, cosyvoice.sample_rate)
        print(f"Generated {out_f}")

print("Synthesizing test variants...")
synth(p1, "p1_instruct_seed42", use_instruct=True, seed=42)
synth(p2_merged, "p2_merged_instruct_seed42", use_instruct=True, seed=42)

# Also concatenate them with silence
silence = torch.zeros((1, int(cosyvoice.sample_rate * 0.3)))
w1, sr = torchaudio.load(os.path.join(out_dir, "p1_instruct_seed42.wav"))
w2, sr = torchaudio.load(os.path.join(out_dir, "p2_merged_instruct_seed42.wav"))
stitched = torch.cat([w1, silence, w2], dim=1)
torchaudio.save(os.path.join(out_dir, "stitched_comparison.wav"), stitched, sr)
print("Saved stitched_comparison.wav!")
