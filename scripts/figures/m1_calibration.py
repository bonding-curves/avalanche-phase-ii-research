"""Charts for deliverable 1.4, Behavioral Calibration: the v0.8 candidate's fitted behaviour with 95% intervals.

The inputs are calibrate.py's raw outputs, delivered unchanged in the ``results/`` folder beside the deliverable page.
calibrate.py was run on model code at commit ``1c891a4`` and the staking periods run ``staking-periods-2026-09-30``, at
origin 2025-11-18. Each chart answers one question and writes four files with one stem into the page folder: a PNG for
the page, an HTML for interaction, a CSV holding exactly the drawn data under readable column names, and a JSON receipt.
The receipt names every input in ``results/`` and every file the chart wrote, each with its sha256.

    uv run --group notebook python scripts/figures/m1_calibration.py            draw both charts
    uv run --group notebook python scripts/figures/m1_calibration.py --check    verify the delivered files

``--check`` recomputes every sha256 a receipt names and rebuilds each readable CSV from its input. It changes no file
and exits nonzero on any difference.

Charts and their inputs:

    terms     results/renewal-terms.csv    The renewal logit's eleven terms, with Laplace and node-bootstrap intervals
    hazard    results/return-hazard.csv    The daily return hazard in nine cells, with exact Poisson intervals
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

PAGE = Path(__file__).resolve().parents[2] / "content" / "Phase II" / "Milestones" / "Milestone 1" / "1-4 Behavioral Calibration"
RESULTS = "results"
PRODUCER = "calibrate.py"
WIDTH = 820
STYLE = {"fontscale": 1.1, "toolbar": None, "show_grid": True}
V08 = MODEL_COLORS["v0.8"]
NOTES = [
    "Each input is a file in results/, written unchanged by calibrate.py, which is kept beside the deliverable page.",
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


def write(chart, table: pd.DataFrame, page: Path, stem: str, inputs: dict[str, str], height: int) -> Path:
    """Save the chart as HTML and PNG and its table as CSV, then a receipt hashing the inputs, producer and outputs."""
    table.to_csv(page / f"{stem}.csv", index=False)
    hv.save(chart, page / f"{stem}.html")
    save_png(page / f"{stem}.html", page / f"{stem}.png", WIDTH + 40, height + 40)

    def entry(name: str) -> dict[str, str]:
        return {"file": name, "sha256": sha256(page / name)}

    receipt = {"chart": stem, "script": "scripts/figures/m1_calibration.py", "producer": entry(PRODUCER),
               "inputs": {key: entry(name) for key, name in inputs.items()},
               "outputs": [entry(f"{stem}.{ext}") for ext in ("csv", "png", "html")], "notes": NOTES}
    (page / f"{stem}.json").write_text(json.dumps(receipt, indent=1) + "\n")
    return page / f"{stem}.png"


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


def chart_terms(page: Path) -> Path:
    """Which features move renewal, and how sure is each? Log-odds terms against the baseline node, with intervals."""
    stem, inputs = CHARTS["terms"][:2]
    table = terms_table(pd.read_csv(page / inputs["terms"]))
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
    return write(chart, table, page, stem, inputs, 500)


def hazard_table(hazard: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in hazard.iterrows():
        band, period = r.cell.split("_", 1)
        rows.append({"Stake band": BANDS[band], "Days since the last commitment ended": PERIODS[period],
                     "Returns": int(r.returns), "Node-days at risk": int(r.node_days),
                     "Daily return probability (%)": round(100 * r.daily_hazard, 4),
                     "95% low (%)": round(100 * r.low, 4), "95% high (%)": round(100 * r.high, 4)})
    return pd.DataFrame(rows)


def chart_hazard(page: Path) -> Path:
    """How quickly do nodes that leave come back? The daily return probability by stake band and time out."""
    stem, inputs = CHARTS["hazard"][:2]
    table = hazard_table(pd.read_csv(page / inputs["hazard"]))
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
    return write(chart, table, page, stem, inputs, 420)


# Chart name: (file stem, inputs by name relative to the page folder, table builder, draw function).
CHARTS = {
    "terms": ("renewal-terms", {"terms": f"{RESULTS}/renewal-terms.csv"}, terms_table, chart_terms),
    "hazard": ("return-hazard", {"hazard": f"{RESULTS}/return-hazard.csv"}, hazard_table, chart_hazard),
}


def check(page: Path) -> list[str]:
    """Every difference between the delivered files and their receipts, as one line each. Prints one line per file."""
    problems = []
    for stem, inputs, build, _ in CHARTS.values():
        receipt = json.loads((page / f"{stem}.json").read_text())
        for key in ("producer", "inputs", "outputs"):
            if key not in receipt:
                problems.append(f"{stem}.json: no {key} recorded")
        named = [*filter(None, [receipt.get("producer")]), *receipt.get("inputs", {}).values(), *receipt.get("outputs", [])]
        if {key: item["file"] for key, item in receipt.get("inputs", {}).items()} != inputs:
            problems.append(f"{stem}.json: inputs {sorted(receipt['inputs'])} are not {inputs}")
        for item in named:
            path = page / item["file"]
            actual = sha256(path) if path.is_file() else "missing"
            status = "ok" if actual == item["sha256"] else "MISMATCH"
            print(f"{status:8} {stem}.json  {item['file']}  {actual[:16]}")
            if status != "ok":
                problems.append(f"{stem}.json: {item['file']} is {actual}, receipt says {item['sha256']}")
        (name,) = inputs.values()
        rebuilt = build(pd.read_csv(page / name)).to_csv(index=False)
        same = rebuilt == (page / f"{stem}.csv").read_text()
        print(f"{'ok' if same else 'MISMATCH':8} {stem}.csv  equals the table rebuilt from {name}")
        if not same:
            problems.append(f"{stem}.csv differs from the table rebuilt from {name}")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("charts", nargs="*", metavar="CHART",
                        help=f"charts to draw, from {', '.join(sorted(CHARTS))}; all when none is named")
    parser.add_argument("--page", type=Path, default=PAGE, help="the deliverable page folder (default: %(default)s)")
    parser.add_argument("--check", action="store_true", help="verify the receipts and readable CSVs, change nothing")
    args = parser.parse_args()
    if args.check:
        problems = check(args.page)
        print("\n".join(problems) if problems else "all receipts match the delivered files")
        sys.exit(1 if problems else 0)
    unknown = sorted(set(args.charts) - set(CHARTS))
    if unknown:
        parser.error(f"unknown chart {', '.join(unknown)}: choose from {', '.join(sorted(CHARTS))}")
    hv.extension("bokeh")
    for name in args.charts or sorted(CHARTS):
        print(CHARTS[name][3](args.page))


if __name__ == "__main__":
    main()
