"""Notebook-facing access to built datasets by catalog ID.

A run is one directory under ``data/runs/`` holding ``capture/`` and ``dataset/``. Nothing here fetches data
or caches results: it reads the receipts and Parquet files that ``avalanche data fetch`` and ``build`` wrote.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from ..core.catalog import DATA_DIR, DataError, load_catalog, sha256

RUNS = DATA_DIR / "runs"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DataError(f"unreadable receipt: {path}: {error}") from error
    if not isinstance(value, dict):
        raise DataError(f"unreadable receipt: {path}: a JSON {type(value).__name__}, not an object")
    return value


def _try_json(path: Path) -> tuple[dict[str, Any] | None, DataError | None]:
    try:
        return _read_json(path), None
    except DataError as error:
        return None, error


def runs(dataset_id: str | None = None, root: Path | None = None) -> list[dict[str, Any]]:
    """Built runs, newest build first, for one dataset or for every dataset.

    A run is skipped when no receipt of it names the requested dataset, even if its other receipt is unreadable. A run
    that one of its receipts ties to the requested dataset is refused with its path when a receipt is unreadable or not
    a JSON object, when its build and capture name different datasets, or when its build names a capture other than its
    own, so a newest-run read never falls back silently to an older run."""
    root = RUNS if root is None else root
    found: list[dict[str, Any]] = []
    if not root.is_dir():
        return found
    for directory in sorted(root.iterdir()):
        build_path = directory / "dataset" / "build.json"
        capture_path = directory / "capture" / "capture.json"
        if not build_path.is_file() or not capture_path.is_file():
            continue
        build, build_error = _try_json(build_path)
        capture, capture_error = _try_json(capture_path)
        names = {value for value in ((build or {}).get("dataset_id"), (capture or {}).get("dataset_id")) if value is not None}
        if dataset_id is not None and names and dataset_id not in names:
            continue
        if build_error or capture_error:
            raise build_error or capture_error
        if len(names) > 1:
            raise DataError(f"run {directory.name}: its build names {build.get('dataset_id')}, its capture {capture.get('dataset_id')}")
        if build.get("source_capture_id") != capture.get("capture_id"):
            raise DataError(f"run {directory.name}: its build names capture {build.get('source_capture_id')}, "
                            f"but its capture is {capture.get('capture_id')}")
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


def readings(reads: dict[str, str], parameters: dict[str, str] | None, root: Path | None = None,
             defaults: dict[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """The built runs a capture's parameters name, for a capture module that declares ``READS``.

    ``reads`` maps a parameter to the dataset whose run it names, and ``defaults`` gives a parameter's value when it is
    not given. A value is a run name, ``auto`` for the newest capture by capture time, or ``none``. Each run found
    becomes a reading: its dataset, run, capture ID, capture directory, and Parquet path. The capture opens those paths
    itself and never imports this module. A parameter with no value, ``none``, or ``auto`` with no built run is left
    out, and the capture decides what that means.
    """
    given = {**(defaults or {}), **{key: value for key, value in (parameters or {}).items() if value}}
    found = {}
    for name, dataset_id in reads.items():
        value = given.get(name)
        if not value or value == "none":
            continue
        if value == "auto":
            available = runs(dataset_id, root)
            if not available:
                continue
            value = max(available, key=lambda item: (item["captured_at"] or "", item["run"]))["run"]
        record = receipt(dataset_id, value, root)
        selected = _select(dataset_id, record["run"], root)
        found[name] = {"dataset_id": dataset_id, "run": record["run"], "capture_id": record["capture"]["capture_id"],
                       "capture_dir": selected["capture_dir"], "parquet": parquet_path(dataset_id, record["run"], root)}
    return found


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
    try:
        for name, item in views(run, root).items():
            path = str(parquet_path(item["dataset_id"], item["run"], root)).replace("'", "''")
            connection.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path}')")
    except Exception:
        connection.close()
        raise
    return connection
