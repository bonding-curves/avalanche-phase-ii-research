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


def qualified_yields(path):
    with duckdb.connect() as c:
        frame = c.execute('SELECT * FROM read_parquet(?)', [path]).df()
    from avalanche_research.datasets.derived.opportunity import NATIVE_SUPPLY_BASIS
    extra = pd.DataFrame({'date_utc': pd.to_datetime(['2023-01-01', '2023-01-01']),
                          'series': ['native-14d', 'native-365d'], 'rate_pct': [5.0, 6.0],
                          'native_supply_basis': [NATIVE_SUPPLY_BASIS]*2,
                          'native_quote_at': pd.to_datetime(['2023-01-01', '2023-01-01']),
                          'native_supply_navax': ['450000000000000017']*2})
    frame = pd.concat([frame, extra], ignore_index=True)
    duckdb.from_df(frame).write_parquet(path)


def test_observed_close_keeps_whole_quote_and_native_provenance(tmp_path):
    paths = write(tmp_path); qualified_yields(paths[3])
    quotes = pd.DataFrame({'observation_date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-01']).date,
                          'observed_at': pd.to_datetime(['2023-01-01 20:00', '2023-01-01 23:59', '2023-01-02 00:00']),
                          'price_usd': [10.0, 20.0, 999.0], 'realized_volatility_30d': [0.1, None, 9.9]})
    duckdb.from_df(quotes).write_parquet(paths[1])
    result = scenario_inputs.build(*paths, price_clock=scenario_inputs.OBSERVED_CLOSE_CLOCK)
    first = result.iloc[0]
    assert first.avax_price_usd == 20 and first.burned_total_usd == 60
    assert pd.isna(first.realized_volatility_30d)
    assert first.price_observed_at == pd.Timestamp('2023-01-01 23:59', tz='UTC')
    assert first.yield_native_14d_pct == 5
    assert first.yield_native_14d_native_supply_navax == '450000000000000017'
    assert first.yield_native_14d_native_quote_at == pd.Timestamp('2023-01-01')
    assert result.attrs['use'].startswith('Descriptive')


def test_observed_close_refuses_unqualified_opportunity_source(tmp_path):
    import pytest

    from avalanche_research.core.catalog import DataError
    with pytest.raises(DataError, match='qualified opportunity'):
        scenario_inputs.build(*write(tmp_path), price_clock=scenario_inputs.OBSERVED_CLOSE_CLOCK)
