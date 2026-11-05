"""The holder layer: liquid staking, funds, institutional and small operators, and delegators, on the delegated
lifecycle, against simple blocks. Off, the model is the delegated lifecycle exactly. On, each rule moves only what it
should, and the extreme conditions hold: no stock below zero, no outflow past the ladder, every stake within supply."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cadCAD")
pytest.importorskip("scipy")

from test_delegated_lifecycle import (
    DELEGATIONS,
    TERMS,
    final_states,
    flowing,
    validators,
    wide,
)
from test_fitted_lifecycle import path

from avalanche_research.mechanisms import ChainReward
from avalanche_research.model import kpis
from avalanche_research.model.delegated_lifecycle import DelegatedLifecycle
from avalanche_research.model.engine import _plain, run
from avalanche_research.model.fitted_blocks import AVAX, RenewalLogit
from avalanche_research.model.holder_lifecycle import (
    HOLDER_FLOAT_VARIABLES,
    HOLDER_VARIABLES,
    HolderLifecycle,
    HolderStakeLifecycle,
    benqi_stake_per_start,
    fund_table,
)
from avalanche_research.model.parts import holders as h
from avalanche_research.model.parts.holders import (
    FundTable,
    HolderSettings,
    effective_operators,
    fund_days,
    fund_of,
    fund_wanted,
    lst_starts,
    lst_target_next,
    nakamoto_operators,
    operator_weights,
)
from avalanche_research.model.stake_lifecycle import StakeLifecycle

BENQI = pd.DataFrame({"validator": [2, 4]})
FUNDS = fund_table([{"fund": "Fund A", "holdings_navax": 1_000_000 * AVAX, "staked_share": 0.7, "validator_stake_navax": 100_000 * AVAX,
                     "min_days": 15, "max_days": 19}])
FLAT = {"liquid_staking": {"drift_per_day": 0.0, "gap_elasticity_per_day": 0.0}}


def base_inputs(**overrides):
    return validators(**{"open_delegations": DELEGATIONS, "delegation_terms": TERMS, "benqi_validators": BENQI,
                         "delegation_flow": flowing(), **overrides})


def holder_model(holders=None, **overrides):
    return HolderLifecycle(**base_inputs(**overrides), holders=holders)


def stock(table, variable="benqi_delegated_stake_navax", run_=1):
    return np.array(path(table, variable, run_), dtype=float)


def floats(table, column, run_=1):
    """A float variable's path: one column of the long table, one value per timestep."""
    rows = table[table["run"] == run_].groupby("timestep")[column].first().sort_index()
    return rows.to_numpy(dtype=float)


def states_after(model):
    """The state after each day from day 1, as mappings."""
    return [row for _, row in final_states(model).iloc[1:].iterrows()]


def paths_only(table):
    columns = ["run", "timestep", "variable", "value"]
    return table[columns].sort_values(columns).reset_index(drop=True)


# Off: the delegated lifecycle exactly.

def test_the_two_holder_models_sit_on_the_two_delegated_bases():
    assert issubclass(HolderLifecycle, DelegatedLifecycle.__mro__[2]) and issubclass(HolderStakeLifecycle, StakeLifecycle)


def test_off_the_specification_settings_state_variables_and_run_are_the_delegated_lifecycles():
    shared = base_inputs()
    theirs, ours = DelegatedLifecycle(**shared), HolderLifecycle(**shared)
    assert theirs.specification() == ours.specification()
    assert theirs.specification_hash() == ours.specification_hash()
    assert {k: _plain(v) for k, v in theirs.settings().items()} == {k: _plain(v) for k, v in ours.settings().items()}
    assert theirs.state_variables() == ours.state_variables() and theirs.float_variables() == ours.float_variables()
    pd.testing.assert_frame_equal(run(theirs), run(ours))


def test_off_the_holder_inputs_are_left_out_of_the_specification_so_the_hash_is_the_delegated_one():
    plain = DelegatedLifecycle(**base_inputs())
    given = HolderLifecycle(**base_inputs(), fund_holdings=FUNDS, benqi_stake_per_start_navax=25 * AVAX,
                            holder_renewal_large=RenewalLogit(intercept=3.0))
    assert given.specification_hash() == plain.specification_hash()
    assert "fund_holdings" not in given.settings() and "holder_renewal_large" not in given.settings()
    pd.testing.assert_frame_equal(run(plain), run(given))


def test_on_the_specification_carries_the_settings_and_the_inputs_and_the_hash_changes():
    plain = DelegatedLifecycle(**base_inputs())
    on = holder_model(FLAT, fund_holdings=FUNDS, benqi_stake_per_start_navax=25 * AVAX)
    spec = on.specification()
    assert spec["holders"] == FLAT and "fund_holdings" in spec["inputs_sha256"] and spec["benqi_stake_per_start_navax"] == 25 * AVAX
    assert on.specification_hash() != plain.specification_hash()
    assert on.state_variables()[-len(HOLDER_VARIABLES):] == list(HOLDER_VARIABLES)
    assert on.float_variables()[-len(HOLDER_FLOAT_VARIABLES):] == list(HOLDER_FLOAT_VARIABLES)


def test_the_settings_are_checked_section_by_section():
    with pytest.raises(ValueError, match="sections the model does not read"):
        HolderSettings.check({"whales": {}})
    with pytest.raises(ValueError, match="settings the model does not read"):
        HolderSettings.check({"funds": {"leverage": 2}})
    with pytest.raises(ValueError, match=r"holders.liquid_staking.gap_elasticity_per_day must be"):
        HolderSettings.check({"liquid_staking": {"gap_elasticity_per_day": -1}})
    checked = HolderSettings.check({"operators": {"line_avax": 1_000_000}})
    assert checked.large_navax == 1_000_000 * AVAX and checked.delegators["response"] == 0.0
    with pytest.raises(ValueError, match="needs holder_renewal_large"):
        holder_model({"operators": {"line_avax": 1_000_000}})


# Liquid staking: BENQI's stock follows its target and withdraws only by expiry.

def test_flat_liquid_staking_holds_benqis_stock_at_the_origins_level_within_one_start():
    per_start = 25 * AVAX
    on = holder_model(FLAT, benqi_stake_per_start_navax=per_start, timesteps=40, runs=1)
    table = run(on)
    benqi = stock(table)
    assert benqi[0] == 51_000 * AVAX  # the BENQI delegations open at the origin: 1,000 and 50,000 AVAX
    # Each day BENQI restarts what expired, so the stock never falls more than one start below the target.
    assert (benqi >= benqi[0] - per_start).all() and (benqi <= benqi[0]).all()
    assert floats(table, "lst_target_navax")[-1] == pytest.approx(benqi[0])


def test_a_positive_drift_grows_benqis_stock_at_the_drift_and_a_negative_one_shrinks_it_only_by_expiry():
    per_start = 25 * AVAX
    up = run(holder_model({"liquid_staking": {"drift_per_day": 0.02}}, benqi_stake_per_start_navax=per_start, timesteps=30, runs=1))
    grown = stock(up)
    assert grown[-1] > grown[0] * 1.5
    assert floats(up, "lst_target_navax")[-1] == pytest.approx(grown[0] * np.exp(0.02 * 30), rel=1e-6)
    falling = holder_model({"liquid_staking": {"drift_per_day": -0.05}}, benqi_stake_per_start_navax=per_start, timesteps=70, runs=1)
    shrunk = stock(run(falling))
    # The 1,000 AVAX BENQI delegation on validator 2 ends on day 60 and the 50,000 one on validator 4 on day 200, so the
    # stock falls by exactly the first within 70 days and never below the second.
    assert (shrunk >= 50_000 * AVAX).all() and shrunk[-1] == 50_000 * AVAX and shrunk[0] == 51_000 * AVAX
    states = states_after(falling)
    new_benqi = [int(((s["delegation_days_left"] == s["delegation_days"]) & s["delegation_benqi"]).sum()) for s in states]
    assert sum(new_benqi) == 0


def test_the_gap_elasticity_reads_the_reward_rule_against_the_lending_yield_from_the_origins_gap():
    settings = HolderSettings.check({"liquid_staking": {"gap_elasticity_per_day": 1.0, "defi_yield_pp": 2.0}})
    setup = h.HolderSetup(settings, FundTable.from_frame(None, settings), 25 * AVAX, lst_gap0=0.05)
    assert lst_target_next(100.0, 0.05, setup) == pytest.approx(100.0)
    assert lst_target_next(100.0, 0.06, setup) == pytest.approx(100.0 * np.exp(0.01))
    assert lst_target_next(100.0, -1.0, setup) >= 0.0
    assert lst_starts(1_000.0, 900, 25) == 4 and lst_starts(800.0, 900, 25) == 0 and lst_starts(1_000.0, 0, 0) == 0


def test_benqis_new_delegations_take_the_28_day_stake_per_start_not_the_years_draw():
    per_start = 77 * AVAX
    states = states_after(holder_model({"liquid_staking": {"drift_per_day": 0.01}}, benqi_stake_per_start_navax=per_start, timesteps=20, runs=1))
    stakes = np.concatenate([s["delegation_stakes"][(s["delegation_days_left"] == s["delegation_days"]) & s["delegation_benqi"]]
                             for s in states])
    assert len(stakes) and (stakes == per_start).all()


def test_the_other_delegators_flow_moves_with_their_response_and_benqis_count_does_not():
    quiet = holder_model({"delegators": {"response": 0.0}}, benqi_stake_per_start_navax=25 * AVAX, timesteps=20, runs=1,
                         mechanism=ChainReward(), renewal_response=0.0)
    assert quiet._holder_settings.delegators["response"] == 0.0
    # Under the chain's own rule the yield gap is zero, so a response moves nothing.
    keen = holder_model({"delegators": {"response": 1.0}}, benqi_stake_per_start_navax=25 * AVAX, timesteps=20, runs=1)
    pd.testing.assert_frame_equal(paths_only(run(quiet)), paths_only(run(keen)))


def test_benqi_stake_per_start_reads_the_28_days_before_the_origin():
    starts = pd.DataFrame({"start_time": pd.to_datetime(["2025-10-01", "2025-11-01", "2025-11-18", "2025-11-18"]),
                           "benqi": [True, True, True, False], "stake_navax": [1_000, 300, 100, 5_000]})
    assert benqi_stake_per_start(starts, pd.Timestamp("2025-11-18").date()) == 200
    assert benqi_stake_per_start(starts, pd.Timestamp("2025-12-30").date()) == 0
    assert benqi_stake_per_start(None, pd.Timestamp("2025-11-18").date()) == 0


# Funds: holdings move, validators follow the mandate.

def test_a_fund_adds_validators_as_its_holdings_grow_past_the_origins_staked_level():
    funds = FUNDS
    on = holder_model({"funds": {"drift_per_day": 0.05}}, fund_holdings=funds, timesteps=30, runs=1)
    table = run(on)
    count, staked, holdings = stock(table, "etf_validators"), stock(table, "etf_validator_stake_navax"), stock(table, "etf_holdings_navax")
    assert count[0] == 0 and holdings[0] == 1_000_000 * AVAX
    assert holdings[-1] == pytest.approx(1_000_000 * AVAX * np.exp(0.05 * 30), rel=1e-6)
    assert count[-1] >= 3 and (staked == count * 100_000 * AVAX).all()
    # The fund's validators carry its stake, and they count as its own in the state.
    last = final_states(on).iloc[-1]
    mine = fund_of(last["node_key"]) == 0
    assert mine.sum() == count[-1] and (last["stakes"][mine] == 100_000 * AVAX).all()
    assert ((last["days"][mine] >= 15) & (last["days"][mine] <= 19)).all()


def test_a_fund_whose_holdings_fall_drops_its_validators_at_their_ends_and_never_keeps_them_as_returners():
    # A fund whose record carries none of its stake wants seven validators on day one, and as its holdings fall by 5% a
    # day it wants fewer each day: its validators leave at their ends and none becomes a node that may return.
    unstaked = FUNDS.assign(staked0_navax=0)
    falling = holder_model({"funds": {"drift_per_day": -0.05}}, fund_holdings=unstaked, timesteps=60, runs=1)
    table = run(falling)
    count = stock(table, "etf_validators")
    assert count[1] == 7 and count[-1] == 0 and (np.diff(count) <= 0)[1:].all()
    for s in states_after(falling):
        assert (fund_of(s["out_node_key"]) < 0).all()


def test_fund_arithmetic():
    funds = FundTable.from_frame(FUNDS, None)
    assert fund_wanted(np.array([1_000_000 * AVAX]), funds).tolist() == [0]
    assert fund_wanted(np.array([2_000_000 * AVAX]), funds).tolist() == [7]
    assert fund_wanted(np.array([0]), funds).tolist() == [0]
    days = fund_days(np.array([15, 15]), np.array([19, 19]), np.array([0.0, 0.999]))
    assert days.tolist() == [15, 19]
    with pytest.raises(ValueError, match="within the validator bounds"):
        FundTable.from_frame(fund_table([{"fund": "x", "holdings_navax": 1, "staked_share": 0.5, "validator_stake_navax": 1, "min_days": 15, "max_days": 19}]), None)


def test_a_fund_reads_the_price_modules_log_return_when_the_state_carries_it():
    settings = HolderSettings.check({"funds": {"price_elasticity": 0.5}})
    assert h.fund_holdings_next(np.array([100 * AVAX]), 0.2, settings).tolist() == [round(100 * AVAX * np.exp(0.1))]
    assert h.fund_holdings_next(np.array([100 * AVAX]), 0.0, settings).tolist() == [100 * AVAX]


# Operators: the institutional line and its own response.

def test_the_institutional_line_redecides_only_the_large_endings_with_the_large_block():
    big = {"operators": {"line_avax": 30_000, "response_scale": 1.0}}
    never = holder_model(big, holder_renewal_large=RenewalLogit(intercept=-20.0), renewal=RenewalLogit(intercept=20.0), timesteps=25, runs=1)
    always = holder_model(big, holder_renewal_large=RenewalLogit(intercept=20.0), renewal=RenewalLogit(intercept=20.0), timesteps=25, runs=1)
    few, many = stock(run(never), "active_validators"), stock(run(always), "active_validators")
    # The 40,000 and 100,000 AVAX commitments are above the line: with the large block refusing, they leave at their ends
    # while every other commitment renews, so the count with the refusing block is never above the other's.
    assert (many >= few).all() and many[-1] > few[-1]


# Concentration.

def test_operator_weights_merge_a_funds_validators_and_the_measures_read_them():
    keys = np.array([h.fund_node_keys(0, 3, 2)[0], h.fund_node_keys(0, 3, 2)[1], 5, 6])
    own = np.array([100, 100, 100, 100])
    on = np.array([0, 0, 50, 0])
    weights = operator_weights(keys, own, on)
    assert sorted(weights.tolist()) == [100, 150, 200]
    assert nakamoto_operators(weights) == 1 and nakamoto_operators(np.array([1, 1, 1])) == 2 and nakamoto_operators(np.zeros(0)) == 0
    assert effective_operators(np.array([1, 1, 1, 1])) == pytest.approx(4.0) and effective_operators(np.zeros(0)) == 0.0
    assert effective_operators(weights) == pytest.approx(1 / ((200 / 450) ** 2 + (150 / 450) ** 2 + (100 / 450) ** 2))


def test_the_daily_table_and_the_kpi_table_carry_the_three_concentration_measures_only_when_the_run_writes_them():
    on = holder_model(FLAT, benqi_stake_per_start_navax=25 * AVAX, timesteps=31, runs=1)
    table = run(on)
    daily = kpis.run_daily_table(table[table["run"] == 1], on.origin)
    for column in kpis.CONCENTRATION_COLUMNS:
        assert column in daily.columns
    values = kpis.kpi_table(daily, on.origin, [30], competing_yield=0.04, operating_costs={"zero": 0.0}, missing="skip")
    measures = set(values["measure"])
    assert {"liquid_staking_share", "nakamoto_operators", "effective_operators"} <= measures
    share = float(values.loc[values["measure"] == "liquid_staking_share", "value"].iloc[0])
    assert 0.0 < share < 1.0
    off = run(DelegatedLifecycle(**base_inputs(timesteps=31)))
    plain = kpis.kpi_table(kpis.run_daily_table(off[off["run"] == 1], on.origin), on.origin, [30], competing_yield=0.04,
                           operating_costs={"zero": 0.0}, missing="skip")
    assert not ({"liquid_staking_share", "nakamoto_operators", "effective_operators"} & set(plain["measure"]))


# Extreme conditions.

def test_every_holder_stake_stays_within_supply_when_funds_and_liquid_staking_outgrow_it():
    small = 260_000 * AVAX  # a counter the fund's mandate and BENQI's target both outgrow within the run
    on = holder_model({"funds": {"drift_per_day": 0.05}, "liquid_staking": {"drift_per_day": 0.05}}, fund_holdings=FUNDS.assign(staked0_navax=0),
                      benqi_stake_per_start_navax=25 * AVAX, supply0_navax=small, timesteps=40, runs=1)
    long = run(on)
    table = wide(long)
    assert (table["active_validator_stake_navax"] + table["active_delegated_stake_navax"] <= table["supply_navax"]).all()
    assert table["etf_validators"].iloc[-1] >= 1
    assert (floats(long, "lst_target_navax") >= 0).all() and (table["etf_holdings_navax"] >= 0).all()
    # The limit bound: the fund's mandate alone asks for more than the counter holds by the end of the run.
    assert FUNDS["holdings_navax"].iloc[0] * 0.7 * np.exp(0.05 * 40) > small


def test_a_lending_yield_above_the_staking_rate_turns_the_gap_negative_and_the_target_decays_to_zero_not_below():
    settings = HolderSettings.check({"liquid_staking": {"gap_elasticity_per_day": 1.0, "defi_yield_pp": 50.0}})
    when = pd.Timestamp("2026-01-01T12:00Z").to_pydatetime()
    gap = h.lst_gap(ChainReward(), 450_000_000 * AVAX, when, settings)
    assert gap < 0.0
    setup = h.HolderSetup(settings, FundTable.from_frame(None, settings), 25 * AVAX, lst_gap0=0.05)
    target = 1_000.0
    for _ in range(100):
        target = lst_target_next(target, gap, setup)
        assert target >= 0.0
    assert target < 1e-9
