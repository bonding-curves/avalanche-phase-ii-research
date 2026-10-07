"""Pinned input sets: checked runs are pinned with their hashes, and a later change to a pinned run is reported."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import duckdb
import pytest
from click.testing import CliRunner

from avalanche_research import cli
from avalanche_research.core.catalog import DataError, canonical_bytes, sha256
from avalanche_research.datasets import pins

LEDGER = "derived.avax-monetary-daily"
PERIODS = "derived.monetary-periods"


def make_run(root: Path, run: str, dataset_id: str, built_at: str, status: str | None = "pass") -> None:
    capture_dir, dataset_dir = root / run / "capture", root / run / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / "table.parquet"
    duckdb.connect().execute(f"COPY (SELECT '{run}' AS run) TO ? (FORMAT PARQUET)", [str(parquet)])
    capture_id = f"capture:test:{run}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({"capture_id": capture_id, "dataset_id": dataset_id, "completed_at": built_at}))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({"dataset_id": dataset_id, "source_capture_id": capture_id, "completed_at": built_at,
                                                              "summary": {"rows": 1}, "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}]}))
    if status:
        (dataset_dir / "check.json").write_bytes(canonical_bytes({"status": status}))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    make_run(runs, "ledger-old", LEDGER, "2026-09-29T00:00:00Z")
    make_run(runs, "ledger-new", LEDGER, "2026-09-30T00:00:00Z")
    make_run(runs, "periods", PERIODS, "2026-09-30T00:00:00Z")
    make_run(runs, "periods-failed", PERIODS, "2026-09-30T01:00:00Z", status="attention")
    return runs


def test_the_newest_or_the_named_run_is_pinned_with_its_hash(root, tmp_path):
    value = pins.pin("m2", [LEDGER, PERIODS], {PERIODS: "periods"}, root=root, directory=tmp_path / "pins")
    assert [(entry["dataset_id"], entry["run"], entry["check"]) for entry in value["runs"]] == [(LEDGER, "ledger-new", "pass"), (PERIODS, "periods", "pass")]
    path = tmp_path / "pins" / "m2.json"
    assert pins.runs(path) == {LEDGER: "ledger-new", PERIODS: "periods"}
    assert pins.verify(path, root) == []
    with pytest.raises(DataError, match="already exists"):
        pins.pin("m2", [LEDGER], root=root, directory=tmp_path / "pins")


def test_a_run_whose_check_has_not_passed_is_refused(root, tmp_path):
    # The newest periods run failed its check, so pinning the newest is refused and names it.
    with pytest.raises(DataError, match="derived.monetary-periods run periods-failed check is attention"):
        pins.pin("m2", [LEDGER, PERIODS], root=root, directory=tmp_path / "pins")
    with pytest.raises(DataError, match="unknown dataset"):
        pins.pin("m2", ["no.such-dataset"], root=root, directory=tmp_path / "pins")
    with pytest.raises(DataError, match="not in the set"):
        pins.pin("m2", [LEDGER], {PERIODS: "periods"}, root=root, directory=tmp_path / "pins")


def test_a_changed_missing_or_failing_run_is_reported(root, tmp_path):
    pins.pin("m2", [LEDGER, PERIODS], {PERIODS: "periods"}, root=root, directory=tmp_path / "pins")
    path = tmp_path / "pins" / "m2.json"
    parquet = root / "ledger-new" / "dataset" / "table.parquet"
    parquet.write_bytes(parquet.read_bytes() + b"\n")
    (root / "periods" / "dataset" / "check.json").write_bytes(canonical_bytes({"status": "attention"}))
    assert pins.verify(path, root) == [f"{LEDGER} run ledger-new differs from its pin", f"{PERIODS} run periods check is now attention"]
    for item in (root / "ledger-new").rglob("*"):
        if item.is_file():
            item.unlink()
    assert pins.verify(path, root)[0] == f"{LEDGER} run ledger-new is missing"


def test_the_cli_pins_and_checks(root, tmp_path, monkeypatch):
    monkeypatch.setattr(pins.datasets, "RUNS", root)
    monkeypatch.setattr(pins, "PINS", tmp_path / "pins")
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["data", "pin", "m2", LEDGER, PERIODS, "--run", f"{PERIODS}=periods", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["pins"]["runs"][0]["run"] == "ledger-new"
    checked = runner.invoke(cli.cli, ["data", "pin-check", str(tmp_path / "pins" / "m2.json")])
    assert checked.exit_code == 0 and "2 runs; 0 findings" in checked.output


def git_repo(path: Path) -> tuple[str, str]:
    """A repository with two commits and the tag v1 on the first. Returns both commit IDs."""
    def run(*args):
        return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True).stdout.strip()
    path.mkdir()
    run("init", "-q")
    for name in ("first", "second"):
        (path / name).write_text(name)
        run("add", name)
        run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", name)
        if name == "first":
            run("tag", "v1")
    return run("rev-parse", "HEAD~1"), run("rev-parse", "HEAD")


def test_a_pin_names_its_code_and_refuses_code_that_does_not_resolve(root, tmp_path):
    repo = tmp_path / "repo"
    first, second = git_repo(repo)
    value = pins.pin("m2", [LEDGER], root=root, directory=tmp_path / "pins", code_commit=first[:7], code_ref="v1", repo=repo)
    assert value["code"] == {"client_commit": first, "ref": "v1"}
    assert pins.verify(tmp_path / "pins" / "m2.json", root, repo=repo) == []
    for kwargs, message in (({"code_commit": "0" * 40}, "does not resolve"), ({"code_commit": second, "code_ref": "v1"}, "does not point"),
                            ({"code_ref": "v1"}, "needs its code commit")):
        with pytest.raises(DataError, match=message):
            pins.pin("other", [LEDGER], root=root, directory=tmp_path / "pins", repo=repo, **kwargs)
    assert not (tmp_path / "pins" / "other.json").exists()
    subprocess.run(["git", "-C", str(repo), "tag", "-f", "v1", second], check=True, capture_output=True)
    assert pins.verify(tmp_path / "pins" / "m2.json", root, repo=repo) == [f"code ref v1 does not point at {first}"]


def test_a_pin_without_code_reads_and_verifies_as_before(root, tmp_path):
    value = pins.pin("m2", [LEDGER], root=root, directory=tmp_path / "pins")
    assert "code" not in value
    assert pins.verify(tmp_path / "pins" / "m2.json", root, repo=tmp_path / "no-repo") == []
