"""Synthetic public-API checks and independent rank-regression references."""

import numpy as np
import pandas as pd
import pytest
from scipy.stats import pearsonr, rankdata

from avalanche_research.analysis.rank_associations import (
    ContractError,
    Resampling,
    _draw_indices,
    analyze_mm1,
)


def table(x, y, **extra):
    n = len(x)
    expected = pd.DataFrame(
        {
            "row_id": ["r" + str(i) for i in range(n)],
            "run": [0] * n,
            "pair_id": [""] * n,
            "variant": ["A"] * n,
            "seed": list(range(n)),
            "model_pin": ["synthetic:model"] * n,
            "data_pin": ["synthetic:data"] * n,
            "design_pin": ["synthetic:design"] * n,
            "response": [0.0] * n,
            "x": x,
            **extra,
        }
    )
    rows = expected.copy()
    rows["status"] = "success"
    rows["disposition"] = ""
    rows["y"] = y
    rows.attrs["cell_accounting"] = {"expected": n, "success": n, "failed": 0}
    return rows


def contract(unit="row", seed=17, replicates=24):
    return Resampling(
        unit,
        None if unit == "row" else "block",
        "Synthetic caller asserts these whole units independent",
        replicates,
        0.9,
        seed,
    )


def analyze(t, params=("x",), spec=None):
    return analyze_mm1(
        t,
        params,
        ["y"],
        response_column="response",
        resampling=contract() if spec is None else spec,
    )


def relationship(result, parameter="x", method="spearman", variant="A", response=0.0):
    return next(
        r
        for r in result["relationships"]
        if r["parameter"] == parameter
        and r["method"] == method
        and r["variant"] == variant
        and r["response"] == response
    )


@pytest.mark.parametrize("sign", [1, -1])
def test_monotonic_signed_one(sign):
    t = table(list(range(12)), [sign * i for i in range(12)])
    result = analyze(t)
    for method in ["spearman", "prcc"]:
        r = relationship(result, method=method)
        assert r["point"]["coefficient"] == pytest.approx(sign, abs=2e-15)
        assert r["point"]["rows"] == 12 and r["point"]["parameter_unique"] == 12
        assert r["interval"]["status"] == "assessable"
        assert r["interval"]["bounds"] == pytest.approx([sign, sign], abs=2e-15)


def test_average_rank_ties_and_exact_large_integers():
    x = [1, 1, 2, 3, 3, 4]
    tied = relationship(analyze(table(x, x)))
    assert tied["point"]["coefficient"] == pytest.approx(1)
    assert tied["point"]["rows"] == 6 and tied["point"]["parameter_unique"] == 4
    huge = [2**60 + i for i in range(12)]
    assert relationship(analyze(table(huge, list(range(12)))))["point"][
        "coefficient"
    ] == pytest.approx(1)


@pytest.mark.parametrize(
    "x,y,reason",
    [
        ([0] * 8, list(range(8)), "constant_parameter"),
        (list(range(8)), [0] * 8, "constant_kpi"),
    ],
)
def test_constants_and_zero_outcomes_explicitly_undefined(x, y, reason):
    r = relationship(analyze(table(x, y)))
    assert r["point"]["reason"] == reason and r["point"]["coefficient"] is None
    assert r["point"]["rows"] == 8 and r["interval"]["status"] == "unassessable"


def test_prcc_matches_independent_normal_equation_rank_regression():
    x = np.arange(1, 13)
    z = np.array([2, 5, 1, 7, 3, 8, 4, 6, 12, 9, 11, 10])
    y = np.array([1, 4, 2, 5, 3, 7, 6, 8, 10, 9, 12, 11])
    result = analyze(table(x, y, z=z), params=("x", "z"))
    ranked_x, ranked_y, ranked_z = map(rankdata, [x, y, z])
    control = np.column_stack([np.ones(len(x)), ranked_z])
    rx = ranked_x - control @ np.linalg.solve(control.T @ control, control.T @ ranked_x)
    ry = ranked_y - control @ np.linalg.solve(control.T @ control, control.T @ ranked_y)
    reference = float(pearsonr(rx, ry).statistic)
    r = relationship(result, method="prcc")
    assert r["point"]["coefficient"] == pytest.approx(reference, abs=2e-14)
    assert r["point"]["control_rank"] == 2 and r["point"]["residual_df"] == 9


def test_rank_deficiency_and_unresolved_residuals_are_not_pseudoinverse_certainty():
    x = list(range(10))
    z = [2, 5, 1, 7, 3, 8, 4, 6, 9, 0]
    result = analyze(table(x, z, z=z, w=z), params=("x", "z", "w"))
    r = relationship(result, method="prcc")
    assert r["point"]["reason"] == "rank_deficient_controls"
    assert (
        r["point"]["coefficient"] is None and r["interval"]["status"] == "unassessable"
    )
    other = relationship(result, parameter="z", method="prcc")
    assert other["point"]["reason"] == "unresolved_parameter_residual"


def test_prcc_reports_nonpositive_residual_df():
    t = table([1, 2, 3], [3, 1, 2], z=[2, 3, 1])
    r = relationship(analyze(t, params=("x", "z")), method="prcc")
    assert r["point"]["reason"] == "nonpositive_residual_df"


def test_whole_blocks_cross_strata_and_fixed_seed_intervals():
    x = list(range(12)) * 4
    variants = ["A"] * 24 + ["B"] * 24
    responses = [0.0] * 12 + [1.0] * 12 + [0.0] * 12 + [1.0] * 12
    signs = [1] * 12 + [-1] * 12 + [-1] * 12 + [1] * 12
    t = table(
        x,
        [i * s for i, s in zip(x, signs)],
        variant=variants,
        response=responses,
        block=["b" + str(i) for i in x],
    )
    spec = contract("block", seed=3)
    indices = _draw_indices(t, spec, np.random.default_rng(spec.seed))
    # Every member in each declared block has exactly the same multiplicity,
    # independently checking that cross-variant/response pairing is preserved.
    counts = np.bincount(indices, minlength=len(t))
    for block in t.block.unique():
        assert len(set(counts[t.block.to_numpy() == block])) == 1
    first = analyze(t, spec=spec)
    assert first == analyze(t, spec=spec)
    assert len(first["relationships"]) == 8
    for variant, response, sign in [
        ("A", 0.0, 1),
        ("A", 1.0, -1),
        ("B", 0.0, -1),
        ("B", 1.0, 1),
    ]:
        r = relationship(first, variant=variant, response=response)
        assert r["point"]["coefficient"] == pytest.approx(sign)
        assert r["independent_units"] == 12 and r["point"]["rows"] == 12
        assert r["interval"]["bounds"] == pytest.approx([sign, sign])


def test_undefined_bootstrap_draws_are_visible_and_not_dropped_from_interval():
    r = relationship(
        analyze(table([1, 2], [1, 2]), spec=contract(seed=0, replicates=20))
    )
    assert r["point"]["status"] == "assessable"
    assert 0 < r["bootstrap_assessable"] < 20
    assert (
        sum(r["bootstrap_undefined_reasons"].values()) + r["bootstrap_assessable"] == 20
    )
    assert r["interval"]["status"] == "unassessable" and r["interval"]["bounds"] is None


def test_replicated_or_paired_rows_refuse_row_iid():
    t = table([1, 1, 2, 2], [1, 2, 2, 3], row_id=["a", "a", "b", "b"], run=[0, 1, 0, 1])
    with pytest.raises(ContractError, match="replicated"):
        analyze(t)
    t = table(
        [1, 1, 2, 2],
        [1, 2, 2, 3],
        variant=["A", "B", "A", "B"],
        pair_id=["p1", "p1", "p2", "p2"],
        seed=[1, 1, 2, 2],
        block=["p1", "p1", "p2", "p2"],
    )
    with pytest.raises(ContractError, match="paired"):
        analyze(t)
    got = analyze(t, spec=contract("block"))
    assert got["input_rows"] == 4


def test_failed_missing_unknown_and_nonempty_disposition_refuse_without_filtering():
    t = table(list(range(8)), list(range(8)))
    for column, value in [
        ("status", "failed"),
        ("status", None),
        ("disposition", "exclude"),
        ("y", np.nan),
        ("x", True),
    ]:
        changed = t.copy()
        changed[column] = changed[column].astype(object)
        changed.loc[0, column] = value
        with pytest.raises(ContractError):
            analyze(changed)
    with pytest.raises(ContractError, match="accounting"):
        analyze(t.iloc[:-1].copy())
    # An upstream-valid failed row with null KPI is still not authorized for MM1.
    t.drop(columns=["status", "disposition", "y"])
    rows = t.copy()
    rows.loc[0, "status"] = "failed"
    rows.loc[0, "disposition"] = "owner_hold"
    rows["y"] = rows.y.astype(float)
    rows.loc[0, "y"] = np.nan
    validated = rows.copy()
    validated.attrs["cell_accounting"] = {
        "expected": len(rows),
        "success": len(rows) - 1,
        "failed": 1,
    }
    with pytest.raises(ContractError, match="owner policy"):
        analyze(validated)


def test_input_and_global_rng_are_unchanged():
    t = table(list(range(10)), list(range(10)))
    before = t.copy(deep=True)
    state = np.random.get_state()
    analyze(t)
    after = np.random.get_state()
    pd.testing.assert_frame_equal(t, before)
    assert (
        state[0] == after[0]
        and np.array_equal(state[1], after[1])
        and state[2:] == after[2:]
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"unit": "seed"},
        {"seed": True},
        {"seed": -1},
        {"replicates": True},
        {"replicates": 1},
        {"confidence": 0},
        {"confidence": np.nan},
        {"independence_statement": ""},
        {"block_column": "block"},
    ],
)
def test_invalid_resampling_contract_refuses(changes):
    values = {
        "unit": "row",
        "block_column": None,
        "independence_statement": "synthetic row independence",
        "replicates": 10,
        "confidence": 0.9,
        "seed": 1,
    }
    with pytest.raises(ContractError):
        Resampling(**(values | changes))


def test_roles_and_insufficient_blocks_refuse():
    t = table(list(range(8)), list(range(8)), block=["b"] * 8)
    with pytest.raises(ContractError, match="two declared"):
        analyze(t, spec=contract("block"))
    with pytest.raises(ContractError, match="overlap"):
        analyze_mm1(t, ["x"], ["x"], response_column="response", resampling=contract())
    with pytest.raises(ContractError, match="distinct"):
        analyze_mm1(t, ["x"], ["y"], response_column="variant", resampling=contract())
