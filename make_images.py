"""Draws the pictures in docs/images/ straight from the code, so the GitHub page shows how they look right now.
Run it after changing how they look:  .venv\\Scripts\\python make_images.py
"""
import os
import random
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))  # else text is boxes

from PIL import Image  # noqa: E402
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import config  # noqa: E402

# the pictures use the defaults, never your own settings (size, corner, budget...), and show both characters
for key, value in config._DEFAULTS.items():
    setattr(config, key, value)
config.DUO, config.CAMERA_BACKGROUND = True, "dark"
import main  # noqa: E402
import character  # noqa: E402
from character import H, VORN_HOLIDAY, VORN_LOOKS, VORN_UNLOCKS, W, Vorn  # noqa: E402
from mika import UNLOCKS as MIKA_UNLOCKS, Mika  # noqa: E402
from senses import Voice  # noqa: E402

sys.excepthook = sys.__excepthook__  # an error here is this script's, not a "Vorn crashed" popup
OUT = Path(__file__).with_name("docs") / "images"


def pose(char, mood="idle", power=False):
    """Settle a character into a mood: facing front, eyes open, powered up if asked."""
    char.glance_at = char.turn_at = 1e9
    char.glance_to = 0.0
    char.set_mood(mood)
    if power:
        char.bloodfire(60)  # Vorn's Bloodfire, Mika's Lovesick
    for _ in range(5):
        char.step(1.0, 0.0)
    return char


def backdrop(imgs, name, pad=16):
    """Pictures side by side on the Discord camera's dark backdrop (readable on GitHub's light and dark themes)."""
    out = QImage(sum(i.width() for i in imgs) + 2 * pad, max(i.height() for i in imgs) + 2 * pad, QImage.Format_RGB32)
    grad = QLinearGradient(0, 0, 0, out.height())
    grad.setColorAt(0, QColor("#24202c"))
    grad.setColorAt(1, QColor("#0e0c12"))
    g = QPainter(out)
    g.fillRect(out.rect(), grad)
    x = pad
    for img in imgs:
        g.drawImage(x, pad, img)
        x += img.width()
    g.end()
    out.save(str(OUT / name))


def acting(char, name, mood="idle"):
    """A character in the middle of one of their idle animations."""
    pose(char, mood)
    char.IDLES = {**type(char).IDLES, name: {**type(char).IDLES[name], "time": 100}}  # held mid-play
    char.act, char.act_t0 = name, char.t - 50
    char.afk = char.was_afk = name == "nod off"
    for _ in range(45):
        char.step(1 / 30, 0.0)
    return char


def thrown(char, angle, rag, heap=False):
    """A character mid-throw (flailing and turned) or in a heap after it, as the flying window draws them."""
    pose(char, "angry" if heap else "surprised")
    char.rag = rag
    if heap:
        char.slump()
    for _ in range(12):
        char.step(1 / 30, 0.0)
    side = int(H * 1.15)
    img = QImage(side, side, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)
    g = QPainter(img)
    g.setRenderHint(QPainter.Antialiasing)
    g.translate(side / 2, side / 2)
    g.rotate(angle)
    g.translate(-W / 2, -H / 2)
    char.paint(g)
    g.end()
    return img.scaled(int(side * 0.8), int(side * 0.8))


def lineup(chars, name, scale=1.2):
    backdrop([c.render(scale) for c in chars], name)


def main_images():
    random.seed(7)  # same pictures every run (the characters' random head start), so only real changes reach GitHub
    OUT.mkdir(parents=True, exist_ok=True)
    pose(Vorn("warlord"), "smug").render(256 / 340, bust=True).save(str(OUT / "icon-vorn.png"))
    pose(Mika("jacket"), "smug").render(256 / 340, bust=True).save(str(OUT / "icon-mika.png"))
    lineup([pose(Vorn("warlord"), m) for m in ("idle", "smug", "angry", "laugh")] + [pose(Vorn("warlord"), "angry", power=True)],
           "vorn.png")
    free = [o for o in VORN_LOOKS if o not in VORN_UNLOCKS and o not in VORN_HOLIDAY.values()]
    lineup([pose(Vorn(o), m) for o, m in zip(free, ("idle", "smug", "angry", "disgusted", "laugh"))], "vorn-outfits.png")
    lineup([pose(Vorn(o), m) for o, m in zip(VORN_UNLOCKS, ("smug", "angry", "disgusted", "idle"))], "vorn-unlockables.png")
    anime = ("maid", "shrine maiden", "magical girl", "yukata", "netrunner", "track suit")
    lineup([pose(Mika(o), m) for o, m in zip(anime, ("smug", "laugh", "idle", "smug", "angry", "laugh"))], "mika-anime.png")
    lineup([pose(Mika(o), m) for o, m in zip(MIKA_UNLOCKS, ("idle", "laugh", "smug", "laugh"))], "mika-unlockables.png")
    lineup([acting(Vorn("warlord"), n) for n in ("stretch", "crack knuckles", "inspect gauntlet", "power stance", "nod off")]
           + [acting(Mika("jacket"), n) for n in ("wave", "heart hands", "adjust headset", "twirl hair")], "idle.png", scale=1.0)
    backdrop([thrown(Vorn("warlord"), 0, 1.0), thrown(Vorn("warlord"), 55, 1.0), thrown(Vorn("warlord"), 90, 0.0, True),
              thrown(Mika("jacket"), -30, 1.0), thrown(Mika("jacket"), -90, 0.0, True)], "thrown.png")
    seasons = []
    for holiday, weather in (("halloween", "bats"), ("christmas", "snow")):  # each pair in their holiday's weather
        character.WEATHER = weather
        seasons += [pose(Vorn(VORN_HOLIDAY[holiday]), "smug").render(1.2), pose(Mika(Mika.HOLIDAY[holiday]), "laugh").render(1.2)]
    character.WEATHER = None
    backdrop(seasons, "holidays.png")
    first = ("gothic", "hoodie", "jacket", "jersey")  # her original four, then Lovesick
    lineup([pose(Mika(o), m) for o, m in zip(first, ("smug", "laugh", "idle", "angry"))] + [pose(Mika("jacket"), "smug", power=True)],
           "mika.png")

    overlay = main.Overlay(Voice(), None, lambda: 10, lambda: 0.0)  # duo mode, as on your screen
    overlay.chars[0].outfit, overlay.chars[1].outfit = "warlord", "jacket"
    for c in overlay.chars:
        pose(c)
    overlay.show_line("smug", "Nine minutes in the menu, sweetie? Pick a game before I pick one for you.", None, "none", "Mika")
    for i, (_, mood) in overlay.later.items():  # the one listening reacts a beat later: let that beat pass
        overlay.chars[i].set_mood(mood)
    for c in overlay.chars:
        c.step(1.0, 0.0)
    overlay.shown = float(len(overlay.text))
    backdrop([overlay.grab().toImage()], "duo.png")
    Image.fromarray(main.Camera(overlay, lambda: (0, 0)).frame()).save(OUT / "camera.png")  # what Discord sees
    print("\n".join(f"{p.name}: {Image.open(p).size}" for p in sorted(OUT.glob("*.png"))))


if __name__ == "__main__":
    app = QApplication.instance() or QApplication([])
    main_images()
