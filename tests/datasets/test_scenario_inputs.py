"""Scenario inputs join the ledger, price, fees and competing yields by day, with nulls where a series has not started."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from avalanche_research.datasets.derived import scenario_inputs

WEI = 10**18


def write(tmp_path: Path) -> tuple[str, str, str, str]:
    days = pd.date_range("2023-01-01", "2023-01-05", freq="D").date
    paths = {name: str(tmp_path / f"{name}.parquet") for name in ("ledger", "price", "fees", "yields")}
    ledger = pd.DataFrame({"date_utc": days, "burned_p_wei": 1 * WEI, "burned_x_wei": 0, "burned_c_evm_wei": 2 * WEI, "burned_c_atomic_wei": 0,
                           "burned_wei": 3 * WEI, "issued_rewards_wei": 10 * WEI, "total_supply_close_wei": 1000 * WEI,
                           "complete": [True, True, True, True, False]})
    duckdb.from_df(ledger).write_parquet(paths["ledger"])
    price = pd.DataFrame({"observation_date": [days[1], days[1], *days[2:]], "price_usd": [9.0, 10.0, 20.0, 30.0, 40.0],
                          "observed_at": pd.to_datetime(["2023-01-02 00:00", "2023-01-02 23:00", "2023-01-03 00:00", "2023-01-04 00:00", "2023-01-05 00:00"]),
                          "realized_volatility_30d": 0.5})
    duckdb.from_df(price).write_parquet(paths["price"])
    duckdb.from_df(pd.DataFrame({"date_utc": days, "fees_usd": 100.0, "revenue_usd": 50.0})).write_parquet(paths["fees"])
    yields = pd.DataFrame({"date_utc": [days[0], days[0], days[2]], "series": ["tbill-3m", "benqi-avax", "tbill-3m"], "rate_pct": [4.0, 6.0, 4.1]})
    duckdb.from_df(yields).write_parquet(paths["yields"])
    return paths["ledger"], paths["price"], paths["fees"], paths["yields"]


def test_one_row_per_complete_ledger_day_with_each_series_joined_by_day(tmp_path):
    table = scenario_inputs.build(*write(tmp_path)).set_index("date_utc")
    assert len(table) == 4
    first, second = table.iloc[0], table.iloc[1]
    assert pd.isna(first["avax_price_usd"]) and second["avax_price_usd"] == 10.0 and second["burned_total_usd"] == 30.0
    assert first["yield_tbill_3m_pct"] == 4.0 and first["yield_benqi_avax_pct"] == 6.0 and pd.isna(second["yield_tbill_3m_pct"])
    assert first["burned_total_avax"] == 3.0 and first["issued_rewards_avax"] == 10.0 and first["revenue_usd"] == 50.0
