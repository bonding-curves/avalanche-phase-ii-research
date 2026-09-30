"""The validator lifecycle model on synthetic inputs whose answers are known."""

import numpy as np
import pytest

pytest.importorskip("cadCAD")

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
    scores = {rate: Entry(rate_per_day=rate).log_prob({}, draws) for rate in (5.5, 6.5, 7.5)}
    assert max(scores, key=scores.get) == 6.5
