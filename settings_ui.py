"""Settings window: change Vorn without touching code. Saves to settings.json, then restarts him."""
import json
import re
import threading
from pathlib import Path

import keyboard
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                               QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

import config

FILE = Path(__file__).with_name("settings.json")
VOICES = ["en-US-ChristopherNeural", "en-US-GuyNeural", "en-US-EricNeural", "en-US-RogerNeural", "en-US-SteffanNeural",
          "en-US-AndrewNeural", "en-GB-RyanNeural", "en-AU-WilliamNeural"]
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


def _signed(text):
    """'+6%' or '-8Hz' -> 6 / -8"""
    m = re.match(r"([+-]?\d+)", text or "0")
    return int(m.group(1)) if m else 0


class SettingsWindow(QDialog):
    def __init__(self, restart, voice):
        super().__init__()
        self.setWindowTitle(f"{config.NAME} settings")
        self.setMinimumWidth(560)
        self.restart, self.voice = restart, voice
        self.get = {}  # setting name -> function returning its new value

        w = {}
        w["NAME"] = QLineEdit(config.NAME)
        w["VOICE"] = _combo(VOICES, config.VOICE, editable=True)
        rate, pitch = _spin(_signed(config.VOICE_RATE), -50, 50, " %"), _spin(_signed(config.VOICE_PITCH), -40, 40, " Hz")
        w["SCALE"] = _real(config.SCALE, 0.4, 2.0, 0.05)
        w["DUCK_TO"] = _real(config.DUCK_TO, 0.0, 1.0, 0.05)
        persona = QPlainTextEdit(config.PERSONA)
        persona.setMinimumHeight(200)
        test = QPushButton("Test voice")
        test.clicked.connect(lambda: self.test_voice(w["VOICE"].currentText(), rate.value(), pitch.value()))
        him = self._page([("Name", w["NAME"]), ("Voice", _row(w["VOICE"], test)), ("Voice speed", rate), ("Voice pitch", pitch),
                          ("Size on screen", w["SCALE"]), ("Other apps' volume while he talks (1 = unchanged)", w["DUCK_TO"]),
                          ("Personality ({name} = his name)", persona)])

        w["MODEL"] = _combo(MODELS, config.MODEL)
        w["SMART_MODEL"] = _combo(MODELS, config.SMART_MODEL)
        w["MONTHLY_BUDGET"] = _spin(config.MONTHLY_BUDGET, 0, 100000, " $")
        brain = self._page([("Model for his automatic comments", w["MODEL"]), ("Model when you talk to him", w["SMART_MODEL"]),
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
        behave = self._page([("Seconds between comments", w["LOOK_COOLDOWN"]), ("Roast after this much silence", w["QUIET_ROAST"]),
                             ("Screen change that counts (lower = more comments)", w["CHANGE_THRESHOLD"]),
                             ("You're AFK after", w["AFK_AFTER"]), ("Nag to take a break after", w["BREAK_AFTER"]),
                             ("Bedtime nags from / until", bed_row), ("Minimum time between nags", w["NAG_EVERY"]),
                             ("Wake word", w["WAKE_WORD"]), ("Mic loudness that counts as speech", w["WAKE_LEVEL"])])

        keys = []
        for name, label in KEYS:
            w[name] = QLineEdit(getattr(config, name))
            keys.append((label, w[name]))
        w["MONITOR"] = _combo(["all", "1", "2", "3"], str(config.MONITOR), editable=True)
        skip, games = QLineEdit(", ".join(config.SKIP_DISPLAYS)), QLineEdit(", ".join(config.GAMES))
        displays = self._page(keys + [("Displays to watch (all, or a number)", w["MONITOR"]),
                                      ("Displays to never look at (comma separated)", skip),
                                      ("Non-Steam games that wake him (exe names)", games)])

        tabs = QTabWidget()
        for page, title in ((him, "Him"), (brain, "Brain && budget"), (behave, "Behavior"), (displays, "Keys && displays")):
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
        self.get["SKIP_DISPLAYS"] = lambda: [s.strip() for s in skip.text().split(",") if s.strip()]
        self.get["GAMES"] = lambda: [s.strip().lower() for s in games.text().split(",") if s.strip()]

    @staticmethod
    def _page(rows):
        page = QWidget()
        form = QFormLayout(page)
        for label, field in rows:
            form.addRow(label, field)
        return page

    def test_voice(self, voice, rate, pitch):
        def run():
            try:
                self.voice.play(self.voice.synth("So this is how I'll sound. Pathetic, grunt.", voice, f"{rate:+d}%", f"{pitch:+d}Hz"))
            except Exception as e:  # unknown voice name or no internet
                print("voice test failed:", e)

        threading.Thread(target=run, daemon=True).start()

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
        if v["MONITOR"] != "all" and not v["MONITOR"].isdigit():
            bad.append('Displays to watch must be "all" or a number.')
        return bad

    def save(self):
        v = self.values()
        bad = self.problems(v)
        if bad:
            QMessageBox.warning(self, "Can't save yet", "\n".join(bad))
            return
        changed = {k: x for k, x in v.items() if json.dumps(x) != json.dumps(config._DEFAULTS.get(k))}
        FILE.write_text(json.dumps(changed, indent=1), encoding="utf-8")
        self.accept()
        self.restart()

    def reset(self):
        if QMessageBox.question(self, "Reset settings", "Go back to the default settings? Your memory and stats are kept.") == QMessageBox.Yes:
            FILE.unlink(missing_ok=True)
            self.accept()
            self.restart()
