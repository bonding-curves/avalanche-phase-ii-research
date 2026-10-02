"""Archive and check C-Chain blocks and transaction receipts missing from the Snowflake share."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from . import __version__
from .catalog import DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256, source
from .rest import _request

DATASET_ID = "c-chain-rpc.receipt-gap-repairs"
SOURCE_ID = "avalanche-c-chain-rpc"
ENDPOINT_ID = "block-and-receipts"
TABLE = "receipt-gap-repairs"
SCHEMA = "c-chain-rpc-capture/v1"
COLUMNS = {
    "block_height": "BIGINT",
    "block_hash": "VARCHAR",
    "block_timestamp": "TIMESTAMP",
    "transaction_hash": "VARCHAR",
    "transaction_index": "INTEGER",
    "gas_used": "BIGINT",
    "effective_gas_price_wei": "DECIMAL(38,0)",
    "burned_wei": "DECIMAL(38,0)",
}


def _height(parameters: dict[str, str] | None) -> int:
    values = parameters or {}
    if set(values) != {"block"}:
        raise DataError("provide exactly one parameter: block=<C-Chain block height>")
    try:
        height = int(values["block"])
    except ValueError as error:
        raise DataError("block must be a positive integer") from error
    if height <= 0:
        raise DataError("block must be a positive integer")
    return height


def _endpoint(catalog: dict[str, Any]) -> str:
    provider = source(catalog, SOURCE_ID)
    return next(item["url"] for item in provider["endpoints"] if item["id"] == ENDPOINT_ID)


def _payload(method: str, params: list[Any], request_id: int) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": method, "params": params, "id": request_id}


def _hex(value: Any, label: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise DataError(f"{label} is not a hex quantity")
    try:
        number = int(value[2:], 16)
    except ValueError as error:
        raise DataError(f"{label} is not a hex quantity") from error
    if number < 0:
        raise DataError(f"{label} is negative")
    return number


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    return {
        "dataset_id": DATASET_ID,
        "source_id": SOURCE_ID,
        "output": str(output),
        "endpoint": _endpoint(load_catalog()),
        "block_height": _height(parameters),
        "writes": ["raw/block.json", "raw/receipt-*.json", "capture.json"],
        "overwrite": False,
    }


def capture(
    dataset_id: str,
    output: Path,
    timeout: float = 20,
    parameters: dict[str, str] | None = None,
    request: Callable[..., tuple[bytes, dict[str, Any]]] = _request,
) -> dict[str, Any]:
    preview = capture_preview(dataset_id, output, parameters)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    records: list[dict[str, Any]] = []

    def fetch(method: str, params: list[Any], request_id: int, path: str) -> dict[str, Any]:
        payload = _payload(method, params, request_id)
        body, metadata = request(preview["endpoint"], timeout, body_json=payload)
        value = json.loads(body)
        relative = Path("raw") / path
        (temporary / relative).write_bytes(body)
        records.append({
            "method": method, "request_json": payload, "url": preview["endpoint"],
            "path": str(relative), "bytes": len(body), "sha256": sha256(body), **metadata,
        })
        if value.get("jsonrpc") != "2.0" or value.get("id") != request_id or value.get("error") or not value.get("result"):
            raise DataError(f"invalid {method} response for block {preview['block_height']}")
        return value["result"]

    try:
        (temporary / "raw").mkdir()
        block = fetch("eth_getBlockByNumber", [hex(preview["block_height"]), False], 0, "block.json")
        if _hex(block.get("number"), "block number") != preview["block_height"]:
            raise DataError("RPC returned a different block height")
        transactions = block.get("transactions")
        if not isinstance(transactions, list) or not transactions or len(transactions) != len(set(transactions)):
            raise DataError("RPC block has no transactions or duplicate transaction hashes")
        for index, transaction_hash in enumerate(transactions):
            fetch("eth_getTransactionReceipt", [transaction_hash], index + 1, f"receipt-{index:05d}.json")
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
            "block_height": preview["block_height"],
            "responses": records,
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        os.replace(temporary, output)
        return receipt
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid C receipt-gap capture: {error}") from error
    if receipt.get("schema_version") != SCHEMA or receipt.get("dataset_id") != DATASET_ID:
        raise DataError("unsupported C receipt-gap capture")
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), DATASET_ID):
        raise DataError("C receipt-gap capture contract hash differs")
    records = receipt.get("responses", [])
    if not isinstance(records, list) or len(records) < 2:
        raise DataError("C receipt-gap capture lacks block or receipts")
    values = []
    for index, record in enumerate(records):
        path = Path(record["path"])
        if path.is_absolute() or ".." in path.parts or path.parts[0] != "raw":
            raise DataError("C receipt-gap capture has an unsafe raw path")
        try:
            body = (capture_dir / path).read_bytes()
        except OSError as error:
            raise DataError(f"missing C receipt-gap response {index}") from error
        if len(body) != record["bytes"] or sha256(body) != record["sha256"]:
            raise DataError(f"C receipt-gap response {index} hash or size differs")
        value = json.loads(body)
        payload = record["request_json"]
        if (record["url"] != _endpoint(load_catalog()) or value.get("jsonrpc") != "2.0"
                or value.get("id") != payload["id"] or value.get("error") or not value.get("result")):
            raise DataError(f"C receipt-gap response {index} differs from its request")
        values.append(value["result"])

    block = values[0]
    height = receipt["block_height"]
    if records[0]["request_json"] != _payload("eth_getBlockByNumber", [hex(height), False], 0):
        raise DataError("C receipt-gap block request differs")
    if _hex(block.get("number"), "block number") != height:
        raise DataError("C receipt-gap block height differs")
    block_hash = block.get("hash")
    transaction_hashes = block.get("transactions")
    if not isinstance(block_hash, str) or not isinstance(transaction_hashes, list) or not transaction_hashes:
        raise DataError("C receipt-gap block has no identity or transactions")
    if len(transaction_hashes) != len(set(transaction_hashes)) or len(records) != len(transaction_hashes) + 1:
        raise DataError("C receipt-gap transaction and response counts differ")
    timestamp = datetime.fromtimestamp(_hex(block.get("timestamp"), "block timestamp"), UTC).replace(tzinfo=None)
    rows = []
    for index, (transaction_hash, value, record) in enumerate(zip(transaction_hashes, values[1:], records[1:])):
        if record["request_json"] != _payload("eth_getTransactionReceipt", [transaction_hash], index + 1):
            raise DataError("C receipt-gap request does not match block transaction order")
        if (value.get("transactionHash") != transaction_hash or value.get("blockHash") != block_hash
                or _hex(value.get("blockNumber"), "receipt block number") != height
                or _hex(value.get("transactionIndex"), "transaction index") != index):
            raise DataError(f"C receipt-gap transaction {index} does not belong to the requested block")
        gas_used = _hex(value.get("gasUsed"), "receipt gas used")
        gas_price = _hex(value.get("effectiveGasPrice"), "effective gas price")
        rows.append((height, block_hash, timestamp, transaction_hash, index, gas_used, gas_price, gas_used * gas_price))
    return receipt, rows


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{TABLE}.parquet", "build.json"], "overwrite": False}


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
            columns = ", ".join(f"{name} {kind}" for name, kind in COLUMNS.items())
            connection.execute(f"CREATE TABLE rows({columns})")
            for row in rows:
                connection.execute(
                    "INSERT INTO rows VALUES (?, ?, ?, ?, ?, ?, CAST(? AS DECIMAL(38,0)), CAST(? AS DECIMAL(38,0)))",
                    [*row[:6], str(row[6]), str(row[7])],
                )
            connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
        finally:
            connection.close()
        result = {
            "schema_version": "c-chain-rpc-build/v1",
            "dataset_id": DATASET_ID,
            "dataset_schema": dataset(load_catalog(), DATASET_ID)["fields"],
            "source_capture_id": receipt["capture_id"],
            "completed_at": now(),
            "tool": f"avalanche-research@{__version__}",
            "summary": {"block_height": receipt["block_height"], "transactions": len(rows), "burned_wei": sum(row[7] for row in rows)},
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(result))
        os.replace(temporary, output)
        return result
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    if against is not None:
        raise DataError("C receipt-gap capture has no reference dataset check")
    receipt, rows = read_rows(capture_dir)
    findings = []
    checked = ["capture hashes", "block identity", "transaction membership", "receipt fee arithmetic"]
    if dataset_dir is not None:
        checked.extend(["build hashes", "Parquet rows"])
        try:
            build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
            output = build_receipt["outputs"][0]
            parquet = dataset_dir / output["path"]
            body = parquet.read_bytes()
            if (build_receipt["source_capture_id"] != receipt["capture_id"]
                    or build_receipt["dataset_id"] != DATASET_ID
                    or len(body) != output["bytes"] or sha256(body) != output["sha256"]):
                findings.append("build receipt or Parquet hash differs")
            else:
                connection = duckdb.connect()
                try:
                    actual = connection.execute("SELECT * FROM read_parquet(?) ORDER BY transaction_index", [str(parquet)]).fetchall()
                    schema = connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(parquet)]).fetchall()
                finally:
                    connection.close()
                if [(item[0], item[1]) for item in schema] != list(COLUMNS.items()) or actual != rows:
                    findings.append("Parquet schema or rows differ from captured receipts")
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid C receipt-gap build: {error}")
    return {
        "dataset_id": DATASET_ID,
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": {
            "block_height": receipt["block_height"],
            "block_hash": rows[0][1],
            "transactions": len(rows),
            "burned_wei": sum(row[7] for row in rows),
        },
        "findings": findings,
    }
