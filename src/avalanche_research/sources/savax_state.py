"""The daily state of BENQI's liquid staking token sAVAX, read from its contract at the last C-Chain block of each UTC day.

sAVAX is the share token of BENQI's StakedAvax contract ``0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be``. A deposit of AVAX
mints shares, and a redemption burns them without a transfer to the zero address, so summing the token's transfers does
not give its supply: Allium's transfer table holds 46.8 million sAVAX of mints and no burns against a supply of 18.7
million on 2026-11-05. The contract's own state does. A capture reads, at each day's last block, ``totalSupply()``, the
shares outstanding, ``totalPooledAvax()``, the AVAX they claim, and ``getPooledAvaxByShares(10**18)``, the AVAX one
sAVAX redeems for, with ``eth_getBlockByNumber`` for the block's hash and time. The days and their last blocks come from
a built ``allium.c-chain-daily-last-blocks`` run named by ``blocks=<its dataset directory>``, copied into the capture
as ``raw/days.json`` and recorded in the receipt with the run's hash, from 2022-01-27, the day the contract first
minted, to the day before that run's capture. The public node answers these calls at past blocks with no
key. The calls go in JSON-RPC batches of 12, four at a time, with a pause before each, about 7,000 calls in all.

The build gives one row per day and cuts nothing. ``held_back`` marks the days from 2025-11-19, which no fit reads. The
check requires every day once, the node's block hash to equal Allium's, the block's time to fall on its day, a positive
supply, and ``totalPooledAvax / totalSupply`` to equal the per-share rate within rounding. The summary counts the days on
which the rate fell.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import urllib.error
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from .. import __version__
from ..core.catalog import DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256, source
from .capture.rest import _request

DATASET_ID = "c-chain-rpc.savax-state-daily"
SOURCE_ID = "avalanche-c-chain-rpc"
ENDPOINT_ID = "staked-avax-call"
BLOCKS_ID = "allium.c-chain-daily-last-blocks"
TABLE = "savax-state-daily"
SCHEMA = "savax-state-capture/v1"
BUILD_SCHEMA = "savax-state-build/v1"
CONTRACT = "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be"
FIRST_DAY = date(2022, 1, 27)
HELD_BACK_CUT = date(2025, 11, 19)
# Keccak-256 selectors of the three view functions. The source tests recompute them.
SUPPLY_SELECTOR = "0x18160ddd"  # totalSupply()
POOLED_SELECTOR = "0x629e8056"  # totalPooledAvax()
RATE_SELECTOR = "0x4a36d6c1"  # getPooledAvaxByShares(uint256)
ONE_SHARE = 10**18
CALLS_PER_DAY = 4
DAYS_PER_BATCH = 3
# The node takes 3 to 9 seconds to load the state of a past block, so four batches are in flight at once.
CONCURRENT_BATCHES = 4
# The node answers a slow historical call with error -32002, request timed out; the batch is sent again.
TIMED_OUT = -32002
PAUSE_SECONDS = 1.0
ATTEMPTS = 6
RETRY_SECONDS = 5.0
# The pooled AVAX over the supply against the rate of one share: both are integer divisions of the same two totals.
RATE_TOLERANCE = 1e-9
COLUMNS = {
    "date_utc": "DATE",
    "block_number": "BIGINT",
    "block_hash": "VARCHAR",
    "block_timestamp": "TIMESTAMP",
    "savax_supply_wei": "DECIMAL(38,0)",
    "pooled_avax_wei": "DECIMAL(38,0)",
    "avax_per_savax_wei": "DECIMAL(38,0)",
    "savax_supply": "DOUBLE",
    "pooled_avax": "DOUBLE",
    "avax_per_savax": "DOUBLE",
    "allium_block_hash": "VARCHAR",
    "held_back": "BOOLEAN",
}


def _endpoint(catalog: dict[str, Any] | None = None) -> str:
    provider = source(catalog or load_catalog(), SOURCE_ID)
    return next(item["url"] for item in provider["endpoints"] if item["id"] == ENDPOINT_ID)


def _blocks(parameters: dict[str, str] | None) -> dict[str, Any]:
    """The built block run named by ``blocks=<its dataset directory>``, checked against its build receipt."""
    values = parameters or {}
    if set(values) != {"blocks"}:
        raise DataError(f"the one parameter is blocks=<the dataset directory of a built {BLOCKS_ID} run>")
    directory = Path(values["blocks"])
    try:
        built = json.loads((directory / "build.json").read_text(encoding="utf-8"))
        captured = json.loads((directory.parent / "capture" / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"no built {BLOCKS_ID} run in {directory}: {error}") from error
    if built.get("dataset_id") != BLOCKS_ID or captured.get("capture_id") != built.get("source_capture_id"):
        raise DataError(f"{directory} is not a built {BLOCKS_ID} run")
    output = built["outputs"][0]
    parquet = directory / output["path"]
    body = parquet.read_bytes()
    if len(body) != output["bytes"] or sha256(body) != output["sha256"]:
        raise DataError(f"block run Parquet differs from its build receipt: {parquet}")
    return {"dataset_id": BLOCKS_ID, "run": directory.parent.name, "capture_id": captured["capture_id"],
            "captured_at": captured["completed_at"], "parquet": parquet.name, "sha256": output["sha256"], "path": parquet}


def _days(blocks: dict[str, Any]) -> list[list[Any]]:
    """The days from the first mint to the day before the block run's capture, each with its last block and hash."""
    last_day = datetime.strptime(blocks["captured_at"], "%Y-%m-%dT%H:%M:%SZ").date() - timedelta(days=1)
    rows = duckdb.connect().execute(
        "SELECT date_utc, last_block_number, last_block_hash FROM read_parquet(?) WHERE date_utc BETWEEN ? AND ? ORDER BY 1",
        [str(blocks["path"]), FIRST_DAY, last_day]).fetchall()
    expected = (last_day - FIRST_DAY).days + 1
    if len(rows) != expected:
        raise DataError(f"the block run holds {len(rows)} of the {expected} days from {FIRST_DAY} to {last_day}")
    return [[str(day), height, block_hash] for day, height, block_hash in rows]


def calls(index: int, height: int) -> list[dict[str, Any]]:
    """The four calls for one day, numbered from ``index * CALLS_PER_DAY``."""
    at = hex(height)
    base = index * CALLS_PER_DAY

    def call(offset: int, data: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": base + offset, "method": "eth_call", "params": [{"to": CONTRACT, "data": data}, at]}

    return [
        {"jsonrpc": "2.0", "id": base, "method": "eth_getBlockByNumber", "params": [at, False]},
        call(1, SUPPLY_SELECTOR),
        call(2, POOLED_SELECTOR),
        call(3, RATE_SELECTOR + ONE_SHARE.to_bytes(32, "big").hex()),
    ]


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    blocks = _blocks(parameters)
    days = _days(blocks)
    return {
        "dataset_id": DATASET_ID, "source_id": SOURCE_ID, "output": str(output), "endpoint": _endpoint(),
        "contract": CONTRACT, "blocks_run": blocks["run"], "days": len(days), "first_day": str(days[0][0]),
        "last_day": str(days[-1][0]), "calls": len(days) * CALLS_PER_DAY, "pause_seconds": PAUSE_SECONDS,
        "writes": ["raw/days.json", "raw/batch-*.json", "capture.json"], "overwrite": False,
    }


class _TimedOut(DataError):
    """The node timed out on a call of the batch."""


def _batch(body: bytes, payloads: list[dict[str, Any]]) -> dict[int, Any]:
    value = json.loads(body)
    if not isinstance(value, list):
        raise DataError(f"invalid batch response: {body[:200]!r}")
    results = {item.get("id"): item for item in value if isinstance(item, dict)}
    wanted = [payload["id"] for payload in payloads]
    if sorted(results) != sorted(wanted) or len(value) != len(wanted):
        raise DataError("a batch response does not answer each call once")
    for index in wanted:
        item = results[index]
        error = item.get("error")
        if isinstance(error, dict) and error.get("code") == TIMED_OUT:
            raise _TimedOut(f"call {index} timed out at the node")
        if error or "result" not in item:
            raise DataError(f"call {index} failed: {error}")
    return {index: results[index]["result"] for index in wanted}


def capture(dataset_id: str, output: Path, timeout: float = 20, parameters: dict[str, str] | None = None,
            request: Callable[..., tuple[bytes, dict[str, Any]]] = _request,
            sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    preview = capture_preview(dataset_id, output, parameters)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    blocks = _blocks(parameters)
    days = _days(blocks)
    endpoint = preview["endpoint"]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    records: list[dict[str, Any]] = []
    retries = 0
    try:
        (temporary / "raw").mkdir()
        days_body = canonical_bytes(days)
        (temporary / "raw" / "days.json").write_bytes(days_body)
        retry_count = [0]

        def send(offset: int) -> dict[str, Any]:
            payloads = [item for index in range(offset, min(len(days), offset + DAYS_PER_BATCH)) for item in calls(index, days[index][1])]
            sleep(PAUSE_SECONDS)
            for attempt in range(1, ATTEMPTS + 1):
                try:
                    body, metadata = request(endpoint, timeout, body_json=payloads, content="json-list")
                    _batch(body, payloads)
                    break
                except DataError as error:
                    retryable = isinstance(error, _TimedOut) or isinstance(error.__cause__, (OSError, urllib.error.URLError))
                    if attempt == ATTEMPTS or not retryable:
                        raise
                    retry_count[0] += 1
                    sleep(RETRY_SECONDS * 2 ** (attempt - 1))
            relative = Path("raw") / f"batch-{offset:05d}.json"
            (temporary / relative).write_bytes(body)
            return {"request_json": payloads, "url": endpoint, "path": str(relative), "bytes": len(body),
                    "sha256": sha256(body), **metadata}

        # A past block costs the node seconds to load, so a few batches go at once; the receipt keeps batch order.
        with ThreadPoolExecutor(max_workers=CONCURRENT_BATCHES) as pool:
            records.extend(pool.map(send, range(0, len(days), DAYS_PER_BATCH)))
        retries = retry_count[0]
        completed_at = now()
        identity = sha256(canonical_bytes({"completed_at": completed_at, "responses": records}))
        receipt = {
            "schema_version": SCHEMA,
            "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
            "dataset_id": DATASET_ID,
            "source_id": SOURCE_ID,
            "completed_at": completed_at,
            "contract_sha256": contract_hash(load_catalog(), DATASET_ID),
            "tool": f"avalanche-research@{__version__}",
            "contract": CONTRACT,
            "blocks_input": {key: value for key, value in blocks.items() if key != "path"},
            "days_path": "raw/days.json",
            "days_sha256": sha256(days_body),
            "first_day": str(days[0][0]),
            "last_day": str(days[-1][0]),
            "days": len(days),
            "calls": len(days) * CALLS_PER_DAY,
            "retries": retries,
            "responses": records,
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        os.replace(temporary, output)
        return receipt
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _read_receipt(capture_dir: Path) -> dict[str, Any]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid sAVAX capture: {error}") from error
    if receipt.get("schema_version") != SCHEMA or receipt.get("dataset_id") != DATASET_ID:
        raise DataError("unsupported sAVAX capture")
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), DATASET_ID):
        raise DataError("sAVAX capture contract hash differs")
    return receipt


def _word(value: Any, label: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x") or len(value) != 66:
        raise DataError(f"{label} is not one 32-byte word")
    return int(value, 16)


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    """Every row of the capture, after each raw response is checked against its hash and its request, and the requests
    against the days and last blocks the capture copied from its block run."""
    receipt = _read_receipt(capture_dir)
    try:
        days_body = (capture_dir / "raw" / "days.json").read_bytes()
        days = json.loads(days_body)
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"sAVAX capture lacks its day list: {error}") from error
    if sha256(days_body) != receipt.get("days_sha256") or len(days) != receipt.get("days"):
        raise DataError("sAVAX capture day list differs from its receipt")
    endpoint = _endpoint()
    results: dict[int, Any] = {}
    for position, record in enumerate(receipt.get("responses", [])):
        path = Path(record["path"])
        if path.is_absolute() or ".." in path.parts or path.parts[0] != "raw":
            raise DataError("sAVAX capture has an unsafe raw path")
        try:
            body = (capture_dir / path).read_bytes()
        except OSError as error:
            raise DataError(f"missing sAVAX response {position}") from error
        if len(body) != record["bytes"] or sha256(body) != record["sha256"] or record["url"] != endpoint:
            raise DataError(f"sAVAX response {position} hash or size differs")
        payloads = record["request_json"]
        for item in payloads:
            index = item["id"] // CALLS_PER_DAY
            if index >= len(days) or item != calls(index, days[index][1])[item["id"] % CALLS_PER_DAY]:
                raise DataError(f"call {item.get('id')} is not the recorded call for its day")
        for key, value in _batch(body, payloads).items():
            if key in results:
                raise DataError(f"call {key} is answered twice")
            results[key] = value
    if sorted(results) != list(range(len(days) * CALLS_PER_DAY)):
        raise DataError(f"sAVAX capture answers {len(results)} of {len(days) * CALLS_PER_DAY} calls")
    rows = []
    for index, (day_text, height, allium_hash) in enumerate(days):
        day = date.fromisoformat(day_text)
        block = results[index * CALLS_PER_DAY]
        if not isinstance(block, dict) or int(block.get("number", "0x0"), 16) != height:
            raise DataError(f"the node returned another block for {day}")
        supply = _word(results[index * CALLS_PER_DAY + 1], f"totalSupply on {day}")
        pooled = _word(results[index * CALLS_PER_DAY + 2], f"totalPooledAvax on {day}")
        rate = _word(results[index * CALLS_PER_DAY + 3], f"getPooledAvaxByShares on {day}")
        stamp = datetime.fromtimestamp(int(block["timestamp"], 16), UTC).replace(tzinfo=None)
        rows.append((day, height, block.get("hash"), stamp, Decimal(supply), Decimal(pooled), Decimal(rate),
                     supply / ONE_SHARE, pooled / ONE_SHARE, rate / ONE_SHARE, allium_hash, day >= HELD_BACK_CUT))
    return receipt, rows


def _load(connection: Any, rows: list[tuple[Any, ...]]) -> None:
    connection.execute(f"CREATE OR REPLACE TABLE rows({', '.join(f'{name} {kind}' for name, kind in COLUMNS.items())})")
    connection.executemany(f"INSERT INTO rows VALUES ({', '.join('?' for _ in COLUMNS)})", rows)


def summarize(connection: Any, table: str = "rows") -> dict[str, Any]:
    count, first, last, falls, largest_fall, held = connection.execute(f"""
        WITH r AS (SELECT date_utc, avax_per_savax, avax_per_savax / lag(avax_per_savax) OVER (ORDER BY date_utc) - 1 AS change
                   FROM {table})
        SELECT (SELECT count(*) FROM {table}), min(date_utc), max(date_utc), count_if(change < 0), min(change),
               (SELECT count_if(held_back) FROM {table})
        FROM r""").fetchone()
    end = connection.execute(
        f"SELECT savax_supply, pooled_avax, avax_per_savax FROM {table} WHERE date_utc < ? ORDER BY date_utc DESC LIMIT 1",
        [HELD_BACK_CUT]).fetchone()
    return {"rows": count, "first": str(first), "last": str(last), "held_back_days": held, "rate_falls": falls,
            "largest_rate_fall": None if largest_fall is None or largest_fall >= 0 else round(largest_fall, 9),
            "before_cut": None if end is None else {"day": str(HELD_BACK_CUT - timedelta(days=1)), "savax_supply": round(end[0], 3),
                                                    "pooled_avax": round(end[1], 3), "avax_per_savax": round(end[2], 9)}}


def findings_of(connection: Any, table: str = "rows") -> list[str]:
    repeats, hashes, off_day, empty, rate = connection.execute(f"""
        SELECT count(*) - count(DISTINCT date_utc), count_if(block_hash IS DISTINCT FROM allium_block_hash),
               count_if(block_timestamp::DATE <> date_utc), count_if(savax_supply_wei <= 0 OR pooled_avax_wei <= 0),
               count_if(abs(pooled_avax / savax_supply - avax_per_savax) > {RATE_TOLERANCE} * avax_per_savax)
        FROM {table}""").fetchone()
    labels = ((repeats, "days repeat"), (hashes, "days read a block whose hash differs from Allium's"),
              (off_day, "days read a block from another day"), (empty, "days have no supply or no pooled AVAX"),
              (rate, "days have pooled AVAX over supply off the rate of one share"))
    return [f"{count} {label}" for count, label in labels if count]


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output),
            "writes": [f"{TABLE}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    build_preview(dataset_id, capture_dir, output)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    receipt, rows = read_rows(capture_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet = temporary / f"{TABLE}.parquet"
        connection = duckdb.connect()
        try:
            _load(connection, rows)
            connection.execute("COPY (SELECT * FROM rows ORDER BY date_utc) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
            summary = summarize(connection)
        finally:
            connection.close()
        result = {
            "schema_version": BUILD_SCHEMA, "dataset_id": DATASET_ID, "dataset_schema": dataset(load_catalog(), DATASET_ID)["fields"],
            "source_capture_id": receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": summary,
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(result))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return result


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    if against is not None:
        raise DataError(f"{DATASET_ID} takes no --against directory")
    receipt, rows = read_rows(capture_dir)
    checked = ["response hashes", "requests against the recorded block run", "every day once", "block hash against Allium's",
               "block time on its day", "positive supply", "pooled AVAX over supply against the rate of one share"]
    connection = duckdb.connect()
    try:
        _load(connection, rows)
        findings = findings_of(connection)
        summary = summarize(connection)
        if dataset_dir is not None:
            checked.extend(["build hashes", "Parquet rows"])
            try:
                built = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
                if built.get("source_capture_id") != receipt["capture_id"]:
                    findings.append("build does not belong to this capture")
                for item in built["outputs"]:
                    body = (dataset_dir / item["path"]).read_bytes()
                    if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                        findings.append(f"output hash or size differs: {item['path']}")
                parquet = str(dataset_dir / f"{TABLE}.parquet")
                schema = [(row[0], row[1]) for row in connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [parquet]).fetchall()]
                if schema != list(COLUMNS.items()):
                    findings.append("Parquet schema differs from the dataset contract")
                elif connection.execute(
                        "SELECT (SELECT count(*) FROM (SELECT * FROM rows EXCEPT ALL SELECT * FROM read_parquet(?)))"
                        " + (SELECT count(*) FROM (SELECT * FROM read_parquet(?) EXCEPT ALL SELECT * FROM rows))",
                        [parquet, parquet]).fetchone()[0]:
                    findings.append("Parquet rows differ from the captured responses")
            except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
                findings.append(f"invalid dataset output: {error}")
    finally:
        connection.close()
    return {"dataset_id": DATASET_ID, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}
