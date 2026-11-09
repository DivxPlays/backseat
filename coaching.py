"""Weekly coaching report: this week against last week from what they've tracked (time, where it went, score, when you
play), plus a headline and tips Claude writes once a week from their notes about your play. A page next to the weekly
highlights, in the Hall of Shame folder (which stays on your PC).
"""
import html
from datetime import datetime, time, timedelta

import config
from memory import fmt

EVERY = timedelta(days=7)  # a new report at most this often
MIN_PLAY = 1800  # seconds played in the week before there's anything to coach
GOLD, INK, DIM, GRID, CARD = "#f2c64d", "#f1e9df", "#a89a90", "#3a2e33", "#211a1f"
GOOD, BAD = "#5bd18b", "#ff7a7a"


def sessions_of(d):
    """Every character's sessions (each one's own list; in duo mode only the current one records)."""
    out = list(d.get("sessions", []))
    for mind in d.get("characters", {}).values():
        out += mind.get("sessions", [])
    return out


def week_stats(d, last_day, n=7):
    """Totals for the n calendar days up to last_day (a date, included): time per day, per app and per hour of the day,
    sessions and score."""
    days = [last_day - timedelta(days=n - 1 - i) for i in range(n)]
    start, end = datetime.combine(days[0], time()), datetime.combine(last_day + timedelta(days=1), time())
    per_day = [d.get("days", {}).get(day.isoformat(), 0.0) for day in days]
    apps, hours, events, lengths, late = {}, [0.0] * 24, {}, [], 0
    for s in sessions_of(d):
        begun = datetime.fromisoformat(s["start"])
        if not start <= begun < end or s.get("seconds", 0) < 60:
            continue
        lengths.append(s["seconds"])
        late += begun.hour < 5
        for app, sec in s.get("apps", {}).items():
            apps[app] = apps.get(app, 0.0) + sec
        for kind, n in s.get("events", {}).items():
            events[kind] = events.get(kind, 0) + n
        left, hour, offset = s["seconds"], begun.hour, begun.minute * 60  # spread over the hours it ran
        while left > 0:
            take = min(left, 3600 - offset)
            hours[hour] += take
            left, hour, offset = left - take, (hour + 1) % 24, 0
    return {"days": days, "per_day": per_day, "played": sum(per_day), "apps": sorted(apps.items(), key=lambda kv: -kv[1]),
            "hours": hours, "events": events, "sessions": len(lengths), "longest": max(lengths, default=0), "late": late}


def summary(this, last):
    """The two weeks as plain text, for Claude to coach from."""
    def line(w, label):
        score = ", ".join(f"{n} {k}" for k, n in w["events"].items()) or "nothing scored"
        top = ", ".join(f"{a} {fmt(s)}" for a, s in w["apps"][:5]) or "nothing"
        return (f"{label}: played {fmt(w['played'])} over {w['sessions']} sessions (longest {fmt(w['longest'])}, "
                f"{w['late']} started after midnight). Time went to: {top}. Score: {score}.")
    return line(this, "This week") + "\n" + line(last, "Last week")


def due(d, now):
    """True when it's time for a new report: a week since the last one, and enough play to talk about."""
    reports = d.get("coaching", [])
    if reports and now - datetime.fromisoformat(reports[-1]["made"]) < EVERY:
        return False
    return week_stats(d, now.date())["played"] >= MIN_PLAY


# ------------------------------------------------------------------ the page
CSS = f"""
:root {{ --bg:#141016; --card:{CARD}; --ink:{INK}; --dim:{DIM}; --gold:{GOLD}; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.5 "Segoe UI", system-ui, sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:32px 16px 64px; }}
h1 {{ margin:0 0 4px; font-size:34px; }} h1 span {{ color:var(--gold); }}
h2 {{ font-size:18px; margin:0 0 12px; }}
.sub {{ color:var(--dim); margin:0 0 24px; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:12px; margin-bottom:24px; }}
.stat, .card {{ background:var(--card); border:1px solid {GRID}; border-radius:12px; padding:14px 16px; }}
.stat b {{ display:block; font-size:26px; font-weight:600; }}
.stat small {{ color:var(--dim); }}
.delta {{ display:block; font-size:13px; color:var(--dim); }}
.delta i {{ font-style:normal; font-weight:700; }}
.coach {{ margin-bottom:24px; }}
.coach q {{ display:block; font-size:21px; font-weight:600; margin-bottom:10px; quotes:"\\201C" "\\201D"; }}
.coach li {{ margin:4px 0; }}
.charts {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:16px; }}
svg {{ display:block; width:100%; height:auto; }}
svg text {{ fill:var(--dim); font:12px "Segoe UI", system-ui, sans-serif; }}
svg .val {{ fill:var(--ink); font-weight:600; }}
svg rect.bar:hover {{ opacity:.8; }}
details {{ margin-top:8px; color:var(--dim); font-size:13px; }}
table {{ border-collapse:collapse; margin-top:6px; }} td, th {{ padding:2px 10px 2px 0; text-align:left; }}
.empty {{ color:var(--dim); font-style:italic; }}
"""


def bar(x, y, w, h, tip):
    """A bar growing up from the baseline: 4px rounded top, square bottom, a hover tooltip."""
    r = min(4, w / 2, h)
    path = (f"M{x:.1f},{y + h:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} H{x + w - r:.1f} "
            f"Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} V{y + h:.1f} Z")
    return f'<path class="bar" d="{path}" fill="{GOLD}"><title>{html.escape(tip)}</title></path>'


def columns(values, labels, tips, ref=None, every=1):
    """Columns (≤ 24 px, 2 px apart), hairline gridlines, the tallest labelled, an optional reference line (its meaning
    goes in the chart's title: a label on the plot would sit on the bars)."""
    W, H, left, bottom, top = 520, 200, 40, 24, 16
    peak = max(values + [ref or 0, 1e-9])
    step = next(s for s in (0.25, 0.5, 1, 2, 4, 6, 8, 12, 24, 48) if peak / s <= 4)
    scale = (H - bottom - top) / (step * (int(peak / step) + 1))
    band = (W - left) / len(values)
    w = min(24, band - 2)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img">']
    for i in range(int(peak / step) + 2):
        y = H - bottom - i * step * scale
        if y < top - 1:
            break
        out.append(f'<line x1="{left}" x2="{W}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>'
                   f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{i * step:g}</text>')
    best = max(range(len(values)), key=lambda i: values[i])
    for i, v in enumerate(values):
        x, h = left + i * band + (band - w) / 2, v * scale
        if h > 0.5:
            out.append(bar(x, H - bottom - h, w, h, tips[i]))
        if i == best and v > 0:
            out.append(f'<text class="val" x="{x + w / 2:.1f}" y="{H - bottom - h - 5:.1f}" text-anchor="middle">{v:.1f}</text>')
        if i % every == 0:
            out.append(f'<text x="{x + w / 2:.1f}" y="{H - 6}" text-anchor="middle">{html.escape(labels[i])}</text>')
    if ref:
        y = H - bottom - ref * scale
        out.append(f'<line x1="{left}" x2="{W}" y1="{y:.1f}" y2="{y:.1f}" stroke="{DIM}" stroke-width="1"/>')
    return "".join(out) + "</svg>"


def bars(items, tips):
    """Horizontal bars (≤ 24 px thick), the value at each tip."""
    W, row, left = 520, 30, 130
    H = max(row * len(items), row)
    peak = max([v for _, v in items] + [1e-9])
    out = [f'<svg viewBox="0 0 {W} {H}" role="img">']
    for i, ((name, v), tip) in enumerate(zip(items, tips)):
        y, w = i * row + 4, (W - left - 70) * v / peak
        out.append(f'<text x="{left - 8}" y="{y + 15}" text-anchor="end">{html.escape(name[:18])}</text>')
        if w > 0.5:
            r = min(4, w)
            out.append(f'<path class="bar" d="M{left},{y} H{left + w - r:.1f} Q{left + w:.1f},{y} {left + w:.1f},{y + r} '
                       f'V{y + 22 - r} Q{left + w:.1f},{y + 22} {left + w - r:.1f},{y + 22} H{left} Z" fill="{GOLD}">'
                       f'<title>{html.escape(tip)}</title></path>')
        out.append(f'<text class="val" x="{left + w + 6:.1f}" y="{y + 15}">{html.escape(tip.split(": ")[-1])}</text>')
    return "".join(out) + "</svg>"


def table(rows):
    return ("<details><summary>Show as a table</summary><table>"
            + "".join(f"<tr><td>{html.escape(a)}</td><td>{html.escape(b)}</td></tr>" for a, b in rows) + "</table></details>")


def delta(now, before, good_when_up, as_time=False):
    """"▲ 2.1 h vs last week", coloured by whether that's good, with the arrow so it isn't colour alone."""
    if now == before:
        return '<span class="delta">same as last week</span>'
    up = now > before
    color = GOOD if up == good_when_up else BAD
    size = fmt(abs(now - before)) if as_time else f"{abs(now - before):g}"
    return f'<span class="delta"><i style="color:{color}">{"▲" if up else "▼"} {size}</i> vs last week</span>'


def build(d, report, folder, now=None):
    """Write `coaching.html` into the Hall of Shame folder; returns its path. report: Claude's latest, or None."""
    now = now or datetime.now()
    this, last = week_stats(d, now.date()), week_stats(d, now.date() - EVERY)
    ev, lev = this["events"], last["events"]
    tiles = [(fmt(this["played"]), "played", delta(this["played"], last["played"], True, True)),
             (str(this["sessions"]), "sessions", delta(this["sessions"], last["sessions"], True)),
             (fmt(this["longest"]), "longest session", delta(this["longest"], last["longest"], False, True)),
             (str(ev.get("death", 0)), "deaths", delta(ev.get("death", 0), lev.get("death", 0), False)),
             (str(ev.get("win", 0)), "wins", delta(ev.get("win", 0), lev.get("win", 0), True)),
             (str(ev.get("loss", 0)), "losses", delta(ev.get("loss", 0), lev.get("loss", 0), False))]
    if report:
        coach = (f'<div class="card coach"><h2>{html.escape(config.NAME)}\'s verdict</h2><q>{html.escape(report["headline"])}</q>'
                 f'<p><b>Better:</b> {html.escape(report["better"])}<br><b>Worse:</b> {html.escape(report["worse"])}</p>'
                 "<ol>" + "".join(f"<li>{html.escape(t)}</li>" for t in report["tips"]) + "</ol></div>")
    else:
        coach = (f'<div class="card coach"><p class="empty">No verdict yet: {html.escape(config.NAME)} writes one once you\'ve '
                 f"played {MIN_PLAY // 60} minutes in a week, then every 7 days.</p></div>")
    hours = [h / 3600 for h in this["per_day"]]
    avg_last = last["played"] / 7 / 3600
    day_chart = columns(hours, [day.strftime("%a") for day in this["days"]],
                        [f"{day:%a %b %d}: {fmt(s)}" for day, s in zip(this["days"], this["per_day"])],
                        avg_last if last["played"] else None)
    day_title = "Hours played each day" + (f" (the line: last week's average, {avg_last:.1f} h)" if last["played"] else "")
    top = this["apps"][:6]
    app_chart = bars([(a, s / 3600) for a, s in top], [f"{a}: {fmt(s)}" for a, s in top]) if top else '<p class="empty">Nothing yet.</p>'
    hour_chart = columns([h / 3600 for h in this["hours"]], [f"{h:02d}" for h in range(24)],
                         [f"{h:02d}:00-{h:02d}:59: {fmt(s)}" for h, s in enumerate(this["hours"])], every=3)
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, '
            f'initial-scale=1"><title>Coaching report</title><style>{CSS}</style></head><body><main>'
            f"<h1><span>{html.escape(config.NAME)}'s</span> coaching report</h1>"
            f'<p class="sub">{this["days"][0]:%b %d} to {this["days"][-1]:%b %d}, against the 7 days before.</p>' + coach
            + '<div class="stats">' + "".join(f'<div class="stat"><b>{html.escape(v)}</b><small>{html.escape(k)}</small>{dl}</div>'
                                              for v, k, dl in tiles) + "</div>"
            + '<div class="charts">'
            + f'<div class="card"><h2>{html.escape(day_title)}</h2>{day_chart}'
            + table([(f"{day:%a %b %d}", fmt(s)) for day, s in zip(this["days"], this["per_day"])]) + "</div>"
            + f'<div class="card"><h2>Where your time went</h2>{app_chart}' + table([(a, fmt(s)) for a, s in top]) + "</div>"
            + f'<div class="card"><h2>When you play (hours, by time of day)</h2>{hour_chart}'
            + table([(f"{h:02d}:00", fmt(s)) for h, s in enumerate(this["hours"]) if s]) + "</div>"
            + "</div></main></body></html>")
    folder.mkdir(exist_ok=True)
    path = folder / "coaching.html"
    path.write_text(page, encoding="utf-8")
    return path
