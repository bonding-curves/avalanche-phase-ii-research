"""Complete synthetic Saltelli coupling and estimator/convergence controls."""

import importlib.util
import json
import os
import subprocess
import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_m2_associations import design, draws

from avalanche_research.analysis import m2_associations as a
from avalanche_research.analysis import m2_sensitivity as s
from avalanche_research.analysis.sobol import _indices


def run(table, reps=24, ix=None, sizes=(16, 32), **kwargs):
    mapping = {} if ix is None else ix
    if ix is None:
        for (family, yield_pp), scope in table.groupby(["family", "yield_pp"]):
            mapping[family, float(yield_pp)] = draws(
                int((scope.block == "A").sum()), reps
            )
    return s.analyze_sensitivity(
        table,
        measures=kwargs.pop("measures", ("y",)),
        bootstrap_indices=mapping,
        bootstrap_replicates=reps,
        convergence_sizes=sizes,
        **kwargs,
    )


def arrays(table):
    ya = table.loc[table.block == "A"].sort_values("i").y.to_numpy()[:, None]
    yb = table.loc[table.block == "B"].sort_values("i").y.to_numpy()[:, None]
    d = len(a.FAMILY_INPUTS[table.family.iloc[0]])
    yab = np.stack(
        [
            table.loc[(table.block == "AB") & (table.j == j + 1)]
            .sort_values("i")
            .y.to_numpy()
            for j in range(d)
        ],
        axis=1,
    )[:, :, None]
    return ya, yb, yab


def test_complete_enumeration_additive_oracle_and_no_response_filtering():
    points = np.array(list(product((0.0, 1.0), repeat=6)))
    table = design(points=points)
    table["y"] = table.u1 + 2 * table.u2
    out, meta = run(table, sizes=(32, 64))
    np.testing.assert_allclose(out["first"], [0.2, 0.8, 0.0], atol=1e-14)
    np.testing.assert_allclose(out["total"], [0.2, 0.8, 0.0], atol=1e-14)
    assert len(out) == 3
    assert set(out.input) == set(a.FAMILY_INPUTS["ramp"])
    assert meta["scopes"][0]["retained_BA_rows"] == 192


def test_batch_numerics_match_delivered_kernel_each_draw_and_joint_intervals():
    table = design(32)
    ix = draws(32)
    ya, yb, yab = arrays(table)
    first, total, valid = s._batch_indices(ya[ix], yb[ix], yab[ix])
    for b, selected in enumerate(ix):
        ef, et, ev = _indices(ya[selected], yb[selected], yab[selected])
        np.testing.assert_allclose(first[b], ef, rtol=0, atol=2e-14)
        np.testing.assert_allclose(total[b], et, rtol=0, atol=2e-14)
        np.testing.assert_array_equal(valid[b], ev)
    out, meta = run(table, ix={("ramp", 5.0): ix})
    np.testing.assert_allclose(out["first"], _indices(ya, yb, yab)[0][:, 0], atol=1e-14)
    np.testing.assert_allclose(
        out[["first_low", "first_high"]],
        np.quantile(first[:, :, 0], [0.025, 0.975], axis=0).T,
        atol=1e-14,
    )
    np.testing.assert_allclose(
        out[["total_low", "total_high"]],
        np.quantile(total[:, :, 0], [0.025, 0.975], axis=0).T,
        atol=1e-14,
    )
    assert meta["scopes"][0]["bootstrap_indices_sha256"] == a._digest(ix)


def test_frozen_256_512_prefix_check_original_order_and_all_indices():
    table = design(512)
    ix = np.tile(np.arange(512), (1000, 1))
    original = table.copy(deep=True)
    out, meta = run(table, reps=1000, ix={("ramp", 5.0): ix}, sizes=(256, 512))
    ya, yb, yab = arrays(table)
    f, t, _ = _indices(ya, yb, yab)
    fs, ts, _ = _indices(ya[:256], yb[:256], yab[:256])
    movement = np.abs(np.concatenate([f - fs, t - ts])).max()
    assert out.max_change.eq(movement).all()
    assert out.converged.eq(movement <= 0.02).all()
    assert meta["frozen_configuration"] is True
    shuffled, _ = run(
        table.sample(frac=1, random_state=21),
        reps=1000,
        ix={("ramp", 5.0): ix},
        sizes=(256, 512),
    )
    pd.testing.assert_frame_equal(out, shuffled)
    pd.testing.assert_frame_equal(table, original)


def test_movement_above_threshold_is_nonconverged_without_clipping():
    table = design(32)
    table.loc[(table.i >= 16) & (table.block == "AB") & (table.j == 1), "y"] += 10
    out, _ = run(table)
    assert (out.max_change > 0.02).all() and not out.converged.any()
    assert (out["total"] > 1).any()
    table.loc[table.block == "AB", "y"] = -10
    negative, _ = run(table)
    assert (negative["first"] < 0).any()


def test_zero_variance_is_explicit_not_zero_importance():
    table = design(32)
    table["y"] = 7.0
    out, _ = run(table)
    assert out.status.eq("unassessable").all()
    assert out["first"].isna().all() and out["total"].isna().all()
    assert out.converged.isna().all() and out.max_change.isna().all()
    assert out.bootstrap_valid.eq(0).all()


def test_invalid_bootstrap_keeps_point_but_refuses_interval():
    table = design(32)
    table.loc[table.i == 0, "y"] = 2.0
    ix = draws(32)
    ix[0] = 0
    out, _ = run(table, ix={("ramp", 5.0): ix})
    assert out.status.eq("assessable").all()
    assert out.interval_status.eq("unassessable").all()
    assert out.bootstrap_valid.eq(23).all()
    assert out.first_low.isna().all()


@pytest.mark.parametrize(
    "kind",
    [
        "AB_coord",
        "BA_coord",
        "AB_key",
        "BA_key",
        "AB_j",
        "missing_BA",
        "repeated_AB",
        "hybrid_physical",
    ],
)
def test_hybrid_coordinate_noise_and_membership_mutations_refuse(kind):
    table = design(32)
    ab = table.index[table.block == "AB"][0]
    ba = table.index[table.block == "BA"][0]
    if kind.endswith("coord"):
        table.loc[ab if kind.startswith("AB") else ba, "u1"] += 0.001
    elif kind.endswith("key"):
        table.loc[ab if kind.startswith("AB") else ba, "draw"] += 10000
    elif kind == "AB_j":
        table.loc[ab, "j"] = 0
    elif kind == "missing_BA":
        table = table.drop(ba)
    elif kind == "repeated_AB":
        table.loc[ab, "i"] = 1
    else:
        table.loc[ab, "target_min_rate"] += 0.001
    with pytest.raises(a.ContractError):
        run(table)


def test_families_and_yields_remain_separate_and_unknown_sizes_unassessable():
    table = pd.concat([design(32), design(32, "before", 10.0, offset=1000)])
    out, meta = run(table, sizes=(256, 512))
    assert len(out) == 5 and len(meta["scopes"]) == 2
    assert out.converged.isna().all()
    assert set(zip(out.family, out.yield_pp)) == {("ramp", 5.0), ("before", 10.0)}
    assert not meta["frozen_configuration"]


def test_ignored_noise_control_and_anchor_outputs_do_not_enter_estimators():
    table = design(32)
    out, _ = run(table)
    ignored = table.loc[[0, 1, 2]].copy()
    ignored["index"] += 1000000
    ignored["block"] = ["noise", "control", "stress"]
    ignored["y"] = 1e40
    augmented, _ = run(pd.concat([table, ignored], ignore_index=True))
    pd.testing.assert_frame_equal(out, augmented)


@pytest.mark.parametrize("sizes", [(128, 512), (3, 6), [16, 32], (True, 2)])
def test_convergence_requires_explicit_nested_power_of_two_prefixes(sizes):
    with pytest.raises(a.ContractError):
        run(design(32), sizes=sizes)


def test_batch_scaling_matches_kernel_for_extreme_finite_and_no_global_rng_change():
    table = design(32)
    table["y"] *= 1e250
    before = np.random.get_state()
    out, _ = run(table)
    expected = _indices(*arrays(table))
    np.testing.assert_allclose(out["first"], expected[0][:, 0], atol=1e-13)
    np.testing.assert_allclose(out["total"], expected[1][:, 0], atol=1e-13)
    after = np.random.get_state()
    np.testing.assert_array_equal(before[1], after[1])
    assert before[0] == after[0] and before[2:] == after[2:]


def numerical_runner():
    path = Path(__file__).resolve().parents[1] / "scripts/m2_numerics.py"
    spec = importlib.util.spec_from_file_location("m2_numerics_driver_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepared_cache(tmp_path):
    import duckdb

    driver = numerical_runner()
    table = design(8, "before")
    for i, measure in enumerate(driver.MEASURES):
        table[measure] = table.y * (i + 1)
    wide = tmp_path / "wide.parquet"
    connection = duckdb.connect(config={"threads": 1})
    connection.register("wide", table)
    connection.execute("COPY wide TO ? (FORMAT PARQUET)", [str(wide)])
    connection.close()
    path = tmp_path / "bootstrap.npz"
    matrix = draws(8, 1000)
    np.savez_compressed(path, **{"before__5.0": matrix})
    manifest = tmp_path / "inputs-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "m2-analysis-inputs/v1",
                "wide_sha256": driver.digest(wide),
                "bootstrap": {
                    "seed": 20261005,
                    "replicates": 1000,
                    "file_sha256": driver.digest(path),
                    "matrices": {
                        "before__5.0": {"shape": [1000, 8], "sha256": a._digest(matrix)}
                    },
                },
            }
        )
    )
    return driver, wide, path, manifest


def test_scope_driver_atomic_outputs_and_hash_bound_resume(tmp_path, monkeypatch):
    driver, wide, draws_path, manifest = prepared_cache(tmp_path)
    output = tmp_path / "output"
    result = driver.execute(
        wide, draws_path, manifest, output, manifest_sha256=driver.digest(manifest)
    )
    assert result["complete"] and not result["scientific_acceptance"]
    assert not result["full_four_family_two_horizon_yield_inventory"]
    assert len(result["scopes"]) == 2 and len(result["outputs"]) == 4
    originals = {name: (output / name).read_bytes() for name in result["outputs"]}

    def refuse(*args, **kwargs):
        raise AssertionError("accepted scope must not be recomputed")

    monkeypatch.setattr(s, "analyze_sensitivity", refuse)
    monkeypatch.setattr(a, "analyze_associations", refuse)
    resumed = driver.execute(
        wide, draws_path, manifest, output, manifest_sha256=driver.digest(manifest)
    )
    assert resumed["scopes"] == result["scopes"]
    for name, value in originals.items():
        assert (output / name).read_bytes() == value
    first = next(iter(result["outputs"]))
    (output / first).write_text("changed")
    with pytest.raises(ValueError, match="completed result bytes changed"):
        driver.execute(
            wide, draws_path, manifest, output, manifest_sha256=driver.digest(manifest)
        )


@pytest.mark.parametrize("target", ["manifest", "wide", "bootstrap"])
def test_scope_driver_refuses_modified_external_inputs_before_numerics(
    tmp_path, target
):
    driver, wide, draws_path, manifest = prepared_cache(tmp_path)
    pin = driver.digest(manifest)
    modified = {"manifest": manifest, "wide": wide, "bootstrap": draws_path}[target]
    modified.write_bytes(modified.read_bytes() + b"modified")
    with pytest.raises(ValueError, match="differs|differ"):
        driver.execute(
            wide, draws_path, manifest, tmp_path / "output", manifest_sha256=pin
        )


def test_scope_driver_preserves_method_failure_and_refuses_stale_configuration(
    tmp_path, monkeypatch
):
    driver, wide, draws_path, manifest = prepared_cache(tmp_path)
    output = tmp_path / "output"

    def fail(*args, **kwargs):
        raise ValueError("independent numerical failure witness")

    monkeypatch.setattr(a, "analyze_associations", fail)
    with pytest.raises(ValueError, match="failure witness"):
        driver.execute(
            wide, draws_path, manifest, output, manifest_sha256=driver.digest(manifest)
        )
    receipt = json.loads((output / "numerics-manifest.json").read_text())
    assert (
        not receipt["complete"] and receipt["failures"][0]["scope"] == "mm1/before/365"
    )
    driver.METHOD_CONFIGURATION = {**driver.METHOD_CONFIGURATION, "confidence": 0.9}
    with pytest.raises(ValueError, match="resume contract/source/input differs"):
        driver.execute(
            wide, draws_path, manifest, output, manifest_sha256=driver.digest(manifest)
        )


def test_actual_cli_subprocess_budget_and_manifest(tmp_path):
    driver, wide, draws_path, manifest = prepared_cache(tmp_path)
    output = tmp_path / "cli-output"
    env = {
        **os.environ,
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }
    result = subprocess.run(
        [
            sys.executable,
            str(Path(driver.__file__)),
            "--wide",
            str(wide),
            "--bootstrap",
            str(draws_path),
            "--manifest",
            str(manifest),
            "--manifest-sha256",
            driver.digest(manifest),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads((output / "numerics-manifest.json").read_text())
    assert receipt["complete"] and len(receipt["scopes"]) == 2
    # Linux ru_maxrss retains the forked parent's pre-exec high water, so a
    # large full-suite parent can inflate this value for a small fresh child.
    # The real execution budget is enforced externally by the job's cgroup.
    assert all(
        np.isfinite(scope["peak_process_RSS_MiB"]) and scope["peak_process_RSS_MiB"] > 0
        for scope in receipt["scopes"].values()
    )
