"""Captures from the Avalanche Foundation's Snowflake account: Allium's hourly token prices, Allium's hourly WAVAX price
from decentralised exchange trades, Allium's lending rate updates, the Foundation's daily C-Chain gas fees and
benchmark rates, the last C-Chain block of each UTC day, the Foundation's monthly Gross Chain Product and Income and daily protocol
revenue streams, Allium's daily chain overview, Allium's atomic transactions between the C-Chain and the P-Chain, and the entity labels of Allium and
of the Foundation for the C-Chain addresses those transactions touch.

The account is read-only and reached through a named connection, ``foundation`` unless
``AVALANCHE_FOUNDATION_SNOWFLAKE_CONNECTION`` names another, which snowflake-connector-python resolves from its
connections.toml file. The account, user, role, warehouse and key file live in that file, outside the repository, and
never enter a capture, a receipt or the output. Each dataset is one query file. A capture records the SQL text, its
bound parameters, the Snowflake query ID and the session's role, warehouse, database and schema, and keeps every row the
query returns in a compressed JSON-lines file with its SHA-256 hash. The capture holds every row of the table in its
window, held-back dates included. The build types the rows and cuts nothing.

The checks report what can be wrong with each table: a repeated key, a value that cannot be right, such as a price that
is not positive or a negative rate, a row outside the captured window, and, for the price service, native AVAX against
WAVAX in the hours both hold. Missing hours or days are counted per token, with the longest run, and reported in the
summary rather than as findings, because the sources have genuine gaps: WAVAX lacks a few hours of the price service,
the exchange price lacks hours without trades, and the gas table lacks days on which its economy recorded no fee. The
lending summary counts each market's updates and the updates with a supply rate, which Compound v2 forks never record.
The exchange price can be checked against a built ``allium.prices-hourly`` run, day by day at the UTC close, and the
benchmark rates against a built ``fred.tbill-3m-daily`` run on the days the table marks as FRED's own value.
"""

from __future__ import annotations

import gzip
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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
from .capture.snowflake import (
    FETCH_SIZE,
    _connector_error,
    _json_value,
    _session,
    connect,
    read_sql,
)

SOURCE_ID = "af-foundation-snowflake"
CONNECTION_VARIABLE = "AVALANCHE_FOUNDATION_SNOWFLAKE_CONNECTION"
DEFAULT_CONNECTION = "foundation"
SCHEMA = "foundation-snowflake-capture/v1"
BUILD_SCHEMA = "foundation-snowflake-build/v1"
NATIVE_AVAX = "0x0000000000000000000000000000000000000000"
WAVAX = "0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7"
TOKENS = {
    NATIVE_AVAX: "AVAX",
    WAVAX: "WAVAX",
    "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be": "sAVAX",
    "0xa25eaf2906fa1a3a13edac9b9657108af7b703e3": "ggAVAX",
    "0xf7d9281e8e363584973f946201b82ba72c965d27": "yyAVAX",
}
# Native AVAX and WAVAX are one asset, so their prices in the same hour should agree. The service quotes the two
# addresses separately and each carries isolated single-hour spikes: in the 2026-11-05 capture 94.6% of the 38,844
# shared hours agree within 0.5%, 99.0% within 2%, and 104 hours differ by more than 5%. A 2% band on 98% of hours
# catches a feed that drifts or freezes; the spikes are reported with the largest difference.
PAIR_TOLERANCE = 0.02
PAIR_SHARE = 0.98
# The exchange price against the service's WAVAX price at the UTC close, on the days both hold.
DEX_TOLERANCE = 0.03
DEX_SHARE = 0.95
# The benchmark table's published DTB3 days must equal FRED's: a decimal rate times 100 against FRED's percent.
FRED_TBILL_ID = "fred.tbill-3m-daily"
FRED_TOLERANCE = 1e-9


@dataclass(frozen=True)
class Spec:
    """One dataset: its query, the captured columns and types, the typed table, its key, and its time grid."""

    dataset_id: str
    query_id: str
    table: str
    default_start: str
    raw_types: dict[str, str]
    table_columns: dict[str, str]
    transform_sql: str
    key: tuple[str, ...]
    time_column: str
    step: str | None
    group: str | None
    invalid_sql: str
    invalid_label: str


PRICES_HOURLY = Spec(
    dataset_id="allium.prices-hourly",
    query_id="allium-prices-hourly",
    table="prices-hourly",
    default_start="2022-06-01",
    raw_types={
        "chain": "VARCHAR", "id": "VARCHAR", "symbol": "VARCHAR", "address": "VARCHAR", "decimals": "INTEGER",
        "hour_utc": "TIMESTAMP", "price_text": "VARCHAR", "created_at": "TIMESTAMP",
    },
    table_columns={
        "token": "VARCHAR", "address": "VARCHAR", "symbol": "VARCHAR", "price_id": "VARCHAR", "chain": "VARCHAR",
        "decimals": "INTEGER", "hour_utc": "TIMESTAMP", "price_usd": "DOUBLE", "created_at": "TIMESTAMP",
    },
    transform_sql="""
        SELECT CASE address {cases} END AS token, address, symbol, id AS price_id, chain, decimals, hour_utc,
               TRY_CAST(price_text AS DOUBLE) AS price_usd, created_at
        FROM capture ORDER BY address, hour_utc""".replace(
        "{cases}", " ".join(f"WHEN '{address}' THEN '{name}'" for address, name in TOKENS.items())),
    key=("address", "hour_utc"),
    time_column="hour_utc",
    step="hour",
    group="token",
    invalid_sql="price_usd IS NULL OR price_usd <= 0",
    invalid_label="carry a missing or non-positive price",
)

DEX_PRICES_HOURLY = Spec(
    dataset_id="allium.dex-token-prices-hourly",
    query_id="allium-dex-token-prices-hourly",
    table="dex-token-prices-hourly",
    default_start="2021-02-02",
    raw_types={
        "chain": "VARCHAR", "address": "VARCHAR", "symbol": "VARCHAR", "hour_utc": "TIMESTAMP", "price": "DOUBLE",
        "median_price": "DOUBLE", "median_safe_price": "DOUBLE", "usd_trading_volume": "DOUBLE", "traders": "BIGINT",
        "trade_count": "BIGINT",
    },
    table_columns={
        "address": "VARCHAR", "symbol": "VARCHAR", "chain": "VARCHAR", "hour_utc": "TIMESTAMP", "price_usd": "DOUBLE",
        "median_price_usd": "DOUBLE", "median_safe_price_usd": "DOUBLE", "usd_trading_volume": "DOUBLE",
        "traders": "BIGINT", "trade_count": "BIGINT",
    },
    transform_sql="""
        SELECT address, symbol, chain, hour_utc, price AS price_usd, median_price AS median_price_usd,
               median_safe_price AS median_safe_price_usd, usd_trading_volume, traders, trade_count
        FROM capture ORDER BY hour_utc""",
    key=("address", "hour_utc"),
    time_column="hour_utc",
    step="hour",
    group="symbol",
    invalid_sql="price_usd IS NULL OR price_usd <= 0",
    invalid_label="carry a missing or non-positive price",
)

ECONOMY_GAS_FEES_DAILY = Spec(
    dataset_id="af.economy-gas-fees-daily",
    query_id="af-economy-gas-fees-daily",
    table="economy-gas-fees-daily",
    default_start="2020-09-23",
    raw_types={
        "date_utc": "DATE", "gas_used_avax": "DOUBLE", "gas_used_usd": "DOUBLE", "gas_used_usd_ref": "DOUBLE",
        "gas_used_avax_ref": "DOUBLE",
    },
    table_columns={
        "date_utc": "DATE", "gas_used_avax": "DOUBLE", "gas_used_usd": "DOUBLE", "gas_used_usd_ref": "DOUBLE",
        "gas_used_avax_ref": "DOUBLE",
    },
    transform_sql="SELECT * FROM capture ORDER BY date_utc",
    key=("date_utc",),
    time_column="date_utc",
    step="day",
    group=None,
    invalid_sql="gas_used_avax IS NULL OR gas_used_avax <= 0",
    invalid_label="carry a missing or non-positive burn",
)

_LENDING_COLUMNS = {
    "project": "VARCHAR", "protocol": "VARCHAR", "market_address": "VARCHAR", "token_address": "VARCHAR",
    "token_symbol": "VARCHAR", "block_timestamp": "TIMESTAMP", "block_number": "BIGINT", "unique_id": "VARCHAR",
    "supply_apy": "DOUBLE", "variable_borrow_apy": "DOUBLE", "stable_borrow_apy": "DOUBLE", "supplied_amount": "DOUBLE",
    "supplied_amount_usd": "DOUBLE", "outstanding_loans": "DOUBLE", "usd_exchange_rate": "DOUBLE",
}

LENDING_INTEREST_RATES = Spec(
    dataset_id="allium.lending-interest-rates",
    query_id="allium-lending-interest-rates",
    table="lending-interest-rates",
    default_start="2021-01-01",
    raw_types=_LENDING_COLUMNS,
    table_columns=_LENDING_COLUMNS,
    transform_sql="SELECT * FROM capture ORDER BY block_timestamp, unique_id",
    key=("unique_id",),
    time_column="block_timestamp",
    step=None,
    group=None,
    invalid_sql="supply_apy < 0 OR variable_borrow_apy < 0 OR supplied_amount < 0 OR outstanding_loans < 0",
    invalid_label="carry a negative rate or amount",
)

BENCHMARK_RATES_DAILY = Spec(
    dataset_id="af.benchmark-rates-daily",
    query_id="af-benchmark-rates-daily",
    table="benchmark-rates-daily",
    default_start="2024-01-01",
    raw_types={"date_utc": "DATE", "rate_id": "VARCHAR", "rate_annual": "DOUBLE", "source": "VARCHAR"},
    table_columns={"date_utc": "DATE", "rate_id": "VARCHAR", "rate_annual": "DOUBLE", "source": "VARCHAR"},
    transform_sql="SELECT * FROM capture ORDER BY date_utc, rate_id",
    key=("date_utc", "rate_id"),
    time_column="date_utc",
    step="day",
    group="rate_id",
    invalid_sql="rate_annual IS NULL OR rate_annual < 0",
    invalid_label="carry a missing or negative rate",
)

P_CHAIN_ATOMIC = Spec(
    dataset_id="allium.p-chain-atomic-transactions",
    query_id="allium-p-chain-atomic-transactions",
    table="p-chain-atomic-transactions",
    default_start="2021-12-01",
    raw_types={
        "hash": "VARCHAR", "source_chain": "VARCHAR", "destination_chain": "VARCHAR", "from_address": "VARCHAR",
        "to_address": "VARCHAR", "amount_navax_text": "VARCHAR", "amount_avax": "DOUBLE", "fees_avax": "DOUBLE",
        "output_json": "VARCHAR", "block_timestamp": "TIMESTAMP", "block_number": "BIGINT",
    },
    table_columns={
        "transaction_hash": "VARCHAR", "direction": "VARCHAR", "c_chain_address": "VARCHAR", "p_chain_address": "VARCHAR",
        "output_addresses": "VARCHAR", "amount_navax": "BIGINT", "amount_avax": "DOUBLE", "fees_avax": "DOUBLE",
        "output_json": "VARCHAR", "block_timestamp": "TIMESTAMP", "block_number": "BIGINT",
    },
    # An export's P-Chain side is every owner address of its outputs, which may differ from TO_ADDRESS or hold several
    # addresses, joined sorted with commas without the P- prefix; Allium writes them as ``addresses`` or as
    # ``owner.addresses``. An import's is its one P-Chain sender. RAW_AMOUNT is in nAVAX on some rows and in wei, 10^18
    # per AVAX, on others; the unit is the one that matches AMOUNT, and a wei amount converts exactly or not at all.
    transform_sql="""
        WITH typed AS (
            SELECT *, TRY_CAST(amount_navax_text AS HUGEINT) AS raw_amount,
                   list_distinct(list_transform(
                       list_concat(coalesce(json_extract_string(output_json, '$[*].addresses[*]'), []),
                                   coalesce(json_extract_string(output_json, '$[*].owner.addresses[*]'), [])),
                       x -> regexp_replace(x, '^P-', ''))) AS owners
            FROM capture)
        SELECT hash AS transaction_hash,
               CASE WHEN source_chain = 'c-chain' AND destination_chain = 'p-chain' THEN 'export'
                    WHEN source_chain = 'p-chain' AND destination_chain = 'c-chain' THEN 'import' END AS direction,
               CASE WHEN source_chain = 'c-chain' THEN from_address ELSE to_address END AS c_chain_address,
               CASE WHEN source_chain = 'c-chain' THEN to_address ELSE from_address END AS p_chain_address,
               CASE WHEN source_chain = 'c-chain' THEN nullif(array_to_string(list_sort(owners), ','), '')
                    ELSE from_address END AS output_addresses,
               CASE WHEN abs(raw_amount / 1e9 - amount_avax) <= 1e-6 * greatest(amount_avax, 1) THEN raw_amount::BIGINT
                    WHEN abs(raw_amount / 1e18 - amount_avax) <= 1e-6 * greatest(amount_avax, 1)
                         AND raw_amount % 1000000000 = 0 THEN (raw_amount // 1000000000)::BIGINT END AS amount_navax,
               amount_avax, fees_avax, output_json, block_timestamp, block_number
        FROM typed ORDER BY block_timestamp, hash""",
    key=("transaction_hash",),
    time_column="block_timestamp",
    step=None,
    group=None,
    invalid_sql=("direction IS NULL OR c_chain_address IS NULL OR amount_navax IS NULL OR amount_navax <= 0"
                 " OR (direction = 'export' AND output_addresses IS NULL)"),
    invalid_label="miss a direction, a C-Chain address, a positive nAVAX amount or an export's P-Chain owner",
)

IDENTITY_LABELS_ATOMIC = Spec(
    dataset_id="allium.identity-labels-atomic",
    query_id="allium-identity-labels-atomic",
    table="identity-labels-atomic",
    default_start="2021-12-01",
    raw_types={
        "address": "VARCHAR", "primary_label": "VARCHAR", "primary_entity": "VARCHAR", "primary_category": "VARCHAR",
        "subcategory_json": "VARCHAR", "confidence": "DOUBLE", "attribution_date": "TIMESTAMP", "source_type": "VARCHAR",
        "source_system": "VARCHAR", "source_priority": "INTEGER", "entity_ranking": "INTEGER", "first_atomic_at": "TIMESTAMP",
    },
    table_columns={
        "address": "VARCHAR", "primary_label": "VARCHAR", "primary_entity": "VARCHAR", "primary_category": "VARCHAR",
        "subcategory_json": "VARCHAR", "confidence": "DOUBLE", "attribution_date": "TIMESTAMP", "source_type": "VARCHAR",
        "source_system": "VARCHAR", "source_priority": "INTEGER", "entity_ranking": "INTEGER", "first_atomic_at": "TIMESTAMP",
    },
    transform_sql="SELECT * FROM capture ORDER BY address",
    key=("address",),
    time_column="first_atomic_at",
    step=None,
    group=None,
    invalid_sql="primary_entity IS NULL AND primary_category IS NULL",
    invalid_label="name neither an entity nor a category",
)

ADDRESS_MAPPING_ATOMIC = Spec(
    dataset_id="af.address-mapping-atomic",
    query_id="af-address-mapping-atomic",
    table="address-mapping-atomic",
    default_start="2021-12-01",
    raw_types={
        "address": "VARCHAR", "entity": "VARCHAR", "sub_entity": "VARCHAR", "category": "VARCHAR", "sector": "VARCHAR",
        "source": "VARCHAR", "priority": "INTEGER", "first_atomic_at": "TIMESTAMP",
    },
    table_columns={
        "address": "VARCHAR", "entity": "VARCHAR", "sub_entity": "VARCHAR", "category": "VARCHAR", "sector": "VARCHAR",
        "source": "VARCHAR", "priority": "INTEGER", "first_atomic_at": "TIMESTAMP",
    },
    transform_sql="SELECT * FROM capture ORDER BY address",
    key=("address",),
    time_column="first_atomic_at",
    step=None,
    group=None,
    invalid_sql="entity IS NULL",
    invalid_label="name no entity",
)

C_CHAIN_DAILY_LAST_BLOCKS = Spec(
    dataset_id="allium.c-chain-daily-last-blocks",
    query_id="allium-c-chain-daily-last-blocks",
    table="c-chain-daily-last-blocks",
    default_start="2020-09-23",
    raw_types={
        "date_utc": "DATE", "last_block_number": "BIGINT", "last_block_hash": "VARCHAR", "last_block_timestamp": "TIMESTAMP",
        "first_block_number": "BIGINT", "blocks": "BIGINT",
    },
    table_columns={
        "date_utc": "DATE", "last_block_number": "BIGINT", "last_block_hash": "VARCHAR", "last_block_timestamp": "TIMESTAMP",
        "first_block_number": "BIGINT", "blocks": "BIGINT",
    },
    transform_sql="SELECT * FROM capture ORDER BY date_utc",
    key=("date_utc",),
    time_column="date_utc",
    step="day",
    group=None,
    invalid_sql=("last_block_hash IS NULL OR blocks <= 0 OR last_block_number - first_block_number + 1 <> blocks"
                 " OR last_block_timestamp::DATE <> date_utc"),
    invalid_label="miss a hash, skip a block height or end on another day",
)

_GCP_GCI_COLUMNS = {"layer": "VARCHAR", "period_start_date": "DATE", "period_interval": "VARCHAR", "ngcp_usd": "DOUBLE", "ngcp_avax": "DOUBLE", "l_usd": "DOUBLE", "p_usd": "DOUBLE", "g_usd": "DOUBLE", "l_avax": "DOUBLE", "p_avax": "DOUBLE", "g_avax": "DOUBLE", "rgcp_level_usd": "DOUBLE", "rgcp_level_avax": "DOUBLE", "holder_yield_usd": "DOUBLE", "issuer_yield_usd": "DOUBLE", "issuer_yield_offchain_usd": "DOUBLE", "ngci_usd": "DOUBLE", "ngci_general_usd": "DOUBLE", "holder_yield_avax": "DOUBLE", "issuer_yield_avax": "DOUBLE", "issuer_yield_offchain_avax": "DOUBLE", "ngci_avax": "DOUBLE", "ngci_general_avax": "DOUBLE"}

GCP_GCI_MONTHLY = Spec(
    dataset_id="af.gcp-gci-monthly",
    query_id="af-gcp-gci-monthly",
    table="gcp-gci-monthly",
    default_start="2020-09-01",
    raw_types=_GCP_GCI_COLUMNS,
    table_columns=_GCP_GCI_COLUMNS,
    transform_sql="SELECT * FROM capture ORDER BY layer, period_start_date",
    key=("layer", "period_start_date", "period_interval"),
    time_column="period_start_date",
    step="month",
    group="layer",
    # USD values start in February 2021, when the pipeline first has a USD price; the months before carry AVAX only.
    invalid_sql="ngcp_avax IS NULL OR period_interval <> 'month'",
    invalid_label="miss the nominal product in AVAX or are not monthly",
)

_STREAM_COLUMNS = {
    "protocol_id": "VARCHAR", "date_utc": "DATE", "stream_id": "VARCHAR", "stream_type": "VARCHAR",
    "denomination_token_address": "VARCHAR", "denomination_token_symbol": "VARCHAR", "amount_token": "DOUBLE",
    "amount_usd": "DOUBLE", "amount_avax": "DOUBLE", "amount_usd_ref": "DOUBLE", "amount_avax_ref": "DOUBLE", "chain_id": "VARCHAR",
}

PROTOCOL_STREAMS_DAILY = Spec(
    dataset_id="af.protocol-stream-token-metrics-daily",
    query_id="af-protocol-stream-token-metrics-daily",
    table="protocol-stream-token-metrics-daily",
    default_start="2021-01-01",
    raw_types=_STREAM_COLUMNS,
    table_columns=_STREAM_COLUMNS,
    transform_sql="SELECT * FROM capture ORDER BY protocol_id, date_utc, stream_id, denomination_token_address, chain_id",
    key=("protocol_id", "date_utc", "stream_id", "denomination_token_address", "chain_id"),
    time_column="date_utc",
    step=None,
    group=None,
    # A fund's holder yield is negative on a day its value fell; revenue and cost streams are never negative.
    invalid_sql="stream_type IN ('revenue', 'cost') AND (amount_token < 0 OR amount_avax < 0 OR amount_usd < 0)",
    invalid_label="carry a negative revenue or cost",
)

_OVERVIEW_COLUMNS = {
    "chain": "VARCHAR", "date_utc": "DATE", "total_blocks": "BIGINT", "total_transactions": "BIGINT",
    "success_transactions": "BIGINT", "failed_transactions": "BIGINT", "transaction_fees": "DOUBLE",
    "transaction_fees_usd": "DOUBLE", "active_addresses": "BIGINT", "new_addresses": "BIGINT",
    "native_token_price_median_usd": "DOUBLE",
}

METRICS_OVERVIEW_DAILY = Spec(
    dataset_id="allium.metrics-overview-daily",
    query_id="allium-metrics-overview-daily",
    table="metrics-overview-daily",
    default_start="2020-09-23",
    raw_types=_OVERVIEW_COLUMNS,
    table_columns=_OVERVIEW_COLUMNS,
    transform_sql="SELECT * FROM capture ORDER BY chain, date_utc",
    key=("chain", "date_utc"),
    time_column="date_utc",
    step="day",
    group="chain",
    invalid_sql="transaction_fees IS NULL OR transaction_fees < 0 OR total_transactions < 0",
    invalid_label="miss the fees or carry a negative count",
)

SPECS = {spec.dataset_id: spec for spec in (
    PRICES_HOURLY, DEX_PRICES_HOURLY, ECONOMY_GAS_FEES_DAILY, LENDING_INTEREST_RATES, BENCHMARK_RATES_DAILY,
    P_CHAIN_ATOMIC, IDENTITY_LABELS_ATOMIC, ADDRESS_MAPPING_ATOMIC, C_CHAIN_DAILY_LAST_BLOCKS, GCP_GCI_MONTHLY,
    PROTOCOL_STREAMS_DAILY, METRICS_OVERVIEW_DAILY)}
DATASET_IDS = tuple(SPECS)


def connection_name() -> str:
    return os.environ.get(CONNECTION_VARIABLE, DEFAULT_CONNECTION)


def spec_for(dataset_id: str) -> Spec:
    try:
        return SPECS[dataset_id]
    except KeyError:
        raise DataError(f"unknown Foundation Snowflake dataset: {dataset_id}") from None


def query_definition(catalog: dict[str, Any], dataset_id: str) -> dict[str, Any]:
    spec = spec_for(dataset_id)
    definition = dataset(catalog, dataset_id)
    provider = source(catalog, definition["source_id"])
    if provider["id"] != SOURCE_ID or definition.get("query_ids") != [spec.query_id]:
        raise DataError(f"dataset is not a Foundation Snowflake query dataset: {dataset_id}")
    return next(item for item in provider["queries"] if item["id"] == spec.query_id)


def resolve_parameters(spec: Spec, parameters: dict[str, str] | None) -> dict[str, str]:
    """The half-open window: ``start`` defaults to the table's first date, ``end`` to the day after the capture day, so a
    default capture holds every row the table has."""
    values = dict(parameters or {})
    unknown = sorted(set(values) - {"start", "end"})
    if unknown:
        raise DataError(f"unknown parameters: {', '.join(unknown)}; expected start and end dates")
    tomorrow = datetime.now(UTC).date() + timedelta(days=1)
    resolved = {"start": values.get("start", spec.default_start), "end": values.get("end", tomorrow.isoformat())}
    bounds = {}
    for key, text in resolved.items():
        try:
            bounds[key] = date.fromisoformat(text)
        except ValueError as error:
            raise DataError(f"{key} must be an ISO date (YYYY-MM-DD): {text}") from error
    if bounds["start"] >= bounds["end"]:
        raise DataError(f"start must precede end: {resolved['start']} >= {resolved['end']}")
    return {key: bounds[key].isoformat() for key in ("start", "end")}


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None,
                    catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    spec = spec_for(dataset_id)
    query = query_definition(catalog, dataset_id)
    sql_text = read_sql(query)
    return {
        "dataset_id": dataset_id,
        "source_id": SOURCE_ID,
        "output": str(output),
        "connection": connection_name(),
        "query_id": spec.query_id,
        "sql": query["sql"],
        "sql_sha256": sha256(sql_text.encode()),
        "parameters": resolve_parameters(spec, parameters),
        "writes": [f"raw/{spec.query_id}.sql", f"raw/{spec.query_id}.jsonl.gz", "capture.json"],
        "overwrite": False,
    }


def capture(dataset_id: str, output: Path, timeout: float = 20, parameters: dict[str, str] | None = None,
            catalog: dict[str, Any] | None = None,
            connector: Callable[[str, float], Any] = connect) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    spec = spec_for(dataset_id)
    preview = capture_preview(dataset_id, output, parameters, catalog)
    sql_text = read_sql(query_definition(catalog, dataset_id))
    expected = tuple(spec.raw_types)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        raw = temporary / "raw"
        raw.mkdir()
        sql_path = raw / f"{spec.query_id}.sql"
        rows_path = raw / f"{spec.query_id}.jsonl.gz"
        sql_path.write_text(sql_text, encoding="utf-8")
        started_at = now()
        connection = connector(preview["connection"], timeout)
        try:
            session = _session(connection)
            cursor = connection.cursor()
            try:
                cursor.execute(sql_text, preview["parameters"])
                columns = tuple(item[0].lower() for item in cursor.description)
                if columns != expected:
                    raise DataError(f"query returned unexpected columns: {', '.join(columns)}")
                rows = 0
                with rows_path.open("wb") as file, gzip.GzipFile(fileobj=file, mode="wb", mtime=0) as handle:
                    while batch := cursor.fetchmany(FETCH_SIZE):
                        for record in batch:
                            values = dict(zip(columns, (_json_value(value) for value in record)))
                            handle.write((json.dumps(values, ensure_ascii=False, sort_keys=True) + "\n").encode())
                            rows += 1
                snowflake_query_id = cursor.sfqid
            finally:
                cursor.close()
        finally:
            connection.close()
        completed_at = now()
        body = rows_path.read_bytes()
        record = {
            "query_id": spec.query_id, "sql_path": f"raw/{sql_path.name}", "sql_sha256": preview["sql_sha256"],
            "parameters": preview["parameters"], "snowflake_query_id": snowflake_query_id, "started_at": started_at,
            "completed_at": completed_at, "columns": list(columns), "rows": rows, "path": f"raw/{rows_path.name}",
            "bytes": len(body), "sha256": sha256(body),
        }
        identity = sha256(canonical_bytes({"completed_at": completed_at, "queries": [record]}))
        receipt = {
            "schema_version": SCHEMA,
            "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
            "dataset_id": dataset_id,
            "source_id": SOURCE_ID,
            "completed_at": completed_at,
            "contract_sha256": contract_hash(catalog, dataset_id),
            "tool": f"avalanche-research@{__version__}",
            "session": session,
            "queries": [record],
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        os.replace(temporary, output)
    except Exception as error:
        shutil.rmtree(temporary, ignore_errors=True)
        if _connector_error(error):
            raise DataError(f"Snowflake query failed: {error}") from error
        raise
    return receipt


def read_capture(capture_dir: Path, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verify a capture's receipt, query text and result hash, and return the receipt."""
    catalog = catalog or load_catalog()
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid capture receipt: {error}") from error
    if receipt.get("schema_version") != SCHEMA:
        raise DataError("unsupported capture receipt schema")
    spec = spec_for(receipt.get("dataset_id", ""))
    if receipt.get("contract_sha256") != contract_hash(catalog, spec.dataset_id):
        raise DataError("capture contract hash differs from the current data contract")
    if len(receipt.get("queries", [])) != 1 or receipt["queries"][0].get("query_id") != spec.query_id:
        raise DataError("capture does not contain the expected query")
    record = receipt["queries"][0]
    current_sql = read_sql(query_definition(catalog, spec.dataset_id))
    try:
        captured_sql = (capture_dir / record["sql_path"]).read_bytes()
        body = (capture_dir / record["path"]).read_bytes()
    except (OSError, KeyError) as error:
        raise DataError(f"missing captured query output: {error}") from error
    if sha256(captured_sql) != record.get("sql_sha256") or captured_sql != current_sql.encode():
        raise DataError("captured query text differs from the current data contract")
    if sha256(body) != record.get("sha256") or len(body) != record.get("bytes"):
        raise DataError(f"captured result hash or size differs: {record['path']}")
    if tuple(record.get("columns", ())) != tuple(spec.raw_types) or not isinstance(record.get("rows"), int):
        raise DataError("captured result columns differ from the data contract")
    return receipt


def load_capture(connection: Any, spec: Spec, capture_dir: Path, receipt: dict[str, Any]) -> None:
    """Read the compressed capture into DuckDB with the declared types and build the typed ``rows`` table. A row the
    table cannot use, one without its key, an unknown token or a price that is not a number, is refused."""
    record = receipt["queries"][0]
    declared = ", ".join(f"{name}: '{kind}'" for name, kind in spec.raw_types.items())
    typed = ", ".join(f"{name} {kind}" for name, kind in spec.table_columns.items())
    path = str(capture_dir / record["path"]).replace("'", "''")
    try:
        connection.execute(
            f"CREATE VIEW capture AS SELECT * FROM read_json('{path}', columns={{{declared}}}, format='newline_delimited')")
        connection.execute(f"CREATE TABLE rows({typed})")
        connection.execute(f"INSERT INTO rows {spec.transform_sql}")
        count = connection.execute("SELECT COUNT(*) FROM rows").fetchone()[0]
    except duckdb.Error as error:
        raise DataError(f"captured rows do not match the declared types: {error}") from error
    if count != record["rows"]:
        raise DataError(f"captured result holds {count} rows, receipt declares {record['rows']}")
    missing = connection.execute(f"SELECT COUNT_IF({' OR '.join(f'{name} IS NULL' for name in spec.key)}) FROM rows").fetchone()[0]
    if missing:
        raise DataError(f"{missing} captured rows miss a key field")
    if spec is PRICES_HOURLY:
        unknown, unreadable = connection.execute(
            "SELECT COUNT_IF(token IS NULL), COUNT_IF(price_usd IS NULL) FROM rows").fetchone()
        if unknown:
            raise DataError(f"{unknown} captured rows name a token address outside the query")
        if unreadable:
            raise DataError(f"{unreadable} captured prices are not numbers")


def coverage(connection: Any, spec: Spec) -> dict[str, Any]:
    """Per token (or for the table), its rows, first and last time, the steps missing between them, and the longest run
    of missing steps with where it starts."""
    group = spec.group or "'all'"
    unit = spec.step
    rows = connection.execute(f"""
        WITH t AS (SELECT grp, ts, lead(ts) OVER (PARTITION BY grp ORDER BY ts) AS next_ts
                   FROM (SELECT DISTINCT {group} AS grp, {spec.time_column} AS ts FROM rows)),
             g AS (SELECT grp, ts, COALESCE(date_diff('{unit}', ts, next_ts) - 1, 0) AS missing FROM t)
        SELECT grp, COUNT(*), MIN(ts), MAX(ts), SUM(missing), COUNT_IF(missing > 0), MAX(missing),
               arg_max(ts, missing) FILTER (WHERE missing > 0)
        FROM g GROUP BY grp ORDER BY grp""").fetchall()
    return {
        grp: {"rows": count, "first": _json_value(first), "last": _json_value(last), f"missing_{unit}s": int(missing),
              "gaps": gaps, f"longest_gap_{unit}s": int(longest), "longest_gap_after": _json_value(after)}
        for grp, count, first, last, missing, gaps, longest, after in rows
    }


def markets(connection: Any) -> dict[str, Any]:
    """Per project, protocol and token: its updates, the updates with a supply rate, its markets, and its first and
    last update. Compound v2 forks record no supply rate."""
    rows = connection.execute("""
        SELECT project || '/' || protocol || '/' || token_symbol, COUNT(*), COUNT(supply_apy), COUNT(DISTINCT market_address),
               MIN(block_timestamp), MAX(block_timestamp), MAX(supply_apy)
        FROM rows GROUP BY 1 ORDER BY 1""").fetchall()
    return {name: {"updates": count, "with_supply_rate": rated, "markets": markets_, "first": _json_value(first),
                   "last": _json_value(last), "max_supply_apy": None if top is None else round(top, 6)}
            for name, count, rated, markets_, first, last, top in rows}


def summarize(connection: Any, spec: Spec) -> dict[str, Any]:
    count, first, last = connection.execute(
        f"SELECT COUNT(*), MIN({spec.time_column}), MAX({spec.time_column}) FROM rows").fetchone()
    summary: dict[str, Any] = {"rows": count, "first": _json_value(first), "last": _json_value(last)}
    if spec.step is not None:
        summary["coverage"] = coverage(connection, spec)
    if spec is ECONOMY_GAS_FEES_DAILY:
        total, without = connection.execute("SELECT SUM(gas_used_avax), COUNT_IF(gas_used_usd IS NULL) FROM rows").fetchone()
        summary["gas_used_avax_total"] = round(total or 0, 6)
        summary["rows_without_usd"] = without
    if spec is LENDING_INTEREST_RATES:
        summary["by_market"] = markets(connection)
    if spec is BENCHMARK_RATES_DAILY:
        summary["rows_by_source"] = dict(connection.execute(
            "SELECT rate_id || ' ' || source, COUNT(*) FROM rows GROUP BY 1 ORDER BY 1").fetchall())
    if spec is P_CHAIN_ATOMIC:
        summary["by_direction"] = {
            direction: {"transactions": count, "avax": round(avax, 6), "c_chain_addresses": c_addresses,
                        "p_chain_addresses": p_addresses}
            for direction, count, avax, c_addresses, p_addresses in connection.execute("""
                SELECT direction, COUNT(*), SUM(amount_navax) / 1e9, COUNT(DISTINCT c_chain_address),
                       COUNT(DISTINCT p_chain_address)
                FROM rows GROUP BY 1 ORDER BY 1""").fetchall()}
        summary["exports_paying_another_address"], summary["imports_without_p_chain_sender"], summary["amounts_in_wei"] = \
            connection.execute("""
                SELECT COUNT_IF(direction = 'export' AND output_addresses <> p_chain_address),
                       COUNT_IF(direction = 'import' AND p_chain_address IS NULL),
                       COUNT_IF(length(amount_navax_text) > 0 AND amount_navax::HUGEINT <> TRY_CAST(amount_navax_text AS HUGEINT))
                FROM rows JOIN capture ON capture.hash = rows.transaction_hash""").fetchone()
    if spec is C_CHAIN_DAILY_LAST_BLOCKS:
        summary["blocks"], summary["height_breaks"] = connection.execute("""
            SELECT SUM(blocks), COUNT_IF(next_first IS NOT NULL AND next_first <> last_block_number + 1)
            FROM (SELECT blocks, last_block_number, lead(first_block_number) OVER (ORDER BY date_utc) AS next_first FROM rows)""").fetchone()
    if spec is GCP_GCI_MONTHLY:
        summary["by_year"] = {f"{layer} {year}": {"ngcp_avax": None if product is None else round(product, 3), "ngci_avax": None if income is None else round(income, 3)}
                              for layer, year, product, income in connection.execute("""
                                  SELECT layer, year(period_start_date), SUM(ngcp_avax), SUM(ngci_avax) FROM rows GROUP BY 1, 2 ORDER BY 1, 2""").fetchall()}
        summary["months_without_usd"] = connection.execute("SELECT COUNT_IF(ngcp_usd IS NULL) FROM rows").fetchone()[0]
    if spec is PROTOCOL_STREAMS_DAILY:
        summary["by_stream_year"] = {f"{protocol} {stream} {year}": round(avax or 0, 3) for protocol, stream, year, avax in connection.execute("""
            SELECT protocol_id, stream_id, year(date_utc), SUM(amount_avax) FROM rows GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""").fetchall()}
        summary["negative_yield_rows"] = dict(connection.execute("""
            SELECT stream_id, COUNT(*) FROM rows WHERE amount_avax < 0 GROUP BY 1 ORDER BY 1""").fetchall())
    if spec is METRICS_OVERVIEW_DAILY:
        summary["fees_avax_total"] = round(connection.execute("SELECT SUM(transaction_fees) FROM rows").fetchone()[0] or 0, 6)
    if spec is IDENTITY_LABELS_ATOMIC:
        summary["by_category"] = dict(connection.execute(
            "SELECT coalesce(primary_category, 'none'), COUNT(*) FROM rows GROUP BY 1 ORDER BY 1").fetchall())
    if spec is ADDRESS_MAPPING_ATOMIC:
        summary["by_category"] = dict(connection.execute(
            "SELECT coalesce(category, 'none') || ' ' || coalesce(source, 'none'), COUNT(*) FROM rows GROUP BY 1 ORDER BY 1").fetchall())
    return summary


def pair_agreement(connection: Any) -> dict[str, Any]:
    """Native AVAX against WAVAX in the hours the service prices both."""
    days, within, median, worst, worst_at = connection.execute(f"""
        WITH p AS (SELECT a.hour_utc, abs(a.price_usd / w.price_usd - 1) AS gap
                   FROM rows a JOIN rows w ON a.hour_utc = w.hour_utc
                   WHERE a.address = '{NATIVE_AVAX}' AND w.address = '{WAVAX}')
        SELECT COUNT(*), AVG(CASE WHEN gap <= {PAIR_TOLERANCE} THEN 1.0 ELSE 0.0 END), median(gap), MAX(gap), arg_max(hour_utc, gap)
        FROM p""").fetchone()
    return {"hours": days, "share_within": None if within is None else round(within, 6),
            "median_difference": None if median is None else round(median, 8),
            "max_difference": None if worst is None else round(worst, 6), "max_difference_at": _json_value(worst_at)}


def check_counts(connection: Any, spec: Spec, window: dict[str, str]) -> list[str]:
    key = ", ".join(spec.key)
    repeats, outside, invalid = connection.execute(f"""
        SELECT (SELECT COUNT(*) FROM rows) - (SELECT COUNT(*) FROM (SELECT DISTINCT {key} FROM rows)),
               COUNT_IF({spec.time_column} < ?::TIMESTAMP OR {spec.time_column} >= ?::TIMESTAMP),
               COUNT_IF({spec.invalid_sql})
        FROM rows""", [window["start"], window["end"]]).fetchone()
    labels = (
        (repeats, f"rows repeat a key ({key})"),
        (outside, "rows lie outside the captured window"),
        (invalid, f"rows {spec.invalid_label}"),
    )
    return [f"{count} {label}" for count, label in labels if count]


def dex_agreement(connection: Any, reference_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Each day's last exchange price against the service's WAVAX price at the same hour, on the days both hold."""
    try:
        built = json.loads((reference_dir / "build.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"no build receipt in {reference_dir}: {error}") from error
    if built.get("dataset_id") != PRICES_HOURLY.dataset_id:
        raise DataError(f"{reference_dir} is a run of {built.get('dataset_id')}, not {PRICES_HOURLY.dataset_id}")
    output = built["outputs"][0]
    parquet = reference_dir / output["path"]
    body = parquet.read_bytes()
    if len(body) != output["bytes"] or sha256(body) != output["sha256"]:
        raise DataError(f"reference Parquet differs from its build receipt: {parquet}")
    path = str(parquet).replace("'", "''")
    connection.execute(f"CREATE TEMP VIEW reference AS SELECT hour_utc, price_usd FROM read_parquet('{path}') WHERE address = '{WAVAX}'")
    days, within, median, worst, worst_day = connection.execute(f"""
        WITH d AS (SELECT hour_utc::DATE AS day, arg_max(hour_utc, hour_utc) AS at FROM rows GROUP BY 1),
             p AS (SELECT d.day, abs(r.price_usd / w.price_usd - 1) AS gap
                   FROM d JOIN rows r ON r.hour_utc = d.at JOIN reference w ON w.hour_utc = d.at)
        SELECT COUNT(*), AVG(CASE WHEN gap <= {DEX_TOLERANCE} THEN 1.0 ELSE 0.0 END), median(gap), MAX(gap), arg_max(day, gap)
        FROM p""").fetchone()
    summary = {"reference_days": days, "reference_share_within": None if within is None else round(within, 6),
               "reference_median_difference": None if median is None else round(median, 6),
               "reference_max_difference": None if worst is None else round(worst, 6),
               "reference_max_difference_day": _json_value(worst_day)}
    findings = []
    if not days:
        findings.append("no day shared with the price service's WAVAX price")
    elif within < DEX_SHARE:
        findings.append(f"{within:.2%} of {days} days lie within {DEX_TOLERANCE:.0%} of the price service's WAVAX price at "
                        f"the day's last exchange hour; at least {DEX_SHARE:.0%} must")
    return summary, findings


def _reference_parquet(reference_dir: Path, dataset_id: str) -> str:
    try:
        built = json.loads((reference_dir / "build.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"no build receipt in {reference_dir}: {error}") from error
    if built.get("dataset_id") != dataset_id:
        raise DataError(f"{reference_dir} is a run of {built.get('dataset_id')}, not {dataset_id}")
    output = next(item for item in built["outputs"] if item["path"].endswith(".parquet"))
    parquet = reference_dir / output["path"]
    body = parquet.read_bytes()
    if len(body) != output["bytes"] or sha256(body) != output["sha256"]:
        raise DataError(f"reference Parquet differs from its build receipt: {parquet}")
    return str(parquet).replace("'", "''")


def fred_agreement(connection: Any, reference_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """The 3-month bill rate on the days the table marks as FRED's own value, against FRED's DTB3 as captured."""
    path = _reference_parquet(reference_dir, FRED_TBILL_ID)
    days, differing, missing = connection.execute(f"""
        WITH f AS (SELECT date_utc, discount_rate_pct FROM read_parquet('{path}') WHERE discount_rate_pct IS NOT NULL),
             b AS (SELECT date_utc, rate_annual * 100 AS pct FROM rows WHERE rate_id = 'DTB3' AND source = 'FRED DTB3'
                   AND date_utc <= (SELECT max(date_utc) FROM f))
        SELECT COUNT(f.date_utc), COUNT_IF(abs(b.pct - f.discount_rate_pct) > {FRED_TOLERANCE}), COUNT_IF(f.date_utc IS NULL)
        FROM b LEFT JOIN f ON f.date_utc = b.date_utc""").fetchone()
    summary = {"fred_days": days, "fred_days_differing": differing, "fred_days_missing": missing}
    findings = []
    if not days:
        findings.append("no published DTB3 day is shared with the FRED capture")
    if differing:
        findings.append(f"{differing} of {days} published DTB3 days differ from FRED's value")
    if missing:
        findings.append(f"{missing} days the table marks as FRED DTB3 have no FRED value")
    return summary, findings


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    spec = spec_for(dataset_id)
    query_definition(load_catalog(), dataset_id)
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output),
            "writes": [f"{spec.table}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    spec = spec_for(dataset_id)
    definition = dataset(catalog, dataset_id)
    receipt = read_capture(capture_dir, catalog)
    if receipt["dataset_id"] != dataset_id:
        raise DataError(f"capture belongs to {receipt['dataset_id']}, not {dataset_id}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet_path = temporary / f"{spec.table}.parquet"
        connection = duckdb.connect()
        try:
            load_capture(connection, spec, capture_dir, receipt)
            connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection, spec)
        finally:
            connection.close()
        build_receipt = {
            "schema_version": BUILD_SCHEMA,
            "dataset_id": dataset_id,
            "dataset_schema": definition["fields"],
            "source_capture_id": receipt["capture_id"],
            "completed_at": now(),
            "tool": f"avalanche-research@{__version__}",
            "summary": summary,
            "outputs": [{"path": parquet_path.name, "bytes": parquet_path.stat().st_size,
                         "sha256": sha256(parquet_path.read_bytes())}],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return build_receipt


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    """Capture hashes and query text, repeated keys, the window, positive values, the gaps per token in the summary,
    native AVAX against WAVAX for the price service, and with ``--against`` a built ``allium.prices-hourly`` run the
    exchange price against the service's WAVAX price."""
    catalog = load_catalog()
    receipt = read_capture(capture_dir, catalog)
    spec = spec_for(receipt["dataset_id"])
    if against is not None and spec not in (DEX_PRICES_HOURLY, BENCHMARK_RATES_DAILY):
        raise DataError(f"{spec.dataset_id} has no reference dataset to check against")
    window = receipt["queries"][0]["parameters"]
    checked = ["capture hashes", "query text", "field types", "unique keys", "captured window", "valid values"]
    if spec.step is not None:
        checked.append("gaps in the time grid, reported in the summary")
    connection = duckdb.connect()
    try:
        load_capture(connection, spec, capture_dir, receipt)
        findings = check_counts(connection, spec, window)
        summary = summarize(connection, spec)
        if spec is C_CHAIN_DAILY_LAST_BLOCKS:
            checked.append("each day starts at the height after the previous day's last block")
            if summary["height_breaks"]:
                findings.append(f"{summary['height_breaks']} days do not start at the height after the previous day's last block")
        if spec is PRICES_HOURLY:
            checked.append(f"native AVAX against WAVAX: {PAIR_SHARE:.1%} of shared hours within {PAIR_TOLERANCE:.1%}")
            pair = pair_agreement(connection)
            summary["avax_wavax"] = pair
            if not pair["hours"]:
                findings.append("no hour holds both native AVAX and WAVAX")
            elif pair["share_within"] < PAIR_SHARE:
                findings.append(f"{pair['share_within']:.3%} of {pair['hours']} shared hours price native AVAX within "
                                f"{PAIR_TOLERANCE:.1%} of WAVAX; at least {PAIR_SHARE:.1%} must")
        if against is not None and spec is BENCHMARK_RATES_DAILY:
            checked.append("FRED's DTB3 on every day the table marks as FRED's own value: equal")
            extra, found = fred_agreement(connection, against)
            summary.update(extra)
            findings.extend(found)
        elif against is not None:
            checked.append(f"the price service's WAVAX price at each day's last exchange hour: {DEX_SHARE:.0%} of days within {DEX_TOLERANCE:.0%}")
            extra, found = dex_agreement(connection, against)
            summary.update(extra)
            findings.extend(found)
        if dataset_dir is not None:
            checked.extend(["build hashes", "Parquet rows"])
            try:
                build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
                if build_receipt.get("source_capture_id") != receipt["capture_id"]:
                    findings.append("build does not belong to this capture")
                for item in build_receipt["outputs"]:
                    body = (dataset_dir / item["path"]).read_bytes()
                    if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                        findings.append(f"output hash or size differs: {item['path']}")
                parquet = str(dataset_dir / f"{spec.table}.parquet")
                schema = connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [parquet]).fetchall()
                if [(item[0], item[1]) for item in schema] != list(spec.table_columns.items()):
                    findings.append("Parquet schema differs from the dataset contract")
                else:
                    differing = connection.execute(
                        "SELECT (SELECT COUNT(*) FROM (SELECT * FROM rows EXCEPT ALL SELECT * FROM read_parquet(?)))"
                        " + (SELECT COUNT(*) FROM (SELECT * FROM read_parquet(?) EXCEPT ALL SELECT * FROM rows))",
                        [parquet, parquet]).fetchone()[0]
                    if differing:
                        findings.append("Parquet rows differ from the captured inputs")
            except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
                findings.append(f"invalid dataset output: {error}")
    finally:
        connection.close()
    return {
        "dataset_id": receipt["dataset_id"],
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summary,
        "findings": findings,
    }
