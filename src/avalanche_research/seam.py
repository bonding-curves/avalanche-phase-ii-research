"""Share rows before the seam, backup rows from it: one table per Snowflake dataset that stays current when the share stops.

| Dataset | Share | Backup |
| --- | --- | --- |
| ``derived.seamed-validator-stakes`` | ``snowflake.primary-validator-stakes`` | ``derived.p-chain-validator-stakes`` |
| ``derived.seamed-delegator-stakes`` | ``snowflake.primary-delegator-stakes`` | ``derived.p-chain-delegator-stakes`` |
| ``derived.seamed-staking-rewards`` | ``snowflake.primary-staking-rewards`` | ``derived.p-chain-staking-rewards`` |
| ``derived.seamed-staking-supply`` | ``snowflake.primary-staking-supply`` | ``derived.p-chain-staking-supply`` |
| ``derived.seamed-burn-daily`` | ``snowflake.primary-burn-daily`` | ``derived.primary-burn-daily`` |
| ``derived.seamed-c-chain-evm-burn-daily`` | ``snowflake.c-chain-evm-burn-daily`` | ``derived.c-chain-evm-burn-daily`` |

Each table has the share's columns and a last column, ``source``, that names where each row came from.

The P-Chain seam is one instant for all four staking tables, so a stake, its supply reading, and its reward never come
from different sides. It is the earliest of: the first row in the share's last day that lacks its staked outputs or its
block supply, and the share's last row. Share rows before it are kept; backup rows from it on are added. The daily
seams are dates: the share's last date, which is partial when the share stops mid-day, comes from the backup.

A backup reward row whose stake started before the walk carries no period or potential reward, since the walk never
saw the stake start. The seamed reward table takes them from the share's row for that stake, as the share's own reward
table joins them, and computes the fee transfer from them. Every such stake started before the seam, so the share has it.

A backup is used only after it has matched the share. Every row both hold before the seam is compared column by column,
and a single difference stops the derive. A share day that declares itself incomplete, with absent or short blocks or
unresolved burns, is kept as it is and counted, not compared. So is a backup that starts after the seam.

The staking log, the node table, the validator weeks, and the ledger read a seamed table in place of its share dataset
whenever one is built and neither is pinned (``resolve``), and their receipts name the one they read. The receipt's
``window`` gives the ledger the dates the table is complete for, as a share capture's query bounds do.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta
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
from .snowflake import SPECS as SHARE_SPECS

SOURCE_ID = "derived"
P_TABLES = {
    "derived.seamed-validator-stakes": ("snowflake.primary-validator-stakes", "derived.p-chain-validator-stakes", "transaction_hash", "accepted_at"),
    "derived.seamed-delegator-stakes": ("snowflake.primary-delegator-stakes", "derived.p-chain-delegator-stakes", "transaction_hash", "accepted_at"),
    "derived.seamed-staking-rewards": ("snowflake.primary-staking-rewards", "derived.p-chain-staking-rewards", "reward_transaction_hash", "rewarded_at"),
    "derived.seamed-staking-supply": ("snowflake.primary-staking-supply", "derived.p-chain-staking-supply", "transaction_hash", "accepted_at"),
}
DAILY_TABLES = {
    "derived.seamed-burn-daily": ("snowflake.primary-burn-daily", "derived.primary-burn-daily", ("date_utc", "chain")),
    "derived.seamed-c-chain-evm-burn-daily": ("snowflake.c-chain-evm-burn-daily", "derived.c-chain-evm-burn-daily", ("date_utc",)),
}
# A share day that declares itself incomplete is kept, and repaired downstream as before, but not compared: the backup
# holds the blocks or burns the share lacks, so it differs from the share there by design.
SHARE_COMPLETE = {
    "derived.seamed-burn-daily": "s.unresolved_transactions = 0",
    "derived.seamed-c-chain-evm-burn-daily": "s.absent_blocks = 0 AND s.short_blocks = 0",
}
DATASET_IDS = (*P_TABLES, *DAILY_TABLES)
DATASET_ID = DATASET_IDS[0]
SEAMED = {share: seamed for seamed, (share, *_) in {**P_TABLES, **DAILY_TABLES}.items()}
# Columns the share leaves null because its load stopped before the stake settled: compared only where the share has them.
SETTLED_LATER = {"rewarded"}
# Share columns a backup cannot know for a stake that started before its walk: compared only where the backup has them.
BACKUP_MAY_LACK = {"staking_tx_type", "node_id", "period_start_time", "period_end_time", "potential_reward_navax", "potential_reward_avax",
                   "fee_transfer_navax", "fee_transfer_avax", "rewarded"}


def table_name(dataset_id: str) -> str:
    return dataset_id.split(".", 1)[1]


def columns(dataset_id: str) -> dict[str, str]:
    share_id = (P_TABLES.get(dataset_id) or DAILY_TABLES[dataset_id])[0]
    return {**SHARE_SPECS[share_id].table_columns, "source": "VARCHAR"}


def resolve(dataset_id: str, pinned: dict[str, str] | None, root: Path | None) -> tuple[str, str | None]:
    """The dataset and run to read for an input: its seamed table when one is built and neither is pinned."""
    pinned = pinned or {}
    seamed = SEAMED.get(dataset_id)
    if seamed is None or dataset_id in pinned:
        return dataset_id, pinned.get(dataset_id)
    if seamed in pinned:
        return seamed, pinned[seamed]
    return (seamed, None) if datasets.runs(seamed, root) else (dataset_id, None)


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    raise DataError(f"{dataset_id} is derived; use `avalanche data derive`")


capture = build_preview = build = capture_preview


def _inputs(dataset_id: str) -> dict[str, str]:
    if dataset_id in P_TABLES:
        return {**{f"share-{table_name(share)}": share for share, _, _, _ in P_TABLES.values()}, "backup": P_TABLES[dataset_id][1]}
    if dataset_id in DAILY_TABLES:
        share, backup, _ = DAILY_TABLES[dataset_id]
        return {"share": share, "backup": backup}
    raise DataError(f"unknown dataset: {dataset_id}")


def select_inputs(dataset_id: str, pinned: dict[str, str] | None, root: Path | None) -> list[dict[str, Any]]:
    wanted = _inputs(dataset_id)
    pinned = pinned or {}
    unknown = sorted(set(pinned) - set(wanted.values()))
    if unknown:
        raise DataError(f"not an input of {dataset_id}: {', '.join(unknown)}")
    selected = []
    for input_id, input_dataset in wanted.items():
        record = datasets.receipt(input_dataset, pinned.get(input_dataset), root)
        parquet = datasets.parquet_path(input_dataset, record["run"], root)
        body = parquet.read_bytes()
        selected.append({"input_id": input_id, "dataset_id": input_dataset, "run": record["run"], "capture_id": record["capture"]["capture_id"],
                         "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet})
    return selected


def _view(connection: Any, name: str, path: Path) -> None:
    quoted = str(path).replace("'", "''")
    connection.execute(f"CREATE OR REPLACE VIEW \"{name}\" AS SELECT * FROM read_parquet('{quoted}')")


def p_seam(connection: Any) -> datetime:
    """The first instant any of the share's four staking tables is incomplete, within its last day, or its last row."""
    candidates = []
    for share_id, _, _, clock in P_TABLES.values():
        name = table_name(share_id)
        last = connection.execute(f'SELECT max({clock}) FROM "{name}"').fetchone()[0]
        if last is None:
            continue
        candidates.append(last)
        if share_id.endswith("stakes"):
            condition = "staked_utxo_count = 0"
        elif share_id.endswith("supply"):
            condition = "block_height >= 0 AND (block_supply_navax IS NULL OR previous_block_supply_navax IS NULL)"
        else:
            continue
        first_gap = connection.execute(f'SELECT min({clock}) FROM "{name}" WHERE {clock} > ? AND {condition}', [last - timedelta(days=1)]).fetchone()[0]
        if first_gap is not None:
            candidates.append(first_gap)
    return min(candidates)


def _conditions(names: list[str], key: tuple[str, ...]) -> list[tuple[str, str]]:
    result = []
    for name in names:
        if name in key or name == "source":
            continue
        if name in SETTLED_LATER:
            condition = f"(s.{name} IS NOT NULL AND b.{name} IS NOT NULL AND b.{name} IS DISTINCT FROM s.{name})"
        elif name in BACKUP_MAY_LACK:
            condition = f"(b.{name} IS NOT NULL AND b.{name} IS DISTINCT FROM s.{name})"
        else:
            condition = f"b.{name} IS DISTINCT FROM s.{name}"
        result.append((name, condition))
    return result


def compute(dataset_id: str, connection: Any) -> dict[str, Any]:
    """Create ``seamed`` and return the seam and the overlap comparison. Raises when the backup has not matched the share."""
    names = [name for name in columns(dataset_id) if name != "source"]
    listed = ", ".join(names)
    if dataset_id in P_TABLES:
        share_id, _, key_name, clock = P_TABLES[dataset_id]
        key: tuple[str, ...] = (key_name,)
        seam = p_seam(connection)
        share, before, after = f'"{table_name(share_id)}"', f"{clock} < ?", f"{clock} >= ?"
        first_backup = connection.execute(f"SELECT min({clock}) FROM backup").fetchone()[0]
        parameters: list[Any] = [seam]
        seam_text = seam.isoformat(sep=" ")
    else:
        share_id, _, key = DAILY_TABLES[dataset_id]
        share, clock = "share", "date_utc"
        seam_date = connection.execute("SELECT max(date_utc) FROM share").fetchone()[0]
        before, after = "date_utc < ?", "date_utc >= ?"
        first_backup = connection.execute("SELECT min(date_utc) FROM backup").fetchone()[0]
        parameters = [seam_date]
        seam_text = str(seam_date)
        seam = seam_date
    if first_backup is None or first_backup > seam:
        raise DataError(f"the backup of {dataset_id} starts at {first_backup}, after the seam {seam_text}")
    joined = " AND ".join(f"b.{name} = s.{name}" for name in key)
    conditions = _conditions(names, key)
    complete = SHARE_COMPLETE.get(dataset_id, "TRUE")
    both = connection.execute(f"SELECT count(*) FROM backup b JOIN {share} s ON {joined} WHERE s.{before} AND {complete}", parameters).fetchone()[0]
    skipped = connection.execute(f"SELECT count(*) FROM backup b JOIN {share} s ON {joined} WHERE s.{before} AND NOT ({complete})", parameters).fetchone()[0]
    differing = {name: connection.execute(f"SELECT count(*) FROM backup b JOIN {share} s ON {joined} WHERE s.{before} AND {complete} AND {condition}",
                                          parameters).fetchone()[0] for name, condition in conditions}
    differing = {name: count for name, count in differing.items() if count}
    missing = connection.execute(
        f"SELECT count(*) FROM {share} s WHERE s.{before} AND s.{clock} >= (SELECT min({clock}) FROM backup)"
        f" AND NOT EXISTS (SELECT 1 FROM backup b WHERE {joined})", parameters).fetchone()[0]
    overlap = {"seam": seam_text, "rows_compared": both, "share_rows_incomplete_not_compared": skipped, "differing_by_column": differing,
               "share_rows_missing_in_backup": missing}
    if differing or missing:
        raise DataError(f"the backup of {dataset_id} differs from the share before the seam {seam_text}: {json.dumps(overlap)}")
    if both == 0:
        raise DataError(f"the backup of {dataset_id} shares no row with the share before the seam {seam_text}")
    connection.execute(
        f"CREATE OR REPLACE TABLE seamed AS SELECT {listed}, 'snowflake' AS source FROM {share} WHERE {before}"
        f" UNION ALL SELECT {listed}, 'backup' AS source FROM backup WHERE {after}", [*parameters, *parameters])
    if dataset_id == "derived.seamed-staking-rewards":
        overlap["backup_rows_described_by_share_stakes"] = _describe_rewards(connection)
    return overlap


def _describe_rewards(connection: Any) -> int:
    """Fill the stake columns of backup reward rows the walk could not describe from the share's stake rows."""
    stakes = ('SELECT transaction_hash, tx_type, node_id, start_time, end_time, potential_reward_navax FROM "primary-validator-stakes"'
              ' UNION ALL SELECT transaction_hash, tx_type, node_id, start_time, end_time, potential_reward_navax FROM "primary-delegator-stakes"')
    connection.execute(f"""
        UPDATE seamed SET staking_tx_type = p.tx_type, node_id = p.node_id, period_start_time = p.start_time, period_end_time = p.end_time,
               potential_reward_navax = p.potential_reward_navax, potential_reward_avax = p.potential_reward_navax / 1e9,
               fee_transfer_navax = seamed.realized_reward_navax - p.potential_reward_navax,
               fee_transfer_avax = (seamed.realized_reward_navax - p.potential_reward_navax) / 1e9
        FROM ({stakes}) p
        WHERE seamed.source = 'backup' AND seamed.staking_tx_type IS NULL AND p.transaction_hash = seamed.staking_transaction_hash""")
    return connection.execute("SELECT count(*) FROM seamed WHERE source = 'backup' AND staking_tx_type IS NOT NULL").fetchone()[0]


def _window(dataset_id: str, connection: Any, inputs: list[dict[str, Any]]) -> dict[str, str]:
    """[start, end) UTC dates the table is complete for: from the share query's start to the backup's last whole day."""
    share_id = (P_TABLES.get(dataset_id) or DAILY_TABLES[dataset_id])[0]
    share = next(item for item in inputs if item["dataset_id"] == share_id)
    capture = datasets.receipt(share_id, share["run"], share["path"].parents[2])["capture"]
    start = capture["queries"][0]["parameters"]["start"] if capture.get("queries") else None
    if dataset_id in P_TABLES:
        last = connection.execute(f"SELECT max({P_TABLES[dataset_id][3]}) FROM backup").fetchone()[0]
        end = last.date()
    else:
        end = connection.execute("SELECT max(date_utc) FROM backup").fetchone()[0] + timedelta(days=1)
    return {"start": start, "end": end.isoformat()}


def _load(connection: Any, inputs: list[dict[str, Any]]) -> None:
    for item in inputs:
        name = "backup" if item["input_id"] == "backup" else "share" if item["input_id"] == "share" else table_name(item["dataset_id"])
        _view(connection, name, item["path"])


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    if dataset_id not in DATASET_IDS:
        raise DataError(f"unknown dataset: {dataset_id}")
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    inputs = select_inputs(dataset_id, pinned, root)
    connection = duckdb.connect()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        _load(connection, inputs)
        overlap = compute(dataset_id, connection)
        window = _window(dataset_id, connection, inputs)
        completed_at = now()
        records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
        identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records}))
        capture_receipt = {
            "schema_version": "derived-capture/v1", "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
            "dataset_id": dataset_id, "source_id": SOURCE_ID, "completed_at": completed_at, "contract_sha256": contract_hash(catalog, dataset_id),
            "tool": f"avalanche-research@{__version__}", "inputs": records, "seam": overlap["seam"], "window": window,
            "parameters": {"rule": "share rows before the seam, backup rows from it, after the backup matched every share row before it"},
        }
        (temporary / "capture").mkdir()
        (temporary / "dataset").mkdir()
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet = temporary / "dataset" / f"{table_name(dataset_id)}.parquet"
        order = "date_utc" if dataset_id in DAILY_TABLES else P_TABLES[dataset_id][3]
        connection.execute(f"COPY (SELECT * FROM seamed ORDER BY {order}, 1) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
        counts = dict(connection.execute("SELECT source, count(*) FROM seamed GROUP BY 1").fetchall())
        build_receipt = {
            "schema_version": "derived-build/v1", "dataset_id": dataset_id, "dataset_schema": dataset(catalog, dataset_id)["fields"],
            "source_capture_id": capture_receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": {"rows": sum(counts.values()), "rows_by_source": counts, "overlap": overlap},
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "dataset" / "build.json").write_bytes(canonical_bytes(build_receipt))
        connection.close()
        os.replace(temporary, output)
    except Exception:
        connection.close()
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"capture": capture_receipt, "build": build_receipt}


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """Inputs unchanged, and a rebuild from them gives the same rows and the same seam."""
    if against is not None:
        raise DataError("a seamed table takes no --against directory; the overlap is checked when it is derived")
    receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    dataset_id = receipt.get("dataset_id")
    if dataset_id not in DATASET_IDS:
        raise DataError(f"not a seamed table capture: {capture_dir}")
    findings: list[str] = []
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), dataset_id):
        findings.append("catalog contract changed since the capture")
    root_dir = datasets.RUNS if root is None else root
    inputs = []
    for item in receipt["inputs"]:
        parquet = root_dir / item["run"] / "dataset" / item["parquet"]
        if not parquet.is_file() or sha256(parquet.read_bytes()) != item["sha256"]:
            findings.append(f"input run missing or changed: {item['run']}")
        inputs.append({**item, "path": parquet})
    summary: dict[str, Any] = {"seam": receipt.get("seam")}
    if dataset_dir is not None and not findings:
        connection = duckdb.connect()
        try:
            _load(connection, inputs)
            overlap = compute(dataset_id, connection)
            if overlap["seam"] != receipt.get("seam"):
                findings.append(f"a rebuild finds the seam at {overlap['seam']}, not {receipt.get('seam')}")
            _view(connection, "built", dataset_dir / f"{table_name(dataset_id)}.parquet")
            differ = connection.execute("SELECT (SELECT count(*) FROM (SELECT * FROM built EXCEPT ALL SELECT * FROM seamed))"
                                        " + (SELECT count(*) FROM (SELECT * FROM seamed EXCEPT ALL SELECT * FROM built))").fetchone()[0]
            if differ:
                findings.append(f"a rebuild from the recorded inputs differs in {differ} rows")
            summary["overlap"] = overlap
        except DataError as error:
            findings.append(str(error))
        finally:
            connection.close()
    return {"dataset_id": dataset_id, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": ["input run hashes", "overlap equality before the seam", "rebuild from inputs"], "summary": summary, "findings": findings}
