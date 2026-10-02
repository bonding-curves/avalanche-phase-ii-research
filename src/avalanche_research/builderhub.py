"""Builder Hub validator uptime: capture, build, check, and the merged hourly table.

Builder Hub's validator explorer serves, for every current Primary Network validator, the hourly median uptime across
Ava Labs' observing nodes for a rolling window, 332 hours until 2026-09-27 and about 175 since. It is the only public
history of uptime percentages: the protocol keeps none. A capture takes the validator list and one detail per node, and also asks again
for nodes the previous capture listed that are no longer listed, so a validator's last hours are kept after it ends.
Each detail is one JSON line written as it arrives. A capture that stops keeps its lines in ``.<output>.partial`` beside
the output and the next capture into the same output resumes from them.

``derived.validator-uptime-hourly`` merges every built capture into one row per node per hour. Consecutive daily
captures overlap by about six days, so the merged table grows without gaps as long as no two captures are more
than a window apart, which the check against the previous capture verifies.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
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

DATASET_ID = "builder-hub.validator-uptime"
DERIVED_ID = "derived.validator-uptime-hourly"
DATASET_IDS = (DATASET_ID, DERIVED_ID)
SOURCE_ID = "avalanche-builder-hub"
LIST_ENDPOINT = "validators"
DETAIL_ENDPOINT = "validator-detail"
LIST_RAW = "raw/validators.json"
DETAIL_RAW = "raw/validator-details.jsonl"
USER_AGENT = "avalanche-phase-ii-research/0.1"
ATTEMPTS = 6
# A node Builder Hub still answers with a server error after every retry is recorded as unavailable and the capture goes
# on, so one node it cannot serve does not cost every other node's hours. More than this many is an outage: the capture
# stops, keeps its lines, and resumes the next hour.
UNAVAILABLE_LIMIT = 3
RETRY_SECONDS = 5.0
MAX_WORKERS = 8
AGREEMENT_FLOOR = 0.99
SETTLED_HOURS = 24
TABLES = ("uptime-hourly", "validators", "bench-daily", "blocks-hourly")
DERIVED_TABLE = "validator-uptime-hourly"


def _endpoint(catalog: dict[str, Any], endpoint_id: str) -> str:
    return next(item["url"] for item in source(catalog, SOURCE_ID)["endpoints"] if item["id"] == endpoint_id)


def _request(url: str, timeout: float) -> tuple[bytes, dict[str, Any]]:
    """One GET. Builder Hub's list route answers a JSON array, which the shared REST layer does not accept."""
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            meta = {"http_status": int(getattr(response, "status", 200)), "x_data_source": response.headers.get("X-Data-Source", "absent")}
    except (OSError, urllib.error.URLError) as error:
        raise DataError(f"request failed for {url}: {error}") from error
    try:
        json.loads(body)
    except json.JSONDecodeError as error:
        raise DataError(f"response is not JSON for {url}: {error}") from error
    return body, meta


def _parameters(parameters: dict[str, str] | None) -> dict[str, Any]:
    values = dict(parameters or {})
    unknown = sorted(set(values) - {"workers", "limit", "previous", "import", "unavailable_limit"})
    if unknown:
        raise DataError(f"unknown parameters for {DATASET_ID}: {', '.join(unknown)}")
    try:
        workers = int(values.get("workers", 4))
        limit = int(values["limit"]) if "limit" in values else None
        unavailable_limit = int(values.get("unavailable_limit", UNAVAILABLE_LIMIT))
    except ValueError as error:
        raise DataError(f"workers, limit, and unavailable_limit must be integers: {error}") from error
    if not 1 <= workers <= MAX_WORKERS:
        raise DataError(f"workers must be between 1 and {MAX_WORKERS}")
    return {"workers": workers, "limit": limit, "previous": values.get("previous", "auto"), "import": values.get("import"),
            "unavailable_limit": unavailable_limit}


def _previous(choice: str, root: Path | None) -> dict[str, Any] | None:
    """The previous capture: ``auto`` for the newest built run, ``none``, or a run name."""
    if choice == "none":
        return None
    available = datasets.runs(DATASET_ID, root)
    if choice != "auto":
        available = [item for item in available if item["run"] == choice]
        if not available:
            raise DataError(f"no built run of {DATASET_ID} named {choice}")
    if not available:
        return None
    newest = max(available, key=lambda item: (item["captured_at"] or "", item["run"]))
    return {"run": newest["run"], "capture_id": newest["capture_id"], "nodes": _listed_nodes(newest["capture_dir"])}


def _listed_nodes(capture_dir: Path) -> list[str]:
    try:
        return [item["node_id"] for item in json.loads((capture_dir / LIST_RAW).read_bytes())]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise DataError(f"unreadable validator list in {capture_dir}: {error}") from error


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    if dataset_id == DERIVED_ID:
        raise DataError(f"{DERIVED_ID} is derived; use `avalanche data derive`")
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    values = _parameters(parameters)
    catalog = load_catalog()
    partial = output.parent / f".{output.name}.partial"
    return {
        "dataset_id": DATASET_ID, "source_id": SOURCE_ID, "output": str(output),
        "list_endpoint": _endpoint(catalog, LIST_ENDPOINT), "detail_endpoint": _endpoint(catalog, DETAIL_ENDPOINT),
        "workers": values["workers"], "limit": values["limit"], "previous": values["previous"], "import": values["import"],
        "unavailable_limit": values["unavailable_limit"],
        "resumes": partial.is_dir(), "partial": str(partial), "writes": [LIST_RAW, DETAIL_RAW, "capture.json"], "overwrite": False,
    }


def _read_lines(path: Path) -> list[dict[str, Any]]:
    """The complete detail lines of a kept capture. A line cut off mid-write is dropped and the file cut back to the rest."""
    if not path.exists():
        return []
    body = path.read_bytes()
    lines, kept = [], 0
    for raw in body.split(b"\n"):
        if not raw:
            break
        try:
            lines.append(json.loads(raw))
        except json.JSONDecodeError:
            break
        kept += len(raw) + 1
    if kept != len(body):
        path.write_bytes(body[:kept])
    return lines


def _import(source_dir: Path, temporary: Path) -> dict[str, Any]:
    """Wrap a capture taken by the 2026-09-24 preservation script, whose lines hold only node_id and body."""
    try:
        receipt = json.loads((source_dir / "receipt.json").read_text(encoding="utf-8"))
        listing = (source_dir / "validators.json").read_bytes()
        details = (source_dir / "validator-details.jsonl").read_bytes()
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"cannot import {source_dir}: {error}") from error
    (temporary / LIST_RAW).write_bytes(listing)
    with (temporary / DETAIL_RAW).open("wb") as handle:
        for raw in details.splitlines():
            item = json.loads(raw)
            line = {"node_id": item["node_id"], "requested_because": "listed", "http_status": 200, "x_data_source": "unknown", "body": item["body"]}
            handle.write(json.dumps(line, separators=(",", ":"), sort_keys=True).encode() + b"\n")
    return {"imported_from": str(source_dir), "imported_sha256": {"validators.json": sha256(listing), "validator-details.jsonl": sha256(details)},
            "imported_receipt": receipt, "started_at": receipt["started_at"], "completed_at": receipt["completed_at"]}


def capture(
    dataset_id: str,
    output: Path,
    timeout: float = 20,
    parameters: dict[str, str] | None = None,
    request: Callable[[str, float], tuple[bytes, dict[str, Any]]] = _request,
    root: Path | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    preview = capture_preview(dataset_id, output, parameters, root)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    temporary = Path(preview["partial"])
    output.parent.mkdir(parents=True, exist_ok=True)
    (temporary / "raw").mkdir(parents=True, exist_ok=True)
    state_path = temporary / "state.json"
    retries = 0
    if preview["import"]:
        imported = _import(Path(preview["import"]), temporary)
        state = {"started_at": imported["started_at"], "previous": None, "ended": []}
    else:
        imported = None
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
        else:
            previous = _previous(preview["previous"], root)
            body, _ = _fetch(request, preview["list_endpoint"], timeout, sleep)
            listing = json.loads(body)
            if not isinstance(listing, list) or not all(isinstance(item, dict) and str(item.get("node_id", "")).startswith("NodeID-") for item in listing):
                raise DataError("the validator list is not an array of validators with node IDs")
            (temporary / LIST_RAW).write_bytes(body)
            listed = {item["node_id"] for item in listing}
            ended = sorted(set(previous["nodes"]) - listed) if previous else []
            state = {"started_at": now(), "previous": {key: previous[key] for key in ("run", "capture_id")} if previous else None, "ended": ended,
                     "unavailable": []}
            state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
        wanted = [(node, "listed") for node in _listed_nodes(temporary)] + [(node, "ended-since-previous") for node in state["ended"]]
        if preview["limit"] is not None:
            wanted = wanted[: preview["limit"]]
        state.setdefault("unavailable", [])
        done = {line["node_id"] for line in _read_lines(temporary / DETAIL_RAW)} | {item["node_id"] for item in state["unavailable"]}
        todo = [item for item in wanted if item[0] not in done]

        def one(item: tuple[str, str]) -> tuple[str, str, bytes | None, dict[str, Any], int]:
            try:
                body, meta, retried = _fetch_counted(request, f"{preview['detail_endpoint']}/{item[0]}", timeout, sleep)
            except DataError as error:
                if "HTTP Error 5" not in str(error):
                    raise
                return item[0], item[1], None, {"error": str(error)}, ATTEMPTS - 1
            return item[0], item[1], body, meta, retried

        with (temporary / DETAIL_RAW).open("ab") as handle, ThreadPoolExecutor(max_workers=preview["workers"]) as pool:
            results = pool.map(one, todo)
            while True:
                try:
                    node, because, body, meta, retried = next(results)
                except StopIteration:
                    break
                except DataError as error:
                    handle.flush()
                    raise DataError(f"{error}; lines kept at {temporary}, the next capture into {output} resumes") from error
                retries += retried
                if body is None:
                    state["unavailable"].append({"node_id": node, "requested_because": because, "error": meta["error"]})
                    state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
                    # Nodes that ended since the previous capture are asked on the chance their last hours remain; Builder Hub
                    # has answered a server error for most of them since 2026-09-27, so only listed nodes count toward an outage.
                    if sum(item["requested_because"] == "listed" for item in state["unavailable"]) > preview["unavailable_limit"]:
                        # An outage: the next capture asks these nodes again.
                        count = sum(item["requested_because"] == "listed" for item in state["unavailable"])
                        state["unavailable"] = [item for item in state["unavailable"] if item["requested_because"] != "listed"]
                        state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
                        handle.flush()
                        raise DataError(f"Builder Hub could not serve {count} listed nodes, an outage; lines kept at {temporary},"
                                        f" the next capture into {output} resumes")
                    continue
                value = json.loads(body)
                if not isinstance(value, dict) or value.get("node_id") != node:
                    raise DataError(f"Builder Hub answered {value.get('node_id') if isinstance(value, dict) else 'a non-object'} for {node}; lines kept at {temporary}")
                line = {"node_id": node, "requested_because": because, **meta, "body": value}
                handle.write(json.dumps(line, separators=(",", ":"), sort_keys=True).encode() + b"\n")
                handle.flush()
    lines = _read_lines(temporary / DETAIL_RAW)
    completed_at = imported["completed_at"] if imported else now()
    listing_body, detail_body = (temporary / LIST_RAW).read_bytes(), (temporary / DETAIL_RAW).read_bytes()
    identity = sha256(canonical_bytes({"completed_at": completed_at, "list": sha256(listing_body), "details": sha256(detail_body)}))
    receipt = {
        "schema_version": f"{SOURCE_ID}-capture/v1",
        "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
        "dataset_id": DATASET_ID,
        "source_id": SOURCE_ID,
        "started_at": state["started_at"],
        "completed_at": completed_at,
        "contract_sha256": contract_hash(catalog, DATASET_ID),
        "tool": f"avalanche-research@{__version__}",
        "previous": state["previous"],
        "nodes_listed": len(_listed_nodes(temporary)),
        "nodes_ended_requested": len(state["ended"]),
        "details": len(lines),
        "fallback_answers": sum(line.get("x_data_source") == "error-fallback-cache" for line in lines),
        "unavailable": state.get("unavailable", []),
        "retries": retries,
        "responses": [
            {"endpoint_id": LIST_ENDPOINT, "path": LIST_RAW, "bytes": len(listing_body), "sha256": sha256(listing_body)},
            {"endpoint_id": DETAIL_ENDPOINT, "path": DETAIL_RAW, "bytes": len(detail_body), "sha256": sha256(detail_body)},
        ],
        **({"import": {key: imported[key] for key in ("imported_from", "imported_sha256", "imported_receipt")}} if imported else {}),
    }
    (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
    state_path.unlink(missing_ok=True)
    os.replace(temporary, output)
    return receipt


def _fetch_counted(request: Callable[..., Any], url: str, timeout: float, sleep: Callable[[float], None]) -> tuple[bytes, dict[str, Any], int]:
    """A request retried with doubling waits, about two and a half minutes in all, when refused, dropped, or answered 5xx."""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            body, meta = request(url, timeout)
            return body, meta, attempt - 1
        except DataError:
            if attempt == ATTEMPTS:
                raise
            sleep(RETRY_SECONDS * 2 ** (attempt - 1))
    raise AssertionError("unreachable")


def _fetch(request: Callable[..., Any], url: str, timeout: float, sleep: Callable[[float], None]) -> tuple[bytes, dict[str, Any]]:
    body, meta, _ = _fetch_counted(request, url, timeout, sleep)
    return body, meta


def read_capture(capture_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """The receipt, the list, and the detail lines, verified against the receipt's hashes."""
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"unreadable capture receipt: {error}") from error
    if receipt.get("dataset_id") != DATASET_ID:
        raise DataError(f"not a {DATASET_ID} capture: {capture_dir}")
    for response in receipt["responses"]:
        body = (capture_dir / response["path"]).read_bytes()
        if len(body) != response["bytes"] or sha256(body) != response["sha256"]:
            raise DataError(f"captured file differs from its receipt: {response['path']}")
    listing = json.loads((capture_dir / LIST_RAW).read_bytes())
    lines = [json.loads(raw) for raw in (capture_dir / DETAIL_RAW).read_bytes().splitlines() if raw]
    return receipt, listing, lines


def _bucket(value: str) -> datetime:
    """``2026-09-10T09:00:00Z`` or ``2026-09-11 00:00:00`` as naive UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00").replace(" ", "T"))
    return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed


def _rows(receipt: dict[str, Any], listing: list[dict[str, Any]], lines: list[dict[str, Any]]) -> dict[str, list[tuple[Any, ...]]]:
    captured_at = _bucket(receipt["completed_at"])
    listed = {item["node_id"]: item for item in listing}
    tables: dict[str, list[tuple[Any, ...]]] = {name: [] for name in TABLES}
    for line in lines:
        body, node = line["body"], line["node_id"]
        uptime = body.get("uptime") or []
        details = body.get("uptime_details") or {}
        for point in uptime:
            tables["uptime-hourly"].append((node, _bucket(point["bucket"]), float(point["p50_uptime"]), captured_at))
        for point in body.get("bench") or []:
            tables["bench-daily"].append((node, datetime.fromisoformat(point["bucket"]).date(), int(point["bench_total"]), captured_at))
        for point in body.get("blocks") or []:
            tables["blocks-hourly"].append((node, _bucket(point["hour"]), int(point["proposed"]), int(point["missed"]), captured_at))
        buckets = [_bucket(point["bucket"]) for point in uptime]
        tables["validators"].append((
            node, line["requested_because"], line.get("x_data_source"), captured_at,
            listed.get(node, {}).get("p50_uptime"), body.get("current_p50_uptime"), body.get("bench_observers"),
            body.get("weight"), body.get("delegator_weight"), body.get("delegator_count"), body.get("delegation_fee"),
            body.get("potential_reward"), body.get("version"), body.get("days_left"),
            body.get("miss_rate_14d"), body.get("missed_14d"), body.get("proposed_14d"),
            details.get("count"), details.get("min"), details.get("max"), details.get("avg"), details.get("p50"), details.get("p95"),
            min(buckets, default=None), max(buckets, default=None), len(buckets),
        ))
    return tables


COLUMNS = {
    "uptime-hourly": {"node_id": "VARCHAR", "bucket_utc": "TIMESTAMP", "p50_uptime_pct": "DOUBLE", "captured_at": "TIMESTAMP"},
    "bench-daily": {"node_id": "VARCHAR", "date_utc": "DATE", "bench_total": "BIGINT", "captured_at": "TIMESTAMP"},
    "blocks-hourly": {"node_id": "VARCHAR", "hour_utc": "TIMESTAMP", "proposed": "BIGINT", "missed": "BIGINT", "captured_at": "TIMESTAMP"},
    "validators": {
        "node_id": "VARCHAR", "requested_because": "VARCHAR", "x_data_source": "VARCHAR", "captured_at": "TIMESTAMP",
        "listed_p50_uptime_pct": "DOUBLE", "current_p50_uptime_pct": "DOUBLE", "bench_observers": "BIGINT",
        "weight_navax": "BIGINT", "delegator_weight_navax": "BIGINT", "delegator_count": "BIGINT", "delegation_fee_pct": "DOUBLE",
        "potential_reward_navax": "BIGINT", "version": "VARCHAR", "days_left": "BIGINT",
        "miss_rate_14d_pct": "DOUBLE", "missed_14d": "BIGINT", "proposed_14d": "BIGINT",
        "observations_14d": "BIGINT", "uptime_min_pct": "DOUBLE", "uptime_max_pct": "DOUBLE", "uptime_mean_pct": "DOUBLE",
        "uptime_p50_pct": "DOUBLE", "uptime_p95_pct": "DOUBLE", "first_bucket_utc": "TIMESTAMP", "last_bucket_utc": "TIMESTAMP", "buckets": "BIGINT",
    },
}
ORDER = {"uptime-hourly": "node_id, bucket_utc", "bench-daily": "node_id, date_utc", "blocks-hourly": "node_id, hour_utc", "validators": "node_id"}


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"{dataset_id} is not built from a capture; use `avalanche data derive`" if dataset_id == DERIVED_ID else f"unknown dataset: {dataset_id}")
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [*(f"{name}.parquet" for name in TABLES), "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    build_preview(dataset_id, capture_dir, output)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    receipt, listing, lines = read_capture(capture_dir)
    tables = _rows(receipt, listing, lines)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.building"
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir()
    try:
        connection = duckdb.connect()
        outputs = []
        try:
            for name in TABLES:
                columns = COLUMNS[name]
                table = name.replace("-", "_")
                connection.execute(f"CREATE TABLE {table}({', '.join(f'{column} {kind}' for column, kind in columns.items())})")
                if tables[name]:
                    connection.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' for _ in columns)})", tables[name])
                parquet = temporary / f"{name}.parquet"
                connection.execute(f"COPY (SELECT * FROM {table} ORDER BY {ORDER[name]}) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
                body = parquet.read_bytes()
                outputs.append({"path": parquet.name, "bytes": len(body), "sha256": sha256(body), "rows": len(tables[name])})
        finally:
            connection.close()
        hours = [row[1] for row in tables["uptime-hourly"]]
        result = {
            "schema_version": f"{SOURCE_ID}-build/v1", "dataset_id": DATASET_ID,
            "dataset_schema": dataset(load_catalog(), DATASET_ID)["fields"], "source_capture_id": receipt["capture_id"],
            "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": {"rows": len(hours), "nodes": len(lines), "first_bucket_utc": min(hours).isoformat() if hours else None,
                        "last_bucket_utc": max(hours).isoformat() if hours else None},
            "outputs": outputs,
        }
        (temporary / "build.json").write_bytes(canonical_bytes(result))
        os.replace(temporary, output)
        return result
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _verify_outputs(dataset_dir: Path, receipt: dict[str, Any], findings: list[str]) -> dict[str, Any] | None:
    try:
        built = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        findings.append(f"BC0 unreadable build receipt: {error}")
        return None
    if built.get("source_capture_id") != receipt["capture_id"]:
        findings.append("BC0 the build names a different capture")
    for item in built.get("outputs", []):
        body = (dataset_dir / item["path"]).read_bytes()
        if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
            findings.append(f"BC0 {item['path']} differs from the build receipt")
    return built


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | list[Path] | tuple[Path, ...] | None = None) -> dict[str, Any]:
    """Finding codes: ``BC1`` completeness, ``BC2`` identity, ``BC3`` series shape, ``BC4`` fallback answers, ``BC9`` nodes
    the source could not serve, and with
    ``--against`` a previous capture's dataset ``BC5`` continuity and ``BC6`` agreement, and a same-day
    ``p-chain-rpc.current-validators`` dataset ``BC7`` node set. ``--against`` repeats, so one check runs all three. A
    finding under BC1, BC2, BC3, or BC5 means the day's history is incomplete. The runner treats those as failure and the others as attention."""
    if (capture_dir / "capture.json").exists() and json.loads((capture_dir / "capture.json").read_text(encoding="utf-8")).get("dataset_id") == DERIVED_ID:
        return check_derived(capture_dir, dataset_dir)
    receipt, listing, lines = read_capture(capture_dir)
    findings: list[str] = []
    checked = ["capture hashes", "BC1 completeness", "BC2 identity", "BC3 series shape", "BC4 fallback answers"]
    by_node = {line["node_id"]: line for line in lines}
    unavailable = {item["node_id"] for item in receipt.get("unavailable", [])}
    missing = [item["node_id"] for item in listing
               if item["node_id"] not in unavailable and (item["node_id"] not in by_node or by_node[item["node_id"]].get("http_status") != 200)]
    if missing:
        findings.append(f"BC1 {len(missing)} listed nodes have no detail, first {missing[0]}")
    if len(by_node) != len(lines):
        findings.append("BC2 a node has more than one detail line")
    wrong = [line["node_id"] for line in lines if line["body"].get("node_id") != line["node_id"]]
    if wrong:
        findings.append(f"BC2 {len(wrong)} details answer for another node")
    captured_at = _bucket(receipt["completed_at"])
    shape = 0
    for line in lines:
        buckets = [_bucket(point["bucket"]) for point in line["body"].get("uptime") or []]
        values = [point["p50_uptime"] for point in line["body"].get("uptime") or []]
        if (any(b.minute or b.second for b in buckets) or buckets != sorted(set(buckets)) or any(b > captured_at for b in buckets)
                or any(not isinstance(v, (int, float)) or not 0 <= v <= 100 for v in values)):
            shape += 1
    if shape:
        findings.append(f"BC3 {shape} nodes have uptime series that are not unique whole hours in order, within 0 to 100, before the capture")
    if unavailable:
        checked.append("BC9 source availability")
        findings.append(f"BC9 Builder Hub could not serve {len(unavailable)} nodes after every retry: {', '.join(sorted(unavailable))}")
    fallback = receipt.get("fallback_answers", 0)
    if fallback:
        findings.append(f"BC4 {fallback} details were answered from Builder Hub's cache after an upstream failure")
    summary: dict[str, Any] = {"nodes_listed": len(listing), "details": len(lines), "fallback_answers": fallback, "retries": receipt.get("retries", 0)}
    if dataset_dir is not None:
        checked.append("build hashes")
        _verify_outputs(dataset_dir, receipt, findings)
    references = [] if against is None else [against] if isinstance(against, Path) else list(against)
    for reference_dir in references:
        reference = json.loads((reference_dir / "build.json").read_text(encoding="utf-8"))
        connection = duckdb.connect()
        try:
            if reference["dataset_id"] == DATASET_ID:
                checked.extend(["BC5 continuity", "BC6 agreement"])
                new = str(dataset_dir / "uptime-hourly.parquet") if dataset_dir is not None else None
                if new is None:
                    raise DataError("the check against a previous capture needs --dataset")
                old = str(reference_dir / "uptime-hourly.parquet")
                oldest_new, newest_old = connection.execute(
                    "SELECT (SELECT min(bucket_utc) FROM read_parquet(?)), (SELECT max(bucket_utc) FROM read_parquet(?))", [new, old]).fetchone()
                summary.update({"oldest_hour_new": str(oldest_new), "newest_hour_previous": str(newest_old)})
                if oldest_new is None or newest_old is None or oldest_new > newest_old + timedelta(hours=1):
                    findings.append(f"BC5 hours between {newest_old} and {oldest_new} are in neither capture")
                settled = captured_at - timedelta(hours=SETTLED_HOURS)
                shared, equal = connection.execute(
                    """SELECT count(*), count(*) FILTER (WHERE n.p50_uptime_pct = o.p50_uptime_pct)
                       FROM read_parquet(?) n JOIN read_parquet(?) o USING (node_id, bucket_utc) WHERE bucket_utc < ?""",
                    [new, old, settled]).fetchone()
                summary.update({"shared_node_hours": shared, "equal_node_hours": equal})
                if shared and equal / shared < AGREEMENT_FLOOR:
                    findings.append(f"BC6 {shared - equal} of {shared} settled node-hours differ from the previous capture")
            elif reference["dataset_id"] == "p-chain-rpc.current-validators":
                checked.append("BC7 node set")
                parquet = next(item["path"] for item in reference["outputs"] if item["path"].endswith(".parquet"))
                rpc = {row[0] for row in connection.execute("SELECT DISTINCT node_id FROM read_parquet(?)", [str(reference_dir / parquet)]).fetchall()}
                listed = {item["node_id"] for item in listing}
                summary.update({"rpc_nodes": len(rpc), "only_rpc": len(rpc - listed), "only_builder_hub": len(listed - rpc)})
                if len(rpc ^ listed) > 0.02 * max(len(rpc), 1):
                    findings.append(f"BC7 node sets differ by {len(rpc ^ listed)} of {len(rpc)}")
            else:
                raise DataError(f"cannot check {DATASET_ID} against {reference['dataset_id']}")
        finally:
            connection.close()
    return {"dataset_id": DATASET_ID, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}


def _inputs(root: Path | None) -> list[dict[str, Any]]:
    """Every built capture under the current contract, oldest first, with the hash of its hourly table."""
    current = contract_hash(load_catalog(), DATASET_ID)
    selected = []
    for item in datasets.runs(DATASET_ID, root):
        capture = json.loads((item["capture_dir"] / "capture.json").read_text(encoding="utf-8"))
        if capture.get("contract_sha256") != current:
            continue
        parquet = item["dataset_dir"] / "uptime-hourly.parquet"
        body = parquet.read_bytes()
        selected.append({"dataset_id": DATASET_ID, "run": item["run"], "capture_id": item["capture_id"], "captured_at": item["captured_at"],
                         "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet})
    if not selected:
        raise DataError(f"no built run of {DATASET_ID} carries the current contract")
    return sorted(selected, key=lambda item: (item["captured_at"] or "", item["run"]))


def _union(inputs: list[dict[str, Any]]) -> str:
    parts = [f"SELECT {rank} AS run_rank, * FROM read_parquet('{str(item['path']).replace(chr(39), chr(39) * 2)}')" for rank, item in enumerate(inputs)]
    return " UNION ALL ".join(parts)


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    """Merge every capture: the newest capture's value for each node-hour, with how many captures held it and whether they agreed."""
    if dataset_id != DERIVED_ID:
        raise DataError(f"{dataset_id} is captured from a provider; use `avalanche data fetch` and `build`")
    if pinned:
        raise DataError(f"{DERIVED_ID} reads every capture; it takes no pinned inputs")
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    inputs = _inputs(root)
    completed_at = now()
    records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records}))
    capture_receipt = {
        "schema_version": "derived-capture/v1", "capture_id": f"capture:derived:{completed_at}:{identity[:12]}",
        "dataset_id": DERIVED_ID, "source_id": "derived", "completed_at": completed_at,
        "contract_sha256": contract_hash(catalog, DERIVED_ID), "tool": f"avalanche-research@{__version__}", "inputs": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.building"
    shutil.rmtree(temporary, ignore_errors=True)
    (temporary / "capture").mkdir(parents=True)
    (temporary / "dataset").mkdir()
    try:
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet = temporary / "dataset" / f"{DERIVED_TABLE}.parquet"
        connection = duckdb.connect()
        try:
            connection.execute(f"""
                COPY (
                  SELECT node_id, bucket_utc,
                         arg_max(p50_uptime_pct, run_rank) AS p50_uptime_pct,
                         count(*) AS captures,
                         count(DISTINCT p50_uptime_pct) > 1 AS revised,
                         min(captured_at) AS first_captured_at,
                         max(captured_at) AS last_captured_at
                  FROM ({_union(inputs)}) GROUP BY node_id, bucket_utc ORDER BY node_id, bucket_utc
                ) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)""", [str(parquet)])
            rows, nodes, first, last, revised = connection.execute(
                "SELECT count(*), count(DISTINCT node_id), min(bucket_utc), max(bucket_utc), count(*) FILTER (WHERE revised) FROM read_parquet(?)",
                [str(parquet)]).fetchone()
        finally:
            connection.close()
        body = parquet.read_bytes()
        build_receipt = {
            "schema_version": "derived-build/v1", "dataset_id": DERIVED_ID, "dataset_schema": dataset(catalog, DERIVED_ID)["fields"],
            "source_capture_id": capture_receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": {"rows": rows, "nodes": nodes, "captures": len(inputs), "first_bucket_utc": first.isoformat() if first else None,
                        "last_bucket_utc": last.isoformat() if last else None, "revised_node_hours": revised},
            "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}],
        }
        (temporary / "dataset" / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"capture": capture_receipt, "build": build_receipt}


def check_derived(capture_dir: Path, dataset_dir: Path | None = None) -> dict[str, Any]:
    """``BC8``: the inputs still hash as recorded, and the table holds every node-hour of every input exactly once."""
    receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    findings: list[str] = []
    checked = ["input hashes"]
    runs_root = capture_dir.parent.parent
    inputs = []
    for item in receipt["inputs"]:
        path = runs_root / item["run"] / "dataset" / item["parquet"]
        try:
            body = path.read_bytes()
        except OSError:
            findings.append(f"BC8 input {item['run']} is missing")
            continue
        if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
            findings.append(f"BC8 input {item['run']} differs from its record")
        inputs.append({**item, "path": path})
    summary: dict[str, Any] = {"captures": len(receipt["inputs"])}
    if dataset_dir is not None and inputs:
        checked.extend(["build hashes", "BC8 every node-hour once"])
        _verify_outputs(dataset_dir, receipt, findings)
        connection = duckdb.connect()
        try:
            table = str(dataset_dir / f"{DERIVED_TABLE}.parquet")
            rows, distinct = connection.execute("SELECT count(*), count(DISTINCT (node_id, bucket_utc)) FROM read_parquet(?)", [table]).fetchone()
            expected = connection.execute(f"SELECT count(DISTINCT (node_id, bucket_utc)) FROM ({_union(inputs)})").fetchone()[0]
        finally:
            connection.close()
        summary.update({"rows": rows, "expected_rows": expected})
        if rows != distinct:
            findings.append("BC8 a node-hour appears twice")
        if rows != expected:
            findings.append(f"BC8 {rows} rows against {expected} distinct node-hours in the inputs")
    return {"dataset_id": DERIVED_ID, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}
