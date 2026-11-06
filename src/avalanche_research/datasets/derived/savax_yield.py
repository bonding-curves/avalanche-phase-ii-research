"""The liquid staking yield from sAVAX's contract rate, one row per decision day before the held-back cut.

A holder of sAVAX earns the change in the AVAX one sAVAX redeems for, the contract's ``getPooledAvaxByShares(10**18)``,
read at each UTC day's close in ``c-chain-rpc.savax-state-daily``. This table replaces the price ratio as the rate behind
the 30-day liquid staking yield, beside ``derived.outside-yields-daily``, which is unchanged.

A row is dated by the decision day d and reads the day d-1, as ``derived.outside-yields-daily`` does. Its rate R is the
state at day d-1's last block. The yield is the rate's growth over 30 days compounded to a year,
``((R(d-1) / R(d-31)) ** (365 / 30) - 1) * 100``. The 7-day median is the median of the yields of days d-7 to d-1 that
have a value, kept when at least 4 of the 7 do. The market discount is a separate column and not a yield: Allium's
hourly price of sAVAX over that of native AVAX (WAVAX where native is missing) stamped at 24:00 UTC of day d-1, over the
contract rate, less 1, in percent.

No row is dated on or after 2025-11-19, and every state the table reads is at a block whose time is before
2025-11-19 00:00 UTC. The check requires that, one row per decision day, the same rows from a rebuild, and the same rows
from a rebuild with every input cut at that instant. The summary compares the yield with the price-ratio yield of
``derived.outside-yields-daily`` on the decision days both hold.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from ...core.catalog import DataError, contract_hash, load_catalog
from . import derived_runs as runs

DATASET_ID = "derived.savax-yield-daily"
DATASET_IDS = (DATASET_ID,)
TABLE = "savax-yield-daily"
INPUTS = {
    "savax-state-daily": "c-chain-rpc.savax-state-daily",
    "prices-hourly": "allium.prices-hourly",
    "outside-yields-daily": "derived.outside-yields-daily",
}
HELD_BACK_CUT = date(2025, 11, 19)
CUT_SQL = "TIMESTAMP '2025-11-19 00:00:00'"
STATE_START = date(2022, 1, 27)
FIRST_DAY = date(2022, 1, 28)
GROWTH_DAYS = 30
MEDIAN_DAYS = 7
MEDIAN_MIN_DAYS = 4
SETTINGS = "SET threads = 1; SET memory_limit = '6GB'"
NATIVE_AVAX = "0x0000000000000000000000000000000000000000"
WAVAX = "0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7"
SAVAX = "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be"
TABLE_COLUMNS = {
    "date_utc": "DATE",
    "rate_day": "DATE",
    "state_block_timestamp": "TIMESTAMP",
    "avax_per_savax": "DOUBLE",
    "savax_supply": "DOUBLE",
    "savax_growth_30d_pct": "DOUBLE",
    "savax_median_7d_pct": "DOUBLE",
    "savax_days_7d": "INTEGER",
    "price_ratio": "DOUBLE",
    "market_discount_pct": "DOUBLE",
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
    block = f"WHERE block_timestamp < {CUT_SQL}" if cut_inputs else ""
    hour = f"AND hour_utc <= {CUT_SQL}" if cut_inputs else ""
    day = f"WHERE date_utc < {CUT_SQL}::DATE" if cut_inputs else ""
    connection.execute(f"""CREATE OR REPLACE VIEW in_state AS SELECT date_utc, block_timestamp, avax_per_savax, savax_supply
        FROM read_parquet('{paths['savax-state-daily']}') {block}""")
    connection.execute(f"""CREATE OR REPLACE VIEW in_prices AS SELECT address, hour_utc, price_usd
        FROM read_parquet('{paths['prices-hourly']}') WHERE address IN ('{NATIVE_AVAX}', '{WAVAX}', '{SAVAX}') {hour}""")
    connection.execute(f"""CREATE OR REPLACE VIEW in_outside AS SELECT date_utc, savax_growth_30d_pct, savax_median_7d_pct
        FROM read_parquet('{paths['outside-yields-daily']}') {day}""")


def compute(connection: Any, name: str = "result") -> None:
    """The rate and its yield by data day x, then one row per decision day d reading day d-1."""
    connection.execute(f"""
        CREATE OR REPLACE TABLE {name} AS
        WITH calendar AS (SELECT unnest(generate_series(DATE '{STATE_START}', {CUT_SQL}::DATE - INTERVAL 2 DAY, INTERVAL 1 DAY))::DATE AS day),
        hourly AS (
            SELECT hour_utc,
                   max(price_usd) FILTER (WHERE address = '{SAVAX}') / COALESCE(max(price_usd) FILTER (WHERE address = '{NATIVE_AVAX}'),
                                                                                max(price_usd) FILTER (WHERE address = '{WAVAX}')) AS ratio
            FROM in_prices WHERE hour(hour_utc) = 0 GROUP BY hour_utc),
        daily AS (
            SELECT c.day, s.block_timestamp, s.avax_per_savax AS rate, s.savax_supply, h.ratio
            FROM calendar c
            LEFT JOIN in_state s ON s.date_utc = c.day
            LEFT JOIN hourly h ON h.hour_utc = c.day + INTERVAL 1 DAY),
        derived AS (
            SELECT *, (power(rate / lag(rate, {GROWTH_DAYS}) OVER (ORDER BY day), 365.0 / {GROWTH_DAYS}) - 1) * 100 AS growth
            FROM daily),
        decided AS (
            SELECT day + INTERVAL 1 DAY AS decision_day, *, median(growth) OVER w AS growth_median, count(growth) OVER w AS growth_days
            FROM derived WINDOW w AS (ORDER BY day ROWS BETWEEN {MEDIAN_DAYS - 1} PRECEDING AND CURRENT ROW))
        SELECT decision_day::DATE AS date_utc, day::DATE AS rate_day, block_timestamp::TIMESTAMP AS state_block_timestamp,
               rate::DOUBLE AS avax_per_savax, savax_supply::DOUBLE AS savax_supply, growth::DOUBLE AS savax_growth_30d_pct,
               (CASE WHEN growth_days >= {MEDIAN_MIN_DAYS} THEN growth_median END)::DOUBLE AS savax_median_7d_pct,
               growth_days::INTEGER AS savax_days_7d, ratio::DOUBLE AS price_ratio,
               ((ratio / rate - 1) * 100)::DOUBLE AS market_discount_pct
        FROM decided
        WHERE decision_day >= DATE '{FIRST_DAY}' AND decision_day < {CUT_SQL}::DATE
        ORDER BY 1""")


def summarize(connection: Any, table: str = "result") -> dict[str, Any]:
    row = connection.execute(f"""
        SELECT count(*), min(date_utc), max(date_utc), min(date_utc) FILTER (WHERE savax_growth_30d_pct IS NOT NULL),
               min(date_utc) FILTER (WHERE savax_median_7d_pct IS NOT NULL), avg(savax_growth_30d_pct), stddev_samp(savax_growth_30d_pct),
               min(savax_growth_30d_pct), max(savax_growth_30d_pct), count_if(savax_growth_30d_pct < 0), max(state_block_timestamp),
               count(market_discount_pct), median(abs(market_discount_pct)), quantile_cont(abs(market_discount_pct), 0.95),
               max(abs(market_discount_pct)), avg(market_discount_pct)
        FROM {table}""").fetchone()
    keys = ("rows", "first_day", "last_day", "yield_first_day", "median_first_day", "yield_mean_pct", "yield_sd_pct", "yield_min_pct",
            "yield_max_pct", "yield_negative_days", "latest_state_block", "discount_days", "discount_abs_median_pct",
            "discount_abs_p95_pct", "discount_abs_max_pct", "discount_mean_pct")
    summary = {key: (round(value, 6) if isinstance(value, float) else str(value) if value is not None and not isinstance(value, int) else value)
               for key, value in zip(keys, row)}
    shared = connection.execute(f"""
        SELECT count(*), corr(r.savax_growth_30d_pct, o.savax_growth_30d_pct),
               count(r.savax_median_7d_pct) FILTER (WHERE o.savax_median_7d_pct IS NOT NULL),
               corr(r.savax_median_7d_pct, o.savax_median_7d_pct), avg(o.savax_growth_30d_pct), stddev_samp(o.savax_growth_30d_pct),
               min(r.date_utc), avg(r.savax_growth_30d_pct), stddev_samp(r.savax_growth_30d_pct)
        FROM {table} r JOIN in_outside o USING (date_utc)
        WHERE r.savax_growth_30d_pct IS NOT NULL AND o.savax_growth_30d_pct IS NOT NULL""").fetchone()
    summary["against_price_ratio_yield"] = {
        key: (round(value, 6) if isinstance(value, float) else str(value) if value is not None and not isinstance(value, int) else value)
        for key, value in zip(("days", "correlation", "median_days", "median_correlation", "price_ratio_mean_pct", "price_ratio_sd_pct",
                               "first_shared_day", "contract_mean_pct", "contract_sd_pct"), shared)}
    return summary


def parameters() -> dict[str, Any]:
    return {"dating": "a row is the decision day d; its rate is of day d-1 and its median of the yields of days d-7 to d-1",
            "growth_days": GROWTH_DAYS, "median_days": MEDIAN_DAYS, "median_min_days": MEDIAN_MIN_DAYS,
            "rate_rule": "getPooledAvaxByShares(10^18) at the last block of the UTC day, from c-chain-rpc.savax-state-daily",
            "discount_rule": "sAVAX over native AVAX (else WAVAX) price at the 24:00 UTC stamp of day d-1, over the rate, less 1",
            "held_back_cut": "2025-11-19T00:00:00Z"}


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
    """Verify the input runs and the contract, and, given the build: one row per decision day before the cut, every state
    read at a block before the cut, the same rows from a rebuild, and from a rebuild with every input cut at the cut."""
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
        checked.extend(["build hashes", "columns", "one row per decision day before the cut", "every state read before the cut",
                        "rebuild from inputs", "rebuild from inputs cut at the held-back instant"])
        connection = duckdb.connect()
        try:
            connection.execute(SETTINGS)
            build_receipt, found = runs.built_findings(connection, DATASET_ID, receipt, dataset_dir, TABLE, TABLE_COLUMNS)
            findings.extend(found)
            rows, distinct, first, late, late_state, missing_state = connection.execute(f"""
                SELECT count(*), count(DISTINCT date_utc), min(date_utc), count_if(date_utc >= {CUT_SQL}::DATE),
                       count_if(state_block_timestamp >= {CUT_SQL}), count_if(state_block_timestamp IS NULL) FROM built""").fetchone()
            expected = (HELD_BACK_CUT - FIRST_DAY).days
            if late:
                findings.append(f"{late} rows are dated on or after the held-back cut {HELD_BACK_CUT}")
            if late_state:
                findings.append(f"{late_state} rows read a state at a block on or after the held-back instant")
            if missing_state:
                findings.append(f"{missing_state} rows have no contract state for their rate day")
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
