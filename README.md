# Vorn: your trash-talking gaming companion

An animated warlord in the corner of your screen. He watches what you play, comments, gives hints when you ask, remembers you between sessions, and roasts your hours played. His brain is Claude.

## Setup

1. Get the code: `git clone https://github.com/DivxPlays/vorn` (private repo, so sign in to GitHub first), or download the ZIP from the repo page.
2. Get an API key at console.anthropic.com (pay-as-you-go, separate from a Claude.ai subscription).
3. Paste it into a file named `api_key.txt` next to `main.py`. It is never uploaded to GitHub.
4. Double-click `run.bat`. The first run installs everything (a few minutes).
5. Set your games to **borderless windowed**. Exclusive fullscreen draws over every overlay.

## Controls

| Key | What it does |
|---|---|
| "Hey Vorn, ..." | talk to him hands-free. Say just "Hey Vorn" and he chimes and waits for your question |
| hold F8 | talk to him (mic, transcribed on your PC) |
| F9 | type to him (Enter sends, Esc closes) |
| F10 | "look at this": he comments on or gives a hint about your screen right now |
| F7 | pause / resume watching (falling chime = stopped, rising = watching). Use it before opening anything private |
| F4 | shut-up mode: he keeps watching and keeping score, but only talks when you talk to him |
| F6 | unlock him, drag him anywhere on any display, then F6 again to lock. He remembers the spot |
| tray icon | right-click for this month's cost (click it for the Costs window), move/lock, pause, shut up, show him on stream, open the Hall of Shame, this week's highlights or battle reports, open Settings, turn on Start with Windows, or quit |

## How it behaves

- He sees all your displays except the ones in `SKIP_DISPLAYS` (the XENEON EDGE is skipped), each sent as its own image. Add a display's name to `SKIP_DISPLAYS` to hide it from him, or set `MONITOR = 1` to watch only your main display.
- When locked, mouse clicks pass straight through him to your game. He only grabs the mouse while unlocked with F6.
- He looks at your screen when it changes a lot (at most every 15 s), or after 60 s of silence to roast you.
- He stops looking and stops counting your time after 5 minutes without keyboard or mouse input.
- If Windows blocks a screenshot (a UAC prompt, the lock screen, a game switching resolution), he waits a few seconds and carries on watching.
- Hours played: time per app while he runs, plus lifetime Steam hours for Steam games (read from Steam's local files).
- **Score:** he counts your deaths, wins, losses, fails and epic plays, per session and per game, and throws the numbers at you.
- **Respect meter (0-100):** goes up when you play well and down when you embarrass yourself. Low respect means pure contempt; high respect means grudging, still-arrogant praise. It moves slowly.
- **Hall of Shame:** truly hilarious fails and genuinely epic plays get saved as screenshots with his caption in the `Hall of Shame` folder (at most one a minute).
- **Battle reports:** when you start him, he writes a short roast of your previous session, reads it out, and adds it to `battle reports.txt`.
- **Hints:** when you ask about something specific (a boss, puzzle, item), he can search the web for guides first. Web search costs about 1 cent per search on top of the question.
- **Nags:** after 90 minutes without a 5-minute break, or between 1 and 6 AM, he tells you to take a break or go to bed (at most every 45 minutes).
- **Wake word:** the mic stays on and listens for "Hey Vorn". Everything is transcribed on your PC; nothing is sent anywhere until he hears his name. If game sound or music keeps setting him off, raise `WAKE_LEVEL` or set `WAKE_WORD = False`.
- **Post-match breakdowns:** after a loss, he goes over the last minute of screenshots and tells you what went wrong (at most every 3 minutes; uses the smart model, so roughly what a question costs).
- **Grudge list:** he tracks which bosses and enemies kill you most in each game and throws it in your face.
- **Evolving look:** his gear upgrades as your respect grows: polished armor and a gold sigil at 25, white fur and a gold-trimmed cape at 50, a war-crown and a golden glow at 75. His aura flares when he levels up.
- **Moods by time of day:** grumpy in the morning, tactical in the afternoon, hyped in the evening, unhinged after 11 PM, extra smug on weekends.
- **Lore:** during quiet moments he sometimes tells a story from his conquests. He remembers what he's told you and keeps it consistent.
- **Voice clips:** every Hall of Shame screenshot gets a WAV of his roast next to it.
- **Weekly highlights:** tray > Open this week's highlights builds a page with the week's Hall of Shame, captions, playable voice clips and your stats.
- **Spending tracker:** he estimates the cost of every call and keeps a monthly total, always shown in a small tag under him. Click the cost line at the top of the tray menu for the **Costs window**: this month against your budget, today, a bar per day, a month-end estimate, and what it went to (talking to him, automatic comments, breakdowns, battle reports). At 80% of `MONTHLY_BUDGET` he switches to cheap mode (Haiku only, no web search, no breakdowns); at 100% he only talks when you talk to him. He tells you when either happens. These are estimates from token counts; the Anthropic Console is the real bill.
- **Start with Windows:** tray > Start with Windows. He starts hidden at login and wakes up when a Steam game (or one listed in `GAMES`) comes to the front. Until then he doesn't watch, listen or track anything. Tray > Wake up now skips the wait.
- **Volume ducking:** while he talks, every other app drops to 35% of its volume (`DUCK_TO`), then goes back. If he ever crashes mid-sentence, raise them again in the Windows Volume Mixer.
- **Only one Vorn at a time:** starting a second copy just tells you he's already running, so you can't double your bill by accident.
- **Idle life:** he yawns when you go AFK, rolls his eyes when you sit in menus, glances at your other screens, and his aura flares when you win. Sometimes he scoffs or laughs before speaking.
- Memory lives in `memory.json`: time stats, score, respect, your last 20 sessions, and his notes about you (general and per game). Delete the file to wipe it.
- He is hidden from screenshots and recordings by default, so he can't see himself. Tick **Show me on stream / recordings** in the tray menu to have him appear in OBS and clips.

## Cost

Each look sends a screenshot of every display he watches. Two models split the work (pick them in Settings). The costs below were measured from real calls with two displays:

- `MODEL` (Claude Haiku 5.5) makes his automatic comments and roasts. About 0.07 cents each. How many depends on **Seconds between comments** (`LOOK_COOLDOWN`), counted from when he last spoke: at 60 s he makes at most ~55 an hour (up to ~4 cents an hour); at the default 15 s, a fast-moving game can push it to ~180 an hour (up to ~13 cents an hour). On a desktop or in menus it's far fewer.
- `SMART_MODEL` (Claude Opus 5.5) answers when you talk to him (voice, F8, F9), when you press F10, and writes post-match breakdowns. About 4.6 cents each, plus 1 cent per web search. Talking to him is usually most of the bill.

Example: 8 active hours a day, comments every 60 s, and 10 questions a day comes to at most ~80 cents a day, about $24 a month. With the default 15 s it's up to ~$1.50 a day, about $45 a month.

To spend less: watch one display (`MONITOR = 1`), raise the seconds between comments, or set the model for talking to him to Haiku (questions drop to about a tenth of a cent, but hints get weaker). Set a monthly spend limit in the Anthropic Console as a hard backstop. The spend in the tray menu is his own estimate from token counts; the Console is the real bill.

## Privacy

Screenshots go to Anthropic's API, which means whatever is on your screen, including Discord or browser tabs. Press F7 first. While paused he answers questions without seeing the screen.

## Tweaking

Right-click the tray icon > **Settings...** to change his name, voice (with a Test button), size, personality, models, budget, timings, nags, wake word, hotkeys and displays. Saving restarts him. Only the settings you changed are stored in `settings.json`, so improvements to the defaults in `config.py` still reach you; **Restore Defaults** deletes it.

## What's on GitHub

The code, this README and [ROADMAP.md](ROADMAP.md) (planned features). Your API key, his memory of you, your settings, logs, battle reports and the Hall of Shame stay on your PC only (see `.gitignore`), so a fresh copy on another PC starts with a blank memory.

If something breaks, look at `companion.log`. Run `.venv\Scripts\python test_selfcheck.py` to check the parts that work without the internet.
