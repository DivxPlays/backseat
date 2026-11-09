# Roadmap

## Planned for 2.0.0

### Characters
- **Duo mode:** Vorn and Mika on screen together, arguing about your gameplay: Mika defends you, Vorn roasts you, and they snipe at each other.
- **Character creator:** make your own character in Settings (name, personality, voice, hair, eye and outfit colours) without touching code.
- **Jealousy across characters:** switch from Mika to Vorn and back and she knows ("You were with *him*?"); Vorn mocks you for hiding behind the girl.
- **Unlockable outfits and armour:** new outfits for Mika and armour for Vorn, earned through hours played, wins and challenges.
- **Holiday outfits and events:** Halloween, Christmas and your birthday change their look and lines automatically.
- **Grudges that stick:** rage-quit or ignore them for days and they hold it against you next session.

### Gameplay
- **Auto-clips:** keep the last 30 seconds of gameplay; on an epic play or a hilarious fail, save a clip with the character's roast voiced over it, so the Hall of Shame becomes shareable videos. Needs a screen recorder (ffmpeg or NVIDIA's instant replay), with your OK first.
- **Challenges and bounties:** "Get 3 headshots this match": tracked, rewarded with respect or affection, roasted when failed.
- **Accurate stats from the game itself:** kills and deaths from game logs or Steam where possible, instead of guessing from screenshots.
- **Smarter free mode:** the local model talks, and every few minutes Haiku double-checks what's actually happening (a few cents a day).
- **Coaching reports:** a weekly breakdown of your play, with real tips and progress charts.
- **Game profiles:** per-game knowledge (maps, weapons, perks) for sharper hints.

### Social
- **Squad leaderboard:** ranks your Discord friends by deaths and roast-worthiness, with a weekly "worst player" award read out loud.

### Interaction
- **Free voice commands:** "Hey Mika, change outfit", "Hey Vorn, shut up for 10 minutes", "switch to Mika": handled on your PC, no API cost.
- **Interrupting:** talk over the character and they stop mid-sentence to listen.
- **Click reactions:** poke them, drag and throw them, and they react.
- **Mini-games in menus and queues:** trivia about your game, or a dare from the character.
- **Real lip-sync:** mouth shapes that match each sound (Kokoro already gives word timing).
- **Sound effects:** Vorn's scoffs and grunts (real ones), Mika's giggles.

### Under the hood
- **Auto-update:** checks your GitHub for a new version and updates himself, also on your friends' PCs.
- **Frame-rate guard:** the local model pauses if your FPS drops while it thinks.

## Not planned
- Twitch/YouTube chat integration and the OBS overlay mode (you passed on these).

## Done
- Discord camera: the current character or both as "OBS Virtual Camera", lip-synced with subtitles; backgrounds dark, green, game screen or real webcam. (Both talking to each other comes with duo mode.)
- Mika (1.2.0): original yandere gamer girl, four outfits, Lovesick power-up, Alpha voice; characters as presets (1.1.0); About and version number (1.0.0).
- Local Kokoro voices (Michael for Vorn), snappier and fresher automatic comments, questions no longer cut off by pauses.
- Discord calls through VoiceMeeter: his voice in the call, a second ear for friends, voice fingerprints to tell them apart, running jokes per friend, one-click VoiceMeeter routing, optional swearing.
- Free local model (qwen3-vl 8B through Ollama) for automatic comments, with Claude when you talk to him; it only comments, Claude keeps score.
- Bloodfire: flaming hair, white-hot eyes, molten armor cracks, crimson aura; on epic plays, two wins in a row, and reaching 100 respect.
- Full body with poses by mood (crossed arms, fist, hands on hips, hands up, lecturing finger) and a slump when you lose.
- Cheaper calls: web search only when asked (questions 4.6 -> 1.9 cents), smaller screenshots of displays without the game (comments 0.07 -> 0.05 cents). Prompt caching doesn't apply: the repeated part of a call is below the minimum length that can be cached.
- Installer, memory export/import, Costs window and cost tag, black hair and eyes.
