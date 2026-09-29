"""Walk P-Chain blocks by height from a public node, a source independent of the Snowflake share.

``platform.getBlockByHeight`` with JSON encoding returns a block's id, parent, height, time, and every transaction with
its inputs, outputs, and staked outputs. The JSON names no transaction type, so the type is read from the fields the
transaction carries (``TX_TYPES``, from the avalanchego v1.15.0 JSON tags), and a transaction with fields no type
declares stops the build rather than being skipped. A block without transactions is a commit or an abort of the
proposal before it, or an empty standard block that only moves the chain's time forward. The JSON cannot tell these
apart, so the walk also reads that block in hex, whose bytes 2 to 6 are the codec type ID: 30 is an abort, 31 a
commit, and 32 a standard block.

One height is one JSON line, the node's responses in request order, written as it arrives, so a walk shows its
progress on disk, retries a refused request, keeps its lines on failure, and continues with ``resume=<kept directory>``.
``extend=<earlier capture directory>`` starts from an earlier walk's lines, checked against its receipt, and reads only
the heights after it, so a daily run costs one day of blocks. A walk to the head ends at the height for which the node
reports its supply counter (``platform.getCurrentSupply``), and the receipt keeps both as ``node_supply``.

``x-chain-rpc.blocks`` walks the X-Chain the same way with ``avm.getBlockByHeight``. Its blocks are linearized standard
blocks, and its five transaction types are read from their fields the same way.
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

from . import __version__
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

DATASET_ID = "p-chain-rpc.blocks"
X_DATASET_ID = "x-chain-rpc.blocks"
DATASET_IDS = (DATASET_ID, X_DATASET_ID)
SOURCE_ID = "avalanche-p-chain-rpc"
ENDPOINT_ID = "get-block-by-height"
HEIGHT_ENDPOINT_ID = "get-height"
SUPPLY_ENDPOINT_ID = "get-current-supply"
TABLE = "p-chain-blocks"
SCHEMA = "p-chain-rpc-blocks-capture/v1"
PROGRESS = "progress.jsonl"
RAW = "raw/blocks.jsonl"
ATTEMPTS = 8
RETRY_SECONDS = 2.0
MAX_BLOCKS = 1_000_000
MAX_WORKERS = 8
AVAX_ASSET_ID = "FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z"
# Fields every transaction that embeds a BaseTx carries, and the extra fields that name each type.
BASE_FIELDS = frozenset({"networkID", "blockchainID", "inputs", "outputs", "memo"})
TX_TYPES = {
    frozenset(): "BaseTx",
    frozenset({"txID"}): "RewardValidatorTx",
    frozenset({"txID", "timestamp"}): "RewardAutoRenewedValidatorTx",
    frozenset({"time"}): "AdvanceTimeTx",
    frozenset({"validator", "stake", "rewardsOwner", "shares"}): "AddValidatorTx",
    frozenset({"validator", "stake", "rewardsOwner"}): "AddDelegatorTx",
    frozenset({"validator", "subnetAuthorization"}): "AddSubnetValidatorTx",
    frozenset({"subnetID", "validator", "signer", "stake", "validationRewardsOwner", "delegationRewardsOwner", "shares"}):
        "AddPermissionlessValidatorTx",
    frozenset({"subnetID", "validator", "stake", "rewardsOwner"}): "AddPermissionlessDelegatorTx",
    frozenset({"nodeID", "signer", "stake", "validationRewardsOwner", "delegationRewardsOwner", "validatorAuthority",
               "delegationShares", "autoCompoundRewardShares", "period"}): "AddAutoRenewedValidatorTx",
    frozenset({"txID", "auth", "autoCompoundRewardShares", "period"}): "SetAutoRenewedValidatorConfigTx",
    frozenset({"nodeID", "subnetID", "subnetAuthorization"}): "RemoveSubnetValidatorTx",
    frozenset({"owner"}): "CreateSubnetTx",
    frozenset({"subnetID", "chainName", "vmID", "fxIDs", "genesisData", "subnetAuthorization"}): "CreateChainTx",
    frozenset({"sourceChain", "importedInputs"}): "ImportTx",
    frozenset({"destinationChain", "exportedOutputs"}): "ExportTx",
    frozenset({"subnetID", "assetID", "initialSupply", "maximumSupply", "minConsumptionRate", "maxConsumptionRate",
               "minValidatorStake", "maxValidatorStake", "minStakeDuration", "maxStakeDuration", "minDelegationFee",
               "minDelegatorStake", "maxValidatorWeightFactor", "uptimeRequirement", "subnetAuthorization"}): "TransformSubnetTx",
    frozenset({"subnetID", "subnetAuthorization", "newOwner"}): "TransferSubnetOwnershipTx",
    frozenset({"subnetID", "chainID", "address", "validators", "subnetAuthorization"}): "ConvertSubnetToL1Tx",
    frozenset({"balance", "proofOfPossession", "message"}): "RegisterL1ValidatorTx",
    frozenset({"message"}): "SetL1ValidatorWeightTx",
    frozenset({"validationID", "balance"}): "IncreaseL1ValidatorBalanceTx",
    frozenset({"validationID", "disableAuthorization"}): "DisableL1ValidatorTx",
}
# Transactions that do not embed a BaseTx and so carry only their own fields.
BARE_TYPES = frozenset({"RewardValidatorTx", "RewardAutoRenewedValidatorTx", "AdvanceTimeTx"})
HEX_BLOCK_TYPES = {30: "abort", 31: "commit", 32: "standard"}
X_TX_TYPES = {
    frozenset(): "BaseTx",
    frozenset({"sourceChain", "importedInputs"}): "ImportTx",
    frozenset({"destinationChain", "exportedOutputs"}): "ExportTx",
    frozenset({"name", "symbol", "denomination", "initialStates"}): "CreateAssetTx",
    frozenset({"operations"}): "OperationTx",
}
CHAINS = {
    DATASET_ID: {"source_id": SOURCE_ID, "prefix": "platform", "table": TABLE, "schema": SCHEMA, "supply": True},
    X_DATASET_ID: {"source_id": "avalanche-x-chain-rpc", "prefix": "avm", "table": "x-chain-blocks", "schema": "x-chain-rpc-blocks-capture/v1", "supply": False},
}
COLUMNS = {
    "block_height": "BIGINT",
    "block_id": "VARCHAR",
    "parent_id": "VARCHAR",
    "block_time": "TIMESTAMP",
    "block_type": "VARCHAR",
    "tx_index": "INTEGER",
    "transaction_hash": "VARCHAR",
    "tx_type": "VARCHAR",
    "input_navax": "BIGINT",
    "output_navax": "BIGINT",
    "staked_navax": "BIGINT",
    "unsigned_tx": "VARCHAR",
}


def _parameters(parameters: dict[str, str] | None) -> dict[str, Any]:
    values = dict(parameters or {})
    unknown = set(values) - {"from_height", "to_height", "workers", "resume", "extend"}
    if unknown:
        raise DataError(f"unknown parameters: {', '.join(sorted(unknown))}")
    if "from_height" not in values and "extend" not in values:
        raise DataError("provide from_height=<first P-Chain height>, or extend=<earlier capture directory>")
    try:
        workers = int(values.get("workers", 4))
        from_height = int(values["from_height"]) if "from_height" in values else None
        to_height = values.get("to_height", "head")
        to_height = to_height if to_height == "head" else int(to_height)
    except ValueError as error:
        raise DataError("from_height and workers are integers, and to_height an integer or head") from error
    if not 1 <= workers <= MAX_WORKERS or (from_height is not None and from_height < 0):
        raise DataError(f"workers must be between 1 and {MAX_WORKERS}, and from_height at least 0")
    return {"from_height": from_height, "to_height": to_height, "workers": workers,
            **{key: values[key] for key in ("resume", "extend") if values.get(key)}}


def _chain(dataset_id: str) -> dict[str, Any]:
    if dataset_id not in CHAINS:
        raise DataError(f"unknown dataset: {dataset_id}")
    return CHAINS[dataset_id]


def _endpoint(catalog: dict[str, Any], endpoint_id: str = ENDPOINT_ID, dataset_id: str = DATASET_ID) -> str:
    provider = source(catalog, _chain(dataset_id)["source_id"])
    return next(item["url"] for item in provider["endpoints"] if item["id"] == endpoint_id)


def _payload(height: int, encoding: str, request_id: int, prefix: str = "platform") -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": f"{prefix}.getBlockByHeight", "params": {"height": str(height), "encoding": encoding}, "id": request_id}


def _read_receipt(capture_dir: Path) -> dict[str, Any]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid P-Chain block capture receipt: {error}") from error
    dataset_id = receipt.get("dataset_id")
    if dataset_id not in CHAINS or receipt.get("schema_version") != CHAINS[dataset_id]["schema"]:
        raise DataError("unsupported block capture receipt")
    return receipt


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    chain = _chain(dataset_id)
    values = _parameters(parameters)
    if "extend" in values:
        earlier = _read_receipt(Path(values["extend"]))
        if values["from_height"] not in (None, earlier["from_height"]):
            raise DataError("an extended walk starts where the earlier walk started")
        values["from_height"] = earlier["from_height"]
    catalog = load_catalog()
    return {
        "dataset_id": dataset_id,
        "source_id": chain["source_id"],
        "output": str(output),
        "endpoint": _endpoint(catalog, ENDPOINT_ID, dataset_id),
        **values,
        "writes": [RAW, "capture.json"],
        "overwrite": False,
    }


def _head(endpoint: str, timeout: float, request: Callable[..., tuple[bytes, dict[str, Any]]], prefix: str = "platform") -> int:
    body, _ = request(endpoint, timeout, body_json={"jsonrpc": "2.0", "method": f"{prefix}.getHeight", "params": {}, "id": 1})
    try:
        return int(json.loads(body)["result"]["height"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise DataError("the node did not report its height") from error


def _current_supply(endpoint: str, timeout: float, request: Callable[..., tuple[bytes, dict[str, Any]]]) -> dict[str, int]:
    """The node's Primary Network supply counter and the height it holds for, the anchor of the supply reconstruction."""
    body, _ = request(endpoint, timeout, body_json={"jsonrpc": "2.0", "method": "platform.getCurrentSupply", "params": {}, "id": 1})
    try:
        result = json.loads(body)["result"]
        return {"height": int(result["height"]), "supply_navax": int(result["supply"])}
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise DataError("the node did not report its current supply and height") from error


def _kept(directory: Path, receipt_records: list[dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], list[bytes]]:
    """The records and lines of a kept or earlier walk, cut back to the longest prefix where each line matches its record."""
    if receipt_records is None:
        try:
            records = [json.loads(line) for line in (directory / PROGRESS).read_text(encoding="utf-8").splitlines()[1:]]
        except (OSError, json.JSONDecodeError) as error:
            raise DataError(f"cannot resume from {directory}: {error}") from error
    else:
        records = receipt_records
    try:
        lines = (directory / RAW).read_bytes().splitlines()
    except OSError as error:
        raise DataError(f"no block lines at {directory}") from error
    kept = 0
    for record, line in zip(records, lines):
        if sha256(line) != record["sha256"] or len(line) != record["bytes"]:
            break
        kept += 1
    if kept < min(len(records), len(lines)) or (receipt_records is not None and kept != len(records)):
        raise DataError(f"block line {kept + 1} at {directory} differs from its record")
    return records[:kept], lines[:kept]


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
    catalog = load_catalog()
    endpoint = preview["endpoint"]
    # Walked to the head, the walk ends at the height the node's supply counter holds for, so the counter anchors it.
    chain = _chain(dataset_id)
    anchor = (_current_supply(_endpoint(catalog, SUPPLY_ENDPOINT_ID, dataset_id), timeout, request)
              if chain["supply"] and preview["to_height"] == "head" else None)
    head = anchor["height"] if anchor else _head(_endpoint(catalog, HEIGHT_ENDPOINT_ID, dataset_id), timeout, request, chain["prefix"])
    to_height = head if preview["to_height"] == "head" else preview["to_height"]
    if to_height > head or to_height < preview["from_height"]:
        raise DataError(f"to_height must be between from_height and the node's height {head}")
    output.parent.mkdir(parents=True, exist_ok=True)
    header = {"endpoint": endpoint, "from_height": preview["from_height"]}
    if "resume" in preview:
        temporary = Path(preview["resume"])
        try:
            kept_header = json.loads((temporary / PROGRESS).read_text(encoding="utf-8").splitlines()[0])
        except (OSError, IndexError, json.JSONDecodeError) as error:
            raise DataError(f"cannot resume from {temporary}: {error}") from error
        if kept_header != header:
            raise DataError("cannot resume: the kept walk starts elsewhere or reads a different endpoint")
        records, lines = _kept(temporary)
    else:
        temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
        (temporary / "raw").mkdir()
        records, lines = [], []
        if "extend" in preview:
            earlier_dir = Path(preview["extend"])
            earlier = _read_receipt(earlier_dir)
            if earlier["endpoint"] != endpoint:
                shutil.rmtree(temporary, ignore_errors=True)
                raise DataError("cannot extend a walk of a different endpoint")
            records, lines = _kept(earlier_dir, earlier["blocks"])
    (temporary / RAW).write_bytes(b"".join(line + b"\n" for line in lines))
    (temporary / PROGRESS).write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in [header, *records]), encoding="utf-8")
    start = records[-1]["block_height"] + 1 if records else preview["from_height"]
    todo = list(range(start, to_height + 1))
    if len(records) + len(todo) > MAX_BLOCKS:
        raise DataError(f"a walk holds at most {MAX_BLOCKS} blocks")
    retries = 0

    def call(payload: dict[str, Any]) -> tuple[bytes, int]:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                body, _ = request(endpoint, timeout, body_json=payload)
                return body, attempt - 1
            except DataError as error:
                # The public node answers 502 now and then. Wait, doubling, about four minutes in all, then keep the lines.
                if attempt == ATTEMPTS or not isinstance(error.__cause__, (OSError, urllib.error.URLError)) and "HTTP" not in str(error):
                    raise
                time.sleep(RETRY_SECONDS * 2 ** (attempt - 1))
        raise AssertionError("unreachable")

    def fetch(height: int) -> tuple[int, bytes, int]:
        body, retried = call(_payload(height, "json", 1, chain["prefix"]))
        answers = [json.loads(body)]
        block = _result_block(answers[0], height)
        if not _transactions(block) and chain["supply"]:
            hex_body, hex_retried = call(_payload(height, "hex", 2, chain["prefix"]))
            answers.append(json.loads(hex_body))
            retried += hex_retried
        return height, json.dumps(answers, separators=(",", ":"), sort_keys=True).encode(), retried

    try:
        batch_size = preview["workers"] * 16
        with (temporary / RAW).open("ab") as raw, (temporary / PROGRESS).open("a", encoding="utf-8") as progress, \
                ThreadPoolExecutor(max_workers=preview["workers"]) as pool:
            for offset in range(0, len(todo), batch_size):
                # map yields in height order and raises at the first failed block, so the lines on disk stay an
                # ascending prefix a resume can continue.
                results = pool.map(fetch, todo[offset: offset + batch_size])
                while True:
                    try:
                        height, line, retried = next(results)
                    except StopIteration:
                        break
                    except (DataError, json.JSONDecodeError) as error:
                        raw.flush()
                        progress.flush()
                        raise DataError(f"{error}; {len(records)} blocks kept at {temporary}") from error
                    retries += retried
                    try:
                        _rows(json.loads(line), height, dataset_id)
                    except DataError as error:
                        raise DataError(f"{error}; {len(records)} blocks kept at {temporary}") from error
                    raw.write(line + b"\n")
                    record = {"block_height": height, "bytes": len(line), "sha256": sha256(line)}
                    records.append(record)
                    progress.write(json.dumps(record, sort_keys=True) + "\n")
                raw.flush()
                progress.flush()
        if not records:
            raise DataError("the walk read no blocks")
        completed_at = now()
        body_all = (temporary / RAW).read_bytes()
        identity = sha256(canonical_bytes({"completed_at": completed_at, "sha256": sha256(body_all)}))
        receipt = {
            "schema_version": chain["schema"],
            "capture_id": f"capture:{chain['source_id']}:{completed_at}:{identity[:12]}",
            "dataset_id": dataset_id,
            "source_id": chain["source_id"],
            "completed_at": completed_at,
            "contract_sha256": contract_hash(catalog, dataset_id),
            "tool": f"avalanche-research@{__version__}",
            "endpoint": endpoint,
            "from_height": preview["from_height"],
            "to_height": to_height,
            "node_height": head,
            **({"node_supply": anchor} if anchor else {}),
            **({"extends_capture_id": _read_receipt(Path(preview["extend"]))["capture_id"]} if "extend" in preview else {}),
            "retries": retries,
            "responses": [{"endpoint_id": ENDPOINT_ID, "path": RAW, "blocks": len(records), "bytes": len(body_all), "sha256": sha256(body_all)}],
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


def _result_block(answer: Any, height: int) -> dict[str, Any]:
    if not isinstance(answer, dict) or answer.get("jsonrpc") != "2.0" or answer.get("error") or not isinstance(answer.get("result"), dict):
        raise DataError(f"the node did not answer block {height}: {answer.get('error') if isinstance(answer, dict) else answer}")
    block = answer["result"].get("block")
    if not isinstance(block, dict) or block.get("height") != height:
        raise DataError(f"the node answered another block for {height}")
    return block


def _transactions(block: dict[str, Any]) -> list[dict[str, Any]]:
    """The block's transactions in order: a proposal block's one transaction, or a standard block's list."""
    return list(block.get("txs") or []) + ([block["tx"]] if block.get("tx") else [])


def tx_type(unsigned: dict[str, Any]) -> str:
    """The transaction type named by the fields the node's JSON carries; an unknown set of fields is an error."""
    fields = frozenset(unsigned)
    kind = TX_TYPES.get(fields - BASE_FIELDS)
    if kind is None or (kind in BARE_TYPES) != (not fields & BASE_FIELDS) or (kind not in BARE_TYPES and not BASE_FIELDS <= fields):
        raise DataError(f"a transaction carries fields no known type declares: {sorted(fields)}")
    return kind


def _amount(item: dict[str, Any], key: str, tx_hash: str) -> int:
    """The amount of one input or output, through a stakeable lock if there is one."""
    inner = item.get("input" if key in ("inputs", "importedInputs") else "output")
    while isinstance(inner, dict) and "amount" not in inner and isinstance(inner.get("input", inner.get("output")), dict):
        inner = inner.get("input", inner.get("output"))
    try:
        amount = int(inner["amount"])
    except (KeyError, TypeError, ValueError) as error:
        raise DataError(f"{key} of {tx_hash} has no integer amount") from error
    if amount < 0:
        raise DataError(f"{key} of {tx_hash} has a negative amount")
    return amount


def _avax(unsigned: dict[str, Any], keys: tuple[str, ...], tx_hash: str) -> int:
    total = 0
    for key in keys:
        items = unsigned.get(key)
        if items is None:
            continue
        if not isinstance(items, list):
            raise DataError(f"{key} of {tx_hash} is not a list")
        total += sum(_amount(item, key, tx_hash) for item in items if item.get("assetID") == AVAX_ASSET_ID)
    return total


def x_tx_type(unsigned: dict[str, Any]) -> str:
    """The X-Chain transaction type named by the fields the node's JSON carries; an unknown set of fields is an error."""
    fields = frozenset(unsigned)
    kind = X_TX_TYPES.get(fields - BASE_FIELDS)
    if kind is None or not BASE_FIELDS <= fields:
        raise DataError(f"an X-Chain transaction carries fields no known type declares: {sorted(fields)}")
    return kind


def _rows(answers: Any, height: int, dataset_id: str = DATASET_ID) -> list[tuple[Any, ...]]:
    """One row per transaction of one captured block, or one row without a transaction for a block that has none."""
    if not isinstance(answers, list) or len(answers) not in (1, 2):
        raise DataError(f"block {height} is not one or two node answers")
    block = _result_block(answers[0], height)
    if not isinstance(block.get("id"), str) or not isinstance(block.get("parentID"), str) or not isinstance(block.get("time"), int):
        raise DataError(f"block {height} has no id, parent, or time")
    block_time = datetime.fromtimestamp(block["time"], UTC).replace(tzinfo=None)
    head = (height, block["id"], block["parentID"], block_time)
    transactions = _transactions(block)
    if dataset_id == X_DATASET_ID:
        if not transactions or len(answers) != 1:
            raise DataError(f"X-Chain block {height} has no transactions")
        return [(*head, "standard", index, transaction["id"], x_tx_type(transaction["unsignedTx"]),
                 _avax(transaction["unsignedTx"], ("inputs", "importedInputs"), transaction["id"]),
                 _avax(transaction["unsignedTx"], ("outputs", "exportedOutputs"), transaction["id"]), 0,
                 json.dumps(transaction["unsignedTx"], separators=(",", ":"), sort_keys=True))
                for index, transaction in enumerate(transactions)]
    if not transactions:
        if len(answers) != 2 or not isinstance(answers[1], dict) or answers[1].get("error"):
            raise DataError(f"block {height} has no transactions and no hex answer")
        encoded = (answers[1].get("result") or {}).get("block", "")
        try:
            kind = HEX_BLOCK_TYPES[int(encoded[6:14], 16)] if encoded.startswith("0x0000") else None
        except (ValueError, KeyError):
            kind = None
        if kind is None:
            raise DataError(f"block {height} has no transactions and is not a commit, an abort, or a standard block")
        return [(*head, kind, None, None, None, None, None, None, None)]
    if len(answers) != 1:
        raise DataError(f"block {height} has transactions and a hex answer")
    block_type = "proposal" if block.get("tx") else "standard"
    rows = []
    for index, transaction in enumerate(transactions):
        tx_hash, unsigned = transaction.get("id"), transaction.get("unsignedTx")
        if not isinstance(tx_hash, str) or not isinstance(unsigned, dict):
            raise DataError(f"transaction {index} of block {height} has no id or body")
        rows.append((*head, block_type, index, tx_hash, tx_type(unsigned),
                     _avax(unsigned, ("inputs", "importedInputs"), tx_hash), _avax(unsigned, ("outputs", "exportedOutputs"), tx_hash),
                     _avax(unsigned, ("stake",), tx_hash), json.dumps(unsigned, separators=(",", ":"), sort_keys=True)))
    return rows


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    receipt = _read_receipt(capture_dir)
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), receipt["dataset_id"]):
        raise DataError("block capture contract hash differs")
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
    heights = [record["block_height"] for record in records]
    if heights != list(range(receipt["from_height"], receipt["to_height"] + 1)):
        raise DataError("the captured heights are not every height from from_height to to_height once, ascending")
    rows: list[tuple[Any, ...]] = []
    for line, record in zip(lines, records):
        if sha256(line) != record["sha256"] or len(line) != record["bytes"]:
            raise DataError(f"block line {record['block_height']} differs from its record")
        rows.extend(_rows(json.loads(line), record["block_height"], receipt["dataset_id"]))
    return receipt, rows


def _summary(receipt: dict[str, Any], rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    types: dict[str, int] = {}
    for row in rows:
        if row[7] is not None:
            types[row[7]] = types.get(row[7], 0) + 1
    return {
        "rows": len(rows),
        "blocks": receipt["to_height"] - receipt["from_height"] + 1,
        "from_height": receipt["from_height"],
        "to_height": receipt["to_height"],
        "first_block_time": rows[0][3].isoformat() if rows else None,
        "last_block_time": rows[-1][3].isoformat() if rows else None,
        "transactions": sum(row[6] is not None for row in rows),
        "transactions_by_type": dict(sorted(types.items())),
        "blocks_by_type": {kind: len({row[0] for row in rows if row[4] == kind}) for kind in ("standard", "proposal", "commit", "abort")},
    }


def _chain_findings(rows: list[tuple[Any, ...]]) -> list[str]:
    """Every block's parent is the block one height below it, and every block and transaction id appears once."""
    blocks: dict[int, tuple[str, str]] = {}
    for row in rows:
        blocks.setdefault(row[0], (row[1], row[2]))
    findings = []
    broken = sum(1 for height, (_, parent) in blocks.items() if height - 1 in blocks and blocks[height - 1][0] != parent)
    if broken:
        findings.append(f"{broken} blocks do not name the block below them as parent")
    if len({block_id for block_id, _ in blocks.values()}) != len(blocks):
        findings.append("a block id repeats")
    hashes = [row[6] for row in rows if row[6] is not None]
    if len(set(hashes)) != len(hashes):
        findings.append(f"{len(hashes) - len(set(hashes))} transaction hashes repeat")
    return findings


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{_chain(dataset_id)['table']}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    build_preview(dataset_id, capture_dir, output)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    receipt, rows = read_rows(capture_dir)
    if receipt["dataset_id"] != dataset_id:
        raise DataError(f"the capture is of {receipt['dataset_id']}, not {dataset_id}")
    findings = _chain_findings(rows)
    if findings:
        raise DataError("; ".join(findings))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet = temporary / f"{_chain(dataset_id)['table']}.parquet"
        connection = duckdb.connect()
        try:
            connection.execute(f"CREATE TABLE rows({', '.join(f'{name} {kind}' for name, kind in COLUMNS.items())})")
            connection.executemany(f"INSERT INTO rows VALUES ({', '.join('?' for _ in COLUMNS)})", rows)
            connection.execute("COPY (SELECT * FROM rows ORDER BY block_height, tx_index) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
        finally:
            connection.close()
        result = {
            "schema_version": "p-chain-rpc-blocks-build/v1",
            "dataset_id": dataset_id,
            "dataset_schema": dataset(load_catalog(), dataset_id)["fields"],
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
    if against is not None:
        raise DataError("the P-Chain block walk has no reference dataset check; the overlap with the share is checked by the datasets built from it")
    receipt, rows = read_rows(capture_dir)
    findings = _chain_findings(rows)
    checked = ["capture hashes", "every height once", "parent links", "unique block and transaction ids", "transaction types"]
    if dataset_dir is not None:
        checked.extend(["build hashes", "Parquet rows"])
        try:
            built = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
            parquet = dataset_dir / f"{_chain(receipt['dataset_id'])['table']}.parquet"
            data = parquet.read_bytes()
            if built["source_capture_id"] != receipt["capture_id"] or len(data) != built["outputs"][0]["bytes"] or sha256(data) != built["outputs"][0]["sha256"]:
                findings.append("build receipt or Parquet hash differs")
            connection = duckdb.connect()
            try:
                actual = connection.execute("SELECT * FROM read_parquet(?) ORDER BY block_height, tx_index", [str(parquet)]).fetchall()
            finally:
                connection.close()
            if actual != sorted(rows, key=lambda row: (row[0], -1 if row[5] is None else row[5])):
                findings.append("Parquet rows differ from the captured blocks")
        except (OSError, KeyError, ValueError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid P-Chain block dataset output: {error}")
    return {"dataset_id": receipt["dataset_id"], "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": {**_summary(receipt, rows), "retries": receipt.get("retries", 0)}, "findings": findings}
