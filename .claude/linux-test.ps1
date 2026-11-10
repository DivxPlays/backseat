# The kit's Linux test: runs a release the way a Linux (or Steam Deck) player's first run goes, in WSL2: a Linux build
# natively, or the Windows build under Wine (Steam Deck's Proton is Wine underneath). Every run gets a fresh home
# folder, a fresh Wine prefix and its own virtual screen (Xvfb), so nothing carries over and nothing opens on your
# desktop. The Linux itself has Wine and the test's tools on it, as a player's would have Wine or Proton.
# Usage: powershell -ExecutionPolicy Bypass -File .claude/linux-test.ps1 -Package <zip, tar, AppImage, file or folder> -Run <what a player
#          starts, e.g. RedlineLauncher.exe or redline.sh> [-Wine] [-Wait 60] [-Out build/linux-test]
#   -Wine   run it under Wine; automatic when -Run is a .exe, .bat, .cmd or .msi
#   -Setup  first time on a PC: installs Ubuntu in WSL and the test's tools (Wine, Xvfb, ImageMagick). Ask the user
#           first: it downloads about 1 GB.
# Results in -Out: result.json, shot-1/2/3.png, app.log (all it printed). Look at the screenshots: a window can be open
# and still show an error. Exit code 0 = a window is open at the end and nothing reported an error, 1 = not.
param([string]$Package, [string]$Run, [switch]$Wine, [int]$Wait = 60, [string]$Out = "build/linux-test",
      [string]$Distro = "Ubuntu-26.04", [switch]$Setup)
$ErrorActionPreference = "Stop"
$env:WSL_UTF8 = "1"
if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) { throw "no WSL on this PC: 'wsl --install' (then restart)" }

# What runs inside Linux. "setup": install the tools. "run": the test, inside xvfb-run's virtual screen.
$sh = @'
#!/bin/bash
if [ "$1" = setup ]; then
  set -e
  export DEBIAN_FRONTEND=noninteractive
  # apt tries IPv6 first, and WSL often has no IPv6 route
  echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4
  dpkg --add-architecture i386
  apt-get update -qq
  apt-get install -y -qq wine wine64 wine32:i386 xvfb x11-utils xdotool imagemagick unzip >/dev/null
  echo "ready: $(wine --version)"
  exit 0
fi
pkg=$(wslpath -a "$2"); run=$3; wait=$4; out=$(wslpath -a "$5"); wine=$6
export PATH=$PATH:/usr/lib/x86_64-linux-gnu/wine  # Ubuntu keeps wineserver off the PATH
work=$(mktemp -d /tmp/kit-linux-XXXXXX)
export HOME=$work/home
mkdir -p "$HOME" "$work/app"
unset WAYLAND_DISPLAY  # windows go to the virtual screen, not the user's desktop
case "$pkg" in
  *.zip) unzip -q "$pkg" -d "$work/app" ;;
  *.tar|*.tar.*|*.tgz) tar -xf "$pkg" -C "$work/app" ;;
  *) cp -r "$pkg" "$work/app/" ;;
esac
target=$(find "$work/app" -type f -name "$(basename "$run")" | head -n1)
: > "$out/app.log"; : > "$out/state.txt"
if [ -n "$target" ]; then
  echo found=1 >> "$out/state.txt"
  cd "$(dirname "$target")"
  if [ "$wine" = 1 ]; then
    export WINEPREFIX=$HOME/.wine WINEDEBUG=fixme-all
    # a new prefix, as on a player's first run, without the Mono and Gecko download prompts
    WINEDLLOVERRIDES="mscoree,mshtml=" wineboot --init >/dev/null 2>&1; wineserver -w
    case "$target" in
      *.bat|*.cmd) wine cmd /c "$target" ;;
      *.msi) wine msiexec /i "$target" ;;
      *) wine "$target" ;;
    esac >> "$out/app.log" 2>&1 &
  else
    chmod +x "$target"
    APPIMAGE_EXTRACT_AND_RUN=1 "$target" >> "$out/app.log" 2>&1 &  # WSL has no FUSE for AppImages
  fi
  pid=$!
  for n in 1 2 3; do sleep $((wait / 3)); import -window root "$out/shot-$n.png" 2>/dev/null; done
  if kill -0 "$pid" 2>/dev/null; then echo running=1 >> "$out/state.txt"
  else wait "$pid"; echo "exit=$?" >> "$out/state.txt"; fi
fi
for w in $(xdotool search --onlyvisible --name . 2>/dev/null); do xdotool getwindowname "$w"; done |
  grep -v '^$' | sort -u > "$out/windows.txt"
[ -n "$target" ] && kill "$pid" 2>/dev/null
[ "$wine" = 1 ] && wineserver -k 2>/dev/null
rm -rf "$work"
exit 0
'@
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("kit-linux-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Force $tmp | Out-Null
[System.IO.File]::WriteAllText((Join-Path $tmp "kit-linux.sh"), $sh.Replace("`r`n", "`n"))
$installed = { @(wsl -l -q | ForEach-Object { $_.Trim() }) -contains $Distro }

try {
  if ($Setup) {
    if (-not (& $installed)) {
      "installing $Distro in WSL..."
      wsl --install -d $Distro --no-launch
      if ($LASTEXITCODE) { throw "couldn't install $Distro" }
    }
    "installing Wine, Xvfb and ImageMagick in $Distro (about 1 GB)..."
    wsl -d $Distro -u root --cd $tmp --exec bash kit-linux.sh setup
    if ($LASTEXITCODE) { throw "the tools didn't install; read the apt errors above" }
    exit 0
  }
  if (-not $Package -or -not $Run) { throw "usage: -Package <zip or folder> -Run <what a player starts> (or -Setup)" }
  if (-not (& $installed)) { throw "$Distro isn't in WSL yet: run this with -Setup first (ask the user: it downloads about 1 GB)" }
  wsl -d $Distro -u root --exec sh -c "command -v xvfb-run && command -v import && command -v xdotool && command -v wine" | Out-Null
  if ($LASTEXITCODE) { throw "the test's tools aren't in $Distro yet: run this with -Setup first" }

  $pkg = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Package)
  if (-not (Test-Path -LiteralPath $pkg)) { throw "no package at $Package" }
  $results = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Out)
  if (Test-Path $results) { Remove-Item -Recurse -Force $results }
  New-Item -ItemType Directory -Force $results | Out-Null
  $useWine = $Wine -or $Run -match '\.(exe|bat|cmd|msi)$'

  "running $Run on Linux$(if ($useWine) { ' under Wine' }) and watching for $Wait seconds..."
  wsl -d $Distro -u root --cd $tmp --exec xvfb-run -a -s "-screen 0 1920x1080x24" bash kit-linux.sh run $pkg $Run $Wait $results $(if ($useWine) { 1 } else { 0 })
  if ($LASTEXITCODE) { throw "the test itself failed in WSL (exit $LASTEXITCODE)" }
} finally {
  Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}

$state = @{}
Get-Content (Join-Path $results "state.txt") | ForEach-Object { $k, $v = $_ -split "=", 2; $state[$k] = $v }
Remove-Item (Join-Path $results "state.txt")
# "$_": plain strings, or Windows PowerShell writes each line's file properties into the JSON
$windows = @(Get-Content (Join-Path $results "windows.txt") | Where-Object { $_ } | ForEach-Object { "$_" })
$errorWindows = @($windows | Where-Object { $_ -match "Program Error|error|exception|fatal|crash|not found|missing" })
# What a broken Linux or Wine run prints: missing libraries or DLLs, crashes, a Python traceback.
$printed = @(Get-Content (Join-Path $results "app.log") | Where-Object { $_ -match
  "error while loading shared libraries|cannot open shared object|err:module|Unhandled (exception|page fault)|segmentation fault|core dumped|command not found|: not found$|Traceback|^\s*(error|fatal)\b" } | ForEach-Object { "$_" })
$exit = if ($state.exit) { [int]$state.exit } else { $null }
[ordered]@{ run = $Run; wine = [bool]$useWine; found = [bool]$state.found; running = [bool]$state.running; exitCode = $exit;
  windows = $windows; errorWindows = $errorWindows; errorLines = @($printed | Select-Object -First 20) } |
  ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 (Join-Path $results "result.json")

$ok = $state.found -and $windows.Count -and -not $errorWindows.Count -and -not $printed.Count
"windows open at the end: $(if ($windows.Count) { $windows -join ' | ' } else { 'none' })"
if (-not $state.found) { "FAIL: $Run isn't in the package" }
elseif ($errorWindows.Count) { "FAIL: error windows: $($errorWindows -join ' | ')" }
elseif ($printed.Count) { "FAIL: it reported errors: $($printed[0].Trim())" }
elseif (-not $windows.Count) { "FAIL: nothing is on screen at the end$(if ($null -ne $exit) { "; it exited with code $exit" })" }
else { "PASS: it ran on Linux$(if ($useWine) { ' under Wine' }) with no error windows or errors" }
"look at the screenshots before trusting it: $results\shot-1.png, shot-2.png, shot-3.png (output in $results\app.log)"
exit $(if ($ok) { 0 } else { 1 })
