"""A sweep from a design file: rows, base models built from pinned data, the row runner, and the sweep's receipt.

v0, unreviewed. The design file is JSON:

    {"generator": "cartesian", "levels": {"renewal_probability": [0.7, 0.8]}, "seed": 0,
     "origins": ["2025-04-08"], "models": ["v0.7"], "rows": 2,
     "pin": "data/pins/p5-v0.7-report.json", "runs": 20, "timesteps": 180, "workers": "auto"}

or ``"generator": "sobol"`` with ``bounds``, ``m`` and ``design_seed``. Rows are crossed with every origin and model,
so the row count is the generator's rows times origins times models; ``rows`` must say so before anything runs. Each
base model is built once per origin and model from the staking periods the pin names. With ``workers: "auto"`` the pool
is sized from free memory at launch and RG1's measured cost per run until a pilot replaces it.

This module reads pin files, so it lives outside ``model``: contracts K4 and K5 keep the model free of the catalog.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from ..datasets import parquet_path, pins
from ..model import designs, runner
from ..model.engine import SimulationModel
from . import receipt

# RG1-V10's measurement on v0.8, fitted as base plus per run: 409 MiB at 5 runs, 2,100 MiB at 40.
RG1_BASE_MIB, RG1_PER_RUN_MIB = 167.4, 48.31
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


def run(design_path: Path, out: Path, build: Callable[[Any, str], SimulationModel] | None = None,
        reducer: Callable | None = None) -> dict:
    """Run the design into ``out`` and write ``receipt.json`` beside its rows. Returns the receipt."""
    from ..core.clock import now

    design = json.loads(design_path.read_text())
    pin_file = Path(design["pin"])
    named = pins.runs(pin_file)
    periods_run = named["derived.staking-periods"]
    build = build or builder(str(parquet_path("derived.staking-periods", periods_run)), periods_run, design["runs"], design["timesteps"])
    planned = rows(design)
    workers = design.get("workers", "auto")
    if workers == "auto":
        workers = runner.size_pool(runner.available_mib(), RG1_BASE_MIB, RG1_PER_RUN_MIB, design["runs"])["workers"]
    started = now()
    stats = runner.run_design(planned, design["rows"], build, out, workers=workers, reducer=reducer)
    first = build(planned[0]["origin"], planned[0]["model"])
    made = receipt.build_sweep(out, first.specification(), stats["design_hash"], len(planned), stats, pin_file,
                               sorted({row["seed"] for row in planned}), started, now())
    made["sweep"]["design_file"] = design
    made["receipt_id"] = receipt.sha256(receipt.canonical_bytes({k: v for k, v in made.items() if k != "receipt_id"}))[:16]
    receipt.write(made, out / "receipt.json")
    return made
