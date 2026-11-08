"""Claude looks at the screenshots plus memory and decides what Vorn says, with which face, and what to remember."""
import json
import logging
import os
from pathlib import Path

import anthropic

import config
from character import MOODS

KEY_FILE = Path(__file__).with_name("api_key.txt")
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
        system=config.PERSONA.replace("{name}", config.NAME),  # replace, not format: an edited persona may contain braces
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": content}],
        **extra,
    )
    spent = cost(model, r.usage)
    if r.stop_reason == "refusal":
        return None, spent
    # shortcut: a pause_turn from a very long web search isn't resumed; max_uses=2 keeps that rare
    return json.loads([b.text for b in r.content if b.type == "text"][-1]), spent  # the JSON answer is the last text block


def think(client, model, context, recent, situation, jpegs, search=False):
    text = f"{context}\n\nRecent dialogue (oldest first):\n" + ("\n".join(recent) or "(nothing yet)") + f"\n\nRight now: {situation}"
    if not jpegs:
        text += "\n(The player has paused your vision, so you can't see the screen right now.)"
    elif len(jpegs) > 1:
        text += f"\n(The {len(jpegs)} images are the player's displays, left to right. The game is usually on one of them.)"
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": j}} for j in jpegs]
    content.append({"type": "text", "text": text})
    tools = WEB_SEARCH if search and "haiku" not in model else None
    try:
        out, spent = _ask(client, model, content, SCHEMA, tools)
    except anthropic.BadRequestError:
        if not tools:
            raise
        logging.warning("web search unavailable, answering without it", exc_info=True)
        out, spent = _ask(client, model, content, SCHEMA)
    return out or QUIET_REPLY, spent


def report(client, model, session_text):
    """Battle report on the previous session, read out at the start of the next one. Returns (text, dollars)."""
    ask = (f"{session_text}\n\nWrite your battle report on that session: 2 or 3 short, savage sentences in character, "
           "under 60 words, no markdown. It will be read aloud at the start of their next session.")
    out, spent = _ask(client, model, [{"type": "text", "text": ask}], REPORT_SCHEMA)
    return (out["report"] if out else ""), spent
