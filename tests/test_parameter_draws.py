"""Parameter uncertainty in every run: tests written before the code."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from scipy import special

from avalanche_research.model.engine import run
from avalanche_research.model.fitted_blocks import (
    AVAX,
    Arrivals,
    RenewalLogit,
    ReturnHazard,
    renewal_design,
)
from avalanche_research.model.fitted_lifecycle import (
    FittedLifecycle,
    TrainingEvents,
    arrival_block_sample,
    clipped_draws,
    node_resample,
    parameter_draws,
    renewal_quarters,
    resampled_tables,
    training_events,
    window_sd_from_quarters,
    window_tau,
)

MOVES = pd.DataFrame({"previous_days": [14], "next_days": [14], "previous_stake_navax": [10_000 * AVAX],
                      "next_stake_navax": [10_000 * AVAX]})


def lifecycle(**overrides):
    base = {
        "initial": pd.DataFrame({"stakes": [10_000 * AVAX] * 4, "days_left": [1] * 4, "done": [3] * 4,
                                 "after_return": [False] * 4, "days": [14] * 4, "handed_on": [False] * 4}),
        "moves": MOVES,
        "first_commitments": pd.DataFrame({"days": [14], "stake_navax": [7_000 * AVAX]}),
        "renewal": RenewalLogit(intercept=0.0),
        "arrivals": Arrivals(mean_per_day=0.0),
        "timesteps": 3, "runs": 2, "inputs_source": "synthetic",
    }
    return FittedLifecycle(**{**base, **overrides})


def active_at(table: pd.DataFrame, t: int) -> list[int]:
    rows = table[(table.variable == "active_validators") & (table.timestep == t)].sort_values("run")
    return rows.value.astype(int).tolist()


def test_run_r_uses_draw_r():
    """Run 1 reads row 1 and loses every ending, run 2 reads row 2 and keeps every one."""
    draws = pd.DataFrame({"renewal.intercept": [-20.0, 20.0]})
    assert active_at(run(lifecycle(draws=draws)), 1) == [0, 4]


def test_identical_rows_reproduce_the_fixed_block_run():
    """A table that repeats the fitted values changes nothing but the specification hash."""
    fixed = lifecycle(renewal=RenewalLogit(intercept=0.4), arrivals=Arrivals(mean_per_day=2.0, dispersion=1.0), timesteps=30)
    draws = pd.DataFrame({"renewal.intercept": [0.4, 0.4], "arrivals.mean_per_day": [2.0, 2.0],
                          "arrivals.dispersion": [1.0, 1.0], "renewal_shift": [0.0, 0.0]})
    drawn = fixed.with_settings(draws=draws)
    assert run(fixed).value.tolist() == run(drawn).value.tolist()
    assert fixed.specification_hash() != drawn.specification_hash()


def test_a_draw_table_with_too_few_rows_or_an_unknown_column_is_refused():
    with pytest.raises(ValueError):
        run(lifecycle(draws=pd.DataFrame({"renewal.intercept": [0.0]})))
    with pytest.raises(ValueError):
        run(lifecycle(draws=pd.DataFrame({"renewal.not_a_term": [0.0, 0.0]})))


def synthetic_endings(rng, nodes: int, per_node: int, propensity) -> tuple[dict, np.ndarray, np.ndarray]:
    """Endings whose covariates are fixed within a node, as a node keeps its habit, so a node's endings share cells."""
    inputs = {"done": rng.integers(0, 8, nodes), "after_return": rng.random(nodes) < 0.2,
              "days": rng.choice([14, 30, 90, 180, 365], nodes), "stake_navax": rng.integers(2_000, 200_000, nodes) * AVAX}
    inputs = {k: np.repeat(v, per_node) for k, v in inputs.items()}
    codes = np.repeat(np.arange(nodes), per_node)
    renewed = rng.random(nodes * per_node) < np.repeat(propensity, per_node)
    return inputs, renewed, codes


def intercept_se(inputs: dict, renewed: np.ndarray, block: RenewalLogit) -> float:
    """The row-level sampling standard error of the fitted intercept.

    The fit is a ridge-penalized mode, so its sampling variance is the sandwich ``H^-1 I H^-1``, with ``H`` the
    penalized Hessian and ``I`` the information. The inverse Hessian alone is the wider posterior variance, which a
    bootstrap does not estimate.
    """
    design = renewal_design(inputs["done"], inputs["after_return"], inputs["days"], inputs["stake_navax"])[:, :-1]
    p = special.expit(design @ block.coefficients()[:-1])
    penalty = np.ones(design.shape[1])
    penalty[0] = 0.0
    information = (design * (p * (1 - p))[:, None]).T @ design
    inverse = np.linalg.inv(information + np.diag(penalty))
    return float(np.sqrt((inverse @ information @ inverse)[0, 0]))


def bootstrap_intercepts(inputs, renewed, codes, draws: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(draws):
        rows = node_resample(codes, rng)
        sample = {k: v[rows] for k, v in inputs.items()}
        out.append(RenewalLogit.fit(sample, renewed[rows], "bootstrap").intercept)
    return np.array(out)


def test_node_resample_takes_whole_nodes_as_many_as_there_are():
    codes = np.array([0, 0, 0, 1, 2, 2])
    rows = node_resample(codes, np.random.default_rng(1))
    picked = codes[rows]
    assert len(np.unique(codes)) == 3
    for node in np.unique(picked):
        assert (picked == node).sum() % (codes == node).sum() == 0
    assert sum((picked == n).sum() // (codes == n).sum() for n in np.unique(picked)) == 3


def test_bootstrap_spread_matches_the_laplace_se_without_clustering():
    """One ending per node: the node bootstrap is the row bootstrap, and agrees with the Hessian."""
    rng = np.random.default_rng(2)
    inputs, renewed, codes = synthetic_endings(rng, 20_000, 1, np.full(20_000, 0.8))
    se = intercept_se(inputs, renewed, RenewalLogit.fit(inputs, renewed, "synthetic"))
    sd = bootstrap_intercepts(inputs, renewed, codes, 200, 3).std(ddof=1)
    assert sd == pytest.approx(se, rel=0.15)


def test_bootstrap_by_node_widens_under_clustering():
    """Nodes with their own propensity: the node bootstrap is wider than the row-level standard error, by the
    square root of the design effect. Every ending sits in one cell, where that theory is exact. Beta(8, 2)
    propensities have intraclass correlation 0.0145 / 0.16 = 0.091 on the renewal scale, so 12 endings a node give a
    design effect of 1 + 11 x 0.091 = 2.0 and a ratio of 1.41."""
    rng = np.random.default_rng(4)
    nodes, per_node = 4_000, 12
    n = nodes * per_node
    inputs = {"done": np.zeros(n, dtype=np.int64), "after_return": np.zeros(n, dtype=bool),
              "days": np.full(n, 14), "stake_navax": np.full(n, 2_000 * AVAX)}
    codes = np.repeat(np.arange(nodes), per_node)
    renewed = rng.random(n) < np.repeat(rng.beta(8, 2, nodes), per_node)
    se = intercept_se(inputs, renewed, RenewalLogit.fit(inputs, renewed, "synthetic"))
    p = renewed.mean()
    assert se == pytest.approx(1 / np.sqrt(n * p * (1 - p)), rel=1e-6)
    sd = bootstrap_intercepts(inputs, renewed, codes, 200, 5).std(ddof=1)
    icc = (8 * 2 / (10**2 * 11)) / (0.8 * 0.2)
    assert sd / se == pytest.approx(np.sqrt(1 + 11 * icc), rel=0.15)


def test_window_tau_recovers_a_known_spread():
    """Twenty quarters of 1,000 endings whose log-odds shift with SD 0.2, and with none."""
    rng = np.random.default_rng(6)
    for true_sd, check in ((0.2, lambda tau: abs(tau - 0.2) < 0.07), (0.0, lambda tau: tau < 0.05)):
        mean_probability = np.full(20, 0.8)
        shifted = special.expit(special.logit(mean_probability) + rng.normal(0, true_sd, 20))
        observed = rng.binomial(1_000, shifted) / 1_000
        assert check(window_tau(observed, mean_probability, np.full(20, 1_000))), true_sd


def test_training_events_refuse_an_origin_in_the_lockbox():
    """An origin in the validation lockbox is refused."""
    with pytest.raises(ValueError, match="lockbox"):
        training_events("no-such-file.parquet", date(2025, 12, 1))


def synthetic_events(origin=date(2024, 3, 6), nodes: int = 300, seed: int = 8) -> TrainingEvents:
    """A small set of training events with node codes, in the shapes training_events returns."""
    rng = np.random.default_rng(seed)
    per = 3
    n = nodes * per
    done = rng.integers(0, 8, n)
    endings = pd.DataFrame({
        "done": done, "after_return": rng.random(n) < 0.2, "days": rng.choice([14, 30, 90, 180], n),
        "stake_navax": rng.integers(2_000, 3_000_000, n) * AVAX, "returns": np.minimum(rng.integers(0, 3, n), done),
        "renewed": rng.random(n) < 0.8, "node_code": np.repeat(np.arange(nodes), per),
    })
    lapsed = pd.DataFrame({"stake_navax": rng.integers(2_000, 200_000, 200) * AVAX, "days_out": rng.integers(1, 400, 200),
                           "came_back": rng.random(200) < 0.4, "node_code": rng.integers(0, nodes, 200)})
    moves = pd.DataFrame({"previous_days": [14, 30], "next_days": [14, 30], "previous_stake_navax": [10_000 * AVAX] * 2,
                          "next_stake_navax": [10_000 * AVAX] * 2, "node_code": [0, 1]})
    first = pd.DataFrame({"days": [14], "stake_navax": [7_000 * AVAX], "node_code": [2]})
    return TrainingEvents(origin=origin, run="synthetic", window="synthetic endings", endings=endings, lapsed=lapsed,
                          first_counts=rng.poisson(3.0, 365), first_total=1_095, moves=moves, first_commitments=first,
                          state={})


def test_parameter_draws_hold_every_block_term_the_shift_and_a_resample_seed():
    """One row per draw: every behavioural parameter of the renewal, return and arrival blocks, the renewal shift and
    the seed of the run's continuation resample."""
    draws = parameter_draws(synthetic_events(), n=3, seed=0, tau=0.2)
    blocks = {"renewal": RenewalLogit(), "returns": ReturnHazard(), "arrivals": Arrivals()}
    expected = {f"{prefix}.{name}" for prefix, block in blocks.items() for name in block.sources()}
    assert set(draws.columns) == expected | {"renewal_shift", "resample_seed"}
    assert len(draws) == 3 and draws["renewal_shift"].std() > 0
    assert draws["resample_seed"].dtype.kind == "i"


def test_parameter_draws_reproduce_from_their_seed_and_differ_by_seed():
    events = synthetic_events()
    a = parameter_draws(events, n=4, seed=1, tau=0.2)
    assert a.equals(parameter_draws(events, n=4, seed=1, tau=0.2))
    assert not a.equals(parameter_draws(events, n=4, seed=2, tau=0.2))


def test_parameter_draws_refuse_an_origin_in_the_lockbox():
    with pytest.raises(ValueError, match="lockbox"):
        parameter_draws(synthetic_events(origin=date(2025, 12, 1)), n=2, seed=0, tau=0.2)


def test_with_a_stake_line_the_large_holder_block_is_drawn_from_the_same_resampled_nodes():
    events = synthetic_events()
    one = parameter_draws(events, n=2, seed=3, tau=0.2)
    two = parameter_draws(events, n=2, seed=3, tau=0.2, large_above_avax=1_000_000)
    assert any(c.startswith("renewal_large.") for c in two.columns)
    assert one["renewal_shift"].tolist() == two["renewal_shift"].tolist()
    assert one["returns.minimum_8_30"].tolist() == two["returns.minimum_8_30"].tolist()


def test_arrival_draws_resample_whole_28_day_blocks_into_365_days():
    counts = np.arange(365)
    sample = arrival_block_sample(counts, np.random.default_rng(9))
    assert len(sample) == 365
    starts = sample[::28]
    for i, start in enumerate(starts):
        block = sample[28 * i: 28 * i + 28]
        assert block.tolist() == list(range(start, start + len(block)))


def test_the_arrival_block_bootstrap_spread_matches_iid_counts():
    """On independent Poisson counts, the bootstrap SD of the mean is within 15% of sqrt(mean / 365)."""
    counts = np.random.default_rng(10).poisson(4.0, 365)
    rng = np.random.default_rng(11)
    means = [arrival_block_sample(counts, rng).mean() for _ in range(2_000)]
    assert np.std(means) == pytest.approx(np.sqrt(counts.mean() / 365), rel=0.15)


def quarter_endings(counts: dict[str, int], share: float = 0.8, seed: int = 12) -> pd.DataFrame:
    """Renewal endings spread over the named calendar quarters, each ending mid-quarter."""
    rng = np.random.default_rng(seed)
    frames = []
    for quarter, n in counts.items():
        middle = pd.Period(quarter, freq="Q").start_time + pd.Timedelta(days=45)
        frames.append(pd.DataFrame({
            "e": np.full(n, middle.value // 1_000), "done": rng.integers(0, 8, n), "after_return": np.zeros(n, dtype=bool),
            "days": np.full(n, 14), "stake_navax": np.full(n, 10_000 * AVAX), "returns": np.zeros(n, dtype=np.int64),
            "renewed": rng.random(n) < share,
        }))
    return pd.concat(frames, ignore_index=True)


def test_only_labelled_quarters_with_enough_endings_count_toward_the_window_shift():
    """A quarter counts when it ended seven days before the cutoff, so every ending in it is labelled, and when it holds at
    least 200 endings."""
    endings = quarter_endings({"2023Q1": 500, "2023Q2": 150, "2023Q3": 500, "2023Q4": 500})
    cutoff = pd.Timestamp("2024-01-05").value // 1_000
    table = renewal_quarters(endings, cutoff, RenewalLogit(intercept=1.4))
    assert table["quarter"].tolist() == ["2023Q1", "2023Q3"]
    assert table["endings"].tolist() == [500, 500]
    assert np.allclose(table["mean_probability"], special.expit(1.4))


def test_fewer_than_eight_quarters_fall_back_to_the_assumed_shift():
    seven = pd.DataFrame({"quarter": [f"q{i}" for i in range(7)], "endings": [1_000] * 7,
                          "observed": [0.8] * 7, "mean_probability": [0.8] * 7})
    tau, source = window_sd_from_quarters(seven)
    assert tau == 0.18 and source.startswith("assumed")
    eight = pd.concat([seven, seven.iloc[:1]], ignore_index=True)
    tau, source = window_sd_from_quarters(eight)
    assert source.startswith("fitted") and tau == window_tau(eight["observed"], eight["mean_probability"], eight["endings"])


CODED_MOVES = pd.DataFrame({
    "previous_days": [14, 14, 30, 30, 90], "next_days": [14, 30, 30, 90, 90],
    "previous_stake_navax": [10_000 * AVAX] * 5,
    "next_stake_navax": np.array([10_000, 11_000, 20_000, 22_000, 40_000]) * AVAX,
    "node_code": [0, 0, 1, 1, 2],
})
CODED_FIRST = pd.DataFrame({"days": [14, 30, 90], "stake_navax": np.array([5_000, 6_000, 7_000]) * AVAX, "node_code": [3, 4, 5]})


def test_a_continuation_resample_takes_whole_nodes_and_reproduces_from_its_seed():
    moves, first = resampled_tables(CODED_MOVES, CODED_FIRST, resample_seed=5, run=1)
    for table, original in ((moves, CODED_MOVES), (first, CODED_FIRST)):
        assert table["node_code"].nunique() <= original["node_code"].nunique()
        for node, rows in table.groupby("node_code"):
            whole = original[original["node_code"] == node]
            assert len(rows) % len(whole) == 0
    again = resampled_tables(CODED_MOVES, CODED_FIRST, resample_seed=5, run=1)
    assert moves.equals(again[0]) and first.equals(again[1])


def test_a_resample_seed_needs_node_codes_and_changes_only_its_own_run():
    draws = pd.DataFrame({"resample_seed": [1, 2]})
    with pytest.raises(ValueError, match="node_code"):
        run(lifecycle(draws=draws))
    coded = {"moves": CODED_MOVES, "first_commitments": CODED_FIRST,
             "arrivals": Arrivals(mean_per_day=3.0, dispersion=1.0), "renewal": RenewalLogit(intercept=1.0), "timesteps": 40}
    plain = run(lifecycle(**coded))
    resampled = run(lifecycle(**coded, draws=draws))
    assert set(resampled["run"]) == {1, 2}
    assert plain.value.tolist() != resampled.value.tolist()
    assert resampled.value.tolist() == run(lifecycle(**coded, draws=draws)).value.tolist()


def test_draws_with_a_renewal_term_at_the_clip_are_counted():
    """A separable cell pushes a logit term to the ±20 clip. Such draws are counted so they can be reported."""
    draws = pd.DataFrame({"renewal.intercept": [1.0, 20.0, 2.0], "renewal_large.stake_over_1m": [0.0, 0.0, -20.0],
                          "renewal.node_prior_strength": [20.0, 5.0, 5.0], "renewal_shift": [0.1, -0.2, 0.0]})
    assert clipped_draws(draws) == 2


def test_parameter_draws_read_nothing_after_the_origin(tmp_path):
    """Draws and the window shift from a periods file cut at the origin's end equal those from the full file."""
    import duckdb

    from avalanche_research import datasets
    from avalanche_research.catalog import DataError
    from avalanche_research.model.fitted_lifecycle import (
        INSTANT_US,
        US_PER_DAY,
        _day,
        fit_blocks,
        window_sd,
    )

    try:
        full = str(datasets.parquet_path("derived.staking-periods"))
    except (DataError, StopIteration, FileNotFoundError):
        pytest.skip("no built staking-periods run in this checkout")
    origin = date(2024, 3, 6)
    cutoff = _day(origin) * US_PER_DAY + INSTANT_US
    cut = str(tmp_path / "cut.parquet")
    duckdb.execute(f"COPY (SELECT * FROM read_parquet(?) WHERE accepted_at <= make_timestamp({cutoff})) TO '{cut}' (FORMAT parquet)", [full])
    tables = {}
    for name, path in (("full", full), ("cut", cut)):
        events = training_events(path, origin)
        tables[name] = (parameter_draws(events, n=3, seed=0, tau=0.2), window_sd(path, origin, fit_blocks(events)["renewal"]))
    assert tables["full"][0].equals(tables["cut"][0])
    assert tables["full"][1] == tables["cut"][1]
