"""Behaviour estimators recover known parameters from simulated data, and the fit measures behave as documented."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import duckdb
import numpy as np
import pandas as pd
import pytest

from avalanche_research.estimation import OUTPUT, _stats, choice, fit, flows, lifecycle
from avalanche_research.model.protocol import annualized_reward_rate
from avalanche_research.model.types import NAVAX_PER_AVAX

SEED = 20260928


def inside(truth: float, interval) -> bool:
    return interval[0] <= truth <= interval[1]


def simulate_choice(rng, beta, weeks=300, offered=40, mean_events=200):
    X = rng.normal(size=(weeks * offered, len(beta)))
    groups = np.repeat(np.arange(weeks), offered)
    y = np.zeros(weeks * offered)
    for week in range(weeks):
        rows = slice(week * offered, (week + 1) * offered)
        utility = X[rows] @ beta
        p = np.exp(utility - utility.max())
        y[rows] = rng.multinomial(rng.poisson(mean_events), p / p.sum())
    return y, X, groups


def test_conditional_logit_equals_poisson_with_week_dummies():
    rng = np.random.default_rng(SEED)
    y, X, groups = simulate_choice(rng, np.array([0.5, -0.4]), weeks=12, offered=8, mean_events=30)
    clogit = choice.fit_conditional_logit(y, X, groups, ("a", "b"))
    dummies = (groups[:, None] == np.arange(12)[None, :]).astype(float)
    poisson = _stats.poisson(y, np.column_stack([X, dummies]), ("a", "b") + tuple(f"w{i}" for i in range(12)))
    np.testing.assert_allclose(clogit.fit.coef, poisson.coef[:2], rtol=1e-6, atol=1e-8)
    np.testing.assert_allclose(clogit.fit.loglik - choice.uniform_loglik(y, groups),
                               choice.conditional_loglik(y, X, groups, clogit.fit.coef) - choice.uniform_loglik(y, groups))


def test_conditional_logit_recovers_parameters_inside_intervals():
    beta = np.array([0.8, -1.5, 0.3])
    y, X, groups = simulate_choice(np.random.default_rng(SEED), beta)
    result = choice.fit_conditional_logit(y, X, groups, ("a", "b", "c"))
    assert result.fit.converged
    for truth, interval in zip(beta, result.fit.ci95):
        assert inside(truth, interval)


def test_conditional_logit_interval_coverage():
    rng = np.random.default_rng(SEED + 1)
    beta = np.array([0.4, -0.7])
    hits = np.zeros(2)
    replications = 100
    for _ in range(replications):
        y, X, groups = simulate_choice(rng, beta, weeks=60, offered=15, mean_events=40)
        ci = choice.fit_conditional_logit(y, X, groups, ("a", "b")).fit.ci95
        hits += (ci[:, 0] <= beta) & (beta <= ci[:, 1])
    assert np.all(hits / replications >= 0.85)


def test_fee_effect_is_the_total_derivative():
    names = choice.FEATURES
    coef = np.array([2.0, -10.0, 0.3, 0.01, -0.02])
    result = choice.fee_effect(_stats.Fit(names, coef, np.eye(5) * 1e-4, 0.0, 1), fees=(0.2,))
    assert result["0.20"]["estimate"] == pytest.approx(-10.0 - 2.0 / 0.8)


def weekly_dates(count: int) -> pd.Series:
    return pd.Series(pd.date_range("2021-01-04", periods=count, freq="7D"))


def ar_spread(rng, count: int, mean=0.05, sd=0.02, rho=0.9) -> np.ndarray:
    values = np.empty(count)
    values[0] = mean
    for t in range(1, count):
        values[t] = mean + rho * (values[t - 1] - mean) + sd * np.sqrt(1 - rho**2) * rng.normal()
    return values


def test_entry_recovers_base_rate_and_elasticity():
    rng = np.random.default_rng(SEED)
    count, base, elasticity = 520, 4.0, 12.0
    spread = ar_spread(rng, count)
    weekly = pd.DataFrame({"week_start_utc": weekly_dates(count), "spread": spread})
    weekly["entries"] = rng.poisson(7 * base * np.exp(elasticity * spread))
    windows = ("2021-01-04", "2029-01-01"), ("2029-01-01", "2031-01-01")
    halves = [("2021-01-04", "2025-01-01"), ("2025-01-01", "2029-01-01")]
    result = lifecycle.fit_entry(weekly, *windows, halves)
    assert inside(base, result["ci95"]["base_per_day"])
    assert inside(elasticity, result["ci95"]["spread_elasticity"])


def test_duration_intervals_cover_the_probabilities_and_elasticity():
    """A single draw misses a 95% interval one time in twenty, so coverage is checked over replications.

    The first version of this test checked one draw and missed the elasticity at 2.0 standard errors. A
    200-replication Monte Carlo at 300 weeks gave a mean estimate of 10.09 and 90% coverage for the current
    spread * days / 365 form, so the clustered interval runs somewhat narrow and the floor here is 0.85.
    """
    rng = np.random.default_rng(SEED)
    count, elasticity, replications = 150, 10.0, 40
    constants = np.array([-0.2, -0.9, -2.3, -2.4])
    truth = lifecycle.duration_probabilities(constants, 0.0, 0.0)
    windows = ("2021-01-04", "2023-11-01"), ("2023-11-01", "2027-01-01")
    halves = [("2021-01-04", "2022-06-01"), ("2022-06-01", "2023-11-01")]
    hits, estimates = np.zeros(1 + len(truth)), []
    for _ in range(replications):
        spread = ar_spread(rng, count)
        market = pd.DataFrame({"week_start_utc": weekly_dates(count), "spread": spread})
        weeks, days = [], []
        for week, s in zip(market["week_start_utc"], spread):
            n = rng.multinomial(rng.poisson(150), lifecycle.duration_probabilities(constants, elasticity, s))
            weeks += [week] * int(n.sum())
            days += list(np.repeat(lifecycle.MENU_DAYS, n))
        periods = pd.DataFrame({"start_week": weeks, "menu_days": days})
        result = lifecycle.fit_duration(periods, market, *windows, halves)
        estimates.append(result["spread_elasticity"])
        hits[0] += inside(elasticity, result["ci95"]["spread_elasticity"])
        hits[1:] += [inside(v, i) for v, i in zip(truth, result["ci95"]["probabilities"])]
    assert np.all(hits / replications >= 0.85)
    assert abs(np.mean(estimates) - elasticity) < 3 * np.std(estimates) / np.sqrt(replications)


def test_renewal_recovers_probability_and_elasticity():
    rng = np.random.default_rng(SEED)
    count, probability, elasticity = 300, 0.8, -6.0
    spread = ar_spread(rng, count)
    market = pd.DataFrame({"week_start_utc": weekly_dates(count), "spread": spread})
    p = 1 / (1 + np.exp(-(np.log(probability / (1 - probability)) + elasticity * spread)))
    sizes = rng.poisson(120, size=count)
    end_week = np.repeat(market["week_start_utc"].to_numpy(), sizes)
    periods = pd.DataFrame({
        "end_week": end_week, "end_time": end_week + np.timedelta64(2, "D"),
        "renewed": rng.random(sizes.sum()) < np.repeat(p, sizes),
    })
    windows = ("2021-01-04", "2025-01-01"), ("2025-01-01", "2027-01-01")
    halves = [("2021-01-04", "2023-01-01"), ("2023-01-01", "2025-01-01")]
    result = lifecycle.fit_renewal(periods, market, *windows, halves)
    assert inside(probability, result["ci95"]["probability"])
    assert inside(elasticity, result["ci95"]["spread_elasticity"])


def test_flow_recovers_sensitivity_with_autocorrelated_noise():
    rng = np.random.default_rng(SEED)
    count, sensitivity = 520, 0.05
    spread = ar_spread(rng, count, mean=0.02, sd=0.03)
    noise = ar_spread(rng, count, mean=0.0, sd=0.002, rho=0.5)
    unstaked = np.full(count, 2.0e8)
    frame = pd.DataFrame({
        "week_start_utc": weekly_dates(count), "spread": spread, "unstaked_supply_avax": unstaked,
        "net_flow_all_avax": (sensitivity * np.tanh(spread) + noise) * unstaked,
    })
    windows = ("2021-01-04", "2029-01-01"), ("2029-01-01", "2031-01-01")
    halves = [("2021-01-04", "2025-01-01"), ("2025-01-01", "2029-01-01")]
    result = flows.fit_flow(frame, "net_flow_all_avax", *windows, halves)
    assert inside(sensitivity, result["ci95"])


def test_menu_bins_follow_the_stated_edges():
    days = [14, 21, 21.001, 45, 45.5, 120, 121, 240, 240.01, 365]
    assert list(lifecycle.menu_bin(days)) == [14, 14, 30, 30, 90, 90, 180, 180, 365, 365]


def test_validator_periods_classify_entries_renewals_and_returns():
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE staking_periods AS SELECT * FROM (VALUES
          ('P1', 'validator', 'A', TIMESTAMP '2022-01-03', TIMESTAMP '2022-01-17'),
          ('P2', 'validator', 'A', TIMESTAMP '2022-01-20', TIMESTAMP '2022-03-01'),
          ('P3', 'validator', 'A', TIMESTAMP '2022-03-09', TIMESTAMP '2022-04-01'),
          ('P4', 'validator', 'B', TIMESTAMP '2022-01-05', TIMESTAMP '2022-02-05'),
          ('D1', 'delegator', 'B', TIMESTAMP '2022-01-06', TIMESTAMP '2022-01-20')
        ) t(transaction_hash, role, node_id, start_time, end_time)
    """)
    periods = lifecycle.validator_periods(con).set_index("transaction_hash")
    assert list(periods.index) == ["P1", "P4", "P2", "P3"]
    assert periods.loc["P1", "kind"] == "first" and periods.loc["P1", "renewed"]
    assert periods.loc["P2", "kind"] == "renewal" and not periods.loc["P2", "renewed"]
    assert periods.loc["P3", "kind"] == "return" and periods.loc["P3", "entry"]
    assert periods.loc["P4", "kind"] == "first" and not periods.loc["P4", "renewed"]
    assert periods.loc["P2", "menu_days"] == 30


def test_market_frame_uses_the_bill_before_the_cutoff_as_a_fraction():
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE market_weeks AS SELECT TIMESTAMP '2023-09-18' AS week_start_utc, 4.3e8 AS total_supply_avax,
          2.4e8 AS unstaked_supply_avax, 3.0e7 AS active_delegated_stake_avax, 1000 AS validators_active,
          10.0 AS price_usdt, 0.5 AS volatility_30d
    """)
    con.execute("CREATE TABLE validator_weeks AS SELECT TIMESTAMP '2023-09-18' AS week_start_utc, 4.3e8 AS supply_counter_avax")
    con.execute("""
        CREATE TABLE par_yield_daily AS SELECT * FROM (VALUES
          (DATE '2023-09-15', '3m', 0.0556), (DATE '2023-09-18', '3m', 0.0600), (DATE '2023-09-15', '1y', 0.0540)
        ) t(observation_date, tenor, yield_rate)
    """)
    frame = lifecycle.market_frame(con)
    row = frame.iloc[0]
    assert row["bill_rate"] == pytest.approx(0.0556)
    quote = annualized_reward_rate(datetime(2023, 9, 18, tzinfo=UTC), 14 * 86_400, 2_000 * NAVAX_PER_AVAX, int(4.3e8) * NAVAX_PER_AVAX)
    assert row["staking_rate"] == pytest.approx(quote)
    assert row["spread"] == pytest.approx(quote - 0.0556)


def test_staking_rate_is_the_kernel_quote():
    rate = lifecycle.staking_rate(4.0e8, datetime(2022, 6, 6, tzinfo=UTC))
    minting_rate = 0.10 + (0.12 - 0.10) * 14 / 365
    assert rate == pytest.approx(minting_rate * (720 - 400) / 400, rel=1e-6)


def test_pearson_rmse_and_direction():
    a = np.array([1.0, 2.0, 3.0, 2.0, np.nan, 5.0])
    b = np.array([2.0, 4.0, 6.0, 4.0, 1.0, 10.0])
    assert fit.pearson_r(a, b) == pytest.approx(1.0)
    assert fit.rmse([0.0, 0.0], [3.0, 4.0]) == pytest.approx(np.sqrt(12.5))
    assert fit.direction_accuracy([1, 2, 3, 2], [1, 3, 2, 1]) == pytest.approx(2 / 3)
    assert np.isnan(fit.pearson_r([1, 1, 1], [1, 2, 3]))
    with pytest.raises(ValueError):
        fit.rmse([1, 2], [1])


def test_phase_alignment_finds_a_known_lag_and_its_sign():
    rng = np.random.default_rng(SEED)
    walk = np.cumsum(rng.normal(size=400))
    observed = walk[20:320]
    trailing = walk[13:313]  # simulated[t + 7] == observed[t]
    assert fit.phase_alignment_days(observed, trailing) == 7
    leading = walk[25:325]  # simulated[t - 5] == observed[t]
    assert fit.phase_alignment_days(observed, leading) == -5
    assert fit.phase_alignment_days(observed, observed) == 0


@pytest.mark.skipif(not OUTPUT.is_file(), reason="behaviour file not built")
def test_behaviour_file_has_the_shared_shape():
    data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert data["version"] == "v0" and data["inputs"]
    for key in ("fit_window", "holdout_window"):
        assert len(data[key]) == 2
    assert data["validator_duration"]["menu_days"] == [14, 30, 90, 180, 365]
    assert sum(data["validator_duration"]["probabilities"]) == pytest.approx(1.0)
    for block in ("validator_entry", "validator_duration", "validator_renewal", "validator_exit", "delegation_flow"):
        assert isinstance(data[block]["identified"], bool) and isinstance(data[block]["ci95"], dict)
    assert {"base_per_day", "spread_elasticity"} <= set(data["validator_entry"])
    assert {"probability", "spread_elasticity"} <= set(data["validator_renewal"])
    assert "base_per_day" in data["validator_exit"]
    assert "sensitivity" in data["delegation_flow"] and "form" in data["delegation_flow"]
    assert set(data["delegator_choice"]["coefficients"]) == set(choice.FEATURES)
    assert {"coefficients", "se", "strata"} <= set(data["delegator_choice"])
