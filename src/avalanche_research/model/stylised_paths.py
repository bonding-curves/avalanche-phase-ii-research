"""Model runs as the daily paths the stylised-fact tests read, and the facts each v0.9.0 model must pass.

:mod:`avalanche_research.model.stylised_facts` measures ten facts of the record on daily paths. This module turns a
run's long table into those paths and names the facts a model is required to reproduce. A required fact that did not
run, because its columns are absent or the path is too short, counts as a failure, never as a pass.

The model counts an ending as renewed when the same node starts its next commitment the day the last one ends. The
record also counts a node that comes back within 7 days, so a model path's renewal share is the immediate part of the
record's.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from avalanche_research.model.stylised_facts import evaluate

NAVAX_PER_AVAX = 10**9

REQUIRED = {
    "v0.9.0 defaults": ("SF4",),
    "v0.9.0 loops": ("SF4", "SF6", "SF7"),
}
"""The facts each v0.9.0 model must pass. Both must leave total stake unmoved by price (SF4). The loops model's renewal
reads the dollar margin, so it must also move the validator count (SF6) and renewal (SF7) with price."""

_PRICE_AND_MARKET = {
    "SF1": "the price path's volatility by market class, which the v0.9.1 regime generator sets",
    "SF2": "the price path's calm and turbulent spells, which the v0.9.1 regime generator sets",
    "SF3": "the price path's swings, which the v0.9.1 regime generator sets",
    "SF5": "stake through a fall of 75% or more, which only some paths contain",
    "SF8": "renewal by volatility state, which needs the volatility response that neither model turns on",
    "SF9": "first-ever arrivals by market class, which needs entry to read the market",
    "SF10": "the dollar reward's range, which rests on the price path, and the lending yield by class, which the model holds fixed",
}
REPORTED = {
    "v0.9.0 defaults": {**_PRICE_AND_MARKET,
                        "SF6": "the validator count on price, which needs renewal to read the dollar margin",
                        "SF7": "renewal on price moves, which needs renewal to read the dollar margin"},
    "v0.9.0 loops": _PRICE_AND_MARKET,
}
"""The facts reported for each v0.9.0 model and not required, each with the reason."""


def paths_from_table(table: pd.DataFrame, origin: date) -> list[pd.DataFrame]:
    """One daily path per simulation and run of an engine long table, indexed by calendar day from the origin.

    The path carries the price when the run has a price path, staked AVAX as validator plus delegated stake, the
    active validator count, and, when the run records turnover (``record_turnover``), the day's endings, immediate
    renewals and first-ever starts. A column the run does not write is left out, so its tests report not applicable."""
    names = {"active_validators": "active_validators", "ended_validators": "endings", "renewed_validators": "renewed",
             "first_ever_validators": "first_ever"}
    paths = []
    for _, run in table.groupby(["simulation", "run"], sort=True):
        wide = run.pivot_table(index="timestep", columns="variable", values="value", aggfunc="first").sort_index()
        days = pd.DatetimeIndex([pd.Timestamp(origin + timedelta(days=int(t))) for t in wide.index])
        path = pd.DataFrame(index=days)
        if "price_usd" in run.columns:
            path["price_usd"] = run.groupby("timestep")["price_usd"].first().sort_index().to_numpy(dtype=float)
        staked = wide["active_validator_stake_navax"].astype(float)
        if "active_delegated_stake_navax" in wide.columns:
            staked = staked + wide["active_delegated_stake_navax"].astype(float)
        path["staked_avax"] = staked.to_numpy() / NAVAX_PER_AVAX
        for variable, column in names.items():
            if variable in wide.columns:
                path[column] = wide[variable].to_numpy(dtype=float)
        paths.append(path)
    return paths


def required_failures(results: pd.DataFrame, model: str) -> pd.DataFrame:
    """The rows of ``evaluate``'s results for the model's required facts that did not pass, including those that did
    not run."""
    rows = results[results["code"].isin(REQUIRED[model]) & results["lo"].notna()]  # diagnostics carry no band
    return rows[~rows["passed"].eq(True)]


def check(paths: list[pd.DataFrame], model: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every fact's result on the paths, and the required facts that did not pass."""
    results = evaluate(paths)
    return results, required_failures(results, model)
