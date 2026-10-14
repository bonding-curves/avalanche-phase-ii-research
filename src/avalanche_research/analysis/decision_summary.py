"""Pure decision summaries for predeclared sweep scopes.

Inputs are already authenticated, paired and response-banded by the caller.
Bootstrap indices refer to whole units, in ``unit_order`` (first appearance
unless supplied). The caller shares those indices across all dependent scopes.
Intervals are conditional design-bootstrap intervals, not predictive coverage.
No function reads runs, generates random numbers or fits a response surface.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

BANDS = ("low", "middle", "high")
GRID = tuple((r, e) for r in BANDS for e in BANDS)
RELATION_SCOPE = ("family", "yield_pp", "horizon_days", "measure", "input", "method")
DESIGN_SCOPE = ("yield_pp", "horizon_days", "renewal_band", "entry_band")


class ContractError(ValueError):
    """An input violates an explicit summary contract."""


def _require(frame: pd.DataFrame, columns: Sequence[str]) -> None:
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ContractError(f"Missing columns: {sorted(missing)}")


def _groups(frame: pd.DataFrame, columns: Sequence[str]):
    _require(frame, columns)
    if frame[list(columns)].isna().any().any():
        raise ContractError("Scope identities must not be missing")
    for key, group in frame.groupby(list(columns), sort=False, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        yield dict(zip(columns, key, strict=True)), group


def confidence_ratings(
    cells: pd.DataFrame,
    *,
    group_columns: Sequence[str] = RELATION_SCOPE,
    expected_cells: Sequence[tuple[str, str]] = GRID,
) -> pd.DataFrame:
    """Rate a relationship across every declared response cell.

    Required cell fields: renewal_band, entry_band, coefficient, ci_low,
    ci_high and status (``assessable``). Missing/undefined cells or intervals
    yield ``not rated``. Separate anchor comparisons can supply their complete
    expected cell labels explicitly; they never silently enter grid ratings.
    """
    _require(
        cells,
        ("renewal_band", "entry_band", "coefficient", "ci_low", "ci_high", "status"),
    )
    expected = set(expected_cells)
    if len(expected) != len(expected_cells) or not expected:
        raise ContractError("Expected cells must be distinct and nonempty")
    output = []
    for scope, frame in _groups(cells, group_columns):
        keys = list(zip(frame.renewal_band, frame.entry_band, strict=True))
        if len(set(keys)) != len(keys) or set(keys) - expected:
            raise ContractError("Duplicate or undeclared response cells")
        reason, rating = "", "not rated"
        numeric = frame[["coefficient", "ci_low", "ci_high"]].to_numpy(dtype=float)
        if set(keys) != expected:
            reason = "missing_response_cell"
        elif not frame.status.eq("assessable").all():
            reason = "undefined_response_cell"
        elif (
            not np.isfinite(numeric).all()
            or (numeric[:, 1] > numeric[:, 2]).any()
            or (
                "interval_status" in frame
                and not frame.interval_status.eq("assessable").all()
            )
        ):
            reason = "unassessable_interval"
        else:
            signs = np.sign(numeric[:, 0])
            excludes = (numeric[:, 1] > 0) | (numeric[:, 2] < 0)
            if len(set(signs)) > 1:
                rating = "Low"
            elif excludes.all() and signs[0] != 0:
                rating = "High"
            else:
                rating = "Medium"
        output.append(
            {
                **scope,
                "confidence_rating": rating,
                "status": "assessable" if not reason else "unassessable",
                "reason": reason,
                "cells_present": len(keys),
                "cells_expected": len(expected),
            }
        )
    return pd.DataFrame(
        output,
        columns=[
            *group_columns,
            "confidence_rating",
            "status",
            "reason",
            "cells_present",
            "cells_expected",
        ],
    )


def sign_reversals(
    cells: pd.DataFrame,
    *,
    group_columns: Sequence[str] = RELATION_SCOPE,
    response_max: float = 0.1,
) -> pd.DataFrame:
    """Compare adjacent grid bands, retaining unassessable edges.

    Opposite nonzero signs detect a reversal. A zero endpoint cannot establish
    a reversal direction. Reported boundaries describe the bands, not an
    interpolated crossing. Anchors require a separate declared comparison.
    """
    _require(cells, ("renewal_band", "entry_band", "coefficient", "status"))
    if not np.isfinite(response_max) or response_max <= 0:
        raise ContractError("response_max must be positive and finite")
    output = []
    for scope, frame in _groups(cells, group_columns):
        if frame.duplicated(["renewal_band", "entry_band"]).any():
            raise ContractError("Duplicate response cells")
        if not set(zip(frame.renewal_band, frame.entry_band, strict=True)) <= set(GRID):
            raise ContractError("Stress/zero anchors must not be pooled into the grid")
        lookup = {(row.renewal_band, row.entry_band): row for row in frame.itertuples()}
        for axis in ("renewal", "entry"):
            for fixed in BANDS:
                for j in (0, 1):
                    keys = [
                        (BANDS[k], fixed) if axis == "renewal" else (fixed, BANDS[k])
                        for k in (j, j + 1)
                    ]
                    pair = [lookup.get(key) for key in keys]
                    reason, changed = "", None
                    if (
                        scope.get("family") == "before"
                        and scope.get("horizon_days") == 180
                    ):
                        reason = "before_180_comparator"
                    elif any(row is None for row in pair):
                        reason = "missing_response_cell"
                    elif any(
                        row.status != "assessable" or not np.isfinite(row.coefficient)
                        for row in pair
                    ):
                        reason = "undefined_response_cell"
                    elif any(row.coefficient == 0 for row in pair):
                        reason = "zero_endpoint"
                    else:
                        changed = bool(pair[0].coefficient * pair[1].coefficient < 0)
                    output.append(
                        {
                            **scope,
                            "response_axis": axis,
                            "other_response_band": fixed,
                            "from_band": BANDS[j],
                            "to_band": BANDS[j + 1],
                            "from_low": j * response_max / 3,
                            "from_high": (j + 1) * response_max / 3,
                            "to_low": (j + 1) * response_max / 3,
                            "to_high": (j + 2) * response_max / 3,
                            "band_boundary": (j + 1) * response_max / 3,
                            "resolution": response_max / 3,
                            "sign_changes": changed,
                            "status": "unassessable"
                            if reason
                            else "reversal"
                            if changed
                            else "no_detected_reversal",
                            "reason": reason,
                        }
                    )
    return pd.DataFrame(output)


def clustered_mean_interval(
    values: Sequence[float],
    unit_ids: Sequence,
    bootstrap_indices: np.ndarray,
    *,
    unit_order: Sequence | None = None,
) -> dict:
    """Finite row-weighted mean with caller-supplied whole-unit resampling.

    A full-scope unit_order can include units absent from a response cell.
    Any empty replicate makes its interval unassessable, rather than dropping
    that replicate. All rows of a repeated unit receive the same multiplicity.
    """
    values_array = np.asarray(values)
    units = list(unit_ids)
    if values_array.ndim != 1 or len(units) != len(values_array):
        raise ContractError("Values and unit identities must align")
    if values_array.dtype.kind not in "iuf" or not np.isfinite(values_array).all():
        raise ContractError("Mean values must be finite numeric values")
    if any(
        unit is None or unit is pd.NA or (np.isscalar(unit) and pd.isna(unit))
        for unit in units
    ):
        raise ContractError("Unit identities must not be missing")
    order = list(dict.fromkeys(units)) if unit_order is None else list(unit_order)
    if len(set(order)) != len(order) or set(units) - set(order):
        raise ContractError("unit_order must be unique and cover every row")
    if (
        np.ma.isMaskedArray(bootstrap_indices)
        and np.ma.getmaskarray(bootstrap_indices).any()
    ):
        raise ContractError("Masked bootstrap indices are unsupported")
    indices = np.asarray(bootstrap_indices)
    if (
        indices.ndim != 2
        or indices.dtype.kind not in "iu"
        or indices.shape[0] < 2
        or indices.shape[1] != len(order)
        or not len(order)
    ):
        raise ContractError(
            "Bootstrap indices need >=2 whole-unit draws, each of scope unit count"
        )
    if indices.min() < 0 or indices.max() >= len(order):
        raise ContractError("Bootstrap unit index out of bounds")
    mapping = {unit: k for k, unit in enumerate(order)}
    codes = np.array([mapping[unit] for unit in units], dtype=int)
    counts = np.bincount(codes, minlength=len(order))
    totals = np.bincount(
        codes, weights=values_array.astype(float), minlength=len(order)
    )
    denominator = counts[indices].sum(axis=1)
    numerator = totals[indices].sum(axis=1)
    replicates = np.divide(
        numerator, denominator, out=np.full(len(indices), np.nan), where=denominator > 0
    )
    invalid = int((~np.isfinite(replicates)).sum())
    insufficient = len(set(units)) < 2
    bounds = (
        [None, None]
        if invalid or insufficient
        else np.quantile(replicates, [0.025, 0.975]).tolist()
    )
    digest = hashlib.sha256(indices.astype("<i8").tobytes()).hexdigest()
    point = float(values_array.mean()) if len(values_array) else None
    return {
        "mean": point,
        "ci_low": bounds[0],
        "ci_high": bounds[1],
        "bootstrap_se": None
        if invalid or insufficient
        else float(np.std(replicates, ddof=1)),
        "runs": len(values_array),
        "units_present": len(set(units)),
        "scope_units": len(order),
        "replicates": len(indices),
        "invalid_replicates": invalid,
        "bootstrap_sha256": digest,
        "status": "unassessable" if invalid or insufficient else "assessable",
        "reason": "empty_bootstrap_replicate"
        if invalid
        else "no_runs"
        if point is None
        else "insufficient_units"
        if insufficient
        else "",
        "interval_interpretation": "conditional design cluster bootstrap",
    }


def clustered_pass_share(
    passed: Sequence[bool],
    unit_ids: Sequence,
    bootstrap_indices: np.ndarray,
    *,
    unit_order: Sequence | None = None,
) -> dict:
    """Boolean pass share and its separate conditional cluster interval."""
    flags = np.asarray(passed)
    if flags.dtype.kind != "b":
        raise ContractError("Pass flags must be Boolean, without missing values")
    result = clustered_mean_interval(
        flags.astype(float), unit_ids, bootstrap_indices, unit_order=unit_order
    )
    result["pass_share"] = result.pop("mean")
    return result


def pass_share_flags(pass_share: float | None) -> dict:
    """Exact inclusive 90/70/50 lines and strict outside-[5,95]% screen."""
    if pass_share is None or not np.isfinite(pass_share):
        return {"meets_90": None, "meets_70": None, "meets_50": None, "flagged": None}
    if not 0 <= pass_share <= 1:
        raise ContractError("Pass share must lie in [0,1]")
    return {
        "meets_90": bool(pass_share >= 0.9),
        "meets_70": bool(pass_share >= 0.7),
        "meets_50": bool(pass_share >= 0.5),
        "flagged": bool(pass_share < 0.05 or pass_share > 0.95),
    }


def threshold_outcomes(
    rows: pd.DataFrame, *, net_inflation_alternative: float
) -> pd.DataFrame:
    """Long primary/alternative flags from already cost-rescored wide rows.

    Issuance >0 is a run-level goal flag only. A per-goal range additionally
    requires the goal interval to exclude zero; this function grants no tier.
    Reported-only KPIs intentionally receive no invented pass criterion.
    """
    _require(
        rows,
        (
            "issuance_saved",
            "validator_stake_retained",
            "net_inflation",
            "return_margin",
        ),
    )
    values = rows[
        ["issuance_saved", "validator_stake_retained", "net_inflation", "return_margin"]
    ].to_numpy(float)
    if not np.isfinite(values).all() or not np.isfinite(net_inflation_alternative):
        raise ContractError("Threshold values and reference must be finite")
    definitions = [
        ("issuance_saved", "primary", rows.issuance_saved > 0, np.zeros(len(rows))),
        (
            "validator_stake_retained",
            "primary",
            rows.validator_stake_retained >= 1 - rows.issuance_saved,
            1 - rows.issuance_saved,
        ),
        (
            "validator_stake_retained",
            "no_stake_loss",
            rows.validator_stake_retained >= 1,
            np.ones(len(rows)),
        ),
        (
            "net_inflation",
            "primary",
            rows.net_inflation <= 0.05,
            np.full(len(rows), 0.05),
        ),
        (
            "net_inflation",
            "trailing_year",
            rows.net_inflation <= net_inflation_alternative,
            np.full(len(rows), net_inflation_alternative),
        ),
        ("return_margin", "primary", rows.return_margin >= 0, np.zeros(len(rows))),
    ]
    frames = []
    for measure, alternative, passed, threshold in definitions:
        frame = rows.copy()
        frame["measure"], frame["threshold_alternative"] = measure, alternative
        frame["passed"], frame["threshold"] = (
            passed.to_numpy(bool),
            np.asarray(threshold),
        )
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def summarize_pass_shares(
    rows: pd.DataFrame,
    *,
    pass_column: str,
    unit_column: str,
    group_columns: Sequence[str],
    bootstrap_indices: np.ndarray,
    unit_order: Sequence,
) -> pd.DataFrame:
    """Summarize cells within ONE independent family/yield resampling scope."""
    _require(rows, (pass_column, unit_column, "family", "yield_pp"))
    if len(rows[["family", "yield_pp"]].drop_duplicates()) > 1:
        raise ContractError(
            "Different family/yield scopes need independent caller indices"
        )
    output = []
    for scope, frame in _groups(rows, group_columns):
        result = clustered_pass_share(
            frame[pass_column],
            frame[unit_column],
            bootstrap_indices,
            unit_order=unit_order,
        )
        output.append({**scope, **result, **pass_share_flags(result["pass_share"])})
    return pd.DataFrame(output)


def design_rankings(
    rows: pd.DataFrame,
    measures: Sequence[str],
    *,
    higher_is_better: Mapping[str, bool],
    group_columns: Sequence[str] = DESIGN_SCOPE,
    expected_yields: Sequence[float] = (3.0, 5.0, 7.0, 10.0),
) -> pd.DataFrame:
    """Rank family means under each family's declared A/B input distribution.

    p10/p90 describe run spread, not uncertainty on the mean. Ties share the
    minimum rank. This comparison does not match different input settings.
    """
    _require(rows, ("family", "block", "horizon_days", *group_columns, *measures))
    if any(measure not in higher_is_better for measure in measures):
        raise ContractError("Declare ranking direction for every measure")
    allowed = {
        "issuance_saved",
        "validator_stake_retained",
        "active_validators_retained",
    }
    if set(measures) - allowed:
        raise ContractError(
            "Between-family rankings use matched relative measures only"
        )
    data = rows[rows.block.isin(["A", "B"])].copy()
    excluded = data.family.eq("before") & data.horizon_days.eq(180)
    excluded_count = int(excluded.sum())
    data = data[~excluded]
    if not np.isfinite(data[list(measures)].to_numpy(float)).all():
        raise ContractError("Design summaries require finite measures")
    output = []
    for scope, frame in _groups(data, group_columns):
        for measure in measures:
            family_rows = []
            for family, values in frame.groupby("family", sort=False):
                array = values[measure].to_numpy(float)
                family_rows.append(
                    {
                        **scope,
                        "family": family,
                        "measure": measure,
                        "mean": float(array.mean()),
                        "p10": float(np.quantile(array, 0.1)),
                        "p90": float(np.quantile(array, 0.9)),
                        "runs": len(array),
                    }
                )
            stats = pd.DataFrame(family_rows)
            stats["rank"] = stats["mean"].rank(
                method="min", ascending=not higher_is_better[measure]
            )
            stats["status"] = "assessable"
            output.extend(stats.to_dict("records"))
    result = pd.DataFrame(
        output,
        columns=[
            *group_columns,
            "family",
            "measure",
            "mean",
            "p10",
            "p90",
            "runs",
            "rank",
            "status",
        ],
    )
    result["order_same_at_every_yield"] = None
    order_groups = [column for column in group_columns if column != "yield_pp"] + [
        "measure"
    ]
    for _, frame in _groups(result, order_groups):
        orders = []
        for _, at_yield in frame.groupby("yield_pp", sort=False):
            orders.append(
                tuple(sorted(zip(at_yield.family, at_yield["rank"], strict=True)))
            )
        complete = set(frame.yield_pp) == set(expected_yields) and len(orders) > 1
        result.loc[frame.index, "order_same_at_every_yield"] = (
            len(set(orders)) == 1 if complete else None
        )
    result.attrs["excluded_before_180_runs"] = excluded_count
    result.attrs["spread_interpretation"] = (
        "p10/p90 run spread; not confidence interval for mean"
    )
    return result


def point_estimates(
    rows: pd.DataFrame, *, input_column: str, group_columns: Sequence[str]
) -> pd.DataFrame:
    """Observed A-only maximum issuance saved, ties by numeric source index.

    No validated point interval or B optimization is inferred from this point.
    """
    _require(
        rows,
        ("index", "family", "horizon_days", "block", "issuance_saved", input_column),
    )
    output = []
    for scope, frame in _groups(rows, group_columns):
        family = scope.get("family", frame.family.iloc[0])
        status = "not_applicable" if family == "before" else "not_found"
        candidates = frame[frame.block.eq("A")]
        if family != "before" and len(candidates):
            if not np.isfinite(
                candidates[[input_column, "issuance_saved", "index"]].to_numpy(float)
            ).all():
                raise ContractError(
                    "Point candidates and indices must be finite numeric values"
                )
            best = candidates.sort_values(
                ["issuance_saved", "index"], ascending=[False, True], kind="stable"
            ).iloc[0]
            output.append(
                {
                    **scope,
                    "input": input_column,
                    "value": best[input_column],
                    "source_index": best["index"],
                    "issuance_saved": best.issuance_saved,
                    "status": "assessable",
                    "provisional": True,
                    "reason": "observed_A_point_no_validated_point_interval",
                }
            )
        else:
            output.append(
                {
                    **scope,
                    "input": input_column,
                    "value": None,
                    "source_index": None,
                    "issuance_saved": None,
                    "status": status,
                    "provisional": True,
                    "reason": "no_mechanism_input"
                    if family == "before"
                    else "no_A_rows",
                }
            )
    return pd.DataFrame(output)


def select_and_confirm(
    discovery: pd.DataFrame,
    confirmation: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    pass_column: str,
    unit_column: str,
    bootstrap_indices: np.ndarray,
    family: str,
    unit_order: Sequence | None = None,
    goal_column: str | None = None,
) -> dict:
    """Select one frozen A candidate and confirm it once on B.

    Candidate rows are long bounds: candidate, input, lower, upper,
    discovery_score. Maximum score wins, ties use candidate first appearance.
    Scores/bounds must be frozen using A only upstream. Every bound is closed;
    the result describes sampled support in that fixed box, never every point
    in a continuous interval. No B-guided fallback to another candidate occurs.
    If goal_column is supplied (issuance_saved), confirmation also requires a
    positive goal mean and lower 95% bound above zero, on the identical B box.
    """
    base = {
        "family": family,
        "provisional": True,
        "status": "not_found",
        "reason": "no_A_candidate",
        "candidate": None,
        "bounds": [],
        "range_claim": "sampled support in fixed A-selected box",
    }
    if family == "before":
        return {**base, "status": "not_applicable", "reason": "no_mechanism_input"}
    _require(discovery, ("block",))
    _require(confirmation, ("block", pass_column, unit_column))
    if goal_column is not None:
        _require(confirmation, (goal_column,))
    if not discovery.block.eq("A").all() or not confirmation.block.eq("B").all():
        raise ContractError("Selection must use A only and confirmation B only")
    if candidates.empty:
        return base
    _require(candidates, ("candidate", "input", "lower", "upper", "discovery_score"))
    if (
        candidates.duplicated(["candidate", "input"]).any()
        or candidates[["candidate", "input"]].isna().any().any()
    ):
        raise ContractError(
            "Candidate input bounds must have unique, nonmissing identities"
        )
    numeric = candidates[["lower", "upper", "discovery_score"]].to_numpy(float)
    if not np.isfinite(numeric).all() or (numeric[:, 0] > numeric[:, 1]).any():
        raise ContractError("Candidate bounds/scores must be finite and ordered")
    if (
        candidates.groupby("candidate", sort=False)
        .discovery_score.nunique()
        .gt(1)
        .any()
    ):
        raise ContractError("A candidate has inconsistent discovery scores")
    first = candidates.drop_duplicates("candidate")
    selected_id = (
        first.sort_values("discovery_score", ascending=False, kind="stable")
        .iloc[0]
        .candidate
    )
    selected = candidates[candidates.candidate.eq(selected_id)]
    inputs = selected.input.tolist()
    _require(discovery, inputs)
    _require(confirmation, inputs)
    masks = []
    for frame in (discovery, confirmation):
        if not np.isfinite(frame[inputs].to_numpy(float)).all():
            raise ContractError("Bound membership inputs must be finite")
        mask = np.ones(len(frame), dtype=bool)
        for bound in selected.itertuples():
            mask &= frame[bound.input].between(bound.lower, bound.upper).to_numpy()
        masks.append(mask)
    base.update(
        candidate=selected_id,
        bounds=selected[["input", "lower", "upper"]].to_dict("records"),
        discovery_runs=int(masks[0].sum()),
    )
    if not masks[0].any():
        raise ContractError("Selected A candidate has no discovery support")
    order = (
        list(dict.fromkeys(confirmation[unit_column]))
        if unit_order is None
        else unit_order
    )
    inside = confirmation.loc[masks[1]]
    if not len(inside):
        return {
            **base,
            "status": "unassessable",
            "reason": "no_B_support",
            "runs": 0,
            "pass_share": None,
            **pass_share_flags(None),
        }
    result = clustered_pass_share(
        inside[pass_column], inside[unit_column], bootstrap_indices, unit_order=order
    )
    flags = pass_share_flags(result["pass_share"])
    status = (
        "unassessable"
        if result["status"] != "assessable"
        else "found"
        if flags["meets_90"]
        else "not_found"
    )
    goal = {"goal_interval_status": "not_evaluated_by_pass_share"}
    reason = result["reason"] or (
        "below_primary_pass_share" if status == "not_found" else ""
    )
    if goal_column is not None:
        estimated = clustered_mean_interval(
            inside[goal_column],
            inside[unit_column],
            bootstrap_indices,
            unit_order=order,
        )
        goal = {
            "goal_column": goal_column,
            "goal_mean": estimated["mean"],
            "goal_ci_low": estimated["ci_low"],
            "goal_ci_high": estimated["ci_high"],
            "goal_interval_status": estimated["status"],
            "goal_reason": estimated["reason"],
            "goal_bootstrap_sha256": estimated["bootstrap_sha256"],
            "goal_meets": None
            if estimated["status"] != "assessable"
            else estimated["mean"] > 0 and estimated["ci_low"] > 0,
        }
        if estimated["status"] != "assessable":
            status, reason = "unassessable", estimated["reason"]
        elif not goal["goal_meets"]:
            status, reason = "not_found", "goal_interval_does_not_exclude_zero"
    return {
        **base,
        **result,
        **flags,
        "status": status,
        "reason": reason,
        **goal,
    }
