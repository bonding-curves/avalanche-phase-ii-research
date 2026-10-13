"""The sweep's key performance indicators, on small tables with hand-calculated answers and on the replayed chain.

The chain tests read the pinned staking periods and monetary ledger and skip without them. Every value they check is
on a day before 2025-11-19, the first day of the held-back test period.
"""

import math
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from avalanche_research.mechanisms import ChainReward
from avalanche_research.model import kpis
from avalanche_research.model.replay import LOCKBOX_FIRST_DAY

AVAX = 10**9
PIN = Path(__file__).resolve().parents[1] / "data" / "pins" / "p2-model-v0.8.json"


def table(origin, values, before=0):
    """A daily table whose first row is ``before`` days before ``origin``, one column per entry of ``values``."""
    length = max(len(v) for v in values.values())
    days = pd.date_range(pd.Timestamp(origin) - pd.Timedelta(before, unit="D"), periods=length, freq="D")
    return pd.DataFrame({name: list(v) + [np.nan] * (length - len(v)) for name, v in values.items()}, index=days)


ORIGIN = date(2024, 6, 30)


# Hand calculations on small tables.

def test_issuance_saved_compares_issuance_after_the_origin_only():
    run = table(ORIGIN, {"issued_navax": [1_000, 10, 20, 30]})
    baseline = table(ORIGIN, {"issued_navax": [5, 40, 40, 40]})
    assert kpis.issuance_saved(run, baseline, ORIGIN, 3) == pytest.approx(1 - 60 / 120)
    assert kpis.issuance_saved(run, run, ORIGIN, 3) == 0


def test_issuance_saved_from_the_recorded_totals_of_two_rules():
    # 180 days from Fortuna at response 0: 4.57 million AVAX issued under ACP-285 at 7.5% against 5.24 million under
    # the rule before it, so 12.8% of issuance is saved.
    run = table(ORIGIN, {"issued_navax": [0, 4.57e6 * AVAX] + [0] * 179})
    baseline = table(ORIGIN, {"issued_navax": [0, 5.24e6 * AVAX] + [0] * 179})
    assert kpis.issuance_saved(run, baseline, ORIGIN, 180) == pytest.approx(0.128, abs=0.0005)


def test_validator_stake_retained_and_its_levels():
    run = table(ORIGIN, {"active_validator_stake_navax": [100, 90, 70, 80]})
    baseline = table(ORIGIN, {"active_validator_stake_navax": [100, 100, 100, 100]})
    assert kpis.validator_stake_retained(run, baseline, ORIGIN, 3) == pytest.approx(0.8)
    assert kpis.validator_stake_at_horizon(run, ORIGIN, 3) == 80
    assert kpis.lowest_validator_stake(run, ORIGIN, 3) == 70


def test_active_validators_as_a_level_and_against_the_baseline():
    run = table(ORIGIN, {"active_validators": [4, 4, 5]})
    baseline = table(ORIGIN, {"active_validators": [4, 4, 4]})
    assert kpis.active_validators(run, ORIGIN, 2) == 5
    assert kpis.active_validators_retained(run, baseline, ORIGIN, 2) == pytest.approx(1.25)


def test_net_inflation_is_the_trailing_year_of_issuance_less_burn_over_realized_supply():
    # 366 days end at the horizon. The first is outside the trailing year and must not count.
    daily = table(ORIGIN, {
        "issued_navax": [10**6] + [10] * 365,
        "burned_navax": [0] + [4] * 365,
        "total_supply_navax": [21_900] * 366,
    }, before=266)
    assert kpis.net_inflation(daily, ORIGIN, 99) == pytest.approx(365 * 6 / 21_900)


def test_net_inflation_on_a_run_builds_realized_supply_from_the_origin_and_a_fixed_burn():
    # 265 chain days before the origin carry their own burn. The run's 100 days carry issuance only.
    before = {"issued_navax": [10] * 266, "burned_navax": [4] * 266, "total_supply_navax": [20_000] * 266}
    after = {"issued_navax": [10] * 100}
    daily = table(ORIGIN, {k: before[k] + after.get(k, []) for k in before}, before=265)
    expected_supply = 20_000 + 100 * (10 - 4)
    value = kpis.net_inflation(daily, ORIGIN, 100, starting_supply_navax=20_000, burn_navax_per_day=4)
    assert value == pytest.approx(365 * 6 / expected_supply)
    filled = kpis.with_realized_supply(daily, ORIGIN, 20_000, 4)
    assert filled["total_supply_navax"].iloc[-1] == expected_supply
    assert filled["burned_navax"].iloc[-1] == 4
    assert filled.loc[:pd.Timestamp(ORIGIN), "total_supply_navax"].eq(20_000).all()


def test_net_inflation_reads_another_issuance_column_when_asked():
    daily = table(ORIGIN, {
        "issued_navax": [10] * 366, "rewards_paid_navax": [20] * 366,
        "burned_navax": [0] * 366, "total_supply_navax": [7_300] * 366,
    }, before=265)
    assert kpis.net_inflation(daily, ORIGIN, 100, issuance="rewards_paid_navax") == pytest.approx(1.0)


def test_mean_daily_burn_takes_the_last_365_complete_days_to_the_origin():
    burn = [float(b) for b in range(1, 401)]
    burn[390] = np.nan
    daily = table(ORIGIN, {"burned_navax": burn + [10**9]}, before=399)
    complete = [b for b in burn if not math.isnan(b)][-365:]
    assert kpis.mean_daily_burn(daily, ORIGIN) == pytest.approx(sum(complete) / 365)


def test_validator_staking_ratio_with_and_without_delegations():
    daily = table(ORIGIN, {
        "active_validator_stake_navax": [0, 30], "active_delegated_stake_navax": [0, 10], "total_supply_navax": [0, 100],
    })
    assert kpis.validator_staking_ratio(daily, ORIGIN, 1) == pytest.approx(0.3)
    assert kpis.validator_staking_ratio(daily, ORIGIN, 1, with_delegations=True) == pytest.approx(0.4)


def test_nakamoto_coefficient_is_the_value_at_the_horizon():
    daily = table(ORIGIN, {"nakamoto_third_nodes": [30, 25, 23]})
    assert kpis.nakamoto_coefficient(daily, ORIGIN, 2) == 23


def test_nakamoto_count_of_a_set_of_stakes():
    # One third of 100 is 33.3: the top two hold 50, the top one 30.
    assert kpis.nakamoto_count([30, 20, 20, 15, 15]) == 2
    # Exactly one third is not more than one third.
    assert kpis.nakamoto_count([1, 1, 1]) == 2


def test_earned_rate_and_return_margin():
    daily = table(ORIGIN, {"issued_navax": [99, 30, 20], "started_stake_days_navax": [1, 200_000, 165_000]})
    assert kpis.earned_rate(daily, ORIGIN, 2) == pytest.approx(365 * 50 / 365_000)
    assert kpis.return_margin(daily, ORIGIN, 2, competing_yield=0.03, operating_cost=0.01) == pytest.approx(0.01)


def test_earned_rate_on_the_worked_example_equals_the_chain():
    # 2,000 AVAX for 14 days and one hour, the reward counter at 461.18 million AVAX, 2 June 2025: 5.655% a year.
    seconds = 14 * 86_400 + 3_600
    reward = ChainReward().potential_reward_navax(2_000 * AVAX, seconds, 461_180_000 * AVAX, datetime(2025, 6, 2, 12, tzinfo=UTC))
    daily = table(date(2025, 6, 1), {"issued_navax": [0, reward], "started_stake_days_navax": [0, 2_000 * AVAX * seconds / 86_400]})
    assert kpis.earned_rate(daily, date(2025, 6, 1), 1) == pytest.approx(0.05655, abs=0.000005)


def test_stake_weighted_duration():
    daily = table(ORIGIN, {"started_stake_navax": [7, 100, 100], "started_stake_days_navax": [7, 3_000, 1_000]})
    assert kpis.stake_weighted_duration(daily, ORIGIN, 2) == pytest.approx(20.0)


def test_reward_rate_volatility_in_percentage_points():
    daily = table(ORIGIN, {"offered_rate_30d": [0.5, 0.05, 0.06, 0.07]})
    assert kpis.reward_rate_volatility(daily, ORIGIN, 3) == pytest.approx(1.0)


def test_stake_volatility_of_a_stake_that_doubles_and_halves():
    stake = [1_000 if t % 2 == 0 else 2_000 for t in range(41)]
    daily = table(ORIGIN, {"active_validator_stake_navax": stake})
    assert kpis.stake_volatility(daily, ORIGIN, 40) == pytest.approx(math.log(2) * math.sqrt(40 / 39))


def test_worst_30_day_stake_fall():
    stake = [100] * 5 + [60] * 31
    daily = table(ORIGIN, {"active_validator_stake_navax": stake})
    assert kpis.worst_30_day_stake_fall(daily, ORIGIN, 35) == pytest.approx(-0.4)
    with pytest.raises(ValueError, match="30 days"):
        kpis.worst_30_day_stake_fall(daily, ORIGIN, 29)


def test_issuance_half_life_from_the_recorded_year():
    # 13.02 million AVAX issued in a year, the counter at 474.84 million: 13.1 years.
    daily = table(ORIGIN, {
        "issued_navax": [0] + [13.02e6 * AVAX / 365] * 365,
        "supply_counter_navax": [0] * 365 + [474.84e6 * AVAX],
    })
    assert kpis.issuance_half_life(daily, ORIGIN, 365) == pytest.approx(13.1, abs=0.05)


def test_issuance_half_life_annualizes_a_shorter_run():
    cap = 720_000_000 * AVAX
    daily = table(ORIGIN, {"issued_navax": [0] + [2 * AVAX] * 180, "supply_counter_navax": [0] * 180 + [cap - 730 * AVAX * 3]})
    assert kpis.issuance_half_life(daily, ORIGIN, 180) == pytest.approx(math.log(2) * 3)


def test_burn_to_issuance_counts_complete_days_only():
    daily = table(ORIGIN, {"burned_navax": [50, 1, 2, np.nan], "rewards_paid_navax": [1, 10, 10, 10]})
    assert kpis.burn_to_issuance(daily, ORIGIN, 3) == pytest.approx(3 / 20)


@pytest.mark.parametrize(("function", "column"), [
    (kpis.nakamoto_coefficient, "nakamoto_third_nodes"),
    (kpis.earned_rate, "started_stake_days_navax"),
    (kpis.stake_weighted_duration, "started_stake_navax"),
    (kpis.reward_rate_volatility, "offered_rate_30d"),
    (kpis.burn_to_issuance, "rewards_paid_navax"),
])
def test_a_kpi_without_its_column_says_which_column_is_missing(function, column):
    daily = table(ORIGIN, {"issued_navax": [1] * 40, "burned_navax": [1] * 40})
    with pytest.raises(kpis.MissingColumn, match=column):
        function(daily, ORIGIN, 30)
    assert issubclass(kpis.MissingColumn, ValueError)


def test_a_window_with_a_missing_day_is_refused():
    daily = table(ORIGIN, {"active_validators": [4, 4, 5]}).drop(pd.Timestamp(ORIGIN) + pd.Timedelta(1, unit="D"))
    with pytest.raises(ValueError, match="no row"):
        kpis.active_validators(daily, ORIGIN, 2)


def test_a_table_with_two_rows_for_one_day_is_refused():
    # Counted twice, the same day's issuance would score the series against itself as issuing half as much again.
    good = table(ORIGIN, {"issued_navax": [0, 10, 10], "burned_navax": [1, 1, 1]})
    doubled = pd.concat([good, good.iloc[[1]]])
    with pytest.raises(ValueError, match="more than one row for 2024-07-01"):
        kpis.issuance_saved(doubled, good, ORIGIN, 2)
    with pytest.raises(ValueError, match="more than one row"):
        kpis.issuance_saved(good, doubled, ORIGIN, 2)
    with pytest.raises(ValueError, match="more than one row"):
        kpis.with_realized_supply(doubled, ORIGIN, 100, 1)


def test_run_daily_table_refuses_two_values_for_one_cell():
    long = pd.DataFrame({
        "simulation": 0, "run": 1, "timestep": [1, 1, 2], "variable": ["issued_navax"] * 3, "value": [10, 99, 10],
    })
    for order in ([0, 1, 2], [1, 0, 2]):
        with pytest.raises(ValueError, match="more than one issued_navax at timestep 1"):
            kpis.run_daily_table(long.iloc[order], ORIGIN)
    wide = pd.DataFrame({
        "simulation": 0, "run": 1, "timestep": [1, 1], "variable": ["issued_navax", "active_validators"],
        "value": [10, 4], "offered_rate_30d": [0.05, 0.06],
    })
    with pytest.raises(ValueError, match="more than one offered_rate_30d at timestep 1"):
        kpis.run_daily_table(wide, ORIGIN)


@pytest.mark.parametrize("bad", [np.inf, -np.inf])
def test_a_value_that_is_not_finite_is_refused(bad):
    good = table(ORIGIN, {"issued_navax": [0.0, 10.0, 10.0]})
    with pytest.raises(ValueError, match="issued_navax on 2024-07-01 is not finite"):
        kpis.issuance_saved(table(ORIGIN, {"issued_navax": [0.0, bad, 1.0]}), good, ORIGIN, 2)
    with pytest.raises(ValueError, match="not finite"):
        kpis.validator_stake_at_horizon(table(ORIGIN, {"active_validator_stake_navax": [1.0, 1.0, bad]}), ORIGIN, 2)
    with pytest.raises(ValueError, match="not finite"):
        kpis.burn_to_issuance(table(ORIGIN, {"burned_navax": [0, bad, np.nan], "rewards_paid_navax": [1, 1, 1]}), ORIGIN, 2)
    with pytest.raises(ValueError, match="burned_navax .* is not finite"):
        kpis.mean_daily_burn(table(ORIGIN, {"burned_navax": [1.0] * 365 + [bad]}, before=365), ORIGIN)
    with pytest.raises(ValueError, match="not finite"):
        kpis.with_realized_supply(good, ORIGIN, 100, bad)
    with pytest.raises(ValueError, match="not finite"):
        kpis.with_realized_supply(good, ORIGIN, bad, 1)


def test_a_zero_baseline_leaves_a_ratio_undefined():
    finite = table(ORIGIN, {"active_validator_stake_navax": [10, 10, 10], "active_validators": [2, 2, 2]})
    zero = table(ORIGIN, {"active_validator_stake_navax": [0, 0, 0], "active_validators": [0, 0, 0]})
    with pytest.raises(ValueError, match="the baseline's validator stake on 2024-07-02 is zero"):
        kpis.validator_stake_retained(finite, zero, ORIGIN, 2)
    with pytest.raises(ValueError, match="the baseline's active validators on 2024-07-02 is zero"):
        kpis.active_validators_retained(finite, zero, ORIGIN, 2)


# One table for every KPI, and the rule that a KPI reads nothing outside its window.

def full_table(days_before=400, days_after=420):
    n = days_before + days_after + 1
    t = np.arange(n)
    return table(ORIGIN, {
        "active_validators": list(1_000 + t % 7),
        "active_validator_stake_navax": list(10**9 * (1_000 + 50 * np.sin(t / 9))),
        "supply_counter_navax": list(450_000_000 * AVAX + t * 30_000 * AVAX),
        "issued_navax": list(30_000 * AVAX + 1_000 * AVAX * (t % 5)),
        "started_stake_navax": list(10_000 * AVAX + 100 * AVAX * (t % 3)),
        "started_stake_days_navax": list(300_000 * AVAX + 1_000 * AVAX * (t % 11)),
        "offered_rate_30d": list(0.06 - 1e-5 * t),
        "nakamoto_third_nodes": list(20 + t % 4),
        "burned_navax": list(5_000 * AVAX + 10 * AVAX * (t % 13)),
        "total_supply_navax": list(440_000_000 * AVAX + t * 25_000 * AVAX),
        "active_delegated_stake_navax": list(10**9 * (500 + 20 * np.cos(t / 5))),
        "rewards_paid_navax": list(28_000 * AVAX + 500 * AVAX * (t % 3)),
    }, before=days_before)


COSTS = {"low": 0.002, "middle": 0.005, "high": 0.01}


def scored(daily, baseline):
    return kpis.kpi_table(daily, ORIGIN, baseline=baseline, competing_yield=0.04, operating_costs=COSTS)


def test_kpi_table_gives_every_kpi_at_each_horizon():
    daily = full_table()
    result = scored(daily, daily)
    assert set(result["horizon_days"]) == {365, 180}
    assert set(kpis.KPIS) <= set(result["measure"])
    margin = result[(result["measure"] == "return_margin") & (result["horizon_days"] == 365)]
    assert sorted(margin["cost_level"]) == sorted(COSTS)
    one = result.set_index(["measure", "horizon_days", "cost_level"])["value"]
    assert one[("net_inflation", 180, "")] == kpis.net_inflation(daily, ORIGIN, 180)
    assert one[("issuance_saved", 365, "")] == 0
    assert one[("return_margin", 365, "high")] == kpis.return_margin(daily, ORIGIN, 365, 0.04, 0.01)


def test_issued_navax_rebuilds_issuance_saved_exactly_with_or_without_a_baseline():
    # The year's sums are above 2**53 nAVAX, where a sum in another type could round differently.
    daily = full_table()
    rng = np.random.default_rng(5)
    baseline = daily.assign(issued_navax=daily["issued_navax"] + rng.integers(0, 7_919 * AVAX, len(daily)))
    assert kpis.issued_navax(baseline, ORIGIN, 365) > 2**53
    for horizon in kpis.HORIZONS:
        ours, theirs = kpis.issued_navax(daily, ORIGIN, horizon), kpis.issued_navax(baseline, ORIGIN, horizon)
        assert int(ours) == int(daily["issued_navax"].iloc[401:401 + horizon].sum())
        assert 1 - float(ours) / float(theirs) == kpis.issuance_saved(daily, baseline, ORIGIN, horizon)
    paired = scored(daily, baseline).set_index(["measure", "horizon_days", "cost_level"])["value"]
    alone = kpis.kpi_table(daily, ORIGIN, competing_yield=0.04, operating_costs=COSTS).set_index(
        ["measure", "horizon_days", "cost_level"])["value"]
    chain = kpis.kpi_table(baseline, ORIGIN, competing_yield=0.04, operating_costs=COSTS).set_index(
        ["measure", "horizon_days", "cost_level"])["value"]
    assert "issuance_saved" not in set(alone.index.get_level_values("measure"))
    for horizon in kpis.HORIZONS:
        key = ("issued_navax", horizon, "")
        assert alone[key] == paired[key]
        assert 1 - alone[key] / chain[key] == paired[("issuance_saved", horizon, "")]


def test_issued_navax_rebuilds_issuance_saved_exactly_on_a_column_of_python_integers():
    # One day of 2**53 + 1 nAVAX, which a 64-bit float cannot hold. The table gives the float the measure divides.
    days = pd.date_range(pd.Timestamp(ORIGIN), periods=31, freq="D")
    daily = pd.DataFrame({"issued_navax": pd.Series([0, 2**53 + 1] + [0] * 29, index=days, dtype=object)})
    baseline = pd.DataFrame({"issued_navax": pd.Series([0, 2**53 + 2] + [0] * 29, index=days, dtype=object)})
    assert kpis.issued_navax(daily, ORIGIN, 30) == 2**53 + 1
    score = lambda table, **extra: kpis.kpi_table(table, ORIGIN, [30], competing_yield=0.04, operating_costs=COSTS,
                                                 missing="skip", **extra)
    ours, theirs, paired = score(daily), score(baseline), score(daily, baseline=baseline)
    value = lambda table, measure: table.loc[table["measure"] == measure, "value"].item()
    assert 1 - value(ours, "issued_navax") / value(theirs, "issued_navax") == value(paired, "issuance_saved")
    assert value(paired, "issuance_saved") == kpis.issuance_saved(daily, baseline, ORIGIN, 30)
    assert value(ours, "issued_navax") == float(2**53 + 1)


def test_kpi_table_leaves_out_missing_outputs_only_when_asked():
    daily = full_table().drop(columns=["nakamoto_third_nodes", "offered_rate_30d", "started_stake_navax", "started_stake_days_navax"])
    with pytest.raises(kpis.MissingColumn):
        scored(daily, daily)
    result = kpis.kpi_table(daily, ORIGIN, baseline=daily, competing_yield=0.04, operating_costs=COSTS, missing="skip")
    measures = set(result["measure"])
    assert {"nakamoto_coefficient", "reward_rate_volatility", "stake_weighted_duration", "return_margin"}.isdisjoint(measures)
    assert {"issuance_saved", "net_inflation", "stake_volatility", "issuance_half_life"} <= measures


def test_no_kpi_reads_a_day_outside_its_window():
    daily = full_table()
    # The longest horizon ends 365 days after the origin. The trailing year of the shortest starts 184 days before it.
    end = pd.Timestamp(ORIGIN) + pd.Timedelta(365, unit="D")
    first = pd.Timestamp(ORIGIN) - pd.Timedelta(184, unit="D")
    changed = daily.copy()
    changed.loc[changed.index > end] = -1e12
    changed.loc[changed.index < first] = -1e12
    assert scored(daily, daily).equals(scored(changed, changed))
    trimmed = daily.loc[first:end]
    assert scored(daily, daily).equals(scored(trimmed, trimmed))


def test_kpis_name_direction_unit_goal_and_threshold():
    for name, kpi in kpis.KPIS.items():
        assert kpi.better in {"higher", "lower", "within a band"}, name
        assert kpi.unit and kpi.goal, name
    assert kpis.KPIS["issuance_saved"].threshold is None
    stake = kpis.KPIS["validator_stake_retained"].threshold
    assert (stake.fails, stake.level, stake.complement_of) == ("below", None, "issuance_saved")
    assert "team default" in stake.source and "not a Foundation figure" in stake.source
    assert (kpis.KPIS["net_inflation"].threshold.fails, kpis.KPIS["net_inflation"].threshold.level) == ("above", 0.05)
    assert (kpis.KPIS["return_margin"].threshold.fails, kpis.KPIS["return_margin"].threshold.level) == ("below", 0.0)
    assert sum(kpi.threshold is not None for kpi in kpis.KPIS.values()) == 3


def test_run_daily_table_pivots_one_run_after_the_chain():
    chain = table(ORIGIN, {"active_validators": [7, 8], "supply_counter_navax": [100, 105], "issued_navax": [3, 5]}, before=1)
    long = pd.DataFrame({
        "simulation": 0, "run": 1, "timestep": [0, 0, 0, 1, 1, 1, 2, 2, 2],
        "variable": ["active_validators", "supply_navax", "issued_navax"] * 3,
        "value": [8, 105, 0, 9, 111, 6, 10, 118, 7],
        "yield_gap_pp": 0.0,
    })
    daily = kpis.run_daily_table(long, ORIGIN, chain)
    assert list(daily["active_validators"]) == [7, 8, 9, 10]
    assert list(daily["supply_counter_navax"]) == [100, 105, 111, 118]
    assert list(daily["issued_navax"]) == [3, 5, 6, 7]
    assert daily.index[-1] == pd.Timestamp(ORIGIN) + pd.Timedelta(2, unit="D")
    with pytest.raises(ValueError, match="one run"):
        kpis.run_daily_table(pd.concat([long, long.assign(run=2)]), ORIGIN)


# The chain's started commitments, on small staking-period files written here.

def staking_periods(path, accepted_at):
    """Two validator commitments: one starts on 2024-01-01 and runs 4 days, one starts on 2024-01-02 and runs 2 days
    and was accepted at ``accepted_at``, UTC. Each has a potential reward of 100 nAVAX on 2,000 AVAX."""
    periods, ledger = path / "periods.parquet", path / "ledger.parquet"
    connection = duckdb.connect()
    connection.execute(
        "CREATE TABLE p (role VARCHAR, node_id VARCHAR, stake_navax BIGINT, start_time TIMESTAMP, end_time TIMESTAMP, "
        "last_cycle_end_time TIMESTAMP, rewarded_at TIMESTAMP, realized_reward_navax BIGINT, "
        "potential_reward_navax BIGINT, supply_before_navax BIGINT, duration_days DOUBLE, accepted_at TIMESTAMP)")
    connection.execute(
        "INSERT INTO p VALUES ('validator', 'open', 2000000000000, '2024-01-01 00:00', '2024-01-05', NULL, "
        "'2024-01-05', 100, 100, 450000000000000000, 4, '2023-12-31')")
    connection.execute(
        "INSERT INTO p VALUES ('validator', 'later', 2000000000000, '2024-01-02 00:00', '2024-01-04', NULL, "
        "'2024-01-04', 100, 100, 450000000000000100, 2, ?)", [accepted_at])
    connection.execute("COPY p TO ? (FORMAT PARQUET)", [str(periods)])
    connection.execute(
        "CREATE TABLE l AS SELECT d::DATE AS date_utc, true AS complete, '0' AS burned_wei, "
        "'440000000000000000000000000' AS total_supply_close_wei, '0' AS issued_rewards_wei "
        "FROM generate_series(TIMESTAMP '2024-01-01', TIMESTAMP '2024-01-03', INTERVAL 1 DAY) t(d)")
    connection.execute("COPY l TO ? (FORMAT PARQUET)", [str(ledger)])
    connection.close()
    return str(periods), str(ledger)


def test_the_chain_leaves_out_commitments_accepted_by_the_origin_that_start_after_it(tmp_path):
    # Accepted on 2023-12-31 and starting on 2024-01-02, the second commitment is scheduled at a 2024-01-01 origin. A
    # run from that origin holds it as scheduled and does not count it, so the chain must not either.
    origin = date(2024, 1, 1)
    daily = kpis.chain_daily_table(*staking_periods(tmp_path, "2023-12-31 00:00"), origin, through=date(2024, 1, 4))
    after = daily.loc[pd.Timestamp(2024, 1, 2)]
    assert (after["issued_navax"], after["issued_all_roles_navax"], after["started_stake_navax"]) == (0, 0, 0)
    assert (after["started_stake_days_navax"], after["started_validators"]) == (0, 0)
    # The counter still reads every start: the scheduled commitment's reward is in it.
    assert daily.loc[pd.Timestamp(2024, 1, 2), "supply_counter_navax"] == 450_000_000_000_000_200
    # Days up to the origin count every start.
    assert daily.loc[pd.Timestamp(origin), "started_stake_navax"] == 2_000 * AVAX
    with pytest.raises(ValueError, match="no commitment starts in the run"):
        kpis.earned_rate(daily, origin, 1)
    with pytest.raises(ValueError, match="no commitment starts in the run"):
        kpis.stake_weighted_duration(daily, origin, 1)


def test_the_chain_counts_a_commitment_accepted_after_the_origin(tmp_path):
    origin = date(2024, 1, 1)
    daily = kpis.chain_daily_table(*staking_periods(tmp_path, "2024-01-02 00:00"), origin, through=date(2024, 1, 4))
    assert daily.loc[pd.Timestamp(2024, 1, 2), "issued_navax"] == 100
    assert kpis.stake_weighted_duration(daily, origin, 1) == 2
    assert kpis.earned_rate(daily, origin, 1) == pytest.approx(365 * 100 / (2_000 * AVAX * 2))


def test_a_chain_table_is_scored_from_the_origin_it_was_built_for(tmp_path):
    inputs = staking_periods(tmp_path, "2023-12-31 00:00")
    daily = kpis.chain_daily_table(*inputs, date(2024, 1, 1), through=date(2024, 1, 4))
    with pytest.raises(ValueError, match="built for the origin 2024-01-01"):
        kpis.earned_rate(daily, date(2024, 1, 2), 1)
    with pytest.raises(ValueError, match="built for the origin 2024-01-01"):
        kpis.issuance_saved(daily, daily, date(2024, 1, 2), 1)
    # A measure that reads no started commitment can be scored from any origin.
    assert kpis.active_validators(daily, date(2024, 1, 2), 1) == 2
    with pytest.raises(ValueError, match="built for the origin 2024-01-01"):
        kpis.run_daily_table(pd.DataFrame({"simulation": 0, "run": 1, "timestep": [1], "variable": ["issued_navax"], "value": [5]}), date(2024, 1, 2), daily)
    with pytest.raises(ValueError, match="before"):
        kpis.chain_daily_table(*inputs, date(2024, 1, 4), through=date(2024, 1, 4))


# The replayed chain. Expected values are recorded in the v0.7 research report or measured on the pinned runs.

FORTUNA = date(2025, 4, 8)
YEAR_BEFORE_FORTUNA = date(2024, 4, 8)


def pinned(dataset_id):
    from avalanche_research import datasets
    from avalanche_research.catalog import DataError

    try:
        return str(datasets.select_run(dataset_id, pin=PIN)["parquet"])
    except (DataError, FileNotFoundError, StopIteration) as error:
        pytest.skip(f"no pinned run of {dataset_id} in this checkout: {error}")


@pytest.fixture(scope="module")
def chain_inputs():
    return pinned("derived.staking-periods"), pinned("derived.avax-monetary-daily")


@pytest.fixture(scope="module")
def chain(chain_inputs):
    return kpis.chain_daily_table(*chain_inputs, YEAR_BEFORE_FORTUNA)


def test_the_chain_table_stops_before_the_held_back_period(chain, chain_inputs):
    assert chain.index[-1] < pd.Timestamp(LOCKBOX_FIRST_DAY)
    with pytest.raises(ValueError):
        kpis.chain_daily_table(*chain_inputs, YEAR_BEFORE_FORTUNA, through=date(2025, 11, 20))


def test_the_chain_table_equals_the_ledger_on_every_complete_day(chain, chain_inputs):
    ledger = duckdb.execute(
        "SELECT date_utc, active_validators, active_validator_stake_wei::VARCHAR AS stake, "
        "active_delegated_stake_wei::VARCHAR AS delegated FROM read_parquet(?) WHERE complete",
        [chain_inputs[1]],
    ).df()
    for column in ("stake", "delegated"):
        assert all(int(wei) % AVAX == 0 for wei in ledger[column])
        ledger[column] = [int(wei) // AVAX for wei in ledger[column]]
    ledger.index = pd.to_datetime(ledger["date_utc"])
    ledger = ledger.loc[ledger.index.isin(chain.index)]
    assert len(ledger) > 1_800
    rows = chain.loc[ledger.index]
    assert (rows["active_validators"].to_numpy() == ledger["active_validators"].to_numpy()).all()
    assert (rows["active_validator_stake_navax"].to_numpy() == ledger["stake"].to_numpy()).all()
    assert (rows["active_delegated_stake_navax"].to_numpy() == ledger["delegated"].to_numpy()).all()


def test_the_supply_counter_at_a_day_end_is_the_next_start_s_reading_within_a_ten_millionth(chain, chain_inputs):
    # A commitment that ends without its reward lowers the counter between two starts, so the reading after a day's
    # last start can differ slightly from the next start's reading. From the year before Fortuna on, by under 1e-7.
    starts = duckdb.execute(
        "SELECT (epoch_us(start_time) - 86399000000 + 86400000000 - 1) // 86400000000 AS day, "
        "arg_min(supply_before_navax, (start_time, supply_before_navax)) AS first_reading "
        "FROM read_parquet(?) WHERE supply_before_navax IS NOT NULL AND start_time < ? GROUP BY 1 ORDER BY 1",
        [chain_inputs[0], datetime.combine(LOCKBOX_FIRST_DAY, datetime.min.time())],
    ).df()
    starts.index = pd.to_datetime(starts["day"] * 86_400, unit="s")
    following = starts["first_reading"].shift(-1).loc[pd.Timestamp(YEAR_BEFORE_FORTUNA):].dropna()
    counter = chain.loc[following.index, "supply_counter_navax"].astype(float)
    assert len(following) > 500
    assert ((counter - following).abs() / counter).max() < 1e-7


def test_issuance_saved_of_the_chain_against_itself_is_zero(chain):
    assert kpis.issuance_saved(chain, chain, YEAR_BEFORE_FORTUNA, 365) == 0


def test_validator_stake_at_fortuna(chain):
    stake = kpis.validator_stake_at_horizon(chain, YEAR_BEFORE_FORTUNA, 365)
    assert round(stake / AVAX) == 188_162_285
    assert kpis.validator_stake_retained(chain, chain, YEAR_BEFORE_FORTUNA, 365) == 1


def test_active_validators_at_fortuna_and_in_october_2025(chain):
    assert kpis.active_validators(chain, YEAR_BEFORE_FORTUNA, 365) == 1_488
    assert kpis.active_validators(chain, date(2024, 10, 5), 365) == 875


def test_net_inflation_at_fortuna_under_each_issuance_clock(chain):
    def inflation(column):
        return kpis.net_inflation(chain, YEAR_BEFORE_FORTUNA, 365, issuance=column)

    assert inflation("issued_navax") == pytest.approx(0.0301, abs=0.00005)
    assert inflation("issued_all_roles_navax") == pytest.approx(0.0358, abs=0.00005)
    assert inflation("rewards_paid_navax") == pytest.approx(0.0410, abs=0.00005)


def test_validator_staking_ratio_at_fortuna(chain):
    assert kpis.validator_staking_ratio(chain, YEAR_BEFORE_FORTUNA, 365) == pytest.approx(0.4234, abs=0.00005)


def test_nakamoto_coefficient_by_node_at_fortuna(chain):
    assert kpis.nakamoto_coefficient(chain, YEAR_BEFORE_FORTUNA, 365) == 23


def test_earned_rate_on_validator_starts_in_the_year_to_fortuna(chain):
    assert kpis.earned_rate(chain, YEAR_BEFORE_FORTUNA, 365) == pytest.approx(0.0666, abs=0.00005)


def test_stake_weighted_duration_of_validator_starts_in_the_year_to_fortuna(chain):
    window = chain.loc[pd.Timestamp(YEAR_BEFORE_FORTUNA) + pd.Timedelta(1, unit="D"):pd.Timestamp(FORTUNA)]
    assert window["started_validators"].sum() == 16_132
    assert kpis.stake_weighted_duration(chain, YEAR_BEFORE_FORTUNA, 365) == pytest.approx(78.08, abs=0.005)


def test_offered_rate_and_its_volatility_in_the_year_to_fortuna(chain):
    assert round(chain.loc[pd.Timestamp(FORTUNA), "supply_counter_navax"] / AVAX) == 456_931_957
    window = chain.loc[pd.Timestamp(YEAR_BEFORE_FORTUNA) + pd.Timedelta(1, unit="D"):pd.Timestamp(FORTUNA), "offered_rate_30d"]
    assert window.iloc[0] == pytest.approx(0.0644, abs=0.00005)
    # Priced at the previous day's counter, the last day's rate is 5.856%. At that day's own counter it is 5.852%.
    assert window.iloc[-1] == pytest.approx(0.05856, abs=0.000005)
    assert kpis.reward_rate_volatility(chain, YEAR_BEFORE_FORTUNA, 365) == pytest.approx(0.145, abs=0.0005)


def test_stake_volatility_in_the_year_to_fortuna(chain):
    assert kpis.stake_volatility(chain, YEAR_BEFORE_FORTUNA, 365) == pytest.approx(0.0247, abs=0.00005)
    assert kpis.worst_30_day_stake_fall(chain, YEAR_BEFORE_FORTUNA, 365) == pytest.approx(-0.229, abs=0.0005)
    stake = chain.loc[pd.Timestamp(YEAR_BEFORE_FORTUNA):pd.Timestamp(FORTUNA), "active_validator_stake_navax"].astype(float)
    change = np.log(stake).diff().dropna()
    assert change.idxmax() == pd.Timestamp(2024, 5, 10)
    assert change.max() == pytest.approx(0.229, abs=0.0005)


@pytest.mark.parametrize(("year", "ratio"), [(2021, 0.0314), (2022, 0.0643), (2023, 0.1079), (2024, 0.0254)])
def test_burn_to_issuance_by_calendar_year(chain, year, ratio):
    origin = date(year - 1, 12, 31)
    days = (date(year, 12, 31) - origin).days
    assert kpis.burn_to_issuance(chain, origin, days) == pytest.approx(ratio, abs=0.00005)


def test_a_complete_day_missing_its_burn_is_refused_when_completeness_is_recorded():
    """With the ledger's completeness flag, a complete day without a value is refused, and an incomplete day is skipped."""
    flagged = table(ORIGIN, {"burned_navax": [50, 1, 2, np.nan], "rewards_paid_navax": [1, 10, 10, 10],
                             "ledger_complete": [True, True, True, False]})
    assert kpis.burn_to_issuance(flagged, ORIGIN, 3) == pytest.approx(3 / 20)
    gap = table(ORIGIN, {"burned_navax": [50, 1, np.nan, 2], "rewards_paid_navax": [1, 10, 10, 10],
                         "ledger_complete": [True, True, True, True]})
    with pytest.raises(ValueError):
        kpis.burn_to_issuance(gap, ORIGIN, 3)
    burn = [float(b) for b in range(1, 401)]
    burn[390] = np.nan
    with pytest.raises(ValueError):
        kpis.mean_daily_burn(table(ORIGIN, {"burned_navax": burn + [1.0], "ledger_complete": [True] * 401}, before=399), ORIGIN)


def test_two_rows_on_one_calendar_day_are_refused_whatever_their_times():
    """A day is a calendar day: two rows at different times of one day are a duplicate, and so is a time other than
    midnight beside the day's own row."""
    origin = date(2024, 6, 30)
    daily = pd.DataFrame({"issued_navax": [10.0, 1000.0]},
                         index=pd.DatetimeIndex(["2024-07-01 00:00:00", "2024-07-01 12:00:00"], name="date"))
    baseline = pd.DataFrame({"issued_navax": [10.0]}, index=pd.DatetimeIndex(["2024-07-01"], name="date"))
    with pytest.raises(ValueError):
        kpis.issuance_saved(daily, baseline, origin, 1)


def test_run_daily_table_keeps_only_the_chain_columns_a_run_continues():
    """A chain column the run does not produce, such as delegated stake for a model without delegations, is left out,
    so no measure reads a column that is empty after the origin. Burn and realized supply, which the measures rebuild
    after the origin, are kept."""
    chain = table(ORIGIN, {"active_validators": [7, 8], "supply_counter_navax": [100, 105], "issued_navax": [3, 5],
                           "active_delegated_stake_navax": [40, 41], "burned_navax": [1, 2],
                           "total_supply_navax": [500, 501]}, before=1)
    long = pd.DataFrame({
        "simulation": 0, "run": 1, "timestep": [0, 0, 0, 1, 1, 1],
        "variable": ["active_validators", "supply_navax", "issued_navax"] * 2,
        "value": [8, 105, 0, 9, 111, 6],
    })
    daily = kpis.run_daily_table(long, ORIGIN, chain)
    assert "active_delegated_stake_navax" not in daily.columns
    assert {"burned_navax", "total_supply_navax"} <= set(daily.columns)


def test_a_daily_table_out_of_date_order_is_refused():
    """The measures that read the last rows of a window read them by position, so a table whose days are not in
    increasing order is refused rather than read wrongly. Shuffling 366 complete days must not change the mean burn."""
    burn = [1.0] * 365 + [1000.0]
    daily = table(ORIGIN, {"burned_navax": burn + [0.0]}, before=365)
    shuffled = daily.sample(frac=1.0, random_state=7)
    assert kpis.mean_daily_burn(daily, ORIGIN) == pytest.approx(sum(burn[1:]) / 365)
    with pytest.raises(ValueError):
        kpis.mean_daily_burn(shuffled, ORIGIN)
