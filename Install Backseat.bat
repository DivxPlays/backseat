@echo off
rem Double-click to install Backseat on this PC (or update it). Everything happens in install.ps1.
rem Next to Backseat's files it installs those; on its own (downloaded from the GitHub release page) it first downloads
rem the latest release (Backseat.zip) into a temporary folder and installs from there.
if exist "%~dp0install.ps1" goto here
echo Downloading the latest Backseat from GitHub...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; [Net.ServicePointManager]::SecurityProtocol = 'Tls12'; $t = Join-Path $env:TEMP ('backseat-' + [guid]::NewGuid()); New-Item -ItemType Directory $t | Out-Null; Invoke-WebRequest 'https://github.com/DivxPlays/backseat/releases/latest/download/Backseat.zip' -OutFile (Join-Path $t 'Backseat.zip') -UseBasicParsing; Expand-Archive (Join-Path $t 'Backseat.zip') $t; & (Get-ChildItem $t -Recurse -Filter install.ps1 | Select-Object -First 1).FullName"
goto done
:here
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
:done
if errorlevel 1 echo. & echo Install failed: see the message above.
pause
