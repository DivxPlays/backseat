"""Accurate stats: real kills, deaths and wins from Steam for games that publish stats (CS2, TF2, Left 4 Dead 2 and
others), read with your own Steam Web API key (Settings) from your own profile. Steam updates them when a match or round
ends, so they're polled every few minutes while such a game is in front, and this session's change is what counts."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import winreg
from pathlib import Path

API = "https://api.steampowered.com/ISteamUserStats/GetUserStatsForGame/v2/"
BASE = 76561197960265728  # SteamID64 = this + the account number (the userdata folder's name)
SKIP = re.compile(r"max|best|most|longest|record|streak|highest|fastest", re.I)  # one-match records, not running totals
KINDS = {"kills": re.compile(r"kill(?!ed)", re.I), "deaths": re.compile(r"death|killed|died", re.I),
         "wins": re.compile(r"win|won", re.I)}


def steam_id(root=None):
    """Your SteamID64: the Steam account used last on this PC (its userdata folder), or None."""
    try:
        if root is None:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
                root = winreg.QueryValueEx(k, "SteamPath")[0]
        newest = max(Path(root).glob("userdata/*/config/localconfig.vdf"), key=lambda p: p.stat().st_mtime)
        return str(BASE + int(newest.parent.parent.name))
    except (OSError, ValueError):
        return None


def fetch(key, steamid, appid, timeout=10):
    """{stat name: value} for a game; {} when it has no stats. PermissionError: a wrong key or a private profile."""
    url = API + "?" + urllib.parse.urlencode({"appid": appid, "key": key, "steamid": steamid})
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise PermissionError(f"Steam said {e.code}") from None
        return {}  # (400/500: a game without stats)
    return {s["name"]: s["value"] for s in data.get("playerstats", {}).get("stats", []) if isinstance(s.get("value"), (int, float))}


def change(before, after):
    """{"kills", "deaths", "wins"} gained between two readings of a game's stats. Names differ per game and some games
    keep subsets (kills per weapon) beside the total, so each is the biggest rise among the running totals that name it."""
    out = {}
    for kind, pattern in KINDS.items():
        rises = [after[n] - before.get(n, 0) for n in after if pattern.search(n) and not SKIP.search(n)]
        out[kind] = max([int(r) for r in rises if r > 0], default=0)
    return out
