from pathlib import Path
from unittest.mock import patch

import pytest

from bridge.install_plugins import (
    install_plexsync,
    install_stashplexagent,
    write_run_sync_script,
    install_all,
    InstallTargets,
)


def _make_vendor(tmp_path: Path) -> Path:
    vendor = tmp_path / "vendor"
    plexsync = vendor / "CommunityScripts" / "plugins" / "PlexSync"
    plexsync.mkdir(parents=True)
    (plexsync / "plexsync.py").write_text("# plexsync")
    (plexsync / "config.yml").write_text("plex_url: x")
    (plexsync / "requirements.txt").write_text("requests\n")

    agent = vendor / "StashPlexAgent.bundle"
    (agent / "Contents").mkdir(parents=True)
    (agent / "Contents" / "Info.plist").write_text("<plist/>")
    (agent / "Contents" / "DefaultPrefs.json").write_text("{}")

    s2p = vendor / "Stash2Plex"
    s2p.mkdir()
    (s2p / "sync.py").write_text("# sync")

    return vendor


def test_install_plexsync_copies_tree(tmp_path: Path):
    vendor = _make_vendor(tmp_path)
    stash_plugins = tmp_path / "stash_plugins"
    stash_plugins.mkdir()

    with patch("bridge.install_plugins._pip_install_into") as mpip:
        copied = install_plexsync(vendor, stash_plugins)
        mpip.assert_called_once()

    target = stash_plugins / "PlexSync"
    assert target.is_dir()
    assert (target / "plexsync.py").exists()
    assert (target / "config.yml").exists()
    assert target in copied or str(target) in map(str, copied)


def test_install_plexsync_is_idempotent(tmp_path: Path):
    vendor = _make_vendor(tmp_path)
    stash_plugins = tmp_path / "stash_plugins"
    stash_plugins.mkdir()

    with patch("bridge.install_plugins._pip_install_into"):
        install_plexsync(vendor, stash_plugins)
        install_plexsync(vendor, stash_plugins)

    assert (stash_plugins / "PlexSync" / "plexsync.py").exists()


def test_install_stashplexagent_copies_bundle(tmp_path: Path):
    vendor = _make_vendor(tmp_path)
    plex_plugins = tmp_path / "plex_plugins"
    plex_plugins.mkdir()

    target = install_stashplexagent(vendor, plex_plugins)

    assert target == plex_plugins / "StashPlexAgent.bundle"
    assert (target / "Contents" / "Info.plist").exists()
    assert (target / "Contents" / "DefaultPrefs.json").exists()


def test_write_run_sync_script(tmp_path: Path):
    vendor = _make_vendor(tmp_path)
    script = write_run_sync_script(tmp_path, vendor)
    assert script.exists()
    content = script.read_text()
    assert "Stash2Plex" in content
    assert "python" in content.lower()


def test_install_all_returns_files(tmp_path: Path):
    vendor = _make_vendor(tmp_path)
    targets = InstallTargets(
        stash_plugins=tmp_path / "stash_plugins",
        plex_plugins=tmp_path / "plex_plugins",
        project_root=tmp_path / "project",
    )
    targets.stash_plugins.mkdir()
    targets.plex_plugins.mkdir()
    targets.project_root.mkdir()

    with patch("bridge.install_plugins._pip_install_into"):
        files = install_all(vendor, targets)

    assert any("PlexSync" in str(f) for f in files)
    assert any("StashPlexAgent.bundle" in str(f) for f in files)
    assert any("run-sync.ps1" in str(f) for f in files)
