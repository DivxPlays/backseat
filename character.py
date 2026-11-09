"""Warlord Vorn: an original character, drawn and animated live with QPainter (no image files).

Serious anime style, full body, hard cel shading. Every face part and limb is driven by numbers, so
moods and poses blend smoothly and the mouth lip-syncs to his voice.

Drawing coordinates: the bust (head to chest) was designed 300 wide around x=150 with the chest at y~340;
the full body continues down to FULL_H. The whole figure is drawn at FIT scale, and W x H is the logical
canvas the overlay sees.
"""
import math
import random

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

import config

BUST_W, BUST_H = 300, 340  # the bust part of the drawing (tray icon)
MARGIN, TOP, FULL_H = 40, 24, 1000  # room beside him for raised arms and above his hair; feet at ~990
FIT = 0.5  # full body at about the screen space the bust used
W, H = int((BUST_W + 2 * MARGIN) * FIT), int((FULL_H + TOP) * FIT)  # logical canvas; the overlay scales it
HEAD_Y = (140 + TOP) * FIT  # his eyes, for the speech bubble

INK = QColor("#1b1418")
SKIN, SKIN_SH = QColor("#d9a27c"), QColor("#a8694c")
HAIR, HAIR_SH, HAIR_HI = QColor("#1d1b24"), QColor("#07060a"), QColor("#4b4f66")  # black, with a cool sheen so it keeps its shape
SCLERA = QColor("#f1e9df")
IRIS, IRIS_SH = QColor("#2b2730"), QColor("#050406")  # black eyes; the white catchlight keeps them alive
GEM = QColor("#d23a3a")
MOUTH, TONGUE = QColor("#3e0d12"), QColor("#a8414c")
SCAR = QColor("#e0a48c")
# upgrades he earns as your respect grows (see tier_for)
GOLD, GOLD_SH = QColor("#f2c64d"), QColor("#9a6b12")
FUR_WHITE, FUR_WHITE_SH = QColor("#ebe7df"), QColor("#9c958a")
LEATHER, LEATHER_SH = QColor("#4a3226"), QColor("#24170f")

# Vorn's outfits: colours as (main, shadow[, highlight]) plus the pieces he wears. Each one is the warlord's armour with changes.
# plate: armour plates (chest, hips, knees, elbows, pauldrons); fore/shin: forearms and shins (default: the armour);
# wraps: cloth wrapped around them; hem: where the cape ends (None: no cape); collar: fur, gorget, scarf or hood
WARLORD = dict(plate=True, spikes=True, steel=("#454b58", "#1f232b", "#7a8396"), polish="#aab4c8", fore=None, shin=None,
               wraps=False, trim=("#c8893f", "#7a4a1a"), suit=("#2e2a35", "#16131a"), legs=None, cape=("#5e1016", "#2a0609"),
               hem=984, lining=None, tabard=("#5e1016", "#2a0609"), collar="fur", collar_c=("#54453c", "#2b221d", "#8a7563"),
               gloves=("#3a302b", "#6a5a50"), boots=("#4a3226", "#24170f"))
VORN_LOOKS = {
    "warlord": {},
    "obsidian": dict(steel=("#2a2830", "#0b0a0e", "#514c5a"), polish="#77727f", trim=("#b3202a", "#5a0c12"),
                     cape=("#17151a", "#050407"), lining="#9e1b24", tabard=("#7a0f17", "#33060a"), collar="gorget",
                     collar_c=("#2a2830", "#0b0a0e", "#514c5a"), gloves=("#1c1a1f", "#3d3a44"), boots=("#1a1719", "#08070a")),
    "frostbound": dict(steel=("#8b95a6", "#4a5263", "#c9d2e0"), polish="#e8eef7", trim=("#7fd3ff", "#2f7fae"),
                       suit=("#2a3142", "#141a26"), cape=("#1c2a4a", "#0b1226"), tabard=("#1c2a4a", "#0b1226"),
                       collar_c=("#ebe7df", "#9c958a", "#ffffff"), gloves=("#4b5468", "#7d879d"), boots=("#3b4252", "#1c212b")),
    "desert raider": dict(spikes=False, steel=("#7a5434", "#3e2a1a", "#a87a52"), polish="#c99a6a",
                          fore=("#c9b48a", "#8a7552", "#e6d6b0"), shin=("#c9b48a", "#8a7552", "#e6d6b0"), wraps=True,
                          trim=("#b08a3e", "#6a4e1c"), suit=("#5a4632", "#2e2318"), cape=("#b5662f", "#6a3416"), hem=650,
                          tabard=("#c8642a", "#7a3412"), collar="scarf", collar_c=("#d8c79f", "#9c8a64", "#f0e4c4"),
                          gloves=("#6b4a2e", "#9a7350"), boots=("#8a6a44", "#4a3620")),
    "off-duty": dict(plate=False, spikes=False, fore=("#24222a", "#0c0b0f", "#3e3b48"), suit=("#24222a", "#0c0b0f"),
                     legs=("#3b3f36", "#1e201b"), shin=("#3b3f36", "#1e201b", "#5a5f52"), trim=("#b3202a", "#5a0c12"),
                     hem=None, tabard=None, collar="hood", collar_c=("#24222a", "#0c0b0f", "#3e3b48"),
                     gloves=("#d9a27c", "#a8694c"), boots=("#2a2420", "#120e0c")),  # a hoodie, combat trousers, bare hands
}


def _outfit(changes):
    o = {**WARLORD, **changes}
    o["fore"], o["shin"], o["legs"] = o["fore"] or o["steel"], o["shin"] or o["steel"], o["legs"] or o["suit"]
    return {k: tuple(map(QColor, v)) if isinstance(v, tuple) else QColor(v) if str(v).startswith("#") else v for k, v in o.items()}


VORN_OUTFITS = {name: _outfit(changes) for name, changes in VORN_LOOKS.items()}
COWL = [(66, 292), (74, 262), (96, 242), (124, 234), (150, 232), (176, 234), (204, 242), (226, 262), (234, 292), (150, 278)]


def tier_for(respect):
    """0 base look, 1 polished armor (25+), 2 gold-trimmed cape and white fur (50+), 3 war-crown and golden glow (75+)."""
    return 3 if respect >= 75 else 2 if respect >= 50 else 1 if respect >= 25 else 0

# Face targets per mood (values blend smoothly between moods):
# brow: inner ends down (+, scowl) or up (-); lift: both brows up; lift_r: extra lift on one brow
# open: eye openness; pupil: pupil size; smile: mouth curve; smirk: one corner up (+) / down (-)
# mouth: openness while silent; teeth / happy (closed laughing eyes) / vein: 0..1; look: pupils sideways
# tilt: head angle in degrees; aura: power-up flames
MOODS = {
    "idle":      dict(brow=0.55, lift=0.0, lift_r=0.0, open=0.8, pupil=1.0, smile=-0.05, smirk=0.35, mouth=0.0, teeth=0, happy=0, vein=0, look=0.0, tilt=0, aura=0.0),
    "smug":      dict(brow=0.25, lift=0.1, lift_r=0.9, open=0.5, pupil=1.0, smile=0.3, smirk=1.0, mouth=0.0, teeth=0, happy=0, vein=0, look=-0.35, tilt=-4, aura=0.0),
    "angry":     dict(brow=1.0, lift=-0.2, lift_r=0.0, open=0.95, pupil=0.55, smile=-0.5, smirk=0.0, mouth=0.3, teeth=1, happy=0, vein=1, look=0.0, tilt=3, aura=1.0),
    "laugh":     dict(brow=-0.1, lift=0.5, lift_r=0.0, open=0.0, pupil=1.0, smile=0.8, smirk=0.2, mouth=0.85, teeth=1, happy=1, vein=0, look=0.0, tilt=-6, aura=0.3),
    "surprised": dict(brow=-0.5, lift=1.0, lift_r=0.0, open=1.25, pupil=0.5, smile=0.0, smirk=0.0, mouth=0.45, teeth=0, happy=0, vein=0, look=0.0, tilt=2, aura=0.0),
    "disgusted": dict(brow=0.7, lift=0.0, lift_r=-0.4, open=0.45, pupil=0.9, smile=-0.35, smirk=-0.7, mouth=0.0, teeth=0, happy=0, vein=0, look=0.8, tilt=-3, aura=0.0),
}

# Arm poses: (arm on the bubble side, other arm), each (upper arm angle, forearm angle, hand, upper arm length).
# Angles in degrees from straight down; positive swings outward, negative across the body, 180 is straight up.
# Length below 1 is foreshortening: the elbow comes toward you.
POSES = {
    "idle":     ((9, 5, "fist", 1.0), (9, 5, "fist", 1.0)),
    "crossed":  ((-4, -97, "fist", 0.72), (-4, -82, "fist", 0.72)),  # forearms stacked across the chest, the near one higher
    "fist":     ((24, 175, "fist", 1.0), (14, 10, "fist", 1.0)),  # shaking a fist at you
    "hips":     ((28, -45, "fist", 1.0), (28, -45, "fist", 1.0)),  # fists on hips
    "startled": ((14, 173, "open", 0.9), (14, 173, "open", 0.9)),
    "point":    ((18, 172, "point", 1.0), (28, -45, "fist", 1.0)),  # lecturing finger, other fist on hip
    "slump":    ((3, 1, "open", 1.0), (3, 1, "open", 1.0)),
}
MOOD_POSE = {"idle": "idle", "smug": "crossed", "angry": "fist", "laugh": "hips", "surprised": "startled", "disgusted": "point"}
SHOULDER = (58, 296)  # where his left arm starts under the pauldron (the right one is mirrored)
UPPER, FORE = 135, 122  # arm segment lengths


def P(x, y):
    return QPointF(x, y)


def pen(color, width):
    return QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)


def fill(g, path, brush, width=2.2):
    g.setPen(pen(INK, width) if width else Qt.NoPen)
    g.setBrush(QBrush(brush))
    g.drawPath(path)


def stroke(g, path, color, width):
    g.setPen(pen(color, width))
    g.setBrush(Qt.NoBrush)
    g.drawPath(path)


def poly(*pts):
    path = QPainterPath(P(*pts[0]))
    for pt in pts[1:]:
        path.lineTo(P(*pt))
    path.closeSubpath()
    return path


def mirror(pts):
    return [(BUST_W - x, y) for x, y in pts]


def vgrad(y0, y1, c0, c1):
    gr = QLinearGradient(0, y0, 0, y1)
    gr.setColorAt(0, c0)
    gr.setColorAt(1, c1)
    return gr


def alpha(color, a):
    c = QColor(color)
    c.setAlphaF(max(0.0, min(1.0, a)))
    return c


def mix(c0, c1, k):
    """Blend two colors, k=0 -> c0, k=1 -> c1."""
    return QColor.fromRgbF(*(a + (b - a) * k for a, b in zip(c0.getRgbF(), c1.getRgbF())))


# Bloodfire, his power-up form: flaming hair, white-hot eyes, molten cracks in the armor
EMBER, EMBER_CORE, BLOOD = QColor("#ff3a1a"), QColor("#ffe2a0"), QColor("#b0001c")
CHEST_CRACKS = [[(150, 326), (142, 346), (148, 362), (134, 392), (140, 414)], [(150, 326), (162, 344), (156, 366), (172, 396)],
                [(96, 296), (104, 322), (96, 342), (102, 368)], [(206, 298), (198, 324), (206, 348)]]
PAULDRON_CRACKS = [[(30, 280), (50, 272), (60, 284), (80, 276), (96, 292)], [(70, 304), (78, 290)]]


def face_path():
    f = QPainterPath(P(100, 96))
    f.cubicTo(P(98, 130), P(100, 150), P(104, 162))
    f.lineTo(P(118, 192))
    f.quadTo(P(128, 208), P(141, 214))
    f.lineTo(P(159, 214))
    f.quadTo(P(172, 208), P(182, 192))
    f.lineTo(P(196, 162))
    f.cubicTo(P(200, 150), P(202, 130), P(200, 96))
    f.cubicTo(P(198, 48), P(102, 48), P(100, 96))
    return f


PAULDRON = [(12, 304), (20, 264), (54, 238), (104, 240), (122, 264), (112, 298), (66, 314)]
SPIKES = [((30, 256), (12, 232), (48, 244)), ((56, 240), (48, 214), (76, 238)), ((84, 239), (86, 220), (102, 241))]
FUR_EDGE = [(62, 270), (70, 250), (80, 258), (88, 238), (100, 250), (108, 230), (120, 246), (130, 232), (140, 246),
            (150, 236), (160, 246), (170, 232), (180, 246), (192, 230), (200, 250), (212, 238), (220, 258),
            (230, 250), (238, 270)]


class Vorn:
    OUTFITS, OUTFIT_SETTING = VORN_OUTFITS, "VORN_OUTFIT"  # his wardrobe and the setting that picks from it

    def __init__(self, outfit=None):
        outfit = outfit or getattr(config, self.OUTFIT_SETTING)
        self.outfit = outfit if outfit in self.OUTFITS else random.choice(sorted(self.OUTFITS))  # "random": a new look each launch
        self.mood = "idle"
        self.p = dict(MOODS["idle"])
        self.t = 0.0
        self.talk = 0.0
        self.blink = 0.0
        self.blink_at = 1.5
        self.glance = 0.0
        self.glance_to = 0.0
        self.glance_at = 3.0
        self.pop = 0.0
        self.afk = False  # set by the overlay: you've stopped touching keyboard and mouse
        self.toward = -1.0  # which way the rest of your screen is (-1 left, 1 right)
        self.yawn_t0, self.yawn_at = -10.0, 6.0
        self.turn, self.turn_at, self.turn_until = 0.0, 15.0, 0.0
        self.roll_t0 = -10.0
        self.flare_amt = 0.0
        self.tier = 0  # set by the overlay from your respect score
        self.slump_t0 = -100.0
        self.blood, self.blood_until = 0.0, -1.0  # Bloodfire: current strength 0..1, and until when it burns
        self.arms = {side: [*POSES["idle"][0][:2], POSES["idle"][0][3]] for side in (-1, 1)}  # current upper, forearm, length
        self.d = self._effective()

    def bloodfire(self, seconds):
        """Power up into Bloodfire for a while; it ignites fast and cools down slowly."""
        self.blood_until = max(self.blood_until, self.t + seconds)

    def slump(self):
        """Shoulders drop, arms hang, head down: you lost and he's ashamed of you."""
        self.slump_t0 = self.t

    def slumping(self):
        """0..1: 4 seconds, easing in and out."""
        e = self.t - self.slump_t0
        return max(0.0, min(1.0, e / 0.4, (4.0 - e) / 0.8))

    def pose(self):
        """{side: (upper, forearm, hand)} the arms are heading for, from his mood (or the slump)."""
        name = "slump" if self.slumping() > 0.5 else MOOD_POSE.get(self.mood, "idle")
        near, far = POSES[name]
        bubble = 1 if self.toward > 0 else -1  # the arm that gestures is on the side of your screen and his bubble
        return {bubble: near, -bubble: far}

    def set_mood(self, mood):
        if mood in MOODS and mood != self.mood:
            self.mood = mood
            self.pop = 1.0

    def flare(self):
        """Aura burst (you won or did something epic)."""
        self.flare_amt = 1.0

    def roll(self):
        """Impatient eye-roll (you're sitting in menus again)."""
        self.roll_t0 = self.t

    def step(self, dt, level):
        """Advance the animation by dt seconds; level is the current voice loudness 0..1."""
        self.t += dt
        k = 1 - math.exp(-dt * 9)
        for key, v in MOODS[self.mood].items():
            self.p[key] += (v - self.p[key]) * k
        self.talk += (level - self.talk) * (1 - math.exp(-dt * 28))
        if self.t >= self.blink_at:
            self.blink = 1.0
            self.blink_at = self.t + random.uniform(2.0, 5.5)
        self.blink = max(0.0, self.blink - dt / 0.16)
        if self.t >= self.glance_at:
            self.glance_to = random.choice([0.0, 0.0, -0.6, 0.6])
            self.glance_at = self.t + random.uniform(1.5, 4.0)
        self.glance += (self.glance_to - self.glance) * (1 - math.exp(-dt * 14))
        self.pop = max(0.0, self.pop - dt * 4)
        if self.afk and self.t >= self.yawn_at:
            self.yawn_t0, self.yawn_at = self.t, self.t + random.uniform(12, 20)
        if self.t >= self.turn_at:  # now and then he glances over at the rest of your screen
            self.turn_until, self.turn_at = self.t + 1.6, self.t + random.uniform(18, 40)
        self.turn += ((self.toward if self.t < self.turn_until else 0.0) - self.turn) * (1 - math.exp(-dt * 6))
        self.flare_amt = max(0.0, self.flare_amt - dt / 2.5)
        burning = self.t < self.blood_until
        self.blood += (float(burning) - self.blood) * (1 - math.exp(-dt * (6 if burning else 1.2)))
        ka = 1 - math.exp(-dt * 7)
        for side, (upper, fore, _, length) in self.pose().items():
            for i, target in enumerate((upper, fore, length)):
                self.arms[side][i] += (target - self.arms[side][i]) * ka

    def _effective(self):
        """Mood values plus the short-lived extras on top: yawns, glances, eye-rolls, aura flares."""
        p = dict(self.p)
        yp = (self.t - self.yawn_t0) / 2.2
        yawn = math.sin(math.pi * yp) if 0 <= yp <= 1 else 0.0
        p["open"] *= (1 - yawn) * (0.6 if self.afk else 1.0)  # bored half-lidded eyes while you're away
        p["mouth"] = max(p["mouth"], 0.95 * yawn)
        p["tilt"] += -7 * yawn + 3 * self.turn
        p["look"] += 1.1 * self.turn
        p["aura"] = max(p["aura"], self.flare_amt)
        rp = (self.t - self.roll_t0) / 1.1
        a = math.pi * rp
        p["roll_x"], p["roll_y"] = (-math.cos(a) * 6, -math.sin(a) * 6) if 0 <= rp <= 1 else (0.0, 0.0)
        p["blood"] = self.blood
        p["aura"] = max(p["aura"], self.blood)
        sl = self.slumping()  # ashamed: heavy lids, brows up, mouth down
        p["slump"] = sl
        p["open"] *= 1 - 0.45 * sl
        p["lift"] += 0.5 * sl
        p["brow"] -= 0.6 * sl
        p["smile"] -= 0.4 * sl
        return p

    def render(self, scale=1.0, bust=False):
        """The full body at W x H times scale, or just head and shoulders (bust=True, for the tray icon)."""
        w, h = (BUST_W, BUST_H) if bust else (W, H)
        img = QImage(int(w * scale), int(h * scale), QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        g = QPainter(img)
        g.scale(scale, scale)
        if bust:
            self.draw(g)
        else:
            self.paint(g)
        g.end()
        return img

    # ---------------------------------------------------------------- drawing
    def paint(self, g):
        """Draw him into the logical W x H canvas."""
        g.save()
        g.scale(FIT, FIT)
        g.translate(MARGIN, TOP)
        self.draw(g)
        g.restore()

    def draw(self, g):
        """Draw him in drawing coordinates (bust 300 wide around x=150, feet near FULL_H)."""
        p, t = self._effective(), self.t
        self.d = p  # what the face-part drawers read
        g.setRenderHint(QPainter.Antialiasing)
        breath = math.sin(t * 2 * math.pi / 3.8)
        s = 1 + 0.04 * self.pop ** 2
        g.save()
        g.translate(150, FULL_H)
        g.scale(s, s)
        g.translate(-150, -FULL_H)
        if self.tier >= 3:  # a constant golden glow once you've earned real respect
            g.save()
            g.translate(150, 480)
            g.scale(0.42, 1.0)  # a round soft glow, squeezed to his tall shape
            glow = QRadialGradient(P(0, 0), 520)
            glow.setColorAt(0, alpha(GOLD, 0.32 + 0.06 * math.sin(t * 2)))
            glow.setColorAt(1, alpha(GOLD, 0))
            g.setPen(Qt.NoPen)
            g.setBrush(QBrush(glow))
            g.drawEllipse(P(0, 0), 520, 520)
            g.restore()
        self._aura(g, p["aura"])
        self._cape(g)
        self._legs(g)
        g.translate(0, breath * 1.4 + 14 * p["slump"] + 3 * p["happy"] * abs(math.sin(t * 18)))  # breathing, slumping, laughing
        head = (
            math.sin(t * 36) * 1.6 * p["happy"] + math.sin(t * 61) * 0.8 * p["aura"] + 3 * self.turn,
            -self.talk * 2.0 + breath * 0.8 - 3 * p["happy"] + 10 * p["slump"],
            p["tilt"] + math.sin(t * 0.7) * 1.0,
        )
        self._in_head(g, head, self._back_hair)
        self._torso(g)
        self._arms(g)
        self._body(g)
        self._in_head(g, head, self._head)
        self._shoulders(g)
        g.restore()

    def _in_head(self, g, head, draw):
        dx, dy, deg = head
        g.save()
        g.translate(150 + dx, 200 + dy)
        g.rotate(deg)
        g.scale(1.14, 1.14)
        g.translate(-150, -200)
        draw(g)
        g.restore()

    def _aura(self, g, a):
        if a < 0.02:
            return
        t = self.t
        g.save()  # drawn for the old bust height, stretched to his full height
        g.translate(150, FULL_H)
        g.scale(1.25, FULL_H / 345)
        g.translate(-150, -345)
        b = self.d["blood"]  # Bloodfire turns the orange aura deep crimson
        glow = QRadialGradient(P(150, 190), 180)
        glow.setColorAt(0, alpha(mix(QColor("#ff4a1a"), BLOOD, b), 0.45 * a + 0.15 * b))
        glow.setColorAt(1, alpha(QColor("#ff2a00"), 0))
        g.setPen(Qt.NoPen)
        g.setBrush(QBrush(glow))
        g.drawEllipse(P(150, 190), 180, 180)
        for layer, (col, size) in enumerate([(mix(QColor("#ff3d12"), BLOOD, b), 1.0 + 0.3 * b), (mix(QColor("#ffc23d"), EMBER, b), 0.6 + 0.2 * b)]):
            for i in range(17):
                u = i / 16
                x = 18 + 264 * u
                base = 345 - 300 * math.sin(math.pi * u) ** 0.7
                h = (50 + 24 * math.sin(t * 7 + i * 1.7) + 14 * math.sin(t * 11.3 + i * 0.9)) * size * a
                w = 16 * size
                sway = math.sin(t * 5 + i) * 6
                fl = QPainterPath(P(x - w, base))
                fl.cubicTo(P(x - w, base - h * 0.5), P(x - w * 0.3 + sway * 0.5, base - h * 0.75), P(x + sway, base - h))
                fl.cubicTo(P(x + w * 0.3 + sway * 0.5, base - h * 0.75), P(x + w, base - h * 0.5), P(x + w, base))
                fl.closeSubpath()
                fill(g, fl, vgrad(base - h, base, alpha(col, 0), alpha(col, (0.85 if layer else 0.65) * a)), 0)
        for i in range(12):
            ph = (t * 0.55 + i * 0.137) % 1.0
            x = 30 + (i * 97) % 240 + math.sin(t * 2 + i) * 7
            y = 335 - ph * 320
            g.setBrush(QBrush(alpha(mix(QColor("#ffd27a"), EMBER_CORE, b), a * (1 - ph))))
            g.drawEllipse(P(x, y), 2.6 * (1 - ph) + 0.6, 2.6 * (1 - ph) + 0.6)
        g.restore()

    @property
    def kit(self):
        """The current outfit: colours and pieces (see VORN_LOOKS)."""
        return self.OUTFITS[self.outfit]

    def _cape(self, g):
        """Cape behind him (floor-length, or shorter in some outfits), with a ragged hem that sways."""
        k, t = self.kit, self.t
        if not k["hem"]:
            return
        g.save()
        if k["hem"] < 984:  # a shorter cape: the long one squeezed up toward his shoulders, and a bit narrower
            f = (k["hem"] - 256) / (984 - 256)
            g.translate(150, 256)
            g.scale(0.6 + 0.4 * f, f)
            g.translate(-150, -256)
        hem = [(-22 + 344 * i / 10 + math.sin(t * 1.3 + i * 0.8) * 4, 984 - (30 if i % 2 else 0) + math.sin(t * 1.1 + i) * 3)
               for i in range(11)]
        cape = QPainterPath(P(52, 256))
        cape.quadTo(P(4, 560), P(*hem[0]))
        for pt in hem[1:]:
            cape.lineTo(P(*pt))
        cape.quadTo(P(296, 560), P(248, 256))
        cape.closeSubpath()
        fill(g, cape, vgrad(256, 990, *k["cape"]))
        for x0, x1 in ((40, 6), (92, 70), (208, 230), (260, 294)):  # folds
            fold = QPainterPath(P(x0, 420))
            fold.quadTo(P((x0 + x1) / 2 + math.sin(t * 1.2 + x0) * 4, 700), P(x1, 950))
            stroke(g, fold, alpha(k["cape"][1], 0.9), 3)
        for color, width in ((k["lining"], 7), (GOLD if self.tier >= 2 else None, 5)):  # coloured lining, then the gold upgrade
            if color is None:
                continue
            for a, c, b in (((52, 258), (4, 560), hem[0]), ((248, 258), (296, 560), hem[-1])):
                edge = QPainterPath(P(*a))
                edge.quadTo(P(*c), P(*b))
                stroke(g, edge, color, width)
        g.restore()

    def _wraps(self, g, a, b, r, color):
        """Cloth bands wrapped around a limb segment from a to b, r wide."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        ux, uy, nx, ny = dx / n, dy / n, -dy / n, dx / n
        for f in (0.12, 0.3, 0.48, 0.66, 0.84):
            cx, cy = a[0] + dx * f, a[1] + dy * f
            band = QPainterPath(P(cx + nx * r - ux * 7, cy + ny * r - uy * 7))
            band.lineTo(P(cx - nx * r + ux * 7, cy - ny * r + uy * 7))
            stroke(g, band, color, 2.2)

    def _limb(self, g, a, b, ra, rb, color, shade=None, ridge=None, width=2.2):
        """A tapered, round-ended segment from a (radius ra) to b (radius rb), cel-shaded on its right side."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / n, dx / n
        if nx < 0:
            nx, ny = -nx, -ny  # (nx, ny) points to the shaded right side
        body = poly((a[0] + nx * ra, a[1] + ny * ra), (b[0] + nx * rb, b[1] + ny * rb),
                    (b[0] - nx * rb, b[1] - ny * rb), (a[0] - nx * ra, a[1] - ny * ra))
        for c, r in ((a, ra), (b, rb)):
            cap = QPainterPath()
            cap.addEllipse(P(*c), r, r)
            body = body.united(cap)
        fill(g, body, color, width)
        if shade is not None:
            g.save()
            g.setClipPath(body)
            fill(g, poly((a[0] + nx * ra * 0.25, a[1] + ny * ra * 0.25), (b[0] + nx * rb * 0.25, b[1] + ny * rb * 0.25),
                         (b[0] + nx * rb * 2, b[1] + ny * rb * 2 + rb), (a[0] + nx * ra * 2, a[1] + ny * ra * 2 - ra)), alpha(shade, 0.7), 0)
            g.restore()
        if ridge is not None:
            line = QPainterPath(P(a[0] - nx * ra * 0.2, a[1] - ny * ra * 0.2))
            line.lineTo(P(b[0] - nx * rb * 0.2, b[1] - ny * rb * 0.2))
            stroke(g, line, ridge, 2)
        return body

    def _polish(self):
        """His armour's highlight: polished once you've earned some respect."""
        return self.kit["polish"] if self.tier >= 1 else self.kit["steel"][2]

    def _trim(self):
        """Trim colour (main, shadow): gold once you've earned some respect."""
        return (GOLD, GOLD_SH) if self.tier >= 1 else self.kit["trim"]

    def _legs(self, g):
        k = self.kit
        polished, trim = self._polish(), self._trim()[0]
        for side in (-1, 1):
            hip = (150 + side * 28, 540)
            sx, cy = side * math.sin(math.radians(7)), math.cos(math.radians(7))  # a wide, planted stance
            knee = (hip[0] + sx * 208, hip[1] + cy * 208)
            ankle = (knee[0] + sx * 186, knee[1] + cy * 186)
            self._limb(g, hip, knee, 42, 30, *k["legs"])
            self._limb(g, knee, ankle, 31, 23, k["shin"][0], k["shin"][1], ridge=polished if k["plate"] and not k["wraps"] else None)
            if k["wraps"]:
                self._wraps(g, knee, ankle, 28, k["shin"][1])
            self._cracks(g, [self._seam(knee, ankle, 22)])
            boot = poly(*[(ankle[0] + side * x, ankle[1] + y) for x, y in
                          ((-23, -14), (23, -14), (25, 30), (46, 38), (54, 50), (50, 58), (-24, 58), (-26, 30))])
            fill(g, boot, vgrad(ankle[1] - 14, ankle[1] + 58, *k["boots"]))
            sole = QPainterPath(P(ankle[0] - side * 24, ankle[1] + 54))
            sole.lineTo(P(ankle[0] + side * 50, ankle[1] + 54))
            stroke(g, sole, INK, 4)
            if not k["plate"]:
                continue
            cuff = poly((ankle[0] - 25, ankle[1] - 16), (ankle[0] + 25, ankle[1] - 16), (ankle[0] + 25, ankle[1] - 4), (ankle[0] - 25, ankle[1] - 4))
            fill(g, cuff, trim, 1.6)
            kneecap = QPainterPath()
            kneecap.addEllipse(P(*knee), 32, 26)
            fill(g, kneecap, vgrad(knee[1] - 24, knee[1] + 24, polished, k["steel"][1]))
            if k["spikes"]:
                spike = poly((knee[0] - 7, knee[1] - 4), (knee[0] + sx * 6, knee[1] - 34), (knee[0] + 7, knee[1] - 4))
                fill(g, spike, vgrad(knee[1] - 34, knee[1], k["steel"][2], k["steel"][0]), 1.6)

    def _sigil(self, g, cx, cy):
        """His emblem: a disc with three claw slashes."""
        sigil = QPainterPath()
        sigil.addEllipse(P(cx, cy), 17, 17)
        fill(g, sigil, vgrad(cy - 17, cy + 17, *self._trim()), 2)
        for i in (-1, 0, 1):
            c = QPainterPath(P(cx - 6 + i * 8, cy - 11))
            c.quadTo(P(cx - 1 + i * 8, cy - 1), P(cx + 4 + i * 8, cy + 11))
            stroke(g, c, INK, 2.6)

    def _hoodie(self, g):
        """Off-duty: a hoodie instead of armour, with a pocket, drawstrings and his sigil."""
        main, shade, hi = self.kit["fore"]
        body = QPainterPath(P(80, 270))
        body.lineTo(P(220, 270))
        body.quadTo(P(238, 400), P(230, 530))
        body.lineTo(P(70, 530))
        body.quadTo(P(62, 400), P(80, 270))
        fill(g, body, vgrad(270, 530, main, shade))
        g.save()
        g.setClipPath(body)
        fill(g, poly((150, 262), (240, 262), (240, 540), (150, 540)), alpha(shade, 0.45), 0)  # cel shadow
        g.restore()
        hem = QPainterPath()
        hem.addRoundedRect(68, 512, 164, 24, 8, 8)
        fill(g, hem, vgrad(512, 536, hi, shade), 2)
        pocket = poly((106, 438), (194, 438), (204, 504), (96, 504))
        fill(g, pocket, alpha(hi, 0.35), 2)
        for x0, x1 in ((140, 134), (160, 166)):  # drawstrings
            s = QPainterPath(P(x0, 276))
            s.quadTo(P((x0 + x1) / 2, 310), P(x1, 338))
            stroke(g, s, QColor("#d9d4de"), 2.4)
            tip = QPainterPath()
            tip.addRoundedRect(x1 - 3, 336, 6, 12, 2, 2)
            fill(g, tip, QColor("#d9d4de"), 1.2)
        self._sigil(g, 150, 388)
        self._cracks(g, CHEST_CRACKS)

    def _torso(self, g):
        k = self.kit
        if not k["plate"]:
            return self._hoodie(g)
        tier = self.tier
        trim = self._trim()
        steel, steel_sh, steel_hi = k["steel"]
        sw = math.sin(self.t * 1.4) * 3
        if k["tabard"]:
            tabard = poly((128, 500), (172, 500), (180 + sw, 700), (150 + sw, 726), (120 + sw, 700))
            fill(g, tabard, vgrad(500, 726, *k["tabard"]))
            if tier >= 2:
                for a, b in (((128, 504), (120 + sw, 698)), ((172, 504), (180 + sw, 698))):
                    edge = QPainterPath(P(*a))
                    edge.lineTo(P(*b))
                    stroke(g, edge, GOLD, 3)
        for side in (-1, 1):  # hip armor plates
            m = (lambda pts: pts) if side < 0 else mirror
            for pts in ([(80, 496), (100, 498), (92, 574), (74, 562)], [(98, 498), (138, 500), (134, 596), (88, 586)]):
                plate = poly(*m(pts))
                fill(g, plate, vgrad(496, 596, steel_hi, steel_sh))
            for rx, ry in m([(108, 512), (126, 513)]):
                g.setPen(pen(INK, 1))
                g.setBrush(QBrush(trim[0]))
                g.drawEllipse(P(rx, ry), 2.6, 2.6)
        fill(g, poly((106, 420), (194, 420), (198, 500), (102, 500)), k["suit"][0])
        band_c = (k["fore"][2], k["fore"][1]) if k["wraps"] else (steel_hi, steel_sh)  # cloth wraps or belly plates
        for i, y in enumerate((430, 451, 472)):
            band = QPainterPath()
            band.addRoundedRect(102 + i * 2, y, 96 - i * 4, 24, 6, 6)
            fill(g, band, vgrad(y, y + 24, *band_c), 1.8)
        belt = QPainterPath()
        belt.addRoundedRect(96, 484, 108, 22, 4, 4)
        fill(g, belt, vgrad(484, 506, LEATHER, LEATHER_SH), 2)
        buckle = QPainterPath()
        buckle.addRoundedRect(136, 480, 28, 30, 5, 5)
        fill(g, buckle, vgrad(480, 510, *trim), 2)
        plate = QPainterPath(P(82, 276))
        plate.lineTo(P(150, 260))
        plate.lineTo(P(218, 276))
        plate.quadTo(P(232, 340), P(222, 400))
        plate.quadTo(P(214, 428), P(198, 438))
        plate.quadTo(P(174, 452), P(150, 450))
        plate.quadTo(P(126, 452), P(102, 438))
        plate.quadTo(P(86, 428), P(78, 400))
        plate.quadTo(P(68, 340), P(82, 276))
        fill(g, plate, vgrad(260, 450, steel, steel_sh))
        g.save()
        g.setClipPath(plate)
        fill(g, poly((150, 262), (240, 262), (240, 460), (150, 460)), alpha(steel_sh, 0.55), 0)  # cel shadow
        g.restore()
        pecs = QPainterPath(P(96, 350))
        pecs.quadTo(P(124, 376), P(150, 360))
        pecs.quadTo(P(176, 376), P(204, 350))
        stroke(g, pecs, alpha(INK, 0.55), 2)
        ridge = QPainterPath(P(150, 266))
        ridge.lineTo(P(150, 446))
        stroke(g, ridge, steel_hi, 2)
        self._sigil(g, 150, 308)
        self._cracks(g, CHEST_CRACKS)

    def _seam(self, a, b, r):
        """A jagged crack running down a limb segment from a to b, r wide."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / n, dx / n
        return [(a[0] + dx * f + nx * r * o, a[1] + dy * f + ny * r * o)
                for f, o in ((0.15, 0.0), (0.32, 0.35), (0.5, -0.2), (0.68, 0.3), (0.85, -0.1))]

    SHOULDER, UPPER, FORE = SHOULDER, UPPER, FORE  # arm geometry (Mika has her own)

    def arm_points(self):
        """{side: (shoulder, elbow, wrist, forearm dx, forearm dy)} for the current pose; side -1 = left, 1 = right."""
        near = 1 if self.toward > 0 else -1  # the gesturing arm, on the side of the bubble
        arm = {}
        for side in (-1, 1):
            upper, fore, length = self.arms[side]
            if side == near and self.mood == "angry":
                fore += math.sin(self.t * 32) * 4  # shaking fist
            sx, sy = self.SHOULDER if side < 0 else (BUST_W - self.SHOULDER[0], self.SHOULDER[1])
            a1, a2 = math.radians(upper), math.radians(fore)
            elbow = (sx + side * math.sin(a1) * self.UPPER * length, sy + math.cos(a1) * self.UPPER * length)
            dx, dy = side * math.sin(a2), math.cos(a2)
            arm[side] = ((sx, sy), elbow, (elbow[0] + dx * self.FORE, elbow[1] + dy * self.FORE), dx, dy)
        return arm

    def _arms(self, g):
        pose = self.pose()
        near = 1 if self.toward > 0 else -1  # the gesturing arm, on the side of his bubble
        k = self.kit
        polished, trim = self._polish(), self._trim()[0]
        arm = {side: ((s[0], s[1] - 24), *rest) for side, (s, *rest) in self.arm_points().items()}  # sleeves start under the pauldron

        def forearm(side):
            _, elbow, wrist, dx, dy = arm[side]
            self._limb(g, elbow, wrist, 26, 21, k["fore"][0], k["fore"][1], ridge=polished if k["plate"] and not k["wraps"] else None)
            if k["wraps"]:
                self._wraps(g, elbow, wrist, 24, k["fore"][1])
            self._cracks(g, [self._seam(elbow, wrist, 18)])
            band = QPainterPath(P(wrist[0] - dy * 22 - dx * 14, wrist[1] + dx * 22 - dy * 14))
            band.lineTo(P(wrist[0] + dy * 22 - dx * 14, wrist[1] - dx * 22 - dy * 14))
            stroke(g, band, trim, 4.5)

        def hand(side):
            _, _, wrist, dx, dy = arm[side]
            g.save()
            g.translate(*wrist)
            g.rotate(math.degrees(math.atan2(-dx, dy)))  # local +y runs along the forearm, out of the wrist
            g.scale(1.5, 1.5)
            self._hand(g, pose[side][2], side)
            g.restore()

        # this order works for every pose: with arms crossed, each hand ends up tucked under the other arm's bicep
        for side in (-near, near):  # hand first, so the wrist disappears into the armored cuff
            hand(side)
            forearm(side)
        for side in (-near, near):
            self._limb(g, arm[side][0], arm[side][1], 31, 25, *k["suit"])
        for side in (-1, 1) if k["plate"] else ():
            elbow = arm[side][1]
            cop = QPainterPath()
            cop.addEllipse(P(*elbow), 22, 21)
            fill(g, cop, vgrad(elbow[1] - 21, elbow[1] + 21, polished, k["steel"][1]))

    def _hand(self, g, kind, side):
        """Gloved (or, off-duty, bare) hand at the wrist, fingers toward local +y."""
        GLOVE, GLOVE_HI = self.kit["gloves"]  # noqa: N806 (the outfit's glove colours)
        if kind == "open":
            for i, ang in enumerate((-16, -5, 6, 17)):
                r = math.radians(ang)
                base = (-12 + i * 8, 20)
                self._limb(g, base, (base[0] + math.sin(r) * -22, base[1] + math.cos(r) * 22), 4.6, 4.0, GLOVE, width=1.6)
            self._limb(g, (side * 12, 8), (side * 30, 22), 5, 4.4, GLOVE, width=1.6)  # thumb toward his body
            palm = QPainterPath()
            palm.addRoundedRect(-16, -4, 32, 28, 9, 9)
            fill(g, palm, GLOVE, 1.8)
            return
        if kind == "point":
            self._limb(g, (side * 6, 22), (side * 6, 54), 5, 4.4, GLOVE, width=1.6)
        fist = QPainterPath()
        fist.addRoundedRect(-17, -4, 34, 32, 10, 10)
        fill(g, fist, GLOVE, 1.8)
        for x in (-8, 0, 8):  # knuckles
            k = QPainterPath(P(x, 18))
            k.lineTo(P(x, 26))
            stroke(g, k, alpha(INK, 0.7), 1.3)
        knuckles = QPainterPath(P(-13, 16))
        knuckles.quadTo(P(0, 12), P(13, 16))
        stroke(g, knuckles, GLOVE_HI, 1.6)

    def _back_hair(self, g):
        t = self.t
        s = math.sin(t * 1.5) * 1.5
        back = poly((96, 110), (86, 80), (92, 58), (104, 52), (104, 34 + s), (124, 40), (136, 24 + s), (152, 36),
                    (168, 22 + s), (178, 38), (198, 30 + s), (198, 50), (214, 54 + s), (212, 80), (204, 110))
        fill(g, back, vgrad(10, 110, HAIR, HAIR_SH))
        if self.d["blood"] > 0.02:
            fill(g, back, vgrad(10, 110, alpha(EMBER, 0.7 * self.d["blood"]), alpha(BLOOD, 0.3 * self.d["blood"])), 0)

    def _hair_fire(self, g, b):
        """Dark-red flames rising off his hair (head coordinates)."""
        t = self.t
        for layer, (c0, c1, size) in enumerate(((BLOOD, EMBER, 1.0), (EMBER, QColor("#ff8a2a"), 0.55))):
            for i in range(9):
                u = i / 8
                x = 94 + 112 * u
                base = 100 - 64 * (1 - ((x - 150) / 58) ** 2)  # along the top of his hair
                h = (46 + 20 * math.sin(t * 9 + i * 1.3) + 10 * math.sin(t * 13.7 + i)) * size * b * (1.25 - 0.6 * abs(u - 0.5))
                w = 13 * size
                sway = math.sin(t * 6 + i * 0.7) * 5
                fl = QPainterPath(P(x - w, base + 6))
                fl.cubicTo(P(x - w, base - h * 0.5), P(x - w * 0.2 + sway * 0.5, base - h * 0.8), P(x + sway, base - h))
                fl.cubicTo(P(x + w * 0.2 + sway * 0.5, base - h * 0.8), P(x + w, base - h * 0.5), P(x + w, base + 6))
                fl.closeSubpath()
                fill(g, fl, vgrad(base - h, base + 6, alpha(c1, 0), alpha(c0 if layer == 0 else c1, (0.9 if layer else 0.8) * b)), 0)

    def _cracks(self, g, lines):
        """Molten light glowing through cracks in the armor (Bloodfire)."""
        b = self.d["blood"]
        if b < 0.02:
            return
        pulse = 0.75 + 0.25 * math.sin(self.t * 7)
        for pts in lines:
            crack = QPainterPath(P(*pts[0]))
            for pt in pts[1:]:
                crack.lineTo(P(*pt))
            stroke(g, crack, alpha(EMBER, 0.45 * b * pulse), 8)
            stroke(g, crack, alpha(EMBER_CORE, b), 2.4)

    def _body(self, g):
        """Neck and collar: fur, an iron gorget, a scarf or a hood, by outfit (the armor is in _torso)."""
        neck = poly((126, 178), (124, 232), (108, 254), (192, 254), (176, 232), (174, 178))
        fill(g, neck, SKIN)
        fill(g, poly((124, 182), (176, 182), (176, 214), (150, 228), (124, 212)), SKIN_SH, 0)  # under-jaw shadow
        fill(g, poly((168, 214), (176, 214), (176, 232), (192, 254), (170, 254)), SKIN_SH, 0)
        for x0, x1 in ((134, 144), (166, 156)):
            m = QPainterPath(P(x0, 216))
            m.lineTo(P(x1, 246))
            stroke(g, m, alpha(SKIN_SH, 0.8), 1.6)
        collar, (main, shade, hi) = self.kit["collar"], self.kit["collar_c"]
        if collar == "fur":
            fur = poly(*FUR_EDGE, (234, 292), (150, 278), (66, 292))
            if self.tier >= 2:  # the white-fur upgrade
                main, shade, hi = FUR_WHITE, FUR_WHITE_SH, FUR_WHITE_SH
            fill(g, fur, vgrad(230, 292, main, shade))
            for i in range(1, len(FUR_EDGE) - 1, 2):
                x, y = FUR_EDGE[i]
                tuft = QPainterPath(P(x, y + 4))
                tuft.lineTo(P(x + (3 if x > 150 else -3), y + 18))
                stroke(g, tuft, hi, 1.6)
            return
        fill(g, poly(*COWL), vgrad(232, 292, hi if collar == "gorget" else main, shade))
        if collar == "gorget":  # iron collar: a ridge, a trim edge and rivets
            ridge = QPainterPath(P(84, 268))
            ridge.quadTo(P(150, 244), P(216, 268))
            stroke(g, ridge, alpha(INK, 0.6), 2)
            edge = QPainterPath(P(66, 292))
            edge.lineTo(P(150, 278))
            edge.lineTo(P(234, 292))
            stroke(g, edge, self._trim()[0], 3.5)
            for rx, ry in ((96, 262), (124, 252), (176, 252), (204, 262)):
                g.setPen(pen(INK, 1))
                g.setBrush(QBrush(self._trim()[0]))
                g.drawEllipse(P(rx, ry), 2.6, 2.6)
        elif collar == "scarf":  # cloth folds
            for a, b in (((100, 248), (112, 284)), ((150, 236), (150, 276)), ((200, 248), (188, 284))):
                fold = QPainterPath(P(*a))
                fold.lineTo(P(*b))
                stroke(g, fold, shade, 2.2)
        else:  # the hood, down around his neck
            opening = QPainterPath(P(108, 252))
            opening.quadTo(P(150, 276), P(192, 252))
            stroke(g, opening, shade, 3)

    def _head(self, g):
        p = self.d
        for side in (-1, 1):
            ear = [(101, 118), (90, 114), (88, 138), (94, 152), (104, 154)]
            fill(g, poly(*(ear if side < 0 else mirror(ear))), SKIN)
        face = face_path()
        fill(g, face, SKIN)
        g.save()
        g.setClipPath(face)
        sh = [(184, 80), (210, 80), (210, 222), (150, 222), (160, 212), (174, 196), (186, 176), (190, 150), (188, 118)]
        fill(g, poly(*sh), SKIN_SH, 0)  # light from the upper left
        fill(g, poly((96, 78), (204, 78), (204, 96), (182, 96), (166, 92), (150, 98), (134, 92), (118, 96), (96, 98)), SKIN_SH, 0)
        for side in (-1, 1):  # shaved sides of the undercut
            fill(g, poly(*([(96, 86), (112, 84), (108, 118), (96, 120)] if side < 0 else mirror([(96, 86), (112, 84), (108, 118), (96, 120)]))), alpha(HAIR_SH, 0.5), 0)
        stubble = QPainterPath(P(100, 168))  # rugged shadow beard along the jaw and chin
        stubble.quadTo(P(116, 190), P(130, 184))
        stubble.quadTo(P(150, 178), P(170, 184))
        stubble.quadTo(P(184, 190), P(200, 168))
        stubble.lineTo(P(200, 222))
        stubble.lineTo(P(100, 222))
        stubble.closeSubpath()
        fill(g, stubble, alpha(HAIR_SH, 0.38), 0)
        fill(g, poly((152, 142), (159, 167), (153, 171), (150, 150)), SKIN_SH, 0)  # nose shadow
        g.restore()

        for cx, side in ((127, -1), (173, 1)):
            self._eye(g, cx, 140, side)
            self._brow(g, cx, 140, side)
        tip = QPainterPath(P(145, 168))
        tip.quadTo(P(152, 174), P(159, 167))
        stroke(g, tip, INK, 1.8)
        bridge = QPainterPath(P(147, 142))
        bridge.lineTo(P(148, 160))
        stroke(g, bridge, alpha(SKIN_SH, 0.9), 1.4)
        for a, b in (((176, 108), (179, 129)), ((182, 151), (188, 172))):  # scar through the brow and cheek
            sc = QPainterPath(P(*a))
            sc.lineTo(P(*b))
            stroke(g, sc, SKIN, 4.5)
            stroke(g, sc, SCAR, 2.4)

        self._mouth(g)

        sw = math.sin(self.t * 1.9) * 1.5
        top = QPainterPath(P(96, 104))
        top.cubicTo(P(90, 62), P(116, 38), P(150, 38))
        top.cubicTo(P(186, 38), P(212, 62), P(204, 104))
        top.cubicTo(P(194, 88), P(180, 80), P(170, 82))
        top.lineTo(P(176 + sw, 100))  # two heavy locks fall forward
        top.lineTo(P(158, 82))
        top.quadTo(P(150, 80), P(142, 82))
        top.lineTo(P(128 + sw, 98))
        top.lineTo(P(130, 82))
        top.cubicTo(P(118, 82), P(104, 90), P(96, 104))
        fill(g, top, vgrad(38, 100, HAIR, HAIR_SH))
        for a, b, c in [((116, 86), (110, 62), (126, 46)), ((150, 80), (146, 58), (152, 42)), ((184, 86), (194, 64), (180, 46))]:
            s = QPainterPath(P(*a))
            s.quadTo(P(*b), P(*c))
            stroke(g, s, HAIR_SH, 1.6)
        hi = QPainterPath(P(120, 56))
        hi.quadTo(P(148, 44), P(178, 54))
        stroke(g, hi, alpha(HAIR_HI, 0.9), 3)
        if p["blood"] > 0.02:  # Bloodfire: the hair glows from within and ignites
            fill(g, top, vgrad(38, 100, alpha(EMBER, 0.75 * p["blood"]), alpha(BLOOD, 0.35 * p["blood"])), 0)
            self._hair_fire(g, p["blood"])

        if self.tier >= 3:  # jagged war-crown
            def arc_y(x):
                return 86 - 22 * (1 - ((x - 150) / 52) ** 2)

            crown = [(x, arc_y(x)) for x in range(100, 201, 10)]
            for x in range(200, 99, -10):
                spike = 26 if x == 150 else 18 if x in (120, 130, 170, 180) else 8
                crown.append((x, arc_y(x) - spike))
            fill(g, poly(*crown), vgrad(40, 90, GOLD, GOLD_SH), 1.8)
            gem = QPainterPath()
            gem.addEllipse(P(150, arc_y(150) - 7), 4, 4)
            fill(g, gem, GEM, 1.2)

        if p["vein"] > 0.05:  # anime anger mark at the temple
            c = alpha(QColor("#e0263a"), p["vein"])
            for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                v = QPainterPath(P(186 + dx * 3, 102 + dy * 8))
                v.quadTo(P(186 + dx * 3, 102 + dy * 3), P(186 + dx * 8, 102 + dy * 3))
                stroke(g, v, c, 2.8)

    def _eye(self, g, cx, cy, side):
        p = self.d
        if p["happy"] > 0.5:
            arc = QPainterPath(P(cx - 13, cy + 3))
            arc.quadTo(P(cx, cy - 6), P(cx + 13, cy + 3))
            stroke(g, arc, INK, 3.6)
            return
        h = 8 * max(0.0, p["open"]) * abs(1 - 2 * self.blink)
        inner, outer = P(cx - side * 14, cy + 1), P(cx + side * 15, cy - 2)
        upper = P(cx + side * 2, cy - 1.7 * h)
        almond = QPainterPath(inner)
        almond.quadTo(upper, outer)
        almond.quadTo(P(cx, cy + 1.2 * h), inner)
        if h > 0.5:
            g.setPen(Qt.NoPen)
            g.setBrush(QBrush(SCLERA))
            g.drawPath(almond)
            g.save()
            g.setClipPath(almond)
            ix, iy = cx + (p["look"] + self.glance) * 6 + p["roll_x"], cy + p["roll_y"]
            k = p["blood"]  # Bloodfire: the eyes burn white
            iris = QRadialGradient(P(ix, iy), 7)
            iris.setColorAt(0, mix(IRIS, QColor("white"), k))
            iris.setColorAt(1, mix(IRIS_SH, EMBER_CORE, k))
            g.setBrush(QBrush(iris))
            g.setPen(pen(INK, 1.2))
            g.drawEllipse(P(ix, iy), 6.6, 6.6)
            g.setPen(Qt.NoPen)
            g.setBrush(QBrush(alpha(INK, 1 - k)))
            g.drawEllipse(P(ix, iy), 2.8 * p["pupil"], 3.0 * p["pupil"])
            g.setBrush(QBrush(QColor("white")))
            g.drawEllipse(P(ix - 2, iy - 2.5), 1.6, 1.6)
            g.setBrush(QBrush(alpha(INK, 0.35)))  # lid shadow on the eyeball
            g.drawRect(cx - 20, cy - 20, 40, 20 - 1.0 * h)
            g.restore()
        lid = QPainterPath(inner)
        lid.quadTo(upper, outer)
        lid.lineTo(P(cx + side * 19, cy - 1))
        stroke(g, lid, INK, 3.4)
        crease = QPainterPath(P(cx - side * 9, cy - 1.7 * h - 3))
        crease.quadTo(P(cx + side * 4, cy - 1.9 * h - 6), P(cx + side * 14, cy - 1.2 * h - 4))
        stroke(g, crease, alpha(INK, 0.6), 1.3)
        low = QPainterPath(P(cx - side * 8, cy + 0.9 * h + 1))
        low.quadTo(P(cx + side * 4, cy + 1.1 * h + 1), P(cx + side * 12, cy + 0.4 * h))
        stroke(g, low, alpha(INK, 0.7), 1.2)
        if p["blood"] > 0.02 and h > 0.5:  # white-hot glow spilling out of the eye
            glow = QRadialGradient(P(cx, cy), 24)
            glow.setColorAt(0, alpha(QColor("white"), 0.75 * p["blood"]))
            glow.setColorAt(0.4, alpha(EMBER_CORE, 0.45 * p["blood"]))
            glow.setColorAt(1, alpha(EMBER, 0))
            g.setPen(Qt.NoPen)
            g.setBrush(QBrush(glow))
            g.drawEllipse(P(cx, cy), 24, 24)

    def _brow(self, g, cx, cy, side):
        p = self.d
        lift = p["lift"] + (p["lift_r"] if side > 0 else 0)
        by = cy - 15 - lift * 7
        inner = (cx - side * 13, by + p["brow"] * 6)
        outer = (cx + side * 20, by - 3 - p["brow"] * 1.5)
        b = poly((inner[0], inner[1] - 3.5), (outer[0], outer[1] - 1), (outer[0] - side * 2, outer[1] + 1.5), (inner[0], inner[1] + 3.5))
        fill(g, b, HAIR_SH, 1.2)

    def _mouth(self, g):
        p = self.d
        cx, cy = 150, 197
        open_ = max(p["mouth"], self.talk * 0.9)
        smile, smirk = p["smile"], p["smirk"]
        w = 12 + 3 * max(smile, 0) + 3 * open_
        left = P(cx - w, cy - smile * 3 + max(-smirk, 0) * 2)
        right = P(cx + w, cy - smile * 3 - smirk * 5)
        upper = P(cx, cy + smile * 5 - open_ * 2)
        if open_ < 0.06 and p["teeth"] < 0.5:
            m = QPainterPath(left)
            m.quadTo(upper, right)
            stroke(g, m, INK, 2.4)
            return
        lower = P(cx + smirk, cy + 3 + open_ * 22 + max(smile, 0) * 5)
        m = QPainterPath(left)
        m.quadTo(upper, right)
        m.quadTo(lower, left)
        g.setPen(Qt.NoPen)
        g.setBrush(QBrush(MOUTH))
        g.drawPath(m)
        g.save()
        g.setClipPath(m)
        g.setBrush(QBrush(TONGUE))
        g.drawEllipse(P(cx, cy + 5 + open_ * 11), w * 0.55, 6)
        gritted = p["teeth"] > 0.5 and open_ < 0.4
        if p["teeth"] > 0.5 or open_ > 0.35:
            g.setBrush(QBrush(SCLERA))
            top = min(left.y(), right.y()) - 4
            g.drawRect(cx - w, top, 2 * w, (upper.y() - top) + 4 + (3 if gritted else 0))
            if gritted:
                g.drawRect(cx - w, cy + 3, 2 * w, 12)
                for i in range(-2, 3):
                    tooth = QPainterPath(P(cx + i * 5, cy - 6))
                    tooth.lineTo(P(cx + i * 5, cy + 12))
                    stroke(g, tooth, alpha(INK, 0.5), 1)
        g.restore()
        g.setBrush(Qt.NoBrush)
        g.setPen(pen(INK, 2.2))
        g.drawPath(m)

    def _shoulders(self, g):
        k = self.kit
        if not k["plate"]:  # off-duty: no pauldrons
            return
        steel, steel_sh, steel_hi = k["steel"]
        for side in (-1, 1):
            m = (lambda pts: pts) if side < 0 else mirror
            for base_a, tip, base_b in SPIKES if k["spikes"] else ():
                fill(g, poly(*m([base_a, tip, base_b])), vgrad(200, 250, steel_hi, steel))
            plate = poly(*m(PAULDRON))
            fill(g, plate, vgrad(238, 314, self._polish(), steel_sh))
            g.save()
            g.setClipPath(plate)
            fill(g, poly(*m([(60, 290), (130, 250), (130, 330), (60, 330)])), alpha(steel_sh, 0.6), 0)
            self._cracks(g, [m(c) for c in PAULDRON_CRACKS])
            g.restore()
            rim = QPainterPath(P(*m([(24, 268)])[0]))
            for pt in m([(56, 246), (100, 248), (114, 266)]):
                rim.lineTo(P(*pt))
            stroke(g, rim, self._trim()[0], 3)
            for rx, ry in m([(40, 268), (66, 256), (94, 258)]):
                g.setPen(pen(INK, 1))
                g.setBrush(QBrush(k["trim"][0]))
                g.drawEllipse(P(rx, ry), 2.6, 2.6)


def make_character(name):
    """The drawing for a preset's CHARACTER: "vorn" or "mika"."""
    if name == "mika":
        from mika import Mika
        char = Mika()
    else:
        char = Vorn()
    char.step(random.uniform(5, 60), 0.0)  # a random head start: two on screen don't breathe, sway and blink in lockstep
    return char
