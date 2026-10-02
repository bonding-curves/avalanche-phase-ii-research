"""Archive and check P-Chain transactions by hash from a public node, for burns the Snowflake share cannot settle.

``platform.getTx`` returns the node's own record of a transaction: every input, imported input, output, and exported
output with its amount. The AVAX burned is inputs minus outputs. The share lacks the consumed UTXOs of some imports
from the C-Chain, and the Data API lists them with no inputs and a zero burn; the node's record settles them.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import duckdb

from . import __version__
from .catalog import DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256, source
from .rest import _request

DATASET_ID = "p-chain-rpc.transactions"
SOURCE_ID = "avalanche-p-chain-rpc"
ENDPOINT_ID = "get-tx"
TABLE = "transactions"
SCHEMA = "p-chain-rpc-capture/v1"
AVAX_ASSET_ID = "FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z"
MAX_HASHES = 500
INPUT_KEYS = ("inputs", "importedInputs")
OUTPUT_KEYS = ("outputs", "exportedOutputs", "stake")
COLUMNS = {
    "transaction_hash": "VARCHAR",
    "tx_kind": "VARCHAR",
    "input_navax": "BIGINT",
    "output_navax": "BIGINT",
    "burned_navax": "BIGINT",
    "input_count": "INTEGER",
    "output_count": "INTEGER",
}


def _hashes(parameters: dict[str, str] | None) -> list[str]:
    values = parameters or {}
    if set(values) != {"hashes"}:
        raise DataError("provide exactly one parameter: hashes=<comma-separated P-Chain transaction hashes>")
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
    return {"jsonrpc": "2.0", "method": "platform.getTx", "params": {"txID": tx_hash, "encoding": "json"}, "id": request_id}


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
                raise DataError(f"invalid platform.getTx response for {tx_hash}: {value.get('error') or 'no result'}")
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


def _avax(items: Any, key: str, tx_hash: str) -> tuple[int, int]:
    """Sum of AVAX amounts and count over one input or output list of the node's transaction JSON."""
    if items is None:
        return 0, 0
    if not isinstance(items, list):
        raise DataError(f"{key} of {tx_hash} is not a list")
    total, count = 0, 0
    for item in items:
        if item.get("assetID") != AVAX_ASSET_ID:
            continue
        inner = item.get("input") if key in INPUT_KEYS else item.get("output")
        try:
            amount = int(inner["amount"])
        except (KeyError, TypeError, ValueError) as error:
            raise DataError(f"{key} of {tx_hash} has no integer amount") from error
        if amount < 0:
            raise DataError(f"{key} of {tx_hash} has a negative amount")
        total += amount
        count += 1
    return total, count


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid P-Chain transaction capture: {error}") from error
    if receipt.get("schema_version") != SCHEMA or receipt.get("dataset_id") != DATASET_ID:
        raise DataError("unsupported P-Chain transaction capture")
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), DATASET_ID):
        raise DataError("P-Chain transaction capture contract hash differs")
    records, hashes = receipt.get("responses", []), receipt.get("hashes", [])
    if not isinstance(records, list) or not records or len(records) != len(hashes):
        raise DataError("P-Chain transaction capture responses do not match its hashes")
    rows = []
    for index, (record, tx_hash) in enumerate(zip(records, hashes)):
        path = Path(record["path"])
        if path.is_absolute() or ".." in path.parts or path.parts[0] != "raw":
            raise DataError("P-Chain transaction capture has an unsafe raw path")
        try:
            body = (capture_dir / path).read_bytes()
        except OSError as error:
            raise DataError(f"missing P-Chain transaction response {index}") from error
        if len(body) != record["bytes"] or sha256(body) != record["sha256"]:
            raise DataError(f"P-Chain transaction response {index} hash or size differs")
        value = json.loads(body)
        if (record["transaction_hash"] != tx_hash or record["request_json"] != _payload(tx_hash, index + 1)
                or record["url"] != _endpoint(load_catalog()) or value.get("jsonrpc") != "2.0" or value.get("id") != index + 1
                or value.get("error") or not value.get("result")):
            raise DataError(f"P-Chain transaction response {index} differs from its request")
        result = value["result"]
        transaction = result.get("tx", {})
        if transaction.get("id") != tx_hash or not isinstance(transaction.get("unsignedTx"), dict):
            raise DataError(f"P-Chain transaction response {index} is not the requested transaction")
        unsigned = transaction["unsignedTx"]
        kind = "ImportTx" if "importedInputs" in unsigned else "ExportTx" if "exportedOutputs" in unsigned else "other"
        input_navax = input_count = output_navax = output_count = 0
        for key in INPUT_KEYS:
            total, count = _avax(unsigned.get(key), key, tx_hash)
            input_navax, input_count = input_navax + total, input_count + count
        for key in OUTPUT_KEYS:
            total, count = _avax(unsigned.get(key), key, tx_hash)
            output_navax, output_count = output_navax + total, output_count + count
        if input_count == 0 or input_navax < output_navax:
            raise DataError(f"P-Chain transaction {tx_hash} has no AVAX inputs or creates more AVAX than it consumes")
        rows.append((tx_hash, kind, input_navax, output_navax, input_navax - output_navax, input_count, output_count))
    return receipt, rows


def _summary(rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    return {"transactions": len(rows), "burned_navax": sum(row[4] for row in rows), "imports": sum(row[1] == "ImportTx" for row in rows)}


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
            "schema_version": "p-chain-rpc-build/v1",
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
        raise DataError("P-Chain transaction capture has no reference dataset check")
    receipt, rows = read_rows(capture_dir)
    findings: list[str] = []
    checked = ["capture hashes", "transaction identity", "AVAX input and output arithmetic"]
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
            findings.append(f"invalid P-Chain transaction build: {error}")
    return {
        "dataset_id": DATASET_ID,
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": _summary(rows),
        "findings": findings,
    }
