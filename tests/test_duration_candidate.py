"""The duration band transition as a candidate in the fitted lifecycle.

The candidate ``v0.8 duration`` is v0.8 with one change: a node that renews or returns draws its next duration from
the fitted transition between duration bands, on the same keyed uniforms the continuation table reads, and its stake
still comes from the continuation table. The switch is the lifecycle's ``durations`` setting. At its default, None, it
is left out of the specification and the settings, so v0.8 keeps its specification hash and simulated table.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cadCAD")
pytest.importorskip("scipy")

from test_lifecycle_stages import (
    EXPECTED_SPECIFICATION_HASH as DRAWN_SPECIFICATION_HASH,
)
from test_lifecycle_stages import EXPECTED_TABLE_SHA256 as DRAWN_TABLE_SHA256
from test_lifecycle_stages import RECORDED_SPECIFICATION_HASH as DRAWN_RECORDED_HASH
from test_lifecycle_stages import drawn_lifecycle
from test_parts_split import (
    EXPECTED_SPECIFICATION_HASH,
    EXPECTED_TABLE_SHA256,
    RECORDED_SPECIFICATION_HASH,
    as_recorded,
    small_lifecycle,
    table_sha256,
)
from test_variant_switches import SCRIPT, differing, events_with_state

from avalanche_research.core.clock import LOCKBOX_START
from avalanche_research.model import variants
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_blocks import AVAX, Continuation
from avalanche_research.model.fitted_lifecycle import (
    FittedLifecycle,
    decided_by_us,
    fit_durations,
    resampled_tables,
)
from avalanche_research.model.parts.continuation import continuation_stage
from avalanche_research.model.parts.duration_transition import (
    BANDS,
    DurationTransition,
    fit_moves,
)
from avalanche_research.model.parts.stages import Day, RunBlocks
from avalanche_research.model.streams import PURPOSES, Streams
from avalanche_research.model.variants import DEVELOPMENT_MODELS, VARIANTS, Switches

LOCKBOX_US = int(LOCKBOX_START.timestamp() * 1_000_000)


def to_long_days() -> DurationTransition:
    """A transition that sends every node to 200 days or more, so its draws cannot be the continuation table's."""
    cells = {f"{a}_to_{b}": 1.0 if b == "d200_365" else 0.0 for a in BANDS for b in BANDS}
    return DurationTransition(**cells)


def stage_inputs(durations: DurationTransition | None):
    """One day of the continuation stage: three ending commitments of which two renew, two nodes out of the set of
    which one comes back, and no arrivals."""
    continuation = Continuation([14, 30, 30], [14, 30, 21], np.array([10, 50, 50]) * 1_000 * AVAX,
                                np.array([12, 45, 55]) * 1_000 * AVAX)
    blocks = RunBlocks(None, None, None, None, 0.0, continuation, np.array([14]), np.array([5_000 * AVAX]), durations)
    ended = {"node_key": np.array([3, 4, 5]), "done": np.array([2, 0, 6]), "stakes": np.array([10, 50, 40]) * 1_000 * AVAX,
             "days": np.array([14, 30, 90]), "returns": np.array([0, 1, 0])}
    state = {"out_node_key": np.array([8, 9]), "out_done": np.array([1, 4]), "out_stakes": np.array([20, 60]) * 1_000 * AVAX,
             "out_last_days": np.array([14, 180]), "out_returns": np.array([0, 2])}
    earlier = {"renewal": {"ended": ended, "renews": np.array([True, False, True])},
               "returns": {"comes_back": np.array([False, True])},
               "arrivals": {"count": 0, "node_key": np.zeros(0, dtype=np.int64)}}
    day = Day(t=0, start=datetime(2024, 3, 7, 12, tzinfo=UTC), draw=Streams(3, 1), blocks=blocks, renewal_gap=0.0,
              entry_gap=0.0, settings=None)
    return state, day, earlier


def test_the_candidate_stage_draws_durations_from_the_transition_and_stakes_from_continuation():
    transition = to_long_days().with_record([200, 300, 365, 365])
    table = continuation_stage(*stage_inputs(None))["started"]
    candidate = continuation_stage(*stage_inputs(transition))["started"]
    assert np.array_equal(candidate["stakes"], table["stakes"])
    assert np.array_equal(candidate["node_key"], table["node_key"]) and np.array_equal(candidate["done"], table["done"])

    draw = Streams(3, 1)
    renew_u = draw.uniforms("renew_days", np.array([3, 5]), np.array([2, 6]))
    return_u = draw.uniforms("return_days", np.array([9]), np.array([4]))
    expected = np.concatenate([transition.days_from_uniforms(np.array([14, 90]), renew_u),
                               transition.days_from_uniforms(np.array([180]), return_u)])
    assert candidate["days"].tolist() == expected.tolist()
    assert set(candidate["days"]) <= {200, 300, 365}
    assert set(table["days"]) <= {14, 21, 30}


def test_the_candidate_reads_no_new_stream_purpose():
    assert {"renew_days", "return_days"} <= set(PURPOSES)
    assert not any("duration" in name or "band" in name for name in PURPOSES)


def test_at_its_default_the_switch_leaves_v08_unchanged():
    for model, spec_hash, recorded, table in (
        (small_lifecycle(), EXPECTED_SPECIFICATION_HASH, RECORDED_SPECIFICATION_HASH, EXPECTED_TABLE_SHA256),
        (drawn_lifecycle(), DRAWN_SPECIFICATION_HASH, DRAWN_RECORDED_HASH, DRAWN_TABLE_SHA256),
    ):
        default = model.with_settings(durations=None)
        assert "durations" not in default.specification() and "durations" not in default.settings()
        assert default.specification_hash() == spec_hash
        assert table_sha256(as_recorded(run(default), recorded)) == table


def small_candidate(**settings) -> FittedLifecycle:
    base = small_lifecycle()
    durations = fit_moves(base.moves, decided_by_us(base.origin), "synthetic moves")
    return base.with_settings(durations=durations, **settings)


def test_the_switch_is_recorded_and_changes_the_run():
    base, candidate = small_lifecycle(), small_candidate()
    assert differing(base.specification(), candidate.specification()) == {"durations"}
    assert "durations" in candidate.settings()
    assert run(candidate).value.tolist() != run(base).value.tolist()


def test_the_candidate_draws_reproduce_on_keyed_streams():
    first, again, other = run(small_candidate()), run(small_candidate()), run(small_candidate(seed=8))
    assert first.equals(again)
    assert first.value.tolist() != other.value.tolist()


def test_with_draws_each_run_refits_the_transition_on_its_own_resample_of_the_moves():
    drawn = drawn_lifecycle()
    durations = fit_moves(drawn.moves, decided_by_us(drawn.origin), "synthetic moves")
    candidate = drawn.with_settings(durations=durations)
    blocks_for = candidate._blocks_by_run()
    for r in (1, 2, 3):
        seed = int(drawn.draws["resample_seed"].iloc[r - 1])
        moves, _ = resampled_tables(drawn.moves, drawn.first_commitments, seed, r)
        refit = fit_moves(moves, decided_by_us(drawn.origin), "resample")
        own = blocks_for(r).durations
        assert np.allclose(own.matrix(), refit.matrix())
        assert own.day_record.tolist() == sorted(moves["next_days"].tolist())
        assert own.sources()["d0_21_to_d0_21"]["evidence"].startswith(f"bootstrap draw {r}")
    assert run(candidate).equals(run(drawn.with_settings(durations=durations)))


def test_without_draws_every_run_reads_the_fitted_transition_with_the_moves_as_its_record():
    candidate = small_candidate()
    block = candidate._blocks_by_run()(1).durations
    assert np.allclose(block.matrix(), candidate.durations.matrix())
    assert block.day_record.tolist() == sorted(candidate.moves["next_days"].tolist())


def test_a_fit_on_moves_that_reach_the_held_back_period_is_refused():
    moves = pd.DataFrame({"previous_days": [14, 30], "next_days": [14, 30]})
    with pytest.raises(ValueError, match="2025-11-19"):
        fit_moves(moves, LOCKBOX_US, "late")
    fit_moves(moves, LOCKBOX_US - 1, "just before")
    assert decided_by_us(date(2025, 11, 18)) < LOCKBOX_US <= decided_by_us(date(2025, 11, 19))
    late = drawn_lifecycle().with_settings(origin=date(2025, 11, 19))
    late = late.with_settings(durations=fit_moves(late.moves, LOCKBOX_US - 1, "synthetic"))
    with pytest.raises(ValueError, match="2025-11-19"):
        late._blocks_by_run()(1)


def test_a_transition_with_its_own_day_record_is_refused():
    with pytest.raises(ValueError, match="day record"):
        small_lifecycle().with_settings(durations=to_long_days().with_record([365]))


@pytest.fixture
def synthetic_periods(monkeypatch):
    monkeypatch.setattr(variants, "training_events", lambda periods, origin, run: events_with_state())
    monkeypatch.setattr(variants, "window_sd", lambda periods, origin, renewal: (0.3, "synthetic"))


def test_the_candidate_is_registered_outside_the_development_scores():
    assert {"v0.8 duration", "v0.8 duration u"} <= set(VARIANTS)
    assert not {"v0.8 duration", "v0.8 duration u"} & set(DEVELOPMENT_MODELS)
    spec = importlib.util.spec_from_file_location("model_development_scores", SCRIPT)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    assert script.MODELS == DEVELOPMENT_MODELS
    assert variants.DURATION == Switches(duration_transition=True)


@pytest.mark.parametrize(("today", "candidate"), [("v0.8", "v0.8 duration"), ("v0.8 u", "v0.8 duration u")])
def test_the_candidate_variant_is_v08_with_the_fitted_transition(synthetic_periods, today, candidate):
    built, prepared = [], []
    for name in (today, candidate):
        variant = VARIANTS[name]
        prepared.append(variant.prepare("synthetic.parquet", events_with_state().origin, "synthetic", draws=3, draw_seed=4))
        built.append(variant.simulation(prepared[-1], seed=2, timesteps=20, runs=3, draws=prepared[-1].draws))
    assert differing(built[0].specification(), built[1].specification()) == {"durations"}
    if prepared[0].draws is not None:
        assert prepared[0].draws.equals(prepared[1].draws)
    events = events_with_state()
    fitted = fit_durations(events)
    assert np.allclose(built[1].durations.matrix(), fitted.matrix())
    assert built[1].durations.day_record is None
    assert {meta["source"] for name, meta in fitted.sources().items() if "_to_" in name} == {"fitted"}
    run(built[1])
