"""The daily market vector: one row per UTC day before the held-back cut of 19 November 2025, with the AVAX close and
its log return, the realised variance of the day's hourly log returns, the Bitcoin log return, and the log of the
day's C-Chain gas burn.

The hourly AVAX price comes from two Allium tables read through the Avalanche Foundation's Snowflake account. From
2022-06-01 01:00 UTC, the first hour of Allium's price service, each hour takes the service's native AVAX price, or its
WAVAX price when the native row is missing. Before that hour it takes Allium's WAVAX price derived from decentralised
exchange trades, which starts on 2021-02-02 15:00 UTC. Both tables stamp a price with the instant it holds at: the
service's price at a stamp agrees with Binance's AVAX/USDT open of the same midnight, and the exchange price agrees
best with the service at the same stamp. So the day's close is the price stamped at the next midnight, 24:00 UTC of
the day, the instant Coin Metrics' Bitcoin reference rate of the same date holds at.

The realised variance of day d is the sum of squared hourly log returns ``ln(p_t / p_{t-1h})`` over the hours t from
d 01:00 to d+1 00:00 UTC, the sum of squared hourly returns of Corsi (2009, https://doi.org/10.1093/jjfinec/nbp001).
A return counts only when both of its hours are priced and come from the same table, so a day with missing hours sums
fewer returns, and ``hourly_returns`` records how many. With all 24 returns from one table the hourly returns sum to
the close-to-close return. The exchange price is smoother than the service's: on the days both are complete the
exchange table's realised variance is lower, so ``dex_realised_variance`` gives that table's figure on every day it
covers, a single-source series across the change of table.

No row is dated on or after the cut, and nothing observed after 2025-11-19 00:00 UTC, the close of 18 November, is
read: the check rebuilds the table from its inputs cut at that instant and requires the same rows.

The check also compares each close with DefiLlama's daily AVAX price at the same midnight, a reference no field reads.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, date, datetime
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

DATASET_ID = "derived.market-daily-vector"
DATASET_IDS = (DATASET_ID,)
SOURCE_ID = "derived"
TABLE = "market-daily-vector"
INPUTS = {
    "prices-hourly": "allium.prices-hourly",
    "dex-prices-hourly": "allium.dex-token-prices-hourly",
    "economy-gas-fees-daily": "af.economy-gas-fees-daily",
    "btc-usd-daily": "coinmetrics.btc-usd-daily",
    "defillama-daily": "defillama.avax-price-daily",
}
# The held-back cut: the table holds only days before it, and reads nothing observed after its first instant.
HELD_BACK_CUT = date(2025, 11, 19)
CUT_SQL = "TIMESTAMP '2025-11-19 00:00:00'"
# The first day the exchange table prices WAVAX, and the first hour of Allium's price service.
FIRST_DAY = date(2021, 2, 2)
SERVICE_START = datetime(2022, 6, 1, 1, tzinfo=UTC)
SERVICE_START_SQL = "TIMESTAMP '2022-06-01 01:00:00'"
NATIVE_AVAX = "0x0000000000000000000000000000000000000000"
WAVAX = "0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7"
SOURCES = ("prices-hourly-avax", "prices-hourly-wavax", "dex-wavax")
# DefiLlama's point must lie within this many seconds of the close instant to be compared.
REFERENCE_WINDOW_SECONDS = 3_600
# Thresholds set after reading the 2026-11-05 capture. Two price services differ by venue and by the minute of the daily
# mark, so equality is not expected. Service days: 95% within 2% and none beyond 10% (observed 99.7% and 4.4%). Exchange
# days carry pool noise: 90% within 2% (observed 94.4%), and their days beyond 10% are listed, not refused. The daily log
# returns over consecutive compared days must correlate at 0.97 or more (observed 0.984), which catches a shifted day.
REFERENCE_BAND = 0.02
REFERENCE_LIMIT = 0.10
SERVICE_SHARE = 0.95
EXCHANGE_SHARE = 0.90
REFERENCE_CORRELATION = 0.97
RETURN_IDENTITY = 1e-9

TABLE_COLUMNS = {
    "date_utc": "DATE",
    "avax_close_usd": "DOUBLE",
    "avax_close_at": "TIMESTAMP",
    "price_source": "VARCHAR",
    "avax_log_return": "DOUBLE",
    "realised_variance": "DOUBLE",
    "hourly_returns": "INTEGER",
    "max_abs_hourly_return": "DOUBLE",
    "dex_realised_variance": "DOUBLE",
    "dex_hourly_returns": "INTEGER",
    "btc_close_usd": "DOUBLE",
    "btc_log_return": "DOUBLE",
    "gas_burn_avax": "DOUBLE",
    "log_gas_burn": "DOUBLE",
}


def _reject(dataset_id: str) -> None:
    if dataset_id != DATASET_ID:
        raise DataError(f"{dataset_id} is not a derived dataset of this module")


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    _reject(dataset_id)
    raise DataError(f"{DATASET_ID} is built with `avalanche data derive`, not fetched")


def capture(dataset_id: str, output: Path, timeout: float = 20, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    return capture_preview(dataset_id, output, parameters)


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    _reject(dataset_id)
    raise DataError(f"{DATASET_ID} is built with `avalanche data derive`, which writes capture and dataset together")


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    return build_preview(dataset_id, capture_dir, output)


def select_inputs(pinned: dict[str, str] | None, root: Path | None) -> list[dict[str, Any]]:
    """The input runs pinned by ``dataset_id=run``, or the newest built run of each."""
    pinned = pinned or {}
    unknown = sorted(set(pinned) - set(INPUTS.values()))
    if unknown:
        raise DataError(f"not an input of {DATASET_ID}: {', '.join(unknown)}")
    selected = []
    for input_id, dataset_id in INPUTS.items():
        run = pinned.get(dataset_id) or datasets.select_run(dataset_id, newest=True, root=root)["run"]
        record = datasets.receipt(dataset_id, run, root)
        parquet = datasets.parquet_path(dataset_id, record["run"], root)
        body = parquet.read_bytes()
        selected.append({
            "input_id": input_id, "dataset_id": dataset_id, "run": record["run"],
            "capture_id": record["capture"]["capture_id"], "contract_sha256": record["capture"].get("contract_sha256"),
            "captured_at": record["capture"].get("completed_at"), "rows": record["build"].get("summary", {}).get("rows"),
            "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet,
        })
    return selected


def _quoted(path: Path) -> str:
    return str(path).replace("'", "''")


def load_inputs(connection: Any, inputs: list[dict[str, Any]]) -> None:
    paths = {item["input_id"]: _quoted(item["path"]) for item in inputs}
    connection.execute(f"CREATE OR REPLACE VIEW in_service AS SELECT address, hour_utc, price_usd FROM read_parquet('{paths['prices-hourly']}')")
    connection.execute(f"CREATE OR REPLACE VIEW in_dex AS SELECT hour_utc, price_usd FROM read_parquet('{paths['dex-prices-hourly']}') WHERE address = '{WAVAX}'")
    connection.execute(f"CREATE OR REPLACE VIEW in_gas AS SELECT date_utc, gas_used_avax FROM read_parquet('{paths['economy-gas-fees-daily']}')")
    connection.execute(f"CREATE OR REPLACE VIEW in_btc AS SELECT observation_date, price_usd, log_return FROM read_parquet('{paths['btc-usd-daily']}')")
    connection.execute(f"CREATE OR REPLACE VIEW in_reference AS SELECT observed_at, observation_date, price_usd FROM read_parquet('{paths['defillama-daily']}')")


def compute(connection: Any, name: str = "vector", cut_inputs: bool = False) -> None:
    """Build the table ``name`` from the input views. With ``cut_inputs`` every input is first cut at the held-back
    instant, hours after 2025-11-19 00:00 and dates from 2025-11-19 dropped, so a rebuild shows what the cut changes."""
    hour_cut = f"WHERE hour_utc <= {CUT_SQL}" if cut_inputs else ""
    date_cut = f"< {CUT_SQL}::DATE" if cut_inputs else "IS NOT NULL"
    connection.execute(f"""
        CREATE OR REPLACE TABLE {name} AS
        WITH service AS (
            SELECT hour_utc,
                   COALESCE(max(price_usd) FILTER (WHERE address = '{NATIVE_AVAX}'), max(price_usd) FILTER (WHERE address = '{WAVAX}')) AS price,
                   CASE WHEN count(*) FILTER (WHERE address = '{NATIVE_AVAX}') > 0 THEN 'prices-hourly-avax' ELSE 'prices-hourly-wavax' END AS source
            FROM (SELECT * FROM in_service {hour_cut}) WHERE address IN ('{NATIVE_AVAX}', '{WAVAX}') AND hour_utc >= {SERVICE_START_SQL}
            GROUP BY hour_utc),
        dex AS (SELECT hour_utc, price_usd AS price, 'dex-wavax' AS source FROM (SELECT * FROM in_dex {hour_cut})),
        hourly AS (SELECT * FROM service UNION ALL SELECT * FROM dex WHERE hour_utc < {SERVICE_START_SQL}),
        returns AS (
            SELECT hour_utc, price, source, (hour_utc - INTERVAL 1 HOUR)::DATE AS day,
                   CASE WHEN lag(hour_utc) OVER w = hour_utc - INTERVAL 1 HOUR
                             AND (lag(source) OVER w = 'dex-wavax') = (source = 'dex-wavax')
                        THEN ln(price / lag(price) OVER w) END AS r
            FROM hourly WINDOW w AS (ORDER BY hour_utc)),
        dex_returns AS (
            SELECT (hour_utc - INTERVAL 1 HOUR)::DATE AS day,
                   CASE WHEN lag(hour_utc) OVER w = hour_utc - INTERVAL 1 HOUR THEN ln(price / lag(price) OVER w) END AS r
            FROM dex WINDOW w AS (ORDER BY hour_utc)),
        days AS (
            SELECT day, arg_max(price, hour_utc) AS close, max(hour_utc) AS close_at, arg_max(source, hour_utc) AS close_source,
                   bool_or(source = 'prices-hourly-wavax') AS wavax_filled,
                   sum(r * r) AS rv, count(r) AS n, max(abs(r)) AS max_abs
            FROM returns GROUP BY day),
        dex_days AS (SELECT day, sum(r * r) AS rv, count(r) AS n FROM dex_returns GROUP BY day),
        calendar AS (SELECT unnest(generate_series(DATE '{FIRST_DAY}', {CUT_SQL}::DATE - INTERVAL 1 DAY, INTERVAL 1 DAY))::DATE AS day),
        joined AS (
            SELECT c.day, d.close, d.close_at,
                   CASE WHEN d.close IS NULL THEN NULL WHEN d.close_source = 'dex-wavax' THEN 'dex-wavax'
                        WHEN d.wavax_filled THEN 'prices-hourly-wavax' ELSE 'prices-hourly-avax' END AS source,
                   d.rv, COALESCE(d.n, 0) AS n, d.max_abs, x.rv AS dex_rv, COALESCE(x.n, 0) AS dex_n
            FROM calendar c LEFT JOIN days d ON d.day = c.day LEFT JOIN dex_days x ON x.day = c.day)
        SELECT j.day::DATE AS date_utc, j.close::DOUBLE AS avax_close_usd, j.close_at::TIMESTAMP AS avax_close_at,
               j.source::VARCHAR AS price_source, ln(j.close / lag(j.close) OVER (ORDER BY j.day))::DOUBLE AS avax_log_return,
               (CASE WHEN j.n > 0 THEN j.rv END)::DOUBLE AS realised_variance, j.n::INTEGER AS hourly_returns,
               j.max_abs::DOUBLE AS max_abs_hourly_return,
               (CASE WHEN j.dex_n > 0 THEN j.dex_rv END)::DOUBLE AS dex_realised_variance, j.dex_n::INTEGER AS dex_hourly_returns,
               b.price_usd::DOUBLE AS btc_close_usd, b.log_return::DOUBLE AS btc_log_return,
               g.gas_used_avax::DOUBLE AS gas_burn_avax, ln(g.gas_used_avax)::DOUBLE AS log_gas_burn
        FROM joined j
        LEFT JOIN (SELECT * FROM in_btc WHERE observation_date {date_cut}) b ON b.observation_date = j.day
        LEFT JOIN (SELECT * FROM in_gas WHERE date_utc {date_cut}) g ON g.date_utc = j.day
        ORDER BY j.day""")


def reference_comparison(connection: Any, name: str = "vector") -> dict[str, Any]:
    """Each close against DefiLlama's price nearest the same midnight: the share of days within 1%, the median and
    largest gap, and the correlation of daily log returns over consecutive compared days, overall and per table."""
    rows = connection.execute(f"""
        WITH r AS (SELECT observation_date, arg_min(price_usd, abs(epoch(observed_at) - epoch(observation_date::TIMESTAMP))) AS price,
                          min(abs(epoch(observed_at) - epoch(observation_date::TIMESTAMP))) AS offset_s
                   FROM in_reference GROUP BY observation_date),
             m AS (SELECT v.date_utc, v.price_source, v.avax_close_usd, r.price AS ref,
                          abs(v.avax_close_usd / r.price - 1) AS gap,
                          ln(v.avax_close_usd / lag(v.avax_close_usd) OVER w) AS ret,
                          ln(r.price / lag(r.price) OVER w) AS ref_ret,
                          date_diff('day', lag(v.date_utc) OVER w, v.date_utc) AS step
                   FROM {name} v JOIN r ON r.observation_date = v.date_utc + INTERVAL 1 DAY
                   WHERE v.avax_close_usd IS NOT NULL AND v.avax_close_at = v.date_utc + INTERVAL 1 DAY AND r.offset_s <= {REFERENCE_WINDOW_SECONDS}
                   WINDOW w AS (ORDER BY v.date_utc))
        SELECT grp, count(*), avg(CASE WHEN gap <= 0.01 THEN 1.0 ELSE 0.0 END), avg(CASE WHEN gap <= {REFERENCE_BAND} THEN 1.0 ELSE 0.0 END),
               median(gap), max(gap), arg_max(date_utc, gap),
               list(strftime(date_utc, '%Y-%m-%d') ORDER BY date_utc) FILTER (WHERE gap > {REFERENCE_LIMIT}),
               corr(ret, ref_ret) FILTER (WHERE step = 1), count(*) FILTER (WHERE step = 1 AND ret IS NOT NULL AND ref_ret IS NOT NULL)
        FROM (SELECT *, 'all' AS grp FROM m
              UNION ALL SELECT *, CASE WHEN price_source = 'dex-wavax' THEN 'exchange' ELSE 'service' END AS grp FROM m)
        GROUP BY grp ORDER BY grp""").fetchall()
    out = {}
    for grp, days, within_1, within_2, median, worst, worst_day, beyond, corr, pairs in rows:
        out[grp] = {"days": days, "share_within_1pct": round(within_1, 6), "share_within_2pct": round(within_2, 6),
                    "median_difference": round(median, 6), "max_difference": round(worst, 6),
                    "max_difference_day": worst_day.isoformat(), "days_beyond_10pct": beyond or [],
                    "return_pairs": pairs, "return_correlation": None if corr is None else round(corr, 6)}
    return out


def summarize(connection: Any, name: str = "vector") -> dict[str, Any]:
    (rows, first, last, priced, full, missing_close, late_close, btc, gas, rv_days) = connection.execute(f"""
        SELECT count(*), min(date_utc), max(date_utc), count(avax_close_usd), count_if(hourly_returns = 24),
               count_if(avax_close_usd IS NULL), count_if(avax_close_at <> date_utc + INTERVAL 1 DAY),
               count(btc_log_return), count(log_gas_burn), count(realised_variance) FROM {name}""").fetchone()
    by_source = dict(connection.execute(
        f"SELECT price_source, count(*) FROM {name} WHERE price_source IS NOT NULL GROUP BY 1 ORDER BY 1").fetchall())
    ratio, overlap = connection.execute(f"""
        SELECT median(dex_realised_variance / realised_variance), count(*) FROM {name}
        WHERE price_source <> 'dex-wavax' AND hourly_returns = 24 AND dex_hourly_returns = 24 AND realised_variance > 0""").fetchone()
    return {
        "rows": rows, "first_day": first.isoformat(), "last_day": last.isoformat(), "held_back_cut": HELD_BACK_CUT.isoformat(),
        "days_with_close": priced, "days_without_close": missing_close, "closes_before_midnight": late_close,
        "days_with_24_hourly_returns": full, "days_with_realised_variance": rv_days, "days_by_price_source": by_source,
        "days_with_btc_return": btc, "days_with_gas_burn": gas,
        "dex_to_service_realised_variance_median_ratio": None if ratio is None else round(ratio, 6),
        "dex_to_service_overlap_days": overlap,
    }


def parameters() -> dict[str, Any]:
    return {
        "held_back_cut": HELD_BACK_CUT.isoformat(),
        "first_day": FIRST_DAY.isoformat(),
        "service_start": SERVICE_START.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "price_rule": "from the service start each hour takes the price service's native AVAX price, or its WAVAX price when native is missing; earlier hours take the exchange-derived WAVAX price",
        "close_rule": "the price stamped at 24:00 UTC of the day, or the day's last priced hour when that stamp is missing",
        "realised_variance_rule": "sum of squared hourly log returns over the hours from 01:00 of the day to 24:00, each return between two consecutive priced hours of the same table",
        "btc_rule": "Coin Metrics PriceUSD of the same date, the reference rate at 24:00 UTC, and its log return on the previous date",
        "gas_rule": "natural log of the day's GAS_USED_AVAX",
        "reference": f"DefiLlama's point nearest the next midnight, within {REFERENCE_WINDOW_SECONDS} seconds",
    }


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    """Build the table into a new run directory holding ``capture/`` and ``dataset/``."""
    _reject(dataset_id)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    inputs = select_inputs(pinned, root)
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
        "parameters": parameters(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "capture").mkdir()
        (temporary / "dataset").mkdir()
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet_path = temporary / "dataset" / f"{TABLE}.parquet"
        connection = duckdb.connect()
        try:
            load_inputs(connection, inputs)
            compute(connection)
            connection.execute("COPY (SELECT * FROM vector ORDER BY date_utc) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection)
            summary["reference"] = reference_comparison(connection)
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


def read_capture(capture_dir: Path) -> dict[str, Any]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"unreadable capture receipt: {error}") from error
    if receipt.get("schema_version") != "derived-capture/v1" or receipt.get("dataset_id") != DATASET_ID:
        raise DataError(f"not a {DATASET_ID} capture: {capture_dir}")
    return receipt


def _differ(connection: Any, left: str, right: str) -> int:
    return connection.execute(
        f"SELECT (SELECT count(*) FROM (SELECT * FROM {left} EXCEPT ALL SELECT * FROM {right}))"
        f" + (SELECT count(*) FROM (SELECT * FROM {right} EXCEPT ALL SELECT * FROM {left}))").fetchone()[0]


def reference_findings(reference: dict[str, Any]) -> list[str]:
    overall = reference.get("all")
    if not overall:
        return ["no close shares a midnight with DefiLlama's daily price"]
    findings = []
    for group, share in (("service", SERVICE_SHARE), ("exchange", EXCHANGE_SHARE)):
        value = reference.get(group)
        if value is None:
            findings.append(f"no {group} close shares a midnight with DefiLlama's daily price")
            continue
        if value["share_within_2pct"] < share:
            findings.append(f"{value['share_within_2pct']:.2%} of {value['days']} {group} closes lie within {REFERENCE_BAND:.0%} of "
                            f"DefiLlama's price at the same midnight; at least {share:.0%} must")
    if reference.get("service", {}).get("days_beyond_10pct"):
        findings.append(f"service closes differ from DefiLlama's by more than {REFERENCE_LIMIT:.0%} on "
                        f"{', '.join(reference['service']['days_beyond_10pct'])}")
    if overall["return_correlation"] is None or overall["return_correlation"] < REFERENCE_CORRELATION:
        findings.append(f"daily log returns correlate at {overall['return_correlation']} with DefiLlama's; "
                        f"at least {REFERENCE_CORRELATION} is required")
    return findings


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """Verify the input runs and the contract, and, given the build: one row per day from the first day to the day
    before the cut, the same rows from a rebuild and from a rebuild with every input cut at the held-back instant, the
    hourly returns of a complete single-table day summing to its close-to-close return, and the closes against
    DefiLlama's daily price."""
    if against is not None:
        raise DataError(f"{DATASET_ID} takes no --against directory; its DefiLlama reference is a recorded input")
    catalog = load_catalog()
    receipt = read_capture(capture_dir)
    findings: list[str] = []
    checked = ["input run hashes", "catalog contract"]
    if receipt.get("contract_sha256") != contract_hash(catalog, DATASET_ID):
        findings.append("catalog contract changed since the capture")
    root_dir = datasets.RUNS if root is None else root
    inputs: list[dict[str, Any]] = []
    for item in receipt.get("inputs", []):
        parquet = root_dir / item["run"] / "dataset" / item["parquet"]
        if not parquet.is_file():
            findings.append(f"input run missing: {item['run']}")
            continue
        body = parquet.read_bytes()
        if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
            findings.append(f"input run differs from the capture receipt: {item['run']}")
        inputs.append({**item, "path": parquet})
    summary: dict[str, Any] = {"inputs": len(receipt.get("inputs", []))}
    if dataset_dir is not None:
        checked.extend(["build hashes", "columns", "one row per day before the cut", "rebuild from inputs",
                        "rebuild from inputs cut at the held-back instant", "hourly returns sum to the daily return",
                        (f"DefiLlama daily price: {SERVICE_SHARE:.0%} of service closes and {EXCHANGE_SHARE:.0%} of exchange "
                         f"closes within {REFERENCE_BAND:.0%}, no service close beyond {REFERENCE_LIMIT:.0%}, "
                         f"return correlation at least {REFERENCE_CORRELATION}")])
        try:
            build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
            if build_receipt.get("source_capture_id") != receipt.get("capture_id"):
                findings.append("build does not belong to this capture")
            for item in build_receipt["outputs"]:
                body = (dataset_dir / item["path"]).read_bytes()
                if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                    findings.append(f"output hash or size differs: {item['path']}")
            connection = duckdb.connect()
            try:
                connection.execute(f"CREATE TABLE built AS SELECT * FROM read_parquet('{_quoted(dataset_dir / f'{TABLE}.parquet')}')")
                described = [(row[0], row[1]) for row in connection.execute("DESCRIBE built").fetchall()]
                declared = [field["name"] for field in dataset(catalog, DATASET_ID)["fields"]]
                if described != list(TABLE_COLUMNS.items()) or [name for name, _ in described] != declared:
                    findings.append("columns differ from the module or the catalog")
                rows, distinct, first, last, late = connection.execute(
                    f"SELECT count(*), count(DISTINCT date_utc), min(date_utc), max(date_utc), count_if(date_utc >= {CUT_SQL}::DATE) FROM built").fetchone()
                expected = (HELD_BACK_CUT - FIRST_DAY).days
                if late:
                    findings.append(f"{late} rows are dated on or after the held-back cut {HELD_BACK_CUT}")
                if rows != distinct or rows != expected or first != FIRST_DAY:
                    findings.append(f"{rows} rows on {distinct} days from {first} to {last}; expected one row per day, {expected} days from {FIRST_DAY}")
                if len(inputs) == len(INPUTS):
                    load_inputs(connection, inputs)
                    compute(connection)
                    differ = _differ(connection, "built", "vector")
                    if differ:
                        findings.append(f"a rebuild from the recorded inputs differs in {differ} rows")
                    sums = connection.execute(f"""
                        WITH r AS (SELECT (hour_utc - INTERVAL 1 HOUR)::DATE AS day, hour_utc, price_usd FROM in_service WHERE address = '{NATIVE_AVAX}'),
                             s AS (SELECT day, sum(ln(price_usd / prev)) AS total, count(*) AS n FROM
                                   (SELECT day, hour_utc, price_usd, lag(price_usd) OVER (ORDER BY hour_utc) AS prev,
                                           lag(hour_utc) OVER (ORDER BY hour_utc) AS prev_at FROM r)
                                   WHERE prev_at = hour_utc - INTERVAL 1 HOUR GROUP BY day)
                        SELECT count(*) FILTER (WHERE abs(s.total - v.avax_log_return) > {RETURN_IDENTITY}), count(*)
                        FROM built v JOIN s ON s.day = v.date_utc
                        WHERE v.hourly_returns = 24 AND s.n = 24 AND v.price_source = 'prices-hourly-avax'
                          AND v.avax_close_at = v.date_utc + INTERVAL 1 DAY""").fetchone()
                    if sums[0]:
                        findings.append(f"on {sums[0]} of {sums[1]} complete native AVAX days the hourly returns do not sum to the daily return")
                    summary["complete_native_days_summed"] = sums[1]
                    compute(connection, "vector_cut", cut_inputs=True)
                    early = _differ(connection, "built", "vector_cut")
                    if early:
                        findings.append(f"{early} rows change when every input is cut at the held-back instant")
                    reference = reference_comparison(connection, "built")
                    summary["reference"] = reference
                    findings.extend(reference_findings(reference))
                summary.update({key: value for key, value in build_receipt.get("summary", {}).items() if key != "reference"})
            finally:
                connection.close()
        except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid dataset output: {error}")
    return {
        "dataset_id": DATASET_ID,
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summary,
        "findings": findings,
    }
