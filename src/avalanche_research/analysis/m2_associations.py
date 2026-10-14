"""Milestone 2 rank adapters on authenticated, complete wide tables.

No I/O, draws or p-value inference. Caller-authenticated trajectories and supplied
whole-base bootstrap positions define conditional design percentile intervals.
Multiplicity weights reproduce reranking of repeated observations exactly.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

import numpy as np
import pandas as pd

from .rank_associations import ContractError

FAMILY_INPUTS = {
    "ramp": ("target_min_rate", "renewal_response", "entry_response"),
    "before": ("renewal_response", "entry_response"),
    "tenure": ("boost_max", "renewal_response", "entry_response"),
    "quadratic": ("exponent", "renewal_response", "entry_response"),
}
BOUNDS = {
    "target_min_rate": (0.05, 0.10),
    "boost_max": (0.0, 0.2),
    "exponent": (1.0, 3.0),
    "renewal_response": (0.0, 0.1),
    "entry_response": (0.0, 0.1),
}
BANDS = ("low", "middle", "high")
PERCENTILE_INVERSION = "percentile-interval-inversion-conservative"
_ROLES = {"A", "B", "AB", "BA", "noise", "zero", "stress", "control", "baseline"}


def _numeric(values, label):
    a = np.asarray(values)
    if a.dtype.kind not in "iuf" or not np.isfinite(a).all():
        raise ContractError(label + " must be complete finite numeric values, not bool")
    return a


def _integers(values, label):
    raw = np.asarray(values)
    # CSV-derived nullable identity columns retain native Python integers in
    # object dtype. Accept those without rounding or accepting bool/strings.
    if raw.dtype.kind == "O":
        if any(
            isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, np.integer))
            for v in raw
        ):
            raise ContractError(label + " requires known native integer identities")
        try:
            raw = raw.astype(np.int64)
        except (OverflowError, ValueError) as exc:
            raise ContractError(label + " exceeds signed integer range") from exc
        if (raw < 0).any():
            raise ContractError(label + " must be nonnegative integer identities")
        return raw
    a = _numeric(values, label)
    if (a < 0).any() or not np.equal(a, np.floor(a)).all():
        raise ContractError(label + " must be nonnegative integer identities")
    if (a >= 2**63).any():
        raise ContractError(label + " exceeds signed integer range")
    return a.astype(np.int64)


def _configuration(bootstrap_replicates, confidence, batch_size):
    if type(bootstrap_replicates) is not int or bootstrap_replicates < 2:
        raise ContractError(
            "at least two explicitly supplied bootstrap replicates required"
        )
    if isinstance(confidence, (bool, np.bool_)) or confidence != 0.95:
        raise ContractError("frozen 95% percentile intervals required")
    if type(batch_size) is not int or batch_size < 1:
        raise ContractError("positive integer batch_size required")


def _validated(frame, measures):
    if (
        not isinstance(frame, pd.DataFrame)
        or frame.empty
        or not frame.columns.is_unique
    ):
        raise ContractError("complete wide DataFrame with unique columns required")
    if isinstance(measures, str):
        raise ContractError("declare a sequence of measure columns")
    measures = tuple(measures)
    if (
        not measures
        or len(set(measures)) != len(measures)
        or any(not isinstance(m, str) or not m for m in measures)
    ):
        raise ContractError("unique nonempty measure names required")
    required = {
        "index",
        "family",
        "yield_pp",
        "block",
        "i",
        "j",
        "u1",
        "u2",
        "u3",
        "baseline",
        "seed",
        "draw",
        "renewal_response",
        "entry_response",
    }
    if not required | set(measures) <= set(frame):
        raise ContractError("missing wide-table identities, coordinates or measures")
    if set(measures) & (required | set(BOUNDS) | {"horizon_days"}):
        raise ContractError("measure and metadata/input roles overlap")
    _integers(frame["index"], "index")
    if frame["index"].duplicated().any() or not frame.block.isin(_ROLES).all():
        raise ContractError("duplicate row identity or unknown row role")
    for name in measures:
        # A matched relative KPI is intentionally absent on baseline-only rows.
        # Every design-role value must still be finite; no outcome is dropped.
        _numeric(frame.loc[frame.block != "baseline", name], name)
    if "horizon_days" in frame:
        horizon = _integers(frame.horizon_days, "horizon_days")
        if len(set(horizon)) != 1 or horizon[0] not in (180, 365):
            raise ContractError("one 180/365-day horizon per adapter call required")
    else:
        horizon = [None]
    selected = frame.loc[frame.block.isin(["A", "B", "AB", "BA"])]
    if selected.empty or not selected.family.isin(FAMILY_INPUTS).all():
        raise ContractError("known family Saltelli rows required")
    _numeric(selected.yield_pp, "yield_pp")
    return measures, selected, None if horizon[0] is None else int(horizon[0])


def _bases(scope, family):
    """Canonical A/B membership; the upstream consumer owns source authentication."""
    inputs = FAMILY_INPUTS[family]
    parts = []
    for role in ("A", "B"):
        part = scope.loc[scope.block == role].sort_values("i", kind="stable")
        ids = _integers(part.i, role + " i")
        if len(ids) < 2 or not np.array_equal(ids, np.arange(len(ids))):
            raise ContractError(
                "complete contiguous A/B base indices starting at zero required"
            )
        for name in ("index", "baseline", "seed", "draw"):
            _integers(part[name], name)
        if not set(inputs) <= set(part):
            raise ContractError("family physical inputs absent")
        coords = np.column_stack(
            [_numeric(part[f"u{j + 1}"], "unit coordinate") for j in range(len(inputs))]
        )
        if ((coords < 0) | (coords > 1)).any():
            raise ContractError("unit coordinates outside [0,1]")
        for j, name in enumerate(inputs):
            lo, hi = BOUNDS[name]
            if not np.array_equal(
                _numeric(part[name], name), lo + coords[:, j] * (hi - lo)
            ):
                raise ContractError(
                    "physical input differs from declared unit coordinate"
                )
        parts.append(part)
    a, b = parts
    if len(a) != len(b):
        raise ContractError("A/B base sizes differ")
    both = pd.concat(parts)
    if any(both[name].duplicated().any() for name in ("seed", "draw")):
        raise ContractError("A/B keys must be independently distinct seeds and draws")
    return a, b


def _draws(mapping, key, n, replicates):
    if not isinstance(mapping, Mapping) or key not in mapping:
        raise ContractError("explicit family/yield bootstrap positions required")
    raw = mapping[key]
    if np.ma.isMaskedArray(raw) and np.ma.getmaskarray(raw).any():
        raise ContractError("masked bootstrap positions refused")
    a = np.asarray(raw)
    if (
        a.dtype.kind not in "iu"
        or a.shape != (replicates, n)
        or (a < 0).any()
        or (a >= n).any()
    ):
        raise ContractError(
            "bootstrap positions must be integer (replicates, base_n) in range"
        )
    return a.astype(np.int64, copy=False)


def _digest(a):
    return hashlib.sha256(np.asarray(a, dtype="<i8", order="C").tobytes()).hexdigest()


def _counts(draws):
    r, n = draws.shape
    return np.bincount(
        (draws + np.arange(r)[:, None] * n).ravel(), minlength=r * n
    ).reshape(r, n)


def _rank_spec(values):
    # Keep original integer precision until ranks have been assigned.
    _, inverse, count = np.unique(values, return_inverse=True, return_counts=True)
    order = np.argsort(inverse, kind="stable")
    return order, np.cumsum(count) - 1, inverse


def _weighted_ranks(specs, weights):
    ranks = np.empty((*weights.shape, len(specs)))
    for j, (order, ends, inverse) in enumerate(specs):
        cumulative = np.cumsum(weights[:, order], axis=1)
        after = cumulative[:, ends]
        before = np.concatenate([np.zeros((len(weights), 1)), after[:, :-1]], axis=1)
        ranks[:, :, j] = ((before + after + 1) / 2)[:, inverse]
    return ranks


def _batch(specs, weights, p, methods):
    """All inputs/KPIs share ranks, control projections and multiplicity weights."""
    if weights.shape[1] == 0:
        shape = (len(weights), p, len(specs) - p)
        return {
            method: (
                np.full(shape, np.nan),
                np.full(shape, "insufficient_rows", dtype=object),
            )
            for method in methods
        }
    n = weights.sum(axis=1)
    ranks = _weighted_ranks(specs, weights)
    centered = ranks - ((n + 1) / 2)[:, None, None]
    root = np.sqrt(weights)[:, :, None]
    x, y = centered[:, :, :p] * root, centered[:, :, p:] * root
    nx, ny = np.linalg.norm(x, axis=1), np.linalg.norm(y, axis=1)
    shape = (len(weights), p, y.shape[2])
    reason = np.full(shape, "", dtype=object)
    reason[np.broadcast_to((nx == 0)[:, :, None], shape)] = "constant_parameter"
    reason[(reason == "") & np.broadcast_to((ny == 0)[:, None, :], shape)] = (
        "constant_kpi"
    )
    reason[n < 2] = "insufficient_rows"
    result = {}
    with np.errstate(invalid="ignore", divide="ignore"):
        if "spearman" in methods:
            corr = np.einsum("bnp,bnm->bpm", x, y) / (nx[:, :, None] * ny[:, None, :])
            result["spearman"] = (np.clip(corr, -1, 1), reason.copy())
        if "prcc" in methods:
            partial = np.full(shape, np.nan)
            why = reason.copy()
            for target in range(p):
                controls = [j for j in range(p) if j != target]
                design = (
                    np.concatenate(
                        [np.ones((*weights.shape, 1)), ranks[:, :, controls]], axis=2
                    )
                    * root
                )
                q, singular, _ = np.linalg.svd(design, full_matrices=False)
                tolerance = (
                    np.finfo(float).eps
                    * np.maximum(n, len(controls) + 1)
                    * singular[:, 0]
                )
                rank = (singular > tolerance[:, None]).sum(axis=1)
                invalid = rank != len(controls) + 1
                empty = why[:, target, :] == ""
                why[:, target, :][invalid[:, None] & empty] = "rank_deficient_controls"
                df = n - rank - 1
                empty = why[:, target, :] == ""
                why[:, target, :][(df <= 0)[:, None] & empty] = (
                    "nonpositive_residual_df"
                )
                rx = x[:, :, target] - np.einsum(
                    "bnc,bc->bn", q, np.einsum("bnc,bn->bc", q, x[:, :, target])
                )
                ry = y - np.einsum("bnc,bcm->bnm", q, np.einsum("bnc,bnm->bcm", q, y))
                rnx, rny = np.linalg.norm(rx, axis=1), np.linalg.norm(ry, axis=1)
                unresolved_x = rnx <= 64 * np.finfo(float).eps * nx[:, target]
                unresolved_y = rny <= 64 * np.finfo(float).eps * ny
                empty = why[:, target, :] == ""
                why[:, target, :][empty & unresolved_x[:, None]] = (
                    "unresolved_parameter_residual"
                )
                empty = why[:, target, :] == ""
                why[:, target, :][empty & unresolved_y] = "unresolved_kpi_residual"
                partial[:, target, :] = np.einsum("bn,bnm->bm", rx, ry) / (
                    rnx[:, None] * rny
                )
            result["prcc"] = (np.clip(partial, -1, 1), why)
    for values, why in result.values():
        why[(why == "") & ~np.isfinite(values)] = "nonfinite_statistic"
        values[why != ""] = np.nan
    return result


def _relationships(
    table,
    inputs,
    measures,
    row_weights,
    draws,
    scope,
    bands,
    methods,
    batch_size,
    pvalue_method,
):
    columns = [table[name].to_numpy() for name in (*inputs, *measures)]
    specs = [_rank_spec(col) for col in columns]
    point = _batch(specs, np.ones((1, len(table))), len(inputs), methods)
    boot = {
        method: np.empty((len(draws), len(inputs), len(measures))) for method in methods
    }
    failures = {method: {} for method in methods}
    for lo in range(0, len(draws), batch_size):
        hi = min(lo + batch_size, len(draws))
        weights = row_weights(lo, hi)
        for method, (values, reasons) in _batch(
            specs, weights, len(inputs), methods
        ).items():
            boot[method][lo:hi] = values
            for name in set(reasons.ravel()) - {""}:
                failures[method].setdefault(
                    name, np.zeros((len(inputs), len(measures)), dtype=int)
                )
                failures[method][name] += (reasons == name).sum(axis=0)
    records = []
    membership = _digest(table["index"].to_numpy())
    independent_units = len(table[["yield_pp", "i"]].drop_duplicates())
    for method in methods:
        for j, name in enumerate(inputs):
            for m, measure in enumerate(measures):
                value = point[method][0][0, j, m]
                why = point[method][1][0, j, m]
                samples = boot[method][:, j, m]
                valid = int(np.isfinite(samples).sum())
                interval = (
                    np.quantile(samples, [0.025, 0.975])
                    if valid == len(draws)
                    and np.isfinite(value)
                    and independent_units >= 2
                    else [np.nan] * 2
                )
                pvalue = np.nan
                if (
                    pvalue_method is not None
                    and valid == len(draws)
                    and np.isfinite(value)
                    and independent_units >= 2
                ):
                    pvalue = min(
                        1.0,
                        2
                        * (
                            1
                            + min(int((samples <= 0).sum()), int((samples >= 0).sum()))
                        )
                        / (len(draws) + 1),
                    )
                records.append(
                    {
                        **scope,
                        "measure": measure,
                        "input": name,
                        "method": method,
                        "renewal_band": bands[0],
                        "entry_band": bands[1],
                        "coefficient": value,
                        "ci_low": interval[0],
                        "ci_high": interval[1],
                        "status": "assessable" if not why else "unassessable",
                        "reason": why,
                        "interval_status": "assessable"
                        if np.isfinite(interval).all()
                        else "unassessable",
                        "interval_reason": ""
                        if np.isfinite(interval).all()
                        else "undefined_point_or_bootstrap_or_insufficient_units",
                        "rows": len(table),
                        "bootstrap_valid": valid,
                        "bootstrap_total": len(draws),
                        "independent_units": independent_units,
                        "bootstrap_invalid_reasons": {
                            key: int(count[j, m])
                            for key, count in failures[method].items()
                            if count[j, m]
                        },
                        "membership_sha256": membership,
                        "pvalue": pvalue,
                        "pvalue_method": pvalue_method
                        or "unassessable_unqualified_null",
                        "pvalue_status": "assessable"
                        if np.isfinite(pvalue)
                        else "unassessable",
                        "adjusted_p": np.nan,
                        "starred": pd.NA,
                    }
                )
    return records


def analyze_associations(
    frame,
    *,
    measures,
    bootstrap_indices,
    bootstrap_replicates=1000,
    confidence=0.95,
    pooled=True,
    batch_size=32,
    pvalue_method=None,
):
    """Return (long rows, metadata), using full and nine-cell A/B populations.

    Draw arrays map ``(family, float_yield)`` to positions in sorted contiguous i.
    Pooled Spearman concatenates within-yield draws, never pools PRCC/horizons.
    Nondefault replicate counts are explicitly labelled synthetic qualification.
    Full-scoped input/source authentication remains the upstream consumer's job.
    """
    _configuration(bootstrap_replicates, confidence, batch_size)
    if pvalue_method not in (None, PERCENTILE_INVERSION):
        raise ContractError(
            "unsupported p-value method; explicit frozen opt-in required"
        )
    measures, selected, horizon = _validated(frame, measures)
    records, inventory, pooled_parts = [], [], {}
    for (family, yield_pp), scope in selected.groupby(
        ["family", "yield_pp"], sort=True
    ):
        a, b = _bases(scope, family)
        table = pd.concat([a, b], ignore_index=True)
        key = (family, float(yield_pp))
        draws = _draws(bootstrap_indices, key, len(a), bootstrap_replicates)
        multiplicities = _counts(draws)
        position = np.tile(np.arange(len(a)), 2)
        inputs = FAMILY_INPUTS[family]
        coords = table[[f"u{j + 1}" for j in range(len(inputs))]].to_numpy()
        band_codes = np.minimum((coords[:, -2:] * 3).astype(int), 2)
        scope_info = {
            "family": family,
            "yield_pp": float(yield_pp),
            "horizon_days": horizon,
        }
        cells = [("all", "all", np.ones(len(table), dtype=bool))]
        cells += [
            (r, e, (band_codes[:, 0] == i) & (band_codes[:, 1] == j))
            for i, r in enumerate(BANDS)
            for j, e in enumerate(BANDS)
        ]
        for r, e, mask in cells:
            member_positions = position[mask]
            records += _relationships(
                table.loc[mask],
                inputs,
                measures,
                lambda lo, hi, pos=member_positions, counts=multiplicities: counts[
                    lo:hi, pos
                ],
                draws,
                scope_info,
                (r, e),
                ("spearman", "prcc"),
                batch_size,
                pvalue_method,
            )
        inventory.append(
            {
                **scope_info,
                "base_ids": list(range(len(a))),
                "bootstrap_indices_sha256": _digest(draws),
                "base_n": len(a),
            }
        )
        pooled_parts.setdefault(family, []).append((table, multiplicities, position))
    if pooled:
        for family, parts in pooled_parts.items():
            table = pd.concat([part[0] for part in parts], ignore_index=True)
            records += _relationships(
                table,
                FAMILY_INPUTS[family],
                measures,
                lambda lo, hi, members=parts: np.concatenate(
                    [counts[lo:hi, pos] for _, counts, pos in members], axis=1
                ),
                range(bootstrap_replicates),
                {"family": family, "yield_pp": "pooled", "horizon_days": horizon},
                ("all", "all"),
                ("spearman",),
                batch_size,
                pvalue_method,
            )
    output = pd.DataFrame(records)
    output["bh_nonreject_slot"] = False
    matrix_keys = [
        "family",
        "yield_pp",
        "horizon_days",
        "renewal_band",
        "entry_band",
        "method",
    ]
    matrices = []
    for key, matrix in output.groupby(matrix_keys, sort=False, dropna=False):
        finite = np.isfinite(matrix.pvalue.to_numpy())
        if pvalue_method is not None:
            # Undefined hypotheses remain in the fixed matrix as p=1
            # nonrejection slots for multiplicity accounting only. Their
            # exported p/q/star remain unknown, never estimated as 1/false.
            padded = np.where(finite, matrix.pvalue.to_numpy(), 1.0)
            adjusted = benjamini_hochberg(padded, method=pvalue_method, qualified=True)
            rows = matrix.index[finite]
            output.loc[rows, "adjusted_p"] = adjusted[finite]
            output.loc[rows, "starred"] = adjusted[finite] <= 0.05
            output.loc[matrix.index[~finite], "bh_nonreject_slot"] = True
        matrices.append(
            {
                **{
                    name: None
                    if pd.isna(value)
                    else value.item()
                    if isinstance(value, np.generic)
                    else value
                    for name, value in zip(matrix_keys, key)
                },
                "relationships": len(matrix),
                "pvalues_assessable": int(finite.sum()),
                "nonreject_slots": int((~finite).sum())
                if pvalue_method is not None
                else 0,
                "BH_status": "assessable_with_explicit_nonreject_slots"
                if pvalue_method is not None
                else "unassessable_unqualified_null",
            }
        )
    return output, {
        "method": "MM1",
        "scopes": inventory,
        "bootstrap_replicates": bootstrap_replicates,
        "confidence": confidence,
        "frozen_replicate_count": bootstrap_replicates == 1000,
        "bootstrap_unit": "family/yield complete Saltelli base i; A/B members travel jointly",
        "interval_interpretation": "conditional design percentile summaries, not empirical coverage or causal effects",
        "pvalue_method": pvalue_method,
        "BH_matrix_keys": matrix_keys,
        "BH_matrices": matrices,
        "pvalue_interpretation": "Conditional design bootstrap percentile inversion with add-one inclusive tails; no empirical FDR guarantee",
        "included_roles": ["A", "B"],
        "response_bands": [0.0, 1 / 3, 2 / 3, 1.0],
        "input_rows": len(frame),
        "saltelli_rows": len(selected),
        "output_rows": len(records),
    }


def benjamini_hochberg(pvalues, *, method, qualified=False):
    """BH-adjust one complete declared matrix of externally qualified p-values.

    The caller declares its null method and matrix family. This function neither
    creates p-values nor proves exchangeability/dependence assumptions.
    """
    if qualified is not True or not isinstance(method, str) or not method.strip():
        raise ContractError("qualified p-value method and complete matrix required")
    p = _numeric(pvalues, "p-values")
    if p.ndim != 1 or not len(p) or ((p < 0) | (p > 1)).any():
        raise ContractError("complete one-dimensional p-values in [0,1] required")
    order = np.argsort(p, kind="stable")
    adjusted = np.minimum.accumulate(
        (p[order] * len(p) / np.arange(1, len(p) + 1))[::-1]
    )[::-1]
    result = np.empty(len(p))
    result[order] = np.minimum(adjusted, 1.0)
    return result
