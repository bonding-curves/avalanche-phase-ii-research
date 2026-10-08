"""Charts for the research report on staking model v0.7.

Each chart answers one question and writes four files with one stem: a PNG for the page, an HTML for interaction, a
CSV holding exactly the drawn data under readable column names, and a JSON receipt naming every input with its sha256.

    uv run --group notebook python scripts/figures/model_v07_report.py CHART OUT_DIR --input NAME=PATH ...

Charts and their inputs:

    scores        summary=development-summary.csv   Mean scaled error by horizon, v0.7 against three simple forecasts
    origins       scores=development-scores.csv     Scaled error at each origin, v0.7 against holding today's value
    bias          scores=development-scores.csv     Signed error at 90 days by origin, with the mean before and from 2024

The score files come from ``scripts/model_development_scores.py`` run on model v0.7 at tag ``model-v0.7.0``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import holoviews as hv
import pandas as pd

from avalanche_research.views.model_results import INK, MODEL_COLORS, MUTED

sys.path.insert(0, str(Path(__file__).parent))
from png import save_png

# Display names: every column, axis and series a reader sees.
VARIABLES = {"active_validator_stake_navax": "Validator stake", "active_validators": "Active validators"}
FORECASTS = {"model": "Model v0.7", "N1": "Holding today's value", "N2": "Extending the 180-day trend",
             "N3": "Weekly time-series fit"}
MARKERS = {"N1": "circle", "N2": "square", "N3": "triangle"}
V07 = MODEL_COLORS["v0.7"]
WIDTH = 820
STYLE = {"fontscale": 1.1, "toolbar": None, "show_grid": True}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(chart, table: pd.DataFrame, out: Path, stem: str, inputs: dict[str, Path], height: int) -> Path:
    """Save the chart as HTML and PNG, its table as CSV, and a receipt of its inputs."""
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / f"{stem}.csv", index=False)
    hv.save(chart, out / f"{stem}.html")
    save_png(out / f"{stem}.html", out / f"{stem}.png", WIDTH + 40, height + 40)
    receipt = {"chart": stem, "script": "scripts/figures/model_v07_report.py",
               "inputs": {name: {"file": p.name, "sha256": sha256(p)} for name, p in inputs.items()}}
    (out / f"{stem}.json").write_text(json.dumps(receipt, indent=1) + "\n")
    return out / f"{stem}.png"


def scores_table(summary: pd.DataFrame) -> pd.DataFrame:
    """One row per variable, horizon and forecast: the mean scaled error at the development origins."""
    rows = []
    for (variable, horizon), part in summary.groupby(["variable", "horizon_days"], sort=False):
        first = part.iloc[0]
        rows.append({"Quantity": VARIABLES[variable], "Days after the origin": int(horizon),
                     "Forecast": FORECASTS["model"], "Mean scaled error": round(first.model_mase, 2),
                     "Origins scored": int(first.origins), "Origins where v0.7 is closer": None})
        for _, r in part.iterrows():
            rows.append({"Quantity": VARIABLES[variable], "Days after the origin": int(horizon),
                         "Forecast": FORECASTS[r.benchmark], "Mean scaled error": round(r.benchmark_mase, 2),
                         "Origins scored": int(r.origins), "Origins where v0.7 is closer": int(r.model_closer)})
    return pd.DataFrame(rows)


def declutter(ends: list[list], gap: float) -> list[list]:
    """Move end labels apart vertically so no two sit closer than ``gap``, keeping their order."""
    ends = sorted(ends, key=lambda e: e[1])
    for i in range(1, len(ends)):
        ends[i][1] = max(ends[i][1], ends[i - 1][1] + gap)
    return ends


def scores_panel(table: pd.DataFrame, quantity: str, title: str, top: float) -> hv.Overlay:
    part = table[table.Quantity == quantity]
    layers, ends = [], []
    for code, name in FORECASTS.items():
        line = part[part.Forecast == name].sort_values("Days after the origin")
        model = code == "model"
        color = V07 if model else MUTED
        layers.append(hv.Curve(line, "Days after the origin", ["Mean scaled error", "Forecast"]).opts(
            color=color, line_width=3.5 if model else 1.6, line_dash="solid" if model else "dashed"))
        layers.append(hv.Scatter(line, "Days after the origin", ["Mean scaled error", "Forecast"]).opts(
            color=color if model else "white", line_color=color, line_width=2, size=11 if model else 9,
            marker=MARKERS.get(code, "circle"), tools=["hover"]))
        end = line.iloc[-1]
        ends.append([float(end["Days after the origin"]), float(end["Mean scaled error"]), name, model])
    labels = [hv.Text(x + 6, y, name, halign="left").opts(text_color=INK if model else MUTED, text_font_size="10.5pt",
                                                          text_font_style="bold" if model else "normal")
              for x, y, name, model in declutter(ends, gap=top * 0.07)]
    return hv.Overlay(layers + labels).opts(
        width=WIDTH, height=330, title=title, xlabel="Days after the origin", ylabel="Mean scaled error (lower is better)",
        ylim=(0, top), xlim=(15, 300), xticks=[(h, f"{h} days") for h in (30, 90, 180)], show_legend=False, **STYLE)


def chart_scores(inputs: dict[str, Path], out: Path) -> Path:
    """Does v0.7 beat simple forecasts as the horizon grows? Validator stake above, the validator count below."""
    summary = pd.read_csv(inputs["summary"])
    table = scores_table(summary)
    top = float(table["Mean scaled error"].max()) * 1.08
    stake = scores_panel(table, "Validator stake",
                         "Validator stake: v0.7 is worse than holding today's value at every horizon", 23)
    count = scores_panel(table, "Active validators",
                         "Active validators: v0.7's mean errors are close to holding today's value", top)
    layout = (stake + count).cols(1).opts(shared_axes=False, toolbar=None)
    return write(layout, table, out, "forecast-scores", inputs, 2 * 330 + 20)


def origin_label(row) -> str:
    when = pd.Timestamp(row.origin_date).strftime("%-d %b %Y")
    return f"{row.origin}, {when}" if row.kind == "upgrade" else when


def origin_table(scores: pd.DataFrame) -> pd.DataFrame:
    """One row per origin, quantity, horizon and forecast, with the scaled and signed errors."""
    t = scores.copy()
    t["Origin"] = t.apply(origin_label, axis=1)
    t["Origin type"] = t.kind.map({"upgrade": "Network upgrade", "quarter": "Start of quarter"})
    t["Signed error (% of actual)"] = ((t.value - t.actual) / t.actual * 100).round(2)
    t["Era"] = t.origin_date.map(lambda d: "Before 2024" if d < "2024-01-01" else "From 2024")
    out = pd.DataFrame({
        "Origin": t.Origin, "Origin date": t.origin_date, "Origin type": t["Origin type"], "Era": t.Era,
        "Quantity": t.variable.map(VARIABLES), "Days after the origin": t.horizon_days,
        "Forecast": t.forecast.map(FORECASTS), "Forecast value": t.value.round(2), "Actual value": t.actual.round(2),
        "Scaled error": t.scaled_error.round(2), "Signed error (% of actual)": t["Signed error (% of actual)"]})
    return out.sort_values(["Quantity", "Days after the origin", "Origin date", "Forecast"]).reset_index(drop=True)


def chart_origins(inputs: dict[str, Path], out: Path) -> Path:
    """Where, by origin, does v0.7 lose to holding today's value? Validator stake at 90 days, origins in date order."""
    table = origin_table(pd.read_csv(inputs["scores"]))
    part = table[(table.Quantity == "Validator stake") & (table["Days after the origin"] == 90)
                 & table.Forecast.isin([FORECASTS["model"], FORECASTS["N1"]])]
    wide = part.pivot_table(index=["Origin date", "Origin"], columns="Forecast", values="Scaled error").reset_index()
    wide = wide.sort_values("Origin date", ascending=False).reset_index(drop=True)
    wide["y"] = range(len(wide))
    model, hold = FORECASTS["model"], FORECASTS["N1"]
    worse = wide[model] > wide[hold]
    segs = hv.Segments((wide[hold].to_numpy(), wide.y.to_numpy(), wide[model].to_numpy(), wide.y.to_numpy())).opts(
        color="#c9ccd1", line_width=3)
    h = hv.Scatter(wide.rename(columns={hold: "x"}), "x", ["y", "Origin"]).opts(
        color="white", line_color=MUTED, line_width=2, size=10, marker="circle")
    m = hv.Scatter(wide.rename(columns={model: "x"}), "x", ["y", "Origin"]).opts(color=V07, size=11)
    ticks = [(int(y), str(o)) for y, o in zip(wide.y, wide.Origin)]
    n_worse = int(worse.sum())
    keys = hv.Text(float(wide[[model, hold]].max().max()) * 0.62, len(wide) - 0.6,
                   "●  Model v0.7      ○  Holding today's value", halign="left").opts(text_font_size="10.5pt", text_color=INK)
    chart = hv.Overlay([segs, h, m, keys]).opts(
        width=WIDTH, height=560, title=f"Stake at 90 days: v0.7 is further off than holding today's value at {n_worse} of {len(wide)} origins",
        xlabel="Scaled error at 90 days (lower is better)", ylabel="", yticks=ticks, ylim=(-0.8, len(wide) + 0.2),
        xlim=(0, None), show_legend=False, **STYLE)
    keep = table[table.Forecast.isin([FORECASTS["model"], FORECASTS["N1"]])]
    return write(chart, keep, out, "forecast-scores-by-origin", inputs, 560)


def chart_bias(inputs: dict[str, Path], out: Path) -> Path:
    """Is the error a bias that changes by era? Signed error on validator stake at 90 days, by origin date."""
    table = origin_table(pd.read_csv(inputs["scores"]))
    part = table[(table.Quantity == "Validator stake") & (table["Days after the origin"] == 90)
                 & (table.Forecast == FORECASTS["model"])].copy()
    part["When"] = pd.to_datetime(part["Origin date"])
    part["Colour"] = part["Signed error (% of actual)"].map(lambda v: V07 if v > 0 else "#3566a3")
    stems = hv.Segments((part.When, [0.0] * len(part), part.When, part["Signed error (% of actual)"])).opts(
        color="#c9ccd1", line_width=2)
    upgrade = part["Origin type"] == "Network upgrade"
    dots = hv.Scatter(part[~upgrade], "When", ["Signed error (% of actual)", "Origin", "Colour"]).opts(
        color="Colour", size=10, tools=["hover"])
    diamonds = hv.Scatter(part[upgrade], "When", ["Signed error (% of actual)", "Origin", "Colour"]).opts(
        color="Colour", size=14, marker="diamond", tools=["hover"])
    layers = [hv.HLine(0).opts(color=INK, line_width=1), stems, dots, diamonds]
    places = {"Before 2024": pd.Timestamp("2022-07-15"), "From 2024": pd.Timestamp("2024-11-20")}
    for era, start, end in (("Before 2024", "2022-06-01", "2023-12-31"), ("From 2024", "2024-01-01", "2025-10-31")):
        mean = float(part[part.Era == era]["Signed error (% of actual)"].mean())
        layers.append(hv.Segments(([pd.Timestamp(start)], [mean], [pd.Timestamp(end)], [mean])).opts(
            color=INK, line_width=2, line_dash="dashed"))
        layers.append(hv.Text(places[era], 33.0, f"{era}: mean {mean:+.1f}%".replace("-", "\u2212"), halign="left").opts(
            text_font_size="11pt", text_color=INK, text_font_style="bold"))
    for _, row in part[upgrade].iterrows():
        layers.append(hv.Text(row.When, -18.5, row.Origin.split(",")[0]).opts(text_font_size="9.5pt", text_color=MUTED))
    chart = hv.Overlay(layers).opts(
        width=WIDTH, height=380, title="Validator stake at 90 days: v0.7 under-forecast before 2024 and over-forecast after",
        xlabel="Origin date", ylabel="Forecast minus actual (% of actual)", ylim=(-21, 55), show_legend=False, **STYLE)
    keep = part.drop(columns=["When", "Colour"])
    return write(chart, keep, out, "forecast-bias-by-era", inputs, 380)


CHARTS = {"scores": chart_scores, "origins": chart_origins, "bias": chart_bias}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("chart", choices=sorted(CHARTS))
    parser.add_argument("out", type=Path)
    parser.add_argument("--input", action="append", default=[], metavar="NAME=PATH")
    args = parser.parse_args()
    hv.extension("bokeh")
    inputs = {k: Path(v) for k, v in (item.split("=", 1) for item in args.input)}
    print(CHARTS[args.chart](inputs, args.out))


if __name__ == "__main__":
    main()
