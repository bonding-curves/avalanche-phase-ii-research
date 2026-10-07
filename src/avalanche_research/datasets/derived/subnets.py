"""Subnet and L1 validation by node: one row per node and Subnet, with the Subnet's L1 conversion.

Before Etna (2024-12-16 17:00 UTC) a Subnet validator had to be a Primary Network validator for its whole Subnet period.
ACP-77 at Etna let a Subnet convert to an L1, whose validators need not validate the Primary Network. The table joins the
P-Chain's Subnet and L1 validator transactions to each node's Primary Network span, so the fall in active validators after
Etna can be split by whether a node validated a Subnet and when that Subnet converted. The build summary reproduces the
exploratory counts of the protocol mechanism catalog (finding F2 to F5) from these recorded inputs. Rewrite the SQL and the
catalog together: the check compares the Parquet columns with the declared fields and rebuilds the table from the inputs.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
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
from ...domain.protocol import MAINNET_UPGRADES

DATASET_ID = "derived.subnet-validation"
DATASET_IDS = (DATASET_ID,)
SOURCE_ID = "derived"
TABLE = "subnet-validation"
INPUTS = {
    "subnet-transactions": "snowflake.subnet-validator-transactions",
    "staking-periods": "derived.staking-periods",
}
OPTIONAL_INPUTS: dict[str, str] = {}

ETNA = MAINNET_UPGRADES.time("etna").replace(tzinfo=None)
ETNA_STAMP = ETNA.isoformat(sep=" ")

TABLE_COLUMNS = {
    "node_id": "VARCHAR", "subnet_id": "VARCHAR",
    "subnet_periods": "BIGINT", "first_subnet_start": "TIMESTAMP", "last_subnet_end": "TIMESTAMP",
    "removed_early": "BIGINT", "l1_converted_at": "TIMESTAMP", "initial_l1_validator": "BOOLEAN",
    "l1_registered_at": "TIMESTAMP", "l1_disabled_at": "TIMESTAMP",
    "subnet_periods_after_conversion": "BIGINT",
    "primary_first_start": "TIMESTAMP", "primary_last_end": "TIMESTAMP",
    "subnet_periods_outside_primary": "BIGINT",
}

# A Subnet period ends at its removal when a RemoveSubnetValidatorTx ended it early. Primary coverage is checked against
# the node's merged validator periods: a Subnet period must lie inside one Primary Network period of the same node.
VALIDATION_SQL = """
CREATE OR REPLACE TABLE validation AS
WITH adds AS (
    SELECT node_id, subnet_id, start_time, least(end_time, coalesce(removal_time, end_time)) AS end_time,
           removal_time IS NOT NULL AS removed
    FROM transactions WHERE tx_type = 'AddSubnetValidatorTx'
),
conversions AS (
    SELECT subnet_id, min(accepted_at) AS converted_at FROM transactions WHERE tx_type = 'ConvertSubnetToL1Tx' GROUP BY 1
),
l1 AS (
    SELECT node_id, subnet_id,
           bool_or(tx_type = 'ConvertSubnetToL1Tx') AS initial_l1_validator,
           min(accepted_at) FILTER (WHERE tx_type IN ('ConvertSubnetToL1Tx', 'RegisterL1ValidatorTx')) AS registered_at,
           max(accepted_at) FILTER (WHERE tx_type = 'DisableL1ValidatorTx') AS disabled_at
    FROM transactions WHERE tx_type IN ('ConvertSubnetToL1Tx', 'RegisterL1ValidatorTx', 'DisableL1ValidatorTx')
    GROUP BY 1, 2
),
primary_periods AS (
    SELECT node_id, start_time, end_time FROM periods WHERE role = 'validator'
),
covered AS (
    SELECT a.node_id, a.subnet_id, a.start_time,
           bool_or(p.start_time <= a.start_time AND p.end_time >= a.end_time) AS inside
    FROM adds a LEFT JOIN primary_periods p ON p.node_id = a.node_id
    GROUP BY 1, 2, 3
),
subnet_rows AS (
    SELECT a.node_id, a.subnet_id, count(*) AS subnet_periods, min(a.start_time) AS first_subnet_start,
           max(a.end_time) AS last_subnet_end, count(*) FILTER (WHERE a.removed) AS removed_early
    FROM adds a GROUP BY 1, 2
),
keys AS (
    SELECT node_id, subnet_id FROM subnet_rows UNION SELECT node_id, subnet_id FROM l1
),
spans AS (
    SELECT node_id, min(start_time) AS primary_first_start, max(end_time) AS primary_last_end FROM primary_periods GROUP BY 1
)
SELECT k.node_id, k.subnet_id,
       coalesce(s.subnet_periods, 0) AS subnet_periods, s.first_subnet_start, s.last_subnet_end,
       coalesce(s.removed_early, 0) AS removed_early,
       c.converted_at AS l1_converted_at, coalesce(l.initial_l1_validator, false) AS initial_l1_validator,
       l.registered_at AS l1_registered_at, l.disabled_at AS l1_disabled_at,
       (SELECT count(*) FROM adds a WHERE a.node_id = k.node_id AND a.subnet_id = k.subnet_id
                                      AND c.converted_at IS NOT NULL AND a.start_time >= c.converted_at) AS subnet_periods_after_conversion,
       sp.primary_first_start, sp.primary_last_end,
       (SELECT count(*) FROM covered v WHERE v.node_id = k.node_id AND v.subnet_id = k.subnet_id
                                        AND NOT coalesce(v.inside, false)) AS subnet_periods_outside_primary
FROM keys k
LEFT JOIN subnet_rows s USING (node_id, subnet_id)
LEFT JOIN l1 l USING (node_id, subnet_id)
LEFT JOIN conversions c ON c.subnet_id = k.subnet_id
LEFT JOIN spans sp ON sp.node_id = k.node_id
ORDER BY k.node_id, k.subnet_id
"""

SUMMARY_SQL = """
SELECT count(*), count(DISTINCT node_id), count(DISTINCT subnet_id),
       count(*) FILTER (WHERE subnet_periods > 0), count(*) FILTER (WHERE l1_registered_at IS NOT NULL),
       count(DISTINCT subnet_id) FILTER (WHERE l1_converted_at IS NOT NULL),
       sum(subnet_periods_after_conversion), sum(subnet_periods_outside_primary),
       count(*) FILTER (WHERE subnet_periods > 0 AND primary_first_start IS NULL)
FROM validation
"""
SUMMARY_KEYS = (
    "rows", "nodes", "subnets", "subnet_validator_rows", "l1_validator_rows", "converted_subnets",
    "subnet_periods_after_conversion", "subnet_periods_outside_primary", "subnet_rows_without_primary_period",
)

# The catalog's ACP-77 counts, recomputed. "Active" is a validator period covering the instant. "Recent Subnet validator"
# is a Subnet period overlapping [2024-06-01, Etna). "Exited" is no validator period ending after 2025-12-31 12:00.
# The prior year uses the catalog's F4 rule: a Subnet period in the 197 days before 2023-12-15 12:00, and not active a
# year later at 12:00.
REPRODUCTION_SQL = f"""
WITH v AS (SELECT node_id, start_time, end_time FROM periods WHERE role = 'validator'),
active AS (SELECT DISTINCT node_id FROM v WHERE start_time <= TIMESTAMP '2024-12-15 12:00:00' AND end_time > TIMESTAMP '2024-12-15 12:00:00'),
active_end_of_day AS (SELECT DISTINCT node_id FROM v WHERE start_time <= TIMESTAMP '2024-12-15 23:59:59' AND end_time > TIMESTAMP '2024-12-15 23:59:59'),
later AS (SELECT DISTINCT node_id FROM v WHERE end_time > TIMESTAMP '2025-12-31 12:00:00'),
recent AS (
    SELECT DISTINCT node_id FROM transactions
    WHERE tx_type = 'AddSubnetValidatorTx' AND least(end_time, coalesce(removal_time, end_time)) > TIMESTAMP '2024-06-01'
      AND start_time < TIMESTAMP '{ETNA_STAMP}'
),
prior_active AS (SELECT DISTINCT node_id FROM v WHERE start_time <= TIMESTAMP '2023-12-15 12:00:00' AND end_time > TIMESTAMP '2023-12-15 12:00:00'),
prior_recent AS (
    SELECT DISTINCT node_id FROM transactions
    WHERE tx_type = 'AddSubnetValidatorTx' AND least(end_time, coalesce(removal_time, end_time)) > TIMESTAMP '2023-12-15 12:00:00' - INTERVAL 197 DAY
      AND start_time < TIMESTAMP '2023-12-15 12:00:00'
)
SELECT (SELECT count(*) FROM active),
       (SELECT count(*) FROM active_end_of_day),
       (SELECT count(*) FROM active WHERE node_id NOT IN (SELECT node_id FROM later)),
       (SELECT count(*) FROM active WHERE node_id IN (SELECT node_id FROM recent)),
       (SELECT count(*) FROM active WHERE node_id IN (SELECT node_id FROM recent) AND node_id NOT IN (SELECT node_id FROM later)),
       (SELECT count(*) FROM prior_active WHERE node_id IN (SELECT node_id FROM prior_recent)),
       (SELECT count(*) FROM prior_active WHERE node_id IN (SELECT node_id FROM prior_recent) AND node_id NOT IN (SELECT node_id FROM active))
"""
REPRODUCTION_KEYS = (
    "active_2024_12_15_noon", "active_2024_12_15_end_of_day", "exited_of_active", "recent_subnet_validators",
    "recent_subnet_validators_exited", "prior_year_subnet_validators", "prior_year_subnet_validators_not_active_a_year_later",
)
# The catalog's figures, for the comparison written into the summary.
CATALOG_FIGURES = {
    "active_2024_12_15_noon": 1555, "exited_of_active": 1036, "recent_subnet_validators": 296,
    "recent_subnet_validators_exited": 270, "excess_exits_beyond_prior_rate": 134,
}


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
    """Each input's run pinned by ``dataset_id=run``, or its newest run."""
    pinned = pinned or {}
    unknown = sorted(set(pinned) - set(INPUTS.values()))
    if unknown:
        raise DataError(f"not an input of {DATASET_ID}: {', '.join(unknown)}")
    return [_describe(input_id, dataset_id, pinned.get(dataset_id), root) for input_id, dataset_id in INPUTS.items()]


def _quoted(path: Path) -> str:
    return str(path).replace("'", "''")


def load_inputs(connection: Any, inputs: list[dict[str, Any]]) -> None:
    connection.execute("SET memory_limit='3GB'")
    views = {"subnet-transactions": "transactions", "staking-periods": "periods"}
    for item in inputs:
        connection.execute(f"CREATE OR REPLACE VIEW {views[item['input_id']]} AS SELECT * FROM read_parquet('{_quoted(item['path'])}')")


def compute(connection: Any) -> None:
    try:
        connection.execute(VALIDATION_SQL)
    except duckdb.Error as error:
        raise DataError(f"Subnet validation computation failed: {error}") from error


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def summarize(connection: Any) -> dict[str, Any]:
    row = connection.execute(SUMMARY_SQL).fetchone()
    summary = {key: _iso(value) for key, value in zip(SUMMARY_KEYS, row)}
    counts = dict(zip(REPRODUCTION_KEYS, connection.execute(REPRODUCTION_SQL).fetchone()))
    prior_rate = counts["prior_year_subnet_validators_not_active_a_year_later"] / counts["prior_year_subnet_validators"] if counts["prior_year_subnet_validators"] else None
    counts["prior_year_rate"] = round(prior_rate, 4) if prior_rate is not None else None
    counts["excess_exits_beyond_prior_rate"] = (
        counts["recent_subnet_validators_exited"] - round(counts["recent_subnet_validators"] * prior_rate) if prior_rate is not None else None
    )
    counts["catalog"] = CATALOG_FIGURES
    counts["differences"] = {key: counts[key] - value for key, value in CATALOG_FIGURES.items() if counts.get(key) is not None}
    counts["note"] = (
        "The monetary ledger counts validators active at 23:59:59 each UTC day, the catalog at 12:00. Counted at 23:59:59, the "
        "staking-period log gives the ledger's figure: the gap is the clock, not the data."
    )
    summary["catalog_reproduction"] = counts
    return summary


def parameters() -> dict[str, Any]:
    return {
        "etna": ETNA.isoformat() + "Z",
        "subnet_period_end": "the period's end, or its removal time when a RemoveSubnetValidatorTx ended it early",
        "primary_coverage": "a Subnet period is inside the Primary Network when one validator period of the same node spans it",
        "reproduction": "active at 2024-12-15 12:00, recent Subnet validator with a Subnet period overlapping 2024-06-01 to Etna, exited when no validator period ends after 2025-12-31 12:00",
    }


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    """Build the table into a new run directory holding ``capture/`` and ``dataset/``."""
    _reject(dataset_id)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    inputs = select_inputs(pinned, root)
    completed_at = now()
    records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records}))
    capture_receipt = {
        "schema_version": "derived-capture/v1",
        "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
        "dataset_id": dataset_id,
        "source_id": SOURCE_ID,
        "completed_at": completed_at,
        "contract_sha256": contract_hash(catalog, dataset_id),
        "tool": f"avalanche-research@{__version__}",
        "inputs": records,
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
            connection.execute("COPY validation TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection)
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
    """Verify the input runs still hash as recorded, the contract is unchanged, and the build holds: one row per node and
    Subnet, no Subnet period starting after its Subnet converted, every Subnet period inside a Primary Network period of
    the same node, and a rebuild from the recorded inputs gives the same rows."""
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
        checked.extend(["build hashes", "columns", "one row per node and Subnet", "no Subnet period after conversion",
                        "Subnet periods inside the Primary Network", "rebuild from inputs"])
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
                columns = [row[0] for row in connection.execute("DESCRIBE built").fetchall()]
                declared = [field["name"] for field in dataset(catalog, DATASET_ID)["fields"]]
                if columns != list(TABLE_COLUMNS) or columns != declared:
                    findings.append("columns differ from the module or the catalog")
                repeats = connection.execute("SELECT count(*) - count(DISTINCT (node_id, subnet_id)) FROM built").fetchone()[0]
                if repeats:
                    findings.append(f"{repeats} rows repeat a node and Subnet")
                after, outside = connection.execute(
                    "SELECT sum(subnet_periods_after_conversion), sum(subnet_periods_outside_primary) FROM built").fetchone()
                if after:
                    findings.append(f"{after} Subnet periods start after their Subnet converted to an L1")
                if outside:
                    findings.append(f"{outside} Subnet periods are not inside a Primary Network period of the same node")
                if len(inputs) == len(INPUTS):
                    load_inputs(connection, inputs)
                    compute(connection)
                    differ = connection.execute(
                        "SELECT (SELECT count(*) FROM (SELECT * FROM built EXCEPT ALL SELECT * FROM validation))"
                        " + (SELECT count(*) FROM (SELECT * FROM validation EXCEPT ALL SELECT * FROM built))").fetchone()[0]
                    if differ:
                        findings.append(f"a rebuild from the recorded inputs differs in {differ} rows")
                summary.update(build_receipt.get("summary", {}))
            finally:
                connection.close()
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
