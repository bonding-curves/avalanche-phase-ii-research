"""The rate gap a behaviour response acts on: a design's change from the reward menu the blocks were fitted under.

``renewal_response`` and ``entry_response`` are per percentage point of the annual rate on a 30-day stake. The point
they count from is the menu the renewal and arrival blocks were fitted under, the rule in force over the fitting
window, not the chain's rule on the forecast day. A response of 0 therefore reproduces the fitted model for every
design, and a design is priced against what operators were seen to respond to.

Before Helicon the two references are the same rule, so the gap equals the one the lifecycle models have always
computed, to the bit. From Helicon, ACP-285 lowers the chain's minimum consumption rate from 10% to 7.5% over 90
days for stakes starting after activation. The fitted menu keeps the rule of its window, so a forecast from a
post-Helicon origin applies the response to ACP-285's change even under the chain's own rule.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, time

import param

from avalanche_research.core.clock import LOCKBOX_START, as_utc
from avalanche_research.domain.protocol import reward_config_for_stake_start
from avalanche_research.domain.protocol.types import RewardConfig
from avalanche_research.mechanisms import RewardMechanism

RESPONSE_DURATION_DAYS = 30


class FittedMenu(RewardMechanism):
    """The chain's rule as it stood at the end of a fitting window, held there whatever the stake's start."""

    label = param.String(default="Fitted menu")
    fitted_at = param.Date(
        default=LOCKBOX_START,
        doc="The last instant of the fitting window. Every stake is priced with the rule in force then",
    )

    @classmethod
    def for_window(cls, start: datetime, end: datetime) -> FittedMenu:
        """The menu of the fitting window ``[start, end)``, read in UTC.

        A window may not reach past the lockbox start, 2025-11-19 16:00 UTC. Every window that stops there ends
        before Helicon, so the chain's rule did not change inside it and its last instant stands for all of it.
        """
        start, end = as_utc(start), as_utc(end)
        if start >= end:
            raise ValueError(f"the fitting window must start before its end, not {start} to {end}")
        if end > LOCKBOX_START:
            raise ValueError(f"the fitting window ends {end}, inside the validation lockbox, which starts 2025-11-19 16:00 UTC")
        return cls(fitted_at=end)

    def config(self, start: datetime) -> RewardConfig:
        return reward_config_for_stake_start(self.fitted_at)


def response_gap_pp(design: RewardMechanism, menu: RewardMechanism, day: date, supply_navax: int, completed_periods: int,
                    outside_yield_pp: float | None = None, fitted_outside_yield_pp: float | None = None,
                    staked_share: float | None = None) -> float:
    """The design's annual rate minus the fitted menu's, in percentage points, for a 30-day stake started at noon UTC
    on ``day`` at ``supply_navax`` and ``completed_periods`` of tenure.

    The renewal response reads it at the typical tenure of a renewing validator and the entry response at no tenure.

    An outside yield, such as a Treasury bill rate, enters the same way as the menu: as its change from its level over
    the fitting window, since the fitted blocks already carry that level. A rise in the outside yield narrows the gap
    point for point. Give both ``outside_yield_pp`` and ``fitted_outside_yield_pp``, or neither.

    ``staked_share`` is the share of supply staked on ``day``, which a design whose rate reads participation prices
    at. The fitted menu never reads it.
    """
    if (outside_yield_pp is None) != (fitted_outside_yield_pp is None):
        raise ValueError("give the outside yield and its level over the fitting window together, or neither")
    start = datetime.combine(day, time(12), tzinfo=UTC)
    ours = design.annual_rate(RESPONSE_DURATION_DAYS, supply_navax, start, completed_periods=completed_periods, staked_share=staked_share)
    fitted = menu.annual_rate(RESPONSE_DURATION_DAYS, supply_navax, start, completed_periods=completed_periods)
    gap = (ours - fitted) * 100
    if outside_yield_pp is None:
        return gap
    if not (math.isfinite(outside_yield_pp) and math.isfinite(fitted_outside_yield_pp)):
        raise ValueError("outside yields must be finite numbers of percentage points")
    return gap - (outside_yield_pp - fitted_outside_yield_pp)
