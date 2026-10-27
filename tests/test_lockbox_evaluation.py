"""Independent clock, fixed-fit, source and scoring fixtures. No protected data or token issuance."""
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest
from test_stake_lifecycle import ORIGIN, model_on

from avalanche_research.core.errors import ModelError
from avalanche_research.model import lockbox_evaluation as subject
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_lifecycle import origin_state, training_events
from avalanche_research.model.variants import Prepared


def parquet(path, rows):
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    with duckdb.connect() as connection:
        connection.register("fixture", frame)
        connection.execute("COPY fixture TO ? (FORMAT PARQUET)", [str(path)])
    return path


def public_periods():
    def row(node, tx, start, end, accepted):
        return {"role": "validator", "node_id": node, "transaction_hash": tx, "stake_navax": 2_000 * 10**9,
                "start_time": datetime.fromisoformat(start), "end_time": datetime.fromisoformat(end),
                "accepted_at": datetime.fromisoformat(accepted), "supply_before_navax": 450_000_000 * 10**9}
    return [row("a", "a0", "2024-02-01", "2024-03-09", "2024-01-31"),
            row("b", "b0", "2024-01-01", "2024-02-10", "2023-12-31"),
            row("a", "a1", "2024-03-09", "2024-03-23", "2024-03-01")]


@pytest.fixture
def periods(tmp_path):
    return parquet(tmp_path / "periods.parquet", public_periods())


def test_public_state_has_hand_computed_pending_and_lapsed_nodes(periods):
    state = origin_state(str(periods), ORIGIN)
    initial, out, scheduled = (state[k] for k in ("initial", "out_of_set", "scheduled"))
    assert initial.to_dict("records") == [{"stakes": 2_000 * 10**9, "days_left": 3, "done": 0,
                                          "after_return": False, "days": 37, "handed_on": True, "returns": 0}]
    assert out.to_dict("records") == [{"out_stakes": 2_000 * 10**9, "out_days": 25, "out_done": 1,
                                      "out_last_days": 40, "out_returns": 0}]
    assert scheduled.to_dict("records") == [{"start_day": 3, "stakes": 2_000 * 10**9, "days": 14,
                                            "done": 1, "after_return": False, "returns": 0}]
    assert state["transactions"]["initial"].tolist() == ["a0"]
    assert state["transactions"]["scheduled"].tolist() == ["a1"]
    assert state["supply0_navax"] == 450_000_000 * 10**9


def test_new_reader_matches_released_training_state_on_admitted_rows(periods):
    legacy, current = training_events(str(periods), ORIGIN).state, origin_state(str(periods), ORIGIN)
    for key in ("initial", "out_of_set", "scheduled"):
        pd.testing.assert_frame_equal(current[key], legacy[key])
    assert current["supply0_navax"] == legacy["supply0_navax"]


def test_unaccepted_rows_cannot_change_origin_state(periods, tmp_path):
    rows = public_periods()
    rows.append({**rows[0], "node_id": "unpublished", "transaction_hash": "late",
                 "start_time": datetime(2024, 3, 5), "accepted_at": datetime(2024, 3, 7)})
    other = parquet(tmp_path / "later.parquet", rows)
    before, after = (origin_state(str(p), ORIGIN) for p in (periods, other))
    for name in ("initial", "out_of_set", "scheduled"):
        pd.testing.assert_frame_equal(before[name], after[name])


def test_missing_acceptance_clock_is_not_silently_admitted(tmp_path):
    rows = public_periods()
    rows[0]["accepted_at"] = None
    with pytest.raises(ValueError, match="public clock"):
        origin_state(str(parquet(tmp_path / "missing.parquet", rows)), ORIGIN)


@pytest.mark.parametrize("token", [None, object(), "not a token"])
def test_protected_request_is_refused_before_any_file_is_opened(token, monkeypatch):
    monkeypatch.setattr(subject, "ROOT", Path("/no-config-or-data-can-be-opened"))
    with pytest.raises(ModelError, match="Unseal"):
        subject.score(token, fit_until=date(2025, 11, 19), score_until=date(2026, 9, 22))


def test_protected_state_refuses_before_querying_nonexistent_path():
    with pytest.raises(ModelError):
        origin_state("/nonexistent", date(2025, 11, 19))


@pytest.mark.parametrize(("fit", "end"), [(date(2025, 11, 20), date(2025, 11, 21)),
                                          (date(2024, 1, 1), date(2024, 1, 1)),
                                          (datetime(2024, 1, 1, 16, tzinfo=UTC), date(2024, 2, 1))])
def test_wrong_cut_or_clock_grain_is_refused(fit, end):
    with pytest.raises(ValueError):
        subject.request_window(fit, end, None)


def test_exclusive_development_cut_stays_before_the_first_protected_day():
    fit_origin, end = subject.request_window(date(2024, 12, 16), date(2025, 11, 19), None)
    assert fit_origin == date(2024, 12, 15)
    assert end == datetime(2025, 11, 19, tzinfo=UTC)


def test_fixed_stake_origin_preserves_receipt_and_default_mechanics():
    base = model_on()
    explicit = model_on(stake_fit_origin=ORIGIN)
    assert "stake_fit_origin" not in base.specification()
    assert base.stake_fit_receipt == explicit.stake_fit_receipt
    columns = ["run", "timestep", "variable", "value"]
    pd.testing.assert_frame_equal(run(base)[columns], run(explicit)[columns])
    later = explicit.with_settings(origin=ORIGIN + timedelta(days=2))
    assert later.stake_fit_receipt == base.stake_fit_receipt
    assert later.stake_fit_sha256 == base.stake_fit_sha256
    assert later.origin != later.stake_fit_origin


def test_later_origin_needs_an_explicit_unchanged_fit_binding():
    with pytest.raises(ValueError, match="origin differs"):
        model_on().with_settings(origin=ORIGIN + timedelta(days=1))
    with pytest.raises(ValueError, match="no later"):
        model_on(stake_fit_origin=ORIGIN + timedelta(days=1))
    model = model_on(stake_fit_origin=ORIGIN)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        model.with_settings(stake_fit_sha256="0" * 64)
    from avalanche_research.model.stake_lifecycle import StakeLifecycle
    with pytest.raises(ValueError, match="fitted_stake=True"):
        StakeLifecycle(stake_fit_origin=ORIGIN)


def test_replacing_state_does_not_refresh_blocks_or_empirical_tables(periods):
    model = model_on()
    prepared = Prepared({k: v for k, v in model.param.values().items() if k not in ("name", "seed", "runs", "timesteps", "draws")},
                        pd.DataFrame({"renewal_shift": [0.0, 0.0]}))
    before = subject.frozen_fingerprint(prepared)
    advanced = subject.at_origin(prepared, origin_state(str(periods), ORIGIN + timedelta(days=1)), ORIGIN + timedelta(days=1), ORIGIN)
    for key in ("renewal", "returns", "arrivals", "moves", "first_commitments", "stake_choice", "stake_fit_receipt"):
        assert advanced.inputs[key] is prepared.inputs[key]
    assert advanced.draws is prepared.draws
    assert subject.frozen_fingerprint(prepared) == before


def test_slice_equality_checks_rows_not_just_pin_hashes(periods, tmp_path):
    assert subject.matching_training_slices(periods, periods, ORIGIN)["rows"] == 3
    rows = public_periods()
    rows[0]["end_time"] += timedelta(days=1)
    other = parquet(tmp_path / "different.parquet", rows)
    with pytest.raises(ValueError, match="slices differ"):
        subject.matching_training_slices(periods, other, ORIGIN)
    future = {**rows[0], "transaction_hash": "later", "node_id": "later", "accepted_at": datetime(2024, 3, 8)}
    unchanged = parquet(tmp_path / "future.parquet", [*public_periods(), future])
    assert subject.matching_training_slices(periods, unchanged, ORIGIN)["status"] == "PASS"


def test_duplicate_projection_identity_refuses_even_if_both_files_agree(tmp_path):
    rows = public_periods()
    path = parquet(tmp_path / "duplicate.parquet", [*rows, rows[0]])
    with pytest.raises(ValueError, match="unique"):
        subject.matching_training_slices(path, path, ORIGIN)


def test_future_start_counter_is_not_an_at_fit_projection_feature(periods, tmp_path):
    rows = public_periods()
    rows[-1]["supply_before_navax"] += 10**12  # Accepted schedule is known; later-start counter is not used at the fit cut.
    later_counter = parquet(tmp_path / "later-counter.parquet", rows)
    assert subject.matching_training_slices(periods, later_counter, ORIGIN)["status"] == "PASS"


def test_projection_sorts_use_distinct_temporary_directories(periods, tmp_path, monkeypatch):
    other = tmp_path / "copy.parquet"
    other.write_bytes(periods.read_bytes())
    original = subject.duckdb.connect
    settings = []
    def connect(*args, **kwargs):
        settings.append(dict(kwargs["config"]))
        return original(*args, **kwargs)
    monkeypatch.setattr(subject.duckdb, "connect", connect)
    assert subject.matching_training_slices(periods, other, ORIGIN)["status"] == "PASS"
    assert len(settings) == 2
    assert settings[0]["temp_directory"] != settings[1]["temp_directory"]
    assert all(x["memory_limit"] == "512MB" and x["threads"] == 2 for x in settings)
    assert all(not Path(x["temp_directory"]).exists() for x in settings)


def test_legacy_fit_inputs_need_an_acceptance_check_separate_from_slice_equality(tmp_path):
    rows = public_periods()
    rows[0]["accepted_at"] = datetime(2024, 3, 7)  # Start precedes fit cut but acceptance is later.
    path = parquet(tmp_path / "unavailable-at-fit.parquet", rows)
    assert subject.matching_training_slices(path, path, ORIGIN)["status"] == "PASS"
    with pytest.raises(ValueError, match="fit-eligible"):
        subject.validate_training_information(path, ORIGIN)


def test_admitted_training_information_passes_before_any_reconstruction(periods):
    assert subject.validate_training_information(periods, ORIGIN)["status"] == "PASS"


def test_mase_crps_and_comparators_have_hand_computed_values():
    series = pd.Series(100 + np.arange(301), index=pd.date_range("2023-01-01", periods=301))
    origin = series.index[200].date()
    # The registered 200-draw design uses the ordinary sample CRPS: 1 - 0.5 = 0.5.
    rows = {x["forecast"]: x for x in subject.cell_scores([329.0, 331.0] * 100, 330.0, series, origin, 30)}
    assert set(rows) == {"model", "N1", "N2", "N3", "N1d", "N2d"}
    assert rows["model"]["mase"] == 0.0
    assert rows["model"]["crps"] == pytest.approx(0.5)
    assert rows["N1"]["mase"] == 30.0
    assert rows["N2"]["mase"] == 0.0
    assert rows["N1d"]["crps"] == pytest.approx(0.0, abs=1e-10)
    # Existing distribution_scores applies the fair correction below100 draws: 1 - 1 = 0.
    tiny = subject.cell_scores([329.0, 331.0], 330.0, series, origin, 30)
    assert tiny[0]["crps"] == 0.0


def test_constant_scaling_and_correlation_are_explicitly_undefined():
    series = pd.Series(2.0, index=pd.date_range("2023-01-01", periods=301))
    rows = subject.cell_scores([2.0, 2.0], 2.0, series, series.index[200].date(), 30)
    assert all(x["crps"] is None and x["undefined_reason"] for x in rows)
    diagnostics = subject.contract_diagnostics(np.ones(90), np.ones(90))
    assert diagnostics["pearson_levels"] is None
    assert diagnostics["pearson_first_differences"] is None
    assert diagnostics["rmse"] == 0.0
    assert diagnostics["undefined_reason"]
    json.dumps(subject._json(rows), allow_nan=False)


def test_point_loss_cannot_pass_by_dropping_a_bad_or_undefined_benchmark():
    cells = []
    for index, origin in enumerate(pd.date_range("2023-01-01", periods=8, freq="MS")):
        for forecast, loss in (("model", 1.0), ("N1", 2.0), ("N2", 2.0), ("N3", 1.0)):
            cells.append({"origin": origin.date().isoformat(), "variable": "x", "horizon_days": 90,
                          "forecast": forecast, "mase": loss})
    assert subject.primary_verdict(cells, ["x"])[0] == "FAIL"
    for cell in cells:
        if cell["forecast"] == "N3":
            cell["mase"] = None
    verdict, rows = subject.primary_verdict(cells, ["x"])
    assert verdict == "INCONCLUSIVE"
    assert next(x for x in rows if x["benchmark"] == "N3")["undefined_reason"]


@pytest.mark.parametrize("corruption", ["missing", "duplicate"])
def test_primary_inventory_never_intersects_away_a_missing_case(corruption):
    origins = [x.date().isoformat() for x in pd.date_range("2023-01-01", periods=8, freq="MS")]
    cells = [{"origin": origin, "variable": "x", "horizon_days": 90, "forecast": forecast,
              "mase": 1.0 if forecast == "model" else 2.0}
             for origin in origins for forecast in ("model", "N1", "N2", "N3")]
    if corruption == "missing":
        cells = [x for x in cells if not (x["forecast"] == "N3" and x["origin"] == origins[-1])]
    else:
        cells.append(dict(cells[0]))
    verdict, comparisons = subject.primary_verdict(cells, ["x"], expected_origins=origins)
    assert verdict == "INCONCLUSIVE"
    assert all("duplicate or missing" in x["undefined_reason"] for x in comparisons)


def test_benchmark_predictions_do_not_read_later_observations():
    series = pd.Series(100 + np.arange(301), index=pd.date_range("2023-01-01", periods=301))
    origin = series.index[200].date()
    changed = series.copy()
    changed.iloc[201:] += 1_000_000
    before = subject.cell_scores([329.0, 331.0] * 100, 330.0, series, origin, 30)
    after = subject.cell_scores([329.0, 331.0] * 100, 330.0, changed, origin, 30)
    assert subject._json(before) == subject._json(after)


def test_exact_primary_origin_inventory_requires_four_overlapping_dm_cases():
    origins = [date(2025, 11, 18), date(2025, 12, 1), *[date(2026, m, 1) for m in range(1, 7)]]
    assert len(origins) == 8
    # 18November overlaps1December,1January and1February, plus its own case.
    assert subject.ev.dm_horizon(90, origins) == 4


def test_secondary_skill_does_not_hide_missing_or_duplicate_cases():
    cells = [{"origin": str(origin.date()), "variable": "x", "horizon_days": 30, "forecast": forecast, "crps": score}
             for origin in pd.date_range("2023-01-01", periods=4, freq="MS")
             for forecast, score in (("model", 1.0), ("N1d", 2.0), ("N2d", 2.0), ("N1", 3.0))]
    cells.append(dict(cells[0]))
    rows = subject.distribution_comparisons(cells)
    assert all(x["skill"] is None and "duplicate" in x["undefined_reason"] for x in rows)


def test_zero_predictive_mass_is_not_hidden_by_clipping():
    losses = subject.binary_loss([0.0, 0.5], [True, False])
    assert losses["brier"] == pytest.approx(0.625)
    assert losses["log_loss"] is None
    assert "infinite" in losses["undefined_reason"]


def test_report_displays_measured_coverage_from_the_score_schema():
    series = pd.Series(np.arange(301), index=pd.date_range("2023-01-01", periods=301))
    cells = subject.cell_scores([100.0, 200.0] * 100, 150.0, series, series.index[200].date(), 30)
    cells = [{**row, "variable": "x"} for row in cells]
    text = subject.report({"verdict": "INCONCLUSIVE", "mode": "development", "specification_status": "draft",
                           "primary_comparisons": [], "S": cells, "distribution_comparisons": [], "B": [],
                           "contract_diagnostics": [], "not_measured": [], "unresolved_specification_choices": []})
    row = next(line for line in text.splitlines() if line.startswith("| x | 30 | model |"))
    assert [value.strip() for value in row.split("|")][-3:-1] == ["1", "1"]


def test_report_keeps_active_pattern_limitations_and_fixed_bands_visible():
    requirements = [{"id": "U5", "population": "validator commitments", "measurement_status": "NOT_MEASURED",
                     "fixed_band": {"median_ratio": [1.3, 2.2]}, "limitation": "joint trace not supplied"},
                    {"id": "AM5", "population": "validator and delegated principal", "measurement_status": "NOT_MEASURED",
                     "fixed_band": None, "limitation": "no delegation forecast"}]
    text = subject.report({"verdict": "INCONCLUSIVE", "mode": "development", "specification_status": "draft",
                           "primary_comparisons": [], "S": [], "distribution_comparisons": [], "B": [],
                           "contract_diagnostics": [], "not_measured": [], "unresolved_specification_choices": [],
                           "active_requirements": requirements})
    assert '| U5 | validator commitments | NOT_MEASURED | {"median_ratio": [1.3, 2.2]}' in text
    assert "joint trace not supplied" in text and "no delegation forecast" in text
    assert "missing measurement is not a pass" in text


def test_duration_history_excludes_overlapping_successors(tmp_path):
    def row(tx, start, end, accepted):
        return {"role": "validator", "node_id": "a", "transaction_hash": tx, "stake_navax": 2_000 * 10**9,
                "start_time": datetime.fromisoformat(start), "end_time": datetime.fromisoformat(end),
                "accepted_at": datetime.fromisoformat(accepted), "supply_before_navax": 450_000_000 * 10**9}
    rows = [row("a0", "2023-11-01", "2023-12-01", "2023-10-31"),
            row("a1", "2023-11-15", "2023-11-29", "2023-11-14"),  # Overlaps a0, excluded from the history law.
            row("a2", "2023-12-01", "2023-12-31", "2023-11-30"),
            row("a3", "2024-03-01", "2024-03-31", "2024-02-29"),
            row("a4", "2024-03-31", "2024-04-30", "2024-03-30")]
    path = parquet(tmp_path / "duration-events.parquet", rows)
    prepared = Prepared({k: v for k, v in model_on().param.values().items() if k != "name"})
    table = subject.behaviour_table(prepared, path, path, ORIGIN,
                                    datetime(2024, 3, 7, tzinfo=UTC), datetime(2024, 4, 15, tzinfo=UTC), None)
    history = next(x for x in table if x["target"] == "next_duration_days" and x["forecast"] == "history")
    assert history["events"] == 1
    assert history["log_loss"] == 0.0  # The admitted history has two30-day successors, not the overlapped14-day one.


def test_ledger_missingness_and_duplicate_dates_refuse(tmp_path):
    day = date(2024, 1, 1)
    row = {"date_utc": day, "complete": True, "active_validator_stake_wei": "2000000000000000000000", "active_validators": 1}
    duplicate = parquet(tmp_path / "duplicate-ledger.parquet", [row, row])
    with pytest.raises(ValueError, match="unique"):
        subject.realized_daily(duplicate, day + timedelta(days=2))
    missing = parquet(tmp_path / "missing-ledger.parquet", [row, {**row, "date_utc": day + timedelta(days=2)}])
    with pytest.raises(ValueError, match="missing dates"):
        subject.realized_daily(missing, day + timedelta(days=3))


def test_real_model_on_synthetic_inputs_returns_strict_complete_tables(periods, tmp_path):
    model = model_on()
    settings = {k: v for k, v in model.param.values().items() if k not in ("name", "seed", "runs", "timesteps", "draws")}
    prepared = Prepared(settings, pd.DataFrame({"renewal_shift": [0.0, 0.0]}))
    end = ORIGIN + timedelta(days=7)
    dates = pd.date_range(ORIGIN - timedelta(days=800), end - timedelta(days=1))
    actual = pd.DataFrame({"date_utc": dates.date, "complete": True,
                           "active_validator_stake_wei": [str((2_000 + i) * 10**18) for i in range(len(dates))],
                           "active_validators": 20 + np.arange(len(dates))})
    ledger = parquet(tmp_path / "ledger.parquet", actual)
    result = subject.evaluate(prepared, periods=periods, monetary=ledger, training=periods,
                              fit_until=ORIGIN + timedelta(days=1), score_until=end,
                              specification={"status": "draft", "batch_seeds": [0], "runs_per_batch": 2,
                                             "horizons_days": [2, 4], "primary_variables": ["active_validator_stake_navax"]})
    assert result["mode"] == "development"
    assert result["verdict"] == "INCONCLUSIVE"  # This tiny software fixture has no 90-day verdict cases.
    assert len(result["S"]) == 2 * 2 * 6
    assert {x["forecast"] for x in result["S"]} == {"model", "N1", "N2", "N3", "N1d", "N2d"}
    assert {x["target"] for x in result["B"]} >= {"renewal_7d", "return_8_90d_given_no_7d_renewal", "next_duration_days", "leave_365d"}
    assert result["model_fit_receipt"] == model.stake_fit_receipt
    assert "not total bonded" in result["report_markdown"]
    json.dumps(result, allow_nan=False)
    assert subject.frozen_fingerprint(prepared) == result["frozen_fit_sha256"]


def test_pinned_metadata_and_bytes_must_both_match(tmp_path, periods):
    folder = tmp_path / "data/runs/frozen/dataset"
    folder.mkdir(parents=True)
    body = periods.read_bytes()
    (folder / "p.parquet").write_bytes(body)
    (folder / "build.json").write_text(json.dumps({"dataset_id": "derived.staking-periods", "source_capture_id": "capture1"}))
    (folder / "check.json").write_text('{"status":"pass"}')
    pins = tmp_path / "data/pins"
    pins.mkdir()
    pin = {"schema_version": "avalanche-pins/v1", "runs": [{"dataset_id": "derived.staking-periods", "run": "frozen",
           "parquet": "p.parquet", "capture_id": "capture1", "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}]}
    (pins / "input.json").write_text(json.dumps(pin))
    assert subject.verified_inputs(tmp_path, "data/pins/input.json")["derived.staking-periods"] == folder / "p.parquet"
    (folder / "check.json").write_text('{"status":"fail"}')
    with pytest.raises(ValueError, match="producer metadata"):
        subject.verified_inputs(tmp_path, "data/pins/input.json")
    (folder / "check.json").write_text('{"status":"pass"}')
    (folder / "p.parquet").write_bytes(body + b"changed")
    with pytest.raises(ValueError, match="pinned bytes"):
        subject.verified_inputs(tmp_path, "data/pins/input.json")


@pytest.fixture
def binding_prepared():
    model = model_on()
    settings = {k: v for k, v in model.param.values().items() if k not in ("name", "seed", "runs", "timesteps", "draws")}
    return Prepared(settings, pd.DataFrame({"renewal_shift": np.zeros(200)}))


def binding_for(prepared, status="adopted"):
    receipt = subject.verify_frozen_fit(prepared, ORIGIN, None)
    return {"status": status, "fit_origin": ORIGIN.isoformat(), "fit_sha256": receipt["fit_sha256"],
            "draws_sha256": receipt["draws_sha256"], "artifact_manifest_sha256": "a" * 64}


def test_fit_binding_verifies_exact_fit_and_draws(binding_prepared):
    binding = binding_for(binding_prepared)
    assert subject.verify_frozen_fit(binding_prepared, ORIGIN, binding)["status"] == "MATCH_ADOPTED"
    binding_prepared.draws.loc[0, "renewal_shift"] = 0.01
    with pytest.raises(ValueError, match="fit fingerprint"):
        subject.verify_frozen_fit(binding_prepared, ORIGIN, binding)


def test_draw_artifact_hash_is_checked_separately(binding_prepared):
    binding = {**binding_for(binding_prepared), "draws_sha256": "0" * 64}
    with pytest.raises(ValueError, match="parameter draws"):
        subject.verify_frozen_fit(binding_prepared, ORIGIN, binding)


@pytest.mark.parametrize("binding", [None, {"status": "candidate"}, {"status": "adopted", "fit_sha256": "invalid"}])
def test_required_fit_binding_cannot_use_missing_or_invalid_identity(binding):
    with pytest.raises(ValueError, match="binding|SHA-256"):
        subject.configured_fit_binding({"frozen_fit": binding}, ORIGIN, required=True)


def test_granite_binding_does_not_apply_to_an_earlier_development_rehearsal(binding_prepared):
    binding = {**binding_for(binding_prepared), "fit_origin": "2025-11-18"}
    assert subject.configured_fit_binding({"frozen_fit": binding}, ORIGIN, required=False) is None
    with pytest.raises(ValueError, match="origin differs"):
        subject.configured_fit_binding({"frozen_fit": binding}, ORIGIN, required=True)


def test_candidate_binding_is_never_an_adopted_release(binding_prepared):
    binding = binding_for(binding_prepared, status="candidate")
    assert subject.configured_fit_binding({"frozen_fit": binding}, ORIGIN, required=False) == binding
    with pytest.raises(ValueError, match="adopted"):
        subject.configured_fit_binding({"frozen_fit": binding}, ORIGIN, required=True)


def test_score_refuses_fit_mismatch_before_evaluate(binding_prepared, tmp_path, monkeypatch):
    binding = {**binding_for(binding_prepared), "fit_sha256": "0" * 64}
    monkeypatch.setattr(subject, "evaluation_specification", lambda **_: {"frozen_fit": binding})
    context = {"training": {"derived.staking-periods": Path("periods")},
               "scoring": {"derived.staking-periods": Path("periods"), "derived.avax-monetary-daily": Path("labels")},
               "training_pin": {"runs": []}, "pin_hashes": {}}
    monkeypatch.setattr(subject, "prepare_fixed_fit", lambda *_: (binding_prepared, context))
    def forbidden(*args, **kwargs):
        pytest.fail("evaluate must not open any labels or later state after a fit mismatch")
    monkeypatch.setattr(subject, "evaluate", forbidden)
    with pytest.raises(ValueError, match="fit fingerprint"):
        subject.score(None, fit_until=ORIGIN + timedelta(days=1), score_until=ORIGIN + timedelta(days=40))


@pytest.mark.parametrize(("adopted", "protected"), [(False, False), (True, False), (True, True)])
def test_score_provenance_distinguishes_development_from_adopted_object(
        binding_prepared, tmp_path, monkeypatch, adopted, protected):
    specification = {"training_pin": "pin.json", "scoring_pin": "pin.json"}
    if adopted:
        specification["frozen_fit"] = binding_for(binding_prepared)
    (tmp_path / "pin.json").write_text('{"runs":[]}')
    context = {"training": {"derived.staking-periods": Path("periods")},
               "scoring": {"derived.staking-periods": Path("periods"), "derived.avax-monetary-daily": Path("labels")},
               "training_pin": {"runs": []}, "pin_hashes": {k: "a" * 64 for k in ("training_pin", "scoring_pin")},
               "slices": {}, "information": {}}
    monkeypatch.setattr(subject, "ROOT", tmp_path)
    monkeypatch.setattr(subject, "evaluation_specification", lambda **_: specification)
    monkeypatch.setattr(subject, "prepare_fixed_fit", lambda *_: (binding_prepared, context))
    monkeypatch.setattr(subject, "evaluate", lambda *_, **__: {})
    monkeypatch.setattr(subject, "verify_input_pins_unchanged", lambda *_: None)
    # A synthetic mode marker exercises reporting only. No actual Unseal is issued.
    if protected:
        monkeypatch.setattr(subject, "request_window", lambda *_: (ORIGIN, None))
    result = subject.score(object() if protected else None,
                           fit_until=ORIGIN + timedelta(days=1), score_until=ORIGIN + timedelta(days=40))
    provenance = result["fit_provenance"]
    assert provenance["evaluation_mode"] == ("protected" if protected else "development")
    if adopted:
        assert result["fit_binding"]["status"] == "MATCH_ADOPTED"
        assert "adopted FIT-O2 numerical realization" in provenance["purpose"]
        assert "historical point mismatch retained" in provenance["parameter_identity_to_released_values"]
        assert "forecast equivalence unknown" in provenance["parameter_identity_to_released_values"]
    else:
        assert result["fit_binding"]["status"] == "UNBOUND_DEVELOPMENT_ONLY"
        assert "not final coefficient adoption" in provenance["purpose"]
        assert provenance["parameter_identity_to_released_values"] == "not verified against stored released parameter values"


def test_protected_evaluate_requires_binding_before_label_access(binding_prepared, monkeypatch):
    # Isolate the numerical-binding layer. Actual token refusal has separate nonstubbed tests.
    monkeypatch.setattr(subject, "request_window", lambda *_: (ORIGIN, datetime(2024, 5, 1, tzinfo=UTC)))
    monkeypatch.setattr(subject, "realized_daily", lambda *_: pytest.fail("unbound protected evaluation must not read labels"))
    with pytest.raises(ValueError, match="adopted frozen fit"):
        subject.evaluate(binding_prepared, periods=Path("/absent"), monetary=Path("/absent"), training=Path("/absent"),
                         fit_until=ORIGIN + timedelta(days=1), score_until=date(2024, 5, 1),
                         specification={"status": "frozen"}, token=object())


def test_nonfinite_parameter_draws_are_refused(binding_prepared):
    binding_prepared.draws.loc[0, "renewal_shift"] = np.nan
    with pytest.raises(ValueError, match="finite"):
        subject.verify_frozen_fit(binding_prepared, ORIGIN, None)


def test_preflight_missing_binding_refuses_before_data_or_fit(tmp_path, monkeypatch):
    monkeypatch.setattr(subject, "evaluation_specification", lambda **_: {"status": "frozen"})
    monkeypatch.setattr(subject, "prepare_fixed_fit", lambda *_: pytest.fail("missing binding must fail before data or fit"))
    with pytest.raises(ValueError, match="adopted frozen fit"):
        subject.preflight_fit(fit_until=date(2025, 11, 19))


@pytest.mark.parametrize("cut", [date(2025, 11, 20), datetime(2025, 11, 19, tzinfo=UTC)])
def test_preflight_rejects_protected_or_partial_fit_cut_before_config(cut, monkeypatch):
    monkeypatch.setattr(subject, "ROOT", Path("/config-must-not-be-opened"))
    with pytest.raises(ValueError, match="exclusive pre-boundary"):
        subject.preflight_fit(fit_until=cut)


def test_preflight_uses_shared_pinned_preparation_without_reading_labels(binding_prepared, periods, tmp_path, monkeypatch):
    root = tmp_path
    runs = []
    for dataset, run_name, body in [("derived.staking-periods", "periods", periods.read_bytes()),
                               ("derived.avax-monetary-daily", "labels", b"not a parquet: must never be queried")]:
        folder = root / "data/runs" / run_name / "dataset"
        folder.mkdir(parents=True)
        (folder / "p.parquet").write_bytes(body)
        (folder / "build.json").write_text(json.dumps({"dataset_id": dataset, "source_capture_id": "fixture"}))
        (folder / "check.json").write_text('{"status":"pass"}')
        runs.append({"dataset_id": dataset, "run": run_name, "parquet": "p.parquet", "capture_id": "fixture",
                     "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
    pin = root / "data/pins/input.json"
    pin.parent.mkdir(parents=True)
    pin.write_text(json.dumps({"schema_version": "avalanche-pins/v1", "runs": runs}))
    specification = {"variant": "v0.8.0", "status": "frozen", "batch_seeds": list(range(10)),
                     "runs_per_batch": 20, "draw_seed": 0, "horizons_days": [30, 90],
                     "training_pin": "data/pins/input.json", "scoring_pin": "data/pins/input.json",
                     "frozen_fit": binding_for(binding_prepared)}
    config = root / "validation/lockbox/specification.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps(specification))
    calls = []
    class FixtureVariant:
        def prepare(self, path, origin, source, *, draws, draw_seed):
            calls.append((origin, source, draws, draw_seed))
            return binding_prepared
    monkeypatch.setattr(subject, "ROOT", root)
    monkeypatch.setattr(subject, "VARIANTS", {"v0.8.0": FixtureVariant()})
    monkeypatch.setattr(subject, "evaluate", lambda **_: pytest.fail("preflight must not evaluate"))
    monkeypatch.setattr(subject, "realized_daily", lambda *_: pytest.fail("preflight must not query realized labels"))
    result = subject.preflight_fit(fit_until=ORIGIN + timedelta(days=1))
    assert calls == [(ORIGIN, "periods", 200, 0)]
    assert result["fit_binding"]["status"] == "MATCH_ADOPTED"
    assert result["protected_labels_read"] is result["forecast_executed"] is False
    assert result["training_slice_equality"]["status"] == "PASS"
    json.dumps(result, allow_nan=False)
