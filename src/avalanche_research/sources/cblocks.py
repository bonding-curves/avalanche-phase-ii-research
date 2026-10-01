"""Capture the fees of the C-Chain blocks the Snowflake share cannot account for, from either of two sources.

The share's C block gaps dataset lists the heights: absent blocks and blocks present without all their receipts.
``data-api.c-chain-block-fees`` reads each block's Data API record, whose ``feesSpent`` is an integer number of wei
equal to the sum of gas used times effective gas price over the block's receipts (checked 2026-09-23 against the
share on complete blocks). ``c-chain-rpc.block-receipt-fees`` reads the block header and every receipt from a public
C-Chain JSON-RPC node in one batch and computes that sum itself, after checking that the receipts are the header's:
one per transaction, each carrying the block's hash, their gas adding to the header's. The two agree to the wei on
every block both hold. One record is one JSON line written as it arrives, so a walk over many thousand blocks shows
its progress on disk, retries a refused request, keeps its lines on failure, and continues with
``resume=<kept directory>``.
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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from .. import __version__
from ..core.catalog import DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256, source
from .capture.rest import _request

DATASET_ID = "data-api.c-chain-block-fees"
SOURCE_ID = "avalanche-data-api"
ENDPOINT_ID = "c-chain-block"
RPC_DATASET_ID = "c-chain-rpc.block-receipt-fees"
RPC_SOURCE_ID = "tenderly-c-chain-rpc"
RPC_ENDPOINT_ID = "block-and-receipts"
# The Data API record walk, and the node's header and receipts in one JSON-RPC batch.
SPECS = {
    DATASET_ID: {"source_id": SOURCE_ID, "endpoint_id": ENDPOINT_ID, "table": "c-chain-block-fees"},
    RPC_DATASET_ID: {"source_id": RPC_SOURCE_ID, "endpoint_id": RPC_ENDPOINT_ID, "table": "c-chain-block-receipt-fees"},
}
GAPS_ID = "snowflake.c-chain-block-gaps"
# The command line resolves the gaps run to a reading (datasets.readings), so a capture reads no dataset code.
READS = {"gaps": GAPS_ID}
TABLE = "c-chain-block-fees"
PROGRESS = "progress.jsonl"
RAW = "raw/blocks.jsonl"
PAGE_ATTEMPTS = 8
PAGE_RETRY_SECONDS = 5.0
MAX_BLOCKS = 250_000
MAX_WORKERS = 16
COLUMNS = {
    "block_height": "BIGINT",
    "block_hash": "VARCHAR",
    "block_timestamp": "TIMESTAMP",
    "date_utc": "DATE",
    "transactions": "INTEGER",
    "gas_used": "BIGINT",
    "base_fee_wei": "DECIMAL(38,0)",
    "fees_wei": "DECIMAL(38,0)",
}


def _parameters(parameters: dict[str, str] | None) -> dict[str, Any]:
    values = dict(parameters or {})
    unknown = set(values) - {"gaps", "kind", "limit", "pause", "resume", "workers"}
    if unknown:
        raise DataError(f"unknown parameters: {', '.join(sorted(unknown))}")
    if not values.get("gaps"):
        raise DataError("provide gaps=<built run of snowflake.c-chain-block-gaps> naming the blocks to read")
    kind = values.get("kind", "all")
    if kind not in {"all", "absent", "short"}:
        raise DataError("kind must be all, absent, or short")
    try:
        limit = int(values.get("limit", MAX_BLOCKS))
        pause = float(values.get("pause", 0))
        workers = int(values.get("workers", 1))
    except ValueError as error:
        raise DataError("limit and workers must be integers and pause seconds") from error
    if not 1 <= limit <= MAX_BLOCKS or not 0 <= pause <= 60 or not 1 <= workers <= MAX_WORKERS:
        raise DataError(f"limit must be between 1 and {MAX_BLOCKS}; pause between 0 and 60 seconds; workers between 1 and {MAX_WORKERS}")
    return {"gaps": values["gaps"], "kind": kind, "limit": limit, "pause": pause, "workers": workers, **({"resume": values["resume"]} if values.get("resume") else {})}


def _spec(dataset_id: str) -> dict[str, Any]:
    if dataset_id not in SPECS:
        raise DataError(f"unknown dataset: {dataset_id}")
    return SPECS[dataset_id]


def _endpoint(catalog: dict[str, Any], dataset_id: str = DATASET_ID) -> str:
    spec = _spec(dataset_id)
    provider = source(catalog, spec["source_id"])
    return next(item["url"] for item in provider["endpoints"] if item["id"] == spec["endpoint_id"])


def _batch(height: int) -> list[dict[str, Any]]:
    return [
        {"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber", "params": [hex(height), False]},
        {"jsonrpc": "2.0", "id": 2, "method": "eth_getBlockReceipts", "params": [hex(height)]},
    ]


def _reading(values: dict[str, Any], readings: dict[str, dict[str, Any]] | None) -> dict[str, Any]:
    reading = (readings or {}).get("gaps")
    if reading is None or reading["run"] != values["gaps"]:
        raise DataError(f"the gaps run {values['gaps']} was not resolved; fetch it through `avalanche data fetch`")
    return reading


def gap_heights(reading: dict[str, Any], kind: str) -> list[int]:
    """The heights a gaps run lists, ascending."""
    parquet = reading["parquet"]
    connection = duckdb.connect()
    try:
        clause = "" if kind == "all" else f"WHERE kind = '{kind}'"
        heights = [row[0] for row in connection.execute(f"SELECT DISTINCT block_height FROM read_parquet(?) {clause} ORDER BY 1", [str(parquet)]).fetchall()]
    finally:
        connection.close()
    return heights


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None,
                    readings: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    spec = _spec(dataset_id)
    values = _parameters(parameters)
    reading = _reading(values, readings)
    heights = gap_heights(reading, values["kind"])
    return {
        "dataset_id": dataset_id,
        "source_id": spec["source_id"],
        "output": str(output),
        "endpoint": _endpoint(load_catalog(), dataset_id),
        "gaps_run": values["gaps"],
        "gaps_capture_id": reading["capture_id"],
        "kind": values["kind"],
        "blocks": len(heights),
        "limit": values["limit"],
        "pause": values["pause"],
        "workers": values["workers"],
        **({"resume": values["resume"]} if "resume" in values else {}),
        "writes": [RAW, "capture.json"],
        "overwrite": False,
    }


def _resume(preview: dict[str, Any], temporary: Path) -> list[dict[str, Any]]:
    try:
        lines = (temporary / PROGRESS).read_text(encoding="utf-8").splitlines()
        header, records = json.loads(lines[0]), [json.loads(line) for line in lines[1:]]
    except (OSError, IndexError, json.JSONDecodeError) as error:
        raise DataError(f"cannot resume from {temporary}: {error}") from error
    if header.get("gaps_capture_id") != preview["gaps_capture_id"] or header.get("kind") != preview["kind"] or header.get("endpoint") != preview["endpoint"]:
        raise DataError("cannot resume: the kept walk reads different blocks or a different endpoint")
    raw = temporary / RAW
    try:
        bodies = raw.read_bytes().splitlines()
    except OSError as error:
        raise DataError("cannot resume: the kept walk has no block lines") from error
    # A walk stopped between writing a line and its record leaves one file longer than the other. Keep the longest
    # prefix where each line matches its record, and cut both files back to it.
    kept = 0
    for record, body in zip(records, bodies):
        if sha256(body) != record["sha256"] or len(body) != record["bytes"]:
            break
        kept += 1
    if kept < min(len(records), len(bodies)):
        raise DataError(f"cannot resume: block line {kept + 1} differs from its record")
    if kept != len(records) or kept != len(bodies):
        raw.write_bytes(b"".join(body + b"\n" for body in bodies[:kept]))
        (temporary / PROGRESS).write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in [header, *records[:kept]]), encoding="utf-8")
    return records[:kept]


def capture(
    dataset_id: str,
    output: Path,
    timeout: float = 20,
    parameters: dict[str, str] | None = None,
    request: Callable[..., tuple[bytes, dict[str, Any]]] = _request,
    readings: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    preview = capture_preview(dataset_id, output, parameters, readings)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    heights = gap_heights(_reading(_parameters(parameters), readings), preview["kind"])
    output.parent.mkdir(parents=True, exist_ok=True)
    if "resume" in preview:
        temporary = Path(preview["resume"])
        records = _resume(preview, temporary)
    else:
        temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
        (temporary / "raw").mkdir()
        header = {key: preview[key] for key in ("endpoint", "gaps_capture_id", "kind")}
        (temporary / PROGRESS).write_text(json.dumps(header, sort_keys=True) + "\n", encoding="utf-8")
        (temporary / RAW).write_bytes(b"")
        records = []
    done = {record["block_height"] for record in records}
    todo = [height for height in heights if height not in done][: max(0, preview["limit"] - len(records))]
    retries = 0

    rpc = dataset_id == RPC_DATASET_ID

    def fetch(height: int) -> tuple[int, bytes, dict[str, Any], int]:
        """One block record, retried with a doubling wait when the API refuses or drops the request."""
        url = preview["endpoint"] if rpc else f"{preview['endpoint']}/{height}"
        for attempt in range(1, PAGE_ATTEMPTS + 1):
            try:
                body, metadata = request(url, timeout, body_json=_batch(height), content="json-list") if rpc else request(url, timeout)
                return height, body, metadata, attempt - 1
            except DataError as error:
                # Keyless, the Data API refuses for minutes after about a thousand requests; with a key it allows about
                # 750 block requests a minute. Wait, doubling, up to about ten minutes in all, then keep the lines.
                if attempt == PAGE_ATTEMPTS or not isinstance(error.__cause__, (OSError, urllib.error.URLError)):
                    raise
                time.sleep(PAGE_RETRY_SECONDS * 2 ** (attempt - 1))
        raise AssertionError("unreachable")

    def url_of(height: int) -> str:
        return preview["endpoint"] if rpc else f"{preview['endpoint']}/{height}"

    try:
        batch_size = preview["workers"] * 8
        with (temporary / RAW).open("ab") as raw, (temporary / PROGRESS).open("a", encoding="utf-8") as progress, \
                ThreadPoolExecutor(max_workers=preview["workers"]) as pool:
            for offset in range(0, len(todo), batch_size):
                if preview["pause"] and offset:
                    time.sleep(preview["pause"])
                # map yields in height order and raises at the first block that failed, so everything before it is
                # written and the lines on disk stay an ascending prefix a resume can continue.
                results = pool.map(fetch, todo[offset: offset + batch_size])
                while True:
                    try:
                        height, body, metadata, retried = next(results)
                    except StopIteration:
                        break
                    except DataError as error:
                        raw.flush()
                        progress.flush()
                        raise DataError(f"{error}; {len(records)} blocks kept at {temporary}") from error
                    retries += retried
                    line = body.strip()
                    if b"\n" in line:
                        line = json.dumps(json.loads(body), separators=(",", ":"), sort_keys=True).encode()
                    try:
                        _row(dataset_id, json.loads(line), height)
                    except DataError as error:
                        raise DataError(f"{error}; {len(records)} blocks kept at {temporary}") from error
                    raw.write(line + b"\n")
                    record = {"block_height": height, "url": url_of(height), "bytes": len(line), "sha256": sha256(line), **metadata}
                    records.append(record)
                    progress.write(json.dumps(record, sort_keys=True) + "\n")
                raw.flush()
                progress.flush()
        if not records:
            raise DataError("the gaps run lists no blocks of that kind")
        completed_at = now()
        identity = sha256(canonical_bytes({"completed_at": completed_at, "responses": records}))
        body_all = (temporary / RAW).read_bytes()
        spec = _spec(dataset_id)
        receipt = {
            "schema_version": f"{spec['source_id']}-capture/v1",
            "capture_id": f"capture:{spec['source_id']}:{completed_at}:{identity[:12]}",
            "dataset_id": dataset_id,
            "source_id": spec["source_id"],
            "completed_at": completed_at,
            "contract_sha256": contract_hash(catalog, dataset_id),
            "tool": f"avalanche-research@{__version__}",
            "gaps_run": preview["gaps_run"],
            "gaps_capture_id": preview["gaps_capture_id"],
            "kind": preview["kind"],
            "blocks_listed": preview["blocks"],
            "retries": retries,
            "responses": [{"endpoint_id": spec["endpoint_id"], "path": RAW, "blocks": len(records), "bytes": len(body_all), "sha256": sha256(body_all)}],
            "blocks": records,
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        (temporary / PROGRESS).unlink()
        os.replace(temporary, output)
        return receipt
    except Exception:
        if not (temporary / RAW).exists() or (temporary / RAW).stat().st_size == 0:
            shutil.rmtree(temporary, ignore_errors=True)
        raise


def _integer(value: Any, label: str, height: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise DataError(f"block {height} has no integer {label}") from error
    if number < 0:
        raise DataError(f"block {height} has a negative {label}")
    return number


def _row(dataset_id: str, value: Any, height: int) -> tuple[Any, ...]:
    """(height, hash, timestamp, date, transactions, gas used, base fee, fees) from one captured line."""
    if dataset_id == DATASET_ID:
        if _integer(value.get("blockNumber"), "height", height) != height:
            raise DataError(f"the Data API answered block {value.get('blockNumber')} for {height}")
        timestamp = datetime.fromtimestamp(_integer(value.get("blockTimestamp"), "timestamp", height), UTC).replace(tzinfo=None)
        return (height, value.get("blockHash"), timestamp, timestamp.date(),
                _integer(value.get("txCount"), "transaction count", height), _integer(value.get("gasUsed"), "gas used", height),
                _integer(value.get("baseFee"), "base fee", height), _integer(value.get("feesSpent"), "fees spent", height))
    answers = {item.get("id"): item for item in value} if isinstance(value, list) else {}
    if set(answers) != {1, 2} or any("error" in item or item.get("result") is None for item in answers.values()):
        raise DataError(f"the node did not answer both calls for block {height}")
    block, receipts = answers[1]["result"], answers[2]["result"]
    if _hex(block.get("number"), "height", height) != height or not isinstance(receipts, list):
        raise DataError(f"the node answered another block for {height}")
    if len(receipts) != len(block.get("transactions") or []) or any(item.get("blockHash") != block.get("hash") for item in receipts):
        raise DataError(f"the receipts of block {height} are not the header's transactions")
    gas = [_hex(item.get("gasUsed"), "receipt gas", height) for item in receipts]
    if sum(gas) != _hex(block.get("gasUsed"), "gas used", height):
        raise DataError(f"the receipts of block {height} do not add to the header's gas")
    fees = sum(used * _hex(item.get("effectiveGasPrice"), "effective gas price", height) for used, item in zip(gas, receipts))
    timestamp = datetime.fromtimestamp(_hex(block.get("timestamp"), "timestamp", height), UTC).replace(tzinfo=None)
    return (height, block.get("hash"), timestamp, timestamp.date(), len(receipts), sum(gas),
            _hex(block.get("baseFeePerGas"), "base fee", height), fees)


def _hex(value: Any, label: str, height: int) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise DataError(f"block {height} has no hex {label}")
    return _integer(int(value, 16), label, height)


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid block-fee capture receipt: {error}") from error
    dataset_id = receipt.get("dataset_id")
    if dataset_id not in SPECS or receipt.get("schema_version") != f"{SPECS[dataset_id]['source_id']}-capture/v1":
        raise DataError("unsupported block-fee capture receipt")
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), dataset_id):
        raise DataError("block-fee capture contract hash differs")
    summary = receipt["responses"][0]
    try:
        body = (capture_dir / summary["path"]).read_bytes()
    except OSError as error:
        raise DataError("missing captured block lines") from error
    if sha256(body) != summary["sha256"] or len(body) != summary["bytes"]:
        raise DataError("captured block lines hash or size differs")
    lines, records = body.splitlines(), receipt.get("blocks", [])
    if len(lines) != len(records) or len(lines) != summary["blocks"]:
        raise DataError("captured block lines differ from the receipt")
    rows, seen = [], set()
    for line, record in zip(lines, records):
        if sha256(line) != record["sha256"] or len(line) != record["bytes"]:
            raise DataError(f"block line {record['block_height']} differs from its record")
        height = record["block_height"]
        if height in seen:
            raise DataError(f"block {height} is repeated or answered with another height")
        seen.add(height)
        rows.append(_row(dataset_id, json.loads(line), height))
    return receipt, rows


def _summary(rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    return {"rows": len(rows), "fees_wei": sum(row[7] for row in rows), "transactions": sum(row[4] for row in rows),
            "first_date": min((row[3] for row in rows), default=None), "last_date": max((row[3] for row in rows), default=None)}


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    table = _spec(dataset_id)["table"]
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{table}.parquet", "build.json"], "overwrite": False}


def _json_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in summary.items()}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    build_preview(dataset_id, capture_dir, output)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    receipt, rows = read_rows(capture_dir)
    if receipt["dataset_id"] != dataset_id:
        raise DataError(f"the capture is of {receipt['dataset_id']}, not {dataset_id}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet = temporary / f"{_spec(dataset_id)['table']}.parquet"
        connection = duckdb.connect()
        try:
            connection.execute(f"CREATE TABLE rows({', '.join(f'{name} {kind}' for name, kind in COLUMNS.items())})")
            for row in rows:
                connection.execute("INSERT INTO rows VALUES (?, ?, ?, ?, ?, ?, CAST(? AS DECIMAL(38,0)), CAST(? AS DECIMAL(38,0)))", [*row[:6], str(row[6]), str(row[7])])
            connection.execute("COPY (SELECT * FROM rows ORDER BY block_height) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
        finally:
            connection.close()
        result = {
            "schema_version": "data-api-build/v1", "dataset_id": dataset_id,
            "dataset_schema": dataset(load_catalog(), dataset_id)["fields"], "source_capture_id": receipt["capture_id"],
            "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": _json_summary(_summary(rows)),
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(result))
        os.replace(temporary, output)
        return result
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    """With ``--against`` the built gaps dataset directory: every captured block is one the gaps run lists."""
    receipt, rows = read_rows(capture_dir)
    findings: list[str] = []
    checked = ["capture hashes", "block identity", "block fields"]
    summary = _json_summary(_summary(rows))
    if against is not None:
        checked.append("listed in the gaps run")
        connection = duckdb.connect()
        try:
            listed = {row[0] for row in connection.execute("SELECT DISTINCT block_height FROM read_parquet(?)", [str(against / "c-chain-block-gaps.parquet")]).fetchall()}
        except duckdb.Error as error:
            raise DataError(f"cannot read the gaps dataset: {error}") from error
        finally:
            connection.close()
        unlisted = sum(row[0] not in listed for row in rows)
        summary["unlisted_blocks"] = unlisted
        if unlisted:
            findings.append(f"{unlisted} captured blocks are not listed in the gaps dataset")
    if dataset_dir is not None:
        checked.extend(["build hashes", "Parquet rows"])
        try:
            built = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
            parquet = dataset_dir / f"{_spec(receipt['dataset_id'])['table']}.parquet"
            data = parquet.read_bytes()
            if built["source_capture_id"] != receipt["capture_id"] or len(data) != built["outputs"][0]["bytes"] or sha256(data) != built["outputs"][0]["sha256"]:
                findings.append("build receipt or Parquet hash differs")
            connection = duckdb.connect()
            try:
                actual = connection.execute("SELECT block_height, fees_wei::VARCHAR FROM read_parquet(?) ORDER BY block_height", [str(parquet)]).fetchall()
            finally:
                connection.close()
            if actual != [(row[0], str(row[7])) for row in sorted(rows)]:
                findings.append("Parquet rows differ from captured blocks")
        except (OSError, KeyError, ValueError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid block-fee dataset output: {error}")
    return {"dataset_id": receipt["dataset_id"], "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": {**summary, "retries": receipt.get("retries", 0)}, "findings": findings}
