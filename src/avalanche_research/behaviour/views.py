"""Param objects the behaviour notebooks display. Each reads results the library already computed, never fits."""

from __future__ import annotations

import holoviews as hv
import hvplot.pandas  # noqa: F401
import pandas as pd
import panel as pn
import param as pm

from . import lifetimes as lifetime_columns

PALETTE = ["#3B82B4", "#D95F02", "#1B9E77", "#7570B3", "#E7298A", "#66A61E", "#E6AB02", "#A6761D", "#666666",
           "#1F78B4", "#B2DF8A", "#FB9A99"]


class LifetimeMap(pm.Parameterized):
    """Nodes on two principal components of their behaviour, coloured by a grouping or by one lifetime column."""

    colour = pm.Selector(default="group", objects=["group"])
    grouping = pm.Selector(default=None, objects=[])
    x = pm.Selector(default="PC1", objects=["PC1"])
    y = pm.Selector(default="PC2", objects=["PC2"])
    coordinates = pm.DataFrame(precedence=-1)
    lifetimes = pm.DataFrame(precedence=-1)
    groupings = pm.Dict(default={}, precedence=-1)

    def __init__(self, **params):
        super().__init__(**params)
        components = list(self.coordinates.columns)
        self.param.x.objects, self.param.y.objects = components, components
        self.x, self.y = components[0], components[1]
        names = list(self.groupings)
        self.param.grouping.objects = names
        self.grouping = names[0] if names else None
        self.param.colour.objects = ["group", *lifetime_columns.BEHAVIOUR, "entry_year", "entry_price_log10"]

    def frame(self) -> pd.DataFrame:
        frame = self.coordinates.join(self.lifetimes)
        if self.grouping:
            frame["group"] = self.groupings[self.grouping].astype(str)
        return frame.reset_index()

    @pm.depends("colour", "grouping", "x", "y")
    def view(self):
        frame = self.frame()
        hover = ["node_id", "group", "periods_log", "median_duration_days", "max_stake_log10", "renew_share"]
        if self.colour == "group":
            return frame.hvplot.scatter(x=self.x, y=self.y, by="group", color=PALETTE, size=6, alpha=0.6,
                                        hover_cols=hover, height=520, responsive=True,
                                        title=f"Nodes by {self.grouping}").opts(legend_position="right")
        return frame.hvplot.scatter(x=self.x, y=self.y, c=self.colour, cmap="viridis", size=6, alpha=0.6,
                                    hover_cols=hover, height=520, responsive=True, colorbar=True,
                                    title=f"Nodes coloured by {self.colour}")


class FoldScores(pm.Parameterized):
    """One score per model and test window, moving forward in time toward the lockbox."""

    metric = pm.Selector(default="log_loss", objects=["log_loss", "brier", "roc_auc", "skill_vs_prior", "accuracy"])
    scores = pm.DataFrame(precedence=-1)

    @pm.depends("metric")
    def view(self):
        lower = self.metric in ("log_loss", "brier")
        title = f"{self.metric} by test window ({'lower' if lower else 'higher'} is better)"
        return self.scores.hvplot.line(x="fold", y=self.metric, by="model", color=PALETTE, markers=True,
                                       height=380, responsive=True, title=title, xlabel="Test window start")


class Calibration(pm.Parameterized):
    """Predicted against observed renewal, in ten probability bins, for one model over every test window."""

    model = pm.Selector(default="boosted", objects=["boosted"])
    tables = pm.Dict(default={}, precedence=-1)

    def __init__(self, **params):
        super().__init__(**params)
        self.param.model.objects = list(self.tables)
        self.model = next(iter(self.tables))

    @pm.depends("model")
    def view(self):
        table = self.tables[self.model]
        diagonal = hv.Curve([(0, 0), (1, 1)], "predicted", "observed").opts(color="#999999", line_dash="dashed")
        points = table.hvplot.scatter(x="predicted", y="observed", size="decisions", scale=0.02, color=PALETTE[0],
                                      hover_cols=["decisions"])
        line = table.hvplot.line(x="predicted", y="observed", color=PALETTE[0])
        return (diagonal * line * points).opts(height=380, responsive=True, xlim=(0, 1), ylim=(0, 1),
                                               title=f"Calibration of {self.model}")


def importance_bars(table: pd.DataFrame, top: int = 20):
    data = table.head(top).iloc[::-1]
    return data.hvplot.barh(x="feature", y="importance", by="family", color=PALETTE, stacked=True, height=520,
                            responsive=True, title="Rise in log loss when a feature is shuffled, last test window",
                            xlabel="", ylabel="Rise in log loss")


def panel(obj, parameters=None):
    """The object's own Param panel beside its view, as the house notebooks lay it out."""
    widgets = {name: {"sizing_mode": "stretch_width", "width": None} for name in (parameters or [])}
    return pn.Row(pn.Param(obj, parameters=parameters, show_name=False, widgets=widgets, width=260), obj.view,
                  sizing_mode="stretch_width")
