# Installs Backseat on this PC: Python 3.12 if needed, its files in %LOCALAPPDATA%\Programs\Backseat, everything it needs,
# your API key, and Start menu + desktop shortcuts. Install-Backseat.exe (installer.iss) and "Install Backseat.bat" run
# it, and so does auto-update (updater.py). Running it again updates it.
# The parameters are for testing; a normal install uses the defaults.
param(
    [string]$Dest = (Join-Path $env:LOCALAPPDATA "Programs\Backseat"),
    [string]$Old = (Join-Path $env:LOCALAPPDATA "Programs\Vorn"),  # where it lived when the app was called Vorn
    [string[]]$ShortcutDirs = @([Environment]::GetFolderPath("Programs"), [Environment]::GetFolderPath("Desktop")),
    [switch]$NoLaunch
)
$ErrorActionPreference = "Stop"
$src = (Resolve-Path $PSScriptRoot).Path

function Find-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $exe = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
    }
    foreach ($p in "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe", "$env:ProgramFiles\Python312\python.exe", "$Dest\python\python.exe") {
        if (Test-Path $p) { return $p }
    }
    return $null
}

Write-Host "Installing Backseat into $Dest" -ForegroundColor Yellow

# 0. Installed back when the app was called Vorn: move it over (memory, settings, key and all) and tidy up after it
if ((Test-Path $Old) -and -not (Test-Path $Dest)) {
    Write-Host "Moving your Vorn install (memory, settings and key included) to $Dest"
    Move-Item $Old $Dest
}
$run = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"  # (Install-Backseat.exe moves the folder itself, before this runs)
$boot = (Get-ItemProperty $run -ErrorAction SilentlyContinue).VornCompanion
if ($boot) {
    Set-ItemProperty $run BackseatCompanion ($boot.Replace($Old, $Dest))
    Remove-ItemProperty $run VornCompanion
}
foreach ($dir in $ShortcutDirs) { Remove-Item (Join-Path $dir "Vorn.lnk") -ErrorAction SilentlyContinue }

# 1. Python 3.12
$python = Find-Python
if (-not $python) {
    # Python's own zip (its NuGet package), unpacked into Backseat's folder: a fresh Windows has no winget yet, and the
    # python.org setup program took 15+ minutes there. The hash pins that exact file.
    Write-Host "Python 3.12 isn't installed. Downloading it (15 MB) into Backseat's folder..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $zip = Join-Path $env:TEMP "python-3.12.10.nupkg"
    $ProgressPreference = "SilentlyContinue"  # Windows PowerShell's progress bar makes downloads many times slower
    Invoke-WebRequest "https://www.nuget.org/api/v2/package/python/3.12.10" -OutFile $zip -UseBasicParsing
    if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne "0EB85C2DFCCCCF1B17352DE4C397F69194035B7D37149EACC16F1147D93DE3B8") {
        Remove-Item $zip
        throw "The Python download was damaged. Run this again."
    }
    $unpacked = Join-Path $env:TEMP ("python-" + [guid]::NewGuid())
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::ExtractToDirectory($zip, $unpacked)
    New-Item -ItemType Directory -Force $Dest | Out-Null
    Move-Item (Join-Path $unpacked "tools") (Join-Path $Dest "python")
    Remove-Item $zip, $unpacked -Recurse -ErrorAction SilentlyContinue
    $python = Find-Python
    if (-not $python) { throw "Python 3.12 didn't install. Install it from python.org, then run this again." }
}
Write-Host "Using $python"

# 2. His program files. Your memory, settings, key and Hall of Shame are never copied or overwritten:
#    move your memory with tray > Export memory / Import memory.
if ($src -ne $Dest) {
    New-Item -ItemType Directory -Force $Dest | Out-Null
    robocopy $src $Dest /E /XD .venv .git __pycache__ "Hall of Shame" presets `
        /XF memory.json settings.json api_key.txt companion.log "battle reports.txt" "memory backup *.zip" /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Copying his files failed (robocopy code $LASTEXITCODE)." }
    # characters: only ones this PC doesn't have yet (an update must not undo your Settings > Character changes)
    robocopy (Join-Path $src "presets") (Join-Path $Dest "presets") *.json /XC /XN /XO /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Copying the characters failed (robocopy code $LASTEXITCODE)." }
}
Get-ChildItem $Dest -Recurse -File -ErrorAction SilentlyContinue | Unblock-File  # files from a downloaded ZIP are marked as "from the internet"
Set-Location $Dest

# 3. Everything he needs (the first time takes a few minutes)
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Couldn't create his Python environment." }
}
& .venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Installing what he needs failed. Check your internet connection and run this again." }

# 4. Your API key, kept only in api_key.txt on this PC, checked with one tiny call (a hundred-thousandth of a dollar)
while (-not (Test-Path "api_key.txt")) {
    Write-Host ""
    Write-Host "Paste your Anthropic API key (console.anthropic.com > API keys) and press Enter." -ForegroundColor Yellow
    $secure = Read-Host -AsSecureString "API key"
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)).Trim()
    if (-not $key) { Write-Host "No key entered. Put it in $Dest\api_key.txt later."; break }
    [IO.File]::WriteAllText((Join-Path $Dest "api_key.txt"), $key)
    $why = & .venv\Scripts\python.exe -c "import sys, brain; why, again = brain.key_problem(brain.make_client()); print(why); sys.exit(3 if again else 0)"
    if ($LASTEXITCODE -eq 3) { Write-Host $why -ForegroundColor Red; Remove-Item "api_key.txt" }  # asks again
    elseif ($LASTEXITCODE -ne 0) { Write-Host "Couldn't check the key. It's saved: Backseat says so if it doesn't work." }
    elseif ($why) { Write-Host $why -ForegroundColor Yellow }
    else { Write-Host "Key checked: it works." -ForegroundColor Green }
}

# 5. Shortcuts
$shell = New-Object -ComObject WScript.Shell
foreach ($dir in $ShortcutDirs) {
    New-Item -ItemType Directory -Force $dir | Out-Null
    $link = $shell.CreateShortcut((Join-Path $dir "Backseat.lnk"))
    $link.TargetPath = Join-Path $Dest ".venv\Scripts\pythonw.exe"
    $link.Arguments = '"' + (Join-Path $Dest "main.py") + '"'
    $link.WorkingDirectory = $Dest
    $link.IconLocation = Join-Path $Dest "vorn.ico"
    $link.Description = "Backseat: Vorn and Mika, your trash-talking gaming companions"
    $link.Save()
}

# 6. Installed with Install-Backseat.exe: Windows Settings > Apps shows the version an auto-update brought (installer.iss's AppId)
$apps = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{9CFB28A7-8A68-4EAF-AA77-952507EC47E8}_is1"
$version = [regex]::Match((Get-Content (Join-Path $Dest "main.py") -Raw), '"Backseat", "([\d.]+)"').Groups[1].Value
if ((Test-Path $apps) -and $version) { Set-ItemProperty $apps DisplayVersion $version }

Write-Host ""
Write-Host "Backseat is installed. Start it from the Start menu or the desktop shortcut." -ForegroundColor Green
if (-not $NoLaunch) { Start-Process (Join-Path $Dest ".venv\Scripts\pythonw.exe") -ArgumentList ('"' + (Join-Path $Dest "main.py") + '"') -WorkingDirectory $Dest }
