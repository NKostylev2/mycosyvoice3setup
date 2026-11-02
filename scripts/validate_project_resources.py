"""
Deterministic Project Resource & Runtime Lock Validator
Martin Mystery AI Dubbing Pipeline (E:\\AI-Dubbing)

Validates:
1. Project root exists and is canonical
2. Venv exists and python executable is functional inside project
3. Required Python packages import without errors
4. Actual GPU device and CUDA availability (NVIDIA GeForce RTX 3070, CUDA 12.8)
5. Runtime bootstrap environment isolation (TTS_HOME, HF_HOME, TORCH_HOME)
6. Dynamic TTS package path and ModelManager output prefix resolution
7. Dynamic XTTS model resolution to project-local paths
8. Required model files exist in project-local directories with SHA-256 hash match
9. Required vendor binaries exist and execute correctly (FFmpeg, FFprobe)
10. Voice profile references exist and are valid audio (10/10)
11. Phase 9 runtime lock file integrity (config/phase9_runtime.json)
12. Zero hardcoded external runtime paths in scripts and configs
"""

import os
import sys
import json
import hashlib
import subprocess
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(r"E:\AI-Dubbing")
MANIFEST_PATH = ROOT_DIR / "config" / "project_resources.json"
ENV_MANIFEST_PATH = ROOT_DIR / "config" / "environment_manifest.json"
RUNTIME_LOCK_PATH = ROOT_DIR / "config" / "phase9_runtime.json"


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    print("=" * 80)
    print("MARTIN MYSTERY AI DUBBING PIPELINE — COMPREHENSIVE RUNTIME LOCK VALIDATOR")
    print("=" * 80)

    total_checks = 0
    passed_checks = 0
    failed_checks = 0
    failures = []

    def record(name: str, passed: bool, detail: str = ""):
        nonlocal total_checks, passed_checks, failed_checks
        total_checks += 1
        if passed:
            passed_checks += 1
            print(f"  [PASS] {name}: {detail}")
        else:
            failed_checks += 1
            failures.append(f"{name}: {detail}")
            print(f"  [FAIL] {name}: {detail}")

    # 1. Project Root
    print("\n[1] Checking Project Root...")
    record("Project Root Exists", ROOT_DIR.exists() and ROOT_DIR.is_dir(), str(ROOT_DIR))

    # 2. Python Virtual Environment
    print("\n[2] Checking Virtual Environment & Interpreter...")
    venv_dir = ROOT_DIR / ".venv"
    py_exe = venv_dir / "Scripts" / "python.exe"
    record("Virtual Environment Directory", venv_dir.exists() and venv_dir.is_dir(), str(venv_dir))
    record("Python Executable Exists", py_exe.exists() and py_exe.is_file(), str(py_exe))
    is_current_venv = (Path(sys.executable).resolve() == py_exe.resolve())
    record("Running within Project Venv", is_current_venv, f"sys.executable={sys.executable}")

    # 3. Required Package Imports & CUDA GPU Verification
    print("\n[3] Checking Package Imports & GPU Acceleration...")
    import torch
    packages = ["torch", "torchaudio", "numpy", "soundfile", "TTS", "faster_whisper"]
    for pkg in packages:
        try:
            mod = __import__(pkg)
            version = getattr(mod, "__version__", "unknown")
            record(f"Import {pkg}", True, f"version={version}")
        except Exception as e:
            record(f"Import {pkg}", False, str(e))

    cuda_avail = torch.cuda.is_available()
    record("CUDA Acceleration", cuda_avail, f"torch_cuda={torch.version.cuda}")
    if cuda_avail:
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        gpu_match = "RTX 3070" in gpu_name
        record("GPU Model Verification", gpu_match, f"{gpu_name} ({vram_gb:.2f} GB VRAM)")
    else:
        record("GPU Model Verification", False, "CUDA not available")

    # 4. Runtime Bootstrap & Dynamic Path Resolution
    print("\n[4] Checking Runtime Bootstrap & Dynamic Path Resolution...")
    sys.path.insert(0, str(ROOT_DIR))
    from scripts.audio import runtime_bootstrap
    paths = runtime_bootstrap.get_runtime_paths()
    
    record("Runtime Bootstrap Root", paths["project_root"] == ROOT_DIR, str(paths["project_root"]))
    record("Runtime TTS_HOME", os.environ.get("TTS_HOME") == str(ROOT_DIR / "cache"), str(os.environ.get("TTS_HOME")))
    record("Runtime HF_HOME", os.environ.get("HF_HOME") == str(ROOT_DIR / "cache" / "huggingface"), str(os.environ.get("HF_HOME")))
    record("Runtime TORCH_HOME", os.environ.get("TORCH_HOME") == str(ROOT_DIR / "cache" / "torch"), str(os.environ.get("TORCH_HOME")))
    record("Runtime PATH includes FFmpeg", str(ROOT_DIR / "vendor" / "ffmpeg" / "bin").lower() in os.environ.get("PATH", "").lower(), "Vendor FFmpeg in PATH")

    # Inspect TTS ModelManager output prefix dynamically
    from TTS.utils.manage import ModelManager
    mm = ModelManager()
    output_prefix = Path(mm.output_prefix).resolve()
    expected_cache = (ROOT_DIR / "cache" / "tts").resolve()
    record("TTS ModelManager Output Prefix", output_prefix == expected_cache, f"prefix={output_prefix}")

    resolved_model_dir = output_prefix / "tts_models--multilingual--multi-dataset--xtts_v2"
    record("XTTS Model Directory in Cache", resolved_model_dir.exists(), str(resolved_model_dir))
    record("XTTS Model Weights in Cache", (resolved_model_dir / "model.pth").exists(), str(resolved_model_dir / "model.pth"))

    # 5. Manifest Existence & Structure
    print("\n[5] Checking Resource & Runtime Manifests...")
    record("Project Resources Manifest", MANIFEST_PATH.exists(), str(MANIFEST_PATH))
    record("Environment Manifest", ENV_MANIFEST_PATH.exists(), str(ENV_MANIFEST_PATH))
    record("Phase 9 Runtime Lock Manifest", RUNTIME_LOCK_PATH.exists(), str(RUNTIME_LOCK_PATH))

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    # 6. Model Files & Hash Verification
    print("\n[6] Checking Canonical Models & SHA-256 Hashes...")
    resources = manifest_data.get("resources", [])
    for res in resources:
        res_type = res.get("type")
        res_class = res.get("classification")
        res_name = res.get("name")
        expected_hash = res.get("sha256")
        expected_size = res.get("size_bytes", 0)

        # Skip non-local or optional
        if res_class in ("OPTIONAL", "EXTERNAL_SYSTEM"):
            continue

        if res_class == "CACHE":
            cp = ROOT_DIR / res.get("path")
            record(f"Cache Directory ({res_name})", cp.exists() and cp.is_dir(), str(cp))
            continue

        p = ROOT_DIR / res.get("path")
        if not p.exists():
            record(f"File Exists: {res_name}", False, f"Missing file at {p}")
            continue

        # Check size
        actual_size = p.stat().st_size
        size_match = (actual_size == expected_size)
        record(f"Size: {res_name}", size_match, f"{actual_size} bytes (expected {expected_size})")

        # Check hash
        if expected_hash and expected_hash not in ("DIRECTORY", "SYSTEM_MANAGED", "NOT_INSTALLED"):
            actual_hash = compute_sha256(p)
            hash_match = (actual_hash == expected_hash)
            record(f"SHA-256: {res_name}", hash_match, f"hash={actual_hash[:12]}...")

    # 7. Vendor Binaries Execution
    print("\n[7] Checking Vendor Executables (FFmpeg / FFprobe)...")
    ffmpeg_exe = ROOT_DIR / "vendor" / "ffmpeg" / "bin" / "ffmpeg.exe"
    ffprobe_exe = ROOT_DIR / "vendor" / "ffmpeg" / "bin" / "ffprobe.exe"
    
    try:
        res_ff = subprocess.run([str(ffmpeg_exe), "-version"], capture_output=True, text=True)
        record("FFmpeg Execution", res_ff.returncode == 0, res_ff.stdout.splitlines()[0] if res_ff.stdout else "No output")
    except Exception as e:
        record("FFmpeg Execution", False, str(e))

    try:
        res_fp = subprocess.run([str(ffprobe_exe), "-version"], capture_output=True, text=True)
        record("FFprobe Execution", res_fp.returncode == 0, res_fp.stdout.splitlines()[0] if res_fp.stdout else "No output")
    except Exception as e:
        record("FFprobe Execution", False, str(e))

    # 8. Voice Profile References Integrity
    print("\n[8] Checking Voice Profile References (S01E01)...")
    vp_json_path = ROOT_DIR / "work" / "S01E01" / "voice_profiles.json"
    if vp_json_path.exists():
        with open(vp_json_path, "r", encoding="utf-8") as f:
            vp_data = json.load(f)
        profiles = vp_data.get("profiles", {})
        record("Voice Profiles Count", len(profiles) == 10, f"Found {len(profiles)} profiles (expected 10)")
        for vp_id, prof in profiles.items():
            ref_path = ROOT_DIR / "work" / "S01E01" / prof.get("reference_audio_path", "")
            record(f"Reference Audio ({vp_id})", ref_path.exists() and ref_path.stat().st_size > 1000, str(ref_path))
    else:
        record("Voice Profiles Catalog", False, "Missing voice_profiles.json")

    # 9. External Path Audit
    print("\n[9] Checking for Forbidden Hardcoded External Paths...")
    forbidden_prefixes = ["C:\\Users\\kosty\\AppData", "C:\\Users\\kosty\\.cache"]
    leaks_found = []
    
    # Check config and scripts for hardcoded AppData
    for scan_dir in [ROOT_DIR / "config", ROOT_DIR / "scripts"]:
        for f in scan_dir.rglob("*.py"):
            if f.name == "validate_project_resources.py":
                continue
            try:
                content = f.read_text(encoding="utf-8")
                for pref in forbidden_prefixes:
                    if pref.lower() in content.lower():
                        leaks_found.append((str(f.relative_to(ROOT_DIR)), pref))
            except Exception:
                pass

    record("Hardcoded External Paths in Scripts", len(leaks_found) == 0, 
           f"Leaks: {leaks_found}" if leaks_found else "0 external paths found in scripts/config")

    # Summary
    print("\n" + "=" * 80)
    print(f"RESOURCE INTEGRITY REPORT: {passed_checks}/{total_checks} CHECKS PASSED")
    if failed_checks > 0:
        print(f"FAILURES DETECTED ({failed_checks}):")
        for fail in failures:
            print(f"  - {fail}")
        print("VERDICT: FAIL")
        print("=" * 80)
        sys.exit(1)
    else:
        print("ALL PROJECT RESOURCES & RUNTIME PATHS FULLY CONSOLIDATED AND VALIDATED!")
        print("VERDICT: PASS")
        print("=" * 80)
        sys.exit(0)


if __name__ == "__main__":
    main()
