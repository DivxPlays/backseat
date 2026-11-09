"""Holidays: festive outfits that switch in by themselves (when the outfit is on "Surprise me"), lines that fit the
season, and a little weather around them (bats, snow, confetti, hearts). Your birthday is the BIRTHDAY setting.
"""
from datetime import date

# key: (first day, last day, the day itself) as (month, day), what's going on, the weather
HOLIDAYS = {
    "halloween": ((10, 25), (11, 1), (10, 31), "Halloween", "bats"),
    "christmas": ((12, 1), (12, 26), (12, 25), "Christmas", "snow"),
    "new year": ((12, 31), (1, 1), (1, 1), "New Year's", "confetti"),
    "valentine": ((2, 14), (2, 14), (2, 14), "Valentine's Day", "hearts"),
}


def birthday_of(text):
    """"02-10" -> (2, 10); anything else -> None."""
    try:
        month, day = (int(x) for x in text.strip().split("-"))
        date(2000, month, day)  # 2000 is a leap year, so 02-29 counts
        return month, day
    except (ValueError, AttributeError):
        return None


def today(birthday="", day=None):
    """(key, what to tell them, weather) for what's on today, or None. Your birthday wins over a holiday."""
    d = day or date.today()
    md = (d.month, d.day)
    if birthday_of(birthday) == md:
        return "birthday", "Today is the player's birthday. If you're greeting them, start with that, in character.", "confetti"
    for key, (first, last, main, name, weather) in HOLIDAYS.items():
        if (first <= md <= last) if first <= last else (md >= first or md <= last):  # New Year's runs over the year's end
            when = f"Today is {name} itself" if md == main else f"It's the {name} season"
            return key, f"{when}. Work it into a line now and then, in character (not every line).", weather
    return None
