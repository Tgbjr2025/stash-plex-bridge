# stash-plex-bridge — Design

**Date:** 2026-04-19
**Owner:** Thomas Bateman
**Status:** Draft — awaiting review

## Summary

An automated Windows-side wrapper that installs and configures three third-party plugins bridging Stash (porn library manager) and Plex (media server): `Stash2Plex`, `PlexSync`, and `StashPlexAgent.bundle`. The wrapper handles port/config setup, token generation and placement, and is safely rerunnable.

## Goals

- One-command install on a Windows box where Stash and Plex are already installed and running.
- Auto-discover install paths, plugin directories, and the Plex token where possible.
- Prompt (once) for anything that cannot be auto-discovered — never twice on rerun.
- Place all plugin files in correct directories and render all config files with correct URLs/ports/tokens.
- Validate end-to-end connectivity (Stash API, Plex API, plugin load) and surface failures with actionable messages.
- Idempotent: rerunning after a partial failure resumes from the failed phase.

## Non-goals (YAGNI)

- No GUI. Terminal only.
- No macOS/Linux support for the wrapper itself.
- No auto-updates on a schedule — `install.ps1 --update` is manual.
- No uninstaller in v1.
- No support for split-host setups (Stash on one box, Plex on another) in v1.
- No installation of Stash or Plex themselves — they are prerequisites.

## Third-party plugins integrated

| Plugin | Repo | Role |
|---|---|---|
| Stash2Plex | `trek-e/Stash2Plex` | Standalone sync tool: pushes Stash metadata into Plex |
| PlexSync | `stashapp/CommunityScripts` → `plugins/PlexSync` | Stash plugin: auto-refreshes Plex when Stash scenes change |
| StashPlexAgent.bundle | `Darklyter/StashPlexAgent.bundle` | Plex agent: pulls Stash metadata during Plex scans |

## Architecture

**Shape:** PowerShell bootstrapper → Python installer, shipped as a single folder copied to the Windows box.

```
install.ps1                      # bootstrap (deps, venv, launch installer)
    ↓
python -m bridge.installer       # 5 idempotent phases
    ↓
  DETECT → FETCH → CONFIGURE → INSTALL → VALIDATE
```

State file `state.json` tracks phase completion + input hashes. Phases skip when `status=ok` and inputs unchanged.

### File layout

```
stash-plex-bridge/
├── install.ps1                  # bootstrap: deps, venv, launches installer
├── README.md                    # usage, troubleshooting
├── bridge/
│   ├── __init__.py
│   ├── installer.py             # phase orchestrator, CLI entrypoint
│   ├── state.py                 # load/save state.json, phase-skip logic
│   ├── detect.py                # find Stash/Plex install + plugin dirs
│   ├── fetch.py                 # git clone/pull the 3 vendor repos
│   ├── configure.py             # token capture, config rendering
│   ├── install_plugins.py       # copy vendor → plugin dirs
│   ├── validate.py              # API health checks
│   ├── tokens.py                # Plex token auto-extract + paste fallback
│   └── paths.py                 # Windows path constants, env lookups
├── templates/
│   ├── stash2plex.config.j2
│   └── plexsync.config.j2
├── vendor/                      # populated by fetch phase (gitignored)
├── tests/
├── state.json                   # phase state (gitignored)
└── .gitignore
```

## Phases

### Phase 1 — DETECT (`detect.py`)

Finds four paths and writes them to `state.json.paths`:

- **Plex install** — registry `HKLM:\SOFTWARE\Plex, Inc.\Plex Media Server` → fallback `%LOCALAPPDATA%\Plex Media Server`
- **Plex plugins dir** — `%LOCALAPPDATA%\Plex Media Server\Plug-ins`
- **Stash install** — check `%USERPROFILE%\.stash`, `%APPDATA%\stash`, common install locations → prompt if none found
- **Stash plugins dir** — `<stash-config>\plugins`

Prompts once per missing path; results persist across reruns.

### Phase 2 — FETCH (`fetch.py`)

`git clone` (or `pull` if exists) into `vendor/`:

- `https://github.com/trek-e/Stash2Plex`
- `https://github.com/stashapp/CommunityScripts` — sparse-checkout `plugins/PlexSync` only
- `https://github.com/Darklyter/StashPlexAgent.bundle`

Commit SHAs pinned in `state.json.phases.fetch.commits` for reproducibility. `--update` flag bumps to latest and updates the pins.

Network errors → retry 3× with exponential backoff, then fail the phase.

### Phase 3 — CONFIGURE (`configure.py`)

**Secrets capture:**
- **Plex token** — `tokens.extract_plex_token()` reads `%LOCALAPPDATA%\Plex Media Server\Preferences.xml` (`PlexOnlineToken` attribute). Fallback: masked paste prompt. Token is validated with `GET /?X-Plex-Token=...` before saving.
- **Stash API key** — always prompted (no auto-extract possible). Masked input. Validated with a `viewer { id }` GraphQL query before saving.
- **Plex library name** — list libraries via `GET /library/sections`, user picks one.

**Config rendering (Jinja2 templates → config files):**
- `vendor/Stash2Plex/config.yml` — `stash_url`, `stash_api_key`, `plex_url`, `plex_token`, `plex_library`
- `vendor/CommunityScripts/plugins/PlexSync/config.yml` — `plex_url`, `plex_token`, `plex_library`, `clean_titles: true`
- `vendor/StashPlexAgent.bundle/Contents/DefaultPrefs.json` — `stash_url`, `stash_api_key`, collection-tag toggles

**Ports:** default `9999` (Stash) and `32400` (Plex); overridable via `--stash-port` / `--plex-port` flags.

### Phase 4 — INSTALL (`install_plugins.py`)

- Copy `vendor/CommunityScripts/plugins/PlexSync/` → `<stash-plugins>/PlexSync/`
- Install PlexSync's Python deps into that folder: `pip install -r requirements.txt -t .`
- Copy `vendor/StashPlexAgent.bundle/` → `<plex-plugins>/StashPlexAgent.bundle/`
- Stash2Plex stays in `vendor/` and runs as a standalone sync tool; wrapper writes a `run-sync.ps1` shortcut at the project root
- Prompt: restart Plex Media Server now? (required for Plex to see the new agent)

### Phase 5 — VALIDATE (`validate.py`)

- `GET http://localhost:<stash-port>/graphql` (with API key) → expect 200 + valid `viewer` response
- `GET http://localhost:<plex-port>/?X-Plex-Token=...` → expect 200 + server name
- `GET <stash>/plugins` → confirm PlexSync listed
- `GET <plex>/:/plugins/all` → confirm StashPlexAgent listed

Prints summary table. Exits non-zero if any check fails.

## Secrets handling

- `state.json` is written with user-only ACL: `icacls state.json /inheritance:r /grant:r "$env:USERNAME:F"`
- Secrets also live inside plugin config files (unavoidable — that's how the plugins consume them)
- `.gitignore` covers `state.json`, `vendor/`, `*.log`, `bridge/.venv/`
- `--reset-tokens` flag wipes tokens from state and re-prompts

## Rerunnability

`state.json` schema:

```json
{
  "version": 1,
  "phases": {
    "detect":    {"status": "ok|failed", "ran_at": "...", "inputs_hash": "...", "error": null},
    "fetch":     {"status": "ok", "commits": {"Stash2Plex": "abc123", "PlexSync": "...", "StashPlexAgent": "..."}},
    "configure": {"status": "ok", "config_hash": "..."},
    "install":   {"status": "ok", "files": ["..."]},
    "validate":  {"status": "ok", "checks": [{"name": "stash-api", "ok": true}, ...]}
  },
  "paths": {
    "plex_install": "...",
    "plex_plugins": "...",
    "stash_config": "...",
    "stash_plugins": "..."
  },
  "secrets": {
    "plex_token": "...",
    "stash_api_key": "...",
    "plex_library": "..."
  }
}
```

- Phase skips when `status=ok` AND `inputs_hash` unchanged
- `--force` reruns everything; `--phase <name>` runs just one; `--update` refreshes vendor commits

## Error handling

- Every phase wrapped in try/except → marks phase `failed` with error string, prints actionable message, exits 1
- Network errors during FETCH → retry 3× with exponential backoff, then fail clean
- Missing admin rights for Plex plugin dir write → detect up-front, print "run PowerShell as admin"
- Stash/Plex service not running at VALIDATE → print "start the service and rerun `install.ps1 --phase validate`"
- All runs log to `.\bridge\logs\install-YYYYMMDD-HHMMSS.log`

## Testing

Directory: `tests/` (pytest).

- `test_detect.py` — mock registry + filesystem, verify path resolution + fallbacks
- `test_tokens.py` — fixture `Preferences.xml`, verify extraction works and handles missing file
- `test_state.py` — write/read/skip-logic round-trip, phase resumption
- `test_configure.py` — template rendering with fake inputs produces expected YAML/JSON
- Integration smoke test: `--dry-run` flag runs all phases against a mocked HTTP server (`respx` or equivalent) to verify no crashes end-to-end

Final acceptance: manual run on the actual Windows box.

## Bootstrap requirements (handled by `install.ps1`)

- `git` — install via `winget install Git.Git` if missing
- `python3` (3.10+) — install via `winget install Python.Python.3.11` if missing
- Python venv at `.\bridge\.venv` with `requests`, `stashapi`, `unidecode`, `lxml`, `jinja2`, `pyyaml`
- On rerun: venv reused if present; `pip install` skipped if `requirements.txt` hash unchanged

## Open questions / risks

- **PlexSync config format uncertainty** — README only documents one setting (`Clean titles`); the actual config schema may have more fields. The FETCH phase will let us inspect the real plugin file and refine the template before first release.
- **StashPlexAgent preferences format** — README mentions `DefaultPrefs.json` conceptually but exact field names need to be read from the bundle. Same refinement path.
- **Stash API key**: no programmatic generation — user must create it once in the Stash UI. Wrapper will open the correct URL (`http://localhost:9999/settings?tab=security`) to shortcut this.
