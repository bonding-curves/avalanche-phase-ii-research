"""Validation commitments after Helicon: one row per validation cycle started at or after activation.

Helicon (2026-09-22 15:00 UTC) lowers the minimum validator duration from 14 days to 48 hours (ACP-273) and adds
auto-renewal. An auto-renewed validation keeps its transaction hash while its start and end move forward, so a cycle is
a distinct (transaction_hash, start_time) and the table reads every snapshot run of the validator set, not only the
newest: a cycle that begins and ends between two snapshots of one run is otherwise lost. Each cycle is compared with the
node's previous validator period, from the staking-period log or an earlier snapshot. Rewrite the SQL and the catalog
together: the check compares the Parquet columns with the declared fields and rebuilds the table from the recorded inputs.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from itertools import pairwise
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
from ...domain.protocol import MAINNET, MAINNET_UPGRADES

DATASET_ID = "derived.helicon-commitments"
DATASET_IDS = (DATASET_ID,)
SOURCE_ID = "derived"
TABLE = "helicon-commitments"
# The newest run, or the pinned run, of the staking-period log: every node's history before Helicon.
INPUTS = {"staking-periods": "derived.staking-periods"}
# Every built run of the RPC snapshot under the current catalog contract, oldest first. Each run is one input record
# with the same input_id, so the receipt names and hashes every snapshot the table was built from. Not pinnable.
MANY_INPUTS = {"current-validators": "p-chain-rpc.current-validators"}
OPTIONAL_INPUTS: dict[str, str] = {}

ACTIVATION = MAINNET_UPGRADES.time("helicon").replace(tzinfo=None)
MIN_DURATION_DAYS = MAINNET.helicon_min_stake_duration_seconds / 86_400
# A cycle is lowered when it is shorter than the node's previous period by more than this many days.
LOWERED_THRESHOLD_DAYS = 1
# The pre-Helicon comparison window: validator periods started in these days before activation.
COMPARISON_DAYS = 30
# Half-open [lower, upper) in days, the last bin closed at 365, the protocol maximum.
BINS = (
    ("48h to 7d", MIN_DURATION_DAYS, 7),
    ("7d to 14d", 7, 14),
    ("14d to 30d", 14, 30),
    ("30d to 90d", 30, 90),
    ("90d to 180d", 90, 180),
    ("180d to 365d", 180, 365),
)
OVER_BIN = "over 365d"
UNDER_BIN = "under 48h"
BIN_LABELS = (*(label for label, _, _ in BINS), OVER_BIN)

TABLE_COLUMNS = {
    "node_id": "VARCHAR", "transaction_hash": "VARCHAR", "cycle_start": "TIMESTAMP", "cycle_end": "TIMESTAMP",
    "duration_days": "DOUBLE", "stake_avax": "DOUBLE", "delegation_fee_rate": "DOUBLE", "first_seen_at": "TIMESTAMP",
    "cycle_number": "BIGINT", "auto_renewed": "BOOLEAN", "node_status": "VARCHAR",
    "previous_duration_days": "DOUBLE", "duration_change_days": "DOUBLE", "lowered": "BOOLEAN", "duration_bin": "VARCHAR",
}


def bin_case(days: str) -> str:
    """The duration bin of an expression in days."""
    parts = [f"WHEN {days} < {MIN_DURATION_DAYS} THEN '{UNDER_BIN}'"]
    parts += [f"WHEN {days} < {upper} THEN '{label}'" for label, _, upper in BINS[:-1]]
    parts.append(f"WHEN {days} <= {BINS[-1][2]} THEN '{BINS[-1][0]}'")
    return f"CASE {' '.join(parts)} ELSE '{OVER_BIN}' END"


STAMP = ACTIVATION.isoformat(sep=" ")

# Within one cycle the snapshots agree on end, stake, and fee; the first snapshot's values are kept all the same.
# History is the staking-period log's validator periods plus snapshot cycles the log does not hold (the log ends at its
# capture). The previous period is the node's latest history period that started before the cycle, found by ASOF join.
COMMITMENTS_SQL = f"""
CREATE OR REPLACE TABLE commitments AS
WITH cycles AS (
    SELECT transaction_hash, start_time AS cycle_start,
           arg_min(node_id, observed_at) AS node_id, arg_min(end_time, observed_at) AS cycle_end,
           arg_min(stake_avax, observed_at) AS stake_avax, arg_min(delegation_fee_rate, observed_at) AS delegation_fee_rate,
           min(observed_at) AS first_seen_at
    FROM snapshots GROUP BY transaction_hash, start_time
),
numbered AS (
    SELECT *, row_number() OVER (PARTITION BY transaction_hash ORDER BY cycle_start) AS cycle_number,
           count(*) OVER (PARTITION BY transaction_hash) > 1 AS auto_renewed
    FROM cycles
),
logged AS (
    SELECT transaction_hash, node_id, start_time, end_time FROM periods WHERE role = 'validator'
),
history AS (
    SELECT node_id, start_time, end_time FROM logged
    UNION ALL
    SELECT c.node_id, c.cycle_start, c.cycle_end FROM cycles c
    WHERE NOT EXISTS (SELECT 1 FROM logged l WHERE l.transaction_hash = c.transaction_hash AND l.start_time = c.cycle_start)
),
prior_nodes AS (
    SELECT DISTINCT node_id FROM history WHERE start_time < TIMESTAMP '{STAMP}'
),
compared AS (
    SELECT n.*, date_diff('second', n.cycle_start, n.cycle_end) / 86400.0 AS duration_days,
           r.node_id IS NOT NULL AS was_validator,
           date_diff('second', h.start_time, h.end_time) / 86400.0 AS previous_duration_days
    FROM numbered n
    ASOF LEFT JOIN history h ON n.node_id = h.node_id AND n.cycle_start > h.start_time
    LEFT JOIN prior_nodes r ON r.node_id = n.node_id
    WHERE n.cycle_start >= TIMESTAMP '{STAMP}'
)
SELECT node_id, transaction_hash, cycle_start, cycle_end, duration_days, stake_avax, delegation_fee_rate, first_seen_at,
       cycle_number, auto_renewed,
       CASE WHEN was_validator THEN 'returning' ELSE 'new' END AS node_status,
       previous_duration_days,
       duration_days - previous_duration_days AS duration_change_days,
       duration_days - previous_duration_days < -{LOWERED_THRESHOLD_DAYS} AS lowered,
       {bin_case('duration_days')} AS duration_bin
FROM compared
ORDER BY cycle_start, transaction_hash
"""

# The same history, for the comparison of the COMPARISON_DAYS before activation.
PRIOR_SQL = f"""
WITH cycles AS (SELECT DISTINCT transaction_hash, start_time, end_time FROM snapshots),
logged AS (SELECT transaction_hash, start_time, end_time FROM periods WHERE role = 'validator'),
history AS (
    SELECT start_time, end_time FROM logged
    UNION ALL
    SELECT c.start_time, c.end_time FROM cycles c
    WHERE NOT EXISTS (SELECT 1 FROM logged l WHERE l.transaction_hash = c.transaction_hash AND l.start_time = c.start_time)
)
SELECT {bin_case("date_diff('second', start_time, end_time) / 86400.0")} AS duration_bin, count(*)
FROM history
WHERE start_time >= TIMESTAMP '{STAMP}' - INTERVAL {COMPARISON_DAYS} DAY AND start_time < TIMESTAMP '{STAMP}'
GROUP BY 1
"""

SUMMARY_SQL = f"""
SELECT count(*), count(DISTINCT (transaction_hash, cycle_start)), count(DISTINCT transaction_hash), count(DISTINCT node_id),
       count(DISTINCT node_id) FILTER (WHERE node_status = 'new'), count(DISTINCT node_id) FILTER (WHERE node_status = 'returning'),
       count(*) FILTER (WHERE lowered), count(DISTINCT node_id) FILTER (WHERE lowered),
       count(*) FILTER (WHERE duration_change_days > {LOWERED_THRESHOLD_DAYS}),
       count(DISTINCT transaction_hash) FILTER (WHERE auto_renewed), count(*) FILTER (WHERE cycle_number > 1),
       count(*) FILTER (WHERE duration_days < {MIN_DURATION_DAYS} - 1e-9), count(*) FILTER (WHERE cycle_start < TIMESTAMP '{STAMP}'),
       min(cycle_start), max(first_seen_at)
FROM commitments
"""
SUMMARY_KEYS = (
    "rows", "distinct_cycles", "transactions", "nodes", "new_nodes", "returning_nodes", "lowered_cycles", "lowered_nodes",
    "raised_cycles", "auto_renewed_transactions", "renewal_cycles", "cycles_under_minimum", "cycles_before_activation",
    "first_cycle_start", "last_first_seen_at",
)

# A renewal must start where the transaction's previous cycle ended and carry the next cycle number.
RENEWAL_SQL = """
SELECT count(*) FROM (
    SELECT cycle_start, cycle_number,
           lag(cycle_end) OVER (PARTITION BY transaction_hash ORDER BY cycle_start) AS previous_end,
           lag(cycle_number) OVER (PARTITION BY transaction_hash ORDER BY cycle_start) AS previous_number
    FROM commitments
) WHERE previous_end IS NOT NULL AND (previous_end <> cycle_start OR cycle_number <> previous_number + 1)
"""


def _reject(dataset_id: str) -> None:
    if dataset_id != DATASET_ID:
        raise DataError(f"{dataset_id} is not a derived dataset of this module")


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    _reject(dataset_id)
    raise DataError(f"{DATASET_ID} is built with `avalanche data derive`, not fetched")


def capture(dataset_id: str, output: Path, timeout: float = 20, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    return capture_preview(dataset_id, output, parameters)


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    _reject(dataset_id)
    raise DataError(f"{DATASET_ID} is built with `avalanche data derive`, which writes capture and dataset together")


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    return build_preview(dataset_id, capture_dir, output)


def _describe(input_id: str, dataset_id: str, run: str | None, root: Path | None) -> dict[str, Any]:
    record = datasets.receipt(dataset_id, run, root)
    parquet = datasets.parquet_path(dataset_id, record["run"], root)
    body = parquet.read_bytes()
    return {
        "input_id": input_id, "dataset_id": dataset_id, "run": record["run"],
        "capture_id": record["capture"]["capture_id"], "contract_sha256": record["capture"].get("contract_sha256"),
        "captured_at": record["capture"].get("completed_at"), "rows": record["build"].get("summary", {}).get("rows"),
        "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet,
    }


def select_inputs(pinned: dict[str, str] | None, root: Path | None) -> list[dict[str, Any]]:
    """The staking-period log pinned by ``dataset_id=run`` or its newest run, then every current snapshot run, oldest first."""
    pinned = pinned or {}
    many = sorted(set(pinned) & set(MANY_INPUTS.values()))
    if many:
        raise DataError(f"{DATASET_ID} reads every run of {', '.join(many)}; it cannot be pinned")
    unknown = sorted(set(pinned) - set(INPUTS.values()))
    if unknown:
        raise DataError(f"not an input of {DATASET_ID}: {', '.join(unknown)}")
    selected = [_describe(input_id, dataset_id, pinned.get(dataset_id), root) for input_id, dataset_id in INPUTS.items()]
    catalog = load_catalog()
    for input_id, dataset_id in MANY_INPUTS.items():
        current = contract_hash(catalog, dataset_id)
        described = [_describe(input_id, dataset_id, item["run"], root) for item in datasets.runs(dataset_id, root)]
        described = [item for item in described if item["contract_sha256"] == current]
        if not described:
            raise DataError(f"no built run of {dataset_id} carries the current contract")
        selected.extend(sorted(described, key=lambda item: (item["captured_at"] or "", item["run"])))
    return selected


def as_of_time(inputs: list[dict[str, Any]]) -> str:
    """The newest snapshot capture time: the table holds every cycle observed up to this instant."""
    return max(item["captured_at"] for item in inputs if item["input_id"] in MANY_INPUTS)


def _quoted(path: Path) -> str:
    return str(path).replace("'", "''")


def load_inputs(connection: Any, inputs: list[dict[str, Any]]) -> None:
    connection.execute("SET memory_limit='3GB'")
    periods = next(item for item in inputs if item["input_id"] == "staking-periods")
    connection.execute(f"CREATE OR REPLACE VIEW periods AS SELECT * FROM read_parquet('{_quoted(periods['path'])}')")
    parts = [
        f"SELECT node_id, transaction_hash, start_time, end_time, stake_avax, delegation_fee_rate, observed_at FROM read_parquet('{_quoted(item['path'])}')"
        for item in inputs if item["input_id"] in MANY_INPUTS
    ]
    connection.execute(f"CREATE OR REPLACE VIEW snapshots AS {' UNION ALL '.join(parts)}")


def compute(connection: Any) -> None:
    try:
        connection.execute(COMMITMENTS_SQL)
    except duckdb.Error as error:
        raise DataError(f"Helicon commitment computation failed: {error}") from error


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _bins(rows: list[tuple[str, int]]) -> dict[str, int]:
    counts = dict(rows)
    ordered = {label: counts.pop(label, 0) for label in BIN_LABELS}
    ordered.update(counts)
    return ordered


def summarize(connection: Any) -> dict[str, Any]:
    row = connection.execute(SUMMARY_SQL).fetchone()
    summary = {key: _iso(value) for key, value in zip(SUMMARY_KEYS, row)}
    summary["cycles_by_bin"] = _bins(connection.execute("SELECT duration_bin, count(*) FROM commitments GROUP BY 1").fetchall())
    # A transaction's choice is its first cycle in the table; renewals repeat it.
    summary["transactions_by_bin"] = _bins(connection.execute(
        "SELECT bin, count(*) FROM (SELECT arg_min(duration_bin, cycle_number) AS bin FROM commitments GROUP BY transaction_hash) GROUP BY 1"
    ).fetchall())
    summary["renewal_breaks"] = connection.execute(RENEWAL_SQL).fetchone()[0]
    return summary


def comparison(connection: Any) -> dict[str, Any]:
    """Validator periods started in the COMPARISON_DAYS before activation, by the same bins."""
    bins = _bins(connection.execute(PRIOR_SQL).fetchall())
    start = ACTIVATION - timedelta(days=COMPARISON_DAYS)
    return {"window_start": start.isoformat(), "window_end": ACTIVATION.isoformat(), "periods": sum(bins.values()), "periods_by_bin": bins}


def snapshot_gaps(inputs: list[dict[str, Any]]) -> float | None:
    """The longest wait in hours between consecutive snapshots from the last one before activation on. Above 48 hours a
    minimum-length cycle can start and end unobserved."""
    times = sorted(item["captured_at"] for item in inputs if item["input_id"] in MANY_INPUTS)
    stamp = ACTIVATION.isoformat() + "Z"
    before = [value for value in times if value < stamp]
    times = ([before[-1]] if before else []) + [value for value in times if value >= stamp]
    if len(times) < 2:
        return None
    parsed = [datetime.fromisoformat(value) for value in times]
    return round(max((b - a).total_seconds() for a, b in pairwise(parsed)) / 3600, 2)


def parameters() -> dict[str, Any]:
    return {
        "activation": ACTIVATION.isoformat() + "Z", "min_duration_days": MIN_DURATION_DAYS,
        "lowered_threshold_days": LOWERED_THRESHOLD_DAYS, "comparison_days": COMPARISON_DAYS,
        "bins": {label: [lower, upper] for label, lower, upper in BINS} | {OVER_BIN: [BINS[-1][2], None]},
        "bin_bounds": "each bin includes its lower bound and excludes its upper, except the last closed bin, which includes 365 days",
    }


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    """Build the commitment table into a new run directory holding ``capture/`` and ``dataset/``."""
    _reject(dataset_id)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    inputs = select_inputs(pinned, root)
    completed_at = now()
    as_of = as_of_time(inputs)
    records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records, "as_of": as_of}))
    capture_receipt = {
        "schema_version": "derived-capture/v1",
        "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
        "dataset_id": dataset_id,
        "source_id": SOURCE_ID,
        "completed_at": completed_at,
        "contract_sha256": contract_hash(catalog, dataset_id),
        "tool": f"avalanche-research@{__version__}",
        "inputs": records,
        "as_of": as_of,
        "parameters": parameters(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "capture").mkdir()
        (temporary / "dataset").mkdir()
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet_path = temporary / "dataset" / f"{TABLE}.parquet"
        connection = duckdb.connect()
        try:
            load_inputs(connection, inputs)
            compute(connection)
            connection.execute("COPY commitments TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection)
            summary["snapshots"] = sum(1 for item in inputs if item["input_id"] in MANY_INPUTS)
            summary["max_snapshot_gap_hours"] = snapshot_gaps(inputs)
            summary["before_helicon"] = comparison(connection)
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "derived-build/v1",
            "dataset_id": dataset_id,
            "dataset_schema": definition["fields"],
            "source_capture_id": capture_receipt["capture_id"],
            "completed_at": now(),
            "tool": f"avalanche-research@{__version__}",
            "summary": summary,
            "outputs": [{"path": parquet_path.name, "bytes": parquet_path.stat().st_size, "sha256": sha256(parquet_path.read_bytes())}],
        }
        (temporary / "dataset" / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"capture": capture_receipt, "build": build_receipt}


def read_capture(capture_dir: Path) -> dict[str, Any]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"unreadable capture receipt: {error}") from error
    if receipt.get("schema_version") != "derived-capture/v1" or receipt.get("dataset_id") != DATASET_ID:
        raise DataError(f"not a {DATASET_ID} capture: {capture_dir}")
    return receipt


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """Verify the input runs still hash as recorded, the contract is unchanged, and the build holds: one row per cycle,
    every cycle starts at or after activation and lasts at least the Helicon minimum, every renewal starts where the
    previous cycle ended, and a rebuild from the recorded inputs gives the same rows."""
    if against is not None:
        raise DataError(f"{DATASET_ID} takes no --against directory")
    catalog = load_catalog()
    receipt = read_capture(capture_dir)
    findings: list[str] = []
    checked = ["input run hashes", "catalog contract"]
    if receipt.get("contract_sha256") != contract_hash(catalog, DATASET_ID):
        findings.append("catalog contract changed since the capture")
    root_dir = datasets.RUNS if root is None else root
    inputs: list[dict[str, Any]] = []
    for item in receipt.get("inputs", []):
        parquet = root_dir / item["run"] / "dataset" / item["parquet"]
        if not parquet.is_file():
            findings.append(f"input run missing: {item['run']}")
            continue
        body = parquet.read_bytes()
        if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
            findings.append(f"input run differs from the capture receipt: {item['run']}")
        inputs.append({**item, "path": parquet})
    summary: dict[str, Any] = {"inputs": len(receipt.get("inputs", []))}
    if dataset_dir is not None:
        checked.extend(["build hashes", "one row per cycle", "cycles after activation", "Helicon minimum duration", "renewal continuity", "rebuild from inputs"])
        try:
            build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
            if build_receipt.get("source_capture_id") != receipt.get("capture_id"):
                findings.append("build does not belong to this capture")
            for item in build_receipt["outputs"]:
                body = (dataset_dir / item["path"]).read_bytes()
                if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                    findings.append(f"output hash or size differs: {item['path']}")
            connection = duckdb.connect()
            try:
                connection.execute("SET memory_limit='3GB'")
                parquet = _quoted(dataset_dir / f"{TABLE}.parquet")
                connection.execute(f"CREATE TABLE built AS SELECT * FROM read_parquet('{parquet}')")
                connection.execute("CREATE VIEW commitments AS SELECT * FROM built")
                columns = [row[0] for row in connection.execute("DESCRIBE built").fetchall()]
                if columns != list(TABLE_COLUMNS):
                    findings.append("Parquet columns differ from the declared fields")
                summary.update(summarize(connection))
                if len(inputs) == len(receipt.get("inputs", [])) and inputs:
                    load_inputs(connection, inputs)
                    connection.execute("DROP VIEW commitments")
                    compute(connection)
                    extra, missing = connection.execute(
                        "SELECT (SELECT count(*) FROM (SELECT * FROM built EXCEPT ALL SELECT * FROM commitments)),"
                        " (SELECT count(*) FROM (SELECT * FROM commitments EXCEPT ALL SELECT * FROM built))"
                    ).fetchone()
                    summary.update({"rebuilt_rows": connection.execute("SELECT count(*) FROM commitments").fetchone()[0]})
                    if extra or missing:
                        findings.append(f"the rebuild from the recorded inputs differs: {extra} rows only in the build, {missing} only in the rebuild")
            finally:
                connection.close()
            if summary["rows"] != summary["distinct_cycles"]:
                findings.append(f"{summary['rows'] - summary['distinct_cycles']} cycles appear more than once")
            if summary["cycles_before_activation"]:
                findings.append(f"{summary['cycles_before_activation']} cycles start before activation")
            if summary["cycles_under_minimum"]:
                findings.append(f"{summary['cycles_under_minimum']} cycles are shorter than the Helicon minimum of 48 hours")
            if summary["renewal_breaks"]:
                findings.append(f"{summary['renewal_breaks']} renewals do not start where the previous cycle ended, so a cycle went unobserved")
        except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid dataset output: {error}")
    return {
        "dataset_id": DATASET_ID,
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summary,
        "findings": findings,
    }
