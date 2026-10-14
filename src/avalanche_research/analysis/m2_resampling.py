"""Whole-unit resampling with caller-owned random state and explicit scope."""
from __future__ import annotations

import hashlib

import numpy as np

from .m2_contract import BOOTSTRAP_REPLICATES, ContractError


def draw_indices(n_units, rng, *, replicates=BOOTSTRAP_REPLICATES):
    if type(n_units) is not int or n_units < 2:
        raise ContractError("at least two independent units required")
    if type(replicates) is not int or replicates < 2:
        raise ContractError("at least two resamples required")
    result = rng.integers(0, n_units, size=(replicates, n_units), dtype=np.int64)
    return validate_indices(result, n_units)


def validate_indices(indices, n_units, *, replicates=None):
    a = np.asarray(indices)
    if a.dtype.kind not in "iu" or a.ndim != 2 or a.shape[1] != n_units:
        raise ContractError("complete integer whole-unit index matrix required")
    if a.shape[0] < 2 or (replicates is not None and a.shape[0] != replicates):
        raise ContractError("resample count differs")
    if (a < 0).any() or (a >= n_units).any():
        raise ContractError("resample index outside declared units")
    return a


def indices_sha256(indices):
    return hashlib.sha256(np.asarray(indices, dtype="<i8").tobytes()).hexdigest()


def scope_draws(labels, rng, *, replicates=BOOTSTRAP_REPLICATES):
    """One shared matrix per Saltelli family/yield; original i fixes ordering."""
    results = {}
    saltelli = labels.loc[labels.block.isin(("A", "B", "AB", "BA"))]
    for (family, yield_pp), group in saltelli.groupby(["family", "yield_pp"], sort=True):
        units = sorted(group.i.unique())
        if any(not {"A", "B"}.issubset(set(part.block)) for _, part in group.groupby("i")):
            raise ContractError("incomplete Saltelli base membership")
        results[(family, float(yield_pp))] = draw_indices(len(units), rng, replicates=replicates)
    return results


def cluster_statistics(values, unit_ids, indices):
    """Ratio of sums after expanding complete clusters, not means of means."""
    a = np.asarray(values, dtype=float)
    ids = np.asarray(unit_ids)
    if a.ndim != 1 or ids.shape != a.shape or not np.isfinite(a).all():
        raise ContractError("complete finite value/unit vectors required")
    units, inverse = np.unique(ids, return_inverse=True)
    draws = validate_indices(indices, len(units))
    totals = np.bincount(inverse, weights=a)
    counts = np.bincount(inverse)
    return totals[draws].sum(axis=1) / counts[draws].sum(axis=1)


def replicated_noise_share(values, indices):
    """Nonnegative one-way random-effects variance share from complete repeats.

    Rows are original noise points, columns their eight independent keys. The
    within component is the mean unbiased within-point variance. The raw between
    component is var(point means, ddof=1) minus within/8. Retain that raw estimate
    and truncate it at zero only for the nonnegative variance-share estimate.
    This is a conditional diagnostic, not a causal or QMC coverage guarantee.
    """
    a = np.asarray(values)
    if a.dtype.kind not in "iuf" or a.ndim != 2 or a.shape[0] < 2 or a.shape[1] != 8 or not np.isfinite(a).all():
        raise ContractError("complete finite point-by-eight-noise-key array required")
    draw = validate_indices(indices, len(a), replicates=1000)
    scale = float(np.max(np.abs(a))) or 1.0
    z = a / scale

    def components(v):
        within = np.mean(np.var(v, axis=-1, ddof=1), axis=-1)
        raw = np.var(np.mean(v, axis=-1), axis=-1, ddof=1) - within / 8
        denominator = within + np.maximum(raw, 0)
        with np.errstate(divide="ignore", invalid="ignore"):
            return within, raw, np.where(denominator > 0, within / denominator, np.nan)

    within, raw, point = components(z)
    _, _, boot = components(z[draw])
    valid = bool(np.isfinite(boot).all() and np.isfinite(point))
    ci = np.quantile(boot, [.025, .975]) if valid else [np.nan, np.nan]
    return {"noise_share": float(point), "ci_low": float(ci[0]), "ci_high": float(ci[1]),
            "within_variance": float(within * scale**2), "between_variance_raw": float(raw * scale**2),
            "between_truncated": bool(raw < 0), "points": len(a), "keys_per_point": 8,
            "status": "assessable" if valid else "unassessable",
            "reason": "" if valid else "zero_variance_point_or_bootstrap", "bootstrap_sha256": indices_sha256(draw)}
