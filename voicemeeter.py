"""One-click VoiceMeeter routing for Discord calls, through VoiceMeeter's own Remote API (Banana or Potato).

    your mic (hardware input 1) -> B1 = "Voicemeeter Out B1", Discord's microphone
    Discord's sound -> "Voicemeeter Input" -> A1 (your headset) + B2 = "Voicemeeter Out B2", his ear for your friends
    his voice -> "Voicemeeter AUX Input" -> A1 (you hear him) + B1 (your friends hear him)
"""
import ctypes
import os
import time
from pathlib import Path

DLL = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "VB", "Voicemeeter", "VoicemeeterRemote64.dll")
VIRTUAL = {2: (3, 4), 3: (5, 6)}  # VoiceMeeter type -> strip numbers of "Voicemeeter Input" and "Voicemeeter AUX Input"
VOICE, FRIENDS, DISCORD_MIC, DISCORD_OUT = "Voicemeeter AUX Input", "Voicemeeter Out B2", "Voicemeeter Out B1", "Voicemeeter Input"


def routes(kind):
    """{parameter: 0/1} for VoiceMeeter type kind (2 Banana, 3 Potato)."""
    vaio, aux = VIRTUAL[kind]
    plan = {0: (0, 1, 0), vaio: (1, 0, 1), aux: (1, 1, 0)}  # strip: (A1, B1, B2)
    return {f"Strip[{s}].{bus}": on for s, buses in plan.items() for bus, on in zip(("A1", "B1", "B2"), buses)}


def setup():
    """Start VoiceMeeter Banana if needed and route it for Discord. Raises RuntimeError with a readable reason."""
    if not DLL.exists():
        raise RuntimeError("VoiceMeeter isn't installed (get VoiceMeeter Banana from vb-audio.com).")
    vm = ctypes.WinDLL(str(DLL))
    vm.VBVMR_SetParameterFloat.argtypes = [ctypes.c_char_p, ctypes.c_float]
    if vm.VBVMR_Login() < 0:
        raise RuntimeError("Couldn't talk to VoiceMeeter.")
    try:
        kind = ctypes.c_long(0)
        if vm.VBVMR_GetVoicemeeterType(ctypes.byref(kind)) != 0:  # installed but not running
            vm.VBVMR_RunVoicemeeter(5)  # Banana, 64-bit
            for _ in range(40):
                time.sleep(0.25)
                if vm.VBVMR_GetVoicemeeterType(ctypes.byref(kind)) == 0:
                    break
        if kind.value not in VIRTUAL:
            raise RuntimeError("This needs VoiceMeeter Banana or Potato: the basic VoiceMeeter has no AUX input for his voice.")
        time.sleep(0.5)
        while vm.VBVMR_IsParametersDirty() > 0:  # let it finish loading before changing anything
            time.sleep(0.1)
        for name, value in routes(kind.value).items():
            if vm.VBVMR_SetParameterFloat(name.encode(), value) != 0:
                raise RuntimeError(f"VoiceMeeter refused {name}.")
        time.sleep(0.5)  # changes apply asynchronously; logging out right away throws them away
    finally:
        vm.VBVMR_Logout()
