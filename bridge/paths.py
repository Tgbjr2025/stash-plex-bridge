"""Windows path constants and environment lookups.

On non-Windows hosts (e.g. macOS dev box) env vars are typically unset;
tests must set them via monkeypatch.
"""

from __future__ import annotations

import os
from pathlib import Path


class EnvNotSet(RuntimeError):
    """Raised when a required environment variable is missing."""


def _env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise EnvNotSet(f"Environment variable {name!r} is not set")
    return val


def plex_preferences_path() -> Path:
    return Path(_env("LOCALAPPDATA")) / "Plex Media Server" / "Preferences.xml"


def plex_plugins_dir() -> Path:
    return Path(_env("LOCALAPPDATA")) / "Plex Media Server" / "Plug-ins"


def plex_install_dir() -> Path:
    return Path(_env("LOCALAPPDATA")) / "Plex Media Server"


def stash_config_candidates() -> list[Path]:
    candidates: list[Path] = []
    try:
        candidates.append(Path(_env("USERPROFILE")) / ".stash")
    except EnvNotSet:
        pass
    try:
        candidates.append(Path(_env("APPDATA")) / "stash")
    except EnvNotSet:
        pass
    return candidates


def project_root() -> Path:
    """Project root is the parent of the `bridge/` package directory."""
    return Path(__file__).resolve().parent.parent


def vendor_dir() -> Path:
    return project_root() / "vendor"


def templates_dir() -> Path:
    return project_root() / "templates"


def state_file() -> Path:
    return project_root() / "state.json"


def logs_dir() -> Path:
    return project_root() / "bridge" / "logs"
