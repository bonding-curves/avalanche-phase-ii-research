"""v0.9: the AVAX price path, security in dollars and the stake-dependent reward, each behind a setting whose default
reproduces v0.8.1.

The reproduction hashes were recorded on branch ``prototype/v0.8.1-supply-cap`` at commit 0284f21 on 2026-10-27, from
three small reference scenarios: the fitted lifecycle with renewals and arrivals, the stake lifecycle of
``test_stake_lifecycle.model_on`` and the delegated lifecycle of ``test_delegated_lifecycle.delegated`` with a flow of
new delegations. The long table's hash leaves out the ``time`` and ``dt`` columns and is taken over the rows in a
fixed order, so it reads every state variable, every float variable and every setting column of every run and day.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cadCAD")
pytest.importorskip("scipy")

from test_delegated_lifecycle import delegated, flowing
from test_fitted_lifecycle import model, path
from test_stake_lifecycle import model_on

from avalanche_research.mechanisms import ChainReward, StakeDependentReward
from avalanche_research.model import kpis
from avalanche_research.model.engine import InvariantError, run
from avalanche_research.model.fitted_blocks import Arrivals, RenewalLogit
from avalanche_research.model.price import (
    PRICE_BOUNDS,
    PRICE_SCENARIOS,
    price_path,
    scenario_price,
)
from avalanche_research.model.response import response_gap_pp
from avalanche_research.model.streams import Streams

AVAX = 10**9
SUPPLY = 465_370_000 * AVAX
START = datetime(2025, 11, 19, 12, tzinfo=UTC)

RECORDED = {
    "fitted": ("88c8bbdc796634fc", "d016bd2b2004f56e3a399502efcf16ebfd603e85904212cdd4ef8db127fbbeb7"),
    "stake": ("62a6e11f79e1b94b", "f00db1205a6b7d5b8bb401400f103c410f27f129fa423ca990fe5a8b4c70ec17"),
    "delegated": ("fa9899b5a83c62cf", "b605be8865300d0131b314071a2131f626acb53c870d345aa248eceb96dafbad"),
}
"""Per reference scenario: the specification hash and the long table's SHA-256 on v0.8.1."""

REFERENCE = {
    "fitted": lambda **extra: model(renewal=RenewalLogit(intercept=0.5), arrivals=Arrivals(mean_per_day=2.0), timesteps=12, runs=2, seed=11, **extra),
    "stake": lambda **extra: model_on(**extra),
    "delegated": lambda **extra: delegated(delegation_flow=flowing(), timesteps=8, **extra),
}

PRICE = {"price0_usd": 14.5, "price_drift_pa": -1.0, "price_volatility_pa": 0.9}


def table_sha256(table: pd.DataFrame) -> str:
    kept = table.drop(columns=[c for c in ("time", "dt") if c in table.columns])
    body = kept.sort_values(["simulation", "run", "timestep", "variable"]).reset_index(drop=True).to_csv(index=False, float_format="%.12g")
    return hashlib.sha256(body.encode()).hexdigest()


# Defaults reproduce v0.8.1.

@pytest.mark.parametrize("name", list(REFERENCE))
def test_the_defaults_reproduce_the_v081_specification_and_table_byte_for_byte(name):
    built = REFERENCE[name]()
    specification, table = RECORDED[name]
    assert built.specification_hash() == specification
    for key in ("yield_gap_at", "price0_usd", "price_drift_pa", "price_volatility_pa"):
        assert key not in built.specification() and key not in built.settings()
    assert table_sha256(run(built)) == table


def test_each_new_setting_enters_the_specification_only_when_set():
    base = REFERENCE["fitted"]()
    assert base.with_settings(yield_gap_at="origin").specification_hash() == base.specification_hash()
    live = base.with_settings(yield_gap_at="live")
    assert live.specification()["yield_gap_at"] == "live" and live.specification_hash() != base.specification_hash()
    priced = base.with_settings(**PRICE)
    assert priced.specification()["price0_usd"] == 14.5 and priced.specification_hash() != base.specification_hash()
    with pytest.raises(ValueError, match="together"):
        base.with_settings(price0_usd=10.0)


def test_the_price_path_leaves_every_other_column_of_the_run_unchanged():
    base, priced = REFERENCE["fitted"](), REFERENCE["fitted"](**PRICE)
    plain, with_price = run(base), run(priced)
    assert "price_usd" not in plain.columns and "price_usd" in with_price.columns
    shared = [c for c in plain.columns if c not in ("price0_usd", "price_drift_pa", "price_volatility_pa", "specification")]
    pd.testing.assert_frame_equal(plain[shared], with_price[shared])


# The stake-dependent reward.

@pytest.mark.parametrize("share", [0.0, 0.2, 0.44, 0.7, 1.0])
def test_the_neutral_setting_is_the_chain_at_every_share_and_duration(share):
    neutral, chain = StakeDependentReward(), ChainReward()
    for days in (2, 14, 30, 90, 365):
        for stake in (2_000 * AVAX, 123_456_789_012, 3_000_000 * AVAX):
            assert neutral.potential_reward_navax(stake, days * 86_400, SUPPLY, START, 2, share) == \
                chain.potential_reward_navax(stake, days * 86_400, SUPPLY, START, 2)
    assert neutral.check(SUPPLY, START) == []


def test_the_rate_pays_the_chain_at_the_reference_share_and_falls_as_the_share_rises():
    rule = StakeDependentReward(elasticity=0.5, reference_share=0.44)
    chain = ChainReward().annual_rate(30, SUPPLY, START)
    assert rule.annual_rate(30, SUPPLY, START, staked_share=0.44) == pytest.approx(chain, rel=1e-9)
    assert rule.annual_rate(30, SUPPLY, START) == pytest.approx(chain, rel=1e-9)
    rates = [rule.annual_rate(30, SUPPLY, START, staked_share=s) for s in (0.2, 0.3, 0.44, 0.6, 0.8, 1.0)]
    assert rates == sorted(rates, reverse=True)
    # Ethereum's shape: half the stake pays the square root of two times the rate.
    assert rule.annual_rate(30, SUPPLY, START, staked_share=0.22) == pytest.approx(chain * 2**0.5, rel=1e-6)
    assert rule.share_multiplier(0.0) == rule.max_multiplier
    assert StakeDependentReward(elasticity=2.0, min_multiplier=0.5).share_multiplier(1.0) == 0.5
    assert rule.check(SUPPLY, START) == [] and rule.curve(SUPPLY, START, staked_share=0.9)["annual_rate"].max() < chain
    with pytest.raises(ValueError, match="within"):
        rule.share_multiplier(1.5)


def test_the_response_gap_prices_a_stake_dependent_design_at_the_days_share():
    rule, menu = StakeDependentReward(elasticity=1.0, reference_share=0.44, acp285=False), ChainReward()
    at_reference = response_gap_pp(rule, menu, START.date(), SUPPLY, 0, staked_share=0.44)
    assert at_reference == pytest.approx(0.0, abs=1e-9)
    assert response_gap_pp(rule, menu, START.date(), SUPPLY, 0, staked_share=0.6) < 0 < response_gap_pp(rule, menu, START.date(), SUPPLY, 0, staked_share=0.3)


def test_in_a_run_the_stake_dependent_rule_mints_less_than_the_chain_once_more_is_staked():
    # Four commitments of 10,000 to 40,000 AVAX on a 1,000,000 AVAX counter: a staked share of at most 0.1 that falls
    # as renewals draw 10,000 AVAX. Against a reference of 0.05 the factor lies in [0.5, 1), against 0.2 above 2.
    shared = {"supply0_navax": 1_000_000 * AVAX, "renewal": RenewalLogit(intercept=20.0), "timesteps": 3, "runs": 1}
    chain = sum(path(run(model(**shared)), "issued_navax"))
    falling = sum(path(run(model(**shared, mechanism=StakeDependentReward(elasticity=1.0, reference_share=0.05, acp285=False))), "issued_navax"))
    generous = sum(path(run(model(**shared, mechanism=StakeDependentReward(elasticity=1.0, reference_share=0.2, acp285=False))), "issued_navax"))
    assert chain > 0 and chain / 2 <= falling < chain < generous


def test_a_live_yield_gap_equals_the_origins_on_day_one_and_then_reads_the_counter():
    base = REFERENCE["fitted"](renewal_response=0.5, entry_response=0.5, mechanism=StakeDependentReward(elasticity=1.0, reference_share=0.1, acp285=False))
    live = base.with_settings(yield_gap_at="live")
    def gaps(table):
        return table[table["run"] == 1].drop_duplicates("timestep").sort_values("timestep")["yield_gap_pp"].tolist()

    origin_gap, live_gap = gaps(run(base)), gaps(run(live))
    assert origin_gap[1] == pytest.approx(live_gap[1])
    assert len(set(np.round(origin_gap[1:], 9))) == 1
    assert live_gap[-1] != pytest.approx(origin_gap[-1])


# The price path.

def test_the_price_path_is_seeded_positive_and_deterministic_without_volatility():
    rng = Streams(seed=3, run=1).generator("price")
    again = Streams(seed=3, run=1).generator("price")
    one, two = price_path(14.5, 0.5, 1.2, 365, rng), price_path(14.5, 0.5, 1.2, 365, again)
    assert np.array_equal(one, two) and (one > 0).all() and len(one) == 365
    other = price_path(14.5, 0.5, 1.2, 365, Streams(seed=3, run=2).generator("price"))
    assert not np.array_equal(one, other)
    flat = price_path(10.0, 0.365, 0.0, 365, rng)
    assert flat[-1] == pytest.approx(10.0 * np.exp(0.365), rel=1e-9)
    with pytest.raises(ValueError, match="positive"):
        price_path(0.0, 0.0, 0.1, 10, rng)


def test_the_scenarios_are_within_the_records_bounds_and_scale_with_strength():
    for state, (drift, volatility) in PRICE_SCENARIOS.items():
        windows = PRICE_BOUNDS["range" if state == "neutral" else state]
        assert windows[0][0] <= drift <= windows[0][1] and windows[1][0] <= volatility <= windows[1][1]
    assert scenario_price("bull", 1.0) == PRICE_SCENARIOS["bull"]
    assert scenario_price("bear", 0.0) == (0.0, PRICE_SCENARIOS["neutral"][1])
    half = scenario_price("bear", 0.5)
    assert half[0] == pytest.approx(PRICE_SCENARIOS["bear"][0] / 2) and PRICE_SCENARIOS["neutral"][1] <= half[1] <= PRICE_SCENARIOS["bear"][1]
    with pytest.raises(ValueError, match="unknown"):
        scenario_price("sideways")


@pytest.mark.parametrize("name", list(REFERENCE))
def test_every_model_carries_the_price_as_a_float_variable_keyed_by_run(name):
    built = REFERENCE[name](**PRICE)
    table = run(built)
    assert "price_usd" in built.float_variables() and built.initial_state()["price_usd"] == 14.5
    by_run = table.drop_duplicates(["run", "timestep"]).pivot(index="timestep", columns="run", values="price_usd")
    assert (by_run > 0).all().all() and by_run.loc[0].tolist() == [14.5, 14.5]
    assert not by_run[1].iloc[1:].equals(by_run[2].iloc[1:])
    # The same seed and run walk the same path under a different reward rule.
    other = run(REFERENCE[name](**PRICE, mechanism=StakeDependentReward(elasticity=0.5)))
    assert other.drop_duplicates(["run", "timestep"])["price_usd"].tolist() == table.drop_duplicates(["run", "timestep"])["price_usd"].tolist()


@pytest.mark.parametrize("drift, volatility", [(-10.0, 3.0), (10.0, 3.0), (-10.0, 0.0), (10.0, 0.0)])
def test_at_the_extremes_the_price_stays_positive_and_finite_and_stake_within_supply(drift, volatility):
    built = model(renewal=RenewalLogit(intercept=20.0), arrivals=Arrivals(mean_per_day=5.0), timesteps=30, runs=1,
                  price0_usd=14.5, price_drift_pa=drift, price_volatility_pa=volatility)
    table = run(built)
    prices = table.drop_duplicates(["run", "timestep"])["price_usd"].to_numpy()
    assert (prices > 0).all() and np.isfinite(prices).all()
    supply, stake = np.array(path(table, "supply_navax")), np.array(path(table, "active_validator_stake_navax"))
    assert (stake <= supply).all()
    assert [name for name, _ in built.invariants()][-1] == "price positive and finite"


def test_the_price_invariant_stops_a_run_whose_price_is_not_positive():
    built = model(timesteps=2, runs=1, **PRICE)
    bad = [("price positive and finite", lambda s: 0.0 < s["price_usd"] < float("inf"))]
    assert all(check({"price_usd": p}) for _, check in bad for p in (1e-300, 1e300))
    assert not any(check({"price_usd": p}) for _, check in bad for p in (0.0, -1.0, float("inf"), float("nan")))
    assert built.invariants()[-1][0] == bad[0][0]


# Security in dollars.

def table(origin, values, before=0):
    length = max(len(v) for v in values.values())
    days = pd.date_range(pd.Timestamp(origin) - pd.Timedelta(before, unit="D"), periods=length, freq="D")
    return pd.DataFrame({name: list(v) + [np.nan] * (length - len(v)) for name, v in values.items()}, index=days)


ORIGIN = datetime(2024, 6, 30).date()


def test_the_cost_of_attack_is_the_fresh_stake_that_reaches_the_share_at_the_horizons_price():
    daily = table(ORIGIN, {"active_validator_stake_navax": [0, 100 * AVAX, 200 * AVAX], "price_usd": [10.0, 20.0, 30.0]})
    # A third: half the honest stake, 100 AVAX at $30. Two thirds: twice it, 400 AVAX at $30.
    assert kpis.cost_of_attack_third_usd(daily, ORIGIN, 2) == pytest.approx(100 * 30.0)
    assert kpis.cost_of_attack_two_thirds_usd(daily, ORIGIN, 2) == pytest.approx(400 * 30.0)
    assert kpis.cost_of_attack_third_usd(daily, ORIGIN, 1) == pytest.approx(50 * 20.0)
    assert kpis.price_usd(daily, ORIGIN, 2) == 30.0
    with_delegations = daily.assign(active_delegated_stake_navax=[0, 0, 100 * AVAX])
    assert kpis.cost_of_attack_third_usd(with_delegations, ORIGIN, 2) == pytest.approx(150 * 30.0)
    assert kpis.security_cover(daily, ORIGIN, 2, 1_500.0) == pytest.approx(2.0)
    with pytest.raises(ValueError, match="secured value"):
        kpis.security_cover(daily, ORIGIN, 2, 0.0)
    with pytest.raises(kpis.MissingColumn):
        kpis.cost_of_attack_third_usd(daily.drop(columns=["price_usd"]), ORIGIN, 2)


def test_the_kpi_table_adds_the_dollar_measures_only_when_the_run_carries_a_price():
    # 365 days before the origin, the origin and 30 days after it, so every trailing measure has its rows.
    n = 396
    base = {"issued_navax": [1] * n, "active_validator_stake_navax": [100] * n, "active_validators": [1] * n,
            "started_stake_navax": [10] * n, "started_stake_days_navax": [300.0] * n, "offered_rate_30d": [0.1] * n,
            "nakamoto_third_nodes": [1] * n, "total_supply_navax": list(range(1_000, 1_000 + n)), "burned_navax": [0] * n}
    options = {"competing_yield": 0.0, "operating_costs": {"zero": 0.0}, "missing": "skip", "starting_supply_navax": 1_000 + 365,
               "burn_navax_per_day": 0.0}
    plain = kpis.kpi_table(table(ORIGIN, base, before=365), ORIGIN, [30], **options)
    assert not set(plain["measure"]) & {"price_usd", "cost_of_attack_third_usd", "cost_of_attack_two_thirds_usd", "security_cover"}
    priced = kpis.kpi_table(table(ORIGIN, {**base, "price_usd": [1.0] * (n - 1) + [4.0]}, before=365), ORIGIN, [30], **options,
                            secured_value_usd=100.0)
    values = priced.set_index("measure")["value"]
    assert values["price_usd"] == 4.0
    assert values["cost_of_attack_third_usd"] == pytest.approx(50 / AVAX * 4.0)
    assert values["cost_of_attack_two_thirds_usd"] == pytest.approx(200 / AVAX * 4.0)
    assert values["security_cover"] == pytest.approx(50 / AVAX * 4.0 / 100.0)
    assert len(priced) == len(plain) + 4


def test_a_priced_runs_daily_table_carries_the_price_the_dollar_measures_read():
    built = REFERENCE["fitted"](**PRICE)
    one = run(built)
    daily = kpis.run_daily_table(one[one["run"] == 1], built.origin)
    assert "price_usd" in daily.columns and daily["price_usd"].iloc[0] == 14.5
    stake = float(daily["active_validator_stake_navax"].iloc[-1]) / AVAX
    assert kpis.cost_of_attack_third_usd(daily, built.origin, 12) == pytest.approx(stake / 2 * float(daily["price_usd"].iloc[-1]))
    assert kpis.security_cover(daily, built.origin, 12, 1e6) == pytest.approx(stake / 2 * float(daily["price_usd"].iloc[-1]) / 1e6)


def test_a_falling_price_lowers_dollar_security_while_the_staked_avax_does_not_change():
    rising = REFERENCE["fitted"](price0_usd=14.5, price_drift_pa=3.0, price_volatility_pa=0.0)
    falling = REFERENCE["fitted"](price0_usd=14.5, price_drift_pa=-3.0, price_volatility_pa=0.0)
    up, down = run(rising), run(falling)
    assert path(up, "active_validator_stake_navax") == path(down, "active_validator_stake_navax")
    up_daily, down_daily = (kpis.run_daily_table(t[t["run"] == 1], rising.origin) for t in (up, down))
    assert kpis.cost_of_attack_third_usd(up_daily, rising.origin, 12) > kpis.cost_of_attack_third_usd(down_daily, rising.origin, 12)
    assert (datetime.combine(rising.origin, datetime.min.time()) + timedelta(days=12)).date() == up_daily.index[-1].date()
