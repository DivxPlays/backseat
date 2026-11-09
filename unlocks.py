"""Outfits you earn: by hours played with them watching, times you've talked to them, days in a row, or respect.
Earned once, kept for good (even if respect drops later). The goals are in each character's UNLOCKS table.
"""
from datetime import date, timedelta

DAY = 600  # seconds of play that make a day count toward a streak
UNIT = {"hours": "hours", "talks": "talks", "streak": "days in a row", "respect": "respect"}


def streak(days, today=None):
    """Days in a row you've played (10+ minutes each), up to today. Today not being played yet doesn't break it."""
    d = today or date.today()
    if days.get(d.isoformat(), 0) < DAY:
        d -= timedelta(days=1)
    n = 0
    while days.get(d.isoformat(), 0) >= DAY:
        n, d = n + 1, d - timedelta(days=1)
    return n


def stats(shared, mind, today=None):
    """What counts toward unlocks. shared: the whole memory (your time is shared); mind: that character's own memory."""
    return {"hours": shared.get("total_seconds", 0) / 3600, "talks": mind.get("talks", 0),
            "streak": streak(shared.get("days", {}), today), "respect": mind.get("respect", 0)}


def due(goals, earned, have):
    """Outfits whose goal you've reached that aren't earned yet."""
    return [o for o, (kind, need) in goals.items() if o not in earned and have[kind] >= need]


def progress(kind, have, need):
    """"3.2 of 10 hours", "12 of 100 talks", "2 of 7 days in a row", "64 of 100 respect" (tray menu, and their replies)."""
    return f"{have:.1f} of {need} {UNIT[kind]}" if kind == "hours" else f"{int(have)} of {need} {UNIT[kind]}"
