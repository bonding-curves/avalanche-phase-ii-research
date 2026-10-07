"""v0.8's fitted behaviour blocks and lifecycle on synthetic inputs whose answers are known."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cadCAD")
pytest.importorskip("scipy")

from scipy import special

from avalanche_research.model.blocks import check_sources
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_blocks import (
    RENEWAL_TERMS,
    Arrivals,
    Continuation,
    RenewalLogit,
    ReturnHazard,
    renewal_design,
    return_cell,
)
from avalanche_research.model.fitted_lifecycle import FittedLifecycle, fitted_inputs

AVAX = 10**9


def synthetic_endings(n, rng):
    return {
        "done": rng.integers(0, 15, n),
        "after_return": rng.random(n) < 0.2,
        "days": rng.choice([14, 30, 60, 180], n),
        "stake_navax": rng.choice([2_000, 50_000, 500_000, 2_000_000], n) * AVAX,
    }


def test_the_renewal_logit_recovers_known_coefficients():
    rng = np.random.default_rng(1)
    inputs = synthetic_endings(200_000, rng)
    truth = np.array([0.3, 0.5, 1.0, 1.2, 1.1, -1.2, 0.6, 0.1, -0.8, -0.4, -0.1, -1.4, 0.0])
    p = special.expit(renewal_design(**inputs) @ truth)
    fitted = RenewalLogit.fit(inputs, rng.random(len(p)) < p, "synthetic", ridge=0.0)
    assert fitted.coefficients() == pytest.approx(truth, abs=0.08)
    assert {fitted.sources()[term]["source"] for term in RENEWAL_TERMS} == {"fitted"}
    check_sources([fitted])


def test_the_fitted_logit_scores_its_own_data_better_than_the_constant():
    rng = np.random.default_rng(2)
    inputs = synthetic_endings(20_000, rng)
    p = special.expit(renewal_design(**inputs) @ np.array([0.0, 1, 1, 1, 1, -1, 0, 0, 0, 0, 0, -2, 0]))
    decisions = rng.random(len(p)) < p
    fitted = RenewalLogit.fit(inputs, decisions, "synthetic")
    constant = RenewalLogit().with_value("intercept", float(special.logit(decisions.mean())), "observed moment", "synthetic")
    assert fitted.log_prob(inputs, decisions) > constant.log_prob(inputs, decisions)


def test_a_term_with_no_events_stays_at_zero_under_the_prior():
    rng = np.random.default_rng(3)
    inputs = synthetic_endings(5_000, rng)
    inputs["stake_navax"] = np.full(5_000, 2_000 * AVAX)
    fitted = RenewalLogit.fit(inputs, rng.random(5_000) < 0.8, "synthetic")
    assert fitted.stake_over_1m == 0.0


def test_arrivals_recover_a_negative_binomial_mean_and_dispersion():
    rng = np.random.default_rng(4)
    mean, k = 4.0, 0.9
    counts = rng.negative_binomial(k, k / (k + mean), size=20_000)
    fitted = Arrivals.fit(counts, "synthetic")
    assert fitted.mean_per_day == pytest.approx(mean, rel=0.03)
    assert fitted.dispersion == pytest.approx(k, rel=0.08)
    draws = np.array([fitted.sample({}, rng) for _ in range(20_000)])
    assert draws.mean() == pytest.approx(mean, rel=0.05)


def test_underdispersed_counts_fit_a_poisson():
    assert Arrivals.fit(np.full(100, 3), "synthetic").dispersion == 1e6


def test_the_return_hazard_recovers_known_daily_rates_under_censoring():
    rng = np.random.default_rng(5)
    n = 60_000
    stake = rng.choice([2_000, 50_000, 500_000], n) * AVAX
    truth = {2_000: 0.01, 50_000: 0.02, 500_000: 0.03}
    hazard = np.vectorize(lambda s: truth[s // AVAX])(stake)
    days = 7 + rng.geometric(hazard)
    censor = rng.integers(8, 400, n)
    returned = days <= np.minimum(censor, 365)
    fitted = ReturnHazard.fit(stake, np.where(returned, days, censor), returned, "synthetic")
    assert fitted.minimum_8_30 == pytest.approx(0.01, rel=0.06)
    assert fitted.mid_31_90 == pytest.approx(0.02, rel=0.06)
    assert fitted.large_8_30 == pytest.approx(0.03, rel=0.06)


def test_a_return_after_a_year_is_censored_at_a_year_not_counted():
    """A node back on day 400 stayed out for the whole window, so it adds exposure and no return."""
    late = ReturnHazard.fit([2_000 * AVAX], [400], [True], "synthetic")
    stayed = ReturnHazard.fit([2_000 * AVAX], [365], [False], "synthetic")
    assert late.hazards().tolist() == stayed.hazards().tolist() == [0.0] * 9
    assert late.sources()["minimum_91_365"]["evidence"] == stayed.sources()["minimum_91_365"]["evidence"]


def test_no_node_returns_inside_its_renewal_week_or_after_a_year():
    cells = return_cell(np.full(4, 50_000 * AVAX), np.array([7, 8, 365, 366]))
    assert cells.tolist() == [-1, 3, 5, -1]
    always = ReturnHazard(**{name: 1.0 for name in ReturnHazard().sources()})
    assert always.probability({"stake_navax": np.full(4, 2_000 * AVAX), "days_since_end": np.array([7, 8, 365, 366])}).tolist() == [0, 1, 1, 0]


def test_a_continuation_keeps_the_duration_habit_and_the_stake_bounds():
    table = Continuation([14, 14, 180, 180], [15, 15, 200, 200], [2_000 * AVAX] * 4, [1_000 * AVAX, 1_000 * AVAX, 4_000 * AVAX, 4_000 * AVAX])
    rng = np.random.default_rng(6)
    assert set(table.durations(np.array([14, 180, 14]), rng)) == {15, 200}
    assert table.durations(np.array([14, 180]), rng).tolist() == [15, 200]
    stakes = table.stakes(np.full(50, 2_000 * AVAX), rng)
    assert set(stakes) <= {2_000 * AVAX, 4_000 * AVAX}


def model(**overrides):
    base = {
        "initial": pd.DataFrame({"stakes": np.array([10, 20, 30, 40]) * 1_000 * AVAX, "days_left": [1, 2, 3, 100], "done": [0, 1, 2, 3],
                                 "after_return": [False] * 4, "days": [14] * 4, "handed_on": [False] * 4}),
        "moves": pd.DataFrame({"previous_days": [14], "next_days": [5], "previous_stake_navax": [10_000 * AVAX], "next_stake_navax": [10_000 * AVAX]}),
        "first_commitments": pd.DataFrame({"days": [5], "stake_navax": [7_000 * AVAX]}),
        "renewal": RenewalLogit(intercept=-20.0),
        "arrivals": Arrivals(mean_per_day=0.0),
        "timesteps": 5, "runs": 2, "inputs_source": "synthetic",
    }
    return FittedLifecycle(**{**base, **overrides})


def path(table, variable, run_=1):
    rows = table[(table["variable"] == variable) & (table["run"] == run_)].sort_values("timestep")
    return rows["value"].tolist()


def test_without_renewal_returns_or_arrivals_commitments_end_on_schedule_and_leave_the_set():
    table = run(model())
    assert path(table, "active_validators") == [4, 3, 2, 1, 1, 1]
    assert path(table, "active_validator_stake_navax") == [v * 1_000 * AVAX for v in (100, 90, 70, 40, 40, 40)]
    assert path(table, "returning_nodes") == [0, 1, 2, 3, 3, 3]


def test_with_certain_renewal_every_commitment_stays():
    table = run(model(renewal=RenewalLogit(intercept=20.0)))
    assert set(path(table, "active_validators")) == {4}


def test_a_node_out_of_the_set_returns_only_after_its_renewal_week_and_is_dropped_after_a_year():
    out = pd.DataFrame({"out_stakes": [10_000 * AVAX, 10_000 * AVAX], "out_days": [0, 364], "out_done": [1, 1], "out_last_days": [14, 14]})
    certain = ReturnHazard(**{name: 1.0 for name in ReturnHazard().sources()})
    table = run(model(initial=pd.DataFrame(columns=["stakes", "days_left", "done", "after_return", "days", "handed_on"]),
                      out_of_set=out, returns=certain, timesteps=10, runs=1))
    # The node a year out returns on day 1 for five days, then leaves again. The other returns on day 8.
    assert path(table, "active_validators") == [0, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1]
    assert path(table, "returning_nodes") == [2, 1, 1, 1, 1, 1, 2, 2, 1, 1, 1]


def test_a_commitment_handed_on_to_a_scheduled_one_neither_renews_nor_leaves():
    initial = pd.DataFrame({"stakes": [10_000 * AVAX], "days_left": [1], "done": [2], "after_return": [False], "days": [14], "handed_on": [True]})
    scheduled = pd.DataFrame({"start_day": [2], "stakes": [12_000 * AVAX], "days": [30], "done": [3], "after_return": [False]})
    table = run(model(initial=initial, scheduled=scheduled, renewal=RenewalLogit(intercept=20.0), timesteps=3, runs=1))
    assert path(table, "active_validators") == [1, 0, 1, 1]
    assert path(table, "returning_nodes") == [0, 0, 0, 0]


def test_runs_are_reproducible_from_the_seed_and_differ_between_runs():
    stochastic = {"renewal": RenewalLogit(), "arrivals": Arrivals(mean_per_day=3.0, dispersion=1.0), "timesteps": 30, "runs": 3}
    first, second = run(model(**stochastic)), run(model(**stochastic))
    assert first["value"].tolist() == second["value"].tolist()
    by_run = first[first["timestep"] == 30].groupby("run")["value"].apply(tuple)
    assert by_run.nunique() > 1


def test_fitted_inputs_refuse_an_origin_in_the_lockbox():
    with pytest.raises(ValueError, match="lockbox"):
        fitted_inputs("unused.parquet", date(2025, 11, 19))


def test_the_renewal_fit_counts_the_same_endings_as_v07():
    from avalanche_research import datasets
    from avalanche_research.catalog import DataError
    from avalanche_research.model.lifecycle import origin_inputs

    try:
        path_ = str(datasets.parquet_path("derived.staking-periods"))
    except (DataError, StopIteration, FileNotFoundError):
        pytest.skip("no built staking-periods run in this checkout")
    origin = date(2024, 3, 6)
    ours, v07 = fitted_inputs(path_, origin), origin_inputs(path_, origin)
    evidence = ours["renewal"].sources()["intercept"]["evidence"]
    endings, renewed = (int(x) for x in evidence.split(": ")[1].replace(" renewed", "").split(" endings, "))
    assert renewed / endings == pytest.approx(v07["renewal_probability"], abs=1e-12)
    assert len(ours["initial"]) == len(v07["initial_stakes"])
    assert set(RENEWAL_TERMS) <= set(ours["renewal"].sources())


def test_the_stake_after_a_move_is_unbiased_for_the_band_total():
    """A small node raising its stake ten times must not lift a large node's expected stake (candidate v0.8-b)."""
    table = Continuation([14] * 3, [14] * 3, [30_000 * AVAX, 50_000 * AVAX, 50_000 * AVAX], [300_000 * AVAX, 45_000 * AVAX, 45_000 * AVAX])
    draws = table.stakes(np.full(20_000, 50_000 * AVAX), np.random.default_rng(7))
    band_ratio = (300_000 + 45_000 + 45_000) / (30_000 + 50_000 + 50_000)
    assert draws.mean() / (50_000 * AVAX) == pytest.approx(band_ratio, rel=0.03)
    assert band_ratio < (10 + 0.9 + 0.9) / 3


def test_the_node_record_is_recovered_with_its_prior_strength():
    """Nodes differ in their own renewal propensity; the record of their earlier endings carries it (candidate v0.8-c)."""
    rng = np.random.default_rng(8)
    nodes, endings = 4_000, 12
    propensity = rng.beta(8, 2, nodes)
    renewed = rng.random((nodes, endings)) < propensity[:, None]
    done = np.tile(np.arange(endings), nodes)
    returns = np.concatenate([np.cumsum(np.concatenate([[0], ~row[:-1]])) for row in renewed])
    inputs = {"done": done, "after_return": np.concatenate([np.concatenate([[False], ~row[:-1]]) for row in renewed]),
              "days": np.full(done.size, 14), "stake_navax": np.full(done.size, 2_000 * AVAX), "returns": returns}
    fitted = RenewalLogit.fit(inputs, renewed.ravel(), "synthetic")
    plain = RenewalLogit.fit({k: v for k, v in inputs.items() if k != "returns"}, renewed.ravel(), "synthetic")
    assert fitted.node_record > 0.5
    assert fitted.node_prior_strength in (2.0, 5.0, 10.0, 20.0)
    assert fitted.log_prob(inputs, renewed.ravel()) > plain.log_prob(inputs, renewed.ravel()) + 100
    assert plain.node_record == 0.0


def test_a_separate_renewal_block_decides_for_commitments_above_the_line():
    """The two-segment approach: the large block alone decides above the line."""
    initial = pd.DataFrame({"stakes": [2_000_000 * AVAX, 10_000 * AVAX], "days_left": [1, 1], "done": [3, 3], "after_return": [False, False],
                            "days": [30, 14], "handed_on": [False, False]})
    table = run(model(initial=initial, renewal=RenewalLogit(intercept=20.0), renewal_large=RenewalLogit(intercept=-20.0),
                      large_above_avax=1_000_000, timesteps=2, runs=1))
    assert path(table, "active_validators") == [2, 1, 1]
    assert path(table, "active_validator_stake_navax")[1] < 1_000_000 * AVAX


def test_arrivals_log_prob_reads_the_scale_that_sample_uses():
    """sample and log_prob share one definition, so a scaled mean is scored as it is drawn."""
    block = Arrivals(mean_per_day=3.0, dispersion=0.5)
    counts = np.random.default_rng(5).negative_binomial(0.5, 0.5 / (0.5 + 4.5), size=2_000)
    assert block.log_prob({"scale": 1.5}, counts) > block.log_prob({"scale": 1.0}, counts)
    assert block.log_prob({"scale": 1.5}, counts) == pytest.approx(Arrivals(mean_per_day=4.5, dispersion=0.5).log_prob({}, counts))


def test_the_scaled_entry_mean_is_capped_at_100_as_in_v07():
    """A large response cannot push the daily arrival mean past 100."""
    block = Arrivals(mean_per_day=50.0, dispersion=1e6)
    capped = Arrivals(mean_per_day=100.0, dispersion=1e6)
    assert block.count_from_uniform(0.5, 10.0) == capped.count_from_uniform(0.5, 1.0)
    assert block.log_prob({"scale": 10.0}, np.array([100])) == pytest.approx(capped.log_prob({}, np.array([100])))


def test_a_scale_that_is_not_finite_and_non_negative_is_refused():
    """min(100, nan) is 100, so a NaN or infinite scale must be refused, never capped."""
    for scale in (float("nan"), float("inf"), -1.0):
        for block in (Arrivals(mean_per_day=0.0), Arrivals(mean_per_day=3.0)):
            with pytest.raises(ValueError):
                block.scaled_mean(scale)
