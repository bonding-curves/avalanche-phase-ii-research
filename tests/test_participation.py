"""Participation: the arrival feedback on the unstaked share of supply, and the supply limit every new stake obeys.

The limit test is the equivalent of the market sweep row that broke ``stake within supply`` on 27 October 2026: a
run whose arrivals, at a multiple of the fitted rate, stake more than the supply holds within the year. Here every
arrival stakes the protocol's maximum, so the run reaches the limit in two days instead of 358.
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cadCAD")
pytest.importorskip("scipy")

from test_delegated_lifecycle import delegated, flowing, wide
from test_fitted_lifecycle import model, path
from test_stake_lifecycle import model_on

from avalanche_research.model.engine import InvariantError, run
from avalanche_research.model.fitted_blocks import Arrivals, RenewalLogit, ReturnHazard
from avalanche_research.model.parts import participation
from avalanche_research.model.parts.participation import (
    MIN_STAKE_NAVAX,
    funded,
    participation_scale,
    unstaked_share,
    within_pool,
)

AVAX = 10**9
SUPPLY = 465_370_000 * AVAX
"""The reward counter at the 14 October sweep's origin."""


def supply_and_stake(table, run_=1):
    return np.array(path(table, "supply_navax", run_)), np.array(path(table, "active_validator_stake_navax", run_))


def fifty_at_the_maximum():
    """Fifty open commitments of 3,000,000 AVAX, 150 million staked of the 465 million counter."""
    return pd.DataFrame({"stakes": np.full(50, 3_000_000 * AVAX), "days_left": np.full(50, 300), "done": np.zeros(50, dtype=np.int64),
                         "after_return": np.zeros(50, bool), "days": np.full(50, 365), "handed_on": np.zeros(50, bool)})


def crowded(stake_avax=3_000_000, **overrides):
    """Arrivals at the model's ceiling of 100 a day, each staking ``stake_avax`` for a year, against 315 million unstaked."""
    settings = {"arrivals": Arrivals(mean_per_day=100.0), "first_commitments": pd.DataFrame({"days": [365], "stake_navax": [stake_avax * AVAX]}),
                "initial": fifty_at_the_maximum(), "supply0_navax": SUPPLY, "timesteps": 10, "runs": 1, "seed": 3}
    return model(**{**settings, **overrides})


# The feedback

def test_the_scale_is_one_at_the_origin_and_one_everywhere_at_zero_elasticity():
    assert participation_scale(0.55, 0.55, 1.0) == 1.0
    assert participation_scale(0.2, 0.55, 0.0) == 1.0
    assert participation_scale(0.275, 0.55, 1.0) == pytest.approx(0.5)
    assert participation_scale(0.0, 0.55, 1.0) == 0.0
    assert participation_scale(0.275, 0.55, 0.5) == pytest.approx(0.5 ** 0.5)
    with pytest.raises(ValueError, match="unstaked supply at the origin"):
        participation_scale(0.5, 0.0, 1.0)


def test_the_unstaked_share_counts_delegated_stake_when_the_state_carries_it():
    state = {"supply_navax": 100 * AVAX, "active_validator_stake_navax": 30 * AVAX}
    assert unstaked_share(state) == pytest.approx(0.7)
    assert unstaked_share({**state, "active_delegated_stake_navax": 20 * AVAX}) == pytest.approx(0.5)
    assert unstaked_share({**state, "active_validator_stake_navax": 120 * AVAX}) == 0.0
    # The delegated model's origin share counts its open delegations.
    base = delegated(supply0_navax=1_000_000 * AVAX, timesteps=1, runs=1)
    assert unstaked_share(base.initial_state()) == pytest.approx(1 - (159_000 + 51_525) / 1_000_000)


def test_at_zero_elasticity_the_setting_is_omitted_and_the_hash_is_the_released_one():
    base = model(arrivals=Arrivals(mean_per_day=3.0, dispersion=1.0), timesteps=30, runs=2)
    assert "participation_elasticity" not in base.specification()
    assert "participation_elasticity" not in base.settings()
    assert base.specification_hash() == base.with_settings(participation_elasticity=0.0).specification_hash()
    fed = base.with_settings(participation_elasticity=1.0)
    assert fed.specification()["participation_elasticity"] == 1.0 and fed.specification_hash() != base.specification_hash()


def test_arrivals_fall_in_proportion_to_the_unstaked_share_and_slow_as_the_pool_empties():
    free = run(crowded(stake_avax=1_000_000, timesteps=20))
    fed = run(crowded(stake_avax=1_000_000, timesteps=20, participation_elasticity=1.0))
    free_count, fed_count = np.array(path(free, "active_validators")), np.array(path(fed, "active_validators"))
    # Day one reads the origin's share, so both admit the fitted rate. Then the feedback admits fewer each day.
    assert fed_count[1] == free_count[1]
    assert fed_count[-1] < free_count[-1]
    supply, stake = supply_and_stake(fed)
    assert (stake <= supply).all()
    share0, share = 315 / 465.37, 1 - stake[-1] / supply[-1]
    scale = participation_scale(share, share0, 1.0)
    assert scale < 0.5
    # The last five days' arrivals are near the fitted rate times the scale, far below the fitted 100 a day.
    late = np.diff(fed_count)[-5:].mean()
    assert late < 100 * participation_scale(1 - stake[-6] / supply[-6], share0, 1.0) + 10 and late < 60


# The supply limit

def test_each_stake_takes_the_room_left_and_none_starts_below_the_minimum():
    stakes = np.array([5, 5, 5, 5]) * 1_000 * AVAX
    out, made = funded(stakes, 12_000 * AVAX)
    assert out.tolist() == [5_000 * AVAX, 5_000 * AVAX, 2_000 * AVAX, 0] and made.tolist() == [True, True, True, False]
    out, made = funded(stakes, 11_500 * AVAX)
    assert out.tolist() == [5_000 * AVAX, 5_000 * AVAX, 0, 0] and made.tolist() == [True, True, False, False]
    out, made = funded(stakes, SUPPLY)
    assert (out == stakes).all() and made.all()
    assert funded(np.zeros(0, dtype=np.int64), 0)[0].tolist() == []
    assert within_pool(np.array([2, 0, 1]), stakes, 11_000 * AVAX).tolist() == [2, 0]
    assert within_pool(np.array([2, 0, 1]), stakes, SUPPLY).tolist() == [2, 0, 1]
    assert within_pool(np.zeros(0, dtype=np.int64), stakes, 0).tolist() == []


def test_the_limit_reproduces_the_sweeps_failure_and_holds_the_invariant(monkeypatch):
    # Without the limit, 100 arrivals a day at 3,000,000 AVAX break the invariant on day two, as the sweep row did on day 358.
    monkeypatch.setattr(participation, "funded", lambda stakes, pool, minimum=MIN_STAKE_NAVAX: (np.asarray(stakes), np.ones(len(stakes), bool)))
    with pytest.raises(InvariantError, match="stake within supply fails at timestep 2"):
        run(crowded())
    monkeypatch.undo()
    table = run(crowded())
    supply, stake = supply_and_stake(table)
    assert (stake <= supply).all()
    # Day one's 92 arrivals fit. From day two the stake fills the counter as it stood at the start of the day, the only
    # slack being that day's own rewards, which the next day's arrivals take, until the slack is below one minimum
    # stake: then no arrival starts, no reward is minted, and the run sits still.
    counts = np.array(path(table, "active_validators"))
    assert counts[1] > 50 and stake[1] < supply[1]
    gap = supply[:-1] - stake[1:]
    assert all(g == 0 or g < MIN_STAKE_NAVAX for g in gap[1:])
    assert stake[2] == supply[1] and stake[2] % (3_000_000 * AVAX) != 0
    assert supply[-1] == supply[-2] and stake[-1] == stake[-2] and counts[-1] == counts[-2]


def test_a_renewal_the_pool_cannot_fund_leaves_the_set_and_a_return_stays_out():
    # Four commitments end on day one and renew at twice their stake against a supply 10,000 AVAX above their total.
    # Rewards are minted on the supply counter, so the counter is set near the cap to keep them small.
    initial = pd.DataFrame({"stakes": np.array([10, 20, 30, 40]) * 1_000 * AVAX, "days_left": [1] * 4, "done": [1] * 4,
                            "after_return": [False] * 4, "days": [14] * 4, "handed_on": [False] * 4})
    doubling = pd.DataFrame({"previous_days": [14], "next_days": [30], "previous_stake_navax": [10_000 * AVAX], "next_stake_navax": [20_000 * AVAX]})
    table = run(model(initial=initial, moves=doubling, renewal=RenewalLogit(intercept=20.0), supply0_navax=110_000 * AVAX, timesteps=2, runs=1))
    supply, stake = supply_and_stake(table)
    # 20k, 40k and the 60k clipped to 50k fit. The 80k finds no room, so its node leaves and waits to return.
    assert stake[1] == 110_000 * AVAX and (stake <= supply).all()
    assert path(table, "active_validators") == [4, 3, 3] and path(table, "returning_nodes") == [0, 1, 1]
    # A node out of the set returns only when the pool funds it: with 1,000 AVAX unstaked it stays out.
    out = pd.DataFrame({"out_stakes": [10_000 * AVAX], "out_days": [10], "out_done": [1], "out_last_days": [14]})
    certain = ReturnHazard(**{name: 1.0 for name in ReturnHazard().sources()})
    full = pd.DataFrame({"stakes": [100_000 * AVAX], "days_left": [100], "done": [0], "after_return": [False], "days": [14], "handed_on": [False]})
    stays = run(model(initial=full, out_of_set=out, returns=certain, supply0_navax=101_000 * AVAX, timesteps=1, runs=1))
    assert path(stays, "returning_nodes") == [1, 1] and path(stays, "active_validators") == [1, 1]
    room = run(model(initial=full, out_of_set=out, returns=certain, supply0_navax=120_000 * AVAX, timesteps=1, runs=1))
    assert path(room, "returning_nodes") == [1, 0] and path(room, "active_validators") == [1, 2]


def test_the_fitted_stake_lifecycle_funds_its_stakes_from_the_same_pool():
    # Twenty commitments of 2,000 AVAX renew at 4,000 each on day one beside a scheduled 79,000: the pool of 121,000 less
    # the scheduled stake leaves 42,000 for 80,000 of renewals, so ten renew in full, one takes the 2,000 left, nine leave.
    tight = model_on(supply0_navax=121_000 * AVAX).with_settings(arrivals=Arrivals(mean_per_day=0.0), returns=ReturnHazard(), timesteps=1, runs=1)
    table = run(tight)
    supply, stake = supply_and_stake(table)
    assert (stake <= supply).all()
    assert path(table, "active_validators")[1] == 12 and path(table, "returning_nodes")[1] == 1 + 9
    assert stake[1] == (10 * 4_000 + 2_000 + 79_000) * AVAX


def test_at_the_records_levels_the_limit_changes_nothing():
    # A synthetic run far from the limit returns the continuation stage's arrays unchanged, object for object.
    seen = []
    original = participation.cap_started

    def watching(state, day, earlier, started, n_renewed, n_back):
        out = original(state, day, earlier, started, n_renewed, n_back)
        seen.append(out["started"] is started and out["renews"] is earlier["renewal"]["renews"])
        return out

    participation.cap_started = watching
    try:
        from avalanche_research.model.parts import continuation
        continuation.cap_started = watching
        table = run(model(arrivals=Arrivals(mean_per_day=3.0, dispersion=1.0), renewal=RenewalLogit(), timesteps=30, runs=2))
    finally:
        participation.cap_started = original
        continuation.cap_started = original
    supply, stake = supply_and_stake(table)
    assert (stake / supply < 0.001).all() and len(seen) == 60 and all(seen)


# Delegations

def test_a_delegation_the_unstaked_supply_does_not_cover_is_unplaced():
    # Twenty delegations a day of up to 6,000 AVAX against 3,000 AVAX unstaked at the origin, on a counter near the cap
    # so that rewards stay small. Renewals keep the validators, so the pool is what the delegations leave.
    staked = (2 + 5 + 10 + 40 + 100 + 2) * 1_000 * AVAX + (500 + 1_000 + 25 + 50_000) * AVAX
    tight = delegated(delegation_flow=flowing(mean=20.0, share=0.0), arrivals=Arrivals(mean_per_day=0.0), renewal=RenewalLogit(intercept=20.0),
                      supply0_navax=staked + 3_000 * AVAX, timesteps=5, runs=1)
    table = wide(run(tight))
    assert (table["active_validator_stake_navax"] + table["active_delegated_stake_navax"] <= table["supply_navax"]).all()
    assert table["unplaced_delegations"].sum() > 0
    loose = wide(run(tight.with_settings(supply0_navax=SUPPLY)))
    assert loose["unplaced_delegations"].sum() == 0
    assert (loose["active_delegations"] >= table["active_delegations"]).all()
    assert (loose["active_delegations"] > table["active_delegations"]).any()
