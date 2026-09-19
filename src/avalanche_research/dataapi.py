"""Avalanche Data API datasets: the current AVAX supply snapshot."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from . import __version__
from .catalog import DataError, canonical_bytes, dataset, load_catalog, now, sha256
from .rest import capture, capture_preview, read_capture  # noqa: F401  shared REST capture path


DATASET_ID = "data-api.avax-supply"
ENDPOINT_ID = "avax-supply"
TABLE = "avax-supply"
IDENTITY_TOLERANCE_AVAX = 1.0
FRESHNESS_SECONDS = 86_400
FIELDS = {
    "total_supply_avax": "totalSupply", "circulating_supply_avax": "circulatingSupply", "total_staked_avax": "totalStaked",
    "total_locked_avax": "totalLocked", "total_rewards_avax": "totalRewards", "total_p_burned_avax": "totalPBurned",
    "total_c_burned_avax": "totalCBurned", "total_x_burned_avax": "totalXBurned", "l1_validator_fees_avax": "l1ValidatorFees",
    "genesis_unlock_avax": "genesisUnlock",
}
TABLE_COLUMNS = {"observed_at": "TIMESTAMP", **{name: "DOUBLE" for name in FIELDS}, "supply_identity_gap_avax": "DOUBLE"}


def load_capture(connection: Any, capture_dir: Path, receipt: dict[str, Any]) -> None:
    record = next(item for item in receipt["responses"] if item["endpoint_id"] == ENDPOINT_ID)
    path = str(capture_dir / record["path"]).replace("'", "''")
    declared = ", ".join(f"{source}: 'VARCHAR'" for source in FIELDS.values()) + ", lastUpdated: 'VARCHAR'"
    typed = ", ".join(f"{name} {kind}" for name, kind in TABLE_COLUMNS.items())
    casts = ", ".join(f"TRY_CAST({source} AS DOUBLE)" for source in FIELDS.values())
    try:
        connection.execute(f"CREATE VIEW capture AS SELECT * FROM read_json('{path}', columns={{{declared}}})")
        connection.execute(f"CREATE TABLE rows({typed})")
        connection.execute(
            f"""
            INSERT INTO rows
            SELECT observed_at, {', '.join(FIELDS)},
                   total_supply_avax - (genesis_unlock_avax + total_rewards_avax - total_p_burned_avax - total_c_burned_avax - total_x_burned_avax)
            FROM (SELECT strptime(lastUpdated, '%Y-%m-%dT%H:%M:%S.%fZ') AS observed_at, {casts} FROM capture)
              AS typed({', '.join(['observed_at', *FIELDS])})
            """
        )
        nulls = connection.execute(f"SELECT COUNT_IF({' OR '.join(f'{c} IS NULL' for c in TABLE_COLUMNS)}) FROM rows").fetchone()[0]
    except duckdb.Error as error:
        raise DataError(f"captured response does not match the declared shape: {error}") from error
    if nulls:
        raise DataError("the supply response misses or mistypes a required value")


def summarize(connection: Any) -> dict[str, Any]:
    record = connection.execute("SELECT observed_at, total_supply_avax, total_staked_avax, total_rewards_avax, supply_identity_gap_avax FROM rows").fetchone()
    return {"rows": 1, "observed_at": record[0].isoformat(timespec="seconds") + "Z", "total_supply_avax": record[1], "total_staked_avax": record[2], "total_rewards_avax": record[3], "supply_identity_gap_avax": record[4]}


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    load_catalog()
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{TABLE}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    receipt, _ = read_capture(capture_dir, catalog)
    if receipt["dataset_id"] != dataset_id:
        raise DataError(f"capture belongs to {receipt['dataset_id']}, not {dataset_id}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet_path = temporary / f"{TABLE}.parquet"
        connection = duckdb.connect()
        try:
            load_capture(connection, capture_dir, receipt)
            connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection)
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "data-api-build/v1",
            "dataset_id": dataset_id,
            "dataset_schema": definition["fields"],
            "source_capture_id": receipt["capture_id"],
            "completed_at": now(),
            "tool": f"avalanche-research@{__version__}",
            "summary": summary,
            "outputs": [{"path": parquet_path.name, "bytes": parquet_path.stat().st_size, "sha256": sha256(parquet_path.read_bytes())}],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return build_receipt


def reconcile(connection: Any, reference_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Compare the API's genesis plus cumulative rewards with the Snowflake protocol supply counter.

    The protocol counter adds each staker's potential reward when it starts, so it runs ahead of minted rewards by
    the potential rewards of periods still in progress. The gap is reported, not judged.
    """
    parquet = reference_dir / "primary-staking-supply.parquet"
    if not parquet.is_file():
        raise DataError(f"missing reference supply dataset: {parquet}")
    record = connection.execute(
        f"""
        SELECT r.genesis_unlock_avax + r.total_rewards_avax AS api_minted_avax, s.block_supply_navax / 1e9 AS protocol_counter_avax, s.accepted_at
        FROM rows r, (SELECT block_supply_navax, accepted_at FROM read_parquet('{str(parquet).replace("'", "''")}') WHERE block_supply_navax IS NOT NULL ORDER BY accepted_at DESC LIMIT 1) s
        """
    ).fetchone()
    return {
        "api_genesis_plus_rewards_avax": record[0],
        "snowflake_protocol_supply_counter_avax": record[1],
        "snowflake_counter_observed_at": record[2].isoformat(timespec="seconds") + "Z",
        "counter_minus_api_avax": record[1] - record[0],
    }, []


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    catalog = load_catalog()
    receipt, _ = read_capture(capture_dir, catalog)
    findings: list[str] = []
    checked = ["capture hashes", "required endpoints", "response shape", "positive totals", "supply identity", "freshness"]
    connection = duckdb.connect()
    try:
        load_capture(connection, capture_dir, receipt)
        completed = receipt["completed_at"].replace("Z", "")
        counts = connection.execute(
            f"""
            SELECT COUNT_IF({' OR '.join(f'{c} < 0' for c in FIELDS)}),
                   COUNT_IF(abs(supply_identity_gap_avax) > {IDENTITY_TOLERANCE_AVAX}),
                   COUNT_IF(abs(date_diff('second', observed_at, TIMESTAMP '{completed}')) > {FRESHNESS_SECONDS})
            FROM rows
            """
        ).fetchone()
        labels = ("carry a negative total", "break the supply identity by more than one AVAX", "were last updated more than a day before the capture")
        findings.extend(f"{failed} rows {label}" for failed, label in zip(counts, labels) if failed)
        summary = summarize(connection)
        if dataset_dir is not None:
            checked.extend(["build hashes", "Parquet rows"])
            try:
                build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
                for item in build_receipt["outputs"]:
                    body = (dataset_dir / item["path"]).read_bytes()
                    if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                        findings.append(f"output hash or size differs: {item['path']}")
                parquet = str(dataset_dir / f"{TABLE}.parquet")
                columns = ", ".join(TABLE_COLUMNS)
                differing = connection.execute(
                    f"""
                    SELECT (SELECT COUNT(*) FROM (SELECT {columns} FROM rows EXCEPT ALL SELECT {columns} FROM read_parquet(?)))
                         + (SELECT COUNT(*) FROM (SELECT {columns} FROM read_parquet(?) EXCEPT ALL SELECT {columns} FROM rows))
                    """,
                    [parquet, parquet],
                ).fetchone()[0]
                if differing:
                    findings.append("Parquet rows differ from the captured inputs")
            except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
                findings.append(f"invalid dataset output: {error}")
        if against is not None:
            checked.append("Snowflake supply counter comparison")
            reconciliation, reconciliation_findings = reconcile(connection, against)
            summary.update(reconciliation)
            findings.extend(reconciliation_findings)
    finally:
        connection.close()
    return {
        "dataset_id": receipt["dataset_id"],
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summary,
        "findings": findings,
    }
