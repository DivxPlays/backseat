# Roadmap

## Planned for 2.0.0

### Characters
- **Character creator:** make your own character in Settings (name, personality, voice, hair, eye and outfit colours) without touching code.
- **Jealousy across characters:** switch from Mika to Vorn and back and she knows ("You were with *him*?"); Vorn mocks you for hiding behind the girl.
- **Grudges that stick:** rage-quit or ignore them for days and they hold it against you next session.

### Gameplay
- **Auto-clips:** keep the last 30 seconds of gameplay; on an epic play or a hilarious fail, save a clip with the character's roast voiced over it, so the Hall of Shame becomes shareable videos. Needs a screen recorder (ffmpeg or NVIDIA's instant replay), with your OK first.
- **Challenges and bounties:** "Get 3 headshots this match": tracked, rewarded with respect or affection, roasted when failed.
- **Accurate stats from the game itself:** kills and deaths from game logs or Steam where possible, instead of guessing from screenshots.
- **Coaching reports:** a weekly breakdown of your play, with real tips and progress charts.
- **Game profiles:** per-game knowledge (maps, weapons, perks) for sharper hints.

### Social
- **Squad leaderboard:** ranks your Discord friends by deaths and roast-worthiness, with a weekly "worst player" award read out loud.

### Interaction
- **Click reactions:** poke them, drag and throw them, and they react.
- **Mini-games in menus and queues:** trivia about your game, or a dare from the character.
- **Sound effects:** Vorn's scoffs and grunts (real ones), Mika's giggles.

### Under the hood
- **Auto-update:** checks your GitHub for a new version and updates himself, also on your friends' PCs.
- **Frame-rate guard:** the local model pauses if your FPS drops while it thinks.

## Not planned
- Twitch/YouTube chat integration and the OBS overlay mode (you passed on these).

## Done
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
