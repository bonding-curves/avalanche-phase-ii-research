"""Numerical references and adversarial provenance checks for paired analysis."""
import copy
import json
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from avalanche_research.analysis import paired_sweep as p
from avalanche_research.core.hashing import canonical_bytes, sha256
from avalanche_research.model.designs import design_hash, row_id

MECHANISMS = {
    "ramp": {"name": "ACP285Ramp", "activation": "2025-11-18T16:00:00+00:00", "ramp_days": 90, "target_min_rate": 0.075},
    "before": {"name": "ACP285Ramp", "target_min_rate": 0.1},
    "tenure": {"name": "TenureBoost", "boost_max": 0.1, "acp285": False},
    "quadratic": {"name": "QuadraticReward", "exponent": 2.0, "acp285": False},
}


@pytest.fixture
def bundle(tmp_path):
    rows, labels = [], []
    for i, family in enumerate(p.FAMILIES):
        rows.append({"seed": 1, "draw": 0, "origin": "2025-11-18", "model": "fixture",
                     "mechanism": copy.deepcopy(MECHANISMS[family]), "renewal_response": 0.04,
                     "entry_response": 0.02, "outside_yield_pp": 5.0, "fitted_outside_yield_pp": 4.0})
        labels.append({"index": i, "family": family, "yield_pp": 5.0, "block": "A",
                       "i": 0, "j": "", "baseline": 4})
    rows.append({**rows[0], "mechanism": {"name": "ChainReward"}})
    labels.append({"index": 4, "family": "chain", "yield_pp": 5.0, "block": "baseline",
                   "i": 0, "j": "", "baseline": ""})
    (tmp_path / "rows.json").write_bytes(canonical_bytes(rows))
    pd.DataFrame(labels).to_csv(tmp_path / "labels.csv", index=False)
    conn = duckdb.connect()
    conn.execute("COPY (SELECT 0 AS draw) TO ? (FORMAT PARQUET)", [str(tmp_path / "draws.parquet")])
    conn.close()
    hashes = {name: sha256((tmp_path / name).read_bytes()) for name in p.BUNDLE_FILES if name != "design.json"}
    design = {"generator": "explicit", "models": ["fixture"], "origins": ["2025-11-18"],
              "rows": len(rows), "runs": 1, "timesteps": 365, "name": "test-design",
              "rows_file": "rows.json", "rows_sha256": hashes["rows.json"],
              "draws_file": "draws.parquet", "draws_sha256": hashes["draws.parquet"],
              "reducer": {"kind": "kpis", "horizons": [365, 180], "operating_costs": {"zero": 0.0}}}
    (tmp_path / "design.json").write_bytes(canonical_bytes(design))
    hashes["design.json"] = sha256((tmp_path / "design.json").read_bytes())
    return p.read_bundle(tmp_path, hashes)


@pytest.fixture
def outputs(bundle, tmp_path):
    directory = tmp_path / "outputs"
    directory.mkdir()
    settings = {"model": "test", "fixed_law": [1, 2, 3]}
    base = sha256(json.dumps(settings, sort_keys=True).encode())[:16]
    files, identities, frames = {}, [], []
    for i, row in enumerate(bundle.rows):
        producer_row = {"design": bundle.design["name"], **row, "index": i}
        identity = row_id(producer_row, base)
        identities.append(identity)
        records = []
        for measure, horizon, cost in sorted(p.expected_cells(bundle.design)):
            value = {"issued_navax": 200.0 if i == 4 else 100.0,
                     "active_validators": 100.0 if i == 4 else 50.0,
                     "validator_stake_navax": 1000.0}.get(measure, 0.2)
            records.append({**producer_row, "mechanism": json.dumps(row["mechanism"], sort_keys=True),
                            "row_id": identity, "run": 1, "measure": measure, "horizon_days": horizon,
                            "cost_level": cost, "value": value, "base_specification": base,
                            "specification": "2" * 16, "worker_peak_mib": 42.0})
        frame = pd.DataFrame(records)
        conn = duckdb.connect()
        conn.register("records", frame)
        conn.execute("COPY records TO ? (FORMAT PARQUET)", [str(directory / f"{identity}.parquet")])
        conn.close()
        values = frame.drop(columns="worker_peak_mib")
        values = values[sorted(values.columns)].sort_values(sorted(values.columns), kind="mergesort")
        files[identity] = sha256(values.to_csv(index=False).encode())
        frames.append(frame)
    receipt = {"schema_version": "avalanche-run-receipt/v1", "code": {"commit": "a" * 40, "dirty": False},
               "inputs": {"pin_file_sha256": "b" * 64}, "conservation": [],
               "model": {"specifications": [{"hash": base, "settings": settings}]},
               "sweep": {"complete": True, "rows_planned": 5, "rows_written": 5, "rows_skipped": 0,
                         "files": files, "design_file": bundle.design,
                         "design_hash": design_hash([{"identity": v} for v in identities], "design")},
               "output": {"rows": sum(len(f) for f in frames), "sha256": sha256(canonical_bytes(files))}}
    receipt["receipt_id"] = sha256(canonical_bytes(receipt))[:16]
    (directory / "receipt.json").write_bytes(canonical_bytes(receipt))
    return directory, pd.concat(frames, ignore_index=True), receipt


def test_finite_inputs_with_overflowing_paired_ratio_refuse(bundle, outputs):
    _, table, _ = outputs
    table.loc[(table["index"] == 0) & (table.measure == "issued_navax"), "value"] = 1e308
    table.loc[(table["index"] == 4) & (table.measure == "issued_navax"), "value"] = 1e-308
    with pytest.raises(p.ContractError, match="nonfinite derived paired ratio"):
        p.relative_kpis(table, bundle)


def test_actual_parquet_receipt_readback_and_hand_calculated_ratios(bundle, outputs):
    directory, expected, _ = outputs
    table, _, raw = p.read_outputs(directory, bundle, code_commit="a" * 40, pin_sha256="b" * 64,
                                  receipt_sha256=sha256((directory / "receipt.json").read_bytes()))
    pd.testing.assert_frame_equal(table, expected.sort_values(list(p.CELL), kind="stable").reset_index(drop=True))
    ratios = p.relative_kpis(table, bundle)
    assert len(raw) == 5 and len(ratios) == 24
    assert set(ratios.baseline) == {4}  # Sharing is preserved, not mistaken for independent noise.
    assert set(ratios.loc[ratios.measure == "issuance_saved", "value"]) == {0.5}
    assert set(ratios.loc[ratios.measure == "active_validators_retained", "value"]) == {0.5}
    assert set(ratios.loc[ratios.measure == "validator_stake_retained", "value"]) == {1.0}


def test_selection_keeps_original_indices_and_shared_baseline(bundle):
    subset = p.rehearsal_selection(bundle)
    assert subset["original_indices"] == [0, 1, 2, 3, 4]
    assert (subset["design_rows"], subset["baseline_rows"]) == (4, 1)
    assert subset["simulation_executed"] is False


@pytest.mark.parametrize("change", ["seed", "draw", "entry_response", "outside_yield_pp", "mechanism"])
def test_changed_baseline_semantics_refuse(bundle, change):
    rows = copy.deepcopy(list(bundle.rows))
    rows[4][change] = {"name": "OtherRule"} if change == "mechanism" else rows[4][change] + 1
    with pytest.raises(p.ContractError):
        p.validate_pairing(rows, bundle.labels)


@pytest.mark.parametrize("partner", [0, 1, 999, None, True])
def test_invalid_baseline_reference_refuses(bundle, partner):
    labels = bundle.labels.copy()
    labels.at[0, "baseline"] = partner
    with pytest.raises(p.ContractError):
        p.validate_pairing(bundle.rows, labels)


@pytest.mark.parametrize("change", ["missing", "duplicate", "value", "setting", "index", "horizon", "boolean_index"])
def test_output_cell_and_setting_mutations_refuse(bundle, outputs, change):
    _, table, receipt = outputs
    if change == "missing":
        table = table.iloc[1:]
    elif change == "duplicate":
        table = pd.concat([table, table.iloc[[0]]])
    elif change == "value":
        table.at[0, "value"] = float("nan")
    elif change == "setting":
        table.at[0, "seed"] = 2
    elif change == "index":
        table.at[0, "index"] = 99
    elif change == "horizon":
        table.at[0, "horizon_days"] = 30
    else:
        table["index"] = table["index"].astype(bool)
    with pytest.raises(p.ContractError):
        p.validate_outputs(table, bundle, receipt)


@pytest.mark.parametrize("change", ["source", "pin", "receipt", "missing_file", "changed_file", "extra_file"])
def test_provenance_and_file_mutations_refuse(bundle, outputs, change):
    directory, _, receipt = outputs
    code, pin = "a" * 40, "b" * 64
    receipt_hash = sha256((directory / "receipt.json").read_bytes())
    if change == "source":
        code = "c" * 40
    elif change == "pin":
        pin = "c" * 64
    elif change == "receipt":
        receipt["sweep"]["rows_planned"] = 4
        (directory / "receipt.json").write_bytes(canonical_bytes(receipt))
    elif change == "missing_file":
        next(directory.glob("*.parquet")).unlink()
    elif change == "changed_file":
        path = next(directory.glob("*.parquet"))
        path.write_bytes(b"broken")
    else:
        (directory / ("0" * 16 + ".parquet")).write_bytes(b"extra")
    with pytest.raises((p.ContractError, duckdb.Error)):
        p.read_outputs(directory, bundle, code_commit=code, pin_sha256=pin, receipt_sha256=receipt_hash)


def test_nonpositive_baseline_is_an_explicit_refusal(bundle, outputs):
    _, table, _ = outputs
    table.loc[(table["index"] == 4) & (table.measure == "issued_navax"), "value"] = 0.0
    with pytest.raises(p.ContractError, match="denominator"):
        p.relative_kpis(table, bundle)


def test_both_horizons_and_all_bundle_hashes_are_required(bundle):
    with pytest.raises(p.ContractError, match="four"):
        p.read_bundle(Path("irrelevant"), {})
    design = copy.deepcopy(bundle.design)
    design["reducer"]["horizons"] = [365]
    with pytest.raises(p.ContractError, match="horizons"):
        p.expected_cells(design)


def test_actual_ramp_mislabeled_as_tenure_refuses(bundle):
    labels = bundle.labels.copy()
    labels.at[0, "family"] = "tenure"
    with pytest.raises(p.ContractError, match="family"):
        p.validate_pairing(bundle.rows, labels)


@pytest.fixture
def controls(bundle):
    rows, labels = [], []

    def add(family, mechanism, renewal, entry, yield_pp, seed, draw, block, j=None):
        rows.append({**bundle.rows[0], "mechanism": copy.deepcopy(mechanism), "renewal_response": renewal,
                     "entry_response": entry, "outside_yield_pp": yield_pp, "seed": seed, "draw": draw})
        labels.append({"index": len(rows) - 1, "family": family, "block": block, "i": 0,
                       "j": j, "yield_pp": yield_pp, "baseline": None})

    for family, mechanism in MECHANISMS.items():
        add(family, mechanism, 0.0, 0.0, 5.0, 1, 0, "zero")
    specifications = [("before", 0.0, 0.0, 4.0, None), ("before", 0.1, 0.0, 4.0, None),
                      ("before", 0.0, 0.1, 4.0, None), ("ramp", 0.05, 0.05, 5.0, 0.05),
                      ("ramp", 0.05, 0.05, 5.0, 0.1), ("tenure", 0.05, 0.05, 5.0, 0.0),
                      ("tenure", 0.05, 0.05, 5.0, 0.2)]
    for j, (family, renewal, entry, yield_pp, value) in enumerate(specifications, 1):
        mechanism = copy.deepcopy(MECHANISMS[family])
        if value is not None:
            mechanism["target_min_rate" if family == "ramp" else "boost_max"] = value
        add(family, mechanism, renewal, entry, yield_pp, 2, 1, "control", j)
    baseline_by_key = {}
    for row, label in zip(rows[:], labels[:]):
        key = json.dumps({k: v for k, v in row.items() if k != "mechanism"}, sort_keys=True)
        if key not in baseline_by_key:
            baseline_by_key[key] = len(rows)
            rows.append({**row, "mechanism": {"name": "ChainReward"}})
            labels.append({"index": len(rows) - 1, "family": "chain", "block": "baseline", "i": 0,
                           "j": None, "yield_pp": row["outside_yield_pp"], "baseline": None})
        label["baseline"] = baseline_by_key[key]
    frame = pd.DataFrame(labels)
    for key in ("j", "baseline"):
        frame[key] = pd.Series([label[key] for label in labels], dtype=object)
    design = copy.deepcopy(bundle.design)
    design["rows"] = len(rows)
    current = p.Bundle(design, tuple(rows), frame, {}, 2)
    records = []
    for label in labels:
        for measure, horizon, cost in p.expected_cells(design):
            value = 1.0
            if measure == "issued_navax" and label["block"] == "control":
                value = {1: 80.0, 2: 80.0, 3: 80.0, 4: 120.0, 5: 80.0, 6: 90.0, 7: 110.0}[label["j"]]
            records.append({"index": label["index"], "measure": measure, "horizon_days": horizon,
                            "cost_level": cost, "value": value})
    return current, pd.DataFrame(records)


def test_declared_zero_and_active_controls_pass_known_outputs(controls):
    bundle, table = controls
    result = p.control_checks(table, bundle)
    assert len(result) == 9 and result.passed.all()


def test_nonzero_response_control_refuses_even_with_matching_baselines_and_equal_outputs(controls):
    bundle, table = controls
    rows = copy.deepcopy(list(bundle.rows))
    zero_indices = set(bundle.labels.loc[bundle.labels.block == "zero", "index"])
    zero_indices.update(bundle.labels.loc[bundle.labels.block == "zero", "baseline"])
    for i in zero_indices:
        rows[i]["renewal_response"] = 0.15
        rows[i]["entry_response"] = 0.12
    altered = p.Bundle(bundle.design, tuple(rows), bundle.labels, {}, bundle.draws)
    with pytest.raises(p.ContractError, match="nonzero responses"):
        p.control_checks(table, altered)


def test_control_noise_mismatch_refuses_with_its_own_matching_baseline(controls):
    bundle, table = controls
    rows = copy.deepcopy(list(bundle.rows))
    rows[0]["seed"] = 99
    rows.append({**rows[0], "mechanism": {"name": "ChainReward"}})
    labels = pd.concat([bundle.labels, pd.DataFrame([{"index": len(rows) - 1, "family": "chain",
                         "yield_pp": 5.0, "block": "baseline", "i": 9, "j": None, "baseline": None}])], ignore_index=True)
    labels["baseline"] = labels["baseline"].astype(object)
    labels.at[0, "baseline"] = len(rows) - 1
    altered = p.Bundle(bundle.design, tuple(rows), labels, {}, 2)
    with pytest.raises(p.ContractError, match="share noise"):
        p.control_checks(table, altered)


def test_valid_family_wrong_control_endpoint_refuses(controls):
    bundle, table = controls
    rows = copy.deepcopy(list(bundle.rows))
    index = bundle.labels.loc[(bundle.labels.block == "control") & (bundle.labels.j == 4), "index"].iat[0]
    rows[index]["mechanism"]["target_min_rate"] = 0.06
    with pytest.raises(p.ContractError, match="control 4 settings"):
        p.control_checks(table, p.Bundle(bundle.design, tuple(rows), bundle.labels, {}, 2))


@pytest.mark.parametrize("condition", ["zero_count", "idle_ramp", "nonfinite"])
def test_numerical_control_mutations_fail(controls, condition):
    bundle, table = controls
    if condition == "nonfinite":
        table.at[0, "value"] = float("nan")
        with pytest.raises(p.ContractError, match="nonfinite"):
            p.control_checks(table, bundle)
        return
    if condition == "zero_count":
        table.loc[(table["index"] == 0) & (table.measure == "active_validators"), "value"] = 2.0
    else:
        index = bundle.labels.loc[(bundle.labels.block == "control") & (bundle.labels.j == 4), "index"].iat[0]
        table.loc[(table["index"] == index) & (table.measure == "issued_navax"), "value"] = 80.0
    assert not p.control_checks(table, bundle).passed.all()
