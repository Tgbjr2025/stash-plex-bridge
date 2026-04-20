"""Plex token auto-extraction from Preferences.xml."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from lxml import etree


def extract_plex_token_from_prefs(prefs_path: Path) -> Optional[str]:
    """Read PlexOnlineToken from Plex's Preferences.xml.

    Returns None when the file is missing, malformed, or the attribute
    is absent — caller falls back to a paste prompt.
    """
    if not prefs_path.exists():
        return None
    try:
        tree = etree.parse(str(prefs_path))
    except etree.XMLSyntaxError:
        return None
    root = tree.getroot()
    token = root.get("PlexOnlineToken")
    return token if token else None
