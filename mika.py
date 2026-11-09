"""Mika: an original anime gamer girl (long pink hair, pink eyes, gamer headset), drawn live with QPainter like Vorn.

She reuses Vorn's animation (moods, blinks, glances, poses, slump, power-up timing) and draws her own body.
Her power-up is "Lovesick": the light leaves her eyes, a shadow falls over her face, and dark hearts rise around her.
Same drawing coordinates as Vorn: 300 wide around x=150, feet near FULL_H.
"""
import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QRadialGradient

from character import FULL_H, GOLD, IDLES, INK, P, Vorn, alpha, fill, heart, mirror, mix, pen, poly, stroke, vgrad

SKIN, SKIN_SH, BLUSH = QColor("#ffe3d3"), QColor("#f0b49c"), QColor("#ff8fb1")
HAIR, HAIR_SH, HAIR_HI, HAIR_DEEP = QColor("#ff8cc6"), QColor("#e0559c"), QColor("#ffd0e8"), QColor("#b8327a")
IRIS, IRIS_SH, PUPIL = QColor("#ff5fa8"), QColor("#9e1a5c"), QColor("#4a0c2c")
SET, SET_HI, LED, CYAN = QColor("#26232e"), QColor("#4a4658"), QColor("#ff4fa3"), QColor("#3ee6ff")
WHITE = QColor("#f7f4f9")
DARK = QColor("#2a0618")  # Lovesick shadow

OUTFITS = {
    # top style, main, trim, accent, bottom style, bottom colour, socks, sock stripe, sock top (y), shoes, shoe trim
    "jacket": dict(top="jacket", main="#24212c", trim="#ff4fa3", accent="#3ee6ff", bottom="skirt", low="#2b2733",
                   socks="#1f1c25", stripe="#ff4fa3", sock_top=612, shoes="#f5f3f7", shoe_trim="#ff4fa3"),
    "hoodie": dict(top="hoodie", main="#ffc4de", trim="#ff7fb8", accent="#ffffff", bottom="shorts", low="#2d2a35",
                   socks="#ffffff", stripe="#ff9cc9", sock_top=742, shoes="#ffffff", shoe_trim="#ff7fb8"),
    "gothic": dict(top="dress", main="#1c1a22", trim="#f1eef4", accent="#c2185b", bottom="none", low="#1c1a22",
                   socks="#16141b", stripe=None, sock_top=520, shoes="#141218", shoe_trim="#c2185b"),
    "jersey": dict(top="jersey", main="#f6f4fa", trim="#ff4fa3", accent="#7b5cff", bottom="shorts", low="#ff4fa3",
                   socks="#f6f4fa", stripe="#7b5cff", sock_top=730, shoes="#26232e", shoe_trim="#ff4fa3"),
    # anime-inspired (original takes on common looks). Extra pieces: apron, obi (sash colour), pattern (flower colour),
    # chest_bow, sleeves ("puff" or "wide"), head ("maid" frill, "bow" or "flower"). Socks up at the hip make trousers.
    "maid": dict(top="dress", main="#1e1b24", trim="#ffffff", accent="#ff4fa3", bottom="none", low="#1e1b24", socks="#ffffff",
                 stripe=None, sock_top=600, shoes="#1a1720", shoe_trim="#ff4fa3", apron=True, sleeves="puff", head="maid"),
    "shrine maiden": dict(top="kimono", main="#fbf8f4", trim="#d7263d", accent="#d7263d", bottom="hakama", low="#c8203a",
                          socks="#ffffff", stripe=None, sock_top=860, shoes="#f2ede6", shoe_trim="#d7263d", obi="#c8203a",
                          sleeves="wide", head="bow"),
    "magical girl": dict(top="dress", main="#ffb3d9", trim="#ffffff", accent="#ffd34d", bottom="none", low="#ffb3d9",
                         socks="#ffffff", stripe="#ff7fb8", sock_top=660, shoes="#ff7fb8", shoe_trim="#ffd34d", chest_bow=True,
                         sleeves="puff", head="bow"),
    "yukata": dict(top="kimono", main="#27325e", trim="#f3e9ff", accent="#ff8fc8", bottom="robe", low="#27325e", socks="#ffffff",
                   stripe=None, sock_top=880, shoes="#b07a46", shoe_trim="#d7263d", obi="#ff8fc8", pattern="#ffc2e0",
                   sleeves="wide", head="flower"),
    "netrunner": dict(top="jacket", main="#121018", trim="#2ef2ff", accent="#ff2e9a", bottom="shorts", low="#1a1622",
                      socks="#141119", stripe="#2ef2ff", sock_top=500, shoes="#1a1720", shoe_trim="#2ef2ff"),
    "track suit": dict(top="jacket", main="#22305e", trim="#ffffff", accent="#ff4fa3", bottom="none", low="#22305e",
                       socks="#22305e", stripe=None, sock_top=428, shoes="#ffffff", shoe_trim="#ff4fa3"),  # trousers from the jacket hem
    # holidays (see HOLIDAY)
    "pumpkin": dict(top="dress", main="#2a1a33", trim="#ff8a1f", accent="#9b4dff", bottom="none", low="#2a1a33", socks="#1a0f22",
                    stripe="#ff8a1f", sock_top=600, shoes="#1a0f22", shoe_trim="#ff8a1f", head="bow"),  # Halloween
    "holly": dict(top="dress", main="#c8102e", trim="#ffffff", accent="#1f7a3a", bottom="none", low="#c8102e", socks="#ffffff",
                  stripe="#c8102e", sock_top=640, shoes="#1a1720", shoe_trim="#ffffff", sleeves="puff", head="bow"),  # Christmas
    # earned (see UNLOCKS)
    "night owl": dict(top="hoodie", main="#1f2a4a", trim="#8fb4ff", accent="#ffe28a", bottom="shorts", low="#141b30",
                      socks="#2a355a", stripe="#ffe28a", sock_top=700, shoes="#f5f3f7", shoe_trim="#8fb4ff"),
    "idol": dict(top="jacket", main="#fbf7fb", trim="#ffd36b", accent="#ff8fc8", bottom="skirt", low="#ff4fa3", socks="#ffffff",
                 stripe="#ffd36b", sock_top=640, shoes="#ffffff", shoe_trim="#ffd36b", head="bow"),
    "crimson": dict(top="jacket", main="#24070e", trim="#e0244f", accent="#7a0f22", bottom="skirt", low="#1a060b", socks="#14050a",
                    stripe="#e0244f", sock_top=600, shoes="#120608", shoe_trim="#e0244f"),
    "sweetheart": dict(top="dress", main="#ffd6e6", trim="#ffffff", accent="#ff4f8b", bottom="none", low="#ffd6e6", socks="#ffffff",
                       stripe="#ff8fb1", sock_top=680, shoes="#ff8fb1", shoe_trim="#ffffff", chest_bow=True, pattern="#ff8fb1"),
}
HOLIDAY = {"halloween": "pumpkin", "christmas": "holly"}
# her own idle animations, on top of the shared ones (see character.IDLES)
MIKA_IDLES = {
    "adjust headset": dict(time=2.4, pose=((110, -155, "open", 0.65), None), front=True, head=(-2, 0, -5), face=dict(open=-0.3)),
    "twirl hair": dict(time=3.0, pose=((-10, 165, "point", 0.6), None), front=True, wiggle=("near", 10, 3), head=(2, 0, 6),
                       face=dict(smile=0.4)),
    "wave": dict(time=2.4, pose=((30, 170, "open", 1.0), None), wiggle=("near", 18, 2.5), face=dict(smile=0.6, lift=0.3)),
    "heart hands": dict(time=2.8, pose=((-10, -140, "open", 0.8), (-10, -140, "open", 0.8)), face=dict(happy=0.6), effect="hearts"),
    "bounce": dict(time=1.8, face=dict(happy=0.8, smile=0.3)),  # a happy little bounce
}
UNLOCKS = {"night owl": ("hours", 10), "idol": ("talks", 100), "crimson": ("streak", 7), "sweetheart": ("respect", 100)}


class Mika(Vorn):
    SHOULDER, UPPER, FORE = (92, 248), 112, 100

    OUTFITS, OUTFIT_SETTING = OUTFITS, "OUTFIT"  # her wardrobe and the setting that picks from it (Vorn.__init__ chooses)
    SKIN, SKIN_SH, HAIR, HAIR_SH, HAIR_HI, HAIR_DEEP = SKIN, SKIN_SH, HAIR, HAIR_SH, HAIR_HI, HAIR_DEEP  # (recolor())
    IRIS, IRIS_SH, PUPIL = IRIS, IRIS_SH, PUPIL
    LED, TINTED = LED, ("LED",)  # her headset's lights and glow: in the outfit's colour
    SHADES = {"hair": ("HAIR", "HAIR_SH", "HAIR_HI", "HAIR_DEEP"), "eyes": ("IRIS", "IRIS_SH", "PUPIL"), "skin": ("SKIN", "SKIN_SH")}
    UNLOCKS, HOLIDAY = UNLOCKS, HOLIDAY
    IDLES = {**IDLES, **MIKA_IDLES}  # the shared ones and her own
    HAND = 1.35
    earned = set()  # her own (not Vorn's)

    # ---------------------------------------------------------------- drawing
    def draw(self, g):
        p, t = self._effective(), self.t
        self.d = p
        o = self.OUTFITS[self.outfit]
        g.setRenderHint(QPainter.Antialiasing)
        breath = math.sin(t * 2 * math.pi / 3.4)
        s = 1 + 0.04 * self.pop ** 2
        g.save()
        g.translate(150, FULL_H)
        g.scale(s, s)
        g.translate(-150, -FULL_H)
        if self.tier >= 3:  # a soft glow once you've earned her full devotion
            g.save()
            g.translate(150, 480)
            g.scale(0.42, 1.0)
            glow = QRadialGradient(P(0, 0), 520)
            glow.setColorAt(0, alpha(mix(GOLD, self.LED, 0.5), 0.28 + 0.05 * math.sin(t * 2)))
            glow.setColorAt(1, alpha(self.LED, 0))
            g.setPen(Qt.NoPen)
            g.setBrush(QBrush(glow))
            g.drawEllipse(P(0, 0), 520, 520)
            g.restore()
        self._weather(g)
        self._aura(g, p["aura"])
        self._back_hair(g)
        self._legs(g, o)
        g.translate(0, breath * 1.2 + 14 * p["slump"] + 3 * p["happy"] * abs(math.sin(t * 16)))
        ax, ay, atilt = self.idle_head()
        head = (math.sin(t * 34) * 1.4 * p["happy"] + 3 * self.turn + ax,
                -self.talk * 1.6 + breath * 0.6 - 3 * p["happy"] + 10 * p["slump"] + ay,
                p["tilt"] + math.sin(t * 0.8) * 1.2 + atilt)
        self._lower(g, o)
        self._top(g, o)
        self._arms(g)
        self._neck(g, o)
        self._in_head(g, head, self._head)
        self.front_hand(g)
        self.idle_effect(g)
        g.restore()

    def _in_head(self, g, head, draw):
        dx, dy, deg = head
        g.save()
        g.translate(150 + dx, 200 + dy)
        g.rotate(deg)
        g.scale(1.18, 1.18)  # anime proportions: a big head
        g.translate(-150, -200)
        draw(g)
        g.restore()

    def _aura(self, g, a):
        """Pink sparkle when she flares up; in Lovesick it turns dark crimson with hearts rising."""
        b = self.d["blood"]
        if a < 0.02:
            return
        t = self.t
        glow = QRadialGradient(P(150, 420), 330)
        glow.setColorAt(0, alpha(mix(self.LED, QColor("#7a0030"), b), 0.4 * a))
        glow.setColorAt(1, alpha(self.LED, 0))
        g.setPen(Qt.NoPen)
        g.setBrush(QBrush(glow))
        g.drawEllipse(P(150, 420), 230, 560)
        for i in range(14):
            ph = (t * 0.32 + i * 0.173) % 1.0
            x = 20 + (i * 83) % 260 + math.sin(t * 1.7 + i) * 10
            y = 900 - ph * 860
            col = mix(QColor("#ff6fb5"), QColor("#5a0022"), b)
            fill(g, heart(x, y, 9 + 5 * (i % 3)), alpha(col, a * (1 - ph) * 0.85), 1.2 * b)
            if b > 0.5 and i % 2:  # cracked hearts
                crack = QPainterPath(P(x, y - 6))
                crack.lineTo(P(x - 3, y))
                crack.lineTo(P(x + 2, y + 3))
                stroke(g, crack, alpha(INK, (1 - ph) * b), 1.4)

    def _back_hair(self, g):
        t = self.t
        sw = math.sin(t * 1.3 * (1 + 4 * self.rag)) * 5 * (1 + 3 * self.rag)  # (thrown: her hair streams)
        hair = QPainterPath(P(92, 120))
        hair.cubicTo(P(78, 40), P(222, 40), P(208, 120))
        hair.cubicTo(P(228, 260), P(238 + sw, 470), P(226 + sw, 600))
        for i, x in enumerate((206, 186, 166, 150, 134, 114, 94)):  # pointed tips
            hair.lineTo(P(x + sw * 0.8, 600 - (26 if i % 2 == 0 else 0) + (14 if i in (2, 4) else 0)))
        hair.lineTo(P(74 + sw, 600))
        hair.cubicTo(P(62 + sw, 470), P(72, 260), P(92, 120))
        fill(g, hair, vgrad(60, 600, self.HAIR_SH, self.HAIR_DEEP))
        for x0, x1 in ((112, 96), (150, 150), (188, 206)):
            strand = QPainterPath(P(x0, 240))
            strand.quadTo(P((x0 + x1) / 2 + sw * 0.5, 420), P(x1 + sw, 570))
            stroke(g, strand, alpha(self.HAIR_DEEP, 0.8), 2)
        if self.d["blood"] > 0.02:
            fill(g, hair, alpha(QColor("#3a0014"), 0.35 * self.d["blood"]), 0)

    def _legs(self, g, o):
        for side in (-1, 1):
            hip, knee, ankle = (150 + side * 30, 470), (150 + side * 31, 728), (150 + side * 32, 948)
            if self.legs[side]:  # kicking while thrown: the leg swings out around the hip
                a = math.radians(self.legs[side]) * side
                knee, ankle = ((hip[0] + (x - hip[0]) * math.cos(a) + (y - hip[1]) * math.sin(a),
                                hip[1] - (x - hip[0]) * math.sin(a) + (y - hip[1]) * math.cos(a)) for x, y in (knee, ankle))
            leg = self._limb(g, hip, knee, 35, 21, self.SKIN, self.SKIN_SH, width=1.8)
            shin = self._limb(g, knee, ankle, 21, 13, self.SKIN, self.SKIN_SH, width=1.8)
            g.save()  # socks or tights over the skin from sock_top down
            g.setClipPath(leg.united(shin))
            fill(g, poly((60, o["sock_top"]), (240, o["sock_top"]), (240, 960), (60, 960)), QColor(o["socks"]), 0)
            if o["stripe"]:
                fill(g, poly((60, o["sock_top"] + 6), (240, o["sock_top"] + 6), (240, o["sock_top"] + 16), (60, o["sock_top"] + 16)),
                     QColor(o["stripe"]), 0)
            g.restore()
            stroke(g, leg.united(shin), INK, 1.8)
            shoe = poly(*[(ankle[0] + side * x, ankle[1] + y) for x, y in
                          ((-14, -8), (14, -8), (18, 14), (30, 22), (32, 34), (-16, 36), (-18, 14))])
            fill(g, shoe, QColor(o["shoes"]), 1.8)
            sole = QPainterPath(P(ankle[0] - side * 16, ankle[1] + 32))
            sole.lineTo(P(ankle[0] + side * 31, ankle[1] + 32))
            stroke(g, sole, QColor(o["shoe_trim"]), 4)

    def _lower(self, g, o):
        main = QColor(o["low"])
        if o["bottom"] == "skirt":
            sw = math.sin(self.t * 1.6) * 2
            skirt = poly((90, 412), (210, 412), (234 + sw, 532), (66 + sw, 532))
            fill(g, skirt, vgrad(412, 526, main, mix(main, INK, 0.5)))
            for x in (108, 129, 150, 171, 192):  # pleats
                pleat = QPainterPath(P(x, 418))
                pleat.lineTo(P(x + (x - 150) * 0.32 + sw, 530))
                stroke(g, pleat, alpha(INK, 0.6), 1.3)
            hem = QPainterPath(P(68 + sw, 524))
            hem.lineTo(P(232 + sw, 524))
            stroke(g, hem, QColor(o["trim"]), 4)
        elif o["bottom"] == "shorts":
            for side in (-1, 1):
                fill(g, poly(*([(92, 420), (150, 420), (150, 476), (82, 498)] if side < 0 else
                              mirror([(92, 420), (150, 420), (150, 476), (82, 498)]))), main, 1.8)
        elif o["bottom"] in ("hakama", "robe"):  # down to the ankles: wide pleated trousers, or a yukata's straight robe
            sw = math.sin(self.t * 1.3) * 2
            wide = o["bottom"] == "hakama"
            x0, x1 = (52, 248) if wide else (100, 200)
            long = poly((94, 372), (206, 372), (x1 + sw, 912), (x0 + sw, 912))
            fill(g, long, vgrad(372, 912, main, mix(main, INK, 0.4)))
            if wide:
                for x in (112, 132, 150, 168, 188):  # pleats
                    pleat = QPainterPath(P(x, 392))
                    pleat.lineTo(P(x + (x - 150) * 0.9 + sw, 908))
                    stroke(g, pleat, alpha(INK, 0.45), 1.4)
            else:
                fold = QPainterPath(P(162, 392))  # where the robe overlaps itself
                fold.lineTo(P(178 + sw, 910))
                stroke(g, fold, alpha(INK, 0.55), 1.6)
                self._pattern(g, o, long, 400, 900)
            hem = QPainterPath(P(x0 + sw, 908))
            hem.lineTo(P(x1 + sw, 908))
            stroke(g, hem, mix(main, INK, 0.5), 3)

    def _pattern(self, g, o, shape, y0, y1):
        """Little five-petal flowers scattered over a piece of clothing (yukata, sweetheart dress)."""
        if not o.get("pattern"):
            return
        g.save()
        g.setClipPath(shape)
        color = QColor(o["pattern"])
        for i in range(int((y1 - y0) / 34) * 3):
            cx, cy = 60 + (i * 67) % 180, y0 + (i * 37) % (y1 - y0)
            g.setPen(Qt.NoPen)
            g.setBrush(QBrush(alpha(color, 0.85)))
            for k in range(5):
                a = k * 2 * math.pi / 5
                g.drawEllipse(P(cx + math.cos(a) * 4.2, cy + math.sin(a) * 4.2), 3.2, 3.2)
            g.setBrush(QBrush(QColor("#ffe28a")))
            g.drawEllipse(P(cx, cy), 1.8, 1.8)
        g.restore()

    def _top(self, g, o):
        main, trim, accent = QColor(o["main"]), QColor(o["trim"]), QColor(o["accent"])
        dark = mix(main, INK, 0.45 if main.lightness() < 128 else 0.15)  # light fabric would turn grey with dark shading
        style = o["top"]
        if style == "dress":  # bodice and a flared lace skirt
            sw = math.sin(self.t * 1.5) * 3
            skirt = QPainterPath(P(104, 380))
            skirt.lineTo(P(196, 380))
            skirt.quadTo(P(236, 470), P(246 + sw, 566))
            for i in range(9):  # scalloped lace hem
                x = 246 - (i + 1) * 192 / 9 + sw
                skirt.quadTo(P(x + 192 / 18, 584), P(x, 566))
            skirt.quadTo(P(64, 470), P(104, 380))
            fill(g, skirt, vgrad(378, 580, main, dark))
            self._pattern(g, o, skirt, 386, 580)
            lace = QPainterPath(P(54 + sw, 566))
            lace.lineTo(P(246 + sw, 566))
            stroke(g, lace, trim, 5)
        hem_y = {"hoodie": 476, "jersey": 446, "dress": 386, "kimono": 384}.get(style, 432)
        wide = 12 if style == "hoodie" else 0
        body = QPainterPath(P(150, 226))
        body.lineTo(P(214 + wide, 236))
        body.quadTo(P(228 + wide, 252), P(224 + wide, 294))
        body.quadTo(P(218 + wide * 0.4, 344), P(196 + wide, 384))  # waist
        body.quadTo(P(212 + wide, 412), P(212 + wide, hem_y))  # hips
        body.lineTo(P(88 - wide, hem_y))
        body.quadTo(P(88 - wide, 412), P(104 - wide, 384))
        body.quadTo(P(82 - wide * 0.4, 344), P(76 - wide, 294))
        body.quadTo(P(72 - wide, 252), P(86 - wide, 236))
        body.closeSubpath()
        fill(g, body, vgrad(226, hem_y, main, dark))
        g.save()
        g.setClipPath(body)
        fill(g, poly((150, 220), (240, 220), (240, hem_y + 10), (158, hem_y + 10)), alpha(INK, 0.18), 0)  # cel shadow
        if style == "jacket":
            fill(g, poly((136, 232), (164, 232), (156, 360), (144, 360)), WHITE, 1.4)  # top under the open jacket
            for side in (-1, 1):  # cyan side panels and pink zip edges
                fill(g, poly(*([(82, 300), (102, 296), (106, 430), (90, 430)] if side < 0 else
                              mirror([(82, 300), (102, 296), (106, 430), (90, 430)]))), alpha(accent, 0.85), 0)
                edge = QPainterPath(P(150 + side * 14, 234))
                edge.lineTo(P(150 + side * 6, 432))
                stroke(g, edge, trim, 3.5)
            fill(g, poly((86, 420), (214, 420), (214, 432), (86, 432)), trim, 0)  # hem band
            fill(g, heart(118, 292, 7), trim, 1.2)  # logo patch
        elif style == "hoodie":
            pocket = QPainterPath()
            pocket.addRoundedRect(112, 404, 76, 46, 12, 12)
            fill(g, pocket, mix(main, INK, 0.12), 1.6)
            for x in (142, 158):  # drawstrings
                cord = QPainterPath(P(x, 236))
                cord.lineTo(P(x + (x - 150) * 0.3, 312))
                stroke(g, cord, accent, 2.4)
                g.setBrush(QBrush(trim))
                g.drawEllipse(P(x + (x - 150) * 0.3, 314), 3.5, 3.5)
        elif style == "jersey":
            fill(g, poly((136, 228), (164, 228), (150, 262)), self.SKIN, 1.4)  # v-neck
            for side in (-1, 1):
                fill(g, poly(*([(82, 290), (96, 288), (102, 446), (90, 446)] if side < 0 else
                              mirror([(82, 290), (96, 288), (102, 446), (90, 446)]))), trim, 0)
            g.setPen(QColor(o["trim"]))
            g.setFont(QFont("Arial Black", 30, QFont.Black))
            g.drawText(QRectF(110, 300, 80, 50), Qt.AlignCenter, "01")
        elif style == "dress":
            fill(g, poly((120, 230), (180, 230), (172, 250), (128, 250)), trim, 1.2)  # lace collar
        elif style == "kimono":
            fill(g, poly((128, 226), (172, 226), (150, 306)), trim, 0)  # the under-collar showing in the V
            for a, b in (((122, 230), (166, 362)), ((178, 230), (148, 312))):  # crossed collar, left over right
                band = QPainterPath(P(*a))
                band.lineTo(P(*b))
                stroke(g, band, INK, 11)
                stroke(g, band, trim if main.lightness() < 160 else mix(trim, main, 0.2), 8)
        self._pattern(g, o, body, 232, hem_y)
        g.restore()
        if o.get("obi"):  # the sash at the waist, with a cord across it
            obi = QPainterPath()
            obi.addRoundedRect(84, 346, 132, 42, 6, 6)
            fill(g, obi, vgrad(346, 388, QColor(o["obi"]), mix(QColor(o["obi"]), INK, 0.35)), 1.8)
            cord = QPainterPath(P(86, 368))
            cord.lineTo(P(214, 368))
            stroke(g, cord, accent if o["obi"] != o["accent"] else trim, 3)
        if o.get("apron"):  # maid: a frilled bib and a waist apron
            bib = poly((126, 252), (174, 252), (178, 340), (122, 340))
            fill(g, bib, WHITE, 1.6)
            front = QPainterPath(P(106, 390))
            front.lineTo(P(194, 390))
            front.lineTo(P(206, 528))
            for i in range(6):  # scalloped hem
                x = 206 - (i + 1) * 112 / 6
                front.quadTo(P(x + 112 / 12, 544), P(x, 528))
            front.closeSubpath()
            fill(g, front, WHITE, 1.6)
            stroke(g, poly((104, 380), (196, 380), (196, 392), (104, 392)), INK, 1.2)
            fill(g, poly((104, 380), (196, 380), (196, 392), (104, 392)), WHITE, 0)  # the apron strings at her waist
        if o.get("chest_bow"):  # magical girl: a big bow with tails, a gem in the knot
            for side in (-1, 1):
                fill(g, poly((150, 262), (150 + side * 36, 242), (150 + side * 40, 262), (150 + side * 34, 286)), accent, 1.6)
                fill(g, poly((150 + side * 3, 268), (150 + side * 16, 318), (150 + side * 6, 312), (150, 272)), accent, 1.4)
            gem = QPainterPath()
            gem.addEllipse(P(150, 263), 8, 8)
            fill(g, gem, vgrad(255, 271, WHITE, trim if trim != WHITE else QColor("#ff4f8b")), 1.6)
        elif style == "dress":
            for side in (-1, 1):  # red ribbon bow at the collar
                fill(g, poly((150, 240), (150 + side * 18, 230), (150 + side * 18, 252)), accent, 1.4)
            g.setBrush(QBrush(accent))
            g.drawEllipse(P(150, 241), 5, 5)
        if self.tier >= 2:  # a gold heart pin
            fill(g, heart(184, 300, 7), GOLD, 1.2)
        if self.d["blood"] > 0.02:
            fill(g, body, alpha(DARK, 0.25 * self.d["blood"]), 0)

    def _arms(self, g):
        o = self.OUTFITS[self.outfit]
        pose = self.pose()
        near = 1 if self.toward > 0 else -1
        arm = self.arm_points()
        sleeve, cuff = QColor(o["main"]), QColor(o["trim"])
        short = o["top"] == "jersey"
        for side in (-near, near):  # gesturing arm in front
            shoulder, elbow, wrist, dx, dy = arm[side]
            g.save()
            g.translate(*wrist)
            g.rotate(math.degrees(math.atan2(-dx, dy)))
            g.scale(self.HAND, self.HAND)
            self._hand(g, pose[side][2], side)
            g.restore()
            wide = o.get("sleeves") == "wide"  # kimono sleeves: loose and hanging below the arm
            if wide:
                fill(g, poly((elbow[0] - 14, elbow[1]), (wrist[0] - 14, wrist[1]), (wrist[0] - 4, wrist[1] + 44),
                             (elbow[0] + 4, elbow[1] + 30)), vgrad(elbow[1], wrist[1] + 44, sleeve, mix(sleeve, INK, 0.3)), 1.6)
            self._limb(g, elbow, wrist, 24 if wide else 16, 21 if wide else 12.5, self.SKIN if short else sleeve,
                       self.SKIN_SH if short else INK, width=1.8)
            self._limb(g, shoulder, elbow, 24 if wide else 22 if o["top"] == "hoodie" else 20, 22 if wide else 16, sleeve, INK, width=1.8)
            if o.get("sleeves") == "puff":  # puffed shoulders
                puff = QPainterPath()
                puff.addEllipse(P(shoulder[0] + side * 4, shoulder[1] + 10), 25, 21)
                fill(g, puff, vgrad(shoulder[1] - 10, shoulder[1] + 32, sleeve, mix(sleeve, INK, 0.3)), 1.6)
                rim = QPainterPath(P(shoulder[0] - 20 + side * 4, shoulder[1] + 26))
                rim.quadTo(P(shoulder[0] + side * 4, shoulder[1] + 36), P(shoulder[0] + 20 + side * 4, shoulder[1] + 26))
                stroke(g, rim, cuff, 3)
            if not short:
                band = QPainterPath(P(wrist[0] - dy * 14 - dx * 6, wrist[1] + dx * 14 - dy * 6))
                band.lineTo(P(wrist[0] + dy * 14 - dx * 6, wrist[1] - dx * 14 - dy * 6))
                stroke(g, band, cuff, 4)

    def _hand(self, g, kind, side):
        """A small hand at the wrist, fingers toward local +y."""
        if kind == "open":
            for i, ang in enumerate((-14, -4, 6, 16)):
                r = math.radians(ang)
                base = (-7 + i * 4.6, 12)
                self._limb(g, base, (base[0] - math.sin(r) * 13, base[1] + math.cos(r) * 13), 2.6, 2.2, self.SKIN, width=1.2)
            self._limb(g, (side * 7, 4), (side * 16, 13), 2.8, 2.4, self.SKIN, width=1.2)
            palm = QPainterPath()
            palm.addRoundedRect(-9, -2, 18, 16, 5, 5)
            fill(g, palm, self.SKIN, 1.3)
            return
        if kind == "point":
            self._limb(g, (side * 3, 12), (side * 3, 30), 2.8, 2.4, self.SKIN, width=1.2)
        fist = QPainterPath()
        fist.addRoundedRect(-9, -2, 18, 18, 6, 6)
        fill(g, fist, self.SKIN, 1.3)
        for x in (-4, 0, 4):
            k = QPainterPath(P(x, 11))
            k.lineTo(P(x, 15))
            stroke(g, k, alpha(self.SKIN_SH, 0.9), 1)

    def _neck(self, g, o):
        fill(g, poly((138, 186), (162, 186), (165, 228), (135, 228)), self.SKIN, 1.6)
        fill(g, poly((140, 186), (160, 186), (160, 204), (140, 198)), self.SKIN_SH, 0)
        if o["top"] == "jacket":  # high collar
            for side in (-1, 1):
                fill(g, poly(*([(124, 222), (142, 214), (146, 240), (128, 244)] if side < 0 else
                              mirror([(124, 222), (142, 214), (146, 240), (128, 244)]))), QColor(o["main"]), 1.6)
        elif o["top"] == "hoodie":  # the hood bunched behind her neck
            hood = QPainterPath(P(112, 232))
            hood.quadTo(P(150, 206), P(188, 232))
            hood.quadTo(P(150, 246), P(112, 232))
            fill(g, hood, mix(QColor(o["main"]), INK, 0.15), 1.6)

    def _head(self, g):
        p, b = self.d, self.d["blood"]
        face = QPainterPath(P(104, 100))
        face.cubicTo(P(102, 140), P(108, 165), P(122, 182))
        face.quadTo(P(138, 198), P(150, 200))
        face.quadTo(P(162, 198), P(178, 182))
        face.cubicTo(P(192, 165), P(198, 140), P(196, 100))
        face.cubicTo(P(194, 52), P(106, 52), P(104, 100))
        fill(g, face, self.SKIN, 1.8)
        g.save()
        g.setClipPath(face)
        fill(g, poly((176, 90), (204, 90), (204, 210), (150, 210), (172, 186), (186, 160), (190, 120)), alpha(self.SKIN_SH, 0.7), 0)
        blush = max(0.25, 0.35 + 0.4 * max(p["smile"], 0) + 0.3 * p["happy"] - 0.3 * p["vein"]) + 0.3 * b
        for x in (122, 178):
            g.setPen(Qt.NoPen)
            g.setBrush(QBrush(alpha(BLUSH, 0.5 * blush)))
            g.drawEllipse(P(x, 160), 11, 5)
        if b > 0.02:  # Lovesick: a shadow falls over her eyes
            fill(g, poly((96, 60), (204, 60), (204, 168), (96, 168)), vgrad(70, 168, alpha(DARK, 0.7 * b), alpha(DARK, 0)), 0)
        g.restore()

        for cx, side in ((128, -1), (172, 1)):
            self._eye(g, cx, 140, side)
        nose = QPainterPath(P(151, 156))
        nose.lineTo(P(149, 162))
        stroke(g, nose, alpha(self.SKIN_SH, 1), 1.6)
        self._mouth(g)

        sw = math.sin(self.t * 1.7) * 1.5
        top = QPainterPath(P(96, 118))  # hair over the top of the head, with blunt bangs
        top.cubicTo(P(90, 46), P(210, 46), P(204, 118))
        for i, x in enumerate((196, 186, 175, 163, 150, 137, 125, 114, 104)):
            top.lineTo(P(x + sw * 0.5, (124 if i % 2 == 0 else 110) + (6 if i in (3, 4, 5) else 0)))
        top.closeSubpath()
        fill(g, top, vgrad(40, 124, self.HAIR_HI, self.HAIR))
        for side in (-1, 1):  # side locks framing her face, down to her chest
            m = (lambda pts: pts) if side < 0 else mirror
            lock = poly(*m([(98, 104), (110, 112), (112, 200), (106, 270 + sw), (98, 330 + sw), (90, 262), (88, 170)]))
            fill(g, lock, vgrad(100, 330, self.HAIR, self.HAIR_SH))
        shine = QPainterPath(P(118, 66))
        shine.quadTo(P(150, 54), P(182, 66))
        stroke(g, shine, alpha(QColor("white"), 0.7), 3)
        if b > 0.02:
            fill(g, top, alpha(QColor("#3a0014"), 0.3 * b), 0)
        for side in (-1, 1):
            self._brow(g, 150 + side * 22, 140, side)
        self._headset(g)
        self._headpiece(g, self.OUTFITS[self.outfit])
        if p["vein"] > 0.05:  # anime anger mark
            c = alpha(QColor("#e0263a"), p["vein"])
            for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                v = QPainterPath(P(186 + dx * 3, 94 + dy * 7))
                v.quadTo(P(186 + dx * 3, 94 + dy * 3), P(186 + dx * 7, 94 + dy * 3))
                stroke(g, v, c, 2.4)

    def _headpiece(self, g, o):
        """What some outfits add on her head, in front of the headset: a maid's frill, a bow, or a flower."""
        kind = o.get("head")
        if kind == "maid":
            band = QPainterPath(P(102, 96))
            band.cubicTo(P(100, 52), P(200, 52), P(198, 96))
            stroke(g, band, INK, 12)
            stroke(g, band, WHITE, 9)
            for i in range(9):  # the frill along it
                u = i / 8
                x, y = 104 + 92 * u, 92 - 34 * math.sin(math.pi * u)
                frill = QPainterPath()
                frill.addEllipse(P(x, y - 6), 7, 6)
                fill(g, frill, WHITE, 1.3)
        elif kind == "bow":  # on the side of her head, by the cat ear
            c, accent = (194, 76), QColor(o["accent"] if o["top"] != "kimono" else o["trim"])
            for side in (-1, 1):
                fill(g, poly(c, (c[0] + side * 22, c[1] - 14), (c[0] + side * 24, c[1] + 12)), accent, 1.6)
            knot = QPainterPath()
            knot.addEllipse(P(*c), 5.5, 5.5)
            fill(g, knot, mix(accent, INK, 0.2), 1.4)
        elif kind == "flower":  # a big flower clip above her ear
            cx, cy, petal = 102, 98, QColor(o["accent"])
            for k in range(5):
                a = k * 2 * math.pi / 5 - math.pi / 2
                leaf = QPainterPath()
                leaf.addEllipse(P(cx + math.cos(a) * 9, cy + math.sin(a) * 9), 8, 8)
                fill(g, leaf, petal, 1.4)
            center = QPainterPath()
            center.addEllipse(P(cx, cy), 5, 5)
            fill(g, center, QColor("#ffe28a"), 1.2)

    def _headset(self, g):
        led = mix(self.LED, CYAN, 0.0) if self.tier < 1 else mix(self.LED, QColor("white"), 0.25)
        b = self.d["blood"]
        led = mix(led, QColor("#ff1030"), b)
        band = QPainterPath(P(92, 126))
        band.cubicTo(P(84, 30), P(216, 30), P(208, 126))
        stroke(g, band, INK, 11)
        stroke(g, band, SET, 8)
        for side in (-1, 1):  # cat ears on the band, glowing inside
            m = (lambda pts: pts) if side < 0 else mirror
            ear = poly(*m([(110, 62), (104, 30), (130, 50)]))
            fill(g, ear, SET, 1.8)
            fill(g, poly(*m([(112, 56), (108, 38), (124, 51)])), alpha(led, 0.9), 0)
        mic = QPainterPath(P(94, 150))
        mic.quadTo(P(100, 186), P(124, 184))
        stroke(g, mic, INK, 5)
        stroke(g, mic, SET_HI, 3)
        g.setBrush(QBrush(SET))
        g.setPen(pen(INK, 1.4))
        g.drawEllipse(P(126, 184), 4.5, 3.5)
        for side in (-1, 1):  # ear cups with LED rings
            cx = 150 + side * 58
            cup = QPainterPath()
            cup.addEllipse(P(cx, 132), 16, 24)
            fill(g, cup, vgrad(108, 156, SET_HI, SET), 2)
            ring = QPainterPath()
            ring.addEllipse(P(cx + side * 2, 132), 10, 17)
            stroke(g, ring, alpha(led, 0.9 + 0.1 * math.sin(self.t * 3)), 2.6)

    def _eye(self, g, cx, cy, side):
        p, b = self.d, self.d["blood"]
        if p["happy"] > 0.5:  # ^ ^
            arc = QPainterPath(P(cx - 12, cy + 3))
            arc.quadTo(P(cx, cy - 8), P(cx + 12, cy + 3))
            stroke(g, arc, INK, 3.2)
            return
        h = 14 * max(0.0, p["open"]) * abs(1 - 2 * self.blink)
        top_y = cy - 1.25 * h
        eye = QPainterPath(P(cx - 14, cy + 1))
        eye.cubicTo(P(cx - 12, top_y), P(cx + 12, top_y), P(cx + 15, cy - 1))
        eye.cubicTo(P(cx + 12, cy + 1.05 * h), P(cx - 12, cy + 1.05 * h), P(cx - 14, cy + 1))
        if h > 0.6:
            g.setPen(Qt.NoPen)
            g.setBrush(QBrush(QColor("white")))
            g.drawPath(eye)
            g.save()
            g.setClipPath(eye)
            ix, iy = cx + (p["look"] + self.glance) * 4 + p["roll_x"] * 0.7, cy + 1 + p["roll_y"] * 0.7
            iris = QRadialGradient(P(ix, iy - 3), 13)
            iris.setColorAt(0, mix(self.IRIS, QColor("#7a0026"), b))
            iris.setColorAt(1, mix(self.IRIS_SH, QColor("#1a0008"), b))
            g.setBrush(QBrush(iris))
            g.setPen(pen(INK, 1.1))
            g.drawEllipse(P(ix, iy), 10.5, 13.5)
            g.setPen(Qt.NoPen)
            g.setBrush(QBrush(self.PUPIL))
            g.drawEllipse(P(ix, iy + 1), 4 * p["pupil"] * (1 - 0.5 * b), 6 * p["pupil"] * (1 - 0.5 * b))
            if b < 0.6:  # the light in her eyes (gone in Lovesick)
                g.setBrush(QBrush(alpha(QColor("white"), 1 - b)))
                g.drawEllipse(P(ix - 3.5, iy - 5), 3.4, 3.8)
                g.drawEllipse(P(ix + 3, iy + 5), 1.6, 1.6)
            else:
                ring = QPainterPath()
                ring.addEllipse(P(ix, iy), 6.5, 8)
                stroke(g, ring, alpha(QColor("#ff2a55"), b), 1.2)
            g.restore()
        lash = QPainterPath(P(cx - 15, cy + 2))
        lash.cubicTo(P(cx - 12, top_y - 1), P(cx + 12, top_y - 1), P(cx + 16, cy - 2))
        stroke(g, lash, INK, 3.4)
        wing = QPainterPath(P(cx + side * 15, cy + (-2 if side > 0 else 2)))  # a little flick at the outer corner
        wing.lineTo(P(cx + side * 21, cy - 5))
        stroke(g, wing, INK, 2.6)
        low = QPainterPath(P(cx - 9, cy + 1.05 * h - 1))
        low.quadTo(P(cx, cy + 1.15 * h), P(cx + 10, cy + 1.0 * h - 1))
        stroke(g, low, alpha(INK, 0.55), 1.1)

    def _brow(self, g, cx, cy, side):
        p = self.d
        lift = p["lift"] + (p["lift_r"] if side > 0 else 0)
        by = cy - 24 - lift * 6
        inner, outer = (cx - side * 10, by + p["brow"] * 4), (cx + side * 13, by - 2 - p["brow"] * 1.2)
        brow = QPainterPath(P(*inner))
        brow.quadTo(P(cx, by - 3), P(*outer))
        stroke(g, brow, self.HAIR_DEEP, 2.4)

    def _mouth(self, g):
        p, b = self.d, self.d["blood"]
        cx, cy = 150, 178
        open_ = max(p["mouth"], self.lips[0] * 0.85)
        wide, rnd = self.lips[1], max(0.0, -self.lips[1])  # lip-sync: wider on "ee", a little O on "oo"
        smile = min(1.0, p["smile"] + 0.8 * b)  # Lovesick: a too-wide smile
        w = (8 + 4 * max(smile, 0) + 2 * open_ + 3 * max(wide, 0) + 6 * b) * (1 - 0.4 * rnd)
        left, right = P(cx - w, cy - smile * 2.5 + max(-p["smirk"], 0) * 1.5), P(cx + w, cy - smile * 2.5 - p["smirk"] * 3)
        upper = P(cx, cy + smile * 3.5 - open_ * 1.5 - rnd * open_ * 6)
        if open_ < 0.06 and b < 0.3:
            m = QPainterPath(left)
            m.quadTo(upper, right)
            stroke(g, m, INK, 2)
            return
        lower = P(cx, cy + 2 + open_ * 13 + max(smile, 0) * 4)
        m = QPainterPath(left)
        m.quadTo(upper, right)
        m.quadTo(lower, left)
        fill(g, m, QColor("#7a1e3a"), 1.8)
        g.save()
        g.setClipPath(m)
        g.setPen(Qt.NoPen)
        g.setBrush(QBrush(QColor("#ff7f9e")))
        g.drawEllipse(P(cx, cy + 5 + open_ * 7), w * 0.55, 4)
        if smile > 0.4 or p["teeth"] > 0.5 or self.lips[2] > 0.5:
            g.setBrush(QBrush(QColor("white")))
            g.drawRect(QRectF(cx - w, min(left.y(), right.y()) - 4, 2 * w, upper.y() - min(left.y(), right.y()) + 5))
        g.restore()
