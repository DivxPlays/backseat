"""Settings window: change Vorn without touching code. Saves to settings.json, then restarts him."""
import json
import logging
import random
import re
import threading
from pathlib import Path

import keyboard
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget,
                               QVBoxLayout, QWidget)

import brain
import commands
import config
import holidays
from character import make_character
from senses import device_names

FILE = Path(__file__).with_name("settings.json")
VOICES = ["kokoro:am_michael", "kokoro:am_onyx", "kokoro:am_fenrir", "kokoro:am_eric", "kokoro:am_adam", "kokoro:bm_george",
          "kokoro:bm_lewis", "kokoro:bm_daniel", "kokoro:jf_alpha", "kokoro:af_heart", "kokoro:af_nicole",  # on this PC: fast, no pitch control
          "en-US-ChristopherNeural", "en-US-GuyNeural", "en-US-EricNeural", "en-US-RogerNeural", "en-US-SteffanNeural",
          "en-US-AndrewNeural", "en-GB-RyanNeural", "en-AU-WilliamNeural"]  # Microsoft online voices
MODELS = ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]
KEYS = [("KEY_TALK", "Hold to talk"), ("KEY_TYPE", "Type to him"), ("KEY_LOOK", "Look at this"), ("KEY_PAUSE", "Pause watching"),
        ("KEY_MUTE", "Shut-up mode"), ("KEY_MOVE", "Move / lock")]


def _spin(value, lo, hi, suffix=""):
    w = QSpinBox()
    w.setRange(lo, hi)
    w.setValue(value)
    w.setSuffix(suffix)
    return w


def _real(value, lo, hi, step, decimals=2):
    w = QDoubleSpinBox()
    w.setRange(lo, hi)
    w.setSingleStep(step)
    w.setDecimals(decimals)
    w.setValue(value)
    return w


def _combo(items, value, editable=False):
    w = QComboBox()
    w.setEditable(editable)
    w.addItems(items if value in items else [value] + items)
    w.setCurrentText(value)
    return w


def _row(*widgets):
    """Widgets side by side, in a container widget: a bare layout passed to addRow can be freed by Python early and crash Qt."""
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    for w in widgets:
        lay.addWidget(w)
    return box


def presets():
    """The characters you can pick: presets/<name>.json."""
    return sorted(p.stem for p in config.PRESETS.glob("*.json")) or [config.PRESET]


def webcams():
    """Real webcams (not virtual ones), for the camera background."""
    from PySide6.QtMultimedia import QMediaDevices
    return [d.description() for d in QMediaDevices.videoInputs() if not any(w in d.description().lower() for w in ("virtual", "obs"))]


def set_setting(key, value):
    """Save one setting into settings.json (the tray menu's character and outfit pickers)."""
    saved = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
    saved[key] = value
    FILE.write_text(json.dumps(saved, indent=1), encoding="utf-8")


BUILDS = {"Vorn's build (warlord)": "vorn", "Mika's build (gamer girl)": "mika"}
PARTS = (("hair", "Hair"), ("eyes", "Eyes"), ("skin", "Skin"), ("outfit", "Outfit"))
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def test_voice(player, voice, rate, pitch):
    def run():
        try:
            player.play(player.synth("So this is how I sound. Try to keep up.", voice, f"{rate:+d}%", f"{pitch:+d}Hz"))
        except Exception as e:  # unknown voice name or no internet
            print("voice test failed:", e)

    threading.Thread(target=run, daemon=True).start()


class ColorPicks(QWidget):
    """Hair, eyes, skin and outfit colour buttons (the outfit colour tints every outfit); unset ones keep the build's own."""

    def __init__(self, colors, changed=lambda: None):
        super().__init__()
        self.colors, self.changed, self.buttons = {k: v for k, v in (colors or {}).items() if v}, changed, {}
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        for part, label in PARTS:
            self.buttons[part] = QPushButton(label)
            self.buttons[part].clicked.connect(lambda _=False, p=part: self.pick(p))
            lay.addWidget(self.buttons[part])
        own = QPushButton("Their own")
        own.setToolTip("Back to the build's own colours")
        own.clicked.connect(self.reset)
        lay.addWidget(own)
        self.show_colors()

    def pick(self, part):
        c = QColorDialog.getColor(QColor(self.colors.get(part, "#808080")), self, f"{dict(PARTS)[part]} colour")
        if c.isValid():
            self.colors[part] = c.name()
            self.show_colors()
            self.changed()

    def reset(self):
        self.colors = {}
        self.show_colors()
        self.changed()

    def show_colors(self):
        for part, b in self.buttons.items():
            c = self.colors.get(part)
            b.setStyleSheet(f"background: {c}; color: {'black' if QColor(c).lightness() > 128 else 'white'}" if c else "")

    def value(self):
        return dict(self.colors)


def own_lines(made, example):
    """The lines Claude wrote for a new character that are safe to say: for each moment in `example` ({key: (mood,
    lines)}), the lines using only that moment's {placeholders} and no stray braces."""
    out = {}
    for key, (mood, lines) in example.items():
        allowed = set(PLACEHOLDER.findall(" ".join(lines)))
        got = made.get(key) if isinstance(made.get(key), dict) else {}
        ok = [line.strip() for line in got.get("lines", []) if line.strip() and set(PLACEHOLDER.findall(line)) <= allowed
              and not set(PLACEHOLDER.sub("", line)) & set("{}")]
        if ok:
            out[key] = [got.get("mood", mood), ok]
    return out


def save_character(name, build, voice, power, colors, about, made):
    """Write a new character to presets/ (never over an existing one) and return its preset name. made: what Claude wrote
    ({"persona", "wake_names", "lines"}), or {} when it couldn't (a plain personality from your words, Vorn's or Mika's lines)."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "character"
    path, n = config.PRESETS / f"{slug}.json", 2
    while path.exists():
        path, n = config.PRESETS / f"{slug}-{n}.json", n + 1
    persona = (made.get("persona") or "").strip() or (
        "You are {name}, a companion who lives in a small window in the corner of the player's screen, watches them play "
        f"and talks to them out loud.\n\nWho you are: {about}\n\nRespect is how much you rate the player: the score (0-100) "
        "colours your tone. It moves slowly.\n\n{power} is your power-up form: your most intense moment.")
    wake = [name.lower()] + [w.strip().lower() for w in made.get("wake_names", []) if w.strip()]
    preset = {"NAME": name, "PERSONA": persona, "VOICE": voice, "VOICE_RATE": "+0%", "VOICE_PITCH": "+0Hz", "CHARACTER": build,
              "WAKE_NAMES": list(dict.fromkeys(wake)), "POWER": power, "COLORS": colors,
              "LINES": own_lines(made.get("lines", {}), commands.LINES[build])}
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(preset, indent=1), encoding="utf-8")
    return path.stem


class CreatorWindow(QDialog):
    """Make your own character: name, build (Vorn's or Mika's body), who they are, voice, power-up and colours, with a live
    preview. Claude writes their full personality, the ways their name gets misheard and their own lines (one call)."""
    MOODS = ("idle", "smug", "laugh", "angry", "surprised", "disgusted")

    def __init__(self, voice, spend, created):
        super().__init__()
        self.setWindowTitle("Create a character")
        self.voice, self.spend, self.created, self.result = voice, spend, created, None
        self.name = QLineEdit()
        self.name.setPlaceholderText("Captain Rook")
        self.build = QComboBox()
        self.build.addItems(list(BUILDS))
        self.build.currentTextChanged.connect(self.redress)
        self.about = QPlainTextEdit()
        self.about.setPlaceholderText("A washed-up pirate captain who thinks every match is a naval battle. Gruff and dramatic, "
                                      "calls the player 'deckhand', secretly proud of them.")
        self.about.setMinimumHeight(120)
        self.voice_pick = _combo(VOICES, VOICES[0], editable=True)
        test = QPushButton("Test voice")
        test.clicked.connect(lambda: test_voice(self.voice, self.voice_pick.currentText(), 0, 0))
        self.power = QLineEdit()
        self.power.setPlaceholderText("Stormcall")
        self.picks = ColorPicks({}, self.redress)
        form = QWidget()
        rows = QFormLayout(form)
        for label, field in (("Name", self.name), ("Body", self.build), ("Who they are", self.about),
                             ("Voice", _row(self.voice_pick, test)), ("Power-up name", self.power), ("Colours", self.picks)):
            rows.addRow(label, field)
        self.preview = QLabel()
        self.preview.setMinimumSize(180, 470)
        self.status = QLabel("Claude writes their full personality and their own lines from your words "
                             f"(one call to {config.SMART_MODEL}, about 6 cents). You can edit them after in Settings > Character.")
        self.status.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("Create")
        self.buttons.accepted.connect(self.create)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(_row(form, self.preview))
        layout.addWidget(self.status)
        layout.addWidget(self.buttons)
        self.frame = 0
        self.redress()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(66)

    def redress(self, *_):
        """A fresh preview in the chosen body and colours."""
        self.char = make_character(BUILDS[self.build.currentText()], self.picks.value())
        self.tick()

    def tick(self):
        self.frame += 1
        if self.frame % 60 == 1:  # a new face every 4 s
            self.char.set_mood(random.choice(self.MOODS))
        self.char.step(1 / 15, 0.0)
        self.preview.setPixmap(QPixmap.fromImage(self.char.render(0.9)))

    def create(self):
        name, about = self.name.text().strip(), self.about.toPlainText().strip()
        if not name or not about:
            QMessageBox.warning(self, "Create a character", "Give them a name and a few words about who they are.")
            return
        build, power = BUILDS[self.build.currentText()], self.power.text().strip() or "Overdrive"
        self.buttons.setEnabled(False)
        self.status.setText(f"Writing who {name} is...")
        example = commands._preset(build).get("PERSONA", "")

        def run():
            try:
                client = brain.make_client()
                self.result = ({}, 0.0) if client is None else brain.create_character(
                    client, config.SMART_MODEL, name, build.title(), power, about, example, commands.LINES[build])
            except Exception:
                logging.warning("couldn't write the new character", exc_info=True)
                self.result = ({}, 0.0)

        threading.Thread(target=run, daemon=True).start()
        self.waiter = QTimer(self)
        self.waiter.timeout.connect(lambda: self.finish(name, build, power, about))
        self.waiter.start(200)

    def finish(self, name, build, power, about):
        if self.result is None:
            return
        self.waiter.stop()
        made, spent = self.result
        self.spend(spent)
        preset = save_character(name, build, self.voice_pick.currentText(), power, self.picks.value(), about, made or {})
        logging.info("created character %s ($%.4f)%s", preset, spent, "" if made else " without Claude")
        self.timer.stop()
        self.accept()
        self.created(preset, name)


def _signed(text):
    """'+6%' or '-8Hz' -> 6 / -8"""
    m = re.match(r"([+-]?\d+)", text or "0")
    return int(m.group(1)) if m else 0


class SettingsWindow(QDialog):
    def __init__(self, restart, voice, spend=lambda dollars: None):
        super().__init__()
        self.setWindowTitle(f"{config.NAME} settings")
        self.setMinimumWidth(560)
        self.restart, self.voice, self.spend = restart, voice, spend
        self.get = {}  # setting name -> function returning its new value

        w = {}
        w["PRESET"] = _combo(presets(), config.PRESET)
        w["NAME"] = QLineEdit(config.NAME)
        w["VOICE"] = _combo(VOICES, config.VOICE, editable=True)
        rate, pitch = _spin(_signed(config.VOICE_RATE), -50, 50, " %"), _spin(_signed(config.VOICE_PITCH), -40, 40, " Hz")
        w["SCALE"] = _real(config.SCALE, 0.4, 2.0, 0.05)
        w["DUCK_TO"] = _real(config.DUCK_TO, 0.0, 1.0, 0.05)
        w["SWEAR"] = QCheckBox("Let them swear (never slurs)")
        w["SWEAR"].setChecked(config.SWEAR)
        persona = QPlainTextEdit(config.PERSONA)
        persona.setMinimumHeight(200)
        test = QPushButton("Test voice")
        test.clicked.connect(lambda: test_voice(self.voice, w["VOICE"].currentText(), rate.value(), pitch.value()))
        picks = ColorPicks(config.COLORS)
        create = QPushButton("Create a character...")
        create.clicked.connect(self.open_creator)
        self.preset_pick = w["PRESET"]
        him = self._page([("Character (switching restarts)", _row(w["PRESET"], create)), ("Name", w["NAME"]),
                          ("Colours (over the build's own)", picks), ("Voice", _row(w["VOICE"], test)),
                          ("Voice speed", rate), ("Voice pitch (online voices)", pitch), ("Size on screen", w["SCALE"]),
                          ("Other apps' volume while they talk (1 = unchanged)", w["DUCK_TO"]),
                          ("Language", w["SWEAR"]), ("Personality ({name} = their name)", persona)])

        w["MODEL"] = _combo(MODELS, config.MODEL)
        w["SMART_MODEL"] = _combo(MODELS, config.SMART_MODEL)
        w["MONTHLY_BUDGET"] = _spin(config.MONTHLY_BUDGET, 0, 100000, " $")
        w["LOCAL_MODEL"] = _combo(["", "qwen3-vl:8b-instruct", "qwen3-vl:4b-instruct"], config.LOCAL_MODEL, editable=True)
        w["CHECK_EVERY"] = _spin(config.CHECK_EVERY, 0, 120, " min")
        w["GPU_BUSY"] = _spin(config.GPU_BUSY, 0, 100, " %")
        w["LOCAL_IN_GAMES"] = QCheckBox("Use it in games too (off: Claude comments in games\nand the model leaves the graphics card)")
        w["LOCAL_IN_GAMES"].setChecked(config.LOCAL_IN_GAMES)
        w["GAME_PROFILES"] = QCheckBox("Look each new game up on the web once (about 1 cent a game)")
        w["GAME_PROFILES"].setChecked(config.GAME_PROFILES)
        w["STEAM_KEY"] = QLineEdit(config.STEAM_KEY)
        w["STEAM_KEY"].setEchoMode(QLineEdit.Password)
        w["STEAM_KEY"].setPlaceholderText("from steamcommunity.com/dev/apikey (blank = off)")
        w["AUTO_UPDATE"] = QCheckBox("Check GitHub for a newer version once a day (you're asked before it updates)")
        w["AUTO_UPDATE"].setChecked(config.AUTO_UPDATE)
        brain = self._page([("Model for his automatic comments", w["MODEL"]), ("Model when you talk to him", w["SMART_MODEL"]),
                            ("Free local model for automatic comments\n(Ollama; blank = use Claude)", w["LOCAL_MODEL"]),
                            ("With the local model, Claude keeps score every\n(and on wins and deaths; 0 = never)", w["CHECK_EVERY"]),
                            ("Local model in games", w["LOCAL_IN_GAMES"]),
                            ("Frame-rate guard (in games): Claude comments instead\nwhen a game has the GPU this busy (0 = off)", w["GPU_BUSY"]),
                            ("Game profiles", w["GAME_PROFILES"]), ("Updates", w["AUTO_UPDATE"]),
                            ("Steam Web API key: real kills and deaths\nin games with Steam stats", w["STEAM_KEY"]),
                            ("Monthly budget (0 = no limit)", w["MONTHLY_BUDGET"])])

        w["LOOK_COOLDOWN"] = _spin(config.LOOK_COOLDOWN, 5, 600, " s")
        w["QUIET_ROAST"] = _spin(config.QUIET_ROAST, 10, 3600, " s")
        w["CHANGE_THRESHOLD"] = _spin(config.CHANGE_THRESHOLD, 1, 100)
        w["AFK_AFTER"] = _spin(config.AFK_AFTER, 30, 3600, " s")
        w["BREAK_AFTER"] = _spin(config.BREAK_AFTER, 10, 600, " min")
        w["NAG_EVERY"] = _spin(config.NAG_EVERY, 5, 600, " min")
        bed_from, bed_to = _spin(config.BEDTIME[0], 0, 23, ":00"), _spin(config.BEDTIME[1], 0, 23, ":00")
        bed_row = _row(bed_from, bed_to)
        w["WAKE_WORD"] = QCheckBox(f'Listen for "Hey {config.NAME}"')
        w["WAKE_WORD"].setChecked(config.WAKE_WORD)
        w["WAKE_LEVEL"] = _real(config.WAKE_LEVEL, 0.001, 0.5, 0.005, 3)
        w["MUSIC"] = QCheckBox("Comment on what you play on Spotify")
        w["MUSIC"].setChecked(config.MUSIC)
        w["MUSIC_SEARCH"] = QCheckBox("Look new songs up on the web first (about 1 cent a song)")
        w["MUSIC_SEARCH"].setChecked(config.MUSIC_SEARCH)
        w["BIRTHDAY"] = QLineEdit(config.BIRTHDAY)
        w["BIRTHDAY"].setPlaceholderText("month-day, like 02-10")
        w["INTERRUPT"] = QCheckBox("Talk over them and they pause to listen (needs a headset)")
        w["INTERRUPT"].setChecked(config.INTERRUPT)
        w["SOUND_EFFECTS"] = QCheckBox("Real grunts, gasps, giggles, sighs and yawns (pokes, throws, idles, some lines)")
        w["SOUND_EFFECTS"].setChecked(config.SOUND_EFFECTS)
        behave = self._page([("Seconds between comments", w["LOOK_COOLDOWN"]), ("Roast after this much silence", w["QUIET_ROAST"]),
                             ("Screen change that counts (lower = more comments)", w["CHANGE_THRESHOLD"]),
                             ("You're AFK after", w["AFK_AFTER"]), ("Nag to take a break after", w["BREAK_AFTER"]),
                             ("Bedtime nags from / until", bed_row), ("Minimum time between nags", w["NAG_EVERY"]),
                             ("Wake word", w["WAKE_WORD"]), ("Mic loudness that counts as speech", w["WAKE_LEVEL"]),
                             ("Interrupting", w["INTERRUPT"]), ("Sound effects", w["SOUND_EFFECTS"]), ("Your birthday (they celebrate it)", w["BIRTHDAY"]),
                             ("Music", w["MUSIC"]), ("", w["MUSIC_SEARCH"])])

        keys = []
        for name, label in KEYS:
            w[name] = QLineEdit(getattr(config, name))
            keys.append((label, w[name]))
        w["MONITOR"] = _combo(["all", "1", "2", "3"], str(config.MONITOR), editable=True)
        skip, games = QLineEdit(", ".join(config.SKIP_DISPLAYS)), QLineEdit(", ".join(config.GAMES))
        w["CLIP_KEY"] = QLineEdit(config.CLIP_KEY)
        displays = self._page(keys + [("Displays to watch (all, or a number)", w["MONITOR"]),
                                      ("Displays to never look at (comma separated)", skip),
                                      ("Games they miss (exe names)", games),
                                      ("Auto-clips: the key that saves what just happened\n(Game Bar windows+alt+g, NVIDIA alt+f10; "
                                       "Medal running: its own key; blank = off)", w["CLIP_KEY"])])

        w["MIC_DEVICE"] = _combo([""] + device_names("input"), config.MIC_DEVICE, editable=True)
        w["VOICE_DEVICE"] = _combo([""] + device_names("output"), config.VOICE_DEVICE, editable=True)
        w["FRIENDS_DEVICE"] = _combo([""] + [f"loopback:{d}" for d in device_names("output")] + device_names("input"),
                                     config.FRIENDS_DEVICE, editable=True)  # loopback: what a speaker plays (a call)
        w["CAMERA"] = _combo(["off", "current", "both"], config.CAMERA)
        w["CAMERA_BACKGROUND"] = _combo(["dark", "green", "game", "webcam"], config.CAMERA_BACKGROUND)
        w["CAMERA_WEBCAM"] = _combo([""] + webcams(), config.CAMERA_WEBCAM, editable=True)
        audio = self._page([("Your mic (blank = default)", w["MIC_DEVICE"]),
                            ("Their voice (blank = default)", w["VOICE_DEVICE"]),
                            ("Friends' voices from a call (blank = off)", w["FRIENDS_DEVICE"]),
                            ("Discord camera (\"OBS Virtual Camera\")", w["CAMERA"]),
                            ("Camera background", w["CAMERA_BACKGROUND"]),
                            ("Your real webcam (blank = first one)", w["CAMERA_WEBCAM"])])

        tabs = QTabWidget()
        for page, title in ((him, "Character"), (brain, "Brain && budget"), (behave, "Behavior"), (displays, "Keys && displays"),
                            (audio, "Discord && audio")):
            tabs.addTab(page, title)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults)
        buttons.button(QDialogButtonBox.Save).setText("Save && restart")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self.reset)
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

        for name, widget in w.items():
            if isinstance(widget, QLineEdit):
                self.get[name] = widget.text
            elif isinstance(widget, QComboBox):
                self.get[name] = widget.currentText
            elif isinstance(widget, QCheckBox):
                self.get[name] = widget.isChecked
            else:
                self.get[name] = widget.value
        self.get["VOICE_RATE"] = lambda: f"{rate.value():+d}%"
        self.get["VOICE_PITCH"] = lambda: f"{pitch.value():+d}Hz"
        self.get["BEDTIME"] = lambda: [bed_from.value(), bed_to.value()]
        self.get["PERSONA"] = persona.toPlainText
        self.get["COLORS"] = picks.value
        self.get["SKIP_DISPLAYS"] = lambda: [s.strip() for s in skip.text().split(",") if s.strip()]
        self.get["GAMES"] = lambda: [s.strip().lower() for s in games.text().split(",") if s.strip()]

    @staticmethod
    def _page(rows):
        page = QWidget()
        form = QFormLayout(page)
        for label, field in rows:
            form.addRow(label, field)
        return page

    def open_creator(self):
        self.creator = CreatorWindow(self.voice, self.spend, self.created)
        self.creator.show()

    def created(self, preset, name):
        """A new character is ready: switch to them now (he restarts), or later from tray > Character."""
        self.preset_pick.addItem(preset)
        if QMessageBox.question(self, "Character created", f"{name} is ready. Switch to them now? (restarts)") == QMessageBox.Yes:
            set_setting("PRESET", preset)
            self.reject()
            self.restart()

    def values(self):
        return {name: get() for name, get in self.get.items()}

    def problems(self, v):
        bad = []
        if not v["NAME"].strip():
            bad.append("His name can't be empty.")
        for name, label in KEYS:
            try:
                keyboard.parse_hotkey(v[name])
            except ValueError:
                bad.append(f'"{v[name]}" isn\'t a key I recognize ({label}).')
        if v["CLIP_KEY"].strip():
            try:
                keyboard.parse_hotkey(v["CLIP_KEY"])
            except ValueError:
                bad.append(f'"{v["CLIP_KEY"]}" isn\'t a key I recognize (auto-clips).')
        if v["MONITOR"] != "all" and not v["MONITOR"].isdigit():
            bad.append('Displays to watch must be "all" or a number.')
        if v["BIRTHDAY"].strip() and not holidays.birthday_of(v["BIRTHDAY"]):
            bad.append('Your birthday must look like 02-10 (month-day), or be blank.')
        return bad

    def save(self):
        v = self.values()
        bad = self.problems(v)
        if bad:
            QMessageBox.warning(self, "Can't save yet", "\n".join(bad))
            return
        if v["PRESET"] == config.PRESET:  # the character's own fields go into its preset (when switching, the new one loads as is)
            path = config.PRESETS / f"{config.PRESET}.json"
            preset = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            preset.update({k: x for k, x in v.items() if k in config.PRESET_KEYS})
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(preset, indent=1), encoding="utf-8")
        changed = {k: x for k, x in v.items() if k not in config.PRESET_KEYS and json.dumps(x) != json.dumps(config._DEFAULTS.get(k))}
        FILE.write_text(json.dumps(changed, indent=1), encoding="utf-8")
        self.accept()
        self.restart()

    def reset(self):
        if QMessageBox.question(self, "Reset settings", "Go back to the default settings? Your memory and stats are kept.") == QMessageBox.Yes:
            FILE.unlink(missing_ok=True)
            self.accept()
            self.restart()
