"""The lockbox token is built only after the unseal tag is on the remote, and gates rows from the boundary on."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from avalanche_research.core import lockbox
from avalanche_research.core.clock import LOCKBOX_START
from avalanche_research.core.errors import ModelError


def repo_with_remote(tmp_path: Path) -> Path:
    remote, repo = tmp_path / "remote.git", tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    for args in (["config", "user.email", "t@t"], ["config", "user.name", "t"], ["commit", "-q", "--allow-empty", "-m", "base"],
                 ["remote", "add", "origin", str(remote)], ["push", "-q", "origin", "main"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True)
    return repo


def test_no_token_before_the_tag_is_on_the_remote(tmp_path):
    repo = repo_with_remote(tmp_path)
    with pytest.raises(ModelError, match="not on record"):
        lockbox.issue(repo)
    subprocess.run(["git", "-C", str(repo), "tag", "-a", lockbox.TAG, "-m", "unsealing"], check=True)
    with pytest.raises(ModelError):
        lockbox.issue(repo)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", f"refs/tags/{lockbox.TAG}"], check=True)
    assert lockbox.issue(repo).tag_object == lockbox.remote_tag(repo)


def test_a_token_cannot_be_built_directly_and_lockbox_rows_need_one(tmp_path):
    with pytest.raises(ModelError, match="only by lockbox.issue"):
        lockbox.Unseal("abc", object())
    lockbox.require(datetime(2025, 11, 19, 15, 59, tzinfo=UTC), None)
    with pytest.raises(ModelError, match="no Unseal token"):
        lockbox.require(LOCKBOX_START, None)
