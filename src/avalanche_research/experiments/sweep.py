"""A sweep from a design file: rows, base models built from pinned data, the row runner, and the sweep's receipt.

v0, unreviewed. Two commands run it:

    avalanche model sweep DESIGN OUT [--pin PIN]
    avalanche model run PIN OUT --origin 2025-04-08 [--model v0.8] [--runs 20] [--timesteps 180] [--seed 0]

The design file is JSON:

    {"generator": "cartesian", "levels": {"renewal_probability": [0.7, 0.8]}, "seed": 0,
     "origins": ["2025-04-08"], "models": ["v0.7"], "rows": 2,
     "pin": "data/pins/p5-v0.7-report.json", "runs": 20, "timesteps": 180, "workers": "auto"}

- ``generator``: ``cartesian``, crossing every ``levels`` list, or ``sobol`` with ``bounds`` (name to low and high),
  ``m`` (2^m points) and ``design_seed``. A level named ``seed`` sets each row's random seed. Other levels are model
  settings.
- ``origins``: model origin days, each before the validation lockbox. ``models``: names from ``MODELS``.
- ``rows``: the generator's rows times origins times models, stated so a wrong design stops before anything runs.
- ``pin``: a pin file (below). ``--pin`` on the command replaces it.
- ``runs`` per row, ``timesteps`` in days, and ``workers``: a number, or ``auto`` to size the pool from free memory at
  launch and a measured v0.8 cost per worker until a sweep's own pilot replaces it.

``model run`` is a one-row design: one origin, one model and one seed.

With ``"reducer": {"kind": "kpis", "horizons": [365, 180], "competing_yield": 0.04, "operating_costs": {"mid": 0.01}}``
each row keeps one value per run, KPI, horizon and cost level instead of its daily paths: the KPI module's
``kpi_table`` on the run's daily table, which follows the chain's daily table up to the origin. The chain table, the
realized supply at the origin and the mean daily burn before it come from the ``derived.avax-monetary-daily`` run the
pin names. Measures against a baseline run are left to the analysis, which has every run's absolute values.

A pin file (``avalanche data pin``) is ``avalanche-pins/v1`` JSON naming one checked run per dataset, with its capture
ID, Parquet file, bytes and sha256, and optionally the client commit its results were made with. A sweep reads the
``derived.staking-periods`` run it names, and refuses to start when the pin no longer verifies: a run missing, changed or
no longer passing its check, or a named commit that does not resolve. Each base model is built once per origin and model
from those staking periods.

This module reads pin files, so it lives outside ``model``: contracts K4 and K5 keep the model free of the catalog.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from ..core.catalog import DataError
from ..datasets import parquet_path, pins
from ..model import designs, runner
from ..model.engine import SimulationModel
from . import receipt

# Measured on 2026-10-07 by a v0.8 pilot at the Fortuna origin, 180 days, with v0.8's fitted inputs in each worker:
# 1,222 MiB at 5 runs and 2,092 MiB at 20, fitted as a base plus a per-run cost. RG1-V10 had 409 MiB at 5 runs without
# the fitted inputs, so this base is the safer default until a sweep's own pilot replaces it.
PILOT_BASE_MIB, PILOT_PER_RUN_MIB = 931.9, 58.0
MODELS = ("v0.7", "v0.8", "v0.8 separate")


def builder(periods: str, run_name: str, runs: int, timesteps: int) -> Callable[[Any, str], SimulationModel]:
    """The base model for an origin and model name, from the pinned staking periods."""
    def build(origin: Any, model: str) -> SimulationModel:
        day = date.fromisoformat(str(origin))
        if model == "v0.7":
            from ..model.lifecycle import ValidatorLifecycle, origin_inputs
            return ValidatorLifecycle(origin=day, inputs_source=run_name, runs=runs, timesteps=timesteps, **origin_inputs(periods, day))
        if model in ("v0.8", "v0.8 separate"):
            from ..model.fitted_lifecycle import FittedLifecycle, fitted_inputs
            large = 1_000_000 if model == "v0.8 separate" else None
            return FittedLifecycle(runs=runs, timesteps=timesteps, **fitted_inputs(periods, day, run_name, large_above_avax=large))
        raise ValueError(f"unknown model {model!r}; known: {', '.join(MODELS)}")
    return build


def rows(design: dict) -> list[dict]:
    """The design's rows, crossed with its origins and models, with the index running over the whole design."""
    if design["generator"] == "cartesian":
        inner = list(designs.cartesian(design["levels"], seed=design.get("seed", 0), name=design.get("name", "cartesian")))
    elif design["generator"] == "sobol":
        inner = list(designs.sobol(design["bounds"], design["m"], design["design_seed"], seed=design.get("seed", 0)))
    else:
        raise ValueError(f"unknown generator {design['generator']!r}")
    crossed = []
    for origin in design["origins"]:
        for model in design["models"]:
            for row in inner:
                crossed.append({**row, "index": len(crossed), "origin": origin, "model": model})
    return crossed


REBUILT_AFTER_ORIGIN = {"burned_navax", "total_supply_navax"}


class KpiReducer:
    """One row per run, KPI, horizon and cost level, from each run's daily table after the chain's table to its origin.
    A chain column the run does not produce, such as delegated stake for a model without delegations, is dropped, so
    its measures are left out rather than read from empty days. Burn and realized supply are rebuilt after the origin."""

    def __init__(self, chains: dict[str, Any], horizons: list[int], competing_yield: float, operating_costs: dict[str, float]):
        self.chains, self.horizons = chains, list(horizons)
        self.competing_yield, self.operating_costs = competing_yield, dict(operating_costs)

    def __call__(self, table, row):
        import pandas as pd

        from ..model import kpis

        origin = date.fromisoformat(str(row["origin"]))
        chain = self.chains[str(origin)]
        supply = float(chain.loc[pd.Timestamp(origin), "total_supply_navax"])
        burn = kpis.mean_daily_burn(chain, origin)
        frames = []
        for run_number, one in table.groupby("run"):
            daily = kpis.run_daily_table(one, origin, chain=chain)
            after = daily.index > pd.Timestamp(origin)
            produced = set(one["variable"]) | REBUILT_AFTER_ORIGIN
            daily = daily.drop(columns=[c for c in daily.columns if c not in produced and daily.loc[after, c].isna().any()])
            values = kpis.kpi_table(daily, origin, self.horizons, competing_yield=self.competing_yield,
                                    operating_costs=self.operating_costs, starting_supply_navax=supply, burn_navax_per_day=burn,
                                    missing="skip")
            values.insert(0, "run", int(run_number))
            frames.append(values)
        return pd.concat(frames, ignore_index=True)


def kpi_reducer(design: dict, pin_file: Path, periods: str) -> KpiReducer | None:
    """The design's KPI reducer with the chain's daily table for each origin, or None when it keeps daily paths."""
    spec = design.get("reducer")
    if spec is None:
        return None
    if spec.get("kind") != "kpis":
        raise ValueError(f"unknown reducer {spec.get('kind')!r}; known: kpis")
    if max(spec["horizons"]) > design["timesteps"]:
        raise ValueError(f"a KPI horizon of {max(spec['horizons'])} days is past the run's {design['timesteps']} timesteps")
    from ..model import kpis

    named = pins.runs(pin_file)
    if "derived.avax-monetary-daily" not in named:
        raise DataError(f"pin {pin_file} names no derived.avax-monetary-daily run, which the KPI reducer reads")
    ledger = str(parquet_path("derived.avax-monetary-daily", named["derived.avax-monetary-daily"]))
    chains = {str(origin): kpis.chain_daily_table(periods, ledger, date.fromisoformat(str(origin))) for origin in design["origins"]}
    return KpiReducer(chains, spec["horizons"], spec["competing_yield"], spec["operating_costs"])


def pinned_periods(pin_file: Path) -> tuple[str, str]:
    """The staking periods' Parquet path and run that a pin names, after the whole pin verifies."""
    findings = pins.verify(pin_file)
    if findings:
        raise DataError(f"pin {pin_file} does not verify: " + "; ".join(findings))
    named = pins.runs(pin_file)
    if "derived.staking-periods" not in named:
        raise DataError(f"pin {pin_file} names no derived.staking-periods run")
    run_name = named["derived.staking-periods"]
    return str(parquet_path("derived.staking-periods", run_name)), run_name


def scenario(pin: Path, origin: str, model: str, runs: int, timesteps: int, seed: int = 0, workers: int | str = "auto") -> dict:
    """A one-row design: one origin, one model and one seed from a pin file."""
    return {"generator": "cartesian", "levels": {"seed": [seed]}, "origins": [origin], "models": [model], "rows": 1, "pin": str(pin),
            "runs": runs, "timesteps": timesteps, "workers": workers}


def run(design_path: Path | dict, out: Path, build: Callable[[Any, str], SimulationModel] | None = None,
        reducer: Callable | None = None, pin: Path | None = None) -> dict:
    """Run the design, a file or its dictionary, into ``out`` and write ``receipt.json`` beside its rows. ``pin``
    replaces the design's pin file. Returns the receipt."""
    from ..core.clock import now

    design = dict(json.loads(design_path.read_text()) if isinstance(design_path, Path) else design_path)
    if pin is not None:
        design["pin"] = str(pin)
    pin_file = Path(design["pin"])
    periods, periods_run = pinned_periods(pin_file)
    build = build or builder(periods, periods_run, design["runs"], design["timesteps"])
    reducer = reducer or kpi_reducer(design, pin_file, periods)
    planned = rows(design)
    workers = design.get("workers", "auto")
    if workers == "auto":
        workers = runner.size_pool(runner.available_mib(), PILOT_BASE_MIB, PILOT_PER_RUN_MIB, design["runs"])["workers"]
    started = now()
    stats = runner.run_design(planned, design["rows"], build, out, workers=workers, reducer=reducer)
    specification = stats.pop("base_specifications")[0]
    made = receipt.build_sweep(out, specification, stats["design_hash"], len(planned), stats, pin_file,
                               sorted({row["seed"] for row in planned}), started, now())
    made["sweep"]["design_file"] = design
    made["receipt_id"] = receipt.sha256(receipt.canonical_bytes({k: v for k, v in made.items() if k != "receipt_id"}))[:16]
    receipt.write(made, out / "receipt.json")
    return made
