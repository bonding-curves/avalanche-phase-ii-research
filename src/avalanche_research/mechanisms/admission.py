"""Admission mechanisms as Param classes: which validator stakes the chain accepts, by duration.

The chain admits a Primary Network validator stake of at least 2,000 AVAX for any duration from the
minimum, 48 hours since Helicon under ACP-273, to one year. The admission frontier Hash presented on
2026-09-29 replaces the flat minimum with one that falls as duration rises, the bounded harmonic curve:

    S_min(d) = S_floor + (S_short - S_floor) * eta(d) ** p
    eta(d)   = (1/d - 1/d_max) / (1/d_min - 1/d_max)

so short commitments post more stake and long ones less. Each admission mechanism offers:

- ``min_stake_avax``: the minimum stake at a duration.
- ``admits``: whether one stake is accepted.
- ``curve``: minimum stake and stake-days by duration, a table ready to plot.
- ``admitted``: which of a set of real stakes the rule would accept, by count and by AVAX.
- ``check``: the properties the rule must keep, returned as a list of failures.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from itertools import pairwise

import pandas as pd
import param

from avalanche_research.model.protocol import (
    MAINNET,
    MAINNET_UPGRADES,
    min_stake_duration_seconds,
)
from avalanche_research.model.types import SECONDS_PER_DAY

AVAX = 10**9
DEFAULT_DURATIONS_DAYS = (2, 3, 5, 7, 10, 14, 21, 30, 45, 60, 90, 120, 180, 270, 365)
SYBIL_BASELINE_AVAX_DAYS = 2_000 * 14


class AdmissionRule(param.Parameterized):
    """Which validator stakes are admitted. The base class is the chain's flat minimum."""

    label = param.String(default="Chain today", doc="Name shown in tables and legends")

    def duration_bounds_days(self, start: datetime) -> tuple[float, float]:
        low = min_stake_duration_seconds(start, MAINNET, MAINNET_UPGRADES, role="validator") / SECONDS_PER_DAY
        return low, MAINNET.max_stake_duration_seconds / SECONDS_PER_DAY

    def min_stake_avax(self, duration_days: float) -> float:
        return MAINNET.min_validator_stake_navax / AVAX

    def admits(self, stake_navax: int, duration_seconds: int, start: datetime) -> bool:
        low, high = self.duration_bounds_days(start)
        days = duration_seconds / SECONDS_PER_DAY
        if not low <= days <= high or stake_navax > MAINNET.max_validator_stake_navax:
            return False
        return stake_navax >= round(self.min_stake_avax(days) * AVAX)

    def curve(self, durations_days: Iterable[float] = DEFAULT_DURATIONS_DAYS) -> pd.DataFrame:
        rows = []
        for days in durations_days:
            stake = self.min_stake_avax(days)
            rows.append({"mechanism": self.label, "duration_days": days, "min_stake_avax": stake, "stake_days": stake * days})
        return pd.DataFrame(rows)

    def admitted(self, stakes: pd.DataFrame) -> pd.DataFrame:
        """``stakes`` with an ``admitted`` column. It needs ``stake_navax``, ``duration_seconds``, and ``start``."""
        out = stakes.copy()
        out["admitted"] = [
            self.admits(int(row.stake_navax), int(row.duration_seconds), row.start) for row in stakes.itertuples(index=False)
        ]
        return out

    def check(self, start: datetime) -> list[str]:
        return []


class ChainAdmission(AdmissionRule):
    """Mainnet: 2,000 AVAX minimum for any duration in the allowed range."""


class BoundedHarmonicFrontier(AdmissionRule):
    """Hash's admission frontier, the bounded harmonic curve of 2026-09-29.

    His memo requires p >= 1 for strict convexity. On the call he used p near 0.71 to put 2,500 to 3,000 AVAX
    at 14 days, so p is allowed below 1 and ``check`` reports which properties then fail.
    """

    label = param.String(default="Admission frontier")
    s_short_avax = param.Number(default=7_000.0, bounds=(1.0, 3_000_000.0), doc="Minimum stake at the shortest duration, AVAX")
    s_floor_avax = param.Number(default=1_000.0, bounds=(1.0, 3_000_000.0), doc="Minimum stake at the longest duration, AVAX")
    p = param.Number(default=1.0, bounds=(0.25, 4.0), step=0.01, doc="Curvature. The memo requires at least 1")
    d_min_days = param.Number(default=2.0, bounds=(1.0 / 24.0, 365.0), doc="Shortest duration, days. ACP-273: 2")
    d_max_days = param.Number(default=365.0, bounds=(1.0, 365.0), doc="Longest duration, days")

    @param.depends("d_min_days", "d_max_days", watch=True, on_init=True)
    def _durations_ordered(self):
        if self.d_min_days >= self.d_max_days:
            raise ValueError("the shortest duration must be below the longest")

    def duration_bounds_days(self, start: datetime) -> tuple[float, float]:
        return self.d_min_days, self.d_max_days

    @classmethod
    def through(cls, stake_avax: float, at_days: float, **params) -> BoundedHarmonicFrontier:
        """The frontier that asks exactly ``stake_avax`` at ``at_days``, with its other settings from ``params``.

        It solves the short-duration stake instead of taking a rounded one, so the seat at ``at_days`` holds exactly
        ``stake_avax`` times ``at_days`` AVAX-days. For example, ``through(2_000, 14, s_floor_avax=500, p=1.282)``.
        """
        shape = cls(**{**params, "s_short_avax": 3_000_000.0})
        eta = shape.eta(at_days)
        if not 0 < eta < 1:
            raise ValueError(f"{at_days} days is not strictly between the shortest and longest durations")
        s_short = shape.s_floor_avax + (stake_avax - shape.s_floor_avax) / eta**shape.p
        return cls(**{**params, "s_short_avax": float(s_short)})

    def eta(self, duration_days: float) -> float:
        inverse = 1 / duration_days
        return (inverse - 1 / self.d_max_days) / (1 / self.d_min_days - 1 / self.d_max_days)

    def min_stake_avax(self, duration_days: float) -> float:
        eta = min(max(self.eta(duration_days), 0.0), 1.0)
        return self.s_floor_avax + (self.s_short_avax - self.s_floor_avax) * eta**self.p

    def curve(self, durations_days: Iterable[float] = DEFAULT_DURATIONS_DAYS) -> pd.DataFrame:
        days = [d for d in durations_days if self.d_min_days <= d <= self.d_max_days]
        return super().curve(days)

    def check(self, start: datetime) -> list[str]:
        """The memo's axioms: monotone decay, strict convexity, and exact interpolation at both ends."""
        failures = []
        grid = [self.d_min_days + (self.d_max_days - self.d_min_days) * i / 400 for i in range(401)]
        stakes = [self.min_stake_avax(d) for d in grid]
        if self.s_short_avax <= self.s_floor_avax:
            failures.append("the short-duration stake is not above the floor")
        if any(later >= earlier for earlier, later in pairwise(stakes)):
            failures.append("minimum stake does not fall with duration")
        second = [a - 2 * b + c for a, b, c in zip(stakes, stakes[1:], stakes[2:])]
        if any(value <= 0 for value in second):
            failures.append("minimum stake is not strictly convex in duration")
        if abs(self.min_stake_avax(self.d_min_days) - self.s_short_avax) > 1e-9:
            failures.append("does not reach the short-duration stake at the shortest duration")
        if abs(self.min_stake_avax(self.d_max_days) - self.s_floor_avax) > 1e-9:
            failures.append("does not reach the floor at the longest duration")
        return failures

    def below_sybil_parity(self, durations_days: Iterable[float] = DEFAULT_DURATIONS_DAYS) -> list[float]:
        """Durations where stake times days falls below 2,000 AVAX for 14 days, Hash's sybil-parity objective."""
        return [d for d in durations_days if self.d_min_days <= d <= self.d_max_days and self.min_stake_avax(d) * d < SYBIL_BASELINE_AVAX_DAYS]
