"""The unseal script's guards, its lock before the first lockbox read, its single use, and its rehearsal."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import unseal_lockbox as unseal

from avalanche_research import datasets
from avalanche_research.core import lockbox
from avalanche_research.core.clock import LOCKBOX_START
from avalanche_research.core.errors import ModelError
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

PREFLIGHT = '''
import hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EVENTS = []
def preflight(*, fit_until):
    EVENTS.append("preflight")
    assert fit_until.isoformat() == "2025-11-19"
    return {"schema": "validator-fit-preflight/v1", "fit_until_exclusive": fit_until.isoformat(),
            "fit_binding": {"status": "MATCH_ADOPTED", "fit_origin": "2025-11-18",
                            "fit_sha256": "1" * 64, "draws_sha256": "2" * 64,
                            "artifact_manifest_sha256": "3" * 64},
            "fitting_operation": True, "protected_labels_read": False, "forecast_executed": False,
            "entrypoint_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
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
        "entry_point": "lockbox_entry:score", "author": "modeling-lead", "uv_lock_sha256": sha256(b"lock\n"),
        "fit_preflight_entry_point": "lockbox_preflight:preflight",
        "pins": ["data/pins/fixture.json"],
        "rehearsal": {"fit_until": "2024-12-16", "score_until": "2025-11-18"}, "foundation_answer": {"default_used": True}}))
    (folder / "template.md").write_text("Verdict: {verdict}. MASE at 90 days: {mase_90}.\n")
    (repo / "src").mkdir()
    (repo / "src" / "lockbox_entry.py").write_text(ENTRY + f"REPO = {str(repo)!r}\n")
    (repo / "src" / "lockbox_preflight.py").write_text(PREFLIGHT)
    (repo / "data" / "pins").mkdir(parents=True)
    # The guard verifies real bytes and receipts without depending on a local research run.
    runs = tmp_path / "runs"
    monkeypatch.setattr(datasets, "RUNS", runs)
    output = runs / "fixture" / "dataset"
    output.mkdir(parents=True)
    parquet = output / "fixture.parquet"
    with duckdb.connect() as connection:
        connection.execute("COPY (SELECT DATE '2024-01-01' AS date_utc, 1 AS value) TO ? (FORMAT PARQUET)", [str(parquet)])
    (output / "build.json").write_text(json.dumps({"dataset_id": "fixture.public", "source_capture_id": "fixture"}))
    (output / "check.json").write_text(json.dumps({"status": "pass"}))
    (repo / "data" / "pins" / "fixture.json").write_text(json.dumps({
        "schema_version": "avalanche-pins/v1", "runs": [{
            "dataset_id": "fixture.public", "run": "fixture", "capture_id": "fixture", "parquet": parquet.name,
            "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes()), "check": "pass",
        }],
    }))
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


def clone_of(repo: Path, name: str) -> Path:
    clone = repo.parent / name
    subprocess.run(["git", "clone", "-q", "-b", "main", str(repo.parent / "remote.git"), str(clone)], check=True)
    git(clone, "config", "user.name", "t")
    git(clone, "config", "user.email", "t@t")
    return clone


def test_two_runners_racing_with_the_same_second_score_once(setup, monkeypatch):
    repo, args = setup
    clone = clone_of(repo, "repo2")
    barrier, pushed, original = threading.Barrier(2), threading.Event(), unseal.git

    def ordered(path, *command):
        if command[:2] == ("push", "origin") and command[-1] == f"refs/tags/{lockbox.TAG}":
            barrier.wait(timeout=10)
            if path == clone:
                assert pushed.wait(timeout=10)
            try:
                return original(path, *command)
            finally:
                if path == repo:
                    pushed.set()
        return original(path, *command)

    monkeypatch.setattr(unseal, "git", ordered)
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-10-08T12:00:00+00:00")
    scored = []
    sys.modules.pop("lockbox_entry", None)

    def run(path):
        try:
            return unseal.unseal(path, args)
        except unseal.GuardFailed as error:
            return str(error)

    real_entry = unseal.entry_point

    def counting(spec, path):
        function = real_entry(spec, path)
        if spec["entry_point"] != "lockbox_entry:score":
            return function
        return lambda *a, **k: scored.append(path) or function(*a, **k)

    monkeypatch.setattr(unseal, "entry_point", counting)
    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(run, [repo, clone]))
    assert scored == [repo]
    assert isinstance(outcomes[0], dict) and outcomes[1].startswith("G4")


def test_a_scorer_failure_after_the_lock_is_published_as_the_result(setup, monkeypatch):
    repo, args = setup
    (repo / "src" / "lockbox_entry.py").write_text("def score(token, fit_until, score_until):\n    if token is not None:\n"
                                                   "        raise RuntimeError('synthetic')\n    return {'verdict': 'n/a'}\n")
    git(repo, "commit", "-q", "-am", "failing scorer")
    git(repo, "push", "-q", "origin", "main")
    args.commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    args.bundle_hash = unseal.bundle_hash(repo / unseal.FOLDER)
    args.rehearsal = str(unseal.rehearse(repo, unseal.argparse.Namespace(out=str(repo.parent / "rehearsal-again.json"))))
    receipt = unseal.unseal(repo, args)
    assert receipt["published"] and "synthetic" in receipt["results"]["error"]
    assert "Verdict: (not computed)" in (repo / unseal.FOLDER / "report.md").read_text()
    assert subprocess.run(["git", "-C", str(repo), "ls-remote", "--heads", "origin", unseal.RECEIPT_BRANCH], capture_output=True, text=True,
                          check=True).stdout


def test_a_failed_publication_is_recorded_with_its_recovery_and_never_rescores(setup, monkeypatch):
    repo, args = setup
    original = unseal.git

    def refusing(path, *command):
        if command[-1] == unseal.RECEIPT_BRANCH and command[0] == "push":
            raise subprocess.CalledProcessError(1, "git push", stderr="remote refused")
        return original(path, *command)

    monkeypatch.setattr(unseal, "git", refusing)
    receipt = unseal.unseal(repo, args)
    stored = json.loads((repo / unseal.FOLDER / "receipt.json").read_text())
    assert not receipt["published"] and "must not run again" in stored["recovery"]
    assert len([call for call in sys.modules["lockbox_entry"].CALLS if call[0] is not None]) == 1


@pytest.mark.parametrize(("fit", "score"), [("2026-01-01", "2025-11-18"), ("2025-06-01", "2025-01-01"), ("2024-12-16", "2025-11-20")])
def test_a_rehearsal_window_that_is_unordered_or_reaches_the_lockbox_is_refused_before_any_call(setup, fit, score):
    repo, _ = setup
    path = repo / unseal.FOLDER / "manifest.json"
    spec = json.loads(path.read_text())
    spec["rehearsal"] = {"fit_until": fit, "score_until": score}
    path.write_text(json.dumps(spec))
    git(repo, "commit", "-q", "-am", "window")
    sys.modules.pop("lockbox_entry", None)
    with pytest.raises(unseal.GuardFailed, match="rehearsal"):
        unseal.rehearse(repo, unseal.argparse.Namespace(out=str(repo.parent / "unsafe.json")))
    assert "lockbox_entry" not in sys.modules


def test_a_rehearsal_from_a_dirty_checkout_is_refused(setup):
    repo, _ = setup
    (repo / "stray.txt").write_text("x")
    with pytest.raises(unseal.GuardFailed, match="clean checkout"):
        unseal.rehearse(repo, unseal.argparse.Namespace(out=str(repo.parent / "dirty.json")))


@pytest.mark.parametrize("spoil", [
    lambda record: {"commit": "", "passed": True, "script_sha256": record["script_sha256"]},
    lambda record: {**record, "bundle_hash": "0" * 64},
    lambda record: {**record, "fit_until": "2024-01-01"},
    lambda record: {**record, "commit": record["commit"][:12]},
])
def test_g7_refuses_a_minimal_or_mismatched_rehearsal_record(setup, spoil):
    repo, args = setup
    record = json.loads(Path(args.rehearsal).read_text())
    Path(args.rehearsal).write_text(json.dumps(spoil(record)))
    with pytest.raises(unseal.GuardFailed, match="^G7"):
        unseal.guards(repo, args)


def test_g3_refuses_a_manifest_without_pins(setup):
    repo, args = setup
    path = repo / unseal.FOLDER / "manifest.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "pins": []}))
    git(repo, "commit", "-q", "-am", "no pins")
    git(repo, "push", "-q", "origin", "main")
    args.commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    args.bundle_hash = unseal.bundle_hash(repo / unseal.FOLDER)
    with pytest.raises(unseal.GuardFailed, match="^G3"):
        unseal.guards(repo, args)


@pytest.mark.parametrize("missing", [False, True])
def test_g3_refuses_changed_or_missing_pinned_bytes(setup, missing):
    repo, args = setup
    parquet = datasets.RUNS / "fixture" / "dataset" / "fixture.parquet"
    if missing:
        parquet.unlink()
    else:
        parquet.write_bytes(parquet.read_bytes() + b"changed")
    with pytest.raises(unseal.GuardFailed, match="^G3"):
        unseal.guards(repo, args)


def test_an_entry_point_outside_the_repository_is_refused(setup):
    repo, _ = setup
    with pytest.raises(unseal.GuardFailed, match="not a file inside"):
        unseal.entry_point({"entry_point": "json:loads"}, repo)


def test_a_forged_token_is_refused():
    forged = object.__new__(lockbox.Unseal)
    with pytest.raises(ModelError):
        lockbox.require(LOCKBOX_START, forged)


def test_a_template_that_cannot_be_filled_still_publishes_the_receipt_with_a_fallback_report(setup):
    repo, args = setup
    folder = repo / unseal.FOLDER
    (folder / "template.md").write_text("MASE: {mase_90:.2f}\n")
    (repo / "src" / "lockbox_entry.py").write_text("def score(token, fit_until, score_until):\n    if token is not None:\n"
                                                   "        raise RuntimeError('synthetic')\n    return {'mase_90': 1.0}\n")
    git(repo, "commit", "-q", "-am", "failing scorer, number format")
    git(repo, "push", "-q", "origin", "main")
    args.commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    args.bundle_hash = unseal.bundle_hash(folder)
    args.rehearsal = str(unseal.rehearse(repo, unseal.argparse.Namespace(out=str(repo.parent / "rehearsal-format.json"))))
    receipt = unseal.unseal(repo, args)
    stored = json.loads((folder / "receipt.json").read_text())
    assert receipt["published"] and stored["published"] and "synthetic" in stored["results"]["error"]
    assert "ValueError" in stored["report_error"] and "could not be filled" in (folder / "report.md").read_text()
    assert subprocess.run(["git", "-C", str(repo), "ls-remote", "--heads", "origin", unseal.RECEIPT_BRANCH], capture_output=True, text=True,
                          check=True).stdout


def test_any_failure_while_publishing_keeps_the_receipt_and_its_recovery(setup, monkeypatch):
    repo, args = setup
    monkeypatch.setattr(unseal, "render_report", lambda template, results: (_ for _ in ()).throw(OSError("disk full")))
    receipt = unseal.unseal(repo, args)
    stored = json.loads((repo / unseal.FOLDER / "receipt.json").read_text())
    assert not receipt["published"] and "disk full" in stored["publish_error"] and "must not run again" in stored["recovery"]
    assert len([call for call in sys.modules["lockbox_entry"].CALLS if call[0] is not None]) == 1


def failing_receipt_writes(monkeypatch, failures):
    """Make the first ``failures`` writes of receipt.json raise OSError."""
    original, count = Path.write_bytes, {"n": 0}

    def write_bytes(self, data):
        if self.name == "receipt.json" and count["n"] < failures:
            count["n"] += 1
            raise OSError("storage unavailable")
        return original(self, data)

    monkeypatch.setattr(Path, "write_bytes", write_bytes)
    return count


def test_a_transient_first_receipt_write_failure_is_retried_and_the_remote_receipt_is_confirmed(setup, monkeypatch):
    repo, args = setup
    failing_receipt_writes(monkeypatch, 1)
    receipt = unseal.unseal(repo, args)
    remote = unseal.remote_receipt(repo)
    assert receipt["published"] and json.loads(remote)["published"] and "recovery" not in json.loads(remote)
    assert len([call for call in sys.modules["lockbox_entry"].CALLS if call[0] is not None]) == 1


def test_a_receipt_that_cannot_be_written_is_printed_with_its_recovery_and_exits_three(setup, monkeypatch, capsys):
    repo, args = setup
    failing_receipt_writes(monkeypatch, 10**6)
    argv = ["unseal", "--repo", str(repo), "--commit", args.commit, "--bundle-hash", args.bundle_hash, "--runner", args.runner,
            "--witness", args.witness, "--rehearsal", args.rehearsal, "--registry-unsealed-at", args.registry_unsealed_at]
    assert unseal.main(argv) == 3
    printed = capsys.readouterr().out
    assert "must not run again" in printed and "could not be written" in printed and '"persisted": false' in printed
    assert len([call for call in sys.modules["lockbox_entry"].CALLS if call[0] is not None]) == 1


def test_publication_counts_only_when_the_remote_holds_the_committed_receipt(setup, monkeypatch):
    repo, args = setup
    monkeypatch.setattr(unseal, "remote_receipt", lambda path: b"another receipt")
    receipt = unseal.unseal(repo, args)
    stored = json.loads((repo / unseal.FOLDER / "receipt.json").read_text())
    assert not receipt["published"] and "remote receipt branch" in stored["publish_error"] and "must not run again" in stored["recovery"]


@pytest.fixture
def pre_marker(tmp_path, monkeypatch):
    """Synthetic callable and spies only: no Git remote, model, token or marker."""
    repo = tmp_path / "candidate"
    source = repo / "src" / "synthetic_fit.py"
    source.parent.mkdir(parents=True)
    source.write_text(PREFLIGHT)
    folder = repo / unseal.FOLDER
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps({
        "entry_point": "synthetic_score:score", "fit_preflight_entry_point": "synthetic_fit:preflight"}))
    args = unseal.argparse.Namespace(commit="a" * 40, bundle_hash=unseal.bundle_hash(folder), runner="synthetic-runner")
    events = []
    original_entry, original_publish = unseal.entry_point, unseal.publish

    def reads_only(path, *command):
        if command == ("rev-parse", "HEAD"):
            return args.commit
        if command == ("status", "--porcelain"):
            return ""
        raise RuntimeError("synthetic publication unavailable")

    def load(spec, path):
        if spec["entry_point"] == "synthetic_score:score":
            events.append("entry_point")
            return lambda *a, **k: events.append("score") or {"verdict": "synthetic"}
        function = original_entry(spec, path)
        function.__globals__["EVENTS"] = events
        return function

    monkeypatch.setattr(unseal, "git", reads_only)
    monkeypatch.setattr(unseal, "guards", lambda *a: events.append("guards") or {f"G{n}": "synthetic" for n in range(1, 9)})
    monkeypatch.setattr(unseal, "acquire", lambda *a: events.append("acquire") or "synthetic-marker")
    monkeypatch.setattr(unseal.lockbox, "issue", lambda *a: events.append("issue") or object())
    monkeypatch.setattr(unseal, "entry_point", load)
    monkeypatch.setattr(unseal, "publish", lambda repo, args, receipt, results: events.append("publish") or {**receipt, "published": True})
    return repo, args, events, source, original_publish


def assert_no_marker(events):
    assert not set(events) & {"acquire", "issue", "entry_point", "score", "publish"}


def test_pre_marker_success_order_and_bound_proof(pre_marker):
    repo, args, events, source, _ = pre_marker
    receipt = unseal.unseal(repo, args)
    assert events == ["guards", "preflight", "acquire", "issue", "entry_point", "score", "publish"]
    assert receipt["fit_preflight"]["fit_binding"]["status"] == "MATCH_ADOPTED"
    assert receipt["fit_preflight"]["entrypoint_sha256"] == sha256(source.read_bytes())
    assert set(receipt["guards"]) == {f"G{n}" for n in range(1, 9)}


@pytest.mark.parametrize("declaration", [None, "", "json:loads", "../outside:preflight"])
def test_pre_marker_missing_or_invalid_callable_never_acquires(pre_marker, declaration):
    repo, args, events, _, _ = pre_marker
    path = repo / unseal.FOLDER / "manifest.json"
    spec = json.loads(path.read_text())
    spec["fit_preflight_entry_point"] = declaration
    path.write_text(json.dumps(spec))
    with pytest.raises(unseal.GuardFailed):
        unseal.unseal(repo, args)
    assert_no_marker(events)


def test_pre_marker_fit_failure_never_acquires(pre_marker):
    repo, args, events, source, _ = pre_marker
    source.write_text(PREFLIGHT.replace('    EVENTS.append("preflight")', '    raise ValueError("synthetic fit mismatch")'))
    with pytest.raises(unseal.GuardFailed, match="synthetic fit mismatch"):
        unseal.unseal(repo, args)
    assert_no_marker(events)


@pytest.mark.parametrize("mutation", [
    'result["schema"] = "wrong"',
    'result["fit_until_exclusive"] = "2025-11-18"',
    'result["fit_binding"]["status"] = "MATCH_CANDIDATE"',
    'result["fit_binding"]["fit_origin"] = "2025-11-19"',
    'result["fit_binding"]["fit_sha256"] = "bad"',
    'result["fit_binding"]["draws_sha256"] = "bad"',
    'result["fit_binding"]["artifact_manifest_sha256"] = "bad"',
    'result["fitting_operation"] = False',
    'result["protected_labels_read"] = True',
    'result["forecast_executed"] = True',
    'result["entrypoint_sha256"] = "0" * 64',
    'result["not_serializable"] = object()',
    'result["extra_diagnostic"] = float("nan")',
    'result["extra_diagnostic"] = float("inf")',
    'result["extra_diagnostic"] = float("-inf")',
])
def test_pre_marker_invalid_proof_never_acquires(pre_marker, mutation):
    repo, args, events, source, _ = pre_marker
    source.write_text(PREFLIGHT.replace("    return {", "    result = {") + "\n    " + mutation + "\n    return result\n")
    with pytest.raises(unseal.GuardFailed):
        unseal.unseal(repo, args)
    assert_no_marker(events)


def test_pre_marker_wrong_root_refuses_before_callable(pre_marker):
    repo, args, events, source, _ = pre_marker
    source.write_text(PREFLIGHT.replace('EVENTS = []', 'ROOT = ROOT.parent\nEVENTS = []'))
    with pytest.raises(unseal.GuardFailed, match="wrong ROOT"):
        unseal.unseal(repo, args)
    assert events == ["guards"]


def test_pre_marker_symlink_escape_refuses_before_import(pre_marker, tmp_path):
    repo, args, events, source, _ = pre_marker
    outside = tmp_path / "outside.py"
    outside.write_text('raise AssertionError("outside module imported")')
    source.unlink()
    source.symlink_to(outside)
    with pytest.raises(unseal.GuardFailed, match="outside"):
        unseal.unseal(repo, args)
    assert_no_marker(events)


def test_pre_marker_reexported_callable_has_wrong_source(pre_marker, monkeypatch, tmp_path):
    repo, args, events, source, _ = pre_marker
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "synthetic_foreign_fit.py").write_text(PREFLIGHT)
    monkeypatch.syspath_prepend(str(foreign))
    source.write_text("from synthetic_foreign_fit import preflight\n")
    with pytest.raises(unseal.GuardFailed, match="wrong source"):
        unseal.unseal(repo, args)
    assert events == ["guards"]


@pytest.mark.parametrize("change", ["head", "dirty", "bundle", "source"])
def test_pre_marker_drift_refuses_before_acquire(pre_marker, monkeypatch, change):
    repo, args, events, source, _ = pre_marker
    if change == "source":
        extra = 'Path(__file__).write_text(Path(__file__).read_text() + "# drift\\n")'
        source.write_text(PREFLIGHT.replace("    return {", "    result = {") + "\n    " + extra + "\n    return result\n")
    elif change == "bundle":
        extra = '(ROOT / "validation/lockbox/drift.txt").write_text("drift")'
        source.write_text(PREFLIGHT.replace("    return {", "    result = {") + "\n    " + extra + "\n    return result\n")
    else:
        original = unseal.git

        def drift(path, *command):
            if "preflight" in events:
                if change == "head" and command == ("rev-parse", "HEAD"):
                    return "b" * 40
                if change == "dirty" and command == ("status", "--porcelain"):
                    return " M tracked"
            return original(path, *command)

        monkeypatch.setattr(unseal, "git", drift)
    with pytest.raises(unseal.GuardFailed):
        unseal.unseal(repo, args)
    assert_no_marker(events)


def test_pre_marker_score_failure_still_reaches_publication(pre_marker, monkeypatch):
    repo, args, events, _, _ = pre_marker
    original = unseal.entry_point

    def load(spec, path):
        if spec["entry_point"] == "synthetic_score:score":
            def fail(*args, **kwargs):
                events.append("score")
                raise RuntimeError("synthetic scorer failed")
            return fail
        return original(spec, path)

    monkeypatch.setattr(unseal, "entry_point", load)
    receipt = unseal.unseal(repo, args)
    assert receipt["published"] and "synthetic scorer failed" in receipt["results"]["error"]
    assert events.count("acquire") == events.count("issue") == events.count("publish") == 1


def test_pre_marker_publication_failure_preserves_recovery(pre_marker, monkeypatch):
    repo, args, events, _, original_publish = pre_marker
    monkeypatch.setattr(unseal, "publish", original_publish)
    receipt = unseal.unseal(repo, args)
    stored = json.loads((repo / unseal.FOLDER / "receipt.json").read_text())
    assert not receipt["published"] and "must not run again" in stored["recovery"]
    assert "synthetic publication unavailable" in stored["publish_error"]
    assert events.count("acquire") == events.count("issue") == events.count("score") == 1
