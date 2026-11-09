@echo off
cd /d "%~dp0"
rem Launch only if everything is installed; otherwise install what's missing first.
.venv\Scripts\python.exe -c "import anthropic, PySide6, faster_whisper, pycaw, sherpa_onnx, kokoro_onnx" 2>nul || call :setup || goto :fail
start "" .venv\Scripts\pythonw.exe main.py
exit /b

:setup
echo Installing what Vorn needs, this can take a few minutes...
rem Rebuild the environment only if it's missing or broken; otherwise just add the missing packages.
.venv\Scripts\python.exe -c "import pip" 2>nul || (if exist .venv rmdir /s /q .venv) & .venv\Scripts\python.exe -c "import pip" 2>nul || python -m venv .venv || exit /b 1
.venv\Scripts\python -m pip install -r requirements.txt || exit /b 1
exit /b 0

:fail
echo Setup failed. Make sure Python 3.12 is installed, and that this folder has a short path
echo such as E:\Claude\Vorn - Windows breaks installs in very deep folders.
pause
