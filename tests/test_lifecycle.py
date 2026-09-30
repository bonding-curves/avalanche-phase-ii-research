"""The validator lifecycle model on synthetic inputs whose answers are known."""

import numpy as np
import pytest

pytest.importorskip("cadCAD")

from datetime import UTC

from avalanche_research.model.engine import run
from avalanche_research.model.lifecycle import Entry, ValidatorLifecycle


def model(**overrides):
    base = {
        "initial_stakes": np.array([10, 20, 30, 40]), "initial_days_left": np.array([1, 2, 3, 100]),
        "draw_durations": np.array([5]), "draw_stakes": np.array([7]), "entry_rate_per_day": 0.0,
        "renewal_probability": 0.0, "timesteps": 5, "runs": 2, "inputs_source": "synthetic",
    }
    return ValidatorLifecycle(**{**base, **overrides})


def path(table, variable):
    rows = table[(table["variable"] == variable) & (table["run"] == 1)].sort_values("timestep")
    return rows["value"].tolist()


def test_without_renewal_or_entry_commitments_end_on_schedule():
    table = run(model())
    assert path(table, "active_validators") == [4, 3, 2, 1, 1, 1]
    assert path(table, "active_validator_stake_navax") == [100, 90, 70, 40, 40, 40]


def test_with_certain_renewal_every_commitment_stays():
    table = run(model(renewal_probability=1.0))
    assert set(path(table, "active_validators")) == {4}
    assert set(path(table, "active_validator_stake_navax")) == {100}


def test_runs_are_reproducible_from_the_seed_and_differ_between_runs():
    stochastic = {"renewal_probability": 0.5, "entry_rate_per_day": 3.0, "timesteps": 30, "runs": 3}
    first, second = run(model(**stochastic)), run(model(**stochastic))
    assert first["value"].tolist() == second["value"].tolist()
    by_run = first[first["timestep"] == 30].groupby("run")["value"].apply(tuple)
    assert by_run.nunique() > 1


def test_entry_rate_is_recovered_by_its_log_prob():
    rng = np.random.default_rng(3)
    draws = np.array([Entry(rate_per_day=6.5).sample({}, rng) for _ in range(5_000)])
    assert draws.mean() == pytest.approx(6.5, abs=0.15)
    scores = {rate: Entry().with_value("rate_per_day", rate, "assumed", "grid").log_prob({}, draws) for rate in (5.5, 6.5, 7.5)}
    assert max(scores, key=scores.get) == 6.5


def test_origin_inputs_arrive_in_a_fixed_order():
    from datetime import date

    from avalanche_research import datasets
    from avalanche_research.catalog import DataError
    from avalanche_research.model.lifecycle import origin_inputs

    try:
        path = str(datasets.parquet_path("derived.staking-periods"))
    except (DataError, StopIteration, FileNotFoundError):
        pytest.skip("no built staking-periods run in this checkout")
    first, second = origin_inputs(path, date(2024, 3, 6)), origin_inputs(path, date(2024, 3, 6))
    for key in ("initial_stakes", "initial_days_left", "draw_durations", "draw_stakes"):
        assert (first[key] == second[key]).all()


def test_each_started_commitment_is_priced_by_the_mechanism_and_minted_into_supply():
    from datetime import date, datetime

    from avalanche_research.mechanisms import ChainReward

    m = model(renewal_probability=1.0, timesteps=3, runs=1, origin=date(2024, 3, 6), supply0_navax=440_000_000 * 10**9,
              initial_stakes=np.array([2_000 * 10**9]), initial_days_left=np.array([1]), initial_periods_done=np.array([3]))
    table = run(m)
    issued = path(table, "issued_navax")
    supply = path(table, "supply_navax")
    start = datetime(2024, 3, 7, 12, tzinfo=UTC)
    expected = ChainReward().potential_reward_navax(2_000 * 10**9, 5 * 86_400, 440_000_000 * 10**9, start, 4)
    assert issued[1] == expected
    assert supply == [440_000_000 * 10**9 + sum(issued[: i + 1]) for i in range(len(issued))]


def test_a_neutral_mechanism_gives_the_chain_path_and_a_different_one_does_not():
    from avalanche_research.mechanisms import ChainReward, QuadraticReward, TenureBoost

    stochastic = {
        "renewal_probability": 0.8, "entry_rate_per_day": 2.0, "timesteps": 20, "runs": 2, "supply0_navax": 440_000_000 * 10**9,
        "initial_stakes": np.full(4, 2_000 * 10**9), "initial_periods_done": np.array([0, 2, 5, 9]), "draw_stakes": np.array([2_000 * 10**9]),
    }
    chain = run(model(mechanism=ChainReward(), **stochastic))
    linear = run(model(mechanism=QuadraticReward(exponent=1.0), **stochastic))
    boosted = run(model(mechanism=TenureBoost(boost_max=0.5), **stochastic))
    assert path(chain, "supply_navax") == path(linear, "supply_navax")
    assert path(boosted, "supply_navax")[-1] > path(chain, "supply_navax")[-1]


def test_two_equal_mechanism_objects_give_one_specification_hash():
    from avalanche_research.mechanisms import QuadraticReward

    assert model(mechanism=QuadraticReward(exponent=1.5)).specification_hash() == model(mechanism=QuadraticReward(exponent=1.5)).specification_hash()
    assert model(mechanism=QuadraticReward(exponent=1.5)).specification_hash() != model(mechanism=QuadraticReward(exponent=2.0)).specification_hash()


def test_responses_move_behaviour_only_when_the_mechanism_changes_the_yield():
    from avalanche_research.mechanisms import ChainReward, TenureBoost

    base = {"renewal_probability": 0.8, "entry_rate_per_day": 2.0, "timesteps": 60, "runs": 3, "supply0_navax": 440_000_000 * 10**9,
            "initial_stakes": np.full(40, 2_000 * 10**9), "initial_days_left": np.arange(1, 41), "initial_periods_done": np.full(40, 4),
            "draw_stakes": np.array([2_000 * 10**9]), "draw_durations": np.array([14])}
    chain_neutral = run(model(mechanism=ChainReward(), renewal_response=0.0, **base))
    chain_responsive = run(model(mechanism=ChainReward(), renewal_response=1.0, entry_response=1.0, **base))
    boost_responsive = run(model(mechanism=TenureBoost(boost_max=0.5), renewal_response=1.0, entry_response=1.0, **base))
    assert model(mechanism=ChainReward()).yield_gap_pp() == 0.0
    assert path(chain_neutral, "active_validators") == path(chain_responsive, "active_validators")
    last = lambda table: table[(table["variable"] == "active_validators") & (table["timestep"] == 60)]["value"].mean()
    assert last(boost_responsive) > last(chain_responsive)


def test_a_ramp_that_starts_at_the_origin_widens_the_daily_yield_gap():
    from datetime import UTC, date, datetime

    from avalanche_research.mechanisms import ACP285Ramp

    origin = date(2025, 4, 8)
    ramp = model(mechanism=ACP285Ramp(activation=datetime(2025, 4, 8, 16, tzinfo=UTC)), origin=origin, timesteps=100, runs=1,
                 supply0_navax=440_000_000 * 10**9)
    table = run(ramp)
    gaps = path(table, "yield_gap_pp")[1:]
    assert gaps[0] < 0 and gaps[0] > gaps[45] > gaps[95]
    assert gaps[95] == pytest.approx(gaps[99])
