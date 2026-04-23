# Contributing

Thanks for considering a contribution.

## Ground rules

- One logical change per pull request.
- New features require tests.
- All commits must be signed (`git commit -S`). GitHub displays a "Verified" badge on signed commits.
- Run `python -m pytest` before submitting. CI also runs tests, CodeQL, and OpenSSF Scorecard on every PR.

## Development setup

```
git clone https://github.com/Tgbjr2025/stash-plex-bridge.git
cd stash-plex-bridge
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
```

## Pull request checklist

- [ ] Tests pass locally
- [ ] New/changed behavior covered by tests
- [ ] Docs / README updated if behavior is user-visible
- [ ] Commit message follows `type: concise description` convention
- [ ] Commit is GPG-signed

## Reporting issues

Open an issue with:

- What you expected to happen
- What actually happened
- Exact steps to reproduce
- Environment (OS, Python version, Stash version, Plex version)

Security issues — see `SECURITY.md`.
