"""Eyes (screen capture), ears (push-to-talk speech-to-text), voice (neural TTS with lip-sync levels)."""
import asyncio
import contextlib
import base64
import io
import logging
import os
import queue
import re
import textwrap
import threading
import time
import urllib.request
import wave
import winsound
from datetime import datetime
from pathlib import Path

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


OTHER_EDGE = 768  # displays without the game: about a quarter of the image cost, still readable enough to mock


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

    def look(self, point=None):
        """(thumbnail strip for change detection, one JPEG base64 per display for Claude, the raw (display, image) pairs).
        The display with point on it (the game) is sent sharp; the others smaller, which is cheaper and still enough to roast."""
        pairs, jpegs = self.grab(), []
        imgs = [img for _, img in pairs]
        focus = game_display(pairs, point) if point else None
        for i, img in enumerate(imgs):
            small = img.copy()
            edge = 1568 if focus in (None, i) else OTHER_EDGE  # 1568: Claude's max useful edge; keeps HUD text readable on ultrawides
            small.thumbnail((edge, edge))
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


def videos_folder():
    """Your Windows Videos folder (where Game Bar and NVIDIA save clips by default), even when it's been moved."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            return Path(os.path.expandvars(winreg.QueryValueEx(k, "My Video")[0]))
    except OSError:
        return Path.home() / "Videos"


def new_clip(folder, since, timeout=25.0, step=1.0):
    """The video a capture tool saves after `since` (time.time()) in `folder` or up to two folders down (Game Bar's
    Captures, NVIDIA's per-game folders), once it's done writing; None if none comes within `timeout` s."""
    sizes, end = {}, time.time() + timeout
    while time.time() < end:
        for p in [p for pattern in ("*.mp4", "*/*.mp4", "*/*/*.mp4") for p in folder.glob(pattern)]:
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_mtime >= since - 1:
                if st.st_size and sizes.get(p) == st.st_size:  # (the same size twice: written)
                    return p
                sizes[p] = st.st_size
        time.sleep(step)
    return None


def find_device(name, kind):
    """Index of the input or output device whose name contains `name` (any case); None = the Windows default.
    Only MME devices: they accept any sample rate. MME cuts names at 31 characters, so a cut name also matches."""
    if not name:
        return None
    want, key = name.lower(), "max_input_channels" if kind == "input" else "max_output_channels"
    mme = next(i for i, api in enumerate(sd.query_hostapis()) if api["name"] == "MME")
    for i, d in enumerate(sd.query_devices()):
        dev = d["name"].lower()
        if d["hostapi"] == mme and d[key] > 0 and (want in dev or (len(dev) >= 31 and dev.rstrip() in want)):
            return i
    logging.warning("no %s device named %r, using the Windows default", kind, name)
    return None


def device_names(kind):
    """Full names of the input or output devices, for the Settings window."""
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    wasapi = next((i for i, api in enumerate(sd.query_hostapis()) if api["name"] == "Windows WASAPI"), None)
    return sorted({d["name"] for d in sd.query_devices() if d["hostapi"] == wasapi and d[key] > 0})


def loopback_mic(speaker):
    """A recorder of what `speaker` (part of its name) plays, or None. Built by hand: soundcard's own lookup reads
    every device's name and fails on half-removed devices (error 0xE000020B)."""
    import soundcard
    from soundcard.mediafoundation import _Microphone

    for s in soundcard.all_speakers():
        try:
            if speaker.lower() in s.name.lower():
                return _Microphone(s, isloopback=True)
        except RuntimeError:  # a device that's being removed
            continue
    return None


def listen_source_ok(name):
    """True if the friends' ear can open `name`: an input device, or "loopback:<speaker>"."""
    if name.startswith("loopback:"):
        return loopback_mic(name[9:]) is not None
    return find_device(name, "input") is not None


class Ears:
    def __init__(self):
        self._model = None
        self._lock = threading.Lock()
        self._busy = threading.Lock()  # your mic and the Discord ear share one Whisper model
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
        self._stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32", device=find_device(config.MIC_DEVICE, "input"),
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
        with self._busy:
            segments, _ = self.model().transcribe(audio, language="en", beam_size=1, initial_prompt=prompt)
            return " ".join(s.text.strip() for s in segments).strip()


class WakeListener:
    """Always-on mic that waits for "Hey Vorn". Everything is transcribed on this PC; nothing is sent until he's called."""

    # Whisper often mishears an invented name, so accept the usual near-misses
    @staticmethod
    def pattern(names):
        """ "Hey <name>" for any of the ways the speech recognizer may hear the name."""
        return re.compile(r"\b(?:hey|hay|hi|a|okay|ok)[\s,.!]+(?:" + "|".join(map(re.escape, names)) + r")\b[\s,.!?]*", re.I)

    WAKE = pattern(config.WAKE_NAMES)

    DONE = 1.2  # after "Hey Vorn", the question is sent once you've been quiet this long (on top of the 0.7 s pause)
    WAIT = 6.0  # after a bare "Hey Vorn", how long he waits for you to start the question

    def __init__(self, ears, voice, on_heard, device=None):
        self.ears, self.voice, self.on_heard, self.device = ears, voice, on_heard, device
        self.q = queue.Queue()
        self.pending, self.clips, self.last_end = None, [], 0.0  # the question being collected after "Hey Vorn"
        self.keep_name = False  # duo mode: keep "Hey Mika" in the question, so only the one you called answers
        self.called = ""  # that "Hey Mika", for the question being collected
        self.speaking = False  # someone is mid-sentence right now
        self.interrupts = False  # your mic (not a loopback, which hears his own voice): talking over him pauses him
        self.speech, self.silent, self.voiced = [], 0, 0  # the stretch of talking being heard: chunks, quiet ones at the end, loud ones
        self.deaf_until = 0.0  # a loopback hears their own voice: deaf while they talk and ECHO_TAIL after

    INTERRUPT_AFTER = 4  # 0.1 s chunks of your voice over his before he pauses to listen (a cough or a click doesn't)
    ECHO_TAIL = 1.0  # s: the end of their line still arriving (audio latency, chunks queued during a transcription)

    def active(self):
        """True while someone is talking to him (so he doesn't start a comment over them)."""
        return self.speaking or self.pending is not None

    def run(self):
        if (self.device or "").startswith("loopback:"):  # what a speaker plays (a call's audio), not a mic
            threading.Thread(target=self._loopback, args=(self.device[9:],), daemon=True).start()
            source = contextlib.nullcontext()
        else:
            source = sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=1600,  # 0.1 s chunks
                                    device=find_device(self.device, "input"), callback=lambda data, *_: self.q.put(data[:, 0].copy()))
        with source:
            while True:
                try:
                    chunk = self.q.get(timeout=0.3)
                except queue.Empty:
                    chunk = np.zeros(1600, np.float32)  # a source with nothing to say still lets questions finish
                self.take(chunk)

    def take(self, chunk):
        """One 0.1 s chunk of sound: collect talking, pause him if you talk over him, transcribe after a pause."""
        self.speaking = bool(self.speech)
        self.flush()
        if self.voice.busy() and not self.interrupts:
            self.deaf_until = time.monotonic() + self.ECHO_TAIL
        if self.ears.recording or time.monotonic() < self.deaf_until:  # push-to-talk; his own voice on a loopback
            self.speech, self.silent, self.voiced = [], 0, 0
            return
        loud = float(np.sqrt(np.mean(chunk * chunk))) > config.WAKE_LEVEL
        if loud or self.speech:
            self.speech.append(chunk)
            self.silent, self.voiced = (0 if loud else self.silent + 1), self.voiced + loud
        if self.interrupts and self.voiced >= self.INTERRUPT_AFTER and self.voice.busy():
            self.voice.pause()  # you're talking over him: he stops mid-sentence to listen
        if self.speech and (self.silent >= 7 or len(self.speech) >= 300):  # a 0.7 s pause (or 30 s) ends a stretch of talking
            audio = np.concatenate(self.speech)
            self.speech, self.silent, self.voiced = [], 0, 0
            try:
                if len(audio) > 16000 * 0.5:
                    self.hear(self.ears.transcribe(audio, prompt=f"Hey {config.NAME}."), audio)
            finally:
                self.settle()

    def settle(self):
        """After you talked over him: he stops for good if it was to him ("Hey Vorn, ..."), else carries on."""
        if self.voice.paused():
            if self.pending is not None:
                self.voice.stop()
            else:
                self.voice.resume()

    def _loopback(self, speaker):
        """Feed what `speaker` plays into the listener, in 0.1 s chunks at 16 kHz."""
        mic = loopback_mic(speaker)
        with mic.recorder(samplerate=16000, channels=1, blocksize=1600) as rec:
            while True:
                self.q.put(rec.record(numframes=1600)[:, 0].astype(np.float32))

    def hear(self, text, audio=None):
        """Collect what's said after "Hey Vorn"; flush() sends it once you stop talking."""
        m = self.WAKE.search(text)
        if m:
            rest = text[m.end():].strip()
            self.called = m.group(0).strip(" ,.!?") if self.keep_name else ""  # kept even if the question comes after a pause
            if not rest:
                self.on_heard(None, None)  # just his name: he chimes and waits for the question
            self.pending, self.clips = rest, ([audio] if rest and audio is not None else [])
        elif text and self.pending is not None:  # you kept talking after a pause: same question
            self.pending = f"{self.pending} {text}".strip()
            if audio is not None:
                self.clips.append(audio)
        self.last_end = time.monotonic()

    def expect(self, seconds, called=""):
        """Take what's said in the next `seconds` as said to them, no wake word needed (they just asked you something).
        called: in duo mode, the "Hey Mika" it counts as (so the one who asked answers)."""
        self.pending, self.clips, self.called = "", [], called
        self.last_end = time.monotonic() + seconds - self.WAIT

    def flush(self, force=False):
        """Send the collected question once you've stopped talking (force: now)."""
        if self.pending is None or (self.speaking and not force):
            return
        quiet = time.monotonic() - self.last_end
        if self.pending and (force or quiet >= self.DONE):
            text, clips = self.pending, self.clips
            self.pending, self.clips = None, []
            self.on_heard(f"{self.called}, {text}" if self.called else text, np.concatenate(clips) if clips else None)
        elif not self.pending and (force or quiet >= self.WAIT):  # a bare "Hey Vorn", then nothing
            self.pending = None


MOUTH_FPS = 50  # mouth shapes per second of speech


def mouth_track(audio, sr=SR):
    """How the mouth moves through a line, every 1/50 s: rows of (open 0..1, wide -1 round .. 1 wide, teeth 0 or 1).
    Read from the sound itself, so it works for every voice: silence closes the lips (also on m, b, p), hiss shows the
    teeth (s, f, sh), and the vowel's resonances (formants, found by linear prediction) tell open "ah" from round "oo"
    and wide "ee". Each line is measured against its own range, so a high voice and a deep one both work."""
    rate, order = sr // 2, 12  # 12 kHz is plenty: the formants that shape the lips are below 4 kHz
    x = audio[: len(audio) // 2 * 2].reshape(-1, 2).mean(axis=1)
    hop, win = rate // MOUTH_FPS, int(rate * 0.03)
    if len(x) < win * 2:
        return np.zeros((0, 3), np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(x, win)[::hop]
    n = len(frames)
    loud = np.sqrt((frames ** 2).mean(axis=1))
    full = np.lib.stride_tricks.sliding_window_view(audio, win * 2)[::hop * 2][:n] * np.hanning(win * 2)
    spec = np.abs(np.fft.rfft(full, axis=1)) ** 2
    freqs = np.fft.rfftfreq(win * 2, 1 / sr)
    hiss = spec[:, freqs >= 4000].sum(1) / (spec[:, (freqs >= 250) & (freqs < 3200)].sum(1) + 1e-12)
    n = len(hiss)
    emph = np.append(x[0], x[1:] - 0.94 * x[:-1])  # pre-emphasis lifts the higher formants
    f = np.lib.stride_tricks.sliding_window_view(emph, win)[::hop][:n] * np.hamming(win)
    r = np.stack([(f[:, : win - k] * f[:, k:]).sum(1) for k in range(order + 1)], axis=1)
    a, err = np.zeros((n, order + 1)), r[:, 0] + 1e-12  # Levinson-Durbin, all frames at once
    a[:, 0] = 1
    for i in range(1, order + 1):
        k = -(r[:, i] + (a[:, 1:i] * r[:, i - 1:0:-1]).sum(1)) / err
        a[:, 1:i + 1] = a[:, 1:i + 1] + k[:, None] * a[:, i - 1::-1][:, :i]
        err = err * (1 - k * k) + 1e-12
    comp = np.zeros((n, order, order))  # the prediction polynomial's roots are the resonances
    comp[:, 0, :] = -a[:, 1:]
    comp[:, np.arange(1, order), np.arange(order - 1)] = 1
    z = np.linalg.eigvals(comp)
    hz, bw = np.angle(z) * rate / (2 * np.pi), -rate / np.pi * np.log(np.abs(z) + 1e-12)
    hz = np.sort(np.where((z.imag > 0) & (hz > 200) & (bw < 500), hz, np.inf), axis=1)
    f1, f2 = np.where(hz[:, 0] < 1100, hz[:, 0], np.inf), hz[:, 1]  # above 1100 Hz it missed the first one
    level = np.clip(loud[:n] / (np.percentile(loud[:n], 95) + 1e-9), 0, 1)  # the line's loud parts, not one peak
    vowel = (level > 0.12) & (hiss < 3) & np.isfinite(f1) & np.isfinite(f2)

    def spread(v, least):  # 0..1 within this line's own range
        if vowel.sum() < 3:
            return np.full(n, 0.5)
        lo, hi = np.percentile(v[vowel], [10, 90])
        mid, half = (lo + hi) / 2, max(hi - lo, least) / 2
        return np.clip((np.where(np.isfinite(v), v, mid) - (mid - half)) / (2 * half), 0, 1)

    opened, front = spread(f1, 250), spread(f2, 600)
    track = np.zeros((n, 3), np.float32)
    track[:, 0] = np.where(vowel, level * (0.3 + 0.7 * opened), np.where(level > 0.12, 0.15 + 0.3 * level, 0))
    wide = np.where(front >= 0.5, (front - 0.5) * 2, -(0.5 - front) * 2 * (1 - opened))  # round only when closed too: "oo", not "ah"
    track[:, 1] = np.where(vowel, wide, np.where(level > 0.12, 0.4, 0))
    track[:, 2] = (level > 0.12) & ((hiss >= 3) | vowel & (front > 0.75) & (opened < 0.4))
    for col in (0, 1):  # a touch of smoothing: no 20 ms flicker
        track[:, col] = np.convolve(track[:, col], [0.25, 0.5, 0.25], mode="same")
    return track


KOKORO = Path(__file__).with_name("models") / "kokoro"
KOKORO_FILES = {"kokoro-v1.0.fp16-gpu.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/",
                "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"}
ONLINE = "en-US-ChristopherNeural"  # backup voice if the local one fails
logging.getLogger("phonemizer").setLevel(logging.ERROR)  # Kokoro's pronouncer warns about harmless word-count mismatches


def speed_of(rate):
    """'+6%' -> 1.06 (Kokoro's speed from the voice-speed setting)."""
    m = re.match(r"([+-]?\d+)", rate or "0")
    return 1 + (int(m.group(1)) if m else 0) / 100


class Voice:
    """His voice: "kokoro:<voice>" runs Kokoro on this PC (well under a second), anything else is a Microsoft online voice."""

    def __init__(self):
        self._audio = None
        self._t0 = 0.0
        self._held = None  # paused mid-line because you started talking: (audio, where to carry on)
        self._track = None  # the playing line's mouth shapes
        self.cut = False  # stop() was called: whoever is waiting on a line drops the rest of the exchange
        self._kokoro = None
        self._lock = threading.Lock()

    def kokoro(self):
        """Load Kokoro once (downloading its ~205 MB of files the first time)."""
        with self._lock:
            if self._kokoro is None:
                import onnxruntime as ort
                from kokoro_onnx import Kokoro
                KOKORO.mkdir(parents=True, exist_ok=True)
                for name, url in KOKORO_FILES.items():
                    if not (KOKORO / name).exists():
                        tmp = KOKORO / (name + ".part")
                        urllib.request.urlretrieve(url + name, tmp)
                        tmp.replace(KOKORO / name)
                options = ort.SessionOptions()
                options.intra_op_num_threads = 4  # leave the rest of the CPU to your game
                session = ort.InferenceSession(str(KOKORO / "kokoro-v1.0.fp16-gpu.onnx"), options, providers=["CPUExecutionProvider"])
                self._kokoro = Kokoro.from_session(session, str(KOKORO / "voices-v1.0.bin"))
            return self._kokoro

    def synth(self, text, voice=None, rate=None, pitch=None):
        """Speech audio for text; voice/rate/pitch override the settings (the Settings window's Test button)."""
        voice, rate = voice or config.VOICE, rate or config.VOICE_RATE
        if voice.startswith("kokoro:"):
            try:
                audio, sr = self.kokoro().create(text, voice=voice[7:], speed=speed_of(rate))
                return audio.astype(np.float32) if sr == SR else np.interp(
                    np.arange(0, len(audio), sr / SR), np.arange(len(audio)), audio).astype(np.float32)
            except Exception:
                logging.warning("local voice failed, using the online voice", exc_info=True)
                voice = ONLINE

        async def fetch():
            out = bytearray()
            async for chunk in edge_tts.Communicate(text, voice, rate=rate, pitch=pitch or config.VOICE_PITCH).stream():
                if chunk["type"] == "audio":
                    out += chunk["data"]
            return bytes(out)

        mp3 = asyncio.run(fetch())
        snd = miniaudio.decode(mp3, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1, sample_rate=SR)
        return np.frombuffer(snd.samples, dtype=np.float32).copy()

    def play(self, audio):
        """Start playing; returns the duration in seconds."""
        sd.stop()
        self._audio, self._t0, self._held = audio, time.monotonic(), None
        self._track = mouth_track(audio)  # a few milliseconds for a 5 s line
        sd.play(audio, SR, device=find_device(config.VOICE_DEVICE, "output"))  # a VoiceMeeter input puts him in your calls
        return len(audio) / SR

    def stop(self):
        """Stop for good (push-to-talk, or you said his name over him): the rest of the line and exchange are dropped."""
        sd.stop()
        self._audio, self._held, self.cut = None, None, True

    def pause(self):
        """Stop mid-line because you started talking, keeping the place for resume(). True if he was talking."""
        if not self.busy():
            return False
        at = int((time.monotonic() - self._t0) * SR)
        self._held = (self._audio, max(0, at - SR // 4))  # carry on a quarter second back: restarting mid-word is jarring
        sd.stop()
        self._audio = None
        return True

    def paused(self):
        return self._held is not None

    def resume(self):
        """Carry on where pause() left off (you weren't talking to him)."""
        held, self._held = self._held, None
        if held:
            audio, at = held
            self._audio, self._t0 = audio, time.monotonic() - at / SR  # level() and busy() keep counting from the line's start
            sd.play(audio[at:], SR, device=find_device(config.VOICE_DEVICE, "output"))

    def busy(self):
        return self._audio is not None and time.monotonic() - self._t0 < len(self._audio) / SR

    def mouth(self):
        """(open, wide, teeth) for the mouth right now (see mouth_track); closed when he isn't talking."""
        if not self.busy() or self._track is None or not len(self._track):
            return (0.0, 0.0, 0.0)
        return tuple(float(v) for v in self._track[min(int((time.monotonic() - self._t0) * MOUTH_FPS), len(self._track) - 1)])

    def level(self):
        """Loudness 0..1 at the current playback position (moves his head as he talks)."""
        if not self.busy():
            return 0.0
        i = int((time.monotonic() - self._t0) * SR)
        w = self._audio[i:i + 800]
        return float(min(1.0, np.sqrt(np.mean(w * w)) * 7)) if len(w) else 0.0
