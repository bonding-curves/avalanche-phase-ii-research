#!/usr/bin/env python3
"""The staking model v0 memo's three charts: the replay against the ledger, the reward curves, and the mechanism sweep.

    uv run --group notebook --group model python scripts/figures/model_v0_figures.py <memo folder>

Reads two pinned runs through avalanche_research.datasets, `staking-periods-2026-09-30` and
`avax-monetary-daily-2026-09-30`, and only staking periods accepted before 2025-11-19 16:00 UTC, the start of the
held-back test period. Writes `model-v0-replay.{csv,html}`, `model-v0-reward-curves.{csv,html}`, and
`model-v0-sweep.{csv,html}`, and prints the numbers the memo quotes.
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

import holoviews as hv
import numpy as np
import pandas as pd

from avalanche_research import datasets
from avalanche_research.mechanisms import (
    ACP285Ramp,
    ChainReward,
    QuadraticReward,
    TenureBoost,
)
from avalanche_research.mechanisms.cohort import group_stakes, load_periods
from avalanche_research.model.engine import run, sweep
from avalanche_research.model.lifecycle import ValidatorLifecycle, origin_inputs
from avalanche_research.model.replay import Replay, compare, daily_events
from avalanche_research.palette import QUANTITY_COLORS
from avalanche_research.staking_cohorts import (
    NETWORK_START,
    _era_intervals,
    _upgrade_axis,
)
from avalanche_research.views.mechanism_explorer import issuance_table

RUN = "staking-periods-2026-09-30"
LEDGER = "avax-monetary-daily-2026-09-30"
SUPPLY_NAVAX = 465_373_500 * 10**9
PRICED_AT = datetime(2026, 12, 22, tzinfo=UTC)
FORTUNA = date(2025, 4, 8)
RESPONSES = (0.0, 0.1, 0.3)
ERA_SHADE = "#eeeeee"
SIZE = {"width": 1000, "height": 520, "fontscale": 1.2, "toolbar": None, "show_grid": True}
COLORS = {
    "Chain today": QUANTITY_COLORS["commitments"],
    "ACP-285 settings": QUANTITY_COLORS["nodes"],
    "Tenure boost": QUANTITY_COLORS["stake"],
    "Quadratic curve": QUANTITY_COLORS["duration"],
    "Quadratic curve, today's issuance": QUANTITY_COLORS["addresses"],
}


def replay_chart(out: Path, periods_path: str) -> dict:
    events = daily_events(periods_path)
    table = run(Replay(events=events, events_source=RUN))
    ledger_path = str(datasets.parquet_path("derived.avax-monetary-daily", LEDGER))
    result = compare(table, events, ledger_path)
    wide = table[table.timestep >= 1].pivot_table(index="timestep", columns="variable", values="value", aggfunc="first")
    frame = pd.DataFrame({"date": pd.to_datetime(events.date_utc.iloc[: len(wide)].to_numpy()),
                          "Replayed by the model": wide.active_validator_stake_navax.to_numpy(dtype=float) / 1e9 / 1e6})
    ledger = datasets.load("derived.avax-monetary-daily", run=LEDGER)
    ledger = pd.DataFrame({"date": pd.to_datetime(ledger.date_utc), "complete": ledger.complete,
                           "Recorded on chain": pd.to_numeric(ledger.active_validator_stake_wei) / 1e18 / 1e6})
    frame = frame.merge(ledger, on="date", how="left")
    frame.loc[~frame.complete.fillna(False).astype(bool), "Recorded on chain"] = np.nan
    frame.drop(columns="complete").to_csv(out / "model-v0-replay.csv", index=False)
    end = frame.date.max() + pd.Timedelta(days=1)
    bands = [hv.VSpan(a, b).opts(color=ERA_SHADE, line_alpha=0)
             for index, (_, a, b) in enumerate(_era_intervals(NETWORK_START, end)) if index % 2]
    recorded = hv.Curve(frame, "date", "Recorded on chain", label="Recorded on chain").opts(
        color=QUANTITY_COLORS["stake"], line_width=9, alpha=0.35)
    replayed = hv.Curve(frame, "date", "Replayed by the model", label="Replayed by the model").opts(
        color="#1b1b1b", line_width=2, tools=["hover"])
    chart = hv.Overlay([*bands, recorded, replayed]).opts(
        **SIZE, title="Active validator stake, recorded on chain and replayed by the model, 2020-09-10 to 2025-11-18",
        xlabel="Date (UTC)", ylabel="Active validator stake (million AVAX)", legend_position="top_right",
        hooks=[_upgrade_axis], xlim=(frame.date.min(), end),
        ylim=(0.95 * frame["Replayed by the model"].min(), 1.03 * frame["Replayed by the model"].max()))
    hv.save(chart, out / "model-v0-replay.html")
    return result


def reward_chart(out: Path, periods_path: str) -> pd.DataFrame:
    cohort = group_stakes(load_periods(periods_path))
    quadratic = QuadraticReward()
    mechanisms = [ChainReward(), ACP285Ramp(target_min_rate=0.05), TenureBoost(), quadratic,
                  quadratic.at_equal_issuance(cohort.assign(start=PRICED_AT), SUPPLY_NAVAX)]
    labels = list(COLORS)
    days = [2, *range(4, 366, 3), 365]
    curves = []
    for mechanism, label in zip(mechanisms, labels):
        curve = mechanism.curve(SUPPLY_NAVAX, PRICED_AT, days, completed_periods=8)
        curves.append(curve.assign(mechanism=label, annual_rate_pct=curve.annual_rate * 100))
    frame = pd.concat(curves)[["mechanism", "duration_days", "annual_rate_pct"]]
    frame.to_csv(out / "model-v0-reward-curves.csv", index=False)
    lines = [hv.Curve(frame[frame.mechanism == label], "duration_days", ["annual_rate_pct", "mechanism"], label=label).opts(
        color=COLORS[label], line_width=4 if label == "Chain today" else 3, line_dash="dashed" if label.endswith("issuance") else "solid",
        tools=["hover"]) for label in labels]
    chart = hv.Overlay(lines).opts(
        **SIZE, title="Each mechanism prices duration differently; tenure adds to the rate for validators who stay",
        xlabel="Staking duration (days)", ylabel="Annual reward rate (%)", legend_position="bottom_right")
    hv.save(chart, out / "model-v0-reward-curves.html")
    return issuance_table(mechanisms, cohort, SUPPLY_NAVAX, PRICED_AT).assign(mechanism=labels)


def sweep_chart(out: Path, periods_path: str) -> pd.DataFrame:
    inputs = origin_inputs(periods_path, FORTUNA)
    start = datetime(2025, 4, 9, 12, tzinfo=UTC)
    stakes = pd.DataFrame({"stake_navax": inputs["initial_stakes"], "start": start, "completed_periods": inputs["initial_periods_done"],
                           "duration_seconds": np.clip(inputs["initial_days_left"], 1, 365) * 86_400})
    mechanisms = [ChainReward(label="Chain today"),
                  ACP285Ramp(activation=datetime(2025, 4, 8, 16, tzinfo=UTC), label="ACP-285 settings"),
                  TenureBoost(label="Tenure boost"), QuadraticReward(label="Quadratic curve"),
                  QuadraticReward().at_equal_issuance(stakes, inputs["supply0_navax"])]
    mechanisms[-1].label = "Quadratic curve, today's issuance"
    model = ValidatorLifecycle(origin=FORTUNA, timesteps=180, runs=20, inputs_source=RUN, **inputs)
    rows = []
    for response in RESPONSES:
        table = sweep(model, {"mechanism": mechanisms, "renewal_response": [response], "entry_response": [response]})
        last = table[(table.timestep == 180) & (table.variable == "active_validators")]
        issued = table[table.variable == "issued_navax"].groupby(["mechanism", "run"]).value.sum() / 1e15
        for mechanism, group in last.groupby("mechanism"):
            rows.append({"response": response, "mechanism": mechanism, "validators_mean": group.value.mean(),
                         "validators_p10": group.value.quantile(0.1), "validators_p90": group.value.quantile(0.9),
                         "issuance_million_avax": issued.loc[mechanism].mean()})
    frame = pd.DataFrame(rows)
    frame.to_csv(out / "model-v0-sweep.csv", index=False)
    panels = []
    for response in RESPONSES:
        part = frame[frame.response == response]
        layers = []
        for label, color in COLORS.items():
            row = part[part.mechanism == label]
            layers.append(hv.ErrorBars((row.issuance_million_avax, row.validators_mean, row.validators_mean - row.validators_p10,
                                        row.validators_p90 - row.validators_mean), vdims=["y", "yerrneg", "yerrpos"]).opts(
                color=color, line_width=2))
            layers.append(hv.Scatter(row, "issuance_million_avax", ["validators_mean", "mechanism"], label=label).opts(
                color=color, size=13, line_color="white", tools=["hover"]))
        title = "No response to pay" if response == 0 else f"Response {response}"
        panels.append(hv.Overlay(layers).opts(
            width=340, height=520, fontscale=1.1, toolbar=None, show_grid=True, title=title, show_legend=response == RESPONSES[0],
            legend_position="bottom_left", xlabel="AVAX issued in 180 days (million)", ylabel="Active validators after 180 days"))
    layout = hv.Layout(panels).cols(3).opts(shared_axes=True, toolbar=None)
    hv.save(layout, out / "model-v0-sweep.html")
    return frame


def main() -> None:
    out = Path(sys.argv[1])
    hv.extension("bokeh")
    periods_path = str(datasets.parquet_path("derived.staking-periods", RUN))
    print("replay", replay_chart(out, periods_path))
    print(reward_chart(out, periods_path).to_string(index=False))
    print(sweep_chart(out, periods_path).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
