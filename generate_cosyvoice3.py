import os
import sys
import argparse

ROOT_DIR = r"E:\AI-Dubbing\CosyVoice"
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "third_party", "Matcha-TTS"))

import torch
import torchaudio
from cosyvoice.cli.cosyvoice import AutoModel

def main():
    parser = argparse.ArgumentParser(description="CosyVoice 3 TTS Generation CLI")
    parser.add_argument("--text", type=str, required=True, help="Text to synthesize")
    parser.add_argument("--voice", type=str, default=r"E:\AI-Dubbing\alltalk_tts\voices\male_01.wav", help="Reference audio path")
    parser.add_argument("--instruct", type=str, default=None, help="Optional emotion/style instruction")
    parser.add_argument("--output", type=str, default=r"E:\AI-Dubbing\alltalk_tts\outputs\cosyvoice3_out.wav", help="Output WAV path")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed (default: 1.0)")
    args = parser.parse_args()

    model_dir = os.path.join(ROOT_DIR, "pretrained_models", "Fun-CosyVoice3-0.5B")
    cosyvoice = AutoModel(model_dir=model_dir)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    if args.instruct:
        instruct_text = f"You are a helpful assistant. {args.instruct}<|endofprompt|>"
        outputs = list(cosyvoice.inference_instruct2(args.text, instruct_text, args.voice, speed=args.speed))
    else:
        tts_text = f"You are a helpful assistant.<|endofprompt|>{args.text}"
        outputs = list(cosyvoice.inference_cross_lingual(tts_text, args.voice, speed=args.speed))

    if outputs:
        wav_tensor = torch.concat([o['tts_speech'] for o in outputs], dim=1)
        torchaudio.save(args.output, wav_tensor, cosyvoice.sample_rate)
        print(f"Generated successfully: {args.output}")
    else:
        print("Failed to generate audio.")

if __name__ == "__main__":
    main()
