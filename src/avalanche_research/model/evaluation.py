"""Scoring a forecast from an origin against the validation protocol's naive benchmarks.

The protocol (test ``B4.1``) scores every forecast at 30, 90 and 180 days after an origin against three naive
benchmarks, each built only from data up to the origin:

* ``N1`` persistence: the value at the origin, held.
* ``N2`` drift: the origin value plus the mean daily change over the 180 days before the origin.
* ``N3`` reduced form: an AR(1) on weekly changes, fitted on the data before the origin and iterated from it.

The score is the mean absolute scaled error (Hyndman and Koehler, 2006): the absolute error divided by the mean
absolute one-day change before the origin. Two forecasts are compared with the Diebold-Mariano test (1995), with the
small-sample correction of Harvey, Leybourne and Newbold (1997) and a long-run variance over ``h - 1`` lags.

Every function takes a daily series indexed by date and reads nothing after the origin, except ``actual_at``, which
reads the realized value a forecast is scored against.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd
from scipy import stats

DRIFT_DAYS = 180


def _before(series: pd.Series, origin) -> pd.Series:
    origin = pd.Timestamp(origin)
    known = series.loc[series.index <= origin].dropna()
    if known.empty or known.index[-1] != origin:
        raise ValueError(f"the series has no value at the origin {origin.date()}")
    return known


def actual_at(series: pd.Series, origin, horizon_days: int) -> float:
    """The realized value ``horizon_days`` after the origin."""
    when = pd.Timestamp(origin) + pd.Timedelta(int(horizon_days), unit="D")
    if when not in series.index or pd.isna(series.loc[when]):
        raise ValueError(f"no realized value on {when.date()}")
    return float(series.loc[when])


def persistence(series: pd.Series, origin, horizon_days: int) -> float:
    """``N1``: the value at the origin."""
    return float(_before(series, origin).iloc[-1])


def drift(series: pd.Series, origin, horizon_days: int, window_days: int = DRIFT_DAYS) -> float:
    """``N2``: the origin value plus ``horizon_days`` times the mean daily change over ``window_days`` before it."""
    known = _before(series, origin)
    start = known.index[-1] - pd.Timedelta(int(window_days), unit="D")
    if start not in known.index:
        raise ValueError(f"no value {window_days} days before the origin")
    daily_change = (known.iloc[-1] - known.loc[start]) / window_days
    return float(known.iloc[-1] + horizon_days * daily_change)


def reduced_form(series: pd.Series, origin, horizon_days: int) -> float:
    """``N3``: an AR(1) on weekly changes, fitted by least squares on weeks ending at the origin, then iterated.

    Weeks are counted back from the origin, so the last weekly value is the origin's own. A horizon that is not a whole
    number of weeks is read by linear interpolation along the iterated weekly path.
    """
    known = _before(series, origin)
    weekly = known.loc[known.index[-1] - pd.to_timedelta(np.arange(0, len(known), 7)[::-1], unit="D")]
    weekly = weekly.dropna()
    changes = weekly.diff().dropna().to_numpy()
    if len(changes) < 3:
        raise ValueError("fewer than three weekly changes before the origin")
    x, y = changes[:-1], changes[1:]
    if np.ptp(x) == 0:
        slope, intercept = 0.0, float(y.mean())
    else:
        slope, intercept = np.polyfit(x, y, 1)
    path, level, change = [0.0], float(weekly.iloc[-1]), float(changes[-1])
    weeks = math.ceil(horizon_days / 7)
    for _ in range(weeks):
        change = intercept + slope * change
        level += change
        path.append(level - float(weekly.iloc[-1]))
    step = np.interp(horizon_days / 7, np.arange(weeks + 1), path)
    return float(weekly.iloc[-1] + step)


BENCHMARKS = {"N1": persistence, "N2": drift, "N3": reduced_form}


def benchmarks(series: pd.Series, origin, horizons: Iterable[int] = (30, 90, 180)) -> pd.DataFrame:
    """Each benchmark's forecast at each horizon, one row per benchmark and horizon."""
    rows = [{"benchmark": name, "horizon_days": h, "forecast": rule(series, origin, h)}
            for name, rule in BENCHMARKS.items() for h in horizons]
    return pd.DataFrame(rows)


def mase_scale(series: pd.Series, origin) -> float:
    """The mean absolute one-day change up to the origin, the denominator of the scaled error."""
    known = _before(series, origin)
    daily = known.asfreq("D")
    scale = float(daily.diff().abs().mean())
    if not scale > 0:
        raise ValueError("the series does not change before the origin, so errors cannot be scaled")
    return scale


def scaled_error(forecast: float, actual: float, scale: float) -> float:
    """The absolute error in units of the mean one-day change before the origin."""
    return abs(forecast - actual) / scale


def diebold_mariano(loss_a: Iterable[float], loss_b: Iterable[float], horizon: int = 1) -> dict[str, float]:
    """Whether forecast A has lower expected loss than forecast B.

    ``loss_a`` and ``loss_b`` are paired losses, for example scaled errors at one horizon across origins. The
    statistic uses a long-run variance with ``horizon - 1`` autocovariances and the Harvey, Leybourne and Newbold
    correction, and is read against Student's t with ``n - 1`` degrees of freedom. The truncated sum Diebold and
    Mariano use can be negative in short samples. Then the autocovariances get Bartlett weights (Newey and West,
    1987), which keep the variance positive, and ``variance`` says which was used. ``p_less`` is the one-sided p-value
    for A better than B, ``p_two_sided`` the two-sided one.
    """
    d = np.asarray(list(loss_a), dtype=float) - np.asarray(list(loss_b), dtype=float)
    n = len(d)
    if n < 3:
        raise ValueError("at least three paired losses are needed")
    if horizon < 1 or horizon >= n:
        raise ValueError("the horizon must be at least 1 and below the number of pairs")
    mean = d.mean()
    centred = d - mean
    gamma = [float(centred @ centred) / n] + [float(centred[k:] @ centred[:-k]) / n for k in range(1, horizon)]
    variance, kind = (gamma[0] + 2 * sum(gamma[1:])) / n, "truncated"
    if variance <= 0:
        weights = [1 - k / horizon for k in range(1, horizon)]
        variance, kind = (gamma[0] + 2 * sum(w * g for w, g in zip(weights, gamma[1:]))) / n, "bartlett"
    if variance <= 0:
        raise ValueError("the loss differences have no variance")
    correction = math.sqrt((n + 1 - 2 * horizon + horizon * (horizon - 1) / n) / n)
    statistic = correction * mean / math.sqrt(variance)
    return {"statistic": statistic, "mean_difference": float(mean), "n": n, "variance": kind,
            "p_less": float(stats.t.cdf(statistic, df=n - 1)),
            "p_two_sided": float(2 * stats.t.sf(abs(statistic), df=n - 1))}
