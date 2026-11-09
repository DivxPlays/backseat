"""Sound effects: real recordings (CC0, see sounds/CREDITS.md) of grunts, gasps, scoffs, chuckles, giggles, sighs and
yawns for Vorn's build and Mika's (a created character uses its build's). They play when poked, grabbed and landing
after a throw, with some idle animations, and now and then before a line, by its mood."""
import random
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np

import config

FOLDER = Path(__file__).with_name("sounds")
SR = 24000  # the voice's sample rate (senses.SR); the recordings are stored at it
MOODS = {"smug": ("scoff", "chuckle", "giggle"), "laugh": ("laugh", "chuckle", "giggle"), "angry": ("grunt", "pout"),
         "disgusted": ("scoff", "pout", "sigh"), "surprised": ("gasp",)}  # before a line in that mood
MOMENTS = {"poke": ("grunt",), "poke head": ("grunt",), "poke annoyed": ("grunt", "pout"), "grabbed": ("gasp", "grunt"),
           "throw": ("yell", "gasp"), "thrown": ("grunt",)}  # pokes and throws (let go: Vorn yells, Mika gasps; landing: a grunt)
IDLES = {"sigh": ("sigh",), "nod off": ("yawn",), "stretch": ("yawn", "sigh"), "power stance": ("chuckle",),
         "heart hands": ("giggle",), "bounce": ("giggle",), "wave": ("giggle",)}  # with these idle animations
IDLE_GAP = 45  # s: at most one idle sound per character this often


@lru_cache(maxsize=None)
def clips(build, kind):
    """The recordings of `kind` ("grunt", "giggle"...) for a build ("vorn" or "mika"), as float32 audio at SR."""
    out = []
    for path in sorted((FOLDER / build).glob(f"{kind}-*.wav")):
        with wave.open(str(path)) as w:
            out.append(np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768)
    return tuple(out)


def pick(build, kinds):
    """A random recording of one of `kinds` that the build has; None if it has none or sound effects are off."""
    have = [k for k in kinds if clips(build, k)] if config.SOUND_EFFECTS else []
    return random.choice(clips(build, random.choice(have))) if have else None


def before(sound, audio):
    """A line's audio starting with a sound effect (a scoff, a giggle), a short breath between them."""
    return audio if sound is None or audio is None else np.concatenate([sound, np.zeros(int(SR * 0.12), np.float32), audio])
