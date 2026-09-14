"""Snowpeer capture, transformation, and validation."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

import duckdb

from . import __version__
from .catalog import (
    DataError, canonical_bytes, catalog_hash, dataset, load_catalog, now as _now, sha256, source,
)


DATASET_ID = "snowpeer.network-summary"


def _request(
    url: str,
    timeout: float,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> tuple[bytes, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "avalanche-phase-ii-research/0.1"},
    )
    try:
        with opener(request, timeout=timeout) as response:
            body = response.read()
            status = int(getattr(response, "status", 200))
            content_type = response.headers.get("Content-Type", "")
    except (OSError, urllib.error.URLError) as error:
        raise DataError(f"request failed for {url}: {error}") from error
    if status != 200:
        raise DataError(f"request returned HTTP {status} for {url}")
    try:
        value = json.loads(body)
    except json.JSONDecodeError as error:
        raise DataError(f"response is not JSON for {url}: {error}") from error
    if not isinstance(value, dict):
        raise DataError(f"response is not a JSON object for {url}")
    return body, {"http_status": status, "content_type": content_type}


def capture_preview(
    dataset_id: str,
    output: Path,
    parameters: dict[str, str] | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if parameters:
        raise DataError(f"{dataset_id} accepts no parameters")
    catalog = catalog or load_catalog()
    definition = dataset(catalog, dataset_id)
    provider = source(catalog, definition["source_id"])
    endpoints = {item["id"]: item for item in provider["endpoints"]}
    requests = [
        {"endpoint_id": endpoint_id, "url": endpoints[endpoint_id]["url"]}
        for endpoint_id in definition["endpoint_ids"]
    ]
    return {
        "dataset_id": dataset_id,
        "source_id": provider["id"],
        "output": str(output),
        "requests": requests,
        "writes": ["raw/*.json", "capture.json"],
        "overwrite": False,
    }


def capture(
    dataset_id: str,
    output: Path,
    timeout: float = 20,
    parameters: dict[str, str] | None = None,
    catalog: dict[str, Any] | None = None,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    preview = capture_preview(dataset_id, output, parameters, catalog)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    records = []
    try:
        raw = temporary / "raw"
        raw.mkdir()
        for item in preview["requests"]:
            body, metadata = _request(item["url"], timeout, opener)
            relative = Path("raw") / f"{item['endpoint_id']}.json"
            (temporary / relative).write_bytes(body)
            records.append({
                "endpoint_id": item["endpoint_id"],
                "url": item["url"],
                "path": str(relative),
                "bytes": len(body),
                "sha256": sha256(body),
                **metadata,
            })
        completed_at = _now()
        identity = sha256(canonical_bytes({"completed_at": completed_at, "responses": records}))
        receipt = {
            "schema_version": "snowpeer-capture/v1",
            "capture_id": f"capture:snowpeer:{completed_at}:{identity[:12]}",
            "dataset_id": dataset_id,
            "source_id": preview["source_id"],
            "completed_at": completed_at,
            "catalog_sha256": catalog_hash(catalog),
            "tool": f"avalanche-research@{__version__}",
            "responses": records,
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return receipt


def read_capture(
    capture_dir: Path,
    catalog: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog = catalog or load_catalog()
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid capture receipt: {error}") from error
    if receipt.get("schema_version") != "snowpeer-capture/v1":
        raise DataError("unsupported capture receipt schema")
    if receipt.get("catalog_sha256") != catalog_hash(catalog):
        raise DataError("capture catalog hash differs from the current data contract")
    values: dict[str, Any] = {}
    for item in receipt.get("responses", []):
        path = capture_dir / item["path"]
        try:
            body = path.read_bytes()
        except OSError as error:
            raise DataError(f"missing captured response: {item.get('path')}") from error
        if sha256(body) != item.get("sha256") or len(body) != item.get("bytes"):
            raise DataError(f"captured response hash or size differs: {item.get('path')}")
        try:
            value = json.loads(body)
        except json.JSONDecodeError as error:
            raise DataError(f"captured response is not JSON: {item.get('path')}") from error
        if not isinstance(value, dict):
            raise DataError(f"captured response is not an object: {item.get('path')}")
        values[item["endpoint_id"]] = value
    expected = set(dataset(catalog, receipt["dataset_id"])["endpoint_ids"])
    missing = sorted(expected - values.keys())
    if missing:
        raise DataError(f"capture is missing endpoints: {', '.join(missing)}")
    return receipt, values


def _number(value: Any, field: str, integer: bool = False) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataError(f"{field} must be numeric")
    if value < 0 or (integer and not isinstance(value, int)):
        raise DataError(f"{field} has an invalid value: {value}")
    return value


def transform(receipt: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    general = values["general-stats"]
    primary = values["primary-validator-count"]
    return {
        "observed_at": receipt["completed_at"],
        "market_cap_usd": _number(values["total-market-cap"].get("mcap"), "mcap", True),
        "l1_count": _number(general.get("activeL1Count"), "activeL1Count", True) + 1,
        "validator_count": (
            _number(general.get("l1ValidatorCount"), "l1ValidatorCount", True)
            + _number(primary.get("count"), "primary validator count", True)
        ),
        "average_tps_30d": _number(values["average-tps-30d"].get("dailyAvgTps"), "dailyAvgTps"),
        "average_daily_transactions_30d": _number(
            values["average-daily-transactions-30d"].get("dailyTxCount"), "dailyTxCount", True
        ),
        "average_daily_icm_messages_30d": _number(
            values["average-daily-icm-30d"].get("dailyIcmCount"), "dailyIcmCount", True
        ),
    }


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    catalog = load_catalog()
    dataset(catalog, dataset_id)
    return {
        "dataset_id": dataset_id,
        "capture": str(capture_dir),
        "output": str(output),
        "writes": ["network-summary.json", "network-summary.parquet", "build.json"],
        "overwrite": False,
    }


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    receipt, values = read_capture(capture_dir, catalog)
    if receipt["dataset_id"] != dataset_id:
        raise DataError(f"capture belongs to {receipt['dataset_id']}, not {dataset_id}")
    row = transform(receipt, values)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        json_path = temporary / "network-summary.json"
        parquet_path = temporary / "network-summary.parquet"
        json_path.write_bytes(canonical_bytes(row))
        connection = duckdb.connect()
        try:
            connection.execute(
                """
                CREATE TABLE network_summary(
                  observed_at VARCHAR,
                  market_cap_usd BIGINT,
                  l1_count INTEGER,
                  validator_count INTEGER,
                  average_tps_30d DOUBLE,
                  average_daily_transactions_30d BIGINT,
                  average_daily_icm_messages_30d BIGINT
                )
                """
            )
            connection.execute(
                "INSERT INTO network_summary VALUES (?, ?, ?, ?, ?, ?, ?)", list(row.values())
            )
            connection.execute("COPY network_summary TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "snowpeer-build/v1",
            "dataset_id": dataset_id,
            "dataset_schema": definition["fields"],
            "source_capture_id": receipt["capture_id"],
            "completed_at": _now(),
            "tool": f"avalanche-research@{__version__}",
            "outputs": [
                {"path": json_path.name, "bytes": json_path.stat().st_size, "sha256": sha256(json_path.read_bytes())},
                {"path": parquet_path.name, "bytes": parquet_path.stat().st_size, "sha256": sha256(parquet_path.read_bytes())},
            ],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return build_receipt


def check(capture_dir: Path, dataset_dir: Path | None = None) -> dict[str, Any]:
    catalog = load_catalog()
    receipt, values = read_capture(capture_dir, catalog)
    expected_row = transform(receipt, values)
    findings: list[str] = []
    checked = ["capture hashes", "required endpoints", "field types", "non-negative values"]
    if dataset_dir is not None:
        checked.extend(["build hashes", "JSON row", "Parquet row"])
        try:
            build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
            for item in build_receipt["outputs"]:
                path = dataset_dir / item["path"]
                body = path.read_bytes()
                if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                    findings.append(f"output hash or size differs: {item['path']}")
            observed_json = json.loads((dataset_dir / "network-summary.json").read_text(encoding="utf-8"))
            if observed_json != expected_row:
                findings.append("JSON row differs from the captured inputs")
            connection = duckdb.connect()
            try:
                columns = list(expected_row)
                row = connection.execute(
                    "SELECT * FROM read_parquet(?)", [str(dataset_dir / "network-summary.parquet")]
                ).fetchone()
                observed_parquet = dict(zip(columns, row or ()))
            finally:
                connection.close()
            if observed_parquet != expected_row:
                findings.append("Parquet row differs from the captured inputs")
        except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid dataset output: {error}")
    return {
        "dataset_id": receipt["dataset_id"],
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "row": expected_row,
        "findings": findings,
    }
