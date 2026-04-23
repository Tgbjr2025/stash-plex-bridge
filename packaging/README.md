# Packaging

Package-manager manifests for distributing `stash-plex-bridge` via third-party
registries so end users install it with zero warnings.

## Why this matters

Windows SmartScreen warns on any unsigned binary — and a self-signed Authenticode
certificate still shows "Unknown Publisher." The only *free* paths to a warning-free
install are:

1. Distribute via a trusted package manager (**winget**, **Chocolatey**, **Scoop**).
2. Get approved to [SignPath.io's free OSS program](https://signpath.io/open-source) for
   real EV Authenticode signing.

This directory contains the manifests for path 1. SignPath.io application is tracked
in `docs/signpath-application.md`.

## Manifests

| Manager | Install command | Manifest |
|---|---|---|
| **winget** | `winget install Tgbjr2025.StashPlexBridge` | `winget/*.yaml` |
| **Scoop** | `scoop install stash-plex-bridge` | `scoop/stash-plex-bridge.json` |
| **Chocolatey** | `choco install stash-plex-bridge` | `chocolatey/*.nuspec` |

## How to update after each release

Every new release changes the `InstallerSha256` / `hash` / `checksum` fields.
The GitHub Actions release workflow prints the SHA256 — copy it into all three
manifests, then submit the PRs (see submission steps below).

## Submission steps

### winget (Microsoft)

1. Fork https://github.com/microsoft/winget-pkgs
2. Place the three yaml files in `manifests/t/Tgbjr2025/StashPlexBridge/1.0.0/`
3. Update `InstallerSha256` with the real hash
4. Open a PR — auto-validated by Microsoft's bot, merged within 1–7 days.

### Scoop

1. Fork https://github.com/ScoopInstaller/Main (or use `Extras` bucket for less-strict reviews)
2. Add `bucket/stash-plex-bridge.json` with the real `hash`
3. Open a PR.

### Chocolatey

1. Build the nupkg locally: `choco pack packaging/chocolatey/stash-plex-bridge.nuspec`
2. Push to Chocolatey Community Repo: `choco push stash-plex-bridge.1.0.0.nupkg --source https://push.chocolatey.org/`
3. Moderation review takes 1–14 days.

### PowerShell Gallery (optional)

Only useful if we restructure `install.ps1` as a proper PS module (`.psm1` + manifest).
Deferred until v1.1.

## Verification checklist after release

- [ ] All three manifests updated with correct SHA256
- [ ] winget PR opened and merged
- [ ] Scoop PR opened and merged
- [ ] Chocolatey package submitted and approved
- [ ] README badges render green
- [ ] `gh attestation verify install.ps1 --repo Tgbjr2025/stash-plex-bridge` succeeds
