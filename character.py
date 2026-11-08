"""Warlord Vorn: an original character, drawn and animated live with QPainter (no image files).

Serious anime bust with hard cel shading. Every face part is driven by numbers, so moods blend
smoothly and the mouth lip-syncs to his voice.
"""
import math
import random

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

W, H = 300, 340  # logical canvas; the overlay scales it

INK = QColor("#1b1418")
SKIN, SKIN_SH = QColor("#d9a27c"), QColor("#a8694c")
HAIR, HAIR_SH, HAIR_HI = QColor("#7a1f22"), QColor("#3a0b0f"), QColor("#c0504a")
SCLERA = QColor("#f1e9df")
IRIS, IRIS_SH = QColor("#ff6a2a"), QColor("#7a0e00")
STEEL, STEEL_SH, STEEL_HI = QColor("#454b58"), QColor("#1f232b"), QColor("#7a8396")
BRONZE, BRONZE_SH = QColor("#c8893f"), QColor("#7a4a1a")
FUR, FUR_SH, FUR_HI = QColor("#54453c"), QColor("#2b221d"), QColor("#8a7563")
CAPE, CAPE_SH = QColor("#5e1016"), QColor("#2a0609")
MOUTH, TONGUE = QColor("#3e0d12"), QColor("#a8414c")
SCAR = QColor("#e0a48c")
# upgrades he earns as your respect grows (see tier_for)
GOLD, GOLD_SH = QColor("#f2c64d"), QColor("#9a6b12")
STEEL_POLISH = QColor("#aab4c8")
FUR_WHITE, FUR_WHITE_SH = QColor("#ebe7df"), QColor("#9c958a")


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
    return [(W - x, y) for x, y in pts]


def vgrad(y0, y1, c0, c1):
    gr = QLinearGradient(0, y0, 0, y1)
    gr.setColorAt(0, c0)
    gr.setColorAt(1, c1)
    return gr


def alpha(color, a):
    c = QColor(color)
    c.setAlphaF(max(0.0, min(1.0, a)))
    return c


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
    def __init__(self):
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
        self.d = self._effective()

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
        return p

    def render(self, scale=1.0):
        img = QImage(int(W * scale), int(H * scale), QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        g = QPainter(img)
        g.scale(scale, scale)
        self.paint(g)
        g.end()
        return img

    # ---------------------------------------------------------------- drawing
    def paint(self, g):
        p, t = self._effective(), self.t
        self.d = p  # what the face-part drawers read
        g.setRenderHint(QPainter.Antialiasing)
        breath = math.sin(t * 2 * math.pi / 3.8)
        s = 1 + 0.04 * self.pop ** 2
        g.save()
        g.translate(W / 2, H)
        g.scale(s, s)
        g.translate(-W / 2, -H)
        if self.tier >= 3:  # a constant golden glow once you've earned real respect
            glow = QRadialGradient(P(150, 200), 170)
            glow.setColorAt(0, alpha(GOLD, 0.3 + 0.06 * math.sin(t * 2)))
            glow.setColorAt(1, alpha(GOLD, 0))
            g.setPen(Qt.NoPen)
            g.setBrush(QBrush(glow))
            g.drawEllipse(P(150, 200), 170, 170)
        self._aura(g, p["aura"])
        g.translate(0, breath * 1.4)
        head = (
            math.sin(t * 36) * 1.6 * p["happy"] + math.sin(t * 61) * 0.8 * p["aura"] + 3 * self.turn,
            -self.talk * 2.0 + breath * 0.8 - 3 * p["happy"],
            p["tilt"] + math.sin(t * 0.7) * 1.0,
        )
        self._cape(g)
        self._in_head(g, head, self._back_hair)
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
        glow = QRadialGradient(P(150, 190), 180)
        glow.setColorAt(0, alpha(QColor("#ff4a1a"), 0.45 * a))
        glow.setColorAt(1, alpha(QColor("#ff2a00"), 0))
        g.setPen(Qt.NoPen)
        g.setBrush(QBrush(glow))
        g.drawEllipse(P(150, 190), 180, 180)
        for layer, (col, size) in enumerate([(QColor("#ff3d12"), 1.0), (QColor("#ffc23d"), 0.6)]):
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
            g.setBrush(QBrush(alpha(QColor("#ffd27a"), a * (1 - ph))))
            g.drawEllipse(P(x, y), 2.6 * (1 - ph) + 0.6, 2.6 * (1 - ph) + 0.6)

    def _cape(self, g):
        fill(g, poly((52, 256), (2, 344), (298, 344), (248, 256)), vgrad(256, 344, CAPE, CAPE_SH))
        if self.tier >= 2:
            for a, b in (((52, 258), (4, 342)), ((248, 258), (296, 342))):
                edge = QPainterPath(P(*a))
                edge.lineTo(P(*b))
                stroke(g, edge, GOLD, 4)

    def _back_hair(self, g):
        t = self.t
        s = math.sin(t * 1.5) * 1.5
        back = poly((96, 110), (86, 80), (92, 58), (104, 52), (104, 34 + s), (124, 40), (136, 24 + s), (152, 36),
                    (168, 22 + s), (178, 38), (198, 30 + s), (198, 50), (214, 54 + s), (212, 80), (204, 110))
        fill(g, back, vgrad(10, 110, HAIR, HAIR_SH))

    def _body(self, g):
        plate = poly((76, 344), (82, 276), (150, 260), (218, 276), (224, 344))
        fill(g, plate, vgrad(260, 344, STEEL, STEEL_SH))
        fill(g, poly((150, 262), (218, 277), (224, 344), (150, 344)), alpha(STEEL_SH, 0.55), 0)  # cel shadow
        ridge = QPainterPath(P(150, 266))
        ridge.lineTo(P(150, 344))
        stroke(g, ridge, STEEL_HI, 2)
        sigil = QPainterPath()
        sigil.addEllipse(P(150, 308), 17, 17)
        fill(g, sigil, vgrad(291, 325, *((GOLD, GOLD_SH) if self.tier >= 1 else (BRONZE, BRONZE_SH))), 2)
        for i in (-1, 0, 1):  # three claw slashes
            c = QPainterPath(P(144 + i * 8, 297))
            c.quadTo(P(149 + i * 8, 307), P(154 + i * 8, 319))
            stroke(g, c, INK, 2.6)
        neck = poly((126, 178), (124, 232), (108, 254), (192, 254), (176, 232), (174, 178))
        fill(g, neck, SKIN)
        fill(g, poly((124, 182), (176, 182), (176, 214), (150, 228), (124, 212)), SKIN_SH, 0)  # under-jaw shadow
        fill(g, poly((168, 214), (176, 214), (176, 232), (192, 254), (170, 254)), SKIN_SH, 0)
        for x0, x1 in ((134, 144), (166, 156)):
            m = QPainterPath(P(x0, 216))
            m.lineTo(P(x1, 246))
            stroke(g, m, alpha(SKIN_SH, 0.8), 1.6)
        fur = poly(*FUR_EDGE, (234, 292), (150, 278), (66, 292))
        white = self.tier >= 2
        fill(g, fur, vgrad(230, 292, *((FUR_WHITE, FUR_WHITE_SH) if white else (FUR, FUR_SH))))
        for i in range(1, len(FUR_EDGE) - 1, 2):
            x, y = FUR_EDGE[i]
            tuft = QPainterPath(P(x, y + 4))
            tuft.lineTo(P(x + (3 if x > 150 else -3), y + 18))
            stroke(g, tuft, FUR_WHITE_SH if white else FUR_HI, 1.6)

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
            fill(g, gem, IRIS, 1.2)

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
            iris = QRadialGradient(P(ix, iy), 7)
            iris.setColorAt(0, IRIS)
            iris.setColorAt(1, IRIS_SH)
            g.setBrush(QBrush(iris))
            g.setPen(pen(INK, 1.2))
            g.drawEllipse(P(ix, iy), 6.6, 6.6)
            g.setPen(Qt.NoPen)
            g.setBrush(QBrush(INK))
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
        for side in (-1, 1):
            m = (lambda pts: pts) if side < 0 else mirror
            for base_a, tip, base_b in SPIKES:
                fill(g, poly(*m([base_a, tip, base_b])), vgrad(200, 250, STEEL_HI, STEEL))
            plate = poly(*m(PAULDRON))
            fill(g, plate, vgrad(238, 314, STEEL_POLISH if self.tier >= 1 else STEEL_HI, STEEL_SH))
            g.save()
            g.setClipPath(plate)
            fill(g, poly(*m([(60, 290), (130, 250), (130, 330), (60, 330)])), alpha(STEEL_SH, 0.6), 0)
            g.restore()
            rim = QPainterPath(P(*m([(24, 268)])[0]))
            for pt in m([(56, 246), (100, 248), (114, 266)]):
                rim.lineTo(P(*pt))
            stroke(g, rim, GOLD if self.tier >= 1 else BRONZE, 3)
            for rx, ry in m([(40, 268), (66, 256), (94, 258)]):
                g.setPen(pen(INK, 1))
                g.setBrush(QBrush(BRONZE))
                g.drawEllipse(P(rx, ry), 2.6, 2.6)
