"""DefiLlama yield histories for the opportunity-cost study: daily pool charts and the lending and borrowing snapshot.

| Dataset | Rows |
| --- | --- |
| ``defillama.pool-history`` | One per declared pool and day of DefiLlama's ``/chart/{pool}`` series |
| ``defillama.lend-borrow`` | One per Avalanche lending pool at the capture instant, supply rate beside borrow rate |

The pool list is fixed here, so a pool that DefiLlama renames or retires keeps its identifier and its label. Pool
identifiers were resolved from ``yields.llama.fi/pools`` on 2026-10-05. DefiLlama keeps no history of the lending
endpoint (``/chartLendBorrow`` answers HTTP 402), so ``defillama.lend-borrow`` is a series only through repeated captures.
"""

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


HISTORY_ID = "defillama.pool-history"
LEND_BORROW_ID = "defillama.lend-borrow"
DATASET_IDS = (HISTORY_ID, LEND_BORROW_ID)
TABLES = {HISTORY_ID: "pool-history", LEND_BORROW_ID: "lend-borrow"}
# Label, chain, project and symbol as DefiLlama reported them on 2026-10-05. The endpoint id is ``pool-chart-<label>``.
POOLS = {
    "savax": ("3790c3e5-8644-4f6b-8feb-12434d8b99f9", "Avalanche", "benqi-staked-avax", "SAVAX"),
    "ggavax": ("3efc0d84-53c6-4c6a-b1c3-c140502c7f26", "Avalanche", "hypha", "GGAVAX"),
    "aave-wavax": ("a1e18d7d-9a5f-4251-acb4-a87e005fe2c5", "Avalanche", "aave-v3", "WAVAX"),
    "aave-usdc": ("c4b05318-88af-4536-a834-f5fc8940d2d3", "Avalanche", "aave-v3", "USDC"),
    "aave-usdt": ("e6692d08-85b6-4b50-952b-7c5c531862fe", "Avalanche", "aave-v3", "USDT"),
    "benqi-avax": ("38583317-5354-4767-8f1e-6a0ae3aa7b5d", "Avalanche", "benqi-lending", "AVAX"),
    "benqi-usdc": ("ff59b165-64e0-4868-a6db-6049b5135358", "Avalanche", "benqi-lending", "USDC"),
    "steth": ("747c1d2a-c668-4682-b9f9-296708a3dd90", "Ethereum", "lido", "STETH"),
    "jitosol": ("0e7d0722-9054-4907-8593-567b353c0900", "Solana", "jito-liquid-staking", "JITOSOL"),
}
HISTORY_COLUMNS = {
    "observation_date": "DATE",
    "observed_at": "TIMESTAMP",
    "label": "VARCHAR",
    "pool_id": "VARCHAR",
    "chain": "VARCHAR",
    "project": "VARCHAR",
    "symbol": "VARCHAR",
    "tvl_usd": "DOUBLE",
    "apy": "DOUBLE",
    "apy_base": "DOUBLE",
    "apy_reward": "DOUBLE",
    "apy_base_7d": "DOUBLE",
    "price_per_share": "DOUBLE",
}
LEND_BORROW_COLUMNS = {
    "observed_at": "TIMESTAMP",
    "pool_id": "VARCHAR",
    "chain": "VARCHAR",
    "project": "VARCHAR",
    "symbol": "VARCHAR",
    "apy_supply": "DOUBLE",
    "apy_base_supply": "DOUBLE",
    "apy_reward_supply": "DOUBLE",
    "apy_base_borrow": "DOUBLE",
    "apy_reward_borrow": "DOUBLE",
    "total_supply_usd": "DOUBLE",
    "total_borrow_usd": "DOUBLE",
    "debt_ceiling_usd": "DOUBLE",
    "ltv": "DOUBLE",
    "borrowable": "BOOLEAN",
    "borrow_factor": "DOUBLE",
}
COLUMNS = {HISTORY_ID: HISTORY_COLUMNS, LEND_BORROW_ID: LEND_BORROW_COLUMNS}
POINT_STRUCT = (
    "STRUCT(\"timestamp\" VARCHAR, tvlUsd DOUBLE, apy DOUBLE, apyBase DOUBLE, apyReward DOUBLE, apyBase7d DOUBLE, "
    "pricePerShare DOUBLE)[]"
)
POOL_STRUCT = "STRUCT(pool VARCHAR, chain VARCHAR, project VARCHAR, symbol VARCHAR, apy DOUBLE, apyBase DOUBLE, apyReward DOUBLE)[]"
LEND_STRUCT = (
    "{pool: 'VARCHAR', apyBaseBorrow: 'DOUBLE', apyRewardBorrow: 'DOUBLE', totalSupplyUsd: 'DOUBLE', totalBorrowUsd: 'DOUBLE', "
    "debtCeilingUsd: 'DOUBLE', ltv: 'DOUBLE', borrowable: 'BOOLEAN', borrowFactor: 'DOUBLE'}"
)


def _path(capture_dir: Path, receipt: dict[str, Any], endpoint_id: str) -> str:
    record = next(item for item in receipt["responses"] if item["endpoint_id"] == endpoint_id)
    return str(capture_dir / record["path"]).replace("'", "''")


def _load_history(connection: Any, capture_dir: Path, receipt: dict[str, Any]) -> None:
    parts = []
    for label, (pool_id, chain, project, symbol) in POOLS.items():
        path = _path(capture_dir, receipt, f"pool-chart-{label}")
        parts.append(
            f"SELECT '{label}' AS label, '{pool_id}' AS pool_id, '{chain}' AS chain, '{project}' AS project, '{symbol}' AS symbol, "
            f"unnest(data) AS d FROM read_json('{path}', columns={{status: 'VARCHAR', data: '{POINT_STRUCT}'}})"
        )
    # A pool can report twice in one UTC day. The later point is the day's value.
    connection.execute(
        f"""
        INSERT INTO rows
        SELECT * FROM (
          SELECT DISTINCT ON (label, observed_at::DATE) observed_at::DATE, observed_at, label, pool_id, chain, project, symbol,
                 tvl_usd, apy, apy_base, apy_reward, apy_base_7d, price_per_share
          FROM (
            SELECT strptime(d."timestamp", '%Y-%m-%dT%H:%M:%S.%gZ') AS observed_at, label, pool_id, chain, project, symbol,
                   d.tvlUsd AS tvl_usd, d.apy, d.apyBase AS apy_base, d.apyReward AS apy_reward, d.apyBase7d AS apy_base_7d,
                   d.pricePerShare AS price_per_share
            FROM ({" UNION ALL ".join(parts)})
          )
          ORDER BY label, observed_at::DATE, observed_at DESC
        )
        ORDER BY label, 1
        """
    )


def _load_lend_borrow(connection: Any, capture_dir: Path, receipt: dict[str, Any]) -> None:
    observed_at = receipt["completed_at"].replace("Z", "")
    pools = _path(capture_dir, receipt, "pool-yields")
    lending = _path(capture_dir, receipt, "lend-borrow")
    connection.execute(
        f"""
        INSERT INTO rows
        SELECT TIMESTAMP '{observed_at}', l.pool, p.chain, p.project, p.symbol, p.apy, p.apyBase, p.apyReward,
               l.apyBaseBorrow, l.apyRewardBorrow, l.totalSupplyUsd, l.totalBorrowUsd, l.debtCeilingUsd, l.ltv, l.borrowable,
               l.borrowFactor
        FROM read_json('{lending}', format='array', columns={LEND_STRUCT}) AS l
        JOIN (SELECT unnest(data, recursive := true) FROM read_json('{pools}', columns={{status: 'VARCHAR', data: '{POOL_STRUCT}'}})) AS p
          ON p.pool = l.pool
        WHERE p.chain = 'Avalanche'
        ORDER BY p.project, p.symbol, l.pool
        """
    )


def load_capture(connection: Any, capture_dir: Path, receipt: dict[str, Any]) -> None:
    """Type the captured responses into ``rows`` for the receipt's dataset."""
    dataset_id = receipt["dataset_id"]
    typed = ", ".join(f"{name} {kind}" for name, kind in COLUMNS[dataset_id].items())
    try:
        connection.execute(f"CREATE TABLE rows({typed})")
        if dataset_id == HISTORY_ID:
            _load_history(connection, capture_dir, receipt)
            missing = connection.execute(
                "SELECT COUNT(*), COUNT_IF(observed_at IS NULL OR tvl_usd IS NULL), COUNT(DISTINCT label) FROM rows"
            ).fetchone()
            if missing[2] != len(POOLS):
                raise DataError(f"{len(POOLS) - missing[2]} declared pools returned no history")
        else:
            _load_lend_borrow(connection, capture_dir, receipt)
            missing = connection.execute("SELECT COUNT(*), COUNT_IF(pool_id IS NULL OR project IS NULL), 0 FROM rows").fetchone()
    except duckdb.Error as error:
        raise DataError(f"captured response does not match the declared shape: {error}") from error
    if missing[0] == 0:
        raise DataError("captured responses hold no rows")
    if missing[1]:
        raise DataError(f"{missing[1]} rows miss a required field")


def summarize(connection: Any, dataset_id: str) -> dict[str, Any]:
    if dataset_id == HISTORY_ID:
        pools = connection.execute(
            """
            SELECT label, COUNT(*), MIN(observation_date), MAX(observation_date),
                   date_diff('day', MIN(observation_date), MAX(observation_date)) + 1 - COUNT(*)
            FROM rows GROUP BY label ORDER BY label
            """
        ).fetchall()
        return {
            "rows": sum(item[1] for item in pools),
            "pools": {label: {"days": days, "first": str(first), "last": str(last), "missing_days": gaps} for label, days, first, last, gaps in pools},
        }
    record = connection.execute(
        """
        SELECT COUNT(*), MAX(observed_at), COUNT(DISTINCT project), SUM(total_supply_usd), SUM(total_borrow_usd),
               COUNT_IF(apy_base_borrow IS NULL)
        FROM rows
        """
    ).fetchone()
    return {
        "rows": record[0],
        "observed_at": record[1].isoformat(timespec="seconds") + "Z",
        "distinct_projects": record[2],
        "total_supply_usd": record[3],
        "total_borrow_usd": record[4],
        "pools_without_borrow_rate": record[5],
    }


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id not in DATASET_IDS:
        raise DataError(f"unknown dataset: {dataset_id}")
    load_catalog()
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{TABLES[dataset_id]}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id not in DATASET_IDS:
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
        parquet_path = temporary / f"{TABLES[dataset_id]}.parquet"
        connection = duckdb.connect()
        try:
            load_capture(connection, capture_dir, receipt)
            connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection, dataset_id)
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
    dataset_id = receipt["dataset_id"]
    columns = COLUMNS[dataset_id]
    findings: list[str] = []
    checked = ["capture hashes", "required endpoints", "response shape", "unique keys", "value bounds"]
    key = "label, observation_date" if dataset_id == HISTORY_ID else "pool_id"
    rates = "apy < 0 OR apy_base < 0" if dataset_id == HISTORY_ID else "apy_base_borrow < 0 OR total_supply_usd < 0 OR total_borrow_usd < 0"
    connection = duckdb.connect()
    try:
        load_capture(connection, capture_dir, receipt)
        counts = connection.execute(
            f"SELECT COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT {key} FROM rows)), COUNT_IF({rates}) FROM rows"
        ).fetchone()
        labels = ("repeat a key", "have a negative rate or amount")
        findings.extend(f"{failed} rows {label}" for failed, label in zip(counts, labels) if failed)
        summary = summarize(connection, dataset_id)
        if dataset_dir is not None:
            checked.extend(["build hashes", "Parquet rows"])
            try:
                build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
                for item in build_receipt["outputs"]:
                    body = (dataset_dir / item["path"]).read_bytes()
                    if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                        findings.append(f"output hash or size differs: {item['path']}")
                parquet = str(dataset_dir / f"{TABLES[dataset_id]}.parquet")
                names = ", ".join(columns)
                differing = connection.execute(
                    f"""
                    SELECT (SELECT COUNT(*) FROM (SELECT {names} FROM rows EXCEPT ALL SELECT {names} FROM read_parquet(?)))
                         + (SELECT COUNT(*) FROM (SELECT {names} FROM read_parquet(?) EXCEPT ALL SELECT {names} FROM rows))
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
        "dataset_id": dataset_id,
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summary,
        "findings": findings,
    }
