# Changelog

Every version, newest first. Stages, least to most finished: pre-alpha, alpha, pre-beta, beta, release. Each released
version's entry is also its release notes on GitHub.

## 2.1.1 Beta (2026-11-10)

Fixes for games lagging with Backseat running, and for installing on a new PC. The install fixes were tried on a fresh
Windows (Windows Sandbox): it installs in about 3 minutes and the characters start. The lag fixes are self-checked but
haven't been tried in a full Fortnite match yet.

### Fixed
- **The installer stopped on a new PC** (#1). It installed Python with winget, which a fresh Windows doesn't have
  yet. Without Python 3.12, it now downloads Python's own package (15 MB, checked against a known fingerprint) and
  unpacks it into Backseat's folder in seconds: no setup program, no admin prompt (python.org's setup program took
  15 minutes or more on a fresh Windows).
- **On a new PC, Backseat couldn't download what it needs from the web.** A fresh Windows fetches the certificates
  that prove a website is genuine only when something asks for them, and Python's own check never asked, so the local
  voices, the voice fingerprints for your friends, update checks and Steam stats failed with a certificate error (he
  fell back to the online voice). Backseat now checks websites the way Windows does.
- **Games lagged badly with the free local model, and so did the characters (seen in Fortnite).** The local model
  thought on the game's graphics card for about 3 seconds a comment and held 10 GB of its memory the whole time. Now,
  while a game is in front, Claude Haiku makes the comments and the model is taken off the graphics card (Settings >
  Brain & budget > Local model in games turns the old way back on), and it loads with a smaller context (6.7 GB
  instead of 10).
- **The characters lagged badly and showed a black background while a game was running.** Started with Windows
  (or through its task), Backseat ran at below-normal CPU priority, so with a game taking the CPU their window
  couldn't repaint in time. It now runs at normal priority however it starts.
- Less work in the background while you play: the Discord camera draws 15 frames a second instead of 24 (it took half a
  CPU core), and the screen is checked for changes every 3 seconds instead of every second.

## 2.1.0 Beta (2026-11-09)

"Clip that!", milestones, fresher lines and a Report a problem button, plus two fixes from the log. Still beta: the new
parts are self-checked but haven't been tried in a real game yet.

### New
- **Fresher lines.** Their automatic comments kept opening the same way ("Ah, the tinkerer...", "[your name], still
  idling..."), a third brought up the hour and one in nine said "Pathetic". Now each one they start themselves is told
  how they opened lately and the words they keep leaning on (from this session and the last two), and they bring up the
  time only now and then. Tried on the free local model: "Pathetic" went from 4 of 6 lines to none.
- **"Clip that!"** Say it while you're in a game, no "Hey Vorn" needed (friends in your Discord call can say it too),
  and they frame the moment in the Hall of Shame with their verdict, a roast for a fail or grudging praise for a great
  play, and save the clip with your capture tool. It only works while a game is in front. About 0.05 cents.
- **Clips through Medal, with split audio.** With Medal running, clips use Medal's own clip key and clips folder instead
  of Game Bar's. **For clips with split audio (the game and your Discord call on their own tracks), you need Medal**, with
  its audio split by app: Game Bar and NVIDIA Instant Replay don't split it, and Game Bar records the game's sound only.
- **Milestones.** 10, 50, 100, 250, 500 and 1,000 hours together, a month since you met, and every year since: they
  celebrate it at the next greeting or comment, once. Updating from 2.0, the day you met is the first day they still
  have in memory.
- **Report a problem.** Tray > Report a problem... opens a new issue on GitHub in your browser, already filled in with
  your version, your Windows version and the last error in companion.log, with names, paths, keys, emails and Steam IDs
  taken out. Nothing is sent until you read it and press Submit (you need a GitHub account).
- **Open source.** Backseat is now free software under the GNU GPL v3 (see LICENSE): anyone can use, change and
  share it, and a shared changed version stays GPL v3, with its source. The About box says so too.

### Fixed
- **A crash when the sound device dropped out.** A headset reconnecting or Windows switching its default device made
  playing a line fail with "Device unavailable", and that took the whole app down. Now the line plays on Windows' default
  device instead, or, if no device will play right then, shows as subtitles without sound.
- **Mini-games outside games.** The free local model sometimes calls the desktop a "menu", so trivia started while you
  were in other apps (questions about Windows or the app you had open). Mini-games now start only while a game is in
  front.

## 2.0.2 Beta (2026-11-09)

A hotfix.

### Fixed
- **In duo mode they did the same idle animations at the same time.** After each exchange both of them went quiet at
  once and started their next idle together, often the same stretch or look-around. Now each takes their own pause after
  talking (2 to 14 seconds), so they move on their own again.

## 2.0.1 Beta (2026-11-09)

A hotfix.

### Fixed
- **Start with Windows didn't start him.** Windows' startup list skipped Backseat at log-in without a word. Start with
  Windows is now a task in Task Scheduler ("Backseat", 20 seconds after you log in, as you, no admin rights), with the
  startup list as a fallback. If you turned it on in 2.0.0, it moves to the task by itself the next time Backseat starts.
- **Started with Windows, he's on screen right away**, watching and talking as if you'd opened him, instead of hiding
  until a game starts.
- Started with Windows, he now notes it in companion.log, and a second copy quietly bows out instead of showing
  "already running".

## 2.0.0 Beta (2026-11-09)

The whole first roadmap. Beta: everything is built and tested, but some of it (clips, Steam stats, updates) hasn't seen
much real play yet.

### New
- **Character creator:** your own character on Vorn's or Mika's body (name, who they are, voice, power-up, hair, eye, skin
  and outfit colours, live preview). Claude writes their personality, the ways their name gets misheard and their own
  lines. Colours for Vorn and Mika too.
- **Challenges and bounties:** one thing for your next match they can check on screen, with a respect bounty paid by whoever
  set it, a fine when you fail or dodge it, and a record. "Hey Mika, give me a challenge."
- **Games detected anywhere**, not just Steam: Windows Game Bar's list, launcher folders, or fullscreen.
- **Game profiles:** each game looked up once with a web search, so comments, hints, trivia and dares use its real maps
  and weapons.
- **Mini-games in menus:** trivia (from Sonnet, checked against the game's profile, no repeats) and challenges.
- **Squad leaderboard:** weekly shame points for your Discord friends and a worst-player award.
- **Sound effects:** 37 real recorded grunts, gasps, yells, giggles, sighs and yawns (public domain, from Freesound) on
  pokes, throws, landings, idle animations and before some lines.
- **Auto-clips:** a Hall of Shame moment in a game saves the last 30 seconds (Windows Game Bar or NVIDIA Instant Replay);
  the highlights page plays it with their roast and them over the clip.
- **Frame-rate guard:** with the free local model, a game keeping the GPU 90%+ busy gets its comments from Claude instead.
- **Accurate stats from Steam:** real kills, deaths and wins for games with Steam stats, with your own Steam Web API key.
- **Auto-update:** a daily check of GitHub's latest release, then tray > Update; the repo is public now.
- **Releases:** a one-file installer (Install-Backseat.bat) that downloads the rest, version stages, and this changelog.
- Holidays, jealousy, grudges, click reactions and ragdoll throws, lip-sync, interrupting, free voice commands, outfits to
  earn, anime outfits for Mika, outfits for Vorn, Spotify comments, coaching reports, varied duo banter and more idle
  animations (all since 1.2.0).

### Fixed
- In duo mode the free local model no longer answers with a copy of the line it's answering.
- The Discord ear no longer takes their own voices for a friend talking.
- A friend's dumb question no longer costs you respect.
- Test scripts can't pop up a crash box or write to companion.log.
- Updating no longer overwrites characters you edited in Settings.

## 1.2.0 Pre-Beta (2026-11-08)

- **Mika:** an original yandere gamer girl with long pink hair and a cat-ear headset, four outfits, the Lovesick power-up
  and her own voice (Kokoro Alpha).

## 1.1.0 Alpha (2026-11-08)

- **Characters as presets** (name, personality, voice, look, wake word, power-up), with Vorn as the first one.

## 1.0.0 Pre-Alpha (2026-11-08)

The first version: Warlord Vorn, a trash-talking gaming companion who watches your screen.

- Comments and roasts from Claude, hints when you talk to him (wake word, push-to-talk or typing), long-term memory.
- His full body with poses by mood, black hair and eyes, and Bloodfire, his power-up form.
- A free local model option for automatic comments, and a local Kokoro voice (Michael).
- Discord calls: his voice in the call, friends' voices and voice fingerprints.
- A Costs window and cost tag, cheaper calls, memory export and import, an installer, and an About dialog with this version
  number.
