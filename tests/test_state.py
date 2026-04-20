import json
from pathlib import Path

import pytest

from bridge.state import State, PhaseStatus


def test_state_roundtrip(tmp_path: Path):
    path = tmp_path / "state.json"
    s = State.load(path)
    assert s.version == 1
    assert s.get_phase("detect").status == PhaseStatus.PENDING

    s.set_phase("detect", PhaseStatus.OK, inputs_hash="abc")
    s.save()

    s2 = State.load(path)
    assert s2.get_phase("detect").status == PhaseStatus.OK
    assert s2.get_phase("detect").inputs_hash == "abc"


def test_should_run_skips_when_ok_and_hash_matches(tmp_path: Path):
    s = State.load(tmp_path / "state.json")
    s.set_phase("detect", PhaseStatus.OK, inputs_hash="abc")
    assert not s.should_run("detect", inputs_hash="abc")
    assert s.should_run("detect", inputs_hash="different")


def test_should_run_true_when_failed(tmp_path: Path):
    s = State.load(tmp_path / "state.json")
    s.set_phase("detect", PhaseStatus.FAILED, inputs_hash="abc", error="boom")
    assert s.should_run("detect", inputs_hash="abc")


def test_should_run_force_overrides(tmp_path: Path):
    s = State.load(tmp_path / "state.json")
    s.set_phase("detect", PhaseStatus.OK, inputs_hash="abc")
    assert s.should_run("detect", inputs_hash="abc", force=True)


def test_secrets_roundtrip(tmp_path: Path):
    path = tmp_path / "state.json"
    s = State.load(path)
    s.set_secret("plex_token", "xyz")
    s.save()
    assert State.load(path).get_secret("plex_token") == "xyz"


def test_paths_roundtrip(tmp_path: Path):
    path = tmp_path / "state.json"
    s = State.load(path)
    s.set_path("plex_plugins", "/fake/plex/plug-ins")
    s.save()
    assert State.load(path).get_path("plex_plugins") == "/fake/plex/plug-ins"


def test_load_corrupt_file_rebuilds(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text("not json {")
    s = State.load(path)
    assert s.version == 1
