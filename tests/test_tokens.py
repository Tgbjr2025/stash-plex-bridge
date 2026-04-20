from pathlib import Path

import pytest

from bridge.tokens import extract_plex_token_from_prefs


def test_extract_valid(fake_plex_prefs: Path):
    assert extract_plex_token_from_prefs(fake_plex_prefs) == "fake-plex-token-abc123"


def test_extract_missing_file_returns_none(tmp_path: Path):
    missing = tmp_path / "nope.xml"
    assert extract_plex_token_from_prefs(missing) is None


def test_extract_no_token_attr_returns_none(tmp_path: Path):
    f = tmp_path / "Preferences.xml"
    f.write_text('<?xml version="1.0"?><Preferences FriendlyName="x"/>')
    assert extract_plex_token_from_prefs(f) is None


def test_extract_malformed_xml_returns_none(tmp_path: Path):
    f = tmp_path / "Preferences.xml"
    f.write_text("not xml <<<")
    assert extract_plex_token_from_prefs(f) is None
