"""Matched natural-unit export controls with independent small arithmetic."""

import json

import numpy as np
import pandas as pd
import pytest

from avalanche_research.analysis.explainer_pairs import (
    ABSOLUTE_SPECS,
    PairingError,
    matched_natural_units,
    units_metadata,
)


def wide_fixture():
    rows = []
    for horizon, multiplier in ((365, 4), (180, 1)):
        common = {
            "horizon_days": horizon,
            "yield_pp": 5.0,
            "i": 0,
            "j": None,
            "u1": 0.5,
            "u2": 0.25,
            "u3": 0.5,
            "seed": 11,
            "draw": 22,
            "renewal_response": 0.05,
            "entry_response": 0.025,
            "renewal_band": "middle",
            "entry_band": "low",
            "model": "fixture-v1",
            "origin": "2025-11-18",
        }
        base = {
            **common,
            "index": 100,
            "row_id": "baseline100",
            "baseline": None,
            "baseline_row_id": None,
            "family": "chain",
            "block": "baseline",
            "unit_id": "baseline:100",
            "target_min_rate": np.nan,
            "boost_max": np.nan,
            "exponent": np.nan,
            "issued_navax": 1e9 * multiplier,
            "validator_stake_navax": 100e9,
            "lowest_validator_stake_navax": 2e9,
            "active_validators": 10.0,
            "net_inflation": 0.03,
            "validator_staking_ratio": 0.4,
            "nakamoto_coefficient": 3.0,
            "earned_rate": 0.05,
            "stake_weighted_duration": 20.0,
            "reward_rate_volatility": 0.35,
            "stake_volatility": 0.008,
            "worst_30_day_stake_fall": -0.1,
            "issuance_half_life": 5.0,
            "return_margin": 0.01,
            "issuance_saved": np.nan,
            "validator_stake_retained": np.nan,
            "active_validators_retained": np.nan,
        }
        rows.append(base)
        for index, family, param, value in (
            (1, "ramp", "target_min_rate", 0.075),
            (2, "before", None, None),
            (3, "tenure", "boost_max", 0.1),
            (4, "quadratic", "exponent", 2.0),
        ):
            design = {
                **base,
                "index": index,
                "row_id": f"design{index}",
                "baseline": 100,
                "baseline_row_id": "baseline100",
                "family": family,
                "block": "A",
                "unit_id": f"saltelli:{family}:5:0",
                "issued_navax": 2e9 * multiplier,
                "validator_stake_navax": 150e9,
                "lowest_validator_stake_navax": 3e9,
                "active_validators": 12.0,
                "earned_rate": 0.1,
                "stake_weighted_duration": 10.0,
                "return_margin": 0.06,
                "reward_rate_volatility": 0.25,
                "net_inflation": 0.04,
                "issuance_saved": -1.0,
                "validator_stake_retained": 1.5,
                "active_validators_retained": 1.2,
            }
            if param:
                design[param] = value
            rows.append(design)
    frame = pd.DataFrame(rows)
    for key in ("index", "horizon_days", "i", "j", "seed", "draw", "baseline"):
        frame[key] = frame[key].astype("Int64")
    return frame


def test_two_horizons_four_families_shared_baseline_and_order_are_preserved():
    wide = wide_fixture()
    original = wide.copy(deep=True)
    result = matched_natural_units(wide.sample(frac=1, random_state=9))
    assert list(zip(result.horizon_days, result["index"], strict=True)) == [
        (h, i) for h in (180, 365) for i in (1, 2, 3, 4)
    ]
    assert len(result) == 8 and result.pair_id.is_unique
    assert result.baseline.tolist() == [100] * 8
    assert result.baseline_row_id.tolist() == ["baseline100"] * 8
    pd.testing.assert_frame_equal(wide, original)
    assert (
        result.mechanism_input_name.tolist()
        == ["target_min_rate", None, "boost_max", "exponent"] * 2
    )
    np.testing.assert_allclose(
        result.mechanism_input_value, [0.075, np.nan, 0.1, 2.0] * 2, equal_nan=True
    )
    for name in (
        "issuance_saved",
        "validator_stake_retained",
        "active_validators_retained",
    ):
        expected = (
            wide[wide.block.ne("baseline")]
            .sort_values(["horizon_days", "index"])[name]
            .to_numpy()
        )
        assert result[name].to_numpy().tobytes() == expected.tobytes()


def test_navax_conversion_and_delta_sign_not_relative_saved_sign():
    result = matched_natural_units(wide_fixture())
    first = result.iloc[0]
    assert (
        first.issued_avax_design,
        first.issued_avax_baseline,
        first.issued_avax_delta,
    ) == (2.0, 1.0, 1.0)
    assert (
        first.validator_stake_avax_design,
        first.validator_stake_avax_baseline,
        first.validator_stake_avax_delta,
    ) == (150.0, 100.0, 50.0)
    assert (
        first.lowest_validator_stake_avax_design,
        first.lowest_validator_stake_avax_baseline,
        first.lowest_validator_stake_avax_delta,
    ) == (3.0, 2.0, 1.0)
    assert first.issuance_saved == -1.0 and first.issued_avax_delta > 0
    assert result.iloc[4].issued_avax_baseline == 4.0
    for _source, natural, _source_unit, _unit, _divisor in ABSOLUTE_SPECS:
        np.testing.assert_array_equal(
            result[natural + "_delta"],
            result[natural + "_design"] - result[natural + "_baseline"],
        )


def test_fraction_percentage_point_and_time_units_are_not_silently_rescaled():
    result = matched_natural_units(wide_fixture()).iloc[0]
    assert result.return_margin_design == 0.06
    assert result.earned_rate_design == 0.1
    assert result.net_inflation_design == 0.04
    assert result.reward_rate_volatility_design == 0.25
    assert result.reward_rate_volatility_delta == pytest.approx(-0.1)
    assert result.stake_volatility_design == 0.008
    assert result.worst_30_day_stake_fall_design == -0.1
    assert result.stake_weighted_duration_design == 10.0
    units = units_metadata()
    assert units["absolute"]["return_margin"]["unit"] == "annual fraction"
    assert units["absolute"]["reward_rate_volatility"]["unit"] == "percentage points"
    assert units["absolute"]["issuance_half_life"]["unit"] == "years"
    assert len(units["absolute"]) == 14
    json.dumps(units, allow_nan=False)
    units["absolute"].clear()
    assert len(units_metadata()["absolute"]) == 14


def test_w8_reconstructs_started_commitments_with_365_at_both_horizons():
    result = matched_natural_units(wide_fixture())
    first = result.iloc[0]
    later = result.iloc[4]
    assert first.committed_avax_days_design == 7300.0
    assert first.committed_avax_days_baseline == 7300.0
    assert first.committed_avax_days_delta == 0.0
    assert first.started_avax_design == 730.0
    assert first.started_avax_baseline == 365.0
    assert first.started_avax_delta == 365.0
    assert later.committed_avax_days_design == 29200.0
    assert later.started_avax_delta == 1460.0
    assert result.committed_avax_days_design_status.eq("defined").all()
    assert result.started_avax_delta_reason.eq("").all()
    assert (
        "not active-stake integral"
        in units_metadata()["derived"]["committed_avax_days"]["basis"]
    )


@pytest.mark.parametrize(
    "field",
    [
        "seed",
        "draw",
        "renewal_response",
        "entry_response",
        "yield_pp",
        "model",
        "origin",
    ],
)
def test_pair_coupling_mutation_refuses(field):
    wide = wide_fixture()
    mask = wide.block.eq("baseline")
    wide.loc[mask, field] = (
        "wrong" if field in ("model", "origin") else wide.loc[mask, field] + 1
    )
    with pytest.raises(PairingError, match="coupling"):
        matched_natural_units(wide)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "wrong_row_id",
        "wrong_base_id",
        "missing_horizon",
        "changed_horizon_identity",
        "duplicate_row_identity",
    ],
)
def test_identity_and_horizon_mutations_refuse(mutation):
    wide = wide_fixture()
    if mutation == "missing":
        wide = wide.loc[wide.block.ne("baseline")]
    elif mutation == "duplicate":
        wide = pd.concat((wide, wide.loc[wide.block.eq("baseline")]), ignore_index=True)
    elif mutation == "wrong_row_id":
        wide.loc[wide.block.ne("baseline"), "baseline_row_id"] = "other"
    elif mutation == "wrong_base_id":
        wide.loc[wide.block.ne("baseline"), "baseline"] = 999
    elif mutation == "missing_horizon":
        wide = wide.loc[~(wide["index"].eq(1) & wide.horizon_days.eq(180))]
    elif mutation == "changed_horizon_identity":
        wide.loc[wide["index"].eq(1) & wide.horizon_days.eq(180), "row_id"] = "changed"
    else:
        wide.loc[wide["index"].eq(2), "row_id"] = "design1"
    with pytest.raises(PairingError):
        matched_natural_units(wide)


@pytest.mark.parametrize("rate", [0.0, -0.1])
def test_w8_nonpositive_rate_keeps_rows_with_reason_and_no_infinities(rate):
    wide = wide_fixture()
    wide.loc[wide["index"].eq(1), "earned_rate"] = rate
    result = matched_natural_units(wide)
    bad = result.loc[result["index"].eq(1)]
    assert len(result) == 8 and len(bad) == 2
    assert bad.committed_avax_days_design.isna().all()
    assert bad.committed_avax_days_design_reason.eq("nonpositive_earned_rate").all()
    assert bad.started_avax_design_reason.eq("committed_avax_days_undefined").all()
    assert bad.started_avax_delta_reason.eq("design_reconstruction_undefined").all()
    assert not np.isinf(
        result.select_dtypes(include="number").to_numpy(dtype=float, na_value=np.nan)
    ).any()


def test_w8_bad_duration_only_undefines_started_stake():
    wide = wide_fixture()
    wide.loc[wide["index"].eq(1), "stake_weighted_duration"] = 0.0
    result = matched_natural_units(wide)
    bad = result.loc[result["index"].eq(1)]
    assert bad.committed_avax_days_design.notna().all()
    assert bad.started_avax_design.isna().all()
    assert bad.started_avax_design_reason.eq(
        "nonpositive_stake_weighted_duration"
    ).all()


def test_w8_overflow_is_explicit_undefined_not_infinity():
    wide = wide_fixture()
    wide.loc[wide["index"].eq(1), "earned_rate"] = np.nextafter(0.0, 1.0)
    result = matched_natural_units(wide)
    bad = result.loc[result["index"].eq(1)]
    assert bad.committed_avax_days_design.isna().all()
    assert bad.committed_avax_days_design_reason.eq(
        "nonfinite_float64_reconstruction"
    ).all()


@pytest.mark.parametrize(
    "ratio",
    ["issuance_saved", "validator_stake_retained", "active_validators_retained"],
)
def test_ratio_mutation_refuses_instead_of_overwriting_source(ratio):
    wide = wide_fixture()
    wide.loc[wide["index"].eq(1), ratio] += 0.01
    with pytest.raises(PairingError, match="ratio algebra"):
        matched_natural_units(wide)


def test_nonpositive_existing_ratio_baseline_refuses_without_new_ratio_policy():
    wide = wide_fixture()
    wide.loc[wide.block.eq("baseline"), "active_validators"] = 0.0
    with pytest.raises(PairingError, match="ratio denominator"):
        matched_natural_units(wide)


def test_masks_nonfinite_absolute_and_missing_columns_refuse():
    for name in ("issued_navax", "return_margin", "reward_rate_volatility"):
        wide = wide_fixture()
        wide.loc[wide["index"].eq(1), name] = np.nan
        with pytest.raises(PairingError, match="finite"):
            matched_natural_units(wide)
    with pytest.raises(PairingError, match="missing wide"):
        matched_natural_units(wide_fixture().drop(columns="baseline_row_id"))


def test_native_identity_not_float_rounding_required():
    wide = wide_fixture()
    wide["index"] = wide["index"].astype(float)
    with pytest.raises(PairingError, match="original.*integer"):
        matched_natural_units(wide)


@pytest.mark.parametrize(
    "also_design,expected",
    [
        (False, "baseline_reconstruction_undefined"),
        (True, "both_reconstructions_undefined"),
    ],
)
def test_baseline_and_both_denominator_roles_preserve_undefined_delta(
    also_design, expected
):
    wide = wide_fixture()
    wide.loc[wide.block.eq("baseline"), "earned_rate"] = 0.0
    if also_design:
        wide.loc[wide.block.ne("baseline"), "earned_rate"] = 0.0
    result = matched_natural_units(wide)
    assert len(result) == 8
    assert result.committed_avax_days_baseline.isna().all()
    assert result.committed_avax_days_baseline_reason.eq(
        "nonpositive_earned_rate"
    ).all()
    assert result.committed_avax_days_delta.isna().all()
    assert result.committed_avax_days_delta_reason.eq(expected).all()
    assert result.started_avax_delta_reason.eq(expected).all()
