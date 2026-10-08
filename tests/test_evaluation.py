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


# Distribution scores, written before the functions.


def test_ensemble_crps_of_many_normal_draws_matches_the_closed_form():
    """CRPS of 200,000 normal draws matches the closed form."""
    draws = np.random.default_rng(1).normal(size=200_000)
    for y in (0.0, 0.5, 2.0):
        assert ev.crps_ensemble(draws, y) == pytest.approx(ev.crps_normal(0.0, 1.0, y), abs=0.005)


def test_identical_draws_score_their_absolute_error():
    """Draws that all equal one value score its absolute error."""
    assert ev.crps_ensemble(np.full(50, 3.0), 5.5) == pytest.approx(2.5)


def test_the_fair_estimator_removes_the_small_ensemble_bias():
    """Twenty draws: the plain estimator overstates, the fair one does not."""
    sets = np.random.default_rng(2).normal(size=(2_000, 20))
    closed = ev.crps_normal(0.0, 1.0, 0.5)
    plain = np.mean([ev.crps_ensemble(d, 0.5) for d in sets])
    fair = np.mean([ev.crps_ensemble(d, 0.5, fair=True) for d in sets])
    assert abs(fair - closed) < 0.01 and abs(plain - closed) > 0.01


def test_weighted_crps_reduces_to_the_plain_one_and_matches_a_two_point_mixture():
    """Equal weights reproduce the plain CRPS, and a two-point mixture matches its closed form."""
    draws = np.random.default_rng(3).normal(size=500)
    assert ev.crps_ensemble(draws, 0.3, weights=np.full(500, 1 / 500)) == pytest.approx(ev.crps_ensemble(draws, 0.3))
    a, b, p, y = 1.0, 4.0, 0.3, 2.0
    closed = p * abs(a - y) + (1 - p) * abs(b - y) - p * (1 - p) * abs(a - b)
    assert ev.crps_ensemble([b, a], y, weights=[1 - p, p]) == pytest.approx(closed)
    with pytest.raises(ValueError):
        ev.crps_ensemble([a, b], y, weights=[p, 1 - p], fair=True)


def test_pit_is_the_share_below_plus_half_the_share_equal():
    """PIT is 0 below every draw, 1 above, and counts half of a tie."""
    draws = [1.0, 2.0, 3.0, 4.0]
    assert ev.pit(draws, 0.5) == 0.0 and ev.pit(draws, 9.0) == 1.0
    assert ev.pit(draws, 2.0) == pytest.approx(0.25 + 0.125)
    assert ev.pit([5.0], 5.0) == 0.5
    assert ev.pit(draws, 2.5, weights=[0.7, 0.1, 0.1, 0.1]) == pytest.approx(0.8)


def test_the_central_interval_follows_the_linear_quantile_rule():
    draws = np.random.default_rng(4).normal(size=301)
    assert ev.central_interval(draws, 0.8) == pytest.approx(tuple(np.quantile(draws, [0.1, 0.9])))
    assert ev.central_interval(draws, 0.8, weights=np.full(301, 1 / 301)) == pytest.approx(tuple(np.quantile(draws, [0.1, 0.9])))


def test_the_interval_score_is_the_width_plus_the_penalised_miss():
    """Inside the interval the score is its width. Outside it adds 2 / alpha times the miss."""
    assert ev.interval_score(2.0, 6.0, 4.0, 0.8) == pytest.approx(4.0)
    assert ev.interval_score(2.0, 6.0, 7.0, 0.8) == pytest.approx(4.0 + 10.0 * 1.0)
    assert ev.interval_score(2.0, 6.0, 0.5, 0.8) == pytest.approx(4.0 + 10.0 * 1.5)


def test_dressed_and_local_level_read_nothing_after_the_origin():
    """As test_benchmarks_read_nothing_after_the_origin does for N1 to N3."""
    series = line() + pd.Series(np.random.default_rng(5).normal(0, 3, len(DAYS)), index=DAYS)
    changed = series.copy()
    changed.loc[changed.index > ORIGIN] = -1e9
    for rule in ("N1", "N2"):
        assert ev.dressed(series, ORIGIN, 30, rule).tolist() == ev.dressed(changed, ORIGIN, 30, rule).tolist()
    assert ev.local_level(series, ORIGIN, 90) == ev.local_level(changed, ORIGIN, 90)


def test_the_dressed_samples_are_the_past_changes_around_the_benchmark():
    series = line()
    n1d = ev.dressed(series, ORIGIN, 30, "N1", window_days=100)
    assert len(n1d) == 71 and np.allclose(n1d, ev.persistence(series, ORIGIN, 30) + 60.0)
    assert np.allclose(ev.dressed(series, ORIGIN, 30, "N2", window_days=100), ev.drift(series, ORIGIN, 30))


def test_the_local_level_recovers_known_variances_and_reduces_to_persistence():
    """Known variances are recovered, and with no measurement noise the forecast is persistence."""
    rng = np.random.default_rng(6)
    days = pd.date_range("2015-01-01", periods=3_000, freq="D")
    level = 50.0 + np.cumsum(rng.normal(0, 2.0, len(days)))
    noisy = pd.Series(level + rng.normal(0, 3.0, len(days)), index=days)
    fit = ev.fit_local_level(noisy.to_numpy())
    assert fit["var_level"] == pytest.approx(4.0, rel=0.15)
    assert fit["var_measurement"] == pytest.approx(9.0, rel=0.15)
    walk = pd.Series(level, index=days)
    mean, sd = ev.local_level(walk, days[-1], 30)
    assert mean == pytest.approx(level[-1], abs=0.05) and sd == pytest.approx(2.0 * np.sqrt(30), rel=0.15)


def test_distribution_scores_scale_the_crps_and_interval_widths():
    draws = np.random.default_rng(7).normal(10.0, 2.0, size=1_000)
    scores = ev.distribution_scores(draws, 10.0, scale=2.0)
    assert set(scores) == {"crps", "pit", "in50", "in80", "is80", "width80"}
    assert scores["crps"] == pytest.approx(ev.crps_ensemble(draws, 10.0) / 2.0)
    assert scores["in50"] == scores["in80"] == 1.0
    assert scores["width80"] == pytest.approx(scores["is80"])


def test_the_diebold_mariano_horizon_counts_overlapping_quarterly_origins():
    """For quarterly origins, one at 30 and 90 days and two at 180."""
    assert [ev.dm_horizon(h) for h in (30, 90, 180)] == [1, 1, 2]


def test_the_diebold_mariano_horizon_counts_overlap_from_the_origin_dates():
    """Upgrade origins can fall a week from a quarter start, so overlap is counted from the dates."""
    dates = pd.to_datetime(["2024-01-01", "2024-03-06", "2024-04-01", "2024-07-01", "2024-10-01"])
    assert ev.dm_horizon(30, dates) == 2
    assert ev.dm_horizon(90, dates) == 2
    assert ev.dm_horizon(180, dates) == 3
    assert ev.dm_horizon(30, pd.to_datetime(["2024-01-01", "2024-04-01"])) == 1


def test_diebold_mariano_inputs_are_ordered_by_date():
    """Lagged autocovariances need losses in time order, so origins are sorted by date."""
    names = pd.Index(["Banff", "2022-07-01", "Cortina", "2023-01-01"])
    dates = pd.Series(pd.to_datetime(["2022-10-18", "2022-07-01", "2023-04-25", "2023-01-01"]), index=names)
    assert ev.chronological(names, dates) == ["2022-07-01", "Banff", "2023-01-01", "Cortina"]


def test_zero_weight_draws_are_ignored():
    """A draw with no weight changes no score, and a one-point distribution has a one-point interval."""
    assert ev.central_interval([3.0, 1.0, 5.0], 0.8, weights=[1.0, 0.0, 0.0]) == (3.0, 3.0)
    assert ev.crps_ensemble([3.0, 1.0, 5.0], 4.0, weights=[1.0, 0.0, 0.0]) == pytest.approx(1.0)
    assert ev.pit([3.0, 1.0, 5.0], 4.0, weights=[1.0, 0.0, 0.0]) == 1.0


def test_scores_refuse_empty_draws_and_accept_a_single_draw():
    """No draws is a ValueError, and one draw scores as a point forecast."""
    with pytest.raises(ValueError):
        ev.crps_ensemble([], 0.0)
    with pytest.raises(ValueError):
        ev.distribution_scores([], 0.0, scale=1.0)
    single = ev.distribution_scores([3.0], 5.0, scale=1.0)
    assert single["crps"] == pytest.approx(2.0) and single["width80"] == 0.0 and single["in80"] == 0.0


ADOPTION_ORIGINS = pd.date_range("2021-01-01", periods=19, freq="QS")
PASSED = {"event_test": True, "calibration": True, "origin_available": True}


def _system(worse_by=None, wobble: float = 2.0) -> pd.DataFrame:
    """Scaled CRPS for an incumbent and a challenger at 19 quarterly origins, six cells. ``worse_by`` maps a cell to
    the challenger's mean worsening there. The spread around it sums to zero, so the mean is exact."""
    worse_by = worse_by or {}
    spread = np.sin(np.arange(19) * 2.3)
    spread -= spread.mean()
    rows = []
    for variable in ("active_validators", "active_validator_stake_navax"):
        for horizon in (30, 90, 180):
            incumbent = 5.0 + np.cos(np.arange(19) * 0.7)
            challenger = incumbent + worse_by.get((variable, horizon), 0.0) + wobble * spread
            rows += [{"origin": f"o{i}", "date": ADOPTION_ORIGINS[i], "variable": variable, "horizon": horizon,
                      "incumbent": incumbent[i], "challenger": challenger[i]} for i in range(19)]
    return pd.DataFrame(rows)


def test_adoption_accepts_a_passing_block_within_the_margin():
    """A block that passes its event tests and worsens 90-day stake by 1.0 scaled unit, under the 2.2 margin, is adopted.
    The spread across origins, about 3.5 units, is near the measured one that makes 2.2 the smallest detectable mean."""
    verdict = ev.adoption_verdict(PASSED, _system({("active_validator_stake_navax", 90): 1.0}, wobble=5.0))
    assert verdict["verdict"] == "adopt" and verdict["reasons"] == []
    assert verdict["primary_mean_difference"] == pytest.approx(1.0)


def test_adoption_rejects_a_worsening_beyond_the_margin():
    """A mean worsening of 3.0 on 90-day stake is past the margin, so the system clause rejects."""
    verdict = ev.adoption_verdict(PASSED, _system({("active_validator_stake_navax", 90): 3.0}, wobble=8.0))
    assert verdict["verdict"] == "reject" and verdict["reasons"] == ["system"]


def test_adoption_never_rests_on_the_system_score_alone():
    """A block that fails its event test is rejected however much the forecast improves."""
    block = dict(PASSED, event_test=False)
    verdict = ev.adoption_verdict(block, _system({("active_validator_stake_navax", 90): -5.0}))
    assert verdict["verdict"] == "reject" and verdict["reasons"] == ["event test"]


def test_adoption_rejects_one_clearly_worse_cell():
    """One cell worse with a one-sided p near 0.001 or below rejects, even with the primary cell unchanged."""
    verdict = ev.adoption_verdict(PASSED, _system({("active_validators", 30): 0.5}, wobble=0.1))
    assert verdict["verdict"] == "reject" and verdict["reasons"] == ["cell active_validators 30"]
    assert verdict["worst_cell"] == ("active_validators", 30) and verdict["worst_cell_p"] < 0.001


def test_adoption_needs_an_event_test():
    """A block with no held-out event test cannot be adopted, and its system score is still reported."""
    block = {"event_test": None, "calibration": None, "origin_available": None}
    verdict = ev.adoption_verdict(block, _system({("active_validator_stake_navax", 90): -1.0}))
    assert verdict["verdict"] == "no event test"
    assert verdict["primary_mean_difference"] == pytest.approx(-1.0)


def test_adoption_does_not_depend_on_row_order():
    """The paired test runs on origins in date order, so shuffled rows give the same verdict and p-values."""
    system = _system({("active_validators", 180): 0.4}, wobble=0.5)
    shuffled = system.sample(frac=1.0, random_state=3).reset_index(drop=True)
    assert ev.adoption_verdict(PASSED, shuffled) == ev.adoption_verdict(PASSED, system)


def test_adoption_refuses_scores_that_are_not_finite():
    """A missing or infinite score cannot pass the margin by comparing false, so it is refused."""
    system = _system()
    system.loc[0, "challenger"] = np.nan
    with pytest.raises(ValueError):
        ev.adoption_verdict(PASSED, system)


def test_adoption_reads_numpy_flags_and_refuses_other_types():
    """A failed test given as a NumPy boolean rejects as a Python one does. A flag that is not a boolean or None is
    refused."""
    system = _system()
    assert ev.adoption_verdict(dict(PASSED, event_test=np.bool_(False)), system)["reasons"] == ["event test"]
    assert ev.adoption_verdict(dict(PASSED, origin_available=np.bool_(False)), system)["reasons"] == ["origin-available"]
    with pytest.raises(ValueError):
        ev.adoption_verdict(dict(PASSED, calibration="yes"), system)


def test_adoption_needs_every_cell():
    """The rule tests six cells, two variables at three horizons, so a table missing one is refused."""
    system = _system()
    with pytest.raises(ValueError):
        ev.adoption_verdict(PASSED, system[~((system.variable == "active_validators") & (system.horizon == 180))])


def test_adoption_reads_dates_given_as_text():
    """Dates given as text are ordered in time, not as text, so the verdict matches the one from datetimes."""
    system = _system({("active_validators", 180): 0.4}, wobble=0.5)
    dates = pd.Series(ADOPTION_ORIGINS.strftime("%Y-%m-%d"), index=ADOPTION_ORIGINS)
    as_text = system.assign(date=dates.reindex(system["date"]).to_numpy())
    as_text["date"] = as_text["date"].str.replace(r"^(\d{4})-0?(\d+)-0?(\d+)$", r"\1-\2-\3", regex=True)
    assert ev.adoption_verdict(PASSED, as_text) == ev.adoption_verdict(PASSED, system)


def test_adoption_refuses_a_repeated_origin():
    """Each cell holds one row per origin. A repeated row would reweight the mean, so it is refused."""
    system = _system({("active_validator_stake_navax", 90): 3.0}, wobble=8.0)
    primary = system[(system.variable == "active_validator_stake_navax") & (system.horizon == 90)]
    with pytest.raises(ValueError):
        ev.adoption_verdict(PASSED, pd.concat([system, primary.iloc[[0]]], ignore_index=True))


def test_adoption_refuses_malformed_tables_and_thresholds():
    """A horizon that is not a whole number of days or a missing date is refused, so neither can turn a rejection into
    an adoption."""
    system = _system({("active_validator_stake_navax", 90): 3.0}, wobble=8.0)
    primary = system[(system.variable == "active_validator_stake_navax") & (system.horizon == 90)]
    with pytest.raises(ValueError):
        ev.adoption_verdict(PASSED, pd.concat([system, primary.assign(horizon=90.5, challenger=0.0)], ignore_index=True))
    with pytest.raises(ValueError):
        ev.adoption_verdict(PASSED, system.assign(date=system["date"].where(system.index != 0)))
    with pytest.raises(ValueError):
        ev.adoption_verdict(PASSED, pd.concat([system, primary.assign(horizon=0)], ignore_index=True))


def test_adoption_refuses_unlabelled_rows_and_uneven_origins():
    """A row with no variable, cells scored on different origins, or fewer than three origins is refused, so no row
    can be dropped or left out to turn a rejection into an adoption."""
    system = _system({("active_validator_stake_navax", 90): 3.0}, wobble=8.0)
    with pytest.raises(ValueError):
        ev.adoption_verdict(PASSED, system.assign(variable=system["variable"].where(system.index != 0)))
    primary = (system.variable == "active_validator_stake_navax") & (system.horizon == 90)
    with pytest.raises(ValueError):
        ev.adoption_verdict(PASSED, system[~(primary & (system["date"] > ADOPTION_ORIGINS[0]))])
    with pytest.raises(ValueError):
        ev.adoption_verdict(PASSED, system[system["date"] < ADOPTION_ORIGINS[2]])


def test_adoption_does_not_depend_on_the_scale_of_scores():
    """The paired test does not depend on the scale of the differences, so very large finite scores give the same p
    and the same verdict instead of overflowing."""
    system = _system({("active_validators", 30): 0.5}, wobble=0.1)
    cell = (system.variable == "active_validators") & (system.horizon == 30)
    scaled = system.copy()
    scaled.loc[cell, ["incumbent", "challenger"]] *= 1e160
    small, large = ev.adoption_verdict(PASSED, system), ev.adoption_verdict(PASSED, scaled)
    assert large["verdict"] == small["verdict"] == "reject"
    assert large["cells"][("active_validators", 30)]["p_worse"] == pytest.approx(small["worst_cell_p"], rel=1e-9)


def test_adoption_refuses_scores_that_are_not_exact_real_numbers():
    """Complex scores or horizons, and integers too large to hold exactly as floats, are refused rather than
    converted with a loss that could change the verdict."""
    system = _system()
    with pytest.raises(ValueError):
        ev.adoption_verdict(PASSED, system.assign(challenger=system["challenger"].astype(complex)))
    with pytest.raises(ValueError):
        ev.adoption_verdict(PASSED, system.assign(horizon=system["horizon"].astype(complex)))
    large = system.assign(incumbent=np.int64(2**60), challenger=np.int64(2**60) + 3)
    with pytest.raises(ValueError):
        ev.adoption_verdict(PASSED, large)
    small = system.assign(incumbent=np.int64(5), challenger=np.int64(8))
    assert ev.adoption_verdict(PASSED, small)["verdict"] == "reject"


def test_adoption_thresholds_are_fixed_and_inputs_are_checked():
    """The margin, the cell test level and the cells are fixed in the module, so no caller can loosen the rule. A block
    that is not a mapping, a table that is not a DataFrame, or a table missing a column is refused with ValueError."""
    import inspect

    assert list(inspect.signature(ev.adoption_verdict).parameters) == ["block", "system"]
    assert ev.ADOPTION_MARGIN == 2.2 and ev.ADOPTION_CELL_ALPHA == pytest.approx(0.05 / 6)
    system = _system()
    for block, table in ((None, system), (PASSED, None), (PASSED, system.to_dict("records")),
                         (PASSED, system.drop(columns="date")), (PASSED, system.drop(columns="challenger"))):
        with pytest.raises(ValueError):
            ev.adoption_verdict(block, table)


def test_adoption_a_failed_test_rejects_even_without_an_event_test():
    """A failed calibration or origin-available test rejects, and the missing event test is named among the reasons.
    With no failure and no event test the verdict is "no event test"."""
    system = _system()
    verdict = ev.adoption_verdict({"event_test": None, "calibration": False, "origin_available": None}, system)
    assert verdict["verdict"] == "reject" and verdict["reasons"] == ["no event test", "calibration"]
    verdict = ev.adoption_verdict({"event_test": None, "calibration": None, "origin_available": False}, system)
    assert verdict["verdict"] == "reject" and verdict["reasons"] == ["no event test", "origin-available"]
