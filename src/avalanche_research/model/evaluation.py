"""Scoring a forecast from an origin against the validation protocol's naive benchmarks.

The protocol (test ``B4.1``) scores every forecast at 30, 90 and 180 days after an origin against three naive
benchmarks, each built only from data up to the origin:

* ``N1`` persistence: the value at the origin, held.
* ``N2`` drift: the origin value plus the mean daily change over the 180 days before the origin.
* ``N3`` reduced form: an AR(1) on weekly changes, fitted on the data before the origin and iterated from it.

The score is the mean absolute scaled error (Hyndman and Koehler, 2006): the absolute error divided by the mean
absolute one-day change before the origin. Two forecasts are compared with the Diebold-Mariano test (1995), with the
small-sample correction of Harvey, Leybourne and Newbold (1997) and a long-run variance over ``h - 1`` lags.

Distribution scores judge the spread of a forecast as well as its centre: the continuous ranked
probability score (CRPS, Gneiting and Raftery, 2007), the probability integral transform (PIT), central-interval
coverage and the interval score. Their benchmarks are distributions too: ``N1d`` and ``N2d`` dress ``N1`` and ``N2``
with the series' own past changes, and ``N4`` is a Gaussian local-level model (Harvey, 1989).

Every function takes a daily series indexed by date and reads nothing after the origin, except ``actual_at``, which
reads the realized value a forecast is scored against.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd
from scipy import optimize, stats

DRIFT_DAYS = 180
DRESS_DAYS = 730
FAIR_BELOW = 100


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


def _sorted(draws, weights) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(draws, dtype=float)
    if x.ndim != 1 or len(x) == 0 or not np.isfinite(x).all():
        raise ValueError("draws must be a non-empty one-dimensional array of finite values")
    w = np.full(len(x), 1 / len(x)) if weights is None else np.asarray(weights, dtype=float)
    if len(w) != len(x):
        raise ValueError("there must be one weight per draw")
    if (w < 0).any() or not math.isclose(w.sum(), 1.0, rel_tol=1e-9):
        raise ValueError("weights must be non-negative and sum to 1")
    x, w = x[w > 0], w[w > 0]
    order = np.argsort(x, kind="stable")
    return x[order], w[order]


def crps_ensemble(draws, actual: float, weights=None, fair: bool = False) -> float:
    """``E|X - y| - E|X - X'| / 2`` for the sample, by the sorted-sample identity.

    With weights ``w`` summing to 1, after sorting, ``E|X - X'| = 2 * sum(w_i * x_i * (C_{i-1} + C_i - 1))``, ``C`` the
    cumulative weight. ``fair`` divides the pair sum by ``m(m - 1)`` instead of ``m**2``, which removes the plain
    estimator's overstatement for small ensembles (Ferro, 2014). It needs equal weights.
    """
    if fair and weights is not None:
        raise ValueError("the fair estimator needs equal weights")
    x, w = _sorted(draws, weights)
    cumulative = np.cumsum(w)
    spread = 2 * float(np.sum(w * x * (cumulative - w + cumulative - 1)))
    if fair:
        m = len(x)
        if m < 2:
            raise ValueError("the fair estimator needs at least two draws")
        spread *= m / (m - 1)
    return float(np.sum(w * np.abs(x - actual))) - spread / 2


def crps_normal(mean: float, sd: float, actual: float) -> float:
    """The CRPS of a normal forecast: ``sd * (z * (2 Phi(z) - 1) + 2 phi(z) - 1 / sqrt(pi))``."""
    if not sd > 0:
        raise ValueError("the standard deviation must be positive")
    z = (actual - mean) / sd
    return float(sd * (z * (2 * stats.norm.cdf(z) - 1) + 2 * stats.norm.pdf(z) - 1 / math.sqrt(math.pi)))


def pit(draws, actual: float, weights=None) -> float:
    """The forecast's probability below the realized value, counting half of any probability exactly on it."""
    x, w = _sorted(draws, weights)
    return float(w[x < actual].sum() + w[x == actual].sum() / 2)


def central_interval(draws, level: float, weights=None) -> tuple[float, float]:
    """The central interval holding ``level`` of the forecast, by the linear quantile rule.

    Sorted draws sit at positions ``(C_i - C_1) / (1 - C_1)``, ``C`` the cumulative weight, which with equal weights is
    ``(i - 1) / (m - 1)``, NumPy's default rule. Like that rule, it is a rule on the draws as given, not on the
    distribution they describe: splitting one draw's weight across duplicates moves the positions and can change the
    interval. The pooled forecasts here pass each sample's draws as drawn.
    """
    if not 0 < level < 1:
        raise ValueError("the level must be between 0 and 1")
    x, w = _sorted(draws, weights)
    if len(x) == 1:
        return float(x[0]), float(x[0])
    cumulative = np.cumsum(w)
    positions = (cumulative - cumulative[0]) / (1 - cumulative[0])
    tail = (1 - level) / 2
    lower, upper = np.interp([tail, 1 - tail], positions, x)
    return float(lower), float(upper)


def interval_score(lower: float, upper: float, actual: float, level: float) -> float:
    """The width plus ``2 / alpha`` times any miss, ``alpha = 1 - level`` (Gneiting and Raftery, 2007)."""
    alpha = 1 - level
    return (upper - lower) + (2 / alpha) * max(lower - actual, 0.0) + (2 / alpha) * max(actual - upper, 0.0)


def dressed(series: pd.Series, origin, horizon_days: int, rule: str = "N1", window_days: int = DRESS_DAYS) -> np.ndarray:
    """``N1d`` or ``N2d``: a benchmark spread by every ``horizon_days`` change that ends by the origin.

    ``N1d`` is the origin value plus each change in the ``window_days`` before the origin. ``N2d`` is ``N2`` plus each
    change less their mean, so its centre stays on the drift forecast.
    """
    known = _before(series, origin)
    start = known.index[-1] - pd.Timedelta(int(window_days), unit="D")
    daily = known.loc[known.index >= start].asfreq("D")
    changes = (daily.shift(-int(horizon_days)) - daily).dropna().to_numpy(dtype=float)
    if len(changes) == 0:
        raise ValueError(f"no {horizon_days}-day change ends by the origin")
    if rule == "N1":
        return float(known.iloc[-1]) + changes
    if rule == "N2":
        return drift(series, origin, horizon_days) + changes - changes.mean()
    raise ValueError(f"unknown dressed rule {rule!r}")


def _local_level_filter(y: np.ndarray, var_measurement: float, var_level: float) -> tuple[float, float, float]:
    """Log-likelihood, filtered level and its variance, conditioning on the first value."""
    level, variance, loglik = y[0], var_measurement, 0.0
    for value in y[1:]:
        variance += var_level
        total = variance + var_measurement
        surprise = value - level
        loglik -= 0.5 * (math.log(2 * math.pi * total) + surprise * surprise / total)
        gain = variance / total
        level += gain * surprise
        variance *= 1 - gain
    return loglik, level, variance


def fit_local_level(values) -> dict[str, float]:
    """Maximum-likelihood fit of ``y[t] = mu[t] + eps``, ``mu[t+1] = mu[t] + eta``.

    The two log variances are found with ``scipy.optimize`` on the series divided by the standard deviation of its
    one-day changes, which puts both variances near 1 for a series that wanders, and are reported in the series' own
    units with the last filtered level and its variance.
    """
    y = np.asarray(values, dtype=float)
    if len(y) < 3 or not np.isfinite(y).all():
        raise ValueError("at least three finite values are needed")
    unit = float(np.std(np.diff(y))) or 1.0
    z = y / unit
    result = optimize.minimize(lambda p: -_local_level_filter(z, math.exp(p[0]), math.exp(p[1]))[0],
                               x0=[math.log(0.5), math.log(0.5)], method="Nelder-Mead",
                               options={"xatol": 1e-6, "fatol": 1e-9, "maxiter": 2_000})
    var_measurement, var_level = math.exp(result.x[0]), math.exp(result.x[1])
    _, level, variance = _local_level_filter(z, var_measurement, var_level)
    return {"var_measurement": var_measurement * unit**2, "var_level": var_level * unit**2,
            "level": level * unit, "level_variance": variance * unit**2}


def local_level(series: pd.Series, origin, horizon_days: int) -> tuple[float, float]:
    """``N4``: the mean and standard deviation of the local-level forecast fitted on every day to the origin."""
    fit = fit_local_level(_before(series, origin).to_numpy(dtype=float))
    variance = fit["level_variance"] + horizon_days * fit["var_level"] + fit["var_measurement"]
    return float(fit["level"]), float(math.sqrt(variance))


def distribution_scores(draws, actual: float, scale: float, weights=None) -> dict[str, float]:
    """CRPS, PIT, 50% and 80% coverage, the 80% interval score and width, with CRPS, score and width over ``scale``.

    From two to ``FAIR_BELOW`` equally weighted draws the CRPS uses the fair estimator. One draw scores as a point
    forecast, and no draws is a ``ValueError``.
    """
    fair = weights is None and 2 <= len(draws) < FAIR_BELOW
    lower50, upper50 = central_interval(draws, 0.5, weights)
    lower80, upper80 = central_interval(draws, 0.8, weights)
    return {"crps": crps_ensemble(draws, actual, weights, fair=fair) / scale,
            "pit": pit(draws, actual, weights),
            "in50": float(lower50 <= actual <= upper50),
            "in80": float(lower80 <= actual <= upper80),
            "is80": interval_score(lower80, upper80, actual, 0.8) / scale,
            "width80": (upper80 - lower80) / scale}


def dm_horizon(horizon_days: int, origin_dates=None, origin_spacing_days: int = 90) -> int:
    """The Diebold-Mariano horizon: one plus the most later origins that fall inside one forecast's window.

    Forecasts whose windows overlap have correlated errors, and the test's long-run variance covers ``horizon - 1``
    lags. With ``origin_dates`` the overlap is counted from the dates, since an upgrade origin can fall a week from a
    quarter start. Without them the origins are taken as ``origin_spacing_days`` apart.
    """
    if origin_dates is None:
        return math.ceil(horizon_days / origin_spacing_days)
    days = np.sort(pd.to_datetime(pd.Series(origin_dates)).to_numpy())
    window = np.timedelta64(int(horizon_days), "D")
    inside = [int(np.sum((days[i + 1:] - day) < window)) for i, day in enumerate(days)]
    return 1 + max(inside, default=0)


def chronological(origins, dates) -> list:
    """``origins`` sorted by their dates in ``dates``, a mapping or Series from origin to date, for lagged tests."""
    return sorted(origins, key=lambda origin: pd.Timestamp(dates[origin]))
