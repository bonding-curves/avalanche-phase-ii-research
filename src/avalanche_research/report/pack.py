"""The standard output pack: every PSuU output of one sweep in one folder, listed on an index page.

`build` scores the sweep once and writes:

- `tables/` and `figures/`: the PSuU tables and the overview, response, importance and pass-rate figures (`psuu`);
- `figures/heatmap-*`: utility heat maps (`heatmaps`);
- `figures/tree-*` with `tables/tree-*.csv`: decision trees per goal and per KPI (`trees`);
- `figures/grid-*`: each input against each KPI (`grid`);
- `recommendations/`: recommendation tables and the sign-and-confidence matrix, as Markdown and CSV (`recommend`);
- `index.md`, which lists every output with the finding in its title, and `pack-receipt.json` with input hashes.

Every figure is written as PNG and SVG. The new figures carry a CSV of the data they draw.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import grid, heatmaps, psuu, recommend, trees
from .style import family_label, feature_label, feature_value, fmt_horizon

TABLE_NOTES = {
    "trajectory-utilities.parquet": "Every analysed run with its metric values, passes, utilities and goal scores.",
    "summary-goals.csv": "Utility and pass rate of each goal, by horizon, design and scenario.",
    "summary-metrics.csv": "Value, utility and pass rate of each KPI, by horizon, design and scenario.",
    "regions.csv": "Best cell, highest-utility region and all-goal region of each design's settings.",
    "region-cells.csv": "Every setting cell with its runs, utilities and pass rates.",
    "forest-fit.csv": "Random forest fit to each goal utility: out-of-bag and held-out R².",
    "forest-importance.csv": "Permutation importance of each input in each forest.",
    "response-curves.csv": "Binned run means and forest partial dependence for each input and goal.",
    "tree-fit.csv": "Each decision tree's out-of-fold accuracy, balanced accuracy and majority-class accuracy.",
    "tree-importance.csv": "Out-of-fold permutation importance of each tree input.",
    "tree-leaves.csv": "Each leaf of each drawn tree: its conditions, runs and pass share.",
}


def details(scored):
    """The simulation details table: runs per design and horizon, and the values each input took."""
    runs, layout = scored.runs, scored.layout
    counts = runs.groupby([layout["horizon"], layout["family"]]).size()
    lines = ["| Horizon | Design | Runs analysed |", "| --- | --- | --- |"]
    lines += [f"| {fmt_horizon(h)} | {family_label(f)} | {n:,} |" for (h, f), n in counts.items()]
    lines += ["", "| Input | Role | Values swept |", "| --- | --- | --- |"]
    for role, names in (("setting", layout["parameters"]), ("validator response", layout["behaviour"]),
                        ("scenario", layout["scenarios"])):
        for c in names:
            fams = runs.groupby(layout["family"])[c].nunique()
            fams = fams[fams > 1].index if role == "setting" else fams[fams > 0].index
            col = runs.loc[runs[layout["family"]].isin(fams), c].dropna()
            if col.empty:
                continue
            uniq = sorted(col.unique(), key=lambda v: (isinstance(v, str), v))
            if col.dtype == object or len(uniq) <= 8:
                values = ", ".join(feature_value(c, v) for v in uniq)
            else:
                values = f"{feature_value(c, col.min())} to {feature_value(c, col.max())}, {len(uniq):,} values"
            used = ", ".join(family_label(f) for f in sorted(fams))
            lines.append(f"| {feature_label(c)} | {role}, {used} | {values} |")
    return "\n".join(lines)


def figure_list(folder: Path, titles: dict, prefix: str = "figures/"):
    lines = []
    for name, title in titles.items():
        extra = [f"[SVG]({prefix}{name}.svg)"]
        if (folder / f"{name}.csv").exists():
            extra.append(f"[data]({prefix}{name}.csv)")
        lines.append(f"1. [{title}]({prefix}{name}.png) ({', '.join(extra)})")
    return "\n".join(lines) if lines else "None drawn."


def index_page(out: Path, scored, version, sections, receipt):
    inputs = scored.inputs
    spec = scored.spec
    head = [f"# PSuU output pack{f' for model {version}' if version else ''}", "",
            "Parameter selection under uncertainty, PSuU, scores every run of a sweep against declared goals and asks "
            "which settings of each reward design keep the goals met across scenarios. This page lists every output "
            "of the pack. Each figure title states its finding.", "",
            "| Input | File | SHA-256 |", "| --- | --- | --- |",
            f"| Sweep wide table | `{Path(inputs['wide']).name}` | `{inputs['wide_sha256'][:16]}` |",
            f"| Sweep manifest | `{Path(inputs['manifest']).name}` | `{inputs['manifest_sha256'][:16]}` |",
            f"| Utility specification `{spec.get('name')}` | `{Path(inputs['spec']).name}` | "
            f"`{inputs['spec_sha256'][:16]}` |", "",
            f"Built in {receipt['seconds']:.0f} s. Goals: "
            + "; ".join(f"{g['id']} {g['name']}" for g in spec["goals"]) + ".", "",
            "## Simulation details", "", details(scored), ""]
    body = []
    for heading, text, items in sections:
        body += [f"## {heading}", "", text, "", items, ""]
    (out / "index.md").write_text("\n".join(head + body))


def build(wide, manifest, spec, out, version=None, trees_n=300, repeats=10, jobs=8, seed=20261027,
          sample=grid.SAMPLE, log=print):
    started = time.time()
    out = Path(out).expanduser()
    figures, tables = out / "figures", out / "tables"
    scored = psuu.load_scored(wide, manifest, spec, log=log)
    made = psuu.run(scored, out, trees_n, repeats, jobs, seed, log)
    heat = heatmaps.draw_all(scored, figures, log)
    fit, imp, leaves, tree_titles = trees.fit_all(scored, figures, seed, log)
    fit.to_csv(tables / "tree-fit.csv", index=False)
    imp.to_csv(tables / "tree-importance.csv", index=False)
    leaves.to_csv(tables / "tree-leaves.csv", index=False)
    grids = grid.draw_all(scored, figures, sample, seed, log)
    recommend.write_all(scored, out / "recommendations", seed, log)

    receipt = {"version": version, **scored.inputs, "rows_analysed": len(scored.runs), "seed": seed,
               "forest_trees": trees_n, "permutation_repeats": repeats, "grid_sample_per_design": sample,
               "figures": {**made["titles"], **heat, **tree_titles, **grids}, "seconds": round(time.time() - started, 1)}
    (out / "pack-receipt.json").write_text(json.dumps(receipt, indent=2, default=str) + "\n")

    fitted = fit[fit.status == "fitted"] if not fit.empty else fit
    tree_note = ("Depth-three classification trees from each design's settings and the scenario to whether a run "
                 "passes each goal, every goal and each KPI. They describe and make no causal claim. Accuracy is out of "
                 "fold, five folds grouped by shared draws, beside the accuracy of always predicting the larger class.")
    if not fitted.empty:
        better = int((fitted.oof_accuracy > fitted.majority_accuracy + 0.005).sum())
        tree_note += (f" {better} of {len(fitted)} fitted trees beat that baseline out of fold. Targets where every "
                      "run passes or none does have no tree and are listed in `tables/tree-fit.csv`.")
    tables_list = "\n".join(f"1. [`{name}`](tables/{name}): {note}" for name, note in TABLE_NOTES.items()
                            if (tables / name).exists())
    sections = [
        ("PSuU scoring", "Goal and KPI utilities for every run, random forests, response curves and regions.",
         figure_list(figures, made["titles"])),
        ("Utility heat maps", "Each goal's mean utility and the combined utility over cells of each design's settings: "
         "sorted cells, each setting against each scenario, and each pair of settings.", figure_list(figures, heat)),
        ("Decision trees", tree_note, figure_list(figures, tree_titles)),
        ("Inputs against KPIs", f"Each input against each KPI. Points are a seeded sample of at most {sample} runs "
         "per design. Lines and bands use every run.", figure_list(figures, grids)),
        ("Recommendations", "Computed from the setting cells, with confidence, as Markdown and CSV.",
         "1. [Recommendation tables](recommendations/recommendations.md) ([CSV](recommendations/recommendations.csv)): "
         "point estimate, a range per goal and the range for every goal, by design and scenario.\n"
         "1. [Sign and confidence matrix](recommendations/sign-confidence.md) "
         "([CSV](recommendations/sign-confidence.csv)): each input against each KPI and goal."),
        ("Tables", "Every table the pack writes.", tables_list),
    ]
    index_page(out, scored, version, sections, receipt)
    log(f"pack written to {out} in {receipt['seconds']} s")
    return receipt
