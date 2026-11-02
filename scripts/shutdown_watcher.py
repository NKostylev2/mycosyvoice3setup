import os
import sys
import time
import subprocess

PID_TO_WATCH = "15696"
TARGET_FILE = r"E:\AI-Dubbing\output\wide_awake\Wide_Awake_Chapters_03_04.mp3"

def is_pid_running(pid_str):
    res = subprocess.run(["tasklist", "/FI", f"PID eq {pid_str}"], capture_output=True, text=True)
    return pid_str in res.stdout

print(f"[Shutdown Watcher] Monitoring batch_runner (PID {PID_TO_WATCH})...")

while is_pid_running(PID_TO_WATCH):
    time.sleep(5)

print("[Shutdown Watcher] Batch runner exited. Waiting for ffmpeg and file sync...")
time.sleep(5)

timeout = 0
while timeout < 120:
    res = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ffmpeg.exe"], capture_output=True, text=True)
    if "ffmpeg.exe" in res.stdout:
        time.sleep(3)
        timeout += 3
    else:
        break

time.sleep(5)

if os.path.exists(TARGET_FILE) and os.path.getsize(TARGET_FILE) > 10 * 1024 * 1024:
    size_mb = os.path.getsize(TARGET_FILE) / (1024 * 1024)
    print(f"[Shutdown Watcher] Target confirmed: {TARGET_FILE} ({size_mb:.2f} MB).")
    print("[Shutdown Watcher] Triggering PC shutdown in 60s...")
    subprocess.run([
        "shutdown", "/s", "/t", "60",
        "/c", "Wide Awake: Glavy 3 i 4 uspeshno sgenerirovany! Vyklyuchenie PK cherez 60s. Dlya otmeny: shutdown /a"
    ])
else:
    print("[Shutdown Watcher] Target file missing or incomplete. Aborting shutdown for safety.")
