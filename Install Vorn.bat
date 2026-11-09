@echo off
rem Double-click to install Vorn on this PC (or update him). Everything happens in install.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 echo. & echo Install failed: see the message above.
pause
