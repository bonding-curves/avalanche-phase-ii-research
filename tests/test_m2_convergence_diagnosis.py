"""Independent analytic references and corrupted saved-result refusals."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location(
    "convergence_diagnosis",
    Path(__file__).parents[1] / "scripts/m2_convergence_diagnosis.py",
)
diag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diag)


def factorial():
    bits = ((np.arange(16)[:, None] >> np.arange(4)) & 1).astype(float)
    a, b = bits[:, :2], bits[:, 2:]
    return a, b


def fixture():
    a, b = factorial()
    order = np.argsort(a[:, 0], kind="stable")
    a, b = a[order], b[order]
    parts = []
    for role, own, other, seed0 in (("A", a, b, 1), ("B", b, a, 101)):
        for j in [None] if role in ("A", "B") else []:
            parts.append((role, j, own, seed0))
        for j in range(2):
            hybrid = own.copy()
            hybrid[:, j] = other[:, j]
            parts.append(("AB" if role == "A" else "BA", j + 1, hybrid, seed0))
    rows = []
    for role, j, coordinates, seed0 in parts:
        for i, values in enumerate(coordinates):
            rows.append(
                {
                    "index": len(rows),
                    "i": i,
                    "j": j,
                    "block": role,
                    "seed": seed0 + i,
                    "draw": seed0 + i + 1000,
                    "baseline": len(rows) + 1000,
                    "u1": values[0],
                    "u2": values[1],
                    "renewal_response": values[0] * 0.1,
                    "entry_response": values[1] * 0.1,
                    "outcome": values[0] + 0.001 * values[1],
                }
            )
    frame = pd.DataFrame(rows)
    blocks = diag.ordered_blocks(frame, "before", 16)
    ys = [
        blocks["A"].outcome.to_numpy(),
        blocks["B"].outcome.to_numpy(),
        np.column_stack([p.outcome for p in blocks["AB"]]),
    ]
    points = []
    for n in (8, 16):
        ya, yb, yab = [x[:n] for x in ys]
        center = np.concatenate((ya, yb)).mean()
        variance = np.concatenate((ya, yb)).var()
        points.append(
            ((yb - center)[:, None] * (yab - ya[:, None])).mean(axis=0) / variance
        )
        points.append(0.5 * ((ya[:, None] - yab) ** 2).mean(axis=0) / variance)
    movement = max(
        np.max(abs(points[2] - points[0])), np.max(abs(points[3] - points[1]))
    )
    saved = pd.DataFrame(
        [
            {
                "family": "before",
                "yield_pp": 3.0,
                "horizon_days": 365,
                "measure": "outcome",
                "input": name,
                "first": points[2][j],
                "total": points[3][j],
                "max_change": movement,
                "converged": movement <= 0.02,
                "first_low": points[2][j] - 0.1,
                "first_high": points[2][j] + 0.1,
                "total_low": points[3][j] - 0.1,
                "total_high": points[3][j] + 0.1,
            }
            for j, name in enumerate(diag.FAMILY_INPUTS["before"])
        ]
    )
    return frame, saved


def test_additive_exact_analytic_indices():
    a, b = factorial()
    first, total = diag.reference_indices(
        a[:, 0] + 2 * a[:, 1],
        b[:, 0] + 2 * b[:, 1],
        np.column_stack((b[:, 0] + 2 * a[:, 1], a[:, 0] + 2 * b[:, 1])),
    )
    np.testing.assert_allclose(first, [0.2, 0.8], rtol=0, atol=1e-15)
    np.testing.assert_allclose(total, [0.2, 0.8], rtol=0, atol=1e-15)


def test_interaction_exact_analytic_indices():
    a, b = (2 * x - 1 for x in factorial())
    first, total = diag.reference_indices(
        a[:, 0] * a[:, 1],
        b[:, 0] * b[:, 1],
        np.column_stack((b[:, 0] * a[:, 1], a[:, 0] * b[:, 1])),
    )
    np.testing.assert_array_equal(first, [0, 0])
    np.testing.assert_array_equal(total, [1, 1])


def test_affine_invariance_and_undefined_constant():
    a, b = factorial()
    arrays = (
        a[:, 0] + 2 * a[:, 1],
        b[:, 0] + 2 * b[:, 1],
        np.column_stack((b[:, 0] + 2 * a[:, 1], a[:, 0] + 2 * b[:, 1])),
    )
    expected = diag.reference_indices(*arrays)
    for multiplier, shift in ((1.0, -0.075), (-3.0, 20.0), (1e100, 1e101)):
        actual = diag.reference_indices(*(multiplier * x + shift for x in arrays))
        np.testing.assert_allclose(actual, expected, atol=2e-14, rtol=2e-14)
    assert np.isnan(
        diag.reference_indices(np.ones(8), np.ones(8), np.ones((8, 2)))
    ).all()


def test_input_delta_is_distinct_from_group_max_flag():
    frame, saved = fixture()
    result = diag.diagnose_scope(frame, saved, "before", sizes=(8, 16))
    assert len(result) == 2
    assert not result.converged.any()
    assert result.individual_converged.sum() == 1
    assert result.propagated_failure_only.sum() == 1
    assert result.recomputed_group_max_change.nunique() == 1
    assert result.individual_max_change.nunique() == 2
    summary = diag.summarize(result.assign(test="all"), ["test"]).iloc[0]
    assert summary.group_flag_false == 2
    assert summary.individual_false == 1
    assert summary.propagated_failure_only == 1


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("omit", "incomplete Saltelli"),
        ("repeat", "repeated trajectory"),
        ("i", "base i"),
        ("hybrid", "coordinate replacement"),
        ("key", "parent seed/draw"),
        ("collision", "keys collide"),
        ("baseline", "baseline identity"),
        ("physical", "physical coordinate"),
    ],
)
def test_semantic_input_mutations_refuse(mutation, reason):
    frame, _ = fixture()
    if mutation == "omit":
        frame = frame.iloc[:-1].copy()
    elif mutation == "repeat":
        frame.loc[1, "index"] = frame.loc[0, "index"]
    elif mutation == "i":
        frame.loc[1, "i"] = 0
    elif mutation == "hybrid":
        frame.loc[frame.block.eq("AB").idxmax(), "u1"] = 0.123
    elif mutation == "key":
        frame.loc[frame.block.eq("AB").idxmax(), "seed"] = 999
    elif mutation == "collision":
        frame.loc[frame.block.eq("B"), "seed"] = frame.loc[
            frame.block.eq("A"), "seed"
        ].to_numpy()
    elif mutation == "baseline":
        frame.loc[0, "baseline"] = np.nan
    elif mutation == "physical":
        frame.loc[0, "renewal_response"] = 0.049
    with pytest.raises(ValueError, match=reason):
        diag.ordered_blocks(frame, "before", 16)


@pytest.mark.parametrize("field", ["first", "total", "max_change", "converged"])
def test_saved_result_mutations_refuse(field):
    frame, saved = fixture()
    if field == "converged":
        saved.loc[0, field] = not saved.loc[0, field]
    else:
        saved.loc[0, field] += 0.1
    with pytest.raises(ValueError, match="saved"):
        diag.diagnose_scope(frame, saved, "before", sizes=(8, 16))


def test_missing_or_repeated_saved_rows_refuse():
    frame, saved = fixture()
    for changed in (
        saved.iloc[:1],
        pd.concat((saved, saved.iloc[:1]), ignore_index=True),
    ):
        with pytest.raises(ValueError, match="saved"):
            diag.diagnose_scope(frame, changed, "before", sizes=(8, 16))


def test_extension_arithmetic_counts_shared_baselines_once():
    all_scopes = [(f, y) for f in diag.FAMILY_INPUTS for y in (3.0, 5.0, 7.0, 10.0)]
    counts = diag.extension_counts(all_scopes)
    assert counts["new_saltelli_design_rows"] == 61440
    assert counts["new_matched_baseline_rows"] == 49152
    assert counts["new_trajectories"] == 110592
    assert counts["new_independent_seed_draw_pairs"] == 16384
    assert diag.extension_counts([("before", 3.0)])["new_trajectories"] == 6144
    assert diag.extension_counts([("ramp", 3.0)])["new_trajectories"] == 7168


def test_external_pin_refuses_selfhashed_receipt_edit(tmp_path):
    inputs = tmp_path / "inputs"
    report = tmp_path / "report"
    inputs.mkdir()
    report.mkdir()
    (inputs / "inputs-manifest.json").write_text("{}")
    (report / "analysis-receipt.json").write_text("{}")
    with pytest.raises(ValueError, match="external SHA"):
        diag.authenticate(inputs, tmp_path, report, "0" * 64, "1" * 64)


def test_binding_directory_escape_refuses(tmp_path):
    (tmp_path / "secret").write_text("x")
    child = tmp_path / "child"
    child.mkdir()
    with pytest.raises(ValueError, match="escapes"):
        diag._bound(child, "../secret")


def authenticated_fixture(tmp_path):
    import hashlib
    import json

    inputs, numerics, report = (tmp_path / n for n in ("inputs", "numerics", "report"))
    for directory in (inputs, numerics, report):
        directory.mkdir()
    (inputs / "wide.parquet").write_bytes(b"synthetic-authentication-only")
    matrix = np.zeros((1000, 2), dtype=np.int64)
    np.savez(inputs / "bootstrap.npz", synthetic=matrix)
    manifest = {
        "schema": "m2-analysis-inputs/v1",
        "wide_sha256": diag.digest(inputs / "wide.parquet"),
        "bootstrap": {
            "file_sha256": diag.digest(inputs / "bootstrap.npz"),
            "matrices": {
                "synthetic": {
                    "shape": [1000, 2],
                    "sha256": hashlib.sha256(
                        matrix.astype("<i8").tobytes()
                    ).hexdigest(),
                }
            },
        },
    }
    (inputs / "inputs-manifest.json").write_text(json.dumps(manifest))
    input_sha = diag.digest(inputs / "inputs-manifest.json")
    (numerics / "scope.csv").write_text("bound-output\n")
    nm = {
        "complete": True,
        "failures": [],
        "contract": {
            "inputs_manifest_sha256": input_sha,
            "wide_sha256": manifest["wide_sha256"],
            "bootstrap_sha256": manifest["bootstrap"]["file_sha256"],
            "configuration": {
                "convergence_sizes": [256, 512],
                "maximum_index_movement": 0.02,
            },
            "measures": [f"m{i}" for i in range(23)],
        },
        "scopes": {
            "test": {
                "outputs": {
                    "csv": {
                        "path": "scope.csv",
                        "sha256": diag.digest(numerics / "scope.csv"),
                    }
                }
            }
        },
    }
    (numerics / "numerics-manifest.json").write_text(json.dumps(nm))
    (report / "output.csv").write_text("bound-report\n")
    rm = {
        "schema": "m2-report-analysis/v1",
        "inputs": manifest,
        "outputs": {"output.csv": diag.digest(report / "output.csv")},
        "numerics_receipt_sha256": diag.digest(numerics / "numerics-manifest.json"),
    }
    (report / "analysis-receipt.json").write_text(json.dumps(rm))
    return (
        inputs,
        numerics,
        report,
        input_sha,
        diag.digest(report / "analysis-receipt.json"),
    )


def test_authentication_accepts_complete_bound_fixture(tmp_path):
    inputs, numerics, report, ish, rsh = authenticated_fixture(tmp_path)
    im, nm, rm = diag.authenticate(inputs, numerics, report, ish, rsh)
    assert nm["complete"] and rm["inputs"] == im


@pytest.mark.parametrize(
    "relative",
    [
        "inputs/wide.parquet",
        "inputs/bootstrap.npz",
        "numerics/scope.csv",
        "numerics/numerics-manifest.json",
        "report/output.csv",
        "report/analysis-receipt.json",
    ],
)
def test_each_consumed_authentication_layer_refuses_byte_mutation(tmp_path, relative):
    inputs, numerics, report, ish, rsh = authenticated_fixture(tmp_path)
    path = tmp_path / relative
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="differ"):
        diag.authenticate(inputs, numerics, report, ish, rsh)


def test_runtime_is_wall_throughput_not_standalone_cpu_claim(tmp_path):
    import json

    path = tmp_path / "timing.json"
    source = {
        "custody": {"receipt_sha256": "producer"},
        "counts": {"completed": 132800},
        "producer_timings": {"seconds": 28821.036},
        "host": {"workers": 4, "observed_worker_peak_mib": 1140.9296875},
    }
    path.write_text(json.dumps(source))
    receipt = {"inputs": {"bindings": {"receipt_sha256": "producer"}}}
    result = diag.runtime_proposal(path, diag.digest(path), receipt, 110592)
    assert result["same_worker_throughput_hours"] == pytest.approx(6.667034833734939)
    assert result["planning_allowance_1_5x_hours"] == pytest.approx(10.000552250602408)
    assert result["measured_workers"] == 4
    receipt["inputs"]["bindings"]["receipt_sha256"] = "other"
    with pytest.raises(ValueError, match="producer receipt"):
        diag.runtime_proposal(path, diag.digest(path), receipt, 110592)


def test_constant_outcome_stays_undefined_in_all_accounting():
    frame, saved = fixture()
    frame["outcome"] = 7.0
    for name in ("first", "total", "max_change"):
        saved[name] = np.nan
    saved["converged"] = pd.NA
    result = diag.diagnose_scope(frame, saved, "before", sizes=(8, 16))
    assert result.individual_converged.isna().all()
    assert result.recomputed_group_max_change.isna().all()
    assert not result.propagated_failure_only.any()
    summary = diag.summarize(result.assign(test="constant"), ["test"]).iloc[0]
    assert summary.undefined_rows == 2 and summary.individual_false == 0


def test_occupied_output_refuses_before_reading_or_overwriting_inputs(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    original = output / "kept.csv"
    original.write_text("do not change\n")
    with pytest.raises(ValueError, match="new empty"):
        diag.execute(
            tmp_path, tmp_path, tmp_path, output, inputs_sha256="x", report_sha256="y"
        )
    assert original.read_text() == "do not change\n"
