"""Hand-calculated policy fixtures; no sweep files or generated randomness."""

import hashlib
import json
import runpy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from avalanche_research.analysis.decision_summary import (
    GRID,
    ContractError,
    clustered_mean_interval,
    clustered_pass_share,
    confidence_ratings,
    design_rankings,
    pass_share_flags,
    point_estimates,
    select_and_confirm,
    sign_reversals,
    summarize_pass_shares,
    threshold_outcomes,
)


def cells():
    return pd.DataFrame(
        [
            {
                "family": "after",
                "yield_pp": 3,
                "horizon_days": 365,
                "measure": "issuance_saved",
                "input": "rate",
                "method": "spearman",
                "renewal_band": r,
                "entry_band": e,
                "coefficient": 0.5,
                "ci_low": 0.1,
                "ci_high": 0.8,
                "status": "assessable",
            }
            for r, e in GRID
        ]
    )


def test_nine_cell_high_medium_low_and_missing_are_distinct():
    frame = cells()
    assert confidence_ratings(frame).iloc[0].confidence_rating == "High"
    frame.loc[0, "ci_low"] = 0
    assert confidence_ratings(frame).iloc[0].confidence_rating == "Medium"
    frame.loc[0, ["coefficient", "ci_low", "ci_high"]] = [-0.5, -0.8, -0.1]
    assert confidence_ratings(frame).iloc[0].confidence_rating == "Low"
    missing = confidence_ratings(frame.iloc[1:]).iloc[0]
    assert missing.confidence_rating == "not rated"
    assert missing.reason == "missing_response_cell"


def test_undefined_constant_or_interval_cannot_be_high_or_medium():
    frame = cells()
    frame.loc[0, "status"] = "constant_kpi"
    assert confidence_ratings(frame).iloc[0].confidence_rating == "not rated"
    frame = cells()
    frame.loc[0, "ci_low"] = np.nan
    assert confidence_ratings(frame).iloc[0].reason == "unassessable_interval"
    frame = cells()
    frame["interval_status"] = "assessable"
    frame.loc[0, "interval_status"] = "unassessable"
    assert confidence_ratings(frame).iloc[0].confidence_rating == "not rated"


def test_anchors_do_not_silently_enter_grid_or_duplicate_cells():
    frame = cells()
    with pytest.raises(ContractError, match="Duplicate"):
        confidence_ratings(pd.concat([frame, frame.iloc[:1]]))
    extra = frame.iloc[:1].assign(renewal_band="stress_renewal", entry_band="zero")
    with pytest.raises(ContractError, match="undeclared"):
        confidence_ratings(pd.concat([frame, extra]))


def test_sign_reversal_is_adjacent_band_statement_without_interpolation():
    frame = cells()
    frame.loc[frame.renewal_band.eq("high"), "coefficient"] = -0.5
    result = sign_reversals(frame)
    assert len(result) == 12
    reversals = result[result.status.eq("reversal")]
    assert len(reversals) == 3
    assert set(reversals.response_axis) == {"renewal"}
    assert set(reversals.from_band) == {"middle"}
    assert reversals.band_boundary.to_numpy() == pytest.approx([0.1 * 2 / 3] * 3)
    assert result.resolution.to_numpy() == pytest.approx([0.1 / 3] * 12)
    assert not sign_reversals(cells()).sign_changes.any()


def test_missing_and_zero_edges_and_before180_remain_unassessable():
    frame = cells()
    frame.loc[0, "coefficient"] = 0
    assert "zero_endpoint" in set(sign_reversals(frame).reason)
    assert "missing_response_cell" in set(sign_reversals(frame.iloc[1:]).reason)
    result = sign_reversals(cells().assign(family="before", horizon_days=180))
    assert result.status.eq("unassessable").all()
    assert result.sign_changes.isna().all()


def test_bootstrap_repeats_entire_unequal_clusters_not_rows():
    # Unit A has 2/2 passes, B 0/1. Four resamples: AA, AB, BA, BB.
    indices = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
    result = clustered_pass_share([True, True, False], ["a", "a", "b"], indices)
    reference = np.quantile([1, 2 / 3, 2 / 3, 0], [0.025, 0.975])
    assert result["pass_share"] == pytest.approx(2 / 3)
    assert [result["ci_low"], result["ci_high"]] == pytest.approx(reference)
    assert result["units_present"] == 2
    assert len(result["bootstrap_sha256"]) == 64


def test_finite_mean_interval_uses_same_cluster_indices_and_raw_scale():
    indices = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
    result = clustered_mean_interval([10.0, 20.0, -5.0], [0, 0, 1], indices)
    assert result["mean"] == pytest.approx(25 / 3)
    assert [result["ci_low"], result["ci_high"]] == pytest.approx(
        np.quantile([15.0, 25 / 3, 25 / 3, -5.0], [0.025, 0.975])
    )
    flags = clustered_pass_share([True, True, False], [0, 0, 1], indices)
    assert flags["bootstrap_sha256"] == result["bootstrap_sha256"]
    with pytest.raises(ContractError, match="finite"):
        clustered_mean_interval([1, np.nan], [0, 1], indices)


def test_missing_units_in_cell_retain_empty_replicate_invalidation():
    result = clustered_pass_share(
        [True], ["a"], np.array([[0, 0], [1, 1]]), unit_order=["a", "b"]
    )
    assert result["pass_share"] == 1
    assert result["invalid_replicates"] == 1
    assert result["ci_low"] is None
    assert result["status"] == "unassessable"


def test_single_unit_has_point_but_no_qualified_interval():
    result = clustered_pass_share([True, False], [0, 0], np.array([[0], [0]]))
    assert result["pass_share"] == 0.5
    assert result["status"] == "unassessable"
    assert result["reason"] == "insufficient_units"
    assert result["ci_low"] is None
    with pytest.raises(ContractError, match="missing"):
        clustered_pass_share([True, False], [None, 1], np.array([[0, 1], [1, 0]]))


def test_missing_yields_do_not_support_every_yield_order_claim():
    result = design_rankings(
        designs(), ["issuance_saved"], higher_is_better={"issuance_saved": True}
    )
    assert result.order_same_at_every_yield.isna().all()


@pytest.mark.parametrize(
    "indices",
    [
        np.array([[0, 2], [1, 0]]),
        np.array([[0.0, 1.0], [1.0, 0.0]]),
        np.array([[0, 1]]),
    ],
)
def test_invalid_bootstrap_contracts(indices):
    with pytest.raises(ContractError):
        clustered_pass_share([True, False], ["a", "b"], indices)


def test_non_boolean_flags_and_split_family_bootstraps_refused():
    with pytest.raises(ContractError, match="Boolean"):
        clustered_pass_share([1, 0], ["a", "b"], np.array([[0, 1], [1, 0]]))
    rows = pd.DataFrame(
        {
            "family": ["a", "b"],
            "yield_pp": [3, 3],
            "unit": [0, 1],
            "passed": [True, False],
        }
    )
    with pytest.raises(ContractError, match="independent"):
        summarize_pass_shares(
            rows,
            pass_column="passed",
            unit_column="unit",
            group_columns=["family"],
            bootstrap_indices=np.array([[0, 1], [1, 0]]),
            unit_order=[0, 1],
        )


@pytest.mark.parametrize(
    "share,expected",
    [
        (0.9, (True, True, True, False)),
        (0.7, (False, True, True, False)),
        (0.5, (False, False, True, False)),
        (0.05, (False, False, False, False)),
        (0.95, (True, True, True, False)),
        (0.049, (False, False, False, True)),
        (0.951, (True, True, True, True)),
    ],
)
def test_frozen_cutoffs_are_inclusive_and_flags_strict(share, expected):
    assert tuple(pass_share_flags(share).values()) == expected
    assert all(value is None for value in pass_share_flags(None).values())


def test_threshold_alternatives_boundary_and_no_invented_reported_goal():
    frame = pd.DataFrame(
        {
            "issuance_saved": [0.1, 0],
            "validator_stake_retained": [0.9, 1],
            "net_inflation": [0.05, 0.02],
            "return_margin": [0, -0.01],
            "active_validators_retained": [0.5, 1],
        }
    )
    result = threshold_outcomes(frame, net_inflation_alternative=0.02397867184808486)
    lookup = result.groupby(
        ["measure", "threshold_alternative"], sort=False
    ).passed.apply(list)
    assert lookup["validator_stake_retained", "primary"] == [True, True]
    assert lookup["validator_stake_retained", "no_stake_loss"] == [False, True]
    assert lookup["net_inflation", "primary"] == [True, True]
    assert lookup["net_inflation", "trailing_year"] == [False, True]
    assert lookup["return_margin", "primary"] == [True, False]
    assert lookup["issuance_saved", "primary"] == [True, False]
    assert "active_validators_retained" not in result.measure.values


def designs():
    return pd.DataFrame(
        [
            {
                "family": family,
                "yield_pp": yield_pp,
                "horizon_days": horizon,
                "renewal_band": "low",
                "entry_band": "middle",
                "block": block,
                "issuance_saved": value,
            }
            for yield_pp in (3, 5)
            for horizon in (180, 365)
            for family, values in (
                ("before", [0.0, 0.0]),
                ("a", [0.1, 0.3]),
                ("b", [0.2, 0.4]),
            )
            for block, value in zip(("A", "B"), values, strict=True)
        ]
    )


def test_design_means_spread_rank_ties_and_before180_exclusion():
    result = design_rankings(
        designs(),
        ["issuance_saved"],
        higher_is_better={"issuance_saved": True},
        expected_yields=(3, 5),
    )
    assert not ((result.family == "before") & (result.horizon_days == 180)).any()
    assert result.attrs["excluded_before_180_runs"] == 4
    row = result[
        (result.family == "a") & (result.yield_pp == 3) & (result.horizon_days == 365)
    ].iloc[0]
    assert (row["mean"], row.p10, row.p90, row["rank"], row.runs) == pytest.approx(
        (0.2, 0.12, 0.28, 2, 2)
    )
    assert result.order_same_at_every_yield.all()
    changed = designs()
    changed.loc[(changed.family == "a") & (changed.yield_pp == 5), "issuance_saved"] = 1
    reversed_order = design_rankings(
        changed,
        ["issuance_saved"],
        higher_is_better={"issuance_saved": True},
        expected_yields=(3, 5),
    )
    assert not reversed_order.order_same_at_every_yield.any()
    with pytest.raises(ContractError, match="relative"):
        design_rankings(
            designs().assign(net_inflation=0.02),
            ["net_inflation"],
            higher_is_better={"net_inflation": False},
        )


def test_point_uses_A_only_then_numeric_source_index():
    rows = pd.DataFrame(
        {
            "index": [10, 2, 0],
            "family": ["after"] * 3,
            "horizon_days": [365] * 3,
            "block": ["A", "A", "B"],
            "issuance_saved": [0.3, 0.3, 99],
            "rate": [1, 2, 3],
        }
    )
    result = point_estimates(
        rows, input_column="rate", group_columns=["family", "horizon_days"]
    ).iloc[0]
    assert result.source_index == 2
    assert result.value == 2
    assert result.provisional
    rows.loc[rows.block == "B", "issuance_saved"] = -99
    assert (
        point_estimates(
            rows, input_column="rate", group_columns=["family", "horizon_days"]
        )
        .iloc[0]
        .source_index
        == 2
    )


def candidate_fixture():
    a = pd.DataFrame({"block": ["A"] * 4, "rate": [0, 0.2, 0.8, 1]})
    b = pd.DataFrame(
        {
            "block": ["B"] * 4,
            "rate": [0, 0.2, 0.8, 1],
            "passed": [False, False, True, True],
            "unit": [0, 1, 2, 3],
        }
    )
    candidates = pd.DataFrame(
        {
            "candidate": ["left", "right"],
            "input": ["rate"] * 2,
            "lower": [0, 0.8],
            "upper": [0.2, 1],
            "discovery_score": [0.9, 0.8],
        }
    )
    indices = np.array([[0, 1, 2, 3], [3, 2, 1, 0]])
    return a, b, candidates, indices


def test_failed_B_confirmation_does_not_select_other_B_successful_box():
    a, b, candidates, indices = candidate_fixture()
    result = select_and_confirm(
        a,
        b,
        candidates,
        pass_column="passed",
        unit_column="unit",
        bootstrap_indices=indices,
        family="after",
    )
    assert result["candidate"] == "left"
    assert result["pass_share"] == 0
    assert result["status"] == "not_found"
    b["passed"] = ~b.passed
    changed = select_and_confirm(
        a,
        b,
        candidates,
        pass_column="passed",
        unit_column="unit",
        bootstrap_indices=indices,
        family="after",
    )
    assert changed["candidate"] == "left"
    assert changed["status"] == "found"
    assert changed["goal_interval_status"] == "not_evaluated_by_pass_share"


def test_range_not_applicable_empty_and_wrong_role_contracts():
    a, b, candidates, indices = candidate_fixture()
    arguments = {
        "pass_column": "passed",
        "unit_column": "unit",
        "bootstrap_indices": indices,
    }
    assert (
        select_and_confirm(a, b, candidates, family="before", **arguments)["status"]
        == "not_applicable"
    )
    assert (
        select_and_confirm(a, b, candidates.iloc[:0], family="after", **arguments)[
            "status"
        ]
        == "not_found"
    )
    no_support = b.assign(rate=2)
    assert (
        select_and_confirm(a, no_support, candidates, family="after", **arguments)[
            "reason"
        ]
        == "no_B_support"
    )
    with pytest.raises(ContractError, match="A only"):
        select_and_confirm(
            a.assign(block="B"), b, candidates, family="after", **arguments
        )


def test_multivariate_bounds_all_constrain_membership():
    a, b, candidates, indices = candidate_fixture()
    a["response"] = [0, 0.1, 0.2, 0.3]
    b["response"] = [0, 0.1, 0.2, 0.3]
    first = candidates.iloc[:1]
    second = first.assign(input="response", lower=0.05, upper=0.15)
    result = select_and_confirm(
        a,
        b,
        pd.concat([first, second]),
        pass_column="passed",
        unit_column="unit",
        bootstrap_indices=indices,
        family="after",
    )
    assert result["runs"] == 1
    assert result["discovery_runs"] == 1
    assert len(result["bounds"]) == 2


def test_goal_mean_interval_is_separate_from_successful_limit_pass_share():
    a = pd.DataFrame({"block": ["A", "A"], "rate": [0.0, 1.0]})
    b = pd.DataFrame(
        {
            "block": ["B", "B"],
            "rate": [0.0, 1.0],
            "passed": [True, True],
            "unit": [0, 1],
            "issuance_saved": [-0.1, 0.3],
        }
    )
    candidates = pd.DataFrame(
        {
            "candidate": ["frozen"],
            "input": ["rate"],
            "lower": [0.0],
            "upper": [1.0],
            "discovery_score": [1.0],
        }
    )
    indices = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
    arguments = {
        "pass_column": "passed",
        "unit_column": "unit",
        "bootstrap_indices": indices,
        "family": "after",
        "goal_column": "issuance_saved",
    }
    result = select_and_confirm(a, b, candidates, **arguments)
    assert result["pass_share"] == 1
    assert result["meets_90"]
    assert result["goal_mean"] == pytest.approx(0.1)
    assert result["goal_ci_low"] < 0
    assert result["status"] == "not_found"
    assert not result["goal_meets"]
    b["issuance_saved"] = [0.1, 0.3]
    result = select_and_confirm(a, b, candidates, **arguments)
    assert result["goal_meets"]
    assert result["status"] == "found"
    assert result["bootstrap_sha256"] == result["goal_bootstrap_sha256"]


def decision_driver_fixture():
    rows = []
    for block in ("A", "B", "zero", "stress", "noise"):
        for i in range(18 if block in ("A", "B") else 4):
            for j in (
                range(1, 4)
                if block == "stress"
                else range(8)
                if block == "noise"
                else [0]
            ):
                band = GRID[i % 9]
                row = {
                    "index": len(rows),
                    "family": "ramp",
                    "yield_pp": 3.0,
                    "horizon_days": 365,
                    "block": block,
                    "i": i,
                    "j": j,
                    "renewal_band": band[0],
                    "entry_band": band[1],
                    "renewal_response": 0.02,
                    "entry_response": 0.03,
                    "target_min_rate": 0.05 + 0.002 * i,
                    "issuance_saved": 0.1 + 0.001 * i,
                    "validator_stake_retained": 0.95,
                    "active_validators_retained": 0.98,
                    "net_inflation": 0.04,
                    "return_margin": 0.04,
                }
                for cost, fraction in (("low", 0.0075), ("mid", 0.015), ("high", 0.03)):
                    row[f"return_margin_{cost}"] = 0.04 - fraction
                    row[f"return_margin_{cost}_fitting_price"] = (
                        0.04 - fraction * 14.58 / 26.10
                    )
                rows.append(row)
    bootstrap = {
        "ramp__3.0": np.tile(np.arange(18), (4, 1)),
        "anchor__3.0": np.tile(np.arange(4), (4, 1)),
        "noise__ramp__3.0": np.tile(np.arange(4), (4, 1)),
    }
    return pd.DataFrame(rows), bootstrap


def test_driver_preserves_nine_cells_separate_stress_noise_and_A_selection():
    module = runpy.run_path(
        str(Path(__file__).parents[1] / "scripts" / "m2_decisions.py")
    )
    wide, bootstrap = decision_driver_fixture()
    result = module["summarize_decisions"](wide, bootstrap, replicates=4)
    passes = result["pass-shares.csv"]
    assert set(passes.population) == {
        "all",
        "grid",
        "zero",
        "stress_1",
        "stress_2",
        "stress_3",
        "noise",
    }
    assert len(result["point-estimates.csv"]) == 9
    differences = result["baseline-comparison-cells.csv"]
    assert len(differences) == 13 * 3
    stake = differences[differences.measure.eq("validator_stake_retained")]
    assert np.allclose(stake.coefficient, -0.05)
    assert result["range-confirmations.csv"].provisional.all()
    assert result["range-confirmations.csv"].tier.notna().all()
    zero_cost = result["range-confirmations.csv"].cost_level.eq("zero")
    assert (
        not result["range-confirmations.csv"]
        .loc[zero_cost, "eligible_for_recommendation"]
        .any()
    )
    assert all(
        candidate["positive_target"] == "PASS"
        for candidate in result["A-PASS-selected-boxes.json"]
    )
    # Every A-selected candidate is invariant to B outcome mutation.
    changed = wide.copy()
    changed.loc[changed.block.eq("B"), "issuance_saved"] = -0.2
    alternative = module["summarize_decisions"](changed, bootstrap, replicates=4)
    assert (
        result["A-PASS-selected-boxes.json"]
        == alternative["A-PASS-selected-boxes.json"]
    )


def test_driver_cli_hash_bound_parquet_and_npz_replay(tmp_path):
    import duckdb

    module = runpy.run_path(
        str(Path(__file__).parents[1] / "scripts" / "m2_decisions.py")
    )
    wide, bootstrap = decision_driver_fixture()
    wide["boost_max"], wide["exponent"] = np.nan, np.nan
    wide_path = tmp_path / "wide.parquet"
    bootstrap_path = tmp_path / "bootstrap.npz"
    connection = duckdb.connect()
    connection.register("fixture", wide)
    connection.execute("COPY fixture TO ? (FORMAT PARQUET)", [str(wide_path)])
    connection.close()
    matrices = {key: np.tile(array[:1], (1000, 1)) for key, array in bootstrap.items()}
    np.savez(bootstrap_path, **matrices)

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = {
        "wide_sha256": sha(wide_path),
        "bootstrap": {
            "file_sha256": sha(bootstrap_path),
            "matrices": {
                key: {
                    "shape": list(array.shape),
                    "sha256": hashlib.sha256(array.astype("<i8").tobytes()).hexdigest(),
                }
                for key, array in matrices.items()
            },
        },
    }
    (tmp_path / "inputs-manifest.json").write_text(json.dumps(manifest))
    output = tmp_path / "out"
    arguments = [
        "--wide",
        str(wide_path),
        "--bootstrap",
        str(bootstrap_path),
        "--output",
        str(output),
    ]
    module["main"](arguments)
    receipt = json.loads((output / "decisions-receipt.json").read_text())
    assert receipt["status"] == "partial"  # No rank associations supplied.
    assert receipt["ranges"] == "computed"
    assert len(receipt["outputs"]) == 10
    assert json.loads((output / "A-PASS-selected-boxes.json").read_text())
    assert set(pd.read_csv(output / "pass-shares.csv").population) >= {
        "stress_1",
        "stress_2",
        "stress_3",
    }
    manifest["wide_sha256"] = "0" * 64
    (tmp_path / "inputs-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ContractError, match="bytes differ"):
        module["main"](arguments)
