"""Capture C-Chain block records from the Data API for the blocks the Snowflake share cannot account for.

The share's C block gaps dataset lists the heights: absent blocks and blocks present without all their receipts.
Each block's Data API record carries the fees spent in it, an integer number of wei that equals the sum of gas used
times effective gas price over the block's receipts (checked 2026-09-23 against the share on complete blocks), its
timestamp, and its transaction count. One record is one JSON line written as it arrives, so a walk over many
thousand blocks shows its progress on disk, retries a refused request, keeps its lines on failure, and continues
with ``resume=<kept directory>``.
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

from . import __version__, datasets
from .catalog import DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256, source
from .rest import _request

DATASET_ID = "data-api.c-chain-block-fees"
SOURCE_ID = "avalanche-data-api"
ENDPOINT_ID = "c-chain-block"
GAPS_ID = "snowflake.c-chain-block-gaps"
TABLE = "c-chain-block-fees"
PROGRESS = "progress.jsonl"
RAW = "raw/blocks.jsonl"
PAGE_ATTEMPTS = 8
PAGE_RETRY_SECONDS = 5.0
MAX_BLOCKS = 200_000
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
    unknown = set(values) - {"gaps", "kind", "limit", "pause", "resume"}
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
    except ValueError as error:
        raise DataError("limit must be an integer and pause seconds") from error
    if not 1 <= limit <= MAX_BLOCKS or not 0 <= pause <= 60:
        raise DataError(f"limit must be between 1 and {MAX_BLOCKS}; pause between 0 and 60 seconds")
    return {"gaps": values["gaps"], "kind": kind, "limit": limit, "pause": pause, **({"resume": values["resume"]} if values.get("resume") else {})}


def _endpoint(catalog: dict[str, Any]) -> str:
    provider = source(catalog, SOURCE_ID)
    return next(item["url"] for item in provider["endpoints"] if item["id"] == ENDPOINT_ID)


def gap_heights(run: str, kind: str, root: Path | None = None) -> tuple[dict[str, Any], list[int]]:
    """The heights a gaps run lists, ascending, and that run's receipt."""
    record = datasets.receipt(GAPS_ID, run, root)
    parquet = datasets.parquet_path(GAPS_ID, run, root)
    connection = duckdb.connect()
    try:
        clause = "" if kind == "all" else f"WHERE kind = '{kind}'"
        heights = [row[0] for row in connection.execute(f"SELECT DISTINCT block_height FROM read_parquet(?) {clause} ORDER BY 1", [str(parquet)]).fetchall()]
    finally:
        connection.close()
    return record, heights


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    values = _parameters(parameters)
    record, heights = gap_heights(values["gaps"], values["kind"], root)
    return {
        "dataset_id": DATASET_ID,
        "source_id": SOURCE_ID,
        "output": str(output),
        "endpoint": _endpoint(load_catalog()),
        "gaps_run": values["gaps"],
        "gaps_capture_id": record["capture"]["capture_id"],
        "kind": values["kind"],
        "blocks": len(heights),
        "limit": values["limit"],
        "pause": values["pause"],
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
    if len(bodies) != len(records):
        raise DataError("cannot resume: the kept walk's lines and records differ")
    for number, (record, body) in enumerate(zip(records, bodies), 1):
        if sha256(body) != record["sha256"] or len(body) != record["bytes"]:
            raise DataError(f"cannot resume: block line {number} differs from its record")
    return records


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
    _, heights = gap_heights(preview["gaps_run"], preview["kind"], root)
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
    try:
        with (temporary / RAW).open("ab") as raw, (temporary / PROGRESS).open("a", encoding="utf-8") as progress:
            for number, height in enumerate(todo, 1):
                if preview["pause"] and number > 1:
                    time.sleep(preview["pause"])
                url = f"{preview['endpoint']}/{height}"
                for attempt in range(1, PAGE_ATTEMPTS + 1):
                    try:
                        body, metadata = request(url, timeout)
                        break
                    except DataError as error:
                        # The Data API refuses a keyless client for minutes after about a thousand requests. Wait, doubling,
                        # up to about ten minutes in all, then keep the lines for a later resume.
                        if attempt == PAGE_ATTEMPTS or not isinstance(error.__cause__, (OSError, urllib.error.URLError)):
                            raise DataError(f"{error} after {attempt} attempts; {len(records)} blocks kept at {temporary}") from error
                        retries += 1
                        time.sleep(PAGE_RETRY_SECONDS * 2 ** (attempt - 1))
                line = body.strip()
                if b"\n" in line:
                    line = json.dumps(json.loads(body), separators=(",", ":"), sort_keys=True).encode()
                value = json.loads(line)
                if str(value.get("blockNumber")) != str(height):
                    raise DataError(f"the Data API answered block {value.get('blockNumber')} for {height}; {len(records)} blocks kept at {temporary}")
                raw.write(line + b"\n")
                raw.flush()
                record = {"block_height": height, "url": url, "bytes": len(line), "sha256": sha256(line), **metadata}
                records.append(record)
                progress.write(json.dumps(record, sort_keys=True) + "\n")
                progress.flush()
        if not records:
            raise DataError("the gaps run lists no blocks of that kind")
        completed_at = now()
        identity = sha256(canonical_bytes({"completed_at": completed_at, "responses": records}))
        body_all = (temporary / RAW).read_bytes()
        receipt = {
            "schema_version": f"{SOURCE_ID}-capture/v1",
            "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
            "dataset_id": DATASET_ID,
            "source_id": SOURCE_ID,
            "completed_at": completed_at,
            "contract_sha256": contract_hash(catalog, DATASET_ID),
            "tool": f"avalanche-research@{__version__}",
            "gaps_run": preview["gaps_run"],
            "gaps_capture_id": preview["gaps_capture_id"],
            "kind": preview["kind"],
            "blocks_listed": preview["blocks"],
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


def _integer(value: Any, label: str, height: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise DataError(f"block {height} has no integer {label}") from error
    if number < 0:
        raise DataError(f"block {height} has a negative {label}")
    return number


def read_rows(capture_dir: Path) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid block-fee capture receipt: {error}") from error
    if receipt.get("dataset_id") != DATASET_ID or receipt.get("schema_version") != f"{SOURCE_ID}-capture/v1":
        raise DataError("unsupported block-fee capture receipt")
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), DATASET_ID):
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
        value = json.loads(line)
        height = record["block_height"]
        if height in seen or _integer(value.get("blockNumber"), "height", height) != height:
            raise DataError(f"block {height} is repeated or answered with another height")
        seen.add(height)
        timestamp = datetime.fromtimestamp(_integer(value.get("blockTimestamp"), "timestamp", height), UTC).replace(tzinfo=None)
        rows.append((
            height, value.get("blockHash"), timestamp, timestamp.date(),
            _integer(value.get("txCount"), "transaction count", height), _integer(value.get("gasUsed"), "gas used", height),
            _integer(value.get("baseFee"), "base fee", height), _integer(value.get("feesSpent"), "fees spent", height),
        ))
    return receipt, rows


def _summary(rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    return {"rows": len(rows), "fees_wei": sum(row[7] for row in rows), "transactions": sum(row[4] for row in rows),
            "first_date": min((row[3] for row in rows), default=None), "last_date": max((row[3] for row in rows), default=None)}


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{TABLE}.parquet", "build.json"], "overwrite": False}


def _json_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in summary.items()}


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
            for row in rows:
                connection.execute("INSERT INTO rows VALUES (?, ?, ?, ?, ?, ?, CAST(? AS DECIMAL(38,0)), CAST(? AS DECIMAL(38,0)))", [*row[:6], str(row[6]), str(row[7])])
            connection.execute("COPY (SELECT * FROM rows ORDER BY block_height) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
        finally:
            connection.close()
        result = {
            "schema_version": "data-api-build/v1", "dataset_id": DATASET_ID,
            "dataset_schema": dataset(load_catalog(), DATASET_ID)["fields"], "source_capture_id": receipt["capture_id"],
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
            parquet = dataset_dir / f"{TABLE}.parquet"
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
    return {"dataset_id": DATASET_ID, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": {**summary, "retries": receipt.get("retries", 0)}, "findings": findings}
