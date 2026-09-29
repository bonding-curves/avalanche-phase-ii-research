"""Capture, for every staking period a P-Chain block walk sees end, the stake's own record and the reward it paid.

A walk's ``RewardValidatorTx`` names the staking transaction it closes. Most of those stakes started before the walk, so
the walk alone cannot say what they were. Two captures, one per source, read them by hash:

``data-api.p-chain-staking-transactions`` reads the Data API's record of the staking transaction: its type, node, block,
start, end, amount staked, and ``estimatedReward``, the potential reward the protocol added to the supply counter when
the stake started. The supply reconstruction needs it for stakes that started before the walk and end unrewarded.

``p-chain-rpc.reward-utxos`` reads the node's ``platform.getRewardUTXOs`` for the staking transaction: the reward outputs it
paid, decoded from their codec bytes. A staker that ended unrewarded has none.

One hash is one JSON line, written as it arrives, and a stopped capture continues with ``resume=<kept directory>``.
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

from . import __version__, datasets
from .catalog import (
    DataError,
    canonical_bytes,
    contract_hash,
    dataset,
    load_catalog,
    now,
    sha256,
    source,
)
from .rest import _request

STAKING_ID = "data-api.p-chain-staking-transactions"
REWARDS_ID = "p-chain-rpc.reward-utxos"
DATASET_IDS = (STAKING_ID, REWARDS_ID)
DATASET_ID = STAKING_ID
BLOCKS_ID = "p-chain-rpc.blocks"
SPECS = {
    STAKING_ID: {"source_id": "avalanche-data-api", "endpoint_id": "p-chain-transaction", "table": "p-chain-staking-transactions"},
    REWARDS_ID: {"source_id": "avalanche-p-chain-rpc", "endpoint_id": "get-reward-utxos", "table": "reward-utxos"},
}
REWARD_TYPES = ("RewardValidatorTx", "RewardAutoRenewedValidatorTx")
PROGRESS = "progress.jsonl"
RAW = "raw/records.jsonl"
ATTEMPTS = 8
RETRY_SECONDS = 2.0
MAX_WORKERS = 8
AVAX_ASSET_HEX = "21e67317cbc4be2aeb00677ad6462778a8f52274b9d605df2591b23027a87dff"
TRANSFER_OUTPUT = 7
STAKEABLE_LOCK_OUT = 22
COLUMNS = {
    STAKING_ID: {
        "staking_transaction_hash": "VARCHAR",
        "tx_type": "VARCHAR",
        "node_id": "VARCHAR",
        "block_height": "BIGINT",
        "accepted_at": "TIMESTAMP",
        "start_time": "TIMESTAMP",
        "end_time": "TIMESTAMP",
        "estimated_reward_navax": "BIGINT",
        "reward_transaction_hash": "VARCHAR",
    },
    REWARDS_ID: {
        "staking_transaction_hash": "VARCHAR",
        "reward_utxo_count": "INTEGER",
        "realized_reward_navax": "BIGINT",
    },
}


def _spec(dataset_id: str) -> dict[str, str]:
    if dataset_id not in SPECS:
        raise DataError(f"unknown dataset: {dataset_id}")
    return SPECS[dataset_id]


def _endpoint(catalog: dict[str, Any], dataset_id: str) -> str:
    spec = _spec(dataset_id)
    return next(item["url"] for item in source(catalog, spec["source_id"])["endpoints"] if item["id"] == spec["endpoint_id"])


def _parameters(parameters: dict[str, str] | None) -> dict[str, Any]:
    values = dict(parameters or {})
    unknown = set(values) - {"blocks", "workers", "resume"}
    if unknown:
        raise DataError(f"unknown parameters: {', '.join(sorted(unknown))}")
    if not values.get("blocks"):
        raise DataError(f"provide blocks=<built run of {BLOCKS_ID}> whose reward transactions name the stakes to read")
    try:
        workers = int(values.get("workers", 4))
    except ValueError as error:
        raise DataError("workers is an integer") from error
    if not 1 <= workers <= MAX_WORKERS:
        raise DataError(f"workers must be between 1 and {MAX_WORKERS}")
    return {"blocks": values["blocks"], "workers": workers, **({"resume": values["resume"]} if values.get("resume") else {})}


def staking_hashes(run: str, root: Path | None = None) -> tuple[dict[str, Any], list[str]]:
    """The staking transactions the walk's reward transactions close, in walk order, and the walk's receipt."""
    record = datasets.receipt(BLOCKS_ID, run, root)
    parquet = datasets.parquet_path(BLOCKS_ID, run, root)
    connection = duckdb.connect()
    try:
        hashes = [row[0] for row in connection.execute(
            "SELECT json_extract_string(unsigned_tx, '$.txID') FROM read_parquet(?) WHERE tx_type IN (?, ?)"
            " ORDER BY block_height, tx_index", [str(parquet), *REWARD_TYPES]).fetchall()]
    finally:
        connection.close()
    return record, list(dict.fromkeys(hashes))


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    spec = _spec(dataset_id)
    values = _parameters(parameters)
    record, hashes = staking_hashes(values["blocks"], root)
    return {
        "dataset_id": dataset_id, "source_id": spec["source_id"], "output": str(output), "endpoint": _endpoint(load_catalog(), dataset_id),
        "blocks_run": values["blocks"], "blocks_capture_id": record["capture"]["capture_id"], "stakes": len(hashes),
        "workers": values["workers"], **({"resume": values["resume"]} if "resume" in values else {}),
        "writes": [RAW, "capture.json"], "overwrite": False,
    }


def _call(dataset_id: str, endpoint: str, tx_hash: str) -> tuple[str, dict[str, Any] | None]:
    """The URL and JSON body of the one request for a staking transaction."""
    if dataset_id == STAKING_ID:
        return f"{endpoint}/{tx_hash}", None
    return endpoint, {"jsonrpc": "2.0", "id": 1, "method": "platform.getRewardUTXOs", "params": {"txID": tx_hash, "encoding": "hex"}}


def capture(
    dataset_id: str,
    output: Path,
    timeout: float = 20,
    parameters: dict[str, str] | None = None,
    request: Callable[..., tuple[bytes, dict[str, Any]]] = _request,
    root: Path | None = None,
) -> dict[str, Any]:
    preview = capture_preview(dataset_id, output, parameters, root)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    _, hashes = staking_hashes(preview["blocks_run"], root)
    header = {"endpoint": preview["endpoint"], "blocks_capture_id": preview["blocks_capture_id"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    if "resume" in preview:
        temporary = Path(preview["resume"])
        try:
            lines = (temporary / PROGRESS).read_text(encoding="utf-8").splitlines()
            kept_header, records = json.loads(lines[0]), [json.loads(line) for line in lines[1:]]
            bodies = (temporary / RAW).read_bytes().splitlines()
        except (OSError, IndexError, json.JSONDecodeError) as error:
            raise DataError(f"cannot resume from {temporary}: {error}") from error
        if kept_header != header:
            raise DataError("cannot resume: the kept capture reads another walk or endpoint")
        kept = 0
        for record, body in zip(records, bodies):
            if sha256(body) != record["sha256"] or len(body) != record["bytes"]:
                break
            kept += 1
        records = records[:kept]
        (temporary / RAW).write_bytes(b"".join(body + b"\n" for body in bodies[:kept]))
        (temporary / PROGRESS).write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in [header, *records]), encoding="utf-8")
    else:
        temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
        (temporary / "raw").mkdir()
        (temporary / RAW).write_bytes(b"")
        (temporary / PROGRESS).write_text(json.dumps(header, sort_keys=True) + "\n", encoding="utf-8")
        records = []
    done = {record["staking_transaction_hash"] for record in records}
    todo = [tx_hash for tx_hash in hashes if tx_hash not in done]
    retries = 0

    def fetch(tx_hash: str) -> tuple[str, bytes, int]:
        url, body_json = _call(dataset_id, preview["endpoint"], tx_hash)
        for attempt in range(1, ATTEMPTS + 1):
            try:
                body, _ = request(url, timeout, body_json=body_json) if body_json else request(url, timeout)
                return tx_hash, json.dumps(json.loads(body), separators=(",", ":"), sort_keys=True).encode(), attempt - 1
            except DataError as error:
                # Keyless, the Data API refuses for minutes after about a thousand requests, and the node answers 502
                # now and then. Wait, doubling, about four minutes in all, then keep the lines.
                if attempt == ATTEMPTS or not isinstance(error.__cause__, (OSError, urllib.error.URLError)):
                    raise
                time.sleep(RETRY_SECONDS * 2 ** (attempt - 1))
        raise AssertionError("unreachable")

    try:
        batch_size = preview["workers"] * 16
        with (temporary / RAW).open("ab") as raw, (temporary / PROGRESS).open("a", encoding="utf-8") as progress, \
                ThreadPoolExecutor(max_workers=preview["workers"]) as pool:
            for offset in range(0, len(todo), batch_size):
                results = pool.map(fetch, todo[offset: offset + batch_size])
                while True:
                    try:
                        tx_hash, line, retried = next(results)
                    except StopIteration:
                        break
                    except (DataError, json.JSONDecodeError) as error:
                        raw.flush()
                        progress.flush()
                        raise DataError(f"{error}; {len(records)} records kept at {temporary}") from error
                    retries += retried
                    try:
                        _row(dataset_id, json.loads(line), tx_hash)
                    except DataError as error:
                        raise DataError(f"{error}; {len(records)} records kept at {temporary}") from error
                    raw.write(line + b"\n")
                    record = {"staking_transaction_hash": tx_hash, "bytes": len(line), "sha256": sha256(line)}
                    records.append(record)
                    progress.write(json.dumps(record, sort_keys=True) + "\n")
                raw.flush()
                progress.flush()
        if not records:
            raise DataError("the walk closes no staking period")
        completed_at = now()
        body_all = (temporary / RAW).read_bytes()
        spec = _spec(dataset_id)
        identity = sha256(canonical_bytes({"completed_at": completed_at, "sha256": sha256(body_all)}))
        receipt = {
            "schema_version": f"{spec['source_id']}-staker-capture/v1",
            "capture_id": f"capture:{spec['source_id']}:{completed_at}:{identity[:12]}",
            "dataset_id": dataset_id, "source_id": spec["source_id"], "completed_at": completed_at,
            "contract_sha256": contract_hash(catalog, dataset_id), "tool": f"avalanche-research@{__version__}",
            "endpoint": preview["endpoint"], "blocks_run": preview["blocks_run"], "blocks_capture_id": preview["blocks_capture_id"],
            "retries": retries,
            "responses": [{"endpoint_id": spec["endpoint_id"], "path": RAW, "records": len(records), "bytes": len(body_all), "sha256": sha256(body_all)}],
            "records": records,
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        (temporary / PROGRESS).unlink()
        os.replace(temporary, output)
        return receipt
    except Exception:
        if not (temporary / RAW).exists() or (temporary / RAW).stat().st_size == 0:
            shutil.rmtree(temporary, ignore_errors=True)
        raise


def _utc(seconds: Any, label: str, tx_hash: str) -> datetime:
    try:
        return datetime.fromtimestamp(int(seconds), UTC).replace(tzinfo=None)
    except (TypeError, ValueError) as error:
        raise DataError(f"{tx_hash} has no integer {label}") from error


def reward_outputs(utxos: list[str], tx_hash: str) -> tuple[int, int]:
    """(count, AVAX sum) of reward UTXOs in hex: codec version, UTXO id, asset id, then a TransferOutput or a
    StakeableLockOut around one, and the hex encoding's 4-byte checksum."""
    total = 0
    for encoded in utxos:
        try:
            data = bytes.fromhex(encoded.removeprefix("0x"))
        except (AttributeError, ValueError) as error:
            raise DataError(f"a reward UTXO of {tx_hash} is not hex") from error
        if len(data) < 2 + 32 + 4 + 32 + 4 + 8 or data[:2] != b"\0\0":
            raise DataError(f"a reward UTXO of {tx_hash} is too short or has an unknown codec version")
        if data[38:70].hex() != AVAX_ASSET_HEX:
            raise DataError(f"a reward UTXO of {tx_hash} is not AVAX")
        offset = 70
        kind = int.from_bytes(data[offset: offset + 4], "big")
        if kind == STAKEABLE_LOCK_OUT:
            offset += 4 + 8
            kind = int.from_bytes(data[offset: offset + 4], "big")
        if kind != TRANSFER_OUTPUT:
            raise DataError(f"a reward UTXO of {tx_hash} has output type {kind}")
        total += int.from_bytes(data[offset + 4: offset + 12], "big")
    return len(utxos), total


def _row(dataset_id: str, value: Any, tx_hash: str) -> tuple[Any, ...]:
    if dataset_id == STAKING_ID:
        if not isinstance(value, dict) or value.get("txHash") != tx_hash:
            raise DataError(f"the Data API answered another transaction for {tx_hash}")
        estimated = value.get("estimatedReward")
        return (tx_hash, value.get("txType"), value.get("nodeId"), int(value["blockNumber"]),
                _utc(value.get("blockTimestamp"), "block time", tx_hash), _utc(value.get("startTimestamp"), "start", tx_hash),
                _utc(value.get("endTimestamp"), "end", tx_hash), None if estimated is None else int(estimated), value.get("rewardTxHash"))
    if not isinstance(value, dict) or value.get("error") or not isinstance(value.get("result"), dict):
        raise DataError(f"the node did not answer the reward UTXOs of {tx_hash}")
    utxos = value["result"].get("utxos") or []
    if int(value["result"].get("numFetched", -1)) != len(utxos):
        raise DataError(f"the node's reward UTXO count for {tx_hash} differs from its list")
    count, total = reward_outputs(utxos, tx_hash)
    return (tx_hash, count, total)


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid staker capture receipt: {error}") from error
    dataset_id = receipt.get("dataset_id")
    if dataset_id not in SPECS or receipt.get("schema_version") != f"{SPECS[dataset_id]['source_id']}-staker-capture/v1":
        raise DataError("unsupported staker capture receipt")
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), dataset_id):
        raise DataError("staker capture contract hash differs")
    summary = receipt["responses"][0]
    try:
        body = (capture_dir / summary["path"]).read_bytes()
    except OSError as error:
        raise DataError("missing captured staker lines") from error
    if sha256(body) != summary["sha256"] or len(body) != summary["bytes"]:
        raise DataError("captured staker lines hash or size differs")
    lines, records = body.splitlines(), receipt.get("records", [])
    if len(lines) != len(records) or len(lines) != summary["records"]:
        raise DataError("captured staker lines differ from the receipt")
    rows = []
    for line, record in zip(lines, records):
        if sha256(line) != record["sha256"] or len(line) != record["bytes"]:
            raise DataError(f"staker line {record['staking_transaction_hash']} differs from its record")
        rows.append(_row(dataset_id, json.loads(line), record["staking_transaction_hash"]))
    if len({row[0] for row in rows}) != len(rows):
        raise DataError("a staking transaction repeats")
    return receipt, rows


def _summary(dataset_id: str, rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    if dataset_id == STAKING_ID:
        types: dict[str, int] = {}
        for row in rows:
            types[row[1]] = types.get(row[1], 0) + 1
        return {"rows": len(rows), "rows_by_tx_type": dict(sorted(types.items())), "rows_without_estimated_reward": sum(row[7] is None for row in rows)}
    return {"rows": len(rows), "rows_without_reward_utxo": sum(row[1] == 0 for row in rows), "realized_reward_navax": sum(row[2] for row in rows)}


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    table = _spec(dataset_id)["table"]
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{table}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    build_preview(dataset_id, capture_dir, output)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    receipt, rows = read_rows(capture_dir)
    if receipt["dataset_id"] != dataset_id:
        raise DataError(f"the capture is of {receipt['dataset_id']}, not {dataset_id}")
    columns = COLUMNS[dataset_id]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet = temporary / f"{_spec(dataset_id)['table']}.parquet"
        connection = duckdb.connect()
        try:
            connection.execute(f"CREATE TABLE rows({', '.join(f'{name} {kind}' for name, kind in columns.items())})")
            connection.executemany(f"INSERT INTO rows VALUES ({', '.join('?' for _ in columns)})", rows)
            connection.execute("COPY (SELECT * FROM rows ORDER BY staking_transaction_hash) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
        finally:
            connection.close()
        result = {
            "schema_version": "staker-build/v1", "dataset_id": dataset_id, "dataset_schema": dataset(load_catalog(), dataset_id)["fields"],
            "source_capture_id": receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": _summary(dataset_id, rows),
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
        raise DataError("the staker captures take no --against directory")
    receipt, rows = read_rows(capture_dir)
    dataset_id = receipt["dataset_id"]
    findings: list[str] = []
    checked = ["capture hashes", "one record per staking transaction", "record identity"]
    if dataset_id == REWARDS_ID:
        checked.append("reward outputs are AVAX transfer outputs")
    if dataset_dir is not None:
        checked.extend(["build hashes", "Parquet rows"])
        try:
            built = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
            parquet = dataset_dir / f"{_spec(dataset_id)['table']}.parquet"
            data = parquet.read_bytes()
            if built["source_capture_id"] != receipt["capture_id"] or len(data) != built["outputs"][0]["bytes"] or sha256(data) != built["outputs"][0]["sha256"]:
                findings.append("build receipt or Parquet hash differs")
            connection = duckdb.connect()
            try:
                actual = connection.execute("SELECT * FROM read_parquet(?) ORDER BY staking_transaction_hash", [str(parquet)]).fetchall()
            finally:
                connection.close()
            if actual != sorted(rows):
                findings.append("Parquet rows differ from the captured records")
        except (OSError, KeyError, ValueError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid staker dataset output: {error}")
    return {"dataset_id": dataset_id, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": {**_summary(dataset_id, rows), "retries": receipt.get("retries", 0)}, "findings": findings}
