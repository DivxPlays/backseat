# Installs Vorn on this PC: Python 3.12 if needed, his files in %LOCALAPPDATA%\Programs\Vorn, everything he needs,
# your API key, and Start menu + desktop shortcuts. Run it through "Install Vorn.bat". Running it again updates him.
# The parameters are for testing; a normal install uses the defaults.
param(
    [string]$Dest = (Join-Path $env:LOCALAPPDATA "Programs\Vorn"),
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
    foreach ($p in "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe", "$env:ProgramFiles\Python312\python.exe") {
        if (Test-Path $p) { return $p }
    }
    return $null
}

Write-Host "Installing Vorn into $Dest" -ForegroundColor Yellow

# 1. Python 3.12
$python = Find-Python
if (-not $python) {
    Write-Host "Python 3.12 isn't installed. Installing it with winget..."
    winget install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements
    $python = Find-Python
    if (-not $python) { throw "Python 3.12 didn't install. Install it from python.org, then run this again." }
}
Write-Host "Using $python"

# 2. His program files. Your memory, settings, key and Hall of Shame are never copied or overwritten:
#    move your memory with tray > Export memory / Import memory.
if ($src -ne $Dest) {
    New-Item -ItemType Directory -Force $Dest | Out-Null
    robocopy $src $Dest /E /XD .venv .git __pycache__ "Hall of Shame" `
        /XF memory.json settings.json api_key.txt companion.log "battle reports.txt" "memory backup *.zip" /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Copying his files failed (robocopy code $LASTEXITCODE)." }
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

# 4. Your API key, kept only in api_key.txt on this PC
if (-not (Test-Path "api_key.txt")) {
    Write-Host ""
    Write-Host "Paste your Anthropic API key (console.anthropic.com > API keys) and press Enter." -ForegroundColor Yellow
    $secure = Read-Host -AsSecureString "API key"
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)).Trim()
    if ($key) { [IO.File]::WriteAllText((Join-Path $Dest "api_key.txt"), $key) }
    else { Write-Host "No key entered. Put it in $Dest\api_key.txt later." }
}

# 5. Shortcuts
$shell = New-Object -ComObject WScript.Shell
foreach ($dir in $ShortcutDirs) {
    New-Item -ItemType Directory -Force $dir | Out-Null
    $link = $shell.CreateShortcut((Join-Path $dir "Vorn.lnk"))
    $link.TargetPath = Join-Path $Dest ".venv\Scripts\pythonw.exe"
    $link.Arguments = '"' + (Join-Path $Dest "main.py") + '"'
    $link.WorkingDirectory = $Dest
    $link.IconLocation = Join-Path $Dest "vorn.ico"
    $link.Description = "Vorn, your trash-talking gaming companion"
    $link.Save()
}

Write-Host ""
Write-Host "Vorn is installed. Start him from the Start menu or the desktop shortcut." -ForegroundColor Green
if (-not $NoLaunch) { Start-Process (Join-Path $Dest ".venv\Scripts\pythonw.exe") -ArgumentList ('"' + (Join-Path $Dest "main.py") + '"') -WorkingDirectory $Dest }
