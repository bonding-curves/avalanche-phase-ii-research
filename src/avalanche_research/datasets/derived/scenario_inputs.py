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

from ...core.catalog import DataError
from .observed_quotes import select_quotes
from .opportunity import NATIVE_SUPPLY_BASIS

WEI_PER_AVAX = 10**18
LEGACY_PRICE_CLOCK = "legacy-nominal-day/v1"
OBSERVED_CLOSE_CLOCK = "observed-before-daily-close/v1"


def _quoted(path: str) -> str:
    return path.replace("'", "''")


def build(ledger_parquet: str, price_parquet: str, fees_parquet: str, opportunity_parquet: str,
          *, price_clock: str = LEGACY_PRICE_CLOCK) -> pd.DataFrame:
    if price_clock == OBSERVED_CLOSE_CLOCK:
        return _observed_build(ledger_parquet, price_parquet, fees_parquet, opportunity_parquet)
    if price_clock != LEGACY_PRICE_CLOCK:
        raise DataError(f"unsupported scenario price clock: {price_clock}")
    return _legacy_build(ledger_parquet, price_parquet, fees_parquet, opportunity_parquet)


def _legacy_build(ledger_parquet, price_parquet, fees_parquet, opportunity_parquet):
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


def _observed_build(ledger_parquet, price_parquet, fees_parquet, opportunity_parquet):
    # Validate source grain before the legacy pivot can hide a duplicate or a NULL.
    with duckdb.connect(config={"threads": "2", "memory_limit": "2GB", "TimeZone": "UTC"}) as connection:
        columns = {row[0] for row in connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [opportunity_parquet]).fetchall()}
        required = {"date_utc", "series", "rate_pct", "native_supply_basis", "native_quote_at", "native_supply_navax"}
        if not required <= columns:
            raise DataError("observed-close scenarios require qualified opportunity basis/time/supply metadata")
        opportunity = connection.execute("""SELECT date_utc,series,rate_pct,native_supply_basis,native_quote_at,
            native_supply_navax::VARCHAR AS native_supply_navax FROM read_parquet(?)""", [opportunity_parquet]).df()
    opportunity = opportunity.drop_duplicates()
    if opportunity[["date_utc", "series"]].isna().any().any() or opportunity.duplicated(["date_utc", "series"]).any():
        raise DataError("conflicting or unknown opportunity date/series key")
    native = opportunity[opportunity.series.isin(["native-14d", "native-365d"])]
    if native.empty or not native.native_supply_basis.eq(NATIVE_SUPPLY_BASIS).all() or native[["native_quote_at", "native_supply_navax"]].isna().any().any():
        raise DataError("native scenario yields require their declared realised-supply approximation")
    result = _legacy_build(ledger_parquet, price_parquet, fees_parquet, opportunity_parquet)
    days = pd.to_datetime(result.date_utc, utc=True)
    quotes = select_quotes(pd.DataFrame({"quote_key": result.date_utc,
                                        "quote_cutoff_at": days + pd.Timedelta(days=1)}), price_parquet)
    quote_metadata = dict(quotes.attrs)
    quotes = quotes.rename(columns={"quote_key": "date_utc", "quote_cutoff_at": "price_cutoff_at",
                                    "price_usd": "avax_price_usd", "volatility_30d": "realized_volatility_30d"})
    result = result.drop(columns=["avax_price_usd", "realized_volatility_30d", "burned_total_usd"])
    result = result.merge(quotes, on="date_utc", how="left", validate="one_to_one")
    result["burned_total_usd"] = result.burned_total_avax * result.avax_price_usd
    for series in ("native-14d", "native-365d"):
        selected = native[native.series.eq(series)][["date_utc", "native_supply_basis", "native_quote_at", "native_supply_navax"]]
        prefix = "yield_" + series.replace("-", "_")
        selected = selected.rename(columns={field: prefix + "_" + field for field in selected if field != "date_utc"})
        result = result.merge(selected, on="date_utc", how="left", validate="one_to_one")
    result["price_clock"] = OBSERVED_CLOSE_CLOCK
    result.attrs = {"price_clock": OBSERVED_CLOSE_CLOCK, "price_selection": quote_metadata,
                    "use": "Descriptive daily-close projection; not information at the day's opening.",
                    "native_yield_basis": NATIVE_SUPPLY_BASIS,
                    "native_limit": "Kernel quote uses its recorded realised-ledger opening supply, not a verified protocol-counter offer."}
    return result
