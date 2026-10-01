"""Archive and check C-Chain atomic transactions by hash from a public node, for burns the Data API cannot settle.

``avax.getAtomicTx`` returns the node's own signed transaction as hex with a four-byte checksum. Decoded, an import
carries every imported input and every EVM output with its amount, and the AVAX burned is inputs minus outputs. The
Data API lists a few early imports with fewer consumed UTXOs than the transaction spent, so its burn comes out
negative; the node's record settles them. The transaction ID is the CB58 form of the SHA-256 of the signed bytes, so a response for
another transaction cannot pass.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import duckdb

from .. import __version__
from ..core.catalog import DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256, source
from .capture.rest import _request

DATASET_ID = "c-chain-rpc.atomic-transactions"
SOURCE_ID = "avalanche-c-chain-rpc"
ENDPOINT_ID = "get-atomic-tx"
TABLE = "atomic-transactions"
SCHEMA = "c-chain-rpc-atomic-capture/v1"
AVAX_ASSET_ID = "FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z"
MAX_HASHES = 500
IMPORT_TX = 0
TRANSFER_INPUT = 5
CREDENTIAL = 9
SIGNATURE_BYTES = 65
BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
COLUMNS = {
    "transaction_hash": "VARCHAR",
    "tx_kind": "VARCHAR",
    "block_height": "BIGINT",
    "input_navax": "BIGINT",
    "output_navax": "BIGINT",
    "burned_navax": "BIGINT",
    "input_count": "INTEGER",
    "output_count": "INTEGER",
}


def cb58(data: bytes) -> str:
    """Avalanche's CB58: base58 of the bytes followed by the last four bytes of their SHA-256."""
    data = data + hashlib.sha256(data).digest()[-4:]
    number = int.from_bytes(data, "big")
    text = ""
    while number:
        number, remainder = divmod(number, 58)
        text = BASE58[remainder] + text
    return "1" * (len(data) - len(data.lstrip(b"\0"))) + text


def _hashes(parameters: dict[str, str] | None) -> list[str]:
    values = parameters or {}
    if set(values) != {"hashes"}:
        raise DataError("provide exactly one parameter: hashes=<comma-separated C-Chain atomic transaction hashes>")
    hashes = [item.strip() for item in values["hashes"].split(",") if item.strip()]
    if not hashes or len(hashes) != len(set(hashes)) or len(hashes) > MAX_HASHES:
        raise DataError(f"hashes must name between 1 and {MAX_HASHES} distinct transaction hashes")
    if any(not item.isalnum() for item in hashes):
        raise DataError("a transaction hash is base58 text")
    return hashes


def _endpoint(catalog: dict[str, Any]) -> str:
    provider = source(catalog, SOURCE_ID)
    return next(item["url"] for item in provider["endpoints"] if item["id"] == ENDPOINT_ID)


def _payload(tx_hash: str, request_id: int) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": "avax.getAtomicTx", "params": {"txID": tx_hash, "encoding": "hex"}, "id": request_id}


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    return {
        "dataset_id": DATASET_ID,
        "source_id": SOURCE_ID,
        "output": str(output),
        "endpoint": _endpoint(load_catalog()),
        "hashes": _hashes(parameters),
        "writes": ["raw/tx-*.json", "capture.json"],
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
    try:
        (temporary / "raw").mkdir()
        for index, tx_hash in enumerate(preview["hashes"]):
            payload = _payload(tx_hash, index + 1)
            body, metadata = request(preview["endpoint"], timeout, body_json=payload)
            value = json.loads(body)
            relative = Path("raw") / f"tx-{index:05d}.json"
            (temporary / relative).write_bytes(body)
            records.append({
                "transaction_hash": tx_hash, "request_json": payload, "url": preview["endpoint"],
                "path": str(relative), "bytes": len(body), "sha256": sha256(body), **metadata,
            })
            if value.get("jsonrpc") != "2.0" or value.get("id") != index + 1 or value.get("error") or not value.get("result"):
                raise DataError(f"invalid avax.getAtomicTx response for {tx_hash}: {value.get('error') or 'no result'}")
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
            "hashes": preview["hashes"],
            "responses": records,
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        os.replace(temporary, output)
        return receipt
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def decode_import(signed: bytes, tx_hash: str) -> tuple[int, int, int, int]:
    """(AVAX in, inputs, AVAX out, outputs) of a signed C-Chain import, codec version 0. Every byte must be read."""
    offset = 0

    def take(count: int) -> bytes:
        nonlocal offset
        if offset + count > len(signed):
            raise DataError(f"atomic transaction {tx_hash} ends early")
        part = signed[offset:offset + count]
        offset += count
        return part

    def u32() -> int:
        return struct.unpack(">I", take(4))[0]

    def u64() -> int:
        return struct.unpack(">Q", take(8))[0]

    if struct.unpack(">H", take(2))[0] != 0:
        raise DataError(f"atomic transaction {tx_hash} has an unknown codec version")
    if u32() != IMPORT_TX:
        raise DataError(f"atomic transaction {tx_hash} is not an import")
    take(4 + 32 + 32)  # network, destination chain, source chain
    input_navax = input_count = output_navax = output_count = 0
    for _ in range(u32()):
        take(32 + 4)  # the consumed UTXO's transaction and index
        asset = cb58(take(32))
        if u32() != TRANSFER_INPUT:
            raise DataError(f"atomic transaction {tx_hash} has an input that is not a transfer input")
        amount = u64()
        take(4 * u32())  # signature indices
        if asset == AVAX_ASSET_ID:
            input_navax, input_count = input_navax + amount, input_count + 1
    for _ in range(u32()):
        take(20)  # the EVM address credited
        amount = u64()
        if cb58(take(32)) == AVAX_ASSET_ID:
            output_navax, output_count = output_navax + amount, output_count + 1
    for _ in range(u32()):
        if u32() != CREDENTIAL:
            raise DataError(f"atomic transaction {tx_hash} has an unknown credential")
        take(SIGNATURE_BYTES * u32())
    if offset != len(signed):
        raise DataError(f"atomic transaction {tx_hash} has {len(signed) - offset} unread bytes")
    return input_navax, input_count, output_navax, output_count


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid C-Chain atomic transaction capture: {error}") from error
    if receipt.get("schema_version") != SCHEMA or receipt.get("dataset_id") != DATASET_ID:
        raise DataError("unsupported C-Chain atomic transaction capture")
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), DATASET_ID):
        raise DataError("C-Chain atomic transaction capture contract hash differs")
    records, hashes = receipt.get("responses", []), receipt.get("hashes", [])
    if not isinstance(records, list) or not records or len(records) != len(hashes):
        raise DataError("C-Chain atomic transaction capture responses do not match its hashes")
    rows = []
    for index, (record, tx_hash) in enumerate(zip(records, hashes)):
        path = Path(record["path"])
        if path.is_absolute() or ".." in path.parts or path.parts[0] != "raw":
            raise DataError("C-Chain atomic transaction capture has an unsafe raw path")
        try:
            body = (capture_dir / path).read_bytes()
        except OSError as error:
            raise DataError(f"missing C-Chain atomic transaction response {index}") from error
        if len(body) != record["bytes"] or sha256(body) != record["sha256"]:
            raise DataError(f"C-Chain atomic transaction response {index} hash or size differs")
        value = json.loads(body)
        if (record["transaction_hash"] != tx_hash or record["request_json"] != _payload(tx_hash, index + 1)
                or record["url"] != _endpoint(load_catalog()) or value.get("jsonrpc") != "2.0" or value.get("id") != index + 1
                or value.get("error") or not value.get("result")):
            raise DataError(f"C-Chain atomic transaction response {index} differs from its request")
        result = value["result"]
        text = result.get("tx")
        if result.get("encoding") != "hex" or not isinstance(text, str) or not text.startswith("0x"):
            raise DataError(f"C-Chain atomic transaction response {index} is not hex")
        try:
            encoded = bytes.fromhex(text[2:])
            height = int(result["blockHeight"])
        except (KeyError, TypeError, ValueError) as error:
            raise DataError(f"C-Chain atomic transaction response {index} is malformed") from error
        # The node's hex format ends with the last four bytes of the SHA-256 of what precedes them.
        signed, checksum = encoded[:-4], encoded[-4:]
        if len(encoded) < 5 or hashlib.sha256(signed).digest()[-4:] != checksum:
            raise DataError(f"C-Chain atomic transaction response {index} fails its hex checksum")
        if cb58(hashlib.sha256(signed).digest()) != tx_hash:
            raise DataError(f"C-Chain atomic transaction response {index} is not the requested transaction")
        input_navax, input_count, output_navax, output_count = decode_import(signed, tx_hash)
        if input_count == 0 or input_navax < output_navax:
            raise DataError(f"C-Chain atomic transaction {tx_hash} has no AVAX inputs or creates more AVAX than it consumes")
        rows.append((tx_hash, "ImportTx", height, input_navax, output_navax, input_navax - output_navax, input_count, output_count))
    return receipt, rows


def _summary(rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    return {"transactions": len(rows), "burned_navax": sum(row[5] for row in rows), "imports": sum(row[1] == "ImportTx" for row in rows)}


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
            connection.execute(f"CREATE TABLE rows({', '.join(f'{name} {kind}' for name, kind in COLUMNS.items())})")
            connection.executemany(f"INSERT INTO rows VALUES ({', '.join('?' for _ in COLUMNS)})", rows)
            connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
        finally:
            connection.close()
        result = {
            "schema_version": "c-chain-rpc-atomic-build/v1",
            "dataset_id": DATASET_ID,
            "dataset_schema": dataset(load_catalog(), DATASET_ID)["fields"],
            "source_capture_id": receipt["capture_id"],
            "completed_at": now(),
            "tool": f"avalanche-research@{__version__}",
            "summary": {"rows": len(rows), **_summary(rows)},
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
        raise DataError("C-Chain atomic transaction capture has no reference dataset check")
    receipt, rows = read_rows(capture_dir)
    findings: list[str] = []
    checked = ["capture hashes", "transaction identity from the signed bytes", "complete decoding", "AVAX input and output arithmetic"]
    if dataset_dir is not None:
        checked.extend(["build hashes", "Parquet rows"])
        try:
            build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
            output = build_receipt["outputs"][0]
            parquet = dataset_dir / output["path"]
            body = parquet.read_bytes()
            if (build_receipt["source_capture_id"] != receipt["capture_id"] or build_receipt["dataset_id"] != DATASET_ID
                    or len(body) != output["bytes"] or sha256(body) != output["sha256"]):
                findings.append("build receipt or Parquet hash differs")
            else:
                connection = duckdb.connect()
                try:
                    actual = connection.execute("SELECT * FROM read_parquet(?) ORDER BY transaction_hash", [str(parquet)]).fetchall()
                    schema = connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(parquet)]).fetchall()
                finally:
                    connection.close()
                if [(item[0], item[1]) for item in schema] != list(COLUMNS.items()) or actual != sorted(rows):
                    findings.append("Parquet schema or rows differ from the captured transactions")
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid C-Chain atomic transaction build: {error}")
    return {
        "dataset_id": DATASET_ID,
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": _summary(rows),
        "findings": findings,
    }
