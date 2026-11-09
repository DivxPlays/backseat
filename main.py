"""Vorn: an AI gaming companion that watches your screen, talks, gives hints and trash-talks you."""
import ctypes
import difflib
import logging
import os
import queue
import random
import re
import subprocess
import sys
import threading
import time
import winreg
from collections import deque
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
APP, VERSION, AUTHOR = "Vorn", "1.2.0", "DivxPlays"  # x.y.Z fixes, x.Y.0 features; bumped when the user agrees
logging.basicConfig(filename=HERE / "companion.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
for noisy in ("httpx", "httpx2", "huggingface_hub", "faster_whisper", "comtypes"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


def _crash(*exc):  # he runs without a console, so a crash must be visible somewhere
    logging.critical("crash", exc_info=exc)
    ctypes.windll.user32.MessageBoxW(None, f"{exc[1]!r}\n\nDetails are in companion.log next to main.py.", "Vorn crashed", 0x10)


sys.excepthook = _crash
threading.excepthook = lambda a: logging.critical("thread crash", exc_info=(a.exc_type, a.exc_value, a.exc_traceback))

import anthropic  # noqa: E402
import keyboard  # noqa: E402
from PySide6.QtCore import QObject, QPoint, QRectF, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QLineEdit, QMenu, QMessageBox, QSystemTrayIcon, QWidget  # noqa: E402

import brain  # noqa: E402
import config  # noqa: E402
import highlights  # noqa: E402
import transfer  # noqa: E402
from camera import BACKGROUNDS, REACT, Camera  # noqa: E402
import voices  # noqa: E402
from costs_ui import CostsWindow  # noqa: E402
from memories_ui import MemoriesWindow  # noqa: E402
from character import H as CH, HEAD_Y, W as CW, make_character, tier_for  # noqa: E402
from memory import Memory, app_name, fmt, foreground_app, foreground_center, idle_seconds, steam_app, steam_hours  # noqa: E402
from senses import SR, Ducker, Ears, Eyes, Voice, WakeListener, changed, cue, game_display, listen_source_ok, save_clip, save_moment  # noqa: E402
from settings_ui import SettingsWindow, presets, set_setting  # noqa: E402

user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
BUBBLE_W = 280
INK = QColor("#1b1418")
HALL = HERE / "Hall of Shame"
REPORTS = HERE / "battle reports.txt"
PYTHONW = HERE / ".venv" / "Scripts" / "pythonw.exe"
RUN_KEY, RUN_NAME = r"Software\Microsoft\Windows\CurrentVersion\Run", "VornCompanion"
SITUATIONS = {
    "start": "The player just started you up. Greet them with a roast. If your stats include a battle report on their last session, "
             "open with its highlights; otherwise use their time stats or notes.",
    "change": "The player's screen changed. React to what is happening right now, in one short sentence (under 15 words). "
              "Only talk about what you can actually see in the screenshots; if you can't tell what's on screen, don't guess. "
              "Never bring up a moment you already reacted to in your recent lines; if nothing new happened, jab at something "
              "else you see, or return an empty line to stay quiet.",
    "quiet": "You've been quiet a while. Look at the screen and trash-talk the player in one short sentence (under 15 words): "
             "their play, their hours, or their idling. Don't repeat a point from your recent lines.",
    "lore": "You've been quiet a while. Tell a new, very short story from your own past: one not in your listed past (it "
            "must fit with it, never retell it), "
            "then turn it into a jab at the player. Under 25 words.",
    "look": "The player pressed the look hotkey. Comment on what they're looking at, or give a hint about it.",
    "nag": "It's late, or the player has gone a long time without a break (see the local time and break time in the stats). "
           "Nag them to take a break or go to sleep, as a roast.",
    "breakdown": "The player just lost. These screenshots are from the last minute or so, oldest first. Break down what went "
                 "wrong, specific and tactical, still a roast. Up to 3 sentences, under 50 words.",
}
AUTO = {"change", "quiet", "lore", "nag", "breakdown"}  # jobs he starts himself; they stop when the budget runs out
COMEBACK = 0.6  # duo mode, local model: how often the other one fires back at a comment
COMEBACK_SAYS = ('{a} (the other one in your window) just said: "{line}". Fire back at {a} in one short sentence (under 15 '
                 "words), in your own style: roast what {a} said, or take the player's side against {a}. Your past is your "
                 "own: never tell {a}'s stories or claim {a}'s deeds as yours.")
BLOODFIRE = {"bloodfire": 8, "bloodfire-max": 25}  # seconds he burns: a big play, or reaching 100 respect


def repeats(line, recent):
    """True if line is nearly word for word one of their last few lines ("You: ..." or, in duo mode, "You (Mika): ...")."""
    words = re.findall(r"[a-z']+", line.lower())
    return any(difflib.SequenceMatcher(None, words, re.findall(r"[a-z']+", said.split(": ", 1)[-1].lower())).ratio() > 0.6
               for said in recent[-8:] if said.startswith("You"))


def addressed(text, wake_of):
    """Duo mode: which character the speaker called by name first ({name: their wake names}), or None."""
    hits = [(m.start(), name) for name, names in wake_of.items()
            if (m := re.search(r"\b(?:" + "|".join(map(re.escape, names)) + r")\b", text, re.I))]
    return min(hits)[1] if hits else None


def turns_of(out, names):
    """What to say, as [(speaker, mood, line)]: one line for a solo character, a short exchange in duo mode."""
    if "turns" in out:
        turns = [(t["speaker"], t.get("mood", "idle"), t["line"].strip()) for t in out["turns"]
                 if t.get("speaker") in names and t.get("line", "").strip()]
        return turns[:3] or [(names[0], "idle", "")]
    return [(names[0], out.get("mood", "idle"), out.get("line", ""))]


def bloodfire(streak, event, before, after):
    """(new win streak, "bloodfire" / "bloodfire-max" / None) after a look, from the event and respect before/after it."""
    streak = streak + 1 if event in ("win", "epic") else 0 if event in ("death", "loss", "fail") else streak
    if after >= 100 > before:
        return streak, "bloodfire-max"
    if event == "epic" or (event == "win" and streak >= 2):
        return streak, "bloodfire"
    return streak, None


REMEMBER = re.compile(r"^(?:please\s+)?(?:remember|don'?t forget)\s+(?:that\s+|this:?\s+)?(?!my voice)(.{3,})", re.I)
FORGET = re.compile(r"^(?:please\s+)?forget\s+(?:that\s+|about\s+|this:?\s+)?(.{2,})", re.I)
ENROLL = re.compile(r"\b(?:remember|learn|save)\s+my\s+voice\W+(?:please\W+)?(?:(?:i'?m|i am|my name is|it'?s|this is|call me)\s+)?"
                    r"(?!please\b)([a-z][a-z'-]{1,20})", re.I)
SEARCH_ASKED = re.compile(r"\b(search|look (it |that |this )?up|google|wiki|guide|walkthrough)", re.I)
BUDGET_NEWS = {1: "Also tell them they've burned through 80% of this month's budget on you, so you're switching to cheap mode.",
               2: "Also tell them this month's budget is gone, so from now on you only speak when they talk to you."}
SOUNDS = {"smug": ["Heh.", "Hmph."], "angry": ["Hmph!", "Argh!"], "laugh": ["Ha ha ha!", "Hah!"],
          "disgusted": ["Ugh.", "Hmph."], "surprised": ["What?!", "Huh?!"], "idle": ["Hmph."]}
ALREADY_A_SOUND = re.compile(r"^(hmph|heh|hah?|ugh|argh|what|huh|tch)\b", re.I)


class Bridge(QObject):
    """Signals that carry events from background threads to the UI thread."""
    say = Signal(str, str, object, str, str)  # mood, line, audio samples (or None), game event, who says it
    note = Signal(str)  # status text in the bubble, no voice
    chat = Signal()
    move = Signal()
    awake = Signal()


def set_clickthrough(widget, on):
    """Locked = mouse clicks pass straight through him to the game (WS_EX_TRANSPARENT)."""
    hwnd = int(widget.winId())
    style = user32.GetWindowLongPtrW(hwnd, -20)  # GWL_EXSTYLE
    user32.SetWindowLongPtrW(hwnd, -20, (style | 0x20) if on else (style & ~0x20))


def autostart_on():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
        return True
    except OSError:
        return False


def set_autostart(on):
    """Start with Windows, hidden, and wake up when a game starts."""
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, f'"{PYTHONW}" "{HERE / "main.py"}" --wait-for-game')
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


class Overlay(QWidget):
    def __init__(self, voice, saved_pos, respect, spent):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.char, self.voice, self.respect, self.spent, self.ducker = make_character(config.CHARACTER), voice, respect, spent, Ducker()
        self.text, self.shown, self.cps, self.hide_at = "", 0.0, 40.0, 0.0
        self.moving, self.grab_at = False, QPoint()
        self.left = "left" in config.CORNER  # True = bubble on his right
        other = brain.partner()
        self.chars = [self.char] + ([make_character(other["CHARACTER"])] if other else [])  # duo mode: both on screen
        self.names = [config.NAME] + ([other["NAME"]] if other else [])
        self.speaking = 0  # which of them is talking (their mouth follows the voice)
        self.span = CW * config.SCALE * len(self.chars)  # how wide the characters are together
        self.resize(int(BUBBLE_W + self.span), int(CH * config.SCALE) + 26)  # + a strip under their feet for the cost tag
        geo = QApplication.primaryScreen().availableGeometry()
        x, y = (geo.left() if self.left else geo.right() - self.width() + 1), geo.bottom() - self.height() + 1
        if saved_pos and QApplication.screenAt(QPoint(saved_pos[0] + self.width() // 2, saved_pos[1] + self.height() // 2)):
            x, y, self.left = saved_pos  # where you locked him last time, if that display is still connected
            geo = QApplication.screenAt(QPoint(x + self.width() // 2, y + self.height() // 2)).availableGeometry()
            y = max(geo.top(), min(y, geo.bottom() - self.height() + 1))  # he's taller than when you saved the spot
        self.move(x, y)
        self.last = time.monotonic()
        self.timer = QTimer(self)  # the animation loop: face, lip-sync and subtitles all advance here
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

    def toggle_move(self):
        """F6: unlock to drag him anywhere; F6 again locks him. Returns the locked position to save."""
        self.moving = not self.moving
        set_clickthrough(self, not self.moving)
        if self.moving:
            return None
        s = config.SCALE
        char_x = self.x() + (0 if self.left else BUBBLE_W) + self.span / 2
        screen = (QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()).geometry()
        left = char_x < screen.center().x()  # bubble goes on the side with more room
        if left != self.left:
            self.move(self.x() + (BUBBLE_W if left else -BUBBLE_W), self.y())  # keep him where you dropped him
            self.left = left
        return [self.x(), self.y(), self.left]

    def mousePressEvent(self, e):
        if self.moving:
            self.grab_at = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self.moving and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self.grab_at)

    def show_line(self, mood, line, audio, event="none", who=""):
        self.speaking = self.names.index(who) if who in self.names else 0
        char = self.chars[self.speaking]
        char.set_mood(mood)
        for i, other in enumerate(self.chars):
            if i != self.speaking:
                other.set_mood(REACT.get(mood, "idle"))  # duo mode: the other one reacts to what's said
        if event in BLOODFIRE:
            for c in self.chars:  # both power up
                c.bloodfire(BLOODFIRE[event])
        elif event in ("win", "epic"):
            char.flare()
        elif event == "menu":
            char.roll()
        elif event == "loss":
            char.slump()
        if len(self.chars) > 1:
            line = f"{who or self.names[0]}: {line}"  # who's talking, in the shared bubble
        if audio is not None:
            self.ducker.duck()
        dur = self.voice.play(audio) if audio is not None else 0.0
        self.text, self.shown = line, 0.0
        self.cps = len(line) / dur if dur > 0.3 else 40.0
        self.hide_at = time.monotonic() + max(dur, len(line) / 15) + 4

    def note(self, text):
        self.text, self.shown, self.cps = text, float(len(text)), 40.0
        self.hide_at = time.monotonic() + 5

    def tick(self):
        now = time.monotonic()
        dt, self.last = min(0.1, now - self.last), now
        afk, level = idle_seconds() > 60, self.voice.level()
        for i, char in enumerate(self.chars):
            char.afk = afk  # yawns and bored eyes while you're away
            char.toward = 1.0 if self.left else -1.0  # the rest of your screen is on the bubble side
            char.tier = tier_for(self.respect())  # gear upgrades as you earn respect
            char.step(dt, level if i == self.speaking else 0.0)  # only the one talking moves their mouth
        if self.ducker.saved and not self.voice.busy():
            self.ducker.restore()
        self.shown += dt * self.cps
        if self.text and now > self.hide_at:
            self.text = ""
            for char in self.chars:
                char.set_mood("idle")
        self.update()

    def paintEvent(self, _):
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing)
        if self.moving:  # visible frame so the whole box is grabbable
            g.setPen(QPen(QColor("#c8893f"), 2, Qt.DashLine))
            g.setBrush(QColor(20, 16, 20, 90))
            g.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 12, 12)
            g.setPen(QColor("#f1e9df"))
            g.setFont(QFont("Segoe UI", 10, QFont.Bold))
            g.drawText(QRectF(12, 8, BUBBLE_W, 40), Qt.TextWordWrap, f"Drag me anywhere.\n{config.KEY_MOVE.upper()} to lock.")
        for i, char in enumerate(self.chars):
            g.save()
            g.translate((0 if self.left else BUBBLE_W) + i * CW * config.SCALE, 0)
            g.scale(config.SCALE, config.SCALE)
            char.paint(g)
            g.restore()
        self.cost_tag(g)
        if self.text:
            self.bubble(g)
        g.end()

    def cost_tag(self, g):
        """This month's API spend, always shown under him."""
        text = f"${self.spent():.2f}" + (f" / ${config.MONTHLY_BUDGET}" if config.MONTHLY_BUDGET else "")
        font = QFont("Segoe UI", 9, QFont.Bold)
        g.setFont(font)
        w = QFontMetrics(font).horizontalAdvance(text) + 18
        center = (0 if self.left else BUBBLE_W) + self.span / 2
        r = QRectF(center - w / 2, self.height() - 24, w, 20)
        g.setPen(QPen(QColor(232, 194, 122, 120), 1))
        g.setBrush(QColor(18, 14, 18, 200))
        g.drawRoundedRect(r, 10, 10)
        g.setPen(QColor("#e8c27a"))
        g.drawText(r, Qt.AlignCenter, text)

    def bubble(self, g):
        font = QFont("Segoe UI", 11, QFont.DemiBold)
        g.setFont(font)
        r = QFontMetrics(font).boundingRect(0, 0, BUBBLE_W - 44, 1000, Qt.TextWordWrap, self.text)  # full text: no jumping
        bw, bh = r.width() + 28, r.height() + 20
        s = config.SCALE
        x = self.span + 14 if self.left else BUBBLE_W - bw - 14
        y = max(4.0, HEAD_Y * s - bh / 2)
        tip_x, base_x = (x - 16, x + 2) if self.left else (x + bw + 16, x + bw - 2)
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(x, y, bw, bh), 14, 14)
        tail = QPainterPath()
        tail.moveTo(base_x, y + bh * 0.35)
        tail.lineTo(tip_x, y + bh * 0.55)
        tail.lineTo(base_x, y + bh * 0.7)
        tail.closeSubpath()
        g.setPen(QPen(INK, 2.5))
        g.setBrush(QColor(250, 244, 234, 242))
        g.drawPath(shape.united(tail))
        g.setPen(INK)
        g.drawText(QRectF(x + 14, y + 10, r.width() + 2, r.height() + 2), Qt.TextWordWrap, self.text[: int(self.shown)])


class ChatBox(QLineEdit):
    def __init__(self, on_send):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setPlaceholderText(f"Talk to {config.NAME}...  (Enter = send, Esc = close)")
        self.setStyleSheet("QLineEdit{background:#1b1418;color:#f1e9df;border:2px solid #c8893f;"
                           "border-radius:10px;padding:8px;font:11pt 'Segoe UI'}")
        self.resize(BUBBLE_W + 160, 42)
        self.on_send, self.prev = on_send, None
        self.returnPressed.connect(self.send)

    def popup(self, overlay):
        self.prev = user32.GetForegroundWindow()
        geo = (QApplication.screenAt(overlay.geometry().center()) or QApplication.primaryScreen()).availableGeometry()
        y = overlay.y() - 52 if overlay.y() - 52 >= geo.top() else overlay.y() + overlay.height() + 10  # below him if he's at the top
        self.move(min(max(overlay.x() + 20, geo.left()), geo.right() - self.width()), y)
        self.clear()
        self.show()
        self.raise_()
        # Windows won't hand focus to a background app; borrow the game's input thread for a moment
        other, me = user32.GetWindowThreadProcessId(self.prev, None), kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(other, me, True)
        user32.SetForegroundWindow(int(self.winId()))
        user32.AttachThreadInput(other, me, False)
        self.activateWindow()
        self.setFocus()

    def send(self):
        text = self.text().strip()
        self.close_box()
        if text:
            self.on_send(text)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close_box()
        else:
            super().keyPressEvent(e)

    def close_box(self):
        self.hide()
        if self.prev:
            user32.SetForegroundWindow(self.prev)  # back to the game


class Companion:
    def __init__(self, bridge, waiting):
        self.bridge = bridge
        self.mem, self.eyes, self.ears, self.voice = Memory(), Eyes(), Ears(), Voice()
        self.client = brain.make_client()
        self.jobs = queue.Queue()
        self.recent = []
        self.paused = self.muted = self.busy = self.started = False
        self.awake = not waiting  # started with Windows: stay hidden until a game starts
        self.show_on_stream = bool(self.mem.d.get("show_on_stream"))
        now = time.monotonic()
        self.last_spoke, self.last_shame, self.last_breakdown = now, 0.0, 0.0
        self.streak_start = now  # when your current stretch without a break began
        self.last_nag = now - (config.NAG_EVERY - 10) * 60  # first nag can come 10 minutes in
        self.app = ("", "", 0)
        self.focus = foreground_center()  # middle of the last window you used that isn't him: which display the game is on
        self.base_thumb = None
        self.history = deque(maxlen=3)  # the game's display from the last few looks, for post-match breakdowns
        self.streak = 0  # wins and epic plays in a row, for Bloodfire
        self.local_down_until = 0.0  # after the local model fails, use Claude until then
        self.voices = voices.Voices()  # friends' voice fingerprints (the model loads on first use)
        self.listeners = []  # "Hey Vorn" listeners: your mic, and your friends' voices from Discord
        self.partner = brain.partner()  # duo mode: the other character, on screen too
        self.names = [config.NAME] + ([self.partner["NAME"]] if self.partner else [])
        self.voices_of = {config.NAME: {"VOICE": config.VOICE, "VOICE_RATE": config.VOICE_RATE, "VOICE_PITCH": config.VOICE_PITCH,
                                        "POWER": config.POWER}}
        self.wake_of = {config.NAME: config.WAKE_NAMES}
        if self.partner:
            self.voices_of[self.partner["NAME"]] = {k: self.partner[k] for k in ("VOICE", "VOICE_RATE", "VOICE_PITCH", "POWER")}
            self.wake_of[self.partner["NAME"]] = self.partner["WAKE_NAMES"]
        if config.LOCAL_MODEL:
            threading.Thread(target=brain.start_ollama, daemon=True).start()

    def start(self):
        preload = [self.ears.model] + ([self.voice.kokoro] if config.VOICE.startswith("kokoro:") else [])  # Whisper, Kokoro
        for target in [self.worker, self.watcher] + preload:
            threading.Thread(target=target, daemon=True).start()
        if self.awake:
            self.wake_up()

    def wake_up(self):
        """Start talking and listening: right away, or once a game starts if he launched with Windows."""
        if self.started:
            return
        self.started = self.awake = True
        if config.WAKE_WORD:  # the mic only opens once he's awake
            self.listeners.append(WakeListener(self.ears, self.voice, self.wake_heard, config.MIC_DEVICE))
        if config.FRIENDS_DEVICE and listen_source_ok(config.FRIENDS_DEVICE):  # his ear on your friends' voices (a mic or a loopback)
            # (never on a missing device: the fallback would be your own mic, and he'd hear you twice)
            self.listeners.append(WakeListener(self.ears, self.voice, self.friend_heard, config.FRIENDS_DEVICE))
        for listener in self.listeners:
            if self.partner:  # duo mode: answer to either name, and keep it so the one you called answers first
                listener.WAKE = WakeListener.pattern(config.WAKE_NAMES + self.partner["WAKE_NAMES"])
                listener.keep_name = True
            threading.Thread(target=listener.run, daemon=True).start()
        self.bridge.awake.emit()
        self.jobs.put(("start", None))

    def wake_heard(self, text, audio=None):
        if text is None:  # just "Hey Vorn": he's listening for the question
            cue("on")
            self.bridge.note.emit("(listening...)")
        else:
            self.jobs.put(("ask", text))

    def friend_heard(self, text, audio):
        if text is None:
            self.bridge.note.emit("(listening to your friend...)")
        else:
            self.jobs.put(("friend", (text, audio)))

    def who(self, text, clip):
        """(the friend's name or None, whether they just taught him their voice). Fingerprints never leave this PC."""
        m = ENROLL.search(text)
        fp = None
        if clip is not None and len(clip) > 16000 * 0.8:
            try:
                fp = self.voices.fingerprint(clip)
            except Exception:
                logging.warning("voice fingerprint failed", exc_info=True)
        with self.mem.lock:
            friends = self.mem.d.setdefault("friends", {})
            if m:
                name = m.group(1).lower()
                friend = friends.setdefault(name, {"notes": []})
                if fp is not None:
                    friend["voice"] = voices.learn(friend.get("voice"), fp)
                return name, True
            if fp is None:
                return None, False
            name, score = voices.identify({n: f["voice"] for n, f in friends.items() if f.get("voice")}, fp)
            if name and score > 0.65:
                friends[name]["voice"] = voices.learn(friends[name]["voice"], fp, 0.15)  # he keeps learning their voice
            return name, False

    # hotkeys (these run on the keyboard library's thread)
    def talk_down(self):
        if self.awake and not self.ears.recording:
            self.voice.stop()
            self.ears.start()
            self.bridge.note.emit("(listening...)")

    def talk_up(self):
        audio = self.ears.stop()
        if audio is not None:
            self.jobs.put(("heard", audio))

    def toggle_pause(self):
        self.paused = not self.paused
        cue("off" if self.paused else "on")
        self.bridge.note.emit(f"(not watching your screen: {config.KEY_PAUSE.upper()} to resume)" if self.paused else "(watching again)")

    def toggle_mute(self):
        self.muted = not self.muted
        cue("off" if self.muted else "on")
        self.bridge.note.emit(f"(shut-up mode: I'll only talk when you talk to me. {config.KEY_MUTE.upper()} to undo)"
                              if self.muted else "(free to speak my mind again)")

    def worker(self):
        while True:
            kind, arg = self.jobs.get()
            self.busy = True
            try:
                self.handle(kind, arg)
            except anthropic.AuthenticationError:
                self.bridge.note.emit("(API key rejected: check api_key.txt)")
            except Exception:
                logging.exception("job %s failed", kind)
                self.bridge.note.emit("(something broke: see companion.log)")
            finally:
                self.busy = False
                self.last_spoke = time.monotonic()

    def handle(self, kind, arg):
        if not self.awake:
            return
        if kind == "heard":
            arg = self.ears.transcribe(arg)
            if not arg:
                return self.bridge.note.emit("(didn't catch that)")
            kind = "ask"
        if kind == "ask":
            self.bridge.note.emit(f'You: "{arg}"')
        speaker, enrolled = None, False
        if kind == "friend":  # someone in your Discord call said "Hey Vorn"
            arg, clip = arg
            speaker, enrolled = self.who(arg, clip)
            self.bridge.note.emit(f'{(speaker or "Friend").title()}: "{arg}"')
        if self.client is None:
            return self.speak("disgusted", "You forgot my API key, fool. Put it in api underscore key dot text.")
        level, crossed = self.mem.budget_level()
        local = config.LOCAL_MODEL and kind in AUTO and kind != "breakdown" and time.monotonic() > self.local_down_until
        if level == 2 and kind in AUTO and not crossed and not local:
            return  # budget used up: he only answers when you talk to him (the free local model keeps going)
        if kind == "start":
            self.write_battle_report()
        exe, title, _ = self.app
        app = app_name(exe, title)
        shot = None
        if kind == "breakdown":
            jpegs = list(self.history)
        else:
            shot = None if self.paused else self.eyes.look(self.focus)
            jpegs = shot[1] if shot else []
            if shot:
                self.base_thumb = shot[0]
                self.history.append(shot[1][game_display(shot[2], self.focus)])
        if kind == "friend":
            name = speaker.title() if speaker else None
            situation = (f"{name}, the player's friend in their voice call, just asked you to remember their voice. You will now. "
                         f"Greet {name} with a roast." if enrolled else
                         f'{name or "One of the player`s friends (you can`t tell which; if they say their name, use it)"}, in the voice call '
                         f'with the player, says to you: "{arg}". Answer them.')
        else:
            situation = f'The player says to you: "{arg}". Answer them.' if kind == "ask" else SITUATIONS[kind]
        if kind == "ask":  # duo mode keeps "Hey Mika, " in front: "remember that ..." comes after it
            m = WakeListener.pattern([n for names in self.wake_of.values() for n in names]).match(arg)
            situation += self.memory_command(arg[m.end():] if m else arg)
        to = addressed(arg, self.wake_of) if self.partner and kind in ("ask", "friend") else None
        if to:  # duo mode: without this the other one answers too ("My day?") when only one was asked
            other = next(n for n in self.names if n != to)
            situation += f" (This was said to {to}: only {to} speaks, in one turn. {other} stays silent.)"
        if crossed:
            situation += " " + BUDGET_NEWS[level]
        # duo mode: the small local model voices one of them per comment and sees only that one's own past (shown both,
        # it tells the other's stories). shortcut: if it fails, Claude's fallback reply also misses the other's past (rare)
        alone = random.choice([brain.me(), self.partner]) if local and self.partner else None
        query = arg if kind in ("ask", "friend") else ""  # picks the facts relevant to what was said
        context = self.knowledge(app, title, exe, query, alone)
        smart = kind in ("ask", "look", "breakdown") and level == 0  # cheap mode (80% of budget): Haiku only, no web search
        model = config.SMART_MODEL if smart else config.MODEL
        search = smart and kind == "ask" and bool(SEARCH_ASKED.search(arg))  # having the tool costs ~2 cents even unused
        out = None
        if local:
            try:
                out, spent = brain.local_think(config.LOCAL_MODEL, context, self.recent[-4:], situation, jpegs,
                                               only=alone)  # less old talk to mix up
                # the small local model only talks: it calls kills "wins" and misreads screens, so it doesn't keep score,
                # move respect, set off Bloodfire, frame the Hall of Shame, trigger breakdowns or write notes or stories
                # (it reads your memory, it doesn't write it); Claude does those
                out.update(event="none", respect="same", save_moment=False, killer="", remember="", game_note="", lore="")
                said = out["turns"][0] if alone else None
                if said and said["line"].strip() and random.random() < COMEBACK:  # duo mode: the other one fires back
                    other = brain.me() if alone is self.partner else self.partner  # from their own head: own past only
                    back, _ = brain.local_think(config.LOCAL_MODEL, self.knowledge(app, title, exe, query, other),
                                                self.recent[-3:] + [f"{said['speaker']}: {said['line']}"],
                                                COMEBACK_SAYS.format(a=said["speaker"], line=said["line"]), jpegs, only=other)
                    out["turns"] += back["turns"]
            except Exception:
                logging.warning("local model failed; using Claude for the next 5 minutes", exc_info=True)
                self.local_down_until = time.monotonic() + 300
        if out is None:
            out, spent = brain.think(self.client, model, context, self.recent, situation, jpegs, search=search)
        self.mem.spend(spent, kind)
        logging.info("%s%s ($%.4f) -> %s", kind, " (local)" if spent == 0 and local else "", spent, out)
        turns = turns_of(out, self.names)  # [(speaker, mood, line)]: one for a solo character, a short exchange in duo mode
        if to:  # only the one you called speaks, even if the model wrote a line for the other
            turns = [t for t in turns if t[0] == to] or turns
        text = " ".join(line for _, _, line in turns)
        if kind in AUTO and (not text.strip() or repeats(text, self.recent)):
            return logging.info("nothing new to say: staying quiet")  # a stale moment must not be counted or spoken again
        before = self.mem.d["respect"]
        self.mem.record(app, out, friend=speaker)
        for t in out.get("turns", []):  # duo mode: a story goes to whoever told it (the local model's turns have none)
            if t.get("speaker") in self.names:
                self.mem.add_lore(t.get("lore", ""), None if t["speaker"] == config.NAME else self.partner["PRESET"])
        event = "epic" if tier_for(self.mem.d["respect"]) > tier_for(before) else out.get("event", "none")  # new gear: aura flare
        self.streak, fire = bloodfire(self.streak, out.get("event"), before, self.mem.d["respect"])
        event = fire or event
        shame = None
        if out.get("save_moment") and shot and time.monotonic() - self.last_shame > 60:
            self.last_shame = time.monotonic()
            shame = save_moment(shot[2], self.focus, turns[0][2], HALL)
        if out.get("event") == "loss" and kind != "breakdown" and not self.muted and time.monotonic() - self.last_breakdown > 180:
            self.last_breakdown = time.monotonic()
            self.jobs.put(("breakdown", None))
        self.mem.save()
        if self.muted and kind == "change":  # shut-up mode: he keeps score, he just keeps it to himself
            if shame:
                self.hall_entry(shame, turns[0][2], title or app, self.synth(turns[0][2]))
            return
        if kind in ("ask", "friend"):
            said = f"Player: {arg}" if kind == "ask" else f"{(speaker or 'unknown').title()} (friend): {arg}"
            self.recent.append(said)
            self.mem.line(said)
        first = None
        for i, (who, mood, line) in enumerate(turns):
            said = f"You ({who}): {line}" if len(self.names) > 1 else f"You: {line}"
            self.recent = (self.recent + [said])[-12:]
            self.mem.line(said)
            spoken, audio = self.speak(mood, line, event if i == 0 else "none", who)
            first = first or (spoken, audio)
            if i < len(turns) - 1 and audio is not None:
                time.sleep(len(audio) / SR + 0.25)  # let them finish before the other one answers
        if shame:
            self.hall_entry(shame, first[0], title or app, first[1])
        self.condense_memory()

    def knowledge(self, app, title, exe, query="", alone=None):
        """What they know right now; `alone` (a preset: duo mode, local model) shows only that character's own past."""
        text = self.mem.context(app, title, steam_hours(exe), time.monotonic() - self.streak_start, query=query,
                                stories=alone is None or alone["NAME"] == config.NAME)
        if self.partner:  # duo mode: they also know what the other one remembers about you
            text += "\n" + self.mem.partner_context(self.partner["PRESET"], self.partner["NAME"], query=query,
                                                    stories=alone is None or alone is self.partner)
        return text + ("\n(You are visible in a corner of the screenshots, with your speech bubble. Ignore yourself.)"
                       if self.show_on_stream else "\n(Your own overlay is hidden from the screenshots.)")

    def memory_command(self, said):
        """ "Remember that ..." pins a fact for good, "forget ..." removes it; returns a note for the reply."""
        m = REMEMBER.match(said)
        if m:
            if not self.mem.pin(m.group(1)):
                return (" (Your memory for pinned facts is full: 500. Tell them, in character, to make room in the tray menu "
                        "under Memories.)")
            return f' (You have now pinned this in your memory for good: "{m.group(1)}". Confirm it briefly, in character.)'
        m = FORGET.match(said)
        if m:
            gone = self.mem.unpin(m.group(1))
            return (f" (You erased this from your memory: {'; '.join(gone)}. Confirm it briefly, in character.)" if gone else
                    " (Nothing in your memory matched that. Say so, in character.)")
        return ""

    def condense_memory(self):
        """When the notes are nearly full, fold the oldest into the long-term profile instead of losing them."""
        old = self.mem.old_notes()
        if not old or self.client is None:
            return
        try:
            profile, spent = brain.condense(self.client, config.MODEL, self.mem.d["profile"], old)
        except Exception:
            return logging.warning("couldn't update the long-term profile", exc_info=True)
        self.mem.spend(spent, "memory")
        self.mem.condensed(old, profile)
        self.mem.save()
        logging.info("folded %d old notes into the long-term profile ($%.4f)", len(old), spent)

    def hall_entry(self, path, line, game, audio):
        clip = path.with_suffix(".wav") if audio is not None else None
        if clip:
            save_clip(clip, audio)
        self.mem.add_hall({"file": path.name, "clip": clip.name if clip else None, "caption": line, "game": game,
                           "when": datetime.now().isoformat(timespec="minutes")})
        self.mem.save()
        logging.info("hall of shame: %s", path)

    def write_battle_report(self):
        """Report on the previous session, written at the next launch so it works even if the PC was shut down."""
        prev = self.mem.unreported()
        if not prev:
            return
        text, spent = brain.report(self.client, config.MODEL, Memory.report_input(prev))
        self.mem.spend(spent, "report")
        with self.mem.lock:
            prev["report"] = text
        self.mem.save()
        with open(REPORTS, "a", encoding="utf-8") as f:
            f.write(f"{prev['start']} ({fmt(prev['seconds'])}):\n{text}\n\n")

    def synth(self, line):
        try:
            return self.voice.synth(line)
        except Exception:
            logging.exception("voice failed; showing text only")
            return None

    def speak(self, mood, line, event="none", who=None):
        """Say a line in the voice of `who` (a character's name; default the current one)."""
        voice = self.voices_of.get(who) or {}
        if event in BLOODFIRE:
            line = f"{voice.get('POWER', config.POWER)}! {line}"  # shouted as the character transforms
        elif random.random() < 0.4 and not ALREADY_A_SOUND.match(line):  # a scoff, laugh or grunt first
            line = f"{random.choice(SOUNDS.get(mood, ['Hmph.']))} {line}"
        try:
            audio = self.voice.synth(line, voice.get("VOICE"), voice.get("VOICE_RATE"), voice.get("VOICE_PITCH"))
        except Exception:
            logging.exception("voice failed; showing text only")
            audio = None
        self.bridge.say.emit(mood, line, audio, event, who or config.NAME)
        return line, audio

    def watcher(self):
        while True:  # one failed screenshot (UAC prompt, lock screen, resolution change) must not end his comments for good
            try:
                self._watch()
            except Exception:
                logging.exception("watcher failed, restarting it")
                time.sleep(5)

    def _watch(self):
        prev = last_save = time.monotonic()
        while True:
            time.sleep(1)
            now = time.monotonic()
            dt, prev = now - prev, now
            exe, title, pid = foreground_app()
            if pid != os.getpid():
                self.app, self.focus = (exe, title, pid), foreground_center()
            if not self.awake:  # started with Windows: wait for a game, without tracking or looking
                if steam_app(self.app[0]) or app_name(*self.app[:2]) in [g.lower() for g in config.GAMES]:
                    self.wake_up()
                continue
            afk = idle_seconds() > config.AFK_AFTER
            if afk:
                self.streak_start = now  # a real break resets the no-break clock
            else:
                self.mem.tick(app_name(*self.app[:2]), dt)
            if now - last_save > 30:
                self.mem.save()
                last_save = now
            quiet = now - self.last_spoke
            broke = not config.LOCAL_MODEL and config.MONTHLY_BUDGET and self.mem.spent() >= config.MONTHLY_BUDGET
            talking_to_him = self.ears.recording or any(listener.active() for listener in self.listeners)
            if afk or broke or self.busy or not self.jobs.empty() or self.voice.busy() or talking_to_him or quiet < config.LOOK_COOLDOWN:
                continue
            start, end = config.BEDTIME
            hour = datetime.now().hour
            late = start <= hour < end if start < end else (hour >= start or hour < end)
            if not self.muted and now - self.last_nag > config.NAG_EVERY * 60 and (late or now - self.streak_start > config.BREAK_AFTER * 60):
                self.last_nag = now
                self.jobs.put(("nag", None))
                continue
            if self.paused or quiet < config.LOOK_COOLDOWN * (2 if self.muted else 1):
                continue
            thumb = self.eyes.thumb()
            if self.base_thumb is None:
                self.base_thumb = thumb
            if changed(self.base_thumb, thumb, config.CHANGE_THRESHOLD):
                self.jobs.put(("change", None))
            elif quiet > config.QUIET_ROAST and not self.muted:
                self.jobs.put(("lore" if random.random() < 0.3 else "quiet", None))


def main():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    mutex = k32.CreateMutexW(None, False, "Local\\VornCompanion")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS: one Vorn at a time (two would double your API bill)
        user32.MessageBoxW(None, f"{config.NAME} is already running. Look for his icon in the system tray.", config.NAME, 0x40)
        return
    waiting = "--wait-for-game" in sys.argv
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    bridge = Bridge()
    comp = Companion(bridge, waiting)

    def update_skips(*_):  # Qt keeps each display's real top-left corner, which is how the capture library names it too
        comp.eyes.skip = {(s.geometry().x(), s.geometry().y()) for s in app.screens()
                          if any(n.lower() in s.name().lower() for n in config.SKIP_DISPLAYS)}

    update_skips()
    app.screenAdded.connect(update_skips)
    app.screenRemoved.connect(update_skips)
    overlay = Overlay(comp.voice, comp.mem.d.get("overlay_pos"), lambda: comp.mem.d["respect"], comp.mem.spent)
    set_clickthrough(overlay, True)  # also creates his window, even while he's hidden waiting for a game

    def set_stream(on):  # off = WDA_EXCLUDEFROMCAPTURE: hidden from OBS, recordings and his own screenshots
        comp.show_on_stream = on
        if not user32.SetWindowDisplayAffinity(int(overlay.winId()), 0 if on else 0x11):
            logging.warning("could not change overlay capture visibility")
        with comp.mem.lock:
            comp.mem.d["show_on_stream"] = on
        comp.mem.save()

    set_stream(comp.show_on_stream)
    if not waiting:
        overlay.show()
    chat = ChatBox(lambda text: comp.jobs.put(("ask", text)))

    def toggle_move():
        pos = overlay.toggle_move()
        if pos:
            with comp.mem.lock:
                comp.mem.d["overlay_pos"] = pos
            comp.mem.save()

    def restart():
        k32.CloseHandle(mutex)  # let the new copy start
        subprocess.Popen([str(PYTHONW if PYTHONW.exists() else sys.executable), str(HERE / "main.py")], cwd=HERE)
        app.quit()

    def weekly():
        with comp.mem.lock:
            page = highlights.build(comp.mem.d, HALL)
        os.startfile(page)

    def export_memory():
        path, _ = QFileDialog.getSaveFileName(None, f"Export {config.NAME}'s memory",
                                              str(Path.home() / f"{config.NAME} memory {datetime.now():%Y-%m-%d}.zip"), "Zip (*.zip)")
        if path:
            comp.mem.save()
            transfer.export_memory(HERE, path)
            overlay.note("(memory exported: copy the .zip to your other PC and import it there)")

    def import_memory():
        path, _ = QFileDialog.getOpenFileName(None, f"Import {config.NAME}'s memory", str(Path.home()), "Zip (*.zip)")
        if not path or QMessageBox.question(None, "Import memory", f"Replace {config.NAME}'s memory with this one? Your current memory "
                                            "is backed up in his folder first, then he restarts.") != QMessageBox.Yes:
            return
        comp.mem.save()  # the backup gets everything up to now
        with comp.mem.lock:
            comp.mem.frozen = True  # from here until the restart, nothing may save over the imported memory
        try:
            transfer.import_memory(HERE, path)
        except Exception as e:  # not a zip, not his, unreadable
            comp.mem.frozen = False
            QMessageBox.warning(None, "Import memory", f"That file isn't a memory export from {config.NAME}.\n\n{e}")
            return
        restart()

    settings = SettingsWindow(restart, comp.voice)
    windows = {}

    def open_costs():
        windows["costs"] = CostsWindow(comp.mem)  # built fresh each time, so the numbers are current
        windows["costs"].show()
        windows["costs"].raise_()
        windows["costs"].activateWindow()

    def open_memories():
        windows["memories"] = MemoriesWindow(comp.mem, config.NAME)  # fresh each time: shows what they remember now
        windows["memories"].show()
        windows["memories"].raise_()
        windows["memories"].activateWindow()

    bridge.say.connect(overlay.show_line)
    bridge.note.connect(overlay.note)
    bridge.chat.connect(lambda: comp.awake and chat.popup(overlay))
    bridge.move.connect(toggle_move)
    bridge.awake.connect(overlay.show)

    tray = QSystemTrayIcon(QIcon(QPixmap.fromImage(overlay.char.render(0.3, bust=True))), app)
    menu = QMenu()
    spend = menu.addAction("")
    spend.triggered.connect(open_costs)
    wake = menu.addAction("Wake up now")
    wake.setVisible(waiting)
    wake.triggered.connect(lambda: (comp.wake_up(), wake.setVisible(False)))
    bridge.awake.connect(lambda: wake.setVisible(False))
    menu.addSeparator()
    menu.addAction(f"Move / lock ({config.KEY_MOVE.upper()})").triggered.connect(toggle_move)
    menu.addAction(f"Pause / resume watching ({config.KEY_PAUSE.upper()})").triggered.connect(lambda: comp.toggle_pause())
    menu.addAction(f"Shut-up mode ({config.KEY_MUTE.upper()})").triggered.connect(lambda: comp.toggle_mute())
    stream = menu.addAction("Show me on stream / recordings")
    stream.setCheckable(True)
    stream.setChecked(comp.show_on_stream)
    stream.toggled.connect(set_stream)
    menu.addSeparator()
    menu.addAction("Open Hall of Shame").triggered.connect(lambda: (HALL.mkdir(exist_ok=True), os.startfile(HALL)))
    menu.addAction("Open this week's highlights").triggered.connect(weekly)
    menu.addAction("Open battle reports").triggered.connect(lambda: REPORTS.exists() and os.startfile(REPORTS))
    menu.addSeparator()
    menu.addAction("Memories (what they remember about you)...").triggered.connect(open_memories)
    menu.addAction("Export memory (to move him to another PC)...").triggered.connect(export_memory)
    menu.addAction("Import memory...").triggered.connect(import_memory)
    menu.addSeparator()
    characters = menu.addMenu("Character")
    for preset in presets():
        pick = characters.addAction(preset.title())
        pick.setCheckable(True)
        pick.setChecked(preset == config.PRESET and not config.DUO)
        pick.triggered.connect(lambda _=False, p=preset: (set_setting("PRESET", p), set_setting("DUO", False), restart())
                               if p != config.PRESET or config.DUO else None)
    both = characters.addAction("Both (duo mode)")
    both.setCheckable(True)
    both.setChecked(config.DUO)
    both.triggered.connect(lambda: (set_setting("DUO", True), restart()) if not config.DUO else None)
    camera = Camera(overlay, lambda: comp.focus)  # the Discord camera
    cam_menu = menu.addMenu("Discord camera")
    cam_picks = {}

    def set_camera(key, value):
        set_setting(key, value)
        setattr(config, key, value)
        for (k, v), action in cam_picks.items():
            action.setChecked(getattr(config, k) == v)
        camera.stop()
        camera.start()
        QTimer.singleShot(3000, lambda: camera.error and overlay.note(f"(Discord camera: {camera.error})"))

    for key, values in (("CAMERA", ("off", "current", "both")), ("CAMERA_BACKGROUND", BACKGROUNDS)):
        for value in values:
            label = {"off": "Off", "current": f"On: {config.NAME}", "both": "On: Vorn and Mika", "dark": "Background: dark",
                     "green": "Background: green screen", "game": "Background: your game", "webcam": "Background: your webcam"}[value]
            cam_picks[key, value] = cam_menu.addAction(label)
            cam_picks[key, value].setCheckable(True)
            cam_picks[key, value].setChecked(getattr(config, key) == value)
            cam_picks[key, value].triggered.connect(lambda _=False, k=key, v=value: set_camera(k, v))
        cam_menu.addSeparator()
    camera.start()
    for who, dresser in zip(overlay.names, overlay.chars):  # each one's wardrobe (both in duo mode), switched live
        outfits = menu.addMenu("Outfit" if len(overlay.chars) == 1 else f"{who}'s outfit")
        choices = {}

        def wear(name, dresser=dresser, choices=choices):
            set_setting(dresser.OUTFIT_SETTING, name)
            setattr(config, dresser.OUTFIT_SETTING, name)
            dresser.outfit = name if name in dresser.OUTFITS else random.choice(sorted(dresser.OUTFITS))  # "random": one now too
            for n, action in choices.items():
                action.setChecked(n == name)

        for name in sorted(dresser.OUTFITS) + ["random"]:
            choices[name] = outfits.addAction("Surprise me (a new one each launch)" if name == "random" else name.title())
            choices[name].setCheckable(True)
            choices[name].setChecked(name == getattr(config, dresser.OUTFIT_SETTING))
            choices[name].triggered.connect(lambda _=False, n=name, w=wear: w(n))
    menu.addAction("Settings...").triggered.connect(lambda: (settings.show(), settings.raise_(), settings.activateWindow()))
    boot = menu.addAction("Start with Windows (wakes up when a game starts)")
    boot.setCheckable(True)
    boot.setChecked(autostart_on())
    boot.toggled.connect(set_autostart)
    menu.addAction(f"About {APP}...").triggered.connect(lambda: QMessageBox.about(None, f"About {APP}", (
        f"<h3>{APP} {VERSION}</h3><p>Your trash-talking gaming companion.</p><p>Made by <b>{AUTHOR}</b>.</p>"
        "<p>Brain: Claude by Anthropic. Voices: Kokoro on your PC, or Microsoft online voices. "
        "Hearing: Whisper on your PC.</p><p><a href='https://github.com/DivxPlays/vorn'>github.com/DivxPlays/vorn</a></p>")))
    menu.addAction("Quit").triggered.connect(app.quit)
    menu.aboutToShow.connect(lambda: spend.setText(
        f"Costs: ${comp.mem.spent():.2f}" + (f" of ${config.MONTHLY_BUDGET}" if config.MONTHLY_BUDGET else "") + " this month..."))
    tray.setContextMenu(menu)
    tray.setToolTip(f"{config.NAME}" + (" (waiting for a game)" if waiting else "")
                    + f": hold {config.KEY_TALK.upper()} or say \"Hey {config.NAME}\" to talk, {config.KEY_TYPE.upper()} type, "
                    f"{config.KEY_LOOK.upper()} look, {config.KEY_PAUSE.upper()} pause, {config.KEY_MUTE.upper()} shut up")
    tray.show()

    keyboard.on_press_key(config.KEY_TALK, lambda e: comp.talk_down())
    keyboard.on_release_key(config.KEY_TALK, lambda e: comp.talk_up())
    keyboard.add_hotkey(config.KEY_TYPE, bridge.chat.emit)
    keyboard.add_hotkey(config.KEY_LOOK, lambda: comp.jobs.put(("look", None)))
    keyboard.add_hotkey(config.KEY_PAUSE, comp.toggle_pause)
    keyboard.add_hotkey(config.KEY_MOVE, bridge.move.emit)
    keyboard.add_hotkey(config.KEY_MUTE, comp.toggle_mute)
    app.aboutToQuit.connect(comp.mem.save)
    app.aboutToQuit.connect(camera.stop)
    app.aboutToQuit.connect(overlay.ducker.restore)
    app.aboutToQuit.connect(keyboard.unhook_all)
    comp.start()
    code = app.exec()  # the aboutToQuit handlers above have saved memory and restored volumes by now
    logging.shutdown()
    os._exit(code)  # skip Python's teardown, which can destroy Qt objects in an order that aborts the process


if __name__ == "__main__":
    main()
