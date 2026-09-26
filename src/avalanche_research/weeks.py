"""The validator-week panel and the observed delegations it is read against, derived from the staking-period log.

``derived.validator-weeks`` has one row per Primary Network validator node per UTC week, Monday 00:00 to the next
Monday, for every week the node is validating at the Monday cutoff or first starts to validate during it. Every
feature is computed from staking transactions accepted before the cutoff, so a row never changes when later events are
appended: the check rebuilds the early weeks from truncated inputs and compares them. Outcomes are the delegations
accepted during the week, counted with and without the one address that made 93% of all delegations.

``derived.observed-delegations`` has one row per delegation accepted in the window, with its exact duration, its
week, and whether its validator was on offer at that week's cutoff. No delegation is dropped: one whose validator has no
row in its week is flagged, and the panel's summary counts it.

The window, the concentrated address, and the protocol limits are parameters in the capture receipt.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from . import __version__, datasets
from .catalog import DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256

WEEKS_ID = "derived.validator-weeks"
DELEGATIONS_ID = "derived.observed-delegations"
DATASET_IDS = (WEEKS_ID, DELEGATIONS_ID)
SOURCE_ID = "derived"
TABLES = {WEEKS_ID: "validator-weeks", DELEGATIONS_ID: "observed-delegations"}
INPUTS = {
    "staking-periods": "derived.staking-periods",
    "validator-stakes": "snowflake.primary-validator-stakes",
    "delegator-stakes": "snowflake.primary-delegator-stakes",
}
# The pre-Helicon window of decision SD10: the first Monday week holding a captured delegation to the last full week
# before Helicon activated on 2026-09-22 15:00 UTC.
WINDOW_START = "2020-09-21"
WINDOW_END = "2026-09-21"
# The one address behind 93% of delegation events (node table NK2); its stratum is decision SD8. Not named as an operator.
CONCENTRATED_ADDRESS = "avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy"
# AvalancheGo e9a8b75: MaxValidatorWeightFactor 5 (proposal_tx_executor.go:32), MaxValidatorStake 3M AVAX and
# MinDelegatorStake 25 AVAX (genesis_mainnet.go:57-58), MinStakeDuration two weeks (line 60, before Helicon).
WEIGHT_FACTOR = 5
MAX_WEIGHT_AVAX = 3_000_000
MIN_DELEGATION_AVAX = 25
MIN_DURATION_DAYS = 14
SECONDS_PER_WEEK = 604_800
# A row of the check's rebuild from inputs truncated here must equal the full build's row.
INVARIANCE_CUTOFF = "2025-01-06"

WEEK_COLUMNS = {
    "node_id": "VARCHAR", "week_start_utc": "TIMESTAMP", "active_at_week_start": "BOOLEAN", "offered_at_week_start": "BOOLEAN",
    "validator_transaction_hash": "VARCHAR", "period_start": "TIMESTAMP", "period_end": "TIMESTAMP", "days_remaining": "DOUBLE",
    "self_stake_avax": "DOUBLE", "delegation_fee_rate": "DOUBLE",
    "first_start_known": "TIMESTAMP", "node_age_weeks": "DOUBLE", "days_staked_weeks": "DOUBLE",
    "completed_periods": "BIGINT", "started_periods": "BIGINT", "reward_address_asof": "VARCHAR",
    "delegated_avax_at_week_start": "DOUBLE", "max_delegated_avax_14d": "DOUBLE", "max_weight_avax": "DOUBLE",
    "capacity_left_avax": "DOUBLE", "capacity_left_avax_14d": "DOUBLE",
    "delegations_all": "BIGINT", "delegated_avax_all": "DOUBLE", "delegations_excl_concentrated": "BIGINT", "delegated_avax_excl_concentrated": "DOUBLE",
}
DELEGATION_COLUMNS = {
    "transaction_hash": "VARCHAR", "node_id": "VARCHAR", "validator_transaction_hash": "VARCHAR", "delegator_address": "VARCHAR",
    "concentrated_address": "BOOLEAN", "accepted_at": "TIMESTAMP", "week_start_utc": "TIMESTAMP",
    "start_time": "TIMESTAMP", "end_time": "TIMESTAMP", "duration_seconds": "BIGINT", "duration_weeks": "DOUBLE",
    "stake_avax": "DOUBLE", "node_week_row": "BOOLEAN", "validator_offered_at_week_start": "BOOLEAN", "not_in_week_start_risk_set": "BOOLEAN",
}

# Every feature of week w reads only transactions accepted before w. A period starts no earlier than its acceptance, so
# a period started before w was accepted before it; the SQL states both conditions so the rule reads off the query.
PANEL_SQL = f"""
CREATE OR REPLACE TABLE weeks AS
SELECT unnest(generate_series(TIMESTAMP '{{window_start}}', TIMESTAMP '{{window_end}}' - INTERVAL 7 DAY, INTERVAL 7 DAY)) AS week_start_utc;

CREATE OR REPLACE TABLE v AS
SELECT p.node_id, p.transaction_hash, p.accepted_at, p.start_time, p.end_time, p.stake_navax, p.delegation_fee_rate, s.reward_address
FROM periods p LEFT JOIN validators s USING (transaction_hash)
WHERE p.role = 'validator' AND p.accepted_at < TIMESTAMP '{{known_until}}';

CREATE OR REPLACE TABLE d AS
SELECT p.transaction_hash, p.node_id, p.validator_transaction_hash, s.delegator_address, p.accepted_at, p.start_time, p.end_time, p.stake_navax
FROM periods p LEFT JOIN delegators s USING (transaction_hash)
WHERE p.role = 'delegator' AND p.accepted_at < TIMESTAMP '{{known_until}}';

-- Disjoint validating intervals per node: a period overlapping an earlier one extends it.
CREATE OR REPLACE TABLE islands AS
WITH ordered AS (
    SELECT node_id, start_time, end_time,
           max(end_time) OVER (PARTITION BY node_id ORDER BY start_time, transaction_hash ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prior_end
    FROM v
), numbered AS (
    SELECT *, sum(CASE WHEN prior_end IS NULL OR start_time > prior_end THEN 1 ELSE 0 END) OVER (PARTITION BY node_id ORDER BY start_time, end_time) AS island
    FROM ordered
)
SELECT node_id, island, min(start_time) AS island_start, max(end_time) AS island_end FROM numbered GROUP BY node_id, island;

-- Rows: validating at the cutoff, or starting a period during the week without validating at the cutoff.
CREATE OR REPLACE TABLE active AS
SELECT w.week_start_utc, v.node_id,
       arg_max(v.transaction_hash, v.start_time) AS validator_transaction_hash,
       max(v.start_time) AS period_start, arg_max(v.end_time, v.start_time) AS period_end,
       arg_max(v.stake_navax, v.start_time) AS stake_navax, arg_max(v.delegation_fee_rate, v.start_time) AS delegation_fee_rate
FROM weeks w JOIN v ON v.accepted_at < w.week_start_utc AND v.start_time < w.week_start_utc AND v.end_time > w.week_start_utc
GROUP BY 1, 2;

CREATE OR REPLACE TABLE keys AS
SELECT week_start_utc, node_id, TRUE AS active_at_week_start FROM active
UNION ALL
SELECT DISTINCT w.week_start_utc, v.node_id, FALSE
FROM weeks w JOIN v ON v.start_time >= w.week_start_utc AND v.start_time < w.week_start_utc + INTERVAL 7 DAY
WHERE NOT EXISTS (SELECT 1 FROM active a WHERE a.week_start_utc = w.week_start_utc AND a.node_id = v.node_id);

CREATE OR REPLACE TABLE history AS
SELECT k.week_start_utc, k.node_id,
       min(v.start_time) FILTER (WHERE v.start_time < k.week_start_utc) AS first_start_known,
       count(*) FILTER (WHERE v.end_time <= k.week_start_utc) AS completed_periods,
       count(*) FILTER (WHERE v.start_time < k.week_start_utc) AS started_periods,
       arg_max(v.reward_address, v.accepted_at) AS reward_address_asof
FROM keys k LEFT JOIN v ON v.node_id = k.node_id AND v.accepted_at < k.week_start_utc
GROUP BY 1, 2;

CREATE OR REPLACE TABLE staked AS
SELECT k.week_start_utc, k.node_id,
       coalesce(sum(epoch(least(i.island_end, k.week_start_utc) - i.island_start)), 0) / {SECONDS_PER_WEEK} AS days_staked_weeks
FROM keys k LEFT JOIN islands i ON i.node_id = k.node_id AND i.island_start < k.week_start_utc
GROUP BY 1, 2;

-- Delegated weight on the cutoff's validation, known at the cutoff: at the cutoff and at every scheduled start within
-- the next fourteen days, the shortest delegation a new delegator could make.
CREATE OR REPLACE TABLE known_d AS
SELECT a.week_start_utc, a.node_id, d.start_time, d.end_time, d.stake_navax
FROM active a JOIN d ON d.validator_transaction_hash = a.validator_transaction_hash AND d.accepted_at < a.week_start_utc
WHERE d.end_time > a.week_start_utc AND d.start_time < a.week_start_utc + INTERVAL {MIN_DURATION_DAYS} DAY;

CREATE OR REPLACE TABLE points AS
SELECT week_start_utc, node_id, week_start_utc AS point FROM active
UNION
SELECT week_start_utc, node_id, start_time FROM known_d WHERE start_time > week_start_utc;

CREATE OR REPLACE TABLE weight AS
SELECT p.week_start_utc, p.node_id, p.point, coalesce(sum(k.stake_navax), 0) AS delegated_navax
FROM points p LEFT JOIN known_d k ON k.week_start_utc = p.week_start_utc AND k.node_id = p.node_id AND k.start_time <= p.point AND k.end_time > p.point
GROUP BY 1, 2, 3;

CREATE OR REPLACE TABLE capacity AS
SELECT week_start_utc, node_id,
       max(delegated_navax) FILTER (WHERE point = week_start_utc) / 1e9 AS delegated_avax_at_week_start,
       max(delegated_navax) / 1e9 AS max_delegated_avax_14d
FROM weight GROUP BY 1, 2;

CREATE OR REPLACE TABLE outcomes AS
SELECT k.week_start_utc, k.node_id,
       count(d.transaction_hash) AS delegations_all, coalesce(sum(d.stake_navax), 0) / 1e9 AS delegated_avax_all,
       count(d.transaction_hash) FILTER (WHERE d.delegator_address IS DISTINCT FROM '{CONCENTRATED_ADDRESS}') AS delegations_excl_concentrated,
       coalesce(sum(d.stake_navax) FILTER (WHERE d.delegator_address IS DISTINCT FROM '{CONCENTRATED_ADDRESS}'), 0) / 1e9 AS delegated_avax_excl_concentrated
FROM keys k LEFT JOIN d ON d.node_id = k.node_id AND d.accepted_at >= k.week_start_utc AND d.accepted_at < k.week_start_utc + INTERVAL 7 DAY
GROUP BY 1, 2;

CREATE OR REPLACE TABLE panel AS
SELECT k.node_id, k.week_start_utc, k.active_at_week_start,
       coalesce(k.active_at_week_start AND epoch(a.period_end - k.week_start_utc) >= {MIN_DURATION_DAYS} * 86400
                AND least({WEIGHT_FACTOR} * a.stake_navax / 1e9, {MAX_WEIGHT_AVAX}) - a.stake_navax / 1e9 - c.max_delegated_avax_14d >= {MIN_DELEGATION_AVAX}, FALSE) AS offered_at_week_start,
       a.validator_transaction_hash, a.period_start, a.period_end, epoch(a.period_end - k.week_start_utc) / 86400 AS days_remaining,
       a.stake_navax / 1e9 AS self_stake_avax, a.delegation_fee_rate,
       h.first_start_known, epoch(k.week_start_utc - h.first_start_known) / {SECONDS_PER_WEEK} AS node_age_weeks, s.days_staked_weeks,
       h.completed_periods, h.started_periods, h.reward_address_asof,
       c.delegated_avax_at_week_start, c.max_delegated_avax_14d,
       least({WEIGHT_FACTOR} * a.stake_navax / 1e9, {MAX_WEIGHT_AVAX}) AS max_weight_avax,
       least({WEIGHT_FACTOR} * a.stake_navax / 1e9, {MAX_WEIGHT_AVAX}) - a.stake_navax / 1e9 - c.delegated_avax_at_week_start AS capacity_left_avax,
       least({WEIGHT_FACTOR} * a.stake_navax / 1e9, {MAX_WEIGHT_AVAX}) - a.stake_navax / 1e9 - c.max_delegated_avax_14d AS capacity_left_avax_14d,
       o.delegations_all, o.delegated_avax_all, o.delegations_excl_concentrated, o.delegated_avax_excl_concentrated
FROM keys k
LEFT JOIN active a USING (week_start_utc, node_id)
JOIN history h USING (week_start_utc, node_id)
JOIN staked s USING (week_start_utc, node_id)
LEFT JOIN capacity c USING (week_start_utc, node_id)
JOIN outcomes o USING (week_start_utc, node_id)
ORDER BY k.week_start_utc, k.node_id;

CREATE OR REPLACE TABLE observed AS
SELECT d.transaction_hash, d.node_id, d.validator_transaction_hash, d.delegator_address,
       d.delegator_address IS NOT DISTINCT FROM '{CONCENTRATED_ADDRESS}' AS concentrated_address,
       d.accepted_at, date_trunc('week', d.accepted_at) AS week_start_utc, d.start_time, d.end_time,
       epoch(d.end_time - d.start_time)::BIGINT AS duration_seconds, epoch(d.end_time - d.start_time) / {SECONDS_PER_WEEK} AS duration_weeks,
       d.stake_navax / 1e9 AS stake_avax,
       p.node_id IS NOT NULL AS node_week_row, coalesce(p.offered_at_week_start, FALSE) AS validator_offered_at_week_start,
       NOT coalesce(p.offered_at_week_start, FALSE) AS not_in_week_start_risk_set
FROM d LEFT JOIN panel p ON p.node_id = d.node_id AND p.week_start_utc = date_trunc('week', d.accepted_at)
WHERE d.accepted_at >= TIMESTAMP '{{window_start}}' AND d.accepted_at < TIMESTAMP '{{window_end}}'
ORDER BY d.accepted_at, d.transaction_hash;
"""

SUMMARY_SQL = """
SELECT (SELECT count(*) FROM panel), (SELECT count(DISTINCT (node_id, week_start_utc)) FROM panel), (SELECT count(DISTINCT node_id) FROM panel),
       (SELECT count(DISTINCT week_start_utc) FROM panel), (SELECT count(*) FILTER (WHERE active_at_week_start) FROM panel),
       (SELECT count(*) FILTER (WHERE offered_at_week_start) FROM panel),
       (SELECT count(*) FROM observed), (SELECT count(*) FILTER (WHERE node_week_row) FROM observed),
       (SELECT count(*) FILTER (WHERE not_in_week_start_risk_set) FROM observed),
       (SELECT coalesce(sum(delegations_all), 0) FROM panel),
       (SELECT round(coalesce(sum(stake_avax), 0), 6) FROM observed),
       (SELECT count(*) FILTER (WHERE concentrated_address) FROM observed),
       (SELECT round(coalesce(sum(stake_avax) FILTER (WHERE concentrated_address), 0), 6) FROM observed)
"""
SUMMARY_KEYS = ("rows", "distinct_keys", "nodes", "weeks", "active_rows", "offered_rows", "delegations", "delegations_with_row",
                "delegations_not_in_week_start_risk_set", "panel_delegations", "delegated_avax", "concentrated_delegations", "concentrated_avax")


def _reject(dataset_id: str) -> None:
    if dataset_id not in DATASET_IDS:
        raise DataError(f"{dataset_id} is not a derived dataset of this module")


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    _reject(dataset_id)
    raise DataError(f"{dataset_id} is built with `avalanche data derive`, not fetched")


def capture(dataset_id: str, output: Path, timeout: float = 20, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    return capture_preview(dataset_id, output, parameters)


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    _reject(dataset_id)
    raise DataError(f"{dataset_id} is built with `avalanche data derive`, which writes capture and dataset together")


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    return build_preview(dataset_id, capture_dir, output)


def select_inputs(dataset_id: str, pinned: dict[str, str] | None, root: Path | None) -> list[dict[str, Any]]:
    pinned = pinned or {}
    unknown = sorted(set(pinned) - set(INPUTS.values()))
    if unknown:
        raise DataError(f"not an input of {dataset_id}: {', '.join(unknown)}")
    selected = []
    for input_id, input_dataset in INPUTS.items():
        run = pinned.get(input_dataset)
        record = datasets.receipt(input_dataset, run, root)
        parquet = datasets.parquet_path(input_dataset, run, root)
        body = parquet.read_bytes()
        selected.append({
            "input_id": input_id, "dataset_id": input_dataset, "run": record["run"], "capture_id": record["capture"]["capture_id"],
            "contract_sha256": record["capture"].get("contract_sha256"), "captured_at": record["capture"].get("completed_at"),
            "rows": record["build"].get("summary", {}).get("rows"), "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet,
        })
    return selected


def load_inputs(connection: Any, paths: dict[str, Path]) -> None:
    names = {"staking-periods": "periods", "validator-stakes": "validators", "delegator-stakes": "delegators"}
    for input_id, path in paths.items():
        connection.execute(f"CREATE OR REPLACE VIEW {names[input_id]} AS SELECT * FROM read_parquet('{str(path).replace(chr(39), chr(39) * 2)}')")


def compute(connection: Any, window_start: str = WINDOW_START, window_end: str = WINDOW_END, known_until: str | None = None) -> None:
    """Build ``panel`` and ``observed`` from the input views. ``known_until`` drops every transaction accepted from then on,
    which is how the check proves that earlier rows do not depend on later events."""
    sql = PANEL_SQL.format(window_start=window_start, window_end=window_end, known_until=known_until or window_end)
    try:
        for statement in [item.strip() for item in sql.split(";") if item.strip()]:
            connection.execute(statement)
    except duckdb.Error as error:
        raise DataError(f"validator-week computation failed: {error}") from error


def summarize(connection: Any) -> dict[str, Any]:
    return {key: (float(value) if key.endswith("avax") else value) for key, value in zip(SUMMARY_KEYS, connection.execute(SUMMARY_SQL).fetchone())}


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    """Build one of the two tables into a new run directory holding ``capture/`` and ``dataset/``."""
    _reject(dataset_id)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    inputs = select_inputs(dataset_id, pinned, root)
    completed_at = now()
    records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    parameters = {"window_start": WINDOW_START, "window_end": WINDOW_END, "concentrated_address": CONCENTRATED_ADDRESS,
                  "weight_factor": WEIGHT_FACTOR, "max_weight_avax": MAX_WEIGHT_AVAX, "min_delegation_avax": MIN_DELEGATION_AVAX,
                  "min_duration_days": MIN_DURATION_DAYS, "invariance_cutoff": INVARIANCE_CUTOFF}
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records, "parameters": parameters}))
    capture_receipt = {
        "schema_version": "derived-capture/v1", "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
        "dataset_id": dataset_id, "source_id": SOURCE_ID, "completed_at": completed_at,
        "contract_sha256": contract_hash(catalog, dataset_id), "tool": f"avalanche-research@{__version__}",
        "inputs": records, "parameters": parameters,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "capture").mkdir()
        (temporary / "dataset").mkdir()
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet_path = temporary / "dataset" / f"{TABLES[dataset_id]}.parquet"
        connection = duckdb.connect()
        try:
            load_inputs(connection, {item["input_id"]: item["path"] for item in inputs})
            compute(connection)
            table = "panel" if dataset_id == WEEKS_ID else "observed"
            connection.execute(f"COPY {table} TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection)
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "derived-build/v1", "dataset_id": dataset_id, "dataset_schema": definition["fields"],
            "source_capture_id": capture_receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
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
    if receipt.get("schema_version") != "derived-capture/v1" or receipt.get("dataset_id") not in DATASET_IDS:
        raise DataError(f"not a validator-week capture: {capture_dir}")
    return receipt


def invariance(paths: dict[str, Path], cutoff: str = INVARIANCE_CUTOFF) -> dict[str, Any]:
    """Rows for weeks before ``cutoff`` built from every input against the same rows built from transactions accepted
    before ``cutoff`` only. No row in either set and not the other proves no early row reads a later event."""
    connection = duckdb.connect()
    try:
        load_inputs(connection, paths)
        compute(connection)
        connection.execute("ALTER TABLE panel RENAME TO panel_full")
        compute(connection, known_until=cutoff)
        early = f"week_start_utc < TIMESTAMP '{cutoff}'"
        rows, only_full, only_truncated = connection.execute(f"""
            SELECT (SELECT count(*) FROM panel_full WHERE {early}),
                   (SELECT count(*) FROM (SELECT * FROM panel_full WHERE {early} EXCEPT ALL SELECT * FROM panel WHERE {early})),
                   (SELECT count(*) FROM (SELECT * FROM panel WHERE {early} EXCEPT ALL SELECT * FROM panel_full WHERE {early}))
        """).fetchone()
    finally:
        connection.close()
    return {"cutoff": cutoff, "rows": int(rows), "rows_only_in_full": int(only_full), "rows_only_in_truncated": int(only_truncated),
            "equal": only_full == 0 and only_truncated == 0}


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """Input hashes, the contract, the columns, one row per key, every delegation accounted for, and the append-future
    rule: early rows rebuilt from truncated inputs equal the full build's."""
    if against is not None:
        raise DataError("the validator-week tables take no --against directory")
    catalog = load_catalog()
    receipt = read_capture(capture_dir)
    dataset_id = receipt["dataset_id"]
    findings: list[str] = []
    checked = ["input run hashes", "catalog contract"]
    if receipt.get("contract_sha256") != contract_hash(catalog, dataset_id):
        findings.append("catalog contract changed since the capture")
    root_dir = datasets.RUNS if root is None else root
    paths: dict[str, Path] = {}
    for item in receipt.get("inputs", []):
        parquet = root_dir / item["run"] / "dataset" / item["parquet"]
        if not parquet.is_file():
            findings.append(f"input run missing: {item['run']}")
            continue
        body = parquet.read_bytes()
        if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
            findings.append(f"input run differs from the capture receipt: {item['run']}")
        paths[item["input_id"]] = parquet
    summary: dict[str, Any] = {"inputs": len(receipt.get("inputs", []))}
    if dataset_dir is not None:
        checked.extend(["build hashes", "columns", "one row per key", "every delegation accounted for"])
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
                parquet = str(dataset_dir / f"{TABLES[dataset_id]}.parquet").replace("'", "''")
                connection.execute(f"CREATE VIEW built AS SELECT * FROM read_parquet('{parquet}')")
                columns = [row[0] for row in connection.execute("DESCRIBE built").fetchall()]
                expected = WEEK_COLUMNS if dataset_id == WEEKS_ID else DELEGATION_COLUMNS
                if columns != list(expected):
                    findings.append("Parquet columns differ from the declared fields")
                key = "node_id, week_start_utc" if dataset_id == WEEKS_ID else "transaction_hash"
                rows, keys = connection.execute(f"SELECT count(*), count(DISTINCT ({key})) FROM built").fetchone()
                summary.update({"rows": rows, "distinct_keys": keys})
                if rows != keys:
                    findings.append(f"{rows - keys} rows repeat a key")
            finally:
                connection.close()
            built = build_receipt["summary"]
            summary.update({name: built[name] for name in SUMMARY_KEYS if name in built})
            if built["panel_delegations"] != built["delegations_with_row"]:
                findings.append(f"the panel's outcomes count {built['panel_delegations']} delegations, the rows own {built['delegations_with_row']}")
            summary["delegations_without_row"] = built["delegations"] - built["delegations_with_row"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid dataset output: {error}")
    if dataset_id == WEEKS_ID and len(paths) == len(INPUTS):
        checked.append("rows before the invariance cutoff do not read later events")
        result = invariance(paths, receipt.get("parameters", {}).get("invariance_cutoff", INVARIANCE_CUTOFF))
        summary["invariance"] = result
        if not result["equal"]:
            findings.append(f"rows before {result['cutoff']} change when later events are added")
    return {"dataset_id": dataset_id, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}
