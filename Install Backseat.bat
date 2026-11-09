@echo off
rem Double-click to install Backseat on this PC (or update it). Everything happens in install.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 echo. & echo Install failed: see the message above.
pause
