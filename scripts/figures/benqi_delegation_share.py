#!/usr/bin/env python3
"""BENQI's share of delegated AVAX, daily, against all other delegators: the brief's GR5.

    uv run --group notebook python scripts/figures/benqi_delegation_share.py <output folder> [--from-csv]

BENQI is the funding and stake-owning address avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy, named at tier AS1 by the
attribution rows OA9 and OA10 in data/operator-attributions.json. A delegation is BENQI's when the Snowflake share names
that address as its delegator (run `delegator-stakes-helicon-plus-7d`, to 2026-09-22 08:32 UTC) or, after the share stopped,
when the P-Chain walk names it as the stake owner (run `p-chain-blocks-2026-10-01`). Start, end and stake of every
delegation come from `staking-periods-2026-10-01`, accepted to 2026-10-01 02:28 UTC.

Every day is drawn, including Granite to Helicon, on Shawn's decision of 2026-10-02 that people may review all data and
only the model's fitting and selection are held back. Helicon's activation is marked. Writes `benqi-delegation-share.csv`, `.html` and `.png`. With
`--from-csv`, the chart is redrawn from the CSV already in the output folder, without reading the runs again.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import holoviews as hv
import numpy as np
import pandas as pd

from avalanche_research import datasets

sys.path.insert(0, str(Path(__file__).resolve().parent))
from png import save_png

BENQI = "avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy"
PERIODS_RUN = "staking-periods-2026-10-01"
SHARE_RUN = "delegator-stakes-helicon-plus-7d"
WALK_RUN = "p-chain-blocks-2026-10-01"
GRANITE = pd.Timestamp("2025-11-19 16:00:00")
HELICON = pd.Timestamp("2026-09-22 15:00:00")
LAST_DAY = pd.Timestamp("2026-10-01")


def benqi_transactions() -> set[str]:
    share = datasets.parquet_path("snowflake.primary-delegator-stakes", SHARE_RUN)
    walk = datasets.parquet_path("p-chain-rpc.blocks", WALK_RUN)
    con = duckdb.connect()
    from_share = con.execute("SELECT transaction_hash FROM read_parquet(?) WHERE delegator_address = ?", [str(share), BENQI]).fetchall()
    from_walk = con.execute(
        "SELECT transaction_hash FROM read_parquet(?) WHERE tx_type = 'AddPermissionlessDelegatorTx'"
        " AND json_extract(unsigned_tx, '$.stake')::VARCHAR LIKE ?", [str(walk), f"%{BENQI}%"]).fetchall()
    return {row[0] for row in from_share} | {row[0] for row in from_walk}


def table() -> pd.DataFrame:
    periods = datasets.load("derived.staking-periods", run=PERIODS_RUN)
    delegations = periods[periods.role == "delegator"][["transaction_hash", "start_time", "end_time", "stake_avax"]].copy()
    delegations["benqi"] = delegations.transaction_hash.isin(benqi_transactions())
    days = pd.date_range("2021-01-01", LAST_DAY, freq="D")
    rows = {"day": days}
    for name, part in (("benqi", delegations[delegations.benqi]), ("others", delegations[~delegations.benqi])):
        starts = np.sort(part.start_time.values)
        ends = np.sort(part.end_time.values)
        stake_by_start = part.sort_values("start_time").stake_avax.cumsum().values
        stake_by_end = part.sort_values("end_time").stake_avax.cumsum().values
        started = np.searchsorted(starts, days.values, side="right")
        ended = np.searchsorted(ends, days.values, side="right")
        active = np.where(started > 0, stake_by_start[np.maximum(started - 1, 0)], 0.0) - np.where(ended > 0, stake_by_end[np.maximum(ended - 1, 0)], 0.0)
        rows[f"{name}_avax"] = active
    frame = pd.DataFrame(rows)
    frame["benqi_share_pct"] = 100 * frame.benqi_avax / (frame.benqi_avax + frame.others_avax)
    return frame


def chart(frame: pd.DataFrame) -> hv.Overlay:
    line = {"color": "#1f5fa8", "line_width": 2}
    marks = [hv.VLine(day).opts(color="#888888", line_dash="dotted") for day in (GRANITE, HELICON)]
    labels = [hv.Text(day - pd.Timedelta(days=10), 95, name, halign="right", fontsize=11).opts(color="#555555")
              for day, name in ((GRANITE, "Granite"), (HELICON, "Helicon"))]
    return (hv.Curve(frame, "day", "benqi_share_pct").opts(**line) * hv.Overlay(marks) * hv.Overlay(labels)).opts(
        width=1000, height=520, fontscale=1.2, toolbar=None, show_grid=True, ylim=(0, 100),
        title="Share of delegated AVAX held by BENQI's address, daily, against all other delegators",
        xlabel="Day, 00:00 UTC. Data as of 2026-10-01 02:28 UTC", xlim=(pd.Timestamp("2021-01-01"), pd.Timestamp("2026-10-15")),
        ylabel="BENQI's share of delegated AVAX (%)")


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    hv.extension("bokeh")
    if "--from-csv" in sys.argv:
        frame = pd.read_csv(out / "benqi-delegation-share.csv", parse_dates=["day"])
    else:
        frame = table()
        frame.to_csv(out / "benqi-delegation-share.csv", index=False)
    hv.save(chart(frame), out / "benqi-delegation-share.html")
    save_png(out / "benqi-delegation-share.html", out / "benqi-delegation-share.png", 1040, 580)
    shown = frame.set_index("day")
    print(shown.loc[[d for d in ("2022-01-01", "2023-01-01", "2024-01-01", "2025-01-01", "2025-11-19", "2026-03-01", "2026-06-01", "2026-09-21") if pd.Timestamp(d) in shown.index]].round(1).to_string())
    print(shown[shown.index >= HELICON].round(1).to_string())


if __name__ == "__main__":
    main()
