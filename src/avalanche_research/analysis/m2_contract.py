"""Explicit scopes and frozen scientific constants for the M2 analysis.

This module selects no observations or fitted model. Input values must come
from an authenticated paired-sweep bundle and complete KPI table.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

FAMILY_INPUTS = {
    "ramp": ("target_min_rate", "renewal_response", "entry_response"),
    "before": ("renewal_response", "entry_response"),
    "tenure": ("boost_max", "renewal_response", "entry_response"),
    "quadratic": ("exponent", "renewal_response", "entry_response"),
}
COSTS = {"zero": 0.0, "low": 0.0075, "mid": 0.015, "high": 0.03}
BOOTSTRAP_REPLICATES = 1000
BOOTSTRAP_SEED = 20261005
CONFIDENCE = 0.95
HORIZONS = (180, 365)
BANDS = ("low", "middle", "high")
CHAIN_INFLATION = 0.02397867184808486
PRICE_FACTOR = 14.58 / 26.10


class ContractError(ValueError):
    """An analysis input cannot satisfy its declared scientific scope."""


def response_band(unit):
    """Equal-width unit-coordinate bands with explicit endpoint ownership."""
    a = np.asarray(unit)
    if a.dtype.kind not in "fiu" or not np.isfinite(a).all():
        raise ContractError("finite numeric response coordinates required")
    if ((a < 0) | (a > 1)).any():
        raise ContractError("response coordinate outside unit interval")
    return np.asarray(BANDS)[np.minimum((a * 3).astype(int), 2)]


def row_metadata(bundle):
    """Preserve all labels and physical inputs, never infer role from output."""
    frame = bundle.labels.sort_values("index", kind="stable").reset_index(drop=True).copy()
    if frame["index"].duplicated().any() or len(frame) != len(bundle.rows):
        raise ContractError("unique complete row labels required")
    if frame["index"].tolist() != list(range(len(bundle.rows))):
        raise ContractError("source row indices must be complete")
    for column in ("u1", "u2", "u3"):
        if column in frame:
            frame[column] = frame[column].map(lambda v: np.nan if v == "" else float(v))
    rows = bundle.rows
    for name in ("seed", "draw", "renewal_response", "entry_response", "model", "origin"):
        frame[name] = [r[name] for r in rows]
    for name in ("target_min_rate", "boost_max", "exponent"):
        frame[name] = [r["mechanism"].get(name, np.nan) for r in rows]
    frame["renewal_band"] = "not_applicable"
    frame["entry_band"] = "not_applicable"
    for family, inputs in FAMILY_INPUTS.items():
        mask = (frame.family == family) & frame.block.isin(("A", "B", "AB", "BA", "noise"))
        offset = len(inputs) - 2
        for field, position in (("renewal", offset + 1), ("entry", offset + 2)):
            unit = frame.loc[mask, f"u{position}"].to_numpy(dtype=float)
            actual = frame.loc[mask, field + "_response"].to_numpy(dtype=float)
            if not np.allclose(actual, unit * 0.1, rtol=0, atol=2e-17):
                raise ContractError("response and original unit coordinate differ")
            frame.loc[mask, field + "_band"] = response_band(unit)
    for block in ("zero", "stress"):
        mask = frame.block == block
        frame.loc[mask, ["renewal_band", "entry_band"]] = block
    # The stress axes remain numerical and j remains the original setting ID.
    frame["unit_id"] = [
        f"anchor:{y:g}:{i}" if b in ("zero", "stress") else f"{b if b == 'noise' else 'saltelli'}:{f}:{y:g}:{i}"
        for f, y, b, i in frame[["family", "yield_pp", "block", "i"]].itertuples(index=False, name=None)
    ]
    return frame


def rescore_costs(frame, *, price_factor=PRICE_FACTOR):
    """Affine cost transformation; the original zero margin remains intact."""
    if not math.isfinite(price_factor) or price_factor <= 0:
        raise ContractError("positive finite cost conversion required")
    if "return_margin" not in frame or not np.isfinite(frame.return_margin).all():
        raise ContractError("complete finite zero-cost margins required")
    result = frame.copy()
    for name, cost in COSTS.items():
        if name == "zero":
            continue
        result[f"return_margin_{name}"] = result.return_margin - cost
        result[f"return_margin_{name}_fitting_price"] = result.return_margin - cost * price_factor
    return result


def failure_labels(frame, *, cost="mid", inflation=0.05, strict_stake=False):
    """The frozen goal/limit labels, with equality retained as a pass."""
    if cost not in COSTS or not math.isfinite(inflation):
        raise ContractError("declared cost and finite inflation line required")
    margin = "return_margin" if cost == "zero" else f"return_margin_{cost}"
    columns = ("issuance_saved", "validator_stake_retained", "net_inflation", margin)
    if any(c not in frame or not np.isfinite(frame[c]).all() for c in columns):
        raise ContractError("all goal and limit observations required")
    floor = 1.0 if strict_stake else 1.0 - frame.issuance_saved
    return pd.DataFrame({
        "issuance_saved": frame.issuance_saved <= 0,
        "validator_stake_retained": frame.validator_stake_retained < floor,
        "net_inflation": frame.net_inflation > inflation,
        "return_margin": frame[margin] < 0,
    }, index=frame.index)
