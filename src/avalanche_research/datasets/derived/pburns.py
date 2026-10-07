"""P- and X-Chain burns per UTC day from the nodes' own blocks: a second source for ``snowflake.primary-burn-daily``.

A transaction burns the AVAX it consumes less the AVAX it creates: inputs and imported inputs, less outputs, exported
outputs, and staked outputs. The three P-Chain transactions that fund an L1 validator balance carry that deposit in the
difference; it is subtracted and reported apart, as in the share, because it is consumed later as the continuous L1
validator fee. That fee is the earlier active L1 validator count times the rise in the fee each has accrued, between
consecutive P-Chain blocks that hold a transaction, from the Data API's block list, dated by the later block. The share
reads the counters at transactions, so blocks without one are skipped; reading every block instead differs by at most
0.0003 AVAX a day over 2026-09-15 to 2026-09-21, from active counts that change at blocks without transactions. The node's own record settles every
transaction, so all count as recorded, as in the share, where ``RewardValidatorTx`` carries a recorded burn of zero.

A day is in the table when both walks and the block list cover all of it: a source that starts after midnight covers
from the next day, which is conservative for a walk that started at a day's first block.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import date, time, timedelta
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
from ...sources.snowflake import PRIMARY_BURN_DAILY

DATASET_ID = "derived.primary-burn-daily"
DATASET_IDS = (DATASET_ID,)
SOURCE_ID = "derived"
TABLE = "primary-burn-daily"
COLUMNS = PRIMARY_BURN_DAILY.table_columns
INPUTS = {"p-chain-blocks": "p-chain-rpc.blocks", "x-chain-blocks": "x-chain-rpc.blocks", "p-block-list": "data-api.p-chain-block-list"}


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    raise DataError(f"{dataset_id} is derived; use `avalanche data derive`")


capture = build_preview = build = capture_preview


def l1_balance(tx_type: str, unsigned: dict[str, Any]) -> int:
    """The AVAX a transaction deposits into L1 validator balances."""
    if tx_type in ("RegisterL1ValidatorTx", "IncreaseL1ValidatorBalanceTx"):
        return int(unsigned["balance"])
    if tx_type == "ConvertSubnetToL1Tx":
        return sum(int(validator["balance"]) for validator in unsigned["validators"])
    return 0


def _select(pinned: dict[str, str] | None, root: Path | None) -> list[dict[str, Any]]:
    pinned = pinned or {}
    unknown = sorted(set(pinned) - set(INPUTS.values()))
    if unknown:
        raise DataError(f"not an input of {DATASET_ID}: {', '.join(unknown)}")
    inputs = []
    for input_id, dataset_id in INPUTS.items():
        record = datasets.receipt(dataset_id, pinned.get(dataset_id), root)
        parquet = datasets.parquet_path(dataset_id, record["run"], root)
        body = parquet.read_bytes()
        inputs.append({"input_id": input_id, "dataset_id": dataset_id, "run": record["run"], "capture_id": record["capture"]["capture_id"],
                       "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet})
    return inputs


def compute(inputs: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    paths = {item["input_id"]: str(item["path"]) for item in inputs}
    connection = duckdb.connect()
    try:
        transactions = {chain: connection.execute(
            "SELECT block_time, tx_type, input_navax, output_navax, staked_navax, unsigned_tx, transaction_hash FROM read_parquet(?)"
            " WHERE transaction_hash IS NOT NULL ORDER BY block_height, tx_index", [paths[key]]).fetchall()
            for chain, key in (("P", "p-chain-blocks"), ("X", "x-chain-blocks"))}
        spans = {chain: connection.execute("SELECT min(block_time), max(block_time) FROM read_parquet(?)", [paths[key]]).fetchone()
                 for chain, key in (("P", "p-chain-blocks"), ("X", "x-chain-blocks"))}
        counters = connection.execute(
            "SELECT block_timestamp, active_l1_validators, l1_validators_accrued_fees_navax FROM read_parquet(?) WHERE transactions > 0"
            " ORDER BY block_height",
            [paths["p-block-list"]]).fetchall()
    finally:
        connection.close()
    # Whole days only. A source that starts at midnight covers its first day; one that starts later covers from the next.
    starts = (spans["P"][0], spans["X"][0], counters[0][0])
    first = max(start.date() if start.time() == time() else start.date() + timedelta(days=1) for start in starts)
    last = min(spans["P"][1], spans["X"][1], counters[-1][0]).date() - timedelta(days=1)
    days: dict[tuple[date, str], dict[str, Any]] = {}
    for chain, rows in transactions.items():
        for block_time, tx_type, input_navax, output_navax, staked_navax, unsigned_json, tx_hash in rows:
            day = block_time.date()
            if not first <= day <= last:
                continue
            item = days.setdefault((day, chain), {"transactions": 0, "burned": 0, "recorded": 0, "system": 0, "l1": 0})
            item["transactions"] += 1
            deposit = l1_balance(tx_type, json.loads(unsigned_json)) if chain == "P" else 0
            burned = input_navax - output_navax - staked_navax - deposit
            if burned < 0:
                raise DataError(f"{chain}-Chain transaction {tx_hash} creates more AVAX than it consumes")
            item["burned"] += burned
            item["recorded"] += 1
            item["l1"] += deposit
    fees: dict[date, int] = {}
    for (_, count, accrued), (stamp, _, later) in pairwise(counters):
        fees[stamp.date()] = fees.get(stamp.date(), 0) + count * (later - accrued)
    rows_out = []
    day = first
    while day <= last:
        for chain in ("P", "X"):
            item = days.get((day, chain), {"transactions": 0, "burned": 0, "recorded": 0, "system": 0, "l1": 0})
            rows_out.append((day, chain, item["transactions"], item["burned"], item["recorded"], item["system"], 0, 0, 0, None,
                             item["l1"], fees.get(day, 0) if chain == "P" else 0))
        day += timedelta(days=1)
    return rows_out


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    inputs = _select(pinned, root)
    rows = compute(inputs)
    if not rows:
        raise DataError("the walks and the block list share no whole UTC day")
    completed_at = now()
    records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records}))
    capture_receipt = {
        "schema_version": "derived-capture/v1", "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
        "dataset_id": DATASET_ID, "source_id": SOURCE_ID, "completed_at": completed_at, "contract_sha256": contract_hash(catalog, DATASET_ID),
        "tool": f"avalanche-research@{__version__}", "inputs": records,
        "parameters": {"burn_rule": "inputs and imported inputs less outputs, exported outputs, staked outputs, and L1 balance deposits",
                       "l1_fee_rule": "earlier active L1 validator count times the rise in accrued fees between consecutive P-Chain blocks holding a transaction, dated by the later block"},
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
            connection.execute(f"CREATE TABLE rows({', '.join(f'{name} {kind}' for name, kind in COLUMNS.items())})")
            connection.executemany(f"INSERT INTO rows VALUES ({', '.join('?' for _ in COLUMNS)})", rows)
            connection.execute("COPY (SELECT * FROM rows ORDER BY date_utc, chain) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "derived-build/v1", "dataset_id": DATASET_ID, "dataset_schema": dataset(catalog, DATASET_ID)["fields"],
            "source_capture_id": capture_receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": {"rows": len(rows), "first_date": str(rows[0][0]), "last_date": str(rows[-1][0]),
                        "burned_navax": {chain: sum(row[3] for row in rows if row[1] == chain) for chain in ("P", "X")},
                        "l1_validator_fees_navax": sum(row[11] for row in rows)},
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "dataset" / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"capture": capture_receipt, "build": build_receipt}


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """Inputs unchanged and a rebuild equal. With ``--against`` a built ``snowflake.primary-burn-daily``: every date and chain
    both hold has the same burn, L1 deposit, and L1 fee."""
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
    if dataset_dir is not None:
        built_path = dataset_dir / f"{TABLE}.parquet"
        connection = duckdb.connect()
        try:
            built = connection.execute("SELECT * FROM read_parquet(?) ORDER BY date_utc, chain", [str(built_path)]).fetchall()
            if not findings and [tuple(row) for row in built] != compute(inputs):
                findings.append("a rebuild from the recorded inputs differs")
            if against is not None:
                share = next(against.glob("*.parquet"))
                pairs = connection.execute(
                    "SELECT b.date_utc, b.chain, b.burned_navax, s.burned_navax, b.l1_balance_deposited_navax, s.l1_balance_deposited_navax,"
                    " b.l1_validator_fees_navax, s.l1_validator_fees_navax, s.unresolved_transactions, b.transactions, s.transactions"
                    " FROM read_parquet(?) b JOIN read_parquet(?) s USING (date_utc, chain) ORDER BY 1, 2", [str(built_path), str(share)]).fetchall()
                differing = [f"{row[0]} {row[1]}" for row in pairs if row[8] == 0 and (row[2], row[4], row[6]) != (row[3], row[5], row[7])]
                summary["overlap"] = {"rows_in_both": len(pairs), "differing": differing,
                                      "differences": [{"date": str(row[0]), "chain": row[1], "burn": [row[2], row[3]], "l1_deposit": [row[4], row[5]],
                                                       "l1_fee": [row[6], row[7]], "transactions": [row[9], row[10]]}
                                                      for row in pairs if f"{row[0]} {row[1]}" in differing]}
                if differing:
                    findings.append(f"{len(differing)} dates and chains differ from the share: {', '.join(differing)}")
        finally:
            connection.close()
    return {"dataset_id": DATASET_ID, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": ["input run hashes", "rebuild from inputs", *(["overlap equality with the share"] if against is not None else [])],
            "summary": summary, "findings": findings}
