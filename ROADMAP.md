# Roadmap

## Planned

2.2.0 (picked 2026-11-10):
- **Pick any duo partner:** pair any two characters, created ones included (today a created character pairs only with Vorn).
- **Session recap card:** after a game, a picture with that session's stats and their verdict, ready to post (no ffmpeg).
- **"Is it slowing my game?":** a tray button that measures Backseat's CPU and graphics card use for 30 seconds during
  a match and says what to turn off.
- **More holidays:** Lunar New Year, Valentine's outfits, St. Patrick's, Easter, Thanksgiving.

- **The Discord camera may cost game frames** (#2): measure it in a game at normal priority; if it still costs
  frames, draw it in its own process or resend unchanged frames.

## Not yet tested in real use

Built and self-checked, but not yet seen working on a real day:
- Start with Windows after a real restart (2.0.1's task ran by hand, not at a log-in yet).
- Auto-update on an installed copy (a friend's PC on 2.0.0 being offered 2.0.2).
- Auto-clips in a real game (the Game Bar key, the clip on the highlights page).
- Steam stats with a real Steam Web API key.
- The squad leaderboard with friends on a real Discord call.
- 2.1.0: "Clip that!" and clips through Medal in a real game, a milestone party, and Report a problem opening a real issue.
- 2.1.1: the lag fixes in a full Fortnite match (normal priority, the local model off the graphics card in games).

## Ideas for 2.2.0 (not decided: pick the ones you want)

GitHub issues land in Planned with their number. Checked 2026-11-10: #2 is in Planned; #1 was fixed in 2.1.1; #3 is built for 2.2.0.

### Squad and clips
- **Squad trivia:** menu trivia your Discord friends can answer too; the first right answer scores on the squad board.
- **Shareable clips:** an .mp4 with them and their roast burned in, ready to send (needs ffmpeg, a download).

### Characters
- **Power-up colours** for created characters, and their **own outfit choice** instead of sharing Vorn's or Mika's.

### Quality
- **Our history page:** respect over time, outfit progress, trivia and challenge records, squad boards and Steam stats, any time.
- **Bigger free model:** benchmark a larger local vision model on the RTX 4090 against frame rate (a model download).
- **An .exe installer instead of the .bat** (asked for on 2026-11-09): one Install-Backseat.exe to download and run,
  with Backseat's icon, a proper window and an uninstaller, built by the release script (for example with Inno Setup,
  a free tool download). An unsigned .exe still gets Windows' "More info > Run anyway" warning, and antivirus flags
  unsigned installers more often than a .bat; a code-signing certificate (about $10 a month through Azure Trusted
  Signing, or more elsewhere) removes most of that.

## Bigger ideas (a later version)

Added 2026-11-09 at your request. Not designed yet: each needs its own plan first.

- **Cloud sync between PCs:** memory, settings, characters, the Hall of Shame and battle reports kept in step between your
  PCs, instead of tray > Export memory and Import by hand. The cheapest route needs no server of ours: keep them in a
  folder OneDrive, Google Drive or Dropbox already syncs, encrypted with a passphrase (memory.json holds personal notes),
  and merge two PCs' memories when both changed (respect, hours, notes). Never the API key: each PC keeps its own.
- **iOS and Android (very limited):** a phone can't watch your PC game the way he does on Windows (iOS allows no
  overlays on other apps; Android allows them but needs screen-capture permission every session and would cost a lot of
  battery), so it would be a companion app instead: talk to them by voice or text, see the Hall of Shame, stats, trivia
  records and squad board, get their roasts as notifications while your PC plays, and mute or pause the PC copy from your
  phone. Needs cloud sync first, and a way for the phone to reach your PC or the synced data.

## Not planned
- Twitch/YouTube chat integration and the OBS overlay mode (you passed on these).

## Done

2.2.0 (in progress):
- "What's new" after an update: a window with the version's changes, and the greeting mentions the update.
- The installer checks your API key with one tiny call (asks again for a rejected key, points a no-credit account to Billing).
- The About box and the trailer's end card say Backseat is made with the help of AI (#3).

2.1.1 (2026-11-10):
- Fix (#1): the installer stopped on a fresh Windows (no winget). Without Python 3.12 it now unpacks Python's own package into Backseat's folder; a fresh Windows reaches the API key prompt in about 3 minutes.
- Fix: started with Windows, Backseat ran at below-normal priority, so in games the characters lagged on a black background. Normal priority now.
- Fix: games lagged with the free local model (Fortnite). In games Claude comments and the model leaves the graphics card; it loads in 6.7 GB instead of 10; the camera draws 15 fps; the screen is checked every 3 s.

2.1.0 (2026-11-09):
- Milestones: 10 to 1,000 hours together, a month since you met and each year since, celebrated once at the next greeting or comment.
- "Clip that!": said in a game (no wake word; friends too), the moment goes in the Hall of Shame with their verdict and the clip is saved.
- Clips through Medal when it's running (its key and folder): Medal is needed for split audio (the game and Discord on their own tracks).
- Report a problem: tray > Report a problem... opens a GitHub issue filled in with the version, Windows and the last error (names, paths and keys taken out).
- Fresher lines: each automatic line is told their recent openings and pet words (this session and the last two) to avoid, and the hour comes up only now and then.
- Fix: a sound device dropping out (a headset reconnecting) no longer crashes the app: the default device plays the line, or it shows as subtitles.
- Fix: mini-games start only while a game is in front, never on the desktop or in other apps.

2.0.0 (2026-11-09):
- Accurate stats from Steam: real kills, deaths and wins this session for games with Steam stats (CS2, TF2, Left 4 Dead 2...), with your own Steam Web API key; read every 2 minutes while such a game is in front.
- Auto-update: a daily check of GitHub (the repo is public now) and tray > Update to x.y.z, which runs the new version's installer and keeps memory, settings, key and characters (the installer no longer overwrites characters you edited).
- Sound effects: 37 real recordings (public domain, from Freesound): grunts on pokes, grabs and landings, sighs, yawns, chuckles and giggles with idle animations, and a scoff or giggle before some lines.
- Fix: in duo mode the free local model no longer answers with a copy of the line it's answering.
- Auto-clips: a Hall of Shame moment in a game saves the last 30 seconds through Windows Game Bar's "Record what happened" (or NVIDIA Instant Replay), and the highlights page plays the clip with their roast over its end and them standing in the corner of it with their line. No downloads.
- Frame-rate guard: with the free local model, a game keeping the GPU 90%+ busy gets its comments from Claude Haiku instead, so the local model never takes frames (NVIDIA, via nvidia-smi; adjustable, 0 = off).
- Squad leaderboard: weekly shame points for your Discord friends (deaths, fails and epic plays seen on screen or told, their talk roasted or praised), standings when asked, and last week's worst player award announced when a friend first talks that week.
- Character creator: your own character on Vorn's or Mika's body (name, who they are, voice, power-up, hair, eye, skin and outfit colours, live preview); Claude writes their full personality, misheard names and their own voice-command lines (about 6 cents). Colours for Vorn and Mika too; created characters travel with Export memory.
- Challenges and bounties: one thing for your next match they can check on screen, with a bounty (easy, hard, brutal) paid by whoever set it, a fine when you fail or dodge it, settled from your screen, and a record. Ask for one any time ("give me a challenge").
- Fixes: the Discord ear no longer takes their own voices for a friend talking; test scripts can't pop up a crash box or write to companion.log.
- Game profiles: each game looked up once with a web search (modes, maps, weapons, good play) and used in comments, hints, trivia and dares; trivia now from Sonnet, checked against the profile, no repeats. Games are found anywhere, not just Steam: Windows' Game Bar list, launcher folders, or fullscreen.
- Mini-games in menus: trivia about your game (answer without the wake word, judged in character, a record kept) and dares for your next match.
- Ragdoll throws with screams: they flail, spin, bounce, land in a heap and get up; and they scream when thrown.
- Varied duo banter: 1 to 6 lines an exchange, usually short, now and then a real argument.
- Coaching reports: weekly, this week against last with charts, and a verdict with 3 tips from their notes on your play (one call a week).
- Spotify: they notice what you play (from the Spotify app's window), look a new song up with one web search (about 1 cent, remembered), and react now and then; repeats and your top artists too.
- Idle animations: stretch, look around, sigh, lean in, nod off for both; knuckle cracks, gauntlet inspection, dusting off and a power stance for Vorn; waving, headset, hair twirl, heart hands and a bounce for Mika.
- Click reactions: Ctrl+click pokes them (head or body, more annoyed the more you poke), Ctrl+drag throws them across the screen and they glide back.
- Grudges that stick: rage-quits, days of being ignored and too many "shut up"s cost respect and get a cold greeting and digs, until you apologize (or 2 days pass).
- Jealousy across characters: they track your time alone with each; whoever was left out opens with it, and the rivalry comes up now and then.
- Holidays: Halloween and Christmas outfits for both that switch in by themselves, bats, snow, confetti (New Year's, your birthday) and hearts (Valentine's), festive lines, and a birthday setting.
- Real lip-sync: mouth shapes for each sound (open, wide, round, teeth), read from the voice's sound, for both characters and the Discord camera.
- Smarter free mode: with the local model, Haiku takes a comment every 5 minutes and double-checks wins, deaths and losses (at most every 2 minutes), so score, respect, Bloodfire and the Hall of Shame keep working (about 10 cents a day).
- Outfits to earn: four each (10 hours, 100 talks, 7 days in a row, 100 respect), plus six free anime-inspired outfits for Mika (maid, shrine maiden, magical girl, yukata, netrunner, track suit).
- Interrupting: talk over them and they pause to listen; they stop for good if you called them, and carry on if you didn't.
- Free voice commands: shut up (for a while), talk again, stop looking / look again, change or name an outfit, switch character or duo mode, and "how much have you cost me", handled on your PC with in-character replies.
- Outfits for Vorn: Warlord, Obsidian, Frostbound, Desert Raider and Off-Duty, picked in tray > Outfit or new each launch.
- Duo mode: Vorn and Mika side by side, each reaction a 2-3 line exchange in their own voices, lip-synced, on the overlay and the Discord camera; call one by name and only that one answers, and each keeps their own memories and past.
- Discord camera: the current character or both as "OBS Virtual Camera", lip-synced with subtitles; backgrounds dark, green, game screen or real webcam. (Both talking to each other comes with duo mode.)
- Mika (1.2.0): original yandere gamer girl, four outfits, Lovesick power-up, Alpha voice; characters as presets (1.1.0); About and version number (1.0.0).
- Local Kokoro voices (Michael for Vorn), snappier and fresher automatic comments, questions no longer cut off by pauses.
- Discord: friends see and hear him through your whole-screen stream; a second ear for friends with voice fingerprints and running jokes per friend; optional swearing. (VoiceMeeter routing was removed in favour of this.)
- Free local model (qwen3-vl 8B through Ollama) for automatic comments, with Claude when you talk to him; it only comments, Claude keeps score.
- Bloodfire: flaming hair, white-hot eyes, molten armor cracks, crimson aura; on epic plays, two wins in a row, and reaching 100 respect.
- Full body with poses by mood (crossed arms, fist, hands on hips, hands up, lecturing finger) and a slump when you lose.
- Cheaper calls: web search only when asked (questions 4.6 -> 1.9 cents), smaller screenshots of displays without the game (comments 0.07 -> 0.05 cents). Prompt caching doesn't apply: the repeated part of a call is below the minimum length that can be cached.
- Installer, memory export/import, Costs window and cost tag, black hair and eyes.
