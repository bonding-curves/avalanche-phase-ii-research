"""The four daily outputs the KPIs read, checked against an independent computation on small runs.

Each run's next state lists the commitments that continue, then those started that day, then the scheduled ones due
that day (model.parts.stages). The started commitments are therefore the rows between the continuing ones and the
scheduled ones, and the checks below sum them directly. The offered rate is the run's own reward rule for a 30-day
stake at noon, at the counter the previous day ended with, and the Nakamoto count is the KPI module's own count on the
day's open stakes.
"""

from datetime import UTC, datetime, time, timedelta

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cadCAD")
pytest.importorskip("scipy")

from test_delegated_lifecycle import delegated, flowing
from test_parts_split import small_lifecycle
from test_stake_lifecycle import model_on

from avalanche_research.mechanisms import ChainReward, QuadraticReward
from avalanche_research.model import kpis
from avalanche_research.model.engine import _execute, _long_table
from avalanche_research.model.fitted_lifecycle import (
    FittedLifecycle,
    nakamoto_third_nodes,
)
from avalanche_research.model.stake_lifecycle import StakeLifecycle
from avalanche_research.model.streams import KIND_SCHEDULED, node_keys
from avalanche_research.model.variants import VARIANTS

SIGNALS = ("started_stake_navax", "started_stake_days_navax", "nakamoto_third_nodes", "offered_rate_30d")


def states_and_table(model):
    """The state after each day, one row per run and timestep, and the long table of the same execution."""
    raw = _execute([model])
    last = raw.groupby(["run", "timestep"])["substep"].transform("max")
    states = raw[raw["substep"] == last].sort_values(["run", "timestep"]).reset_index(drop=True)
    return states, _long_table(raw, [model])


def expected_signals(model, states):
    """Each run's four signals by timestep, computed from the states alone."""
    scheduled = model.scheduled
    rows = []
    for run_, frame in states.groupby("run"):
        frame = frame.set_index("timestep")
        for t in frame.index[1:]:
            before, after = frame.loc[t - 1], frame.loc[t]
            kept = int((np.asarray(before["days_left"]) > 1).sum())
            due = np.flatnonzero(np.asarray(scheduled["start_day"]) == t) if scheduled is not None else np.zeros(0, int)
            end = len(after["stakes"]) - len(due)
            assert (np.asarray(after["node_key"][end:]) == node_keys(KIND_SCHEDULED, 0, due)).all()
            stakes, days = after["stakes"][kept:end], after["days"][kept:end]
            open_stakes = np.asarray(after["stakes"])
            assert len(np.unique(after["node_key"])) == len(open_stakes)
            noon = datetime.combine(model.origin + timedelta(days=int(t)), time(12), tzinfo=UTC)
            rows.append({
                "run": run_, "timestep": t, "due": len(due), "started": len(stakes),
                "started_stake_navax": sum(int(s) for s in stakes),
                "started_stake_days_navax": float(sum(int(s) * int(d) for s, d in zip(stakes, days))),
                "nakamoto_third_nodes": kpis.nakamoto_count(open_stakes) if len(open_stakes) else 0,
                "offered_rate_30d": model.mechanism.annual_rate(30, int(before["supply_navax"]), noon),
            })
    return pd.DataFrame(rows).set_index(["run", "timestep"])


def written_signals(table):
    """The four signals as the run's daily table carries them, by run and timestep."""
    wide = table.pivot_table(index=["run", "timestep"], columns="variable", values="value", aggfunc="first")
    floats = table.groupby(["run", "timestep"])[["started_stake_days_navax", "offered_rate_30d"]].first()
    return wide[["started_stake_navax", "nakamoto_third_nodes"]].join(floats)


MODELS = {
    "fitted lifecycle with scheduled commitments": small_lifecycle,
    "stake lifecycle with the fitted stake hurdle": model_on,
    "delegated lifecycle with a flow of delegations": lambda: delegated(delegation_flow=flowing()),
}


@pytest.mark.parametrize("build", MODELS.values(), ids=MODELS.keys())
def test_each_day_writes_the_four_signals_of_an_independent_computation(build):
    model = build()
    states, table = states_and_table(model)
    expected = expected_signals(model, states)
    written = written_signals(table)
    after = written.loc[expected.index]
    for column in ("started_stake_navax", "nakamoto_third_nodes"):
        assert after[column].tolist() == expected[column].tolist(), column
    for column in ("started_stake_days_navax", "offered_rate_30d"):
        assert after[column].to_numpy().tolist() == expected[column].to_numpy().tolist(), column
    # The origin's own row: nothing started, the Nakamoto count of the open commitments, and no offered rate, since
    # the counter the day before the origin is not an input.
    origin = written.xs(0, level="timestep")
    assert (origin["started_stake_navax"] == 0).all() and (origin["started_stake_days_navax"] == 0).all()
    assert origin["offered_rate_30d"].isna().all()
    first = states[states["timestep"] == 0].iloc[0]
    assert (origin["nakamoto_third_nodes"] == kpis.nakamoto_count(first["stakes"])).all()
    # The runs start commitments, so the checks are not of zeros.
    assert (expected["started"] > 0).any()


def test_scheduled_commitments_due_on_a_day_are_not_counted_as_started():
    model = small_lifecycle()
    states, table = states_and_table(model)
    expected = expected_signals(model, states)
    due = expected[expected["due"] > 0]
    assert len(due) == 2 * model.runs
    scheduled_stake = model.scheduled.set_index("start_day")["stakes"]
    written = written_signals(table)
    for (run_, t), row in due.iterrows():
        assert written.loc[(run_, t), "started_stake_navax"] == row["started_stake_navax"]
        assert written.loc[(run_, t), "started_stake_navax"] != row["started_stake_navax"] + scheduled_stake[t]


def test_the_offered_rate_is_the_runs_own_rule_at_each_days_counter():
    chain = small_lifecycle()
    design = chain.with_settings(mechanism=QuadraticReward())
    for model in (chain, design):
        states, table = states_and_table(model)
        expected = expected_signals(model, states)
        assert written_signals(table).loc[expected.index, "offered_rate_30d"].tolist() == expected["offered_rate_30d"].tolist()
    chain_rates = written_signals(states_and_table(chain)[1])["offered_rate_30d"].dropna()
    design_rates = written_signals(states_and_table(design)[1])["offered_rate_30d"].dropna()
    assert (chain_rates != design_rates).all()
    # Each day's counter, not the origin's: day 1 reads the counter at the origin, later days the counter after issuance.
    day_one = ChainReward().annual_rate(30, chain.supply0_navax, datetime.combine(chain.origin + timedelta(days=1), time(12), tzinfo=UTC))
    assert (chain_rates.xs(1, level="timestep") == day_one).all()
    assert chain_rates.nunique() > chain.runs


def test_the_run_daily_table_carries_the_signals_and_the_kpis_read_them():
    model = small_lifecycle()
    states, table = states_and_table(model)
    expected = expected_signals(model, states).xs(1, level="run")
    daily = kpis.run_daily_table(table[table["run"] == 1], model.origin)
    assert set(SIGNALS) <= set(daily.columns)
    horizon = len(daily) - 1
    assert horizon == expected.index.max() == model.timesteps
    assert kpis.nakamoto_coefficient(daily, model.origin, horizon) == expected["nakamoto_third_nodes"].iloc[-1]
    assert kpis.stake_weighted_duration(daily, model.origin, horizon) == pytest.approx(
        expected["started_stake_days_navax"].sum() / expected["started_stake_navax"].sum(), rel=1e-12)
    assert kpis.reward_rate_volatility(daily, model.origin, horizon) == pytest.approx(
        100 * np.std(expected["offered_rate_30d"].to_numpy(), ddof=1), rel=1e-9)
    issued = daily["issued_navax"].iloc[1:].sum()
    assert kpis.earned_rate(daily, model.origin, horizon) == pytest.approx(
        365 * issued / expected["started_stake_days_navax"].sum(), rel=1e-12)
    assert kpis.NOT_IN_MODEL_YET == {}


def test_a_delegated_runs_daily_issuance_counts_validators_only_as_its_stake_days_do():
    model = delegated(delegation_flow=flowing())
    states, table = states_and_table(model)
    one = table[table["run"] == 1]
    wide = one.pivot_table(index="timestep", columns="variable", values="value", aggfunc="first")
    assert wide["delegator_issued_navax"].iloc[1:].sum() > 0
    daily = kpis.run_daily_table(one, model.origin)
    assert daily["issued_navax"].tolist() == wide["validator_issued_navax"].tolist()
    assert daily["issued_all_roles_navax"].tolist() == wide["issued_navax"].tolist()
    expected = expected_signals(model, states).xs(1, level="run")
    horizon = model.timesteps
    assert kpis.earned_rate(daily, model.origin, horizon) == pytest.approx(
        365 * wide["validator_issued_navax"].iloc[1:].sum() / expected["started_stake_days_navax"].sum(), rel=1e-12)
    # Realized supply grows by every role's issuance, delegators' included.
    filled = kpis.with_realized_supply(daily, model.origin, 10**17, 0.0)
    assert filled["total_supply_navax"].iloc[-1] == 10**17 + wide["issued_navax"].iloc[1:].sum()
    assert filled["total_supply_navax"].iloc[-1] > 10**17 + wide["validator_issued_navax"].iloc[1:].sum()


def test_the_nakamoto_count_sums_each_nodes_stake_and_needs_more_than_a_third():
    assert nakamoto_third_nodes(np.array([1, 1, 1]), np.array([1, 2, 3])) == 2
    assert nakamoto_third_nodes(np.array([1, 1, 1]), np.array([1, 1, 2])) == 1
    assert nakamoto_third_nodes(np.array([], dtype=np.int64), np.array([], dtype=np.int64)) == 0
    rng = np.random.default_rng(3)
    for _ in range(200):
        stakes = rng.integers(2_000, 3_000_000, rng.integers(1, 300)) * 10**9
        assert nakamoto_third_nodes(stakes, np.arange(len(stakes))) == kpis.nakamoto_count(stakes)


def test_every_variant_on_the_fitted_lifecycle_writes_the_signals_and_v080_is_one():
    assert issubclass(VARIANTS["v0.8.0"].model, StakeLifecycle)
    built_on = {variant.model for variant in VARIANTS.values() if issubclass(variant.model, FittedLifecycle)}
    assert len(built_on) >= 3
    for cls in built_on:
        model = cls()
        assert set(SIGNALS) <= set(model.state_variables()) | set(model.float_variables()), cls.__name__
