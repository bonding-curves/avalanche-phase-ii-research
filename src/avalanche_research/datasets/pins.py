"""Pinned input sets: a named list of built runs that a model or study reads, frozen with each run's hashes.

A pin file under ``data/pins/`` names one run per dataset, with its capture ID, Parquet file, byte count, sha256, and
the status of its check. ``pin`` takes each dataset's newest run unless one is named, and refuses a run whose check has
not passed. ``verify`` confirms that every pinned run still exists and is unchanged. A reader takes its runs from
``runs`` instead of the newest, so a result can be rebuilt from exactly the inputs it was made from.

A pin may also name the client code commit its results were made with, as ``code``: ``client_commit`` and an optional
``ref`` such as a tag. ``pin`` refuses a commit that does not resolve in the client repository, or a ref that points
elsewhere, and ``verify`` checks both again. A pin without ``code`` reads and verifies as before.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .. import datasets
from ..core.catalog import (
    DATA_DIR,
    ROOT,
    DataError,
    canonical_bytes,
    load_catalog,
    now,
    sha256,
)

PINS = DATA_DIR / "pins"
SCHEMA = "avalanche-pins/v1"


def _check_status(run: str, root: Path | None) -> str:
    path = (datasets.RUNS if root is None else root) / run / "dataset" / "check.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["status"]
    except (OSError, KeyError, json.JSONDecodeError):
        return "unchecked"


def _resolve(revision: str, repo: Path) -> str | None:
    """The full commit a revision names in ``repo``, or None."""
    try:
        run = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"],
                             capture_output=True, text=True, check=False)
    except OSError:
        return None
    return run.stdout.strip() or None


def code_findings(code: dict[str, Any], repo: Path = ROOT) -> list[str]:
    """What no longer holds for a pin's code: a commit that does not resolve here, or a ref that points elsewhere."""
    findings = []
    commit = _resolve(code["client_commit"], repo)
    if commit != code["client_commit"]:
        findings.append(f"code commit {code['client_commit']} does not resolve in {repo.name}")
    if code.get("ref") and _resolve(code["ref"], repo) != code["client_commit"]:
        findings.append(f"code ref {code['ref']} does not point at {code['client_commit']}")
    return findings


def pin(name: str, dataset_ids: list[str], chosen: dict[str, str] | None = None, root: Path | None = None,
        directory: Path | None = None, code_commit: str | None = None, code_ref: str | None = None,
        repo: Path = ROOT) -> dict[str, Any]:
    """Write ``<directory>/<name>.json`` for these datasets. Every pinned run must have passed its check.

    ``code_commit`` and ``code_ref`` name the client code the pin's results come from; the commit is stored in full."""
    chosen = chosen or {}
    if sorted(set(chosen) - set(dataset_ids)):
        raise DataError(f"a run is named for a dataset not in the set: {', '.join(sorted(set(chosen) - set(dataset_ids)))}")
    if len(set(dataset_ids)) != len(dataset_ids):
        raise DataError("a dataset is listed twice")
    known = {item["id"] for item in load_catalog()["datasets"]}
    unknown = [dataset_id for dataset_id in dataset_ids if dataset_id not in known]
    if unknown:
        raise DataError(f"unknown dataset: {', '.join(unknown)}")
    path = (PINS if directory is None else directory) / f"{name}.json"
    if path.exists():
        raise DataError(f"pin file already exists: {path}")
    entries, refused = [], []
    for dataset_id in dataset_ids:
        record = datasets.receipt(dataset_id, chosen.get(dataset_id), root)
        parquet = datasets.parquet_path(dataset_id, record["run"], root)
        status = _check_status(record["run"], root)
        if status != "pass":
            refused.append(f"{dataset_id} run {record['run']} check is {status}")
        body = parquet.read_bytes()
        entries.append({"dataset_id": dataset_id, "run": record["run"], "capture_id": record["capture"]["capture_id"],
                        "captured_at": record["capture"].get("completed_at"), "parquet": parquet.name, "bytes": len(body),
                        "sha256": sha256(body), "check": status})
    if refused:
        raise DataError("; ".join(refused))
    value = {"schema_version": SCHEMA, "name": name, "pinned_at": now(), "runs": entries}
    if code_ref and not code_commit:
        raise DataError("a code ref needs its code commit")
    if code_commit:
        full = _resolve(code_commit, repo)
        if full is None:
            raise DataError(f"code commit {code_commit} does not resolve in {repo.name}")
        code = {"client_commit": full, **({"ref": code_ref} if code_ref else {})}
        findings = code_findings(code, repo)
        if findings:
            raise DataError("; ".join(findings))
        value["code"] = code
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))
    return value


def read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"unreadable pin file: {path}: {error}") from error
    if value.get("schema_version") != SCHEMA:
        raise DataError(f"not a pin file: {path}")
    return value


def verify(path: Path, root: Path | None = None, repo: Path = ROOT) -> list[str]:
    """What no longer matches: a missing run, a changed Parquet file, a check that no longer passes, or named code that no
    longer resolves."""
    findings = []
    value = read(path)
    if "code" in value:
        findings += code_findings(value["code"], repo)
    for entry in value["runs"]:
        parquet = (datasets.RUNS if root is None else root) / entry["run"] / "dataset" / entry["parquet"]
        if not parquet.is_file():
            findings.append(f"{entry['dataset_id']} run {entry['run']} is missing")
            continue
        body = parquet.read_bytes()
        if len(body) != entry["bytes"] or sha256(body) != entry["sha256"]:
            findings.append(f"{entry['dataset_id']} run {entry['run']} differs from its pin")
        build = parquet.parent / "build.json"
        try:
            built = json.loads(build.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            built = {}
        if built.get("dataset_id") != entry["dataset_id"]:
            findings.append(f"{entry['dataset_id']} run {entry['run']} is a run of {built.get('dataset_id')}")
        elif built.get("source_capture_id") != entry["capture_id"]:
            findings.append(f"{entry['dataset_id']} run {entry['run']} was built from another capture than its pin names")
        status = _check_status(entry["run"], root)
        if status != "pass":
            findings.append(f"{entry['dataset_id']} run {entry['run']} check is now {status}")
    return findings


def runs(path: Path) -> dict[str, str]:
    """Dataset ID to pinned run, for a reader that passes it to ``datasets.load``."""
    return {entry["dataset_id"]: entry["run"] for entry in read(path)["runs"]}
