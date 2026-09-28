"""Behavioural calibration (deliverable 1.4): delegator choice, validator lifecycle, and delegation flow.

``write_behaviour()`` fits every block and writes ``data/model/behaviour-v0.json`` in the shape the simulation
reads. It opens the input datasets itself, pinned to one run each, and records those run ids in ``inputs``.
Rebuild with ``uv run python -m avalanche_research.estimation``.

Windows are fixed before any estimate is seen: fit on weeks starting in [2021-01-01, 2025-01-01), so the genesis
era of 2020 does not dominate, and score on weeks starting in 2025. Half windows [2021, 2023) and [2023, 2025)
check sign stability. A parameter is identified when its 95% interval excludes zero and its sign agrees across
strata (delegators) or across the two half windows (validators and flows).
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from .. import datasets
from ..catalog import DATA_DIR
from . import choice, flows, lifecycle

FIT_WINDOW = ("2021-01-01", "2025-01-01")
HOLDOUT_WINDOW = ("2025-01-01", "2026-01-01")
HALVES = [("2021-01-01", "2023-01-01"), ("2023-01-01", "2025-01-01")]
OUTPUT = DATA_DIR / "model" / "behaviour-v0.json"
INPUTS = {
    "derived.validator-weeks": "validator_weeks",
    "derived.observed-delegations": "observed_delegations",
    "derived.market-weeks": "market_weeks",
    "derived.staking-periods": "staking_periods",
    "us-treasury.par-yield-daily": "par_yield_daily",
}
SPREAD_DEFINITION = (
    "staking rate minus external yield, both annual fractions, at the Monday 00:00 UTC cutoff. Staking rate: "
    "model.protocol.annualized_reward_rate for a 14-day, 2,000 AVAX stake at the P-Chain supply counter read before "
    "the cutoff, gross of fees, the quote sim.engine uses. External yield: US Treasury 3-month par yield on the last date before the cutoff (par_yield_daily.yield_rate, already a fraction)."
)


def open_inputs(runs: dict[str, str] | None = None) -> tuple[Any, dict[str, str]]:
    """A DuckDB connection with one view per input dataset, each pinned to one run (the latest unless named)."""
    runs = dict(runs or {})
    con = duckdb.connect()
    con.execute("SET memory_limit='5GB'; SET threads=6;")
    for dataset_id, view in INPUTS.items():
        run = runs.get(dataset_id) or datasets.runs(dataset_id)[0]["run"]
        path = str(datasets.parquet_path(dataset_id, run)).replace("'", "''")
        con.execute(f"CREATE VIEW {view} AS SELECT * FROM read_parquet('{path}')")
        runs[dataset_id] = run
    return con, runs


def _clean(value: Any) -> Any:
    """JSON-safe: NaN and infinities become null, numpy scalars become Python numbers."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _inclusive(window: tuple[str, str]) -> list[str]:
    end = datetime.fromisoformat(window[1]).date().toordinal() - 1
    return [window[0], datetime.fromordinal(end).date().isoformat()]


def estimate_behaviour(con: Any, runs: dict[str, str]) -> dict[str, Any]:
    market = lifecycle.market_frame(con)
    in_fit = lifecycle.in_window(market["week_start_utc"], FIT_WINDOW)
    spread_mean = float(market.loc[in_fit, "spread"].mean())

    periods = lifecycle.validator_periods(con)
    weekly = lifecycle.weekly_lifecycle(market, periods, lifecycle.active_validator_days(con))
    entry = lifecycle.fit_entry(weekly, FIT_WINDOW, HOLDOUT_WINDOW, HALVES)
    duration = lifecycle.fit_duration(periods, market, FIT_WINDOW, HOLDOUT_WINDOW, HALVES)
    renewal = lifecycle.fit_renewal(periods, market, FIT_WINDOW, HOLDOUT_WINDOW, HALVES)
    exit_ = lifecycle.fit_exit(weekly, FIT_WINDOW, HOLDOUT_WINDOW)

    flow_frame = flows.weekly_flows(con, market)
    flow_strata = flows.fit_strata(flow_frame, FIT_WINDOW, HOLDOUT_WINDOW, HALVES)
    primary_flow = flow_strata[flows.PRIMARY_STRATUM]

    fit_panel = choice.choice_panel(con, *FIT_WINDOW)
    holdout_panel = choice.choice_panel(con, *HOLDOUT_WINDOW)
    choice_strata = choice.fit_strata(fit_panel, holdout_panel)
    primary_choice = choice_strata[choice.PRIMARY_STRATUM]

    spreads = market.loc[in_fit, "spread"]
    return _clean({
        "version": "v0",
        "status": "v0, unreviewed",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "uv run python -m avalanche_research.estimation",
        "inputs": runs,
        "fit_window": _inclusive(FIT_WINDOW),
        "holdout_window": _inclusive(HOLDOUT_WINDOW),
        "spread_definition": SPREAD_DEFINITION,
        "spread_mean_fit_window": spread_mean,
        "spread_fit_window": {"min": float(spreads.min()), "max": float(spreads.max()), "weeks": int(spreads.notna().sum())},
        "validator_entry": entry,
        "validator_duration": duration,
        "validator_renewal": renewal,
        "validator_exit": exit_,
        "delegation_flow": {
            "sensitivity": primary_flow["sensitivity"],
            "form": "net weekly delegated flow / unstaked supply = sensitivity * tanh(staking_apr - external_yield)",
            "ci95": {"sensitivity": primary_flow["ci95"]},
            "identified": flows.identified(flow_strata),
            "primary_stratum": flows.PRIMARY_STRATUM,
            "strata": flow_strata,
            "ledger_check": flows.ledger_check(flow_frame, FIT_WINDOW),
        },
        "delegator_choice": {
            "coefficients": primary_choice["coefficients"],
            "se": primary_choice["se"],
            "ci95": primary_choice["ci95"],
            "primary_stratum": choice.PRIMARY_STRATUM,
            "identified": choice.identified(choice_strata),
            "form": "P(node i | week w) = softmax over offered nodes of sum_k coefficients_k * feature_ik",
            "strata": choice_strata,
            "coverage": {"fit": choice.panel_coverage(con, *FIT_WINDOW), "holdout": choice.panel_coverage(con, *HOLDOUT_WINDOW)},
            "within_week_correlation": choice.within_week_correlation(fit_panel),
        },
    })


def write_behaviour(path: Path = OUTPUT, runs: dict[str, str] | None = None) -> dict[str, Any]:
    con, pinned = open_inputs(runs)
    try:
        result = estimate_behaviour(con, pinned)
    finally:
        con.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


__all__ = ["FIT_WINDOW", "HALVES", "HOLDOUT_WINDOW", "OUTPUT", "estimate_behaviour", "open_inputs", "write_behaviour"]
