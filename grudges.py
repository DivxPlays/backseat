"""Grudges that stick: rage-quit right after a loss, ignore them for days, or keep telling them to shut up, and they hold
it against you next time: a cold greeting, digs about it, a hit to respect. An apology ends it; so do two days.
"""
from datetime import datetime, timedelta

HOLD = timedelta(days=2)  # how long a grudge lasts without an apology
IGNORED = 3  # days away that count as ignoring them
SHUSHED = 3  # "shut up"s in one session that count
QUIT = 180  # seconds of play after a death or loss within which ending the session counts as a rage-quit
COST = 3  # respect each new grudge costs


def new(prev, last_with, now):
    """Grudges from how you left things. prev: their last session (or None); last_with: when they were last on screen."""
    why = []
    if prev and prev.get("loss") and prev.get("seconds", 0) - prev.get("loss_at", -1e9) <= QUIT:
        why.append(f"rage-quitting right after a {prev['loss']} last time")
    if prev and prev.get("shushed", 0) >= SHUSHED:
        why.append(f"being told to shut up {prev['shushed']} times last time")
    if last_with:
        days = (now - datetime.fromisoformat(last_with)).days
        if days >= IGNORED:
            why.append(f"being ignored for {days} days")
    return [{"why": w, "since": now.isoformat(timespec="minutes"), "until": (now + HOLD).isoformat(timespec="minutes")}
            for w in why]


def active(held, now):
    """The grudges still held (not yet expired)."""
    return [g for g in held if datetime.fromisoformat(g["until"]) > now]
