"""Validator entry, duration choice, renewal, and exit, each against the staking spread.

The spread is the staking reward rate minus the external yield, both annual fractions, observed at the Monday
00:00 UTC cutoff:

* staking rate: the protocol kernel's annualized reward rate for a 14-day stake at the P-Chain supply counter
  read before the cutoff (``validator_weeks.supply_counter_avax``, ``RD8``). It is the gross rate, before any
  delegation fee, and it depends on supply only. Fourteen days matches the delegator features
  (``log_net_apy_14d``) and the simulation engine's quote (``sim.behaviour`` ``quote_duration_days``).
* external yield: the 3-month US Treasury par yield on the last observation date before the cutoff. The
  ``par_yield_daily.yield_rate`` column is already a fraction (0.0556 is 5.56%). It stands in for the 3-month
  bill until FRED ``DTB3`` is captured.

The functional forms are the ones ``sim.policies`` applies, with the spread entering uncentered: a base value is
the behaviour at a spread of zero, which lies below every observed week. Each block also reports its value at
the fit window's mean spread.

Validator periods come from ``staking_periods`` with ``role = 'validator'``, ordered per node:

* a start is a **renewal** when the node's previous period ended at most 7 days earlier, else an **entry**
  (the node's first period, or a return after a gap of more than 7 days);
* a period is **renewed** when the node starts another period within 7 days after it ends;
* an **exit** is a period end that is not renewed. Its hazard is exits per active validator-day.

Renewal probability and exit hazard describe the same events two ways. A model should use one of them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from ..model.protocol import MAINNET_REWARD, annualized_reward_rate
from ..model.types import NAVAX_PER_AVAX, SECONDS_PER_DAY
from . import _stats
from .choice import conditional_loglik, fit_conditional_logit

MENU_DAYS = (14, 30, 90, 180, 365)
BIN_UPPER_DAYS = (21, 45, 120, 240)
RENEWAL_WINDOW_DAYS = 7
QUOTE_DAYS = 14
QUOTE_STAKE_AVAX = 2_000
HAC_LAGS = 8
MINTING_PERIOD_DAYS = MAINNET_REWARD.minting_period_seconds / SECONDS_PER_DAY


def staking_rate(supply_avax: float, at: datetime) -> float:
    """Annualized kernel reward rate of a 14-day, 2,000 AVAX stake at the given supply counter."""
    supply_navax = round(supply_avax * NAVAX_PER_AVAX)
    return annualized_reward_rate(at, QUOTE_DAYS * SECONDS_PER_DAY, QUOTE_STAKE_AVAX * NAVAX_PER_AVAX, supply_navax)


def menu_bin(duration_days: np.ndarray | pd.Series) -> np.ndarray:
    """Map durations to the menu: <=21 to 14, <=45 to 30, <=120 to 90, <=240 to 180, longer to 365."""
    index = np.searchsorted(np.asarray(BIN_UPPER_DAYS, dtype=float), np.asarray(duration_days, dtype=float), side="left")
    return np.asarray(MENU_DAYS)[index]


def market_frame(con: Any) -> pd.DataFrame:
    """One row per Monday week: supply counter, staking rate, bill rate, spread, price, volatility, unstaked supply."""
    frame = con.execute(
        """
        WITH counter AS (
          SELECT week_start_utc, max(supply_counter_avax) AS supply_counter_avax
          FROM validator_weeks GROUP BY week_start_utc
        )
        SELECT m.week_start_utc, c.supply_counter_avax, m.total_supply_avax, m.unstaked_supply_avax,
               m.active_delegated_stake_avax, m.validators_active, m.price_usdt, m.volatility_30d
        FROM market_weeks m LEFT JOIN counter c USING (week_start_utc)
        ORDER BY m.week_start_utc
        """
    ).df()
    bills = con.execute(
        "SELECT observation_date, yield_rate FROM par_yield_daily WHERE tenor = '3m' AND yield_rate IS NOT NULL ORDER BY observation_date"
    ).df()
    bills["observation_date"] = pd.to_datetime(bills["observation_date"])
    frame["week_start_utc"] = pd.to_datetime(frame["week_start_utc"])
    frame = pd.merge_asof(
        frame, bills, left_on="week_start_utc", right_on="observation_date", allow_exact_matches=False, direction="backward"
    ).rename(columns={"observation_date": "bill_date"})
    frame = frame.rename(columns={"yield_rate": "bill_rate"})
    frame["staking_rate"] = [
        staking_rate(supply, week.to_pydatetime().replace(tzinfo=UTC)) if pd.notna(supply) else np.nan
        for supply, week in zip(frame["supply_counter_avax"], frame["week_start_utc"])
    ]
    frame["spread"] = frame["staking_rate"] - frame["bill_rate"]
    return frame


def validator_periods(con: Any) -> pd.DataFrame:
    """Validator periods with the node's previous end and next start, the start kind, and the renewal flag."""
    periods = con.execute(
        """
        SELECT node_id, transaction_hash, start_time, end_time,
               epoch(end_time - start_time) / 86400.0 AS duration_days,
               lag(end_time) OVER w AS previous_end, lead(start_time) OVER w AS next_start,
               date_trunc('week', start_time) AS start_week, date_trunc('week', end_time) AS end_week
        FROM staking_periods WHERE role = 'validator'
        WINDOW w AS (PARTITION BY node_id ORDER BY start_time, transaction_hash)
        ORDER BY start_time, transaction_hash
        """
    ).df()
    window = np.timedelta64(RENEWAL_WINDOW_DAYS, "D")
    periods["kind"] = np.where(
        periods["previous_end"].isna(), "first",
        np.where(periods["start_time"] <= periods["previous_end"] + window, "renewal", "return"),
    )
    periods["entry"] = periods["kind"] != "renewal"
    periods["renewed"] = periods["next_start"].notna() & (periods["next_start"] <= periods["end_time"] + window)
    periods["menu_days"] = menu_bin(periods["duration_days"])
    return periods


def active_validator_days(con: Any) -> pd.DataFrame:
    """Validator-days of active stake inside each Monday week."""
    return con.execute(
        """
        WITH w AS (SELECT week_start_utc AS ws, week_start_utc + INTERVAL 7 DAY AS we FROM market_weeks)
        SELECT w.ws AS week_start_utc,
               sum(epoch(least(p.end_time, w.we) - greatest(p.start_time, w.ws))) / 86400.0 AS active_validator_days
        FROM w JOIN staking_periods p ON p.role = 'validator' AND p.start_time < w.we AND p.end_time > w.ws
        GROUP BY 1 ORDER BY 1
        """
    ).df().assign(week_start_utc=lambda d: pd.to_datetime(d["week_start_utc"]))


def in_window(values: pd.Series, window: tuple[str, str]) -> pd.Series:
    return (values >= pd.Timestamp(window[0])) & (values < pd.Timestamp(window[1]))


def weekly_lifecycle(market: pd.DataFrame, periods: pd.DataFrame, exposure: pd.DataFrame) -> pd.DataFrame:
    """Per week: entries, starts, exits, ended periods, and active validator-days, joined to the spread."""
    starts = periods.groupby("start_week").agg(starts=("entry", "size"), entries=("entry", "sum"))
    ends = periods.groupby("end_week").agg(ended=("renewed", "size"), renewed=("renewed", "sum"))
    ends["exits"] = ends["ended"] - ends["renewed"]
    frame = market.set_index("week_start_utc")
    frame = frame.join(starts, how="left").join(ends, how="left").join(exposure.set_index("week_start_utc"), how="left")
    for column in ("starts", "entries", "ended", "renewed", "exits", "active_validator_days"):
        frame[column] = frame[column].fillna(0.0)
    return frame.reset_index()


def _sign_stable(values: list[float]) -> bool:
    return len({np.sign(v) for v in values}) == 1


def _excludes_zero(interval: list[float]) -> bool:
    return interval[0] > 0 or interval[1] < 0


def fit_entry(weekly: pd.DataFrame, fit_window: tuple[str, str], holdout_window: tuple[str, str], halves: list[tuple[str, str]]) -> dict[str, Any]:
    """Weekly entries ~ Poisson(7 * base_per_day * exp(elasticity * spread)), Newey-West errors."""

    def design(frame):
        return np.column_stack([np.ones(len(frame)), frame["spread"]]), np.full(len(frame), np.log(7.0))

    def fit(window):
        part = weekly[in_window(weekly["week_start_utc"], window)]
        X, offset = design(part)
        return _stats.poisson(part["entries"].to_numpy(), X, ("log_base_per_day", "spread_elasticity"), offset, hac_lags=HAC_LAGS), part

    main, fit_part = fit(fit_window)
    null = _stats.poisson(
        fit_part["entries"].to_numpy(), np.ones((len(fit_part), 1)), ("log_base_per_day",), np.full(len(fit_part), np.log(7.0)), hac_lags=HAC_LAGS
    )
    out = weekly[in_window(weekly["week_start_utc"], holdout_window)]
    X_out, offset_out = design(out)
    predicted = np.exp(offset_out + X_out @ main.coef)
    half_estimates = [fit(window)[0].coef[1] for window in halves]
    table = main.table()
    elasticity_ci = table["spread_elasticity"]["ci95"]
    return {
        "base_per_day": float(np.exp(main.coef[0])),
        "spread_elasticity": float(main.coef[1]),
        "ci95": {
            "base_per_day": [float(np.exp(v)) for v in table["log_base_per_day"]["ci95"]],
            "spread_elasticity": elasticity_ci,
        },
        "identified": bool(_excludes_zero(elasticity_ci) and _sign_stable(half_estimates + [main.coef[1]])),
        "form": "new validators per day = base_per_day * exp(spread_elasticity * spread)",
        "diagnostics": {
            "rate_at_mean_spread": float(np.exp(main.coef[0] + main.coef[1] * fit_part["spread"].mean())),
            "weeks": main.n, "entries": float(fit_part["entries"].sum()), "se": {k: v["se"] for k, v in table.items()},
            "half_window_elasticity": [float(v) for v in half_estimates],
            "holdout": {
                "weeks": len(out), "entries": float(out["entries"].sum()), "predicted": float(predicted.sum()),
                "loglik": _stats.poisson_loglik(out["entries"].to_numpy(), X_out, main.coef, offset_out),
                "loglik_no_spread": _stats.poisson_loglik(out["entries"].to_numpy(), X_out[:, :1], null.coef, offset_out),
                "rmse_per_week": float(np.sqrt(np.mean((out["entries"].to_numpy() - predicted) ** 2))),
            },
        },
    }


def _duration_rows(periods: pd.DataFrame, market: pd.DataFrame, window: tuple[str, str]) -> pd.DataFrame:
    part = periods[in_window(periods["start_week"], window)]
    counts = part.groupby(["start_week", "menu_days"]).size().unstack(fill_value=0).reindex(columns=list(MENU_DAYS), fill_value=0)
    rows = counts.stack().rename("n").reset_index()
    rows = rows.merge(market[["week_start_utc", "spread"]], left_on="start_week", right_on="week_start_utc", how="left")
    for days in MENU_DAYS[1:]:
        rows[f"const_{days}"] = (rows["menu_days"] == days).astype(float)
    rows["spread_x_years"] = rows["spread"] * rows["menu_days"] / MINTING_PERIOD_DAYS
    return rows


DURATION_NAMES = tuple(f"const_{days}" for days in MENU_DAYS[1:]) + ("spread_x_years",)


def duration_probabilities(constants: np.ndarray, elasticity: float, spread: float) -> np.ndarray:
    utility = np.concatenate([[0.0], constants]) + elasticity * spread * np.asarray(MENU_DAYS) / MINTING_PERIOD_DAYS
    weight = np.exp(utility - utility.max())
    return weight / weight.sum()


def fit_duration(periods: pd.DataFrame, market: pd.DataFrame, fit_window: tuple[str, str], holdout_window: tuple[str, str], halves: list[tuple[str, str]], seed: int = 0) -> dict[str, Any]:
    """Multinomial logit over the menu with one constant per duration and one spread slope on days / 365.

    P(k | spread) is proportional to probabilities_k * exp(spread_elasticity * spread * days_k / 365),
    so a positive elasticity moves choices toward longer durations when the spread is higher.
    """

    def fit(window, names=DURATION_NAMES):
        rows = _duration_rows(periods, market, window)
        return fit_conditional_logit(rows["n"].to_numpy(float), rows[list(names)].to_numpy(float), rows["start_week"].to_numpy(), names), rows

    main, rows = fit(fit_window)
    null, _ = fit(fit_window, DURATION_NAMES[:-1])
    out = _duration_rows(periods, market, holdout_window)
    y_out, g_out = out["n"].to_numpy(float), out["start_week"].to_numpy()
    constants, elasticity = main.fit.coef[:-1], float(main.fit.coef[-1])
    probabilities = duration_probabilities(constants, elasticity, 0.0)
    mean_spread = float(market.loc[in_window(market["week_start_utc"], fit_window), "spread"].mean())
    rng = np.random.default_rng(seed)
    draws = rng.multivariate_normal(main.fit.coef, main.fit.cov, size=4000)
    draw_p = np.array([duration_probabilities(d[:-1], d[-1], 0.0) for d in draws])
    elasticity_ci = [float(v) for v in main.fit.ci95[-1]]
    half_estimates = [float(fit(window)[0].fit.coef[-1]) for window in halves]
    fit_shares = rows.groupby("menu_days")["n"].sum()
    out_shares = out.groupby("menu_days")["n"].sum()
    return {
        "menu_days": list(MENU_DAYS),
        "probabilities": [float(p) for p in probabilities],
        "spread_elasticity": elasticity,
        "ci95": {
            "probabilities": [[float(lo), float(hi)] for lo, hi in zip(*np.quantile(draw_p, [0.025, 0.975], axis=0))],
            "spread_elasticity": elasticity_ci,
        },
        "identified": bool(_excludes_zero(elasticity_ci) and _sign_stable(half_estimates + [elasticity])),
        "form": "P(days_k) proportional to probabilities_k * exp(spread_elasticity * spread * days_k / 365)",
        "diagnostics": {
            "probabilities_at_mean_spread": [float(p) for p in duration_probabilities(constants, elasticity, mean_spread)],
            "starts": main.events, "weeks": main.weeks, "se": {n: float(v) for n, v in zip(DURATION_NAMES, main.fit.se)},
            "coefficients": {n: float(v) for n, v in zip(DURATION_NAMES, main.fit.coef)},
            "observed_shares_fit": {int(k): float(v / fit_shares.sum()) for k, v in fit_shares.items()},
            "observed_shares_holdout": {int(k): float(v / out_shares.sum()) for k, v in out_shares.items()},
            "half_window_elasticity": half_estimates,
            "holdout": {
                "starts": int(y_out.sum()),
                "loglik": conditional_loglik(y_out, out[list(DURATION_NAMES)].to_numpy(float), g_out, main.fit.coef),
                "loglik_no_spread": conditional_loglik(y_out, out[list(DURATION_NAMES[:-1])].to_numpy(float), g_out, null.fit.coef),
            },
        },
    }


def fit_renewal(periods: pd.DataFrame, market: pd.DataFrame, fit_window: tuple[str, str], holdout_window: tuple[str, str], halves: list[tuple[str, str]]) -> dict[str, Any]:
    """Logit of renewal within 7 days on the spread at the cutoff before the period's end, clustered by end week."""
    spread = market.set_index("week_start_utc")["spread"]

    def rows(window):
        part = periods[in_window(periods["end_time"], window)]
        s = part["end_week"].map(spread).to_numpy(float)
        return part["renewed"].to_numpy(float), np.column_stack([np.ones(len(part)), s]), part["end_week"].to_numpy()

    def fit(window):
        y, X, g = rows(window)
        return _stats.logit(y, X, ("logit_probability", "spread_elasticity"), groups=g)

    main = fit(fit_window)
    y_fit, X_fit, g_fit = rows(fit_window)
    null = _stats.logit(y_fit, X_fit[:, :1], ("logit_probability",), groups=g_fit)
    y_out, X_out, _ = rows(holdout_window)
    half_estimates = [float(fit(window).coef[1]) for window in halves]
    table = main.table()
    elasticity_ci = table["spread_elasticity"]["ci95"]
    expit = lambda v: float(1.0 / (1.0 + np.exp(-v)))
    return {
        "probability": expit(main.coef[0]),
        "spread_elasticity": float(main.coef[1]),
        "ci95": {
            "probability": [expit(v) for v in table["logit_probability"]["ci95"]],
            "spread_elasticity": elasticity_ci,
        },
        "identified": bool(_excludes_zero(elasticity_ci) and _sign_stable(half_estimates + [main.coef[1]])),
        "form": "logit P(renew within 7 days of period end) = logit(probability) + spread_elasticity * spread",
        "diagnostics": {
            "probability_at_mean_spread": expit(main.coef[0] + main.coef[1] * float(X_fit[:, 1].mean())),
            "ended_periods": main.n, "renewed_share": float(y_fit.mean()), "se": {k: v["se"] for k, v in table.items()},
            "half_window_elasticity": half_estimates,
            "holdout": {
                "ended_periods": len(y_out), "renewed_share": float(y_out.mean()) if len(y_out) else float("nan"),
                "predicted_share": float(np.mean(1.0 / (1.0 + np.exp(-(X_out @ main.coef))))) if len(y_out) else float("nan"),
                "loglik": _stats.logit_loglik(y_out, X_out, main.coef),
                "loglik_no_spread": _stats.logit_loglik(y_out, X_out[:, :1], null.coef),
            },
        },
    }


def fit_exit(weekly: pd.DataFrame, fit_window: tuple[str, str], holdout_window: tuple[str, str]) -> dict[str, Any]:
    """Exits per active validator-day: Poisson with log exposure offset, Newey-West errors."""
    part = weekly[in_window(weekly["week_start_utc"], fit_window) & (weekly["active_validator_days"] > 0)]
    offset = np.log(part["active_validator_days"].to_numpy())
    main = _stats.poisson(part["exits"].to_numpy(), np.ones((len(part), 1)), ("log_base_per_day",), offset, hac_lags=HAC_LAGS)
    table = main.table()
    out = weekly[in_window(weekly["week_start_utc"], holdout_window) & (weekly["active_validator_days"] > 0)]
    rate = float(np.exp(main.coef[0]))
    ci = [float(np.exp(v)) for v in table["log_base_per_day"]["ci95"]]
    return {
        "base_per_day": rate,
        "ci95": {"base_per_day": ci},
        "identified": bool(ci[0] > 0),
        "form": "validators leaving per active validator per day = base_per_day (a period end with no new period within 7 days)",
        "diagnostics": {
            "weeks": main.n, "exits": float(part["exits"].sum()), "active_validator_days": float(part["active_validator_days"].sum()),
            "holdout": {
                "exits": float(out["exits"].sum()),
                "predicted": float(rate * out["active_validator_days"].sum()),
                "rate_per_day": float(out["exits"].sum() / out["active_validator_days"].sum()) if len(out) else float("nan"),
            },
        },
    }
