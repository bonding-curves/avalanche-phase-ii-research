"""Charts for deliverable 1.4, Behavioral Calibration: the v0.8 candidate's fitted behaviour with 95% intervals.

Each chart answers one question and writes four files with one stem: a PNG for the page, an HTML for interaction, a
CSV holding exactly the drawn data under readable column names, and a JSON receipt naming every input with its sha256.

    uv run --group notebook python scripts/figures/m1_calibration.py CHART OUT_DIR --input NAME=PATH ...

Charts and their inputs:

    terms     terms=renewal-terms.csv     The renewal logit's eleven terms, with Laplace and node-bootstrap intervals
    hazard    hazard=return-hazard.csv    The daily return hazard in nine cells, with exact Poisson intervals

The input files are written by ``calibrate.py``, kept beside the deliverable page, run on model code at commit
``1c891a4`` and the staking periods run ``staking-periods-2026-09-30``, at origin 2025-11-18.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import holoviews as hv
import numpy as np
import pandas as pd

from avalanche_research.views.model_results import INK, MODEL_COLORS, MUTED

sys.path.insert(0, str(Path(__file__).parent))
from png import save_png

WIDTH = 820
STYLE = {"fontscale": 1.1, "toolbar": None, "show_grid": True}
V08 = MODEL_COLORS["v0.8"]
NOTES = [
    "Each input is the file of that name written by calibrate.py, which is kept beside the deliverable page.",
    "Fitted at origin 2025-11-18 on staking-periods-2026-09-30 with the v0.8 candidate's code at commit 1c891a4.",
    "Renewal: penalized logit on 14,977 endings by 2,968 nodes in the 365 days to seven days before the origin.",
    "Laplace interval: estimate plus or minus 1.96 standard errors from the inverse penalized Hessian.",
    "Node bootstrap interval: 2.5th to 97.5th percentile of 300 refits on nodes resampled with replacement.",
    "Return hazard: returns over node-days at risk per cell, exact Poisson (Garwood) 95% interval.",
]

# Display names for the renewal terms, in the order drawn from the top.
TERMS = {
    "tenure_2": ("Tenure", "Second commitment"),
    "tenure_3_6": ("Tenure", "Third to sixth commitment"),
    "tenure_7_9": ("Tenure", "Seventh to ninth commitment"),
    "tenure_10_plus": ("Tenure", "Tenth or later commitment"),
    "after_return": ("History", "Begun after a return"),
    "days_21_40": ("Duration", "21 to 40 days"),
    "days_41_100": ("Duration", "41 to 100 days"),
    "days_over_100": ("Duration", "Over 100 days"),
    "stake_2k_100k": ("Stake", "2,100 to 100,000 AVAX"),
    "stake_100k_1m": ("Stake", "100,000 to 1M AVAX"),
    "stake_over_1m": ("Stake", "Over 1M AVAX"),
}
BANDS = {"minimum": "Up to 2,100 AVAX", "mid": "2,100 to 100,000 AVAX", "large": "Over 100,000 AVAX"}
BAND_COLORS = {"minimum": "#62676f", "mid": "#237a57", "large": V08}
PERIODS = {"8_30": "8 to 30 days", "31_90": "31 to 90 days", "91_365": "91 to 365 days"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(chart, table: pd.DataFrame, out: Path, stem: str, inputs: dict[str, Path], height: int) -> Path:
    """Save the chart as HTML and PNG, its table as CSV, and a receipt of its inputs."""
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / f"{stem}.csv", index=False)
    hv.save(chart, out / f"{stem}.html")
    save_png(out / f"{stem}.html", out / f"{stem}.png", WIDTH + 40, height + 40)
    receipt = {"chart": stem, "script": "scripts/figures/m1_calibration.py",
               "inputs": {name: {"file": p.name, "sha256": sha256(p)} for name, p in inputs.items()}, "notes": NOTES}
    (out / f"{stem}.json").write_text(json.dumps(receipt, indent=1) + "\n")
    return out / f"{stem}.png"


def terms_table(terms: pd.DataFrame) -> pd.DataFrame:
    """One row per term, intercept first, with both intervals and the odds multiplier."""
    rows = []
    for _, r in terms.iterrows():
        group, name = ("Baseline", "Intercept: first commitment, 20 days or less, up to 2,100 AVAX") if r.term == "intercept" \
            else TERMS[r.term]
        rows.append({
            "Group": group, "Term": name, "Estimate (log-odds)": round(r.estimate, 3),
            "Laplace 95% low": round(r.laplace_low, 3), "Laplace 95% high": round(r.laplace_high, 3),
            "Node bootstrap 95% low": round(r.bootstrap_low, 3), "Node bootstrap 95% high": round(r.bootstrap_high, 3),
            "Odds multiplier": round(float(np.exp(r.estimate)), 2),
            "Bootstrap width over Laplace width": round(r.bootstrap_over_laplace_width, 2)})
    return pd.DataFrame(rows)


def chart_terms(inputs: dict[str, Path], out: Path) -> Path:
    """Which features move renewal, and how sure is each? Log-odds terms against the baseline node, with intervals."""
    table = terms_table(pd.read_csv(inputs["terms"]))
    drawn = table[table.Group != "Baseline"].reset_index(drop=True)
    n = len(drawn)
    drawn["y"] = [n - 1 - i for i in range(n)]
    labels = [(int(y), f"{g}: {t}") for y, g, t in zip(drawn.y, drawn.Group, drawn.Term)]
    up = 0.14
    boot = hv.Segments((drawn["Node bootstrap 95% low"], drawn.y + up, drawn["Node bootstrap 95% high"], drawn.y + up)).opts(
        color=V08, line_width=7, alpha=0.35)
    lap = hv.Segments((drawn["Laplace 95% low"], drawn.y - up, drawn["Laplace 95% high"], drawn.y - up)).opts(
        color=INK, line_width=2)
    points = hv.Scatter(drawn, "Estimate (log-odds)", ["y", "Term", "Node bootstrap 95% low", "Node bootstrap 95% high"]).opts(
        color=V08, size=11, tools=["hover"])
    zero = hv.VLine(0).opts(color=MUTED, line_width=1.2, line_dash="dashed")
    rules = [hv.HLine(b).opts(color="#d5d8dc", line_width=1) for b in (6.5, 5.5, 2.5)]
    key = hv.Text(-1.75, n - 0.35, "●  estimate     ▬  node bootstrap 95%     ─  Laplace 95%", halign="left").opts(
        text_font_size="10pt", text_color=INK)
    lower = hv.Text(-1.75, -0.9, "← less likely to renew", halign="left").opts(text_font_size="9.5pt", text_color=MUTED)
    higher = hv.Text(2.15, -0.9, "more likely to renew →", halign="right").opts(text_font_size="9.5pt", text_color=MUTED)
    chart = hv.Overlay([zero, *rules, boot, lap, points, key, lower, higher]).opts(
        width=WIDTH, height=500, title="Tenure moves renewal most, and a return after a gap lowers it",
        xlabel="Change in the log-odds of renewing within 7 days, against the baseline node", ylabel="",
        yticks=labels, ylim=(-1.4, n + 0.1), xlim=(-1.8, 2.2), show_legend=False, **STYLE)
    return write(chart, table, out, "renewal-terms", inputs, 500)


def hazard_table(hazard: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in hazard.iterrows():
        band, period = r.cell.split("_", 1)
        rows.append({"Stake band": BANDS[band], "Days since the last commitment ended": PERIODS[period],
                     "Returns": int(r.returns), "Node-days at risk": int(r.node_days),
                     "Daily return probability (%)": round(100 * r.daily_hazard, 4),
                     "95% low (%)": round(100 * r.low, 4), "95% high (%)": round(100 * r.high, 4)})
    return pd.DataFrame(rows)


def chart_hazard(inputs: dict[str, Path], out: Path) -> Path:
    """How quickly do nodes that leave come back? The daily return probability by stake band and time out."""
    raw = pd.read_csv(inputs["hazard"])
    table = hazard_table(raw)
    layers = []
    offsets = {"minimum": -0.12, "mid": 0.0, "large": 0.12}
    for band, label in BANDS.items():
        part = table[table["Stake band"] == label].copy()
        part["x"] = [i + offsets[band] for i in range(len(part))]
        color = BAND_COLORS[band]
        layers.append(hv.Curve(part, "x", "Daily return probability (%)").opts(color=color, line_width=1.5, alpha=0.6))
        layers.append(hv.Segments((part.x, part["95% low (%)"], part.x, part["95% high (%)"])).opts(color=color, line_width=3))
        layers.append(hv.Scatter(part, "x", ["Daily return probability (%)", "Stake band", "Returns", "Node-days at risk"]).opts(
            color=color, size=10, tools=["hover"]))
        last = part.iloc[-1]
        layers.append(hv.Text(2.22, float(last["Daily return probability (%)"]), label, halign="left").opts(
            text_color=color, text_font_size="10pt", text_font_style="bold"))
    layers.append(hv.Text(-0.25, 0.0045, "Vertical bars: exact Poisson 95% intervals", halign="left").opts(
        text_font_size="9.5pt", text_color=MUTED))
    chart = hv.Overlay(layers).opts(
        width=WIDTH, height=420, title="A node that leaves returns most often in its first month out, rarely after 90 days",
        xlabel="Days since the node's last commitment ended", ylabel="Daily probability of returning (%), log scale",
        logy=True, ylim=(0.003, 5), xlim=(-0.35, 3.25), xticks=[(i, p) for i, p in enumerate(PERIODS.values())],
        yticks=[(v, f"{v:g}") for v in (0.005, 0.01, 0.05, 0.1, 0.5, 1, 2, 5)], show_legend=False, **STYLE)
    return write(chart, table, out, "return-hazard", inputs, 420)


CHARTS = {"terms": chart_terms, "hazard": chart_hazard}


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
