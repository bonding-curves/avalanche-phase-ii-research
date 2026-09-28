"""The sweep's trajectory tensor: parameter sets x scenarios x seeds.

Parameter sets are a seeded Latin hypercube over the proposal's controllable ranges. Scenarios pair an external
yield path with a price path. Price paths are geometric Brownian motion in log space, calibrated from
``avax_usdt_daily`` and seeded by (design seed, scenario, seed) so every parameter set sees the same price draws
(common random numbers).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import qmc

from ..catalog import canonical_bytes, sha256
from .mechanisms import DEFAULT_ARGS

DESIGN_SEED = 20260928
START_DATE = "2025-01-01"
DAYS = 365
SEEDS = (0, 1, 2, 3, 4)
N_PARAMETER_SETS = 500

# Controllable parameters and their sweep ranges (proposal). Days are rounded to whole days.
PARAMETER_RANGES: dict[str, tuple[float, float]] = {
    "min_consumption_rate": (0.07, 0.10),
    "max_consumption_rate": (0.10, 0.14),
    "min_stake_days": (2, 28),
    "max_stake_days": (180, 730),
    "min_delegation_fee": (0.0, 0.05),
}
INTEGER_PARAMETERS = ("min_stake_days", "max_stake_days")
MECHANISMS = ("linear", "piecewise", "state_dependent", "node_age")
CONTROLLABLE = (*PARAMETER_RANGES, "mechanism")

YIELDS = (0.03, 0.05, 0.07, 0.10)
MARKETS = ("bull", "neutral", "bear")
SHOCK_DAY = 90
SHOCK_DAYS = 7
SHOCK_DROP = 0.50
STRESS_YIELD_RISE = 0.03  # annual fraction added linearly over the horizon on stress paths
CALIBRATION_WINDOW = ("2022-01-01", "2024-12-31")


@dataclass(frozen=True)
class PriceCalibration:
    """GBM inputs. ``drift_log_annual`` is the drift of log price per year, so the median path grows by exp(drift)."""

    start_price_usd: float
    sigma_annual: float
    drift_log_annual: dict[str, float]
    window: tuple[str, str]
    source: str


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: int
    name: str
    kind: str  # base, shock, stress
    market: str
    yield_start: float
    yield_rise: float = 0.0
    shock_day: int | None = None
    shock_days: int = SHOCK_DAYS
    shock_drop: float = 0.0


@dataclass(frozen=True)
class Design:
    parameters: pd.DataFrame = field(compare=False)
    scenarios: tuple[ScenarioSpec, ...]
    seeds: tuple[int, ...]
    calibration: PriceCalibration
    days: int = DAYS
    start_date: str = START_DATE
    design_seed: int = DESIGN_SEED

    @property
    def n_trajectories(self) -> int:
        return len(self.parameters) * len(self.scenarios) * len(self.seeds)

    def trajectory(self, trajectory_id: int) -> tuple[int, int, int]:
        """(parameter row, scenario index, seed) for a trajectory id. Parameter-major, then scenario, then seed."""
        n_seeds, n_scenarios = len(self.seeds), len(self.scenarios)
        seed_index = trajectory_id % n_seeds
        scenario_index = (trajectory_id // n_seeds) % n_scenarios
        return trajectory_id // (n_seeds * n_scenarios), scenario_index, self.seeds[seed_index]

    def describe(self) -> dict[str, Any]:
        rows = self.parameters.assign(mechanism_args=self.parameters["mechanism_args"].map(list)).to_dict("records")
        return {
            "design_seed": self.design_seed,
            "start_date": self.start_date,
            "days": self.days,
            "seeds": list(self.seeds),
            "parameter_ranges": {key: list(value) for key, value in PARAMETER_RANGES.items()},
            "mechanisms": list(MECHANISMS),
            "mechanism_args": {name: _jsonable(args) for name, args in DEFAULT_ARGS.items() if name in MECHANISMS},
            "calibration": _jsonable(asdict(self.calibration)),
            "scenarios": [asdict(spec) for spec in self.scenarios],
            "parameter_sets": json.loads(json.dumps(rows, default=_jsonable)),
            "counts": {
                "parameter_sets": len(self.parameters), "scenarios": len(self.scenarios),
                "seeds": len(self.seeds), "trajectories": self.n_trajectories,
            },
        }

    def digest(self) -> str:
        return sha256(canonical_bytes(self.describe()))


def _jsonable(value: Any) -> Any:
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, np.generic):
        return value.item()
    return value


def calibrate_prices(con: Any, start_date: str = START_DATE, window: tuple[str, str] = CALIBRATION_WINDOW) -> PriceCalibration:
    """Volatility from daily log returns and bull and bear drifts from rolling 365-day log returns in the window.

    sigma = standard deviation of daily log returns x sqrt(365). Bull drift = 75th percentile and bear drift =
    25th percentile of 365-day log returns. Neutral drift is zero. The start price is the close on ``start_date``.
    """
    sigma, q25, q75, windows = con.execute(
        """
        WITH r AS (
            SELECT log_return,
                   sum(log_return) OVER w AS r365,
                   count(log_return) OVER w AS n
            FROM avax_usdt_daily
            WHERE observation_date BETWEEN ?::DATE AND ?::DATE
            WINDOW w AS (ORDER BY observation_date ROWS BETWEEN 364 PRECEDING AND CURRENT ROW)
        )
        SELECT stddev_samp(log_return) * sqrt(365),
               quantile_cont(r365, 0.25) FILTER (WHERE n = 365),
               quantile_cont(r365, 0.75) FILTER (WHERE n = 365),
               count(*) FILTER (WHERE n = 365)
        FROM r
        """,
        [window[0], window[1]],
    ).fetchone()
    price = con.execute("SELECT close_usdt FROM avax_usdt_daily WHERE observation_date = ?::DATE", [start_date]).fetchone()
    if price is None or sigma is None or not windows:
        raise ValueError("avax_usdt_daily lacks the start price or the calibration window")
    return PriceCalibration(
        start_price_usd=float(price[0]),
        sigma_annual=float(sigma),
        drift_log_annual={"bull": float(q75), "neutral": 0.0, "bear": float(q25)},
        window=window,
        source="avax_usdt_daily (Binance AVAXUSDT daily candles)",
    )


def scenario_specs() -> tuple[ScenarioSpec, ...]:
    """12 base paths (yield x market), 4 shock paths (neutral market, -50% over a week from day 90), and
    4 stress paths (bear market, yield rising by ``STRESS_YIELD_RISE`` over the year), one per yield level."""
    specs: list[ScenarioSpec] = []
    for level in YIELDS:
        for market in MARKETS:
            specs.append(ScenarioSpec(len(specs), f"y{level:.2f}-{market}", "base", market, level))
    for level in YIELDS:
        specs.append(ScenarioSpec(len(specs), f"y{level:.2f}-shock", "shock", "neutral", level,
                                  shock_day=SHOCK_DAY, shock_drop=SHOCK_DROP))
    for level in YIELDS:
        specs.append(ScenarioSpec(len(specs), f"y{level:.2f}-stress", "stress", "bear", level, yield_rise=STRESS_YIELD_RISE))
    return tuple(specs)


def price_path(spec: ScenarioSpec, calibration: PriceCalibration, seed: int, days: int, design_seed: int = DESIGN_SEED) -> np.ndarray:
    """Daily USD price, day 0 at the start price. Log price moves by drift/365 + sigma/sqrt(365) * z each day."""
    rng = np.random.default_rng([design_seed, spec.scenario_id, seed])
    steps = calibration.drift_log_annual[spec.market] / 365 + calibration.sigma_annual / np.sqrt(365) * rng.standard_normal(days - 1)
    log_price = np.log(calibration.start_price_usd) + np.concatenate([[0.0], np.cumsum(steps)])
    if spec.shock_day is not None and spec.shock_drop > 0:
        fall = np.clip((np.arange(days) - spec.shock_day + 1) / spec.shock_days, 0.0, 1.0)
        log_price = log_price + np.log(1 - spec.shock_drop) * fall
    return np.exp(log_price)


def yield_path(spec: ScenarioSpec, days: int) -> np.ndarray:
    """Annual external yield as a fraction for each day."""
    return spec.yield_start + spec.yield_rise * np.arange(days) / 365


def parameter_sets(n: int = N_PARAMETER_SETS, design_seed: int = DESIGN_SEED) -> pd.DataFrame:
    """Latin hypercube over ``PARAMETER_RANGES`` plus one categorical dimension for the mechanism."""
    names = list(PARAMETER_RANGES)
    sample = qmc.LatinHypercube(d=len(names) + 1, seed=design_seed).random(n)
    lower = np.array([PARAMETER_RANGES[name][0] for name in names], dtype=float)
    upper = np.array([PARAMETER_RANGES[name][1] for name in names], dtype=float)
    values = pd.DataFrame(qmc.scale(sample[:, :-1], lower, upper), columns=names)
    for name in INTEGER_PARAMETERS:
        values[name] = values[name].round().astype(int)
    mechanism = np.minimum((sample[:, -1] * len(MECHANISMS)).astype(int), len(MECHANISMS) - 1)
    values["mechanism"] = [MECHANISMS[index] for index in mechanism]
    values["mechanism_args"] = [DEFAULT_ARGS[name] for name in values["mechanism"]]
    if (values["max_consumption_rate"] < values["min_consumption_rate"]).any():
        raise ValueError("a parameter set has max_consumption_rate below min_consumption_rate")
    values.insert(0, "param_id", np.arange(n))
    return values


def build_design(
    calibration: PriceCalibration,
    n_parameter_sets: int = N_PARAMETER_SETS,
    seeds: tuple[int, ...] = SEEDS,
    days: int = DAYS,
    design_seed: int = DESIGN_SEED,
    start_date: str = START_DATE,
    scenarios: tuple[ScenarioSpec, ...] | None = None,
) -> Design:
    return Design(
        parameters=parameter_sets(n_parameter_sets, design_seed),
        scenarios=scenario_specs() if scenarios is None else scenarios,
        seeds=tuple(seeds),
        calibration=calibration,
        days=days,
        start_date=start_date,
        design_seed=design_seed,
    )
