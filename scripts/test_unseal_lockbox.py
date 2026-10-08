"""The unseal script's guards, its lock before the first lockbox read, its single use, and its rehearsal."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unseal_lockbox as unseal

from avalanche_research.core import lockbox
from avalanche_research.core.hashing import sha256

ENTRY = '''
from avalanche_research.core import lockbox
CALLS = []
def score(token, fit_until, score_until):
    CALLS.append((token, fit_until, score_until))
    if token is not None:
        assert lockbox.remote_tag(REPO) is not None, "a lockbox row was read before the lock"
    return {"verdict": "pass", "mase_90": 0.91}
'''


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    remote, repo = tmp_path / "remote.git", tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    (repo / "uv.lock").write_text("lock\n")
    folder = repo / unseal.FOLDER
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps({
        "entry_point": "lockbox_entry:score", "author": "modeling-lead", "uv_lock_sha256": sha256(b"lock\n"), "pins": [],
        "rehearsal": {"fit_until": "2024-12-16", "score_until": "2025-11-18"}, "foundation_answer": {"default_used": True}}))
    (folder / "template.md").write_text("Verdict: {verdict}. MASE at 90 days: {mase_90}.\n")
    (tmp_path / "lockbox_entry.py").write_text(ENTRY + f"REPO = {str(repo)!r}\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("lockbox_entry", None)
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "pre-registration")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    witness = tmp_path / "witness.ots"
    witness.write_text("proof\n")
    rehearsal = unseal.rehearse(repo, unseal.argparse.Namespace(out=str(tmp_path / "rehearsal.json")))
    args = unseal.argparse.Namespace(commit=commit, bundle_hash=unseal.bundle_hash(folder), runner="fresh-agent", witness=str(witness),
                                     rehearsal=str(rehearsal), registry_unsealed_at="none")
    return repo, args


def test_the_rehearsal_uses_development_data_only_and_records_this_script(setup):
    _, args = setup
    record = json.loads(Path(args.rehearsal).read_text())
    assert record["passed"] and record["script_sha256"] == unseal.script_hash() and record["score_until"] == "2025-11-18"
    assert sys.modules["lockbox_entry"].CALLS[-1][0] is None


@pytest.mark.parametrize(("change", "code"), [
    ({"bundle_hash": "0" * 64}, "G1"), ({"witness": "/missing"}, "G5"), ({"runner": "modeling-lead"}, "G6"),
    ({"rehearsal": "/missing"}, "G7"), ({"registry_unsealed_at": "2026-10-27"}, "G4")])
def test_each_guard_refuses(setup, change, code):
    repo, args = setup
    for key, value in change.items():
        setattr(args, key, value)
    with pytest.raises(unseal.GuardFailed, match=f"^{code}"):
        unseal.guards(repo, args)


def test_a_dirty_checkout_fails_g2(setup):
    repo, args = setup
    (repo / "uv.lock").write_text("changed\n")
    with pytest.raises(unseal.GuardFailed, match="^G2"):
        unseal.guards(repo, args)


def test_the_unseal_locks_before_reading_writes_its_receipt_and_cannot_run_twice(setup):
    repo, args = setup
    receipt = unseal.unseal(repo, args)
    token = sys.modules["lockbox_entry"].CALLS[-1][0]
    assert isinstance(token, lockbox.Unseal) and receipt["tag_object"] == lockbox.remote_tag(repo)
    assert receipt["results"]["verdict"] == "pass" and set(receipt["guards"]) == {f"G{n}" for n in range(1, 9)}
    report = (repo / unseal.FOLDER / "report.md").read_text()
    assert report == "Verdict: pass. MASE at 90 days: 0.91.\n"
    git(repo, "switch", "-q", "--detach", args.commit)
    with pytest.raises(unseal.GuardFailed, match="^G4"):
        unseal.guards(repo, args)
