import json
from pathlib import Path
from unittest.mock import patch

import pytest
import respx
import httpx

from bridge.configure import (
    ConfigInputs,
    render_configs,
    validate_plex_token,
    validate_stash_api_key,
    list_plex_libraries,
    capture_inputs,
)


def _inputs() -> ConfigInputs:
    return ConfigInputs(
        stash_url="http://localhost:9999",
        stash_api_key="stash-key-xyz",
        plex_url="http://localhost:32400",
        plex_token="plex-token-abc",
        plex_library="Adult",
    )


def test_render_configs_produces_three_files(tmp_path: Path):
    vendor = tmp_path / "vendor"
    (vendor / "Stash2Plex").mkdir(parents=True)
    (vendor / "CommunityScripts" / "plugins" / "PlexSync").mkdir(parents=True)
    (vendor / "StashPlexAgent.bundle" / "Contents").mkdir(parents=True)

    written = render_configs(_inputs(), vendor)

    assert (vendor / "Stash2Plex" / "config.yml") in written
    assert (vendor / "CommunityScripts" / "plugins" / "PlexSync" / "config.yml") in written
    assert (vendor / "StashPlexAgent.bundle" / "Contents" / "DefaultPrefs.json") in written

    s2p = (vendor / "Stash2Plex" / "config.yml").read_text()
    assert "plex-token-abc" in s2p
    assert "stash-key-xyz" in s2p
    assert "http://localhost:32400" in s2p

    prefs_json = json.loads(
        (vendor / "StashPlexAgent.bundle" / "Contents" / "DefaultPrefs.json").read_text()
    )
    assert prefs_json["stash_api_key"] == "stash-key-xyz"


@respx.mock
def test_validate_plex_token_ok():
    respx.get("http://localhost:32400/").mock(
        return_value=httpx.Response(200, text='<MediaContainer friendlyName="Home"/>')
    )
    assert validate_plex_token("http://localhost:32400", "t") is True


@respx.mock
def test_validate_plex_token_unauthorized():
    respx.get("http://localhost:32400/").mock(return_value=httpx.Response(401))
    assert validate_plex_token("http://localhost:32400", "bad") is False


@respx.mock
def test_validate_stash_api_key_ok():
    respx.post("http://localhost:9999/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"me": {"id": "1"}}})
    )
    assert validate_stash_api_key("http://localhost:9999", "k") is True


@respx.mock
def test_validate_stash_api_key_bad():
    respx.post("http://localhost:9999/graphql").mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "unauthorized"}]})
    )
    assert validate_stash_api_key("http://localhost:9999", "k") is False


@respx.mock
def test_list_plex_libraries():
    respx.get("http://localhost:32400/library/sections").mock(
        return_value=httpx.Response(
            200,
            text=(
                '<MediaContainer>'
                '<Directory key="1" title="Movies" type="movie"/>'
                '<Directory key="2" title="Adult" type="movie"/>'
                '</MediaContainer>'
            ),
        )
    )
    libs = list_plex_libraries("http://localhost:32400", "t")
    assert libs == ["Movies", "Adult"]


def test_capture_inputs_uses_state_cache(tmp_path: Path, monkeypatch):
    from bridge.state import State
    state = State.load(tmp_path / "state.json")
    state.set_secret("plex_token", "cached-plex")
    state.set_secret("stash_api_key", "cached-stash")
    state.set_secret("plex_library", "Adult")

    with patch("bridge.configure.validate_plex_token", return_value=True), \
         patch("bridge.configure.validate_stash_api_key", return_value=True):
        inputs = capture_inputs(
            state,
            stash_url="http://localhost:9999",
            plex_url="http://localhost:32400",
            prompt_text=lambda m: pytest.fail("should not prompt"),
            prompt_secret=lambda m: pytest.fail("should not prompt for secret"),
            prompt_library=lambda libs: pytest.fail("should not prompt for library"),
        )
    assert inputs.plex_token == "cached-plex"
    assert inputs.stash_api_key == "cached-stash"
    assert inputs.plex_library == "Adult"
