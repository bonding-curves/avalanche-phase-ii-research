"""Commitment-weighted and stake-weighted durations of weekly acceptance cohorts."""

from __future__ import annotations

import holoviews as hv
import pandas as pd
import panel as pn
import param as pm
from bokeh.models import NumeralTickFormatter

from .staking_cohorts import (
    DAY,
    NETWORK_START,
    StakingCohorts,
    _era_intervals,
    _legend_interaction,
    _upgrade_axis,
    cohort_table,
    for_population,
)

DURATION_SERIES = {
    "Mean duration (days)": {"color": "#1f77b4", "line_dash": "solid"},
    "Stake-weighted mean duration (days)": {"color": "#b85c00", "line_dash": "dashed"},
}
CHART_HEIGHT = 500
LINE_WIDTH = 3
ERA_SHADE = "#eeeeee"
CONTROL_WIDTH = 220


def mean_commitment_durations(cohorts: pd.DataFrame) -> pd.DataFrame:
    """Derive two means from additive cohort totals without averaging daily means."""
    columns = [
        "Reporting Interval", "Start (UTC)", "End (UTC)", "Role", "Total Commitments",
        "Total Stake (AVAX)", "Total Committed Duration (commitment-days)",
        "Total Stake-duration (AVAX-days)",
    ]
    result = cohorts[columns].copy().sort_values(["Start (UTC)", "Role"])
    counts = result["Total Commitments"].replace(0, float("nan"))
    stake = result["Total Stake (AVAX)"].replace(0, float("nan"))
    result["Mean duration (days)"] = result["Total Committed Duration (commitment-days)"] / counts
    result["Stake-weighted mean duration (days)"] = result["Total Stake-duration (AVAX-days)"] / stake
    return result.reset_index(drop=True)


class StakingDurations(pm.Parameterized):
    """Compare duration means using an existing cohort object's shared selections."""

    cohorts = pm.ClassSelector(class_=StakingCohorts, allow_None=False,
                              constant=True, precedence=-1)

    @pm.depends("cohorts.population", "cohorts.date_range")
    def table(self) -> pd.DataFrame:
        owner = self.cohorts
        if owner.date_range == owner.param.date_range.bounds:
            weekly = owner._tables["Week"]
        else:
            start, end = owner.date_range
            weekly = cohort_table(owner._daily, owner._cutoffs, "Week",
                                  window=(pd.Timestamp(start), pd.Timestamp(end) + DAY))
        return mean_commitment_durations(for_population(weekly, owner.population))

    @pm.depends("cohorts.population", "cohorts.date_range")
    def plot(self):
        frame = self.table()
        if frame.empty or not frame["Total Commitments"].gt(0).any():
            return pn.pane.Markdown("No accepted commitments in the selected dates.")
        frame["Date"] = frame["Start (UTC)"] + (frame["End (UTC)"] - frame["Start (UTC)"]) / 2
        start, end = frame["Start (UTC)"].min(), frame["End (UTC)"].max()
        bands = [hv.VSpan(a, b).opts(color=ERA_SHADE, line_alpha=0)
                 for index, (_, a, b) in enumerate(_era_intervals(NETWORK_START, end))
                 if index % 2 and b > start]
        curves = []
        for role, rows in frame.groupby("Role", sort=False):
            for measure, style in DURATION_SERIES.items():
                label = f"{role}: {measure}" if self.cohorts.population == "Both" else measure
                data = rows.assign(Statistic=label)
                curve = hv.Curve(data, "Date", [measure, "Statistic", "Total Commitments",
                                               "Start (UTC)", "End (UTC)"], label=label)
                hover = {
                    "tools": ["hover"],
                    "hover_tooltips": [("Mean", "@Statistic"), ("Duration (days)", f"@{{{measure}}}{{0,0.00}}"),
                                    ("Commitments", "@{Total Commitments}{0,0}"),
                                    ("Accepted from (UTC)", "@{Start (UTC)}{%F %T}"),
                                    ("Before (UTC)", "@{End (UTC)}{%F %T}")],
                    "hover_formatters": {"@{Start (UTC)}": "datetime", "@{End (UTC)}": "datetime"},
                }
                curves.append(curve.opts(**style, line_width=LINE_WIDTH, **hover))
                if data[measure].notna().sum() == 1:
                    curves.append(hv.Scatter(curve).opts(color=style["color"], size=LINE_WIDTH * 2,
                                                        show_legend=False, **hover))
        return hv.Overlay([*bands, *curves]).opts(
            title="Commitment durations by week accepted", xlabel="Calendar time",
            ylabel="Mean commitment duration (days)", responsive=True, height=CHART_HEIGHT,
            xlim=(start, end), ylim=(0, None), padding=0,
            yformatter=NumeralTickFormatter(format="0,0.##"),
            legend_position="top_right", hooks=[_upgrade_axis, _legend_interaction],
        )

    def panel(self):
        """Controls edit the cohort owner rather than a second selection object."""
        owner = self.cohorts
        population = pn.widgets.Select.from_param(owner.param.population, width=CONTROL_WIDTH)
        dates = pn.widgets.DateRangeSlider.from_param(
            owner.param.date_range, start=owner.param.date_range.bounds[0],
            end=owner.param.date_range.bounds[1], step=1, format="%Y-%m-%d",
            sizing_mode="stretch_width",
        )
        note = (f"Pinned run `{owner.run}`. Weekly acceptance cohorts. "
                "Solid: every commitment has equal weight. Dashed: weight is entry stake in AVAX. "
                "Both means use full commitment durations in days, not days spent in that week. "
                "Zero-denominator weeks have gaps. Edge weeks can be partial. "
                "Validator and delegator roles remain separate when Population is Both.")
        return pn.Column(population, dates, self.plot, pn.pane.Markdown(note),
                         sizing_mode="stretch_width")
