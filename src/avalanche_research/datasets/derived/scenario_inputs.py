"""Scenario inputs for revenue-funded rewards: one row per UTC day of the price, the chain's burns and issuance, fees and
revenue, and every competing yield, from the series already captured. A model reads price paths, competing yields and a
revenue path from here instead of from each source.

Burns and issuance come from the monetary ledger, complete days only, in AVAX. Price and its trailing 30-day realized
volatility come from the daily price series, one value a day: the series repeats some dates, and the last observation of
the day is taken. Fees and revenue are DefiLlama's daily Avalanche totals in USD. Each
competing yield is one column, ``yield_<series>_pct``, from the opportunity-cost table. ``burned_total_usd`` is the day's
burn at that day's price. Days before a series starts are null, never filled.
"""

from __future__ import annotations

import duckdb
import pandas as pd

WEI_PER_AVAX = 10**18


def _quoted(path: str) -> str:
    return path.replace("'", "''")


def build(ledger_parquet: str, price_parquet: str, fees_parquet: str, opportunity_parquet: str) -> pd.DataFrame:
    connection = duckdb.connect()
    try:
        series = [row[0] for row in connection.execute(
            f"SELECT DISTINCT series FROM read_parquet('{_quoted(opportunity_parquet)}') ORDER BY 1").fetchall()]
        columns = ", ".join(f"max(rate_pct) FILTER (WHERE series = '{name}') AS yield_{name.replace('-', '_')}_pct" for name in series)
        return connection.execute(f"""
            WITH l AS (
                SELECT date_utc, burned_p_wei::DOUBLE / {WEI_PER_AVAX} AS burned_p_avax, burned_x_wei::DOUBLE / {WEI_PER_AVAX} AS burned_x_avax,
                       burned_c_evm_wei::DOUBLE / {WEI_PER_AVAX} AS burned_c_evm_avax, burned_c_atomic_wei::DOUBLE / {WEI_PER_AVAX} AS burned_c_atomic_avax,
                       burned_wei::DOUBLE / {WEI_PER_AVAX} AS burned_total_avax, issued_rewards_wei::DOUBLE / {WEI_PER_AVAX} AS issued_rewards_avax,
                       total_supply_close_wei::DOUBLE / {WEI_PER_AVAX} AS supply_close_avax
                FROM read_parquet('{_quoted(ledger_parquet)}') WHERE complete),
                 p AS (SELECT observation_date AS date_utc, arg_max(price_usd, observed_at) AS avax_price_usd,
                              arg_max(realized_volatility_30d, observed_at) AS realized_volatility_30d
                       FROM read_parquet('{_quoted(price_parquet)}') WHERE price_usd IS NOT NULL GROUP BY 1),
                 f AS (SELECT date_utc, fees_usd, revenue_usd FROM read_parquet('{_quoted(fees_parquet)}')),
                 y AS (SELECT date_utc, {columns} FROM read_parquet('{_quoted(opportunity_parquet)}') GROUP BY 1)
            SELECT l.*, p.avax_price_usd, p.realized_volatility_30d, l.burned_total_avax * p.avax_price_usd AS burned_total_usd,
                   f.fees_usd, f.revenue_usd, y.* EXCLUDE (date_utc)
            FROM l LEFT JOIN p USING (date_utc) LEFT JOIN f USING (date_utc) LEFT JOIN y USING (date_utc)
            ORDER BY l.date_utc
            """).df()
    finally:
        connection.close()
