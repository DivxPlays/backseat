"""Publish the current version as a GitHub release, after its version bump is committed and pushed:
    .venv\\Scripts\\python release.py notes.md
It attaches Backseat.zip (the app with its installer inside; what auto-update downloads) and Install-Backseat.bat (the
one-file installer: on its own it downloads the latest Backseat.zip itself)."""
import shutil
import subprocess
import sys
from pathlib import Path

from updater import VERSION

GH = r"C:\Program Files\GitHub CLI\gh.exe"
HERE = Path(__file__).parent


def run(*args):
    return subprocess.run(args, cwd=HERE, check=True, capture_output=True, text=True).stdout.strip()


def build():
    """dist/Backseat.zip (the committed files, in a Backseat folder) and dist/Install-Backseat.bat; returns the version."""
    version = VERSION.search((HERE / "main.py").read_text(encoding="utf-8")).group(1)
    if run("git", "status", "--porcelain", "--untracked-files=no"):
        sys.exit("Commit your changes first: the release is made from what's committed.")
    dist = HERE / "dist"
    dist.mkdir(exist_ok=True)
    run("git", "archive", "--format=zip", "--prefix=Backseat/", "-o", str(dist / "Backseat.zip"), "HEAD")
    shutil.copy(HERE / "Install Backseat.bat", dist / "Install-Backseat.bat")
    return version


def publish(notes):
    version = build()
    run("git", "fetch", "-q", "origin")
    if run("git", "rev-parse", "HEAD") != run("git", "rev-parse", "origin/main"):
        sys.exit("Push first: GitHub's main must be this commit.")
    run(GH, "release", "create", f"v{version}", str(HERE / "dist" / "Backseat.zip"), str(HERE / "dist" / "Install-Backseat.bat"),
        "--title", f"Backseat {version}", "--notes-file", notes, "--target", run("git", "rev-parse", "HEAD"), "--latest")
    print(f"released v{version}")


if __name__ == "__main__":
    publish(sys.argv[1]) if len(sys.argv) > 1 else print(f"built {build()} in dist/ (pass a notes file to publish)")
