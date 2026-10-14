"""Full Saltelli MM3 adapter with supplied joint-base resampling, no new draws.

Numerics retain the delivered centered-B Saltelli first/Jansen total estimators.
BA rows are validated and retained in the resampling contract even though these
two estimators use A, B and AB. Never filters by response or pools yields.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .m2_associations import (
    BOUNDS,
    FAMILY_INPUTS,
    _bases,
    _configuration,
    _digest,
    _draws,
    _integers,
    _numeric,
    _validated,
)
from .rank_associations import ContractError
from .sobol import _indices


def _hybrids(scope, a, b, inputs):
    n, d = len(a), len(inputs)
    coordinates = [f"u{j + 1}" for j in range(d)]
    ca, cb = a[coordinates].to_numpy(), b[coordinates].to_numpy()
    blocks = {}
    for role, own, other, parent in (("AB", ca, cb, a), ("BA", cb, ca, b)):
        all_rows = scope.loc[scope.block == role]
        js = _integers(all_rows.j, role + " hybrid j")
        if len(all_rows) != n * d or set(js) != set(range(1, d + 1)):
            raise ContractError(
                "all AB/BA hybrid coordinates required, numbered from one"
            )
        parts = []
        for j in range(d):
            rows = all_rows.loc[all_rows.j == j + 1].sort_values("i", kind="stable")
            if not np.array_equal(_integers(rows.i, "hybrid i"), np.arange(n)):
                raise ContractError("missing or repeated hybrid base index")
            expected = own.copy()
            expected[:, j] = other[:, j]
            if not np.array_equal(rows[coordinates].to_numpy(), expected):
                raise ContractError(role + " coordinate replacement/order differs")
            for name in ("seed", "draw"):
                if not np.array_equal(
                    _integers(rows[name], name), parent[name].to_numpy()
                ):
                    raise ContractError(role + " must retain its parent seed/draw")
            for column, name in enumerate(inputs):
                lo, hi = BOUNDS[name]
                if not np.array_equal(
                    _numeric(rows[name], name), lo + expected[:, column] * (hi - lo)
                ):
                    raise ContractError("hybrid physical input differs from coordinate")
            _integers(rows.baseline, "hybrid baseline")
            parts.append(rows)
        blocks[role] = parts
    return blocks


def _batch_indices(a, b, ab):
    """Vectorized equivalent of sobol._indices for leading bootstrap dimension."""
    scale = np.maximum.reduce(
        [
            np.max(np.abs(a), axis=1),
            np.max(np.abs(b), axis=1),
            np.max(np.abs(ab), axis=(1, 2)),
        ]
    )
    scale = np.where(scale == 0, 1.0, scale)
    a, b, ab = (
        a / scale[:, None, :],
        b / scale[:, None, :],
        ab / scale[:, None, None, :],
    )
    center = np.mean(np.concatenate([a, b], axis=1), axis=1)
    a, b, ab = (
        a - center[:, None, :],
        b - center[:, None, :],
        ab - center[:, None, None, :],
    )
    variance = np.var(np.concatenate([a, b], axis=1), axis=1, ddof=0)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore", under="ignore"):
        first = (
            np.mean(b[:, :, None, :] * (ab - a[:, :, None, :]), axis=1)
            / variance[:, None, :]
        )
        total = (
            0.5 * np.mean((a[:, :, None, :] - ab) ** 2, axis=1) / variance[:, None, :]
        )
    valid = (
        (variance > 0)
        & np.isfinite(variance)
        & np.isfinite(first).all(axis=1)
        & np.isfinite(total).all(axis=1)
    )
    first = np.where(valid[:, None, :], first, np.nan)
    total = np.where(valid[:, None, :], total, np.nan)
    return first, total, valid


def analyze_sensitivity(
    frame,
    *,
    measures,
    bootstrap_indices,
    bootstrap_replicates=1000,
    confidence=0.95,
    convergence_sizes=(256, 512),
    batch_size=32,
):
    """Return (long rows, metadata) for each complete family/yield design.

    Supplied draw positions refer to sorted original i, not filtered cells. The
    N/2N check always uses original i prefixes, never bootstrap/canonical strings.
    Nonstandard sizes/replicate counts are labelled synthetic qualification.
    """
    _configuration(bootstrap_replicates, confidence, batch_size)
    if (
        type(convergence_sizes) is not tuple
        or len(convergence_sizes) != 2
        or any(type(n) is not int or n < 2 or n & (n - 1) for n in convergence_sizes)
        or convergence_sizes[1] != 2 * convergence_sizes[0]
    ):
        raise ContractError("nested power-of-two N/2N convergence sizes required")
    measures, selected, horizon = _validated(frame, measures)
    records, inventory = [], []
    for (family, yield_pp), scope in selected.groupby(
        ["family", "yield_pp"], sort=True
    ):
        a, b = _bases(scope, family)
        inputs, n = FAMILY_INPUTS[family], len(a)
        hybrids = _hybrids(scope, a, b, inputs)
        draws = _draws(
            bootstrap_indices, (family, float(yield_pp)), n, bootstrap_replicates
        )
        ya, yb = (
            a[list(measures)].to_numpy(dtype=float),
            b[list(measures)].to_numpy(dtype=float),
        )
        yab = np.stack(
            [part[list(measures)].to_numpy(dtype=float) for part in hybrids["AB"]],
            axis=1,
        )
        point_f, point_t, point_valid = _indices(ya, yb, yab)
        fs = np.empty((bootstrap_replicates, len(inputs), len(measures)))
        ts = np.empty_like(fs)
        valid = np.empty((bootstrap_replicates, len(measures)), dtype=bool)
        for lo in range(0, bootstrap_replicates, batch_size):
            hi = min(lo + batch_size, bootstrap_replicates)
            ix = draws[lo:hi]
            fs[lo:hi], ts[lo:hi], valid[lo:hi] = _batch_indices(ya[ix], yb[ix], yab[ix])
        convergence = n == convergence_sizes[1]
        if convergence:
            small = _indices(
                ya[: convergence_sizes[0]],
                yb[: convergence_sizes[0]],
                yab[: convergence_sizes[0]],
            )
        membership = _digest(scope.sort_values(["block", "j", "i"])["index"].to_numpy())
        for m, measure in enumerate(measures):
            assessable = bool(point_valid[m])
            interval_ok = assessable and valid[:, m].all()
            if interval_ok:
                flo, fhi = np.quantile(fs[:, :, m], [0.025, 0.975], axis=0)
                tlo, thi = np.quantile(ts[:, :, m], [0.025, 0.975], axis=0)
            else:
                flo = fhi = tlo = thi = np.full(len(inputs), np.nan)
            movement = np.nan
            if convergence and assessable and small[2][m]:
                movement = float(
                    np.max(
                        np.abs(
                            np.concatenate(
                                [
                                    point_f[:, m] - small[0][:, m],
                                    point_t[:, m] - small[1][:, m],
                                ]
                            )
                        )
                    )
                )
            for j, name in enumerate(inputs):
                records.append(
                    {
                        "family": family,
                        "yield_pp": float(yield_pp),
                        "horizon_days": horizon,
                        "measure": measure,
                        "input": name,
                        "method": "sobol",
                        "first": point_f[j, m],
                        "total": point_t[j, m],
                        "first_low": flo[j],
                        "first_high": fhi[j],
                        "total_low": tlo[j],
                        "total_high": thi[j],
                        "base_n": n,
                        "max_change": movement,
                        "converged": bool(movement <= 0.02)
                        if np.isfinite(movement)
                        else pd.NA,
                        "convergence_status": "assessable"
                        if np.isfinite(movement)
                        else "unassessable",
                        "convergence_reason": ""
                        if np.isfinite(movement)
                        else "missing_nested_sizes_or_undefined_index",
                        "status": "assessable" if assessable else "unassessable",
                        "reason": ""
                        if assessable
                        else "zero_variance_or_nonfinite_index",
                        "interval_status": "assessable"
                        if interval_ok
                        else "unassessable",
                        "bootstrap_valid": int(valid[:, m].sum()),
                        "bootstrap_total": bootstrap_replicates,
                        "membership_sha256": membership,
                    }
                )
        inventory.append(
            {
                "family": family,
                "yield_pp": float(yield_pp),
                "base_n": n,
                "base_ids": list(range(n)),
                "bootstrap_indices_sha256": _digest(draws),
                "retained_BA_rows": n * len(inputs),
                "membership_sha256": membership,
            }
        )
    return pd.DataFrame(records), {
        "method": "MM3",
        "scopes": inventory,
        "bootstrap_replicates": bootstrap_replicates,
        "confidence": confidence,
        "convergence_sizes": list(convergence_sizes),
        "maximum_movement": 0.02,
        "frozen_configuration": bootstrap_replicates == 1000
        and convergence_sizes == (256, 512)
        and all(s["base_n"] == 512 for s in inventory),
        "bootstrap_unit": "complete family/yield i, all A/B/AB/BA and referenced baselines",
        "estimators": "centered-B Saltelli first; Jansen total; pooled A/B ddof0 variance",
        "interval_interpretation": "conditional design percentiles; no index clipping or empirical coverage claim",
        "included_roles": ["A", "B", "AB", "BA"],
        "input_rows": len(frame),
        "output_rows": len(records),
    }
