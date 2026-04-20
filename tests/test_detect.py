from pathlib import Path

import pytest

from bridge.detect import detect_paths, DetectionResult
from bridge.state import State


def _setup_fake_windows(monkeypatch, tmp_path: Path, *, with_stash: bool = True):
    local = tmp_path / "LocalAppData"
    userprofile = tmp_path / "Users" / "me"
    appdata = tmp_path / "Users" / "me" / "AppData" / "Roaming"
    for p in (local, userprofile, appdata):
        p.mkdir(parents=True, exist_ok=True)

    plex = local / "Plex Media Server"
    (plex / "Plug-ins").mkdir(parents=True)
    (plex / "Preferences.xml").write_text(
        '<?xml version="1.0"?><Preferences PlexOnlineToken="t"/>'
    )

    if with_stash:
        stash = userprofile / ".stash"
        (stash / "plugins").mkdir(parents=True)
        (stash / "config.yml").write_text("stash_config: {}\n")

    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("USERPROFILE", str(userprofile))
    monkeypatch.setenv("APPDATA", str(appdata))


def test_detect_all_paths_present(monkeypatch, tmp_path: Path):
    _setup_fake_windows(monkeypatch, tmp_path)
    state = State.load(tmp_path / "state.json")

    result = detect_paths(state, prompt=lambda _msg: pytest.fail("no prompt expected"))

    assert isinstance(result, DetectionResult)
    assert result.plex_install.name == "Plex Media Server"
    assert result.plex_plugins.name == "Plug-ins"
    assert result.stash_config.name == ".stash"
    assert result.stash_plugins.name == "plugins"
    assert state.get_path("plex_plugins") == str(result.plex_plugins)
    assert state.get_path("stash_plugins") == str(result.stash_plugins)


def test_detect_prompts_for_missing_stash(monkeypatch, tmp_path: Path):
    _setup_fake_windows(monkeypatch, tmp_path, with_stash=False)
    custom_stash = tmp_path / "custom_stash"
    (custom_stash / "plugins").mkdir(parents=True)

    calls: list[str] = []

    def prompt(msg: str) -> str:
        calls.append(msg)
        return str(custom_stash)

    state = State.load(tmp_path / "state.json")
    result = detect_paths(state, prompt=prompt)

    assert len(calls) == 1
    assert "Stash" in calls[0]
    assert result.stash_config == custom_stash
    assert result.stash_plugins == custom_stash / "plugins"


def test_detect_raises_on_missing_plex(monkeypatch, tmp_path: Path):
    userprofile = tmp_path / "Users" / "me"
    userprofile.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Missing"))
    monkeypatch.setenv("USERPROFILE", str(userprofile))
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))

    state = State.load(tmp_path / "state.json")
    with pytest.raises(FileNotFoundError, match="Plex"):
        detect_paths(state, prompt=lambda m: "")


def test_detect_caches_results_in_state(monkeypatch, tmp_path: Path):
    _setup_fake_windows(monkeypatch, tmp_path, with_stash=False)
    state = State.load(tmp_path / "state.json")
    state.set_path("stash_config", str(tmp_path / "cached_stash"))
    (tmp_path / "cached_stash" / "plugins").mkdir(parents=True)

    result = detect_paths(
        state, prompt=lambda m: pytest.fail("should not prompt when cached")
    )
    assert result.stash_config == tmp_path / "cached_stash"
