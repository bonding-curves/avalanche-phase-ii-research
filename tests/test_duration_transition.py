"""The fitted transition between duration bands and its persistence benchmark."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from avalanche_research.core.clock import LOCKBOX_START
from avalanche_research.model.parts.duration_transition import (
    BAND_EDGES,
    BANDS,
    DurationTransition,
    duration_band,
    duration_moves,
    persistence_log_prob,
    persistence_matrix,
)
from avalanche_research.model.streams import Streams

LOCKBOX_US = int(LOCKBOX_START.timestamp() * 1_000_000)
BEFORE_US = LOCKBOX_US - 400 * 86_400_000_000
# One whole-day duration per band, and the day each band's record heaps at.
TYPICAL = np.array([14, 30, 90, 180, 365])


def _moves(matrix: np.ndarray, n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Synthetic moves: previous bands equally often, next bands from ``matrix``, each band at its typical day."""
    draws = np.random.default_rng(seed)
    previous = draws.integers(0, len(BANDS), n)
    cumulative = matrix.cumsum(axis=1)
    following = (draws.random(n)[:, None] > cumulative[previous]).sum(axis=1)
    return TYPICAL[previous], TYPICAL[np.minimum(following, len(BANDS) - 1)]


def _decided(n: int) -> np.ndarray:
    return np.full(n, BEFORE_US, dtype=np.int64)


def test_bands_are_closed_below_and_open_above():
    assert BAND_EDGES == (21, 45, 100, 200)
    days = np.array([1, 14, 20, 21, 44, 45, 99, 100, 199, 200, 365])
    assert duration_band(days).tolist() == [0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4]


def test_fit_recovers_a_known_matrix_from_synthetic_moves():
    truth = np.array([
        [0.80, 0.10, 0.05, 0.03, 0.02],
        [0.15, 0.70, 0.10, 0.03, 0.02],
        [0.05, 0.10, 0.75, 0.05, 0.05],
        [0.02, 0.03, 0.10, 0.80, 0.05],
        [0.01, 0.02, 0.02, 0.05, 0.90],
    ])
    previous, following = _moves(truth, 200_000, seed=11)
    block = DurationTransition.fit(previous, following, _decided(len(previous)), "synthetic moves")
    assert np.abs(block.matrix() - truth).max() < 0.01
    assert np.allclose(block.matrix().sum(axis=1), 1.0)


def test_every_fitted_cell_is_labelled_with_its_evidence():
    previous, following = _moves(persistence_matrix(0.2), 500, seed=3)
    block = DurationTransition.fit(previous, following, _decided(len(previous)), "synthetic moves")
    cells = {name: meta for name, meta in block.sources().items() if "_to_" in name}
    assert len(cells) == len(BANDS) ** 2
    assert {meta["source"] for meta in cells.values()} == {"fitted"}
    assert all(meta["evidence"].startswith("synthetic moves") for meta in cells.values())
    assert block.sources()["prior_strength"]["source"] == "fitted"


def test_log_prob_matches_a_hand_calculation():
    # Band 0 to band 0 twice and band 0 to band 1 once, with a prior of 2 moves at a floor of 0.2: the row from band 0
    # is the counts plus 2 times (0.8, 0.05, 0.05, 0.05, 0.05), over 3 + 2 moves. Band 2 has no moves, so it is the prior.
    block = DurationTransition.fit([14, 15, 14], [14, 14, 30], _decided(3), "hand", prior_strength=2.0, floor=0.2)
    row0 = (np.array([2, 1, 0, 0, 0]) + 2.0 * np.array([0.8, 0.05, 0.05, 0.05, 0.05])) / 5.0
    assert np.allclose(block.matrix()[0], row0)
    assert np.allclose(block.matrix()[2], [0.05, 0.05, 0.8, 0.05, 0.05])
    expected = np.log(row0[0]) + np.log(row0[1]) + np.log(0.05)
    assert block.log_prob({"previous_days": np.array([14, 20, 90])}, np.array([15, 21, 365])) == pytest.approx(expected)


def test_persistence_benchmark_puts_the_floor_on_a_change():
    assert np.allclose(persistence_matrix(0.01).diagonal(), 0.99)
    assert np.allclose(persistence_matrix(0.01).sum(axis=1), 1.0)
    expected = 2 * np.log(0.99) + np.log(0.0025)
    assert persistence_log_prob(np.array([14, 30, 90]), np.array([15, 31, 14])) == pytest.approx(expected)


def test_with_no_moves_the_block_is_persistence():
    block = DurationTransition.fit([], [], np.zeros(0, dtype=np.int64), "no moves", prior_strength=1e6, floor=0.01)
    assert np.allclose(block.matrix(), persistence_matrix(0.01))
    previous, following = np.array([14, 30, 90, 180, 365]), np.array([15, 14, 90, 365, 365])
    assert block.log_prob({"previous_days": previous}, following) == pytest.approx(persistence_log_prob(previous, following, 0.01))


def test_a_strong_persistence_prior_outweighs_the_moves():
    previous, following = _moves(np.full((5, 5), 0.2), 1_000, seed=5)
    block = DurationTransition.fit(previous, following, _decided(len(previous)), "uniform moves", prior_strength=1e9)
    assert np.abs(block.matrix() - persistence_matrix(block.floor)).max() < 1e-5


def test_fitting_refuses_moves_from_the_held_back_period():
    with pytest.raises(ValueError, match="2025-11-19"):
        DurationTransition.fit([14, 14], [14, 30], np.array([BEFORE_US, LOCKBOX_US]), "late")
    DurationTransition.fit([14, 14], [14, 30], np.array([BEFORE_US, LOCKBOX_US - 1]), "just before")


def _heaped_block() -> DurationTransition:
    record = np.array([14] * 300 + [15] * 500 + [16] * 50 + [28] * 100 + [30] * 200 + [31] * 60 + [60] * 40 + [90] * 80 + [182] * 30 + [365] * 120)
    previous = np.roll(record, 7)
    return DurationTransition.fit(previous, record, _decided(len(record)), "heaped moves")


def test_sampling_by_inversion_is_reproducible_and_keyed():
    block = _heaped_block()
    previous = np.tile([14, 30, 90, 365], 2_500)
    keys, done = np.arange(len(previous), dtype=np.int64), np.full(len(previous), 3)
    first = block.days_from_uniforms(previous, Streams(4, 0).uniforms("renew_days", keys, done))
    again = block.days_from_uniforms(previous, Streams(4, 0).uniforms("renew_days", keys, done))
    other = block.days_from_uniforms(previous, Streams(5, 0).uniforms("renew_days", keys, done))
    assert np.array_equal(first, again)
    assert not np.array_equal(first, other)
    u = np.linspace(0, 1, 1_001, endpoint=False)
    assert (np.diff(block.days_from_uniforms(np.full(len(u), 14), u)) >= 0).all()


def test_sampling_keeps_the_exact_day_heaps_of_each_band():
    block = _heaped_block()
    u = Streams(0, 0).uniforms("renew_days", np.arange(200_000, dtype=np.int64))
    days = block.days_from_uniforms(np.full(len(u), 14), u)
    assert set(np.unique(days)) <= {14, 15, 16, 28, 30, 31, 60, 90, 182, 365}
    short = days[days < 21]
    assert np.mean(short == 15) == pytest.approx(500 / 850, abs=0.01)
    bands = duration_band(days)
    assert np.mean(bands == 0) == pytest.approx(block.matrix()[0, 0], abs=0.005)


def test_sample_draws_through_the_generator_it_is_given():
    block = _heaped_block()
    previous = np.full(1_000, 30)
    first = block.sample({"previous_days": previous}, Streams(1, 2).generator("renew_days"))
    again = block.sample({"previous_days": previous}, Streams(1, 2).generator("renew_days"))
    assert np.array_equal(first, again)
    assert first.shape == (1_000,)


def test_an_empty_band_draws_its_default_day():
    block = DurationTransition.fit([14, 14], [14, 15], _decided(2), "short moves only", prior_strength=10.0, floor=0.5)
    # The row from band 0 is (7, 1.25, 1.25, 1.25, 1.25) / 12, so these uniforms fall in bands 0, 1, 2 and 4.
    days = block.days_from_uniforms(np.full(4, 14), np.array([0.0, 0.65, 0.75, 0.999]))
    assert duration_band(days).tolist() == [0, 1, 2, 4]
    assert days.tolist() == [14, 30, 90, 365]


def test_moves_are_taken_from_the_window_and_skip_overlaps():
    day = 86_400_000_000
    rows = pd.DataFrame({
        "days": [14, 30, 90, 15],
        "e": [10 * day, 50 * day, 200 * day, 300 * day],
        "next_s": [10 * day, 51 * day, 150 * day, np.nan],
        "next_e": [40 * day, 141 * day, 165 * day, np.nan],
    })
    moves = duration_moves(rows, 20 * day, 60 * day)
    assert moves["previous_days"].tolist() == [30]
    assert moves["next_days"].tolist() == [90]
    assert moves["decided_us"].tolist() == [51 * day]


def test_a_row_with_no_weight_is_refused_instead_of_giving_nan():
    """A transition row whose cells sum to zero has no distribution, so reading the matrix refuses it."""
    values = {name: 0.0 for name in DurationTransition().param.values() if "_to_" in name and name.startswith(BANDS[0] + "_")}
    with pytest.raises(ValueError):
        DurationTransition(**values).matrix()


@pytest.mark.parametrize("bad", [-2, 0, 366, 1.9])
def test_durations_outside_whole_days_from_1_to_365_are_refused(bad):
    """A duration is a whole number of days from 1 to 365. Anything else is refused when fitting and in a day record."""
    previous, following = np.array([30, 30, 14]), np.array([30, 14, 14])
    decided = np.full(3, 1_600_000_000_000_000)
    with pytest.raises(ValueError):
        DurationTransition.fit(np.append(previous, 30), np.append(following, bad), np.append(decided, decided[0]), "test")
    with pytest.raises(ValueError):
        DurationTransition.fit(previous, following, decided, "test").with_record(np.array([30, bad]))


def test_the_fit_records_the_hash_of_its_moves():
    """Every fitted value's evidence names the SHA-256 of the moves it was fitted on, so the same moves give the same
    record and other moves a different one."""
    previous, following = np.array([30, 30, 14]), np.array([30, 14, 14])
    decided = np.full(3, 1_600_000_000_000_000)
    first = DurationTransition.fit(previous, following, decided, "three moves").sources()
    again = DurationTransition.fit(previous, following, decided, "three moves").sources()
    other = DurationTransition.fit(previous, np.array([30, 30, 14]), decided, "three moves").sources()
    fitted = [name for name, record in first.items() if record["source"] == "fitted"]
    assert fitted and all("inputs sha256 " in first[name]["evidence"] for name in fitted)
    assert first == again and first[fitted[0]]["evidence"] != other[fitted[0]]["evidence"]
