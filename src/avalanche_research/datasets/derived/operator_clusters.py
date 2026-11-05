"""Operator clusters: one row per validator staking period with four cut-safe groupings, so renewal draws can be fitted
per operator rather than per node.

Every grouping is an inference. A shared address links nodes, and it never proves one decision maker: one operator can
use several addresses, and one address can pay several operators. Addresses are pseudonymous and are kept as addresses.

The four groupings:

1. ``reward_address``, the period's own reward address. It uses nothing later than the period.
2. ``owner_key``, the reward address, except for the periods paid to the pool address of GoGoPool, a liquid staking
   protocol that has since closed. That one address paid thousands of nodes of many node operators, so its periods are
   split by the owner of the node's minipool record, and its periods with no minipool record form one key, the pool
   block. The pool address is found in the data: the reward address that holds most periods of the nodes the minipool
   records list.
3. ``cohort_key``, the node's entry week (UTC weeks from Monday 2020-09-07) and delegation fee, both from the node's
   first accepted period. It is the fleet of ``derived.operators`` without its exit week.
4. ``component_id``, a connected component of the graph that links each node to the owner keys of its periods. Only
   periods accepted before the held-back cut build the graph, and periods accepted on or after it get no component.

No row accepted before the cut takes a label from a record on or after it. The pool address is identified from periods
before the cut. A minipool record labels such a period only when the record's latest start, the later of its creation
and its first cycle start, is before the cut. The cohort comes from the node's first accepted period, never later than
the row itself. The check rebuilds the table from the inputs cut at the held-back date and requires every
earlier row to come out the same.

A minipool record keeps only the node's latest owner. Its owner is applied to every period the node was paid to the pool
address, also those before the record's latest start. The field ``owner_basis`` marks those as carried back, which
assumes that a node re-created as a minipool kept its owner.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
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
from . import seam

DATASET_ID = "derived.operator-clusters"
DATASET_IDS = (DATASET_ID,)
SOURCE_ID = "derived"
TABLE = "operator-clusters"
INPUTS = {
    "staking-periods": "derived.staking-periods",
    "validator-stakes": "snowflake.primary-validator-stakes",
    "minipool-records": "c-chain-rpc.minipool-records",
}
OPTIONAL_INPUTS: dict[str, str] = {}
# The held-back cut: no row accepted before it is labelled from a record on or after it.
HELD_BACK_CUT = datetime(2025, 11, 19, tzinfo=UTC)
CUT_SQL = "TIMESTAMP '2025-11-19 00:00:00'"
WEEK_ORIGIN = "2020-09-07"
# The pool address must hold more than this share of the minipool nodes' periods before the cut to be identified.
POOL_SHARE_FLOOR = 0.5
BASES = ("reward-address", "minipool-owner", "minipool-owner-carried-back", "pool-no-record")

TABLE_COLUMNS = {
    "transaction_hash": "VARCHAR", "node_id": "VARCHAR", "accepted_at": "TIMESTAMP", "start_time": "TIMESTAMP",
    "end_time": "TIMESTAMP", "held_back": "BOOLEAN", "reward_address": "VARCHAR", "pool_address": "BOOLEAN",
    "minipool_owner": "VARCHAR", "owner_key": "VARCHAR", "owner_basis": "VARCHAR",
    "entry_week": "DATE", "entry_fee_rate": "DOUBLE", "cohort_key": "VARCHAR",
    "component_id": "VARCHAR", "component_nodes": "BIGINT", "component_keys": "BIGINT",
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


def select_inputs(pinned: dict[str, str] | None, root: Path | None) -> list[dict[str, Any]]:
    """The input runs pinned by ``dataset_id=run``, or the newest built run of each. Validator stakes are read from the
    seamed table when one is built and neither is pinned."""
    pinned = pinned or {}
    unknown = sorted(set(pinned) - set(INPUTS.values()) - set(seam.SEAMED.values()))
    if unknown:
        raise DataError(f"not an input of {DATASET_ID}: {', '.join(unknown)}")
    selected = []
    for input_id, share_id in INPUTS.items():
        dataset_id, run = seam.resolve(share_id, pinned, root)
        record = datasets.receipt(dataset_id, run, root)
        parquet = datasets.parquet_path(dataset_id, record["run"], root)
        body = parquet.read_bytes()
        selected.append({
            "input_id": input_id, "dataset_id": dataset_id, "run": record["run"],
            "capture_id": record["capture"]["capture_id"], "contract_sha256": record["capture"].get("contract_sha256"),
            "captured_at": record["capture"].get("completed_at"), "rows": record["build"].get("summary", {}).get("rows"),
            "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet,
        })
    return selected


def _quoted(path: Path) -> str:
    return str(path).replace("'", "''")


def load_inputs(connection: Any, inputs: list[dict[str, Any]]) -> None:
    connection.execute("SET memory_limit='2GB'")
    path = {item["input_id"]: _quoted(item["path"]) for item in inputs}
    connection.execute(
        "CREATE OR REPLACE TABLE source_periods AS SELECT p.transaction_hash, p.node_id, p.accepted_at, p.start_time, p.end_time,"
        " p.delegation_fee_rate::DOUBLE AS delegation_fee_rate, v.reward_address"
        f" FROM read_parquet('{path['staking-periods']}') p"
        f" LEFT JOIN (SELECT transaction_hash, reward_address FROM read_parquet('{path['validator-stakes']}')) v USING (transaction_hash)"
        " WHERE p.role = 'validator'")
    connection.execute(
        "CREATE OR REPLACE TABLE source_records AS SELECT node_id, owner, multisig_address, tx_id,"
        " coalesce(greatest(creation_time, initial_start_time), 'infinity'::TIMESTAMP) AS record_start"
        f" FROM read_parquet('{path['minipool-records']}')")


def pool_address(connection: Any, suffix: str = "") -> str | None:
    """The reward address that holds most periods, accepted before the cut, of nodes with a minipool record that began
    before the cut. None when no such period exists, and an error when no address holds more than half of them."""
    rows = connection.execute(f"""
        SELECT p.reward_address, count(*) FROM periods{suffix} p JOIN records{suffix} r USING (node_id)
        WHERE p.accepted_at < {CUT_SQL} AND r.record_start < {CUT_SQL} AND p.reward_address IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC, 1""").fetchall()
    if not rows:
        return None
    total = sum(count for _, count in rows)
    if rows[0][1] <= POOL_SHARE_FLOOR * total:
        raise DataError(f"no reward address holds more than half of the minipool nodes' periods ({rows[0][1]} of {total})")
    return rows[0][0]


def _components(pairs: list[tuple[str, str | None]]) -> dict[str, tuple[str, int, int]]:
    """Connected components of the graph joining each node to each owner key it was paid to: for every node, the
    smallest node ID in its component, and the component's node and key counts."""
    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def find(item: tuple[str, str]) -> tuple[str, str]:
        parent.setdefault(item, item)
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    for node, key in pairs:
        find(("node", node))
        if key is not None:
            left, right = find(("node", node)), find(("key", key))
            if left != right:
                parent[max(left, right)] = min(left, right)
    members: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for item in list(parent):
        members.setdefault(find(item), []).append(item)
    result = {}
    for items in members.values():
        nodes = sorted(name for kind, name in items if kind == "node")
        keys = sum(1 for kind, _ in items if kind == "key")
        for node in nodes:
            result[node] = (nodes[0], len(nodes), keys)
    return result


def compute(connection: Any, cut_only: bool = False) -> str | None:
    """Write table ``clusters`` (``clusters_cut`` from the inputs cut at the held-back date) and return the pool address."""
    suffix = "_cut" if cut_only else ""
    where_periods = f"WHERE accepted_at < {CUT_SQL}" if cut_only else ""
    where_records = f"WHERE record_start < {CUT_SQL}" if cut_only else ""
    try:
        connection.execute(f"CREATE OR REPLACE TEMP VIEW periods{suffix} AS SELECT * FROM source_periods {where_periods}")
        connection.execute(f"CREATE OR REPLACE TEMP VIEW records{suffix} AS SELECT * FROM source_records {where_records}")
        pool = pool_address(connection, suffix)
        connection.execute(f"""
        CREATE OR REPLACE TABLE clusters{suffix} AS
        WITH firsts AS (
            SELECT node_id, start_time AS first_start, delegation_fee_rate AS entry_fee_rate FROM (
                SELECT *, row_number() OVER (PARTITION BY node_id ORDER BY accepted_at, start_time, transaction_hash) AS n
                FROM periods{suffix}) WHERE n = 1
        ),
        labelled AS (
            SELECT p.*, p.accepted_at >= {CUT_SQL} AS held_back, p.reward_address = $pool AS pool_address,
                   CASE WHEN r.node_id IS NOT NULL AND (r.record_start < {CUT_SQL} OR p.accepted_at >= {CUT_SQL})
                        THEN r.owner END AS owner,
                   r.record_start,
                   DATE '{WEEK_ORIGIN}' + INTERVAL (7 * (date_diff('day', DATE '{WEEK_ORIGIN}', f.first_start::DATE) // 7)) DAY AS entry_week,
                   f.entry_fee_rate
            FROM periods{suffix} p LEFT JOIN records{suffix} r USING (node_id) LEFT JOIN firsts f USING (node_id)
        )
        SELECT transaction_hash, node_id, accepted_at, start_time, end_time, held_back, reward_address,
               coalesce(pool_address, false) AS pool_address,
               CASE WHEN pool_address THEN owner END AS minipool_owner,
               CASE WHEN reward_address IS NULL THEN NULL
                    WHEN NOT coalesce(pool_address, false) THEN reward_address
                    WHEN owner IS NULL THEN reward_address || '/pool'
                    ELSE reward_address || '/owner/' || owner END AS owner_key,
               CASE WHEN reward_address IS NULL THEN NULL
                    WHEN NOT coalesce(pool_address, false) THEN 'reward-address'
                    WHEN owner IS NULL THEN 'pool-no-record'
                    WHEN start_time >= record_start THEN 'minipool-owner'
                    ELSE 'minipool-owner-carried-back' END AS owner_basis,
               entry_week::DATE AS entry_week, entry_fee_rate,
               strftime(entry_week, '%Y-%m-%d') || '/' || coalesce(entry_fee_rate::VARCHAR, '') AS cohort_key,
               NULL::VARCHAR AS component_id, NULL::BIGINT AS component_nodes, NULL::BIGINT AS component_keys
        FROM labelled
        """, {"pool": pool})
        pairs = connection.execute(
            f"SELECT DISTINCT node_id, owner_key FROM clusters{suffix} WHERE NOT held_back ORDER BY 1, 2").fetchall()
        components = _components(pairs)
        connection.execute(f"CREATE OR REPLACE TEMP TABLE components{suffix}(node_id VARCHAR, component_id VARCHAR, component_nodes BIGINT, component_keys BIGINT)")
        connection.executemany(f"INSERT INTO components{suffix} VALUES (?, ?, ?, ?)",
                               [(node, *value) for node, value in sorted(components.items())])
        connection.execute(f"""
        UPDATE clusters{suffix} SET component_id = c.component_id, component_nodes = c.component_nodes, component_keys = c.component_keys
        FROM components{suffix} c WHERE clusters{suffix}.node_id = c.node_id AND NOT clusters{suffix}.held_back""")
    except duckdb.Error as error:
        raise DataError(f"operator cluster computation failed: {error}") from error
    return pool


def summarize(connection: Any, pool: str | None) -> dict[str, Any]:
    def one(sql: str) -> tuple[Any, ...]:
        return connection.execute(sql).fetchone()

    rows, nodes, held = one("SELECT count(*), count(DISTINCT node_id), count(*) FILTER (WHERE held_back) FROM clusters")
    keys = dict(zip(("reward_address", "owner_key", "cohort_key"), one(
        "SELECT count(DISTINCT reward_address), count(DISTINCT owner_key), count(DISTINCT cohort_key) FROM clusters")))
    before = dict(zip(("reward_address", "owner_key", "cohort_key", "component_id"), one(
        "SELECT count(DISTINCT reward_address), count(DISTINCT owner_key), count(DISTINCT cohort_key), count(DISTINCT component_id)"
        " FROM clusters WHERE NOT held_back")))
    largest = dict(zip(("reward_address", "owner_key", "cohort_key", "component_id"), one("""
        SELECT (SELECT max(k) FROM (SELECT count(DISTINCT node_id) AS k FROM clusters WHERE NOT held_back GROUP BY reward_address)),
               (SELECT max(k) FROM (SELECT count(DISTINCT node_id) AS k FROM clusters WHERE NOT held_back GROUP BY owner_key)),
               (SELECT max(k) FROM (SELECT count(DISTINCT node_id) AS k FROM clusters WHERE NOT held_back GROUP BY cohort_key)),
               (SELECT max(component_nodes) FROM clusters)""")))
    bases = {basis: {"periods": periods, "nodes": count, "periods_before_cut": early}
             for basis, periods, count, early in connection.execute(
                 "SELECT owner_basis, count(*), count(DISTINCT node_id), count(*) FILTER (WHERE NOT held_back)"
                 " FROM clusters WHERE pool_address GROUP BY 1 ORDER BY 1").fetchall()}
    owners, largest_owner = one(
        "SELECT count(DISTINCT minipool_owner), max(k) FROM (SELECT minipool_owner, count(DISTINCT node_id) AS k FROM clusters"
        " WHERE pool_address AND minipool_owner IS NOT NULL GROUP BY 1)")
    later, later_nodes = one(f"""
        SELECT count(*), count(DISTINCT c.node_id) FROM clusters c JOIN source_records r USING (node_id)
        WHERE c.pool_address AND NOT c.held_back AND r.record_start >= {CUT_SQL}""")
    records, multisigs, matched = one("""
        SELECT count(*), list(DISTINCT multisig_address ORDER BY multisig_address),
               count(*) FILTER (WHERE tx_id IN (SELECT transaction_hash FROM clusters WHERE pool_address)) FROM source_records""")
    return {
        "rows": rows, "periods": rows, "nodes": nodes, "held_back_periods": held,
        "held_back_cut": HELD_BACK_CUT.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "periods_without_reward_address": one("SELECT count(*) FROM clusters WHERE reward_address IS NULL")[0],
        "keys": keys, "keys_before_cut": before, "largest_nodes_before_cut": largest,
        "pool": {
            "address": pool, "periods": sum(item["periods"] for item in bases.values()),
            "nodes": one("SELECT count(DISTINCT node_id) FROM clusters WHERE pool_address")[0],
            "by_basis": bases, "minipool_owners": owners, "largest_owner_nodes": largest_owner,
            "pool_no_record_periods_before_cut_whose_node_has_a_record_from_after_the_cut": {"periods": later, "nodes": later_nodes},
        },
        "minipool_records": {"rows": records, "multisig_addresses": multisigs, "tx_ids_matching_a_pool_period": matched},
    }


def parameters() -> dict[str, Any]:
    return {
        "held_back_cut": HELD_BACK_CUT.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "week_origin": WEEK_ORIGIN,
        "pool_rule": "the reward address holding more than half of the periods, accepted before the cut, of nodes whose minipool record began before the cut",
        "owner_rule": "a pool-address period takes its node's minipool owner when the record began before the cut or the period was accepted on or after it, and the period joins the pool block otherwise",
        "cohort_rule": "entry week and delegation fee of the node's first accepted period",
        "component_rule": "connected components of nodes and owner keys over periods accepted before the cut",
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
            pool = compute(connection)
            connection.execute("COPY (SELECT * FROM clusters ORDER BY transaction_hash) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection, pool)
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


def _differ(connection: Any, left: str, right: str) -> int:
    return connection.execute(
        f"SELECT (SELECT count(*) FROM (SELECT * FROM {left} EXCEPT ALL SELECT * FROM {right}))"
        f" + (SELECT count(*) FROM (SELECT * FROM {right} EXCEPT ALL SELECT * FROM {left}))").fetchone()[0]


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """Verify the input runs still hash as recorded and the contract is unchanged, and, given the build: every validator
    period once, no component on or after the cut, a rebuild from the inputs gives the same rows, and a rebuild from the
    inputs cut at the held-back date gives the same labels to every earlier row."""
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
        checked.extend(["build hashes", "columns", "every validator period once", "no component on or after the cut",
                        "rebuild from inputs", "rebuild from inputs cut at the held-back date"])
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
                connection.execute(f"CREATE TABLE built AS SELECT * FROM read_parquet('{_quoted(dataset_dir / f'{TABLE}.parquet')}')")
                columns = [row[0] for row in connection.execute("DESCRIBE built").fetchall()]
                declared = [field["name"] for field in dataset(catalog, DATASET_ID)["fields"]]
                if columns != list(TABLE_COLUMNS) or columns != declared:
                    findings.append("columns differ from the module or the catalog")
                repeats, late = connection.execute(
                    "SELECT count(*) - count(DISTINCT transaction_hash),"
                    f" count(*) FILTER (WHERE component_id IS NOT NULL AND accepted_at >= {CUT_SQL}) FROM built").fetchone()
                if repeats:
                    findings.append(f"{repeats} periods appear more than once")
                if late:
                    findings.append(f"{late} periods accepted on or after the cut carry a component")
                if len(inputs) == len(INPUTS):
                    load_inputs(connection, inputs)
                    missing = connection.execute(
                        "SELECT count(*) FROM source_periods WHERE transaction_hash NOT IN (SELECT transaction_hash FROM built)").fetchone()[0]
                    if missing:
                        findings.append(f"{missing} validator periods of the input are not in the table")
                    pool = compute(connection)
                    if pool != build_receipt.get("summary", {}).get("pool", {}).get("address"):
                        findings.append("a rebuild identifies a different pool address")
                    differ = _differ(connection, "built", "clusters")
                    if differ:
                        findings.append(f"a rebuild from the recorded inputs differs in {differ} rows")
                    compute(connection, cut_only=True)
                    early = _differ(connection, "(SELECT * FROM built WHERE NOT held_back)", "clusters_cut")
                    if early:
                        findings.append(f"{early} rows before the cut change when the inputs are cut at the held-back date")
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
