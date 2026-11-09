# Working on Vorn

- **After every change, upload it.** Bump VERSION in main.py (x.y.Z for fixes, x.Y.0 for features) and the version line at the top of README.md, update README.md so it matches what changed (features, controls, settings, costs), take built items off ROADMAP.md, then commit and push to GitHub (origin = https://github.com/DivxPlays/vorn, private, branch main). The user asked for this on 2026-11-08, so don't ask first each time.
- Before committing code changes, run `.venv\Scripts\python test_selfcheck.py`. Don't push if it fails; fix it or tell the user.
- The GitHub CLI isn't on Git Bash's PATH: use `"/c/Program Files/GitHub CLI/gh.exe"`. Push with:
  `git -c credential.helper= -c 'credential.helper=!"/c/Program Files/GitHub CLI/gh.exe" auth git-credential' push`
- Never commit secrets or personal data: api_key.txt, memory.json, settings.json, companion.log, battle reports.txt, Hall of Shame/ (all in .gitignore). Before pushing, check for a real key: `git grep --cached -E "sk-ant-[A-Za-z0-9_-]{20,}"` must find nothing.
- The character is an original design, Warlord Vorn. Never recreate Vegeta, Saiyans, Super Saiyan or any other Dragon Ball design, name or form.
- Don't launch Vorn unless the user asks. He bills the API while running.
