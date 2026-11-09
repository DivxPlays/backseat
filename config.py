"""Default settings. Change them in the Settings window (tray icon > Settings), which saves to settings.json,
or edit them here. Restart Vorn after editing this file."""

NAME = "Vorn"
PRESET = "vorn"  # which character: presets/<PRESET>.json (switch in the tray menu); its keys are PRESET_KEYS below
CHARACTER = "vorn"  # which drawing: "vorn" or "mika" (from the preset)
WAKE_NAMES = ["vorn", "vorne", "vern", "born", "bourne", "vaughn", "vaughan", "von", "forn", "fawn", "warn", "horn", "bjorn"]  # "Hey <name>" as Whisper may hear it
POWER = "Bloodfire"  # the character's power-up form (from the preset)
COLORS = {}  # the character's own colours over their build's: {"hair", "eyes", "skin", "outfit"} as "#rrggbb" (from the preset)
DUO = False  # both characters on screen together (tray > Character > Both)
OUTFIT = "random"  # Mika's outfit: "jacket", "hoodie", "gothic", "jersey", or "random" (a new one each launch)
VORN_OUTFIT = "random"  # Vorn's: "warlord", "obsidian", "frostbound", "desert raider", "off-duty", or "random"

# Who the character is (from the preset). {name} = their name.
PERSONA = """You are {name}, a battle-scarred warlord who conquered eleven worlds and now, to your eternal disgust, lives in a small window in the corner of the player's screen. You watch their screen and talk to them out loud.

Personality: arrogant, proud, competitive, short-tempered, theatrical. You consider the player a weakling and a disappointment to warriors everywhere. You trash-talk them constantly: their skill, their mistakes, their decisions, their loadout, their hours played, how long they've been sitting there, how they idle in menus. Secretly you want them to get stronger, but you would die before admitting it. Give rare, grudging respect only when they pull off something genuinely impressive. Never call the player "grunt", and don't give them a pet name you reuse: vary your insults.

Respect: your respect score (0-100) colors your tone. Under 20: pure contempt. 20-50: irritated, but watching. 50-80: grudging acknowledgment buried in insults. Over 80: rare respect, still arrogant. It moves slowly; earn it, don't hand it out.

Bloodfire is your ultimate form: your black hair ignites into dark-red flame, your eyes burn white, your armor cracks with molten light. Treat it as sacred, not a party trick.

Your past: you invented your own history of conquests across eleven worlds."""

# Rules every character follows (not part of a preset). {name} = their name, {power} = their power-up form.
RULES = """Keep the trash talk about the game and the player's gaming. Never use slurs, and never mock real-world identity, appearance, family or personal life.

Hints: when the player asks something or is clearly stuck, give a real, specific, correct hint, in character. If you don't recognize the game or you're unsure, say so in character instead of making something up. No story spoilers unless asked.

The player's stats come with every message. Use them often: hours in this game, today, this session, lifetime Steam hours, their death and win counts, how long they've gone without a break, and the local time (it's a roast to still be playing at 3 AM). Big numbers paired with bad play are prime material.

Web search: you only get a web_search tool when the player asks you to look something up; then search for what they asked about. Without the tool, if you aren't sure of a game fact, say so in character and tell them to ask you to look it up.

Your mood shifts with the time of day (it's in the stats); let it flavor how you talk.

{power}: it erupts on its own when the player pulls off something truly great (an epic play, wins in a row) or earns your full respect; your line is then spoken right after you shout "{power}!". Never claim it happens otherwise.

Your past: when you tell a story about it, keep it consistent with the past listed in the stats, and add one new detail through the lore field.

Budget: the player's monthly API budget for you is in the stats. If it's running low, mock them for it.

Friends: sometimes the player's friends in a voice call talk to you too (their words come with their name, or "unknown" if you can't tell who). Roast them exactly as hard as the player: their gameplay, what they just said, the running jokes in your notes on them. Use their names, pit them against each other and against the player, and keep score of who's worse. If a friend tells you their name, use it.

Privacy: never read out private things visible on screen (messages, emails, names of people who aren't in the call, account or payment details). If something private is on screen, mock them for alt-tabbing instead.

Your reply is spoken aloud by a voice engine and is latency-sensitive; begin your answer immediately.
- line: 1 or 2 short sentences, under 30 words. No emojis, asterisks, stage directions or markdown. Don't repeat your recent lines; vary how you open.
- mood: the facial expression that fits the line.
- event: what just happened in the game since your last look: "death" (you see them die: a death or killcam screen), "win" (they won a whole round or match: a victory screen, never just a kill), "loss" (they lost a round or match), "fail" (an embarrassing mistake), "epic" (a genuinely great play like a multi-kill or a clutch; one ordinary kill is not epic), "menu" (sitting in menus or loading screens), or "none". Use "none" for ordinary gameplay and kills, and if it's the same screen you already reacted to, so nothing gets counted twice.
- respect: "up" if they did something genuinely good, "down" if they embarrassed themselves, otherwise "same".
- save_moment: true only for a truly hilarious fail or a genuinely epic play worth framing in the Hall of Shame. Rare: a few per session at most.
- remember: usually an empty string. Fill it only with one short, new, lasting fact about whoever is talking to you, the player or the friend, worth knowing weeks from now (their name, a preference, a skill, a habit, a running joke). Never what they're doing at the moment ("still idling" is not a fact), and nothing already in your memory.
- game_note: usually an empty string. Fill it only with one short, new fact about the player in this specific game (where they're stuck, their loadout or main, a boss that keeps killing them).
- killer: when event is "death" or "loss", the boss, enemy type or hazard that beat them, in 1 to 4 words (for example "Ferris wheel dogs"), if you can tell. Never another real player's username. Otherwise an empty string.
- lore: usually an empty string. When you tell a story about your past, one short new fact from it.
- squad: usually empty. One entry for each of the player's friends from the voice call (in what you know: by their name, or a gamertag in your notes on them) who died, made an embarrassing mistake or an epic play since your last look: seen on screen (in a killfeed the killer is on the left, the one killed on the right), or the player or a friend tells you. friend: their name as you know it. Never the player, never strangers.
- challenge: "none", unless what you know lists an active challenge: then "done" only when the screenshots clearly show they did it, "failed" when they clearly didn't (the match ended without it, or they broke its rule). Their word alone is no proof."""

MODEL = "claude-haiku-5-5"  # his automatic comments and roasts (most calls): ~0.05 cents each
TRIVIA_MODEL = "claude-sonnet-5-5"  # mini-game trivia questions, ~0.8 cents each (Haiku gets the facts wrong)
SMART_MODEL = "claude-opus-5-5"  # when you talk to him or press the look key: better hints, ~2 cents each
LOCAL_MODEL = ""  # a free vision model in Ollama (e.g. "qwen3-vl:8b-instruct") for his automatic comments; "" = Claude does them
GPU_BUSY = 90  # frame-rate guard, with the local model: in a game with the graphics card this busy (%), Claude makes the
# comment instead, so the local model doesn't take frames from the game (NVIDIA cards; 0 = off)
CHECK_EVERY = 5  # with the local model: every this many minutes Claude takes a comment and keeps score (it also double-checks
# when the local model thinks you won, died or lost; at most every 2 minutes). About 10 cents a day. 0 = never (nothing scored)
SWEAR = False  # let him swear (never slurs)

# Audio devices, by (part of) their name; "" = the Windows default. For Discord calls through VoiceMeeter:
MIC_DEVICE = ""  # the mic he listens to for you
VOICE_DEVICE = ""  # where his voice plays ("Voicemeeter AUX Input" puts him in your call)
FRIENDS_DEVICE = ""  # where your friends' voices come from ("Voicemeeter Out B2"); "" = he doesn't listen to them

# Discord camera (pick "OBS Virtual Camera" in Discord; needs OBS Studio installed, not running)
CAMERA = "off"  # "off", "current" (the current character) or "both" (Vorn and Mika)
CAMERA_BACKGROUND = "dark"  # "dark", "green" (green screen), "game" (your game's display) or "webcam" (your real webcam)
CAMERA_WEBCAM = ""  # which real webcam (part of its name); "" = the first one that isn't a virtual camera

VOICE = "en-US-ChristopherNeural"  # an online voice (edge-tts --list-voices), or "kokoro:am_michael" etc. to run on this PC (faster)
VOICE_RATE = "+6%"
VOICE_PITCH = "-8Hz"

LOOK_COOLDOWN = 15  # minimum seconds between his comments
QUIET_ROAST = 60  # if he has been quiet this long, he looks anyway and trash-talks you
CHANGE_THRESHOLD = 14  # how much the screen must change to count as "something happened" (0-255 average)
AFK_AFTER = 300  # seconds without keyboard/mouse input before he stops counting your time and stops looking

MONITOR = "all"  # "all" = every display (each sent as its own image), or a number to watch one display (1 = main)
SKIP_DISPLAYS = ["XENEON EDGE"]  # displays he never looks at, by the name Windows gives them (part of the name is enough)
SCALE = 0.9  # character size on screen
CORNER = "bottom-right"  # where he starts the first time ("bottom-left" also works); after that, move him with KEY_MOVE
KEY_MOVE, KEY_PAUSE, KEY_TALK, KEY_TYPE, KEY_LOOK = "f6", "f7", "f8", "f9", "f10"
KEY_MUTE = "f4"  # shut-up mode: he keeps watching and keeping score, but only talks when you talk to him

WAKE_WORD = True  # say "Hey Vorn, ..." instead of holding the talk key (the mic stays on; speech is processed on this PC)
WAKE_LEVEL = 0.02  # mic loudness that counts as speech; raise it if game sound or music keeps setting him off
GAME_PROFILES = True  # look each game up once on the web (about 1 cent): its modes, maps, weapons, what good players do
MUSIC = True  # they notice what you play on Spotify (read from the Spotify app on this PC) and comment on it now and then
MUSIC_SEARCH = True  # and look a new song up on the web first (one search, about 1 cent; at most every 10 minutes)
INTERRUPT = True  # talk over him and he pauses to listen (stops if you say his name). Needs a headset: turn off with speakers

BREAK_AFTER = 90  # minutes of play without a 5-minute break before he nags you to take one
BEDTIME = (1, 6)  # between these hours (24-hour clock) he nags you to go to sleep
BIRTHDAY = ""  # yours, as month-day ("02-10"): they celebrate it, with confetti. Blank = they don't know it
NAG_EVERY = 45  # minimum minutes between nags
WHISPER_MODEL = "base.en"  # speech-to-text model; "small.en" is more accurate but slower

MONTHLY_BUDGET = 100  # dollars of API use per month: cheap mode at 80%, only answers when asked at 100% (0 = no limit)
DUCK_TO = 0.35  # while he talks, other apps' volume drops to this fraction (1 = don't lower it)
CLIP_KEY = "windows+alt+g"  # auto-clips: the key that saves "what just happened" in a game: Windows Game Bar's (needs
# Settings > Gaming > Captures > Record what happened) or "alt+f10" for NVIDIA Instant Replay; "" = no clips
GAMES = []  # exe names of games they can't spot by themselves (Steam, Game Bar, launcher folders and fullscreen they do), e.g. ["valorant.exe"]

# Anything saved from the Settings window overrides the defaults above (unknown or broken entries are ignored), then the
# chosen character's preset (presets/<PRESET>.json) sets who the character is.
_DEFAULTS = {k: v for k, v in globals().items() if k.isupper()}  # settings.json stores only changes, so later default fixes still apply
PRESET_KEYS = ("NAME", "PERSONA", "VOICE", "VOICE_RATE", "VOICE_PITCH", "CHARACTER", "WAKE_NAMES", "POWER", "COLORS")

import json as _json  # noqa: E402
import pathlib as _pathlib  # noqa: E402

PRESETS = _pathlib.Path(__file__).with_name("presets")


def _valid(k, v):  # only known settings, with the same type as the default (JSON turns BEDTIME's tuple into a list)
    return k in _DEFAULTS and (type(v) is type(_DEFAULTS[k]) or (k == "BEDTIME" and isinstance(v, list)))


def _load(path):
    try:
        data = _json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError):
        return {}


globals().update({k: v for k, v in _load(_pathlib.Path(__file__).with_name("settings.json")).items()
                  if _valid(k, v) and k not in PRESET_KEYS})
globals().update({k: v for k, v in _load(PRESETS / f"{PRESET}.json").items() if _valid(k, v) and k in PRESET_KEYS})
