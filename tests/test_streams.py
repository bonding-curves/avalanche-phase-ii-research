"""Keyed random streams: tests written before the lifecycle used them."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from avalanche_research.mechanisms import ChainReward, TenureBoost
from avalanche_research.model import streams
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_blocks import (
    AVAX,
    Arrivals,
    Continuation,
    RenewalLogit,
)
from avalanche_research.model.fitted_lifecycle import FittedLifecycle
from avalanche_research.model.streams import Streams, node_keys

MOVES = pd.DataFrame({
    "previous_days": [14] * 6, "next_days": [7, 14, 30, 60, 90, 180],
    "previous_stake_navax": [10_000 * AVAX] * 6,
    "next_stake_navax": np.array([5_000, 8_000, 10_000, 12_000, 20_000, 40_000]) * AVAX,
})


def lifecycle(**overrides):
    base = {
        "initial": pd.DataFrame({"stakes": [10_000 * AVAX] * 4, "days_left": [1] * 4, "done": [3] * 4,
                                 "after_return": [False] * 4, "days": [14] * 4, "handed_on": [False] * 4}),
        "moves": MOVES,
        "first_commitments": pd.DataFrame({"days": [14], "stake_navax": [7_000 * AVAX]}),
        "renewal": RenewalLogit(intercept=-10.0, tenure_3_6=20.0),
        "arrivals": Arrivals(mean_per_day=0.0),
        "timesteps": 5, "runs": 1, "inputs_source": "synthetic",
    }
    return FittedLifecycle(**{**base, **overrides})


def one_step(model):
    policy = model.blocks()[0]["policies"]["lifecycle"]
    state = {**model.initial_state(), "timestep": 0, "run": 1}
    return policy(model.param.values(), 0, [], state)


def test_one_more_renewal_leaves_every_other_draw_unchanged():
    """Node 0 renews in one design and leaves in the other. Nodes 1 to 3 renew in both, with the same draws."""
    all_renew = one_step(lifecycle())
    initial = lifecycle().initial.assign(done=[0, 3, 3, 3])
    zero_leaves = one_step(lifecycle(initial=initial))
    assert len(all_renew["stakes"]) == 4 and len(zero_leaves["stakes"]) == 3
    assert all_renew["stakes"][1:].tolist() == zero_leaves["stakes"].tolist()
    assert all_renew["days_left"][1:].tolist() == zero_leaves["days_left"].tolist()


def test_response_zero_gives_identical_runs_across_designs():
    """With no response, the reward design changes only supply and issuance."""
    stochastic = {"renewal": RenewalLogit(), "arrivals": Arrivals(mean_per_day=2.0, dispersion=1.0), "timesteps": 40, "runs": 2}
    chain = run(lifecycle(mechanism=ChainReward(), **stochastic))
    boost = run(lifecycle(mechanism=TenureBoost(), **stochastic))
    keep = ~chain["variable"].isin(["supply_navax", "issued_navax"])
    assert chain.loc[keep, "value"].tolist() == boost.loc[keep, "value"].tolist()


def test_keyed_uniforms_are_uniform_and_independent():
    """Uniform and independent, including adjacent decisions of one node are independent."""
    s = Streams(seed=11, run=3)
    keys = np.arange(1_000_000, dtype=np.int64)
    u = s.uniforms("renewal", keys, 4)
    assert stats.kstest(u, "uniform").pvalue > 0.001
    assert abs(np.corrcoef(u, s.uniforms("returns", keys, 4))[0, 1]) < 0.005
    assert abs(np.corrcoef(u[:-1], u[1:])[0, 1]) < 0.005
    following = s.uniforms("renewal", keys, 5)
    table = np.histogram2d(u, following, bins=32, range=[[0, 1], [0, 1]])[0]
    assert stats.chi2_contingency(table)[1] > 0.001


def test_streams_replay_and_differ_by_seed_run_and_purpose():
    keys = np.arange(100)
    a = Streams(1, 1).uniforms("renewal", keys)
    assert a.tolist() == Streams(1, 1).uniforms("renewal", keys).tolist()
    for other in (Streams(2, 1).uniforms("renewal", keys), Streams(1, 2).uniforms("renewal", keys), Streams(1, 1).uniforms("returns", keys)):
        assert not np.allclose(a, other)
    assert Streams(1, 1).uniforms("renewal", np.zeros(0, dtype=np.int64)).size == 0


def test_declaring_a_purpose_moves_no_other_purpose(monkeypatch):
    """Ids come from names, not positions."""
    keys = np.arange(1_000)
    before = Streams(0, 1).uniforms("renewal", keys)
    monkeypatch.setitem(streams.PURPOSES, "a_new_purpose", "test only")
    assert Streams(0, 1).uniforms("renewal", keys).tolist() == before.tolist()
    with pytest.raises(KeyError):
        Streams(0, 1).uniforms("undeclared", keys)


def test_generator_seed_lists_never_collide_with_keyed_roots():
    """Tagged, fixed-length seed lists: a generator with no keys differs from one with a zero key."""
    s = Streams(0, 1)
    assert s.generator("parameter_draw").random() != s.generator("parameter_draw", 0).random()
    assert s.generator("parameter_draw", 5).random() == Streams(0, 1).generator("parameter_draw", 5).random()


def test_node_keys_hold_kind_day_and_index():
    k = node_keys(3, 7, np.array([0, 5]))
    assert (k >> 48).tolist() == [3, 3] and ((k >> 24) & 0xFFFFFF).tolist() == [7, 7] and (k & 0xFFFFFF).tolist() == [0, 5]
    with pytest.raises(ValueError):
        node_keys(0, 1 << 24, np.array([0]))


def test_inversion_draws_match_the_table():
    """Stakes by inversion keep the band's stake-weighted ratio, as the weighted draw does."""
    table = Continuation([14] * 3, [14] * 3, [30_000 * AVAX, 50_000 * AVAX, 50_000 * AVAX], [300_000 * AVAX, 45_000 * AVAX, 45_000 * AVAX])
    u = Streams(0, 1).uniforms("renew_stake", np.arange(200_000))
    draws = table.stakes_from_uniforms(np.full(200_000, 50_000 * AVAX), u)
    band_ratio = (300_000 + 45_000 + 45_000) / (30_000 + 50_000 + 50_000)
    assert draws.mean() / (50_000 * AVAX) == pytest.approx(band_ratio, rel=0.03)
    days = Continuation([14, 14, 180], [15, 30, 200], [2_000 * AVAX] * 3, [2_000 * AVAX] * 3).durations_from_uniforms(np.array([14, 14, 180]), np.array([0.1, 0.9, 0.5]))
    assert days.tolist() == [15, 30, 200]


def test_the_arrival_count_by_inversion_has_the_fitted_mean():
    block = Arrivals(mean_per_day=3.0, dispersion=0.5)
    counts = [block.count_from_uniform(u, 1.0) for u in Streams(0, 1).uniforms("arrivals", np.arange(50_000))]
    assert np.mean(counts) == pytest.approx(3.0, rel=0.05)
    assert Arrivals(mean_per_day=0.0).count_from_uniform(0.7, 1.0) == 0


def test_a_design_generator_has_its_own_declared_stream():
    """A sweep's design generator in library code seeds through this stream, as the seed audit requires."""
    first = Streams(7, 0).generator("design").random(3)
    assert first.tolist() == Streams(7, 0).generator("design").random(3).tolist()
    assert first.tolist() != Streams(7, 0).generator("parameter_draw").random(3).tolist()
