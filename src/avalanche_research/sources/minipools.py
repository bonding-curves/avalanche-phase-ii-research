"""Every minipool record in GoGoPool's MinipoolManager contract on the C-Chain, read at one block.

GoGoPool, a liquid staking protocol that has since closed, paired AVAX from a node operator with AVAX from its liquid
staking pool in a minipool, one record per validator node in the contract
``0xc300Bc9B4b690BA7A182126299a0618eCe268Ee7``. A capture asks the public keyless C-Chain node for its newest block, or
takes ``block=<height>``, then makes every call at that block: ``getMinipoolCount()``, then ``getMinipool(int256)`` for
each index from 0, in JSON-RPC batches with a pause between them. The capture is therefore one point in time, and it
records that block's number, hash and time.

The build decodes the fixed head words of each returned ``Minipool`` struct, as the contract's verified source lays it
out. A record holds the node ID, the owner, the multisig that moves its stake to the P-Chain, amounts, times and the
P-Chain transaction of its latest staking period. The contract keeps one record per node ID, so a node ID that a second
owner reused shows only the latest owner. Nodes the protocol funded from its pool alone, outside a minipool, have no
record.

The owner and multisig are pseudonymous C-Chain addresses. An owner address links the nodes it holds, and it never
proves one decision maker: one person can hold several addresses, and an address can act for several people.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import urllib.error
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from .. import __version__
from ..core.catalog import (
    DataError,
    canonical_bytes,
    contract_hash,
    dataset,
    load_catalog,
    now,
    sha256,
    source,
)
from .capture.rest import _request
from .catx import cb58

DATASET_ID = "c-chain-rpc.minipool-records"
SOURCE_ID = "avalanche-c-chain-rpc"
ENDPOINT_ID = "minipool-manager-call"
TABLE = "minipool-records"
SCHEMA = "minipool-records-capture/v1"
BUILD_SCHEMA = "minipool-records-build/v1"
MANAGER = "0xc300bc9b4b690ba7a182126299a0618ece268ee7"
# Keccak-256 selectors of the two view functions. The source tests recompute them.
COUNT_SELECTOR = "0xae4d0bed"  # getMinipoolCount()
RECORD_SELECTOR = "0xd8ce16f4"  # getMinipool(int256)
# The public node bans a client after about 90,000 requests, and it answers a batch of 50 calls with HTTP 500 (40 pass,
# observed 2026-11-05). A full read is about 1,700 calls in about 70 batches of 25.
BATCH_SIZE = 25
PAUSE_SECONDS = 1.0
ATTEMPTS = 4
RETRY_SECONDS = 5.0
# The contract's MinipoolStatus enum, in order.
STATUS = ("Prelaunch", "Launched", "Staking", "Withdrawable", "Finished", "Canceled", "Error")
WEI_PER_AVAX = 10**18
FEE_DENOMINATOR = 10**6
COLUMNS = {
    "block_number": "BIGINT",
    "block_time": "TIMESTAMP",
    "minipool_index": "BIGINT",
    "node_id": "VARCHAR",
    "status": "VARCHAR",
    "duration_days": "DOUBLE",
    "delegation_fee_rate": "DOUBLE",
    "owner": "VARCHAR",
    "multisig_address": "VARCHAR",
    "node_op_avax": "DOUBLE",
    "node_op_initial_avax": "DOUBLE",
    "liquid_staker_avax": "DOUBLE",
    "tx_id": "VARCHAR",
    "creation_time": "TIMESTAMP",
    "initial_start_time": "TIMESTAMP",
    "start_time": "TIMESTAMP",
    "end_time": "TIMESTAMP",
    "total_reward_avax": "DOUBLE",
    "error_code": "VARCHAR",
    "ggp_slash_amount": "DOUBLE",
    "node_op_reward_avax": "DOUBLE",
    "liquid_staker_reward_avax": "DOUBLE",
    "hardware_provider": "VARCHAR",
}


def _endpoint(catalog: dict[str, Any] | None = None) -> str:
    provider = source(catalog or load_catalog(), SOURCE_ID)
    return next(item["url"] for item in provider["endpoints"] if item["id"] == ENDPOINT_ID)


def _block(parameters: dict[str, str] | None) -> int | None:
    values = parameters or {}
    if set(values) - {"block"}:
        raise DataError("the only parameter is block=<C-Chain block height>, and leaving it out reads the newest block")
    if "block" not in values:
        return None
    try:
        height = int(values["block"])
    except ValueError as error:
        raise DataError("block must be a positive integer") from error
    if height <= 0:
        raise DataError("block must be a positive integer")
    return height


def _hex(value: Any, label: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise DataError(f"{label} is not a hex quantity")
    try:
        return int(value, 16)
    except ValueError as error:
        raise DataError(f"{label} is not a hex quantity") from error


def count_call(height: int) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": 0, "method": "eth_call", "params": [{"to": MANAGER, "data": COUNT_SELECTOR}, hex(height)]}


def record_call(index: int, height: int) -> dict[str, Any]:
    data = RECORD_SELECTOR + index.to_bytes(32, "big").hex()
    return {"jsonrpc": "2.0", "id": index, "method": "eth_call", "params": [{"to": MANAGER, "data": data}, hex(height)]}


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    height = _block(parameters)
    return {
        "dataset_id": DATASET_ID,
        "source_id": SOURCE_ID,
        "output": str(output),
        "endpoint": _endpoint(),
        "contract": MANAGER,
        "block": height if height is not None else "the node's newest block at fetch time",
        "batch_size": BATCH_SIZE,
        "pause_seconds": PAUSE_SECONDS,
        "writes": ["raw/block-number.json", "raw/block.json", "raw/count.json", "raw/records-*.json", "capture.json"],
        "overwrite": False,
    }


def _single(body: bytes, payload: dict[str, Any], label: str) -> Any:
    value = json.loads(body)
    if not isinstance(value, dict) or value.get("id") != payload["id"] or value.get("error") or "result" not in value:
        raise DataError(f"invalid {label} response: {body[:200]!r}")
    return value["result"]


def _batch(body: bytes, payloads: list[dict[str, Any]], label: str) -> dict[int, str]:
    value = json.loads(body)
    if not isinstance(value, list):
        raise DataError(f"invalid {label} response: {body[:200]!r}")
    results = {item.get("id"): item for item in value if isinstance(item, dict)}
    wanted = [payload["id"] for payload in payloads]
    if sorted(results) != sorted(wanted) or len(value) != len(wanted):
        raise DataError(f"{label} response does not answer each call once")
    for index in wanted:
        item = results[index]
        if item.get("error") or not isinstance(item.get("result"), str) or not item["result"].startswith("0x"):
            raise DataError(f"{label} call {index} failed: {item.get('error')}")
    return {index: results[index]["result"] for index in wanted}


def capture(
    dataset_id: str,
    output: Path,
    timeout: float = 20,
    parameters: dict[str, str] | None = None,
    request: Callable[..., tuple[bytes, dict[str, Any]]] = _request,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    preview = capture_preview(dataset_id, output, parameters)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    endpoint = preview["endpoint"]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    records: list[dict[str, Any]] = []
    retries = 0

    def fetch(payload: dict[str, Any] | list[dict[str, Any]], path: str, content: str = "json") -> bytes:
        nonlocal retries
        for attempt in range(1, ATTEMPTS + 1):
            try:
                body, metadata = request(endpoint, timeout, body_json=payload, content=content)
                break
            except DataError as error:
                if attempt == ATTEMPTS or not isinstance(error.__cause__, (OSError, urllib.error.URLError)):
                    raise
                retries += 1
                sleep(RETRY_SECONDS * 2 ** (attempt - 1))
        relative = Path("raw") / path
        (temporary / relative).write_bytes(body)
        records.append({"request_json": payload, "url": endpoint, "path": str(relative), "bytes": len(body),
                        "sha256": sha256(body), **metadata})
        return body

    try:
        (temporary / "raw").mkdir()
        height = _block(parameters)
        if height is None:
            payload = {"jsonrpc": "2.0", "id": 0, "method": "eth_blockNumber", "params": []}
            height = _hex(_single(fetch(payload, "block-number.json"), payload, "eth_blockNumber"), "block number")
        payload = {"jsonrpc": "2.0", "id": 0, "method": "eth_getBlockByNumber", "params": [hex(height), False]}
        block = _single(fetch(payload, "block.json"), payload, "eth_getBlockByNumber")
        if not isinstance(block, dict) or _hex(block.get("number"), "block number") != height:
            raise DataError("the node returned a different block")
        payload = count_call(height)
        count = _hex(_single(fetch(payload, "count.json"), payload, "getMinipoolCount"), "minipool count")
        if count <= 0:
            raise DataError("the contract reports no minipools at that block")
        for offset in range(0, count, BATCH_SIZE):
            sleep(PAUSE_SECONDS)
            payloads = [record_call(index, height) for index in range(offset, min(count, offset + BATCH_SIZE))]
            _batch(fetch(payloads, f"records-{offset:05d}.json", "json-list"), payloads, "getMinipool")
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
            "contract": MANAGER,
            "block_number": height,
            "block_hash": block.get("hash"),
            "block_time": datetime.fromtimestamp(_hex(block.get("timestamp"), "block time"), UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "minipool_count": count,
            "calls": count + 1,
            "retries": retries,
            "responses": records,
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        os.replace(temporary, output)
        return receipt
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _time(value: int) -> datetime | None:
    return datetime.fromtimestamp(value, UTC).replace(tzinfo=None) if value else None


def _node_id(word: bytes) -> str:
    return "NodeID-" + cb58(word[12:])


def decode(result: str) -> dict[str, Any]:
    """The head words of one ``Minipool`` struct. The struct holds a dynamic ``bytes`` field, so the return value starts
    with the offset of the tuple, and each fixed field is one 32-byte word after it, in declaration order."""
    raw = bytes.fromhex(result.removeprefix("0x"))
    if len(raw) < 32 * 23 or int.from_bytes(raw[:32], "big") != 32:
        raise DataError("a getMinipool answer is too short or does not start with the tuple offset")
    head = raw[32:]

    def word(k: int) -> bytes:
        return head[32 * k:32 * k + 32]

    def number(k: int) -> int:
        return int.from_bytes(word(k), "big")

    def address(k: int) -> str:
        return "0x" + word(k)[12:].hex()

    def optional_hex(k: int) -> str | None:
        return "0x" + word(k).hex() if number(k) else None

    status = number(2)
    return {
        "minipool_index": number(0),
        "node_id": _node_id(word(1)),
        "status": STATUS[status] if status < len(STATUS) else str(status),
        "duration_days": number(3) / 86400,
        "delegation_fee_rate": number(4) / FEE_DENOMINATOR,
        "owner": address(5),
        "multisig_address": address(6),
        "node_op_avax": number(7) / WEI_PER_AVAX,
        "node_op_initial_avax": number(8) / WEI_PER_AVAX,
        "liquid_staker_avax": number(9) / WEI_PER_AVAX,
        "tx_id": cb58(word(11)) if number(11) else None,
        "creation_time": _time(number(12)),
        "initial_start_time": _time(number(13)),
        "start_time": _time(number(14)),
        "end_time": _time(number(15)),
        "total_reward_avax": number(16) / WEI_PER_AVAX,
        "error_code": optional_hex(17),
        "ggp_slash_amount": number(18) / WEI_PER_AVAX,
        "node_op_reward_avax": number(19) / WEI_PER_AVAX,
        "liquid_staker_reward_avax": number(20) / WEI_PER_AVAX,
        "hardware_provider": optional_hex(21),
    }


def _read_receipt(capture_dir: Path) -> dict[str, Any]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid minipool capture: {error}") from error
    if receipt.get("schema_version") != SCHEMA or receipt.get("dataset_id") != DATASET_ID:
        raise DataError("unsupported minipool capture")
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), DATASET_ID):
        raise DataError("minipool capture contract hash differs")
    return receipt


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    """Every row of the capture, after each raw response is checked against its hash and its request, every call is
    checked to name the capture's block, and the record calls are checked to cover each index once."""
    receipt = _read_receipt(capture_dir)
    height, count = receipt.get("block_number"), receipt.get("minipool_count")
    if not isinstance(height, int) or not isinstance(count, int) or count <= 0:
        raise DataError("minipool capture lacks its block or count")
    endpoint = _endpoint()
    bodies: dict[str, tuple[Any, bytes]] = {}
    batches: list[tuple[list[dict[str, Any]], bytes]] = []
    for position, record in enumerate(receipt.get("responses", [])):
        path = Path(record["path"])
        if path.is_absolute() or ".." in path.parts or path.parts[0] != "raw":
            raise DataError("minipool capture has an unsafe raw path")
        try:
            body = (capture_dir / path).read_bytes()
        except OSError as error:
            raise DataError(f"missing minipool response {position}") from error
        if len(body) != record["bytes"] or sha256(body) != record["sha256"] or record["url"] != endpoint:
            raise DataError(f"minipool response {position} hash or size differs")
        payload = record["request_json"]
        if isinstance(payload, list):
            batches.append((payload, body))
        else:
            bodies[path.name] = (payload, body)
    if "block.json" not in bodies or "count.json" not in bodies:
        raise DataError("minipool capture lacks its block or count response")
    payload, body = bodies["block.json"]
    block = _single(body, payload, "eth_getBlockByNumber")
    if payload["params"] != [hex(height), False] or _hex(block.get("number"), "block number") != height or block.get("hash") != receipt.get("block_hash"):
        raise DataError("minipool capture block differs from its receipt")
    block_time = _time(_hex(block.get("timestamp"), "block time"))
    payload, body = bodies["count.json"]
    if payload != count_call(height) or _hex(_single(body, payload, "getMinipoolCount"), "minipool count") != count:
        raise DataError("minipool capture count differs from its receipt")
    results: dict[int, str] = {}
    for payloads, body in batches:
        for item in payloads:
            if item != record_call(item["id"], height):
                raise DataError(f"minipool call {item.get('id')} is not getMinipool at the capture's block")
        for index, result in _batch(body, payloads, "getMinipool").items():
            if index in results:
                raise DataError(f"minipool index {index} is read twice")
            results[index] = result
    if sorted(results) != list(range(count)):
        raise DataError(f"minipool capture covers {len(results)} of {count} indices")
    rows = []
    for index in range(count):
        values = decode(results[index])
        if values["minipool_index"] != index:
            raise DataError(f"minipool record {index} carries index {values['minipool_index']}")
        rows.append(tuple({"block_number": height, "block_time": block_time, **values}[name] for name in COLUMNS))
    return receipt, rows


def _write(parquet: Path, rows: list[tuple[Any, ...]]) -> None:
    connection = duckdb.connect()
    try:
        connection.execute(f"CREATE TABLE rows({', '.join(f'{name} {kind}' for name, kind in COLUMNS.items())})")
        connection.executemany(f"INSERT INTO rows VALUES ({', '.join('?' for _ in COLUMNS)})", rows)
        connection.execute("COPY (SELECT * FROM rows ORDER BY minipool_index) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
    finally:
        connection.close()


def _summary(receipt: dict[str, Any], rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    names = list(COLUMNS)
    column = {name: [row[names.index(name)] for row in rows] for name in ("node_id", "status", "owner", "multisig_address")}
    statuses: dict[str, int] = {}
    for value in column["status"]:
        statuses[value] = statuses.get(value, 0) + 1
    return {
        "rows": len(rows),
        "block_number": receipt["block_number"],
        "block_time": receipt["block_time"],
        "node_ids": len(set(column["node_id"])),
        "owners": len(set(column["owner"])),
        "multisig_addresses": sorted(set(column["multisig_address"])),
        "statuses": dict(sorted(statuses.items())),
    }


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
        _write(parquet, rows)
        result = {
            "schema_version": BUILD_SCHEMA,
            "dataset_id": DATASET_ID,
            "dataset_schema": dataset(load_catalog(), DATASET_ID)["fields"],
            "source_capture_id": receipt["capture_id"],
            "completed_at": now(),
            "tool": f"avalanche-research@{__version__}",
            "summary": _summary(receipt, rows),
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(result))
        os.replace(temporary, output)
        return result
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    """Recheck the capture, and the build when given: each node ID once, one multisig, and the rows as decoded."""
    if against is not None:
        raise DataError(f"{DATASET_ID} has no reference dataset check")
    receipt, rows = read_rows(capture_dir)
    findings: list[str] = []
    checked = ["capture hashes", "every call at the capture's block", "every index once", "struct decoding"]
    summary = _summary(receipt, rows)
    if summary["node_ids"] != summary["rows"]:
        findings.append(f"{summary['rows'] - summary['node_ids']} node IDs hold more than one record")
    if len(summary["multisig_addresses"]) != 1:
        findings.append(f"the records name {len(summary['multisig_addresses'])} multisig addresses, not one")
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
                    actual = connection.execute("SELECT * FROM read_parquet(?) ORDER BY minipool_index", [str(parquet)]).fetchall()
                    schema = connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(parquet)]).fetchall()
                finally:
                    connection.close()
                declared = [field["name"] for field in dataset(load_catalog(), DATASET_ID)["fields"]]
                if [(item[0], item[1]) for item in schema] != list(COLUMNS.items()) or declared != list(COLUMNS):
                    findings.append("Parquet columns differ from the module or the catalog")
                elif actual != rows:
                    findings.append("Parquet rows differ from the captured responses")
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid minipool build: {error}")
    return {
        "dataset_id": DATASET_ID,
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summary,
        "findings": findings,
    }
