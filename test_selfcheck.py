"""Quick self-check, no API key or internet needed:  python test_selfcheck.py"""
import json
import os
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import config  # noqa: E402
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
w = WakeListener(None, None, heard.append)
for said in ("Hey Vorn, what does this boss do?", "hey born. where's the key", "Okay, Vern! reload faster"):
    w.hear(said)
w.hear("hey there buddy")
w.hear("Hey Vorn.")
w.hear("how do I beat this?")  # the sentence right after a bare "Hey Vorn" is the question
assert heard == ["what does this boss do?", "where's the key", "reload faster", None, "how do I beat this?"], heard

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
    v = Vorn()
    v.tier = tier
    assert not v.render().isNull()
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

real_file, settings_ui.FILE = settings_ui.FILE, Path(tempfile.mkdtemp()) / "settings.json"
win = SettingsWindow(lambda: None, None)
win.get["NAME"] = lambda: "Krag"
win.save()
written = json.loads(settings_ui.FILE.read_text(encoding="utf-8"))
assert "PERSONA" not in written and written["NAME"] == "Krag", written  # only changes are saved
settings_ui.FILE = real_file
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

print("all self-checks passed", flush=True)
os._exit(0)  # same exit as main.py: skip Qt's teardown order
