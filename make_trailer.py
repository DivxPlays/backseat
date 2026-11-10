"""The trailer: a ~75 s video showing off Backseat, rendered straight from the code: their real drawings, outfits, power-ups,
voices, lip-sync and sound effects, over real gameplay from your own recordings (CLIPS: Medal's folder; the shots are
named in SCENES; a made-up game screen stands in without them). Only your own footage: never other people's videos, no
clip audio (one track is your mic), a stranger's name blurred. Writes dist/trailer.mp4 (attached to each release by
release.py) and docs/images/trailer.gif (a short silent teaser for the README).
Run it whenever their looks or features change:  .venv\\Scripts\\python make_trailer.py
"""
import math
import os
from functools import lru_cache
import random
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))

import av  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import config  # noqa: E402

for key, value in config._DEFAULTS.items():  # the defaults, never your own settings
    setattr(config, key, value)
import sfx  # noqa: E402
from character import H, W, Vorn  # noqa: E402
from mika import Mika  # noqa: E402
from senses import MOUTH_FPS, SR, Voice, mouth_track  # noqa: E402

HERE = Path(__file__).parent
VIDEO, GIF = HERE / "dist" / "trailer.mp4", HERE / "docs" / "images" / "trailer.gif"
WIDTH, HEIGHT, FPS = 1280, 720, 30
GOLD, CREAM, INK = QColor("#f2c64d"), QColor("#f1e9df"), QColor("#1b1418")
CLIPS = Path(os.environ.get("BACKSEAT_CLIPS", r"C:\Medal\Clips"))  # your gameplay recordings
VOICES = {"Vorn": ("kokoro:am_michael", "+6%"), "Mika": ("kokoro:jf_alpha", "+0%"), "Rook": ("kokoro:bm_george", "+0%")}


# ---------------------------------------------------------------- the script
# shots: (recording, start s, length s) from CLIPS, cut one after another; blur: boxes (1280x720) hiding a stranger's name;
# a line: (start s, speaker, mood, text); a sound: (start s, build, kind)
FN_A, FN_B = "MedalTVFortnite20261029213000414", "MedalTVFortnite20261028210434981"
DEATH = [(FN_A, 31 * 60 + 36.2, 6.5)]
NAME_BOX = [(445, 596, 775, 680)]  # "Eliminated by <a stranger>" and the match id under it
SCENES = [
    dict(time=4.5, kind="title", shots=[(FN_A, 14 * 60 + 38, 4.5)], dim=0.62, sounds=[(1.4, "vorn", "chuckle"), (2.6, "mika", "giggle")]),
    dict(time=8.5, kind="game", caption="They watch you play.", shots=[(FN_A, 13 * 60 + 6, 4.0), (FN_A, 14 * 60 + 38, 4.5)],
         lines=[(0.4, "Mika", "smug", "Seconds to the bus and you're still emoting, sweetie? Focus. On me."),
                (4.6, "Vorn", "disgusted", "You dive like a falling rock. At least rocks land somewhere useful.")]),
    dict(time=6.0, kind="game", caption="Any game, Steam or not.",
         shots=[("MedalTVBeatSaber20261024220146518", 178, 1.0), ("MedalTVRoblox20261030235142835", 24, 1.0),
                ("MedalTVCyberpunk207720261024163732758", 12 * 60 + 8, 1.0), ("MedalTVRoblox20261029234339486", 3 * 60 + 28, 1.0),
                (FN_A, 11 * 60 + 8, 1.0), (FN_B, 16 * 60 + 8, 1.0)],
         lines=[(0.6, "Vorn", "smug", "Six games, and you're bad at every single one.")]),
    dict(time=6.5, kind="game", caption="They roast every death.", shots=DEATH, blur=NAME_BOX,
         lines=[(3.4, "Vorn", "angry", "Third place. Eleven worlds conquered, and I get third place.")]),
    dict(time=7.0, kind="game", caption='Talk to them: "Hey Mika, ..."', shots=[(FN_A, 27 * 60 + 38, 7.0)],
         player=(0.3, "Hey Mika, where's he hiding?"),
         lines=[(1.8, "Mika", "laugh", "Behind the rock on the left, cutie. Peek, shoot, and don't you dare miss.")]),
    dict(time=5.0, kind="power", caption="Bloodfire and Lovesick.", shots=[(FN_A, 15 * 60 + 38, 5.0)],
         lines=[(0.6, "Vorn", "angry", "Bloodfire!")], sounds=[(2.2, "mika", "giggle")]),
    dict(time=6.0, kind="outfits", caption="{outfits} outfits: holidays, anime looks and ones you earn.",
         shots=[(FN_B, 36 * 60 + 48, 6.0)], dim=0.55),
    dict(time=5.5, kind="throw", caption="Ctrl+drag to throw them.", shots=[(FN_B, 16 * 60 + 8, 5.5)], sounds=[(1.8, "mika", "giggle")]),
    dict(time=7.0, kind="menu", caption="Mini-games in menus and queues: trivia, challenges, bounties.",
         shots=[(FN_B, 22 * 60 + 46, 7.0)],
         lines=[(0.4, "Vorn", "smug", "A challenge, weakling: three eliminations this match. Bounty: eight respect.")],
         note=(4.6, "(challenge: three eliminations, +8)")),
    dict(time=6.0, kind="squad", caption="A leaderboard for your Discord squad.", shots=[(FN_A, 29 * 60 + 38, 6.0)], dim=0.5,
         lines=[(0.6, "Mika", "smug", "Worst player of the week: Mike. Again, sweetie.")]),
    dict(time=6.0, kind="creator", caption="Make your own character.",
         lines=[(1.2, "Rook", "smug", "Ahoy, deckhand. Try not to sink this time.")]),
    dict(time=6.5, kind="clip", caption="Every fail saved, with the roast on top.", card=DEATH, blur=NAME_BOX,
         lines=[(0.8, "Vorn", "laugh", "Third place, framed forever. You're welcome.")]),
    dict(time=6.5, kind="end", sounds=[(1.0, "vorn", "scoff")]),
]
FADE = 0.3  # s of fade between scenes


@lru_cache(maxsize=1)
def version():
    text = (HERE / "main.py").read_text(encoding="utf-8")
    import updater
    v, stage = updater.VERSION.search(text).group(1), updater.STAGE.search(text).group(1)
    return updater.pretty(v if stage == "release" else f"{v}-{stage}")


# ---------------------------------------------------------------- footage
class Footage:
    """One shot from a recording: its frames from `start` on, the middle 16:9 of the screen at 1280x720, with `blur`
    boxes blurred."""

    def __init__(self, name, start, blur=()):
        self.container = av.open(str(next(CLIPS.rglob(f"{name}.*"))))
        self.stream = self.container.streams.video[0]
        self.container.seek(int(start / self.stream.time_base), stream=self.stream, backward=True)
        self.frames, self.start, self.blur = self.container.decode(self.stream), start, blur
        self.frame, self.when, self.image = None, -1.0, None

    def at(self, t):
        """The picture `t` s into the shot (a QImage), holding the last one past the recording's end."""
        target = self.start + t
        moved = False
        while self.when < target:
            try:
                self.frame = next(self.frames)
            except (StopIteration, av.error.EOFError):
                break
            self.when, moved = float(self.frame.pts * self.frame.time_base), True
        if moved or self.image is None:
            im = self.frame.to_image()
            w, h = im.size
            cw, ch = (int(h * 16 / 9), h) if w / h > 16 / 9 else (w, int(w * 9 / 16))
            im = im.crop(((w - cw) // 2, (h - ch) // 2, (w - cw) // 2 + cw, (h - ch) // 2 + ch)).resize((WIDTH, HEIGHT), Image.LANCZOS)
            for box in self.blur:
                im.paste(im.crop(box).filter(ImageFilter.GaussianBlur(16)), box[:2])
            self.data = im.tobytes("raw", "RGB")  # (kept alive for the QImage)
            self.image = QImage(self.data, WIDTH, HEIGHT, WIDTH * 3, QImage.Format_RGB888)
        return self.image

    def close(self):
        self.container.close()


class Shots:
    """A scene's shots, cut one after another; None without the recordings (the made-up screen stands in)."""

    def __init__(self):
        self.open = {}

    def frame(self, scene, shots, t):
        if not shots or not CLIPS.is_dir():
            return None
        at = 0.0
        for k, (name, start, length) in enumerate(shots):
            if t < at + length or k == len(shots) - 1:
                key = (id(scene), k)
                if key not in self.open:
                    for old in [o for o in self.open if o[0] != id(scene)]:  # (the last scene's are done)
                        self.open.pop(old).close()
                    try:
                        self.open[key] = Footage(name, start, scene.get("blur", ()))
                    except (StopIteration, OSError):
                        return None
                return self.open[key].at(t - at)
            at += length
        return None


# ---------------------------------------------------------------- sound
def mix(track, audio, at, gain=1.0):
    i = int(at * SR)
    n = min(len(audio), len(track) - i)
    if n > 0:
        track[i:i + n] += audio[:n] * gain


def music(seconds):
    """An original, simple beat to sit under them: kick, hat and a minor bass line at 96 BPM, quiet."""
    out, beat = np.zeros(int(seconds * SR) + SR, np.float32), 60 / 96
    t = np.arange(int(0.25 * SR)) / SR
    kick = (np.sin(2 * np.pi * (45 + 80 * np.exp(-t * 30)) * t) * np.exp(-t * 14)).astype(np.float32)
    hat = (np.random.default_rng(3).normal(0, 1, int(0.05 * SR)) * np.exp(-np.arange(int(0.05 * SR)) / SR * 80)).astype(np.float32)
    hat = np.diff(hat, prepend=0).astype(np.float32) * 0.5  # (brighter)
    notes = [55.0, 55.0, 65.4, 49.0]  # A1, A1, C2, G1
    for n in range(int(seconds / beat)):
        mix(out, kick, n * beat, 0.55 if n % 2 == 0 else 0.35)
        mix(out, hat, n * beat + beat / 2, 0.12)
        if n % 2 == 0:
            f, tt = notes[(n // 8) % 4], np.arange(int(beat * 1.8 * SR)) / SR
            mix(out, (np.sign(np.sin(2 * np.pi * f * tt)) * 0.5 + np.sin(4 * np.pi * f * tt) * 0.3).astype(np.float32)
                * np.exp(-tt * 1.6), n * beat, 0.07)
    return out


def whoosh():
    n = int(0.45 * SR)
    noise = np.random.default_rng(5).normal(0, 1, n).astype(np.float32)
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    smooth = np.convolve(noise, np.ones(24) / 24, mode="same")  # (a soft, low rush)
    return (smooth * env * 0.9).astype(np.float32)


# ---------------------------------------------------------------- drawing
def font(size, weight=QFont.Bold):
    f = QFont("Segoe UI", 1, weight)
    f.setPixelSize(size)
    return f


def game_screen(g, t, dead=False, menu=False):
    """A made-up shooter screen: dusk sky, blocky buildings, a crosshair and a HUD. Nothing from a real game."""
    sway = math.sin(t * 0.7) * 14
    sky = QLinearGradient(0, 0, 0, HEIGHT)
    sky.setColorAt(0, QColor("#2b3a55"))
    sky.setColorAt(0.6, QColor("#c9785a"))
    sky.setColorAt(1, QColor("#3a2b2b"))
    g.fillRect(0, 0, WIDTH, HEIGHT, sky)
    rnd = random.Random(11)
    for layer, (shade, base) in enumerate(((QColor("#3b3346"), 420), (QColor("#2a2431"), 470), (QColor("#1c1820"), 520))):
        x = -200 + sway * (layer + 1) * 0.6
        while x < WIDTH + 200:
            w, h = rnd.randint(80, 190), rnd.randint(90, 260)
            g.fillRect(QRectF(x, base - h, w, HEIGHT), shade)
            for wy in range(base - h + 18, base, 34):  # lit windows
                for wx in range(int(x) + 12, int(x + w) - 16, 28):
                    if rnd.random() < 0.3:
                        g.fillRect(QRectF(wx, wy, 10, 14), QColor(255, 210, 140, 110))
            x += w + rnd.randint(10, 40)
    g.fillRect(QRectF(0, 560, WIDTH, HEIGHT), QColor("#241f22"))
    if menu:
        g.fillRect(0, 0, WIDTH, HEIGHT, QColor(10, 8, 14, 170))
        g.setFont(font(54))
        g.setPen(CREAM)
        g.drawText(QRectF(90, 150, 700, 80), Qt.AlignLeft, "FIND MATCH")
        g.setFont(font(26, QFont.DemiBold))
        for i, item in enumerate(("Loadout", "Operators", "Battle Pass", "Settings")):
            g.setPen(QColor(241, 233, 223, 150))
            g.drawText(QRectF(94, 250 + i * 46, 500, 40), Qt.AlignLeft, item)
        return
    g.setPen(QPen(QColor(255, 255, 255, 210), 2))  # crosshair
    cx, cy = WIDTH / 2, HEIGHT / 2
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        g.drawLine(QPointF(cx + dx * 8, cy + dy * 8), QPointF(cx + dx * 20, cy + dy * 20))
    g.setFont(font(30))
    g.setPen(CREAM)
    g.drawText(QRectF(40, HEIGHT - 70, 300, 40), Qt.AlignLeft, "HP 64")
    g.drawText(QRectF(560, HEIGHT - 70, 200, 40), Qt.AlignLeft, "24 / 90")  # (clear of them, bottom right)
    g.setBrush(QColor(0, 0, 0, 90))
    g.setPen(QPen(QColor(255, 255, 255, 120), 2))
    g.drawEllipse(QPointF(110, HEIGHT - 170), 60, 60)  # minimap
    g.setFont(font(17, QFont.DemiBold))
    for i, row in enumerate(("Raven [rifle] Duke", "you [smg] Blitz", "Nova [knife] Pike")):
        g.setPen(QColor(241, 233, 223, 200))
        g.drawText(QRectF(WIDTH - 420, 30 + i * 26, 390, 24), Qt.AlignRight, row)
    if dead:
        g.fillRect(0, 0, WIDTH, HEIGHT, QColor(120, 0, 10, 110))
        g.setFont(font(72))
        g.setPen(QColor("#ffdddd"))
        g.drawText(QRectF(0, 340, WIDTH, 100), Qt.AlignCenter, "ELIMINATED")


def dark(g):
    grad = QLinearGradient(0, 0, 0, HEIGHT)
    grad.setColorAt(0, QColor("#24202c"))
    grad.setColorAt(1, QColor("#0e0c12"))
    g.fillRect(0, 0, WIDTH, HEIGHT, grad)


def bubble(g, text, shown, right, y, tail_x, player=False):
    """A speech bubble whose right edge is at `right` (their side), showing the first `shown` characters."""
    f = font(22, QFont.DemiBold)
    r = QFontMetrics(f).boundingRect(0, 0, 420, 1000, Qt.TextWordWrap, text)
    bw, bh = r.width() + 36, r.height() + 26
    x = right - bw
    shape = QPainterPath()
    shape.addRoundedRect(QRectF(x, y, bw, bh), 16, 16)
    tail = QPainterPath()
    tail.moveTo(right - 2, y + bh * 0.35)
    tail.lineTo(tail_x, y + bh * 0.6)
    tail.lineTo(right - 2, y + bh * 0.75)
    tail.closeSubpath()
    g.setPen(Qt.NoPen)
    g.setBrush(QColor(40, 60, 90, 235) if player else QColor(250, 244, 234, 242))
    g.drawPath(shape.united(tail))
    g.setFont(f)
    g.setPen(CREAM if player else INK)
    g.drawText(QRectF(x + 18, y + 13, r.width() + 2, r.height() + 2), Qt.TextWordWrap, text[:int(shown)])


def caption(g, text, t, dur):
    a = min(1.0, t / 0.4, (dur - t) / 0.4)
    if a <= 0:
        return
    g.setFont(font(40))
    m = QFontMetrics(g.font())
    w = m.horizontalAdvance(text) + 48
    g.setBrush(QColor(14, 12, 18, int(200 * a)))
    g.setPen(Qt.NoPen)
    g.drawRoundedRect(QRectF(40, 40, w, 66), 14, 14)
    g.setPen(QColor(242, 198, 77, int(255 * a)))
    g.drawText(QRectF(64, 40, w, 66), Qt.AlignVCenter | Qt.AlignLeft, text)


def draw_char(g, char, x, y, scale, angle=0.0):
    img = char.render(scale)
    if angle:
        g.save()
        g.translate(x + img.width() / 2, y + img.height() / 2)
        g.rotate(angle)
        g.drawImage(QPointF(-img.width() / 2, -img.height() / 2), img)
        g.restore()
    else:
        g.drawImage(QPointF(x, y), img)


def creator_image():
    import settings_ui
    w = settings_ui.CreatorWindow(Voice(), lambda d: None, lambda p, n: None)
    w.timer.stop()
    w.name.setText("Captain Rook")
    w.about.setPlainText("A washed-up pirate captain who thinks every match is a naval battle. Gruff, dramatic, secretly proud of you.")
    w.power.setText("Stormcall")
    w.voice_pick.setCurrentText("kokoro:bm_george")
    w.picks.colors = {"hair": "#c0392b", "eyes": "#3ee6ff", "outfit": "#1f6f8b"}
    w.picks.show_colors()
    w.redress()
    w.char.outfit = "warlord"
    w.char.glance_at = w.char.turn_at = 1e9
    w.char.set_mood("smug")
    for _ in range(5):
        w.char.step(1.0, 0.0)
    from PySide6.QtGui import QPixmap
    w.preview.setPixmap(QPixmap.fromImage(w.char.render(0.9)))
    w.resize(w.sizeHint())
    return w.grab().toImage()


# ---------------------------------------------------------------- the render
def main():
    random.seed(7)
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841 (Qt needs it)
    starts, total = [], 0.0
    for s in SCENES:
        starts.append(total)
        total += s["time"]
    voice = Voice()
    track = np.zeros(int(total * SR) + SR, np.float32)
    mix(track, music(total)[:len(track)], 0, 1.0)
    speech = []  # (start, end, speaker, audio, mouth track)
    for s, at in zip(SCENES, starts):
        if at:
            mix(track, whoosh(), at - 0.2, 0.35)
        for start, who, mood, text in s.get("lines", []):
            name, rate = VOICES[who]
            audio = voice.synth(text, name, rate)
            mix(track, audio, at + start, 1.0)
            speech.append((at + start, at + start + len(audio) / SR, who, audio, mouth_track(audio), mood, text, s))
        for start, build, kind in s.get("sounds", []):
            clip = sfx.clips(build, kind)[0]
            mix(track, clip, at + start, 0.9)
            speech.append((at + start, at + start + len(clip) / SR, build.title(), clip, mouth_track(clip), None, "", s))
    for s, at in zip(SCENES, starts):  # throw: a yell at the launch, a grunt on landing
        if s["kind"] == "throw":
            yell, grunt = sfx.clips("vorn", "yell")[1], sfx.clips("vorn", "grunt")[0]
            mix(track, yell, at + 0.9, 1.0)
            mix(track, grunt, at + 2.6, 1.0)
            speech += [(at + 0.9, at + 0.9 + len(yell) / SR, "Vorn", yell, mouth_track(yell), None, "", s),
                       (at + 2.6, at + 2.6 + len(grunt) / SR, "Vorn", grunt, mouth_track(grunt), None, "", s)]
    track *= 0.95 / max(0.95, float(np.abs(track).max()))

    chars = {"Vorn": Vorn("warlord"), "Mika": Mika("jacket"), "Rook": Vorn("warlord")}
    chars["Rook"].recolor({"hair": "#c0392b", "eyes": "#3ee6ff", "outfit": "#1f6f8b"})
    for c in chars.values():
        c.glance_at = c.turn_at = 1e9
    vorn_looks, mika_looks = list(Vorn.OUTFITS), list(Mika.OUTFITS)
    outfits_total = len(vorn_looks) + len(mika_looks)
    creator = creator_image()
    shots = Shots()

    VIDEO.parent.mkdir(exist_ok=True)
    out = av.open(str(VIDEO), "w")
    vs = out.add_stream("libx264", rate=FPS, options={"crf": "24", "preset": "slow"})
    vs.width, vs.height, vs.pix_fmt = WIDTH, HEIGHT, "yuv420p"
    rate48 = 48000
    audio48 = np.interp(np.arange(0, len(track), SR / rate48), np.arange(len(track)), track).astype(np.float32)
    as_ = out.add_stream("aac", rate=rate48, layout="mono")
    apos, gif = 0, []
    frames = int(total * FPS)
    for n in range(frames):
        t = n / FPS
        i = max(k for k, at in enumerate(starts) if at <= t)
        s, lt = SCENES[i], t - starts[i]
        img = QImage(WIDTH, HEIGHT, QImage.Format_RGB32)
        g = QPainter(img)
        g.setRenderHint(QPainter.Antialiasing)
        g.setRenderHint(QPainter.SmoothPixmapTransform)
        kind = s["kind"]
        if kind != "outfits":  # (their usual looks, outside the outfit parade)
            chars["Vorn"].outfit, chars["Mika"].outfit = "warlord", "jacket"
        talking = [sp for sp in speech if sp[0] <= t < sp[1]]
        for name, c in chars.items():  # mouths and faces follow what's being said
            line = next((sp for sp in talking if sp[2] == name), None)
            if line:
                k = min(int((t - line[0]) * MOUTH_FPS), len(line[4]) - 1)
                c.say = tuple(float(v) for v in line[4][k])
                if line[5]:
                    c.set_mood(line[5])
                lvl = float(np.sqrt(np.mean(line[3][int((t - line[0]) * SR):int((t - line[0]) * SR) + 800] ** 2) + 1e-9))
            else:
                c.say, lvl = (0.0, 0.0, 0.0), 0.0
                if not any(sp[2] == name and sp[1] <= t < sp[1] + 1.2 for sp in speech) and kind not in ("throw", "power", "dead"):
                    c.set_mood("idle")
            c.step(1 / FPS, min(1.0, lvl * 6))
        footage = shots.frame(s, s.get("shots"), lt)
        if footage is not None:  # your gameplay
            g.drawImage(0, 0, footage)
            if s.get("dim"):
                g.fillRect(0, 0, WIDTH, HEIGHT, QColor(10, 8, 14, int(255 * s["dim"])))
        elif kind in ("game", "dead", "power", "throw"):
            game_screen(g, t, dead=kind == "dead")
        elif kind == "menu":
            game_screen(g, t, menu=True)
        else:
            dark(g)
        scale = 0.95
        cw, ch = W * scale, H * scale
        duo_x, duo_y = WIDTH - 2 * cw - 30, HEIGHT - ch + 10
        if kind == "title" or kind == "end":
            a = min(1.0, lt / 0.8)
            g.setFont(font(120))
            g.setPen(QColor(242, 198, 77, int(255 * a)))
            g.drawText(QRectF(0, 150 if kind == "title" else 120, WIDTH, 150), Qt.AlignCenter, "BACKSEAT")
            g.setFont(font(34, QFont.DemiBold))
            g.setPen(QColor(241, 233, 223, int(255 * a)))
            sub = ("Your trash-talking gaming companions" if kind == "title"
                   else f"github.com/DivxPlays/backseat   ·   {version()}")
            g.drawText(QRectF(0, 290 if kind == "title" else 265, WIDTH, 60), Qt.AlignCenter, sub)
            if kind == "end":
                g.setFont(font(24, QFont.Normal))
                g.setPen(QColor(241, 233, 223, int(200 * a)))
                g.drawText(QRectF(0, 325, WIDTH, 50), Qt.AlignCenter, "Free download for Windows  ·  bring your own Anthropic API key")
                g.setFont(font(18, QFont.Normal))
                g.setPen(QColor(241, 233, 223, int(160 * a)))
                g.drawText(QRectF(0, 362, WIDTH, 40), Qt.AlignCenter, "Made with the help of AI: Anthropic's Claude writes and tests much of the code")
            slide = (1 - min(1.0, lt / 1.0)) ** 2 * 300
            draw_char(g, chars["Vorn"], WIDTH / 2 - cw - 20 - slide, HEIGHT - ch * 0.62, scale)
            draw_char(g, chars["Mika"], WIDTH / 2 + 20 + slide, HEIGHT - ch * 0.62, scale)
        elif kind == "outfits":
            step = int(lt / 0.42)
            chars["Vorn"].outfit, chars["Mika"].outfit = vorn_looks[step % len(vorn_looks)], mika_looks[step % len(mika_looks)]
            for k, (c, x) in enumerate(((chars["Vorn"], WIDTH / 2 - cw - 40), (chars["Mika"], WIDTH / 2 + 40))):
                c.set_mood(("smug", "laugh", "idle")[(step + k) % 3])
                draw_char(g, c, x, HEIGHT - ch + 20, scale)
        elif kind == "throw":
            v, m = chars["Vorn"], chars["Mika"]
            draw_char(g, m, WIDTH - cw - 30, duo_y, scale)
            if lt < 0.9:  # held up by your cursor, dangling
                v.rag = 0.6
                v.set_mood("surprised")
                draw_char(g, v, WIDTH - 2 * cw - 60 + math.sin(lt * 9) * 6, duo_y - 120 * lt, scale, math.sin(lt * 7) * 12)
                g.setBrush(CREAM)
                g.setPen(QPen(INK, 2))
                hx, hy = WIDTH - 2 * cw - 60 + cw / 2, duo_y - 120 * lt + 40
                g.drawPolygon([QPointF(hx, hy), QPointF(hx, hy + 30), QPointF(hx + 8, hy + 23), QPointF(hx + 16, hy + 36)])
            elif lt < 2.6:  # flying, spinning, flailing
                ft = lt - 0.9
                v.rag = 1.0
                x = WIDTH - 2 * cw - 60 - ft * 330
                y = duo_y - 108 - 620 * ft + 900 * ft * ft
                draw_char(g, v, x, min(y, duo_y + 60), scale, -ft * 420)
            else:  # landed in a heap, then up again
                v.rag = 0.0
                if lt < 2.7:
                    v.slump()
                    v.set_mood("angry")
                draw_char(g, v, WIDTH - 2 * cw - 60 - 1.7 * 330, duo_y + (150 if lt < 4.2 else 0), scale, -90 if lt < 4.2 else 0)
        elif kind == "squad":
            g.setBrush(QColor(20, 16, 24, 230))
            g.setPen(QPen(GOLD, 2))
            g.drawRoundedRect(QRectF(50, 170, 360, 330), 18, 18)
            g.setFont(font(34))
            g.setPen(GOLD)
            g.drawText(QRectF(76, 190, 330, 50), Qt.AlignLeft, "Squad leaderboard")
            g.setFont(font(28, QFont.DemiBold))
            for k, (who, pts, why) in enumerate((("Mike", 9, "5 deaths, 2 roasts"), ("Sam", 2, "1 death, 1 roast"), ("Tess", -1, "1 epic play"))):
                g.setPen(CREAM if k else QColor("#ff8a8a"))
                g.drawText(QRectF(76, 260 + k * 70, 330, 40), Qt.AlignLeft, f"{k + 1}. {who}   {pts:+d}")
                g.setFont(font(18, QFont.Normal))
                g.setPen(QColor(241, 233, 223, 150))
                g.drawText(QRectF(112, 296 + k * 70, 290, 30), Qt.AlignLeft, why)
                g.setFont(font(28, QFont.DemiBold))
            draw_char(g, chars["Vorn"], duo_x, duo_y, scale)
            draw_char(g, chars["Mika"], duo_x + cw, duo_y, scale)
        elif kind == "creator":
            zoom = 0.74 + lt * 0.012  # (a slow push in)
            cwid, chei = creator.width() * zoom, creator.height() * zoom
            g.drawImage(QRectF(40, 130 + (HEIGHT - 130 - chei) / 2, cwid, chei), creator)
            draw_char(g, chars["Rook"], WIDTH - cw - 10, HEIGHT - ch + 30, scale * 0.9)
        elif kind == "clip":
            frame = shots.frame(s, s.get("card"), lt)
            if frame is None:
                frame = QImage(WIDTH, HEIGHT, QImage.Format_RGB32)
                fg = QPainter(frame)
                game_screen(fg, 3.0 + lt * 0.2, dead=True)
                fg.end()
            card = QRectF(110, 140, 760, 428)
            g.drawImage(card, frame)
            g.setPen(QPen(QColor("#3a2e33"), 3))
            g.setBrush(Qt.NoBrush)
            g.drawRoundedRect(card, 10, 10)
            g.fillRect(QRectF(card.x() + 20, card.bottom() - 30, card.width() - 40, 6), QColor(255, 255, 255, 80))
            g.fillRect(QRectF(card.x() + 20, card.bottom() - 30, (card.width() - 40) * min(1.0, 0.75 + lt / 26), 6), GOLD)
            draw_char(g, chars["Vorn"], card.right() - W * 0.62 - 10, card.bottom() - H * 0.62, 0.62)
        else:
            draw_char(g, chars["Vorn"], duo_x, duo_y, scale)
            draw_char(g, chars["Mika"], duo_x + cw, duo_y, scale)
            if kind == "power" and lt < 0.1:
                chars["Vorn"].bloodfire(4.0)
                chars["Mika"].bloodfire(4.0)
        for sp in talking:  # their lines, in a bubble on their side
            if not sp[6] or sp[7] is not s:
                continue
            shown = (t - sp[0]) / max(0.3, sp[1] - sp[0]) * len(sp[6]) * 1.15
            if kind == "clip":
                bubble(g, sp[6], shown, 1240, 170, 1150)
            elif kind == "creator":
                bubble(g, sp[6], shown, WIDTH - cw + 10, HEIGHT - ch + 10, WIDTH - cw / 2)
            else:  # left of the two, its tail toward whoever is talking
                bubble(g, sp[6], shown, duo_x + 20, duo_y - 40, duo_x + cw * (1.35 if sp[2] == "Mika" else 0.45))
        if "player" in s and s["player"][0] <= lt < s["time"] - 0.3:  # you, talking to them
            bubble(g, s["player"][1], len(s["player"][1]), 560, 300, 600, player=True)
        if "note" in s and lt >= s["note"][0]:
            g.setFont(font(22, QFont.DemiBold))
            g.setPen(QColor("#e8c27a"))
            g.drawText(QRectF(44, 122, 800, 40), Qt.AlignLeft, s["note"][1])  # (under the caption, clear of them)
        if s.get("caption"):
            caption(g, s["caption"].format(outfits=outfits_total), lt, s["time"])
        fade = min(1.0, lt / FADE, (s["time"] - lt) / FADE)
        if fade < 1:
            g.fillRect(0, 0, WIDTH, HEIGHT, QColor(0, 0, 0, int(255 * (1 - max(0.0, fade)))))
        g.end()
        rgb = img.convertToFormat(QImage.Format_RGB888)
        arr = np.frombuffer(rgb.constBits(), np.uint8, count=rgb.sizeInBytes()).reshape(HEIGHT, rgb.bytesPerLine())[:, :WIDTH * 3]
        arr = arr.reshape(HEIGHT, WIDTH, 3).copy()
        for p in vs.encode(av.VideoFrame.from_ndarray(arr, format="rgb24")):
            out.mux(p)
        while apos < min(len(audio48), int((t + 1 / FPS) * rate48)):  # the sound, kept in step with the picture
            chunk = audio48[apos:apos + 1024]
            if len(chunk) < 1024:
                chunk = np.pad(chunk, (0, 1024 - len(chunk)))
            af = av.AudioFrame.from_ndarray(chunk.reshape(1, -1), format="fltp", layout="mono")
            af.sample_rate, af.pts = rate48, apos
            for p in as_.encode(af):
                out.mux(p)
            apos += 1024
        if n % 3 == 0 and ((i == 1 and 4.0 <= lt < 8.4) or (kind == "throw" and 0.6 <= lt < 3.0)):  # the README teaser:
            gif.append(Image.fromarray(arr).resize((360, 203), Image.LANCZOS).quantize(128, method=Image.Quantize.MEDIANCUT))
        if n % (FPS * 5) == 0:
            print(f"  {t:4.1f} s / {total:.0f} s", flush=True)
    for stream in (vs, as_):
        for p in stream.encode(None):
            out.mux(p)
    out.close()
    gif[0].save(GIF, save_all=True, append_images=gif[1:], duration=100, loop=0, optimize=True)
    print(f"{VIDEO.relative_to(HERE)}: {VIDEO.stat().st_size / 1e6:.1f} MB, {total:.0f} s | "
          f"{GIF.relative_to(HERE)}: {GIF.stat().st_size / 1e6:.1f} MB, {len(gif)} frames")


if __name__ == "__main__":
    main()
