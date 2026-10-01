"""DefiLlama pool yields filtered to Avalanche and major proof-of-stake staking products."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from .. import __version__
from ..core.catalog import DataError, canonical_bytes, dataset, load_catalog, now, sha256
from .capture.rest import capture, capture_preview, read_capture  # noqa: F401  shared REST capture path


DATASET_ID = "defillama.pool-yields"
ENDPOINT_ID = "pool-yields"
TABLE = "pool-yields"
# DefiLlama project slugs for liquid and native proof-of-stake staking products across chains.
PROOF_OF_STAKE_PROJECTS = (
    "benqi-staked-avax", "lido", "rocket-pool", "coinbase-wrapped-staked-eth", "frax-ether", "stakewise-v3", "stader",
    "ankr", "jito", "jito-liquid-staking", "marinade-finance", "marinade-liquid-staking", "stride", "persistence", "mantle-staked-eth", "ether.fi-stake", "renzo",
)
TABLE_COLUMNS = {
    "observed_at": "TIMESTAMP",
    "pool_id": "VARCHAR",
    "selection": "VARCHAR",
    "chain": "VARCHAR",
    "project": "VARCHAR",
    "symbol": "VARCHAR",
    "tvl_usd": "DOUBLE",
    "liquidity_usd": "DOUBLE",
    "apy": "DOUBLE",
    "apy_base": "DOUBLE",
    "apy_reward": "DOUBLE",
    "apy_mean_30d": "DOUBLE",
    "apy_base_7d": "DOUBLE",
    "apy_base_inception": "DOUBLE",
    "horizon_days": "INTEGER",
    "fee_rate": "DOUBLE",
    "lockup_days": "INTEGER",
    "stablecoin": "BOOLEAN",
    "il_risk": "VARCHAR",
    "exposure": "VARCHAR",
    "reward_tokens": "VARCHAR",
    "underlying_tokens": "VARCHAR",
    "pool_meta": "VARCHAR",
    "outlier": "BOOLEAN",
    "apy_mu": "DOUBLE",
    "apy_sigma": "DOUBLE",
    "observation_count": "INTEGER",
}
POOL_STRUCT = (
    "STRUCT(chain VARCHAR, project VARCHAR, symbol VARCHAR, tvlUsd DOUBLE, apyBase DOUBLE, apyReward DOUBLE, apy DOUBLE, "
    "rewardTokens VARCHAR[], pool VARCHAR, stablecoin BOOLEAN, ilRisk VARCHAR, exposure VARCHAR, poolMeta VARCHAR, "
    "mu DOUBLE, sigma DOUBLE, count INTEGER, outlier BOOLEAN, underlyingTokens VARCHAR[], apyBase7d DOUBLE, apyMean30d DOUBLE, "
    "apyBaseInception DOUBLE)[]"
)


def load_capture(connection: Any, capture_dir: Path, receipt: dict[str, Any]) -> None:
    """Read the captured pools response, keep Avalanche pools and proof-of-stake products, and type them."""
    record = next(item for item in receipt["responses"] if item["endpoint_id"] == ENDPOINT_ID)
    path = str(capture_dir / record["path"]).replace("'", "''")
    typed = ", ".join(f"{name} {kind}" for name, kind in TABLE_COLUMNS.items())
    observed_at = receipt["completed_at"].replace("Z", "")
    projects = ", ".join(f"'{item}'" for item in PROOF_OF_STAKE_PROJECTS)
    try:
        connection.execute(
            f"CREATE VIEW capture AS SELECT unnest(data) AS p FROM read_json('{path}', columns={{status: 'VARCHAR', data: '{POOL_STRUCT}'}})"
        )
        connection.execute(f"CREATE TABLE rows({typed})")
        connection.execute(
            f"""
            INSERT INTO rows
            SELECT TIMESTAMP '{observed_at}', p.pool,
                   CASE WHEN p.chain = 'Avalanche' THEN 'avalanche' ELSE 'proof-of-stake' END,
                   p.chain, p.project, p.symbol, p.tvlUsd, p.tvlUsd,
                   p.apy, p.apyBase, p.apyReward, p.apyMean30d, p.apyBase7d, p.apyBaseInception,
                   NULL, NULL, NULL,
                   p.stablecoin, p.ilRisk, p.exposure, array_to_string(p.rewardTokens, ','), array_to_string(p.underlyingTokens, ','),
                   p.poolMeta, p.outlier, p.mu, p.sigma, p.count
            FROM capture
            WHERE p.chain = 'Avalanche' OR p.project IN ({projects})
            ORDER BY p.chain, p.project, p.pool
            """
        )
        counts = connection.execute("SELECT COUNT(*), COUNT_IF(pool_id IS NULL OR chain IS NULL OR project IS NULL OR tvl_usd IS NULL) FROM rows").fetchone()
    except duckdb.Error as error:
        raise DataError(f"captured response does not match the declared shape: {error}") from error
    if counts[0] == 0:
        raise DataError("captured response holds no selected pools")
    if counts[1]:
        raise DataError(f"{counts[1]} pools miss a required field")


def summarize(connection: Any) -> dict[str, Any]:
    record = connection.execute(
        """
        SELECT COUNT(*), MAX(observed_at), COUNT_IF(selection = 'avalanche'), COUNT_IF(selection = 'proof-of-stake'),
               COUNT(DISTINCT project), SUM(tvl_usd), median(apy), COUNT_IF(apy IS NULL), COUNT_IF(outlier), COUNT_IF(stablecoin)
        FROM rows
        """
    ).fetchone()
    return {
        "rows": record[0],
        "observed_at": record[1].isoformat(timespec="seconds") + "Z",
        "avalanche_pools": record[2],
        "proof_of_stake_pools": record[3],
        "distinct_projects": record[4],
        "tvl_usd_total": record[5],
        "apy_median": record[6],
        "pools_without_apy": record[7],
        "pools_flagged_outlier": record[8],
        "stablecoin_pools": record[9],
    }


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
            "schema_version": "defillama-build/v1",
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


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    if against is not None:
        raise DataError("this dataset has no reference dataset to check against")
    catalog = load_catalog()
    receipt, _ = read_capture(capture_dir, catalog)
    findings: list[str] = []
    checked = ["capture hashes", "required endpoints", "response shape", "unique pools", "selection coverage", "value bounds"]
    connection = duckdb.connect()
    try:
        load_capture(connection, capture_dir, receipt)
        counts = connection.execute(
            """
            SELECT COUNT(*) - COUNT(DISTINCT pool_id),
                   CASE WHEN COUNT_IF(selection = 'avalanche') = 0 OR COUNT_IF(selection = 'proof-of-stake') = 0 THEN 1 ELSE 0 END,
                   COUNT_IF(tvl_usd < 0 OR apy < 0 OR apy_base < 0)
            FROM rows
            """
        ).fetchone()
        labels = ("repeat a pool identifier", "selections are empty", "have a negative TVL or yield")
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
