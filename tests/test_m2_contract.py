"""Independent boundary and affine-KPI controls for the frozen M2 adapter."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from avalanche_research.analysis.m2_contract import (
    COSTS,
    ContractError,
    failure_labels,
    rescore_costs,
    response_band,
)
from avalanche_research.model.kpis import return_margin


def test_exact_band_boundaries_and_neighbors():
    points = [0, np.nextafter(1 / 3, 0), 1 / 3, np.nextafter(2 / 3, 0), 2 / 3, 1]
    assert response_band(points).tolist() == ["low", "low", "middle", "middle", "high", "high"]
    for bad in [[-0.001], [1.001], [np.nan], [True], ["0.5"]]:
        with pytest.raises(ContractError):
            response_band(bad)


def test_cost_rescore_matches_direct_kpi_for_both_horizons():
    origin = date(2025, 11, 18)
    days = pd.date_range(origin, periods=366)
    daily = pd.DataFrame({"issued_navax": np.arange(366) + 1.0,
                          "started_stake_days_navax": (np.arange(366) + 1.0) * 6000}, index=days)
    zero = [return_margin(daily, origin, horizon, .03, 0) for horizon in (180, 365)]
    scored = rescore_costs(pd.DataFrame({"return_margin": zero}))
    for name, cost in COSTS.items():
        for i, horizon in enumerate((180, 365)):
            column = "return_margin" if name == "zero" else f"return_margin_{name}"
            assert scored.loc[i, column] == return_margin(daily, origin, horizon, .03, cost)
    assert scored.return_margin.tolist() == zero


def test_limit_equality_passes_and_goal_zero_is_not_positive():
    frame = rescore_costs(pd.DataFrame({"return_margin": [.015, .0149], "issuance_saved": [0., .1],
                                      "validator_stake_retained": [1., .89], "net_inflation": [.05, .0501]}))
    failed = failure_labels(frame)
    assert failed.iloc[0].to_dict() == {"issuance_saved": True, "validator_stake_retained": False,
                                        "net_inflation": False, "return_margin": False}
    assert failed.iloc[1].to_dict() == {"issuance_saved": False, "validator_stake_retained": True,
                                        "net_inflation": True, "return_margin": True}


def test_missing_or_nonfinite_never_imputes():
    with pytest.raises(ContractError):
        rescore_costs(pd.DataFrame({"return_margin": [np.nan]}))
    with pytest.raises(ContractError):
        failure_labels(pd.DataFrame({"issuance_saved": [0]}))
