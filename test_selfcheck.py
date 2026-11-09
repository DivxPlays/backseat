"""Quick self-check, no API key or internet needed:  python test_selfcheck.py"""
import base64
import io
import json
import os
import re
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import config  # noqa: E402

config.DUO = False  # the checks below start from one character, whatever your settings say (duo mode is checked on its own)
from brain import SCHEMA  # noqa: E402
from character import MOODS, Vorn  # noqa: E402
from memory import Memory, parse_vdf, playtime_minutes, steam_app  # noqa: E402
from senses import changed, thumbnail  # noqa: E402

# Steam's KeyValues format
assert parse_vdf('"A" { "b" "1" "C" { "d" "x" "" "" } "e" "2" }') == {"A": {"b": "1", "C": {"d": "x", "": ""}, "e": "2"}}
lc = parse_vdf('"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { "apps" { "7940" { "LastPlayed" "1" '
               '"cloud" { "x" "y" } "Playtime" "72240" } } } } } }')
assert playtime_minutes(lc, "7940") == 72240 and playtime_minutes(lc, "1") is None

with tempfile.TemporaryDirectory() as d:
    Path(d, "steamapps").mkdir()
    Path(d, "steamapps", "appmanifest_7940.acf").write_text('"AppState" { "appid" "7940" "name" "Call of Duty 4" "installdir" "Call of Duty 4" }')
    assert steam_app(str(Path(d, "steamapps", "common", "Call of Duty 4", "iw3mp.exe"))) == ("7940", "Call of Duty 4")
    assert steam_app(r"C:\Windows\notepad.exe") is None

# memory: time tracking, note cap, dedupe, reload, corrupt-file recovery
with tempfile.TemporaryDirectory() as d:
    f = Path(d, "memory.json")
    m = Memory(f)
    m.tick("game.exe", 7200)
    for i in range(50):
        m.remember(f"note {i}")
    m.remember("note 49")
    m.save()
    m2 = Memory(f)
    assert m2.d["apps"]["game.exe"] == 7200 and m2.d["session_count"] == 2 and len(m2.d["sessions"]) == 2
    assert len(m2.d["notes"]) == 40 and m2.d["notes"][-1].endswith(": note 49")
    m2.record("game.exe", {"event": "death", "respect": "down", "game_note": "stuck on the bridge", "remember": "likes snipers"})
    m2.record("game.exe", {"event": "death", "respect": "down", "game_note": "stuck on the bridge", "remember": ""})
    m2.record("game.exe", {"event": "menu", "respect": "up", "game_note": "", "remember": ""})  # menus aren't scored
    for _ in range(20):
        m2.record("game.exe", {"event": "none", "respect": "down"})  # respect can't drop below 0
    assert m2.d["games"]["game.exe"] == {"events": {"death": 2}, "notes": ["stuck on the bridge"]}
    assert m2.d["respect"] == 0 and m2.session["events"] == {"death": 2}
    ctx = m2.context("game.exe", "Some Game", ("Some Game", 1204.0), 5400)
    for want in ("2.0 h tracked", "1204 h", "note 49", "2 deaths", "0/100", "stuck on the bridge", "likes snipers", "1.5 h"):
        assert want in ctx, (want, ctx)
    m2.line("You: pathetic")
    m2.session["seconds"] = 300
    m2.save()
    m3 = Memory(f)
    prev = m3.unreported()
    assert prev and "2 deaths" in Memory.report_input(prev) and "You: pathetic" in Memory.report_input(prev)
    prev["report"] = "You died twice on a bridge."
    assert m3.unreported() is None and "died twice on a bridge" in m3.context("game.exe", "Some Game", None, 0)
    f.write_text("{broken")
    assert Memory(f).d["total_seconds"] == 0 and Path(d, "memory.corrupt.json").exists()

# screen change detection
black, white = thumbnail(Image.new("RGB", (1920, 1080), "black")), thumbnail(Image.new("RGB", (1920, 1080), "white"))
assert not changed(black, black, config.CHANGE_THRESHOLD) and changed(black, white, config.CHANGE_THRESHOLD)
two_displays = np.concatenate([black, black], axis=1)
assert changed(black, two_displays, config.CHANGE_THRESHOLD)  # a display plugged in counts as a change, no crash

# persona formats cleanly, schema moods match the art, every mood renders
assert config.NAME in config.PERSONA.replace("{name}", config.NAME)
assert SCHEMA["properties"]["mood"]["enum"] == list(MOODS)
app = QApplication([])
for mood in MOODS:
    v = Vorn()
    v.set_mood(mood)
    for _ in range(30):
        v.step(1 / 30, 0.6)
    img = v.render()
    assert not img.isNull() and img.pixelColor(150, 150).alpha() == 255, mood
# full body: every outfit and pose, gesturing to either side, stays inside his window (aura off: it's meant to spill)
for mood, toward, outfit in [(m, t, o) for m in MOODS for t in (1.0, -1.0) for o in Vorn.OUTFITS]:
    v = Vorn(outfit)
    v.toward = toward
    v.set_mood(mood)
    for _ in range(90):
        v.step(1 / 30, 0.0)
    v.p["aura"], v.flare_amt = 0.0, 0.0
    img = v.render()
    edges = [img.pixelColor(x, y).alpha() for x in (0, img.width() - 1) for y in range(0, img.height(), 2)]
    edges += [img.pixelColor(x, 0).alpha() for x in range(img.width())]
    assert max(edges) == 0, (mood, toward, outfit)
v.slump()
for _ in range(30):
    v.step(1 / 30, 0.0)
assert v.pose()[1][2] == "open" and v._effective()["slump"] == 1.0  # he slumps when you lose
assert v.render(0.3, bust=True).size().toTuple() == (90, 102)  # tray icon: head and shoulders

# the overlay's animation loop really runs: his face moves and the subtitles type out
import sys  # noqa: E402

import main  # noqa: E402
from senses import CUES, Voice  # noqa: E402

sys.excepthook = sys.__excepthook__  # main.py shows a crash dialog; a test should just fail
o = main.Overlay(Voice(), None, lambda: 10, lambda: 4.83)
o.show_line("smug", "Subtitle test, grunt.", None)
QTest.qWait(300)
assert o.timer.isActive() and o.shown > 0, "overlay animation loop is not running"
assert all(c[:4] == b"RIFF" and len(c) > 1000 for c in CUES.values())
o.show_line("smug", "Win!", None, "win")
assert o.char.flare_amt == 1.0

# idle extras: yawn, glance, eye-roll and aura flare all render
v = Vorn()
v.afk, v.yawn_at = True, 0.0
v.roll()
v.flare()
for _ in range(20):
    v.step(1 / 30, 0.0)
assert v._effective()["aura"] > 0.5 and v._effective()["mouth"] > 0.1 and not v.render().isNull()

# brain: every field Claude returns is required by the schema
assert set(SCHEMA["required"]) == set(SCHEMA["properties"])

# Hall of Shame: caption bar added under the screenshot, on the display the game is on
from senses import WakeListener, save_moment  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    mons = [({"left": 0, "top": 0, "width": 100, "height": 50}, Image.new("RGB", (1000, 500), "red")),
            ({"left": 100, "top": 0, "width": 100, "height": 50}, Image.new("RGB", (800, 400), "blue"))]
    path = save_moment(mons, (150, 10), "You walked into your own grenade. Again.", Path(d, "hall"))
    saved = Image.open(path)
    assert saved.width == 800 and saved.height > 400 and saved.getpixel((10, 10))[2] > 200  # blue display, plus caption

# wake word: tolerant of Whisper's mishearings, ignores everything else
heard = []
w = WakeListener(None, None, lambda text, audio: heard.append(text))
VORN_NAMES = json.loads((config.PRESETS / "vorn.json").read_text(encoding="utf-8"))["WAKE_NAMES"]
w.WAKE = WakeListener.pattern(VORN_NAMES)  # the tests speak to Vorn, whichever character you have active


def say(*stretches):  # stretches of talking with short pauses between, then silence
    for s in stretches:
        w.hear(s)
    w.flush(force=True)


say("Hey Vorn, what does this boss do?")
say("hey born. where's the key")
say("Okay, Vern! reload faster")
say("hey there buddy")
say("Hey Vorn.", "how do I beat this?")  # after a bare "Hey Vorn" he chimes (None), then takes the question
say("Hey Vorn, how do I", "get past the second phase", "without dying?")  # pauses mid-question don't cut it off
say("Hey Vorn.")  # and then nothing: nothing is sent
assert heard == ["what does this boss do?", "where's the key", "reload faster", None, "how do I beat this?",
                 "how do I get past the second phase without dying?", None], heard
w.hear("Hey Vorn, wait")
w.speaking = True
w.flush()
assert heard[-1] is None and w.active()  # not sent while you're still mid-sentence

# spending: cost math, monthly ledger, cheap mode at 80%, announced once
from types import SimpleNamespace  # noqa: E402

import brain  # noqa: E402
import highlights  # noqa: E402
from character import tier_for  # noqa: E402
from memory import time_mood  # noqa: E402
from senses import Ducker, game_display, save_clip  # noqa: E402

usage = SimpleNamespace(input_tokens=1_000_000, output_tokens=100_000, cache_creation_input_tokens=0, cache_read_input_tokens=0,
                        server_tool_use=SimpleNamespace(web_search_requests=2))
assert abs(brain.cost("claude-opus-5-5", usage) - (4 + 2 + 0.02)) < 1e-9
assert abs(brain.cost("claude-haiku-5-5", usage) - (0.10 + 0.05 + 0.02)) < 1e-9
with tempfile.TemporaryDirectory() as d:
    m = Memory(Path(d, "memory.json"))
    budget = config.MONTHLY_BUDGET
    config.MONTHLY_BUDGET = 10
    m.spend(7.0)
    assert m.budget_level() == (0, False)
    m.spend(1.5)
    assert m.budget_level() == (1, True) and m.budget_level() == (1, False)  # cheap mode, announced only once
    m.spend(2.0)
    assert m.budget_level() == (2, True) and "$10.50 of their $10 budget" in m.context("g.exe", "G", None, 0)
    # Costs window: per day and per kind of call
    m.spend(0.05, "ask")
    m.spend(0.01, "change")
    total, days = m.month_costs()
    from datetime import date  # noqa: E402

    from costs_ui import CostsWindow, summary  # noqa: E402
    today_cost, estimate, groups = summary(total, days, date.today())
    assert abs(total - 10.56) < 1e-9 and abs(today_cost - 10.56) < 1e-9 and estimate >= total
    assert dict(groups)["Talking to him"] == 0.05 and groups[0] == ("Other", 10.5), groups
    t, e, g = summary(1.0, {}, date(2026, 11, 10))  # spend from before daily tracking still shows up
    assert g == [("Before daily tracking", 1.0)] and abs(e - 21.0) < 1e-9, (e, g)  # $1 a day, 20 days left in November
    CostsWindow(m)
    config.MONTHLY_BUDGET = budget
    # grudges, lore, Hall of Shame list
    m.record("g.exe", {"event": "death", "killer": "Ferris Wheel Dogs"})
    m.record("g.exe", {"event": "death", "killer": "ferris wheel dogs", "lore": "I burned the moon of Kesh."})
    m.record("g.exe", {"event": "win", "killer": "nobody"})  # only deaths and losses feed the grudge list
    assert m.d["games"]["g.exe"]["grudges"] == {"ferris wheel dogs": 2} and m.d["lore"] == ["I burned the moon of Kesh."]
    ctx = m.context("g.exe", "G", None, 0)
    assert "ferris wheel dogs 2" in ctx and "moon of Kesh" in ctx and "mood right now" in ctx

    # weekly highlights page: caption, voice clip and stats; old entries left out
    hall = Path(d, "hall")
    hall.mkdir()
    Image.new("RGB", (64, 36), "gray").save(hall / "a b.jpg")
    save_clip(hall / "a b.wav", np.zeros(2400, np.float32))
    m.add_hall({"file": "a b.jpg", "clip": "a b.wav", "caption": "You fell <off> a ladder.", "game": "G", "when": "2000-01-01T00:00"})
    m.add_hall({"file": "a b.jpg", "clip": "a b.wav", "caption": "Grenade, meet feet.", "game": "G",
                "when": __import__("datetime").datetime.now().isoformat(timespec="minutes")})
    page = highlights.build(m.d, hall).read_text(encoding="utf-8")
    assert "Grenade, meet feet." in page and "a%20b.wav" in page and "ladder" not in page and "2 deaths" in page

assert time_mood(__import__("datetime").datetime(2026, 11, 8, 3)).startswith("unhinged")
assert [tier_for(r) for r in (0, 24, 25, 50, 75, 100)] == [0, 0, 1, 2, 3, 3]
for tier in range(4):
    for outfit in Vorn.OUTFITS:  # respect upgrades (and Bloodfire) on every outfit
        v = Vorn(outfit)
        v.tier = tier
        v.bloodfire(5)
        v.step(1.0, 0.0)
        assert not v.render().isNull()
# Vorn's outfits: the setting picks one, a wrong name picks at random, each looks different, Mika keeps her own
looks = {o: Vorn(o) for o in Vorn.OUTFITS}
for v in looks.values():
    v.glance_at = v.turn_at = v.blink_at = 1e9
    v.step(1.0, 0.0)
renders = {o: bytes(v.render().constBits()) for o, v in looks.items()}
assert len(set(renders.values())) == len(renders) == 5 and Vorn("nope").outfit in Vorn.OUTFITS
saved_outfit, config.VORN_OUTFIT = config.VORN_OUTFIT, "obsidian"
assert Vorn().outfit == "obsidian"
config.VORN_OUTFIT = saved_outfit
assert game_display([({"left": 0, "top": 0, "width": 10, "height": 10}, None), ({"left": 10, "top": 0, "width": 10, "height": 10}, None)], (15, 5)) == 1
config.DUCK_TO, duck = 1.0, Ducker()
duck.duck()
assert duck.saved == []  # ducking off: other apps untouched

# settings window: every value it saves has the type config.py expects, so nothing gets silently ignored
from settings_ui import SettingsWindow  # noqa: E402

saved = SettingsWindow(lambda: None, None).values()
for key, value in saved.items():
    default = getattr(config, key)
    assert type(value) is type(default) or (key == "BEDTIME" and isinstance(value, list)), (key, value, default)
assert not SettingsWindow(lambda: None, None).problems(saved)

import settings_ui  # noqa: E402

import shutil  # noqa: E402

real_file, settings_ui.FILE = settings_ui.FILE, Path(tempfile.mkdtemp()) / "settings.json"
real_presets, config.PRESETS = config.PRESETS, Path(tempfile.mkdtemp())  # never touch the real characters
shutil.copy(real_presets / f"{config.PRESET}.json", config.PRESETS)
win = SettingsWindow(lambda: None, None)
win.get["NAME"] = lambda: "Krag"
win.get["SCALE"] = lambda: 1.25
win.save()
written = json.loads(settings_ui.FILE.read_text(encoding="utf-8"))
preset = json.loads((config.PRESETS / f"{config.PRESET}.json").read_text(encoding="utf-8"))
assert written == {k: v for k, v in written.items() if k not in config.PRESET_KEYS} and written["SCALE"] == 1.25, written
assert preset["NAME"] == "Krag" and preset["PERSONA"] == config.PERSONA, preset  # the character's fields go to its preset
settings_ui.FILE, config.PRESETS = real_file, real_presets
assert "grunt" not in config.PERSONA.split("Never call")[0]  # he turned "a grunt" into a nickname for every line

import logging  # noqa: E402
import time  # noqa: E402

watch_calls, real_sleep = [], time.sleep


def flaky_watch():
    watch_calls.append(1)
    if len(watch_calls) == 1:
        raise RuntimeError("BitBlt failed")  # what killed his comments for good
    raise SystemExit  # a BaseException, so it ends the test loop


time.sleep, _ = (lambda s: None), logging.disable(logging.CRITICAL)
try:
    main.Companion.watcher(SimpleNamespace(_watch=flaky_watch))
except SystemExit:
    pass
time.sleep, _ = real_sleep, logging.disable(logging.NOTSET)
assert len(watch_calls) == 2, watch_calls  # the watcher came back after the failed screenshot

# cheaper calls: web search only when asked for; the game's display sharp, the others small
assert all(main.SEARCH_ASKED.search(q) for q in ("look it up", "Can you search the build?", "google that boss", "any guide for this"))
assert not any(main.SEARCH_ASKED.search(q) for q in ("how do I beat this boss?", "what do you think of my aim", "researcher"))
from unittest import mock  # noqa: E402

from senses import Eyes  # noqa: E402

screens = [({"left": 0, "top": 0, "width": 5120, "height": 1440}, Image.new("RGB", (5120, 1440))),
           ({"left": 5120, "top": 0, "width": 3840, "height": 2160}, Image.new("RGB", (3840, 2160)))]
with mock.patch.object(Eyes, "grab", lambda self: screens):
    sizes = [Image.open(io.BytesIO(base64.b64decode(j))).size for j in Eyes().look((6000, 900))[1]]
assert sizes == [(768, 216), (1568, 882)], sizes  # the game is on the 4K display
with mock.patch.object(Eyes, "grab", lambda self: screens):
    sizes = [Image.open(io.BytesIO(base64.b64decode(j))).size for j in Eyes().look()[1]]
assert sizes == [(1568, 441), (1568, 882)], sizes  # no game point: everything sharp

# moving his memory to another PC: export, import (with a backup first), and nothing escapes his folder
import zipfile  # noqa: E402

import transfer  # noqa: E402

with tempfile.TemporaryDirectory() as old_pc, tempfile.TemporaryDirectory() as new_pc:
    old, new = Path(old_pc), Path(new_pc)
    (old / "memory.json").write_text('{"respect": 77}', encoding="utf-8")
    (old / "battle reports.txt").write_text("report", encoding="utf-8")
    (old / "Hall of Shame").mkdir()
    (old / "Hall of Shame" / "fail.jpg").write_bytes(b"jpg")
    export = transfer.export_memory(old, old / "export.zip")
    (new / "memory.json").write_text('{"respect": 3}', encoding="utf-8")
    backup = transfer.import_memory(new, export)
    assert json.loads((new / "memory.json").read_text(encoding="utf-8")) == {"respect": 77}
    assert (new / "Hall of Shame" / "fail.jpg").read_bytes() == b"jpg" and (new / "battle reports.txt").exists()
    assert json.loads(zipfile.ZipFile(backup).read("memory.json")) == {"respect": 3}  # the memory it replaced
    with zipfile.ZipFile(new / "evil.zip", "w") as z:
        z.writestr("memory.json", "{}")
        z.writestr("Hall of Shame/../../escaped.txt", "x")
        z.writestr("Hall of Shame\\..\\..\\escaped2.txt", "x")
        z.writestr("api_key.txt", "x")
    (new / "sub").mkdir()
    transfer.import_memory(new / "sub", new / "evil.zip")
    assert not any((new / n).exists() for n in ("escaped.txt", "escaped2.txt", "sub/api_key.txt"))
    with zipfile.ZipFile(new / "notvorn.zip", "w") as z:
        z.writestr("photo.jpg", "x")
    try:
        transfer.import_memory(new, new / "notvorn.zip")
        raise AssertionError("imported a zip with no memory.json")
    except ValueError:
        pass
    frozen = Memory(new / "memory.json")
    frozen.frozen = True
    frozen.d["respect"] = 1
    frozen.save()
    assert json.loads((new / "memory.json").read_text(encoding="utf-8")) == {"respect": 77}  # no save over an import

# free local model through Ollama: same reply format as Claude, costs nothing, raises on failure so he falls back to Claude
import http.server  # noqa: E402
import threading  # noqa: E402

seen = []


class FakeOllama(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen.append(body)
        if body["model"] == "broken":
            self.send_response(500)
            self.end_headers()
            return
        reply = json.dumps({"message": {"content": json.dumps({"mood": "smug", "line": "Free roast.", "event": "death", "extra": 1})}})
        self.send_response(200)
        self.end_headers()
        self.wfile.write(reply.encode())

    def log_message(self, *args):
        pass


server = http.server.HTTPServer(("127.0.0.1", 0), FakeOllama)
threading.Thread(target=server.serve_forever, daemon=True).start()
real_ollama, brain.OLLAMA = brain.OLLAMA, f"http://127.0.0.1:{server.server_port}"
out, spent = brain.local_think("qwen3-vl:8b-instruct", "stats", [], "Roast them.", ["aW1n"])
assert spent == 0.0 and out["line"] == "Free roast." and out["event"] == "death" and out["killer"] == "" and "extra" not in out
assert seen[0]["format"] == brain.SCHEMA and seen[0]["messages"][1]["images"] == ["aW1n"] and not seen[0]["stream"]
try:
    brain.local_think("broken", "stats", [], "Roast them.", [])
    raise AssertionError("a failing local model must raise so he falls back to Claude")
except OSError:
    pass
brain.OLLAMA = real_ollama
server.shutdown()

# Discord calls: devices by name, "remember my voice", voice matching, friend notes, VoiceMeeter routes, swearing
import senses  # noqa: E402
import voices  # noqa: E402

fake_devices = [{"name": "Microphone (HyperX Cloud Alpha ", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0},
                {"name": "Voicemeeter AUX Input (VB-Audio", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2},
                {"name": "Voicemeeter Out B2 (VB-Audio Vo", "hostapi": 0, "max_input_channels": 2, "max_output_channels": 0},
                {"name": "Voicemeeter AUX Input (VB-Audio Voicemeeter VAIO)", "hostapi": 1, "max_input_channels": 0,
                 "max_output_channels": 2}]
with mock.patch.object(senses.sd, "query_devices", lambda: fake_devices), \
        mock.patch.object(senses.sd, "query_hostapis", lambda: [{"name": "MME"}, {"name": "Windows WASAPI"}]):
    assert senses.find_device("Microphone (HyperX Cloud Alpha 2 Wireless Chat)", "input") == 0  # MME cut the name
    assert senses.find_device("voicemeeter aux input", "output") == 1 and senses.find_device("Voicemeeter Out B2", "input") == 2
    logging.disable(logging.CRITICAL)  # the miss below is on purpose: keep its warning out of his real log
    assert senses.find_device("", "input") is None and senses.find_device("Voicemeeter AUX Input", "input") is None
    logging.disable(logging.NOTSET)
    assert senses.device_names("output") == ["Voicemeeter AUX Input (VB-Audio Voicemeeter VAIO)"]
for said, name in (("remember my voice, I'm Mike.", "Mike"), ("Learn my voice. My name is Sam", "Sam"),
                   ("remember my voice please, it's Tess", "Tess"), ("save my voice: Raj", "Raj"), ("remember my voice", None)):
    m = main.ENROLL.search(said)
    assert (m.group(1) if m else None) == name, (said, m and m.group(1))
a, b = np.eye(4, dtype=np.float32)[:2]
prints = {"mike": voices.learn(None, a), "sam": voices.learn(None, b)}
assert voices.identify(prints, voices.learn(None, a + 0.2 * b))[0] == "mike"
assert voices.identify(prints, voices.learn(None, a + b))[0] is None  # too close to call: nobody, rather than the wrong one
assert voices.identify({}, a) == (None, 0.0)
with tempfile.TemporaryDirectory() as d:
    m = Memory(Path(d, "memory.json"))
    m.record("g.exe", {"remember": "Mike blames lag for everything."}, friend="mike")
    m.record("g.exe", {"remember": "The player camps in corners."})
    assert m.d["friends"]["mike"]["notes"] == ["Mike blames lag for everything."] and len(m.d["notes"]) == 1
    assert "Mike: Mike blames lag for everything." in m.context("g.exe", "G", None, 0)


class FakeVoices:
    def fingerprint(self, clip):
        return a


comp = SimpleNamespace(voices=FakeVoices(), mem=Memory(Path(tempfile.mkdtemp(), "memory.json")))
clip = np.zeros(16000 * 2, np.float32)
assert main.Companion.who(comp, "remember my voice, I'm Mike", clip) == ("mike", True)
assert main.Companion.who(comp, "roast him, he's trash", clip) == ("mike", False)  # known by his voice now
assert main.Companion.who(comp, "short", np.zeros(100, np.float32)) == (None, False)  # too short to tell
swear = config.SWEAR
config.SWEAR = True
assert "swear freely" in brain.system() and "Never slurs" in brain.system()
config.SWEAR = False
assert "swear freely" not in brain.system()
config.SWEAR = swear

# local voice: Kokoro on this PC, the online voice as backup if it fails
assert senses.speed_of("+6%") == 1.06 and senses.speed_of("-10%") == 0.9 and senses.speed_of("") == 1.0
used = []


class FakeCommunicate:
    def __init__(self, text, voice, rate, pitch):
        used.append(voice)

    async def stream(self):
        yield {"type": "audio", "data": b"mp3"}


logging.disable(logging.CRITICAL)
with mock.patch.object(senses.Voice, "kokoro", side_effect=RuntimeError("no model")), \
        mock.patch.object(senses.edge_tts, "Communicate", FakeCommunicate), \
        mock.patch.object(senses.miniaudio, "decode", lambda *a, **k: SimpleNamespace(samples=np.zeros(5, np.float32).tobytes())):
    backup = senses.Voice().synth("Hi.", voice="kokoro:am_michael")
logging.disable(logging.NOTSET)
assert used == [senses.ONLINE] and len(backup) == 5
if (senses.KOKORO / "voices-v1.0.bin").exists():  # the real thing, when the model is on this PC
    spoken = senses.Voice().synth("Pathetic, noob.", voice="kokoro:am_michael")
    assert len(spoken) > senses.SR * 0.3 and np.abs(spoken).max() > 0.05

# freshness: a near word-for-word repeat of one of his recent lines is dropped (not spoken, not counted again)
said = ["Player: nice", "You: Finally, the soundboard monk dares to kill someone. One kill doesn't make a warrior."]
assert main.repeats("Finally, the soundboard monk dares to kill someone. One kill doesn't make a warlord, you know.", said)
assert not main.repeats("You died again? Fourteen deaths, that's a cry for help.", said)
assert not main.repeats("Finally, the soundboard monk dares to kill someone.", ["Player: Finally, the soundboard monk dares to kill someone."])

# characters: each keeps their own respect and past; the wake word follows the name
with tempfile.TemporaryDirectory() as d:
    real_preset, config.PRESET = config.PRESET, "vorn"  # start as Vorn, whichever character you have active
    m = Memory(Path(d, "memory.json"))
    m.d["respect"], m.d["lore"], m.d["total_seconds"] = 64, ["I burned the moon of Kesh."], 3600
    m.pin("Vorn knows my main is the M40A3")
    m.remember("Vorn's note")
    m.record("g.exe", {"event": "death", "killer": "dogs"})
    m.spend(0.25, "ask")
    m.save()
    config.PRESET = "mika"
    m2 = Memory(Path(d, "memory.json"))
    assert m2.d["respect"] == 10 and m2.d["lore"] == [] and m2.d["pinned"] == [] and m2.d["notes"] == [] and m2.d["games"] == {}
    assert m2.d["characters"]["vorn"]["respect"] == 64 and m2.d["total_seconds"] == 3600 and m2.spent() == 0.25  # shared
    assert "M40A3" not in m2.context("g.exe", "G", None, 0, query="main")  # Mika doesn't know what Vorn was told
    m2.d["respect"] = 33
    m2.pin("Mika knows I hate campers")
    m2.save()
    config.PRESET = "vorn"
    m3 = Memory(Path(d, "memory.json"))
    assert m3.d["respect"] == 64 and m3.d["lore"] == ["I burned the moon of Kesh."] and m3.d["characters"]["mika"]["respect"] == 33
    assert m3.d["pinned"] == ["Vorn knows my main is the M40A3"] and m3.d["games"]["g.exe"]["grudges"] == {"dogs": 1}
    assert len(m3.d["notes"]) == 1 and "campers" not in m3.context("g.exe", "G", None, 0)
    m3.add_lore("I stalked a raid boss for a week.", "mika")  # duo mode: Mika's story goes to Mika
    m3.add_lore("I burned the moon of Kesh.")  # already told: not twice
    assert m3.d["lore"] == ["I burned the moon of Kesh."] and m3.d["characters"]["mika"]["lore"] == ["I stalked a raid boss for a week."]
    assert "raid boss" in m3.partner_context("mika", "Mika") and "raid boss" not in m3.context("g.exe", "G", None, 0)
    # the local model voicing one of them sees only that one's stories
    assert "raid boss" not in m3.partner_context("mika", "Mika", stories=False) and "Kesh" not in m3.context("g.exe", "G", None, 0, stories=False)
    config.PRESET = real_preset
assert WakeListener.pattern(VORN_NAMES).search("hey vern, look") and "{power}" in config.RULES and config.POWER in brain.system()
assert WakeListener.pattern(json.loads((config.PRESETS / "mika.json").read_text(encoding="utf-8"))["WAKE_NAMES"]).search("Hey Micah, look")
assert type(main.make_character("vorn")).__name__ == "Vorn"

# Mika: her preset loads, every outfit and mood renders inside her window, Lovesick takes the light from her eyes
from mika import OUTFITS, Mika  # noqa: E402

mika_preset = json.loads((config.PRESETS / "mika.json").read_text(encoding="utf-8"))
assert mika_preset["CHARACTER"] == "mika" and set(mika_preset) == set(config.PRESET_KEYS)
assert type(main.make_character("mika")).__name__ == "Mika" and Mika("nope").outfit in OUTFITS
for outfit in OUTFITS:
    for mood in MOODS:
        for toward in (1.0, -1.0):
            v = Mika(outfit)
            v.toward = toward
            v.set_mood(mood)
            for _ in range(60):
                v.step(1 / 30, 0.3)
            v.p["aura"], v.flare_amt = 0.0, 0.0
            img = v.render()
            edges = [img.pixelColor(x, y).alpha() for x in (0, img.width() - 1) for y in range(0, img.height(), 3)]
            assert max(edges + [img.pixelColor(x, 0).alpha() for x in range(img.width())]) == 0, (outfit, mood, toward)
v = Mika("jacket")
v.bloodfire(8)
for _ in range(60):
    v.step(1 / 30, 0.0)
assert v.blood > 0.95 and not v.render().isNull() and not v.render(0.3, bust=True).isNull()

# Discord camera: frames for one character or both, every background, subtitles; an ultrawide game screen is cropped, not squashed
import camera as cam_mod  # noqa: E402

assert cam_mod.fit(Image.new("RGB", (5120, 1440)), 1280, 720).size == (1280, 720)
stub = SimpleNamespace(char=Vorn(), text="Pathetic aim, again.", shown=8.0)
for mode in ("current", "both"):
    for bg in cam_mod.BACKGROUNDS:
        config.CAMERA, config.CAMERA_BACKGROUND = mode, bg
        c = cam_mod.Camera(stub, lambda: (0, 0))
        c.other = main.make_character("mika") if mode == "both" else None
        c.background = QImage(1280, 720, QImage.Format_RGB888) if bg in ("game", "webcam") else None
        frame = c.frame()
        assert frame.shape == (720, 1280, 3) and frame.std() > 5, (mode, bg)
config.CAMERA, config.CAMERA_BACKGROUND = "off", "dark"

# friends' ear on a call's audio: a missing speaker or device is refused (never a silent fallback to your own mic)
assert not senses.listen_source_ok("loopback:No Such Speaker 123") and not senses.listen_source_ok("No Such Mic 123")

# long-term memory: pinned facts stay, "forget" removes them, old notes fold into the profile, the window round-trips
for said, fact in (("remember that my main is the M40A3", "my main is the M40A3"), ("Don't forget I hate snipers.", "I hate snipers."),
                   ("remember my voice, I'm Mike", None), ("how do I remember the map", None)):
    m = main.REMEMBER.match(said)
    assert (m.group(1) if m else None) == fact, (said, m and m.group(1))
assert main.FORGET.match("forget about the M40A3").group(1) == "the M40A3"
from memories_ui import MemoriesWindow  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    m = Memory(Path(d, "memory.json"))
    m.pin("My main is the M40A3.")
    m.pin("my main is the m40a3")  # no duplicates
    m.pin("I hate snipers")
    m.d["notes"] = [f"2026-11-0{i % 9 + 1}: note {i}" for i in range(38)] + ["2026-11-08: Plays CoD4 on a 5120x1440 screen."]
    assert m.d["pinned"] == ["My main is the M40A3", "I hate snipers"], m.d["pinned"]
    old = m.old_notes()
    assert len(old) == 20 and old[0].endswith("note 0")
    m.condensed(old, "DivxPlays, plays CoD4, mains the M40A3.")
    assert len(m.d["notes"]) == 19 and m.d["profile"].startswith("DivxPlays") and not m.old_notes()
    ctx = m.context("g.exe", "G", None, 0)
    assert "long-term picture of the player: DivxPlays" in ctx and "always remember:\n- My main is the M40A3" in ctx
    assert m.unpin("the M40A3") == ["My main is the M40A3"] and m.d["pinned"] == ["I hate snipers"]
    win = MemoriesWindow(m, "Mika")
    win.pinned.addItem("Birthday is in March")
    win.save()
    assert m.d["pinned"] == ["I hate snipers", "Birthday is in March"] and json.loads(Path(d, "memory.json").read_text(encoding="utf-8"))["pinned"][-1] == "Birthday is in March"

# 500 pinned facts: the cap holds without dropping any, only relevant ones are sent, and they're Vorn's alone
import memory as memory_mod  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    real_preset, config.PRESET = config.PRESET, "vorn"
    m = Memory(Path(d, "memory.json"))
    config.PRESET = real_preset
    for i in range(memory_mod.MAX_PINNED - 1):
        assert m.pin(f"Fact number {i} about crate {i}")
    assert m.pin("My favorite sniper rifle is the M40A3")  # the 500th fits
    assert not m.pin("One fact too many") and len(m.d["pinned"]) == 500 and m.d["pinned"][0] == "Fact number 0 about crate 0"
    m.d["pinned"].insert(3, m.d["pinned"].pop())  # bury the rifle fact among the old ones
    shown = m.relevant_pinned("what's my favorite sniper rifle again")
    assert "My favorite sniper rifle is the M40A3" in shown and len(shown) <= memory_mod.SHOW_PINNED, len(shown)
    assert m.d["pinned"][-1] in shown  # the newest always come along
    m.save()
    contexts = {}
    for preset in ("vorn", "mika", "vorn"):
        real_preset, config.PRESET = config.PRESET, preset
        mem = Memory(Path(d, "memory.json"))
        contexts[preset] = mem.context("iw3mp.exe", "Call of Duty 4", None, 0, query="what's my favorite sniper rifle")
        mem.save()
        config.PRESET = real_preset
    assert "My favorite sniper rifle is the M40A3" in contexts["vorn"] and "more facts are stored" in contexts["vorn"]
    assert contexts["vorn"].count("\n- Fact number") < 45  # not all 500 in one message
    assert "M40A3" not in contexts["mika"]  # Mika has her own memory

# duo mode: both on screen, one exchange per reaction, the right one talks, and the one you called answers first
names = ["Vorn", "Mika"]
assert main.turns_of({"turns": [{"speaker": "Mika", "mood": "smug", "line": "Mine."}, {"speaker": "Bob", "mood": "idle", "line": "x"},
                                {"speaker": "Vorn", "mood": "angry", "line": " Weak. "}]}, names) == [("Mika", "smug", "Mine."), ("Vorn", "angry", "Weak.")]
assert main.turns_of({"mood": "smug", "line": "Solo."}, names) == [("Vorn", "smug", "Solo.")]  # a refusal or a solo reply still works
assert main.repeats("Mine, all mine.", ["You (Mika): Mine, all mine!"])
saved_duo = (config.DUO, config.PRESET, config.NAME, config.CHARACTER, config.PERSONA)
config.DUO, config.PRESET, config.NAME, config.CHARACTER = True, "vorn", "Vorn", "vorn"
config.PERSONA = json.loads((config.PRESETS / "vorn.json").read_text(encoding="utf-8"))["PERSONA"]
assert brain.partner()["NAME"] == "Mika" and "turns" in brain.schema()["properties"] and "line" not in brain.schema()["properties"]
assert brain.schema()["properties"]["turns"]["items"]["properties"]["speaker"]["enum"] == ["Vorn", "Mika"]
assert "=== Vorn ===" in brain.system() and "=== Mika ===" in brain.system() and "Duo mode" in brain.system()
# a story belongs to whoever told it; the one you called answers alone; nobody's past leaks into the other's
assert "lore" not in brain.schema()["properties"] and "lore" in brain.schema()["properties"]["turns"]["items"]["required"]
assert "conquests" not in main.SITUATIONS["lore"]  # Vorn's word, and every character tells stories
comeback = main.COMEBACK_SAYS.format(a="Mika", line="I stole a {controller}.")  # the other one fires back, keeping to their own past
assert '"I stole a {controller}."' in comeback and "never tell Mika's stories" in comeback and 0 < main.COMEBACK < 1
wake_of = {"Vorn": VORN_NAMES, "Mika": brain.partner()["WAKE_NAMES"]}
assert main.addressed("Hey Mika, how was your day?", wake_of) == "Mika"
assert main.addressed("hey vern, ask mika what she thinks", wake_of) == "Vorn"  # the first one called
assert main.addressed("how was everyone's day?", wake_of) is None
sent = []


class FakeOllama:  # answers local_think's HTTP call here
    def __init__(self, req, timeout=None):
        sent.append(json.loads(req.data))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps({"message": {"content": json.dumps({"mood": "smug", "line": "Mine.", "lore": "a tale"})}}).encode()


real_urlopen, brain.urllib.request.urlopen = brain.urllib.request.urlopen, FakeOllama
try:
    speakers = set()
    for alone in (brain.me(), brain.partner()):  # the small local model voices one of them per comment, with only that one's persona
        out, _ = brain.local_think("m", "ctx", ["You (Mika): Mine."], "now", [], only=alone)
        who = out["turns"][0]["speaker"]
        speakers.add(who)
        system_text, user_text = sent[-1]["messages"][0]["content"], sent[-1]["messages"][1]["content"]
        assert len(out["turns"]) == 1 and out["turns"][0]["lore"] == "" and f"You are {who}," in system_text
        assert "Duo mode" not in system_text and ("warlord" in system_text) == (who == "Vorn")
        assert "Mika: Mine." in user_text and "You (Mika)" not in user_text
finally:
    brain.urllib.request.urlopen = real_urlopen
assert speakers == {"Vorn", "Mika"}

# free voice commands: a whole sentence that is a command is handled on this PC, no API call; anything else goes to Claude
import commands  # noqa: E402

V, M = sorted(Vorn.OUTFITS), sorted(OUTFITS)
chars = {"vorn": VORN_NAMES, "mika": ["mika", "micah"]}
for text, outfits, want in [
        ("Shut up for 10 minutes.", V, ("mute", 600)), ("shut up", V, ("mute", None)), ("Be quiet for half an hour please", V, ("mute", 1800)),
        ("shut up for a minute", V, ("mute", 60)), ("Can you be quiet for a while?", V, ("mute", 600)), ("You can talk again.", V, ("unmute", None)),
        ("Stop looking at my screen.", V, ("vision", False)), ("Look again", V, ("vision", True)),
        ("How much have you cost me this month?", V, ("cost", None)), ("Change your outfit.", V, ("outfit", None)),
        ("Wear the hoodie.", V, ("outfit", "off-duty")), ("Wear the hoodie.", M, ("outfit", "hoodie")),
        ("Put on your obsidian armor", V, ("outfit", "obsidian")), ("Switch to the desert one", V, ("outfit", "desert raider")),
        ("Switch to Micah.", V, ("switch", "mika")), ("Both of you.", V, ("switch", "both")), ("Go back to Vorn", M, ("switch", "vorn")),
        ("Shut up, you're wrong about that map.", V, None), ("How much did this game cost?", V, None), ("I want pizza", V, None),
        ("Wear something cool", V, None), ("Switch to a better loadout", V, None)]:
    assert commands.parse(text, outfits, chars) == want, (text, commands.parse(text, outfits, chars), want)
assert commands.duration(600) == "10 minutes" and commands.duration(3600) == "an hour" and commands.money(12.07) == "12 dollars and 7 cents"
done = []
fake = SimpleNamespace(  # just what Companion.command touches: duo mode, Vorn current, Mika beside him
    wake_of={"Vorn": VORN_NAMES, "Mika": ["mika", "micah"]}, partner=brain.partner(), names=["Vorn", "Mika"],
    dressers=[Vorn("warlord"), Mika("jacket")], recent=[], mem=SimpleNamespace(spent=lambda: 1.5, line=lambda t: None),
    set_mute=lambda on, seconds=0: done.append(("mute", on, seconds)), set_pause=lambda on: done.append(("pause", on)),
    bridge=SimpleNamespace(wear=SimpleNamespace(emit=lambda i, n: done.append(("wear", i, n))),
                           switch=SimpleNamespace(emit=lambda t: done.append(("switch", t)))),
    speak=lambda mood, line, event, who: (done.append(("say", who, line)), (line, None))[1])
for said, want in [("Hey Mika, wear the hoodie.", ("wear", 1, "hoodie")), ("Hey Vorn, wear the hoodie.", ("wear", 0, "off-duty")),
                   ("Hey Vorn, shut up for 10 minutes.", ("mute", True, 600)), ("Hey Mika, stop looking.", ("pause", True)),
                   ("Hey Mika, how much have you cost me?", None), ("Hey Mika, switch to Vorn.", ("switch", "vorn")),
                   ("Hey Vorn, both of you.", None)]:
    done.clear()
    assert main.Companion.command(fake, said), said
    who = "Mika" if "Mika," in said else "Vorn"
    assert (want is None or want in done) and any(d[0] == "say" and d[1] == who for d in done), (said, done)
    assert not any(d[0] == "switch" for d in done) or "switch to" in said  # "both of you" while they're both here: no restart
assert "1 dollar and 50 cents" in fake.recent[-5] and "10 minutes" in fake.recent[-9]  # what they said back is in the dialogue
done.clear()
assert not main.Companion.command(fake, "Hey Vorn, how was your day?") and not done  # a normal question goes to Claude
duo = main.Overlay(Voice(), None, lambda: 10, lambda: 0.0)
assert [type(c).__name__ for c in duo.chars] == ["Vorn", "Mika"] and duo.width() > o.width()
duo.show_line("angry", "Hands off my player.", None, "none", "Mika")
assert duo.speaking == 1 and duo.text.startswith("Mika: ") and duo.chars[1].mood == "angry" and duo.chars[0].mood == "surprised"
config.DUO, config.PRESET, config.NAME, config.CHARACTER, config.PERSONA = saved_duo
assert brain.partner() is None or config.DUO
heard_duo = []
wl = WakeListener(None, None, lambda text, audio: heard_duo.append(text))
wl.WAKE, wl.keep_name = WakeListener.pattern(["vorn", "mika"]), True
wl.hear("Hey Mika, am I getting better?")
wl.flush(force=True)
assert heard_duo == ["Hey Mika, am I getting better?"], heard_duo
wl.hear("Hey Mika.")  # the name, a pause, then the question: the name must still reach them
wl.hear("You look pretty today.")
wl.flush(force=True)
assert heard_duo[-1] == "Hey Mika, You look pretty today.", heard_duo
assert main.addressed(heard_duo[-1], {"Vorn": VORN_NAMES, "Mika": ["mika", "micah"]}) == "Mika"
# interrupting: talk over him and he pauses to listen; he carries on if it wasn't to him, stops for good if it was
import senses  # noqa: E402

real_sd = (senses.sd.play, senses.sd.stop)
senses.sd.play = senses.sd.stop = lambda *a, **k: None  # no real sound in a test
try:
    said_to_him, heard_now = [], [""]
    ears = SimpleNamespace(recording=False, transcribe=lambda audio, prompt=None: heard_now[0])
    voice = Voice()
    mic = WakeListener(ears, voice, lambda text, audio: said_to_him.append(text))
    mic.WAKE, mic.interrupts = WakeListener.pattern(["vorn"]), True
    loud, hush = np.full(1600, 0.2, np.float32), np.zeros(1600, np.float32)

    def talk_over(words, chunks=6):
        """He's mid-line; you say `words` for `chunks` tenths of a second, then go quiet."""
        heard_now[0] = words
        voice.cut = False
        voice.play(np.zeros(senses.SR * 5, np.float32))
        voice._t0 -= 1.0  # a second into his line
        for _ in range(chunks):
            mic.take(loud)
        paused = voice.paused()
        for _ in range(7):
            mic.take(hush)
        return paused

    assert not talk_over("cough", chunks=2) and voice.busy()  # a cough: he doesn't even pause
    assert talk_over("Ha ha ha.") and voice.busy() and not voice.paused() and not voice.cut  # you laughed: he carried on
    assert abs((time.monotonic() - voice._t0) - 0.75) < 0.1  # from a quarter second before where he stopped
    assert talk_over("Hey Vorn, shut up.") and not voice.busy() and voice.cut  # you called him: he stopped for good
    mic.flush(force=True)
    assert said_to_him == ["shut up."], said_to_him
    deaf = WakeListener(ears, voice, lambda text, audio: said_to_him.append(text))  # the Discord loopback hears his own voice
    voice.play(np.zeros(senses.SR * 5, np.float32))
    for _ in range(6):
        deaf.take(loud)
    assert not voice.paused() and deaf.speech == []
finally:
    senses.sd.play, senses.sd.stop = real_sd

# two on screen never look like copies: the listener makes a different face, and their idle motion is out of step
assert all(main.REACT[m] != m for m in main.REACT if m != "idle")
assert main.make_character("vorn").t != main.make_character("vorn").t

# About: a real version number and who made it
assert re.fullmatch(r"\d+\.\d+\.\d+", main.VERSION) and main.AUTHOR == "DivxPlays"

# Bloodfire: epic plays, two wins in a row, or reaching 100 respect; he ignites, then cools down
assert main.bloodfire(0, "epic", 40, 43) == (1, "bloodfire")
assert main.bloodfire(0, "win", 40, 43) == (1, None) and main.bloodfire(1, "win", 40, 43) == (2, "bloodfire")
assert main.bloodfire(2, "death", 40, 38) == (0, None) and main.bloodfire(3, "menu", 40, 40) == (3, None)
assert main.bloodfire(0, "none", 98, 100) == (0, "bloodfire-max") and main.bloodfire(0, "win", 100, 100) == (1, None)
v = Vorn()
v.set_mood("angry")
plain = v.render()
v.bloodfire(8)
for _ in range(60):
    v.step(1 / 30, 0.0)
burning = v.render()
assert v.blood > 0.95 and burning != plain
hair = burning.pixelColor(int(main.CW / 2), int(main.HEAD_Y - 40))  # above his eyes: flaming red hair
assert hair.red() > 2 * hair.blue(), hair.name()
for _ in range(300):  # 10 s later he has cooled down
    v.step(1 / 30, 0.0)
assert v.blood < 0.05

print("all self-checks passed", flush=True)
os._exit(0)  # same exit as main.py: skip Qt's teardown order
