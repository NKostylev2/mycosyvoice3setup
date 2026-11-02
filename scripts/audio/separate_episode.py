import os
import sys
import time

# Ensure ffmpeg and torch CUDA DLLs are in PATH
os.environ["PATH"] = r"E:\AI-Dubbing\vendor\ffmpeg\bin;E:\AI-Dubbing\.venv\Lib\site-packages\torch\lib;" + os.environ["PATH"]

from audio_separator.separator import Separator

def run_separation():
    start_time = time.time()
    input_audio = r"E:\AI-Dubbing\work\S01E01\audio\english.wav"
    output_dir = r"E:\AI-Dubbing\work\S01E01\audio"
    models_dir = r"E:\AI-Dubbing\models"

    print("=" * 60)
    print("  AI-Dubbing: BS-RoFormer Vocal & Instrumental Separation")
    print("=" * 60)
    print(f"Input Master Audio: {input_audio}")
    print(f"Target Output Directory: {output_dir}")
    print("Using Model: BS-RoFormer (model_bs_roformer_ep_317_sdr_12.9755.ckpt) on CUDA")

    separator = Separator(
        output_dir=output_dir,
        output_format="WAV",
        model_file_dir=models_dir
    )

    separator.load_model("model_bs_roformer_ep_317_sdr_12.9755.ckpt")

    print("\nProcessing audio on GPU (RTX 3070)...")
    output_files = separator.separate(
        input_audio,
        custom_output_names={"Vocals": "english_vocals", "Instrumental": "english_instrumental"}
    )

    elapsed = time.time() - start_time
    print(f"\n[SUCCESS] Separation completed in {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)!")
    print(f"Vocals file: {output_files}")

if __name__ == "__main__":
    run_separation()
