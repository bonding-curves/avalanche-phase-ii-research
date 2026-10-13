"""The v0.8 candidates a, c and e as switches on today's code.

The three candidates differ in three choices: whether the renewal logit reads the node's own renewal record, the
stake bands within which a moving node draws its stake ratio, and whether each move in that draw is weighted by its
previous stake. v0.8-a has no node record and draws unweighted within the return block's three stake bands. v0.8-c adds
the node record and the weight. v0.8-e draws within ten log-spaced bands, and is today's v0.8.

Each switch must change only its own part of the specification, and v0.8-e must be today's v0.8 byte for byte: the
same specification hash and the same simulated table as recorded before the switches existed.
"""

from __future__ import annotations

import importlib.util
from dataclasses import fields, replace
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("cadCAD")
pytest.importorskip("scipy")

from test_lifecycle_stages import (
    EXPECTED_SPECIFICATION_HASH as DRAWN_SPECIFICATION_HASH,
)
from test_lifecycle_stages import EXPECTED_TABLE_SHA256 as DRAWN_TABLE_SHA256
from test_lifecycle_stages import RECORDED_SPECIFICATION_HASH as DRAWN_RECORDED_HASH
from test_lifecycle_stages import drawn_lifecycle
from test_parameter_draws import synthetic_events
from test_parts_split import (
    EXPECTED_SPECIFICATION_HASH,
    EXPECTED_TABLE_SHA256,
    RECORDED_SPECIFICATION_HASH,
    as_recorded,
    small_lifecycle,
    table_sha256,
)

from avalanche_research.model import variants
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_blocks import (
    AVAX,
    MOVE_STAKE_EDGES,
    RENEWAL_TERMS,
    RETURN_STAKE_EDGES,
    Continuation,
    RenewalLogit,
    _newton,
    renewal_design,
)
from avalanche_research.model.fitted_lifecycle import (
    FittedLifecycle,
    fit_blocks,
    parameter_draws,
    renewal_inputs,
)
from avalanche_research.model.variants import (
    CANDIDATES,
    COMBINED_ON_A,
    DEVELOPMENT_MODELS,
    ON_A,
    VARIANTS,
    Switches,
    switched_inputs,
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "model_development_scores.py"


def events_with_state():
    """Synthetic training events with the small lifecycle's state and moves, so a stake switch changes the run."""
    base = small_lifecycle()
    moves = base.moves.assign(node_code=[0, 0, 1, 2, 2, 3, 4])
    first = base.first_commitments.assign(node_code=[5, 6, 7])
    state = {"initial": base.initial, "out_of_set": base.out_of_set, "scheduled": base.scheduled, "supply0_navax": base.supply0_navax}
    return replace(synthetic_events(), moves=moves, first_commitments=first, state=state)


def specification(switches: Switches) -> dict:
    return FittedLifecycle(**switched_inputs(events_with_state(), switches)).specification()


def differing(a: dict, b: dict) -> set[str]:
    return {k for k in a.keys() | b.keys() if a.get(k, "absent") != b.get(k, "absent")}


@pytest.fixture
def synthetic_periods(monkeypatch):
    """The variants read the synthetic events in place of a staking-periods file."""
    monkeypatch.setattr(variants, "training_events", lambda periods, origin, run: events_with_state())
    monkeypatch.setattr(variants, "window_sd", lambda periods, origin, renewal: (0.3, "synthetic"))


def test_the_candidates_are_registered_and_the_development_scores_run_the_four_variants_as_before():
    assert DEVELOPMENT_MODELS == ("v0.7", "v0.8", "v0.8 separate", "v0.8 u")
    assert list(VARIANTS) == [*DEVELOPMENT_MODELS, "v0.8-a", "v0.8-a u", "v0.8-c", "v0.8-c u", "v0.8-e", "v0.8-e u",
                              "v0.8-a record", "v0.8-a record u", "v0.8-a bands", "v0.8-a bands u",
                              "v0.8-a duration", "v0.8-a duration u", "v0.8-a bands return", "v0.8-a bands return u",
                              "v0.8 duration", "v0.8 duration u", "v0.8-a return", "v0.8-a return u", "v0.8-a stake",
                              "v0.8-a stake u", "v0.8-a stake return", "v0.8-a stake return u", "v0.8.1 stub"]
    spec = importlib.util.spec_from_file_location("model_development_scores", SCRIPT)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    assert script.MODELS == DEVELOPMENT_MODELS


def test_the_candidates_set_their_three_switches():
    assert CANDIDATES == {
        "v0.8-a": Switches(node_record=False, move_stake_bands="three", move_stake_weighted=False),
        "v0.8-c": Switches(node_record=True, move_stake_bands="three", move_stake_weighted=True),
        "v0.8-e": Switches(node_record=True, move_stake_bands="ten log-spaced", move_stake_weighted=True),
    }
    assert CANDIDATES["v0.8-e"] == Switches()


def test_the_candidates_on_a_each_change_one_switch():
    a = CANDIDATES["v0.8-a"]
    assert ON_A == {
        "v0.8-a record": Switches(node_record=True, move_stake_bands="three", move_stake_weighted=False),
        "v0.8-a bands": Switches(node_record=False, move_stake_bands="ten log-spaced", move_stake_weighted=False),
        "v0.8-a duration": Switches(node_record=False, move_stake_bands="three", move_stake_weighted=False,
                                    duration_transition=True),
    }
    for switches in ON_A.values():
        assert sum(getattr(switches, field) != getattr(a, field) for field in vars(a)) == 1


def test_v08e_switches_give_the_recorded_specification_hash_and_table():
    """The hashes were recorded before the switches existed."""
    e = CANDIDATES["v0.8-e"].settings()
    small = small_lifecycle().with_settings(**e)
    assert small.specification_hash() == EXPECTED_SPECIFICATION_HASH
    assert table_sha256(as_recorded(run(small), RECORDED_SPECIFICATION_HASH)) == EXPECTED_TABLE_SHA256
    drawn = drawn_lifecycle().with_settings(**e)
    assert drawn.specification_hash() == DRAWN_SPECIFICATION_HASH
    assert table_sha256(as_recorded(run(drawn), DRAWN_RECORDED_HASH)) == DRAWN_TABLE_SHA256


@pytest.mark.parametrize(("today", "candidate"), [("v0.8", "v0.8-e"), ("v0.8 u", "v0.8-e u")])
def test_v08e_builds_todays_v08_byte_for_byte(synthetic_periods, today, candidate):
    built = []
    for name in (today, candidate):
        variant = VARIANTS[name]
        prepared = variant.prepare("synthetic.parquet", events_with_state().origin, "synthetic", draws=3, draw_seed=4)
        built.append(variant.simulation(prepared, seed=2, timesteps=20, runs=3, draws=prepared.draws))
    assert built[0].specification() == built[1].specification()
    assert built[0].specification_hash() == built[1].specification_hash()
    assert run(built[0]).equals(run(built[1]))


@pytest.mark.parametrize(("switch", "value", "changed"), [
    ("node_record", False, {"renewal"}),
    ("move_stake_bands", "three", {"move_stake_bands"}),
    ("move_stake_weighted", False, {"move_stake_weighted"}),
])
def test_each_switch_changes_only_its_part_of_the_specification(switch, value, changed):
    assert differing(specification(Switches()), specification(replace(Switches(), **{switch: value}))) == changed


def test_the_candidates_differ_only_in_their_switched_parts():
    a, c, e = (specification(CANDIDATES[name]) for name in ("v0.8-a", "v0.8-c", "v0.8-e"))
    assert differing(a, c) == {"renewal", "move_stake_weighted"}
    assert differing(c, e) == {"move_stake_bands"}
    assert {"move_stake_bands", "move_stake_weighted"}.isdisjoint(e)


def test_without_the_node_record_the_renewal_fit_drops_exactly_that_term():
    events = events_with_state()
    ended = events.endings
    with_record = renewal_inputs(ended)
    without = renewal_inputs(ended, node_record=False)
    assert set(with_record) - set(without) == {"returns"}
    assert all(np.array_equal(without[k], with_record[k]) for k in without)

    renewal = fit_blocks(events, node_record=False)["renewal"]
    design = renewal_design(ended["done"], ended["after_return"], ended["days"], ended["stake_navax"])
    beta, _ = _newton(design[:, :-1], ended["renewed"].to_numpy().astype(float), 1.0)
    assert design.shape[1] - 1 == 12 == len(RENEWAL_TERMS) - 1
    assert np.array_equal(renewal.coefficients()[:-1], np.clip(beta, -20.0, 20.0))
    assert renewal.node_record == 0.0
    assert renewal.node_prior_strength == RenewalLogit.param["node_prior_strength"].default
    assert "node record left out" in renewal.sources()["node_record"]["evidence"]
    # A node's record cannot move a block fitted without it.
    assert np.array_equal(renewal.probability(with_record), renewal.probability(without))

    record = fit_blocks(events)["renewal"]
    assert record.node_record != 0.0
    assert not np.allclose(record.coefficients()[:-1], renewal.coefficients()[:-1])


def test_draws_without_the_node_record_resample_the_same_nodes_and_draw_nothing_new():
    events = events_with_state()
    on = parameter_draws(events, n=3, seed=4, tau=0.3)
    off = parameter_draws(events, n=3, seed=4, tau=0.3, node_record=False)
    assert list(on.columns) == list(off.columns)
    assert (off["renewal.node_record"] == 0.0).all() and (on["renewal.node_record"] != 0.0).all()
    shared = [c for c in on.columns if not c.startswith("renewal.")]
    assert on[shared].equals(off[shared])


def test_the_stake_bands_and_the_weight_choose_which_move_a_uniform_picks():
    previous = np.array([3_000, 50_000, 50_000]) * AVAX
    after = np.array([30_000, 45_000, 55_000]) * AVAX
    query = np.full(3, 50_000 * AVAX)
    u = np.array([0.05, 0.45, 0.9])

    def stakes(edges, weighted):
        return Continuation([14] * 3, [14] * 3, previous, after, stake_edges=edges, stake_weighted=weighted).stakes_from_uniforms(query, u)

    # Ten bands: 3,000 AVAX is in its own band, so a 50,000 AVAX node draws only from the two 50,000 AVAX moves.
    assert (stakes(MOVE_STAKE_EDGES, True) // AVAX).tolist() == [45_000, 45_000, 55_000]
    # Three bands, weighted: the 3,000 AVAX move holds 3/103 of the weight.
    assert (stakes(RETURN_STAKE_EDGES, True) // AVAX).tolist() == [45_000, 45_000, 55_000]
    # Three bands, unweighted: each move holds a third.
    assert (stakes(RETURN_STAKE_EDGES, False) // AVAX).tolist() == [500_000, 45_000, 55_000]
    default = Continuation([14] * 3, [14] * 3, previous, after)
    assert default.stake_edges == MOVE_STAKE_EDGES and default.weight is not None


@pytest.mark.parametrize("settings", [{"move_stake_bands": "three"}, {"move_stake_weighted": False}])
def test_a_stake_switch_is_recorded_and_changes_the_run(settings):
    base = small_lifecycle()
    switched = base.with_settings(**settings)
    assert set(settings) <= set(switched.specification()) and set(settings) <= set(switched.settings())
    assert not set(settings) & set(base.specification()) and not set(settings) & set(base.settings())
    def stake(table):
        return table[table.variable == "active_validator_stake_navax"].value.tolist()

    assert stake(run(switched)) != stake(run(base))


def test_an_unknown_stake_band_set_is_refused():
    with pytest.raises(ValueError):
        small_lifecycle().with_settings(move_stake_bands="nine")
    assert set(FittedLifecycle.param["move_stake_bands"].objects) == {"ten log-spaced", "three"}
    assert [f.name for f in fields(Switches)] == ["node_record", "move_stake_bands", "move_stake_weighted", "duration_transition",
                                              "return_history"]


def test_the_combined_candidate_on_a_holds_the_ten_bands_and_the_return_hazard_and_nothing_else():
    assert COMBINED_ON_A == {
        "v0.8-a bands return": Switches(node_record=False, move_stake_bands="ten log-spaced", move_stake_weighted=False,
                                        return_history=True),
    }
