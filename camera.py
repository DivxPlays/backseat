"""Discord camera: the current character (or Vorn and Mika together) as a virtual webcam, with subtitles and a background.

Frames go to OBS's virtual camera through pyvirtualcam; pick "OBS Virtual Camera" in Discord's video settings.
Drawn in its own thread at 1280x720, 15 fps, from the same animated character the overlay shows.
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
from character import H, W, make_character

CAM_W, CAM_H, FPS = 1280, 720, 15  # (each frame is ~23 ms of drawing: at 24 fps it took half a CPU core from your game)
BACKGROUNDS = ("dark", "green", "game", "webcam")
# the face the one listening makes: never the speaker's own, so the two never look like copies
REACT = {"laugh": "smug", "angry": "surprised", "smug": "disgusted", "surprised": "laugh", "disgusted": "smug", "idle": "idle"}


def fit(img, w, h):
    """Crop to the w:h shape from the middle, then scale (an ultrawide game screen loses its sides, not its height)."""
    iw, ih = img.size
    if iw / ih > w / h:
        cw = int(ih * w / h)
        img = img.crop(((iw - cw) // 2, 0, (iw - cw) // 2 + cw, ih))
    else:
        ch = int(iw * h / w)
        img = img.crop((0, (ih - ch) // 2, iw, (ih - ch) // 2 + ch))
    return img.resize((w, h))


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
            shot = s.grab(mon)
        img = fit(Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX"), CAM_W, CAM_H)
        return QImage(img.tobytes(), CAM_W, CAM_H, CAM_W * 3, QImage.Format_RGB888).copy()

    def run(self):
        try:
            import pyvirtualcam
            with pyvirtualcam.Camera(CAM_W, CAM_H, FPS, backend="obs") as cam:
                self.error = ""
                last_bg, last = 0.0, time.monotonic()
                while self.running:
                    now = time.monotonic()
                    if config.CAMERA_BACKGROUND == "game" and now - last_bg > 0.5:
                        last_bg, self.background = now, self.game_screen()
                    if self.other:
                        self.other.step(now - last, 0.0)
                    last = now
                    cam.send(self.frame())
                    cam.sleep_until_next_frame()
        except Exception as e:  # no OBS, camera busy, ...
            self.error = str(e)
            self.running = False
            logging.warning("Discord camera stopped: %s", e)

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
