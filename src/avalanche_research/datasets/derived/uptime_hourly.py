"""``derived.validator-uptime-hourly``: every built Builder Hub uptime capture merged into one row per node per hour.

Consecutive daily captures overlap by about six days, so the merged table grows without gaps as long as no two captures
are more than a window apart, which the check against the previous capture verifies. The capture is
``sources.builderhub``. This module moves to ``datasets.derived`` at restructure step M4.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import duckdb

from ... import __version__, datasets
from ...core.catalog import (
    DataError,
    canonical_bytes,
    contract_hash,
    dataset,
    load_catalog,
    now,
    sha256,
)
from ...sources.builderhub import DATASET_ID, _verify_outputs

DERIVED_ID = "derived.validator-uptime-hourly"
DATASET_IDS = (DERIVED_ID,)
DERIVED_TABLE = "validator-uptime-hourly"


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    raise DataError(f"{DERIVED_ID} is derived; use `avalanche data derive`")


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    raise DataError(f"{dataset_id} is not built from a capture; use `avalanche data derive`")


def _inputs(root: Path | None) -> list[dict[str, Any]]:
    """Every built capture under the current contract, oldest first, with the hash of its hourly table."""
    current = contract_hash(load_catalog(), DATASET_ID)
    selected = []
    for item in datasets.runs(DATASET_ID, root):
        capture = json.loads((item["capture_dir"] / "capture.json").read_text(encoding="utf-8"))
        if capture.get("contract_sha256") != current:
            continue
        parquet = item["dataset_dir"] / "uptime-hourly.parquet"
        body = parquet.read_bytes()
        selected.append({"dataset_id": DATASET_ID, "run": item["run"], "capture_id": item["capture_id"], "captured_at": item["captured_at"],
                         "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet})
    if not selected:
        raise DataError(f"no built run of {DATASET_ID} carries the current contract")
    return sorted(selected, key=lambda item: (item["captured_at"] or "", item["run"]))


def _union(inputs: list[dict[str, Any]]) -> str:
    parts = [f"SELECT {rank} AS run_rank, * FROM read_parquet('{str(item['path']).replace(chr(39), chr(39) * 2)}')" for rank, item in enumerate(inputs)]
    return " UNION ALL ".join(parts)


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    """Merge every capture: the newest capture's value for each node-hour, with how many captures held it and whether they agreed."""
    if dataset_id != DERIVED_ID:
        raise DataError(f"{dataset_id} is captured from a provider; use `avalanche data fetch` and `build`")
    if pinned:
        raise DataError(f"{DERIVED_ID} reads every capture; it takes no pinned inputs")
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    inputs = _inputs(root)
    completed_at = now()
    records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records}))
    capture_receipt = {
        "schema_version": "derived-capture/v1", "capture_id": f"capture:derived:{completed_at}:{identity[:12]}",
        "dataset_id": DERIVED_ID, "source_id": "derived", "completed_at": completed_at,
        "contract_sha256": contract_hash(catalog, DERIVED_ID), "tool": f"avalanche-research@{__version__}", "inputs": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.building"
    shutil.rmtree(temporary, ignore_errors=True)
    (temporary / "capture").mkdir(parents=True)
    (temporary / "dataset").mkdir()
    try:
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet = temporary / "dataset" / f"{DERIVED_TABLE}.parquet"
        connection = duckdb.connect()
        try:
            connection.execute(f"""
                COPY (
                  SELECT node_id, bucket_utc,
                         arg_max(p50_uptime_pct, run_rank) AS p50_uptime_pct,
                         count(*) AS captures,
                         count(DISTINCT p50_uptime_pct) > 1 AS revised,
                         min(captured_at) AS first_captured_at,
                         max(captured_at) AS last_captured_at
                  FROM ({_union(inputs)}) GROUP BY node_id, bucket_utc ORDER BY node_id, bucket_utc
                ) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)""", [str(parquet)])
            rows, nodes, first, last, revised = connection.execute(
                "SELECT count(*), count(DISTINCT node_id), min(bucket_utc), max(bucket_utc), count(*) FILTER (WHERE revised) FROM read_parquet(?)",
                [str(parquet)]).fetchone()
        finally:
            connection.close()
        body = parquet.read_bytes()
        build_receipt = {
            "schema_version": "derived-build/v1", "dataset_id": DERIVED_ID, "dataset_schema": dataset(catalog, DERIVED_ID)["fields"],
            "source_capture_id": capture_receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": {"rows": rows, "nodes": nodes, "captures": len(inputs), "first_bucket_utc": first.isoformat() if first else None,
                        "last_bucket_utc": last.isoformat() if last else None, "revised_node_hours": revised},
            "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}],
        }
        (temporary / "dataset" / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"capture": capture_receipt, "build": build_receipt}


def check_derived(capture_dir: Path, dataset_dir: Path | None = None) -> dict[str, Any]:
    """``BC8``: the inputs still hash as recorded, and the table holds every node-hour of every input exactly once."""
    receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    findings: list[str] = []
    checked = ["input hashes"]
    runs_root = capture_dir.parent.parent
    inputs = []
    for item in receipt["inputs"]:
        path = runs_root / item["run"] / "dataset" / item["parquet"]
        try:
            body = path.read_bytes()
        except OSError:
            findings.append(f"BC8 input {item['run']} is missing")
            continue
        if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
            findings.append(f"BC8 input {item['run']} differs from its record")
        inputs.append({**item, "path": path})
    summary: dict[str, Any] = {"captures": len(receipt["inputs"])}
    if dataset_dir is not None and inputs:
        checked.extend(["build hashes", "BC8 every node-hour once"])
        _verify_outputs(dataset_dir, receipt, findings)
        connection = duckdb.connect()
        try:
            table = str(dataset_dir / f"{DERIVED_TABLE}.parquet")
            rows, distinct = connection.execute("SELECT count(*), count(DISTINCT (node_id, bucket_utc)) FROM read_parquet(?)", [table]).fetchone()
            expected = connection.execute(f"SELECT count(DISTINCT (node_id, bucket_utc)) FROM ({_union(inputs)})").fetchone()[0]
        finally:
            connection.close()
        summary.update({"rows": rows, "expected_rows": expected})
        if rows != distinct:
            findings.append("BC8 a node-hour appears twice")
        if rows != expected:
            findings.append(f"BC8 {rows} rows against {expected} distinct node-hours in the inputs")
    return {"dataset_id": DERIVED_ID, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    """``BC8``, as ``check_derived``."""
    return check_derived(capture_dir, dataset_dir)
