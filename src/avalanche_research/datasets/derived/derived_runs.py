"""The run plumbing of a derived daily table: choosing and hashing its input runs, writing the capture and dataset
receipts into a new run directory, and verifying a recorded capture's inputs before a check rebuilds the table."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import duckdb

from ... import __version__, datasets
from ...core.catalog import (
    DataError,
    canonical_bytes,
    contract_hash,
    dataset,
    load_catalog,
    now,
    sha256,
)

SOURCE_ID = "derived"


def select_inputs(dataset_id: str, inputs: dict[str, str], pinned: dict[str, str] | None, root: Path | None) -> list[dict[str, Any]]:
    """The input runs pinned by ``dataset_id=run``, or the newest built run of each, with their hashes. A Snowflake
    capture's query ID and query-text hash are copied into the record, so the derived capture names the exact read."""
    pinned = pinned or {}
    unknown = sorted(set(pinned) - set(inputs.values()))
    if unknown:
        raise DataError(f"not an input of {dataset_id}: {', '.join(unknown)}")
    selected = []
    for input_id, input_dataset in inputs.items():
        run = pinned.get(input_dataset) or datasets.select_run(input_dataset, newest=True, root=root)["run"]
        record = datasets.receipt(input_dataset, run, root)
        parquet = datasets.parquet_path(input_dataset, record["run"], root)
        body = parquet.read_bytes()
        item = {
            "input_id": input_id, "dataset_id": input_dataset, "run": record["run"],
            "capture_id": record["capture"]["capture_id"], "contract_sha256": record["capture"].get("contract_sha256"),
            "captured_at": record["capture"].get("completed_at"), "rows": record["build"].get("summary", {}).get("rows"),
            "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet,
        }
        queries = record["capture"].get("queries") or []
        if len(queries) == 1 and "snowflake_query_id" in queries[0]:
            item["snowflake_query_id"] = queries[0]["snowflake_query_id"]
            item["sql_sha256"] = queries[0]["sql_sha256"]
        selected.append(item)
    return selected


def quoted(path: Path | str) -> str:
    return str(path).replace("'", "''")


def write_run(dataset_id: str, table: str, output: Path, inputs: list[dict[str, Any]], parameters: dict[str, Any],
              build: Callable[[Any], None], summarize: Callable[[Any], dict[str, Any]]) -> dict[str, Any]:
    """Write ``capture/capture.json`` naming the inputs and ``dataset/<table>.parquet`` with its build receipt.
    ``build`` fills the table ``result`` on a connection with the inputs loaded; ``summarize`` describes it."""
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    completed_at = now()
    records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records}))
    capture_receipt = {
        "schema_version": "derived-capture/v1",
        "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
        "dataset_id": dataset_id,
        "source_id": SOURCE_ID,
        "completed_at": completed_at,
        "contract_sha256": contract_hash(catalog, dataset_id),
        "tool": f"avalanche-research@{__version__}",
        "inputs": records,
        "parameters": parameters,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "capture").mkdir()
        (temporary / "dataset").mkdir()
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet_path = temporary / "dataset" / f"{table}.parquet"
        connection = duckdb.connect()
        try:
            build(connection)
            connection.execute("COPY (SELECT * FROM result ORDER BY 1) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection)
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "derived-build/v1",
            "dataset_id": dataset_id,
            "dataset_schema": definition["fields"],
            "source_capture_id": capture_receipt["capture_id"],
            "completed_at": now(),
            "tool": f"avalanche-research@{__version__}",
            "summary": summary,
            "outputs": [{"path": parquet_path.name, "bytes": parquet_path.stat().st_size, "sha256": sha256(parquet_path.read_bytes())}],
        }
        (temporary / "dataset" / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"capture": capture_receipt, "build": build_receipt}


def read_capture(capture_dir: Path, dataset_id: str) -> dict[str, Any]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"unreadable capture receipt: {error}") from error
    if receipt.get("schema_version") != "derived-capture/v1" or receipt.get("dataset_id") != dataset_id:
        raise DataError(f"not a {dataset_id} capture: {capture_dir}")
    return receipt


def verified_inputs(receipt: dict[str, Any], root: Path | None, findings: list[str]) -> list[dict[str, Any]]:
    """The recorded input runs that still exist, each with its path; a missing or changed run becomes a finding."""
    root_dir = datasets.RUNS if root is None else root
    inputs = []
    for item in receipt.get("inputs", []):
        parquet = root_dir / item["run"] / "dataset" / item["parquet"]
        if not parquet.is_file():
            findings.append(f"input run missing: {item['run']}")
            continue
        body = parquet.read_bytes()
        if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
            findings.append(f"input run differs from the capture receipt: {item['run']}")
        inputs.append({**item, "path": parquet})
    return inputs


def built_findings(connection: Any, dataset_id: str, receipt: dict[str, Any], dataset_dir: Path, table: str,
                   columns: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    """Load the built table as ``built`` and compare its receipt, hash and columns with the capture and the catalog."""
    findings = []
    build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
    if build_receipt.get("source_capture_id") != receipt.get("capture_id"):
        findings.append("build does not belong to this capture")
    for item in build_receipt["outputs"]:
        body = (dataset_dir / item["path"]).read_bytes()
        if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
            findings.append(f"output hash or size differs: {item['path']}")
    connection.execute(f"CREATE OR REPLACE TABLE built AS SELECT * FROM read_parquet('{quoted(dataset_dir / f'{table}.parquet')}')")
    described = [(row[0], row[1]) for row in connection.execute("DESCRIBE built").fetchall()]
    declared = [field["name"] for field in dataset(load_catalog(), dataset_id)["fields"]]
    if described != list(columns.items()) or [name for name, _ in described] != declared:
        findings.append("columns differ from the module or the catalog")
    return build_receipt, findings


def differ(connection: Any, left: str, right: str) -> int:
    return connection.execute(
        f"SELECT (SELECT count(*) FROM (SELECT * FROM {left} EXCEPT ALL SELECT * FROM {right}))"
        f" + (SELECT count(*) FROM (SELECT * FROM {right} EXCEPT ALL SELECT * FROM {left}))").fetchone()[0]


def reject_fetch(dataset_id: str) -> None:
    raise DataError(f"{dataset_id} is built with `avalanche data derive`, not fetched or built from a capture")
