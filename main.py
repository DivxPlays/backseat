"""Vorn: an AI gaming companion that watches your screen, talks, gives hints and trash-talks you."""
import ctypes
import difflib
import functools
import json
import logging
import math
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
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
APP, VERSION, AUTHOR = "Backseat", "1.2.0", "DivxPlays"  # x.y.Z fixes, x.Y.0 features; bumped when the user agrees
RUNNING = __name__ == "__main__"  # (imported by the self-checks or make_images.py: no log file, no crash box)
if RUNNING:
    logging.basicConfig(filename=HERE / "companion.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
for noisy in ("httpx", "httpx2", "huggingface_hub", "faster_whisper", "comtypes"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


def _crash(*exc):  # he runs without a console, so a crash must be visible somewhere
    logging.critical("crash", exc_info=exc)
    ctypes.windll.user32.MessageBoxW(None, f"{exc[1]!r}\n\nDetails are in companion.log next to main.py.", f"{APP} crashed", 0x10)


if RUNNING:
    sys.excepthook = _crash
    threading.excepthook = lambda a: logging.critical("thread crash", exc_info=(a.exc_type, a.exc_value, a.exc_traceback))

import anthropic  # noqa: E402
import keyboard  # noqa: E402
from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QLineEdit, QMenu, QMessageBox, QSystemTrayIcon, QWidget  # noqa: E402

import brain  # noqa: E402
import commands  # noqa: E402
import character  # noqa: E402
import coaching  # noqa: E402
import config  # noqa: E402
import grudges  # noqa: E402
import highlights  # noqa: E402
import music  # noqa: E402
import holidays  # noqa: E402
import transfer  # noqa: E402
import unlocks  # noqa: E402
from camera import BACKGROUNDS, REACT, Camera  # noqa: E402
import sfx  # noqa: E402
import voices  # noqa: E402
from costs_ui import CostsWindow  # noqa: E402
from memories_ui import MemoriesWindow  # noqa: E402
from character import H as CH, HEAD_Y, W as CW, character_class, make_character, tier_for  # noqa: E402
from memory import (SHAME, Memory, app_name, fmt, foreground_app, foreground_center, foreground_fullscreen,  # noqa: E402
                    gpu_load, idle_seconds, is_game, steam_app, steam_hours, week as memory_week)
from senses import (SR, Ducker, Ears, Eyes, Voice, WakeListener, changed, cue, game_display, listen_source_ok, new_clip,  # noqa: E402
                    save_clip, save_moment, videos_folder)
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
RUN_KEY, RUN_NAME = r"Software\Microsoft\Windows\CurrentVersion\Run", "BackseatCompanion"
OLD_RUN_NAMES = ("VornCompanion",)  # the app was called Vorn before
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
    "music": 'The player just put on "{song}" by {artist} on Spotify. React to the song or their taste in music, in one short '
             "sentence (under 15 words), in character. If you know something real about it (see Music above), use it.",
    "look": "The player pressed the look hotkey. Comment on what they're looking at, or give a hint about it.",
    "nag": "It's late, or the player has gone a long time without a break (see the local time and break time in the stats). "
           "Nag them to take a break or go to sleep, as a roast.",
    "breakdown": "The player just lost. These screenshots are from the last minute or so, oldest first. Break down what went "
                 "wrong, specific and tactical, still a roast. Up to 3 sentences, under 50 words.",
}
AUTO = {"change", "quiet", "lore", "nag", "breakdown", "music"}  # jobs he starts himself; they stop when the budget runs out
BANTER = ([1, 2, 3, 4, 5, 6], [2, 4, 3, 2, 1, 1])  # duo mode: how many lines an exchange runs (weights): usually short,
# now and then a real argument. The small local model goes up to LOCAL_BANTER (each line is a call of its own)
LOCAL_BANTER = 4
CHECKED = {"win", "loss", "death", "epic", "fail"}  # the local model naming one of these gets Claude to double-check
CHECK_GAP = 120  # seconds: double-checks at most this often (the local model calls every kill a win)
PROFILE_AGE = 90  # days before a game profile is looked up again
GAME_GAP, ANSWER_TIME = 480, 20
BOUNTIES = {"easy": (5, 2, "a decent match does it"), "hard": (8, 4, "it takes a good match"),  # challenges: respect won
            "brutal": (12, 6, "only their best match does it")}  # if done, lost if failed or dodged; how hard
CHALLENGE_TIME = 1800  # s: a challenge not done by then was dodged
TRIVIA_TOPICS = ("map", "mode", "campaign level or mission", "class or character", "weapon", "map", "fact")  # (picked at random)  # mini-games: at most every 8 minutes; how long the mic takes your trivia answer
MUSIC_GAP, LOOKUP_GAP = 300, 600  # Spotify: a comment on a new song at most every 5 minutes, a web lookup every 10
COMEBACK_SAYS = ('{a} (the other one in your window) just said: "{line}". Fire back at {a} in one short sentence (under 15 '
                 "words), in your own style: roast what {a} said, or take the player's side against {a}. Use your own words: "
                 "never repeat or rephrase {a}'s sentence. Your past is your own: never tell {a}'s stories or claim {a}'s "
                 "deeds as yours.")
BLOODFIRE = {"bloodfire": 8, "bloodfire-max": 25}  # seconds he burns: a big play, or reaching 100 respect


ECHO = 0.45  # within one exchange, a line sharing more of its words (in order) with an earlier one is a copy


def repeats(line, recent, limit=0.6):
    """True if line is nearly word for word one of their last few lines ("You: ..." or, in duo mode, "You (Mika): ...")."""
    words = re.findall(r"[a-z']+", line.lower())
    return any(difflib.SequenceMatcher(None, words, re.findall(r"[a-z']+", said.split(": ", 1)[-1].lower())).ratio() > limit
               for said in recent[-8:] if said.startswith("You"))


def echo(heard, recent):
    """True when what the Discord ear heard is mostly one of their own recent lines ("You: ..." / "You (Mika): ...")
    coming back through the call's audio, not a friend talking."""
    words = set(re.findall(r"[a-z']+", heard.lower())) - {"hey", "hay", "hi", "a", "ok", "okay", "oh", "ooh"}
    return len(words) >= 2 and any(len(words & set(re.findall(r"[a-z']+", said.split(": ", 1)[-1].lower()))) >= 0.7 * len(words)
                                   for said in recent[-8:] if said.startswith("You"))


def squad_line(rows):
    """A squad board as words: "Mike 7 (death 3, roasted 2, talked 5), Sam 1 (...)"."""
    return ", ".join(f"{f.title()} {pts} (" + ", ".join(f"{k} {n}" for k, n in sorted(r.items())) + ")" for f, pts, r in rows)


def award_due(mem, today=None):
    """Last week's worst player, once: (their name, last week's board) if there was a squad last week, someone ended up
    with shame points, and it hasn't been announced; else None. Announcing marks it."""
    last = memory_week((today or datetime.now().date()) - timedelta(days=7))
    rows = mem.squad_board(last)
    with mem.lock:
        if not rows or rows[0][1] <= 0 or mem.d.setdefault("squad", {}).get("announced") == last:
            return None
        mem.d["squad"]["announced"] = last
    return rows[0][0], rows


def fresh_turns(turns, recent):
    """An exchange up to the first line that copies one they said lately or one earlier in it (the small local model
    echoes the line it answers with the name swapped, and a line after a copy answers the copy)."""
    kept = []
    for t in turns:
        if repeats(t[2], recent) or repeats(t[2], [f"You: {k[2]}" for k in kept], ECHO):
            break
        kept.append(t)
    return kept


def addressed(text, wake_of):
    """Duo mode: which character the speaker called by name first ({name: their wake names}), or None."""
    hits = [(m.start(), name) for name, names in wake_of.items()
            if (m := re.search(r"\b(?:" + "|".join(map(re.escape, names)) + r")\b", text, re.I))]
    return min(hits)[1] if hits else None


@functools.lru_cache(maxsize=16)
def preset_name(preset):
    """A preset's character name ("mika" -> "Mika")."""
    try:
        return json.loads((config.PRESETS / f"{preset}.json").read_text(encoding="utf-8"))["NAME"]
    except (OSError, ValueError, KeyError):
        return preset.title()


def minigame_due(now, menu_at, last_game):
    """Time for a mini-game? You're in a menu (seen in the last 90 s) and there hasn't been one for GAME_GAP; checked
    every second, so a small chance each time makes it start after a while, not the moment you open a menu."""
    return now - menu_at < 90 and now - last_game > GAME_GAP and random.random() < 0.02


def judge_note(trivia):
    """What the one who asked needs to judge your trivia answer."""
    who = trivia["who"]
    return (f' (Mini-game: {who} just asked them a trivia question: "{trivia["q"]}" The right answer: "{trivia["a"]}". What '
            f"they just said is their answer. {who} judges it, in character: if it's right (close enough counts), admit it "
            "grudgingly and set respect \"up\"; if it's wrong, roast them, tell them the answer, and set respect \"down\".)")


def needs_check(level, since, event=None):
    """Free mode: should Claude take this comment and keep score? Every CHECK_EVERY minutes, or (at most every CHECK_GAP s)
    when the local model thinks something big happened. Never once the month's budget is used up (level 2)."""
    if level >= 2 or not config.CHECK_EVERY:
        return False
    return since > config.CHECK_EVERY * 60 or (event in CHECKED and since > CHECK_GAP)


def turns_of(out, names):
    """What to say, as [(speaker, mood, line)]: one line for a solo character, a short exchange in duo mode."""
    if "turns" in out:
        turns = [(t["speaker"], t.get("mood", "idle"), t["line"].strip()) for t in out["turns"]
                 if t.get("speaker") in names and t.get("line", "").strip()]
        return turns[:6] or [(names[0], "idle", "")]
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
APOLOGY = re.compile(r"\b(sorry|apologi[sz]e|my bad|forgive me)\b", re.I)  # ends a grudge
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
    wear = Signal(int, str)  # voice command: which character (0 = the current one) puts on which outfit
    switch = Signal(str)  # voice command: switch to a preset, or "both" (restarts him)


def set_clickthrough(widget, on):
    """Locked = mouse clicks pass straight through him to the game (WS_EX_TRANSPARENT). Either way clicking him never
    takes focus from your game (WS_EX_NOACTIVATE)."""
    hwnd = int(widget.winId())
    style = user32.GetWindowLongPtrW(hwnd, -20) | 0x08000000  # GWL_EXSTYLE
    user32.SetWindowLongPtrW(hwnd, -20, (style | 0x20) if on else (style & ~0x20))


def autostart_on():
    for name in (RUN_NAME, *OLD_RUN_NAMES):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                winreg.QueryValueEx(k, name)
            return True
        except OSError:
            pass
    return False


def set_autostart(on):
    """Start with Windows, hidden, and wake up when a game starts."""
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, f'"{PYTHONW}" "{HERE / "main.py"}" --wait-for-game')
        for name in OLD_RUN_NAMES + (() if on else (RUN_NAME,)):  # (an entry from when the app was called Vorn goes too)
            try:
                winreg.DeleteValue(k, name)
            except FileNotFoundError:
                pass


class Flyer(QWidget):
    """One character thrown out of the overlay, in a window of their own (in duo mode the other one stays put)."""

    def __init__(self, char, at):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.char, self.angle = char, 0.0  # the physics: where their middle is (center) and how far they've turned
        self.cw, self.ch = CW * config.SCALE, CH * config.SCALE
        self.side = int(self.ch * 1.15)  # square, with room to spin and flail
        self.resize(self.side, self.side)
        self.center = QPointF(at.x() + self.cw / 2, at.y() + self.ch / 2)
        self.place()
        set_clickthrough(self, True)  # the overlay keeps the mouse while you drag
        self.show()

    def place(self):
        self.move(int(self.center.x() - self.side / 2), int(self.center.y() - self.side / 2))

    def half(self):
        """Half the width and height they take up at this angle (for bounces, and to lie on the floor)."""
        a = math.radians(self.angle)
        c, s = abs(math.cos(a)), abs(math.sin(a))
        return (c * self.cw * 0.6 + s * self.ch) / 2, (s * self.cw * 0.6 + c * self.ch) / 2  # (their body is ~60% of the width)

    def paintEvent(self, _):
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing)
        g.translate(self.side / 2, self.side / 2)
        g.rotate(self.angle)
        g.translate(-self.cw / 2, -self.ch / 2)
        g.scale(config.SCALE, config.SCALE)
        self.char.paint(g)
        g.end()


class Overlay(QWidget):
    poked = Signal(int, str, bool)  # Ctrl+click or a throw: (which one, "poke"/"poke head"/"poke annoyed"/"grabbed"/"thrown", say a line)
    GRAVITY, HEAD = 2600, 115  # thrown: px/s² of fall; pokes above this (drawing units) are on the head

    def __init__(self, voice, saved_pos, respect, spent):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.char, self.voice, self.respect, self.spent, self.ducker = make_character(config.CHARACTER, config.COLORS), voice, respect, spent, Ducker()
        self.text, self.shown, self.cps, self.hide_at = "", 0.0, 40.0, 0.0
        self.moving, self.grab_at = False, QPoint()
        self.left = "left" in config.CORNER  # True = bubble on his right
        other = brain.partner()
        self.chars = [self.char] + ([make_character(other["CHARACTER"], other.get("COLORS"))] if other else [])  # duo mode
        self.names = [config.NAME] + ([other["NAME"]] if other else [])
        self.speaking = 0  # which of them is talking (their mouth follows the voice)
        self.later = {}  # {character index: (when, mood)}: duo mode, each one changes face in their own time
        self.pokeable = False  # Ctrl held: clicks on them land on them instead of your game
        self.grab = None  # Ctrl+drag: [which one, grab offset, recent (time, position) for the throw's speed, dragged yet]
        self.flight = None  # thrown: [vx, vy in px/s, spin in degrees/s] while they fly
        self.flyer = None  # the thrown one's own window (see Flyer)
        self.phase, self.phase_t0, self.rest = None, 0.0, 0.0  # "drag", "fly", "down" (in a heap), "up", "home"
        self.scream = None  # a throw: scream(i) -> (audio, text), set by main (the companion has them ready)
        self.pokes, self.jolts, self.last_said, self.thrown_by = deque(maxlen=12), {}, 0.0, 0
        self.acts, self.yawns, self.idle_sound = {}, {}, {}  # sound effects: idle animation and yawn seen, last idle sound
        self.hush = lambda: False  # shut-up mode: no idle sounds (set by the companion)
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
        self.pokeable = False
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

    def char_at(self, x):
        """Which character is at x (window coordinates), or None."""
        i = int((x - (0 if self.left else BUBBLE_W)) // (CW * config.SCALE))
        return i if 0 <= i < len(self.chars) else None

    def mousePressEvent(self, e):
        if self.moving:
            self.grab_at = e.globalPosition().toPoint() - self.pos()
        elif self.pokeable and e.button() == Qt.LeftButton and self.char_at(e.position().x()) is not None and not self.flyer:
            p = e.globalPosition()
            self.grab = [self.char_at(e.position().x()), p.toPoint() - self.pos(), [(time.monotonic(), p)], False]

    def mouseMoveEvent(self, e):
        if self.moving and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self.grab_at)
        elif self.grab:
            i, offset, trail, dragged = self.grab
            p = e.globalPosition()
            if not dragged and (p - trail[0][1]).manhattanLength() > 12:  # a drag, not a poke: grabbed
                self.grab[3] = dragged = True
                self.flyer, self.thrown_by, self.phase = Flyer(self.chars[i], self.slot(i)), i, "drag"  # into your hand
                self.grab[1] = offset = trail[0][1] - self.flyer.center
                self.chars[i].set_mood("surprised")
                self.effect(i, sfx.MOMENTS["grabbed"])
                self.react(i, "grabbed")
            if dragged:  # they dangle from your hand: tilting against the motion, limbs flailing with the speed
                last_t, last_p = trail[-1]
                vx = (p.x() - last_p.x()) / max(time.monotonic() - last_t, 1 / 120)
                self.flyer.center = p - offset
                self.flyer.angle += (max(-35.0, min(35.0, -vx * 0.03)) - self.flyer.angle) * 0.25
                self.flyer.place()
                self.chars[i].rag = min(1.0, abs(vx) / 900 + 0.35)
            self.grab[2] = (trail + [(time.monotonic(), p)])[-6:]

    def mouseReleaseEvent(self, e):
        if not self.grab:
            return
        i, _, trail, dragged = self.grab
        self.grab = None
        if not dragged:
            return self.poke(i, e.position().y())
        (t0, p0), (t1, p1) = trail[0], trail[-1]
        dt = max(t1 - t0, 1 / 60)
        vx, vy = (p1.x() - p0.x()) / dt, (p1.y() - p0.y()) / dt  # let go: thrown at that speed, spinning with it
        self.flight, self.phase, self.chars[i].rag = [vx, vy, max(-720.0, min(720.0, vx * 0.45))], "fly", 1.0
        got = self.scream(i) if self.scream else None
        if got:  # and they scream
            self.show_line("surprised", got[1], got[0], "none", self.names[i])

    def effect(self, i, kinds):
        """Character i makes a sound (a grunt, a giggle: sfx.py), unless one of them is saying a line."""
        clip = None if self.voice.busy() and not self.voice.effect else sfx.pick(self.chars[i].BUILD, kinds)
        if clip is not None:
            self.speaking = i  # (their mouth moves with it)
            self.voice.play(clip, effect=True)
        return clip is not None

    def idle_sounds(self, now):
        """A sigh, yawn, chuckle or giggle with some idle animations, and a yawn when they yawn while you're away; at
        most one every IDLE_GAP s each, none in shut-up mode."""
        for i, char in enumerate(self.chars):
            act, yawn = char.act, char.yawn_t0
            started = act if act and act != self.acts.get(i) else "nod off" if yawn != self.yawns.get(i, yawn) else None
            self.acts[i], self.yawns[i] = act, yawn
            if (started in sfx.IDLES and now - self.idle_sound.get(i, -sfx.IDLE_GAP) >= sfx.IDLE_GAP and not self.hush()
                    and random.random() < 0.7 and self.effect(i, sfx.IDLES[started])):
                self.idle_sound[i] = now

    def poke(self, i, y):
        """Ctrl+click: they flinch, and say something (more annoyed the more you poke)."""
        now = time.monotonic()
        self.pokes.append(now)
        annoyed = sum(now - t < 30 for t in self.pokes) >= 5
        self.chars[i].pop, self.jolts[i] = 1.0, now
        self.effect(i, sfx.MOMENTS["poke annoyed" if annoyed else "poke"])
        if not self.text:
            self.chars[i].set_mood("angry" if annoyed else "surprised")
            self.later[i] = (now + 1.6, "idle")
        self.react(i, "poke annoyed" if annoyed else "poke head" if y < self.HEAD * config.SCALE else "poke")

    def react(self, i, what, force=False):
        """Tell the companion (it counts pokes, and says a line at most every 3 s)."""
        speak = force or time.monotonic() - self.last_said > 3
        if speak:
            self.last_said = time.monotonic()
        self.poked.emit(i, what, speak)

    def slot(self, i):
        """Where character i stands in the overlay, on the screen."""
        return self.pos() + QPoint(int((0 if self.left else BUBBLE_W) + i * CW * config.SCALE), 0)

    def fly(self, now, dt):
        """Thrown, ragdoll style: gravity, spin and bounces off the screen's edges; they land in a heap, lie there a
        moment and complain, get up, and walk back to their spot."""
        w = self.flyer
        if not w or self.grab:
            return
        char = self.chars[self.thrown_by]
        geo = (QApplication.screenAt(w.center.toPoint()) or QApplication.primaryScreen()).availableGeometry()
        if self.phase == "fly":
            vx, vy, spin = self.flight
            vy += self.GRAVITY * dt
            spin *= math.exp(-0.5 * dt)  # air slows the spin a little
            w.angle += spin * dt
            x, y = w.center.x() + vx * dt, w.center.y() + vy * dt
            hw, hh = w.half()
            if x - hw < geo.left() or x + hw > geo.right():  # a wall: bounce, and the spin reverses
                x, vx, spin = min(max(x, geo.left() + hw), geo.right() - hw), -vx * 0.6, -spin * 0.7
            if y - hh < geo.top():
                y, vy = geo.top() + hh, -vy * 0.5
            if y + hh > geo.bottom():  # the floor: bounce, lose speed, and once it's slow they land
                y, vy, vx, spin = geo.bottom() - hh, -vy * 0.4, vx * 0.7, spin * 0.6
                if abs(vy) < 220:
                    self.land(now)
            w.center = QPointF(x, y)
            if self.phase == "fly":
                self.flight = [vx, vy, spin]
                char.rag = min(1.0, math.hypot(vx, vy) / 1200 + 0.3)
        elif self.phase == "down":  # in a heap: settle onto their side (or feet), lie there, then get up
            w.angle += (self.rest - w.angle) * (1 - math.exp(-dt * 10))
            w.center = QPointF(w.center.x(), geo.bottom() - w.half()[1])
            if now - self.phase_t0 > 1.6:
                self.phase = "up"
        elif self.phase == "up":
            w.angle += -w.angle * (1 - math.exp(-dt * 5))
            w.center = QPointF(w.center.x(), geo.bottom() - w.half()[1])
            if abs(w.angle) < 1:
                w.angle, self.phase = 0.0, "home"
        elif self.phase == "home":  # back to their spot, then back into the overlay
            slot = self.slot(self.thrown_by)
            d = QPointF(slot.x() + w.cw / 2, slot.y() + w.ch / 2) - w.center
            if abs(d.x()) + abs(d.y()) < 16:  # the last few pixels: snap (whole-pixel steps would stall short of it)
                w.close()
                w.deleteLater()
                self.flyer, self.phase, char.rag = None, None, 0.0
                return
            w.center += d * (1 - math.exp(-dt * 5))
        w.place()

    def land(self, now):
        """They hit the floor for good: in a heap on their side (or on their feet), dazed, and they complain."""
        w, char = self.flyer, self.chars[self.thrown_by]
        w.angle = (w.angle + 180) % 360 - 180
        self.rest = 0.0 if abs(w.angle) < 35 else (90.0 if w.angle > 0 else -90.0)
        self.flight, self.phase, self.phase_t0, char.rag = None, "down", now, 0.0
        char.slump()  # limp
        char.set_mood("angry")
        char.pop = 1.0
        self.effect(self.thrown_by, sfx.MOMENTS["thrown"])  # (thud)
        self.react(self.thrown_by, "thrown", force=True)

    def show_line(self, mood, line, audio, event="none", who=""):
        self.speaking = self.names.index(who) if who in self.names else 0
        char = self.chars[self.speaking]
        char.set_mood(mood)
        self.later.pop(self.speaking, None)
        for i in range(len(self.chars)):
            if i != self.speaking:  # duo mode: the other one reacts to what's said, a beat later
                self.later[i] = (time.monotonic() + random.uniform(0.3, 0.8), REACT.get(mood, "idle"))
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
            char.say = self.voice.mouth() if i == self.speaking else (0.0, 0.0, 0.0)  # lip-sync: the shape of each sound
            char.step(dt, level if i == self.speaking else 0.0)  # only the one talking moves their mouth
        want = bool(user32.GetAsyncKeyState(0x11) & 0x8000) or self.grab is not None  # Ctrl: they can be poked
        if want != self.pokeable and not self.moving:
            self.pokeable = want
            set_clickthrough(self, not want)
        self.idle_sounds(now)
        self.fly(now, dt)
        if self.flyer:
            self.flyer.update()
        if self.ducker.saved and not self.voice.busy():
            self.ducker.restore()
        if self.voice.paused():
            self.hide_at += dt  # they stopped mid-sentence to listen to you: the subtitles wait too
        else:
            self.shown += dt * self.cps
        if self.text and now > self.hide_at:
            self.text = ""
            for i in range(len(self.chars)):  # back to idle, each at their own moment
                self.later[i] = (now + random.uniform(0, 1.5) * (len(self.chars) > 1), "idle")
        for i, (when, mood) in list(self.later.items()):
            if now >= when:
                self.chars[i].set_mood(mood)
                del self.later[i]
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
            if self.flyer and i == self.thrown_by:
                continue  # out of the overlay, flying in their own window
            g.save()
            e = time.monotonic() - self.jolts.get(i, -9)
            jolt = math.sin(e * 55) * 7 * (1 - e / 0.35) if e < 0.35 else 0.0  # poked: a quick jolt
            g.translate((0 if self.left else BUBBLE_W) + i * CW * config.SCALE + jolt, 0)
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
        self.unmute_at = 0.0  # "shut up for 10 minutes": when he may talk again (0 = not on a timer)
        self.dressers = []  # the characters on screen (set once the overlay exists), for outfit commands
        self.awake = not waiting  # started with Windows: stay hidden until a game starts
        self.show_on_stream = bool(self.mem.d.get("show_on_stream"))
        now = time.monotonic()
        self.last_spoke, self.last_shame, self.last_breakdown = now, 0.0, 0.0
        self.streak_start = now  # when your current stretch without a break began
        self.last_nag = now - (config.NAG_EVERY - 10) * 60  # first nag can come 10 minutes in
        self.app, self.full = ("", "", 0), False  # the window in front (exe, title, pid); does it fill the screen
        self.focus = foreground_center()  # middle of the last window you used that isn't him: which display the game is on
        self.base_thumb = None
        self.history = deque(maxlen=3)  # the game's display from the last few looks, for post-match breakdowns
        self.streak = 0  # wins and epic plays in a row, for Bloodfire
        self.local_down_until = 0.0  # after the local model fails, use Claude until then
        self.last_check = time.monotonic()  # free mode: when Claude last took a comment to keep score
        self.listening = music.Listening()  # Spotify: what's on, and repeats this session
        self.coached = ""  # a new weekly coaching report's headline, for the greeting
        self.screams = {}  # {character index: [(audio, text)]}, ready before anyone gets thrown
        self.menu_at, self.last_game = -999.0, time.monotonic()  # mini-games: when they last saw a menu, and last played
        self.trivia = self.dare = None  # the trivia question waiting for your answer; the challenge for your next match
        self.dodged = ""  # a challenge that ran out, for their next line
        self.videos, self.clip_warned = {}, False  # auto-clips: {Hall of Shame moment: its video}; told you clips are off
        self.profiling = set()  # games already queued for a lookup this session
        self.last_game_seen = None  # (key, name): for tray > Look up this game again (the tray itself takes the front)
        self.music_news, self.last_music_said, self.last_lookup = None, 0.0, -LOOKUP_GAP
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
        self.on_screen = [config.PRESET] + ([self.partner["PRESET"]] if self.partner else [])
        self.jealous = self.jealousy()  # for the greeting: who was left out, and for whom
        self.fresh_grudges = self.grudges_from_last_time()  # and what they're holding against you
        self.check_season()  # before anyone gets dressed: in season, "Surprise me" is the holiday's look
        for p in presets():  # the outfits you've earned, before anyone gets dressed ("random" only picks from those)
            try:
                cls = character_class(json.loads((config.PRESETS / f"{p}.json").read_text(encoding="utf-8"))["CHARACTER"])
            except (OSError, ValueError, KeyError):
                continue
            cls.earned |= set(self.mem.mind(p).get("unlocked", []))
        if config.LOCAL_MODEL:
            threading.Thread(target=brain.start_ollama, daemon=True).start()

    def look_up(self, playing):
        """Learn about a song with a web search, once per song (MUSIC_SEARCH; about a cent; at most every LOOKUP_GAP s,
        and not in cheap mode). What it finds stays in memory, so a song on repeat or played again is free."""
        key = f"{playing[0]} - {playing[1]}"
        cheap = config.MONTHLY_BUDGET and self.mem.spent() >= 0.8 * config.MONTHLY_BUDGET
        if (not config.MUSIC_SEARCH or self.client is None or cheap or self.mem.song_note(key) is not None
                or time.monotonic() - self.last_lookup < LOOKUP_GAP):
            return
        self.last_lookup = time.monotonic()
        try:
            note, spent = brain.look_up_song(self.client, config.MODEL, *playing)
        except Exception:
            return logging.warning("couldn't look up %s", key, exc_info=True)
        self.mem.spend(spent, "music")
        self.mem.learn_song(key, note)
        logging.info("looked up %s ($%.4f): %s", key, spent, note)

    def jealousy(self):
        """What each character on screen missed: the time you spent alone with another one while they were away."""
        lines = []
        for p in self.on_screen:
            missed = {o: s for o, s in self.mem.missed(p).items() if s >= 600}  # 10 minutes or more
            if missed:
                spent = " and ".join(f"{fmt(s)} alone with {preset_name(o)}" for o, s in missed.items())
                lines.append(f"While {preset_name(p)} was away, the player spent {spent} instead.")
        return " ".join(lines)

    def grudges_from_last_time(self):
        """New grudges from how you left things with each one on screen (grudges.py); each costs respect once."""
        now, notes = datetime.now(), []
        with self.mem.lock:
            for p in self.on_screen:
                mind = self.mem.mind(p)
                prev = [x for x in mind["sessions"] if x is not self.mem.session][-1:] if p == config.PRESET else []
                held = grudges.active(mind.setdefault("held", []), now)
                fresh = [g for g in grudges.new(prev[0] if prev else None, self.mem.d["last_with"].get(p), now)
                         if g["why"] not in {h["why"] for h in held}]
                mind["held"] = held + fresh
                if fresh:
                    mind["respect"] = max(0, mind["respect"] - grudges.COST * len(fresh))
                    notes.append(f"{preset_name(p)} has a new grudge against the player for {'; and '.join(g['why'] for g in fresh)}.")
        return " ".join(notes)

    def forgive(self, preset):
        """You apologized: their grudges end. Returns what they were for."""
        with self.mem.lock:
            mind = self.mem.mind(preset)
            gone = [g["why"] for g in grudges.active(mind.get("held", []), datetime.now())]
            mind["held"] = []
        return gone

    def check_season(self):
        """Today's holiday or your birthday (holidays.py): their lines, and what falls around them."""
        self.season = holidays.today(config.BIRTHDAY)
        character.SEASON, character.WEATHER = (self.season[0], self.season[2]) if self.season else (None, None)

    def preset_of(self, i):
        """The preset of the character at position i on screen (0: the current one, 1: duo mode's partner)."""
        return config.PRESET if i == 0 else self.partner["PRESET"]

    def settle_challenge(self, done, dodged=False):
        """The challenge is over: its bounty goes to (done) or its fine comes from (failed, dodged) whoever set it."""
        c, self.dare = self.dare, None
        i = self.names.index(c["who"]) if c["who"] in self.names else 0
        self.mem.challenge_result(self.preset_of(i), c["dare"], done, c["bounty"] if done else c["fine"])
        logging.info("challenge %s: %s", "done" if done else "dodged" if dodged else "failed", c["dare"])
        if dodged:
            self.dodged = (f' (They never did {c["who"]}\'s challenge, "{c["dare"]}": time ran out, so {c["who"]} takes '
                           f"{c['fine']} respect for dodging it. {c['who']} rubs it in.)")

    def gpu_busy(self):
        """Frame-rate guard: True in a game with the graphics card at GPU_BUSY % or more, where the free local model
        thinking on the same card would cost frames."""
        if not config.GPU_BUSY or not self.current_game():
            return False
        load = gpu_load()
        if load is None or load < config.GPU_BUSY:
            return False
        logging.info("frame-rate guard: the GPU is at %d%% in a game, so Claude takes this comment", load)
        return True

    def current_game(self):
        """(key, name) of the game in front (a Steam game by its Steam name), or None when it isn't a game."""
        exe, title, _ = self.app
        if not is_game(exe, title, self.full):
            return None
        key, steam = app_name(exe, title), steam_app(exe)
        return key, steam[1] if steam else title or key

    def profile_due(self, game):
        """True when this game has no profile yet (or an old one) and looking it up is allowed."""
        if not config.GAME_PROFILES or self.client is None or game[0] in self.profiling:
            return False
        if config.MONTHLY_BUDGET and self.mem.spent() >= 0.8 * config.MONTHLY_BUDGET:
            return False  # cheap mode
        known = self.mem.game_profile(game[0])
        return not known or datetime.now() - datetime.fromisoformat(known["made"]) > timedelta(days=PROFILE_AGE)

    def profile(self, game):
        """Look a game up once with a web search (about a cent) and remember it: modes, maps, weapons, good play."""
        key, name = game
        self.profiling.add(key)
        try:
            text, spent = brain.look_up_game(self.client, config.MODEL, name)
        except Exception:
            return logging.warning("couldn't look up %s", name, exc_info=True)
        self.mem.spend(spent, "game")
        if text:
            self.mem.learn_game(key, name, text)
            self.mem.save()
        logging.info("game profile for %s ($%.4f): %s", name, spent, text)

    def minigame(self, who=None, kind=None):
        """In a menu: one of them asks you a trivia question about your game (the mic then takes your answer for
        ANSWER_TIME s, no wake word) or sets you a challenge with a bounty for your next match (only one at a time).
        who and kind="dare": you asked one of them for a challenge."""
        if self.client is None or (config.MONTHLY_BUDGET and self.mem.spent() >= config.MONTHLY_BUDGET):
            return
        who = who if who in self.names else random.choice(self.names)
        game = self.app[1] or app_name(*self.app[:2])
        kind = kind or ("trivia" if self.dare or random.random() < 0.6 else "dare")
        level = random.choice(list(BOUNTIES))
        bounty, fine, how = BOUNTIES[level]
        terms = f"{level}: {how} (bounty: +{bounty} respect if they do it, -{fine} if they fail)"
        known = self.mem.game_profile(app_name(*self.app[:2]))
        about, asked = (known["profile"] if known else ""), self.mem.d.setdefault("trivia_asked", [])
        if kind == "dare":  # (not the same challenge again)
            asked = [r["challenge"] for r in self.mem.d.get("challenges", {}).get("last", [])]
        for _ in range(3):  # (a trivia answer has to be in their profile of the game, word for word, or it's asked again)
            model = config.TRIVIA_MODEL if kind == "trivia" else config.MODEL
            out, spent = brain.minigame(self.client, model, who, known["name"] if known else game, kind, about,
                                        random.choice(TRIVIA_TOPICS) if kind == "trivia" else terms, asked[-15:])
            self.mem.spend(spent, "game")
            logging.info("mini-game %s ($%.4f) -> %s", kind, spent, out)
            if out and out["line"].strip() and (kind == "dare" or not about or out["answer"].lower() in about.lower()):
                break
        else:
            return  # no question it could stand behind
        if kind == "trivia":
            asked.append(out["answer"])
            del asked[:-50]
        said = f"You ({who}): {out['line']}" if self.partner else f"You: {out['line']}"
        self.recent = (self.recent + [said])[-12:]
        _, audio = self.speak(out["mood"], out["line"], "none", who)
        if kind == "dare":
            if self.dare:  # asked for a new one before finishing the last: that one was dodged
                self.settle_challenge(False, dodged=True)
            self.dare = {"dare": out["answer"], "who": who, "at": time.monotonic(), "bounty": bounty, "fine": fine}
            self.bridge.note.emit(f"(challenge: {out['answer']}, +{bounty})")
            return
        self.trivia = {"q": out["line"], "a": out["answer"], "who": who, "until": time.monotonic() + ANSWER_TIME + 25}
        if audio is not None:
            time.sleep(len(audio) / SR + 0.5)  # let them finish asking
        for listener in self.listeners:
            if listener.on_heard == self.wake_heard:  # your mic (not your friends'): just say the answer
                listener.expect(ANSWER_TIME, f"Hey {who}" if self.partner else "")
                self.bridge.note.emit("(your answer?)")

    def prepare_screams(self):
        """Their screams for when you throw them, in their own voices, a bit faster (a throw can't wait for the voice)."""
        for i, name in enumerate(self.names):
            voice = self.voices_of[name]
            _, lines = commands.lines_of(self.preset_of(i), "scream")
            try:
                self.screams[i] = [(self.voice.synth(text, voice["VOICE"], "+15%", voice["VOICE_PITCH"]), text) for text in lines]
            except Exception:
                logging.warning("couldn't make %s's screams", name, exc_info=True)

    def scream(self, i):
        """(audio, text) of one of character i's screams, or None if they aren't ready yet."""
        return random.choice(self.screams[i]) if self.screams.get(i) else None

    def check_unlocks(self):
        """Hand out outfits whose goal you've reached; each one is announced in character (see unlocks.py)."""
        for i, dresser in enumerate(self.dressers):
            cls = type(dresser)
            with self.mem.lock:
                mind = self.mem.mind(self.preset_of(i))
                new = unlocks.due(cls.UNLOCKS, mind.setdefault("unlocked", []), unlocks.stats(self.mem.d, mind))
                mind["unlocked"] += new
            for outfit in new:
                cls.earned.add(outfit)
                logging.info("unlocked %s for %s", outfit, self.names[i])
                self.jobs.put(("unlock", (i, outfit)))

    def start(self):
        preload = [self.ears.model] + ([self.voice.kokoro] if config.VOICE.startswith("kokoro:") else [])  # Whisper, Kokoro
        for target in [self.worker, self.watcher, self.prepare_screams] + preload:
            threading.Thread(target=target, daemon=True).start()
        if self.awake:
            self.wake_up()

    def wake_up(self):
        """Start talking and listening: right away, or once a game starts if he launched with Windows."""
        if self.started:
            return
        self.started = self.awake = True
        if config.WAKE_WORD:  # the mic only opens once he's awake
            mic = WakeListener(self.ears, self.voice, self.wake_heard, config.MIC_DEVICE)
            mic.interrupts = config.INTERRUPT and not (config.MIC_DEVICE or "").startswith("loopback:")  # a loopback hears him
            self.listeners.append(mic)
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
        if text and echo(text, self.recent):
            return logging.info("the Discord ear heard their own line, not a friend: %s", text)
        if text is None:
            self.bridge.note.emit("(listening to your friend...)")
        else:
            logging.info("friend said: %s", text)
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
        self.set_pause(not self.paused)

    def set_pause(self, on):
        self.paused = on
        cue("off" if self.paused else "on")
        self.bridge.note.emit(f"(not watching your screen: {config.KEY_PAUSE.upper()} to resume)" if self.paused else "(watching again)")

    def toggle_mute(self):
        self.set_mute(not self.muted)

    def set_mute(self, on, seconds=0):
        """Shut-up mode on or off; with seconds, it ends by itself (the watcher checks)."""
        if on and not self.muted:
            self.mem.shush()  # too many in one session and they hold a grudge
        self.muted = on
        self.unmute_at = time.monotonic() + seconds if on and seconds else 0.0
        cue("off" if self.muted else "on")
        self.bridge.note.emit(f"(shut-up mode: I'll only talk when you talk to me. {config.KEY_MUTE.upper()} to undo)"
                              if self.muted else "(free to speak my mind again)")

    def command(self, said):
        """A voice command, handled here for free and instantly (see commands.py). True if `said` was one."""
        m = WakeListener.pattern([n for names in self.wake_of.values() for n in names]).match(said)
        who = addressed(said, self.wake_of) if self.partner else None  # duo mode: the one you called confirms it
        who = who if who in self.names else config.NAME
        i = self.names.index(who)
        dresser = self.dressers[i] if i < len(self.dressers) else None
        characters = {}
        for p in presets():
            try:
                characters[p] = json.loads((config.PRESETS / f"{p}.json").read_text(encoding="utf-8"))["WAKE_NAMES"]
            except (OSError, ValueError, KeyError):
                characters[p] = []
        cmd = commands.parse(said[m.end():] if m else said, sorted(dresser.OUTFITS) if dresser else (), characters)
        if not cmd:
            return False
        kind, value = cmd
        logging.info("voice command: %s %s", kind, value)
        preset = config.PRESET if i == 0 else self.partner["PRESET"]
        key, values, then = kind, {}, None
        if kind == "mute":
            self.set_mute(True, value or 0)
            key, values = ("mute for", {"n": commands.duration(value)}) if value else ("mute", {})
        elif kind == "unmute":
            self.set_mute(False)
        elif kind == "vision":
            self.set_pause(not value)
            key = "vision on" if value else "vision off"
        elif kind == "cost":
            values = {"spent": commands.money(self.mem.spent())}
        elif kind == "challenge":  # "give me a challenge": the one you asked sets it (their line is the reply)
            self.recent.append(f"Player: {said}")
            self.jobs.put(("minigame", (who, "dare")))
            return True
        elif kind == "outfit":
            if dresser is None:
                return False
            have = dresser.wardrobe()
            if value and value not in have:  # not earned yet: they tell you how far you are
                goal, need = dresser.UNLOCKS[value]
                with self.mem.lock:
                    now = unlocks.stats(self.mem.d, self.mem.mind(preset))[goal]
                key, values = "locked", {"outfit": value.title(), "left": unlocks.progress(goal, now, need)}
            else:
                value = value or random.choice([o for o in have if o != dresser.outfit] or have)  # "change your outfit": a new one
                self.bridge.wear.emit(i, value)
                values = {"outfit": value.title()}
        elif kind == "switch":
            if (bool(self.partner) if value == "both" else not self.partner and value == config.PRESET):
                key = "already"
            else:
                key, then = ("switch both" if value == "both" else "only me" if value == preset else "switch"), value
                values = {"other": value.title()}
        mood, line = commands.reply(preset, key, **values)
        self.recent.append(f"Player: {said}")
        self.mem.line(f"Player: {said}")
        said_back = f"You ({who}): {line}" if self.partner else f"You: {line}"
        self.recent = (self.recent + [said_back])[-12:]
        self.mem.line(said_back)
        _, audio = self.speak(mood, line, "none", who)
        if then:  # let them finish, then restart as the other character
            time.sleep((len(audio) / SR if audio is not None else 2.0) + 0.3)
            self.bridge.switch.emit(then)
        return True

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
        if kind == "minigame":
            return self.minigame(*(arg or ()))
        if kind == "profile":  # a game seen for the first time: look it up quietly in the background
            return self.profile(arg)
        if kind == "poke":  # you poked, grabbed or threw one of them (free): a quick line, unless it's gone stale
            i, what, when = arg
            if time.monotonic() - when < 3 and (not self.voice.busy() or self.voice.effect) and i < len(self.names):
                mood, line = commands.reply(self.preset_of(i), what)
                self.recent.append(f"(The player {'threw' if what == 'thrown' else 'grabbed' if what == 'grabbed' else 'poked'} "
                                   f"{self.names[i]}.)")
                self.speak(mood, line, "none", self.names[i])
            return
        if kind == "unlock":  # an outfit you just earned: they put it on and tell you (free, no API call)
            i, outfit = arg
            self.dressers[i].outfit = outfit  # shown off right away; the tray menu picks for good
            mood, line = commands.reply(self.preset_of(i), "unlocked", outfit=outfit.title())
            self.speak(mood, line, "epic", self.names[i])
            return
        if kind == "ask":
            self.bridge.note.emit(f'You: "{arg}"')
            to = addressed(arg, self.wake_of) if self.partner else None
            self.mem.count_talk(self.preset_of(self.names.index(to)) if to in self.names else None)  # toward an outfit
            if self.command(arg):  # "shut up for 10 minutes", "wear the hoodie"...: handled here, no API call
                return
        speaker, enrolled = None, False
        if kind == "friend":  # someone in your Discord call said "Hey Vorn"
            arg, clip = arg
            speaker, enrolled = self.who(arg, clip)
            self.bridge.note.emit(f'{(speaker or "Friend").title()}: "{arg}"')
        if self.client is None:
            return self.speak("disgusted", "You forgot my API key, fool. Put it in api underscore key dot text.")
        level, crossed = self.mem.budget_level()
        local = config.LOCAL_MODEL and kind in AUTO and kind != "breakdown" and time.monotonic() > self.local_down_until
        if local and self.gpu_busy():  # frame-rate guard: Claude takes it (or, budget used up, they stay quiet)
            local = False
        if level == 2 and kind in AUTO and not crossed and not local:
            return  # budget used up: he only answers when you talk to him (the free local model keeps going)
        if kind == "coach":  # tray > coaching report: write this week's if it's due, then open the page
            self.weekly_coaching()
            with self.mem.lock:
                path = coaching.build(self.mem.d, (self.mem.d.get("coaching") or [None])[-1], HALL)
            return os.startfile(path)
        if kind == "start":
            self.write_battle_report()
            self.coached = self.weekly_coaching()
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
            if name:
                situation += (f' (respect: here it\'s your verdict on {name}, not the player: "down" if what they said deserves a '
                              'roast, "up" if it was genuinely smart or funny, else "same".)')
            award = award_due(self.mem)
            if award:  # the squad's first word to them this week: last week's worst player, as a short ceremony
                situation += (f" (Before you answer: announce last week's squad award, a short ceremony in character. Worst "
                              f"player of the week: {award[0].title()}. The board, worst first: {squad_line(award[1])}.)")
        else:
            situation = f'The player says to you: "{arg}". Answer them.' if kind == "ask" else SITUATIONS[kind]
        if kind == "music":  # a new song on Spotify: look it up once (if allowed), then react
            self.look_up(arg)
            plays = self.listening.plays.get(tuple(arg), 1)
            situation = SITUATIONS["music"].format(song=arg[1], artist=arg[0]) + (
                f" They've played it {plays} times this session: it's on repeat." if plays >= 3 else "")
        if kind == "start" and self.coached:
            situation += (f" Also: your weekly coaching report on them is ready (tray > coaching report). Its headline: "
                          f'"{self.coached}". Mention it in a few words.')
            self.coached = ""
        if kind == "start" and self.fresh_grudges:
            situation += (f" {self.fresh_grudges} Open with it, cold and in character, and make them work for forgiveness "
                          "(an apology ends it).")
            self.fresh_grudges = ""
        if kind == "start" and self.jealous:
            situation += (f" {self.jealous} Bring it up in the greeting, in character: whoever was left out is jealous, "
                          "hurt or mocking about it.")
            self.jealous = ""
        if self.dodged and kind not in ("start", "friend"):
            situation, self.dodged = situation + self.dodged, ""
        trivia = self.trivia if kind == "ask" and self.trivia and time.monotonic() < self.trivia["until"] else None
        if trivia:
            situation += judge_note(trivia)
            self.trivia = None
        if kind == "ask" and APOLOGY.search(arg):  # "sorry": the one you're talking to lets their grudge go
            to_whom = addressed(arg, self.wake_of) if self.partner else None
            i = self.names.index(to_whom) if to_whom in self.names else 0
            gone = self.forgive(self.preset_of(i))
            if gone:
                situation += (f" (They're apologizing to {self.names[i]} for {'; and '.join(gone)}. {self.names[i]} lets the "
                              "grudge go, grudgingly and in character.)")
        if kind == "ask":  # duo mode keeps "Hey Mika, " in front: "remember that ..." comes after it
            m = WakeListener.pattern([n for names in self.wake_of.values() for n in names]).match(arg)
            situation += self.memory_command(arg[m.end():] if m else arg)
        to = addressed(arg, self.wake_of) if self.partner and kind in ("ask", "friend") else None
        if to:  # duo mode: without this the other one answers too ("My day?") when only one was asked
            other = next(n for n in self.names if n != to)
            situation += f" (This was said to {to}: only {to} speaks, in one turn. {other} stays silent.)"
        lines = random.choices(*BANTER)[0] if self.partner and not to else 1  # duo mode: this exchange's length
        if self.partner and not to:
            situation += (f" (This exchange runs {lines} line{'s' if lines > 1 else ''}"
                          + (": a real back-and-forth, they go at each other.)" if lines >= 4 else ".)"))
        if crossed:
            situation += " " + BUDGET_NEWS[level]
        # smarter free mode: the local model only talks, so every CHECK_EVERY minutes Claude (Haiku) takes the comment and
        # keeps score, and it double-checks at once (at most every CHECK_GAP s) when the local model thinks something big happened
        now = time.monotonic()
        check = bool(local and needs_check(level, now - self.last_check))
        local = local and not check
        # duo mode: the small local model voices one of them per comment and sees only that one's own past (shown both,
        # it tells the other's stories)
        alone = random.choice([brain.me(), self.partner]) if local and self.partner else None
        query = arg if kind in ("ask", "friend") else ""  # picks the facts relevant to what was said
        context = self.knowledge(app, title, exe, query, alone)
        smart = kind in ("ask", "look", "breakdown") and level == 0 and not trivia  # cheap mode: Haiku only, no web search
        # (judging a trivia answer is easy: Haiku does it)
        model = config.SMART_MODEL if smart else config.MODEL
        search = smart and kind == "ask" and bool(SEARCH_ASKED.search(arg))  # having the tool costs ~2 cents even unused
        out = None
        if local:
            try:
                out, spent = brain.local_think(config.LOCAL_MODEL, context, self.recent[-4:], situation, jpegs,
                                               only=alone)  # less old talk to mix up
                if out.get("event") == "menu":  # (a menu is the one thing it's trusted to spot: mini-games)
                    self.menu_at = now
                if needs_check(level, now - self.last_check, out.get("event")):
                    logging.info("local model saw a %s: Claude double-checks", out["event"])  # (it calls every kill a win)
                    out, check = None, True
                else:
                    # the small local model only talks: it calls kills "wins" and misreads screens, so it doesn't keep score,
                    # move respect, set off Bloodfire, frame the Hall of Shame, trigger breakdowns or write notes or stories
                    # (it reads your memory, it doesn't write it); Claude does those
                    out.update(event="none", respect="same", save_moment=False, killer="", remember="", game_note="", lore="",
                               challenge="none", squad=[])
                    said, voice = (out["turns"][0] if alone else None), alone
                    while said and said["line"].strip() and len(out["turns"]) < min(lines, LOCAL_BANTER):  # they go back and forth
                        voice = brain.me() if voice is self.partner else self.partner  # each from their own head: own past only
                        back, _ = brain.local_think(config.LOCAL_MODEL, self.knowledge(app, title, exe, query, voice),
                                                    self.recent[-3:] + [f"{t['speaker']}: {t['line']}" for t in out["turns"]],
                                                    COMEBACK_SAYS.format(a=said["speaker"], line=said["line"]), jpegs, only=voice)
                        said = back["turns"][0]
                        so_far = [f"You: {t['line']}" for t in out["turns"]]
                        if repeats(said["line"], self.recent) or repeats(said["line"], so_far, ECHO):
                            break  # it parroted the line it answers: end the exchange here
                        out["turns"] += back["turns"]
            except Exception:
                logging.warning("local model failed; using Claude for the next 5 minutes", exc_info=True)
                self.local_down_until = time.monotonic() + 300
        if out is None:
            if alone:  # Claude writes for both of them, so it sees both their pasts
                context = self.knowledge(app, title, exe, query)
            if check:
                self.last_check = now
            out, spent = brain.think(self.client, model, context, self.recent, situation, jpegs, search=search)
        self.mem.spend(spent, kind)
        if out.get("event") == "menu":
            self.menu_at = time.monotonic()
        if trivia:  # your trivia answer, judged: right if they gave respect for it
            self.mem.trivia_result(out.get("respect") == "up")
        logging.info("%s%s ($%.4f) -> %s", kind, " (check)" if check else " (local)" if spent == 0 and local else "", spent, out)
        turns = turns_of(out, self.names)  # [(speaker, mood, line)]: one for a solo character, a short exchange in duo mode
        if to:  # only the one you called speaks, even if the model wrote a line for the other
            turns = [t for t in turns if t[0] == to] or turns
        turns = fresh_turns(turns, self.recent) or ([] if kind in AUTO else turns[:1])  # (asked: they still answer)
        text = " ".join(line for _, _, line in turns)
        if kind in AUTO and (not text.strip() or repeats(text, self.recent)):
            return logging.info("nothing new to say: staying quiet")  # a stale moment must not be counted or spoken again
        before = self.mem.d["respect"]
        self.mem.record(app, out, friend=speaker)
        known = set(self.mem.d.get("friends", {}))
        for seen in out.get("squad", []):  # friends from the call dying, failing or popping off on your screen
            if str(seen.get("friend", "")).lower() in known and seen.get("event") in SHAME:
                self.mem.squad_event(seen["friend"], seen["event"])
        if speaker:  # a friend talked to them: the verdict on what they said goes on the squad board
            self.mem.squad_event(speaker, "talked")
            if out.get("respect") in ("up", "down"):
                self.mem.squad_event(speaker, "praised" if out["respect"] == "up" else "roasted")
        if self.dare and out.get("challenge") in ("done", "failed"):  # (they paid out or collected in this very line)
            self.settle_challenge(out["challenge"] == "done")
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
            if config.CLIP_KEY and self.current_game():  # auto-clips: the last 30 seconds of the game, too
                threading.Thread(target=self.capture_clip, args=(shame.name,), daemon=True).start()
                self.portrait(shame, turns[0][0], turns[0][1])
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
        self.voice.cut = False
        for i, (who, mood, line) in enumerate(turns):
            if self.voice.cut:  # you cut in ("Hey Vorn, ..." or the talk key): the rest of the exchange is dropped
                break
            said = f"You ({who}): {line}" if len(self.names) > 1 else f"You: {line}"
            self.recent = (self.recent + [said])[-12:]
            self.mem.line(said)
            spoken, audio = self.speak(mood, line, event if i == 0 else "none", who)
            first = first or (spoken, audio)
            if i < len(turns) - 1 and audio is not None:
                self.wait_spoken(audio)  # let them finish before the other one answers
        if shame and first:
            self.hall_entry(shame, first[0], title or app, first[1])
        self.condense_memory()

    def wait_spoken(self, audio):
        """Until a line has played, plus any time they spent paused while you talked over them (up to 30 s)."""
        end, held = time.monotonic() + len(audio) / SR + 0.25, 0.0
        while time.monotonic() < end and not self.voice.cut:
            time.sleep(0.05)
            if self.voice.paused() and held < 30:
                end, held = end + 0.05, held + 0.05

    def knowledge(self, app, title, exe, query="", alone=None):
        """What they know right now; `alone` (a preset: duo mode, local model) shows only that character's own past."""
        text = self.mem.context(app, title, steam_hours(exe), time.monotonic() - self.streak_start, query=query,
                                stories=alone is None or alone["NAME"] == config.NAME)
        if self.partner:  # duo mode: they also know what the other one remembers about you
            text += "\n" + self.mem.partner_context(self.partner["PRESET"], self.partner["NAME"], query=query,
                                                    stories=alone is None or alone is self.partner)
        if not self.partner:  # the rivalry: who else they could be switched for, and how much time each gets
            alone = dict(self.mem.d["alone"])
            rivals = [f"{preset_name(p)} ({fmt(s)})" for p, s in alone.items() if p != config.PRESET and s >= 600]
            if rivals:
                text += (f"\nRivals for the player's attention (they can switch you for them): {', '.join(rivals)} alone with "
                         f"the player so far; you: {fmt(alone.get(config.PRESET, 0))}. Bring it up now and then, in character.")
        for p in self.on_screen:  # grudges they're holding
            held = grudges.active(self.mem.mind(p).get("held", []), datetime.now())
            if held:
                text += (f"\n{preset_name(p)} is holding a grudge against the player for {'; and '.join(g['why'] for g in held)}. "
                         f"Stay cold about it and bring it up now and then, until they apologize.")
        playing = self.listening.now if config.MUSIC else None
        if playing:  # Spotify
            artist, song = playing
            plays = self.listening.plays.get(playing, 1)
            text += (f'\nMusic: the player is listening to "{song}" by {artist} on Spotify '
                     f"({fmt(time.monotonic() - self.listening.since)} so far" + (f", {plays} plays this session" if plays > 1 else "") + ").")
            note = self.mem.song_note(f"{artist} - {song}")
            if note:
                text += f" About it: {note}"
            top = self.mem.top_artists(3)
            if top:
                text += " Their most-played artists: " + ", ".join(f"{a} ({fmt(s)})" for a, s in top) + "."
        known = self.mem.game_profile(app_name(exe, title))
        if known:  # what they looked up about the game in front
            text += f"\nAbout {known['name']} (the game on screen): {known['profile']}"
        record = self.mem.d.get("trivia")
        if record and (record["right"] or record["wrong"]):  # mini-games
            text += f"\nTheir trivia record with you: {record['right']} right, {record['wrong']} wrong."
        if self.dare:
            c = self.dare
            text += (f'\nActive challenge from {c["who"]}, set {fmt(time.monotonic() - c["at"])} ago: "{c["dare"]}" (bounty: '
                     f'+{c["bounty"]} respect from {c["who"]} if they do it, -{c["fine"]} if they fail). When you settle it, '
                     f"{c['who']} pays out grudgingly or collects gleefully, in character.")
        board = self.mem.squad_board() if query else []
        if board:  # asked or talked to: the squad leaderboard, for "who's the worst?" and trash talk
            points = ", ".join(f"{k} {v:+d}" for k, v in SHAME.items() if v)
            text += f"\nSquad leaderboard this week (shame points: {points}; worst first): {squad_line(board)}."
        record = self.mem.d.get("challenges")
        if record:
            last = "; ".join(f'"{r["challenge"]}" ({"done" if r["done"] else "failed"})' for r in record["last"][-3:])
            text += f"\nTheir challenge record: {record['done']} done, {record['failed']} failed. Latest: {last}."
        if self.season:  # a holiday or your birthday
            text += "\n" + self.season[1]
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

    def portrait(self, shot, who, mood):
        """Auto-clips: a picture of `who` (the one who roasted the moment) in that mood and their outfit, next to the
        screenshot (" who.png"), for the highlights page to stand over the clip. A fresh drawing: the one on screen is
        busy animating."""
        i = self.names.index(who) if who in self.names else 0
        build, colors = (config.CHARACTER, config.COLORS) if i == 0 else (self.partner["CHARACTER"], self.partner.get("COLORS"))
        char = make_character(build, colors)
        if i < len(self.dressers):
            char.outfit = self.dressers[i].outfit
        char.tier = tier_for(self.mem.d["respect"])
        char.glance_at = char.turn_at = 1e9  # facing front
        char.set_mood(mood)
        for _ in range(5):
            char.step(1.0, 0.0)
        try:
            char.render(0.8).save(str(shot.with_name(f"{shot.stem} who.png")))
        except Exception:
            logging.warning("couldn't draw them for the clip", exc_info=True)

    def capture_clip(self, moment):
        """Auto-clips: press the capture tool's "save what just happened" key (CLIP_KEY) and give the video it saves to this
        Hall of Shame moment (a screenshot's name). The video stays where the tool put it (your Videos folder)."""
        since = time.time()
        try:
            keyboard.send(config.CLIP_KEY)
        except ValueError:
            return logging.warning("auto-clips: %r isn't a key", config.CLIP_KEY)
        video = new_clip(videos_folder(), since)
        if video is None:
            logging.info("auto-clips: no clip was saved for %s", moment)
            if not self.clip_warned:  # (once a session)
                self.clip_warned = True
                self.bridge.note.emit("(no clip saved: turn on Windows Settings > Gaming > Captures > Record what happened)"
                                      if "windows" in config.CLIP_KEY else "(no clip saved: turn on NVIDIA Instant Replay, Alt+Z)")
            return
        self.videos[moment] = str(video)  # (in case its Hall of Shame entry isn't written yet)
        if self.mem.hall_video(moment, str(video)):
            self.mem.save()
        logging.info("auto-clips: %s", video)

    def hall_entry(self, path, line, game, audio):
        clip = path.with_suffix(".wav") if audio is not None else None
        if clip:
            save_clip(clip, audio)
        self.mem.add_hall({"file": path.name, "clip": clip.name if clip else None, "caption": line, "game": game,
                           "when": datetime.now().isoformat(timespec="minutes"), "video": self.videos.pop(path.name, None),
                           "who": who.name if (who := path.with_name(f"{path.stem} who.png")).exists() else None})
        self.mem.save()
        logging.info("hall of shame: %s", path)

    def weekly_coaching(self):
        """Once a week (coaching.due): Claude writes a coaching report from both weeks' numbers and their notes on your
        play. Kept in memory (the last 12); returns its headline, or "" when none was due."""
        now = datetime.now()
        with self.mem.lock:
            if self.client is None or not coaching.due(self.mem.d, now):
                return ""
            d = self.mem.d
            this = coaching.week_stats(d, now.date())
            facts = coaching.summary(this, coaching.week_stats(d, now.date() - coaching.EVERY))
            for app, _ in this["apps"][:4]:
                g = d["games"].get(app, {})
                if g.get("notes"):
                    facts += f"\nYour notes on their play in {app}: " + "; ".join(g["notes"][-6:])
                if g.get("grudges"):
                    facts += f"\nWhat kills them most in {app}: " + ", ".join(f"{k} ({n})" for k, n in g["grudges"].items())
            week = (now - coaching.EVERY).isoformat()
            moments = [e["caption"] for e in d.get("hall", []) if e.get("when", "") >= week][-5:]
            if moments:
                facts += "\nTheir worst moments this week (Hall of Shame): " + "; ".join(moments)
        report, spent = brain.coach(self.client, config.SMART_MODEL, facts)
        self.mem.spend(spent, "report")
        if not report:
            return ""
        report["made"] = now.isoformat(timespec="minutes")
        with self.mem.lock:
            self.mem.d["coaching"] = (self.mem.d.get("coaching", []) + [report])[-12:]
        self.mem.save()
        logging.info("weekly coaching report ($%.4f): %s", spent, report["headline"])
        return report["headline"]

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
        i = self.names.index(who) if who in self.names else 0
        sound = None
        if event in BLOODFIRE:
            line = f"{voice.get('POWER', config.POWER)}! {line}"  # shouted as the character transforms
        elif random.random() < 0.4 and not ALREADY_A_SOUND.match(line):  # a scoff, chuckle, giggle or grunt first
            sound = sfx.pick(self.dressers[i].BUILD if i < len(self.dressers) else config.CHARACTER, sfx.MOODS.get(mood, ()))
            if not config.SOUND_EFFECTS:
                line = f"{random.choice(SOUNDS.get(mood, ['Hmph.']))} {line}"  # (sound effects off: said instead)
        try:
            audio = sfx.before(sound, self.voice.synth(line, voice.get("VOICE"), voice.get("VOICE_RATE"), voice.get("VOICE_PITCH")))
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
        prev = last_save = last_music = time.monotonic()
        while True:
            time.sleep(1)
            now = time.monotonic()
            dt, prev = now - prev, now
            exe, title, pid = foreground_app()
            if pid != os.getpid():
                self.app, self.focus, self.full = (exe, title, pid), foreground_center(), foreground_fullscreen()
            if self.unmute_at and now >= self.unmute_at:  # "shut up for 10 minutes" is over
                self.set_mute(False)
            if not self.awake:  # started with Windows: wait for a game, without tracking or looking
                if self.current_game():
                    self.wake_up()
                continue
            afk = idle_seconds() > config.AFK_AFTER
            if afk:
                self.streak_start = now  # a real break resets the no-break clock
            else:
                self.mem.tick(app_name(*self.app[:2]), dt, self.on_screen)
            if now - last_save > 30:
                self.check_season()  # (midnight may have brought a holiday)
                if self.dare and now - self.dare["at"] > CHALLENGE_TIME:
                    self.settle_challenge(False, dodged=True)
                game = self.current_game()
                self.last_game_seen = game or self.last_game_seen
                if game and self.profile_due(game):
                    self.profiling.add(game[0])
                    self.jobs.put(("profile", game))
                self.check_unlocks()
                self.mem.saw(self.on_screen)  # whoever is on screen knows how you've spent your time up to now
                self.mem.save()
                last_save = now
            if config.MUSIC and now - last_music >= 5:  # what's on Spotify
                last_music, playing = now, music.now_playing()
                if playing:
                    self.mem.listened(playing[0], 5)
                if self.listening.update(playing, now):
                    self.music_news = playing  # a new song: maybe worth a comment, once they're free
            quiet = now - self.last_spoke
            broke = not config.LOCAL_MODEL and config.MONTHLY_BUDGET and self.mem.spent() >= config.MONTHLY_BUDGET
            talking_to_him = self.ears.recording or any(listener.active() for listener in self.listeners)
            if afk or broke or self.busy or not self.jobs.empty() or self.voice.busy() or talking_to_him or quiet < config.LOOK_COOLDOWN:
                continue
            if not (self.muted or self.paused) and minigame_due(now, self.menu_at, self.last_game):  # sitting in a menu
                self.last_game = now
                self.jobs.put(("minigame", None))
                continue
            if self.music_news and not self.muted and now - self.last_music_said > MUSIC_GAP:
                playing, self.music_news = self.music_news, None
                if self.listening.now == playing and random.random() < (0.8 if self.listening.plays[playing] >= 3 else 0.35):
                    self.last_music_said = now  # (more likely when it's on repeat)
                    self.jobs.put(("music", playing))
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
    mutex = k32.CreateMutexW(None, False, "Local\\BackseatCompanion")
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
    comp.dressers = overlay.chars  # for "Hey Vorn, wear Obsidian"

    def poked(i, what, speak):  # Ctrl+click or a throw on the overlay
        if what.startswith("poke"):
            comp.mem.poked()  # (too many and they hold a grudge)
        if speak:
            comp.jobs.put(("poke", (i, what, time.monotonic())))

    overlay.poked.connect(poked)
    overlay.scream = comp.scream  # thrown: they scream
    overlay.hush = lambda: comp.muted  # shut-up mode: no idle sounds
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

    def switch_to(target):
        """Another character (a preset name) or "both" (duo mode); he restarts as them. Tray menu and voice command."""
        if target == "both":
            set_setting("DUO", True)
        else:
            set_setting("PRESET", target)
            set_setting("DUO", False)
        restart()

    bridge.switch.connect(switch_to)

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

    settings = SettingsWindow(restart, comp.voice, lambda dollars: comp.mem.spend(dollars, "create"))
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
    menu.addAction("Open coaching report").triggered.connect(lambda: comp.jobs.put(("coach", None)))

    def relook():  # the game profile had a mistake: fetch a fresh one at the next check
        game = comp.last_game_seen
        if game:
            comp.mem.forget_game(game[0])
            comp.profiling.discard(game[0])
            overlay.note(f"(I'll look up {game[1]} again)")
        else:
            overlay.note("(I haven't seen you play a game yet)")

    menu.addAction("Look up this game again").triggered.connect(relook)
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
        pick.triggered.connect(lambda _=False, p=preset: switch_to(p) if p != config.PRESET or config.DUO else None)
    both = characters.addAction("Both (duo mode)")
    both.setCheckable(True)
    both.setChecked(config.DUO)
    both.triggered.connect(lambda: switch_to("both") if not config.DUO else None)
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
    wearers = []  # wear(outfit) for each character on screen: the tray menus and "Hey Vorn, wear Obsidian" both use them
    bridge.wear.connect(lambda i, name: wearers[i](name))
    locks = []  # (menu entry, which character, outfit) for the ones you have to earn: refreshed whenever the menu opens
    for i, (who, dresser) in enumerate(zip(overlay.names, overlay.chars)):  # each one's wardrobe (both in duo mode), switched live
        outfits = menu.addMenu("Outfit" if len(overlay.chars) == 1 else f"{who}'s outfit")
        choices = {}

        def wear(name, dresser=dresser, choices=choices):
            set_setting(dresser.OUTFIT_SETTING, name)
            setattr(config, dresser.OUTFIT_SETTING, name)
            dresser.outfit = name if name in dresser.OUTFITS else dresser.surprise()  # "random": one now too (in season: the holiday look)
            for n, action in choices.items():
                action.setChecked(n == name)

        wearers.append(wear)
        free = sorted(o for o in dresser.OUTFITS if o not in dresser.UNLOCKS)
        for name in free + list(dresser.UNLOCKS) + ["random"]:  # the ones you earn after the free ones
            if name == "random" or name in dresser.UNLOCKS and name == list(dresser.UNLOCKS)[0]:
                outfits.addSeparator()
            choices[name] = outfits.addAction("Surprise me (a new one each launch)" if name == "random" else name.title())
            choices[name].setCheckable(True)
            choices[name].setChecked(name == getattr(config, dresser.OUTFIT_SETTING))
            choices[name].triggered.connect(lambda _=False, n=name, w=wear: w(n))
            if name in dresser.UNLOCKS:
                locks.append((choices[name], i, name))

    def show_locks():
        for action, i, name in locks:
            dresser = overlay.chars[i]
            earned = name in type(dresser).earned
            action.setEnabled(earned)
            if not earned:
                goal, need = dresser.UNLOCKS[name]
                with comp.mem.lock:
                    have = unlocks.stats(comp.mem.d, comp.mem.mind(comp.preset_of(i)))[goal]
            action.setText(name.title() if earned else f"\U0001F512 {name.title()} ({unlocks.progress(goal, have, need)})")

    show_locks()
    menu.aboutToShow.connect(show_locks)
    menu.addAction("Settings...").triggered.connect(lambda: (settings.show(), settings.raise_(), settings.activateWindow()))
    boot = menu.addAction("Start with Windows (wakes up when a game starts)")
    boot.setCheckable(True)
    boot.setChecked(autostart_on())
    boot.toggled.connect(set_autostart)
    menu.addAction(f"About {APP}...").triggered.connect(lambda: QMessageBox.about(None, f"About {APP}", (
        f"<h3>{APP} {VERSION}</h3><p>Your trash-talking gaming companions: Vorn and Mika.</p><p>Made by <b>{AUTHOR}</b>.</p>"
        "<p>Brain: Claude by Anthropic. Voices: Kokoro on your PC, or Microsoft online voices. "
        "Hearing: Whisper on your PC.</p><p><a href='https://github.com/DivxPlays/backseat'>github.com/DivxPlays/backseat</a></p>")))
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
