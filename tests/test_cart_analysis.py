import copy
import json

import numpy as np
import pandas as pd
import pytest

from avalanche_research.analysis import cart as kernel

SCOPE = {"family": "synthetic", "competing_yield_pp": 3., "horizon_days": 365, "measure": "toy"}


def frozen_fixture():
    x = np.tile([-2., -1., 1., 2.], 20)
    n = len(x); groups = [f"i{i//4:04d}" for i in range(n)]
    draw = (np.arange(1000)[:, None]+np.arange(20)[None, :]) % 20
    return {"X": np.column_stack([x, np.arange(n)]), "labels": x > 0,
        "sample_ids": [f"sample{i}" for i in range(n)], "block_ids": groups,
        "feature_names": ["x", "marker"], "scope": SCOPE, "bootstrap_indices": draw,
        "label_definition": "x>0", "independence_statement": "synthetic complete unit blocks"}


def test_frozen_wrapper_training_majority_and_paired_margin():
    r = kernel.analyze_cart(**frozen_fixture())
    assert r["outer_splits"] == 10 and r["inner_splits"] == 5
    assert r["ccp_alphas"] == [0., .0001, .001, .01, .05, .1, .25, .5]
    assert r["accuracy_interval95"] == [1., 1.]
    assert r["paired_difference_interval95"] == [.5, .5]
    assert r["margin"] == .5 and r["informative"] is True
    assert len(r["held_out_predictions"]) == 80


def test_paired_bound_does_not_subtract_unpaired_baseline_point():
    groups = ["a", "b"]
    indices = np.tile([[0, 0], [1, 1]], (500, 1))
    result = kernel._bootstrap(np.array([1., 0.]), np.array([1., 0.]), groups, indices)
    assert result["raw_interval95"] == [0., 1.]
    assert result["paired_interval95"] == [0., 0.]
    assert result["paired_interval95"][0] != result["raw_interval95"][0]-.5


def test_block_bootstrap_keeps_unequal_sized_units_event_weighted():
    groups = ["a"]+["b"]*3
    draws = np.tile([[0, 1]], (1000, 1))
    r = kernel._bootstrap(np.array([1., 0., 0., 0.]), np.zeros(4), groups, draws)
    assert r["raw_interval95"] == [.25, .25]


def test_one_class_explicit_unassessable_and_bad_draws_refuse():
    args = frozen_fixture(); args["labels"][:] = True
    r = kernel.analyze_cart(**args)
    assert r["status"] == "unassessable" and r["informative"] is None
    args["bootstrap_indices"][0, 0] = 999
    with pytest.raises(kernel.Refused, match="outside"):
        kernel.analyze_cart(**args)


def regression_fixture():
    a = frozen_fixture(); a["values"] = a.pop("labels").astype(float)*10.
    del a["label_definition"]
    return a


def test_continuous_tree_uses_training_mean_and_no_threshold():
    r = kernel.analyze_regression_cart(**regression_fixture())
    assert r["held_out_mse"] == 0 and r["held_out_r2"] == 1
    assert r["training_mean_baseline_mse"] == 25
    assert r["informative"] is None and r["informative_reason"] == "policy_not_prescribed"
    assert r["accuracy_interval95"] is None
    assert r["final_tree"]["depth"] == 1
    assert all(row["training_mean_baseline"] == 5 for row in r["held_out_predictions"])


def test_constant_continuous_measure_has_stump_and_undefined_r2():
    a = regression_fixture(); a["values"][:] = 7
    r = kernel.analyze_regression_cart(**a)
    assert r["held_out_mse"] == 0 and r["held_out_r2"] is None
    assert r["r2_reason"] == "constant_target" and r["final_tree"]["depth"] == 0


def test_regression_outer_labels_never_tune_own_fold():
    a = regression_fixture(); before = kernel.analyze_regression_cart(**a)
    ids = set(before["outer_folds"][0]["held_out"]["sample_ids"])
    indices = [i for i, name in enumerate(a["sample_ids"]) if name in ids]
    a["values"][indices] += 100
    after = kernel.analyze_regression_cart(**a)
    assert before["outer_folds"][0]["selection"] == after["outer_folds"][0]["selection"]
    assert [before["held_out_predictions"][i]["prediction"] for i in indices] == [after["held_out_predictions"][i]["prediction"] for i in indices]


def test_frozen_wrapper_refuses_labeled_alignment_mutations():
    a = frozen_fixture(); a["X"] = pd.DataFrame(a["X"], columns=a["feature_names"])
    a["labels"] = pd.Series(a["labels"], index=a["X"].index[::-1])
    with pytest.raises(kernel.Refused, match="aligned"):
        kernel.analyze_cart(**a)
    a = regression_fixture(); a["X"] = pd.DataFrame(a["X"], columns=["marker", "x"])
    with pytest.raises(kernel.Refused, match="feature"):
        kernel.analyze_regression_cart(**a)


def fixture():
    # Every dependence block contains both outcomes. Replicates travel together.
    x = np.tile(np.array([-2., -1., 1., 2.]), 12)
    n = len(x)
    return {"X": np.column_stack([x, np.arange(n)]), "labels": x > 0,
                "sample_ids": [f"r{i}" for i in range(n)],
                "block_ids": [f"b{i//4}" for i in range(n)],
                "feature_names": ["threshold_feature", "row_marker"],
                "stratum_id": "synthetic/response=0.5/family=A", "target_id": "toy_KPI_v1",
                "label_definition": "toy frozen threshold: outcome > 0, all runs successful",
                "independence_statement": "toy construction: 12 caller-declared independent blocks",
                "ccp_alphas": [0., 0.05, 0.6], "outer_splits": 3, "inner_splits": 2, "seed": 731}


def test_known_threshold_and_diagram_leaf_shares():
    result = kernel.analyze_mm2(**fixture())
    assert result["held_out_metrics"] == {"raw_accuracy": 1., "balanced_accuracy": 1.}
    assert result["held_out_majority_baseline"] == {"raw_accuracy": .5, "balanced_accuracy": .5}
    tree = result["final_tree"]
    assert tree["depth"] == 1
    assert tree["selected_ccp_alpha"] == .05  # strongest perfect declared pruning level
    assert tree["impurity_importance"]["threshold_feature"] == 1
    leaves = [node for node in tree["nodes"] if node["leaf"]]
    assert sorted(node["share_met"] for node in leaves) == [0., 1.]
    assert sum(node["n"] for node in leaves) == 48
    assert "digraph CART" in tree["dot"] and "met=24/24" in tree["dot"]
    json.dumps(result, allow_nan=False)


def test_whole_blocks_and_exact_out_of_fold_support():
    result = kernel.analyze_mm2(**fixture())
    held_ids, held_groups = [], []
    for outer in result["outer_folds"]:
        train, test = outer["train"], outer["held_out"]
        assert set(train["groups"]).isdisjoint(test["groups"])
        assert set(train["sample_ids"]).isdisjoint(test["sample_ids"])
        held_ids += test["sample_ids"]
        held_groups += test["groups"]
        for inner in outer["selection"]["folds"]:
            assert set(inner["train"]["groups"]).isdisjoint(inner["held_out"]["groups"])
            assert set(inner["train"]["groups"] + inner["held_out"]["groups"]) == set(train["groups"])
            assert set(inner["train"]["sample_ids"] + inner["held_out"]["sample_ids"]) == set(train["sample_ids"])
    assert sorted(held_ids) == sorted(fixture()["sample_ids"])
    assert len(held_groups) == len(set(held_groups)) == 12


def test_actual_fit_selection_never_sees_outer_test_rows(monkeypatch):
    calls = []
    actual = kernel._fit
    def spy(X, y, indices, alpha, seed, stage):
        calls.append((stage, set(X[indices, 1].astype(int))))
        return actual(X, y, indices, alpha, seed, stage)
    monkeypatch.setattr(kernel, "_fit", spy)
    result = kernel.analyze_mm2(**fixture())
    for i, outer in enumerate(result["outer_folds"]):
        forbidden = {int(r[1:]) for r in outer["held_out"]["sample_ids"]}
        relevant = [rows for stage, rows in calls if stage.startswith(f"outer{i}/")]
        assert relevant and all(rows.isdisjoint(forbidden) for rows in relevant)
    assert len([stage for stage, _ in calls if stage == "final/descriptive"]) == 1


def test_outer_outcome_perturbation_cannot_change_its_selection_or_predictions():
    args = fixture()
    before = kernel.analyze_mm2(**args)
    fold = before["outer_folds"][0]
    test_indices = [int(r[1:]) for r in fold["held_out"]["sample_ids"]]
    args["labels"][test_indices] = ~args["labels"][test_indices]
    after = kernel.analyze_mm2(**args)
    other = after["outer_folds"][0]
    assert fold["selection"] == other["selection"]
    assert fold["selected_ccp_alpha"] == other["selected_ccp_alpha"]
    assert [before["held_out_predictions"][i]["predicted_met"] for i in test_indices] == [after["held_out_predictions"][i]["predicted_met"] for i in test_indices]
    assert other["held_out_metrics"]["raw_accuracy"] == 0.


def test_fixed_grid_no_pruning_path_or_global_rng_mutation(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("label-dependent pruning path is forbidden")
    monkeypatch.setattr(kernel.DecisionTreeClassifier, "cost_complexity_pruning_path", forbidden)
    np.random.seed(918)
    state = copy.deepcopy(np.random.get_state())
    a = kernel.analyze_mm2(**fixture())
    b = kernel.analyze_mm2(**fixture())
    assert a == b
    after = np.random.get_state()
    assert state[0] == after[0] and np.array_equal(state[1], after[1]) and state[2:] == after[2:]
    assert all(f["selected_ccp_alpha"] in fixture()["ccp_alphas"] for f in a["outer_folds"])


def test_constant_features_are_visible_and_stump_equals_baseline():
    args = fixture()
    args["X"][:] = 1
    result = kernel.analyze_mm2(**args)
    assert result["constant_features"] == args["feature_names"]
    assert result["final_tree"]["leaves"] == 1
    assert result["final_tree"]["nodes"][0]["share_met"] == .5
    assert result["final_tree"]["selected_ccp_alpha"] == .6
    assert result["held_out_metrics"] == result["held_out_majority_baseline"]
    assert all(v == 0 for v in result["final_tree"]["impurity_importance"].values())


@pytest.mark.parametrize("key,value", [
    ("outer_splits", True), ("inner_splits", 2.), ("seed", np.int64(7)),
    ("outer_splits", 1), ("seed", -1), ("seed", 2**32),
    ("ccp_alphas", []), ("ccp_alphas", [0., 0.]), ("ccp_alphas", [1., 0.]),
    ("ccp_alphas", [True]), ("ccp_alphas", [float('nan')]),
    ("ccp_alphas", [float('inf')]), ("ccp_alphas", [10**1000]), ("ccp_alphas", [-.1]),
    ("stratum_id", " "), ("target_id", ""), ("label_definition", ""),
    ("independence_statement", ""),
])
def test_bad_declarations_refuse(key, value):
    args = fixture()
    args[key] = value
    with pytest.raises(kernel.Refused):
        kernel.analyze_mm2(**args)


@pytest.mark.parametrize("case", ["nan", "inf", "overflow", "bool_X", "complex_X", "object_X",
    "ragged", "empty", "bad_labels", "missing_label", "length", "duplicate_id",
    "empty_block", "bad_feature_names", "one_class", "few_blocks", "one_class_fold"])
def test_malformed_or_unassessable_complete_design_refuses(case):
    args = fixture()
    if case in ("nan", "inf", "overflow"):
        args["X"][0, 0] = {"nan": np.nan, "inf": np.inf, "overflow": 1e100}[case]
    elif case == "bool_X": args["X"] = args["X"] > 0
    elif case == "complex_X": args["X"] = args["X"].astype(complex)
    elif case == "object_X": args["X"] = args["X"].astype(str)
    elif case == "ragged": args["X"] = [[1], [2, 3]]
    elif case == "empty": args["X"] = np.empty((0, 2))
    elif case == "bad_labels": args["labels"] = args["labels"].astype(int)
    elif case == "missing_label": args["labels"] = args["labels"].astype(object); args["labels"][0] = None
    elif case == "length": args["labels"] = args["labels"][:-1]
    elif case == "duplicate_id": args["sample_ids"][0] = args["sample_ids"][1]
    elif case == "empty_block": args["block_ids"][0] = " "
    elif case == "bad_feature_names": args["feature_names"] = ["x", "x"]
    elif case == "one_class": args["labels"][:] = True
    elif case == "few_blocks": args["block_ids"] = ["one"]*len(args["labels"])
    elif case == "one_class_fold":
        args["block_ids"] = ["positive" if y else "negative" for y in args["labels"]]
        args["outer_splits"] = 2
    with pytest.raises(kernel.Refused):
        kernel.analyze_mm2(**args)


def test_inputs_are_unchanged():
    args = fixture()
    before = copy.deepcopy(args)
    kernel.analyze_mm2(**args)
    for key in args:
        if isinstance(args[key], np.ndarray): assert np.array_equal(args[key], before[key])
        else: assert args[key] == before[key]


def test_majority_baseline_uses_training_class_counts():
    args = fixture()
    args["labels"] = np.tile([False, True, True, True], 12)
    args["X"][:, 0] = np.tile([-1., 1., 2., 3.], 12)
    result = kernel.analyze_mm2(**args)
    assert result["held_out_majority_baseline"] == {"raw_accuracy": .75, "balanced_accuracy": .5}
    assert all(f["training_majority_met"] is True for f in result["outer_folds"])
    assert result["held_out_metrics"]["balanced_accuracy"] == 1.


@pytest.mark.parametrize("key", ["X", "labels"])
@pytest.mark.parametrize("mask_kind", ["one", "all"])
def test_explicitly_masked_entries_refuse_before_coercion(key, mask_kind):
    args = fixture()
    raw = args[key]
    mask = np.zeros(raw.shape, dtype=bool)
    if mask_kind == "all":
        mask[...] = True
    else:
        mask.flat[0] = True
    args[key] = np.ma.array(raw, mask=mask)
    # Underlying storage is otherwise finite and valid. It must not supply data.
    with pytest.raises(kernel.Refused, match="explicitly masked entries"):
        kernel.analyze_mm2(**args)


def test_all_false_masks_are_complete_positive_control():
    args = fixture()
    expected = kernel.analyze_mm2(**args)
    args["X"] = np.ma.array(args["X"], mask=False)
    args["labels"] = np.ma.array(args["labels"], mask=False)
    assert kernel.analyze_mm2(**args) == expected


def test_nomask_arrays_are_complete_positive_control():
    args = fixture()
    expected = kernel.analyze_mm2(**args)
    args["X"] = np.ma.array(args["X"], mask=np.ma.nomask)
    args["labels"] = np.ma.array(args["labels"], mask=np.ma.nomask)
    assert kernel.analyze_mm2(**args) == expected


@pytest.mark.parametrize("key", ["X", "labels"])
def test_masks_nested_in_ordinary_sequences_refuse(key):
    args = fixture()
    if key == "X":
        rows = list(args["X"])
        rows[0] = np.ma.array(rows[0], mask=[True, False])
        args["X"] = rows
    else:
        labels = list(args["labels"])
        labels[0] = np.ma.masked
        args["labels"] = labels
    with pytest.raises(kernel.Refused, match="explicitly masked entries"):
        kernel.analyze_mm2(**args)
