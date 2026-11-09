"""Vorn: an AI gaming companion that watches your screen, talks, gives hints and trash-talks you."""
import ctypes
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
from costs_ui import CostsWindow  # noqa: E402
from character import H as CH, HEAD_Y, W as CW, Vorn, tier_for  # noqa: E402
from memory import Memory, app_name, fmt, foreground_app, foreground_center, idle_seconds, steam_app, steam_hours  # noqa: E402
from senses import Ducker, Ears, Eyes, Voice, WakeListener, changed, cue, game_display, save_clip, save_moment  # noqa: E402
from settings_ui import SettingsWindow  # noqa: E402

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
    "change": "Something changed on the player's screen. React to what you see.",
    "quiet": "You've been quiet a while. Look at the screen and trash-talk the player: their play, their hours, or their idling.",
    "lore": "You've been quiet a while. Tell a very short story from your own conquests (stay consistent with your past), "
            "then turn it into a jab at the player.",
    "look": "The player pressed the look hotkey. Comment on what they're looking at, or give a hint about it.",
    "nag": "It's late, or the player has gone a long time without a break (see the local time and break time in the stats). "
           "Nag them to take a break or go to sleep, as a roast.",
    "breakdown": "The player just lost. These screenshots are from the last minute or so, oldest first. Break down what went "
                 "wrong, specific and tactical, still a roast. Up to 3 sentences, under 50 words.",
}
AUTO = {"change", "quiet", "lore", "nag", "breakdown"}  # jobs he starts himself; they stop when the budget runs out
SEARCH_ASKED = re.compile(r"\b(search|look (it |that |this )?up|google|wiki|guide|walkthrough)", re.I)
BUDGET_NEWS = {1: "Also tell them they've burned through 80% of this month's budget on you, so you're switching to cheap mode.",
               2: "Also tell them this month's budget is gone, so from now on you only speak when they talk to you."}
SOUNDS = {"smug": ["Heh.", "Hmph."], "angry": ["Hmph!", "Argh!"], "laugh": ["Ha ha ha!", "Hah!"],
          "disgusted": ["Ugh.", "Hmph."], "surprised": ["What?!", "Huh?!"], "idle": ["Hmph."]}
ALREADY_A_SOUND = re.compile(r"^(hmph|heh|hah?|ugh|argh|what|huh|tch)\b", re.I)


class Bridge(QObject):
    """Signals that carry events from background threads to the UI thread."""
    say = Signal(str, str, object, str)  # mood, line, audio samples (or None), game event
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
        self.char, self.voice, self.respect, self.spent, self.ducker = Vorn(), voice, respect, spent, Ducker()
        self.text, self.shown, self.cps, self.hide_at = "", 0.0, 40.0, 0.0
        self.moving, self.grab_at = False, QPoint()
        self.left = "left" in config.CORNER  # True = bubble on his right
        self.resize(int(BUBBLE_W + CW * config.SCALE), int(CH * config.SCALE) + 26)  # + a strip under his feet for the cost tag
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
        char_x = self.x() + (0 if self.left else BUBBLE_W) + CW * s / 2
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

    def show_line(self, mood, line, audio, event="none"):
        self.char.set_mood(mood)
        if event in ("win", "epic"):
            self.char.flare()
        elif event == "menu":
            self.char.roll()
        elif event == "loss":
            self.char.slump()
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
        self.char.afk = idle_seconds() > 60  # yawns and bored eyes while you're away
        self.char.toward = 1.0 if self.left else -1.0  # the rest of your screen is on his bubble side
        self.char.tier = tier_for(self.respect())  # his gear upgrades as you earn respect
        self.char.step(dt, self.voice.level())
        if self.ducker.saved and not self.voice.busy():
            self.ducker.restore()
        self.shown += dt * self.cps
        if self.text and now > self.hide_at:
            self.text = ""
            self.char.set_mood("idle")
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
        g.save()
        g.translate(0 if self.left else BUBBLE_W, 0)
        g.scale(config.SCALE, config.SCALE)
        self.char.paint(g)
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
        center = (0 if self.left else BUBBLE_W) + CW * config.SCALE / 2
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
        x = CW * s + 14 if self.left else BUBBLE_W - bw - 14
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

    def start(self):
        for target in (self.worker, self.watcher, self.ears.model):  # ears.model preloads Whisper
            threading.Thread(target=target, daemon=True).start()
        if self.awake:
            self.wake_up()

    def wake_up(self):
        """Start talking and listening: right away, or once a game starts if he launched with Windows."""
        if self.started:
            return
        self.started = self.awake = True
        if config.WAKE_WORD:  # the mic only opens once he's awake
            threading.Thread(target=WakeListener(self.ears, self.voice, self.wake_heard).run, daemon=True).start()
        self.bridge.awake.emit()
        self.jobs.put(("start", None))

    def wake_heard(self, text):
        if text is None:  # just "Hey Vorn": he's listening for the question
            cue("on")
            self.bridge.note.emit("(listening...)")
        else:
            self.jobs.put(("ask", text))

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
        if self.client is None:
            return self.speak("disgusted", "You forgot my API key, fool. Put it in api underscore key dot text.")
        level, crossed = self.mem.budget_level()
        if level == 2 and kind in AUTO and not crossed:
            return  # budget used up: he only answers when you talk to him
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
        situation = f'The player says to you: "{arg}". Answer them.' if kind == "ask" else SITUATIONS[kind]
        if crossed:
            situation += " " + BUDGET_NEWS[level]
        context = self.mem.context(app, title, steam_hours(exe), time.monotonic() - self.streak_start)
        context += ("\n(You are visible in a corner of the screenshots, with your speech bubble. Ignore yourself.)"
                    if self.show_on_stream else "\n(Your own overlay is hidden from the screenshots.)")
        smart = kind in ("ask", "look", "breakdown") and level == 0  # cheap mode (80% of budget): Haiku only, no web search
        model = config.SMART_MODEL if smart else config.MODEL
        search = smart and kind == "ask" and bool(SEARCH_ASKED.search(arg))  # having the tool costs ~2 cents even unused
        out, spent = brain.think(self.client, model, context, self.recent, situation, jpegs, search=search)
        self.mem.spend(spent, kind)
        logging.info("%s ($%.4f) -> %s", kind, spent, out)
        tier = tier_for(self.mem.d["respect"])
        self.mem.record(app, out)
        event = "epic" if tier_for(self.mem.d["respect"]) > tier else out.get("event", "none")  # new gear: aura flare
        shame = None
        if out.get("save_moment") and shot and time.monotonic() - self.last_shame > 60:
            self.last_shame = time.monotonic()
            shame = save_moment(shot[2], self.focus, out["line"], HALL)
        if out.get("event") == "loss" and kind != "breakdown" and not self.muted and time.monotonic() - self.last_breakdown > 180:
            self.last_breakdown = time.monotonic()
            self.jobs.put(("breakdown", None))
        self.mem.save()
        if self.muted and kind == "change":  # shut-up mode: he keeps score, he just keeps it to himself
            if shame:
                self.hall_entry(shame, out["line"], title or app, self.synth(out["line"]))
            return
        if kind == "ask":
            self.recent.append(f"Player: {arg}")
            self.mem.line(f"Player: {arg}")
        self.recent = (self.recent + [f"You: {out['line']}"])[-12:]
        self.mem.line(f"You: {out['line']}")
        line, audio = self.speak(out.get("mood", "idle"), out["line"], event)
        if shame:
            self.hall_entry(shame, line, title or app, audio)

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

    def speak(self, mood, line, event="none"):
        if random.random() < 0.4 and not ALREADY_A_SOUND.match(line):  # a scoff, laugh or grunt first
            line = f"{random.choice(SOUNDS.get(mood, ['Hmph.']))} {line}"
        audio = self.synth(line)
        self.bridge.say.emit(mood, line, audio, event)
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
            broke = config.MONTHLY_BUDGET and self.mem.spent() >= config.MONTHLY_BUDGET
            if afk or broke or self.busy or not self.jobs.empty() or self.voice.busy() or self.ears.recording or quiet < config.LOOK_COOLDOWN:
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
    menu.addAction("Export memory (to move him to another PC)...").triggered.connect(export_memory)
    menu.addAction("Import memory...").triggered.connect(import_memory)
    menu.addAction("Settings...").triggered.connect(lambda: (settings.show(), settings.raise_(), settings.activateWindow()))
    boot = menu.addAction("Start with Windows (wakes up when a game starts)")
    boot.setCheckable(True)
    boot.setChecked(autostart_on())
    boot.toggled.connect(set_autostart)
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
    app.aboutToQuit.connect(overlay.ducker.restore)
    app.aboutToQuit.connect(keyboard.unhook_all)
    comp.start()
    code = app.exec()  # the aboutToQuit handlers above have saved memory and restored volumes by now
    logging.shutdown()
    os._exit(code)  # skip Python's teardown, which can destroy Qt objects in an order that aborts the process


if __name__ == "__main__":
    main()
