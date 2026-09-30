"""Weekly duration means, shared selections, and inspectable plotting data."""

from datetime import date

import holoviews as hv
import pandas as pd
import panel as pn
import pytest
from bokeh.models import BoxAnnotation, HoverTool

from avalanche_research import staking_cohorts
from avalanche_research.staking_cohorts import StakingCohorts, cohort_table
from avalanche_research.staking_durations import (
    DURATION_SERIES,
    StakingDurations,
    mean_commitment_durations,
)


@pytest.fixture
def owner(monkeypatch):
    hv.extension("bokeh")
    # Validator commitments: (100 AVAX, 2 days), (300 AVAX, 10 days), (200 AVAX, 4 days).
    daily = pd.DataFrame([
        ["2026-09-14", "validator", "granite", "2026-09-14 12:00", 2, 400, 3200, 12, 0, 0],
        ["2026-09-16", "validator", "granite", "2026-09-16 12:00", 1, 200, 800, 4, 0, 0],
        ["2026-09-14", "delegator", "granite", "2026-09-14 12:00", 1, 50, 700, 14, 0, 0],
    ], columns=["accepted_day", "role", "era", "first_accepted", *staking_cohorts.MEASURES])
    cutoffs = {"validator": pd.Timestamp("2026-09-24 12:00"),
               "delegator": pd.Timestamp("2026-09-24 12:00")}
    tables = {grain: cohort_table(daily, cutoffs, grain) for grain in StakingCohorts.param.time_grain.objects}
    monkeypatch.setattr(staking_cohorts, "_cohort_data", lambda run: (
        tables, cutoffs, pd.Timestamp("2026-09-24"), daily, (),
    ))
    return StakingCohorts("duration-fixture")


def test_unequal_stakes_use_ratios_of_sums(owner):
    rows = StakingDurations(cohorts=owner).table()
    first = rows.iloc[0]
    assert first["Total Commitments"] == 3
    assert first["Mean duration (days)"] == pytest.approx((2 + 10 + 4) / 3)
    assert first["Stake-weighted mean duration (days)"] == pytest.approx(
        (100 * 2 + 300 * 10 + 200 * 4) / (100 + 300 + 200),
    )
    original = owner._tables["Week"].query("Role == 'Validator'").sort_values("Start (UTC)")
    assert rows["Mean duration (days)"].tolist()[0] == original["Duration / Commitment (days)"].iloc[0]


def test_equal_stakes_make_means_equal_and_zero_denominators_are_undefined(owner):
    frame = owner._tables["Week"].copy()
    frame.loc[0, ["Total Commitments", "Total Stake (AVAX)",
                  "Total Committed Duration (commitment-days)", "Total Stake-duration (AVAX-days)"]] = [2, 200, 12, 1200]
    summary = mean_commitment_durations(frame)
    row = summary[(summary["Total Commitments"] == 2)].iloc[0]
    assert row["Mean duration (days)"] == row["Stake-weighted mean duration (days)"] == 6
    empty = summary[summary["Total Commitments"].eq(0)]
    assert empty[list(DURATION_SERIES)].isna().all().all()
    frame["Total Stake (AVAX)"] = 0
    assert mean_commitment_durations(frame)["Stake-weighted mean duration (days)"].isna().all()


def test_shared_population_and_inclusive_dates_do_not_change_other_choices(owner):
    comparison = StakingDurations(cohorts=owner)
    controls = comparison.panel()
    assert controls[0].value == owner.population
    controls[0].value = "Delegators"
    assert owner.population == "Delegators"
    assert comparison.table()["Role"].unique().tolist() == ["Delegator"]
    owner.population = "Both"
    assert set(comparison.table()["Role"]) == {"Validator", "Delegator"}
    owner.population = "Validators"
    owner.date_range = (date(2026, 9, 16), date(2026, 9, 16))
    selected = comparison.table().iloc[0]
    assert selected["Total Commitments"] == 1
    assert selected["Mean duration (days)"] == selected["Stake-weighted mean duration (days)"] == 4
    assert controls[1].value == owner.date_range
    assert owner.time_grain == "Era" and owner.periodic_denominator == "Day"
    owner.date_range = (date(2026, 9, 17), date(2026, 9, 18))
    assert comparison.table()[list(DURATION_SERIES)].isna().all().all()
    assert isinstance(comparison.plot(), pn.pane.Markdown)


def test_plot_preserves_gaps_units_hover_and_line_identities(owner):
    hv.extension("bokeh")
    comparison = StakingDurations(cohorts=owner)
    assert DURATION_SERIES == {
        "Mean duration (days)": {"color": "#1f77b4", "line_dash": "solid"},
        "Stake-weighted mean duration (days)": {"color": "#b85c00", "line_dash": "dashed"},
    }
    overlay = comparison.plot()
    curves = [element for element in overlay if isinstance(element, hv.Curve)]
    assert len(curves) == 2
    for curve, (measure, style) in zip(curves, DURATION_SERIES.items(), strict=True):
        assert curve.label == measure
        assert pd.isna(curve.dimension_values(measure)[-1])
        assert hv.Store.lookup_options("bokeh", curve, "style").kwargs["line_dash"] == style["line_dash"]
        assert hv.Store.lookup_options("bokeh", curve, "style").kwargs["color"] == style["color"]
    figure = hv.render(overlay)
    assert figure.yaxis[0].axis_label == "Mean commitment duration (days)"
    assert figure.above and figure.select(BoxAnnotation)
    assert pd.Timestamp(figure.x_range.start) == pd.Timestamp("2026-09-14 12:00")
    assert any("Duration (days)" == label for tool in figure.select(HoverTool) for label, _ in tool.tooltips)
    owner.population = "Both"
    assert sum(isinstance(element, hv.Curve) for element in comparison.plot()) == 4
