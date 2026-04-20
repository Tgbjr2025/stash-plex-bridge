import pytest
from pathlib import Path


@pytest.fixture
def tmp_state_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def fake_plex_prefs(tmp_path: Path) -> Path:
    prefs = tmp_path / "Preferences.xml"
    prefs.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<Preferences PlexOnlineToken="fake-plex-token-abc123" '
        'FriendlyName="HomePlex"/>\n'
    )
    return prefs
