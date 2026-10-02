"""The validation protocol's benchmarks and scores, on series with known answers."""

import numpy as np
import pandas as pd
import pytest

from avalanche_research.model import evaluation as ev

DAYS = pd.date_range("2024-01-01", periods=400, freq="D")
ORIGIN = DAYS[300]


def line(slope=2.0, start=100.0):
    return pd.Series(start + slope * np.arange(len(DAYS)), index=DAYS)


def test_persistence_holds_the_origin_value():
    assert ev.persistence(line(), ORIGIN, 90) == 100.0 + 2.0 * 300


def test_drift_extends_the_180_day_trend_exactly_on_a_line():
    series = line()
    assert ev.drift(series, ORIGIN, 90) == pytest.approx(ev.actual_at(series, ORIGIN, 90))


def test_reduced_form_follows_a_constant_weekly_change():
    series = line() + pd.Series(np.where(np.arange(len(DAYS)) % 2, 0.01, -0.01), index=DAYS)
    assert ev.reduced_form(series, ORIGIN, 28) == pytest.approx(ev.actual_at(line(), ORIGIN, 28), abs=0.5)


def test_benchmarks_read_nothing_after_the_origin():
    series = line()
    changed = series.copy()
    changed.loc[changed.index > ORIGIN] = -1e9
    assert ev.benchmarks(series, ORIGIN).equals(ev.benchmarks(changed, ORIGIN))


def test_an_origin_without_a_value_is_refused():
    with pytest.raises(ValueError):
        ev.persistence(line(), DAYS[-1] + pd.Timedelta(1, unit="D"), 30)


def test_scaled_error_is_in_units_of_the_mean_daily_change():
    series = line(slope=2.0)
    scale = ev.mase_scale(series, ORIGIN)
    assert scale == pytest.approx(2.0)
    assert ev.scaled_error(110.0, 100.0, scale) == pytest.approx(5.0)


def test_diebold_mariano_finds_a_clearly_better_forecast():
    rng = np.random.default_rng(0)
    worse = rng.uniform(1.0, 2.0, 40)
    better = worse - 0.5 + rng.normal(0, 0.05, 40)
    result = ev.diebold_mariano(better, worse, horizon=1)
    assert result["statistic"] < 0
    assert result["p_less"] < 0.001


def test_diebold_mariano_is_symmetric_and_not_significant_for_equal_forecasts():
    rng = np.random.default_rng(1)
    a, b = rng.uniform(1, 2, 60), rng.uniform(1, 2, 60)
    ab, ba = ev.diebold_mariano(a, b, horizon=3), ev.diebold_mariano(b, a, horizon=3)
    assert ab["statistic"] == pytest.approx(-ba["statistic"])
    assert ab["p_two_sided"] > 0.05


def test_diebold_mariano_correction_matches_the_published_factor():
    rng = np.random.default_rng(2)
    a, b = rng.uniform(1, 2, 20), rng.uniform(0.5, 1.5, 20)
    n, h = 20, 2
    plain = ev.diebold_mariano(a, b, horizon=h)["statistic"] / np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    d = a - b
    centred = d - d.mean()
    gamma = [centred @ centred / n] + [centred[k:] @ centred[:-k] / n for k in range(1, h)]
    assert plain == pytest.approx(d.mean() / np.sqrt((gamma[0] + 2 * sum(gamma[1:])) / n))


def test_diebold_mariano_keeps_the_variance_positive_in_short_samples():
    a = np.array([1.0, 3.0, 1.0, 3.0, 1.0, 3.0, 1.0, 3.0])
    b = np.full(8, 1.5)
    result = ev.diebold_mariano(a, b, horizon=2)
    assert result["variance"] == "bartlett"
    assert np.isfinite(result["statistic"])
