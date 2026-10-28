"""A sweep from a design file: rows, base models built from pinned data, the row runner, and the sweep's receipt.

Two commands run it:

    avalanche model sweep DESIGN OUT [--pin PIN]
    avalanche model run PIN OUT --origin 2025-04-08 [--model v0.8.0] [--runs 20] [--timesteps 180] [--seed 0]

``model run`` runs the released model, ``RELEASED_MODEL`` in ``avalanche_research.model``, unless ``--model`` names
another variant.

The design file is JSON:

    {"generator": "cartesian", "levels": {"renewal_probability": [0.7, 0.8]}, "seed": 0,
     "origins": ["2025-04-08"], "models": ["v0.7"], "rows": 2,
     "pin": "data/pins/p5-v0.7-report.json", "runs": 20, "timesteps": 180, "workers": "auto"}

- ``generator``: ``cartesian``, crossing every ``levels`` list, or ``sobol`` with ``bounds`` (name to low and high),
  ``m`` (2^m points) and ``design_seed``. A level named ``seed`` sets each row's random seed. Other levels are model
  settings.
- ``origins``: model origin days, each before the validation lockbox. ``models``: variant names from
  ``VARIANTS`` in ``avalanche_research.model.variants``, such as ``v0.8.0``, ``v0.8`` or ``v0.7``. The builder refuses
  any other name, and ``v0.8.1 stub``.
- ``rows``: the generator's rows times origins times models, stated so a wrong design stops before anything runs.
- ``pin``: a pin file (below). ``--pin`` on the command replaces it.
- ``runs`` per row, ``timesteps`` in days, and ``workers``: a number, or ``auto`` to size the pool from free memory at
  launch and a measured v0.8 cost per worker until a sweep's own pilot replaces it.

``model run`` is a one-row design: one origin, one model and one seed.

``"generator": "explicit"`` with ``rows_file``, a JSON list of rows, takes every row as written, such as a Saltelli
design made elsewhere; each row sets its ``seed``, and the required ``rows_sha256`` must match the file. ``draws_file``
(CSV, gzipped CSV or Parquet, with a required ``draws_sha256``) attaches a table of parameter draws to each fitted base
model, and a row's ``draw: k`` runs with row k of it alone, so rows that share a ``seed`` and a ``draw`` share their
noise key. A file-based design resolves relative row/draw file names from its own folder; a dictionary keeps
the caller's working-directory paths. A row's ``outside_yield_pp`` is also the competing yield the KPI reducer uses for that row.

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

import io
import json
import math
import tempfile
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


def builder(periods: str, run_name: str, runs: int, timesteps: int, draws: Any = None) -> Callable[[Any, str], SimulationModel]:
    """The base model for an origin and model name, from the pinned staking periods, with ``draws`` attached to a v0.8
    base when given."""
    def build(origin: Any, model: str) -> SimulationModel:
        from ..model.variants import VARIANTS

        day = date.fromisoformat(str(origin))
        if model in VARIANTS and model != "v0.8.1 stub":
            variant = VARIANTS[model]
            prepared = variant.prepare(periods, day, run_name, draws=0 if draws is not None else runs)
            return variant.simulation(prepared, seed=0, timesteps=timesteps, runs=runs,
                                      draws=draws if draws is not None else prepared.draws)
        raise ValueError(f"unknown sweep model {model!r}; known: {', '.join(name for name in VARIANTS if name != 'v0.8.1 stub')}")
    return build


def rows(design: dict) -> list[dict]:
    """The design's rows, crossed with its origins and models, with the index running over the whole design."""
    if design["generator"] == "cartesian":
        inner = list(designs.cartesian(design["levels"], seed=design.get("seed", 0), name=design.get("name", "cartesian")))
    elif design["generator"] == "sobol":
        inner = list(designs.sobol(design["bounds"], design["m"], design["design_seed"], seed=design.get("seed", 0)))
    elif design["generator"] == "explicit":
        path = Path(design["rows_file"])
        if not design.get("rows_sha256"):
            raise ValueError("rows_file requires rows_sha256")
        body = path.read_bytes()
        if receipt.sha256(body) != design["rows_sha256"]:
            raise ValueError(f"{path} does not match the design's rows_sha256")
        listed = json.loads(body)
        if not isinstance(listed, list) or not listed or any(not isinstance(row, dict) for row in listed):
            raise ValueError("explicit rows must be a nonempty JSON list of objects")
        missing = [i for i, row in enumerate(listed) if "seed" not in row]
        if missing:
            raise ValueError(f"explicit rows must each set a seed; rows {missing[:5]} do not")
        for row in listed:
            if type(row["seed"]) is not int or row["seed"] < 0:
                raise ValueError("explicit row seed must be a nonnegative integer")
            if "draw" in row and (type(row["draw"]) is not int or row["draw"] < 0):
                raise ValueError("explicit row draw must be a nonnegative integer")
        inner = [{"design": design.get("name", "explicit"), **row} for row in listed]
    else:
        raise ValueError(f"unknown generator {design['generator']!r}")
    crossed = []
    for origin in design["origins"]:
        for model in design["models"]:
            for row in inner:
                crossed.append({**row, "index": len(crossed), "origin": origin, "model": model})
    return crossed


class KpiReducer:
    """One row per run, KPI, horizon and cost level, from each run's daily table after the chain's table to its origin.
    By default a measure whose inputs the run does not produce is left out. ``missing='raise'`` refuses it."""

    def __init__(self, chains: dict[str, Any], horizons: list[int], competing_yield: float, operating_costs: dict[str, float],
                 missing: str = "skip", secured_value_usd: float | None = None):
        if missing not in ("raise", "skip"):
            raise ValueError("missing is 'raise' or 'skip'")
        self.chains, self.horizons = chains, list(horizons)
        self.competing_yield, self.operating_costs = competing_yield, dict(operating_costs)
        self.missing = missing
        self.secured_value_usd = secured_value_usd

    def competing_for(self, row) -> float:
        """The row's own outside yield as a fraction when it sets one, otherwise the design's competing yield."""
        value = row.get("outside_yield_pp")
        if value is None:
            return self.competing_yield
        if isinstance(value, bool) or not math.isfinite(float(value)):
            raise ValueError("outside_yield_pp must be a finite number")
        return float(value) / 100

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
            values = kpis.kpi_table(daily, origin, self.horizons, competing_yield=self.competing_for(row),
                                    operating_costs=self.operating_costs, starting_supply_navax=supply, burn_navax_per_day=burn,
                                    missing=self.missing, secured_value_usd=self.secured_value_usd)
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
    return KpiReducer(chains, spec["horizons"], spec["competing_yield"], spec["operating_costs"], spec.get("missing", "skip"),
                      spec.get("secured_value_usd"))


def load_draws(design: dict) -> Any:
    """The design's table of parameter draws, or None. Its required ``draws_sha256`` must match the file."""
    if not design.get("draws_file"):
        return None
    import pandas as pd

    path = Path(design["draws_file"])
    if not design.get("draws_sha256"):
        raise ValueError("draws_file requires draws_sha256")
    body = path.read_bytes()
    if receipt.sha256(body) != design["draws_sha256"]:
        raise ValueError(f"{path} does not match the design's draws_sha256")
    if path.suffix == ".parquet":
        import duckdb
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "draws.parquet"
            snapshot.write_bytes(body)
            return duckdb.execute("SELECT * FROM read_parquet(?)", [str(snapshot)]).df()
    return pd.read_csv(io.BytesIO(body), compression="gzip" if path.suffix == ".gz" else None)


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
    authored_files = {}
    for stem in ("rows", "draws"):
        if design.get(f"{stem}_file"):
            authored_files[f"{stem}_file"] = design[f"{stem}_file"]
            path = Path(design[f"{stem}_file"])
            if isinstance(design_path, Path) and not path.is_absolute():
                path = design_path.absolute().parent / path
                design[f"{stem}_file"] = str(path)
            if not design.get(f"{stem}_sha256"):
                raise ValueError(f"{stem}_file requires {stem}_sha256")
            digest = receipt.sha256(path.read_bytes())
            if design.get(f"{stem}_sha256") and design[f"{stem}_sha256"] != digest:
                raise ValueError(f"{path} does not match the design's {stem}_sha256")
    if design.get("draws_file") and design["runs"] != 1:
        raise ValueError("an external per-row draw table requires one trajectory per row")
    if design.get("draws_file") and len(design["origins"]) != 1:
        raise ValueError("an external draw table requires exactly one fitting origin")
    if design.get("draws_file") and len(design["models"]) != 1:
        raise ValueError("an external draw table requires exactly one fitted model")
    if pin is not None:
        design["pin"] = str(pin)
    pin_file = Path(design["pin"])
    periods, periods_run = pinned_periods(pin_file)
    draws = load_draws(design)
    planned = rows(design)
    if draws is not None and any(type(row.get("draw")) is not int or not 0 <= row["draw"] < len(draws) for row in planned):
        raise ValueError("every row must select a draw present in the external draw table")
    build = build or builder(periods, periods_run, design["runs"], design["timesteps"], draws)
    reducer = reducer or kpi_reducer(design, pin_file, periods)
    workers = design.get("workers", "auto")
    if workers == "auto":
        workers = runner.size_pool(runner.available_mib(), PILOT_BASE_MIB, PILOT_PER_RUN_MIB, design["runs"])["workers"]
    started = now()
    stats = runner.run_design(planned, design["rows"], build, out, workers=workers, reducer=reducer)
    specifications = stats.pop("base_specifications")
    made = receipt.build_sweep(out, specifications, stats["design_hash"], len(planned), stats, pin_file,
                               sorted({row["seed"] for row in planned}), started, now())
    made["sweep"]["design_file"] = {**design, **authored_files}
    made["receipt_id"] = receipt.sha256(receipt.canonical_bytes({k: v for k, v in made.items() if k != "receipt_id"}))[:16]
    receipt.write(made, out / "receipt.json")
    return made
