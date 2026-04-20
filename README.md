# stash-plex-bridge

One-command Windows installer for three Stash↔Plex plugins:

- [trek-e/Stash2Plex](https://github.com/trek-e/Stash2Plex) — standalone sync tool
- [stashapp/CommunityScripts › PlexSync](https://github.com/stashapp/CommunityScripts/tree/main/plugins/PlexSync) — Stash plugin
- [Darklyter/StashPlexAgent.bundle](https://github.com/Darklyter/StashPlexAgent.bundle) — Plex agent

## What it does

1. Ensures `git` and Python 3.11 are installed (via `winget` if missing).
2. Creates a local venv and installs Python deps.
3. Clones the three plugin repos into `.\vendor\`.
4. Auto-detects Stash and Plex install locations and plugin directories.
5. Auto-extracts your Plex token from `Preferences.xml` (falls back to paste).
6. Prompts once for your Stash API key (generate at
   `http://localhost:9999/settings?tab=security`).
7. Lists your Plex libraries and asks which one to use.
8. Renders config files for all three plugins.
9. Copies plugin files into the right places.
10. Validates end-to-end: Stash API, Plex API, plugin load state.

## Usage

Copy this folder to the Windows box where Stash and Plex are running, then
from PowerShell (normal user unless your Plex plugins dir requires admin):

```powershell
.\install.ps1
```

Safe to rerun. Completed phases are skipped.

### Flags

| Flag | Effect |
|---|---|
| `--force` | Rerun every phase, even if already OK |
| `--phase <name>` | Run one phase only: `detect`, `fetch`, `configure`, `install`, `validate` |
| `--update` | Pull latest vendor repo commits |
| `--reset-tokens` | Wipe saved tokens and re-prompt |
| `--stash-port <N>` | Non-default Stash port (default 9999) |
| `--plex-port <N>` | Non-default Plex port (default 32400) |
| `--dry-run` | Log what would happen, no side effects |

Examples:

```powershell
.\install.ps1 --phase validate
.\install.ps1 --update --force
.\install.ps1 --reset-tokens
```

## State file

Progress and secrets live in `state.json` (user-only ACL, gitignored).
Delete it to start over.

## Logs

`bridge\logs\install-YYYYMMDD-HHMMSS.log` per run.

## Troubleshooting

- **"Plex install not found"** — ensure Plex Media Server is installed for the
  current Windows user. The script reads `%LOCALAPPDATA%\Plex Media Server`.
- **"run PowerShell as admin"** — your Plex plugins directory isn't writable
  by a normal user; relaunch PowerShell with admin rights.
- **Stash or Plex not running at VALIDATE** — start both services and rerun
  `.\install.ps1 --phase validate`.
- **Wrong Plex library picked** — run `.\install.ps1 --reset-tokens --phase configure`.

## Development (on macOS/Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Tests mock Windows paths and HTTP; no real Stash/Plex required.

## Design docs

See `docs/superpowers/specs/2026-04-19-stash-plex-bridge-design.md` and
`docs/superpowers/plans/2026-04-19-stash-plex-bridge.md`.
