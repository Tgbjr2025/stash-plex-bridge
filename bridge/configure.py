"""Phase 3: CONFIGURE — capture secrets and render plugin config files."""

from __future__ import annotations

import getpass
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from xml.etree import ElementTree as ET

import httpx
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from bridge import paths, tokens
from bridge.state import State

PromptText = Callable[[str], str]
PromptSecret = Callable[[str], str]
PromptLibrary = Callable[[list[str]], str]


@dataclass
class ConfigInputs:
    stash_url: str
    stash_api_key: str
    plex_url: str
    plex_token: str
    plex_library: str


def validate_plex_token(plex_url: str, token: str) -> bool:
    try:
        r = httpx.get(
            plex_url.rstrip("/") + "/",
            headers={"X-Plex-Token": token},
            timeout=5.0,
        )
    except httpx.HTTPError:
        return False
    return r.status_code == 200


def validate_stash_api_key(stash_url: str, api_key: str) -> bool:
    try:
        r = httpx.post(
            stash_url.rstrip("/") + "/graphql",
            headers={"ApiKey": api_key},
            json={"query": "{ me { id } }"},
            timeout=5.0,
        )
    except httpx.HTTPError:
        return False
    if r.status_code != 200:
        return False
    body = r.json()
    return "errors" not in body


def list_plex_libraries(plex_url: str, token: str) -> list[str]:
    r = httpx.get(
        plex_url.rstrip("/") + "/library/sections",
        headers={"X-Plex-Token": token},
        timeout=5.0,
    )
    r.raise_for_status()
    root = ET.fromstring(r.text)
    return [d.get("title", "") for d in root.findall("Directory")]


def _acquire_plex_token(
    state: State,
    plex_url: str,
    prompt_secret: PromptSecret,
) -> str:
    cached = state.get_secret("plex_token")
    if cached and validate_plex_token(plex_url, cached):
        return cached

    auto = tokens.extract_plex_token_from_prefs(paths.plex_preferences_path())
    if auto and validate_plex_token(plex_url, auto):
        state.set_secret("plex_token", auto)
        return auto

    for _ in range(3):
        entered = prompt_secret(
            "Paste your Plex token "
            "(see https://support.plex.tv/articles/204059436): "
        ).strip()
        if validate_plex_token(plex_url, entered):
            state.set_secret("plex_token", entered)
            return entered
        print("Token rejected by Plex. Try again.")
    raise RuntimeError("Failed to capture a valid Plex token after 3 attempts.")


def _acquire_stash_api_key(
    state: State,
    stash_url: str,
    prompt_secret: PromptSecret,
) -> str:
    cached = state.get_secret("stash_api_key")
    if cached and validate_stash_api_key(stash_url, cached):
        return cached

    print(
        f"Open {stash_url}/settings?tab=security to generate a Stash API key, "
        "then paste it below."
    )
    for _ in range(3):
        entered = prompt_secret("Stash API key: ").strip()
        if validate_stash_api_key(stash_url, entered):
            state.set_secret("stash_api_key", entered)
            return entered
        print("API key rejected by Stash. Try again.")
    raise RuntimeError("Failed to capture a valid Stash API key after 3 attempts.")


def _acquire_library(
    state: State,
    plex_url: str,
    plex_token: str,
    prompt_library: PromptLibrary,
) -> str:
    cached = state.get_secret("plex_library")
    if cached:
        return cached
    libs = list_plex_libraries(plex_url, plex_token)
    if not libs:
        raise RuntimeError("No Plex libraries found — create one in Plex first.")
    choice = prompt_library(libs)
    state.set_secret("plex_library", choice)
    return choice


def capture_inputs(
    state: State,
    *,
    stash_url: str,
    plex_url: str,
    prompt_text: PromptText = input,
    prompt_secret: PromptSecret = getpass.getpass,
    prompt_library: Optional[PromptLibrary] = None,
) -> ConfigInputs:
    if prompt_library is None:
        def prompt_library(libs: list[str]) -> str:
            print("Available Plex libraries:")
            for i, lib in enumerate(libs, 1):
                print(f"  {i}. {lib}")
            while True:
                raw = prompt_text("Pick a library number: ").strip()
                if raw.isdigit() and 1 <= int(raw) <= len(libs):
                    return libs[int(raw) - 1]

    plex_token = _acquire_plex_token(state, plex_url, prompt_secret)
    stash_api_key = _acquire_stash_api_key(state, stash_url, prompt_secret)
    plex_library = _acquire_library(state, plex_url, plex_token, prompt_library)

    return ConfigInputs(
        stash_url=stash_url,
        stash_api_key=stash_api_key,
        plex_url=plex_url,
        plex_token=plex_token,
        plex_library=plex_library,
    )


def render_configs(inputs: ConfigInputs, vendor_dir: Path) -> list[Path]:
    env = Environment(
        loader=FileSystemLoader(str(paths.templates_dir())),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    ctx = inputs.__dict__

    targets = [
        ("stash2plex.config.yml.j2",
         vendor_dir / "Stash2Plex" / "config.yml"),
        ("plexsync.config.yml.j2",
         vendor_dir / "CommunityScripts" / "plugins" / "PlexSync" / "config.yml"),
        ("stashplexagent.prefs.json.j2",
         vendor_dir / "StashPlexAgent.bundle" / "Contents" / "DefaultPrefs.json"),
    ]

    written: list[Path] = []
    for template_name, out_path in targets:
        rendered = env.get_template(template_name).render(**ctx)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered)
        written.append(out_path)
    return written
