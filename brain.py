"""Claude looks at the screenshots plus memory and decides what Vorn says, with which face, and what to remember."""
import json
import logging
import os
import re
import urllib.request
from pathlib import Path

import anthropic

import config
from character import MOODS

KEY_FILE = Path(__file__).with_name("api_key.txt")
OLLAMA = "http://127.0.0.1:11434"  # the local model server, only used when LOCAL_MODEL is set
EVENTS = ["none", "death", "win", "loss", "fail", "epic", "menu"]
SCHEMA = {
    "type": "object",
    "properties": {
        "mood": {"type": "string", "enum": list(MOODS)},
        "line": {"type": "string"},
        "event": {"type": "string", "enum": EVENTS},
        "respect": {"type": "string", "enum": ["down", "same", "up"]},
        "save_moment": {"type": "boolean"},
        "remember": {"type": "string"},
        "game_note": {"type": "string"},
        "killer": {"type": "string"},
        "lore": {"type": "string"},
    },
    "required": ["mood", "line", "event", "respect", "save_moment", "remember", "game_note", "killer", "lore"],
    "additionalProperties": False,
}
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}  # $ per million tokens


def cost(model, usage):
    """Dollar estimate for one call from its token counts (unknown models priced like Opus, to err high)."""
    p_in, p_out = PRICES.get(model, PRICES["claude-opus-5-5"])
    tokens_in = (usage.input_tokens or 0) + 1.25 * (getattr(usage, "cache_creation_input_tokens", 0) or 0) \
        + 0.1 * (getattr(usage, "cache_read_input_tokens", 0) or 0)
    searches = getattr(getattr(usage, "server_tool_use", None), "web_search_requests", 0) or 0
    return (tokens_in * p_in + (usage.output_tokens or 0) * p_out) / 1e6 + searches * 0.01  # web search: $10 per 1,000
REPORT_SCHEMA = {"type": "object", "properties": {"report": {"type": "string"}}, "required": ["report"], "additionalProperties": False}
WEB_SEARCH = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 2}]
QUIET_REPLY = {"mood": "disgusted", "line": "Hmph. Not worth my breath.", "event": "none", "respect": "same",
               "save_moment": False, "remember": "", "game_note": "", "killer": "", "lore": ""}


SWEARING = ("\n\nLanguage: swear freely (fuck, shit, bitch, ass, damn): the player and their friends want it raw and asked for it. "
            "Never slurs, and never mock real-world identity.")


DUO_RULES = """Duo mode: you write both characters. Instead of a single line and mood, fill "turns": short lines (each under 20 words) between {a} and {b}, as one exchange, as many lines as the moment asks for (usually 1 to 3; when it says so, a longer back-and-forth where they really go at each other). When someone talks to one of them by name, only that one speaks (one turn) and the other stays silent. Otherwise they react to each other: when one is hard on the player, the other takes the player's side in their own way, and they snipe at each other. Each stays fully in character, and each one's past, powers and story are theirs alone: {a} never claims {b}'s, and {b} never claims {a}'s. "remember" is a fact either of them learned; a turn's "lore" is a new fact from that speaker's own past, usually empty. The line rules above apply to every turn."""


def partner():
    """The other character's preset when duo mode is on (both on screen), else None."""
    if not config.DUO:
        return None
    name = "mika" if config.PRESET == "vorn" else "vorn"
    try:
        return {**json.loads((config.PRESETS / f"{name}.json").read_text(encoding="utf-8")), "PRESET": name}
    except (OSError, ValueError):
        return None


def me():
    """The current character, in the shape of a preset."""
    return {"NAME": config.NAME, "PERSONA": config.PERSONA, "POWER": config.POWER}


def system(only=None):
    """The system prompt; `only` (a preset) voices just that character, even in duo mode."""
    # replace, not format: an edited persona may contain braces
    other = None if only else partner()
    if not other:
        c = only or me()
        text = (c["PERSONA"] + "\n\n" + config.RULES).replace("{name}", c["NAME"]).replace("{power}", c["POWER"])
    else:
        a, b = config.NAME, other["NAME"]
        text = (f"You voice two characters who share a small window in the corner of the player's screen: {a} and {b}.\n\n"
                f"=== {a} ===\n" + config.PERSONA.replace("{name}", a) + f"\n\n=== {b} ===\n" + other["PERSONA"].replace("{name}", b)
                + "\n\n" + config.RULES.replace("{name}", f"{a} or {b}").replace("{power}", f"{config.POWER} ({a}) or {other['POWER']} ({b})")
                + "\n\n" + DUO_RULES.replace("{a}", a).replace("{b}", b))
    return text + (SWEARING if config.SWEAR else "")


def schema():
    """The reply format: one line, or in duo mode a few turns between the two characters."""
    other = partner()
    if not other:
        return SCHEMA
    rest = {k: v for k, v in SCHEMA["properties"].items() if k not in ("line", "mood", "lore")}
    turn = {"type": "object", "properties": {"speaker": {"type": "string", "enum": [config.NAME, other["NAME"]]},
                                             "mood": SCHEMA["properties"]["mood"], "line": {"type": "string"},
                                             "lore": {"type": "string"}},  # per turn: a story belongs to whoever told it
            "required": ["speaker", "mood", "line", "lore"], "additionalProperties": False}
    return {"type": "object", "properties": {"turns": {"type": "array", "items": turn}, **rest},
            "required": ["turns"] + [k for k in SCHEMA["required"] if k in rest], "additionalProperties": False}


def make_client():
    key = os.environ.get("ANTHROPIC_API_KEY") or (KEY_FILE.read_text(encoding="utf-8").strip() if KEY_FILE.exists() else "")
    return anthropic.Anthropic(api_key=key, timeout=60, max_retries=1) if key else None


def _ask(client, model, content, schema, tools=None):
    # Haiku has no server-side refusal fallback; the other models re-run a declined request on a fallback model
    extra = {} if "haiku" in model else {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    if tools:
        extra["tools"] = tools
    r = client.beta.messages.create(
        model=model,
        max_tokens=4000,
        system=system(),
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": content}],
        **extra,
    )
    spent = cost(model, r.usage)
    if r.stop_reason == "refusal":
        return None, spent
    # shortcut: a pause_turn from a very long web search isn't resumed; max_uses=2 keeps that rare
    return json.loads([b.text for b in r.content if b.type == "text"][-1]), spent  # the JSON answer is the last text block


def prompt(context, recent, situation, jpegs):
    text = f"{context}\n\nRecent dialogue (oldest first):\n" + ("\n".join(recent) or "(nothing yet)") + f"\n\nRight now: {situation}"
    if not jpegs:
        text += "\n(The player has paused your vision, so you can't see the screen right now.)"
    elif len(jpegs) > 1:
        text += f"\n(The {len(jpegs)} images are the player's displays, left to right. The game is usually on one of them.)"
    return text


def local_think(model, context, recent, situation, jpegs, only=None):
    """think() on a free vision model running on this PC through Ollama. Returns (reply, 0.0); raises if Ollama fails.
    `only` (a preset, duo mode) voices just that one character: given both, the small model mixes up whose past is whose."""
    if only:  # "You (Mika): ..." would tell a model voicing Vorn that he said it
        recent = [re.sub(r"^You \((.+?)\): ", r"\1: ", r) for r in recent]
    form = SCHEMA if only else schema()
    body = {"model": model, "stream": False, "format": form, "keep_alive": "15m", "options": {"num_predict": 500},
            "messages": [{"role": "system", "content": system(only)},
                         {"role": "user", "content": prompt(context, recent, situation, jpegs), "images": jpegs}]}
    req = urllib.request.Request(f"{OLLAMA}/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:  # the first call also loads the model onto the GPU
        out = json.loads(json.loads(r.read())["message"]["content"])
    out = {**QUIET_REPLY, **{k: v for k, v in out.items() if k in form["properties"]}}
    if only:
        out["turns"] = [{"speaker": only["NAME"], "mood": out["mood"], "line": out["line"], "lore": ""}]
    return out, 0.0


def start_ollama():
    """Start the Ollama app if it's installed but not running (it runs the local model)."""
    try:
        urllib.request.urlopen(f"{OLLAMA}/api/version", timeout=2).close()
    except OSError:
        app = Path(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama app.exe")
        if app.exists():
            os.startfile(app)


def think(client, model, context, recent, situation, jpegs, search=False):
    text = prompt(context, recent, situation, jpegs)
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": j}} for j in jpegs]
    content.append({"type": "text", "text": text})
    tools = WEB_SEARCH if search and "haiku" not in model else None
    try:
        out, spent = _ask(client, model, content, schema(), tools)
    except anthropic.BadRequestError:
        if not tools:
            raise
        logging.warning("web search unavailable, answering without it", exc_info=True)
        out, spent = _ask(client, model, content, schema())
    return out or QUIET_REPLY, spent


def report(client, model, session_text):
    """Battle report on the previous session, read out at the start of the next one. Returns (text, dollars)."""
    ask = (f"{session_text}\n\nWrite your battle report on that session: 2 or 3 short, savage sentences in character, "
           "under 60 words, no markdown. It will be read aloud at the start of their next session.")
    out, spent = _ask(client, model, [{"type": "text", "text": ask}], REPORT_SCHEMA)
    return (out["report"] if out else ""), spent


SONG_SCHEMA = {"type": "object", "properties": {"note": {"type": "string"}}, "required": ["note"], "additionalProperties": False}
def look_up_song(client, model, artist, song):
    """Learn about a song with one web search (about a cent on Haiku: the search fee is most of it; ~9 cents on Sonnet).
    Returns (a short note, dollars)."""
    ask = (f'Look up the song "{song}" by {artist} with web search. In under 35 words, as plain notes (not in character): '
           "what it is (genre, year, album), what it's about, and one notable thing about the artist. If you can't find it, "
           "say the little you can.")
    tool = "web_search_20250305" if "haiku" in model else "web_search_20260209"  # Haiku only runs the basic search tool
    try:
        out, spent = _ask(client, model, [{"type": "text", "text": ask}], SONG_SCHEMA, [{"type": tool, "name": "web_search", "max_uses": 1}])
    except anthropic.BadRequestError:  # no web search on this model: what it knows without one
        logging.warning("web search unavailable for a song, answering without it", exc_info=True)
        out, spent = _ask(client, model, [{"type": "text", "text": ask}], SONG_SCHEMA)
    return (out["note"].strip() if out else ""), spent


GAME_SCHEMA = {"type": "object", "properties": {"profile": {"type": "string"}}, "required": ["profile"], "additionalProperties": False}


def look_up_game(client, model, game):
    """A game profile from one web search (about a cent on Haiku): what it is and what good players do.
    Returns (the profile, dollars)."""
    ask = (f'Look up the video game "{game}" with web search (search for that exact title; a newer game with a similar name '
           "is a different game). In under 80 words, as plain notes (not in character): genre and modes; its main maps or "
           "levels; its weapons, classes or characters worth knowing; and three concrete things good players do. If the "
           "search only finds other games, use what you know about this one. Write only the notes: no remarks about the "
           "search.")
    tool = "web_search_20250305" if "haiku" in model else "web_search_20260209"  # Haiku only runs the basic search tool
    try:
        out, spent = _ask(client, model, [{"type": "text", "text": ask}], GAME_SCHEMA, [{"type": tool, "name": "web_search", "max_uses": 1}])
    except anthropic.BadRequestError:  # no web search on this model: what it knows without one
        logging.warning("web search unavailable for a game, answering without it", exc_info=True)
        out, spent = _ask(client, model, [{"type": "text", "text": ask}], GAME_SCHEMA)
    return (out["profile"].strip() if out else ""), spent


MINIGAME_SCHEMA = {"type": "object", "properties": {"mood": SCHEMA["properties"]["mood"], "line": {"type": "string"},
                                                    "answer": {"type": "string"}},
                   "required": ["mood", "line", "answer"], "additionalProperties": False}


def minigame(client, model, name, game, kind, about="", topic="", avoid=()):
    """A mini-game for a menu or queue, from `name`: a trivia question about `game` (answer: the right answer) or a dare
    for their next match (answer: the dare, plainly). about: their profile of the game; topic: what to ask about;
    avoid: answers already asked. Returns (reply, dollars)."""
    if kind == "trivia":
        ask = (f"Mini-game while the player sits in a menu. As {name}, in character, ask them one short trivia question about "
               f"{game} (or about gaming in general if you don't know {game} well), under 25 words. Pick a question with one "
               "clear answer you're sure of. answer: the correct answer, short.")
        if about:
            ask += (f" Ask about one {topic or 'fact'} named in what you know about {game} below, and make the answer exactly "
                    f"that name, word for word as written there; nothing made up, nothing about order or rankings: {about}")
        if avoid:
            ask += " Don't ask anything whose answer is one of these (already asked): " + ", ".join(avoid) + "."
    else:
        ask = (f"Mini-game while the player sits in a menu. As {name}, in character, dare them to do one specific thing in "
               f"their next match of {game}, under 20 words. answer: the dare itself, short and plain (to check it later).")
        if about:
            ask += f" What you know about {game} (use its real maps, weapons or modes): {about}"
    return _ask(client, model, [{"type": "text", "text": ask}], MINIGAME_SCHEMA)


COACH_SCHEMA = {"type": "object", "properties": {"headline": {"type": "string"}, "better": {"type": "string"},
                                                 "worse": {"type": "string"}, "tips": {"type": "array", "items": {"type": "string"}}},
                "required": ["headline", "better", "worse", "tips"], "additionalProperties": False}


def coach(client, model, facts):
    """The weekly coaching report from `facts` (both weeks' numbers and their notes on your play). Returns (report, dollars)."""
    ask = (f"{facts}\n\nWrite this week's coaching report on the player, as yourself: in character, but genuinely useful, and "
           "grounded only in the facts above (no made-up stats). headline: one savage sentence summing up their week. better: "
           "one sentence on what improved (or that nothing did). worse: one sentence on what got worse. tips: exactly 3 "
           "concrete, specific tips for next week (their games, habits, breaks), each under 25 words. No markdown.")
    out, spent = _ask(client, model, [{"type": "text", "text": ask}], COACH_SCHEMA)
    if out:
        out["tips"] = [t.strip() for t in out["tips"] if t.strip()][:3]
    return out, spent


PROFILE_SCHEMA = {"type": "object", "properties": {"profile": {"type": "string"}}, "required": ["profile"], "additionalProperties": False}


def condense(client, model, profile, notes):
    """Fold old notes into the long-term profile of the player (so nothing lasting is lost). Returns (profile, dollars)."""
    ask = ("Your current long-term picture of the player:\n" + (profile or "(empty)") + "\n\nOlder notes you took about them:\n"
           + "\n".join(f"- {n}" for n in notes)
           + "\n\nRewrite the long-term picture so it keeps everything lasting from these notes: their name, preferences, skills, "
             "habits, favourite games and gear, running jokes, friends. Drop anything that was only true at the moment (what they "
             "were doing, the time) and duplicates. Write it as plain notes, not in character: plain sentences, under 120 words.")
    out, spent = _ask(client, model, [{"type": "text", "text": ask}], PROFILE_SCHEMA)
    return (out["profile"] if out else profile), spent
