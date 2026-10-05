#!/usr/bin/env python3
"""Institutional validators and Helicon's two-day minimum: the two views of Eric's request A1 of 2026-10-02.

    uv run --group notebook python scripts/figures/helicon_institutional.py <output folder> [--from-csv]

View 1 asks whether institutional validators moved their two-week stake to two days. It takes every returning node whose
previous validator period lasted 14 to 30 days, the pre-Helicon minimum and just above it, and reads the duration of
the first cycle it started at or after Helicon's activation (2026-09-22 15:00 UTC). View 2 asks whether new institutional capital arrives at two days. It takes
every node that had never validated before activation and reads the duration of its first cycle. A cycle is a
transaction's first cycle, so an auto-renewal is not counted twice.

"Institutional" has two definitions, each drawn as its own bar and not merged:
- (a) the node's operator, its reward-address grouping in `operators-2026-10-04`, is named by a reward-address row at
  tier AS1 to AS3 with class EVIDENCE in `operator-attributions-2026-10-04`;
- (b) the cycle's own validator stake is at least 100,000 AVAX, delegations not counted.
Every other node is drawn as a third bar for comparison.

Cycles come from `helicon-commitments-2026-10-04`, snapshots to 2026-10-04 00:15 UTC. The delegation minimum stays 14
days after Helicon (ACP-273 lowers only the validator minimum), so the numbers file also counts BENQI's delegations since
activation by duration, from `staking-periods-2026-10-02` and the owner named in `p-chain-blocks-2026-10-02`, as in
`benqi_delegation_share.py`.

Writes `helicon-institutional-movers.csv`, `.html`, `.png`, `helicon-institutional-new.csv`, `.html`, `.png`, and
`helicon-institutional.json`. With `--from-csv`, the charts are redrawn from the CSVs already in the output folder.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import holoviews as hv
import pandas as pd

from avalanche_research import datasets

sys.path.insert(0, str(Path(__file__).resolve().parent))
from png import save_png

COMMITMENTS_RUN = "helicon-commitments-2026-10-04"
OPERATORS_RUN = "operators-2026-10-04"
ATTRIBUTIONS_RUN = "operator-attributions-2026-10-04"
PERIODS_RUN = "staking-periods-2026-10-02"
WALK_RUN = "p-chain-blocks-2026-10-02"
DATA_AS_OF = "2026-10-04 00:15 UTC"
ACTIVATION = pd.Timestamp("2026-09-22 15:00:00")
BENQI = "avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy"
LARGE_AVAX = 100_000
# The previous period of a two-week validator: at least the pre-Helicon minimum of 14 days, under 30.
PREVIOUS_DAYS = (14, 30)
TIERS = ("AS1", "AS2", "AS3")

GROUPS = (
    ("attributed", "(a) Attributed operators"),
    ("large", "(b) Own stake 100,000 AVAX or more"),
    ("other", "Every other validator"),
)
CLASSES = (("48h to 7d", 0, 7), ("7d to 14d", 7, 14), ("14d or longer", 14, 366))
COLORS = ["#d1495b", "#edae49", "#1f5fa8"]
DEFINITION_LINES = (
    "(a) The node's operator is named at tier AS1 to AS3 with class EVIDENCE in data/operator-attributions.json.",
    "(b) The cycle's own validator stake is at least 100,000 AVAX, delegations not counted.",
)
DEFINITIONS = " ".join(DEFINITION_LINES)
# Why bar (a) is empty: the three attributed operators and what each runs, from the numbers file of the same runs.
ATTRIBUTED_NOTE = ("(a) is empty: GoGoPool had 1 active node and the genesis holder none, and BENQI delegates, where the "
                   "minimum stays 14 days.")
VIEWS = {
    "movers": {
        "file": "helicon-institutional-movers",
        "title": "Did two-week validators move to two days? First cycle since Helicon of nodes whose previous period was 14 to 30 days",
        "ylabel": "Validator stake in first cycle since Helicon (million AVAX)",
    },
    "new": {
        "file": "helicon-institutional-new",
        "title": "Does new validator capital arrive at two days? First cycle of nodes new since Helicon",
        "ylabel": "Validator stake of new nodes (million AVAX)",
    },
}


def attributed_operators() -> pd.DataFrame:
    rows = datasets.load("derived.operator-attributions", run=ATTRIBUTIONS_RUN)
    named = rows[(rows.subject_kind == "reward-address") & rows.tier.isin(TIERS) & (rows["class"] == "EVIDENCE")]
    return named[["subject", "name", "tier", "attribution_id"]].drop_duplicates("subject").sort_values("subject")


def cycles() -> pd.DataFrame:
    frame = datasets.load("derived.helicon-commitments", run=COMMITMENTS_RUN)
    frame = frame[frame.cycle_number == 1].copy()
    operators = datasets.load("derived.operators", run=OPERATORS_RUN)[["node_id", "operator_id"]]
    frame = frame.merge(operators, on="node_id", how="left")
    frame["attributed"] = frame.operator_id.isin(set(attributed_operators().subject))
    frame["large"] = frame.stake_avax >= LARGE_AVAX
    frame["other"] = ~(frame.attributed | frame.large)
    frame["duration_class"] = pd.cut(frame.duration_days, [low for _, low, _ in CLASSES] + [CLASSES[-1][2]], right=False,
                                     labels=[name for name, _, _ in CLASSES]).astype(str)
    return frame


def summary(frame: pd.DataFrame, view: str) -> pd.DataFrame:
    rows = []
    for key, label in GROUPS:
        group = frame[frame[key]]
        total = group.stake_avax.sum()
        for name, _, _ in CLASSES:
            part = group[group.duration_class == name]
            rows.append({"view": view, "group": label, "duration": name, "cycles": len(part), "nodes": part.node_id.nunique(),
                         "stake_avax": round(float(part.stake_avax.sum()), 2),
                         "stake_share_pct": round(100 * float(part.stake_avax.sum()) / total, 2) if total else 0.0,
                         "group_cycles": len(group)})
    return pd.DataFrame(rows)


def benqi_delegations() -> dict:
    periods = datasets.parquet_path("derived.staking-periods", PERIODS_RUN)
    walk = datasets.parquet_path("p-chain-rpc.blocks", WALK_RUN)
    con = duckdb.connect()
    row = con.execute(
        "SELECT count(*), round(sum(stake_avax), 2), round(min(duration_days), 3), count(*) FILTER (WHERE duration_days < 14)"
        " FROM read_parquet(?) WHERE role = 'delegator' AND start_time >= ? AND transaction_hash IN ("
        "  SELECT transaction_hash FROM read_parquet(?) WHERE tx_type = 'AddPermissionlessDelegatorTx'"
        "  AND json_extract(unsigned_tx, '$.stake')::VARCHAR LIKE ?)",
        [str(periods), ACTIVATION.to_pydatetime(), str(walk), f"%{BENQI}%"]).fetchone()
    return {"runs": [PERIODS_RUN, WALK_RUN], "delegations": row[0], "stake_avax": row[1], "min_duration_days": row[2],
            "under_14_days": row[3]}


def tables() -> tuple[dict[str, pd.DataFrame], dict]:
    frame = cycles()
    movers = frame[(frame.node_status == "returning") & (frame.previous_duration_days >= PREVIOUS_DAYS[0]) & (frame.previous_duration_days < PREVIOUS_DAYS[1])]
    new = frame[frame.node_status == "new"]
    if frame.attributed.any():
        raise SystemExit("an attributed operator started a cycle: rewrite ATTRIBUTED_NOTE before drawing")
    out = {"movers": summary(movers, "movers"), "new": summary(new, "new")}
    operators = attributed_operators()
    active = datasets.load("derived.operators", run=OPERATORS_RUN)
    active = active[active.operator_id.isin(set(operators.subject))].groupby("operator_id").active.sum()
    numbers = {
        "runs": {"commitments": COMMITMENTS_RUN, "operators": OPERATORS_RUN, "attributions": ATTRIBUTIONS_RUN},
        "data_as_of": DATA_AS_OF,
        "activation": str(ACTIVATION),
        "definitions": DEFINITIONS,
        "attributed_operators": [{"attribution_id": r.attribution_id, "name": r.name, "tier": r.tier,
                                  "active_nodes_at_run": int(active.get(r.subject, 0))} for r in operators.itertuples()],
        "first_cycles_since_activation": len(frame),
        "movers_population": "returning nodes whose previous validator period lasted 14 to 30 days",
        "new_population": "nodes with no validator period before activation",
        "benqi_delegations_since_activation": benqi_delegations(),
    }
    for view, table in out.items():
        numbers[view] = {f"{g.group} | {g.duration}": {"cycles": int(g.cycles), "stake_avax": float(g.stake_avax),
                                                       "stake_share_pct": float(g.stake_share_pct)} for g in table.itertuples()}
    return out, numbers


def chart(table: pd.DataFrame, view: str) -> hv.Overlay:
    spec = VIEWS[view]
    data = table.assign(stake_m=table.stake_avax / 1e6)
    top = data.groupby("group", sort=False).stake_m.sum()
    bars = hv.Bars(data, ["group", "duration"], "stake_m").opts(
        stacked=True, cmap=COLORS, color="duration", show_legend=True, legend_position="top_right", toolbar=None,
        width=1100, height=560, fontscale=1.15, show_grid=True, ylim=(0, max(1.0, top.max() * 1.25)),
        title=spec["title"], ylabel=spec["ylabel"], xlabel="")
    counts = data.groupby("group", sort=False).group_cycles.first()
    shorts = data[data.duration == CLASSES[0][0]].set_index("group")
    labels = [hv.Text(group, top[group] + max(1.0, top.max() * 1.25) * 0.03,
                      f"{counts[group]} cycles, {int(shorts.loc[group, 'cycles'])} at 48h to 7d", fontsize=11).opts(color="#333333")
              for group in counts.index]

    def hook(plot, element):
        # The definitions print under the chart, one line each, in the order added.
        from bokeh.models import Title
        window = f"First cycle of each transaction started from Helicon's activation, 2026-09-22 15:00 UTC, to the snapshot of {DATA_AS_OF}."
        lines = (*DEFINITION_LINES, ATTRIBUTED_NOTE, window)
        for line in lines:
            plot.state.add_layout(Title(text=line, text_font_size="12px", text_font_style="normal", text_color="#444444"), "below")

    return (bars * hv.Overlay(labels)).opts(hooks=[hook])


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    hv.extension("bokeh")
    if "--from-csv" in sys.argv:
        frames = {view: pd.read_csv(out / f"{spec['file']}.csv") for view, spec in VIEWS.items()}
    else:
        frames, numbers = tables()
        for view, spec in VIEWS.items():
            frames[view].to_csv(out / f"{spec['file']}.csv", index=False)
        (out / "helicon-institutional.json").write_text(json.dumps(numbers, indent=1, sort_keys=True) + "\n")
    for view, spec in VIEWS.items():
        hv.save(chart(frames[view], view), out / f"{spec['file']}.html")
        save_png(out / f"{spec['file']}.html", out / f"{spec['file']}.png", 1140, 620)
        print(frames[view].to_string(index=False))


if __name__ == "__main__":
    main()
