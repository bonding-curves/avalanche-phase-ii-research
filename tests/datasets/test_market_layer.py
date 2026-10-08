"""The market layer reads every series strictly before the decision day, and carries the node's previous period."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from avalanche_research.datasets.derived import market_layer

NAVAX = 10**9
SUPPLY = 450_000_000 * NAVAX

# (hash, role, node, validator hash, accepted and start, end, stake AVAX, realized reward AVAX, supply before)
ROWS = [
    ("V1", "validator", "A", None, "2023-01-01 10:00", "2023-03-01 10:00", 2_000, 20, SUPPLY),
    ("V2", "validator", "A", None, "2023-03-01 09:00", "2023-06-01 09:00", 2_020, None, SUPPLY),
    ("V3", "validator", "B", None, "2023-04-24 12:00", "2023-05-30 12:00", 5_000, None, SUPPLY),
    ("D1", "delegator", "A", "V1", "2023-02-01 00:00", "2023-03-02 00:00", 1_000, None, None),
    ("D2", "delegator", "A", "V1", "2023-01-05 00:00", "2023-02-20 00:00", 3_000, None, None),
]


def write(tmp_path: Path) -> tuple[str, str, str, str]:
    frame = pd.DataFrame(ROWS, columns=["transaction_hash", "role", "node_id", "validator_transaction_hash", "start_time", "end_time",
                                        "stake_avax", "reward_avax", "supply_before_navax"])
    frame["start_time"], frame["end_time"] = pd.to_datetime(frame["start_time"]), pd.to_datetime(frame["end_time"])
    frame["accepted_at"] = frame["start_time"]
    frame["last_cycle_end_time"] = pd.NaT
    frame["duration_days"] = (frame["end_time"] - frame["start_time"]).dt.days
    frame["stake_navax"] = frame["stake_avax"].astype("int64") * NAVAX
    frame["realized_reward_navax"] = (frame["reward_avax"] * NAVAX).astype("Int64")
    frame["regime"] = "banff"
    paths = {name: str(tmp_path / f"{name}.parquet") for name in ("periods", "price", "tbill", "ledger")}
    duckdb.from_df(frame.drop(columns=["stake_avax", "reward_avax"])).write_parquet(paths["periods"])
    days = pd.date_range("2022-12-25", "2023-06-01", freq="D")
    price = pd.DataFrame({"observation_date": days.date, "price_usd": range(len(days)), "realized_volatility_30d": 0.5,
                          "observed_at": days + pd.Timedelta(hours=12)})
    early = pd.DataFrame({"observation_date": [pd.Timestamp("2023-02-28").date()], "price_usd": [-1], "realized_volatility_30d": 0.5,
                          "observed_at": [pd.Timestamp("2023-02-28 00:00")]})
    price = pd.concat([price, early], ignore_index=True)
    duckdb.from_df(price).write_parquet(paths["price"])
    tbill = pd.DataFrame({"date_utc": days[::7].date, "discount_rate_pct": 4.0})
    duckdb.from_df(tbill).write_parquet(paths["tbill"])
    ledger = pd.DataFrame({"date_utc": days.date, "active_validator_stake_wei": 2 * 10**26, "active_delegated_stake_wei": 10**26,
                           "total_supply_close_wei": 4 * 10**26, "complete": True})
    duckdb.from_df(ledger).write_parquet(paths["ledger"])
    return paths["periods"], paths["price"], paths["tbill"], paths["ledger"]


def test_every_series_is_read_from_a_day_before_the_decision_day(tmp_path):
    layer = market_layer.build(*write(tmp_path)).set_index("transaction_hash")
    for column in ("price_day", "tbill_day", "ledger_day"):
        assert (layer[column] < layer["accepted_at"].dt.normalize()).all()
    assert layer.loc["V2", "price_day"] == pd.Timestamp("2023-02-28") and layer.loc["V2", "staking_ratio"] == 0.75
    assert layer.loc["V2", "price_usd"] >= 0, "a repeated date takes the day's last observation"


def test_previous_period_delegations_compounding_and_upgrade_crossing(tmp_path):
    layer = market_layer.build(*write(tmp_path)).set_index("transaction_hash")
    assert layer.loc["V2", "prev_transaction_hash"] == "V1" and layer.loc["V2", "prev_delegated_open_navax"] == 1_000 * NAVAX
    assert layer.loc["V2", "prev_delegation_limit_navax"] == 4 * 2_000 * NAVAX
    assert bool(layer.loc["V2", "compounding"]) and not bool(layer.loc["V1", "compounding"])
    assert layer.loc["V3", "upgrade_crossed"] == "cortina" and layer.loc["V1", "upgrade_crossed"] is None
    assert not layer["held_back"].any()


def test_menu_rates_rise_with_duration_under_the_chain_rule(tmp_path):
    layer = market_layer.build(*write(tmp_path))
    rates = layer[[f"rate_{days}d" for days in market_layer.MENU_DAYS]].iloc[0].tolist()
    assert rates == sorted(rates) and 0.03 < rates[0] < rates[-1] < 0.12
