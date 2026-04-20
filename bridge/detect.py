"""Phase 1: DETECT — find Stash and Plex install/plugin directories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from bridge import paths
from bridge.state import State

PromptFn = Callable[[str], str]


@dataclass
class DetectionResult:
    plex_install: Path
    plex_plugins: Path
    stash_config: Path
    stash_plugins: Path


def _resolve_plex(state: State) -> tuple[Path, Path]:
    cached = state.get_path("plex_install")
    if cached and Path(cached).is_dir():
        install = Path(cached)
    else:
        install = paths.plex_install_dir()
        if not install.is_dir():
            raise FileNotFoundError(
                f"Plex install not found at {install}. "
                "Ensure Plex Media Server is installed on this machine."
            )
    plugins = install / "Plug-ins"
    plugins.mkdir(parents=True, exist_ok=True)
    return install, plugins


def _resolve_stash(state: State, prompt: PromptFn) -> tuple[Path, Path]:
    cached = state.get_path("stash_config")
    if cached and Path(cached).is_dir():
        config = Path(cached)
    else:
        config = None
        for candidate in paths.stash_config_candidates():
            if candidate.is_dir():
                config = candidate
                break
        if config is None:
            answer = prompt(
                "Stash config directory not found in default locations.\n"
                "Enter the full path to your Stash config dir "
                "(e.g. C:\\Users\\you\\.stash): "
            ).strip().strip('"')
            config = Path(answer)
            if not config.is_dir():
                raise FileNotFoundError(f"Stash config dir not found: {config}")
    plugins = config / "plugins"
    plugins.mkdir(parents=True, exist_ok=True)
    return config, plugins


def detect_paths(state: State, prompt: PromptFn = input) -> DetectionResult:
    plex_install, plex_plugins = _resolve_plex(state)
    stash_config, stash_plugins = _resolve_stash(state, prompt)

    state.set_path("plex_install", str(plex_install))
    state.set_path("plex_plugins", str(plex_plugins))
    state.set_path("stash_config", str(stash_config))
    state.set_path("stash_plugins", str(stash_plugins))

    return DetectionResult(
        plex_install=plex_install,
        plex_plugins=plex_plugins,
        stash_config=stash_config,
        stash_plugins=stash_plugins,
    )
