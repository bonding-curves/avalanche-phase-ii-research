"""The AVAX price as an environmental scenario: a seeded geometric random walk from the price at the origin.

The model's reward rule and behaviour blocks read AVAX amounts. The price enters as a scenario, not as a fitted law:
a daily log-price path with a drift and a volatility held for the whole run, drawn under the run's own keyed stream
(``Streams.generator("price")``), so two runs with the same seed and run number walk the same path whatever else
changes. The path is read by the dollar measures of security (``model.kpis``). It does not move renewal or entry in
this version: the outside yield stays nominal, and the market shifts of the sweep designs carry the record's
behaviour in bull and bear windows. A term that would let an expected appreciation enter the yield gap is not fitted,
because the record before the held-back period cannot separate it from the market shifts fitted on the same windows.

The scenarios' drift and volatility are bounded from the record before the held-back period: the DefiLlama daily
price (dataset ``defillama.avax-price-daily``, run ``avax-price-2026-10-05``, one observation a day, log returns over
consecutive observed days) in the bull, bear and range windows of the environment report's regimes, the same windows
the market shifts of ``scripts/m2_market_sweep_design.py`` pool. Drift is the mean daily log return times 365 and
volatility the daily standard deviation times the square root of 365. The neutral scenario has no expected move,
which lies within the range windows' bounds, and the range windows' volatility.
"""

from __future__ import annotations

from datetime import date

import numpy as np

PRICE_DATASET = "defillama.avax-price-daily"
PRICE_RUN = "avax-price-2026-10-05"

PRICE_WINDOWS: dict[str, tuple[tuple[str, str, str, int, float, float], ...]] = {
    "bull": (
        ("G2", "2021-05-12", "2021-11-21", 186, 3.392, 1.505),
        ("G6", "2023-10-16", "2024-03-31", 92, 4.269, 1.002),
        ("G8", "2024-11-06", "2025-01-20", 37, 6.402, 1.297),
    ),
    "bear": (
        ("G3", "2021-11-22", "2022-05-06", 102, -2.256, 1.177),
        ("G4", "2022-05-07", "2022-12-31", 157, -3.291, 1.129),
        ("G10", "2025-10-07", "2025-11-18", 20, -6.176, 0.984),
    ),
    "range": (
        ("G5", "2023-01-01", "2023-10-15", 226, 0.162, 0.687),
        ("G7", "2024-04-01", "2024-11-05", 163, -1.918, 0.884),
        ("G9", "2025-01-21", "2025-10-06", 128, -2.004, 1.012),
    ),
}
"""Per regime: code, first day, last day, observed daily returns, drift a year, volatility a year. G10 is cut at the
day before the held-back period."""

PRICE_SCENARIOS: dict[str, tuple[float, float]] = {
    "bull": (4.002, 1.350),
    "neutral": (0.0, 0.840),
    "bear": (-3.120, 1.134),
}
"""Each scenario's drift and volatility a year at full strength: the pooled bull windows (315 daily returns), no
expected move at the pooled range windows' volatility (517), and the pooled bear windows (279)."""

PRICE_BOUNDS: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    state: ((min(w[4] for w in windows), max(w[4] for w in windows)), (min(w[5] for w in windows), max(w[5] for w in windows)))
    for state, windows in PRICE_WINDOWS.items()
}
"""Per regime: the range of drift and of volatility across its windows, which a sweep of a scenario's strength stays within."""

DAYS_PER_YEAR = 365


def scenario_price(market: str, strength: float = 1.0) -> tuple[float, float]:
    """A scenario's drift and volatility a year at ``strength`` in [0, 1]: the drift scales with the strength, and
    the volatility moves from the neutral scenario's to the scenario's own."""
    if market not in PRICE_SCENARIOS:
        raise ValueError(f"unknown price scenario {market!r}; known: {', '.join(PRICE_SCENARIOS)}")
    if not 0.0 <= strength <= 1.0:
        raise ValueError(f"the strength must be within [0, 1], not {strength}")
    drift, volatility = PRICE_SCENARIOS[market]
    neutral_volatility = PRICE_SCENARIOS["neutral"][1]
    return drift * strength, neutral_volatility + strength * (volatility - neutral_volatility)


def price_path(price0_usd: float, drift_pa: float, volatility_pa: float, timesteps: int, generator: np.random.Generator) -> np.ndarray:
    """The price on each of ``timesteps`` days after the origin: a geometric random walk from ``price0_usd`` with the
    yearly drift of the log price ``drift_pa`` and volatility ``volatility_pa``, so the expected price grows at the
    drift and the price stays positive on every day."""
    if not (price0_usd > 0 and np.isfinite(price0_usd)):
        raise ValueError(f"the origin price must be positive and finite, not {price0_usd}")
    if timesteps < 1:
        raise ValueError("a price path needs at least one day")
    if volatility_pa < 0:
        raise ValueError("volatility cannot be negative")
    dt = 1.0 / DAYS_PER_YEAR
    shocks = generator.standard_normal(timesteps) if volatility_pa > 0 else np.zeros(timesteps)
    steps = (drift_pa - 0.5 * volatility_pa**2) * dt + volatility_pa * np.sqrt(dt) * shocks
    return float(price0_usd) * np.exp(np.cumsum(steps))


def price_at(parquet: str, origin: date) -> tuple[float, date]:
    """The last recorded price at or before ``origin`` from a ``defillama.avax-price-daily`` Parquet file, as the mean of
    that day's observations, with the day it was observed."""
    import duckdb

    row = duckdb.execute(
        "SELECT observation_date::DATE AS day, avg(price_usd) FROM read_parquet(?) WHERE observation_date::DATE <= ? "
        "GROUP BY 1 ORDER BY 1 DESC LIMIT 1",
        [str(parquet), origin],
    ).fetchone()
    if row is None:
        raise ValueError(f"no price at or before {origin} in {parquet}")
    day, price = row
    return float(price), day if isinstance(day, date) else date.fromisoformat(str(day))
