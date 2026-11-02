import time
import os
import subprocess
import psutil

TARGET_CMD = "batch_runner"
COMBINED_MP3 = r"E:\AI-Dubbing\output\wide_awake\Wide_Awake_Chapters_03_04.mp3"

print("[Shutdown Watcher] Starting monitor for batch_runner completion...")

# Wait until batch_runner process is finished
while True:
    running = False
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = " ".join(p.info['cmdline'] or [])
            if TARGET_CMD in cmd and "shutdown_after_completion" not in cmd:
                running = True
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not running:
        print("[Shutdown Watcher] batch_runner is no longer running.")
        break

    time.sleep(5)

# Wait an additional 5 seconds to allow file handles to close
time.sleep(5)

# Verify the combined file exists
if os.path.exists(COMBINED_MP3) and os.path.getsize(COMBINED_MP3) > 1024 * 1024 * 10:
    size_mb = os.path.getsize(COMBINED_MP3) / (1024 * 1024)
    print(f"[Shutdown Watcher] File verified: {COMBINED_MP3} ({size_mb:.2f} MB).")
    print("[Shutdown Watcher] Triggering PC shutdown in 60 seconds...")
    subprocess.run(["shutdown", "/s", "/t", "60", "/c", "Wide Awake: Главы 3 и 4 готовы! Выключение компьютера через 60 секунд. (Для отмены: shutdown /a)"])
else:
    print(f"[Shutdown Watcher] Warning: output file not found or too small. Shutdown aborted for safety.")
