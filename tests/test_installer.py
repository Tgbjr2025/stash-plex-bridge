from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from bridge.installer import main, build_arg_parser


def test_arg_parser_defaults():
    p = build_arg_parser()
    args = p.parse_args([])
    assert args.force is False
    assert args.phase is None
    assert args.update is False
    assert args.stash_port == 9999
    assert args.plex_port == 32400
    assert args.reset_tokens is False
    assert args.dry_run is False


def test_arg_parser_phase_flag():
    p = build_arg_parser()
    args = p.parse_args(["--phase", "detect"])
    assert args.phase == "detect"


def test_main_runs_all_phases_in_order(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "bridge").mkdir()
    (tmp_path / "state.json").write_text("{}")

    calls: list[str] = []

    def record(name):
        def _inner(*a, **kw):
            calls.append(name)
            if name == "detect":
                return MagicMock(
                    plex_install=tmp_path / "plex",
                    plex_plugins=tmp_path / "plex" / "Plug-ins",
                    stash_config=tmp_path / "stash",
                    stash_plugins=tmp_path / "stash" / "plugins",
                )
            if name == "fetch":
                return {"Stash2Plex": "s1", "CommunityScripts": "s2",
                        "StashPlexAgent.bundle": "s3"}
            if name == "configure_inputs":
                return MagicMock(
                    stash_url="http://localhost:9999",
                    stash_api_key="k",
                    plex_url="http://localhost:32400",
                    plex_token="t",
                    plex_library="Adult",
                )
            if name == "render":
                return []
            if name == "install":
                return []
            if name == "validate":
                return []
        return _inner

    with patch("bridge.installer.detect_paths", side_effect=record("detect")), \
         patch("bridge.installer.fetch_all", side_effect=record("fetch")), \
         patch("bridge.installer.capture_inputs",
               side_effect=record("configure_inputs")), \
         patch("bridge.installer.render_configs", side_effect=record("render")), \
         patch("bridge.installer.install_all", side_effect=record("install")), \
         patch("bridge.installer.run_all_checks", side_effect=record("validate")):
        rc = main([])

    assert rc == 0
    assert calls == ["detect", "fetch", "configure_inputs", "render",
                     "install", "validate"]


def test_main_single_phase(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls: list[str] = []

    def rec(name, ret=None):
        def _f(*a, **kw):
            calls.append(name)
            return ret
        return _f

    with patch("bridge.installer.detect_paths",
               side_effect=rec("detect",
                               MagicMock(
                                   plex_install=tmp_path,
                                   plex_plugins=tmp_path,
                                   stash_config=tmp_path,
                                   stash_plugins=tmp_path))), \
         patch("bridge.installer.fetch_all", side_effect=rec("fetch")):
        rc = main(["--phase", "detect"])

    assert rc == 0
    assert calls == ["detect"]


def test_main_exit_1_on_failure(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with patch("bridge.installer.detect_paths",
               side_effect=RuntimeError("boom")):
        rc = main([])
    assert rc == 1
