#!/usr/bin/env python3
"""Score v0.8's renewal logit against v0.7's renewal block on the endings after each development origin (ML2).

    uv run --group model python scripts/renewal_block_scores.py <output folder>

At each of the validation protocol's 19 origins, three renewal blocks are fitted on the year of endings before it:
v0.7's one probability, ``M1`` the share by the node's previous outcome (first commitment, after a renewal, after a
return), and v0.8's logit. Each is scored on the commitments that end in the 90 days after the origin, labelled
with seven days of follow-up, and never on an ending whose label would reach the held-back period from 2025-11-19.

The tests are the ones written before the scores (roadmap research r4, S1):

* ``S1-A1``: pooled log loss below v0.7's, one-sided p < 0.05 by a paired bootstrap that resamples origins and
  nodes within them, and lower at 14 or more origins.
* ``S1-A2``: log loss no worse than ``M1``. The registered actors are not yet set apart, so this is on all nodes.
* ``S1-A3``: expected calibration error at most 0.02 over 10 quantile bins, and monthly renewal within 3 points
  mean absolute error.
* ``S1-A4``: renewal at tenure 1, 2 and 7 within 3 points.
* ``S1-A5``: a challenger replaces the logit only if it beats it as ``S1-A1`` asks and passes ``S1-A3``. The challenger
  here is ``v0.8-c``, the logit with the node's own renewal record (``EX15``).

Writes ``renewal-scores.csv`` (one row per origin and block), ``renewal-tenure.csv`` and ``renewal-tests.csv``.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from avalanche_research import datasets
from avalanche_research.core.clock import LOCKBOX_START
from avalanche_research.model.fitted_blocks import RenewalLogit
from avalanche_research.model.fitted_lifecycle import (
    INSTANT_US,
    US_PER_DAY,
    renewal_endings,
    renewal_inputs,
    validator_periods,
)

RUN = "staking-periods-2026-09-30"
UPGRADES = {"Banff": date(2022, 10, 18), "Cortina": date(2023, 4, 25), "Durango": date(2024, 3, 6),
            "Etna": date(2024, 12, 16), "Fortuna": date(2025, 4, 8)}
QUARTERS = {f"{y}-{m:02d}-01": date(y, m, 1) for y in (2022, 2023, 2024, 2025) for m in (1, 4, 7, 10)
            if date(2022, 7, 1) <= date(y, m, 1) <= date(2025, 10, 1)}
HORIZON_DAYS = 90
FOLLOW_US = 7 * US_PER_DAY
LOCKBOX_US = int(LOCKBOX_START.timestamp() * 1_000_000)
# An ending is scored only if its whole follow-up week, and so any successor that labels it, falls before the lockbox.
LAST_LABELLED_US = LOCKBOX_US - FOLLOW_US - 1
BOOTSTRAPS = 2_000
BLOCKS = ("v0.7", "M1", "v0.8", "v0.8-c")


def previous_outcome(endings: pd.DataFrame) -> np.ndarray:
    return np.select([endings["done"].to_numpy() == 0, endings["after_return"].to_numpy()], [0, 2], 1)


def log_loss(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log1p(-p))


def bootstrap_p(events: pd.DataFrame, block: str, against: str) -> float:
    """Share of paired bootstrap replicates, resampling origins and nodes within them, in which ``block`` is no better."""
    rng = np.random.default_rng(20261005)
    nodes = events.assign(difference=events[f"loss_{block}"] - events[f"loss_{against}"]).groupby(["origin", "node_id"])["difference"].agg(["sum", "size"])
    groups = [(g["sum"].to_numpy(), g["size"].to_numpy()) for _, g in nodes.groupby(level="origin")]
    differences = np.empty(BOOTSTRAPS)
    for i in range(BOOTSTRAPS):
        total = count = 0.0
        for sums, sizes in (groups[j] for j in rng.integers(0, len(groups), len(groups))):
            picked = rng.integers(0, len(sums), len(sums))
            total += sums[picked].sum()
            count += sizes[picked].sum()
        differences[i] = total / count
    return float((differences >= 0).mean())


def block_tests(events, by_origin, tenure, monthly, monthly_mae, pooled, block, against, code) -> list[dict]:
    """``S1-A1`` (or ``S1-A5`` against another learner) to ``S1-A4`` for one renewal block."""
    p = bootstrap_p(events, block, against)
    lower_at = int((by_origin[f"loss_{block}"] < by_origin[f"loss_{against}"]).sum())
    bins = pd.qcut(events[f"p_{block}"], 10, duplicates="drop")
    calibration = events.groupby(bins, observed=True).agg(n=("renewed", "size"), observed=("renewed", "mean"), predicted=(f"p_{block}", "mean"))
    ece = float((calibration["n"] * (calibration["observed"] - calibration["predicted"]).abs()).sum() / calibration["n"].sum())
    gap = tenure[block] - tenure["observed"]
    return [
        {"block": block, "test": code, "measure": f"pooled log loss against {against}", "value": f"{pooled[block]:.4f} against {pooled[against]:.4f}",
         "detail": f"bootstrap p {p:.4f}, lower at {lower_at} of {len(by_origin)} origins",
         "passes": bool(pooled[block] < pooled[against] and p < 0.05 and lower_at >= 14)},
        {"block": block, "test": "S1-A2", "measure": "pooled log loss against M1", "value": f"{pooled[block]:.4f} against {pooled['M1']:.4f}",
         "detail": "all nodes, registered actors not yet set apart", "passes": bool(pooled[block] <= pooled["M1"])},
        {"block": block, "test": "S1-A3", "measure": "expected calibration error, 10 quantile bins; monthly mean absolute error",
         "value": f"{ece:.4f}; {monthly_mae[block]:.4f}", "detail": f"{len(monthly)} months; monthly error of v0.7 {monthly_mae['v0.7']:.4f}, M1 {monthly_mae['M1']:.4f}",
         "passes": bool(ece <= 0.02 and monthly_mae[block] <= 0.03)},
        {"block": block, "test": "S1-A4", "measure": "renewal at tenure 1, 2 and 7, predicted minus observed",
         "value": "; ".join(f"{t} {g:+.4f}" for t, g in gap.items()),
         "detail": "; ".join(f"{t} observed {o:.3f} of {n}, v0.7 {v:+.4f}" for t, o, n, v in zip(tenure.index, tenure["observed"], tenure["endings"], tenure["v0.7"] - tenure["observed"])),
         "passes": bool((gap.abs() <= 0.03).all())},
    ]


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    periods = str(datasets.parquet_path("derived.staking-periods", RUN))
    rows = validator_periods(periods, LOCKBOX_US - 1)
    scored = []
    for name, origin in {**UPGRADES, **QUARTERS}.items():
        cutoff = (pd.Timestamp(origin) - pd.Timestamp(0)).days * US_PER_DAY + INSTANT_US
        known = validator_periods(periods, cutoff)
        train = renewal_endings(known, cutoff - 365 * US_PER_DAY - FOLLOW_US, cutoff - FOLLOW_US)
        test = renewal_endings(rows, cutoff, min(cutoff + HORIZON_DAYS * US_PER_DAY, LAST_LABELLED_US))
        y_train = train["renewed"].to_numpy()
        plain = {k: v for k, v in renewal_inputs(train).items() if k != "returns"}
        logit = RenewalLogit.fit(plain, y_train, f"{RUN}, {len(train)} endings before {origin}")
        record = RenewalLogit.fit(renewal_inputs(train), y_train, f"{RUN}, {len(train)} endings before {origin}")
        shares = pd.Series(y_train).groupby(previous_outcome(train)).mean()
        predictions = {
            "v0.7": np.full(len(test), y_train.mean()),
            "M1": shares.reindex(previous_outcome(test)).fillna(y_train.mean()).to_numpy(),
            "v0.8": logit.probability({k: v for k, v in renewal_inputs(test).items() if k != "returns"}),
            "v0.8-c": record.probability(renewal_inputs(test)),
        }
        frame = test[["node_id", "e", "done", "stake_navax"]].assign(origin=name, origin_date=origin, renewed=test["renewed"].astype(int))
        for block, p in predictions.items():
            frame[f"p_{block}"] = p
        scored.append(frame)
    events = pd.concat(scored, ignore_index=True)
    for block in BLOCKS:
        events[f"loss_{block}"] = log_loss(events[f"p_{block}"].to_numpy(), events["renewed"].to_numpy())

    by_origin = events.groupby(["origin_date", "origin"]).agg(
        endings=("renewed", "size"), renewed=("renewed", "mean"),
        **{f"loss_{b}": (f"loss_{b}", "mean") for b in BLOCKS},
        **{f"p_{b}": (f"p_{b}", "mean") for b in BLOCKS},
    ).reset_index()
    by_origin.to_csv(out / "renewal-scores.csv", index=False)

    labels = np.where(events["done"] == 0, "1", np.where(events["done"] == 1, "2", np.where(events["done"] == 6, "7", "other")))
    tenure = events.assign(tenure=labels).query("tenure != 'other'").groupby("tenure").agg(
        endings=("renewed", "size"), observed=("renewed", "mean"), **{b: (f"p_{b}", "mean") for b in BLOCKS})
    tenure.to_csv(out / "renewal-tenure.csv")
    month = pd.to_datetime(events["e"], unit="us").dt.to_period("M")
    monthly = events.groupby(month).agg(observed=("renewed", "mean"), n=("renewed", "size"), **{b: (f"p_{b}", "mean") for b in BLOCKS})
    monthly_mae = {b: float((monthly["observed"] - monthly[b]).abs().mean()) for b in BLOCKS}
    pooled = {b: float(events[f"loss_{b}"].mean()) for b in BLOCKS}
    rows = []
    for block in ("v0.8", "v0.8-c"):
        rows += block_tests(events, by_origin, tenure, monthly, monthly_mae, pooled, block, "v0.7", "S1-A1")
    rows += block_tests(events, by_origin, tenure, monthly, monthly_mae, pooled, "v0.8-c", "v0.8", "S1-A5")[:1]
    tests = pd.DataFrame(rows)
    tests.to_csv(out / "renewal-tests.csv", index=False)
    print(by_origin.round(4).to_string(index=False))
    print(tenure.round(4).to_string())
    print(tests.to_string(index=False))


if __name__ == "__main__":
    main()
