"""Independent analytic boxes and A-only selection/confirmation controls."""
import copy

import numpy as np
import pandas as pd
import pytest

from avalanche_research.analysis import prim

SCOPE = {"family": "synthetic", "competing_yield_pp": 3., "horizon_days": 365}


def square():
    A = np.array([(x, y) for x in np.linspace(0, 1, 21) for y in np.linspace(0, 1, 21)])
    B = np.array([(x, y) for x in np.linspace(.025, .975, 20) for y in np.linspace(.025, .975, 20)])
    def failed(X):
        return (X[:, 0] >= .25) & (X[:, 0] <= .75) & (X[:, 1] >= .25) & (X[:, 1] <= .75)
    return {"A": A, "failed_A": failed(A), "B": B, "failed_B": failed(B),
        "sample_ids_A": [f"A{i:04d}" for i in range(len(A))], "sample_ids_B": [f"B{i:04d}" for i in range(len(B))],
        "feature_names": ["x", "y"], "scope": SCOPE}


def test_analytic_square_and_independent_confirmation():
    result = prim.discover_confirm(**square())
    assert result["found"] is True
    assert [(r["lower"], r["upper"]) for r in result["selected_box"]["bounds"]] == [(.25, .75), (.25, .75)]
    assert result["selected_box"]["discovery"]["failing_in_box"] == 121
    assert result["confirmation"]["coverage"] == 1 and result["confirmation"]["density"] == 1
    assert result["confirmation"]["failing_in_box"] == 100
    assert sum(p["inside_box"] for p in result["confirmation_points"]) == 100


def test_pasting_recovers_positive_mass_without_density_loss():
    result = prim.discover_confirm(**square()); path = result["path"]
    first = next(i for i, row in enumerate(path) if row["operation"] == "paste")
    assert path[first]["discovery"]["coverage"] > path[first-1]["discovery"]["coverage"]
    assert path[-1]["discovery"]["coverage"] == 1
    assert path[-1]["discovery"]["density"] == 1
    assert path[first-1]["discovery"]["coverage"] < .7
    assert all(b["discovery"]["runs_in_box"] > a["discovery"]["runs_in_box"] for a, b in zip(path[first-1:], path[first:]))


def test_two_disjoint_corners_have_no_single_qualifying_box():
    a = square()
    for X, target in [(a["A"], "failed_A"), (a["B"], "failed_B")]:
        a[target] = ((X[:, 0] < .2) & (X[:, 1] < .2)) | ((X[:, 0] > .8) & (X[:, 1] > .8))
    result = prim.discover_confirm(**a)
    assert result["found"] is False and result["reason"] == "no_A_qualified_box"
    assert result["display_candidate"] and result["selected_box"] is None
    assert result["confirmation"] is None


def test_B_outcomes_and_locations_cannot_change_A_choice():
    a = square(); before = prim.discover_confirm(**a)
    a["failed_B"][:] = False; a["B"] += 100
    after = prim.discover_confirm(**a)
    assert before["selected_box"] == after["selected_box"] and before["path"] == after["path"]
    assert not after["found"] and after["reason"] == "no_confirmation_failures"


def test_all_fail_no_fail_empty_and_failed_confirmation_are_explicit():
    a = square(); a["failed_A"][:] = True; a["failed_B"][:] = True
    r = prim.discover_confirm(**a)
    assert r["found"] and len(r["path"]) == 1 and r["selected_box"]["restricted_dimensions"] == 0
    a["failed_A"][:] = False
    assert prim.discover_confirm(**a)["reason"] == "no_discovery_failures"
    a = square(); a["B"] = np.empty((0, 2)); a["failed_B"] = np.empty(0, dtype=bool); a["sample_ids_B"] = []
    assert prim.discover_confirm(**a)["reason"] == "empty_confirmation"
    a = square(); a["failed_B"] = ~a["failed_B"]
    r = prim.discover_confirm(**a)
    assert r["reason"] == "B_confirmation_failed" and r["confirmation"]["density"] == 0


def test_aligned_rows_and_columns_reorder_without_changing_box():
    a = square(); expected = prim.discover_confirm(**a)
    for matrix, labels, ids in [("A", "failed_A", "sample_ids_A"), ("B", "failed_B", "sample_ids_B")]:
        a[matrix] = a[matrix][::-1, ::-1]; a[labels] = a[labels][::-1]; a[ids] = a[ids][::-1]
    a["feature_names"] = ["y", "x"]
    actual = prim.discover_confirm(**a)
    assert actual == expected


def test_labeled_dataframe_permutations_and_incomplete_labels_refuse():
    a = square(); a["A"] = pd.DataFrame(a["A"], columns=["x", "y"])
    a["failed_A"] = pd.Series(a["failed_A"], index=a["A"].index[::-1])
    with pytest.raises(prim.Refused, match="aligned"):
        prim.discover_confirm(**a)
    a = square(); a["B"] = pd.DataFrame(a["B"], columns=["y", "x"])
    with pytest.raises(prim.Refused, match="feature"):
        prim.discover_confirm(**a)
    for value in [np.zeros(441), np.full(441, np.nan), np.ma.array(square()["failed_A"], mask=[True]+[False]*440)]:
        a = square(); a["failed_A"] = value
        with pytest.raises(prim.Refused):
            prim.discover_confirm(**a)


def test_source_mutation_and_reused_discovery_ID_refuse():
    a = square(); a["A"][0, 0] = np.nan
    with pytest.raises(prim.Refused, match="nonfinite"):
        prim.discover_confirm(**a)
    a = square(); a["sample_ids_B"][0] = a["sample_ids_A"][0]
    with pytest.raises(prim.Refused, match="overlap"):
        prim.discover_confirm(**a)
    a = square(); before = copy.deepcopy(a)
    prim.discover_confirm(**a)
    for name in ("A", "B", "failed_A", "failed_B"):
        np.testing.assert_array_equal(a[name], before[name])
