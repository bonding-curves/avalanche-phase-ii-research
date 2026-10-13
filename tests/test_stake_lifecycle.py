"""Stake-switch checks exercise the complete lifecycle policy and cadCAD run."""
import hashlib
from datetime import date

import numpy as np
import pandas as pd
import pytest

from avalanche_research.model.engine import _plain, run
from avalanche_research.model.fitted_blocks import Arrivals, RenewalLogit, ReturnHazard
from avalanche_research.model.fitted_lifecycle import FittedLifecycle
from avalanche_research.model.stake_lifecycle import (
    StakeLifecycle,
    fitted_stake_settings,
)

AVAX = 10**9
ORIGIN = date(2024, 3, 6)


def source_tables(multiplier=2):
    tables = {}
    for context in ("renewal", "return", "entry"):
        table = pd.DataFrame({
            "previous_stake_navax": np.full(100, 0 if context == "entry" else 2_000 * AVAX, dtype=np.int64),
            "next_days": np.full(100, 30, dtype=np.int64),
            "next_stake_navax": np.full(100, multiplier * 2_000 * AVAX, dtype=np.int64),
            "decided_us": np.full(100, 1_709_164_800_000_000, dtype=np.int64),
        })
        sha = hashlib.sha256(table.to_csv(index=False).encode()).hexdigest()
        table.attrs = {"context": context, "run": "synthetic", "origin": ORIGIN.isoformat(),
                       "window": "365 days", "sha256": sha,
                       "source": f"synthetic; origin {ORIGIN}; 365 days; sha256 {sha}"}
        tables[context] = table
    return tables


def inputs():
    initial = pd.DataFrame({"stakes": np.full(20, 2_000 * AVAX), "days_left": np.ones(20, dtype=np.int64),
                            "done": np.zeros(20, dtype=np.int64), "after_return": np.zeros(20, bool),
                            "days": np.full(20, 30), "handed_on": np.zeros(20, bool), "returns": np.zeros(20, dtype=np.int64)})
    out = pd.DataFrame({"out_stakes": [2_000 * AVAX], "out_days": [8], "out_done": [1],
                        "out_last_days": [30], "out_returns": [0]})
    scheduled = pd.DataFrame({"start_day": [1], "stakes": [79_000 * AVAX], "days": [60],
                              "done": [3], "after_return": [False], "returns": [1]})
    moves = pd.DataFrame({"previous_days": [30], "next_days": [30],
                          "previous_stake_navax": [2_000 * AVAX], "next_stake_navax": [2_000 * AVAX]})
    first = pd.DataFrame({"days": [30], "stake_navax": [2_000 * AVAX]})
    return {"origin": ORIGIN, "inputs_source": "synthetic", "initial": initial, "out_of_set": out,
                "scheduled": scheduled, "moves": moves, "first_commitments": first,
                "renewal": RenewalLogit(intercept=20), "returns": ReturnHazard(minimum_8_30=1),
                "arrivals": Arrivals(mean_per_day=3), "seed": 7, "timesteps": 5, "runs": 2}


def model_on(**extra):
    return StakeLifecycle(**inputs(), **fitted_stake_settings(source_tables(), ORIGIN, "synthetic"), **extra)


def step(model):
    state = {**model.initial_state(), "timestep": 0, "run": 1}
    policy = model.blocks()[0]["policies"]["lifecycle"]
    return policy({}, 0, [], state)


def test_off_gives_identical_specification_settings_and_complete_run():
    shared = inputs()
    base, off = FittedLifecycle(**shared), StakeLifecycle(**shared)
    assert base.specification() == off.specification()
    assert {k: _plain(v) for k, v in base.settings().items()} == {k: _plain(v) for k, v in off.settings().items()}
    pd.testing.assert_frame_equal(run(base), run(off))


def test_on_changes_whole_model_stake_and_issuance_without_other_first_day_signals():
    base, on = FittedLifecycle(**inputs()), model_on()
    original, changed = step(base), step(on)
    assert changed["stakes"].sum() > original["stakes"].sum()
    assert changed["issued_navax"] > original["issued_navax"]
    # The started commitments' stake and stake-days follow their stakes.
    assert changed["started_stake_navax"] > original["started_stake_navax"]
    assert changed["started_stake_days_navax"] > original["started_stake_days_navax"]
    for key in original.keys() - {"stakes", "issued_navax", "started_stake_navax", "started_stake_days_navax"}:
        np.testing.assert_equal(changed[key], original[key], err_msg=key)
    assert changed["stakes"][-1] == original["stakes"][-1] == 79_000 * AVAX
    before, after = run(base), run(on)
    before = before.loc[before.variable == "active_validator_stake_navax", "value"]
    after = after.loc[after.variable == "active_validator_stake_navax", "value"]
    assert not before.equals(after)


def test_original_csv_attrs_are_preserved_and_json_receipts_are_separate():
    tables = source_tables()
    before = {context: dict(table.attrs) for context, table in tables.items()}
    settings = fitted_stake_settings(tables, ORIGIN, "synthetic")
    assert before == {context: dict(table.attrs) for context, table in tables.items()}
    for context, receipt in settings["stake_fit_receipt"]["contexts"].items():
        assert receipt["producer_csv_sha256"] == before[context]["sha256"]
        assert receipt["ordered_json_sha256"] != before[context]["sha256"]
        assert receipt["ordered_json_sha256"] in receipt["stake_choice_evidence"]


def test_mutated_producer_rows_are_refused_before_fit():
    tables = source_tables()
    tables["renewal"].iloc[0, 2] += 1
    with pytest.raises(ValueError, match="changed after"):
        fitted_stake_settings(tables, ORIGIN, "synthetic")


def test_different_fit_changes_law_digest_and_whole_specification_hash():
    first = model_on()
    other = StakeLifecycle(**inputs(), **fitted_stake_settings(source_tables(3), ORIGIN, "synthetic"))
    assert first.stake_fit_sha256 != other.stake_fit_sha256
    assert first.specification_hash() != other.specification_hash()
    assert first.specification()["stake_choice"]["sources"] != other.specification()["stake_choice"]["sources"]


@pytest.mark.parametrize("call", [lambda model: model.blocks(), lambda model: model.specification(), lambda model: model.settings()])
def test_mutated_receipt_is_refused_before_execution_or_recording(call):
    model = model_on()
    model.stake_fit_receipt["contexts"]["renewal"]["producer_csv_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="changed after"):
        call(model)


def test_mutated_hidden_fitted_law_is_refused():
    model = model_on()
    model.stake_choice._entry_stakes = (2_000 * AVAX,)
    with pytest.raises(ValueError, match="changed after"):
        model.blocks()


def test_fixed_stake_law_supports_other_block_draws_and_labels_missing_stake_uncertainty():
    model = model_on(draws=pd.DataFrame({"renewal.intercept": [19.0, 18.0], "renewal_shift": [0.0, 0.1]}))
    assert "absent" in model.stake_fit_receipt["stake_parameter_uncertainty"]
    assert len(run(model)) > 0


def test_on_refuses_node_resample_bootstrap_instead_of_freezing_stake_uncertainty():
    with pytest.raises(ValueError, match="does not yet support resample_seed"):
        model_on(draws=pd.DataFrame({"resample_seed": [7, 8]}))


def test_explicit_point_estimate_keeps_duration_bootstrap_and_binds_limit(monkeypatch):
    import avalanche_research.model.fitted_lifecycle as lifecycle

    shared = inputs()
    shared["moves"] = shared["moves"].assign(node_code=0)
    shared["first_commitments"] = shared["first_commitments"].assign(node_code=0)
    draws = pd.DataFrame({"resample_seed": [7, 8], "renewal.intercept": [19., 18.]})
    seen = []

    def own_tables(moves, first, seed, run_number):
        seen.append((seed, run_number))
        return moves.assign(next_days=80), first.assign(days=80)

    monkeypatch.setattr(lifecycle, "resampled_tables", own_tables)
    model = StakeLifecycle(**shared, **fitted_stake_settings(source_tables(), ORIGIN, "synthetic"),
                           draws=draws, stake_point_estimate=True)
    blocks_for = model._blocks_by_run()
    first, second = blocks_for(1), blocks_for(2)
    assert seen == [(7, 1), (8, 2)]
    assert first.renewal.intercept == 19.
    assert second.renewal.intercept == 18.
    np.testing.assert_equal(first.continuation.next_days, [80])
    np.testing.assert_equal(first.first_days, [80])
    assert model.specification()["stake_point_estimate"] is True
    assert model.specification()["stake_uncertainty"] == "stake hurdle not resampled"
    assert step(model)["days"].max() == 80


def test_point_estimate_setting_is_explicit_in_digest_and_refuses_disabled_stake():
    enabled = model_on(stake_point_estimate=True)
    default = model_on()
    assert enabled.specification_hash() != default.specification_hash()
    with pytest.raises(ValueError, match="only with"):
        StakeLifecycle(**inputs(), stake_point_estimate=True)


def test_wrong_fit_origin_and_run_are_refused():
    settings = fitted_stake_settings(source_tables(), ORIGIN, "synthetic")
    changed = inputs()
    changed["origin"] = date(2024, 3, 7)
    with pytest.raises(ValueError, match="origin differs"):
        StakeLifecycle(**changed, **settings)
    changed = inputs()
    changed["inputs_source"] = "different run"
    with pytest.raises(ValueError, match="run differs"):
        StakeLifecycle(**changed, **settings)


def test_duration_is_drawn_first_and_existing_stake_uniforms_are_reused(monkeypatch):
    from avalanche_research.model.parts.continuation import Continuation
    from avalanche_research.model.streams import Streams

    model = model_on()
    calls, received = [], []
    original_days = Continuation.durations_from_uniforms
    original_stakes = model.stake_choice.stakes_from_uniforms

    def track_days(self, previous, u):
        calls.append("duration")
        return original_days(self, previous, u)

    def track_stakes(context, previous, days, u):
        calls.append("stake")
        received.append((context, previous.copy(), days.copy(), u.copy()))
        return original_stakes(context, previous, days, u)

    monkeypatch.setattr(Continuation, "durations_from_uniforms", track_days)
    monkeypatch.setattr(model.stake_choice, "stakes_from_uniforms", track_stakes)
    signal = step(model)
    assert calls == ["duration", "duration", "stake", "stake", "stake"]
    state = model.initial_state()
    stream = Streams(model.seed, 1)
    expected_renewal = stream.uniforms("renew_stake", state["node_key"], state["done"])
    expected_return = stream.uniforms("return_stake", state["out_node_key"], state["out_done"])
    new_keys = signal["node_key"][21:-1]
    expected_entry = stream.uniforms("first_stake", new_keys)
    assert [row[0] for row in received] == ["renewal", "return", "entry"]
    for row, expected in zip(received, (expected_renewal, expected_return, expected_entry)):
        np.testing.assert_equal(row[2], np.full(len(expected), 30))
        np.testing.assert_equal(row[3], expected)


@pytest.mark.parametrize("field,value", [("source", "stale"), ("window", ""), ("origin", "2024-03-07"), ("run", "other")])
def test_changed_producer_attrs_are_refused(field, value):
    tables = source_tables()
    tables["renewal"].attrs[field] = value
    with pytest.raises(ValueError, match="attrs"):
        fitted_stake_settings(tables, ORIGIN, "synthetic")


def test_model_import_does_not_load_registry_so_registry_can_import_the_switch():
    import os
    import subprocess
    import sys
    from pathlib import Path

    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    probe = ("import sys; import avalanche_research.model.stake_lifecycle; "
             "assert 'avalanche_research.model.variants' not in sys.modules")
    subprocess.run([sys.executable, "-c", probe], env=environment, check=True, capture_output=True)


def test_a_fitted_stake_lifecycle_pickles_with_its_law_read_only_and_runs_the_same():
    import pickle
    from types import MappingProxyType

    model = model_on()
    copy = pickle.loads(pickle.dumps(model))
    assert copy.specification_hash() == model.specification_hash()
    assert isinstance(copy.stake_choice._cells, MappingProxyType) and isinstance(copy.stake_choice._labels, MappingProxyType)
    assert copy.stake_choice._cells == model.stake_choice._cells and copy.stake_choice._labels == model.stake_choice._labels
    assert copy.stake_choice._entry_stakes == model.stake_choice._entry_stakes
    pd.testing.assert_frame_equal(run(copy), run(model))
