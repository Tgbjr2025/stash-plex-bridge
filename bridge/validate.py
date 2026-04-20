"""Phase 5: VALIDATE — end-to-end health checks."""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET

import httpx


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


def check_stash_api(stash_url: str, api_key: str) -> Check:
    try:
        r = httpx.post(
            stash_url.rstrip("/") + "/graphql",
            headers={"ApiKey": api_key},
            json={"query": "{ me { id } }"},
            timeout=5.0,
        )
    except httpx.HTTPError as e:
        return Check("stash-api", False, f"http error: {e}")
    if r.status_code != 200:
        return Check("stash-api", False, f"status {r.status_code}")
    body = r.json()
    if "errors" in body:
        return Check("stash-api", False, str(body["errors"]))
    return Check("stash-api", True, "ok")


def check_plex_api(plex_url: str, token: str) -> Check:
    try:
        r = httpx.get(
            plex_url.rstrip("/") + "/",
            headers={"X-Plex-Token": token},
            timeout=5.0,
        )
    except httpx.HTTPError as e:
        return Check("plex-api", False, f"http error: {e}")
    if r.status_code != 200:
        return Check("plex-api", False, f"status {r.status_code}")
    try:
        root = ET.fromstring(r.text)
        name = root.get("friendlyName", "")
    except ET.ParseError:
        name = ""
    return Check("plex-api", True, f"server: {name}")


def check_plugin_loaded_stash(
    stash_url: str, api_key: str, plugin_id: str
) -> Check:
    try:
        r = httpx.post(
            stash_url.rstrip("/") + "/graphql",
            headers={"ApiKey": api_key},
            json={"query": "{ plugins { id name } }"},
            timeout=5.0,
        )
    except httpx.HTTPError as e:
        return Check("stash-plugin", False, f"http error: {e}")
    if r.status_code != 200:
        return Check("stash-plugin", False, f"status {r.status_code}")
    plugins = (r.json().get("data") or {}).get("plugins") or []
    found = any(p.get("id") == plugin_id or p.get("name") == plugin_id
                for p in plugins)
    return Check(
        "stash-plugin",
        found,
        f"{plugin_id} {'loaded' if found else 'not found'}",
    )


def check_plugin_loaded_plex(
    plex_url: str, token: str, identifier: str
) -> Check:
    try:
        r = httpx.get(
            plex_url.rstrip("/") + "/:/plugins/all",
            headers={"X-Plex-Token": token},
            timeout=5.0,
        )
    except httpx.HTTPError as e:
        return Check("plex-plugin", False, f"http error: {e}")
    if r.status_code != 200:
        return Check("plex-plugin", False, f"status {r.status_code}")
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError:
        return Check("plex-plugin", False, "malformed response")
    found = any(
        p.get("identifier") == identifier for p in root.findall("Plugin")
    )
    return Check(
        "plex-plugin",
        found,
        f"{identifier} {'loaded' if found else 'not found'}",
    )


def run_all_checks(
    *,
    stash_url: str,
    stash_api_key: str,
    plex_url: str,
    plex_token: str,
    stash_plugin_id: str = "PlexSync",
    plex_plugin_id: str = "com.plexapp.agents.stashplex",
) -> list[Check]:
    return [
        check_stash_api(stash_url, stash_api_key),
        check_plex_api(plex_url, plex_token),
        check_plugin_loaded_stash(stash_url, stash_api_key, stash_plugin_id),
        check_plugin_loaded_plex(plex_url, plex_token, plex_plugin_id),
    ]
