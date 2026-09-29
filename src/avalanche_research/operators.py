"""Operators and fleets: one row per validator node with two groupings, so validator types can be fitted on operators.

A node is a machine, not a decision maker. `operator_id` groups nodes by their latest reward address, the node table's
operator proxy: a shared address links nodes, but it does not prove one decision maker, and different addresses do not
prove different operators. `fleet_id` groups nodes that entered in the same UTC week, left in the same UTC week, and carry
the same latest delegation fee, a behavioural signature that can join nodes paid to different addresses. Named agents
are flagged with the evidence for each label. The build summary reports how many nodes change fleet when the week rule
widens to two weeks, as a stability measure of the fleet grouping.
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
from .catalog import (
    DataError,
    canonical_bytes,
    contract_hash,
    dataset,
    load_catalog,
    now,
    sha256,
)

DATASET_ID = "derived.operators"
DATASET_IDS = (DATASET_ID,)
SOURCE_ID = "derived"
TABLE = "operators"
INPUTS = {"node-table": "derived.node-table"}
OPTIONAL_INPUTS: dict[str, str] = {}

# Named agents, by the reward address of their nodes, with the evidence for each label. A label is evidence only when a
# public source names the address. The catalog addresses are named by behaviour, which is inference.
NAMED_AGENTS = {
    "avax10f8305248c0wsfsdempdtpx7lpkc30vwzl9y9q": ("GoGoPool", "Snowpeer liquid staking provider list, https://api.snowpeer.io/v1/lsps, captured 2026-09-28"),
    "avax19zfygxaf59stehzedhxjesads0p5jdvfeedal0": ("BENQI", "Snowpeer liquid staking provider list, https://api.snowpeer.io/v1/lsps, captured 2026-09-28"),
    "avax1dwkwval9epuwxpy0g2m6xg2l00fx4yxtzah80t": ("unnamed August 2025 exit address", "protocol mechanism catalog finding F6: reward address of nodes that left in August 2025, no public label"),
    "avax134sylz25j3ga2grckw9kgyd2gscqplfmww6zqp": ("unnamed August 2025 exit address", "protocol mechanism catalog finding F6: reward address of nodes that left in August 2025, no public label"),
}
FLEET_WEEKS = 1
ALTERNATE_FLEET_WEEKS = 2

TABLE_COLUMNS = {
    "node_id": "VARCHAR", "operator_id": "VARCHAR", "operator_nodes": "BIGINT",
    "fleet_id": "VARCHAR", "fleet_nodes": "BIGINT", "fleet_operators": "BIGINT",
    "entry_week": "DATE", "exit_week": "DATE", "latest_fee_rate": "DOUBLE", "active": "BOOLEAN", "periods": "BIGINT",
    "named_agent": "VARCHAR", "named_agent_evidence": "VARCHAR",
}


def _agents_values() -> str:
    rows = ", ".join(f"('{address}', '{name}', '{evidence}')" for address, (name, evidence) in NAMED_AGENTS.items())
    return f"(VALUES {rows}) AS a(address, name, evidence)"


def fleet_key(weeks: int) -> str:
    """The fleet signature: entry and exit bucketed into ``weeks``-week UTC periods from Monday 2020-09-07, and the fee."""
    origin = "DATE '2020-09-07'"
    bucket = lambda column: f"{origin} + INTERVAL (7 * {weeks} * (date_diff('day', {origin}, {column}::DATE) // (7 * {weeks}))) DAY"
    return f"md5(strftime({bucket('first_start')}, '%Y-%m-%d') || '/' || strftime({bucket('last_end')}, '%Y-%m-%d') || '/' || coalesce(latest_fee_rate::VARCHAR, ''))"


OPERATORS_SQL = f"""
CREATE OR REPLACE TABLE operators AS
WITH n AS (
    SELECT node_id, reward_address AS operator_id, first_start, last_end, latest_fee_rate, active, periods,
           {fleet_key(FLEET_WEEKS)} AS fleet_id
    FROM nodes
)
SELECT n.node_id, n.operator_id, count(*) OVER (PARTITION BY n.operator_id) AS operator_nodes,
       n.fleet_id, count(*) OVER (PARTITION BY n.fleet_id) AS fleet_nodes,
       NULL::BIGINT AS fleet_operators,
       date_trunc('week', n.first_start)::DATE AS entry_week, date_trunc('week', n.last_end)::DATE AS exit_week,
       n.latest_fee_rate, n.active, n.periods,
       a.name AS named_agent, a.evidence AS named_agent_evidence
FROM n LEFT JOIN {_agents_values()} ON a.address = n.operator_id
ORDER BY n.node_id
"""
FLEET_OPERATORS_SQL = """
UPDATE operators SET fleet_operators = f.k
FROM (SELECT fleet_id, count(DISTINCT operator_id) AS k FROM operators GROUP BY 1) f
WHERE operators.fleet_id = f.fleet_id
"""

SUMMARY_SQL = """
SELECT count(*), count(DISTINCT node_id), count(DISTINCT operator_id), count(DISTINCT fleet_id),
       count(*) FILTER (WHERE operator_nodes = 1), count(*) FILTER (WHERE fleet_nodes = 1),
       count(DISTINCT fleet_id) FILTER (WHERE fleet_operators > 1), max(operator_nodes), max(fleet_nodes)
FROM operators
"""
SUMMARY_KEYS = (
    "rows", "nodes", "operators", "fleets", "single_node_operators", "single_node_fleets", "fleets_spanning_operators",
    "largest_operator_nodes", "largest_fleet_nodes",
)


def stability_sql(weeks: int) -> str:
    """Nodes whose fleet co-members change when the week bucket widens from FLEET_WEEKS to ``weeks``."""
    return f"""
    WITH wide AS (SELECT node_id, {fleet_key(weeks)} AS wide_id FROM nodes),
    pairs AS (SELECT o.node_id, o.fleet_id, w.wide_id FROM operators o JOIN wide w USING (node_id)),
    narrow_size AS (SELECT fleet_id, count(*) AS k FROM pairs GROUP BY 1),
    wide_size AS (SELECT wide_id, count(*) AS k FROM pairs GROUP BY 1)
    SELECT count(DISTINCT p.wide_id), count(*) FILTER (WHERE ns.k <> ws.k)
    FROM pairs p JOIN narrow_size ns USING (fleet_id) JOIN wide_size ws USING (wide_id)
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
    """The node table pinned by ``dataset_id=run``, or its newest run."""
    pinned = pinned or {}
    unknown = sorted(set(pinned) - set(INPUTS.values()))
    if unknown:
        raise DataError(f"not an input of {DATASET_ID}: {', '.join(unknown)}")
    return [_describe(input_id, dataset_id, pinned.get(dataset_id), root) for input_id, dataset_id in INPUTS.items()]


def _quoted(path: Path) -> str:
    return str(path).replace("'", "''")


def load_inputs(connection: Any, inputs: list[dict[str, Any]]) -> None:
    connection.execute("SET memory_limit='2GB'")
    item = next(item for item in inputs if item["input_id"] == "node-table")
    connection.execute(f"CREATE OR REPLACE VIEW nodes AS SELECT * FROM read_parquet('{_quoted(item['path'])}')")


def compute(connection: Any) -> None:
    try:
        connection.execute(OPERATORS_SQL)
        connection.execute(FLEET_OPERATORS_SQL)
    except duckdb.Error as error:
        raise DataError(f"operator computation failed: {error}") from error


def summarize(connection: Any) -> dict[str, Any]:
    summary = dict(zip(SUMMARY_KEYS, connection.execute(SUMMARY_SQL).fetchone()))
    wide_fleets, changed = connection.execute(stability_sql(ALTERNATE_FLEET_WEEKS)).fetchone()
    summary["fleet_stability"] = {
        "rule_weeks": FLEET_WEEKS, "alternate_rule_weeks": ALTERNATE_FLEET_WEEKS,
        "fleets": summary["fleets"], "fleets_under_alternate_rule": wide_fleets, "nodes_whose_fleet_size_changes": changed,
    }
    summary["named_agents"] = {
        name: {"nodes": nodes, "active": active}
        for name, nodes, active in connection.execute(
            "SELECT named_agent || ' ' || left(operator_id, 9), count(*), count(*) FILTER (WHERE active) FROM operators"
            " WHERE named_agent IS NOT NULL GROUP BY named_agent, operator_id ORDER BY 2 DESC").fetchall()
    }
    return summary


def parameters() -> dict[str, Any]:
    return {
        "operator_rule": "operator_id is the node's latest reward address",
        "fleet_rule": "fleet_id joins nodes whose first period started in the same UTC week, whose last period ended in the same UTC week, and whose latest fee is equal",
        "fleet_weeks": FLEET_WEEKS, "alternate_fleet_weeks": ALTERNATE_FLEET_WEEKS,
        "named_agents": {address: {"name": name, "evidence": evidence} for address, (name, evidence) in NAMED_AGENTS.items()},
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
            connection.execute("COPY (SELECT * FROM operators ORDER BY node_id) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
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
    """Verify the input run still hashes as recorded, the contract is unchanged, and the build holds: every node of the
    node table assigned exactly once, every node with an operator and a fleet, and a rebuild from the input gives the
    same rows."""
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
        checked.extend(["build hashes", "columns", "every node assigned once", "operator and fleet present", "rebuild from input"])
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
                connection.execute("SET memory_limit='2GB'")
                parquet = _quoted(dataset_dir / f"{TABLE}.parquet")
                connection.execute(f"CREATE TABLE built AS SELECT * FROM read_parquet('{parquet}')")
                columns = [row[0] for row in connection.execute("DESCRIBE built").fetchall()]
                declared = [field["name"] for field in dataset(catalog, DATASET_ID)["fields"]]
                if columns != list(TABLE_COLUMNS) or columns != declared:
                    findings.append("columns differ from the module or the catalog")
                repeats, missing = connection.execute(
                    "SELECT count(*) - count(DISTINCT node_id), count(*) FILTER (WHERE operator_id IS NULL OR fleet_id IS NULL) FROM built").fetchone()
                if repeats:
                    findings.append(f"{repeats} nodes appear more than once")
                if missing:
                    findings.append(f"{missing} nodes lack an operator or a fleet")
                if len(inputs) == len(INPUTS):
                    load_inputs(connection, inputs)
                    unassigned = connection.execute("SELECT count(*) FROM nodes WHERE node_id NOT IN (SELECT node_id FROM built)").fetchone()[0]
                    if unassigned:
                        findings.append(f"{unassigned} nodes of the node table are not assigned")
                    compute(connection)
                    differ = connection.execute(
                        "SELECT (SELECT count(*) FROM (SELECT * FROM built EXCEPT ALL SELECT * FROM operators))"
                        " + (SELECT count(*) FROM (SELECT * FROM operators EXCEPT ALL SELECT * FROM built))").fetchone()[0]
                    if differ:
                        findings.append(f"a rebuild from the recorded input differs in {differ} rows")
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
