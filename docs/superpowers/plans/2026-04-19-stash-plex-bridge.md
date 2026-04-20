# stash-plex-bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a rerunnable Windows wrapper (PowerShell → Python) that clones, configures, and installs three Stash/Plex plugins (Stash2Plex, PlexSync, StashPlexAgent.bundle) with auto-detected paths and tokens.

**Architecture:** `install.ps1` bootstraps git + Python + venv, then launches `python -m bridge.installer`, which runs 5 idempotent phases (DETECT → FETCH → CONFIGURE → INSTALL → VALIDATE) tracked in `state.json`. Each phase is a separate module in `bridge/`. Tests run on macOS/Linux via mocked Windows paths; final acceptance is on a real Windows box.

**Tech Stack:** Python 3.11, PowerShell, pytest, requests, lxml, Jinja2, PyYAML, respx (HTTP mocking).

**Working directory:** `/Users/thomasbateman/stash-plex-bridge` (git repo initialized on `main`).

---

## Target file structure (final state)

```
stash-plex-bridge/
├── .gitignore
├── README.md
├── install.ps1
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── bridge/
│   ├── __init__.py
│   ├── installer.py          # CLI orchestrator
│   ├── state.py              # state.json load/save + phase-skip
│   ├── paths.py              # Windows path constants + env lookups
│   ├── tokens.py             # Plex token auto-extract
│   ├── detect.py             # Phase 1
│   ├── fetch.py              # Phase 2
│   ├── configure.py          # Phase 3
│   ├── install_plugins.py    # Phase 4
│   └── validate.py           # Phase 5
├── templates/
│   ├── stash2plex.config.yml.j2
│   ├── plexsync.config.yml.j2
│   └── stashplexagent.prefs.json.j2
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_state.py
    ├── test_paths.py
    ├── test_tokens.py
    ├── test_detect.py
    ├── test_fetch.py
    ├── test_configure.py
    ├── test_install_plugins.py
    ├── test_validate.py
    └── test_installer.py
```

---

## Task 0: Project scaffold

**Files:**
- Create: `.gitignore`, `README.md`, `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`
- Create: `bridge/__init__.py`, `tests/__init__.py`, `tests/conftest.py`
- Create empty dirs: `templates/`, `bridge/logs/` (placeholder)

- [ ] **Step 1: Write `.gitignore`**

```
# Python
__pycache__/
*.pyc
.venv/
bridge/.venv/
*.egg-info/
.pytest_cache/

# Wrapper state & vendored third-party code
state.json
vendor/
bridge/logs/
*.log
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "stash-plex-bridge"
version = "0.1.0"
description = "Automated installer for three Stash/Plex bridge plugins"
requires-python = ">=3.10"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

- [ ] **Step 3: Write `requirements.txt`**

```
requests>=2.31
lxml>=4.9
jinja2>=3.1
pyyaml>=6.0
```

- [ ] **Step 4: Write `requirements-dev.txt`**

```
-r requirements.txt
pytest>=8.0
respx>=0.20
httpx>=0.25
```

- [ ] **Step 5: Write `bridge/__init__.py`**

```python
"""stash-plex-bridge: automated installer for Stash/Plex bridge plugins."""

__version__ = "0.1.0"
```

- [ ] **Step 6: Write `tests/__init__.py`** (empty file)

- [ ] **Step 7: Write `tests/conftest.py`**

```python
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
```

- [ ] **Step 8: Write minimal `README.md`**

```markdown
# stash-plex-bridge

Automated Windows installer for three Stash↔Plex plugins:
Stash2Plex, PlexSync, StashPlexAgent.bundle.

See `docs/superpowers/specs/2026-04-19-stash-plex-bridge-design.md`.

## Quick start (on target Windows box)
Copy this folder to the Windows machine where Stash and Plex are installed,
then from PowerShell:

```powershell
.\install.ps1
```

Rerun anytime; completed phases are skipped.
```

- [ ] **Step 9: Set up local dev venv and install**

```bash
cd /Users/thomasbateman/stash-plex-bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Expected: installs without error.

- [ ] **Step 10: Verify pytest discovers nothing yet (sanity)**

```bash
pytest
```

Expected: exit 5 ("no tests ran") — confirms pytest works.

- [ ] **Step 11: Commit**

```bash
git add .gitignore README.md pyproject.toml requirements.txt requirements-dev.txt bridge/__init__.py tests/__init__.py tests/conftest.py
git commit -m "chore: scaffold project (pyproject, deps, test skeleton)"
```

---

## Task 1: `bridge/state.py` — phase state tracking

**Files:**
- Create: `bridge/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write failing test `tests/test_state.py`**

```python
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
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_state.py -v
```

Expected: ImportError / ModuleNotFoundError for `bridge.state`.

- [ ] **Step 3: Implement `bridge/state.py`**

```python
"""Phase state tracking persisted to state.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

PHASES = ("detect", "fetch", "configure", "install", "validate")


class PhaseStatus(str, Enum):
    PENDING = "pending"
    OK = "ok"
    FAILED = "failed"


@dataclass
class PhaseRecord:
    status: PhaseStatus = PhaseStatus.PENDING
    inputs_hash: Optional[str] = None
    ran_at: Optional[str] = None
    error: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "inputs_hash": self.inputs_hash,
            "ran_at": self.ran_at,
            "error": self.error,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PhaseRecord":
        return cls(
            status=PhaseStatus(d.get("status", "pending")),
            inputs_hash=d.get("inputs_hash"),
            ran_at=d.get("ran_at"),
            error=d.get("error"),
            extra=d.get("extra", {}),
        )


class State:
    def __init__(self, path: Path):
        self.path = path
        self.version = 1
        self.phases: dict[str, PhaseRecord] = {p: PhaseRecord() for p in PHASES}
        self.paths: dict[str, str] = {}
        self.secrets: dict[str, str] = {}

    @classmethod
    def load(cls, path: Path) -> "State":
        s = cls(path)
        if not path.exists():
            return s
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return s
        s.version = data.get("version", 1)
        for name, rec in data.get("phases", {}).items():
            if name in s.phases:
                s.phases[name] = PhaseRecord.from_dict(rec)
        s.paths = dict(data.get("paths", {}))
        s.secrets = dict(data.get("secrets", {}))
        return s

    def save(self) -> None:
        data = {
            "version": self.version,
            "phases": {k: v.to_dict() for k, v in self.phases.items()},
            "paths": self.paths,
            "secrets": self.secrets,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2))

    def get_phase(self, name: str) -> PhaseRecord:
        return self.phases[name]

    def set_phase(
        self,
        name: str,
        status: PhaseStatus,
        inputs_hash: Optional[str] = None,
        error: Optional[str] = None,
        **extra,
    ) -> None:
        from datetime import datetime, timezone
        self.phases[name] = PhaseRecord(
            status=status,
            inputs_hash=inputs_hash,
            ran_at=datetime.now(timezone.utc).isoformat(),
            error=error,
            extra=extra,
        )

    def should_run(
        self, name: str, inputs_hash: Optional[str] = None, force: bool = False
    ) -> bool:
        if force:
            return True
        rec = self.phases[name]
        if rec.status != PhaseStatus.OK:
            return True
        if inputs_hash is not None and rec.inputs_hash != inputs_hash:
            return True
        return False

    def set_path(self, key: str, value: str) -> None:
        self.paths[key] = value

    def get_path(self, key: str) -> Optional[str]:
        return self.paths.get(key)

    def set_secret(self, key: str, value: str) -> None:
        self.secrets[key] = value

    def get_secret(self, key: str) -> Optional[str]:
        return self.secrets.get(key)
```

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/test_state.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add bridge/state.py tests/test_state.py
git commit -m "feat(state): phase state tracking in state.json"
```

---

## Task 2: `bridge/paths.py` — Windows path constants & env lookups

**Files:**
- Create: `bridge/paths.py`
- Test: `tests/test_paths.py`

- [ ] **Step 1: Write failing test `tests/test_paths.py`**

```python
from pathlib import Path

import pytest

from bridge import paths


def test_plex_prefs_path(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    expected = tmp_path / "Plex Media Server" / "Preferences.xml"
    assert paths.plex_preferences_path() == expected


def test_plex_plugins_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    expected = tmp_path / "Plex Media Server" / "Plug-ins"
    assert paths.plex_plugins_dir() == expected


def test_stash_config_candidates(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    got = paths.stash_config_candidates()
    assert tmp_path / ".stash" in got
    assert tmp_path / "AppData" / "Roaming" / "stash" in got


def test_env_missing_raises(monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    with pytest.raises(paths.EnvNotSet):
        paths.plex_preferences_path()


def test_project_root_resolves():
    root = paths.project_root()
    assert root.is_dir()
    assert (root / "bridge").is_dir()
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_paths.py -v
```

Expected: ImportError for `bridge.paths`.

- [ ] **Step 3: Implement `bridge/paths.py`**

```python
"""Windows path constants and environment lookups.

On non-Windows hosts (e.g. macOS dev box) env vars are typically unset;
tests must set them via monkeypatch.
"""

from __future__ import annotations

import os
from pathlib import Path


class EnvNotSet(RuntimeError):
    """Raised when a required environment variable is missing."""


def _env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise EnvNotSet(f"Environment variable {name!r} is not set")
    return val


def plex_preferences_path() -> Path:
    return Path(_env("LOCALAPPDATA")) / "Plex Media Server" / "Preferences.xml"


def plex_plugins_dir() -> Path:
    return Path(_env("LOCALAPPDATA")) / "Plex Media Server" / "Plug-ins"


def plex_install_dir() -> Path:
    return Path(_env("LOCALAPPDATA")) / "Plex Media Server"


def stash_config_candidates() -> list[Path]:
    candidates: list[Path] = []
    try:
        candidates.append(Path(_env("USERPROFILE")) / ".stash")
    except EnvNotSet:
        pass
    try:
        candidates.append(Path(_env("APPDATA")) / "stash")
    except EnvNotSet:
        pass
    return candidates


def project_root() -> Path:
    """Project root is the parent of the `bridge/` package directory."""
    return Path(__file__).resolve().parent.parent


def vendor_dir() -> Path:
    return project_root() / "vendor"


def templates_dir() -> Path:
    return project_root() / "templates"


def state_file() -> Path:
    return project_root() / "state.json"


def logs_dir() -> Path:
    return project_root() / "bridge" / "logs"
```

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/test_paths.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add bridge/paths.py tests/test_paths.py
git commit -m "feat(paths): windows path constants and env lookups"
```

---

## Task 3: `bridge/tokens.py` — Plex token auto-extract

**Files:**
- Create: `bridge/tokens.py`
- Test: `tests/test_tokens.py`

- [ ] **Step 1: Write failing test `tests/test_tokens.py`**

```python
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
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_tokens.py -v
```

Expected: ImportError for `bridge.tokens`.

- [ ] **Step 3: Implement `bridge/tokens.py`**

```python
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
```

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/test_tokens.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add bridge/tokens.py tests/test_tokens.py
git commit -m "feat(tokens): auto-extract Plex token from Preferences.xml"
```

---

## Task 4: `bridge/detect.py` — Phase 1 path discovery

**Files:**
- Create: `bridge/detect.py`
- Test: `tests/test_detect.py`

- [ ] **Step 1: Write failing test `tests/test_detect.py`**

```python
from pathlib import Path

import pytest

from bridge.detect import detect_paths, DetectionResult
from bridge.state import State


def _setup_fake_windows(monkeypatch, tmp_path: Path, *, with_stash: bool = True):
    local = tmp_path / "LocalAppData"
    userprofile = tmp_path / "Users" / "me"
    appdata = tmp_path / "Users" / "me" / "AppData" / "Roaming"
    for p in (local, userprofile, appdata):
        p.mkdir(parents=True, exist_ok=True)

    plex = local / "Plex Media Server"
    (plex / "Plug-ins").mkdir(parents=True)
    (plex / "Preferences.xml").write_text(
        '<?xml version="1.0"?><Preferences PlexOnlineToken="t"/>'
    )

    if with_stash:
        stash = userprofile / ".stash"
        (stash / "plugins").mkdir(parents=True)
        (stash / "config.yml").write_text("stash_config: {}\n")

    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("USERPROFILE", str(userprofile))
    monkeypatch.setenv("APPDATA", str(appdata))


def test_detect_all_paths_present(monkeypatch, tmp_path: Path):
    _setup_fake_windows(monkeypatch, tmp_path)
    state = State.load(tmp_path / "state.json")

    result = detect_paths(state, prompt=lambda _msg: pytest.fail("no prompt expected"))

    assert isinstance(result, DetectionResult)
    assert result.plex_install.name == "Plex Media Server"
    assert result.plex_plugins.name == "Plug-ins"
    assert result.stash_config.name == ".stash"
    assert result.stash_plugins.name == "plugins"
    assert state.get_path("plex_plugins") == str(result.plex_plugins)
    assert state.get_path("stash_plugins") == str(result.stash_plugins)


def test_detect_prompts_for_missing_stash(monkeypatch, tmp_path: Path):
    _setup_fake_windows(monkeypatch, tmp_path, with_stash=False)
    custom_stash = tmp_path / "custom_stash"
    (custom_stash / "plugins").mkdir(parents=True)

    calls: list[str] = []

    def prompt(msg: str) -> str:
        calls.append(msg)
        return str(custom_stash)

    state = State.load(tmp_path / "state.json")
    result = detect_paths(state, prompt=prompt)

    assert len(calls) == 1
    assert "Stash" in calls[0]
    assert result.stash_config == custom_stash
    assert result.stash_plugins == custom_stash / "plugins"


def test_detect_raises_on_missing_plex(monkeypatch, tmp_path: Path):
    userprofile = tmp_path / "Users" / "me"
    userprofile.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Missing"))
    monkeypatch.setenv("USERPROFILE", str(userprofile))
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))

    state = State.load(tmp_path / "state.json")
    with pytest.raises(FileNotFoundError, match="Plex"):
        detect_paths(state, prompt=lambda m: "")


def test_detect_caches_results_in_state(monkeypatch, tmp_path: Path):
    _setup_fake_windows(monkeypatch, tmp_path, with_stash=False)
    state = State.load(tmp_path / "state.json")
    state.set_path("stash_config", str(tmp_path / "cached_stash"))
    (tmp_path / "cached_stash" / "plugins").mkdir(parents=True)

    result = detect_paths(
        state, prompt=lambda m: pytest.fail("should not prompt when cached")
    )
    assert result.stash_config == tmp_path / "cached_stash"
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_detect.py -v
```

Expected: ImportError for `bridge.detect`.

- [ ] **Step 3: Implement `bridge/detect.py`**

```python
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
```

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/test_detect.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add bridge/detect.py tests/test_detect.py
git commit -m "feat(detect): phase 1 — locate Stash/Plex install and plugin dirs"
```

---

## Task 5: `bridge/fetch.py` — Phase 2 git vendoring

**Files:**
- Create: `bridge/fetch.py`
- Test: `tests/test_fetch.py`

- [ ] **Step 1: Write failing test `tests/test_fetch.py`**

```python
from pathlib import Path
from unittest.mock import call, patch

import pytest

from bridge.fetch import REPOS, fetch_all, fetch_one, RepoSpec


def test_repos_list_has_three():
    assert len(REPOS) == 3
    names = {r.name for r in REPOS}
    assert names == {"Stash2Plex", "CommunityScripts", "StashPlexAgent.bundle"}


def test_fetch_one_clones_when_missing(tmp_path: Path):
    spec = RepoSpec(
        name="Stash2Plex",
        url="https://github.com/trek-e/Stash2Plex",
        sparse=None,
    )
    dest = tmp_path / "Stash2Plex"

    with patch("bridge.fetch.subprocess.run") as mrun:
        mrun.return_value.returncode = 0
        mrun.return_value.stdout = "abc1234\n"
        sha = fetch_one(spec, dest)

    assert mrun.call_args_list[0].args[0][:2] == ["git", "clone"]
    assert sha == "abc1234"


def test_fetch_one_pulls_when_present(tmp_path: Path):
    dest = tmp_path / "Stash2Plex"
    (dest / ".git").mkdir(parents=True)
    spec = RepoSpec(name="Stash2Plex", url="https://example/x", sparse=None)

    with patch("bridge.fetch.subprocess.run") as mrun:
        mrun.return_value.returncode = 0
        mrun.return_value.stdout = "def5678\n"
        sha = fetch_one(spec, dest)

    first_cmd = mrun.call_args_list[0].args[0]
    assert first_cmd[:2] == ["git", "-C"]
    assert "pull" in first_cmd
    assert sha == "def5678"


def test_fetch_one_sparse_checkout(tmp_path: Path):
    dest = tmp_path / "CommunityScripts"
    spec = RepoSpec(
        name="CommunityScripts",
        url="https://github.com/stashapp/CommunityScripts",
        sparse="plugins/PlexSync",
    )

    with patch("bridge.fetch.subprocess.run") as mrun:
        mrun.return_value.returncode = 0
        mrun.return_value.stdout = "ghi9012\n"
        fetch_one(spec, dest)

    cmds = [c.args[0] for c in mrun.call_args_list]
    assert any("--sparse" in c for c in cmds)
    assert any("sparse-checkout" in c for c in cmds)


def test_fetch_one_retries_then_raises(tmp_path: Path):
    spec = RepoSpec(name="x", url="https://bad", sparse=None)
    with patch("bridge.fetch.subprocess.run") as mrun, \
         patch("bridge.fetch.time.sleep"):
        mrun.return_value.returncode = 128
        mrun.return_value.stderr = "fatal: unable to access"
        with pytest.raises(RuntimeError, match="fetch failed"):
            fetch_one(spec, tmp_path / "x", max_attempts=3)
    assert mrun.call_count == 3


def test_fetch_all_populates_commits(tmp_path: Path):
    with patch("bridge.fetch.fetch_one") as mfetch:
        mfetch.side_effect = ["s1", "s2", "s3"]
        commits = fetch_all(tmp_path)
    assert commits == {
        "Stash2Plex": "s1",
        "CommunityScripts": "s2",
        "StashPlexAgent.bundle": "s3",
    }
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_fetch.py -v
```

Expected: ImportError for `bridge.fetch`.

- [ ] **Step 3: Implement `bridge/fetch.py`**

```python
"""Phase 2: FETCH — clone/pull the three vendor repos.

Uses sparse-checkout for CommunityScripts since we only need one plugin subdir.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RepoSpec:
    name: str
    url: str
    sparse: Optional[str]  # subdirectory for sparse-checkout, or None for full


REPOS: tuple[RepoSpec, ...] = (
    RepoSpec("Stash2Plex", "https://github.com/trek-e/Stash2Plex", None),
    RepoSpec(
        "CommunityScripts",
        "https://github.com/stashapp/CommunityScripts",
        "plugins/PlexSync",
    ),
    RepoSpec(
        "StashPlexAgent.bundle",
        "https://github.com/Darklyter/StashPlexAgent.bundle",
        None,
    ),
)


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _head_sha(dest: Path) -> str:
    r = _run(["git", "-C", str(dest), "rev-parse", "HEAD"])
    if r.returncode != 0:
        raise RuntimeError(f"failed to read HEAD: {r.stderr}")
    return r.stdout.strip()


def fetch_one(
    spec: RepoSpec,
    dest: Path,
    max_attempts: int = 3,
    backoff_seconds: float = 2.0,
) -> str:
    """Clone or pull a repo. Returns the HEAD sha."""
    last_err = ""
    for attempt in range(1, max_attempts + 1):
        try:
            if (dest / ".git").is_dir():
                r = _run(["git", "-C", str(dest), "pull", "--ff-only"])
            elif spec.sparse:
                dest.mkdir(parents=True, exist_ok=True)
                r = _run(
                    ["git", "clone", "--depth=1", "--filter=blob:none",
                     "--sparse", spec.url, str(dest)]
                )
                if r.returncode != 0:
                    raise RuntimeError(r.stderr)
                r = _run(
                    ["git", "-C", str(dest), "sparse-checkout", "set", spec.sparse]
                )
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                r = _run(["git", "clone", "--depth=1", spec.url, str(dest)])

            if r.returncode != 0:
                raise RuntimeError(r.stderr or "git exited non-zero")

            return _head_sha(dest)
        except RuntimeError as e:
            last_err = str(e)
            if attempt < max_attempts:
                time.sleep(backoff_seconds * attempt)

    raise RuntimeError(f"fetch failed for {spec.name}: {last_err}")


def fetch_all(vendor_dir: Path) -> dict[str, str]:
    """Fetch all three repos. Returns {repo_name: head_sha}."""
    commits: dict[str, str] = {}
    for spec in REPOS:
        commits[spec.name] = fetch_one(spec, vendor_dir / spec.name)
    return commits
```

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/test_fetch.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add bridge/fetch.py tests/test_fetch.py
git commit -m "feat(fetch): phase 2 — vendor three plugin repos via git"
```

---

## Task 6: `bridge/configure.py` — Phase 3 templates + secret capture

**Files:**
- Create: `bridge/configure.py`
- Create: `templates/stash2plex.config.yml.j2`
- Create: `templates/plexsync.config.yml.j2`
- Create: `templates/stashplexagent.prefs.json.j2`
- Test: `tests/test_configure.py`

- [ ] **Step 1: Write template `templates/stash2plex.config.yml.j2`**

```yaml
# Stash2Plex configuration (generated by stash-plex-bridge)
stash:
  url: {{ stash_url }}
  api_key: {{ stash_api_key }}
plex:
  url: {{ plex_url }}
  token: {{ plex_token }}
  library: {{ plex_library }}
```

- [ ] **Step 2: Write template `templates/plexsync.config.yml.j2`**

```yaml
# PlexSync plugin configuration (generated by stash-plex-bridge)
plex_url: {{ plex_url }}
plex_token: {{ plex_token }}
plex_library: {{ plex_library }}
clean_titles: true
```

- [ ] **Step 3: Write template `templates/stashplexagent.prefs.json.j2`**

```json
{
  "stash_url": "{{ stash_url }}",
  "stash_api_key": "{{ stash_api_key }}",
  "create_collection_tags": true,
  "ignored_tag_ids": []
}
```

- [ ] **Step 4: Write failing test `tests/test_configure.py`**

```python
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import respx
import httpx

from bridge.configure import (
    ConfigInputs,
    render_configs,
    validate_plex_token,
    validate_stash_api_key,
    list_plex_libraries,
    capture_inputs,
)


def _inputs() -> ConfigInputs:
    return ConfigInputs(
        stash_url="http://localhost:9999",
        stash_api_key="stash-key-xyz",
        plex_url="http://localhost:32400",
        plex_token="plex-token-abc",
        plex_library="Adult",
    )


def test_render_configs_produces_three_files(tmp_path: Path):
    vendor = tmp_path / "vendor"
    (vendor / "Stash2Plex").mkdir(parents=True)
    (vendor / "CommunityScripts" / "plugins" / "PlexSync").mkdir(parents=True)
    (vendor / "StashPlexAgent.bundle" / "Contents").mkdir(parents=True)

    written = render_configs(_inputs(), vendor)

    assert (vendor / "Stash2Plex" / "config.yml") in written
    assert (vendor / "CommunityScripts" / "plugins" / "PlexSync" / "config.yml") in written
    assert (vendor / "StashPlexAgent.bundle" / "Contents" / "DefaultPrefs.json") in written

    s2p = (vendor / "Stash2Plex" / "config.yml").read_text()
    assert "plex-token-abc" in s2p
    assert "stash-key-xyz" in s2p
    assert "http://localhost:32400" in s2p

    prefs_json = json.loads(
        (vendor / "StashPlexAgent.bundle" / "Contents" / "DefaultPrefs.json").read_text()
    )
    assert prefs_json["stash_api_key"] == "stash-key-xyz"


@respx.mock
def test_validate_plex_token_ok():
    respx.get("http://localhost:32400/").mock(
        return_value=httpx.Response(200, text='<MediaContainer friendlyName="Home"/>')
    )
    assert validate_plex_token("http://localhost:32400", "t") is True


@respx.mock
def test_validate_plex_token_unauthorized():
    respx.get("http://localhost:32400/").mock(return_value=httpx.Response(401))
    assert validate_plex_token("http://localhost:32400", "bad") is False


@respx.mock
def test_validate_stash_api_key_ok():
    respx.post("http://localhost:9999/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"me": {"id": "1"}}})
    )
    assert validate_stash_api_key("http://localhost:9999", "k") is True


@respx.mock
def test_validate_stash_api_key_bad():
    respx.post("http://localhost:9999/graphql").mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "unauthorized"}]})
    )
    assert validate_stash_api_key("http://localhost:9999", "k") is False


@respx.mock
def test_list_plex_libraries():
    respx.get("http://localhost:32400/library/sections").mock(
        return_value=httpx.Response(
            200,
            text=(
                '<MediaContainer>'
                '<Directory key="1" title="Movies" type="movie"/>'
                '<Directory key="2" title="Adult" type="movie"/>'
                '</MediaContainer>'
            ),
        )
    )
    libs = list_plex_libraries("http://localhost:32400", "t")
    assert libs == ["Movies", "Adult"]


def test_capture_inputs_uses_state_cache(tmp_path: Path, monkeypatch):
    from bridge.state import State
    state = State.load(tmp_path / "state.json")
    state.set_secret("plex_token", "cached-plex")
    state.set_secret("stash_api_key", "cached-stash")
    state.set_secret("plex_library", "Adult")

    with patch("bridge.configure.validate_plex_token", return_value=True), \
         patch("bridge.configure.validate_stash_api_key", return_value=True):
        inputs = capture_inputs(
            state,
            stash_url="http://localhost:9999",
            plex_url="http://localhost:32400",
            prompt_text=lambda m: pytest.fail("should not prompt"),
            prompt_secret=lambda m: pytest.fail("should not prompt for secret"),
            prompt_library=lambda libs: pytest.fail("should not prompt for library"),
        )
    assert inputs.plex_token == "cached-plex"
    assert inputs.stash_api_key == "cached-stash"
    assert inputs.plex_library == "Adult"
```

- [ ] **Step 5: Run test, verify it fails**

```bash
pytest tests/test_configure.py -v
```

Expected: ImportError for `bridge.configure`.

- [ ] **Step 6: Implement `bridge/configure.py`**

```python
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
```

- [ ] **Step 7: Run test, verify pass**

```bash
pytest tests/test_configure.py -v
```

Expected: 7 passed.

- [ ] **Step 8: Commit**

```bash
git add bridge/configure.py templates/ tests/test_configure.py
git commit -m "feat(configure): phase 3 — capture secrets and render configs"
```

---

## Task 7: `bridge/install_plugins.py` — Phase 4 file deployment

**Files:**
- Create: `bridge/install_plugins.py`
- Test: `tests/test_install_plugins.py`

- [ ] **Step 1: Write failing test `tests/test_install_plugins.py`**

```python
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
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_install_plugins.py -v
```

Expected: ImportError for `bridge.install_plugins`.

- [ ] **Step 3: Implement `bridge/install_plugins.py`**

```python
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
    content = f"""# Run Stash2Plex one-shot sync
$ErrorActionPreference = "Stop"
Push-Location "{rel_vendor}"
try {{
    & python sync.py @args
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
```

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/test_install_plugins.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add bridge/install_plugins.py tests/test_install_plugins.py
git commit -m "feat(install): phase 4 — deploy plugins to Stash and Plex dirs"
```

---

## Task 8: `bridge/validate.py` — Phase 5 health checks

**Files:**
- Create: `bridge/validate.py`
- Test: `tests/test_validate.py`

- [ ] **Step 1: Write failing test `tests/test_validate.py`**

```python
import httpx
import pytest
import respx

from bridge.validate import (
    check_stash_api,
    check_plex_api,
    check_plugin_loaded_stash,
    check_plugin_loaded_plex,
    run_all_checks,
    Check,
)


@respx.mock
def test_check_stash_api_pass():
    respx.post("http://localhost:9999/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"me": {"id": "1"}}})
    )
    c = check_stash_api("http://localhost:9999", "k")
    assert c.ok
    assert c.name == "stash-api"


@respx.mock
def test_check_stash_api_fail_on_error():
    respx.post("http://localhost:9999/graphql").mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "unauth"}]})
    )
    c = check_stash_api("http://localhost:9999", "k")
    assert not c.ok
    assert "unauth" in c.detail


@respx.mock
def test_check_plex_api_pass():
    respx.get("http://localhost:32400/").mock(
        return_value=httpx.Response(200, text='<MediaContainer friendlyName="Home"/>')
    )
    c = check_plex_api("http://localhost:32400", "t")
    assert c.ok
    assert "Home" in c.detail


@respx.mock
def test_check_plex_api_fail():
    respx.get("http://localhost:32400/").mock(return_value=httpx.Response(401))
    assert not check_plex_api("http://localhost:32400", "bad").ok


@respx.mock
def test_check_stash_plugin_loaded():
    respx.post("http://localhost:9999/graphql").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"plugins": [{"id": "PlexSync", "name": "PlexSync"}]}},
        )
    )
    assert check_plugin_loaded_stash("http://localhost:9999", "k", "PlexSync").ok


@respx.mock
def test_check_stash_plugin_not_loaded():
    respx.post("http://localhost:9999/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"plugins": []}})
    )
    assert not check_plugin_loaded_stash("http://localhost:9999", "k", "PlexSync").ok


@respx.mock
def test_check_plex_plugin_loaded():
    respx.get("http://localhost:32400/:/plugins/all").mock(
        return_value=httpx.Response(
            200,
            text=(
                '<MediaContainer>'
                '<Plugin identifier="com.plexapp.agents.stashplex"/>'
                '</MediaContainer>'
            ),
        )
    )
    assert check_plugin_loaded_plex(
        "http://localhost:32400", "t", "com.plexapp.agents.stashplex"
    ).ok


@respx.mock
def test_run_all_checks_aggregates():
    respx.post("http://localhost:9999/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"me": {"id": "1"}, "plugins": []}})
    )
    respx.get("http://localhost:32400/").mock(
        return_value=httpx.Response(200, text='<MediaContainer friendlyName="X"/>')
    )
    respx.get("http://localhost:32400/:/plugins/all").mock(
        return_value=httpx.Response(200, text='<MediaContainer/>')
    )
    checks = run_all_checks(
        stash_url="http://localhost:9999",
        stash_api_key="k",
        plex_url="http://localhost:32400",
        plex_token="t",
    )
    assert len(checks) == 4
    names = {c.name for c in checks}
    assert names == {"stash-api", "plex-api", "stash-plugin", "plex-plugin"}
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_validate.py -v
```

Expected: ImportError for `bridge.validate`.

- [ ] **Step 3: Implement `bridge/validate.py`**

```python
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
```

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/test_validate.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add bridge/validate.py tests/test_validate.py
git commit -m "feat(validate): phase 5 — health checks for api + plugin load"
```

---

## Task 9: `bridge/installer.py` — CLI orchestrator

**Files:**
- Create: `bridge/installer.py`
- Test: `tests/test_installer.py`

- [ ] **Step 1: Write failing test `tests/test_installer.py`**

```python
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
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_installer.py -v
```

Expected: ImportError for `bridge.installer`.

- [ ] **Step 3: Implement `bridge/installer.py`**

```python
"""CLI orchestrator — runs the 5 phases with skip-on-success semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from bridge import paths
from bridge.configure import capture_inputs, render_configs, ConfigInputs
from bridge.detect import detect_paths, DetectionResult
from bridge.fetch import fetch_all
from bridge.install_plugins import install_all, InstallTargets
from bridge.state import State, PhaseStatus
from bridge.validate import run_all_checks, Check

PHASES = ("detect", "fetch", "configure", "install", "validate")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bridge.installer",
        description="Install and configure three Stash/Plex bridge plugins.",
    )
    p.add_argument("--force", action="store_true",
                   help="Rerun all phases even if previously OK.")
    p.add_argument("--phase", choices=PHASES, default=None,
                   help="Run just one phase.")
    p.add_argument("--update", action="store_true",
                   help="Re-pull vendor repos to their latest.")
    p.add_argument("--stash-port", type=int, default=9999)
    p.add_argument("--plex-port", type=int, default=32400)
    p.add_argument("--reset-tokens", action="store_true",
                   help="Wipe saved secrets and re-prompt.")
    p.add_argument("--dry-run", action="store_true",
                   help="Plan phases but do not execute side effects.")
    return p


def _setup_logging() -> None:
    paths.logs_dir().mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    logfile = paths.logs_dir() / f"install-{stamp}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(logfile), logging.StreamHandler()],
    )


def _hash_inputs(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()
    ).hexdigest()


def _run_phase(
    state: State,
    name: str,
    inputs_hash: str,
    force: bool,
    body,
) -> bool:
    if not state.should_run(name, inputs_hash=inputs_hash, force=force):
        logging.info("phase %s: skipped (already ok)", name)
        return True
    logging.info("phase %s: running", name)
    try:
        body()
    except Exception as e:
        state.set_phase(name, PhaseStatus.FAILED,
                        inputs_hash=inputs_hash, error=str(e))
        state.save()
        logging.error("phase %s failed: %s", name, e)
        return False
    state.set_phase(name, PhaseStatus.OK, inputs_hash=inputs_hash)
    state.save()
    return True


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    _setup_logging()

    state_path = paths.state_file()
    state = State.load(state_path)

    if args.reset_tokens:
        state.secrets.clear()
        state.save()
        logging.info("secrets cleared")

    stash_url = f"http://localhost:{args.stash_port}"
    plex_url = f"http://localhost:{args.plex_port}"

    results: dict[str, object] = {}

    def do_detect():
        results["detect"] = detect_paths(state)

    def do_fetch():
        commits = fetch_all(paths.vendor_dir())
        results["fetch_commits"] = commits

    def do_configure():
        inputs = capture_inputs(
            state, stash_url=stash_url, plex_url=plex_url,
        )
        render_configs(inputs, paths.vendor_dir())
        results["config_inputs"] = inputs

    def do_install():
        targets = InstallTargets(
            stash_plugins=Path(state.get_path("stash_plugins")),
            plex_plugins=Path(state.get_path("plex_plugins")),
            project_root=paths.project_root(),
        )
        install_all(paths.vendor_dir(), targets)

    def do_validate():
        inputs: ConfigInputs = results.get("config_inputs") or ConfigInputs(
            stash_url=stash_url,
            stash_api_key=state.get_secret("stash_api_key") or "",
            plex_url=plex_url,
            plex_token=state.get_secret("plex_token") or "",
            plex_library=state.get_secret("plex_library") or "",
        )
        checks: list[Check] = run_all_checks(
            stash_url=inputs.stash_url,
            stash_api_key=inputs.stash_api_key,
            plex_url=inputs.plex_url,
            plex_token=inputs.plex_token,
        )
        for c in checks:
            logging.info("check %s: %s — %s",
                         c.name, "OK" if c.ok else "FAIL", c.detail)
        if not all(c.ok for c in checks):
            raise RuntimeError("one or more validation checks failed")

    phase_bodies = {
        "detect": (do_detect, {"env": ["LOCALAPPDATA", "USERPROFILE", "APPDATA"]}),
        "fetch": (do_fetch, {"update": args.update}),
        "configure": (do_configure, {"stash_url": stash_url, "plex_url": plex_url}),
        "install": (do_install, {}),
        "validate": (do_validate, {}),
    }

    selected = [args.phase] if args.phase else list(PHASES)

    for name in selected:
        body, inputs_obj = phase_bodies[name]
        inputs_hash = _hash_inputs(inputs_obj)
        if args.dry_run:
            logging.info("[dry-run] would run phase %s", name)
            continue
        ok = _run_phase(state, name, inputs_hash, args.force, body)
        if not ok:
            return 1

    logging.info("all selected phases complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/test_installer.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run full test suite (integration sanity)**

```bash
pytest -v
```

Expected: all previous tests still pass (≥35 total).

- [ ] **Step 6: Commit**

```bash
git add bridge/installer.py tests/test_installer.py
git commit -m "feat(installer): CLI orchestrator for the 5 phases"
```

---

## Task 10: `install.ps1` — PowerShell bootstrap

**Files:**
- Create: `install.ps1`

- [ ] **Step 1: Write `install.ps1`**

```powershell
<#
.SYNOPSIS
  Bootstrap and run stash-plex-bridge on Windows.
.DESCRIPTION
  Ensures git + Python 3.11 are installed (via winget), creates a venv in
  .\bridge\.venv, installs Python deps, and launches bridge.installer.
  Safe to rerun.
.PARAMETER Args
  Forwarded to the Python installer (e.g. --force, --phase detect).
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Has-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Install-ViaWinget($id, $friendly) {
    Write-Host "[bridge] installing $friendly via winget..."
    winget install --id $id --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to install $friendly (exit $LASTEXITCODE)"
    }
    # Refresh PATH for current session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + `
                ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

# --- 1. Ensure git ---
if (-not (Has-Command git)) {
    Install-ViaWinget "Git.Git" "Git"
}

# --- 2. Ensure python ---
$python = $null
foreach ($cmd in @("python", "py")) {
    if (Has-Command $cmd) {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.(1[0-9]|[2-9][0-9])") {
            $python = $cmd
            break
        }
    }
}
if (-not $python) {
    Install-ViaWinget "Python.Python.3.11" "Python 3.11"
    $python = "python"
}

# --- 3. Create venv ---
$Venv = Join-Path $ProjectRoot "bridge\.venv"
if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    Write-Host "[bridge] creating venv at $Venv"
    & $python -m venv $Venv
}
$VenvPy = Join-Path $Venv "Scripts\python.exe"

# --- 4. Install deps ---
$ReqHashFile = Join-Path $ProjectRoot "bridge\.reqs.sha256"
$ReqFile = Join-Path $ProjectRoot "requirements.txt"
$CurrentHash = (Get-FileHash $ReqFile -Algorithm SHA256).Hash
$PrevHash = if (Test-Path $ReqHashFile) { Get-Content $ReqHashFile } else { "" }

if ($CurrentHash -ne $PrevHash) {
    Write-Host "[bridge] installing Python deps"
    & $VenvPy -m pip install --upgrade pip | Out-Null
    & $VenvPy -m pip install -r $ReqFile
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    Set-Content -Path $ReqHashFile -Value $CurrentHash
} else {
    Write-Host "[bridge] deps up to date"
}

# --- 5. Lock down state.json ACL if it exists ---
$StateFile = Join-Path $ProjectRoot "state.json"
if (Test-Path $StateFile) {
    icacls $StateFile /inheritance:r /grant:r "$env:USERNAME:F" | Out-Null
}

# --- 6. Launch installer ---
Write-Host "[bridge] launching installer..."
& $VenvPy -m bridge.installer @Args
exit $LASTEXITCODE
```

- [ ] **Step 2: Syntax-check (best-effort from Mac)**

```bash
# Just make sure the file is well-formed enough to commit — full PowerShell
# syntax validation happens on the Windows target.
head -5 install.ps1 && wc -l install.ps1
```

Expected: file exists, starts with `<#`, ~70 lines.

- [ ] **Step 3: Commit**

```bash
git add install.ps1
git commit -m "feat(bootstrap): install.ps1 — ensure git/python, create venv, run installer"
```

---

## Task 11: README + final polish

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite `README.md`**

```markdown
# stash-plex-bridge

One-command Windows installer for three Stash↔Plex plugins:

- [trek-e/Stash2Plex](https://github.com/trek-e/Stash2Plex) — standalone sync tool
- [stashapp/CommunityScripts › PlexSync](https://github.com/stashapp/CommunityScripts/tree/main/plugins/PlexSync) — Stash plugin
- [Darklyter/StashPlexAgent.bundle](https://github.com/Darklyter/StashPlexAgent.bundle) — Plex agent

## What it does

1. Ensures `git` and Python 3.11 are installed (via `winget` if missing).
2. Creates a local venv and installs Python deps.
3. Clones the three plugin repos into `.\vendor\`.
4. Auto-detects Stash and Plex install locations and plugin directories.
5. Auto-extracts your Plex token from `Preferences.xml` (falls back to paste).
6. Prompts once for your Stash API key (generate at
   `http://localhost:9999/settings?tab=security`).
7. Lists your Plex libraries and asks which one to use.
8. Renders config files for all three plugins.
9. Copies plugin files into the right places.
10. Validates end-to-end: Stash API, Plex API, plugin load state.

## Usage

Copy this folder to the Windows box where Stash and Plex are running, then
from PowerShell (normal user unless your Plex plugins dir requires admin):

```powershell
.\install.ps1
```

Safe to rerun. Completed phases are skipped.

### Flags

| Flag | Effect |
|---|---|
| `--force` | Rerun every phase, even if already OK |
| `--phase <name>` | Run one phase only: `detect`, `fetch`, `configure`, `install`, `validate` |
| `--update` | Pull latest vendor repo commits |
| `--reset-tokens` | Wipe saved tokens and re-prompt |
| `--stash-port <N>` | Non-default Stash port (default 9999) |
| `--plex-port <N>` | Non-default Plex port (default 32400) |
| `--dry-run` | Log what would happen, no side effects |

Examples:

```powershell
.\install.ps1 --phase validate
.\install.ps1 --update --force
.\install.ps1 --reset-tokens
```

## State file

Progress and secrets live in `state.json` (user-only ACL, gitignored).
Delete it to start over.

## Logs

`bridge\logs\install-YYYYMMDD-HHMMSS.log` per run.

## Troubleshooting

- **"Plex install not found"** — ensure Plex Media Server is installed for the
  current Windows user. The script reads `%LOCALAPPDATA%\Plex Media Server`.
- **"run PowerShell as admin"** — your Plex plugins directory isn't writable
  by a normal user; relaunch PowerShell with admin rights.
- **Stash or Plex not running at VALIDATE** — start both services and rerun
  `.\install.ps1 --phase validate`.
- **Wrong Plex library picked** — run `.\install.ps1 --reset-tokens --phase configure`.

## Development (on macOS/Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Tests mock Windows paths and HTTP; no real Stash/Plex required.

## Design docs

See `docs/superpowers/specs/2026-04-19-stash-plex-bridge-design.md` and
`docs/superpowers/plans/2026-04-19-stash-plex-bridge.md`.
```

- [ ] **Step 2: Final full test run**

```bash
pytest -v --tb=short
```

Expected: all tests pass, no warnings that require attention.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: flesh out README with usage, flags, troubleshooting"
```

- [ ] **Step 4: Final manual acceptance (on Windows box)**

This step is out of scope for automated testing but must be documented in the
run log of whoever implements the plan:

1. Copy the project folder to the Windows box.
2. Open PowerShell in the project folder.
3. Run `.\install.ps1`.
4. Answer any prompts (Stash path if not auto-found, Stash API key, library).
5. Confirm all 4 VALIDATE checks print OK.
6. In Stash UI, confirm PlexSync plugin appears under Settings → Plugins.
7. In Plex UI, add the StashPlexAgent as the agent for your target library,
   refresh metadata, and confirm scenes pull Stash metadata.
8. Edit a scene in Stash and confirm PlexSync updates Plex within ~30s.

If any step fails, capture the log file from `bridge\logs\` and iterate.

---

## Summary checklist (implementation order)

- [ ] Task 0: scaffold
- [ ] Task 1: state.py
- [ ] Task 2: paths.py
- [ ] Task 3: tokens.py
- [ ] Task 4: detect.py
- [ ] Task 5: fetch.py
- [ ] Task 6: configure.py + templates
- [ ] Task 7: install_plugins.py
- [ ] Task 8: validate.py
- [ ] Task 9: installer.py (CLI)
- [ ] Task 10: install.ps1
- [ ] Task 11: README + final acceptance
