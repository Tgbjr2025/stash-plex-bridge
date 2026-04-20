# stash-plex-bridge

Automated Windows installer for three Stash↔Plex plugins:
Stash2Plex, PlexSync, StashPlexAgent.bundle.

See `docs/superpowers/specs/2026-04-19-stash-plex-bridge-design.md`.

## Quick start (on target Windows box)
Copy this folder to the Windows machine where Stash and Plex are installed,
then from PowerShell:

```powershell
.\install.ps1
```

Rerun anytime; completed phases are skipped.
