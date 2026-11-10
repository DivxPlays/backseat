"""Holidays: festive outfits that switch in by themselves (when the outfit is on "Surprise me"), lines that fit the
season, and a little weather around them (bats, snow, confetti, hearts, clovers, petals, leaves, lanterns). Your
birthday is the BIRTHDAY setting.
"""
from datetime import date, timedelta

# shortcut: a table, not the lunar calendar; the self-check fails once next year isn't in it, as a reminder to add more
LUNAR_NEW_YEAR = {2026: (2, 17), 2027: (2, 6), 2028: (1, 26), 2029: (2, 13), 2030: (2, 3), 2031: (1, 23), 2032: (2, 11),
                  2033: (1, 31), 2034: (2, 19), 2035: (2, 8), 2036: (1, 28), 2037: (2, 15)}


def easter(year):
    """Easter Sunday (the anonymous Gregorian algorithm)."""
    a, (b, c) = year % 19, divmod(year, 100)
    d, e = divmod(b, 4)
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 (the algorithm's own name)
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def thanksgiving(year):
    """The fourth Thursday of November (US)."""
    first = date(year, 11, 1)
    return first + timedelta(days=(3 - first.weekday()) % 7 + 21)


def calendar(year):
    """{key: (first day, last day, the day itself, name, weather)} for `year`, first match wins (New Year's runs into the
    next year; Thanksgiving comes before Christmas, which can start the Monday after it)."""
    def around(day, before, after):
        return day - timedelta(days=before), day + timedelta(days=after), day

    days = {
        "valentine": (date(year, 2, 12), date(year, 2, 14), date(year, 2, 14), "Valentine's Day", "hearts"),
        "st patrick": (date(year, 3, 15), date(year, 3, 17), date(year, 3, 17), "St. Patrick's Day", "clovers"),
        "easter": (*around(easter(year), 2, 1), "Easter", "petals"),
        "halloween": (date(year, 10, 25), date(year, 11, 1), date(year, 10, 31), "Halloween", "bats"),
        "thanksgiving": (*around(thanksgiving(year), 3, 3), "Thanksgiving", "leaves"),
        "christmas": (date(year, 12, 1), date(year, 12, 26), date(year, 12, 25), "Christmas", "snow"),
        "new year": (date(year, 12, 31), date(year + 1, 1, 1), date(year + 1, 1, 1), "New Year's", "confetti"),
    }
    if year in LUNAR_NEW_YEAR:
        days["lunar new year"] = (*around(date(year, *LUNAR_NEW_YEAR[year]), 1, 6), "Lunar New Year", "lanterns")
    return days


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
    if birthday_of(birthday) == (d.month, d.day):
        return "birthday", "Today is the player's birthday. If you're greeting them, start with that, in character.", "confetti"
    on = [(key, main, name, weather) for year in (d.year, d.year - 1)  # (last year's New Year's ends on January 1)
          for key, (first, last, main, name, weather) in calendar(year).items() if first <= d <= last]
    if not on:
        return None
    key, main, name, weather = next((h for h in on if h[1] == d), on[0])  # a holiday's own day beats another's season
    when = f"Today is {name} itself" if d == main else f"It's the {name} season"
    return key, f"{when}. Work it into a line now and then, in character (not every line).", weather
