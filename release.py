"""Publish the current version as a GitHub release, after its version bump and CHANGELOG.md entry are committed and the
commit is tagged v<version> with only the tag pushed (the branch goes after):  .venv\\Scripts\\python release.py publish
Its notes are how to install plus the version's CHANGELOG.md entry. It attaches Backseat.zip (the app with its installer
inside; what auto-update downloads) and Install-Backseat.bat (the one-file installer: on its own it downloads the latest
Backseat.zip itself)."""
import re
import shutil
import subprocess
import sys
from pathlib import Path

from updater import STAGE, VERSION, pretty

GH = r"C:\Program Files\GitHub CLI\gh.exe"
HERE = Path(__file__).parent


def run(*args):
    return subprocess.run(args, cwd=HERE, check=True, capture_output=True, text=True).stdout.strip()


def full_version(main_py):
    """ "2.0.0-beta" from a main.py's VERSION and STAGE (a release has no stage in it)."""
    version, stage = VERSION.search(main_py).group(1), STAGE.search(main_py).group(1)
    return version if stage == "release" else f"{version}-{stage}"


INSTALL = ("## Install\n\nDownload **Install-Backseat.bat** below and double-click it: it downloads the rest itself. Or download "
           "**Backseat.zip**, extract it and double-click **Install Backseat.bat** inside. You need an Anthropic API key "
           "(console.anthropic.com); the installer asks for it. If Windows says the file came from the internet, click **More "
           "info > Run anyway**.\n\n"
           "## Updating\n\n"
           "- **On 2.0.0 or newer:** Backseat checks GitHub for a new version once a day when it starts. When one is out, "
           "Windows shows a notification and the tray icon's menu (right-click the icon by the clock) shows **Update to "
           "x.y.z**: click it and say Yes. It closes, updates in a window you can watch and starts again. Your memory, "
           "settings, API key, Hall of Shame and characters stay as they are. To check any time: right-click the tray icon > "
           "**Check for updates...**\n"
           "- **On 1.x, or not sure:** download **Install-Backseat.bat** below and double-click it. It updates your install "
           "in place and keeps all of the above.\n"
           "- **No update offered?** Settings > Brain & budget > Updates must be on. A copy made with `git clone` updates "
           "with `git pull` instead.\n\n"
           "Problems: [Issues](https://github.com/DivxPlays/backseat/issues).\n\n")


def changelog(version, text):
    """The CHANGELOG.md entry for a version ("2.0.0-beta": the "## 2.0.0 Beta (date)" section), or None."""
    m = re.search(rf"^## {re.escape(pretty(version))} \(.*?\)\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else None


def build():
    """dist/Backseat.zip (the committed files, in a Backseat folder) and dist/Install-Backseat.bat; returns the version."""
    version = full_version((HERE / "main.py").read_text(encoding="utf-8"))
    if run("git", "status", "--porcelain", "--untracked-files=no"):
        sys.exit("Commit your changes first: the release is made from what's committed.")
    dist = HERE / "dist"
    dist.mkdir(exist_ok=True)
    run("git", "archive", "--format=zip", "--prefix=Backseat/", "-o", str(dist / "Backseat.zip"), "HEAD")
    shutil.copy(HERE / "Install Backseat.bat", dist / "Install-Backseat.bat")
    return version


def publish():
    version = build()
    entry = changelog(version, (HERE / "CHANGELOG.md").read_text(encoding="utf-8"))
    if not entry:
        sys.exit(f"Add a CHANGELOG.md entry for {pretty(version)} first (## {pretty(version)} (date)).")
    notes = HERE / "dist" / "notes.md"
    notes.write_text(INSTALL + "## Changelog\n\n" + entry + "\n", encoding="utf-8")
    # the release goes out before the branch (README.md on GitHub only describes released versions): its tag, pushed
    # alone, must be this commit (an annotated tag lists the commit it points to as "<sha> refs/tags/v...^{}")
    if run("git", "rev-parse", "HEAD") not in run("git", "ls-remote", "--tags", "origin", f"v{version}").split():
        sys.exit(f"Tag this commit and push only the tag first: git tag -a v{version} -m {version}, then push refs/tags/v{version}.")
    trailer = HERE / "dist" / "trailer.mp4"  # (a feature release re-renders it first; a hotfix keeps the last one)
    if not trailer.exists():  # the last release's, so the README's link to the latest release's trailer keeps working
        subprocess.run([GH, "release", "download", "--repo", "DivxPlays/backseat", "--pattern", "trailer.mp4", "--dir",
                        str(trailer.parent)], cwd=HERE, capture_output=True)
    files = [str(HERE / "dist" / "Backseat.zip"), str(HERE / "dist" / "Install-Backseat.bat")] + ([str(trailer)] if trailer.exists() else [])
    run(GH, "release", "create", f"v{version}", *files,
        "--title", f"Backseat {pretty(version)}", "--notes-file", str(notes), "--target", run("git", "rev-parse", "HEAD"), "--latest")
    print(f"released v{version}")


if __name__ == "__main__":
    publish() if sys.argv[1:] == ["publish"] else print(f"built {build()} in dist/ (release.py publish to release it)")
