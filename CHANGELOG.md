# Changelog

Every version, newest first. Stages, least to most finished: pre-alpha, alpha, pre-beta, beta, release. Each released
version's entry is also its release notes on GitHub.

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
