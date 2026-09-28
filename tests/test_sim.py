"""The daily staking model: kernel agreement, zero-change control, invariants, behaviour file, and replay."""

from __future__ import annotations

import json
import time

import duckdb
import numpy as np
import pytest

from avalanche_research.model import protocol
from avalanche_research.sim import (
    backtest,
    engine,
    invariants,
    policies,
    replay,
    scenario,
    state,
)
from avalanche_research.sim.behaviour import BehaviourParams
from avalanche_research.sim.params import Params

NAVAX = 10**9
DAY = 86_400


def kernel_navax(stake_avax: float, days: int, counter_avax: float) -> int:
    return protocol.potential_reward(round(stake_avax * NAVAX), days * DAY, round(counter_avax * NAVAX))


# ---------- kernel ----------

@pytest.mark.parametrize("stake", [2_000.0, 25.0, 135_622.0, 3_000_000.0])
@pytest.mark.parametrize("days", [1, 14, 30, 90, 180, 365])
@pytest.mark.parametrize("counter", [360_000_000.0, 452_707_543.0, 719_000_000.0])
def test_linear_mechanism_equals_protocol_kernel(stake, days, counter):
    context = policies.MechanismContext(params=Params(), supply_counter_avax=counter)
    reward = policies.linear(np.array([stake]), np.array([float(days)]), context)[0]
    assert abs(reward * NAVAX - kernel_navax(stake, days, counter)) <= 1


def test_params_default_to_mainnet():
    params = Params()
    assert (params.min_consumption_rate, params.max_consumption_rate) == (0.10, 0.12)
    assert (params.min_stake_days, params.max_stake_days, params.supply_cap_avax) == (14, 365, 720_000_000)
    assert protocol.max_validator_weight_navax(10_000 * NAVAX) == params.max_weight_factor * 10_000 * NAVAX


def single_validator_state(stake: float, counter: float, supply: float) -> state.State:
    start = state.empty("2025-01-01", (14,), horizon=15)
    start.validator_stake[0, 0] = stake
    start.validator_count[0, 0] = 1
    start.counter_avax = counter
    start.supply_avax = supply
    return start


CONTROL = BehaviourParams(
    entry_base_per_day=0.0, renewal_probability=1.0, delegation_sensitivity=0.0,
    duration_menu_days=(14,), duration_probabilities=(1.0,),
    validator_reward_pass_rate=1.0, delegated_reward_pass_rate=1.0,
)


def test_engine_reward_for_a_single_stake_equals_the_protocol_kernel():
    stake, counter, supply = 10_000.0, 452_707_543.0, 440_770_508.0
    params = Params(behaviour=CONTROL)
    frame = engine.run(params, scenario.constant("flat", 20.0, 0.04, 40), seed=0, days=40,
                       initial_state=single_validator_state(stake, counter, supply), check_invariants=True)
    first = kernel_navax(stake, 14, counter)
    second = kernel_navax(stake, 14, counter + first / NAVAX)
    paid = frame["rewards_paid_avax"].to_numpy()
    assert abs(paid[14] * NAVAX - first) <= 1
    assert abs(paid[28] * NAVAX - second) <= 1
    assert np.count_nonzero(paid) == 2
    assert abs(frame["supply_avax"].iloc[-1] - supply - (first + second) / NAVAX) < 1e-6


# ---------- zero-change control ----------

def test_zero_change_control_keeps_stake_constant_and_pays_kernel_rewards():
    params = Params(behaviour=BehaviourParams(entry_base_per_day=0.0, renewal_probability=1.0, delegation_sensitivity=0.0,
                                              validator_reward_pass_rate=1.0, delegated_reward_pass_rate=1.0))
    frame = engine.run(params, scenario.constant("flat", 20.0, 0.04, 365), seed=3, days=365, check_invariants=True)
    initial = state.SYNTHETIC_2025
    assert np.allclose(frame["validator_stake_avax"], sum(initial["validator_stake_avax"]), rtol=0, atol=1e-4)
    assert np.allclose(frame["delegated_stake_avax"], initial["delegated_stake_avax"], rtol=0, atol=1e-4)
    assert (frame["validator_count"] == sum(initial["validator_count"])).all()
    assert (frame["new_validators"] == 0).all() and (frame["renewed_validators"] == frame["expired_validators"]).all()
    # Every reward paid was reserved in the counter: the counter never moves on payment when all periods pass.
    increase = frame["supply_avax"].iloc[-1] - initial["supply_avax"]
    assert abs(increase - frame["rewards_paid_avax"].sum()) < 1e-3
    assert frame["rewards_paid_avax"].min() > 0
    assert invariants.check_frame(frame, params.supply_cap_avax)["holds"]


# ---------- invariants ----------

def test_invariants_hold_every_step_under_default_behaviour_and_flows():
    behaviour = BehaviourParams(delegation_sensitivity=0.05, entry_spread_elasticity=20.0, renewal_spread_elasticity=10.0,
                                duration_spread_elasticity=5.0)
    params = Params(behaviour=behaviour)
    for seed in range(5):
        frame = engine.run(params, scenario.constant("bull", 40.0, 0.03, 365), seed=seed, days=365, check_invariants=True)
        assert invariants.check_frame(frame, params.supply_cap_avax)["holds"]
        assert (frame["delegated_stake_avax"].diff().iloc[1:] > 0).any()


def test_invariants_hold_when_capacity_binds():
    behaviour = BehaviourParams(delegation_sensitivity=5.0, entry_base_per_day=0.0, renewal_probability=0.5)
    params = Params(behaviour=behaviour)
    frame = engine.run(params, scenario.constant("stress", 10.0, 0.0, 365), seed=1, days=365, check_invariants=True)
    assert frame["delegation_forced_exit_avax"].sum() > 0
    assert (frame["delegated_stake_avax"] <= frame["delegation_capacity_avax"] + 1e-6).all()


def test_supply_never_exceeds_cap_near_the_cap():
    start = single_validator_state(3_000_000.0, 719_999_000.0, 719_990_000.0)
    params = Params(behaviour=CONTROL.replace(entry_base_per_day=50.0, entry_stake_avax=3_000_000.0), max_consumption_rate=1.0, min_consumption_rate=1.0)
    frame = engine.run(params, scenario.constant("flat", 20.0, 0.0, 60), seed=0, days=60, initial_state=start, check_invariants=True)
    assert frame["supply_counter_avax"].max() <= params.supply_cap_avax + 1e-6


def test_check_step_names_the_failing_invariant():
    row = {"day": 0, "supply_avax": 100.0, "supply_counter_avax": 100.0, "rewards_paid_avax": 1.0, "rewards_due_avax": 1.0,
           "validator_stake_avax": 1.0, "delegated_stake_avax": 5.0, "validator_count": 1.0, "delegation_capacity_avax": 4.0}
    with pytest.raises(invariants.InvariantError, match="I4"):
        invariants.check_step(row, 99.0, 720.0)
    with pytest.raises(invariants.InvariantError, match="I2"):
        invariants.check_step({**row, "delegated_stake_avax": 1.0}, 90.0, 720.0)


# ---------- interface ----------

def test_run_returns_the_shared_interface_columns():
    frame = engine.run(Params(), scenario.constant("flat", 20.0, 0.04, 30), seed=0, days=30)
    for column in ("day", "date", "supply_avax", "validator_stake_avax", "delegated_stake_avax", "staking_ratio", "validator_count",
                   "rewards_paid_avax", "reward_apr", "hhi", "net_inflation_annual", "validator_profit_usd_month"):
        assert column in frame.columns
    assert len(frame) == 30 and str(frame["date"].iloc[0]) == "2025-01-01"
    same = engine.run(Params(), scenario.constant("flat", 20.0, 0.04, 30), seed=0, days=30)
    assert frame.drop(columns="date").equals(same.drop(columns="date"))


def test_profit_subtracts_operating_cost():
    base = engine.run(Params(), scenario.constant("flat", 20.0, 0.04, 20), seed=0, days=20)
    costly = engine.run(Params(operating_cost_usd_month=500.0), scenario.constant("flat", 20.0, 0.04, 20), seed=0, days=20)
    assert np.allclose(base["validator_profit_usd_month"] - costly["validator_profit_usd_month"], 500.0)


def test_mechanism_swap_needs_no_engine_change():
    policies.register_mechanism("test-zero", lambda stake, days, context: np.zeros_like(np.asarray(stake, dtype=float)))
    try:
        params = Params(mechanism="test-zero", behaviour=CONTROL)
        start = single_validator_state(10_000.0, 452_707_543.0, 440_770_508.0)
        frame = engine.run(params, scenario.constant("flat", 20.0, 0.04, 30), seed=0, days=30, initial_state=start)
        assert frame["rewards_paid_avax"].sum() == 0 and frame["reward_apr"].max() == 0
    finally:
        policies.REWARD_MECHANISMS.pop("test-zero")
    with pytest.raises(KeyError, match="unknown reward mechanism"):
        engine.run(Params(mechanism="missing"), scenario.constant("flat", 20.0, 0.04, 5), seed=0, days=5)


def test_menu_clips_to_governance_bounds():
    menu, probabilities = policies.effective_menu(BehaviourParams(), 30, 180)
    assert menu.tolist() == [30, 90, 180]
    assert probabilities[0] == pytest.approx(0.6326 + 0.2449) and probabilities.sum() == pytest.approx(1.0)
    frame = engine.run(Params(min_stake_days=30, max_stake_days=180), scenario.constant("flat", 20.0, 0.04, 200), seed=0, days=200,
                       check_invariants=True)
    assert frame.attrs["menu_days"] == [30, 90, 180]


def test_one_trajectory_runs_fast():
    params, flat = Params(), scenario.constant("flat", 20.0, 0.04, 365)
    engine.run(params, flat, seed=0, days=365)
    started = time.perf_counter()
    for seed in range(5):
        engine.run(params, flat, seed=seed, days=365)
    # The target is 50 ms; the bound leaves room for a loaded test machine.
    assert (time.perf_counter() - started) / 5 < 0.25


# ---------- behaviour file ----------

def test_behaviour_from_json(tmp_path):
    document = {
        "version": "v0", "inputs": {"derived.validator-weeks": "validator-weeks-2026-09-27"},
        "fit_window": ["2021-01-04", "2024-12-30"], "holdout_window": ["2025-01-06", "2025-12-29"],
        "validator_entry": {"base_per_day": 6.5, "spread_elasticity": 12.0, "ci95": {}, "identified": True},
        "validator_duration": {"menu_days": [14, 30, 90, 180, 365], "probabilities": [0.6, 0.25, 0.1, 0.03, 0.02],
                               "spread_elasticity": 2.0, "ci95": {}, "identified": False},
        "validator_renewal": {"probability": 0.8, "spread_elasticity": 3.0, "ci95": {}, "identified": True},
        "validator_exit": {"base_per_day": 1.2, "ci95": {}, "identified": True},
        "delegation_flow": {"sensitivity": 0.01, "form": "...", "ci95": {}, "identified": True},
        "delegator_choice": {"coefficients": {"log_net_apy_14d": 1.0}, "se": {}, "strata": {}},
    }
    path = tmp_path / "behaviour-v0.json"
    path.write_text(json.dumps(document))
    behaviour = BehaviourParams.from_json(path, delegation_duration_days=20)
    assert behaviour.version == "v0" and behaviour.entry_base_per_day == 6.5 and behaviour.renewal_probability == 0.8
    assert behaviour.duration_probabilities == (0.6, 0.25, 0.1, 0.03, 0.02) and behaviour.delegation_sensitivity == 0.01
    assert "duration_spread_elasticity" in behaviour.assumptions and "entry_base_per_day" not in behaviour.assumptions
    assert behaviour.delegation_duration_days == 20 and dict(behaviour.identified)["validator_duration"] is False
    engine.run(Params(behaviour=behaviour), scenario.constant("flat", 20.0, 0.04, 30), seed=0, days=30, check_invariants=True)
    hash(Params(behaviour=behaviour))


# ---------- replay ----------

def replay_fixture() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE staking_periods AS SELECT * FROM (VALUES
          ('validator', TIMESTAMP '2025-01-01 00:00:00', TIMESTAMP '2025-01-03 00:00:00', 2000000000000::BIGINT, TIMESTAMP '2025-01-03 00:00:05', 7::BIGINT),
          ('validator', TIMESTAMP '2025-01-01 23:59:59', TIMESTAMP '2025-01-02 23:59:59', 3000000000000::BIGINT, NULL, NULL),
          ('validator', TIMESTAMP '2025-01-02 23:59:59.5', TIMESTAMP '2025-01-04 12:00:00', 5000000000000::BIGINT, TIMESTAMP '2025-01-04 12:00:01', 11::BIGINT),
          ('delegator', TIMESTAMP '2025-01-01 12:00:00', TIMESTAMP '2025-01-02 12:00:00', 25000000000::BIGINT, TIMESTAMP '2025-01-02 12:00:01', 3::BIGINT)
        ) t(role, start_time, end_time, stake_navax, rewarded_at, realized_reward_navax)
    """)
    con.execute("""
        CREATE TABLE avax_monetary_daily AS SELECT * FROM (VALUES
          (DATE '2025-01-01', TRUE,  5000000000000000000000::DECIMAL(38,0), 25000000000000000000::DECIMAL(38,0), 0::DECIMAL(38,0), 2::BIGINT, 1::BIGINT),
          (DATE '2025-01-02', TRUE,  2000000000000000000000::DECIMAL(38,0), 0::DECIMAL(38,0), 3000000000::DECIMAL(38,0), 1::BIGINT, 0::BIGINT),
          (DATE '2025-01-03', TRUE,  5000000000000000000000::DECIMAL(38,0), 0::DECIMAL(38,0), 7000000000::DECIMAL(38,0), 1::BIGINT, 0::BIGINT),
          (DATE '2025-01-04', FALSE, 0::DECIMAL(38,0), 0::DECIMAL(38,0), 99::DECIMAL(38,0), 0::BIGINT, 0::BIGINT)
        ) t(date_utc, complete, active_validator_stake_wei, active_delegated_stake_wei, issued_rewards_wei, active_validators, active_delegations)
    """)
    return con


def test_replay_matches_the_ledger_rule_at_day_boundaries():
    con = replay_fixture()
    frame = replay.replay(con)
    by_date = {str(row.date_utc): row for row in frame.itertuples()}
    # Starts at 23:59:59 count that day; a start half a second later counts the next day; an end at 23:59:59 leaves that day.
    assert by_date["2025-01-01"].active_validator_stake_navax == 5_000 * NAVAX
    assert by_date["2025-01-02"].active_validator_stake_navax == 2_000 * NAVAX
    assert by_date["2025-01-03"].active_validator_stake_navax == 5_000 * NAVAX
    assert by_date["2025-01-04"].rewards_paid_navax == 11
    result = replay.compare(con, frame)
    assert result["exact"] and result["complete_days"] == 3


def test_replay_reports_residuals():
    con = replay_fixture()
    con.execute("UPDATE avax_monetary_daily SET issued_rewards_wei = 4000000000 WHERE date_utc = DATE '2025-01-02'")
    result = replay.compare(con)
    assert not result["exact"]
    assert result["components"]["issued_rewards_wei"] == {"days_differ": 1, "abs_residual_wei": 1_000_000_000, "first_differences": [("2025-01-02", 1_000_000_000)]}


# ---------- built data (skipped without the built runs) ----------

def data_connection():
    try:
        from avalanche_research import datasets
        names = datasets.views()
        if not {"staking_periods", "avax_monetary_daily"} <= set(names):
            pytest.skip("built runs of staking periods and the monetary ledger are not present")
        con = datasets.connect()
    except Exception as error:  # noqa: BLE001 - any missing or unreadable run skips the data tests
        pytest.skip(f"built data unavailable: {error}")
    con.execute("SET memory_limit='5GB'; SET threads=6;")
    return con


@pytest.fixture(scope="module")
def built():
    return data_connection()


def test_replay_equals_the_ledger_on_every_complete_day(built):
    result = replay.compare(built)
    assert result["complete_days"] > 2000
    assert result["exact"], result


def test_observed_state_starts_at_the_ledger_close_and_ages_like_the_data(built):
    start = state.observed_state(built, "2025-01-01")
    close = built.execute("""SELECT active_validator_stake_wei::VARCHAR, active_delegated_stake_wei::VARCHAR, active_validators
                             FROM avax_monetary_daily WHERE date_utc = DATE '2024-12-31'""").fetchone()
    totals = start.totals()
    assert abs(totals["validator_stake_avax"] - int(close[0]) / 10**18) < 1e-6
    assert abs(totals["delegated_stake_avax"] - int(close[1]) / 10**18) < 1e-6
    assert totals["validator_count"] == close[2]
    # With nothing starting, the engine's stake at each close is the stake of the open periods not yet ended.
    frozen = BehaviourParams(entry_base_per_day=0.0, renewal_probability=0.0, delegation_sensitivity=0.0)
    frame = engine.run(Params(behaviour=frozen), scenario.constant("flat", 20.0, 0.04, 60), seed=0, days=60, initial_state=start,
                       check_invariants=True)
    survivors = dict(built.execute("""
        SELECT d.i, sum(p.stake_navax) FILTER (WHERE p.role = 'validator')::BIGINT
        FROM range(60) d(i), staking_periods p
        WHERE p.start_time < TIMESTAMP '2025-01-01' AND p.end_time > TIMESTAMP '2025-01-01' + to_days(d.i::INT) + INTERVAL '23:59:59'
        GROUP BY 1""").fetchall())
    expected = np.array([survivors.get(i, 0) / NAVAX for i in range(60)])
    assert np.allclose(frame["validator_stake_avax"].to_numpy(), expected, rtol=0, atol=1e-5)


def test_observed_scenario_reads_price_and_bill_rate(built):
    observed = scenario.observed(built, "2025-01-01", 365)
    assert observed.days == 365 and (observed.price_usd > 0).all()
    assert 0.02 < observed.external_yield.mean() < 0.06



# ---------- backtest measures ----------

def test_backtest_measures_of_identical_series():
    series = 0.45 + 0.02 * np.sin(np.arange(365) / 20.0)
    measures = backtest.fit_measures(series, series, scale=100.0)
    assert measures["pearson_r"] == pytest.approx(1.0)
    assert measures["rmse"] == 0.0 and measures["direction_accuracy"] == 1.0 and measures["phase_lag_days"] == 0
    assert all(backtest.verdict(measures, 2.0).values())


def test_backtest_phase_lag_finds_a_known_shift():
    rng = np.random.default_rng(1)
    actual = np.cumsum(rng.standard_normal(400))
    simulated = actual[5:370]  # simulated moves 5 days before the actual series
    lag, correlation = backtest.phase_lag(simulated, actual[:365])
    assert lag == 5 and correlation > 0.99


def test_backtest_skips_missing_days():
    actual = np.linspace(0.40, 0.50, 60)
    gapped = actual.copy()
    gapped[10] = np.nan
    measures = backtest.fit_measures(actual + 0.01, gapped, scale=100.0)
    assert measures["days"] == 59 and measures["rmse"] == pytest.approx(1.0)
