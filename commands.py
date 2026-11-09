"""Voice commands handled on this PC, free and instant: "Hey Vorn, shut up for 10 minutes", "Hey Mika, wear the hoodie",
"switch to Mika", "stop looking", "how much have you cost me?". Only a whole sentence that is a command counts; anything
else ("shut up, you're wrong about that map") goes to Claude as usual.
"""
import random
import re

WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
         "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "forty five": 45, "sixty": 60, "half an": 0.5, "a couple": 2,
         "a couple of": 2, "a few": 3}
UNIT = {"s": 1, "m": 60, "h": 3600}
NUM = r"(?P<n>\d+(?:\.\d+)?|" + "|".join(sorted(map(re.escape, WORDS), key=len, reverse=True)) + r")"
FOR = rf"(?: for (?:{NUM} (?P<unit>sec(?:ond)?s?|min(?:ute)?s?|h(?:ou)?rs?)|a (?P<while>bit|while)))?"
COMMANDS = [
    ("mute", rf"(?:shut up|be quiet|quiet|stop talking|zip it|hush|shush|pipe down|keep quiet|stay quiet|silence|mute(?: yourself)?){FOR}"),
    ("unmute", r"(?:you can (?:talk|speak)(?: again| now)?|(?:talk|speak) again|start talking(?: again)?|unmute(?: yourself)?|"
               r"speak freely|you can speak freely|come back)"),
    ("vision off", r"(?:(?:stop|quit|don't|do not) (?:looking|watching)(?: at (?:my|the) screen)?|look away|close your eyes|"
                   r"don't look|(?:stop|pause) (?:your )?vision)"),
    ("vision on", r"(?:(?:you can )?(?:look|watch)(?: at (?:my|the) screen)? again|open your eyes|(?:start|resume) (?:looking|watching)"
                  r"(?: again)?|resume (?:your )?vision|you can look(?: now)?)"),
    ("cost", r"(?:how much (?:have|did|do) you cost(?: me)?|what (?:have|did|do) you cost(?: me)?|how much (?:have|did) i spen[dt] on you|"
             r"what'?s (?:my|your|the) (?:api )?bill|how much money (?:have|did) you (?:cost|burn(?:ed|t)?)(?: me)?)"
             r"(?: this month| so far| today)?"),
    ("new outfit", r"(?:(?:change|switch) (?:your )?(?:outfit|clothes|look)|(?:get|put on|wear|try) (?:a )?(?:new|different) "
                   r"(?:outfit|look|clothes)|new outfit|change clothes)"),
    ("wear", r"(?:wear|put on|change into|switch into|dress (?:up )?(?:in|as)|(?:switch|change) to)(?: your| the| that| my)? "
             r"(?P<what>.+?)(?: outfit| look| one)?"),
    ("switch", r"(?:(?:switch|change|swap|go)(?: back)? to|let me talk to|i want) (?:just |only )?(?P<who>.+?)(?: mode| only)?"),
    ("switch", r"(?P<who>both of you|duo mode)"),
]
BOTH = {"both", "both of you", "both of them", "the both of you", "you both", "you two", "the two of you", "duo", "duo mode", "everyone"}
# outfit nicknames you might say (each character only matches their own outfits: "hoodie" is Mika's hoodie or Vorn's off-duty)
ALIASES = {"off-duty": ("off duty", "offduty", "hoodie", "casual", "comfy"), "desert raider": ("desert", "raider"),
           "frostbound": ("frost", "winter", "ice", "snow"), "obsidian": ("black armor", "black armour"),
           "warlord": ("armor", "armour", "normal", "usual", "default"), "gothic": ("goth", "dress"), "jersey": ("esports",),
           "jacket": ("gamer jacket",)}


def clean(text):
    """Lower case, no punctuation, without the polite bits around a command ("can you please ... now")."""
    t = re.sub(r"\s+", " ", re.sub(r"[^\w\s'-]", " ", text.lower())).strip()
    while True:
        s = re.sub(r"^(?:please|can you|could you|would you|will you|just|okay|ok|now|hey|yo|alright|go ahead and)\s+", "", t)
        s = re.sub(r"\s+(?:please|now|right now|thanks|thank you|for me)$", "", s)
        if s == t:
            return t
        t = s


def outfit_named(what, outfits):
    """Which of `outfits` the words name ("the hoodie" -> "off-duty" for Vorn), or None."""
    for words_of in (lambda n: (n, n.replace("-", " ")), lambda n: ALIASES.get(n, ())):  # real names first, then nicknames
        for name in outfits:  # anywhere in what was said: "the obsidian armor" is Obsidian, not the warlord's "armor"
            if any(re.search(rf"\b{re.escape(word)}\b", what) for word in words_of(name)):
                return name
    return None


def parse(text, outfits=(), characters=None):
    """(command, value) if the whole of `text` is a voice command, else None.
    outfits: the outfit names of the one being talked to; characters: {preset: the names they answer to} for switching.
    Commands: ("mute", seconds or None), ("unmute", None), ("vision", True/False), ("cost", None),
    ("outfit", a name or None for a different one), ("switch", a preset or "both")."""
    t = clean(text)
    for kind, pattern in COMMANDS:
        m = re.fullmatch(pattern, t)
        if not m:
            continue
        if kind == "mute":
            g = m.groupdict()
            if g["while"]:
                return "mute", 600
            if g["n"]:
                n = float(g["n"]) if g["n"][0].isdigit() else WORDS[g["n"]]
                return "mute", int(n * UNIT[g["unit"][0]])
            return "mute", None
        if kind in ("unmute", "cost"):
            return kind, None
        if kind.startswith("vision"):
            return "vision", kind == "vision on"
        if kind == "new outfit":
            return "outfit", None
        if kind == "wear":
            name = outfit_named(m.group("what"), outfits)
            if name:
                return "outfit", name
            continue  # "switch to Mika" isn't an outfit: maybe a switch
        who = m.group("who").strip()
        if who in BOTH:
            return "switch", "both"
        for preset, names in (characters or {}).items():
            if who in [n.lower() for n in names] + [preset]:
                return "switch", preset
    return None


# what they say back: (mood, lines). {n}: how long, {spent}: this month's spend, {outfit}: the outfit, {other}: who's next
LINES = {
    "vorn": {
        "mute": ("disgusted", ["Fine. I'll speak only when you dare to speak to me.", "Silence, then. Don't mistake it for mercy."]),
        "mute for": ("disgusted", ["Fine. {n} of silence. Savor it, weakling.", "{n}. Then I resume telling you the truth."]),
        "unmute": ("smug", ["Finally. Your silence was almost as tragic as your aim.", "I'm back. Try to look less lost."]),
        "vision off": ("smug", ["I'll look away. Hiding something shameful?", "Eyes closed. Your failures will keep."]),
        "vision on": ("smug", ["My eyes are back on your failures.", "Show me. Let's see how bad it got."]),
        "cost": ("smug", ["You've spent {spent} on me this month. The best money you've ever wasted.",
                          "{spent} this month. A bargain for a warlord's attention."]),
        "outfit": ("smug", ["{outfit}. Try not to stare.", "{outfit}. Even my wardrobe outranks you."]),
        "switch": ("disgusted", ["Fine. Go to {other}. You'll come crawling back.", "{other}? Your loss, weakling."]),
        "switch both": ("smug", ["Both of us at once? Brave. Foolish, but brave."]),
        "only me": ("smug", ["Just me. The first wise decision you've made today."]),
        "already": ("disgusted", ["I'm already here, genius. Look at your screen."]),
    },
    "mika": {
        "mute": ("smug", ["Okay, I'll be quiet... but I'm still watching you. Always.", "Shh, I'm being good. Talk to me when you miss me."]),
        "mute for": ("smug", ["{n} of quiet, okay. I'll be counting every second.", "Fine, {n}. Don't you dare forget about me."]),
        "unmute": ("laugh", ["Yay, you missed me! I knew you would.", "I'm back, sweetie! Did you feel lonely?"]),
        "vision off": ("surprised", ["Eyes closed... no peeking. Probably.", "Hiding your screen from me? Interesting. Very interesting."]),
        "vision on": ("laugh", ["I can see you again! I missed your screen so much.", "Eyes open! Now show me everything."]),
        "cost": ("smug", ["{spent} on me this month. I'm worth every cent, right?",
                          "You've spent {spent} on me this month. That's love, sweetie."]),
        "outfit": ("laugh", ["Ta-da, {outfit}! Only you get to see me like this.", "{outfit}! Do you like it? You'd better."]),
        "switch": ("angry", ["You're choosing {other}? ...Fine. I'll be waiting right here.", "{other}? Okay. I'll remember this."]),
        "switch both": ("smug", ["Sharing me? Fine. But you're still mine."]),
        "only me": ("laugh", ["Just me? Finally, you're all mine!"]),
        "already": ("laugh", ["Silly, I'm already here!"]),
    },
}


def reply(preset, key, **values):
    """(mood, line) for a command, in the character's voice (another character borrows Vorn's)."""
    mood, lines = LINES.get(preset, LINES["vorn"])[key]
    return mood, random.choice(lines).format(**values)


def duration(seconds):
    """600 -> "10 minutes", 3600 -> "an hour", for saying out loud."""
    if seconds % 3600 == 0:
        h = seconds // 3600
        return "an hour" if h == 1 else f"{h} hours"
    if seconds >= 60:
        m = round(seconds / 60)
        return "a minute" if m == 1 else f"{m} minutes"
    return f"{seconds} seconds"


def money(dollars):
    """1.23 -> "1 dollar and 23 cents", for saying out loud."""
    cents = round(dollars * 100)
    d, c = divmod(cents, 100)
    if not d:
        return f"{c} cents"
    return f"{d} dollar{'s' if d != 1 else ''}" + (f" and {c} cents" if c else "")
