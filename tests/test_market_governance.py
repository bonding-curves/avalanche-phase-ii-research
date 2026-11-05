"""The supplementary sweep's new axes: the governance reward, its duration bounds, the market shifts, and its design."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_stake_lifecycle import inputs, model_on, step

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import m2_market_sweep_design as ms
import m2_sweep_design as m2

from avalanche_research import mechanisms
from avalanche_research.mechanisms import ACP285Ramp, GovernanceReward
from avalanche_research.model.designs import settings
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_blocks import Arrivals, RenewalLogit
from avalanche_research.model.fitted_lifecycle import FittedLifecycle
from avalanche_research.model.parts.stages import bounded_days
from avalanche_research.model.stake_lifecycle import StakeLifecycle

SUPPLY = 465_370_000 * 10**9
STARTS = [datetime(2025, 11, 19, 12, tzinfo=UTC), datetime(2026, 9, 23, 12, tzinfo=UTC), datetime(2027, 6, 1, 12, tzinfo=UTC)]


# Governance reward

@pytest.mark.parametrize("start", STARTS)
def test_governance_reward_at_the_chain_settings_is_the_rule_before_acp285_for_every_duration(start):
    governance, before = GovernanceReward(), ACP285Ramp(target_min_rate=0.10)
    for days in range(1, 366):
        assert governance.potential_reward_navax(10**15, days * 86_400, SUPPLY, start, 3) == \
            before.potential_reward_navax(10**15, days * 86_400, SUPPLY, start, 3)


def test_governance_rate_reaches_the_maximum_at_the_longest_commitment_and_holds_it():
    rule = GovernanceReward(min_rate=0.08, max_rate=0.16, min_days=30, max_days=200)
    start = STARTS[0]
    share = (720_000_000 * 10**9 - SUPPLY) / SUPPLY
    assert rule.annual_rate(200, SUPPLY, start) == pytest.approx(0.16 * share, rel=1e-6)
    assert rule.annual_rate(365, SUPPLY, start) == pytest.approx(0.16 * share, rel=1e-6)
    assert rule.annual_rate(100, SUPPLY, start) == pytest.approx((0.08 + 0.08 * 100 / 200) * share, rel=1e-6)
    assert rule.check(SUPPLY, start) == []
    assert rule.duration_bounds() == (30, 200)
    assert mechanisms.ChainReward().duration_bounds() is None


def test_governance_reward_refuses_a_maximum_below_its_minimum():
    with pytest.raises(ValueError, match="maximum rate"):
        GovernanceReward(min_rate=0.12, max_rate=0.10)
    with pytest.raises(ValueError, match="longest commitment"):
        GovernanceReward(min_days=200, max_days=100)


def test_bounded_days_moves_each_duration_to_the_nearer_bound_only_when_the_rule_sets_bounds():
    days = np.array([1, 14, 30, 200, 365])
    assert bounded_days(days, mechanisms.ChainReward()) is days
    assert bounded_days(days, GovernanceReward(min_days=20, max_days=180)).tolist() == [20, 20, 30, 180, 180]


@pytest.mark.parametrize("stake", [False, True])
def test_duration_bounds_apply_to_every_new_commitment_before_its_stake(stake):
    # Every open commitment ends on day one and renews, drawing 30 days from the moves; the bound lifts them to 60.
    build = (lambda **extra: model_on(**extra)) if stake else (lambda **extra: FittedLifecycle(**inputs(), **extra))
    free = step(build())
    bounded = step(build(mechanism=GovernanceReward(min_days=60, max_days=300)))
    assert (free["days"] == 30).any()
    assert (bounded["days"] >= 60).all()
    assert len(bounded["days"]) == len(free["days"])


# Market shifts

def test_market_shifts_at_zero_leave_the_specification_and_the_run_unchanged():
    base = model_on()
    zero = model_on(market_renewal_shift=0.0, market_entry_shift=0.0)
    assert base.specification_hash() == zero.specification_hash()
    assert "market_renewal_shift" not in base.specification()
    pd.testing.assert_frame_equal(run(base), run(zero))
    assert "market_renewal_shift" in model_on(market_renewal_shift=0.1).specification()


def test_the_renewal_shift_moves_renewals_in_its_direction():
    def renewed(shift):
        shared = {**inputs(), "renewal": RenewalLogit(intercept=0.0), "runs": 1}
        model = StakeLifecycle(**shared, market_renewal_shift=shift)
        signal = step(model)
        return len(signal["stakes"])
    assert renewed(-4.0) < renewed(0.0) < renewed(4.0)


def test_the_entry_shift_scales_first_ever_arrivals():
    def arrived(shift):
        shared = {**inputs(), "arrivals": Arrivals(mean_per_day=5), "timesteps": 20, "runs": 1}
        table = run(StakeLifecycle(**shared, market_entry_shift=shift))
        return table[table["variable"] == "active_validators"]["value"].sum()
    assert arrived(-2.0) < arrived(0.0) < arrived(2.0)


def test_measured_market_shifts_have_the_signs_history_shows():
    renewal_bull, entry_bull = ms.SHIFTS["bull"]
    renewal_bear, _ = ms.SHIFTS["bear"]
    assert renewal_bull > 0 > renewal_bear and entry_bull > 0
    assert ms.SHIFTS["neutral"] == (0.0, 0.0)
    assert ms.market_shifts("bear", 0.5) == (0.5 * renewal_bear, 0.5 * ms.SHIFTS["bear"][1])


# Design

@pytest.fixture(scope="module")
def m2_design():
    rows, labels, _ = m2.build("v0.8-a u", 4.144417670682732)
    return rows, labels


@pytest.fixture(scope="module")
def design(m2_design):
    return ms.build(4.144417670682732, *m2_design)


def test_the_design_counts_keys_and_pairing_are_exact(design):
    rows, labels, new_keys, aliases = design
    assert new_keys == 2 * ms.N_S + 12 * ms.F_KEYS + ms.CONTROL_KEYS
    blocks = ms.counts(labels)
    for alias in aliases:
        blocks[alias["block"]] += 1
    assert blocks["AB"] == blocks["BA"] == ms.N_S * len(ms.GOVERNANCE_INPUTS)
    assert blocks["F"] == 12 * ms.F_KEYS * 4 and blocks["X"] == ms.BRIDGE_ROWS
    assert all(row["seed"] == row["draw"] + 1 for row in rows)
    assert len(rows) < 80_000


def test_the_bridge_copies_milestone_2_rows_on_keys_no_new_row_uses(design, m2_design):
    rows, labels, new_keys, _ = design
    for row, label in zip(rows, labels):
        if label["block"].startswith("X"):
            assert row == m2_design[0][label["m2_index"]] and row["draw"] >= new_keys
        else:
            assert row["draw"] < new_keys


def test_every_market_row_carries_its_market_and_strength_shifts(design):
    rows, labels, _, _ = design
    markets = {label["market"] for label in labels}
    assert markets == set(ms.MARKETS)
    for row, label in zip(rows, labels):
        if not label["block"].startswith("X"):
            assert (row["market_renewal_shift"], row["market_entry_shift"]) == ms.market_shifts(label["market"], label["market_strength"])


def test_aliases_are_only_saltelli_hybrids_that_repeat_their_own_points_row(design):
    rows, labels, _, aliases = design
    assert aliases, "a discrete column swap must sometimes land on the same row"
    for alias in aliases:
        assert alias["block"] in ("AB", "BA") and alias["j"] in (3, 4, 7, 8, 9)
        assert labels[alias["index"]]["i"] == alias["i"]


def test_every_row_setting_is_a_model_setting_and_every_mechanism_builds(design):
    rows, _, _, _ = design
    known = set(StakeLifecycle.param)
    from avalanche_research.model.runner import model_settings
    for row in rows[:: 97]:
        assert set(settings(row)) - {"draw"} <= known
        assert isinstance(model_settings(row)["mechanism"], mechanisms.RewardMechanism)


def test_the_design_repeats_byte_for_byte(design, m2_design):
    again = ms.build(4.144417670682732, *m2_design)
    assert m2.rows_bytes(again[0]) == m2.rows_bytes(design[0])
    assert ms.labels_bytes(again[1]) == ms.labels_bytes(design[1])
    assert json.dumps(again[3]) == json.dumps(design[3])
