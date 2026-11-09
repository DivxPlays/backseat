"""Long-term memory (memory.json): play time (incl. Steam lifetime hours), score, respect, notes, battle reports."""
import ctypes
import json
import os
import re
import threading
from ctypes import wintypes
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import config

FILE = Path(__file__).with_name("memory.json")
MAX_NOTES, MAX_GAME_NOTES, MAX_SESSIONS, MAX_DAYS, MAX_LINES = 40, 20, 20, 30, 30
MAX_PINNED, SHOW_PINNED, CONDENSE = 500, 40, 20  # pinned facts kept / sent per message; old notes folded into the profile at once
STOP = {"the", "a", "an", "my", "i", "is", "it", "to", "of", "and", "in", "on", "what", "you", "me", "do", "that", "how", "for"}
COUNTED = {"death": "deaths", "win": "wins", "loss": "losses", "fail": "fails", "epic": "epic plays"}  # events he keeps score of


def fmt(seconds):
    return f"{seconds / 3600:.1f} h" if seconds >= 3600 else f"{seconds / 60:.0f} min"


def tally(events):
    return ", ".join(f"{n} {COUNTED[e] if n != 1 else e}" for e, n in events.items()) or "nothing yet"


def time_mood(now):
    """His mood by the clock."""
    h = now.hour
    mood = ("grumpy and short-tempered: it's morning and you despise mornings" if 5 <= h < 12 else
            "sharp, cold and tactical" if 12 <= h < 18 else
            "hyped, loud and competitive: prime battle hours" if 18 <= h < 23 else
            "unhinged and theatrical: no sane warrior is awake at this hour")
    return mood + ("; it's the weekend, so extra smug" if now.weekday() >= 5 else "")


def month():
    return date.today().strftime("%Y-%m")


MINE = ("respect", "lore", "notes", "pinned", "profile", "games", "friends", "sessions", "hall")  # per character; time and spend are shared


def fresh_mind():
    """What a character remembers before meeting you."""
    return {"respect": 10, "lore": [], "notes": [], "pinned": [], "profile": "", "games": {}, "friends": {}, "sessions": [], "hall": []}


def pick_pinned(pinned, query):
    """The pinned facts for one message: all of them while there are few, otherwise the ones sharing words with
    `query` (what was said, the game) plus the most recent, so any number can be stored without every call costing more."""
    if len(pinned) <= SHOW_PINNED:
        return pinned
    words = set(re.findall(r"[a-z0-9']+", query.lower())) - STOP
    hits = sorted(((len(words & set(re.findall(r"[a-z0-9']+", p.lower()))), i) for i, p in enumerate(pinned)), reverse=True)
    pick = {i for n, i in hits[:SHOW_PINNED - 10] if n} | set(range(len(pinned) - 10, len(pinned)))
    return [pinned[i] for i in sorted(pick)]


def app_name(exe, title):
    return Path(exe).name.lower() if exe else (title or "unknown")


class Memory:
    def __init__(self, path=FILE):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.frozen = False  # True after importing another PC's memory: nothing may save over it before the restart
        try:
            self.d = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.d = {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.path.replace(self.path.with_suffix(".corrupt.json"))  # keep the damaged file, start fresh
            self.d = {}
        for key, empty in (("total_seconds", 0), ("session_count", 0), ("apps", {}), ("games", {}), ("notes", []),
                           ("sessions", []), ("days", {}), ("respect", 10), ("lore", []), ("spend", {}),
                           ("spend_days", {}), ("spend_level", {}), ("hall", []), ("pinned", []), ("profile", ""), ("friends", {})):
            self.d.setdefault(key, empty)
        self.d["session_count"] += 1
        active = self.d.get("character", "vorn")  # each character keeps their own memory of you (MINE); the rest is shared
        if active != config.PRESET:
            saved = self.d.setdefault("characters", {})
            saved[active] = {k: self.d[k] for k in MINE}
            mine = {**fresh_mind(), **saved.pop(config.PRESET, {})}
            self.d.update({k: mine[k] for k in MINE}, character=config.PRESET)
        self.session = {"start": datetime.now().isoformat(timespec="minutes"), "seconds": 0, "apps": {}, "events": {}, "lines": []}
        self.d["sessions"] = self.d["sessions"][-(MAX_SESSIONS - 1):] + [self.session]

    def tick(self, app, dt):
        with self.lock:
            d, s = self.d, self.session
            d["total_seconds"] += dt
            s["seconds"] += dt
            d["apps"][app] = d["apps"].get(app, 0) + dt
            s["apps"][app] = s["apps"].get(app, 0) + dt
            today = date.today().isoformat()
            d["days"][today] = d["days"].get(today, 0) + dt
            for old in sorted(d["days"])[:-MAX_DAYS]:
                del d["days"][old]

    def pin(self, fact):
        """Something the player asked to be remembered: kept for good (never pushed out like notes).
        Returns False when all MAX_PINNED slots are taken: nothing old is dropped to make room."""
        fact = fact.strip().rstrip(".")
        with self.lock:
            if not fact or fact.lower() in (p.lower() for p in self.d["pinned"]):
                return True  # nothing new to add
            if len(self.d["pinned"]) >= MAX_PINNED:
                return False
            self.d["pinned"].append(fact)  # context() sends only the relevant ones, so the cost stays flat
            return True

    def unpin(self, words):
        """Forget pinned facts and notes that mention all of `words`; returns what was forgotten."""
        want = [w for w in re.findall(r"[a-z0-9']+", words.lower()) if w not in ("the", "a", "an", "my", "that", "about", "i")]
        gone = []
        with self.lock:
            for key in ("pinned", "notes"):
                keep = []
                for item in self.d[key]:
                    (gone if want and all(w in item.lower() for w in want) else keep).append(item)
                self.d[key] = keep
        return gone

    def old_notes(self):
        """When the notes are nearly full: the oldest ones, to be folded into the long-term profile."""
        with self.lock:
            return list(self.d["notes"][:CONDENSE]) if len(self.d["notes"]) >= MAX_NOTES - 4 else []

    def condensed(self, notes, profile):
        """The oldest notes were folded into a new profile: drop them and keep it."""
        with self.lock:
            self.d["notes"] = [n for n in self.d["notes"] if n not in notes]
            self.d["profile"] = profile.strip()

    def remember(self, note):
        note = note.strip()
        with self.lock:
            if note and not any(n.endswith(": " + note) for n in self.d["notes"]):
                self.d["notes"] = (self.d["notes"] + [f"{date.today().isoformat()}: {note}"])[-MAX_NOTES:]

    def record(self, app, out, friend=None):
        """Apply what Claude noticed on screen: keep score, move the respect meter, take per-game notes.
        When a friend in a voice call was talking, his note goes on that friend instead of on you."""
        with self.lock:
            g = self.d["games"].setdefault(app, {"events": {}, "notes": []})
            if out.get("event") in COUNTED:
                for score in (g["events"], self.session["events"]):
                    score[out["event"]] = score.get(out["event"], 0) + 1
            self.d["respect"] = max(0, min(100, self.d["respect"] + {"up": 3, "down": -2}.get(out.get("respect"), 0)))
            note = out.get("game_note", "").strip()
            if note and note not in g["notes"]:
                g["notes"] = (g["notes"] + [note])[-MAX_GAME_NOTES:]
            killer = out.get("killer", "").strip().lower()
            if killer and out.get("event") in ("death", "loss"):
                grudges = g.setdefault("grudges", {})
                grudges[killer] = grudges.get(killer, 0) + 1
            note = out.get("remember", "").strip()
            if friend and note:
                f = self.d.setdefault("friends", {}).setdefault(friend, {"notes": []})
                if note not in f["notes"]:
                    f["notes"] = (f["notes"] + [note])[-MAX_GAME_NOTES:]
        if not friend:
            self.remember(out.get("remember", ""))
        self.add_lore(out.get("lore", ""))

    def add_lore(self, text, preset=None):
        """A new fact from a character's own past: the current one's, or (duo mode) the partner's, by preset name."""
        text = text.strip()
        with self.lock:
            d = self.d if preset is None else self.d.setdefault("characters", {}).setdefault(preset, fresh_mind())
            lore = d.setdefault("lore", [])
            if text and text not in lore:
                d["lore"] = (lore + [text])[-MAX_NOTES:]

    def spend(self, dollars, kind="other"):
        with self.lock:
            self.d["spend"][month()] = self.d["spend"].get(month(), 0.0) + dollars
            day = self.d["spend_days"].setdefault(date.today().isoformat(), {})
            day[kind] = day.get(kind, 0.0) + dollars
            for old in sorted(self.d["spend_days"])[:-62]:  # this month and last
                del self.d["spend_days"][old]

    def spent(self):
        return self.d["spend"].get(month(), 0.0)

    def month_costs(self):
        """(this month's total, {day of the month: {kind of call: dollars}}) for the Costs window."""
        with self.lock:
            return self.spent(), {int(k[8:]): dict(v) for k, v in self.d["spend_days"].items() if k.startswith(month())}

    def budget_level(self):
        """0 = fine, 1 = cheap mode (80% of the budget used), 2 = budget used up. Only counts up within a month."""
        budget = config.MONTHLY_BUDGET
        level = 0 if not budget else 2 if self.spent() >= budget else 1 if self.spent() >= 0.8 * budget else 0
        with self.lock:
            new = level > self.d["spend_level"].get(month(), 0)
            if new:
                self.d["spend_level"][month()] = level
        return level, new

    def add_hall(self, entry):
        with self.lock:
            self.d["hall"] = (self.d["hall"] + [entry])[-500:]

    def line(self, text):
        """Keep the session's dialogue for the battle report."""
        with self.lock:
            self.session["lines"] = (self.session["lines"] + [text])[-MAX_LINES:]

    def unreported(self):
        """The previous session, if it lasted 2+ minutes and has no battle report yet."""
        with self.lock:
            prev = [x for x in self.d["sessions"] if x is not self.session]
            return prev[-1] if prev and "report" not in prev[-1] and prev[-1]["seconds"] >= 120 else None

    @staticmethod
    def report_input(s):
        top = max(s["apps"], key=s["apps"].get) if s["apps"] else "nothing"
        return (f"The player's last session: started {s['start']}, lasted {fmt(s['seconds'])}, mostly in {top}. "
                f"Score: {tally(s.get('events', {}))}.\nWhat was said:\n" + ("\n".join(s.get("lines", [])) or "(nothing)"))

    def save(self):
        with self.lock:  # held while writing, so a save already under way can't overwrite an imported memory
            if self.frozen:
                return
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.d, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)  # atomic: a crash mid-save can't wipe your history

    def partner_context(self, preset, name, query="", stories=True):
        """Duo mode: what the other character remembers about the player (theirs to read, not to change);
        stories=False leaves out their own past."""
        with self.lock:
            mind = {**fresh_mind(), **self.d.get("characters", {}).get(preset, {})}
        pinned = pick_pinned(mind["pinned"], query)
        lines = [f"What {name} remembers about the player:"]
        if mind["profile"]:
            lines.append(f"- Long-term picture: {mind['profile']}")
        lines += [f"- Always remember: {p}" for p in pinned] + [f"- {n}" for n in mind["notes"][-10:]]
        text = "\n".join(lines) if len(lines) > 1 else f"{name} doesn't know much about the player yet."
        if stories:
            text += f"\n{name}'s own past (theirs alone):" + ("".join(f"\n- {n}" for n in mind["lore"]) or " nothing told yet.")
        return text

    def relevant_pinned(self, query):
        return pick_pinned(self.d["pinned"], query)

    def context(self, app, title, steam, streak, query="", stories=True):
        """What the current character knows; stories=False leaves out their own past (duo mode, the other one is talking)."""
        with self.lock:
            d, s = self.d, self.session
            g = d["games"].get(app, {"events": {}, "notes": []})
            past = [x for x in d["sessions"] if x is not s][-5:]
            top = sorted(d["apps"].items(), key=lambda kv: -kv[1])[:5]
            lines = [
                "Player stats (tracked by you while you run):",
                f"- Local time: {datetime.now():%I:%M %p, %A}. Playing without a break for {fmt(streak)}.",
                f"- Your mood right now: {time_mood(datetime.now())}.",
                f"- This session: {fmt(s['seconds'])}. Today: {fmt(d['days'].get(date.today().isoformat(), 0))}. "
                f"All time with you watching: {fmt(d['total_seconds'])} over {d['session_count']} sessions.",
                f'- Current window: "{title}" ({app}), {fmt(d["apps"].get(app, 0))} tracked with you.'
                + (f" Steam lifetime hours in {steam[0]}: {steam[1]:.0f} h." if steam else ""),
                f"- Score this session: {tally(s['events'])}. Score in this game overall: {tally(g['events'])}.",
                f"- Your respect for the player: {d['respect']}/100.",
                "- Grudge list in this game (what keeps beating them): "
                + (", ".join(f"{k} {n}" for k, n in sorted(g.get("grudges", {}).items(), key=lambda kv: -kv[1])[:5]) or "empty"),
                f"- API spend on you this month: ${d['spend'].get(month(), 0.0):.2f}"
                + (f" of their ${config.MONTHLY_BUDGET} budget." if config.MONTHLY_BUDGET else "."),
                "- Most time overall: " + (", ".join(f"{a} ({fmt(sec)})" for a, sec in top) or "nothing yet"),
            ]
            if past:
                lines.append("Previous sessions: " + "; ".join(
                    f"{x['start']} ({fmt(x['seconds'])}, mostly {max(x['apps'], key=x['apps'].get) if x['apps'] else 'nothing'})"
                    for x in past))
            report = next((x["report"] for x in reversed(past) if x.get("report")), None)
            if report:
                lines.append(f'Your battle report on their last session: "{report}"')
            if stories:
                lines.append(f"{config.NAME}'s own past (stay consistent with it):"  # named: in duo mode "your" could be either
                             + ("".join(f"\n- {n}" for n in d["lore"]) or " nothing told yet."))
            lines.append("Notes about the player in this game:" + ("".join(f"\n- {n}" for n in g["notes"]) or " nothing yet."))
            if d["profile"]:
                lines.append(f"Your long-term picture of the player: {d['profile']}")
            if d["pinned"]:
                shown = self.relevant_pinned(f"{query} {title} {app}")
                more = len(d["pinned"]) - len(shown)
                lines.append("The player asked you to always remember:" + "".join(f"\n- {p}" for p in shown)
                             + (f"\n({more} more facts are stored; the ones relevant to this moment are above.)" if more else ""))
            lines.append("Things you remember about the player (recent):" + ("".join(f"\n- {n}" for n in d["notes"]) or " nothing yet."))
            friends = d.get("friends", {})
            if friends:
                lines.append("The player's friends you know from voice calls (running jokes to use):" + "".join(
                    f"\n- {name.title()}: " + ("; ".join(f["notes"]) or "nothing yet") for name, f in friends.items()))
        return "\n".join(lines)


# ------------------------------------------------------------------ Steam

def parse_vdf(text):
    """Minimal parser for Valve's KeyValues text format (nested dicts of strings)."""
    root, stack, key = {}, [], None
    cur = root
    for s, brace in re.findall(r'"((?:[^"\\]|\\.)*)"|([{}])', text):
        if brace == "{":
            new = {}
            cur[key] = new
            stack.append(cur)
            cur, key = new, None
        elif brace == "}":
            cur, key = (stack.pop() if stack else root), None
        elif key is None:
            key = s
        else:
            cur[key], key = s, None
    return root


def _lower(d):
    return {k.lower(): v for k, v in d.items()} if isinstance(d, dict) else {}


@lru_cache(maxsize=64)
def steam_app(exe):
    """(appid, game name) for an exe inside a Steam library folder, else None."""
    m = re.match(r"(.*?)[\\/]steamapps[\\/]common[\\/]([^\\/]+)[\\/]", exe or "", re.I)
    if not m:
        return None
    lib, folder = m.groups()
    for acf in Path(lib, "steamapps").glob("appmanifest_*.acf"):
        try:
            st = _lower(parse_vdf(acf.read_text(encoding="utf-8", errors="ignore")).get("AppState"))
        except OSError:
            continue
        if st.get("installdir", "").lower() == folder.lower():
            return st.get("appid"), st.get("name", folder)
    return None


def playtime_minutes(localconfig, appid):
    node = localconfig
    for key in ("UserLocalConfigStore", "Software", "Valve", "Steam", "apps", appid):
        node = _lower(node).get(key.lower())
        if node is None:
            return None
    try:
        return int(_lower(node).get("playtime"))
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=4)
def _localconfig(path, mtime):  # mtime in the key re-reads the file when Steam updates it
    return parse_vdf(Path(path).read_text(encoding="utf-8", errors="ignore"))


def steam_hours(exe):
    """(game name, lifetime hours) from Steam's local config, or None if it isn't a Steam game."""
    app = steam_app(exe)
    if not app:
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            root = Path(winreg.QueryValueEx(k, "SteamPath")[0])
        newest = max(root.glob("userdata/*/config/localconfig.vdf"), key=lambda p: p.stat().st_mtime)
        mins = playtime_minutes(_localconfig(str(newest), newest.stat().st_mtime), app[0])
    except (OSError, ValueError):
        return None
    return (app[1], mins / 60) if mins is not None else None


# ------------------------------------------------------------------ Windows: what's in front, is the player AFK

user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.GetTickCount.restype = wintypes.DWORD


def foreground_app():
    """(exe path, window title, pid) of the window in front."""
    hwnd = user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    title = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, title, 256)
    exe = ""
    h = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if h:
        buf, size = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            exe = buf.value
        kernel32.CloseHandle(h)
    return exe, title.value, pid.value


class _Rect(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(_Rect)]


def foreground_center():
    """Screen point in the middle of the window in front (which display the game is on)."""
    r = _Rect()
    user32.GetWindowRect(user32.GetForegroundWindow(), ctypes.byref(r))
    return (r.left + r.right) // 2, (r.top + r.bottom) // 2


class _LastInput(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_seconds():
    info = _LastInput(ctypes.sizeof(_LastInput), 0)
    user32.GetLastInputInfo(ctypes.byref(info))
    return ((kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000
