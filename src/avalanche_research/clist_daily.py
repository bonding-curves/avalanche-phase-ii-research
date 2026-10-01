"""``derived.c-chain-evm-burn-daily``: the daily EVM fees of the C-Chain, from every built Data API block list run.

It sums the blocks of each complete UTC day into the columns of ``snowflake.c-chain-evm-burn-daily``. The Data API lists
every block, so a day has no absent or short block. It reads every built block list run together, a block once, so a
daily capture need only page back two days. The capture of the block list is ``sources.clist``. This module moves to
``datasets.derived`` at restructure step M4.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, date, timedelta
from pathlib import Path
from typing import Any

import duckdb

from . import __version__, datasets
from .core.catalog import DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256
from .sources.clist import DATASET_ID, _gaps, _write
from .sources.snowflake import C_CHAIN_EVM_BURN_DAILY

DAILY_ID = "derived.c-chain-evm-burn-daily"
DATASET_IDS = (DAILY_ID,)
DAILY_TABLE = "c-chain-evm-burn-daily"
DAILY_COLUMNS = C_CHAIN_EVM_BURN_DAILY.table_columns


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    raise DataError(f"{dataset_id} is derived; use `avalanche data derive`")


def daily_rows(rows: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """One row per complete UTC day, in the share's columns. The first and last listed days are partial and left out."""
    days: dict[date, list[tuple[Any, ...]]] = {}
    for row in rows:
        days.setdefault(row[3], []).append(row)
    complete = sorted(days)[1:-1] if len(days) > 2 else []
    result = []
    for day in complete:
        blocks = days[day]
        first, last = blocks[0][0], blocks[-1][0]
        receipts = sum(row[4] for row in blocks)
        previous, following = days.get(day - timedelta(days=1)), days.get(day + timedelta(days=1))
        result.append((day, sum(row[7] for row in blocks), len(blocks), first, last, last - first + 1 - len(blocks), 0, 0,
                       previous[-1][0] if previous else None, following[0][0] if following else None, receipts, receipts, receipts, 0,
                       int(blocks[0][2].replace(tzinfo=UTC).timestamp()), int(blocks[-1][2].replace(tzinfo=UTC).timestamp())))
    return result


def union_blocks(paths: list[Path]) -> list[tuple[Any, ...]]:
    """Every block of the given block list runs once, by height. A block two runs list differently is an error."""
    blocks: dict[int, tuple[Any, ...]] = {}
    connection = duckdb.connect()
    try:
        for path in paths:
            for row in connection.execute("SELECT * FROM read_parquet(?)", [str(path)]).fetchall():
                row = (*row[:6], int(row[6]), int(row[7]))
                if blocks.setdefault(row[0], row) != row:
                    raise DataError(f"block {row[0]} differs between block list runs")
    finally:
        connection.close()
    return [blocks[height] for height in sorted(blocks)]


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    """The daily table from every built block list run, or the one pinned."""
    if dataset_id != DAILY_ID:
        raise DataError(f"{dataset_id} is captured; use `avalanche data fetch` and `build`")
    if output.exists():
        raise DataError(f"output already exists: {output}")
    pinned = pinned or {}
    if set(pinned) - {DATASET_ID}:
        raise DataError(f"the only input of {DAILY_ID} is {DATASET_ID}")
    catalog = load_catalog()
    runs = [pinned[DATASET_ID]] if DATASET_ID in pinned else [item["run"] for item in datasets.runs(DATASET_ID, root)]
    if not runs:
        raise DataError(f"no built run of {DATASET_ID}")
    inputs = []
    for run in runs:
        record = datasets.receipt(DATASET_ID, run, root)
        parquet_in = datasets.parquet_path(DATASET_ID, run, root)
        body = parquet_in.read_bytes()
        inputs.append({"input_id": "c-block-list", "dataset_id": DATASET_ID, "run": record["run"], "capture_id": record["capture"]["capture_id"],
                       "parquet": parquet_in.name, "bytes": len(body), "sha256": sha256(body), "path": parquet_in})
    blocks = union_blocks([item["path"] for item in inputs])
    rows = daily_rows(blocks)
    inputs = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    completed_at = now()
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": inputs}))
    capture_receipt = {
        "schema_version": "derived-capture/v1", "capture_id": f"capture:derived:{completed_at}:{identity[:12]}",
        "dataset_id": DAILY_ID, "source_id": "derived", "completed_at": completed_at, "contract_sha256": contract_hash(catalog, DAILY_ID),
        "tool": f"avalanche-research@{__version__}", "inputs": inputs,
        "parameters": {"rule": "complete UTC days between the first and last listed day; burned_wei is the sum of feesSpent"},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "capture").mkdir()
        (temporary / "dataset").mkdir()
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet = temporary / "dataset" / f"{DAILY_TABLE}.parquet"
        _write(parquet, DAILY_COLUMNS, rows)
        build_receipt = {
            "schema_version": "derived-build/v1", "dataset_id": DAILY_ID, "dataset_schema": dataset(catalog, DAILY_ID)["fields"],
            "source_capture_id": capture_receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": {"rows": len(rows), "first_date": str(rows[0][0]) if rows else None, "last_date": str(rows[-1][0]) if rows else None,
                        "block_list_runs": len(inputs), "missing_heights": _gaps(blocks),
                        "absent_blocks": sum(row[5] for row in rows), "burned_wei": str(sum(row[1] for row in rows))},
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "dataset" / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"capture": capture_receipt, "build": build_receipt}


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """A rebuild from the recorded input is equal, and with ``--against`` a built ``snowflake.c-chain-evm-burn-daily``,
    every day both hold has the same burn."""
    receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    findings: list[str] = []
    if receipt.get("dataset_id") != DAILY_ID:
        raise DataError(f"not a {DAILY_ID} capture: {capture_dir}")
    root_dir = datasets.RUNS if root is None else root
    paths = []
    for item in receipt["inputs"]:
        parquet_in = root_dir / item["run"] / "dataset" / item["parquet"]
        if not parquet_in.is_file() or sha256(parquet_in.read_bytes()) != item["sha256"]:
            findings.append(f"input run missing or changed: {item['run']}")
        paths.append(parquet_in)
    summary = {}
    if dataset_dir is not None:
        connection = duckdb.connect()
        try:
            built = connection.execute("SELECT * FROM read_parquet(?) ORDER BY date_utc", [str(dataset_dir / f"{DAILY_TABLE}.parquet")]).fetchall()
            if not findings:
                rebuilt = daily_rows(union_blocks(paths))
                if [tuple(map(str, row)) for row in built] != [tuple(map(str, row)) for row in rebuilt]:
                    findings.append("a rebuild from the recorded input differs")
            if against is not None:
                share = next(against.glob("*.parquet"))
                pairs = connection.execute(
                    "SELECT b.date_utc, b.burned_wei, s.burned_wei, s.absent_blocks + s.short_blocks FROM read_parquet(?) b"
                    " JOIN read_parquet(?) s USING (date_utc) ORDER BY 1", [str(dataset_dir / f"{DAILY_TABLE}.parquet"), str(share)]).fetchall()
                complete = [row for row in pairs if row[3] == 0]
                differing = [str(row[0]) for row in complete if row[1] != row[2]]
                summary["overlap"] = {"days_in_both": len(pairs), "complete_share_days": len(complete), "differing_days": differing}
                if differing:
                    findings.append(f"{len(differing)} complete share days differ in burn: {', '.join(differing)}")
        finally:
            connection.close()
    return {"dataset_id": DAILY_ID, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": ["input run hashes", "rebuild from input", *(["overlap equality with the share"] if against is not None else [])],
            "summary": summary, "findings": findings}
