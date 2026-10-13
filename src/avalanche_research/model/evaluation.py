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
import re
from collections.abc import Iterable, Mapping
from datetime import date

import numpy as np
import pandas as pd
from scipy import optimize, stats

from avalanche_research.model.replay import LOCKBOX_FIRST_DAY

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


ADOPTION_MARGIN = 2.2
"""The smallest mean 90-day difference in scaled CRPS that the scored origins can detect, fixed before any score."""

ADOPTION_CELL_ALPHA = 0.05 / 6
"""The one-sided test level at which one cell clearly worse rejects a challenger: 0.05 shared by six cells."""

ADOPTION_PRIMARY = ("active_validator_stake_navax", 90)
"""The cell whose mean worsening must stay below the margin: validator stake at 90 days."""

ADOPTION_CELLS = tuple((variable, horizon) for variable in ("active_validators", "active_validator_stake_navax")
                       for horizon in (30, 90, 180))
"""The cells a challenger may not be clearly worse in: two variables at three horizons."""

ADOPTION_COLUMNS = ("date", "variable", "horizon", "challenger", "incumbent")


def _real(column: pd.Series, name: str) -> np.ndarray:
    """A column of real numbers as floats. Other types, and integers too large to hold exactly as floats, are refused,
    since converting them would lose information."""
    dtype = column.dtype
    if pd.api.types.is_bool_dtype(dtype) or not (pd.api.types.is_integer_dtype(dtype)
                                                 or pd.api.types.is_float_dtype(dtype)):
        raise ValueError(f"{name} must hold real numbers, not {dtype}")
    if pd.api.types.is_integer_dtype(dtype) and ((column > 2**53) | (column < -(2**53))).any():
        raise ValueError(f"{name} holds integers too large to compare exactly as floats")
    return column.to_numpy(float)


def _flag(block, name: str):
    """A test result as True, False or None. NumPy booleans count as booleans, and any other value is refused."""
    value = block.get(name)
    if value is None or isinstance(value, (bool, np.bool_)):
        return None if value is None else bool(value)
    raise ValueError(f"{name} must be True, False or None, not {value!r}")


# Text names a day only as YYYY-MM-DD, or as that day's UTC midnight. No other text form is read.
_ISO_DAY = re.compile(r"(\d{4}-\d{2}-\d{2})(?:T00:00:00(?:\.0+)?(?:Z|\+00:00)?)?")


def _utc_days(values, what: str) -> list[pd.Timestamp]:
    """Each value as a naive UTC midnight. A date or datetime is read on its own, a zoned one in UTC, and text only in the
    forms ``_ISO_DAY`` allows; any other type or text, or any instant that is not a UTC midnight, is refused, so an
    origin is always one calendar day."""
    days = []
    for value in values:
        if isinstance(value, (bool, int, float, np.integer, np.floating)) or not isinstance(value, (str, date, pd.Timestamp, np.datetime64)):
            raise ValueError(f"{what} must be a date, a datetime or ISO text, not {value!r}")  # noqa: TRY004, one error type for every bad input
        if isinstance(value, np.datetime64) and np.datetime_data(value)[0] in ("ps", "fs", "as"):
            # Units finer than a nanosecond do not fit a timestamp and would be truncated or wrapped into another day.
            raise ValueError(f"{what} must be given in nanoseconds or coarser, not {value!r}")
        if isinstance(value, str):
            match = _ISO_DAY.fullmatch(value)
            if match is None:
                raise ValueError(f"{what} given as text must be YYYY-MM-DD or that day's UTC midnight, not {value!r}")
            try:
                value = date.fromisoformat(match.group(1))
            except ValueError as error:
                raise ValueError(f"{what} given as text must be a real calendar day, not {value!r}") from error
        try:
            day = pd.Timestamp(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{what} must be a date, a datetime or ISO text, not {value!r}") from error
        if pd.isna(day):
            raise ValueError(f"{what} must be a date, a datetime or ISO text, not {value!r}")
        if day.tzinfo is not None:
            day = day.tz_convert("UTC").tz_localize(None)
        if day != day.normalize():
            raise ValueError(f"{what} must be a UTC midnight, one calendar day, not {value!r}")
        days.append(day)
    return days


def adoption_verdict(block, system: pd.DataFrame, origins) -> dict[str, object]:
    """Whether a challenger block replaces the incumbent, by a rule fixed before either is scored.

    The rule's margin, test level and cells are the module constants ``ADOPTION_MARGIN``, ``ADOPTION_CELL_ALPHA``,
    ``ADOPTION_PRIMARY`` and ``ADOPTION_CELLS``, not arguments, so no caller can loosen it. They change only in the
    code, before any challenger is scored.

    ``block`` holds the block's own tests on held-out events: ``event_test`` (lower pooled log score, a paired
    bootstrap p below 0.05, lower at 14 or more of 19 origins), ``calibration`` (calibration error at most 0.02) and
    ``origin_available`` (no worse once inputs unknown at the origin are integrated out). Each is True or False.
    ``event_test`` is None when the block has no held-out event test, and ``origin_available`` is None when the block
    reads no such input.

    ``system`` has one row per origin, variable and horizon, with the origin's ``date`` and the ``challenger`` and
    ``incumbent`` scaled CRPS from the same seeds and parameter draws. The challenger must worsen the primary cell by
    less than the margin on average over origins, and no cell may be worse by a one-sided Diebold-Mariano test, on
    origins in date order, with p below the test level. ``block`` must be a mapping and ``system`` a DataFrame with
    every column. Every cell must be present, every score finite, horizons whole days and every row labelled and dated,
    or a ValueError is raised. ``origins`` lists every registered origin's date, given by the caller and not read from
    ``system``. Each cell must hold one row for every registered origin whose horizon ends before the held-back period
    and for no other date, at least three, so a longer horizon may hold fewer origins but no origin can be left out of
    one cell or of all. Each date may be a date or a datetime, read in UTC when zoned, or text
    as YYYY-MM-DD or that day's UTC midnight (T00:00:00, optionally with zero fractions and Z or +00:00), and must
    be a UTC midnight.

    The verdict is "reject" when any test fails, "no event test" when none fails but the block has no event test, and
    "adopt" otherwise. The reasons name every failure, and "no event test" first when it applies. The system figures
    are returned in every case, so a rejected challenger's forecast score is still on record.
    """
    if not isinstance(block, Mapping):
        raise ValueError("block must be a mapping of test results")  # noqa: TRY004, one error type for every bad input
    if not isinstance(system, pd.DataFrame) or set(ADOPTION_COLUMNS) - set(system.columns):
        raise ValueError(f"system must be a DataFrame with the columns {', '.join(ADOPTION_COLUMNS)}")
    event_test, calibration, origin_available = (_flag(block, name) for name in
                                                 ("event_test", "calibration", "origin_available"))
    reasons = ["no event test"] if event_test is None else []
    if event_test is False:
        reasons.append("event test")
    if calibration is False or (event_test is not None and calibration is not True):
        reasons.append("calibration")
    if origin_available is False:
        reasons.append("origin-available")

    horizons = _real(system["horizon"], "horizon")
    if not (np.isfinite(horizons).all() and (horizons == np.round(horizons)).all() and (horizons > 0).all()):
        raise ValueError("every horizon must be a whole, positive number of days")
    if not system["variable"].map(lambda value: isinstance(value, str)).all():
        raise ValueError("every row needs its variable, as text, and its origin date")
    system = system.assign(date=_utc_days(system["date"], "every row's origin date"), horizon=horizons.astype(int))
    if system.duplicated(["variable", "horizon", "date"]).any():
        raise ValueError("each cell must hold one row per origin date")
    scores = np.column_stack([_real(system[name], name) for name in ("challenger", "incumbent")])
    if not np.isfinite(scores).all():
        raise ValueError("every challenger and incumbent score must be finite")
    required = set(ADOPTION_CELLS) | {ADOPTION_PRIMARY}
    present = {(variable, int(horizon)) for variable, horizon in zip(system["variable"], system["horizon"])}
    if required - present:
        raise ValueError(f"the system table has no rows for {sorted(required - present)}")

    # A cell holds every registered origin whose horizon ends before the held-back period and no other date, as the
    # scoring scripts produce them, so a longer horizon may hold fewer origins but none can be left out or added.
    if isinstance(origins, (str, bytes)) or not isinstance(origins, Iterable):
        raise ValueError("origins must be the registered origins' dates")  # noqa: TRY004, one error type for every bad input
    every = _utc_days(list(origins), "each registered origin")
    if len(set(every)) != len(every):
        raise ValueError("origins must be distinct dates")
    last = pd.Timestamp(LOCKBOX_FIRST_DAY) - pd.Timedelta(1, unit="D")
    for (variable, horizon), rows in system.groupby(["variable", "horizon"], sort=True):
        expected = frozenset(day for day in every if day + pd.Timedelta(int(horizon), unit="D") <= last)
        if frozenset(rows["date"]) != expected or len(expected) < 3:
            raise ValueError(f"the cell {variable} {horizon} must hold every origin whose horizon ends before the "
                             "held-back period, and at least three")

    scored = {}
    for (variable, horizon), rows in system.groupby(["variable", "horizon"], sort=True):
        rows = rows.sort_values("date", kind="stable")
        difference = rows["challenger"].to_numpy(float) - rows["incumbent"].to_numpy(float)
        if not np.isfinite(difference).all():
            raise ValueError("a challenger and incumbent score differ by more than a float can hold")
        size = np.abs(difference).max()
        if np.ptp(difference) == 0:
            p_worse = 0.0 if difference[0] > 0 else 1.0
        else:
            # The statistic does not depend on the scale of the differences, so they are scaled to at most 1 in size
            # first, which keeps very large scores from overflowing the variance.
            lags = dm_horizon(int(horizon), rows["date"])
            p_worse = diebold_mariano(-difference / size, np.zeros(len(difference)), horizon=lags)["p_less"]
        mean = float(np.mean(difference / size) * size) if size > 0 else 0.0
        scored[(variable, int(horizon))] = {"mean_difference": mean, "p_worse": float(p_worse)}

    primary_mean = scored[ADOPTION_PRIMARY]["mean_difference"]
    if primary_mean >= ADOPTION_MARGIN:
        reasons.append("system")
    worst = min(scored, key=lambda cell: scored[cell]["p_worse"])
    reasons += [f"cell {variable} {horizon}" for (variable, horizon), cell in scored.items()
                if cell["p_worse"] < ADOPTION_CELL_ALPHA]

    if [reason for reason in reasons if reason != "no event test"]:
        verdict = "reject"
    else:
        verdict = "no event test" if event_test is None else "adopt"
    return {"verdict": verdict, "reasons": reasons, "primary_mean_difference": primary_mean,
            "worst_cell": worst, "worst_cell_p": scored[worst]["p_worse"], "cells": scored}
