"""Pinned input sets: a named list of built runs that a model or study reads, frozen with each run's hashes.

A pin file under ``data/pins/`` names one run per dataset, with its capture ID, Parquet file, byte count, sha256, and
the status of its check. ``pin`` takes each dataset's newest run unless one is named, and refuses a run whose check has
not passed. ``verify`` confirms that every pinned run still exists and is unchanged. A reader takes its runs from
``runs`` instead of the newest, so a result can be rebuilt from exactly the inputs it was made from.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import datasets
from .catalog import DATA_DIR, DataError, canonical_bytes, load_catalog, now, sha256

PINS = DATA_DIR / "pins"
SCHEMA = "avalanche-pins/v1"


def _check_status(run: str, root: Path | None) -> str:
    path = (datasets.RUNS if root is None else root) / run / "dataset" / "check.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["status"]
    except (OSError, KeyError, json.JSONDecodeError):
        return "unchecked"


def pin(name: str, dataset_ids: list[str], chosen: dict[str, str] | None = None, root: Path | None = None,
        directory: Path | None = None) -> dict[str, Any]:
    """Write ``<directory>/<name>.json`` for these datasets. Every pinned run must have passed its check."""
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


def verify(path: Path, root: Path | None = None) -> list[str]:
    """What no longer matches: a missing run, a changed Parquet file, or a check that no longer passes."""
    findings = []
    for entry in read(path)["runs"]:
        parquet = (datasets.RUNS if root is None else root) / entry["run"] / "dataset" / entry["parquet"]
        if not parquet.is_file():
            findings.append(f"{entry['dataset_id']} run {entry['run']} is missing")
            continue
        body = parquet.read_bytes()
        if len(body) != entry["bytes"] or sha256(body) != entry["sha256"]:
            findings.append(f"{entry['dataset_id']} run {entry['run']} differs from its pin")
        status = _check_status(entry["run"], root)
        if status != "pass":
            findings.append(f"{entry['dataset_id']} run {entry['run']} check is now {status}")
    return findings


def runs(path: Path) -> dict[str, str]:
    """Dataset ID to pinned run, for a reader that passes it to ``datasets.load``."""
    return {entry["dataset_id"]: entry["run"] for entry in read(path)["runs"]}
