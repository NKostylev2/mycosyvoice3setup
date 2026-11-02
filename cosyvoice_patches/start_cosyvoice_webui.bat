@echo off
chcp 65001 >nul
echo ========================================================
echo        Запуск WebUI CosyVoice 3 (Fun-CosyVoice3-0.5B)
echo ========================================================
echo.
echo Порт: http://localhost:50000
echo.

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

set "PYTHON=E:\AI-Dubbing\cosyvoice_env\python.exe"
set "PYTHONPATH=%ROOT_DIR%;%ROOT_DIR%\third_party\Matcha-TTS"

"%PYTHON%" webui.py --port 50000 --model_dir "%ROOT_DIR%pretrained_models\Fun-CosyVoice3-0.5B"

pause
