"""Three outside yields by UTC day, each as a decision on that day could read them, before the held-back cut.

A row is dated by the decision day d. Every value in it comes from complete UTC days before d: the raw value is that of
day d-1, which ends at 24:00 UTC of d-1, and the 7-day median is the median of days d-7 to d-1 that have a value, kept
when at least 4 of the 7 do. No row is dated on or after 2025-11-19, and nothing observed after 2025-11-19 00:00 UTC is
read: the check rebuilds the table from its inputs cut at that instant and requires the same rows. All three are in
percent a year.

1. The AVAX lending composite. Each Avalanche lending market for AVAX or WAVAX in ``allium.lending-interest-rates`` that
   records a supply rate and updated on day x gives the mean of its ``supply_apy`` updates that day, weighted by its
   ``supplied_amount`` in AVAX at its last update of the day. Compound v2 forks, BENQI among them, record no supply rate
   and are left out, and their supplied AVAX is reported beside the composite. A day with no rated update takes the
   Aave v3 WAVAX rate of ``derived.aave-wavax-filled``.
2. The liquid staking yield: the sAVAX exchange rate R(x), the ratio of Allium's sAVAX price to its native AVAX price
   (WAVAX where native is missing) stamped at 24:00 UTC of day x in ``allium.prices-hourly``, and its growth over 30
   days as a rate a year, ``((R(x) / R(x-30)) ** (365 / 30) - 1) * 100``.
3. The hedged bill rate: the 3-month bill rate less the annualised AVAX perpetual funding rate. The bill rate of day x
   is the Foundation's DTB3 in ``af.benchmark-rates-daily`` times 100 where the table marks it as FRED's value or
   carried forward from it, and otherwise, before 2024 and on 2024-01-01, which the table fills back from 2 January,
   FRED's last published DTB3 on or before x from ``fred.tbill-3m-daily``. The funding rate of day x is Binance's
   AVAXUSDT mean funding rate per 8-hour event on that UTC date times 3 times 365 times 100, which equals the day's
   summed rate times 365 times 100 when the day holds all three events.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from ...core.catalog import DataError, contract_hash, load_catalog
from . import derived_runs as runs

DATASET_ID = "derived.outside-yields-daily"
DATASET_IDS = (DATASET_ID,)
TABLE = "outside-yields-daily"
INPUTS = {
    "lending-interest-rates": "allium.lending-interest-rates",
    "aave-wavax-filled": "derived.aave-wavax-filled",
    "prices-hourly": "allium.prices-hourly",
    "benchmark-rates-daily": "af.benchmark-rates-daily",
    "tbill-3m-daily": "fred.tbill-3m-daily",
    "binance-funding": "binance.avax-usdt-perp-funding",
}
# The held-back cut: rows are decision days before it, and nothing observed after its first instant is read.
HELD_BACK_CUT = date(2025, 11, 19)
CUT_SQL = "TIMESTAMP '2025-11-19 00:00:00'"
FIRST_DAY = date(2021, 2, 2)
CALENDAR_START = date(2020, 9, 1)
MEDIAN_DAYS = 7
MEDIAN_MIN_DAYS = 4
GROWTH_DAYS = 30
# One thread, so every floating-point sum adds in the same order and a rebuild gives the same bits.
SETTINGS = "SET threads = 1; SET memory_limit = '6GB'"
NATIVE_AVAX = "0x0000000000000000000000000000000000000000"
WAVAX = "0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7"
SAVAX = "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be"

TABLE_COLUMNS = {
    "date_utc": "DATE",
    "lending_pct": "DOUBLE",
    "lending_source": "VARCHAR",
    "lending_markets": "INTEGER",
    "lending_supplied_avax": "DOUBLE",
    "lending_unrated_supplied_avax": "DOUBLE",
    "lending_median_7d_pct": "DOUBLE",
    "lending_days_7d": "INTEGER",
    "savax_exchange_rate": "DOUBLE",
    "savax_growth_30d_pct": "DOUBLE",
    "savax_median_7d_pct": "DOUBLE",
    "savax_days_7d": "INTEGER",
    "bill_pct": "DOUBLE",
    "bill_source": "VARCHAR",
    "funding_pct": "DOUBLE",
    "funding_events": "INTEGER",
    "hedged_bill_pct": "DOUBLE",
    "hedged_median_7d_pct": "DOUBLE",
    "hedged_days_7d": "INTEGER",
}


def _reject(dataset_id: str) -> None:
    if dataset_id != DATASET_ID:
        raise DataError(f"{dataset_id} is not a derived dataset of this module")


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    _reject(dataset_id)
    runs.reject_fetch(DATASET_ID)


def capture(dataset_id: str, output: Path, timeout: float = 20, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    return capture_preview(dataset_id, output, parameters)


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    _reject(dataset_id)
    runs.reject_fetch(DATASET_ID)


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    return build_preview(dataset_id, capture_dir, output)


def load_inputs(connection: Any, inputs: list[dict[str, Any]], cut_inputs: bool = False) -> None:
    """One view per input. With ``cut_inputs`` every input is first cut at the held-back instant."""
    paths = {item["input_id"]: runs.quoted(item["path"]) for item in inputs}
    hour = f"AND hour_utc <= {CUT_SQL}" if cut_inputs else ""
    block = f"AND block_timestamp < {CUT_SQL}" if cut_inputs else ""

    def day(column: str) -> str:
        return f"AND {column} < {CUT_SQL}::DATE" if cut_inputs else ""

    connection.execute(f"""CREATE OR REPLACE VIEW in_lending AS
        SELECT project, protocol, market_address, token_address, block_timestamp, unique_id, supply_apy, supplied_amount
        FROM read_parquet('{paths['lending-interest-rates']}') WHERE upper(token_symbol) IN ('AVAX', 'WAVAX') {block}""")
    connection.execute(f"""CREATE OR REPLACE VIEW in_aave AS SELECT date_utc, rate_pct
        FROM read_parquet('{paths['aave-wavax-filled']}') WHERE rate_pct IS NOT NULL {day('date_utc')}""")
    connection.execute(f"""CREATE OR REPLACE VIEW in_prices AS SELECT address, hour_utc, price_usd
        FROM read_parquet('{paths['prices-hourly']}') WHERE address IN ('{NATIVE_AVAX}', '{WAVAX}', '{SAVAX}') {hour}""")
    connection.execute(f"""CREATE OR REPLACE VIEW in_benchmark AS SELECT date_utc, rate_annual, source
        FROM read_parquet('{paths['benchmark-rates-daily']}') WHERE rate_id = 'DTB3' {day('date_utc')}""")
    connection.execute(f"""CREATE OR REPLACE VIEW in_tbill AS SELECT date_utc, discount_rate_pct
        FROM read_parquet('{paths['tbill-3m-daily']}') WHERE discount_rate_pct IS NOT NULL {day('date_utc')}""")
    connection.execute(f"""CREATE OR REPLACE VIEW in_funding AS SELECT observation_date, funding_rate_per_8h
        FROM read_parquet('{paths['binance-funding']}') WHERE TRUE {day('observation_date')}""")


def compute(connection: Any, name: str = "result") -> None:
    """Daily values by data day x, then one row per decision day d reading days before d."""
    connection.execute(f"""
        CREATE OR REPLACE TABLE {name} AS
        WITH calendar AS (SELECT unnest(generate_series(DATE '{CALENDAR_START}', {CUT_SQL}::DATE - INTERVAL 1 DAY, INTERVAL 1 DAY))::DATE AS day),
        market_days AS (
            SELECT block_timestamp::DATE AS day, project, protocol, market_address, token_address,
                   avg(supply_apy) AS rate, arg_max(supplied_amount, (block_timestamp, unique_id)) AS amount,
                   count(supply_apy) AS rated
            FROM in_lending GROUP BY ALL),
        lending AS (
            SELECT day,
                   sum(rate * amount) FILTER (WHERE rated > 0 AND amount > 0) / sum(amount) FILTER (WHERE rated > 0 AND amount > 0) AS composite,
                   count(*) FILTER (WHERE rated > 0 AND amount > 0) AS markets,
                   sum(amount) FILTER (WHERE rated > 0 AND amount > 0) AS supplied,
                   sum(amount) FILTER (WHERE rated = 0) AS unrated
            FROM market_days GROUP BY day),
        hourly AS (
            SELECT hour_utc,
                   max(price_usd) FILTER (WHERE address = '{SAVAX}') / COALESCE(max(price_usd) FILTER (WHERE address = '{NATIVE_AVAX}'),
                                                                                max(price_usd) FILTER (WHERE address = '{WAVAX}')) AS ratio
            FROM in_prices WHERE hour(hour_utc) = 0 GROUP BY hour_utc),
        bill_af AS (SELECT date_utc, rate_annual * 100 AS pct FROM in_benchmark WHERE source IN ('FRED DTB3', 'FRED DTB3 ffill')),
        bill_fred AS (SELECT c.day, t.discount_rate_pct AS pct FROM calendar c ASOF LEFT JOIN in_tbill t ON c.day >= t.date_utc),
        funding AS (SELECT observation_date AS day, avg(funding_rate_per_8h) * 3 * 365 * 100 AS pct, count(*) AS events
                    FROM in_funding GROUP BY 1),
        daily AS (
            SELECT c.day,
                   COALESCE(l.composite, a.rate_pct) AS lending,
                   CASE WHEN l.composite IS NOT NULL THEN 'allium-composite' WHEN a.rate_pct IS NOT NULL THEN 'aave-wavax-filled' END AS lending_source,
                   CASE WHEN l.composite IS NOT NULL THEN l.markets ELSE 0 END AS markets,
                   l.supplied, COALESCE(l.unrated, 0) AS unrated,
                   h.ratio,
                   COALESCE(b.pct, f.pct) AS bill,
                   CASE WHEN b.pct IS NOT NULL THEN 'af-benchmark' WHEN f.pct IS NOT NULL THEN 'fred-tbill' END AS bill_source,
                   u.pct AS funding, COALESCE(u.events, 0) AS events
            FROM calendar c
            LEFT JOIN lending l ON l.day = c.day
            LEFT JOIN in_aave a ON a.date_utc = c.day
            LEFT JOIN hourly h ON h.hour_utc = c.day + INTERVAL 1 DAY
            LEFT JOIN bill_af b ON b.date_utc = c.day
            LEFT JOIN bill_fred f ON f.day = c.day
            LEFT JOIN funding u ON u.day = c.day),
        derived AS (
            SELECT *, (power(ratio / lag(ratio, {GROWTH_DAYS}) OVER (ORDER BY day), 365.0 / {GROWTH_DAYS}) - 1) * 100 AS growth,
                   bill - funding AS hedged
            FROM daily),
        decided AS (
            SELECT day + INTERVAL 1 DAY AS decision_day, *,
                   median(lending) OVER w AS lending_median, count(lending) OVER w AS lending_days,
                   median(growth) OVER w AS growth_median, count(growth) OVER w AS growth_days,
                   median(hedged) OVER w AS hedged_median, count(hedged) OVER w AS hedged_days
            FROM derived WINDOW w AS (ORDER BY day ROWS BETWEEN {MEDIAN_DAYS - 1} PRECEDING AND CURRENT ROW))
        SELECT decision_day::DATE AS date_utc,
               lending::DOUBLE AS lending_pct, lending_source::VARCHAR AS lending_source, markets::INTEGER AS lending_markets,
               supplied::DOUBLE AS lending_supplied_avax, unrated::DOUBLE AS lending_unrated_supplied_avax,
               (CASE WHEN lending_days >= {MEDIAN_MIN_DAYS} THEN lending_median END)::DOUBLE AS lending_median_7d_pct,
               lending_days::INTEGER AS lending_days_7d,
               ratio::DOUBLE AS savax_exchange_rate, growth::DOUBLE AS savax_growth_30d_pct,
               (CASE WHEN growth_days >= {MEDIAN_MIN_DAYS} THEN growth_median END)::DOUBLE AS savax_median_7d_pct,
               growth_days::INTEGER AS savax_days_7d,
               bill::DOUBLE AS bill_pct, bill_source::VARCHAR AS bill_source, funding::DOUBLE AS funding_pct,
               events::INTEGER AS funding_events, hedged::DOUBLE AS hedged_bill_pct,
               (CASE WHEN hedged_days >= {MEDIAN_MIN_DAYS} THEN hedged_median END)::DOUBLE AS hedged_median_7d_pct,
               hedged_days::INTEGER AS hedged_days_7d
        FROM decided
        WHERE decision_day >= DATE '{FIRST_DAY}' AND decision_day < {CUT_SQL}::DATE
        ORDER BY 1""")


def summarize(connection: Any, table: str = "result") -> dict[str, Any]:
    row = connection.execute(f"""
        SELECT count(*), min(date_utc), max(date_utc),
               count(lending_median_7d_pct), min(date_utc) FILTER (WHERE lending_pct IS NOT NULL),
               count(savax_median_7d_pct), min(date_utc) FILTER (WHERE savax_growth_30d_pct IS NOT NULL),
               count(hedged_median_7d_pct), min(date_utc) FILTER (WHERE hedged_bill_pct IS NOT NULL),
               avg(lending_pct), avg(savax_growth_30d_pct), avg(bill_pct), avg(funding_pct), avg(hedged_bill_pct),
               median(lending_supplied_avax / (lending_supplied_avax + lending_unrated_supplied_avax))
        FROM {table}""").fetchone()
    keys = ("rows", "first_day", "last_day", "lending_median_days", "lending_first_day", "savax_median_days",
            "savax_first_day", "hedged_median_days", "hedged_first_day", "lending_mean_pct", "savax_growth_mean_pct",
            "bill_mean_pct", "funding_mean_pct", "hedged_mean_pct", "lending_rated_share_median")
    summary = {}
    for key, value in zip(keys, row):
        summary[key] = value.isoformat() if isinstance(value, date) else (round(value, 6) if isinstance(value, float) else value)
    for column in ("lending_source", "bill_source"):
        summary[f"days_by_{column}"] = dict(connection.execute(
            f"SELECT COALESCE({column}, 'none'), count(*) FROM {table} GROUP BY 1 ORDER BY 1").fetchall())
    summary["held_back_cut"] = HELD_BACK_CUT.isoformat()
    return summary


def parameters() -> dict[str, Any]:
    return {
        "held_back_cut": HELD_BACK_CUT.isoformat(),
        "first_day": FIRST_DAY.isoformat(),
        "dating": "a row is the decision day d; its raw values are of day d-1 and its medians of days d-7 to d-1",
        "median_days": MEDIAN_DAYS,
        "median_min_days": MEDIAN_MIN_DAYS,
        "lending_rule": "AVAX and WAVAX markets with a supply rate updated on the day: mean supply_apy weighted by supplied_amount at the market's last update of the day; else the filled Aave v3 WAVAX rate",
        "savax_rule": f"sAVAX over native AVAX (else WAVAX) price at the 24:00 UTC stamp, growth over {GROWTH_DAYS} days compounded to a year",
        "bill_rule": "the benchmark table's DTB3 times 100 on its FRED and carried-forward days, otherwise FRED's last published DTB3 on or before the day",
        "funding_rule": "Binance AVAXUSDT mean funding rate per event on the UTC date times 3 times 365 times 100",
    }


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    """Build the table into a new run directory holding ``capture/`` and ``dataset/``."""
    _reject(dataset_id)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    inputs = runs.select_inputs(DATASET_ID, INPUTS, pinned, root)

    def fill(connection: Any) -> None:
        connection.execute(SETTINGS)
        load_inputs(connection, inputs)
        compute(connection)

    return runs.write_run(DATASET_ID, TABLE, output, inputs, parameters(), fill, summarize)


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """Verify the input runs and the contract, and, given the build: one row per decision day from the first day to the
    day before the cut, and the same rows from a rebuild and from a rebuild with every input cut at the held-back instant."""
    if against is not None:
        raise DataError(f"{DATASET_ID} takes no --against directory")
    receipt = runs.read_capture(capture_dir, DATASET_ID)
    findings: list[str] = []
    checked = ["input run hashes", "catalog contract"]
    if receipt.get("contract_sha256") != contract_hash(load_catalog(), DATASET_ID):
        findings.append("catalog contract changed since the capture")
    inputs = runs.verified_inputs(receipt, root, findings)
    summary: dict[str, Any] = {"inputs": len(receipt.get("inputs", []))}
    if dataset_dir is not None:
        checked.extend(["build hashes", "columns", "one row per decision day before the cut", "rebuild from inputs",
                        "rebuild from inputs cut at the held-back instant"])
        connection = duckdb.connect()
        try:
            connection.execute(SETTINGS)
            build_receipt, found = runs.built_findings(connection, DATASET_ID, receipt, dataset_dir, TABLE, TABLE_COLUMNS)
            findings.extend(found)
            rows, distinct, first, late = connection.execute(
                f"SELECT count(*), count(DISTINCT date_utc), min(date_utc), count_if(date_utc >= {CUT_SQL}::DATE) FROM built").fetchone()
            expected = (HELD_BACK_CUT - FIRST_DAY).days
            if late:
                findings.append(f"{late} rows are dated on or after the held-back cut {HELD_BACK_CUT}")
            if rows != distinct or rows != expected or first != FIRST_DAY:
                findings.append(f"{rows} rows on {distinct} days from {first}; expected one row per day, {expected} days from {FIRST_DAY}")
            if len(inputs) == len(INPUTS):
                load_inputs(connection, inputs)
                compute(connection)
                if runs.differ(connection, "built", "result"):
                    findings.append("a rebuild from the recorded inputs differs")
                load_inputs(connection, inputs, cut_inputs=True)
                compute(connection, "result_cut")
                changed = runs.differ(connection, "built", "result_cut")
                if changed:
                    findings.append(f"{changed} rows change when every input is cut at the held-back instant")
            summary.update(build_receipt.get("summary", {}))
        except (OSError, KeyError, TypeError, ValueError, duckdb.Error) as error:
            findings.append(f"invalid dataset output: {error}")
        finally:
            connection.close()
    return {"dataset_id": DATASET_ID, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}
