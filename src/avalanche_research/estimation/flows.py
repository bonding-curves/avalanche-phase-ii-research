"""Weekly net delegated flow against the staking spread: the proposal's flow equation.

    net weekly delegated flow / unstaked supply = sensitivity * tanh(staking_rate - external_yield)

Net flow in a Monday week is the AVAX of delegations whose stake starts in the week minus the AVAX of
delegations whose stake ends in the week, from ``observed_delegations``. Unstaked supply is the stock at the
week's start from ``market_weeks`` (``SD6``: a stock, not a population choosing). The spread is the one defined
in ``lifecycle``. The equation has no intercept, so it is fitted through the origin, with Newey-West standard
errors. A fit with an intercept is reported beside it as a diagnostic.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from . import _stats
from .fit import pearson_r, rmse
from .lifecycle import HAC_LAGS, in_window

STRATA = {"all": "net_flow_all_avax", "excl_concentrated": "net_flow_excl_avax"}
PRIMARY_STRATUM = "all"


def weekly_flows(con: Any, market: pd.DataFrame) -> pd.DataFrame:
    """Per week and stratum: inflow, outflow, and net delegated AVAX, with the ledger's change in delegated stake."""
    flows = con.execute(
        """
        WITH inflow AS (
          SELECT date_trunc('week', start_time) AS w, sum(stake_avax) AS a,
                 sum(stake_avax) FILTER (WHERE NOT concentrated_address) AS e
          FROM observed_delegations GROUP BY 1
        ), outflow AS (
          SELECT date_trunc('week', end_time) AS w, sum(stake_avax) AS a,
                 sum(stake_avax) FILTER (WHERE NOT concentrated_address) AS e
          FROM observed_delegations GROUP BY 1
        )
        SELECT m.week_start_utc,
               coalesce(i.a, 0) AS inflow_all_avax, coalesce(o.a, 0) AS outflow_all_avax,
               coalesce(i.e, 0) AS inflow_excl_avax, coalesce(o.e, 0) AS outflow_excl_avax,
               lead(m.active_delegated_stake_avax) OVER (ORDER BY m.week_start_utc) - m.active_delegated_stake_avax
                 AS ledger_delegated_change_avax
        FROM market_weeks m
        LEFT JOIN inflow i ON i.w = m.week_start_utc
        LEFT JOIN outflow o ON o.w = m.week_start_utc
        ORDER BY m.week_start_utc
        """
    ).df()
    flows["week_start_utc"] = pd.to_datetime(flows["week_start_utc"])
    flows["net_flow_all_avax"] = flows["inflow_all_avax"] - flows["outflow_all_avax"]
    flows["net_flow_excl_avax"] = flows["inflow_excl_avax"] - flows["outflow_excl_avax"]
    return flows.merge(market[["week_start_utc", "unstaked_supply_avax", "spread"]], on="week_start_utc", how="left")


def fit_flow(frame: pd.DataFrame, column: str, fit_window: tuple[str, str], holdout_window: tuple[str, str], halves: list[tuple[str, str]]) -> dict[str, Any]:
    def rows(window):
        part = frame[in_window(frame["week_start_utc"], window)].dropna(subset=["spread", "unstaked_supply_avax"])
        return (part[column] / part["unstaked_supply_avax"]).to_numpy(float), np.tanh(part["spread"].to_numpy(float))

    y, x = rows(fit_window)
    main = _stats.ols(y, x[:, None], ("sensitivity",), hac_lags=HAC_LAGS)
    with_intercept = _stats.ols(y, np.column_stack([np.ones(len(x)), x]), ("intercept", "sensitivity"), hac_lags=HAC_LAGS)
    halves_estimates = []
    for window in halves:
        y_half, x_half = rows(window)
        halves_estimates.append(float(_stats.ols(y_half, x_half[:, None], ("sensitivity",), hac_lags=HAC_LAGS).coef[0]))
    y_out, x_out = rows(holdout_window)
    predicted = main.coef[0] * x_out
    table = main.table()["sensitivity"]
    return {
        "sensitivity": float(main.coef[0]),
        "se": table["se"],
        "ci95": table["ci95"],
        "weeks": main.n,
        "mean_ratio": float(y.mean()),
        "half_window_sensitivity": halves_estimates,
        "with_intercept": with_intercept.table(),
        "holdout": {
            "weeks": len(y_out),
            "rmse": rmse(y_out, predicted),
            "rmse_zero_flow": rmse(y_out, np.zeros_like(y_out)),
            "pearson_r": pearson_r(y_out, predicted) if np.std(predicted) > 0 else float("nan"),
            "mean_ratio": float(y_out.mean()),
            "mean_predicted": float(predicted.mean()),
        },
    }


def fit_strata(frame: pd.DataFrame, fit_window: tuple[str, str], holdout_window: tuple[str, str], halves: list[tuple[str, str]]) -> dict[str, dict[str, Any]]:
    return {stratum: fit_flow(frame, column, fit_window, holdout_window, halves) for stratum, column in STRATA.items()}


def ledger_check(frame: pd.DataFrame, window: tuple[str, str]) -> dict[str, float]:
    """Agreement of the all-delegations net flow with the ledger's week-over-week change in delegated stake."""
    part = frame[in_window(frame["week_start_utc"], window)].dropna(subset=["ledger_delegated_change_avax"])
    difference = part["net_flow_all_avax"] - part["ledger_delegated_change_avax"]
    return {
        "weeks": len(part),
        "pearson_r": pearson_r(part["net_flow_all_avax"], part["ledger_delegated_change_avax"]),
        "median_abs_difference_avax": float(difference.abs().median()),
        "max_abs_difference_avax": float(difference.abs().max()),
    }


def identified(strata: dict[str, dict[str, Any]]) -> bool:
    """Same sign in both strata and both halves of the fit window, and no 95% interval spanning zero."""
    estimates = [s["sensitivity"] for s in strata.values()] + [v for s in strata.values() for v in s["half_window_sensitivity"]]
    same_sign = len({np.sign(v) for v in estimates}) == 1
    excludes_zero = all(s["ci95"][0] > 0 or s["ci95"][1] < 0 for s in strata.values())
    return bool(same_sign and excludes_zero)
