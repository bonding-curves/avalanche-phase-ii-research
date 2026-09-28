"""Goal thresholds from the proposal and pass or fail per trajectory.

KPI rules:

- STAKING_RATIO passes when the final staking ratio is within [50%, 60%].
- VALIDATOR_COUNT passes when the final validator count exceeds 1,000.
- DECENTRALIZATION (1 - HHI) is "higher is better". It passes when the mean is at least the observed baseline.
- NET_INFLATION passes when its daily series has a negative least-squares slope.
- VAL_PROFITABILITY passes when mean monthly profit per validator is above zero.
- APR_VOLATILITY and STAKING_VOLATILITY are "low". Low means below the observed baseline.

The baseline is the same KPI computed by ``kpis.observed_kpis`` on the observed ledger, 2025-01-01 to 2025-12-31
unless stated otherwise in ``Thresholds.basis``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

GROUPS: dict[str, tuple[str, ...]] = {
    "G1": ("VAL_PROFITABILITY", "APR_VOLATILITY"),
    "G2": ("DECENTRALIZATION", "VALIDATOR_COUNT"),
    "G3": ("STAKING_RATIO", "STAKING_VOLATILITY", "NET_INFLATION"),
}
KPI_NAMES = ("STAKING_RATIO", "VALIDATOR_COUNT", "DECENTRALIZATION", "NET_INFLATION", "VAL_PROFITABILITY",
             "APR_VOLATILITY", "STAKING_VOLATILITY")
BASELINE_PERIOD = ("2025-01-01", "2025-12-31")


@dataclass(frozen=True)
class Thresholds:
    decentralization_min: float
    apr_volatility_max: float
    staking_volatility_max: float
    basis: str
    staking_ratio_low: float = 0.50
    staking_ratio_high: float = 0.60
    validator_count_min: float = 1000
    profit_min: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def thresholds_from_observed(observed: Mapping[str, Any], period: tuple[str, str] = BASELINE_PERIOD) -> Thresholds:
    """Baselines from observed KPIs (the output of ``kpis.observed_kpis``) over ``period``."""
    return Thresholds(
        decentralization_min=float(observed["decentralization_mean"]),
        apr_volatility_max=float(observed["apr_volatility"]),
        staking_volatility_max=float(observed["staking_volatility"]),
        basis=f"observed ledger {period[0]} to {period[1]}",
    )


def evaluate(results: pd.DataFrame, thresholds: Thresholds) -> pd.DataFrame:
    """Add ``pass_<KPI>``, ``pass_G1`` to ``pass_G3``, and ``pass_all`` columns to a KPI table."""
    out = results.copy()
    ratio = out["staking_ratio_final"]
    checks = {
        "STAKING_RATIO": (ratio >= thresholds.staking_ratio_low) & (ratio <= thresholds.staking_ratio_high),
        "VALIDATOR_COUNT": out["validator_count_final"] > thresholds.validator_count_min,
        "DECENTRALIZATION": out["decentralization_mean"] >= thresholds.decentralization_min,
        "NET_INFLATION": out["net_inflation_decreasing"].astype(bool),
        "VAL_PROFITABILITY": out["val_profitability_mean"] > thresholds.profit_min,
        "APR_VOLATILITY": out["apr_volatility"] < thresholds.apr_volatility_max,
        "STAKING_VOLATILITY": out["staking_volatility"] < thresholds.staking_volatility_max,
    }
    for name in KPI_NAMES:
        out[f"pass_{name}"] = checks[name].to_numpy(dtype=bool)
    for group, members in GROUPS.items():
        out[f"pass_{group}"] = out[[f"pass_{name}" for name in members]].all(axis=1)
    out["pass_all"] = out[[f"pass_{group}" for group in GROUPS]].all(axis=1)
    return out


def pass_shares(evaluated: pd.DataFrame) -> pd.DataFrame:
    """Per parameter set, the share of (scenario, seed) trajectories passing each KPI, group, and all goals."""
    columns = [column for column in evaluated.columns if column.startswith("pass_")]
    return evaluated.groupby("param_id")[columns].mean().rename(columns=lambda name: name.replace("pass_", "share_"))
