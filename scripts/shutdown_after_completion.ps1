$targetPath = "E:\AI-Dubbing\output\wide_awake\Wide_Awake_Chapters_03_04.mp3"
$pidToWatch = 15696

Write-Host "[Shutdown Watcher] Monitoring batch_runner (PID $pidToWatch)..."

while (Get-Process -Id $pidToWatch -ErrorAction SilentlyContinue) {
    Start-Sleep -Seconds 4
}

Write-Host "[Shutdown Watcher] batch_runner exited. Waiting for ffmpeg and file sync..."
Start-Sleep -Seconds 5

$timeout = 0
while ((Get-Process -Name "ffmpeg" -ErrorAction SilentlyContinue) -and ($timeout -lt 120)) {
    Start-Sleep -Seconds 2
    $timeout += 2
}

Start-Sleep -Seconds 5

if (Test-Path $targetPath) {
    $size = (Get-Item $targetPath).Length / 1MB
    Write-Host "[Shutdown Watcher] Target ready: $targetPath ($([math]::Round($size, 2)) MB)."
    Write-Host "[Shutdown Watcher] Executing shutdown in 60s..."
    & shutdown.exe /s /t 60 /c "Wide Awake: Главы 3 и 4 успешно сгенерированы! Выключение ПК через 60 секунд. (Для отмены введите: shutdown /a)"
} else {
    Write-Host "[Shutdown Watcher] Target file not found. Aborting shutdown for safety."
}
