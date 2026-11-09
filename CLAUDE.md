# Working on Vorn

- **After every change, upload it.** Update README.md so it matches what changed (features, controls, settings, costs), take built items off ROADMAP.md, then commit and push to GitHub (origin = https://github.com/DivxPlays/vorn, private, branch main). The user asked for this on 2026-11-08, so don't ask first each time.
- **Version number:** don't bump it on your own. Every so often, when a meaningful batch of changes has landed since the last bump (a new feature, or several fixes), suggest a bump to the user with the number you'd use (x.y.Z for fixes, x.Y.0 for features, X.0.0 for a big overhaul) and what it covers. Only on their yes: change VERSION in main.py and the version line at the top of README.md, commit and push. Current: 1.2.0. Everything on ROADMAP.md (and what we add along the way) ships as 2.0.0: the user said not to suggest any smaller bump before that; suggest 2.0.0 once the roadmap is done.
- Before committing code changes, run `.venv\Scripts\python test_selfcheck.py`. Don't push if it fails; fix it or tell the user.
- The GitHub CLI isn't on Git Bash's PATH: use `"/c/Program Files/GitHub CLI/gh.exe"`. Push with:
  `git -c credential.helper= -c 'credential.helper=!"/c/Program Files/GitHub CLI/gh.exe" auth git-credential' push`
- Never commit secrets or personal data: api_key.txt, memory.json, settings.json, companion.log, battle reports.txt, Hall of Shame/ (all in .gitignore). Before pushing, check for a real key: `git grep --cached -E "sk-ant-[A-Za-z0-9_-]{20,}"` must find nothing.
- The characters are original designs: Warlord Vorn and Mika. Never recreate Vegeta, Saiyans, Super Saiyan or any other Dragon Ball design, name or form, or Yuno Gasai or anything from Future Diary (Mika is an original yandere: no pink twin-tails, no diary, no "Yukki").
- Don't launch Vorn unless the user asks. He bills the API while running.
