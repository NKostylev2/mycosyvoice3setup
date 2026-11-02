import os
import sys
import time
import subprocess
import re
from typing import List, Dict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import torch
import torchaudio

from fanfic_pipeline.config import (
    BASE_DIR,
    COSYVOICE_DIR,
    COSYVOICE_MODEL_DIR,
    DEFAULT_VOICE,
    DEFAULT_TTS_INSTRUCT,
    DEFAULT_SEED,
)

# Ensure CosyVoice and Matcha-TTS are in sys.path
if COSYVOICE_DIR not in sys.path:
    sys.path.insert(0, COSYVOICE_DIR)
matcha_dir = os.path.join(COSYVOICE_DIR, "third_party", "Matcha-TTS")
if matcha_dir not in sys.path:
    sys.path.insert(0, matcha_dir)

from cosyvoice.cli.cosyvoice import AutoModel

FFMPEG_EXE = os.path.join(BASE_DIR, "vendor", "ffmpeg", "bin", "ffmpeg.exe")

class CosyVoiceWorker:
    def __init__(
        self,
        model_dir: str = COSYVOICE_MODEL_DIR,
        voice_path: str = DEFAULT_VOICE,
        prompt_text: Optional[str] = None,
        speed: float = 1.0,
        instruct: str = DEFAULT_TTS_INSTRUCT,
        seed: int = DEFAULT_SEED,
    ):
        self.model_dir = model_dir
        self.voice_path = voice_path
        self.speed = speed
        self.instruct = instruct
        self.seed = seed

        # Load reference transcription if available
        if prompt_text:
            self.ref_text = prompt_text
        else:
            ref_path = os.path.splitext(voice_path)[0] + ".reference.txt"
            if os.path.exists(ref_path):
                with open(ref_path, "r", encoding="utf-8") as f:
                    self.ref_text = f.read().strip()
            else:
                self.ref_text = ""

        print(f"[CosyVoice] Loading model from {model_dir}...")
        t0 = time.time()
        self.model = AutoModel(model_dir=model_dir)
        self.sample_rate = self.model.sample_rate
        print(f"[CosyVoice] Model loaded in {time.time() - t0:.2f}s. Sample rate: {self.sample_rate}Hz.")

    def synthesize_sentence(self, text: str, output_path: str) -> bool:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        # Sanitize text from stray CJK or alien symbols, preserving Russian and 'ё'
        text = re.sub(r'[\u4e00-\u9fff]', '', text).strip()
        if not text:
            return False
        try:
            if self.seed is not None:
                torch.manual_seed(self.seed)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(self.seed)

            # CosyVoice3 zero-shot inference with text_frontend=False, stream=False, speed=1.0
            prompt_text = f"You are a helpful assistant.<|endofprompt|>{self.ref_text}"
            outputs = list(self.model.inference_zero_shot(
                tts_text=text,
                prompt_text=prompt_text,
                prompt_wav=self.voice_path,
                stream=False,
                speed=self.speed,
                text_frontend=False
            ))

            if outputs and outputs[0]['tts_speech'].shape[1] > 0:
                wav_tensor = torch.concat([o['tts_speech'] for o in outputs], dim=1)
                torchaudio.save(output_path, wav_tensor, self.sample_rate)
                return True
            else:
                print(f"[CosyVoice Error] Empty output for text: {text[:50]}")
                return False
        except Exception as e:
            print(f"[CosyVoice Error] Failed to synthesize: {e}")
            return False

    def synthesize_segments(
        self,
        segments: List[Dict],
        output_dir: str,
        skip_existing: bool = True,
    ) -> List[str]:
        """
        Synthesizes each segment to a separate WAV file.
        Returns list of generated file paths in order.
        """
        os.makedirs(output_dir, exist_ok=True)
        file_paths = []
        total = len(segments)

        print(f"\n[CosyVoice] Starting synthesis for {total} segments...")

        for idx, seg in enumerate(segments):
            filename = f"seg_{idx:04d}.wav"
            out_path = os.path.join(output_dir, filename)
            file_paths.append(out_path)

            if skip_existing and os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                print(f"[{idx+1}/{total}] Skipping (already exists): {seg['text'][:40]}...")
                continue

            # Safe print
            enc = sys.stdout.encoding or 'utf-8'
            safe_text = seg['text'].encode(enc, errors='replace').decode(enc)
            print(f"[{idx+1}/{total}] Synthesizing: {safe_text}")
            t0 = time.time()
            ok = self.synthesize_sentence(seg['text'], out_path)
            duration = time.time() - t0
            if ok:
                print(f"    -> Done in {duration:.2f}s")
            else:
                print(f"    -> Failed!")

        return file_paths

    def assemble_audio(
        self,
        segments: List[Dict],
        segment_files: List[str],
        final_wav_path: str,
        pause_sentence_ms: int = 200,
        pause_paragraph_ms: int = 500,
        tail_silence_ms: int = 500,
    ) -> str:
        """
        Concatenates segment audio files with natural silence pauses
        and guarantees trailing digital silence (500 ms) so no word endings get truncated.
        """
        print(f"\n[Assembly] Concatenating {len(segment_files)} segments into {final_wav_path}...")
        os.makedirs(os.path.dirname(os.path.abspath(final_wav_path)), exist_ok=True)

        audio_chunks = []
        silence_sentence = torch.zeros((1, int(self.sample_rate * pause_sentence_ms / 1000)))
        silence_para = torch.zeros((1, int(self.sample_rate * pause_paragraph_ms / 1000)))
        silence_tail = torch.zeros((1, int(self.sample_rate * tail_silence_ms / 1000)))

        for idx, (seg, fpath) in enumerate(zip(segments, segment_files)):
            if not os.path.exists(fpath):
                print(f"[Warning] Segment file missing: {fpath}")
                continue

            try:
                wav, sr = torchaudio.load(fpath)
                if sr != self.sample_rate:
                    wav = torchaudio.functional.resample(wav, sr, self.sample_rate)
                # Ensure 2D tensor (channels, time)
                if wav.dim() == 1:
                    wav = wav.unsqueeze(0)
                elif wav.shape[0] > 1:
                    wav = wav.mean(dim=0, keepdim=True)

                audio_chunks.append(wav)

                # Add silence
                if seg.get("is_last_in_p", False):
                    audio_chunks.append(silence_para)
                else:
                    audio_chunks.append(silence_sentence)
            except Exception as e:
                print(f"[Warning] Could not load {fpath}: {e}")

        if not audio_chunks:
            raise RuntimeError("No audio chunks available to assemble.")

        # Append 500ms digital tail silence to protect final syllables
        audio_chunks.append(silence_tail)

        full_wav = torch.cat(audio_chunks, dim=1)
        torchaudio.save(final_wav_path, full_wav, self.sample_rate)
        total_sec = full_wav.shape[1] / self.sample_rate
        print(f"[Assembly] Complete! Total duration: {total_sec / 60:.2f} minutes ({total_sec:.1f}s)")

        # Convert to MP3 if ffmpeg exists
        if os.path.exists(FFMPEG_EXE):
            mp3_path = os.path.splitext(final_wav_path)[0] + ".mp3"
            print(f"[Assembly] Converting to MP3: {mp3_path}...")
            cmd = [
                FFMPEG_EXE,
                "-y",
                "-i", final_wav_path,
                "-codec:a", "libmp3lame",
                "-b:a", "192k",
                mp3_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(mp3_path):
                print(f"[Assembly] MP3 created: {mp3_path}")
                return mp3_path

        return final_wav_path
