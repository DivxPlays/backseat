"""Auto-update: once a day, check GitHub (DivxPlays/backseat, public) for a newer version. On your OK, download it and hand
over to its own installer, which waits for this copy to quit, copies the new files over this install (your memory,
settings, key, Hall of Shame and characters stay as they are), updates what it needs, and starts the new version.
A git clone (where Backseat is developed) isn't touched: update that with git."""
import os
import re
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO = "DivxPlays/backseat"
RAW = f"https://raw.githubusercontent.com/{REPO}/main/main.py"
ZIP = f"https://github.com/{REPO}/archive/refs/heads/main.zip"
VERSION = re.compile(r'APP, VERSION, AUTHOR = "[^"]*", "(\d+\.\d+\.\d+)"')
HEADERS = {"User-Agent": "Backseat updater"}


def numbers(version):
    return tuple(int(x) for x in version.split("."))


def latest(timeout=10):
    """The version on GitHub (read from its main.py), or None (offline, or GitHub unreachable)."""
    try:
        with urllib.request.urlopen(urllib.request.Request(RAW, headers=HEADERS), timeout=timeout) as r:
            m = VERSION.search(r.read().decode("utf-8", "replace"))
    except OSError:
        return None
    return m.group(1) if m else None


def newer(remote, local):
    """True when `remote` ("2.0.1") is a later version than `local`."""
    return remote is not None and numbers(remote) > numbers(local)


def dev_copy(here):
    """A git clone: updated with git, never by the installer."""
    return (Path(here) / ".git").exists()


def update(here, pid=None, timeout=60):
    """Download the newest version, unpack it in a temporary folder and start its installer, which waits for this copy
    (pid) to quit, then installs into `here` and starts it. Returns the unpacked folder."""
    tmp = Path(tempfile.mkdtemp(prefix="backseat-update-"))
    with urllib.request.urlopen(urllib.request.Request(ZIP, headers=HEADERS), timeout=timeout) as r:
        (tmp / "backseat.zip").write_bytes(r.read())
    with zipfile.ZipFile(tmp / "backseat.zip") as z:
        for name in z.namelist():  # (nothing may land outside the folder)
            if not (tmp / name).resolve().is_relative_to(tmp.resolve()):
                raise ValueError(f"unsafe path in the download: {name}")
        z.extractall(tmp)
    src = next(p for p in tmp.iterdir() if p.is_dir() and (p / "install.ps1").exists())
    script = (f"Wait-Process -Id {pid or os.getpid()} -ErrorAction SilentlyContinue; "
              f"& '{src / 'install.ps1'}' -Dest '{Path(here).resolve()}'")
    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                     creationflags=subprocess.CREATE_NEW_CONSOLE)  # (a window: you see it update)
    return src
