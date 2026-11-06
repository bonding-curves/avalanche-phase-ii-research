"""Helicon's rules as swept scenarios: automatic renewal, reward restaking, the 48-hour minimum and the 90% uptime rule.

Helicon activated on 2026-09-22 15:00 UTC (``MAINNET_UPGRADES``). It changed three rules that decide when a
commitment ends, whether it continues and whether its reward is paid. None is fitted: every fit stays on data before
Granite. Each is a share or a probability that sweeps from 0, and at 0 the stage is not wrapped, so the run is v0.9.0's.

* Automatic renewal (ACP-236, ``AddAutoRenewedValidatorTx``). A share of the commitments started from Helicon on are
  auto-renewed validators. At each cycle end such a validator does not face the renewal logit. It leaves with a
  per-cycle hazard, or when the cycle missed the uptime requirement, which removes an auto-renewed validator on the
  chain. Otherwise it starts its next cycle at once on the same node, for the same period, as a new commitment whose
  reward is recomputed at the day's supply.
* Reward restaking (``AutoCompoundRewardShares``). An auto-renewed validator restakes a share of the cycle's reward
  into its own stake at the cycle end, up to the protocol's maximum validator stake, by the chain's own split
  (``auto_renew_restake``). The rest is paid out. The restaked reward was minted at the cycle's start, so the supply
  counter does not move.
* The 48-hour minimum (ACP-273). A share of the commitments started from Helicon on take a period of 2 to 13 whole
  days, uniform, in place of the duration the model draws, within any bounds the reward rule sets.
* The 90% uptime rule (ACP-267). A period ending from Helicon on misses the requirement with an added probability. A
  missed period earns nothing: the reward the run minted for it at its start leaves the supply counter at its end,
  as on the chain, and is recorded as ``uptime_forfeit_navax``.

"From Helicon on" is read at the instant each stage prices a day, noon UTC, so 2026-09-23 is the first such day. Every
draw uses its own keyed stream (model.streams), so no existing draw moves.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from avalanche_research.domain.protocol import MAINNET, MAINNET_UPGRADES, PERCENT_DENOMINATOR, auto_renew_restake
from avalanche_research.model.parts.stages import Day, bounded_days, priced_rewards

HELICON = MAINNET_UPGRADES.time("helicon")
"""Helicon's activation, 2026-09-22 15:00 UTC."""
SHORT_PERIOD_DAYS = (2, 13)
"""The whole days a period below 14 days draws from: 48 hours, ACP-273's minimum, to one day short of the old one."""
MAX_STAKE_NAVAX = MAINNET.max_validator_stake_navax
STATE_ARRAYS = ("auto_renew", "cycle_reward_navax")
"""Per commitment: whether it is an auto-renewed validator, and the reward the run paid for its current cycle."""
FORFEIT = "uptime_forfeit_navax"
_PRIVATE = ("cycle_rewards", "restaked")


def from_helicon(at: datetime) -> bool:
    return MAINNET_UPGRADES.activated("helicon", at)


@dataclass(frozen=True)
class HeliconRules:
    """The four settings one run reads. All zero is a run without them."""

    auto_renew_share: float = 0.0
    auto_renew_exit_hazard: float = 0.0
    auto_compound_share: float = 0.0
    short_period_share: float = 0.0
    uptime_miss_increase: float = 0.0

    @property
    def active(self) -> bool:
        return any((self.auto_renew_share, self.auto_renew_exit_hazard, self.auto_compound_share,
                    self.short_period_share, self.uptime_miss_increase))

    def stages(self, stages: tuple) -> tuple:
        """``stages`` with the renewal, continuation, rewards and assembly stages wrapped, or unchanged when no rule is
        set. A model with delegations or holders is refused: their stages read validator end dates these rules move."""
        if not self.active:
            return stages
        names = [name for name, _ in stages]
        if set(names) - {"renewal", "returns", "arrivals", "continuation", "rewards", "assembly"}:
            raise ValueError(f"the Helicon rules are built for the validator lifecycle, not one with stages {names}")
        wrap = {"renewal": _Renewal, "continuation": _Continuation, "rewards": _Rewards, "assembly": _Assembly}
        return tuple((name, wrap[name](stage, self) if name in wrap else stage) for name, stage in stages)


def restaked_navax(rewards: np.ndarray, stakes: np.ndarray, share: float) -> np.ndarray:
    """Each auto-renewed validator's restaked reward: ``share`` of its cycle reward, at most the room left below the
    maximum validator stake, by the chain's split (``auto_renew_restake``, no delegatee reward)."""
    if not share or not len(rewards):
        return np.zeros(len(rewards), dtype=np.int64)
    shares = round(share * PERCENT_DENOMINATOR)
    return np.array([auto_renew_restake(int(r), 0, shares, int(s))[0] for r, s in zip(rewards, stakes)], dtype=np.int64)


@dataclass(frozen=True)
class _Wrapped:
    stage: Any
    rules: HeliconRules


class _Renewal(_Wrapped):
    """The commitments ending today, with each auto-renewed validator that continues moved to its next cycle before
    the renewal stage sees it, and each one that leaves made to leave whatever the logit draws."""

    def __call__(self, state: Mapping[str, Any], day: Day, earlier: Mapping[str, dict]) -> dict:
        rules = self.rules
        ends = state["days_left"] - 1 <= 0
        key, done = state["node_key"], state["done"]
        missed = np.zeros(len(ends), dtype=bool)
        if rules.uptime_miss_increase and from_helicon(day.start):
            at = np.flatnonzero(ends)
            missed[at] = day.draw.uniforms("uptime_miss", key[at], done[at]) < rules.uptime_miss_increase
        continued = ends & state["auto_renew"] & ~missed
        if rules.auto_renew_exit_hazard:
            at = np.flatnonzero(continued)
            continued[at] = day.draw.uniforms("auto_renew_exit", key[at], done[at]) >= rules.auto_renew_exit_hazard
        moved = {**state, "days_left": np.where(continued, state["days"] + 1, state["days_left"])}
        out = self.stage(moved, day, earlier)
        decided = out["ending"] & ~state["handed_on"]
        renews = out["renews"].copy()
        renews[state["auto_renew"][decided]] = False
        return {**out, "renews": renews, "continued": continued, "missed": missed}


class _Continuation(_Wrapped):
    """The day's starts, with a share of those from Helicon on given a period of 2 to 13 whole days."""

    def __call__(self, state: Mapping[str, Any], day: Day, earlier: Mapping[str, dict]) -> dict:
        out = self.stage(state, day, earlier)
        share = self.rules.short_period_share
        started = out["started"]
        if not share or not from_helicon(day.start) or not len(started["stakes"]):
            return out
        key, done = np.asarray(started["node_key"]), np.asarray(started["done"])
        short = day.draw.uniforms("short_period", key, done) < share
        if not short.any():
            return out
        low, high = SHORT_PERIOD_DAYS
        u = day.draw.uniforms("short_period_days", key[short], done[short])
        days = np.asarray(started["days"], dtype=np.int64).copy()
        days[short] = low + np.minimum((u * (high - low + 1)).astype(np.int64), high - low)
        return {**out, "started": {**started, "days": bounded_days(days, day.settings.mechanism)}}


class _Rewards(_Wrapped):
    """The rewards of the day's starts and of the auto-renewed validators' next cycles, priced together, the cycles
    at their stake after restaking."""

    def __call__(self, state: Mapping[str, Any], day: Day, earlier: Mapping[str, dict]) -> dict:
        continued = earlier["renewal"]["continued"]
        started = earlier["continuation"]["started"]
        stakes = state["stakes"][continued]
        restaked = restaked_navax(state["cycle_reward_navax"][continued], stakes, self.rules.auto_compound_share)
        cycles = {"stakes": stakes + restaked, "days": state["days"][continued], "done": state["done"][continued] + 1}
        priced = {name: np.concatenate([np.asarray(started[name], dtype=np.int64), cycles[name]]) for name in cycles}
        totals, each = priced_rewards(state, day, priced)
        return {**totals, "cycle_rewards": each, "restaked": restaked}


class _Assembly(_Wrapped):
    """The next state, with the auto-renewed validators' next cycles kept in place at their restaked stake, each
    new start's choice of automatic renewal, each commitment's cycle reward, and the reward forfeited today."""

    def __call__(self, state: Mapping[str, Any], day: Day, earlier: Mapping[str, dict]) -> dict:
        rewards, renewal = earlier["rewards"], earlier["renewal"]
        out = self.stage(state, day, {**earlier, "rewards": {k: v for k, v in rewards.items() if k not in _PRIVATE}})
        keep, continued = ~renewal["ending"], renewal["continued"]
        started = earlier["continuation"]["started"]
        n_keep, n_started = int(keep.sum()), len(started["stakes"])
        n_due = len(out["stakes"]) - n_keep - n_started
        cycled = continued[keep]
        stakes, done = out["stakes"].copy(), out["done"].copy()
        stakes[:n_keep][cycled] += rewards["restaked"]
        done[:n_keep][cycled] += 1
        choose = np.zeros(n_started, dtype=bool)
        if self.rules.auto_renew_share and from_helicon(day.start) and n_started:
            choose = day.draw.uniforms("auto_renew", np.asarray(started["node_key"]), np.asarray(started["done"])) < self.rules.auto_renew_share
        each = rewards["cycle_rewards"]
        kept_rewards = state["cycle_reward_navax"][keep].copy()
        kept_rewards[cycled] = each[n_started:]
        n_cycled = int(continued.sum())
        return {
            **out, "stakes": stakes, "done": done,
            "auto_renew": np.concatenate([state["auto_renew"][keep], choose, np.zeros(n_due, dtype=bool)]),
            "cycle_reward_navax": np.concatenate([kept_rewards, each[:n_started], np.zeros(n_due, dtype=np.int64)]),
            FORFEIT: int(state["cycle_reward_navax"][renewal["missed"]].sum()),
            # A cycle end that continues is an ending renewed at once, as the record counts one.
            "ended_validators": out["ended_validators"] + n_cycled,
            "renewed_validators": out["renewed_validators"] + n_cycled,
        }
