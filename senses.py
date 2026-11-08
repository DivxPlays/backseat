"""Eyes (screen capture), ears (push-to-talk speech-to-text), voice (neural TTS with lip-sync levels)."""
import asyncio
import base64
import io
import logging
import os
import queue
import re
import textwrap
import threading
import time
import wave
import winsound
from datetime import datetime

import edge_tts
import miniaudio
import mss
import numpy as np
import sounddevice as sd
from PIL import Image, ImageDraw, ImageFont

import config

SR = 24000  # voice sample rate


def _chime(freqs, note=0.09, sr=22050):
    """Tiny WAV of notes played back to back, with 10 ms fades so it doesn't click."""
    t = np.arange(int(sr * note)) / sr
    env = np.minimum(1, np.minimum(t, note - t) / 0.01)
    pcm = np.concatenate([np.sin(2 * np.pi * f * t) * env for f in freqs]) * 0.3
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((pcm * 32767).astype("<i2").tobytes())
    return buf.getvalue()


CUES = {"off": _chime([660, 440]), "on": _chime([440, 660])}  # falling = stopped looking, rising = looking again


def cue(name):
    """Play a cue through Windows' own player, so it never cuts off his voice."""
    threading.Thread(target=winsound.PlaySound, args=(CUES[name], winsound.SND_MEMORY), daemon=True).start()


def thumbnail(img):
    return np.asarray(img.convert("L").resize((64, 36)), dtype=np.float32)


def changed(a, b, threshold):
    # shape differs = a display was (un)plugged; size 0 = every display is skipped
    return a.shape != b.shape or (a.size > 0 and float(np.abs(a - b).mean()) > threshold)


def strip(imgs):
    """Side-by-side thumbnails of every watched display (empty if he watches none)."""
    return np.concatenate([thumbnail(img) for img in imgs], axis=1) if imgs else np.zeros((36, 0), np.float32)


class Eyes:
    def __init__(self):
        self.skip = set()  # top-left corners of displays to ignore; main.py fills this from SKIP_DISPLAYS

    def grab(self):
        """(display, image) for each watched display, left to right."""
        with mss.MSS() as s:
            if config.MONITOR == "all":
                mons = sorted(s.monitors[1:], key=lambda m: (m["left"], m["top"]))
            else:
                mons = [s.monitors[min(int(config.MONITOR), len(s.monitors) - 1)]]
            mons = [m for m in mons if (m["left"], m["top"]) not in self.skip]
            shots = [s.grab(m) for m in mons]
        return [(m, Image.frombytes("RGB", x.size, x.bgra, "raw", "BGRX")) for m, x in zip(mons, shots)]

    def thumb(self):
        return strip([img for _, img in self.grab()])

    def look(self):
        """(thumbnail strip for change detection, one JPEG base64 per display for Claude, the raw (display, image) pairs)."""
        pairs, jpegs = self.grab(), []
        imgs = [img for _, img in pairs]
        for img in imgs:
            small = img.copy()
            small.thumbnail((1568, 1568))  # Claude's max useful edge; keeps HUD text readable on ultrawides
            buf = io.BytesIO()
            small.save(buf, "JPEG", quality=70)
            jpegs.append(base64.standard_b64encode(buf.getvalue()).decode())
        return strip(imgs), jpegs, pairs


def game_display(pairs, point):
    """Index of the display that point (the middle of the game window) is on; the first display if none."""
    x, y = point
    return next((i for i, (m, _) in enumerate(pairs)
                 if m["left"] <= x < m["left"] + m["width"] and m["top"] <= y < m["top"] + m["height"]), 0)


def save_clip(path, audio):
    """His voice line as a WAV next to the Hall of Shame screenshot."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())


class Ducker:
    """Lowers every other app's volume while he talks, then puts it back. Call from the UI thread (Windows audio is COM)."""

    def __init__(self):
        self.saved = []

    def duck(self):
        if config.DUCK_TO >= 1 or self.saved:
            return
        try:
            from pycaw.pycaw import AudioUtilities
            for s in AudioUtilities.GetAllSessions():
                if s.ProcessId and s.ProcessId != os.getpid():  # 0 = Windows system sounds
                    vol = s.SimpleAudioVolume
                    level = vol.GetMasterVolume()
                    self.saved.append((vol, level))
                    vol.SetMasterVolume(level * config.DUCK_TO, None)
        except Exception:
            logging.warning("could not lower other apps' volume", exc_info=True)

    def restore(self):
        # shortcut: if he crashes mid-sentence, those apps stay quieter until you raise them in the Volume Mixer
        for vol, level in self.saved:
            try:
                vol.SetMasterVolume(level, None)
            except Exception:
                pass  # that app closed while he was talking
        self.saved = []


def save_moment(pairs, point, caption, folder):
    """Hall of Shame: the display the game is on, with his caption burned in underneath. Returns the file path."""
    img = pairs[game_display(pairs, point)][1].copy()
    img.thumbnail((2560, 2560))
    w, h = img.size
    size = max(18, w // 60)
    try:
        font = ImageFont.truetype("segoeuib.ttf", size)
    except OSError:
        font = ImageFont.load_default(size)
    lines = textwrap.wrap(f'{config.NAME}: "{caption}"', max(20, int(w / (size * 0.55))))
    bar = int(size * 1.4 * len(lines) + size)
    out = Image.new("RGB", (w, h + bar), (27, 20, 24))
    out.paste(img, (0, 0))
    draw = ImageDraw.Draw(out)
    for i, text in enumerate(lines):
        draw.text((size, h + size // 2 + i * size * 1.4), text, font=font, fill=(242, 198, 77))
    folder.mkdir(exist_ok=True)
    path = folder / f"{datetime.now():%Y-%m-%d %H-%M-%S}.jpg"
    out.save(path, quality=90)
    return path


class Ears:
    def __init__(self):
        self._model = None
        self._lock = threading.Lock()
        self._frames = []
        self._stream = None
        self.recording = False

    def model(self):
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
            return self._model

    def start(self):
        self._frames = []
        self._stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32",
                                      callback=lambda data, *_: self._frames.append(data.copy()))
        self._stream.start()
        self.recording = True

    def stop(self):
        if not self.recording:
            return None
        self.recording = False
        self._stream.stop()
        self._stream.close()
        return np.concatenate(self._frames)[:, 0] if self._frames else np.zeros(0, np.float32)

    def transcribe(self, audio, prompt=None):
        if len(audio) < 16000 * 0.3:
            return ""
        segments, _ = self.model().transcribe(audio, language="en", beam_size=1, initial_prompt=prompt)
        return " ".join(s.text.strip() for s in segments).strip()


class WakeListener:
    """Always-on mic that waits for "Hey Vorn". Everything is transcribed on this PC; nothing is sent until he's called."""

    # Whisper often mishears an invented name, so accept the usual near-misses
    WAKE = re.compile(r"\b(?:hey|hay|hi|a|okay|ok)[\s,.!]+(?:vorn|vorne|vern|born|bourne|vaughn|vaughan|von|forn|fawn|warn|horn|bjorn)\b[\s,.!?]*", re.I)

    def __init__(self, ears, voice, on_heard):
        self.ears, self.voice, self.on_heard = ears, voice, on_heard
        self.q = queue.Queue()
        self.armed_until = 0.0  # after a bare "Hey Vorn", the next sentence is the question

    def run(self):
        with sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=1600,  # 0.1 s chunks
                            callback=lambda data, *_: self.q.put(data[:, 0].copy())):
            speech, silent = [], 0
            while True:
                chunk = self.q.get()
                if self.voice.busy() or self.ears.recording:  # ignore his own voice and push-to-talk
                    speech, silent = [], 0
                    continue
                loud = float(np.sqrt(np.mean(chunk * chunk))) > config.WAKE_LEVEL
                if loud or speech:
                    speech.append(chunk)
                    silent = 0 if loud else silent + 1
                if speech and (silent >= 7 or len(speech) >= 150):  # a 0.7 s pause (or 15 s) ends a sentence
                    audio = np.concatenate(speech)
                    speech, silent = [], 0
                    if len(audio) > 16000 * 0.5:
                        self.hear(self.ears.transcribe(audio, prompt=f"Hey {config.NAME}."))

    def hear(self, text):
        m = self.WAKE.search(text)
        if m:
            rest = text[m.end():].strip()
            self.armed_until = 0.0 if rest else time.monotonic() + 6
            self.on_heard(rest or None)  # None = he heard his name and is waiting for the question
        elif text and time.monotonic() < self.armed_until:
            self.armed_until = 0.0
            self.on_heard(text)


class Voice:
    def __init__(self):
        self._audio = None
        self._t0 = 0.0

    def synth(self, text, voice=None, rate=None, pitch=None):
        """Speech audio for text; voice/rate/pitch override the settings (the Settings window's Test button)."""
        async def fetch():
            out = bytearray()
            async for chunk in edge_tts.Communicate(text, voice or config.VOICE, rate=rate or config.VOICE_RATE,
                                                    pitch=pitch or config.VOICE_PITCH).stream():
                if chunk["type"] == "audio":
                    out += chunk["data"]
            return bytes(out)

        mp3 = asyncio.run(fetch())
        snd = miniaudio.decode(mp3, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1, sample_rate=SR)
        return np.frombuffer(snd.samples, dtype=np.float32).copy()

    def play(self, audio):
        """Start playing; returns the duration in seconds."""
        sd.stop()
        self._audio, self._t0 = audio, time.monotonic()
        sd.play(audio, SR)
        return len(audio) / SR

    def stop(self):
        sd.stop()
        self._audio = None

    def busy(self):
        return self._audio is not None and time.monotonic() - self._t0 < len(self._audio) / SR

    def level(self):
        """Loudness 0..1 at the current playback position (drives the mouth)."""
        if not self.busy():
            return 0.0
        i = int((time.monotonic() - self._t0) * SR)
        w = self._audio[i:i + 800]
        return float(min(1.0, np.sqrt(np.mean(w * w)) * 7)) if len(w) else 0.0
