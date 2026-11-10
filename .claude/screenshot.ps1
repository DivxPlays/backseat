# The kit's screenshot tool: saves a PNG of a program's window, for the README's pictures (docs/images/).
# Usage: powershell -File .claude/screenshot.ps1 -Out docs/images/menu.png (-Process name | -Title "part of the title") [-Wide169]
#   -Process  the process name without .exe (e.g. stilwater); -Title matches part of the window title instead
#   -Wide169  keep only the middle 16:9 of a wider window (an ultrawide's side bars, where a game draws nothing)
# Look at every picture before committing it: no names, chat, file paths or other people, and default settings.
param([Parameter(Mandatory)][string]$Out, [string]$Process = "", [string]$Title = "", [switch]$Wide169)
$ErrorActionPreference = "Stop"  # a failed save must not still print "saved"
if (-not $Process -and -not $Title) { throw "give -Process or -Title" }
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class KitShot {
  [StructLayout(LayoutKind.Sequential)] public struct R { public int L, T, Ri, B; }
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out R r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref System.Drawing.Point p);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr ctx);
}
"@ -ReferencedAssemblies System.Drawing
# Real pixels on every monitor, even when they're scaled differently (per-monitor aware; -4 = PER_MONITOR_AWARE_V2).
# Only system-aware, a window on a monitor scaled unlike the main one is looked for in the wrong place.
if ([KitShot]::SetThreadDpiAwarenessContext([IntPtr]::new(-4)) -eq [IntPtr]::Zero) { [KitShot]::SetProcessDPIAware() | Out-Null }

$windows = Get-Process | Where-Object { $_.MainWindowHandle -ne 0 }
$p = if ($Process) { $windows | Where-Object { $_.ProcessName -eq $Process } | Select-Object -First 1 }
     else { $windows | Where-Object { $_.MainWindowTitle -like "*$Title*" } | Select-Object -First 1 }
if (-not $p) { throw "no window for $(if ($Process) { "process '$Process'" } else { "title '$Title'" })" }
$h = $p.MainWindowHandle
if ([KitShot]::IsIconic($h)) { [KitShot]::ShowWindow($h, 9) | Out-Null }  # 9 = restore a minimised window
[KitShot]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 400  # let it come to the front and redraw

$r = New-Object KitShot+R; [KitShot]::GetClientRect($h, [ref]$r) | Out-Null
$pt = New-Object System.Drawing.Point 0, 0; [KitShot]::ClientToScreen($h, [ref]$pt) | Out-Null
$w = $r.Ri - $r.L; $hgt = $r.B - $r.T
if ($w -le 0 -or $hgt -le 0) { throw "the window has no visible area" }
$x = 0
if ($Wide169 -and $w * 9 -gt $hgt * 16) { $x = [int](($w - $hgt * 16 / 9) / 2); $w = [int]($hgt * 16 / 9) }
$bmp = New-Object System.Drawing.Bitmap $w, $hgt
$g = [System.Drawing.Graphics]::FromImage($bmp)
# Copied from the screen, not PrintWindow: games drawn with DirectX or Vulkan come out black through PrintWindow.
$g.CopyFromScreen((New-Object System.Drawing.Point ($pt.X + $x), $pt.Y), [System.Drawing.Point]::Empty, $bmp.Size)
$g.Dispose()
$full = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Out)  # relative or absolute
[System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($full)) | Out-Null
$bmp.Save($full, [System.Drawing.Imaging.ImageFormat]::Png)
"saved $Out ($($bmp.Width)x$($bmp.Height)). Look at it before committing: no names, chat, paths or other people."
$bmp.Dispose()
