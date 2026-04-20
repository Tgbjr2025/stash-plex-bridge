from pathlib import Path

import pytest

from bridge import paths


def test_plex_prefs_path(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    expected = tmp_path / "Plex Media Server" / "Preferences.xml"
    assert paths.plex_preferences_path() == expected


def test_plex_plugins_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    expected = tmp_path / "Plex Media Server" / "Plug-ins"
    assert paths.plex_plugins_dir() == expected


def test_stash_config_candidates(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    got = paths.stash_config_candidates()
    assert tmp_path / ".stash" in got
    assert tmp_path / "AppData" / "Roaming" / "stash" in got


def test_env_missing_raises(monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    with pytest.raises(paths.EnvNotSet):
        paths.plex_preferences_path()


def test_project_root_resolves():
    root = paths.project_root()
    assert root.is_dir()
    assert (root / "bridge").is_dir()
