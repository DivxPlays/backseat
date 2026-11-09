"""Move his memory between PCs: one .zip with memory.json, the battle reports and the Hall of Shame."""
import json
import zipfile
from datetime import datetime
from pathlib import Path

FILES = ("memory.json", "battle reports.txt")
HALL = "Hall of Shame"


def export_memory(here, zip_path):
    here = Path(here)
    hall = here / HALL
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            if (here / name).exists():
                z.write(here / name, name)
        for f in sorted(hall.rglob("*")) if hall.is_dir() else []:
            if f.is_file():
                z.write(f, f.relative_to(here).as_posix())
    return Path(zip_path)


def import_memory(here, zip_path):
    """Replace his memory with the export in zip_path. The current memory is backed up first; returns the backup's path."""
    here = Path(here)
    hall = (here / HALL).resolve()
    with zipfile.ZipFile(zip_path) as z:
        if "memory.json" not in z.namelist() or not isinstance(json.loads(z.read("memory.json")), dict):
            raise ValueError("there's no memory.json from him in it")
        wanted = []
        for name in z.namelist():  # only his own files, and nothing that escapes the Hall of Shame folder
            target = (here / name).resolve()
            if not name.endswith("/") and (name in FILES or target.is_relative_to(hall)):
                wanted.append((name, target))
        backup = export_memory(here, here / f"memory backup {datetime.now():%Y-%m-%d %H%M%S}.zip")
        for name, target in wanted:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(name))
    return backup
