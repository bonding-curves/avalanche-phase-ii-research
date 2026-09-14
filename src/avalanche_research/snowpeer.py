"""Snowpeer capture, transformation, and validation."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from . import __version__
from .catalog import DataError, canonical_bytes, dataset, load_catalog, now as _now, sha256
from .rest import capture, capture_preview, read_capture  # noqa: F401  re-exported for the Snowpeer dataset


DATASET_ID = "snowpeer.network-summary"


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
