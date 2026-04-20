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
