import httpx
import pytest
import respx

from bridge.validate import (
    check_stash_api,
    check_plex_api,
    check_plugin_loaded_stash,
    check_plugin_loaded_plex,
    run_all_checks,
    Check,
)


@respx.mock
def test_check_stash_api_pass():
    respx.post("http://localhost:9999/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"me": {"id": "1"}}})
    )
    c = check_stash_api("http://localhost:9999", "k")
    assert c.ok
    assert c.name == "stash-api"


@respx.mock
def test_check_stash_api_fail_on_error():
    respx.post("http://localhost:9999/graphql").mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "unauth"}]})
    )
    c = check_stash_api("http://localhost:9999", "k")
    assert not c.ok
    assert "unauth" in c.detail


@respx.mock
def test_check_plex_api_pass():
    respx.get("http://localhost:32400/").mock(
        return_value=httpx.Response(200, text='<MediaContainer friendlyName="Home"/>')
    )
    c = check_plex_api("http://localhost:32400", "t")
    assert c.ok
    assert "Home" in c.detail


@respx.mock
def test_check_plex_api_fail():
    respx.get("http://localhost:32400/").mock(return_value=httpx.Response(401))
    assert not check_plex_api("http://localhost:32400", "bad").ok


@respx.mock
def test_check_stash_plugin_loaded():
    respx.post("http://localhost:9999/graphql").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"plugins": [{"id": "PlexSync", "name": "PlexSync"}]}},
        )
    )
    assert check_plugin_loaded_stash("http://localhost:9999", "k", "PlexSync").ok


@respx.mock
def test_check_stash_plugin_not_loaded():
    respx.post("http://localhost:9999/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"plugins": []}})
    )
    assert not check_plugin_loaded_stash("http://localhost:9999", "k", "PlexSync").ok


@respx.mock
def test_check_plex_plugin_loaded():
    respx.get("http://localhost:32400/:/plugins/all").mock(
        return_value=httpx.Response(
            200,
            text=(
                '<MediaContainer>'
                '<Plugin identifier="com.plexapp.agents.stashplex"/>'
                '</MediaContainer>'
            ),
        )
    )
    assert check_plugin_loaded_plex(
        "http://localhost:32400", "t", "com.plexapp.agents.stashplex"
    ).ok


@respx.mock
def test_run_all_checks_aggregates():
    respx.post("http://localhost:9999/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"me": {"id": "1"}, "plugins": []}})
    )
    respx.get("http://localhost:32400/").mock(
        return_value=httpx.Response(200, text='<MediaContainer friendlyName="X"/>')
    )
    respx.get("http://localhost:32400/:/plugins/all").mock(
        return_value=httpx.Response(200, text='<MediaContainer/>')
    )
    checks = run_all_checks(
        stash_url="http://localhost:9999",
        stash_api_key="k",
        plex_url="http://localhost:32400",
        plex_token="t",
    )
    assert len(checks) == 4
    names = {c.name for c in checks}
    assert names == {"stash-api", "plex-api", "stash-plugin", "plex-plugin"}
