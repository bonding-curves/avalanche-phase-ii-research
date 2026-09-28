"""Exogenous environment of a trajectory: AVAX price and the external yield, one value per day."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np


@dataclass
class Scenario:
    """price_usd: USD per AVAX per day. external_yield: annual rate as a fraction per day (0.043 is 4.3%)."""

    name: str
    price_usd: np.ndarray
    external_yield: np.ndarray
    start_date: str

    def __post_init__(self) -> None:
        self.price_usd = np.asarray(self.price_usd, dtype=float)
        self.external_yield = np.asarray(self.external_yield, dtype=float)
        if self.price_usd.ndim != 1 or self.price_usd.shape != self.external_yield.shape:
            raise ValueError("price and external yield must be one-dimensional arrays of the same length")
        if np.any(~np.isfinite(self.price_usd)) or np.any(self.price_usd <= 0) or np.any(~np.isfinite(self.external_yield)):
            raise ValueError("price must be positive and both series finite")
        date.fromisoformat(self.start_date)

    @property
    def days(self) -> int:
        return int(self.price_usd.shape[0])


def constant(name: str, price_usd: float, external_yield: float, days: int, start_date: str = "2025-01-01") -> Scenario:
    return Scenario(name, np.full(days, float(price_usd)), np.full(days, float(external_yield)), start_date)


def observed(con: Any, start_date: str, days: int, name: str = "observed") -> Scenario:
    """Observed daily AVAX/USDT close (``binance.avax-usdt-daily``) and the 3-month Treasury par yield
    (``us-treasury.par-yield-daily`` tenor ``3m``, stored as a fraction), each carried forward over days
    without an observation, for ``days`` days from ``start_date``."""
    start = date.fromisoformat(start_date)
    end = start + timedelta(days=days - 1)
    rows = con.execute(
        """
        WITH calendar AS (SELECT unnest(generate_series(?::DATE - INTERVAL 10 DAY, ?::DATE, INTERVAL 1 DAY))::DATE AS d)
        SELECT c.d, last_value(p.close_usdt IGNORE NULLS) OVER w, last_value(y.yield_rate IGNORE NULLS) OVER w
        FROM calendar c
        LEFT JOIN avax_usdt_daily p ON p.observation_date = c.d
        LEFT JOIN (SELECT observation_date, yield_rate FROM par_yield_daily WHERE tenor = '3m') y ON y.observation_date = c.d
        WINDOW w AS (ORDER BY c.d ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        ORDER BY c.d
        """,
        [start.isoformat(), end.isoformat()],
    ).fetchall()
    rows = [row for row in rows if row[0] >= start]
    if len(rows) != days or any(row[1] is None or row[2] is None for row in rows):
        raise ValueError(f"price or yield missing between {start} and {end}")
    return Scenario(name, np.array([row[1] for row in rows]), np.array([row[2] for row in rows]), start.isoformat())
