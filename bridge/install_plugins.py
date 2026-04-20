"""Phase 4: INSTALL — copy plugin files into Stash and Plex plugin dirs."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InstallTargets:
    stash_plugins: Path
    plex_plugins: Path
    project_root: Path


def _pip_install_into(requirements: Path, target_dir: Path) -> None:
    """Install Python deps into the plugin folder (Stash plugins expect this)."""
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "-r", str(requirements),
            "-t", str(target_dir),
            "--upgrade",
        ],
        check=True,
    )


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def install_plexsync(vendor_dir: Path, stash_plugins: Path) -> list[Path]:
    src = vendor_dir / "CommunityScripts" / "plugins" / "PlexSync"
    dst = stash_plugins / "PlexSync"
    _copy_tree(src, dst)

    reqs = dst / "requirements.txt"
    if reqs.exists():
        _pip_install_into(reqs, dst)

    return [dst]


def install_stashplexagent(vendor_dir: Path, plex_plugins: Path) -> Path:
    src = vendor_dir / "StashPlexAgent.bundle"
    dst = plex_plugins / "StashPlexAgent.bundle"
    _copy_tree(src, dst)
    return dst


def write_run_sync_script(project_root: Path, vendor_dir: Path) -> Path:
    script = project_root / "run-sync.ps1"
    rel_vendor = vendor_dir / "Stash2Plex"
    venv_py = project_root / "bridge" / ".venv" / "Scripts" / "python.exe"
    content = f"""# Run Stash2Plex one-shot sync
$ErrorActionPreference = "Stop"
Push-Location "{rel_vendor}"
try {{
    & "{venv_py}" sync.py @args
}} finally {{
    Pop-Location
}}
"""
    script.write_text(content)
    return script


def install_all(vendor_dir: Path, targets: InstallTargets) -> list[Path]:
    written: list[Path] = []
    written.extend(install_plexsync(vendor_dir, targets.stash_plugins))
    written.append(install_stashplexagent(vendor_dir, targets.plex_plugins))
    written.append(write_run_sync_script(targets.project_root, vendor_dir))
    return written
