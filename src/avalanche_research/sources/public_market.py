"""Shared parts of the public market captures: polite downloads, atomic output folders, receipts and the built table.

The Bitcoin price, the Binance BTC/USDT candles and the AVAX perpetual funding rates come from keyless public
endpoints. Each request waits before it is sent, and a refusal for rate (HTTP 418 or 429) or a server error is retried
after a growing pause, so a capture stays well inside each provider's published limit. A capture writes into a
temporary folder beside its output and renames it into place only when every file is written, so a failed capture
leaves nothing behind. A build writes one Parquet table and a receipt that hashes it.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb

from .. import __version__
from ..core.catalog import DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256

USER_AGENT = "avalanche-phase-ii-research/0.1 (+https://github.com/bonding-curves/avalanche-phase-ii-research)"
PAUSE_SECONDS = 0.5
ATTEMPTS = 4
RETRY_SECONDS = 5.0
RETRY_STATUSES = frozenset({418, 429, 500, 502, 503, 504})


class NotPublished(DataError):
    """The provider answered HTTP 404: the file does not exist yet."""


Download = Callable[[str, float], bytes]


def download(url: str, timeout: float, pause: float = PAUSE_SECONDS, opener: Callable[..., Any] = urllib.request.urlopen,
             sleep: Callable[[float], None] = time.sleep) -> bytes:
    """The body of one GET, after a pause. A rate refusal or a server error is retried, honouring Retry-After."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, ATTEMPTS + 1):
        sleep(pause)
        try:
            with opener(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise NotPublished(f"not published: {url}") from error
            if error.code not in RETRY_STATUSES or attempt == ATTEMPTS:
                raise DataError(f"request returned HTTP {error.code} for {url}") from error
            wait = error.headers.get("Retry-After") if error.headers else None
            sleep(float(wait) if wait and wait.isdigit() else RETRY_SECONDS * attempt)
        except (OSError, urllib.error.URLError) as error:
            if attempt == ATTEMPTS:
                raise DataError(f"request failed for {url}: {error}") from error
            sleep(RETRY_SECONDS * attempt)
    raise DataError(f"request failed for {url}")


@contextmanager
def new_folder(output: Path) -> Iterator[Path]:
    """A temporary folder beside ``output``, renamed to it when the block succeeds and removed when it fails."""
    if output.exists():
        raise DataError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        yield temporary
        os.replace(temporary, output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def receipt(schema: str, dataset_id: str, source_id: str, files: list[dict[str, Any]], **values: Any) -> dict[str, Any]:
    """A capture receipt: identity, contract hash, tool, and every file written with its hash."""
    completed_at = now()
    identity = sha256(canonical_bytes({"completed_at": completed_at, "files": files}))
    return {"schema_version": schema, "capture_id": f"capture:{source_id}:{completed_at}:{identity[:12]}",
            "dataset_id": dataset_id, "source_id": source_id, "completed_at": completed_at,
            "contract_sha256": contract_hash(load_catalog(), dataset_id), "tool": f"avalanche-research@{__version__}",
            **values, "files": files}


def record(folder: Path, path: str, body: bytes, **values: Any) -> dict[str, Any]:
    """Write one raw file into a capture folder and describe it for the receipt."""
    target = folder / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return {**values, "path": path, "bytes": len(body), "sha256": sha256(body)}


def read_receipt(capture_dir: Path, schema: str, dataset_id: str) -> dict[str, Any]:
    """The capture receipt, refused when its schema, dataset, contract or any file's hash differs."""
    try:
        value = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid capture for {dataset_id}: {error}") from error
    if value.get("schema_version") != schema or value.get("dataset_id") != dataset_id:
        raise DataError(f"unsupported capture for {dataset_id}")
    if value.get("contract_sha256") != contract_hash(load_catalog(), dataset_id):
        raise DataError(f"{dataset_id} capture contract hash differs")
    for item in value["files"]:
        try:
            body = (capture_dir / item["path"]).read_bytes()
        except OSError as error:
            raise DataError(f"captured file missing: {item['path']}") from error
        if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
            raise DataError(f"{item['path']} differs from its receipt")
    return value


def build_table(dataset_id: str, table: str, columns: dict[str, str], order_by: str, capture: dict[str, Any],
                rows: list[tuple[Any, ...]], summary: dict[str, Any], output: Path, schema: str) -> dict[str, Any]:
    """Write ``<table>.parquet`` and ``build.json`` into a new ``output`` folder."""
    with new_folder(output) as temporary:
        parquet = temporary / f"{table}.parquet"
        connection = duckdb.connect()
        try:
            connection.execute(f"CREATE TABLE rows({', '.join(f'{name} {kind}' for name, kind in columns.items())})")
            connection.executemany(f"INSERT INTO rows VALUES ({', '.join('?' for _ in columns)})", rows)
            connection.execute(f"COPY (SELECT * FROM rows ORDER BY {order_by}) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
        finally:
            connection.close()
        result = {
            "schema_version": schema, "dataset_id": dataset_id, "dataset_schema": dataset(load_catalog(), dataset_id)["fields"],
            "source_capture_id": capture["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": summary,
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(result))
    return result


def built_findings(dataset_dir: Path, table: str, order_by: str, capture: dict[str, Any], rows: list[tuple[Any, ...]]) -> list[str]:
    """What differs between a built folder and the rows its capture yields: the receipt, the hash, or the rows."""
    try:
        built = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
        parquet = dataset_dir / f"{table}.parquet"
        body = parquet.read_bytes()
        findings = []
        if (built["source_capture_id"] != capture["capture_id"] or len(body) != built["outputs"][0]["bytes"]
                or sha256(body) != built["outputs"][0]["sha256"]):
            findings.append("build receipt or Parquet hash differs")
        connection = duckdb.connect()
        try:
            actual = connection.execute(f"SELECT * FROM read_parquet(?) ORDER BY {order_by}", [str(parquet)]).fetchall()
        finally:
            connection.close()
        if actual != rows:
            findings.append("Parquet rows differ from the captured rows")
        return findings
    except (OSError, KeyError, IndexError, ValueError, json.JSONDecodeError, duckdb.Error) as error:
        return [f"invalid dataset output: {error}"]


def reference_rows(reference_dir: Path, dataset_id: str, sql: str) -> list[tuple[Any, ...]]:
    """Rows of a built reference dataset, refused unless its build receipt names ``dataset_id`` and its hash holds."""
    try:
        built = json.loads((reference_dir / "build.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"no build receipt in {reference_dir}: {error}") from error
    if built.get("dataset_id") != dataset_id:
        raise DataError(f"{reference_dir} is a run of {built.get('dataset_id')}, not {dataset_id}")
    output = built["outputs"][0]
    parquet = reference_dir / output["path"]
    try:
        body = parquet.read_bytes()
    except OSError as error:
        raise DataError(f"reference Parquet missing: {parquet}") from error
    if len(body) != output["bytes"] or sha256(body) != output["sha256"]:
        raise DataError(f"reference Parquet differs from its build receipt: {parquet}")
    connection = duckdb.connect()
    try:
        return connection.execute(sql.replace("{parquet}", "read_parquet(?)"), [str(parquet)]).fetchall()
    finally:
        connection.close()


def correlation(pairs: list[tuple[float, float]]) -> float | None:
    """Pearson correlation of paired values, or None with fewer than three pairs or no variance."""
    if len(pairs) < 3:
        return None
    count = len(pairs)
    mean_a = sum(a for a, _ in pairs) / count
    mean_b = sum(b for _, b in pairs) / count
    cov = sum((a - mean_a) * (b - mean_b) for a, b in pairs)
    var_a = sum((a - mean_a) ** 2 for a, _ in pairs)
    var_b = sum((b - mean_b) ** 2 for _, b in pairs)
    if var_a == 0 or var_b == 0:
        return None
    return cov / (var_a * var_b) ** 0.5
