# Vorn: your trash-talking gaming companion

An animated, full-body warlord in the corner of your screen. He watches what you play, comments, gives hints when you ask, remembers you between sessions, and roasts your hours played. His brain is Claude.

## Setup

1. Get an API key at console.anthropic.com (pay-as-you-go, separate from a Claude.ai subscription).
2. Get the code: on the repo page (https://github.com/DivxPlays/vorn, private, so sign in first) click **Code > Download ZIP** and extract it, or `git clone` it.
3. Double-click **Install Vorn.bat**. It:
   - installs Python 3.12 if it's missing (through winget),
   - puts him in `%LOCALAPPDATA%\Programs\Vorn`,
   - installs everything he needs (a few minutes the first time),
   - asks for your API key (kept only in `api_key.txt` on that PC, never uploaded),
   - adds Vorn shortcuts to the Start menu and desktop, and starts him.

   If Windows says the file came from the internet, click **More info > Run anyway**.
4. Set your games to **borderless windowed**. Exclusive fullscreen draws over every overlay.

Running **Install Vorn.bat** from a newer download updates him; your memory, settings and key are kept. To bring your memory along from another PC, see **Moving him to another PC** below. To uninstall, turn off Start with Windows in his tray menu, quit him, then delete `%LOCALAPPDATA%\Programs\Vorn` and the two shortcuts.

Working on his code instead? Put your key in `api_key.txt` in the code folder and double-click `run.bat`; it sets everything up there and starts him.

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
| tray icon | right-click for this month's cost (click it for the Costs window), move/lock, pause, shut up, show him on stream, open the Hall of Shame, this week's highlights or battle reports, export or import his memory, open Settings, turn on Start with Windows, or quit |

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
- **Hints:** he answers from what he knows. To make him search the web for guides first, say "look it up" (or search, google, wiki, guide, walkthrough) in your question. Searching adds about 3-4 cents to that question, so he only does it when you ask.
- **Nags:** after 90 minutes without a 5-minute break, or between 1 and 6 AM, he tells you to take a break or go to bed (at most every 45 minutes).
- **Wake word:** the mic stays on and listens for "Hey Vorn". Everything is transcribed on your PC; nothing is sent anywhere until he hears his name. If game sound or music keeps setting him off, raise `WAKE_LEVEL` or set `WAKE_WORD = False`.
- **Post-match breakdowns:** after a loss, he goes over the last minute of screenshots and tells you what went wrong (at most every 3 minutes; uses the smart model, so roughly what a question costs).
- **Grudge list:** he tracks which bosses and enemies kill you most in each game and throws it in your face.
- **Full body and poses:** he stands in full armor and cape, and his arms follow his mood: relaxed when idle, arms crossed when smug, shaking a fist when angry, fists on hips when he laughs, hands thrown up when surprised, a lecturing finger when disgusted. He slumps in shame when you lose a match. Make him bigger or smaller in Settings > Size on screen.
- **Bloodfire:** his power-up form. His black hair ignites into dark-red flame, his eyes burn white, his armor cracks with molten light and a crimson aura surrounds him. He roars "Bloodfire!" and transforms for about 8 seconds when you pull off an epic play or win twice in a row, and for about 25 seconds when your respect reaches 100. (Not during shut-up mode: he keeps quiet then.)
- **Evolving look:** his gear upgrades as your respect grows: polished armor and gold trim at 25, white fur and a gold-trimmed cape and tabard at 50, a war-crown and a golden glow at 75. His aura flares when he levels up.
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

Each look sends a screenshot of every display he watches: the display with your game sharp, the others smaller (cheaper, still enough to roast). Two models split the work (pick them in Settings). The costs below were measured from real calls with two displays (5120x1440 and 4K):

- `MODEL` (Claude Haiku 5.5) makes his automatic comments and roasts. About 0.05 cents each. How many depends on **Seconds between comments** (`LOOK_COOLDOWN`), counted from when he last spoke: at 60 s he makes at most ~55 an hour (up to ~3 cents an hour); at the default 15 s, a fast-moving game can push it to ~180 an hour (up to ~9 cents an hour). On a desktop or in menus it's far fewer.
- `SMART_MODEL` (Claude Opus 5.5) answers when you talk to him (voice, F8, F9), when you press F10, and writes post-match breakdowns. About 2 cents each; asking him to look something up adds about 3-4 cents.

Example: 8 active hours a day, comments every 60 s, and 10 questions a day comes to at most ~40 cents a day, about $12 a month. With the default 15 s it's up to ~90 cents a day, about $26 a month.

To spend less: watch one display (`MONITOR = 1`), raise the seconds between comments, or set the model for talking to him to Haiku (questions drop to about a tenth of a cent, but hints get weaker). Set a monthly spend limit in the Anthropic Console as a hard backstop. The spend in the tray menu is his own estimate from token counts; the Console is the real bill.

## Privacy

Screenshots go to Anthropic's API, which means whatever is on your screen, including Discord or browser tabs. Press F7 first. While paused he answers questions without seeing the screen.

## Tweaking

Right-click the tray icon > **Settings...** to change his name, voice (with a Test button), size, personality, models, budget, timings, nags, wake word, hotkeys and displays. Saving restarts him. Only the settings you changed are stored in `settings.json`, so improvements to the defaults in `config.py` still reach you; **Restore Defaults** deletes it.

## What's on GitHub

The code, this README and [ROADMAP.md](ROADMAP.md) (planned features). Your API key, his memory of you, your settings, logs, battle reports and the Hall of Shame stay on your PC only (see `.gitignore`), so a fresh copy on another PC starts with a blank memory.

## Moving him to another PC

1. On the old PC: tray > **Export memory...** saves one `.zip` with his memory, battle reports and the Hall of Shame.
2. Install him on the new PC (see Setup), then tray > **Import memory...** and pick the `.zip`. He backs up the memory he had there (`memory backup <date>.zip` in his folder) and restarts with yours.

Your settings and API key aren't in the export; set those up on the new PC.

If something breaks, look at `companion.log`. Run `.venv\Scripts\python test_selfcheck.py` to check the parts that work without the internet.
