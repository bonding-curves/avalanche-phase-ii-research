"""Experiment charts for the research report on staking model v0.7: forecast fans, run-to-run spread, the five
reward designs, and one-setting-at-a-time sensitivity.

    uv run --group notebook python scripts/figures/model_v07_experiments.py RESULTS_DIR OUT_DIR [CHART ...]

RESULTS_DIR holds the tables written by ``scripts/model_v07_report_runs.py``, which runs model v0.7 at tag
``model-v0.7.0`` on the pinned runs of ``data/pins/p2-model-v0.8.json``. Each chart writes four files with one stem: a
PNG for the page, an HTML for interaction, a CSV holding exactly the drawn data under readable column names, and a JSON
receipt naming every input with its sha256.

Charts:

    fan        forecast-fans.*            Daily forecasts from four upgrades against what happened, 180 days
    spread     forecast-run-spread.*      Run-to-run spread 90 days after each of 19 origins, against the actual value
    designs    designs-by-response.*      Validators and AVAX issued after 180 days from Fortuna, five designs, three
                                          response strengths, with the chain's actual validator count
    tornado    sensitivity-tornado.*      Change in validators and issuance when one setting moves from the base
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import holoviews as hv
import pandas as pd

from avalanche_research.palette import MECHANISM_COLORS, QUANTITY_COLORS
from avalanche_research.views.model_results import INK, MUTED

sys.path.insert(0, str(Path(__file__).parent))
from model_v07_report import STYLE, WIDTH, declutter, write

SCRIPT = "scripts/figures/model_v07_experiments.py"
ACTUAL = "#222222"
BAND = "#c9ccd1"
STAKE, NODES = QUANTITY_COLORS["stake"], QUANTITY_COLORS["nodes"]
CHAIN, ACP285 = "Chain before ACP-285", "ACP-285 at 7.5%"
# Each design's colour, from the palette's names for the same designs.
DESIGN_COLORS = {
    CHAIN: MECHANISM_COLORS["Chain today"],
    ACP285: MECHANISM_COLORS["ACP-285 settings"],
    "Tenure boost": MECHANISM_COLORS["Tenure boost"],
    "Quadratic curve": MECHANISM_COLORS["Quadratic curve"],
    "Quadratic curve at the chain's issuance": MECHANISM_COLORS["Quadratic curve, today's issuance"],
}
RUNS_RECEIPT = "model-v07-report-runs.json"


def save(chart, table: pd.DataFrame, out: Path, stem: str, inputs: dict[str, Path], height: int) -> Path:
    """``write`` from the report script, with the receipt naming this script and the runs' receipt."""
    png = write(chart, table, out, stem, inputs, height)
    receipt_path = out / f"{stem}.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["script"] = SCRIPT
    runs = json.loads(inputs["runs receipt"].read_text())
    receipt["model"] = runs["model"]
    receipt["pinned runs"] = runs["inputs"]
    receipt_path.write_text(json.dumps(receipt, indent=1) + "\n")
    return png


def day_label(day: str) -> str:
    return pd.Timestamp(day).strftime("%-d %b %Y")


def origin_label(name: str, day: str) -> str:
    return f"{name}, {day_label(day)}" if not name[0].isdigit() else day_label(day)


def minus(text: str) -> str:
    return text.replace("-", "−")


# Forecast fans --------------------------------------------------------------------------------------------------

def fan_panel(part: pd.DataFrame, quantity: str, unit: str, color: str, title: str, ylim, labels: bool,
              key: bool = False) -> hv.Overlay:
    x = "Days after the origin"
    name = f"{quantity}{unit}"
    col = {k: f"{quantity}, {k}{unit}" for k in ("10th percentile", "25th percentile", "median", "75th percentile",
                                                  "90th percentile", "actual")}
    frame = part.rename(columns={col["median"]: name})
    outer = hv.Area(part, x, [col["10th percentile"], col["90th percentile"]]).opts(color=color, alpha=0.18, line_alpha=0)
    inner = hv.Area(part, x, [col["25th percentile"], col["75th percentile"]]).opts(color=color, alpha=0.35, line_alpha=0)
    median = hv.Curve(frame, x, name).opts(color=color, line_width=2.5)
    actual = hv.Curve(part, x, col["actual"]).opts(color=ACTUAL, line_width=2.2)
    layers = [outer, inner, median, actual]
    if labels:
        last = part.iloc[-1]
        span = ylim[1] - ylim[0]
        ends = [[183.0, float(last[col["median"]]), "Median", color], [183.0, float(last[col["actual"]]), "Actual", ACTUAL]]
        for x0, y0, text, c in declutter(ends, gap=span * 0.1):
            layers.append(hv.Text(x0, y0, text, halign="left").opts(text_color=c, text_font_size="10pt",
                                                                     text_font_style="bold"))
        if key:
            layers.append(hv.Text(4, ylim[0] + span * 0.06, "Bands: 25th to 75th and 10th to 90th percentile of 20 runs",
                                  halign="left", valign="bottom").opts(text_color=color, text_font_size="9pt"))
    return hv.Overlay(layers).opts(
        width=WIDTH // 2, height=205, title=title, xlabel=x, ylabel=f"{quantity}{unit}", ylim=ylim, xlim=(0, 222),
        xticks=[0, 30, 60, 90, 120, 150, 180], show_legend=False, fontsize={"title": "10.5pt"}, **STYLE)


def chart_fan(results: Path, out: Path) -> Path:
    """What does a forecast look like against what happened? Four upgrades, 180 days, stake and validator count."""
    fan = pd.read_csv(results / "fan.csv")
    end = fan[fan["Days after the origin"] == 180]
    outside = sum(int(not (r[f"{q}, 10th percentile{u}"] <= r[f"{q}, actual{u}"] <= r[f"{q}, 90th percentile{u}"]))
                  for _, r in end.iterrows() for q, u in (("Validator stake", " (M AVAX)"), ("Active validators", "")))

    def limits(quantity: str, unit: str, pad: float):
        cols = [c for c in fan.columns if c.startswith(quantity) and c.endswith(unit)]
        lo, hi = float(fan[cols].min().min()), float(fan[cols].max().max())
        return (lo - pad * (hi - lo), hi + pad * (hi - lo))

    stake_lim, count_lim = limits("Validator stake", " (M AVAX)", 0.06), limits("Active validators", "", 0.06)
    panels = []
    for i, origin in enumerate(fan.Origin.unique()):
        part = fan[fan.Origin == origin]
        where = origin_label(origin, part["Origin date"].iloc[0])
        panels.append(fan_panel(part, "Validator stake", " (M AVAX)", STAKE, f"{where}: validator stake", stake_lim, i == 0, i == 0))
        panels.append(fan_panel(part, "Active validators", "", NODES, f"{where}: active validators", count_lim, i == 0))
    layout = hv.Layout(panels).cols(2).opts(
        shared_axes=False, toolbar=None,
        title=f"After 180 days the actual value lies outside the model's 10 to 90% range in {outside} of 8 panels")
    rows = len(panels) // 2
    return save(layout, fan, out, "forecast-fans", {"fan": results / "fan.csv", "runs receipt": results / RUNS_RECEIPT},
                rows * 205 + 10)


# Run-to-run spread ----------------------------------------------------------------------------------------------

def spread_table(spread: pd.DataFrame) -> pd.DataFrame:
    """Each run and the actual value, as a difference from the mean of the 20 runs at that origin, in percent."""
    rows = []
    for (day, name), part in spread.groupby(["Origin date", "Origin"], sort=True):
        for quantity, run_col, actual_col in (
                ("Validator stake", "Validator stake after 90 days (M AVAX)", "Actual validator stake after 90 days (M AVAX)"),
                ("Active validators", "Active validators after 90 days", "Actual active validators after 90 days")):
            mean = part[run_col].mean()
            actual = part[actual_col].iloc[0]
            rel = (part[run_col] / mean - 1) * 100
            rows.append({
                "Origin": origin_label(name, day), "Origin date": day, "Quantity": quantity,
                "Mean of 20 runs (M AVAX for stake, count for validators)": round(mean, 3),
                "10th percentile of runs (% from mean)": round(rel.quantile(0.1), 2),
                "90th percentile of runs (% from mean)": round(rel.quantile(0.9), 2),
                "Standard error of the mean (%)": round(rel.std(ddof=1) / len(rel) ** 0.5, 2),
                "Actual (% from mean)": None if pd.isna(actual) else round((actual / mean - 1) * 100, 2),
                "Runs (% from mean)": " ".join(f"{v:.2f}" for v in rel)})
    return pd.DataFrame(rows)


def spread_panel(table: pd.DataFrame, quantity: str, color: str, ticks, show_ticks: bool) -> hv.Overlay:
    part = table[table.Quantity == quantity].sort_values("Origin date", ascending=False).reset_index(drop=True)
    part["y"] = range(len(part))
    lo, hi = "10th percentile of runs (% from mean)", "90th percentile of runs (% from mean)"
    dots = [(float(v), y) for y, runs in zip(part.y, part["Runs (% from mean)"]) for v in runs.split()]
    seen = part.dropna(subset=["Actual (% from mean)"])
    inside = (seen[lo] <= seen["Actual (% from mean)"]) & (seen["Actual (% from mean)"] <= seen[hi])
    layers = [
        hv.VLine(0).opts(color=MUTED, line_width=1),
        hv.Segments((part[lo], part.y, part[hi], part.y)).opts(color=color, alpha=0.35, line_width=9),
        hv.Scatter(dots, "x", "y").opts(color=color, size=4, alpha=0.75),
        hv.Scatter(seen.rename(columns={"Actual (% from mean)": "x"}), "x", ["y", "Origin"]).opts(
            color=ACTUAL, marker="diamond", size=13, tools=["hover"]),
    ]
    held = part[part["Actual (% from mean)"].isna()]
    for _, r in held.iterrows():
        layers.append(hv.Text(-39, r.y - 0.45, "actual not shown: held back", halign="left").opts(
            text_font_size="9pt", text_color=MUTED))
    title = f"{quantity}: {int((~inside).sum())} of {len(seen)} actuals outside"
    return hv.Overlay(layers).opts(
        width=WIDTH // 2 + (60 if show_ticks else -60), height=560, title=title,
        xlabel="Difference from the mean of 20 runs (%)", ylabel="", yticks=ticks if show_ticks else [(t, "") for t, _ in ticks],
        ylim=(-0.9, len(part) - 0.2), xlim=(-40, 40), show_legend=False, fontsize={"title": "10.5pt"}, **STYLE)


def chart_spread(results: Path, out: Path) -> Path:
    """How much does Monte Carlo noise matter? Run spread at 90 days against where the actual value landed."""
    table = spread_table(pd.read_csv(results / "spread.csv"))
    order = table[table.Quantity == "Validator stake"].sort_values("Origin date", ascending=False).reset_index(drop=True)
    ticks = [(i, o) for i, o in enumerate(order.Origin)]
    stake_spread = table[table.Quantity == "Validator stake"]
    half = (stake_spread["90th percentile of runs (% from mean)"] - stake_spread["10th percentile of runs (% from mean)"]).mean() / 2
    seen = stake_spread.dropna(subset=["Actual (% from mean)"])
    outside = int((~seen["Actual (% from mean)"].between(seen["10th percentile of runs (% from mean)"],
                                                         seen["90th percentile of runs (% from mean)"])).sum())
    layout = hv.Layout([spread_panel(table, "Validator stake", STAKE, ticks, True),
                        spread_panel(table, "Active validators", NODES, ticks, False)]).cols(2).opts(
        shared_axes=False, toolbar=None,
        title=f"At 90 days the runs spread about \u00b1{half:.0f}% on stake, yet {outside} of {len(seen)} actuals fall outside that range")
    return save(layout, table, out, "forecast-run-spread",
                {"spread": results / "spread.csv", "runs receipt": results / RUNS_RECEIPT}, 560 + 30)


# Designs by response --------------------------------------------------------------------------------------------

def chart_designs(results: Path, out: Path) -> Path:
    """What does each design buy in validators for its issuance, at each response strength?"""
    designs = pd.read_csv(results / "designs.csv")
    on_chain = int(designs["Active validators on the chain 180 days after Fortuna"].iloc[0])
    mean, p10, p90 = ("Validators after 180 days, mean", "Validators after 180 days, 10th percentile",
                      "Validators after 180 days, 90th percentile")
    issued = "AVAX issued in 180 days (M)"
    rows, ticks, headers, y = [], [], [], 0
    for response in sorted(designs["Response strength"].unique(), reverse=True):
        part = designs[designs["Response strength"] == response]
        for design in list(DESIGN_COLORS)[::-1]:
            r = part[part.Design == design].iloc[0]
            rows.append({**r.to_dict(), "y": y, "Colour": DESIGN_COLORS[design]})
            ticks.append((y, design))
            y += 1
        headers.append((y, f"Response to reward {response:g}"))
        ticks.append((y, ""))
        y += 1
    frame = pd.DataFrame(rows)
    frame["y1"], frame["zero"] = frame.y, 0.0
    top = y + 0.5
    lim = (-0.7, top + 0.3)
    beside = on_chain + 15
    left = hv.Overlay([
        hv.VLine(on_chain).opts(color=ACTUAL, line_width=2, line_dash="dashed"),
        hv.Text(beside, top - 0.1, f"The chain's actual count after 180 days: {on_chain:,}", halign="left").opts(
            text_font_size="9.5pt", text_color=ACTUAL, text_font_style="bold"),
        *[hv.Text(beside, hy, text, halign="left").opts(text_font_size="9.5pt", text_color=MUTED, text_font_style="bold")
          for hy, text in headers],
        hv.Segments(frame, [p10, "y", p90, "y1"], ["Colour"]).opts(color="Colour", line_width=4),
        hv.Scatter(frame.rename(columns={mean: "x"}), "x", ["y", "Design", "Colour"]).opts(
            color="Colour", size=8, line_color="white", tools=["hover"]),
        hv.Labels(frame.assign(x=frame[p90] + 12, text=frame[mean].map(lambda v: f"{v:,.0f}")), ["x", "y"], "text").opts(
            text_align="left", text_font_size="9pt", text_color=INK),
    ]).opts(width=560, height=600, title="Active validators after 180 days", xlabel="Mean and 10th to 90th percentile of 20 runs",
            ylabel="", yticks=ticks, ylim=lim, xlim=(800, 1640), show_legend=False, **STYLE)
    right = hv.Overlay([
        hv.Segments(frame, ["zero", "y", issued, "y1"], ["Colour"]).opts(color="Colour", line_width=11),
        hv.Labels(frame.assign(x=frame[issued] + 0.15, text=frame[issued].map(lambda v: f"{v:.2f}")), ["x", "y"], "text").opts(
            text_align="left", text_font_size="9pt", text_color=INK),
    ]).opts(width=WIDTH - 560, height=600, title="AVAX issued in 180 days", xlabel="Million AVAX", ylabel="",
            yticks=[(t, "") for t, _ in ticks], ylim=lim, xlim=(0, 7.2), show_legend=False, **STYLE)
    title = f"All five designs end far above the chain's actual {on_chain} validators after 180 days"
    layout = (left + right).cols(2).opts(shared_axes=False, toolbar=None, title=title)
    table = designs.copy()
    return save(layout, table, out, "designs-by-response",
                {"designs": results / "designs.csv", "runs receipt": results / RUNS_RECEIPT}, 600 + 30)


# Sensitivity tornado --------------------------------------------------------------------------------------------

def tornado_panel(part: pd.DataFrame, low: str, high: str, color: str, title: str, xlabel: str, ticks, show_ticks: bool,
                  xlim) -> hv.Overlay:
    layers = [hv.VLine(0).opts(color=INK, line_width=1)]
    layers.append(hv.Segments(([0.0] * len(part), part.y + 0.17, part[low], part.y + 0.17)).opts(
        color=color, alpha=0.4, line_width=13))
    layers.append(hv.Segments(([0.0] * len(part), part.y - 0.17, part[high], part.y - 0.17)).opts(
        color=color, line_width=13))
    pad = (xlim[1] - xlim[0]) * 0.012
    for _, r in part.iterrows():
        if r[low] == 0 and r[high] == 0:
            layers.append(hv.Text(pad, r.y, f"no change at {r['Low value']:.2g} or {r['High value']:.2g}", halign="left").opts(
                text_font_size="9pt", text_color=MUTED))
            continue
        for value, setting, dy in ((r[low], r["Low value"], 0.17), (r[high], r["High value"], -0.17)):
            value = 0.0 if abs(value) < 0.05 else value
            text = minus(f"{setting:.2g}: {value:+.1f}%") if value else f"{setting:.2g}: 0.0%"
            layers.append(hv.Text(value + pad if value >= 0 else value - pad, r.y + dy, text,
                                  halign="left" if value >= 0 else "right").opts(text_font_size="9pt", text_color=INK))
    return hv.Overlay(layers).opts(
        width=WIDTH // 2 + (80 if show_ticks else -80), height=250, title=title, xlabel=xlabel, ylabel="",
        yticks=ticks if show_ticks else [(t, "") for t, _ in ticks], ylim=(-0.6, len(part) - 0.4), xlim=xlim,
        show_legend=False, fontsize={"title": "10.5pt"}, **STYLE)


def chart_tornado(results: Path, out: Path) -> Path:
    """Which assumption moves the outcome most? One setting moved at a time from the Fortuna base."""
    tornado = pd.read_csv(results / "tornado.csv")
    acp = tornado[tornado.Design == ACP285]
    reach = (acp["Validators at high (% from base)"] - acp["Validators at low (% from base)"]).abs()
    order = list(acp.assign(reach=reach.to_numpy()).sort_values("reach").Setting)
    tornado["y"] = tornado.Setting.map({s: i for i, s in enumerate(order)})
    ticks = [(i, s) for i, s in enumerate(order)]
    v_lim, i_lim = (-68, 82), (-52, 55)
    panels = []
    for design in (CHAIN, ACP285):
        part = tornado[tornado.Design == design]
        base = part.iloc[0]
        color = DESIGN_COLORS[design]
        panels.append(tornado_panel(part, "Validators at low (% from base)", "Validators at high (% from base)", color,
                                    f"{design}: validators, base {base['Validators after 180 days at base']:,.0f}",
                                    "Change in validators after 180 days (%)", ticks, True, v_lim))
        panels.append(tornado_panel(part, "Issuance at low (% from base)", "Issuance at high (% from base)", color,
                                    f"AVAX issued, base {base['AVAX issued at base (M)']:.2f} M",
                                    "Change in AVAX issued in 180 days (%)", ticks, False, i_lim))
    top = order[-1]
    layout = hv.Layout(panels).cols(2).opts(
        shared_axes=False, toolbar=None,
        title=f"{top} moves the outcome most. The responses matter only when the reward changes")
    keep = tornado.drop(columns=["y"])
    return save(layout, keep, out, "sensitivity-tornado",
                {"tornado": results / "tornado.csv", "runs receipt": results / RUNS_RECEIPT}, 2 * 250 + 30)


CHARTS = {"fan": chart_fan, "spread": chart_spread, "designs": chart_designs, "tornado": chart_tornado}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results", type=Path, help="folder written by scripts/model_v07_report_runs.py")
    parser.add_argument("out", type=Path, help="folder for the charts")
    parser.add_argument("charts", nargs="*", metavar="CHART", help=f"any of {', '.join(CHARTS)}; all when none is named")
    args = parser.parse_args()
    unknown = sorted(set(args.charts) - set(CHARTS))
    if unknown:
        parser.error(f"unknown chart: {', '.join(unknown)}")
    hv.extension("bokeh")
    for name in args.charts or CHARTS:
        print(CHARTS[name](args.results, args.out))


if __name__ == "__main__":
    main()
