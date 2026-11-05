"""The duration response (ML28, D35): off by default, a tilt of the duration transition's band probabilities by the
rate each band is offered."""

from __future__ import annotations

import numpy as np
import pytest
from test_duration_candidate import small_candidate
from test_delegated_lifecycle import final_states

from avalanche_research.mechanisms import GovernanceReward
from avalanche_research.model.engine import run
from avalanche_research.model.parts.duration_transition import BANDS


def test_a_zero_tilt_is_the_untilted_transition_and_a_large_one_draws_its_band():
    block = small_candidate().durations
    previous, u = np.array([14, 30, 90, 180, 365] * 20), np.linspace(0.001, 0.999, 100)
    assert np.array_equal(block.days_from_uniforms(previous, u, tilt=np.zeros(len(BANDS))), block.days_from_uniforms(previous, u))
    assert np.allclose(block.tilted(np.zeros(len(BANDS))), block.matrix())
    heavy = np.zeros(len(BANDS))
    heavy[-1] = 50.0
    assert (block.days_from_uniforms(previous, u, tilt=heavy) >= 200).all()
    with pytest.raises(ValueError, match="one finite log weight per band"):
        block.tilted(np.zeros(3))


def test_the_response_needs_the_durations_block_and_enters_the_specification_only_when_set():
    base = small_candidate()
    with pytest.raises(ValueError, match="durations block"):
        base.with_settings(durations=None, duration_response=0.5)
    assert "duration_response" not in base.specification()
    assert base.with_settings(duration_response=0.0).specification_hash() == base.specification_hash()
    assert base.with_settings(duration_response=0.5).specification_hash() != base.specification_hash()


def test_at_zero_strength_the_run_is_unchanged_and_under_the_chains_rule_any_strength_is():
    base = small_candidate()
    plain = run(base)
    assert run(base.with_settings(duration_response=0.0)).equals(plain)
    # Under the chain's rule every band's gap is zero, so the tilt is zero at any strength.
    assert np.allclose(base.with_settings(duration_response=2.0).duration_tilt(base.origin), 0.0)


def test_a_rule_that_pays_long_stakes_more_shifts_renewals_toward_longer_bands():
    rule = GovernanceReward(min_rate=0.10, max_rate=0.20)
    fixed = small_candidate(mechanism=rule)
    tilt = fixed.with_settings(duration_response=1.0).duration_tilt(fixed.origin)
    assert (np.diff(tilt) > 0).all()

    def weighted_days(model):
        last = final_states(model.with_settings(timesteps=120, runs=1)).iloc[-1]
        days, stakes = np.asarray(last["days"], dtype=float), np.asarray(last["stakes"], dtype=float)
        return float((days * stakes).sum() / stakes.sum())

    assert weighted_days(fixed.with_settings(duration_response=1.0)) > weighted_days(fixed)


def test_the_band_recorder_is_off_by_default_and_its_bands_sum_to_the_days_started_stake():
    from avalanche_research.model.fitted_lifecycle import BAND_VARIABLES

    base = small_candidate()
    assert not set(BAND_VARIABLES) & set(run(base)["variable"])
    assert base.with_settings(record_duration_bands=False).specification_hash() == base.specification_hash()
    table = run(base.with_settings(record_duration_bands=True, timesteps=60))
    wide = table.pivot_table(index=["run", "timestep"], columns="variable", values="value", aggfunc="first")
    assert (wide[list(BAND_VARIABLES)].sum(axis=1) == wide["started_stake_navax"]).all()
    assert wide["started_stake_navax"].sum() > 0


def test_a_sparse_row_under_a_large_finite_tilt_on_an_unreachable_band_still_sums_to_one():
    # RV05's witness: a row that reaches only its own band, under a tilt far larger on a band it cannot reach, must
    # keep its probability on the band it reaches.
    block = small_candidate().durations
    cells = {f"{a}_to_{b}": (1.0 if a == b else 0.0) for a in BANDS for b in BANDS}
    sparse = block.__class__(**{**{k: v for k, v in block.param.values().items() if k != "name"}, **cells})
    tilt = np.zeros(len(BANDS))
    tilt[-1] = 800.0
    tilted = sparse.tilted(tilt)
    assert np.isfinite(tilted).all() and np.allclose(tilted.sum(axis=1), 1.0)
    assert np.allclose(np.diag(tilted)[:-1], 1.0)
