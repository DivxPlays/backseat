"""Discord camera: the current character (or Vorn and Mika together) as a virtual webcam, with subtitles and a background.

Frames go to OBS's virtual camera through pyvirtualcam; pick "OBS Virtual Camera" in Discord's video settings.
Drawn in its own thread at 1280x720, 15 fps (7.5 while nobody talks or moves: each frame is sent twice), from the same
animated character the overlay shows.
"""
import logging
import threading
import time

import mss
import numpy as np
from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QLinearGradient, QPainter, QPainterPath

import config
import character
from character import H, W, make_character

CAM_W, CAM_H, FPS = 1280, 720, 15  # (a frame is ~11 ms of drawing: at 15 fps about a sixth of a CPU core, half that idle)
BACKGROUNDS = ("dark", "green", "game", "webcam")
# the face the one listening makes: never the speaker's own, so the two never look like copies
REACT = {"laugh": "smug", "angry": "surprised", "smug": "disgusted", "surprised": "laugh", "disgusted": "smug", "idle": "idle"}


def middle(mon, w, h):
    """The w:h part from the middle of a display (an ultrawide game screen loses its sides, not its height): only that
    part is grabbed (a 5120x1440 screen: half of it, ~60 ms down to ~20 per grab)."""
    mw, mh = mon["width"], mon["height"]
    cw, ch = (int(mh * w / h), mh) if mw / mh > w / h else (mw, int(mw * h / w))
    return {"left": mon["left"] + (mw - cw) // 2, "top": mon["top"] + (mh - ch) // 2, "width": cw, "height": ch}


def shrink(img, w, h):
    """Scale to w x h, fast: halve it first while it's at least twice the size."""
    k = min(img.width // w, img.height // h)
    return (img.reduce(k) if k > 1 else img).resize((w, h), Image.BILINEAR)


class Camera:
    def __init__(self, overlay, focus):
        self.overlay, self.focus = overlay, focus  # focus(): a point on the display the game is on
        self.other = None
        self.background = None  # the latest game screen or webcam picture (QImage)
        self.running = False
        self.webcam = None
        self.error = ""

    def start(self):
        """Start sending frames (call on the Qt thread: the webcam has to be opened there)."""
        if self.running or config.CAMERA == "off":
            return
        duo = len(getattr(self.overlay, "chars", [])) > 1  # duo mode: both are already animated by the overlay
        self.other = make_character("mika" if config.CHARACTER == "vorn" else "vorn") if config.CAMERA == "both" and not duo else None
        if config.CAMERA_BACKGROUND == "webcam":
            self.open_webcam()
        self.running = True
        threading.Thread(target=self.run, daemon=True).start()

    def stop(self):
        self.running = False
        if self.webcam:
            self.webcam[0].stop()
            self.webcam = None

    def open_webcam(self):
        from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices, QVideoSink
        real = [d for d in QMediaDevices.videoInputs() if not any(w in d.description().lower() for w in ("virtual", "obs"))]
        want = config.CAMERA_WEBCAM.lower()
        device = next((d for d in real if want and want in d.description().lower()), real[0] if real else None)
        if device is None:
            self.error = "no real webcam found"
            return
        cam, session, sink = QCamera(device), QMediaCaptureSession(), QVideoSink()
        session.setCamera(cam)
        session.setVideoSink(sink)
        sink.videoFrameChanged.connect(lambda frame: setattr(self, "background", frame.toImage()))
        cam.start()
        self.webcam = (cam, session, sink)  # keep them alive

    def game_screen(self):
        x, y = self.focus()
        with mss.MSS() as s:
            mon = next((m for m in s.monitors[1:] if m["left"] <= x < m["left"] + m["width"] and m["top"] <= y < m["top"] + m["height"]),
                       s.monitors[1])
            shot = s.grab(middle(mon, CAM_W, CAM_H))
        img = shrink(Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX"), CAM_W, CAM_H)
        return QImage(img.tobytes(), CAM_W, CAM_H, CAM_W * 3, QImage.Format_RGB888).copy()

    def run(self):
        try:
            import pyvirtualcam
            with pyvirtualcam.Camera(CAM_W, CAM_H, FPS, backend="obs") as cam:
                self.error = ""
                last_bg, last, n, frame = 0.0, time.monotonic(), 0, None
                while self.running:
                    now = time.monotonic()
                    if config.CAMERA_BACKGROUND == "game" and now - last_bg > 0.5:
                        last_bg, self.background = now, self.game_screen()
                    if self.other:
                        self.other.step(now - last, 0.0)
                    last, n = now, n + 1
                    if frame is None or n % 2 or self.lively():  # quiet: every other frame is the last one again
                        frame = self.frame()
                    cam.send(frame)
                    cam.sleep_until_next_frame()
        except Exception as e:  # no OBS, camera busy, ...
            self.error = str(e)
            self.running = False
            logging.warning("Discord camera stopped: %s", e)

    def lively(self):
        """True while someone talks (subtitles up), is thrown, blinks, burns or plays an idle animation, or holiday weather
        falls: then every frame is drawn (breathing and a resting face look the same at half the rate)."""
        chars = getattr(self.overlay, "chars", [self.overlay.char]) + ([self.other] if self.other else [])
        return bool(self.overlay.text or character.WEATHER) or any(
            c.talk > 0.03 or c.rag > 0.05 or c.act or c.blink > 0 or c.blood > 0.05 for c in chars)

    def frame(self):
        img = QImage(CAM_W, CAM_H, QImage.Format_RGB888)
        g = QPainter(img)
        g.setRenderHint(QPainter.Antialiasing)
        self.paint(g)
        g.end()
        rows = np.frombuffer(img.constBits(), np.uint8).reshape(CAM_H, img.bytesPerLine())
        return rows[:, :CAM_W * 3].reshape(CAM_H, CAM_W, 3).copy()  # copy: img's memory is freed when we return

    def paint(self, g):
        bg = config.CAMERA_BACKGROUND
        if bg == "green":
            g.fillRect(0, 0, CAM_W, CAM_H, QColor("#00b140"))
        elif bg in ("game", "webcam") and self.background is not None:
            g.drawImage(QRectF(0, 0, CAM_W, CAM_H), self.background)
        else:
            grad = QLinearGradient(0, 0, 0, CAM_H)
            grad.setColorAt(0, QColor("#24202c"))
            grad.setColorAt(1, QColor("#0e0c12"))
            g.fillRect(0, 0, CAM_W, CAM_H, grad)
        main = self.overlay.char
        scale = (CAM_H - 10) / H
        chars = getattr(self.overlay, "chars", [main])
        if len(chars) > 1:  # duo mode: both, each moving their own mouth
            self.draw_char(g, chars[1], CAM_W - 40 - W * scale, scale)
            main_x = 40
        elif self.other:  # both: the talker on the left, the other on the right reacting
            mood = REACT.get(main.mood, "idle")
            if self.other.mood != mood:
                self.other.set_mood(mood)
            main_x, other_x = 40, CAM_W - 40 - W * scale
            self.other.toward = -1.0  # looks toward the talker
            self.draw_char(g, self.other, other_x, scale)
        else:
            main_x = (CAM_W - W * scale) / 2 if bg in ("dark", "green") else CAM_W - 40 - W * scale
        self.draw_char(g, main, main_x, scale)
        self.subtitles(g)

    def draw_char(self, g, char, x, scale):
        g.save()
        g.translate(x, CAM_H - H * scale)
        g.scale(scale, scale)
        char.paint(g)
        g.restore()

    def subtitles(self, g):
        text = self.overlay.text[: int(self.overlay.shown)]
        if not text:
            return
        font = QFont("Segoe UI", 22, QFont.DemiBold)
        g.setFont(font)
        line = text if len(getattr(self.overlay, "chars", [])) > 1 else f"{config.NAME}: {text}"  # duo text names the speaker
        r = QFontMetrics(font).boundingRect(0, 0, CAM_W - 160, 400, Qt.TextWordWrap, line)
        box = QRectF((CAM_W - r.width()) / 2 - 20, CAM_H - r.height() - 50, r.width() + 40, r.height() + 24)
        path = QPainterPath()
        path.addRoundedRect(box, 14, 14)
        g.fillPath(path, QColor(0, 0, 0, 170))
        g.setPen(QColor("white"))
        g.drawText(box.adjusted(20, 12, -20, -12), Qt.TextWordWrap | Qt.AlignHCenter, line)
