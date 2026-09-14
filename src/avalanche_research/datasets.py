"""Notebook-facing access to built datasets by catalog ID.

A run is one directory under ``data/runs/`` holding ``capture/`` and ``dataset/``. Nothing here fetches data
or caches results: it reads the receipts and Parquet files that ``avalanche data fetch`` and ``build`` wrote.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from .catalog import DATA_DIR, DataError, load_catalog, sha256


RUNS = DATA_DIR / "runs"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"unreadable receipt: {path}: {error}") from error


def runs(dataset_id: str | None = None, root: Path | None = None) -> list[dict[str, Any]]:
    """Built runs, newest build first, for one dataset or for every dataset."""
    root = RUNS if root is None else root
    found: list[dict[str, Any]] = []
    if not root.is_dir():
        return found
    for directory in sorted(root.iterdir()):
        build_path = directory / "dataset" / "build.json"
        capture_path = directory / "capture" / "capture.json"
        if not build_path.is_file() or not capture_path.is_file():
            continue
        build, capture = _read_json(build_path), _read_json(capture_path)
        if dataset_id is not None and build.get("dataset_id") != dataset_id:
            continue
        if build.get("source_capture_id") != capture.get("capture_id"):
            continue
        parquet = next((item["path"] for item in build.get("outputs", []) if item["path"].endswith(".parquet")), None)
        if parquet is None:
            continue
        found.append({
            "dataset_id": build["dataset_id"],
            "run": directory.name,
            "captured_at": capture.get("completed_at"),
            "built_at": build.get("completed_at"),
            "rows": build.get("summary", {}).get("rows"),
            "capture_id": capture.get("capture_id"),
            "capture_dir": directory / "capture",
            "dataset_dir": directory / "dataset",
            "parquet": directory / "dataset" / parquet,
        })
    return sorted(found, key=lambda item: (item["built_at"] or "", item["run"]), reverse=True)


def _select(dataset_id: str, run: str | None, root: Path | None) -> dict[str, Any]:
    root = RUNS if root is None else root
    catalog = load_catalog()
    if dataset_id not in {item["id"] for item in catalog["datasets"]}:
        raise DataError(f"unknown dataset: {dataset_id}")
    available = runs(dataset_id, root)
    if run is not None:
        available = [item for item in available if item["run"] == run]
    if not available:
        raise DataError(f"no built run for {dataset_id}" + (f" named {run}" if run else "") + f" under {root}")
    return available[0]


def receipt(dataset_id: str, run: str | None = None, root: Path | None = None) -> dict[str, Any]:
    """The capture and build receipts of the latest, or the named, run."""
    selected = _select(dataset_id, run, root)
    return {
        "run": selected["run"],
        "capture": _read_json(selected["capture_dir"] / "capture.json"),
        "build": _read_json(selected["dataset_dir"] / "build.json"),
    }


def parquet_path(dataset_id: str, run: str | None = None, root: Path | None = None) -> Path:
    """Path of the built Parquet file after verifying it against the build receipt."""
    selected = _select(dataset_id, run, root)
    build = _read_json(selected["dataset_dir"] / "build.json")
    record = next(item for item in build["outputs"] if item["path"].endswith(".parquet"))
    body = selected["parquet"].read_bytes()
    if len(body) != record["bytes"] or sha256(body) != record["sha256"]:
        raise DataError(f"built output differs from its receipt: {selected['parquet']}")
    return selected["parquet"]


def load(dataset_id: str, run: str | None = None, root: Path | None = None) -> Any:
    """The built table as a pandas DataFrame with the catalog's types.

    Integer columns that hold nulls arrive as pandas nullable Int64, booleans as nullable boolean, and
    timestamps as naive UTC datetimes, exactly as DuckDB stored them.
    """
    path = parquet_path(dataset_id, run, root)
    connection = duckdb.connect()
    try:
        return connection.execute("SELECT * FROM read_parquet(?)", [str(path)]).df()
    finally:
        connection.close()


def view_name(dataset_id: str) -> str:
    """``snowflake.primary-validator-stakes`` becomes ``validator_stakes``; ``coingecko.avax-market-daily`` becomes ``avax_market_daily``."""
    tail = dataset_id.split(".", 1)[1]
    if tail.startswith("primary-"):
        tail = tail[len("primary-"):]
    return tail.replace("-", "_")


def views(run: str | None = None, root: Path | None = None) -> dict[str, dict[str, Any]]:
    """View name to selected run for every dataset that has a built run (or the named run)."""
    catalog = load_catalog()
    selected: dict[str, dict[str, Any]] = {}
    for definition in catalog["datasets"]:
        available = runs(definition["id"], root)
        if run is not None:
            available = [item for item in available if item["run"] == run]
        if available:
            selected[view_name(definition["id"])] = available[0]
    return selected


def connect(run: str | None = None, root: Path | None = None) -> Any:
    """A DuckDB connection with one view per built dataset, so notebooks can join by the keys the datasets carry."""
    connection = duckdb.connect()
    for name, item in views(run, root).items():
        path = str(parquet_path(item["dataset_id"], item["run"], root)).replace("'", "''")
        connection.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path}')")
    return connection
