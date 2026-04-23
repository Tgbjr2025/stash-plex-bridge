# stash-plex-bridge

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Release](https://img.shields.io/github/v/release/Tgbjr2025/stash-plex-bridge?include_prereleases&sort=semver)](https://github.com/Tgbjr2025/stash-plex-bridge/releases)
[![Downloads](https://img.shields.io/github/downloads/Tgbjr2025/stash-plex-bridge/total)](https://github.com/Tgbjr2025/stash-plex-bridge/releases)
[![CI](https://github.com/Tgbjr2025/stash-plex-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/Tgbjr2025/stash-plex-bridge/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Tgbjr2025/stash-plex-bridge/actions/workflows/codeql.yml/badge.svg)](https://github.com/Tgbjr2025/stash-plex-bridge/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/Tgbjr2025/stash-plex-bridge/badge)](https://scorecard.dev/viewer/?uri=github.com/Tgbjr2025/stash-plex-bridge)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/placeholder/badge)](https://www.bestpractices.dev/projects)
[![SLSA 3](https://slsa.dev/images/gh-badge-level3.svg)](https://slsa.dev)
[![Last commit](https://img.shields.io/github/last-commit/Tgbjr2025/stash-plex-bridge)](https://github.com/Tgbjr2025/stash-plex-bridge/commits/main)
[![Stars](https://img.shields.io/github/stars/Tgbjr2025/stash-plex-bridge?style=social)](https://github.com/Tgbjr2025/stash-plex-bridge/stargazers)

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

## Verification and trust

This project ships with a full supply-chain trust stack:

| Signal | What it means |
|---|---|
| **GPG-signed commits** | Every commit by the maintainer is cryptographically signed. GitHub shows a green "Verified" badge on each commit. Public key: `45E3BABE58983A29`. |
| **Authenticode-signed `install.ps1`** | The installer is signed with an X.509 code-signing certificate. Attached `publisher.cer` lets you verify. Runs under `Set-ExecutionPolicy RemoteSigned`. |
| **Sigstore build-provenance attestation** | Every release artifact is attested via [sigstore](https://www.sigstore.dev/) / SLSA. Verify with `gh attestation verify`. |
| **SHA256SUMS.txt** | Every release ships checksums. Verify with `sha256sum -c SHA256SUMS.txt` or PowerShell `Get-FileHash`. |
| **CodeQL security scanning** | Every push and PR is scanned for Python and GitHub Actions vulnerabilities. |
| **OpenSSF Scorecard** | Automated supply-chain security rating. See the badge above. |
| **Dependabot** | Weekly dependency update PRs for Python packages and GitHub Actions. |
| **Private vulnerability reporting** | See [`SECURITY.md`](./SECURITY.md). |

### Verify a downloaded release

```powershell
# Verify the Authenticode signature on install.ps1
Get-AuthenticodeSignature install.ps1

# Verify file integrity against published hashes
Get-FileHash install.ps1 -Algorithm SHA256
# Compare with the line in SHA256SUMS.txt

# Verify sigstore attestation (requires gh CLI >= 2.49)
gh attestation verify install.ps1 --repo Tgbjr2025/stash-plex-bridge
```

## Support and contact

- Security reports — see [`SECURITY.md`](./SECURITY.md)
- General issues — [GitHub Issues](https://github.com/Tgbjr2025/stash-plex-bridge/issues)
- Maintainer — admin@dominusaxis.com · [dominusaxis.com](https://dominusaxis.com)
