"""Auto-update: once a day, check GitHub (DivxPlays/backseat, public) for a newer release. On your OK, download it and hand
over to its own installer, which waits for this copy to quit, copies the new files over this install (your memory,
settings, key, Hall of Shame and characters stay as they are), updates what it needs, and starts the new version.
A git clone (where Backseat is developed) isn't touched: update that with git."""
import json
import os
import re
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO = "DivxPlays/backseat"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
ZIP = f"https://github.com/{REPO}/releases/latest/download/Backseat.zip"  # (release.py names the app's ZIP this)
VERSION = re.compile(r'APP, VERSION, AUTHOR = "[^"]*", "(\d+\.\d+\.\d+)"')  # the version in a main.py
STAGE = re.compile(r'^STAGE = "([a-z-]+)"', re.M)  # and its stage
STAGES = ("pre-alpha", "alpha", "pre-beta", "beta", "release")  # how finished a version is, least to most
TAG = re.compile(r"v?(\d+)\.(\d+)\.(\d+)(?:-(pre-alpha|alpha|pre-beta|beta))?")  # "v2.0.0-beta"; no stage: a release
HEADERS = {"User-Agent": "Backseat updater"}


def order(version):
    """ "2.0.0-beta" -> ((2, 0, 0), 2): numbers first, then the stage (a beta comes before its release)."""
    m = TAG.fullmatch(version)
    return tuple(int(x) for x in m.groups()[:3]), STAGES.index(m.group(4) or "release")


def pretty(version):
    """ "2.0.0-beta" -> "2.0.0 Beta"; "2.0.0" (a release) stays "2.0.0"."""
    m = TAG.fullmatch(version)
    return ".".join(m.groups()[:3]) + (f" {m.group(4).title()}" if m.group(4) else "")


def latest(timeout=10):
    """The newest released version ("2.0.0-beta", from the latest GitHub release's tag "v2.0.0-beta"), or None (offline,
    GitHub unreachable, or no release yet)."""
    try:
        with urllib.request.urlopen(urllib.request.Request(API, headers={**HEADERS, "Accept": "application/vnd.github+json"}),
                                    timeout=timeout) as r:
            tag = json.loads(r.read().decode("utf-8", "replace")).get("tag_name") or ""
    except (OSError, ValueError, AttributeError):
        return None
    return tag.removeprefix("v") if TAG.fullmatch(tag) else None


def newer(remote, local):
    """True when `remote` ("2.0.1", "2.1.0-alpha") is a later version than `local` (the same number's release is later
    than its beta)."""
    return remote is not None and order(remote) > order(local)


def dev_copy(here):
    """A git clone: updated with git, never by the installer."""
    return (Path(here) / ".git").exists()


def update(here, pid=None, timeout=60):
    """Download the newest release, unpack it in a temporary folder and start its installer, which waits for this copy
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
