"""
Runtime Bootstrap Module for Phase 9 Batch TTS
Martin Mystery AI Dubbing Pipeline (E:\\AI-Dubbing)

This module deterministically configures project-local paths and environment variables
without requiring any manual PowerShell environment variable exports:
- COQUI_TOS_AGREED = 1
- TTS_HOME = E:\\AI-Dubbing\\cache
- HF_HOME = E:\\AI-Dubbing\\cache\\huggingface
- TORCH_HOME = E:\\AI-Dubbing\\cache\\torch
- PATH includes E:\\AI-Dubbing\\vendor\\ffmpeg\\bin
"""

import os
import sys
from pathlib import Path

# Compute project root from file location
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Deterministically establish project-local environment
os.environ["COQUI_TOS_AGREED"] = "1"
os.environ["TTS_HOME"] = str(PROJECT_ROOT / "cache")
os.environ["HF_HOME"] = str(PROJECT_ROOT / "cache" / "huggingface")
os.environ["TORCH_HOME"] = str(PROJECT_ROOT / "cache" / "torch")

# Prepend project-local vendor ffmpeg/bin to PATH
ffmpeg_bin = str(PROJECT_ROOT / "vendor" / "ffmpeg" / "bin")
current_path = os.environ.get("PATH", "")
if ffmpeg_bin.lower() not in current_path.lower():
    os.environ["PATH"] = ffmpeg_bin + os.pathsep + current_path


def get_runtime_paths():
    """Return dictionary of canonical project runtime paths."""
    return {
        "project_root": PROJECT_ROOT,
        "python": Path(sys.executable),
        "tts_home": PROJECT_ROOT / "cache",
        "hf_home": PROJECT_ROOT / "cache" / "huggingface",
        "torch_home": PROJECT_ROOT / "cache" / "torch",
        "xtts_model_canonical": PROJECT_ROOT / "models" / "xtts",
        "xtts_cache_dir": PROJECT_ROOT / "cache" / "tts" / "tts_models--multilingual--multi-dataset--xtts_v2",
        "ffmpeg": PROJECT_ROOT / "vendor" / "ffmpeg" / "bin" / "ffmpeg.exe",
        "ffprobe": PROJECT_ROOT / "vendor" / "ffmpeg" / "bin" / "ffprobe.exe",
        "voice_profiles": PROJECT_ROOT / "work" / "S01E01" / "voice_profiles",
        "tts_preparation": PROJECT_ROOT / "work" / "S01E01" / "tts_preparation.json",
        "speaker_casting": PROJECT_ROOT / "work" / "S01E01" / "speaker_casting.json",
    }


def init_xtts_pipeline(gpu=True):
    """
    Initializes XTTS-v2 from project-local resources.
    Returns: (tts_instance, resolved_paths_dict)
    """
    import torch
    from TTS.api import TTS
    from TTS.utils.manage import ModelManager

    mm = ModelManager()
    output_prefix = mm.output_prefix
    model_full_name = "tts_models--multilingual--multi-dataset--xtts_v2"
    resolved_model_dir = Path(output_prefix) / model_full_name

    use_cuda = gpu and torch.cuda.is_available()
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=use_cuda)

    resolved_paths = {
        "output_prefix": str(output_prefix),
        "resolved_cache_path": str(resolved_model_dir),
        "resolved_model_path": str(resolved_model_dir / "model.pth"),
        "resolved_config_path": str(resolved_model_dir / "config.json"),
        "canonical_model_path": str(PROJECT_ROOT / "models" / "xtts" / "model.pth"),
        "is_project_local": str(resolved_model_dir).lower().startswith(str(PROJECT_ROOT).lower()),
    }
    return tts, resolved_paths
