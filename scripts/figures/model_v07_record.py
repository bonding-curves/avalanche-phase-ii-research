"""Charts of the staking record and of model v0.7's protocol layer and inputs, for the v0.7 research report.

Each chart answers one question and writes four files with one stem: a PNG for the page, an HTML for interaction, a
CSV holding exactly the drawn data under readable column names, and a JSON receipt naming the pinned runs and every
other input with its sha256.

    uv run --group notebook python scripts/figures/model_v07_record.py CHART OUT_DIR [--input renewal=PATH]

Charts:

    record      The staking record: validator stake, delegated stake and active validators by day, with upgrade eras
    monthly     Validator commitments started each month, renewals against new commitments
    inputs      Renewal share and entry rate v0.7 assumed at each development origin, against what followed
    kernel      Share of recorded potential rewards the reward formula reproduces, by role and start kind
    replay      Validator stake recorded on the ledger against the replay, and their daily difference in nAVAX
    designs     Annual reward rate by committed duration for each reward design, and AVAX each mints for one cohort
    tenure      Renewal within seven days by the node's number of commitments, against v0.7's single probability
    all         Every chart above

Inputs are the two runs of pin ``p2-model-v0.8``, read through ``avalanche_research.datasets``:
``staking-periods-2026-09-30`` and ``avax-monetary-daily-2026-09-30``. The script refuses to run if either file no
longer matches its pinned sha256. ``--input renewal=renewal-scores.csv``, the output of
``scripts/renewal_block_scores.py``, is optional: when given, the inputs chart checks its own renewal numbers against
that file and names it in the receipt.

Model v0.7 is tag ``model-v0.7.0``. The functions this script calls (the reward formula, the replay, the reward
designs and ``origin_inputs``) compute the same values in the current library as at the tag: since the tag the
protocol module has moved and been reformatted, and the engine keeps non-integer state in its own column, which does
not touch any value drawn here.

Model fitting and selection stop at 2025-11-19 16:00 UTC, the start of the held-back period. Later data appear only in
the record and kernel charts, drawn in a distinct style and labelled as description.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import holoviews as hv
import numpy as np
import pandas as pd

from avalanche_research import datasets
from avalanche_research.datasets import pins
from avalanche_research.mechanisms import (
    ACP285Ramp,
    ChainReward,
    QuadraticReward,
    TenureBoost,
)
from avalanche_research.mechanisms.cohort import group_stakes, load_periods
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_lifecycle import renewal_endings, validator_periods
from avalanche_research.model.lifecycle import origin_inputs
from avalanche_research.model.replay import Replay, compare, daily_events
from avalanche_research.palette import MECHANISM_COLORS, QUANTITY_COLORS
from avalanche_research.staking_cohorts import NETWORK_START, _era_intervals
from avalanche_research.views.mechanism_explorer import issuance_table
from avalanche_research.views.model_results import INK, MUTED

sys.path.insert(0, str(Path(__file__).parent))
from model_v07_report import STYLE, V07, WIDTH, write

PIN = "p2-model-v0.8"
RUN = "staking-periods-2026-09-30"
LEDGER = "avax-monetary-daily-2026-09-30"
TAG = "model-v0.7.0"
HELD_BACK = pd.Timestamp("2025-11-19 16:00")
HELICON = pd.Timestamp("2026-09-22 15:00")
US_PER_DAY = 86_400_000_000
INSTANT_US = 86_399_000_000
FOLLOW_US = 7 * US_PER_DAY
HELD_BACK_US = int(HELD_BACK.tz_localize("UTC").timestamp() * 1_000_000)
LAST_LABELLED_US = HELD_BACK_US - FOLLOW_US - 1
UPGRADES = {"Banff": date(2022, 10, 18), "Cortina": date(2023, 4, 25), "Durango": date(2024, 3, 6),
            "Etna": date(2024, 12, 16), "Fortuna": date(2025, 4, 8)}
QUARTERS = {f"{y}-{m:02d}-01": date(y, m, 1) for y in (2022, 2023, 2024, 2025) for m in (1, 4, 7, 10)
            if date(2022, 7, 1) <= date(y, m, 1) <= date(2025, 10, 1)}
STAKE = QUANTITY_COLORS["stake"]
NODES = QUANTITY_COLORS["nodes"]
REWARDS = QUANTITY_COLORS["rewards"]
COMMITMENTS = QUANTITY_COLORS["commitments"]
ACTUAL = "#222222"
ERA_SHADE = "#eeeeee"
HELD_SHADE = "#f6ead8"
HELD_TEXT = "#8a5a1c"
HELD_LABEL = "Held back from model fitting: description only"


# Inputs and receipts ---------------------------------------------------------------------------------------------

def periods_path() -> str:
    return str(datasets.parquet_path("derived.staking-periods", RUN))


def ledger_path() -> str:
    return str(datasets.parquet_path("derived.avax-monetary-daily", LEDGER))


def check_pin() -> dict:
    """The pin's entries for the two runs, after checking that both files still match their pinned sha256."""
    path = pins.PINS / f"{PIN}.json"
    named = pins.runs(path)
    if named.get("derived.staking-periods") != RUN or named.get("derived.avax-monetary-daily") != LEDGER:
        raise SystemExit(f"pin {PIN} no longer names {RUN} and {LEDGER}")
    findings = pins.verify(path)
    if findings:
        raise SystemExit("pinned runs do not match: " + "; ".join(findings))
    return {"pin": PIN, "runs": [{k: e[k] for k in ("dataset_id", "run", "sha256")} for e in pins.read(path)["runs"]]}


def client_commit() -> str:
    found = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=Path(__file__).parent, check=False)
    return found.stdout.strip() or "unknown"


def save(chart, table: pd.DataFrame, out: Path, stem: str, height: int, notes: list[str],
         inputs: dict[str, Path] | None = None) -> Path:
    """Write the chart with the shared writer, then complete its receipt with the pinned runs, the code and notes."""
    png = write(chart, table, out, stem, inputs or {}, height)
    receipt = json.loads((out / f"{stem}.json").read_text())
    receipt["script"] = "scripts/figures/model_v07_record.py"
    receipt["pinned_runs"] = PINNED
    receipt["code"] = {"client_commit": client_commit(), "model": f"v0.7, tag {TAG}",
                       "equivalence": "The library functions called here compute the same values as at the tag"}
    receipt["held_back_from"] = "2025-11-19 16:00 UTC"
    receipt["notes"] = notes
    (out / f"{stem}.json").write_text(json.dumps(receipt, indent=1) + "\n")
    return png


PINNED: dict = {}


def era_layers(start: pd.Timestamp, end: pd.Timestamp, label_y: float | None, size: str = "9.5pt") -> list:
    """Alternate grey bands for the upgrade eras before the held-back period, and their names."""
    layers, texts = [], []
    for index, (era, a, b) in enumerate(_era_intervals(start, end)):
        name = era.capitalize()
        if index % 2 and a < HELD_BACK:
            layers.append(hv.VSpan(a, min(b, HELD_BACK)).opts(color=ERA_SHADE, line_alpha=0))
        if label_y is not None and era != "helicon":
            middle = a + (b - a) / 2
            texts.append(hv.Text(middle, label_y, name).opts(text_font_size=size, text_color=MUTED))
    return layers + texts


def held_back_band(end: pd.Timestamp) -> hv.VSpan:
    return hv.VSpan(HELD_BACK, end).opts(color=HELD_SHADE, line_alpha=0)


# C1: the staking record ------------------------------------------------------------------------------------------

def record_table() -> pd.DataFrame:
    ledger = duckdb.execute(
        """SELECT date_utc, complete, active_validator_stake_wei::DOUBLE / 1e24 AS v, active_delegated_stake_wei::DOUBLE / 1e24 AS d,
                  active_validators AS n FROM read_parquet(?) ORDER BY date_utc""", [ledger_path()]).df()
    held = pd.to_datetime(ledger.date_utc) >= HELD_BACK.normalize()
    return pd.DataFrame({
        "Date (UTC)": pd.to_datetime(ledger.date_utc).dt.date.astype(str),
        "Validator stake (M AVAX)": ledger.v.round(3), "Delegated stake (M AVAX)": ledger.d.round(3),
        "Active validators": ledger.n, "Day complete": ledger.complete,
        "Part of the record": np.where(held, "Held back from model fitting", "Before the held-back period")})


def chart_record(out: Path) -> Path:
    """What does the staking record look like, and where are the upgrades, the held-back period and Helicon?"""
    table = record_table()
    frame = table[table["Day complete"]].copy()
    frame["When"] = pd.to_datetime(frame["Date (UTC)"])
    end = frame.When.max() + pd.Timedelta(days=1)
    before = frame[frame.When < HELD_BACK.normalize()]
    after = frame[frame.When >= HELD_BACK.normalize() - pd.Timedelta(days=1)]
    top_max = float(frame[["Validator stake (M AVAX)", "Delegated stake (M AVAX)"]].max().max()) * 1.18

    def lines(column: str, color: str, width: float) -> list:
        return [hv.Curve(before, "When", [column, "Date (UTC)"]).opts(color=color, line_width=width, tools=["hover"]),
                hv.Curve(after, "When", [column, "Date (UTC)"]).opts(color=color, line_width=width, line_dash="dotted",
                                                                     alpha=0.85, tools=["hover"])]

    peak = before.loc[before["Active validators"].idxmax()]
    last = before.iloc[-1]
    stake_layers = [*era_layers(NETWORK_START, end, top_max * 0.95), held_back_band(end),
                    *lines("Validator stake (M AVAX)", STAKE, 2.6), *lines("Delegated stake (M AVAX)", STAKE, 1.4),
                    hv.Text(pd.Timestamp("2021-07-01"), 148, "Validator stake", halign="left").opts(
                        text_font_size="10pt", text_color=STAKE, text_font_style="bold"),
                    hv.Text(pd.Timestamp("2022-03-01"), 62, "Delegated stake", halign="left").opts(
                        text_font_size="10pt", text_color=STAKE),
                    hv.Text(HELD_BACK + pd.Timedelta(days=10), top_max * 0.89, "Held back from\nmodel fitting",
                            halign="left", valign="top").opts(text_font_size="9pt", text_color=HELD_TEXT),
                    hv.VLine(HELICON).opts(color=INK, line_width=1.2, line_dash="dashed")]
    stake = hv.Overlay(stake_layers).opts(
        width=WIDTH, height=330, title=f"Active validators fell from {peak['Active validators']:,} in "
        f"{pd.Timestamp(peak.When):%B %Y} to {last['Active validators']:,} before the held-back period",
        xlabel="", ylabel="Stake (M AVAX)", ylim=(0, top_max), xlim=(NETWORK_START, end), show_legend=False, **STYLE)
    n_max = float(frame["Active validators"].max()) * 1.15
    count_layers = [*era_layers(NETWORK_START, end, None), held_back_band(end),
                    *lines("Active validators", NODES, 2.2),
                    hv.Text(pd.Timestamp("2022-10-20"), 1560, "Active validators", halign="left").opts(
                        text_font_size="10pt", text_color=NODES, text_font_style="bold"),
                    hv.VLine(HELICON).opts(color=INK, line_width=1.2, line_dash="dashed"),
                    hv.Text(HELICON - pd.Timedelta(days=6), n_max * 0.86, "Helicon, 22 Sep 2026", halign="right").opts(
                        text_font_size="9pt", text_color=INK)]
    count = hv.Overlay(count_layers).opts(
        width=WIDTH, height=230, title="", xlabel="Date (UTC)", ylabel="Active validators", ylim=(0, n_max),
        xlim=(NETWORK_START, end), show_legend=False, **STYLE)
    layout = (stake + count).cols(1).opts(shared_axes=False, toolbar=None)
    notes = [f"Daily values at 23:59:59 UTC from {LEDGER}, complete days only ({int(table['Day complete'].sum())} of {len(table)}).",
             "Days from 2025-11-19 are drawn dotted on a shaded band: they are after the held-back boundary and are shown as description."]
    return save(layout, table, out, "staking-record", 330 + 230 - 20, notes)


# C2: commitments started each month ------------------------------------------------------------------------------

def commitment_starts() -> pd.DataFrame:
    """Every validator commitment, with whether it is a renewal: the same node starting again within seven days of the
    end of its previous commitment, as ``origin_inputs`` counts renewals."""
    rows = duckdb.execute(
        """SELECT node_id, start_time, stake_navax, epoch_us(start_time) AS s,
                  lag(epoch_us(end_time)) OVER (PARTITION BY node_id ORDER BY start_time, transaction_hash) AS prev_e
           FROM read_parquet(?) WHERE role = 'validator' AND stake_navax IS NOT NULL ORDER BY start_time""",
        [periods_path()]).df()
    rows["renewal"] = rows.prev_e.notna() & (rows.s >= rows.prev_e) & (rows.s <= rows.prev_e + FOLLOW_US)
    rows["held"] = rows.start_time >= HELD_BACK
    return rows


def chart_monthly(out: Path) -> Path:
    """How are the validator commitments the model follows made, month by month: renewals or new commitments?"""
    rows = commitment_starts()
    rows["month"] = rows.start_time.dt.to_period("M").dt.to_timestamp()
    grouped = rows.groupby(["month", "held"]).agg(renewals=("renewal", "sum"), total=("renewal", "size")).reset_index()
    grouped["new"] = grouped.total - grouped.renewals
    table = pd.DataFrame({
        "Month": grouped.month.dt.strftime("%Y-%m"),
        "Part of the record": np.where(grouped.held, "Held back from model fitting", "Before the held-back period"),
        "Renewals": grouped.renewals.astype(int), "New commitments": grouped.new.astype(int),
        "Commitments started": grouped.total.astype(int)})
    layers = []
    end = pd.Timestamp(rows.start_time.max()).normalize() + pd.Timedelta(days=1)
    top = float(grouped.groupby("month").total.sum().max()) * 1.15
    layers.append(held_back_band(end + pd.Timedelta(days=20)))
    layers.extend(era_layers(NETWORK_START, end, top * 0.95))
    base = {}
    for _, r in grouped.sort_values(["month", "held"]).iterrows():
        left = r.month + pd.Timedelta(days=3)
        right = r.month + pd.offsets.MonthEnd(0) - pd.Timedelta(days=2)
        y0 = base.get(r.month, 0)
        for value, color in ((r.renewals, COMMITMENTS), (r.new, NODES)):
            layers.append(hv.Rectangles([(left, y0, right, y0 + value)]).opts(
                color=color, line_color=None, alpha=0.4 if r.held else 1.0))
            y0 += value
        base[r.month] = y0
    durango = rows[(rows.start_time >= pd.Timestamp("2024-03-06 16:00")) & ~rows.held].renewal.mean()
    early = rows[rows.start_time < pd.Timestamp("2022-10-18 16:00")].renewal.mean()
    key_y = top * 0.80
    layers += [hv.Text(pd.Timestamp("2020-11-01"), key_y, "■ Renewals", halign="left").opts(text_color=COMMITMENTS, text_font_size="10.5pt", text_font_style="bold"),
               hv.Text(pd.Timestamp("2020-11-01"), key_y * 0.88, "■ New commitments", halign="left").opts(text_color=NODES, text_font_size="10.5pt", text_font_style="bold"),
               hv.Text(HELD_BACK + pd.Timedelta(days=12), top * 0.84, "Held back,\npale bars", halign="left", valign="top").opts(
                   text_font_size="9pt", text_color=HELD_TEXT)]
    chart = hv.Overlay(layers).opts(
        width=WIDTH, height=400,
        title=f"Renewals are most validator commitments: {durango:.0%} from Durango on, {early:.0%} before Banff",
        xlabel="Month the commitment started (UTC)", ylabel="Validator commitments started", ylim=(0, top),
        xlim=(NETWORK_START, end + pd.Timedelta(days=20)), show_legend=False, **STYLE)
    notes = [(f"Validator commitments in {RUN}. A renewal is a commitment that starts on the same node within seven days of "
             "the end of that node's previous commitment, the definition origin_inputs uses for v0.7's renewal probability."),
             ("Shares in the title are pooled over commitments started from Durango (2024-03-06 16:00 UTC) to the held-back "
             "boundary, and before Banff (2022-10-18 16:00 UTC)."),
             ("Commitments that start from 2025-11-19 16:00 UTC are drawn pale: description only. "
             f"The last month, {table.Month.iloc[-1]}, runs to the end of the pinned run, {rows.start_time.max():%Y-%m-%d %H:%M} UTC.")]
    return save(chart, table, out, "commitments-by-month", 400, notes)


# C3: v0.7's renewal and entry inputs against what followed ------------------------------------------------------

def origin_label(name: str, when: date) -> str:
    return f"{name}, {when:%-d %b %Y}" if name in UPGRADES else f"{when:%-d %b %Y}"


def inputs_table(check: Path | None) -> pd.DataFrame:
    """For each development origin, v0.7's renewal probability and entry rate, and the realized values in the 90 days
    after it, cut at the held-back boundary."""
    path = periods_path()
    everything = validator_periods(path, HELD_BACK_US - 1)
    starts = duckdb.execute(
        """SELECT epoch_us(start_time) AS s, epoch_us(accepted_at) AS a,
                  lag(epoch_us(end_time)) OVER (PARTITION BY node_id ORDER BY start_time, transaction_hash) AS prev_e
           FROM read_parquet(?) WHERE role = 'validator' AND stake_navax IS NOT NULL""", [path]).df()
    starts["renewal"] = starts.prev_e.notna() & (starts.s >= starts.prev_e) & (starts.s <= starts.prev_e + FOLLOW_US)
    rows = []
    for name, origin in sorted({**UPGRADES, **QUARTERS}.items(), key=lambda kv: kv[1]):
        cutoff = (pd.Timestamp(origin) - pd.Timestamp(0)).days * US_PER_DAY + INSTANT_US
        given = origin_inputs(path, origin)
        renew_end = min(cutoff + 90 * US_PER_DAY, LAST_LABELLED_US)
        ended = renewal_endings(everything, cutoff, renew_end)
        entry_end = min(cutoff + 90 * US_PER_DAY, HELD_BACK_US - 1)
        window = starts[(starts.s > cutoff) & (starts.s <= entry_end) & (starts.a > cutoff) & ~starts.renewal]
        days = (entry_end - cutoff) / US_PER_DAY
        rows.append({
            "Origin": origin_label(name, origin), "Origin date": origin.isoformat(),
            "Origin type": "Network upgrade" if name in UPGRADES else "Start of quarter",
            "Renewal share assumed by v0.7 (%)": round(100 * given["renewal_probability"], 2),
            "Renewal share realized, next 90 days (%)": round(100 * ended.renewed.mean(), 2),
            "Endings in the next 90 days": len(ended),
            "New commitments per day assumed by v0.7": round(given["entry_rate_per_day"], 2),
            "New commitments per day realized, next 90 days": round(len(window) / days, 2),
            "Days observed after the origin": round(days, 1)})
    table = pd.DataFrame(rows)
    if check is not None:
        scores = pd.read_csv(check)
        merged = table.merge(scores, left_on="Origin date", right_on="origin_date")
        gap_p = (merged["Renewal share assumed by v0.7 (%)"] / 100 - merged["p_v0.7"]).abs().max()
        gap_r = (merged["Renewal share realized, next 90 days (%)"] / 100 - merged["renewed"]).abs().max()
        if len(merged) != len(table) or gap_p > 1e-4 or gap_r > 1e-4:
            raise SystemExit(f"renewal numbers differ from {check.name}: {gap_p:.6f}, {gap_r:.6f}")
        print(f"renewal numbers match {check.name} at all {len(merged)} origins")
    return table


def dumbbell(table: pd.DataFrame, assumed: str, realized: str, ylabel: str, title: str, ylim: tuple, height: int,
             upgrade_y: float, key_y: float, fmt: str, short_note: str) -> hv.Overlay:
    t = table.assign(When=pd.to_datetime(table["Origin date"]))
    segs = hv.Segments((t.When, t[assumed], t.When, t[realized])).opts(color="#c9ccd1", line_width=3)
    a = hv.Scatter(t, "When", [assumed, "Origin"]).opts(color=V07, size=11, tools=["hover"])
    r = hv.Scatter(t, "When", [realized, "Origin"]).opts(color="white", line_color=ACTUAL, line_width=2, size=10,
                                                          tools=["hover"])
    layers = [segs, a, r]
    for _, row in t[t["Origin type"] == "Network upgrade"].iterrows():
        layers.append(hv.Text(row.When, upgrade_y, row.Origin.split(",")[0]).opts(text_font_size="9pt", text_color=MUTED))
    last = t.iloc[-1]
    offset = (ylim[1] - ylim[0]) * 0.07 * (1 if last[realized] >= last[assumed] else -1)
    layers.append(hv.Text(last.When, last[realized] + offset, short_note).opts(text_font_size="8.5pt", text_color=MUTED))
    layers.append(hv.Text(pd.Timestamp("2022-06-10"), key_y, "●  Assumed by v0.7", halign="left").opts(
        text_font_size="10pt", text_color=V07, text_font_style="bold"))
    layers.append(hv.Text(pd.Timestamp("2023-02-20"), key_y, "○  Realized in the next 90 days", halign="left").opts(
        text_font_size="10pt", text_color=ACTUAL, text_font_style="bold"))
    return hv.Overlay(layers).opts(width=WIDTH, height=height, title=title, xlabel="Origin date", ylabel=ylabel,
                                   ylim=ylim, xlim=(pd.Timestamp("2022-05-15"), pd.Timestamp("2025-11-15")),
                                   show_legend=False, yformatter=fmt, **STYLE)


def chart_inputs(out: Path, check: Path | None) -> Path:
    """What renewal and entry did v0.7 assume at each origin, and what happened in the 90 days after?"""
    table = inputs_table(check)
    gaps = table["Renewal share assumed by v0.7 (%)"] - table["Renewal share realized, next 90 days (%)"]
    worst = table.loc[gaps.abs().idxmax()]
    renew = dumbbell(table, "Renewal share assumed by v0.7 (%)", "Renewal share realized, next 90 days (%)",
                     "Renewal within 7 days (%)",
                     f"Renewal: v0.7's input missed what followed by up to {gaps.abs().max():.0f} points, at {worst.Origin}",
                     (65, 92), 320, 66.8, 90.3, "%.0f%%", "42 days")
    ratio = table["New commitments per day realized, next 90 days"] / table["New commitments per day assumed by v0.7"]
    low = high = ratio[table["Days observed after the origin"] == 90]
    entry_top = float(table[["New commitments per day assumed by v0.7", "New commitments per day realized, next 90 days"]].max().max()) * 1.2
    entry = dumbbell(table, "New commitments per day assumed by v0.7", "New commitments per day realized, next 90 days",
                     "New commitments a day",
                     f"Entry: the next 90 days ran from {1 - low.min():.0%} below v0.7's input to {high.max() - 1:.0%} above",
                     (0, entry_top), 320, entry_top * 0.04, entry_top * 0.93, "%.0f", "49 days")
    layout = (renew + entry).cols(1).opts(shared_axes=False, toolbar=None)
    notes = [("Assumed values are origin_inputs at each origin: the seven-day renewal share of validator commitments that ended "
             "in the year before it, and the daily count of commitments in that year that were not renewals."),
             ("Realized renewal is the share of commitments ending in the 90 days after the origin that the same node renewed "
             "within seven days. Realized entry counts commitments accepted and started in those 90 days that were not renewals."),
             ("Both realized windows stop at the held-back boundary: endings stop seven days before 2025-11-19 16:00 UTC and starts "
             "stop at it, so the 2025-10-01 origin is observed for 49 days of entry and 42 days of endings. No held-back data is drawn.")]
    return save(layout, table, out, "renewal-and-entry-inputs", 2 * 320 - 20, notes,
                {"renewal_scores": check} if check is not None else None)


# C4: the reward formula against the chain ------------------------------------------------------------------------

def kernel_table() -> tuple[pd.DataFrame, dict]:
    counts = duckdb.execute(
        """SELECT accepted_at >= TIMESTAMP '2025-11-19 16:00:00' AS held, role, start_kind,
                  count(*) AS rows, count(reproduced) AS checked, sum(reproduced::INT) AS reproduced,
                  max(abs(kernel_gap_navax)) AS largest_gap,
                  count(*) FILTER (WHERE kernel_reward_navax IS NULL AND regime = 'genesis') AS genesis,
                  count(*) FILTER (WHERE kernel_reward_navax IS NULL AND supply_before_navax IS NULL AND regime <> 'genesis') AS no_supply,
                  count(*) FILTER (WHERE kernel_reward_navax IS NOT NULL AND potential_reward_navax IS NULL) AS no_record
           FROM read_parquet(?) GROUP BY ALL ORDER BY ALL""", [periods_path()]).df()
    names = {("delegator", "immediate"): "Delegations, started at acceptance",
             ("validator", "immediate"): "Validators, started at acceptance",
             ("delegator", "pending"): "Delegations, started after acceptance",
             ("validator", "pending"): "Validators, started after acceptance"}
    table = pd.DataFrame({
        "Role and start": [names[(r.role, r.start_kind)] for r in counts.itertuples()],
        "Part of the record": np.where(counts.held, "Accepted in the held-back period", "Accepted before the held-back period"),
        "Commitments": counts.rows.astype(int), "Checked by the formula": counts.checked.astype(int),
        "Reward reproduced exactly": counts.reproduced.fillna(0).astype(int),
        "Share reproduced (%)": (100 * counts.reproduced / counts.checked).round(4),
        "Largest gap (nAVAX)": counts.largest_gap.fillna(0).astype(np.int64),
        "Not checked: genesis validators": counts.genesis.astype(int),
        "Not checked: no supply recorded before the start": counts.no_supply.astype(int),
        "Not checked: no recorded potential reward": counts.no_record.astype(int)})
    whole = duckdb.execute(
        """SELECT count(reproduced) FILTER (WHERE start_kind = 'immediate'), sum(reproduced::INT) FILTER (WHERE start_kind = 'immediate'),
                  count(*) FILTER (WHERE start_kind = 'immediate'), max(accepted_at)
           FROM read_parquet(?)""", [periods_path()]).fetchone()
    return table, {"checked": whole[0], "reproduced": whole[1], "rows": whole[2], "last": whole[3]}


def chart_kernel(out: Path) -> Path:
    """Does the reward formula reproduce the potential reward the chain recorded for each stake?"""
    table, whole = kernel_table()
    order = ["Delegations, started at acceptance", "Validators, started at acceptance",
             "Delegations, started after acceptance", "Validators, started after acceptance"]
    rows = []
    for name in order:
        for part in ("Accepted before the held-back period", "Accepted in the held-back period"):
            hit = table[(table["Role and start"] == name) & (table["Part of the record"] == part)]
            if len(hit):
                rows.append(hit.iloc[0])
    drawn = pd.DataFrame(rows).reset_index(drop=True)
    drawn["y"] = np.arange(len(drawn))[::-1]
    layers = []
    for _, r in drawn.iterrows():
        held = r["Part of the record"] != "Accepted before the held-back period"
        layers.append(hv.Rectangles([(0, r.y - 0.34, r["Share reproduced (%)"], r.y + 0.34)]).opts(
            color=REWARDS, line_color=REWARDS, alpha=0.35 if held else 1.0, line_dash="dashed" if held else "solid",
            line_width=1.5 if held else 0))
        missed = r["Checked by the formula"] - r["Reward reproduced exactly"]
        share = "all" if missed == 0 else (f"all but {missed}" if missed < 10 else f"{r['Share reproduced (%)']:.1f}%")
        text = f"{r['Reward reproduced exactly']:,} of {r['Checked by the formula']:,}  ({share})"
        inside = r["Share reproduced (%)"] > 60
        layers.append(hv.Text(r["Share reproduced (%)"] - 1.5 if inside else r["Share reproduced (%)"] + 1.5, r.y, text,
                              halign="right" if inside else "left").opts(
            text_font_size="10pt", text_color="white" if inside and not held else INK, text_font_style="bold"))
    ticks = [(int(r.y), r["Role and start"].replace(", ", ",\n") + (",\nheld back: description" if r["Part of the record"] != "Accepted before the held-back period" else ""))
             for _, r in drawn.iterrows()]
    pre = table[(table["Part of the record"] == "Accepted before the held-back period") & table["Role and start"].str.contains("at acceptance")]
    chart = hv.Overlay(layers).opts(
        width=WIDTH, height=400,
        title=f"The formula reproduces all but {pre['Checked by the formula'].sum() - pre['Reward reproduced exactly'].sum()} "
              f"of {pre['Checked by the formula'].sum():,} stakes started at acceptance",
        xlabel="Recorded potential rewards reproduced exactly (%)", ylabel="", yticks=ticks, xlim=(0, 104),
        ylim=(-0.6, len(drawn) - 0.4), show_legend=False, **STYLE)
    notes = [(f"Run {RUN}, every staking period accepted from 2020-09-10 to {whole['last']:%Y-%m-%d %H:%M} UTC. A stake counts as "
             "reproduced when the formula's potential reward equals the recorded one to the nAVAX."),
             (f"Over the whole run, {whole['reproduced']:,} of {whole['checked']:,} stakes that started at acceptance are reproduced. "
             f"The other {whole['rows'] - whole['checked']} ({int(table['Not checked: genesis validators'].sum())} genesis validators and "
             f"{int(table['Not checked: no supply recorded before the start'].sum())} validators with no supply recorded before their start) are not checked."),
             "The one stake not reproduced is a delegation accepted 2024-03-07 01:16:05 UTC, 31 nAVAX apart.",
             ("Stakes started after acceptance, possible before Durango, were priced by the chain with the supply at their start, while "
             "the record holds the supply at acceptance, so the formula is given a different input, not a different rule."),
             "Stakes accepted from 2025-11-19 16:00 UTC are drawn pale and dashed: description only."]
    return save(chart, table, out, "reward-kernel-reproduction", 400, notes)


# C5: the replay against the ledger -------------------------------------------------------------------------------

def replay_table() -> tuple[pd.DataFrame, dict]:
    events = daily_events(periods_path())
    long = run(Replay(events=events, events_source=RUN))
    result = compare(long, events, ledger_path())
    wide = long[long.timestep >= 1].pivot_table(index="timestep", columns="variable", values="value", aggfunc="first")
    replayed = pd.DataFrame({
        "date": events.date_utc.iloc[: len(wide)].astype(str).to_numpy(),
        "rv": [int(v) for v in wide.active_validator_stake_navax], "rd": [int(v) for v in wide.active_delegated_stake_navax],
        "rr": [int(v) for v in wide.rewards_paid_navax], "rn": [int(v) for v in wide.active_validators]})
    ledger = duckdb.execute(
        """SELECT date_utc::VARCHAR AS date, complete, active_validator_stake_wei::VARCHAR AS v, active_delegated_stake_wei::VARCHAR AS d,
                  issued_rewards_wei::VARCHAR AS r, active_validators AS n FROM read_parquet(?)""", [ledger_path()]).df()
    m = replayed.merge(ledger, on="date", how="left")
    m = m[m.complete.fillna(False).astype(bool)]
    nav = 10**9
    rec_v = [int(x) // nav for x in m.v]
    if any(int(x) % nav for x in m.v) or any(int(x) % nav for x in m.d) or any(int(x) % nav for x in m.r):
        raise SystemExit("the ledger holds a stake or reward that is not a whole nAVAX")
    table = pd.DataFrame({
        "Date (UTC)": m.date.to_numpy(),
        "Validator stake recorded (M AVAX)": [v / 1e15 for v in rec_v],
        "Validator stake replayed (M AVAX)": [v / 1e15 for v in m.rv],
        "Validator stake difference (nAVAX)": [a - b for a, b in zip(rec_v, m.rv)],
        "Delegated stake difference (nAVAX)": [int(x) // nav - b for x, b in zip(m.d, m.rd)],
        "Rewards paid difference (nAVAX)": [int(x) // nav - b for x, b in zip(m.r, m.rr)],
        "Active validators difference": [int(a) - int(b) for a, b in zip(m.n, m.rn)]})
    return table, result


def chart_replay(out: Path) -> Path:
    """Does the model's protocol layer, replaying the recorded stakes, reproduce the ledger day by day?"""
    table, result = replay_table()
    if not result["exact"]:
        print("replay differs from the ledger:", result)
    t = table.assign(When=pd.to_datetime(table["Date (UTC)"]))
    end = t.When.max() + pd.Timedelta(days=1)
    diffs = ["Validator stake difference (nAVAX)", "Delegated stake difference (nAVAX)", "Rewards paid difference (nAVAX)",
             "Active validators difference"]
    nonzero = int((t[diffs] != 0).any(axis=1).sum())
    top = float(t["Validator stake recorded (M AVAX)"].max()) * 1.15
    upper = hv.Overlay([
        *era_layers(NETWORK_START, end, top * 0.94),
        hv.Curve(t, "When", ["Validator stake recorded (M AVAX)", "Date (UTC)"]).opts(color=STAKE, line_width=9, alpha=0.35),
        hv.Curve(t, "When", ["Validator stake replayed (M AVAX)", "Date (UTC)"]).opts(color=INK, line_width=1.6, tools=["hover"]),
        hv.Text(pd.Timestamp("2022-11-01"), top * 0.12, "Wide green: recorded on the ledger.  Thin black: replayed by the model",
                halign="left").opts(text_font_size="10pt", text_color=INK)]).opts(
        width=WIDTH, height=320,
        title=f"The replay equals the ledger to the nAVAX on all {len(t):,} complete days",
        xlabel="", ylabel="Validator stake (M AVAX)", ylim=(0, top), xlim=(NETWORK_START, end), show_legend=False, **STYLE)
    lower = hv.Overlay([
        *era_layers(NETWORK_START, end, None),
        hv.Curve(t, "When", ["Validator stake difference (nAVAX)", "Date (UTC)"]).opts(color=STAKE, line_width=2.5, tools=["hover"]),
        hv.Text(pd.Timestamp("2020-11-01"), 3.2, f"Validator stake, recorded minus replayed. Days not zero: {nonzero}", halign="left").opts(
            text_font_size="10pt", text_color=INK, text_font_style="bold"),
        hv.Text(pd.Timestamp("2020-11-01"), -3.2, "Delegated stake, rewards paid and both counts also differ by zero on every day",
                halign="left").opts(text_font_size="9.5pt", text_color=MUTED)]).opts(
        width=WIDTH, height=200, title="", xlabel="Date (UTC)", ylabel="Difference (nAVAX)", ylim=(-5, 5),
        yticks=[-4, -2, 0, 2, 4], xlim=(NETWORK_START, end), show_legend=False, **STYLE)
    layout = (upper + lower).cols(1).opts(shared_axes=False, toolbar=None)
    notes = [f"Replay of {RUN} through model.replay with daily_events up to 2025-11-18, compared with {LEDGER} on every complete day.",
             f"compare() result: {json.dumps(result)}",
             "The ledger records stake in wei. Every value is a whole nAVAX, so differences are exact integers in nAVAX.",
             "The replay is not a fit. It stops before the held-back period because daily_events refuses later days."]
    return save(layout, table, out, "replay-against-ledger", 320 + 200 - 30, notes)


# C6: reward designs -----------------------------------------------------------------------------------------------

SUPPLY_NAVAX = 465_373_500 * 10**9
PRICED_AT = datetime(2026, 12, 22, tzinfo=UTC)
DESIGN_COLORS = {
    "Chain before ACP-285, 10% floor": MECHANISM_COLORS["Chain today"],
    "ACP-285 at 7.5%, the chain from Helicon": MECHANISM_COLORS["ACP-285 settings"],
    "ACP-285 at 5%": MECHANISM_COLORS["ACP-285 settings"],
    "Tenure boost, up to +10%, on ACP-285 at 7.5%": MECHANISM_COLORS["Tenure boost"],
    "Quadratic curve, on ACP-285 at 7.5%": MECHANISM_COLORS["Quadratic curve"],
    "Quadratic curve, scaled to ACP-285 at 7.5% issuance": MECHANISM_COLORS["Quadratic curve, today's issuance"],
}
DESIGN_DASH = {"ACP-285 at 5%": "dashed", "Quadratic curve, scaled to ACP-285 at 7.5% issuance": "dashed"}


def designs_tables() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    periods = load_periods(periods_path())
    cohort = group_stakes(periods)
    quadratic = QuadraticReward()
    held = quadratic.at_equal_issuance(cohort.assign(start=PRICED_AT), SUPPLY_NAVAX)
    mechanisms = [ACP285Ramp(target_min_rate=0.10), ChainReward(), ACP285Ramp(target_min_rate=0.05), TenureBoost(),
                  quadratic, held]
    names = list(DESIGN_COLORS)
    for mechanism, name in zip(mechanisms, names):
        mechanism.label = name
    days = [14, *range(21, 365, 7), 365]
    curves = pd.concat([m.curve(SUPPLY_NAVAX, PRICED_AT, days, completed_periods=8) for m in mechanisms], ignore_index=True)
    curves = pd.DataFrame({"Design": curves.mechanism, "Committed duration (weeks)": (curves.duration_days / 7).round(2),
                           "Committed duration (days)": curves.duration_days, "Annual reward rate (%)": (100 * curves.annual_rate).round(4)})
    minted = issuance_table(mechanisms, cohort, SUPPLY_NAVAX, PRICED_AT)
    floor = float(minted.issuance_avax.iloc[0])
    issuance = pd.DataFrame({"Design": minted.mechanism, "AVAX minted for the cohort (M)": (minted.issuance_avax / 1e6).round(3),
                             "Change from the 10% floor (%)": (100 * (minted.issuance_avax / floor - 1)).round(1)})
    sizes = cohort.groupby("role").periods.sum().to_dict()
    return curves, issuance, sizes


def chart_designs(out: Path) -> Path:
    """How does each design price committed duration, and how much AVAX does it mint for the same stakes?"""
    curves, issuance, sizes = designs_tables()
    lines = []
    for name, color in DESIGN_COLORS.items():
        part = curves[curves.Design == name]
        lines.append(hv.Curve(part, "Committed duration (weeks)", ["Annual reward rate (%)", "Design"], label=name).opts(
            color=color, line_width=3.5 if name.startswith("Chain") else 2.6,
            line_dash=DESIGN_DASH.get(name, "solid"), tools=["hover"]))
    rates = hv.Overlay(lines).opts(
        width=WIDTH, height=440, title="The designs differ most on short commitments, and most meet at one year",
        xlabel="Committed duration (weeks)", ylabel="Annual reward rate (%)", xlim=(2, 52), ylim=(0, 7.8),
        legend_position="bottom", legend_cols=2, legend_opts={"label_text_font_size": "9.5pt", "border_line_alpha": 0}, **STYLE)
    bars = issuance.iloc[::-1].reset_index(drop=True)
    bars["y"] = np.arange(len(bars))
    layers = []
    for _, r in bars.iterrows():
        dashed = DESIGN_DASH.get(r.Design) == "dashed"
        layers.append(hv.Rectangles([(0, r.y - 0.34, r["AVAX minted for the cohort (M)"], r.y + 0.34)]).opts(
            color=DESIGN_COLORS[r.Design], line_color=DESIGN_COLORS[r.Design], alpha=0.55 if dashed else 1.0, line_width=0))
        change = "baseline" if r.y == len(bars) - 1 else f"{r['Change from the 10% floor (%)']:+.1f}%".replace("-", "−")
        layers.append(hv.Text(0.25, r.y, r.Design, halign="left").opts(
            text_font_size="10pt", text_color=INK if dashed else "white"))
        layers.append(hv.Text(r["AVAX minted for the cohort (M)"] + 0.15, r.y,
                              f"{r['AVAX minted for the cohort (M)']:.2f}M  ({change})", halign="left").opts(
            text_font_size="10pt", text_color=INK, text_font_style="bold"))
    seven = float(issuance.loc[issuance.Design.str.startswith("ACP-285 at 7.5%"), "Change from the 10% floor (%)"].iloc[0])
    five = float(issuance.loc[issuance.Design == "ACP-285 at 5%", "Change from the 10% floor (%)"].iloc[0])
    minted = hv.Overlay(layers).opts(
        width=WIDTH, height=330,
        title=f"Against the 10% floor, ACP-285 at 7.5% mints {abs(seven):.1f}% less, a 5% target {abs(five):.1f}% less",
        xlabel="AVAX minted for the reference cohort (M)", ylabel="", yaxis=None,
        xlim=(0, float(bars["AVAX minted for the cohort (M)"].max()) * 1.32), ylim=(-0.6, len(bars) - 0.4), show_legend=False, **STYLE)
    layout = (rates + minted).cols(1).opts(shared_axes=False, toolbar=None)
    table = curves.merge(issuance, on="Design")
    notes = [(f"Reference cohort: the {sizes.get('validator', 0):,} validator commitments and {sizes.get('delegator', 0):,} delegations "
             "in mechanisms.cohort's default window, accepted before 2025-11-19 16:00 UTC, repriced to start on 2026-12-22 with the "
             "P-Chain counter at 465.37M AVAX, as in the 2 October memo."),
             ("ACP-285's 90-day ramp from Helicon (2026-09-22 15:00 UTC) ends on 2026-12-21, so the chain priced on 2026-12-22 is at its "
             "7.5% floor. The 10% floor is the chain before ACP-285. The memo's Section 6 compared a 5% target with the chain already at "
             "7.5%. This chart compares every design with the 10% floor."),
             ("Rates are for a node with eight completed commitments, at which the tenure boost is full (+10%). The quadratic curve has "
             "exponent 2. Its scaled version mints what ACP-285 at 7.5% mints for the cohort.")]
    return save(layout, table, out, "reward-designs", 440 + 330 - 10, notes)


# C15: renewal by tenure -------------------------------------------------------------------------------------------

def tenure_table() -> pd.DataFrame:
    path = periods_path()
    rows = validator_periods(path, HELD_BACK_US - 1)
    first = (pd.Timestamp(min(QUARTERS.values())) - pd.Timestamp(0)).days * US_PER_DAY + INSTANT_US
    ended = renewal_endings(rows, first, LAST_LABELLED_US)
    tenure = ended.done + 1
    bins = pd.cut(tenure, [0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 24, 10**6],
                  labels=["1", "2", "3", "4", "5", "6", "7", "8", "9 to 12", "13 to 24", "25 or more"])
    grouped = ended.assign(bin=bins).groupby("bin", observed=True).renewed.agg(["size", "mean"]).reset_index()
    assumed = []
    for name, origin in sorted({**UPGRADES, **QUARTERS}.items(), key=lambda kv: kv[1]):
        assumed.append({"Origin": origin_label(name, origin),
                        "Renewal share assumed by v0.7 (%)": round(100 * origin_inputs(path, origin)["renewal_probability"], 2)})
    assumed = pd.DataFrame(assumed)
    table = pd.DataFrame({"Commitment number on the node": grouped["bin"].astype(str), "Endings": grouped["size"].astype(int),
                          "Renewed within 7 days (%)": (100 * grouped["mean"]).round(2)})
    table["v0.7, lowest origin (%)"] = assumed["Renewal share assumed by v0.7 (%)"].min()
    table["v0.7, highest origin (%)"] = assumed["Renewal share assumed by v0.7 (%)"].max()
    table["v0.7, mean of origins (%)"] = round(assumed["Renewal share assumed by v0.7 (%)"].mean(), 2)
    return table


def chart_tenure(out: Path) -> Path:
    """Why does v0.7 miss renewal? Renewal by the node's commitment number, against v0.7's one probability."""
    table = tenure_table()
    t = table.reset_index(drop=True).assign(x=lambda d: np.arange(len(d)))
    low, high, mean = (float(t[c].iloc[0]) for c in ("v0.7, lowest origin (%)", "v0.7, highest origin (%)", "v0.7, mean of origins (%)"))
    layers = []
    for _, r in t.iterrows():
        layers.append(hv.Rectangles([(r.x - 0.36, 0, r.x + 0.36, r["Renewed within 7 days (%)"])]).opts(color=COMMITMENTS, line_color=None))
        layers.append(hv.Text(r.x, 11, f"{r['Renewed within 7 days (%)']:.0f}%").opts(
            text_font_size="10.5pt", text_color="white", text_font_style="bold"))
        layers.append(hv.Text(r.x, 4, f"{r.Endings:,}").opts(text_font_size="8.5pt", text_color="white"))
    layers += [hv.HSpan(low, high).opts(color=V07, alpha=0.18, line_alpha=0),
               hv.HLine(mean).opts(color=V07, line_width=2.5, line_dash="dashed"),
               hv.Text(-0.45, 97, f"v0.7: one renewal probability per origin, {low:.0f}% to {high:.0f}% (dashed: mean {mean:.0f}%)",
                       halign="left").opts(text_font_size="10pt", text_color=V07, text_font_style="bold")]
    first, last = float(t["Renewed within 7 days (%)"].iloc[0]), float(t["Renewed within 7 days (%)"].iloc[-1])
    chart = hv.Overlay(layers).opts(
        width=WIDTH, height=400,
        title=f"Renewal climbs from {first:.0f}% after a first commitment to {last:.0f}%, against v0.7's single {mean:.0f}%",
        xlabel="Commitment number on the node (small figures: endings counted)", ylabel="Renewed within 7 days (%)",
        xticks=[(int(r.x), r["Commitment number on the node"]) for _, r in t.iterrows()], ylim=(0, 105),
        xlim=(-0.6, len(t) - 0.4), show_legend=False, **STYLE)
    notes = [(f"Validator commitments in {RUN} that ended from 2022-07-01 to seven days before 2025-11-19 16:00 UTC, each counted "
             "once. One overlapped by the node's next commitment made no decision and is left out, as renewal_endings defines."),
             "Commitment number counts the node's commitments up to and including the one that ended.",
             "v0.7's probability is origin_inputs' renewal share at each of the 19 development origins, and the band spans their range."]
    return save(chart, table, out, "renewal-by-tenure", 400, notes)


CHARTS = {"record": chart_record, "monthly": chart_monthly, "kernel": chart_kernel, "replay": chart_replay,
          "designs": chart_designs, "tenure": chart_tenure}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("chart", choices=sorted([*CHARTS, "inputs", "all"]))
    parser.add_argument("out", type=Path)
    parser.add_argument("--input", action="append", default=[], metavar="NAME=PATH")
    args = parser.parse_args()
    hv.extension("bokeh")
    inputs = {k: Path(v) for k, v in (item.split("=", 1) for item in args.input)}
    PINNED.update(check_pin())
    chosen = [*CHARTS, "inputs"] if args.chart == "all" else [args.chart]
    for name in chosen:
        if name == "inputs":
            print(chart_inputs(args.out, inputs.get("renewal")))
        else:
            print(CHARTS[name](args.out))


if __name__ == "__main__":
    main()
