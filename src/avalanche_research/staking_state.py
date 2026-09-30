"""Active staking stocks and supply on a checked common daily support."""

from __future__ import annotations

from functools import cache

import holoviews as hv
import pandas as pd
import panel as pn
import param as pm
from bokeh.models import NumeralTickFormatter

from . import datasets
from .palette import QUANTITY_COLORS
from .staking_cohorts import (
    NETWORK_START,
    _era_intervals,
    _legend_interaction,
    _upgrade_axis,
)

DATASET = "derived.avax-monetary-daily"
WEI_PER_AVAX = 10**18
DAY = pd.Timedelta(1, unit="D")
GROUPINGS = {"Day": "D", "Week": "W-MON", "Month": "MS", "Year": "YS"}
STOCK_COLUMNS = {
    "Validator stake (AVAX)": "active_validator_stake_wei",
    "Delegated stake (AVAX)": "active_delegated_stake_wei",
    "Realized total supply (AVAX)": "total_supply_close_wei",
}
ROLE_STYLES = {"Validator": "solid", "Delegated": "dashed", "Combined": "dotted"}
CHART_HEIGHT = 500
LINE_WIDTH = 3
ERA_SHADE = "#eeeeee"
SUPPLY_INK = "#4c4c4c"  # Neutral local rendering, not a new global semantic hue.
CONTROL_WIDTH = 220


def daily_state(ledger: pd.DataFrame) -> pd.DataFrame:
    """Keep missing days as gaps and use identical support for all stocks/ratios."""
    if ledger.date_utc.duplicated().any():
        raise ValueError("daily ledger dates must be unique")
    result = pd.DataFrame({"Date (UTC)": pd.to_datetime(ledger.date_utc).dt.as_unit("ns")})
    for label, column in STOCK_COLUMNS.items():
        result[label] = pd.to_numeric(ledger[column], errors="raise") / WEI_PER_AVAX
    complete = ledger.complete & result[list(STOCK_COLUMNS)].notna().all(axis=1)
    complete &= result["Realized total supply (AVAX)"].gt(0)
    result.loc[~complete, list(STOCK_COLUMNS)] = float("nan")
    result["Complete days"] = complete.astype(int)
    result["Observed days"] = 1
    result["Combined stake (AVAX)"] = result["Validator stake (AVAX)"] + result["Delegated stake (AVAX)"]
    for role in ROLE_STYLES:
        stake = "Delegated stake (AVAX)" if role == "Delegated" else f"{role} stake (AVAX)"
        result[f"{role} staking ratio (%)"] = 100 * result[stake] / result["Realized total supply (AVAX)"]
    return result.sort_values("Date (UTC)").reset_index(drop=True)


def summarize_state(daily: pd.DataFrame, grouping: str, statistic: str) -> pd.DataFrame:
    """Reduce snapshots or daily ratios, never sum snapshots as an active stock."""
    data = daily.set_index("Date (UTC)")
    if grouping == "Era":
        end = data.index.max() + DAY
        era = pd.Series(index=data.index, dtype="datetime64[ns]")
        closes = data.index + DAY - pd.Timedelta(1, unit="s")
        for _, start, finish in _era_intervals(NETWORK_START, end):
            era.loc[(closes >= start) & (closes < finish)] = start
        groups = data.groupby(era.rename("Date (UTC)"))
    else:
        groups = data.groupby(pd.Grouper(freq=GROUPINGS[grouping], closed="left", label="left"))
    values = data.drop(columns=["Complete days", "Observed days"]).columns
    if statistic == "Last minus first":
        reduced = groups[values].last() - groups[values].first()
    else:
        reduced = getattr(groups[values], {"Last": "last", "Mean": "mean", "Median": "median"}[statistic])()
    coverage = groups[["Complete days", "Observed days"]].sum()
    return reduced.join(coverage).reset_index()


@cache
def _state_data(run: str) -> pd.DataFrame:
    return daily_state(datasets.load(DATASET, run))


class StakingState(pm.Parameterized):
    """A snapshot explorer, separate from acceptance-cohort clocks and controls."""

    quantity = pm.Selector(default="Active stake", objects=["Active stake", "Supply", "Staking ratio"], label="Quantity")
    population = pm.Selector(default="Both", objects=["Validators", "Delegators", "Both"], label="Population")
    grouping = pm.Selector(default="Week", objects=[*GROUPINGS, "Era"], label="Group by")
    statistic = pm.Selector(default="Mean", objects=["Last", "Mean", "Median", "Last minus first"], label="Snapshot statistic")
    date_range = pm.CalendarDateRange(default=None, allow_None=True, label="Snapshot dates (UTC)")

    def __init__(self, run: str, **params):
        super().__init__(**params)
        self.run = run
        self._daily = _state_data(run)
        self.param.date_range.bounds = (self._daily["Date (UTC)"].min().date(), self._daily["Date (UTC)"].max().date())
        if self.date_range is None:
            self.date_range = self.param.date_range.bounds

    def columns(self):
        if self.quantity == "Supply":
            return ["Realized total supply (AVAX)"]
        roles = {"Validators": ["Validator"], "Delegators": ["Delegated"], "Both": list(ROLE_STYLES)}[self.population]
        suffix = "stake (AVAX)" if self.quantity == "Active stake" else "staking ratio (%)"
        return [f"{role} {suffix}" for role in roles]

    @pm.depends("quantity", "population", "grouping", "statistic", "date_range")
    def table(self):
        start, end = self.date_range
        selected = self._daily.loc[self._daily["Date (UTC)"].between(pd.Timestamp(start), pd.Timestamp(end))]
        if selected.empty:
            return pd.DataFrame(columns=["Date (UTC)", *self.columns(), "Complete days", "Observed days"])
        frame = summarize_state(selected, self.grouping, self.statistic)
        context = ["Date (UTC)"]
        if self.grouping == "Era":
            names = {a: era for era, a, _ in _era_intervals(NETWORK_START, selected["Date (UTC)"].max() + DAY)}
            frame["Era"] = frame["Date (UTC)"].map(names).str.title()
            context.append("Era")
        return frame[[*context, *self.columns(), "Complete days", "Observed days"]]

    @pm.depends("quantity", "population", "grouping", "statistic", "date_range")
    def plot(self):
        frame = self.table()
        if frame.empty:
            return pn.pane.Markdown("No snapshots in the selected dates.")
        start, end = (pd.Timestamp(value) for value in self.date_range)
        bands = [hv.VSpan(a, b).opts(color=ERA_SHADE, line_alpha=0)
                 for index, (_, a, b) in enumerate(_era_intervals(NETWORK_START, end + DAY))
                 if index % 2 and b > start]
        curves = []
        for measure in self.columns():
            role = measure.split()[0]
            color = SUPPLY_INK if self.quantity == "Supply" else QUANTITY_COLORS["stake"]
            curve = hv.Curve(frame.assign(Measure=measure), "Date (UTC)",
                             [measure, "Measure", "Complete days", "Observed days"], label=measure)
            hover = {"tools": ["hover"], "hover_tooltips": [("Group start (UTC)", "@{Date (UTC)}{%F}"),
                     ("Measure", "@Measure"),
                     ("Value", f"@{{{measure}}}{{0,0.00}}"), ("Complete days", "@{Complete days}"),
                     ("Observed days", "@{Observed days}")],
                     "hover_formatters": {"@{Date (UTC)}": "datetime"}}
            curves.append(curve.opts(color=color, line_dash=ROLE_STYLES.get(role, "solid"),
                                     line_width=LINE_WIDTH, **hover))
            if frame[measure].notna().sum() == 1:
                curves.append(hv.Scatter(curve).opts(color=color, size=LINE_WIDTH * 2, show_legend=False, **hover))
        return hv.Overlay([*bands, *curves]).opts(
            title=f"{self.statistic} {self.quantity.lower()} by {self.grouping.lower()}",
            xlabel="UTC snapshot date", ylabel="Staking ratio (%)" if self.quantity == "Staking ratio" else "AVAX",
            responsive=True, height=CHART_HEIGHT, padding=0, xlim=(min(start, frame["Date (UTC)"].min()), end + DAY),
            yformatter=NumeralTickFormatter(format="0,0.##"), legend_position="top_right",
            hooks=[_upgrade_axis, _legend_interaction],
        )

    def panel(self):
        controls = pn.Row(*(pn.widgets.Select.from_param(self.param[name], width=CONTROL_WIDTH)
                            for name in ["quantity", "population", "grouping", "statistic"]))
        dates = pn.widgets.DateRangeSlider.from_param(self.param.date_range, sizing_mode="stretch_width", format="%Y-%m-%d")
        table = pn.widgets.Tabulator(self.table(), show_index=False, disabled=True, pagination="local", page_size=10,
                                     sizing_mode="stretch_width", layout="fit_columns",
                                     formatters={"Date (UTC)": {"type": "datetime", "format": "yyyy-MM-dd"},
                                                 **{column: {"type": "number", "format": "0,0.00"}
                                                    for column in self._daily.columns
                                                    if column not in ["Date (UTC)", "Complete days", "Observed days"]}})
        self.param.watch(lambda event: setattr(table, "value", self.table()),
                         ["quantity", "population", "grouping", "statistic", "date_range"])
        note = (f"Pinned ledger `{self.run}`. Active stake is sampled at 23:59:59 UTC and supply at day close. "
                "All quantities use the same complete daily support. Missing days stay missing. "
                "Mean/median ratios reduce daily ratios, not ratios of aggregated stocks. "
                "Last means last complete reading. Last minus first is a change between complete closes, not issuance or burn. "
                "Grouped points use interval starts. Edge groups can be partial. These controls do not change acceptance cohorts.")
        return pn.Column(controls, dates, self.plot, table, pn.pane.Markdown(note), sizing_mode="stretch_width")
