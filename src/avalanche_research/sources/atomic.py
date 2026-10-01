"""Capture and check C-Chain atomic AVAX burns from transaction-level Data API records.

The endpoint lists newest first and takes no date filter without an address, so a dated capture walks pages backward
until it crosses the requested start. A walk over the full history is thousands of pages: each page is written to disk
as it arrives, a dropped page is retried, a failed walk keeps its pages, and ``resume=<kept directory>`` continues one.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import urllib.error
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

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

DATASET_ID = "data-api.c-chain-atomic-burn"
SOURCE_ID = "avalanche-data-api"
ENDPOINT_ID = "c-chain-atomic-transactions"
TABLE = "c-chain-atomic-burn"
AVAX_ASSET_ID = "FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z"
PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 1_000
PAGE_ATTEMPTS = 8
PAGE_RETRY_SECONDS = 5.0
# The first C block. A walk whose start lies at or before this date may run out of pages before crossing it: that is the
# end of the listing, not a truncated capture.
C_CHAIN_FIRST_DATE = date(2020, 9, 23)
PROGRESS = "progress.jsonl"
COLUMNS = {
    "transaction_hash": "VARCHAR",
    "tx_type": "VARCHAR",
    "accepted_at": "TIMESTAMP",
    "block_height": "BIGINT",
    "block_hash": "VARCHAR",
    "unlocked_navax": "BIGINT",
    "created_navax": "BIGINT",
    "burned_navax": "BIGINT",
}


def _window(parameters: dict[str, str] | None) -> tuple[int, int, int, float]:
    values = {key: value for key, value in (parameters or {}).items() if key != "resume"}
    unknown = set(values) - {"start", "end", "max_pages", "pause"}
    if unknown:
        raise DataError(f"unknown parameters: {', '.join(sorted(unknown))}")
    try:
        start = date.fromisoformat(values["start"])
        end = date.fromisoformat(values["end"])
        max_pages = int(values.get("max_pages", DEFAULT_MAX_PAGES))
        pause = float(values.get("pause", 0))
    except (KeyError, ValueError) as error:
        raise DataError("start and end must be ISO dates; max_pages must be an integer; pause must be seconds") from error
    start_at = int(datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp())
    end_at = int(datetime(end.year, end.month, end.day, tzinfo=UTC).timestamp())
    if not start_at < end_at <= int(datetime.now(UTC).timestamp()):
        raise DataError("start must precede end, and end must not be in the future")
    if not 1 <= max_pages <= 50_000:
        raise DataError("max_pages must be between 1 and 50000")
    if not 0 <= pause <= 60:
        raise DataError("pause must be between 0 and 60 seconds")
    return start_at, end_at, max_pages, pause


def _endpoint(catalog: dict[str, Any]) -> str:
    provider = source(catalog, SOURCE_ID)
    return next(item["url"] for item in provider["endpoints"] if item["id"] == ENDPOINT_ID)


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    start, end, max_pages, pause = _window(parameters)
    resume = (parameters or {}).get("resume")
    return {
        "dataset_id": dataset_id,
        "source_id": SOURCE_ID,
        "output": str(output),
        "request": _endpoint(load_catalog()),
        "start_timestamp": start,
        "end_timestamp": end,
        "max_pages": max_pages,
        "pause": pause,
        **({"resume": resume} if resume else {}),
        "writes": ["raw/page-*.json", "capture.json"],
        "overwrite": False,
    }


def _resume(preview: dict[str, Any], temporary: Path) -> list[dict[str, Any]]:
    """The page records of a kept walk, each page verified against its record, so the walk continues after them."""
    try:
        lines = (temporary / PROGRESS).read_text(encoding="utf-8").splitlines()
        header, records = json.loads(lines[0]), [json.loads(line) for line in lines[1:]]
    except (OSError, IndexError, json.JSONDecodeError) as error:
        raise DataError(f"cannot resume from {temporary}: {error}") from error
    if header.get("start_timestamp") != preview["start_timestamp"] or header.get("end_timestamp") != preview["end_timestamp"] or header.get("request") != preview["request"]:
        raise DataError("cannot resume: the kept walk has a different window or endpoint")
    if not records:
        raise DataError("cannot resume: the kept walk has no pages")
    for number, record in enumerate(records, 1):
        try:
            body = (temporary / record["path"]).read_bytes()
        except OSError as error:
            raise DataError(f"cannot resume: page {number} is missing") from error
        if record["page_index"] != number or sha256(body) != record["sha256"] or len(body) != record["bytes"]:
            raise DataError(f"cannot resume: page {number} differs from its record")
    if not records[-1]["next_page_token"]:
        raise DataError("cannot resume: the kept walk already reached its last page")
    return records


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
    output.parent.mkdir(parents=True, exist_ok=True)
    resumed = 0
    if "resume" in preview:
        temporary = Path(preview["resume"])
        records = _resume(preview, temporary)
        resumed = len(records)
        page_token, previous_oldest = records[-1]["next_page_token"], records[-1]["oldest_timestamp"]
    else:
        temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
        (temporary / "raw").mkdir()
        header = {key: preview[key] for key in ("request", "start_timestamp", "end_timestamp")}
        (temporary / PROGRESS).write_text(json.dumps(header, sort_keys=True) + "\n", encoding="utf-8")
        records, page_token, previous_oldest = [], None, None
    retries, end_of_listing = 0, False
    try:
        for number in range(resumed + 1, preview["max_pages"] + 1):
            query = {"pageSize": PAGE_SIZE}
            if page_token:
                query["pageToken"] = page_token
            url = preview["request"] + "?" + urlencode(query)
            if preview["pause"] and number > resumed + 1:
                time.sleep(preview["pause"])
            for attempt in range(1, PAGE_ATTEMPTS + 1):
                try:
                    body, metadata = request(url, timeout)
                    break
                except DataError as error:
                    # A long walk meets dropped connections and rate limits: keyless, the Data API answered HTTP 429 after
                    # about 130 pages at three a second and again after about 1,000 pages at one a second (2026-09-23), and
                    # the refusal lasts minutes. Retry the one page with a doubling wait, up to about ten minutes in all,
                    # then give up and keep the pages.
                    if attempt == PAGE_ATTEMPTS or not isinstance(error.__cause__, (OSError, urllib.error.URLError)):
                        raise DataError(f"{error} after {attempt} attempts; {number - 1} pages kept at {temporary}") from error
                    retries += 1
                    time.sleep(PAGE_RETRY_SECONDS * 2 ** (attempt - 1))
            page = json.loads(body)
            rows = page.get("transactions")
            if not isinstance(rows, list) or not rows:
                raise DataError(f"atomic page {number} has no transactions; {number - 1} pages kept at {temporary}")
            timestamps = [int(row["timestamp"]) for row in rows]
            if timestamps != sorted(timestamps, reverse=True) or (previous_oldest is not None and timestamps[0] > previous_oldest):
                raise DataError(f"atomic page {number} is not in descending time order; {number - 1} pages kept at {temporary}")
            previous_oldest = timestamps[-1]
            relative = Path("raw") / f"page-{number:05d}.json"
            (temporary / relative).write_bytes(body)
            record = {
                "endpoint_id": ENDPOINT_ID, "url": url, "page_index": number,
                "request_page_token": page_token, "next_page_token": page.get("nextPageToken"),
                "newest_timestamp": timestamps[0], "oldest_timestamp": timestamps[-1],
                "path": str(relative), "bytes": len(body), "sha256": sha256(body), **metadata,
            }
            records.append(record)
            with (temporary / PROGRESS).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
            if timestamps[-1] < preview["start_timestamp"]:
                break
            page_token = page.get("nextPageToken")
            if not page_token:
                if preview["start_timestamp"] > int(datetime(C_CHAIN_FIRST_DATE.year, C_CHAIN_FIRST_DATE.month, C_CHAIN_FIRST_DATE.day, tzinfo=UTC).timestamp()):
                    raise DataError(f"atomic pagination ended before the requested start date; {number} pages kept at {temporary}")
                end_of_listing = True
                break
        else:
            raise DataError(f"atomic pagination exceeded max_pages={preview['max_pages']} before reaching start; {len(records)} pages kept at {temporary}")
        completed_at = now()
        identity = sha256(canonical_bytes({"completed_at": completed_at, "responses": records}))
        receipt = {
            "schema_version": f"{SOURCE_ID}-capture/v1",
            "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
            "dataset_id": DATASET_ID,
            "source_id": SOURCE_ID,
            "completed_at": completed_at,
            "contract_sha256": contract_hash(catalog, DATASET_ID),
            "tool": f"avalanche-research@{__version__}",
            "start_timestamp": preview["start_timestamp"],
            "end_timestamp": preview["end_timestamp"],
            "end_of_listing": end_of_listing,
            "resumed_pages": resumed,
            "retries": retries,
            "responses": records,
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        (temporary / PROGRESS).unlink()
        os.replace(temporary, output)
        return receipt
    except Exception:
        # A failed walk keeps its pages, so `resume=<that directory>` continues it instead of starting over.
        if not any((temporary / "raw").glob("page-*.json")):
            shutil.rmtree(temporary, ignore_errors=True)
        raise


def _amount(items: Any) -> int:
    if not isinstance(items, list):
        raise DataError("atomic transaction is missing asset amounts")
    total = 0
    for item in items:
        if item.get("assetId") == AVAX_ASSET_ID:
            if item.get("denomination") != 9 or item.get("symbol") != "AVAX":
                raise DataError("atomic AVAX asset metadata is inconsistent")
            amount = int(item["amount"])
            if amount < 0:
                raise DataError("atomic AVAX amount is negative")
            total += amount
    return total


def _utxo_amount(items: Any) -> int:
    if not isinstance(items, list):
        raise DataError("atomic transaction is missing inputs or outputs")
    return _amount([item["asset"] for item in items])


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    catalog = load_catalog()
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid atomic capture receipt: {error}") from error
    if receipt.get("dataset_id") != DATASET_ID or receipt.get("schema_version") != f"{SOURCE_ID}-capture/v1":
        raise DataError("unsupported atomic capture receipt")
    if receipt.get("contract_sha256") != contract_hash(catalog, DATASET_ID):
        raise DataError("atomic capture contract hash differs")
    records = receipt.get("responses", [])
    if not records or (records[-1]["oldest_timestamp"] >= receipt["start_timestamp"] and not receipt.get("end_of_listing")):
        raise DataError("atomic capture does not cover the requested start")
    rows: list[tuple[Any, ...]] = []
    seen: set[str] = set()
    previous_token: str | None = None
    previous_oldest: int | None = None
    for number, record in enumerate(records, 1):
        if record["page_index"] != number or record["request_page_token"] != previous_token:
            raise DataError("atomic capture has a missing or disconnected page")
        path = capture_dir / record["path"]
        try:
            body = path.read_bytes()
        except OSError as error:
            raise DataError(f"missing captured atomic page {number}") from error
        if sha256(body) != record["sha256"] or len(body) != record["bytes"]:
            raise DataError(f"captured atomic page {number} hash or size differs")
        page = json.loads(body)
        transactions = page.get("transactions")
        if not isinstance(transactions, list) or not transactions:
            raise DataError(f"atomic page {number} is empty")
        timestamps = [int(item["timestamp"]) for item in transactions]
        if (timestamps != sorted(timestamps, reverse=True)
                or timestamps[0] != record["newest_timestamp"]
                or timestamps[-1] != record["oldest_timestamp"]
                or page.get("nextPageToken") != record["next_page_token"]
                or (previous_oldest is not None and timestamps[0] > previous_oldest)):
            raise DataError(f"atomic page {number} ordering or receipt differs")
        previous_token = record["next_page_token"]
        previous_oldest = timestamps[-1]
        for item in transactions:
            timestamp = int(item["timestamp"])
            if not receipt["start_timestamp"] <= timestamp < receipt["end_timestamp"]:
                continue
            tx_hash = item["txHash"]
            if tx_hash in seen:
                raise DataError(f"repeated atomic transaction: {tx_hash}")
            seen.add(tx_hash)
            if item["txType"] not in {"ImportTx", "ExportTx"}:
                raise DataError(f"unexpected C atomic transaction type: {item['txType']}")
            unlocked = _amount(item["amountUnlocked"])
            created = _amount(item["amountCreated"])
            inputs = item["consumedUtxos"] if item["txType"] == "ImportTx" else item["evmInputs"]
            outputs = item["evmOutputs"] if item["txType"] == "ImportTx" else item["emittedUtxos"]
            if unlocked != _utxo_amount(inputs) or created != _utxo_amount(outputs):
                raise DataError(f"atomic AVAX summary differs from transaction inputs or outputs: {tx_hash}")
            burned = unlocked - created
            if created < 0 or (item["txType"] == "ExportTx" and (unlocked <= 0 or burned < 0)):
                raise DataError(f"invalid atomic AVAX balance: {tx_hash}")
            if unlocked <= 0 or burned < 0:
                # An import whose consumed UTXOs the API lists incompletely: its burn is unsettled here, and
                # c-chain-rpc.atomic-transactions settles it from the node's signed transaction.
                burned = None
            rows.append((
                tx_hash, item["txType"], datetime.fromtimestamp(timestamp, UTC).replace(tzinfo=None),
                int(item["blockHeight"]), item["blockHash"], unlocked, created, burned,
            ))
    return receipt, rows


def _summary(rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "import_rows": sum(row[1] == "ImportTx" for row in rows),
        "export_rows": sum(row[1] == "ExportTx" for row in rows),
        "distinct_blocks": len({row[3] for row in rows}),
        "burned_navax": sum(row[7] for row in rows if row[7] is not None),
        "unsettled_rows": sum(row[7] is None for row in rows),
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
    definition = dataset(load_catalog(), DATASET_ID)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet = temporary / f"{TABLE}.parquet"
        connection = duckdb.connect()
        try:
            connection.execute(f"CREATE TABLE rows ({', '.join(f'{name} {kind}' for name, kind in COLUMNS.items())})")
            if rows:
                connection.executemany(f"INSERT INTO rows VALUES ({', '.join('?' for _ in COLUMNS)})", rows)
            connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
        finally:
            connection.close()
        result = {
            "schema_version": "data-api-build/v1", "dataset_id": DATASET_ID,
            "dataset_schema": definition["fields"], "source_capture_id": receipt["capture_id"],
            "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": _summary(rows),
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
        raise DataError("atomic burn has no built cross-check dataset; use the documented Snowflake block audit")
    receipt, rows = read_rows(capture_dir)
    findings: list[str] = []
    checked = ["capture hashes", "pagination continuity", "date coverage", "unique transactions", "AVAX balance"]
    if dataset_dir is not None:
        checked.extend(["build hashes", "Parquet rows"])
        try:
            built = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
            if built["source_capture_id"] != receipt["capture_id"] or built["summary"] != _summary(rows):
                findings.append("build receipt differs from captured rows")
            parquet = dataset_dir / f"{TABLE}.parquet"
            data = parquet.read_bytes()
            if len(data) != built["outputs"][0]["bytes"] or sha256(data) != built["outputs"][0]["sha256"]:
                findings.append("Parquet hash or size differs")
            connection = duckdb.connect()
            try:
                actual = connection.execute("SELECT * FROM read_parquet(?) ORDER BY transaction_hash", [str(parquet)]).fetchall()
            finally:
                connection.close()
            if actual != sorted(rows):
                findings.append("Parquet rows differ from captured transactions")
        except (OSError, KeyError, ValueError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid atomic dataset output: {error}")
    return {
        "dataset_id": DATASET_ID, "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention", "checked": checked,
        "summary": {**_summary(rows), "pages": len(receipt["responses"]), "end_of_listing": bool(receipt.get("end_of_listing")), "retries": receipt.get("retries", 0)},
        "findings": findings,
    }
