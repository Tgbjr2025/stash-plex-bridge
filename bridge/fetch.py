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
