"""The monetary ledger summarized by network upgrade period: the upgrade-period table the validator study reads (M4).

One row per period from genesis to the ledger's last day, each period running from one activation instant to the next.
The daily active-stake-to-supply ratios, validators alone and validators with delegators, and the daily total supply are
observations at each UTC day's close, so a day belongs to the period in force at its close. Issuance is split exactly at
each activation instant from the reward transactions' own times, using the reward run the ledger itself read, so the
periods sum to the ledger's issuance to the wei. Burns are captured by UTC day only, except in narrow windows, so a
day's burns also go to the period in force at its close; the burns of each activation day are reported apart, so their
size is visible.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC
from pathlib import Path
from typing import Any

import duckdb

from . import __version__, datasets
from .catalog import (
    DataError,
    canonical_bytes,
    contract_hash,
    dataset,
    load_catalog,
    now,
    sha256,
)
from .model.protocol import MAINNET_UPGRADES

DATASET_ID = "derived.monetary-periods"
DATASET_IDS = (DATASET_ID,)
SOURCE_ID = "derived"
TABLE = "monetary-periods"
GENESIS = "2020-09-10 00:00:00"
TABLE_COLUMNS = {
    "regime": "VARCHAR", "starts_at": "TIMESTAMP", "ends_at": "TIMESTAMP", "days_observed": "INTEGER", "days_in_period": "INTEGER",
    "mean_validator_ratio": "DOUBLE", "median_validator_ratio": "DOUBLE", "mean_combined_ratio": "DOUBLE", "median_combined_ratio": "DOUBLE",
    "mean_total_supply_avax": "DOUBLE", "issued_avax": "DOUBLE", "burned_p_avax": "DOUBLE", "burned_x_avax": "DOUBLE",
    "burned_c_evm_avax": "DOUBLE", "burned_c_atomic_avax": "DOUBLE", "burned_avax": "DOUBLE", "activation_day_burned_avax": "DOUBLE",
}


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    raise DataError(f"{dataset_id} is derived; use `avalanche data derive`")


capture = build_preview = build = capture_preview


def periods() -> list[tuple[str, str]]:
    """(regime, start) from genesis through every upgrade, as naive UTC text."""
    return [("genesis", GENESIS)] + [(item.name, item.activated_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")) for item in MAINNET_UPGRADES.upgrades]


def _inputs(pinned: dict[str, str] | None, root: Path | None) -> list[dict[str, Any]]:
    """The ledger, and the reward run it recorded reading."""
    pinned = pinned or {}
    if set(pinned) - {"derived.avax-monetary-daily"}:
        raise DataError(f"the only pinnable input of {DATASET_ID} is derived.avax-monetary-daily")
    ledger = datasets.receipt("derived.avax-monetary-daily", pinned.get("derived.avax-monetary-daily"), root)
    rewards = next(item for item in ledger["capture"]["inputs"] if item["input_id"] == "staking-rewards")
    selected = []
    for input_id, dataset_id, run in (("ledger", "derived.avax-monetary-daily", ledger["run"]), ("rewards", rewards["dataset_id"], rewards["run"])):
        parquet = datasets.parquet_path(dataset_id, run, root)
        body = parquet.read_bytes()
        record = datasets.receipt(dataset_id, run, root)
        selected.append({"input_id": input_id, "dataset_id": dataset_id, "run": run, "capture_id": record["capture"]["capture_id"],
                         "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet})
    if selected[1]["sha256"] != rewards["sha256"]:
        raise DataError(f"the reward run {rewards['run']} changed since the ledger read it")
    return selected


def compute(inputs: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    paths = {item["input_id"]: str(item["path"]).replace("'", "''") for item in inputs}
    connection = duckdb.connect()
    try:
        connection.execute(f"CREATE VIEW ledger AS SELECT * FROM read_parquet('{paths['ledger']}')")
        connection.execute(f"CREATE VIEW rewards AS SELECT * FROM read_parquet('{paths['rewards']}')")
        connection.execute("CREATE TABLE starts(regime VARCHAR, starts_at TIMESTAMP)")
        connection.executemany("INSERT INTO starts VALUES (?, ?)", periods())
        last = connection.execute("SELECT max(date_utc) + INTERVAL 1 DAY FROM ledger").fetchone()[0]
        return connection.execute(f"""
            WITH bounds AS (
                SELECT regime, starts_at, coalesce(lead(starts_at) OVER (ORDER BY starts_at), TIMESTAMP '{last}') AS ends_at FROM starts
                WHERE starts_at < TIMESTAMP '{last}'),
            days AS (
                SELECT l.*, b.regime, b.starts_at, (l.date_utc + INTERVAL 1 DAY)::TIMESTAMP AS closes_at,
                       l.active_validator_stake_wei / l.total_supply_close_wei AS validator_ratio,
                       (l.active_validator_stake_wei + l.active_delegated_stake_wei) / l.total_supply_close_wei AS combined_ratio
                FROM ledger l ASOF JOIN bounds b ON (l.date_utc + INTERVAL 1 DAY)::TIMESTAMP > b.starts_at),
            issued AS (
                SELECT b.regime, sum(r.realized_reward_navax)::DOUBLE / 1e9 AS issued_avax
                FROM rewards r JOIN bounds b ON r.rewarded_at >= b.starts_at AND r.rewarded_at < b.ends_at
                WHERE r.rewarded_at < TIMESTAMP '{last}' GROUP BY 1)
            SELECT b.regime, b.starts_at, b.ends_at, count(d.date_utc)::INTEGER,
                   date_diff('day', b.starts_at::DATE, b.ends_at::DATE)::INTEGER,
                   avg(d.validator_ratio::DOUBLE), median(d.validator_ratio::DOUBLE), avg(d.combined_ratio::DOUBLE), median(d.combined_ratio::DOUBLE),
                   avg(d.total_supply_close_wei::DOUBLE) / 1e18, coalesce(any_value(i.issued_avax), 0),
                   coalesce(sum(d.burned_p_wei), 0)::DOUBLE / 1e18, coalesce(sum(d.burned_x_wei), 0)::DOUBLE / 1e18,
                   coalesce(sum(d.burned_c_evm_wei + d.burned_c_evm_gap_wei), 0)::DOUBLE / 1e18, coalesce(sum(d.burned_c_atomic_wei), 0)::DOUBLE / 1e18,
                   coalesce(sum(d.burned_wei), 0)::DOUBLE / 1e18,
                   coalesce(sum(d.burned_wei) FILTER (WHERE d.date_utc = b.starts_at::DATE AND b.starts_at <> b.starts_at::DATE::TIMESTAMP), 0)::DOUBLE / 1e18
            FROM bounds b LEFT JOIN days d USING (regime) LEFT JOIN issued i USING (regime)
            GROUP BY b.regime, b.starts_at, b.ends_at ORDER BY b.starts_at""").fetchall()
    finally:
        connection.close()


def _totals(inputs: list[dict[str, Any]]) -> tuple[float, float]:
    """The ledger's own issuance and burn over all its days, in AVAX."""
    path = str(next(item["path"] for item in inputs if item["input_id"] == "ledger")).replace("'", "''")
    connection = duckdb.connect()
    try:
        return connection.execute(f"SELECT sum(issued_rewards_wei)::DOUBLE / 1e18, sum(burned_wei)::DOUBLE / 1e18 FROM read_parquet('{path}')").fetchone()
    finally:
        connection.close()


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    inputs = _inputs(pinned, root)
    rows = compute(inputs)
    issued, burned = _totals(inputs)
    completed_at = now()
    records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records}))
    capture_receipt = {
        "schema_version": "derived-capture/v1", "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}", "dataset_id": DATASET_ID,
        "source_id": SOURCE_ID, "completed_at": completed_at, "contract_sha256": contract_hash(catalog, DATASET_ID),
        "tool": f"avalanche-research@{__version__}", "inputs": records,
        "parameters": {"periods": periods(), "stock_rule": "a day's close-of-day observations belong to the period in force at its close",
                       "issuance_rule": "reward transactions split at the activation instant", "burn_rule": "a day's burns belong to the period in force at its close"},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "capture").mkdir()
        (temporary / "dataset").mkdir()
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet = temporary / "dataset" / f"{TABLE}.parquet"
        connection = duckdb.connect()
        try:
            connection.execute(f"CREATE TABLE rows({', '.join(f'{name} {kind}' for name, kind in TABLE_COLUMNS.items())})")
            connection.executemany(f"INSERT INTO rows VALUES ({', '.join('?' for _ in TABLE_COLUMNS)})", rows)
            connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "derived-build/v1", "dataset_id": DATASET_ID, "dataset_schema": dataset(catalog, DATASET_ID)["fields"],
            "source_capture_id": capture_receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": {"rows": len(rows), "issued_avax": sum(row[10] for row in rows), "ledger_issued_avax": issued,
                        "burned_avax": sum(row[15] for row in rows), "ledger_burned_avax": burned,
                        "periods_missing_days": [row[0] for row in rows if row[3] != row[4]]},
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "dataset" / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"capture": capture_receipt, "build": build_receipt}


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """Inputs unchanged, a rebuild equal, and the periods' issuance and burns summing to the ledger's."""
    if against is not None:
        raise DataError(f"{DATASET_ID} takes no --against directory")
    receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    if receipt.get("dataset_id") != DATASET_ID:
        raise DataError(f"not a {DATASET_ID} capture: {capture_dir}")
    findings: list[str] = []
    root_dir = datasets.RUNS if root is None else root
    inputs = []
    for item in receipt["inputs"]:
        parquet = root_dir / item["run"] / "dataset" / item["parquet"]
        if not parquet.is_file() or sha256(parquet.read_bytes()) != item["sha256"]:
            findings.append(f"input run missing or changed: {item['run']}")
        inputs.append({**item, "path": parquet})
    summary: dict[str, Any] = {}
    if dataset_dir is not None and not findings:
        built = duckdb.connect().execute("SELECT * FROM read_parquet(?) ORDER BY starts_at", [str(dataset_dir / f"{TABLE}.parquet")]).fetchall()
        if [tuple(map(str, row)) for row in built] != [tuple(map(str, row)) for row in compute(inputs)]:
            findings.append("a rebuild from the recorded inputs differs")
        issued, burned = _totals(inputs)
        summary = {"rows": len(built), "issued_avax": sum(row[10] for row in built), "ledger_issued_avax": issued,
                   "burned_avax": sum(row[15] for row in built), "ledger_burned_avax": burned}
        if abs(summary["issued_avax"] - issued) > 1e-6 * max(issued, 1) or abs(summary["burned_avax"] - burned) > 1e-6 * max(burned, 1):
            findings.append("the periods' issuance or burns do not sum to the ledger's")
    return {"dataset_id": DATASET_ID, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": ["input run hashes", "rebuild from inputs", "period sums equal the ledger"], "summary": summary, "findings": findings}
