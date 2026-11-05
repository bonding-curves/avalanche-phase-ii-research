"""The Aave v3 WAVAX supply rate by UTC day, DefiLlama's series with its two gaps filled from Allium.

The series ``aave-wavax`` of ``derived.opportunity-costs-daily`` is DefiLlama's pool history of the Aave v3 rate for
lending WAVAX, wrapped AVAX, on the C-Chain, one value a day from 2022-08-08. It has no value from 2024-01-04 to
2024-01-10 or from 2024-10-09 to 2025-03-09. Those days, and only those, take the daily mean of ``supply_apy`` over every
Allium rate update of protocol ``aave_v3`` and token WAVAX in ``allium.lending-interest-rates``, grouped by the update's
UTC date. Both are annual percentage yields in percent of the supplied amount a year. Every day DefiLlama has keeps its
value, and the field ``source`` names the table of each row, so the series changes only where it was empty.

Allium's daily mean and median, and its count of updates, stand beside every row Allium covers, so the agreement of the
two sources can be read on any day. The check measures it on the 60 days both cover around the second gap, 1 September
to 8 October 2024 and 10 to 31 March 2025.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from ...core.catalog import DataError, contract_hash, load_catalog
from . import derived_runs as runs

DATASET_ID = "derived.aave-wavax-filled"
DATASET_IDS = (DATASET_ID,)
TABLE = "aave-wavax-filled"
INPUTS = {
    "opportunity-costs-daily": "derived.opportunity-costs-daily",
    "lending-interest-rates": "allium.lending-interest-rates",
}
SERIES = "aave-wavax"
DEFILLAMA = "defillama.pool-history"
ALLIUM = "allium.lending-interest-rates"
FILL_WINDOWS = ((date(2024, 1, 4), date(2024, 1, 10)), (date(2024, 10, 9), date(2025, 3, 9)))
AGREEMENT_WINDOWS = ((date(2024, 9, 1), date(2024, 10, 8)), (date(2025, 3, 10), date(2025, 3, 31)))
# On the shared days the two sources must agree to a mean absolute difference of 0.10 points and a correlation of 0.95.
# The data steward's review of the same read found 0.037 points and 0.989 over these 60 days.
AGREEMENT_MEAN_ABS = 0.10
AGREEMENT_CORRELATION = 0.95
# One thread, so every floating-point mean adds in the same order and a rebuild gives the same bits.
SETTINGS = "SET threads = 1"

TABLE_COLUMNS = {
    "date_utc": "DATE",
    "rate_pct": "DOUBLE",
    "source": "VARCHAR",
    "defillama_rate_pct": "DOUBLE",
    "allium_mean_pct": "DOUBLE",
    "allium_median_pct": "DOUBLE",
    "allium_updates": "INTEGER",
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


def _windows(windows: tuple[tuple[date, date], ...], column: str) -> str:
    return " OR ".join(f"{column} BETWEEN DATE '{first}' AND DATE '{last}'" for first, last in windows)


def load_inputs(connection: Any, inputs: list[dict[str, Any]]) -> None:
    paths = {item["input_id"]: runs.quoted(item["path"]) for item in inputs}
    connection.execute(f"""CREATE OR REPLACE VIEW in_defillama AS SELECT date_utc, rate_pct
        FROM read_parquet('{paths['opportunity-costs-daily']}') WHERE series = '{SERIES}' AND rate_pct IS NOT NULL""")
    connection.execute(f"""CREATE OR REPLACE VIEW in_allium AS
        SELECT block_timestamp::DATE AS date_utc, avg(supply_apy) AS mean_pct, median(supply_apy) AS median_pct, count(*) AS updates
        FROM read_parquet('{paths['lending-interest-rates']}')
        WHERE protocol = 'aave_v3' AND token_symbol = 'WAVAX' AND supply_apy IS NOT NULL GROUP BY 1""")


def compute(connection: Any) -> None:
    connection.execute(f"""
        CREATE OR REPLACE TABLE result AS
        WITH fill_days AS (SELECT unnest(generate_series(DATE '{FILL_WINDOWS[0][0]}', DATE '{FILL_WINDOWS[-1][1]}', INTERVAL 1 DAY))::DATE AS date_utc),
             days AS (SELECT date_utc FROM in_defillama
                      UNION SELECT date_utc FROM fill_days WHERE {_windows(FILL_WINDOWS, 'date_utc')})
        SELECT d.date_utc::DATE AS date_utc,
               COALESCE(f.rate_pct, CASE WHEN {_windows(FILL_WINDOWS, 'd.date_utc')} THEN a.mean_pct END)::DOUBLE AS rate_pct,
               (CASE WHEN f.rate_pct IS NOT NULL THEN '{DEFILLAMA}'
                     WHEN a.mean_pct IS NOT NULL AND ({_windows(FILL_WINDOWS, 'd.date_utc')}) THEN '{ALLIUM}' END)::VARCHAR AS source,
               f.rate_pct::DOUBLE AS defillama_rate_pct, a.mean_pct::DOUBLE AS allium_mean_pct,
               a.median_pct::DOUBLE AS allium_median_pct, a.updates::INTEGER AS allium_updates
        FROM days d LEFT JOIN in_defillama f ON f.date_utc = d.date_utc LEFT JOIN in_allium a ON a.date_utc = d.date_utc
        ORDER BY d.date_utc""")


def agreement(connection: Any, table: str = "result") -> dict[str, Any]:
    """Allium's daily mean less DefiLlama's value on the shared days around the second gap, and on every shared day."""
    out = {}
    for name, where in (("review_window", _windows(AGREEMENT_WINDOWS, "date_utc")), ("all_shared_days", "TRUE")):
        days, mean, mean_abs, median_abs, worst, worst_day, corr, median_mean_abs = connection.execute(f"""
            SELECT count(*), avg(allium_mean_pct - defillama_rate_pct), avg(abs(allium_mean_pct - defillama_rate_pct)),
                   median(abs(allium_mean_pct - defillama_rate_pct)), max(abs(allium_mean_pct - defillama_rate_pct)),
                   arg_max(date_utc, abs(allium_mean_pct - defillama_rate_pct)), corr(allium_mean_pct, defillama_rate_pct),
                   avg(abs(allium_median_pct - defillama_rate_pct))
            FROM {table} WHERE allium_mean_pct IS NOT NULL AND defillama_rate_pct IS NOT NULL AND ({where})""").fetchone()
        out[name] = {"days": days, "mean_difference_pp": None if mean is None else round(mean, 6),
                     "mean_abs_difference_pp": None if mean_abs is None else round(mean_abs, 6),
                     "median_abs_difference_pp": None if median_abs is None else round(median_abs, 6),
                     "max_abs_difference_pp": None if worst is None else round(worst, 6),
                     "max_abs_difference_day": None if worst_day is None else worst_day.isoformat(),
                     "correlation": None if corr is None else round(corr, 6),
                     "median_mean_abs_difference_pp": None if median_mean_abs is None else round(median_mean_abs, 6)}
    return out


def summarize(connection: Any, table: str = "result") -> dict[str, Any]:
    rows, first, last, filled, unfilled, fill_mean, fill_min, fill_max = connection.execute(f"""
        SELECT count(*), min(date_utc), max(date_utc), count_if(source = '{ALLIUM}'), count_if(rate_pct IS NULL),
               avg(rate_pct) FILTER (WHERE source = '{ALLIUM}'), min(rate_pct) FILTER (WHERE source = '{ALLIUM}'),
               max(rate_pct) FILTER (WHERE source = '{ALLIUM}') FROM {table}""").fetchone()
    windows = {f"{a}/{b}": connection.execute(
        f"SELECT count(*) FILTER (WHERE source = '{ALLIUM}'), (date_diff('day', DATE '{a}', DATE '{b}') + 1) FROM {table}"
        f" WHERE date_utc BETWEEN DATE '{a}' AND DATE '{b}'").fetchone() for a, b in FILL_WINDOWS}
    seams = {}
    for left, right in ((date(2024, 10, 8), date(2024, 10, 9)), (date(2025, 3, 9), date(2025, 3, 10))):
        values = dict(connection.execute(
            f"SELECT date_utc, rate_pct FROM {table} WHERE date_utc IN (DATE '{left}', DATE '{right}')").fetchall())
        seams[f"{left}/{right}"] = [None if values.get(day) is None else round(values[day], 6) for day in (left, right)]
    return {"rows": rows, "first_day": first.isoformat(), "last_day": last.isoformat(), "filled_days": filled,
            "days_without_rate": unfilled,
            "filled_by_window": {key: {"filled": value[0], "days": value[1]} for key, value in windows.items()},
            "fill_mean_pct": None if fill_mean is None else round(fill_mean, 6),
            "fill_min_pct": None if fill_min is None else round(fill_min, 6),
            "fill_max_pct": None if fill_max is None else round(fill_max, 6),
            "seams_pct": seams, "agreement": agreement(connection, table)}


def parameters() -> dict[str, Any]:
    return {
        "series": SERIES,
        "fill_windows": [[first.isoformat(), last.isoformat()] for first, last in FILL_WINDOWS],
        "fill_rule": "on a fill day without a DefiLlama value, the mean of supply_apy over the day's Allium updates of protocol aave_v3 and token_symbol WAVAX, by UTC date of block_timestamp",
        "keep_rule": "every DefiLlama value is kept as it is",
        "agreement_windows": [[first.isoformat(), last.isoformat()] for first, last in AGREEMENT_WINDOWS],
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
    """Verify the input runs and the contract, and, given the build: a rebuild gives the same rows, every DefiLlama day
    keeps its value, every fill day has a value and none lies outside the fill windows, and Allium agrees with DefiLlama
    on the 60 shared days around the second gap."""
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
        checked.extend(["build hashes", "columns", "rebuild from inputs", "every DefiLlama value kept",
                        "every fill day filled, and only fill days", (f"agreement on the shared days: mean absolute difference at most "
                                                                      f"{AGREEMENT_MEAN_ABS} points, correlation at least {AGREEMENT_CORRELATION}")])
        connection = duckdb.connect()
        try:
            connection.execute(SETTINGS)
            build_receipt, found = runs.built_findings(connection, DATASET_ID, receipt, dataset_dir, TABLE, TABLE_COLUMNS)
            findings.extend(found)
            if len(inputs) == len(INPUTS):
                load_inputs(connection, inputs)
                compute(connection)
                if runs.differ(connection, "built", "result"):
                    findings.append("a rebuild from the recorded inputs differs")
                changed, missing = connection.execute(f"""
                    SELECT count_if(b.rate_pct IS DISTINCT FROM f.rate_pct OR b.source IS DISTINCT FROM '{DEFILLAMA}'),
                           count_if(b.date_utc IS NULL)
                    FROM in_defillama f LEFT JOIN built b ON b.date_utc = f.date_utc""").fetchone()
                if changed:
                    findings.append(f"{changed} DefiLlama days changed value or source")
                if missing:
                    findings.append(f"{missing} DefiLlama days are missing")
            unfilled, stray = connection.execute(f"""
                SELECT count_if(rate_pct IS NULL AND ({_windows(FILL_WINDOWS, 'date_utc')})),
                       count_if(source = '{ALLIUM}' AND NOT ({_windows(FILL_WINDOWS, 'date_utc')})) FROM built""").fetchone()
            if unfilled:
                findings.append(f"{unfilled} days in the fill windows have no value")
            if stray:
                findings.append(f"{stray} filled days lie outside the fill windows")
            summary.update(build_receipt.get("summary", {}))
            shared = agreement(connection, "built")["review_window"]
            summary["agreement"] = agreement(connection, "built")
            if not shared["days"]:
                findings.append("no shared day in the review windows")
            elif shared["mean_abs_difference_pp"] > AGREEMENT_MEAN_ABS or (shared["correlation"] or 0) < AGREEMENT_CORRELATION:
                findings.append(f"on {shared['days']} shared days Allium differs from DefiLlama by {shared['mean_abs_difference_pp']} "
                                f"points on average with correlation {shared['correlation']}; at most {AGREEMENT_MEAN_ABS} and "
                                f"at least {AGREEMENT_CORRELATION} are required")
        except (OSError, KeyError, TypeError, ValueError, duckdb.Error) as error:
            findings.append(f"invalid dataset output: {error}")
        finally:
            connection.close()
    return {"dataset_id": DATASET_ID, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}
