"""Weekly highlights page: the last 7 days of the Hall of Shame, with his captions, voice clips and your stats."""
import html
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import config
from memory import fmt, tally

CSS = """
:root { --bg:#141016; --card:#211a1f; --ink:#f1e9df; --dim:#a89a90; --gold:#f2c64d; --red:#b3262f; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.5 "Segoe UI", system-ui, sans-serif; }
main { max-width:1200px; margin:0 auto; padding:32px 16px 64px; }
h1 { margin:0 0 4px; font-size:34px; letter-spacing:.5px; }
h1 span { color:var(--gold); }
.sub { color:var(--dim); margin:0 0 24px; }
.stats { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:12px; margin-bottom:32px; }
.stat { background:var(--card); border:1px solid #3a2e33; border-radius:12px; padding:14px 16px; }
.stat b { display:block; font-size:26px; color:var(--gold); }
.stat small { color:var(--dim); }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(340px, 1fr)); gap:18px; }
figure { margin:0; background:var(--card); border:1px solid #3a2e33; border-radius:14px; overflow:hidden; }
figure img, figure video { display:block; width:100%; height:auto; background:#000; }
figcaption { padding:12px 16px 4px; }
figcaption q { display:block; font-weight:600; quotes:"\\201C" "\\201D"; }
.when { display:block; color:var(--dim); font-size:13px; margin-bottom:4px; }
audio { width:calc(100% - 32px); margin:8px 16px 16px; }
.empty { color:var(--dim); font-style:italic; }
"""


SYNC = """<script>
// a clip plays with the roast laid over its end: the roast starts so it finishes with the clip
document.querySelectorAll("figure video").forEach(v => {
  const a = v.parentElement.querySelector("audio");
  if (!a) return;
  a.preload = "auto";
  const start = () => Math.max(0, v.duration - (a.duration || 4) - 1);
  v.addEventListener("timeupdate", () => {
    const t = v.currentTime - start();
    if (!v.paused && a.paused && t >= 0 && t < (a.duration || 4) - 0.2) { a.currentTime = t; a.play(); }
  });
  v.addEventListener("pause", () => a.pause());
  v.addEventListener("seeked", () => a.pause());
});
</script>"""


def build(d, folder):
    """Write `this week.html` into the Hall of Shame folder from memory data `d`; returns its path."""
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    entries = [e for e in reversed(d.get("hall", []))
               if datetime.fromisoformat(e["when"]) >= week_ago and (folder / e["file"]).exists()]
    events = {}
    for s in d.get("sessions", []):
        if datetime.fromisoformat(s["start"]) >= week_ago:
            for kind, n in s.get("events", {}).items():
                events[kind] = events.get(kind, 0) + n
    played = sum(sec for day, sec in d.get("days", {}).items() if day >= week_ago.date().isoformat())
    month_spend = d.get("spend", {}).get(now.strftime("%Y-%m"), 0.0)
    stats = [(fmt(played), "played this week"), (str(events.get("death", 0)), "deaths"), (str(events.get("win", 0)), "wins"),
             (f"{d.get('respect', 10)}/100", f"{config.NAME}'s respect"), (f"${month_spend:.2f}", "spent on him this month")]
    cards = []
    for e in entries:
        when = datetime.fromisoformat(e["when"]).strftime("%a %b %d, %I:%M %p")
        audio = f'<audio controls preload="none" src="{quote(e["clip"])}"></audio>' if e.get("clip") and (folder / e["clip"]).exists() else ""
        video = e.get("video") and Path(e["video"]).exists()  # auto-clips: the moment itself, with the roast over its end
        shot = (f'<video controls preload="metadata" poster="{quote(e["file"])}" src="{Path(e["video"]).as_uri()}"></video>' if video
                else f'<img src="{quote(e["file"])}" alt="" loading="lazy">')
        cards.append(f'<figure>{shot}<figcaption>'
                     f'<span class="when">{html.escape(when)} &middot; {html.escape(e.get("game", ""))}</span>'
                     f'<q>{html.escape(e["caption"])}</q></figcaption>{audio}</figure>')
    body = "".join(cards) or '<p class="empty">Nothing worth framing this week. Either you played flawlessly, or you barely played at all.</p>'
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>Hall of Shame</title><style>{CSS}</style></head><body><main>'
            f'<h1><span>{html.escape(config.NAME)}\'s</span> Hall of Shame</h1>'
            f'<p class="sub">{week_ago:%b %d} to {now:%b %d}. Score this week: {html.escape(tally(events))}.</p>'
            '<div class="stats">' + "".join(f"<div class=\"stat\"><b>{html.escape(v)}</b><small>{html.escape(k)}</small></div>" for v, k in stats)
            + f'</div><div class="grid">{body}</div></main>{SYNC}</body></html>')
    folder.mkdir(exist_ok=True)
    path = folder / "this week.html"
    path.write_text(page, encoding="utf-8")
    return path
