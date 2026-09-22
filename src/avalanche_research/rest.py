"""Immutable capture of REST endpoint responses declared in the data catalog.

An endpoint that declares ``page`` is followed through its continuation token: each page is one JSON line in the raw
file, and the receipt records the page count. Everything else about the capture is unchanged.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from xml.etree import ElementTree
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .catalog import (
    DataError, canonical_bytes, contract_hash, dataset, load_catalog, now as _now, sha256, source,
)


def _request(
    url: str,
    timeout: float,
    opener: Callable[..., Any] = urllib.request.urlopen,
    body_json: dict[str, Any] | None = None,
    content: str = "json",
) -> tuple[bytes, dict[str, Any]]:
    """Fetch one endpoint. A JSON body turns the request into a POST; content selects the response validation."""
    headers = {"Accept": "application/json" if content == "json" else "application/xml, text/xml", "User-Agent": "avalanche-phase-ii-research/0.1"}
    data = None
    if body_json is not None:
        data = json.dumps(body_json, separators=(",", ":"), sort_keys=True).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        with opener(request, timeout=timeout) as response:
            body = response.read()
            status = int(getattr(response, "status", 200))
            content_type = response.headers.get("Content-Type", "")
    except (OSError, urllib.error.URLError) as error:
        raise DataError(f"request failed for {url}: {error}") from error
    if status != 200:
        raise DataError(f"request returned HTTP {status} for {url}")
    if content == "json":
        try:
            value = json.loads(body)
        except json.JSONDecodeError as error:
            raise DataError(f"response is not JSON for {url}: {error}") from error
        if not isinstance(value, dict):
            raise DataError(f"response is not a JSON object for {url}")
    elif content == "xml":
        try:
            ElementTree.fromstring(body)
        except ElementTree.ParseError as error:
            raise DataError(f"response is not well-formed XML for {url}: {error}") from error
    else:
        raise DataError(f"unsupported endpoint content type: {content}")
    return body, {"http_status": status, "content_type": content_type}


def _paged(url: str, page: dict[str, Any], timeout: float, opener: Callable[..., Any], target_path: Path) -> dict[str, Any]:
    """Follow ``page['token_field']`` in each JSON response as ``page['token_parameter']`` on the next request.

    Each page is appended to ``target_path`` as one JSON line the moment it arrives, so a long walk shows its progress
    on disk and a failure leaves the pages already fetched for inspection. The last page is the one without a token,
    so an empty page ends the walk only when it carries no token. ``max_pages`` bounds the cost of a runaway token."""
    token_field, token_parameter, limit = page["token_field"], page["token_parameter"], int(page.get("max_pages", 100))
    pages, token, metadata = 0, None, {}
    with target_path.open("wb") as handle:
        while True:
            target = url if token is None else f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode({token_parameter: token})}"
            body, metadata = _request(target, timeout, opener, None, "json")
            handle.write(body.strip() + b"\n")
            handle.flush()
            pages += 1
            token = json.loads(body).get(token_field)
            if not token:
                break
            if pages >= limit:
                raise DataError(f"pagination exceeded {limit} pages for {url}; {pages} pages kept at {target_path}")
    return {**metadata, "pages": pages}


def capture_preview(
    dataset_id: str,
    output: Path,
    parameters: dict[str, str] | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if parameters:
        raise DataError(f"{dataset_id} accepts no parameters")
    catalog = catalog or load_catalog()
    definition = dataset(catalog, dataset_id)
    provider = source(catalog, definition["source_id"])
    endpoints = {item["id"]: item for item in provider["endpoints"]}
    requests = [
        {
            "endpoint_id": endpoint_id,
            "url": endpoints[endpoint_id]["url"],
            "method": "POST" if "request_json" in endpoints[endpoint_id] else "GET",
            "content": endpoints[endpoint_id].get("content", "json"),
            **({"request_json": endpoints[endpoint_id]["request_json"]} if "request_json" in endpoints[endpoint_id] else {}),
            **({"page": endpoints[endpoint_id]["page"]} if "page" in endpoints[endpoint_id] else {}),
        }
        for endpoint_id in definition["endpoint_ids"]
    ]
    return {
        "dataset_id": dataset_id,
        "source_id": provider["id"],
        "output": str(output),
        "requests": requests,
        "writes": ["raw/*.json", "raw/*.jsonl", "capture.json"],
        "overwrite": False,
    }


def capture(
    dataset_id: str,
    output: Path,
    timeout: float = 20,
    parameters: dict[str, str] | None = None,
    catalog: dict[str, Any] | None = None,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    preview = capture_preview(dataset_id, output, parameters, catalog)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    records = []
    try:
        raw = temporary / "raw"
        raw.mkdir()
        for item in preview["requests"]:
            if "page" in item:
                relative = Path("raw") / f"{item['endpoint_id']}.jsonl"
                metadata = _paged(item["url"], item["page"], timeout, opener, temporary / relative)
                body = (temporary / relative).read_bytes()
            else:
                body, metadata = _request(item["url"], timeout, opener, item.get("request_json"), item["content"])
                relative = Path("raw") / f"{item['endpoint_id']}.{item['content']}"
                (temporary / relative).write_bytes(body)
            records.append({
                "endpoint_id": item["endpoint_id"],
                "url": item["url"],
                "method": item["method"],
                **({"request_json": item["request_json"]} if "request_json" in item else {}),
                **({"page": item["page"]} if "page" in item else {}),
                "path": str(relative),
                "bytes": len(body),
                "sha256": sha256(body),
                **metadata,
            })
        completed_at = _now()
        identity = sha256(canonical_bytes({"completed_at": completed_at, "responses": records}))
        receipt = {
            "schema_version": f"{preview['source_id']}-capture/v1",
            "capture_id": f"capture:{preview['source_id']}:{completed_at}:{identity[:12]}",
            "dataset_id": dataset_id,
            "source_id": preview["source_id"],
            "completed_at": completed_at,
            "contract_sha256": contract_hash(catalog, dataset_id),
            "tool": f"avalanche-research@{__version__}",
            "responses": records,
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        os.replace(temporary, output)
    except Exception:
        # A failed paged walk keeps its temporary directory, so the pages fetched so far can be inspected.
        if not any((temporary / "raw").glob("*.jsonl")):
            shutil.rmtree(temporary, ignore_errors=True)
        raise
    return receipt


def read_capture(
    capture_dir: Path,
    catalog: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog = catalog or load_catalog()
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid capture receipt: {error}") from error
    if receipt.get("schema_version") != f"{receipt.get('source_id')}-capture/v1":
        raise DataError("unsupported capture receipt schema")
    if receipt.get("contract_sha256") != contract_hash(catalog, receipt.get("dataset_id", "")):
        raise DataError("capture contract hash differs from the current data contract")
    values: dict[str, Any] = {}
    for item in receipt.get("responses", []):
        path = capture_dir / item["path"]
        try:
            body = path.read_bytes()
        except OSError as error:
            raise DataError(f"missing captured response: {item.get('path')}") from error
        if sha256(body) != item.get("sha256") or len(body) != item.get("bytes"):
            raise DataError(f"captured response hash or size differs: {item.get('path')}")
        if item["path"].endswith(".xml"):
            try:
                ElementTree.fromstring(body)
            except ElementTree.ParseError as error:
                raise DataError(f"captured response is not well-formed XML: {item.get('path')}") from error
            values[item["endpoint_id"]] = body.decode("utf-8", errors="replace")
            continue
        if item["path"].endswith(".jsonl"):
            try:
                pages = [json.loads(line) for line in body.splitlines() if line.strip()]
            except json.JSONDecodeError as error:
                raise DataError(f"captured page is not JSON: {item.get('path')}") from error
            if len(pages) != item.get("pages") or not all(isinstance(page, dict) for page in pages):
                raise DataError(f"captured pages differ from the receipt: {item.get('path')}")
            values[item["endpoint_id"]] = pages
            continue
        try:
            value = json.loads(body)
        except json.JSONDecodeError as error:
            raise DataError(f"captured response is not JSON: {item.get('path')}") from error
        if not isinstance(value, dict):
            raise DataError(f"captured response is not an object: {item.get('path')}")
        values[item["endpoint_id"]] = value
    expected = set(dataset(catalog, receipt["dataset_id"])["endpoint_ids"])
    missing = sorted(expected - values.keys())
    if missing:
        raise DataError(f"capture is missing endpoints: {', '.join(missing)}")
    return receipt, values


