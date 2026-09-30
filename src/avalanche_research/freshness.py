"""How fresh each data source is: the time of its newest record, read live, against a 36-hour limit.

A source is stale when its newest record is more than ``STALE_HOURS`` old, and a probe that cannot read its source
counts as not fresh. The Snowflake share stopped loading on 2026-09-22 and nothing said so for a week; this is the
check that says so the same day. It reads no key: the Snowflake connection is the named one, and the Data API is read
on its keyless host.

A source in ``KNOWN_STOPPED`` has stopped at a recorded time. While its newest record is still that one it is reported
as known stale and does not fail the check, so the check fails only on a new stop. A newer record makes it fresh again.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import duckdb

from . import datasets
from .catalog import DataError
from .rest import _request

STALE_HOURS = 36
SHARE = "AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY"
# Share tables and the SQL for the time of their newest row. Each filter keeps the scan to a month.
SNOWFLAKE_TABLES = {
    "P_TRANSACTIONS": f"SELECT MAX(timestamp) FROM {SHARE}.P_TRANSACTIONS WHERE timestamp >= DATEADD(day, -30, CURRENT_TIMESTAMP())",
    "P_BLOCKS": f"SELECT MAX(timestamp) FROM {SHARE}.P_BLOCKS WHERE timestamp >= DATEADD(day, -30, CURRENT_TIMESTAMP())",
    "X_TRANSACTIONS": f"SELECT MAX(timestamp) FROM {SHARE}.X_TRANSACTIONS WHERE timestamp >= DATEADD(day, -30, CURRENT_TIMESTAMP())",
    "C_BLOCKS": f"SELECT TO_TIMESTAMP_NTZ(MAX(blocktimestamp)) FROM {SHARE}.C_BLOCKS WHERE partition_date >= CURRENT_DATE - 30",
}
P_CHAIN_RPC = "https://api.avax.network/ext/bc/P"
TENDERLY = "https://avalanche-mainnet.gateway.tenderly.co"
DATA_API_P_BLOCKS = "https://data-api.avax.network/v1/networks/mainnet/blockchains/p-chain/blocks?pageSize=1"
METRICS = "https://metrics.avax.network/v2"
# A daily Metrics API point is dated at the start of its UTC day and complete at its end.
METRICS_SERIES = {
    "c-chain fees paid": f"{METRICS}/chains/43114/metrics/feesPaid?timeInterval=day&pageSize=1",
    "validator count": f"{METRICS}/networks/mainnet/metrics/validatorCount?timeInterval=day&pageSize=1",
}
WALKS = {"p-chain-rpc.blocks": "block_time"}
# Sources that stopped and are known to have, with the newest record they stopped at and why.
SHARE_STOP = "the Snowflake share stopped loading on 2026-09-22"
KNOWN_STOPPED = {
    "snowflake P_TRANSACTIONS": ("2026-09-22T08:35:40Z", SHARE_STOP),
    "snowflake P_BLOCKS": ("2026-09-22T07:49:27Z", SHARE_STOP),
    "snowflake X_TRANSACTIONS": ("2026-09-22T08:28:04Z", SHARE_STOP),
    "snowflake C_BLOCKS": ("2026-09-21T23:59:59Z", SHARE_STOP),
    "metrics api validator count": ("2026-09-01T00:00:00Z", "the Metrics API's staking metrics have no point after 2026-08-31"),
}


def _utc(seconds: float) -> datetime:
    return datetime.fromtimestamp(seconds, UTC)


def _post(url: str, payload: dict[str, Any], timeout: float, request: Callable[..., tuple[bytes, dict[str, Any]]]) -> Any:
    body, _ = request(url, timeout, body_json=payload)
    value = json.loads(body)
    if value.get("error") or "result" not in value:
        raise DataError(f"{url} answered {value.get('error') or 'no result'}")
    return value["result"]


def p_chain_head(timeout: float, request: Callable[..., tuple[bytes, dict[str, Any]]] = _request) -> datetime:
    height = _post(P_CHAIN_RPC, {"jsonrpc": "2.0", "id": 1, "method": "platform.getHeight", "params": {}}, timeout, request)["height"]
    block = _post(P_CHAIN_RPC, {"jsonrpc": "2.0", "id": 1, "method": "platform.getBlockByHeight",
                                "params": {"height": str(height), "encoding": "json"}}, timeout, request)["block"]
    return _utc(block["time"])


def tenderly_head(timeout: float, request: Callable[..., tuple[bytes, dict[str, Any]]] = _request) -> datetime:
    block = _post(TENDERLY, {"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber", "params": ["latest", False]}, timeout, request)
    return _utc(int(block["timestamp"], 16))


def data_api_p_head(timeout: float, request: Callable[..., tuple[bytes, dict[str, Any]]] = _request) -> datetime:
    body, _ = request(DATA_API_P_BLOCKS, timeout)
    return _utc(json.loads(body)["blocks"][0]["blockTimestamp"])


def metrics_point(url: str) -> Callable[[float], datetime]:
    def probe(timeout: float, request: Callable[..., tuple[bytes, dict[str, Any]]] = _request) -> datetime:
        body, _ = request(url, timeout)
        return _utc(max(item["timestamp"] for item in json.loads(body)["results"])) + timedelta(days=1)
    return probe


def snowflake_tables(timeout: float) -> dict[str, datetime | Exception]:
    """The newest row of each share table, or the error that stopped the read."""
    from . import snowflake

    try:
        connection = snowflake.connect(snowflake.connection_name(), timeout)
    except DataError as error:
        return {table: error for table in SNOWFLAKE_TABLES}
    found: dict[str, datetime | Exception] = {}
    try:
        cursor = connection.cursor()
        for table, sql in SNOWFLAKE_TABLES.items():
            try:
                cursor.execute(sql)
                value = cursor.fetchone()[0]
                if value is None:
                    raise DataError(f"{table} has no row in the last 30 days")
                found[table] = value.replace(tzinfo=UTC)
            except Exception as error:  # noqa: BLE001 - a connector error names the table; the probe reports it instead of stopping.
                found[table] = error
    finally:
        connection.close()
    return found


def walk_newest(dataset_id: str, column: str) -> datetime:
    """The newest record of this repository's own latest built walk."""
    path = datasets.parquet_path(dataset_id)
    connection = duckdb.connect()
    try:
        value = connection.execute(f"SELECT MAX({column}) FROM read_parquet(?)", [str(path)]).fetchone()[0]
    finally:
        connection.close()
    if value is None:
        raise DataError(f"the latest {dataset_id} run has no rows")
    return value.replace(tzinfo=UTC)


def probes(timeout: float) -> dict[str, Callable[[], datetime | Exception]]:
    """Each source's name and a call that returns the time of its newest record."""
    def safe(call: Callable[[], datetime]) -> Callable[[], datetime | Exception]:
        def run() -> datetime | Exception:
            try:
                return call()
            except Exception as error:  # noqa: BLE001 - any failure to read is a finding, never a crash of the monitor.
                return error
        return run

    shared: dict[str, dict[str, datetime | Exception]] = {}

    def table(name: str) -> Callable[[], datetime | Exception]:
        def run() -> datetime | Exception:
            if "tables" not in shared:
                shared["tables"] = snowflake_tables(timeout)
            return shared["tables"][name]
        return run

    return {
        **{f"snowflake {name}": table(name) for name in SNOWFLAKE_TABLES},
        "p-chain rpc head": safe(lambda: p_chain_head(timeout)),
        "tenderly c-chain head": safe(lambda: tenderly_head(timeout)),
        "data api p-chain head": safe(lambda: data_api_p_head(timeout)),
        **{f"metrics api {name}": safe(lambda url=url: metrics_point(url)(timeout)) for name, url in METRICS_SERIES.items()},
        **{f"our walk {dataset_id}": safe(lambda dataset_id=dataset_id, column=column: walk_newest(dataset_id, column))
           for dataset_id, column in WALKS.items()},
    }


def measure(sources: dict[str, Callable[[], datetime | Exception]], clock: datetime | None = None,
            stale_hours: float = STALE_HOURS, known: dict[str, tuple[str, str]] | None = None) -> dict[str, Any]:
    """One row per source: its newest record, its age in hours, and fresh, stale, known stale, or error."""
    clock = datetime.now(UTC) if clock is None else clock
    known = KNOWN_STOPPED if known is None else known
    rows = []
    for name, probe in sources.items():
        value = probe()
        if isinstance(value, Exception):
            rows.append({"source": name, "status": "error", "newest": None, "age_hours": None, "error": str(value)[:300]})
            continue
        age = (clock - value).total_seconds() / 3600
        newest = value.strftime("%Y-%m-%dT%H:%M:%SZ")
        row = {"source": name, "status": "stale" if age > stale_hours else "fresh", "newest": newest, "age_hours": round(age, 1)}
        if row["status"] == "stale" and name in known and newest <= known[name][0]:
            row.update(status="known stale", error=known[name][1])
        rows.append(row)
    return {
        "measured_at": clock.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stale_hours": stale_hours,
        "status": "pass" if all(row["status"] in ("fresh", "known stale") for row in rows) else "attention",
        "sources": rows,
    }
