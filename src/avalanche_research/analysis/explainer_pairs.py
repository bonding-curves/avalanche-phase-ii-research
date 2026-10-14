"""Pure matched trajectory values in natural units, without statistical inference.

The caller authenticates the prepared wide table. This module checks its pairing
and two-horizon structure, retains every non-baseline row, and returns values
rather than summaries. W8 quantities reconstruct started commitments from saved
float64 KPIs. They are not an integral of active stake or an integer-state replay.
"""

from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd

# Source, natural-unit name, source unit, output unit, divisor.
ABSOLUTE_SPECS = (
    ("issued_navax", "issued_avax", "nAVAX", "AVAX", 1e9),
    ("validator_stake_navax", "validator_stake_avax", "nAVAX", "AVAX", 1e9),
    (
        "lowest_validator_stake_navax",
        "lowest_validator_stake_avax",
        "nAVAX",
        "AVAX",
        1e9,
    ),
    ("active_validators", "active_validators", "count", "count", 1.0),
    ("net_inflation", "net_inflation", "annual fraction", "annual fraction", 1.0),
    ("validator_staking_ratio", "validator_staking_ratio", "fraction", "fraction", 1.0),
    ("nakamoto_coefficient", "nakamoto_coefficient", "count", "count", 1.0),
    ("earned_rate", "earned_rate", "annual fraction", "annual fraction", 1.0),
    ("stake_weighted_duration", "stake_weighted_duration", "days", "days", 1.0),
    (
        "reward_rate_volatility",
        "reward_rate_volatility",
        "percentage points",
        "percentage points",
        1.0,
    ),
    (
        "stake_volatility",
        "stake_volatility",
        "standard deviation of daily log stake change",
        "standard deviation of daily log stake change",
        1.0,
    ),
    ("worst_30_day_stake_fall", "worst_30_day_stake_fall", "fraction", "fraction", 1.0),
    ("issuance_half_life", "issuance_half_life", "years", "years", 1.0),
    ("return_margin", "return_margin", "annual fraction", "annual fraction", 1.0),
)
RELATIVE = {
    "issuance_saved": "issued_navax",
    "validator_stake_retained": "validator_stake_navax",
    "active_validators_retained": "active_validators",
}
FAMILY_INPUTS = {
    "ramp": "target_min_rate",
    "before": None,
    "tenure": "boost_max",
    "quadratic": "exponent",
}
METADATA = (
    "index",
    "horizon_days",
    "row_id",
    "baseline",
    "baseline_row_id",
    "family",
    "yield_pp",
    "block",
    "i",
    "j",
    "unit_id",
    "u1",
    "u2",
    "u3",
    "seed",
    "draw",
    "renewal_response",
    "entry_response",
    "renewal_band",
    "entry_band",
    "target_min_rate",
    "boost_max",
    "exponent",
    "model",
    "origin",
)
COUPLING = (
    "seed",
    "draw",
    "renewal_response",
    "entry_response",
    "yield_pp",
    "model",
    "origin",
)


class PairingError(ValueError):
    """The input cannot preserve the declared matched trajectory identities."""


def _require(condition, reason):
    if not condition:
        raise PairingError(reason)


def _ids(values, name, *, nullable=False):
    _require(
        all(
            (nullable and pd.isna(v))
            or (
                isinstance(v, Integral)
                and not isinstance(v, (bool, np.bool_))
                and 0 <= v < 2**63
            )
            for v in values
        ),
        name + " must contain original nonnegative integer identities",
    )


def _numeric(values, name):
    _require(
        pd.api.types.is_numeric_dtype(values.dtype)
        and not pd.api.types.is_bool_dtype(values.dtype),
        name + " must be numeric, not Boolean",
    )
    array = values.to_numpy(dtype=np.float64, na_value=np.nan)
    _require(
        np.isfinite(array).all(), name + " must contain complete finite float64 values"
    )
    return array


def units_metadata():
    """Return fresh JSON-serializable source/output units and reconstruction limits."""
    absolute = {
        natural: {
            "source_column": source,
            "source_unit": source_unit,
            "unit": unit,
            "divisor": divisor,
            "columns": {
                role: f"{natural}_{role}" for role in ("design", "baseline", "delta")
            },
        }
        for source, natural, source_unit, unit, divisor in ABSOLUTE_SPECS
    }
    return {
        "schema": "matched-natural-units/v1",
        "absolute": absolute,
        "relative": {
            name: {
                "unit": "fraction" if name == "issuance_saved" else "ratio",
                "preserved_from_source": True,
            }
            for name in RELATIVE
        },
        "derived": {
            "committed_avax_days": {
                "unit": "AVAX-days",
                "formula": "365 * (issued_navax / 1e9) / earned_rate",
                "basis": "full committed stake-days of commitments started in the horizon, not active-stake integral",
            },
            "started_avax": {
                "unit": "AVAX",
                "formula": "committed_avax_days / stake_weighted_duration",
                "basis": "sum of stake in commitments started in the horizon, not active stake at horizon",
            },
        },
        "delta_definition": "design minus matched baseline, in the same natural unit",
        "metadata_columns": list(METADATA)
        + ["pair_id", "mechanism_input_name", "mechanism_input_value"],
        "metadata_units": {
            "yield_pp": "percentage points per year",
            "mechanism_input_value": "source parameter units named by mechanism_input_name",
            "renewal_response": "source response parameter, unchanged",
            "entry_response": "source response parameter, unchanged",
        },
        "limits": [
            "Caller authenticates wide input bytes and producer provenance.",
            "All arithmetic is float64 over reduced KPIs. No exact integer daily-state reconstruction, active-stake integral, new fit, interval or causal inference.",
            "Annual fractions remain fractions; reward-rate volatility is already in percentage points. No implicit percentage conversion.",
            "W8 requires positive earned rate and duration. Undefined or nonfinite reconstructions/deltas are NaN with explicit status and reason; no infinities or zero substitution.",
        ],
    }


def _w8(issued_avax, rate, duration):
    n = len(rate)
    days = np.full(n, np.nan)
    started = np.full(n, np.nan)
    days_reason = np.full(n, "", dtype=object)
    started_reason = np.full(n, "", dtype=object)
    positive_rate = rate > 0
    days_reason[~positive_rate] = "nonpositive_earned_rate"
    with np.errstate(over="ignore", divide="ignore", invalid="ignore", under="ignore"):
        np.divide(365 * issued_avax, rate, out=days, where=positive_rate)
    nonfinite = positive_rate & ~np.isfinite(days)
    days_reason[nonfinite] = "nonfinite_float64_reconstruction"
    days[nonfinite] = np.nan
    known = np.isfinite(days)
    started_reason[~known] = "committed_avax_days_undefined"
    started_reason[known & (duration <= 0)] = "nonpositive_stake_weighted_duration"
    allowed = known & (duration > 0)
    with np.errstate(over="ignore", divide="ignore", invalid="ignore", under="ignore"):
        np.divide(days, duration, out=started, where=allowed)
    nonfinite = allowed & ~np.isfinite(started)
    started_reason[nonfinite] = "nonfinite_float64_reconstruction"
    started[nonfinite] = np.nan
    return {
        "committed_avax_days": (days, days_reason),
        "started_avax": (started, started_reason),
    }


def matched_natural_units(wide: pd.DataFrame) -> pd.DataFrame:
    """Return complete design/baseline/delta rows sorted by horizon and index.

    Both180/365 horizons are required for each original trajectory, with stable
    metadata across them. Shared baselines remain shared, never multiplied into
    independent observations. Source ratios are copied exactly after validating
    their existing algebra. W8 undefined rows remain in place with reasons.
    """
    _require(
        isinstance(wide, pd.DataFrame) and not wide.empty and wide.columns.is_unique,
        "nonempty wide DataFrame with unique columns required",
    )
    required = set(METADATA) | set(RELATIVE) | {x[0] for x in ABSOLUTE_SPECS}
    _require(
        required <= set(wide),
        "missing wide columns: " + str(sorted(required - set(wide))),
    )
    for name in ("index", "horizon_days", "seed", "draw", "i"):
        _ids(wide[name], name)
    for name in ("baseline", "j"):
        _ids(wide[name], name, nullable=True)
    _require(
        not wide.duplicated(["index", "horizon_days"]).any(),
        "duplicate trajectory/horizon",
    )
    _require(set(wide.horizon_days) == {180, 365}, "both180 and365 horizons required")
    ordered = wide.sort_values(["horizon_days", "index"], kind="stable")
    early = (
        ordered.loc[ordered.horizon_days.eq(180), list(METADATA)]
        .drop(columns="horizon_days")
        .reset_index(drop=True)
    )
    late = (
        ordered.loc[ordered.horizon_days.eq(365), list(METADATA)]
        .drop(columns="horizon_days")
        .reset_index(drop=True)
    )
    _require(
        early.equals(late),
        "trajectory identities/metadata differ or are missing across horizons",
    )
    _require(
        wide.row_id.map(lambda v: isinstance(v, str) and bool(v)).all(),
        "nonempty original row_id required",
    )
    _require(
        not early.row_id.duplicated().any(),
        "row_id identifies more than one trajectory",
    )
    _require(
        wide.unit_id.map(lambda v: isinstance(v, str) and bool(v)).all(),
        "original unit_id required",
    )
    _require(
        wide.block.isin(
            ("A", "B", "AB", "BA", "noise", "zero", "stress", "control", "baseline")
        ).all(),
        "unknown block",
    )
    design = ordered.loc[ordered.block.ne("baseline")].copy()
    baseline = ordered.loc[ordered.block.eq("baseline")]
    _require(
        not design.empty and not baseline.empty, "design and baseline rows required"
    )
    _require(design.family.isin(FAMILY_INPUTS).all(), "unknown design family")
    _require(
        baseline.family.eq("chain").all() and baseline.baseline.isna().all(),
        "baseline roles must identify chain with no baseline of their own",
    )
    _require(design.baseline.notna().all(), "design baseline reference absent")
    for name in ("renewal_response", "entry_response", "yield_pp"):
        _numeric(wide[name], name)
    for source, *_ in ABSOLUTE_SPECS:
        _numeric(wide[source], source)
    columns = [
        "index",
        "horizon_days",
        "row_id",
        *COUPLING,
        *[x[0] for x in ABSOLUTE_SPECS],
    ]
    base = baseline[columns].rename(
        columns={name: "_matched_" + name for name in columns if name != "horizon_days"}
    )
    paired = design.merge(
        base,
        left_on=["baseline", "horizon_days"],
        right_on=["_matched_index", "horizon_days"],
        how="left",
        validate="many_to_one",
        indicator=True,
        sort=False,
    )
    _require(paired._merge.eq("both").all(), "missing same-horizon baseline row")
    _require(
        paired.baseline_row_id.eq(paired._matched_row_id).all(),
        "baseline_row_id differs from matched row_id",
    )
    for name in COUPLING:
        _require(
            paired[name].eq(paired["_matched_" + name]).all(),
            "matched baseline coupling differs: " + name,
        )
    result = paired[list(METADATA)].copy()
    result["pair_id"] = result.row_id + "|h" + result.horizon_days.astype(str)
    result["mechanism_input_name"] = result.family.map(FAMILY_INPUTS)
    result["mechanism_input_value"] = np.nan
    for family, name in FAMILY_INPUTS.items():
        if name is not None:
            mask = result.family.eq(family)
            result.loc[mask, "mechanism_input_value"] = _numeric(
                paired.loc[mask, name], name
            )
    for name, source in RELATIVE.items():
        supplied = _numeric(paired[name], name)
        denominator = paired["_matched_" + source].to_numpy(dtype=np.float64)
        _require(
            (denominator > 0).all(),
            "nonpositive existing paired ratio denominator: " + name,
        )
        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            expected = paired[source].to_numpy(dtype=np.float64) / denominator
            if name == "issuance_saved":
                expected = 1 - expected
        _require(
            np.isfinite(expected).all() and np.array_equal(supplied, expected),
            "existing paired ratio algebra differs: " + name,
        )
        result[name] = supplied
    for source, natural, _source_unit, _unit, divisor in ABSOLUTE_SPECS:
        d = paired[source].to_numpy(dtype=np.float64) / divisor
        b = paired["_matched_" + source].to_numpy(dtype=np.float64) / divisor
        with np.errstate(over="ignore", invalid="ignore"):
            delta = d - b
        _require(np.isfinite(delta).all(), "nonfinite natural-unit delta: " + natural)
        result[natural + "_design"] = d
        result[natural + "_baseline"] = b
        result[natural + "_delta"] = delta
    reconstructed = {
        side: _w8(
            result["issued_avax_" + side].to_numpy(),
            result["earned_rate_" + side].to_numpy(),
            result["stake_weighted_duration_" + side].to_numpy(),
        )
        for side in ("design", "baseline")
    }
    for name in ("committed_avax_days", "started_avax"):
        for side in ("design", "baseline"):
            values, reasons = reconstructed[side][name]
            result[name + "_" + side] = values
            result[name + "_" + side + "_status"] = np.where(
                np.isfinite(values), "defined", "undefined"
            )
            result[name + "_" + side + "_reason"] = reasons
        d, b = (reconstructed[side][name][0] for side in ("design", "baseline"))
        with np.errstate(over="ignore", invalid="ignore"):
            delta = d - b
        finite = np.isfinite(delta)
        result[name + "_delta"] = np.where(finite, delta, np.nan)
        result[name + "_delta_status"] = np.where(finite, "defined", "undefined")
        reason = np.full(len(result), "", dtype=object)
        reason[~finite & ~np.isfinite(d)] = "design_reconstruction_undefined"
        reason[~finite & ~np.isfinite(b)] = "baseline_reconstruction_undefined"
        reason[~finite & ~np.isfinite(d) & ~np.isfinite(b)] = (
            "both_reconstructions_undefined"
        )
        reason[~finite & np.isfinite(d) & np.isfinite(b)] = "nonfinite_float64_delta"
        result[name + "_delta_reason"] = reason
    _require(
        len(result) == len(design)
        and not result.duplicated(["index", "horizon_days"]).any(),
        "paired export lost or repeated design rows",
    )
    result.attrs["units_metadata"] = units_metadata()
    return result.reset_index(drop=True)
