#!/usr/bin/env python3
"""BENQI's share of delegated AVAX, daily, against all other delegators: the brief's GR5.

    uv run --group notebook python scripts/figures/benqi_delegation_share.py <output folder>

BENQI is the funding and stake-owning address avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy, named at tier AS1 by the
attribution rows OA9 and OA10 in data/operator-attributions.json. A delegation is BENQI's when the Snowflake share names
that address as its delegator (run `delegator-stakes-helicon-plus-7d`, to 2026-09-22 08:32 UTC) or, after the share stopped,
when the P-Chain walk names it as the stake owner (run `p-chain-blocks-2026-10-01`). Start, end and stake of every
delegation come from `staking-periods-2026-10-01`, accepted to 2026-10-01 02:28 UTC.

The days from Granite (2025-11-19 16:00 UTC) to Helicon's activation (2026-09-22 15:00 UTC) are held back for the model's
one-time out-of-sample test and are not drawn. Writes `benqi-delegation-share.csv`, `.html` and `.png`.
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
    days = days[(days < GRANITE) | (days >= HELICON)]
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
    before = frame[frame.day < GRANITE]
    after = frame[frame.day >= HELICON]
    line = {"color": "#1f5fa8", "line_width": 2}
    held = hv.VSpan(GRANITE, HELICON).opts(color="#dddddd", alpha=0.6)
    note = hv.Text(GRANITE - pd.Timedelta(days=15), 92, "Shaded: held back for the\nmodel's one-time test", halign="right", fontsize=12)
    return (held * hv.Curve(before, "day", "benqi_share_pct").opts(**line) * hv.Curve(after, "day", "benqi_share_pct").opts(**line)
            * hv.Scatter(after, "day", "benqi_share_pct").opts(color="#1f5fa8", size=6) * note).opts(
        width=1000, height=520, fontscale=1.2, toolbar=None, show_grid=True, ylim=(0, 100),
        title="Share of delegated AVAX held by BENQI's address (tier AS1), daily, against all other delegators",
        xlabel=f"Day, 00:00 UTC. Runs {PERIODS_RUN}, {SHARE_RUN}, {WALK_RUN}", xlim=(pd.Timestamp("2021-01-01"), pd.Timestamp("2026-10-15")),
        ylabel="BENQI's share of delegated AVAX (%)")


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    hv.extension("bokeh")
    frame = table()
    frame.to_csv(out / "benqi-delegation-share.csv", index=False)
    hv.save(chart(frame), out / "benqi-delegation-share.html")
    save_png(out / "benqi-delegation-share.html", out / "benqi-delegation-share.png", 1040, 580)
    shown = frame.set_index("day")
    print(shown.loc[[d for d in ("2022-01-01", "2023-01-01", "2024-01-01", "2025-01-01", "2025-11-19") if pd.Timestamp(d) in shown.index]].round(1).to_string())
    print(shown[shown.index >= HELICON].round(1).to_string())


if __name__ == "__main__":
    main()
