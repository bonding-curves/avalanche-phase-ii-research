"""Holder types: who holds the AVAX that gets staked, each with its own rule, on top of the delegated lifecycle.

Five kinds of holder appear in the record, and the v0.8.1 model treats them as one population of validators and one
Poisson flow of delegations with BENQI's share. This part gives each kind its own rule, every rule off by default so the
model with ``holders=None`` is v0.8.1 exactly.

* Liquid staking providers, with BENQI's sAVAX as the one in the record. BENQI's delegated stock is a programme, not a
  crowd: every expiring delegation is re-delegated within minutes on a 14-to-17-day ladder, so the stock moves only with
  deposits. The rule carries a target stock that grows each day by ``drift_per_day`` plus ``gap_elasticity_per_day``
  times the change in the yield gap from its level at the origin, where the gap is the annual rate of a 14-day delegation
  under the run's reward rule less BENQI's fee share and less ``defi_yield_pp``, the lending rate the same AVAX could
  earn. BENQI starts as many delegations as bring its aged stock up to the target, each at the mean stake of its starts
  over the 28 days before the origin, and withdraws only by letting delegations expire, so no day's outflow can pass the
  stake that ends that day. Record: BENQI's chain-side delegated stock, 6.7 million AVAX on 6 March 2024 to 22.6 million
  on 18 November 2025, grew 2.4% a week over 2025 and 0% over 2024. Its weekly growth on the lagged gap to the Aave WAVAX
  supply rate has a slope of 3.7 (standard error 1.7, 50 weeks), on a gap whose standard deviation is 0.45 points, so the
  elasticity is bounded, not estimated. The stake per start over the 28 days before an origin differs from the year's by
  up to 3.7 times (243 against 65 AVAX at 8 April 2025), which is why v0.8.1 minted BENQI's stock several times too
  large at Banff: it drew the year's stakes at the month's count.
* Exchange-traded funds: Bitwise BAVA, VanEck VAVX and 21Shares' Avalanche ETP. Holdings move with fund flows, which the
  record links only weakly to price: 21Shares' weekly change in shares outstanding on the week's log price return has a
  slope of 0.07 (standard error 0.04) over 207 weeks to 18 November 2025 and 0.01 (0.02) from 2024 on, so
  ``price_elasticity`` is bounded and the growth is a scenario, ``drift_per_day``. A fund stakes ``staked_share`` of its
  holdings (Bitwise 0.67 and VanEck 0.80 by their own figures of 26 October 2026) as validators of
  ``validator_stake_navax`` each (BAVA's 11 validators held 1,786,084 AVAX on 27 October 2026, 162,371 each) for
  ``min_days`` to ``max_days`` (BAVA's 25 commitments since Helicon ran 15.1 to 19.1 days). The share a fund staked at
  the origin is taken to be inside the record's validator set already, since the record cannot tell which commitments
  are a fund's before Helicon, so the rule adds validators as holdings grow past the origin's level and drops them as
  holdings fall, and the model-made ones are the fund's for the concentration measures.
* Institutional validators and small independent operators: the record names no institution, so the line between them is
  the large-holder line of 1,000,000 AVAX the v0.8 development scores used, with its own renewal logit fitted on the
  endings above it (``v0.8 separate``), and ``response_scale``, the institutional response to the yield gap as a multiple
  of the small operators', which nothing in the record pins and which is swept.
* Plain delegators: the Poisson flow of v0.8.1 less BENQI's share, with ``response``, the change in its log per
  percentage point of yield gap, swept over the entry response's bounds because the record has not measured it.

The settings come as one ``holders`` dictionary, ``HolderSettings`` once checked, so a sweep row can carry them as JSON.
The concentration measures the part writes each day are the liquid-staking share of all stake, the Nakamoto coefficient
by operator, the fewest operators whose weight passes one third, and the effective number of operators, one over the
Herfindahl index of weights, where an operator's weight is its validators' own stake plus the delegations on them, every
fund's model-made validators count as one operator, and every other node is its own.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from avalanche_research.model.parts.base import AVAX
from avalanche_research.model.parts.participation import (
    MIN_STAKE_NAVAX,
    funded,
    validator_pool,
)
from avalanche_research.model.streams import node_keys

FUND_KIND_BASE = 8
"""Node keys of a fund's model-made validators carry kind ``FUND_KIND_BASE + fund row``, so a key names its fund."""
MAX_FUNDS = 16
LST_DELEGATION_DAYS = 14
"""The delegation whose annual rate the liquid staking rule prices: BENQI's ladder is 14 to 17 days."""
MAX_VALIDATOR_STAKE_NAVAX = 3_000_000 * AVAX

LIQUID_STAKING_KEYS = {"drift_per_day": (-0.05, 0.05), "gap_elasticity_per_day": (0.0, 2.0), "defi_yield_pp": (0.0, 50.0),
                       "fee_share": (0.0, 1.0)}
FUND_KEYS = {"drift_per_day": (-0.05, 0.05), "price_elasticity": (0.0, 1.0), "staked_share": (0.0, 1.0)}
OPERATOR_KEYS = {"line_avax": (2_000.0, 3_000_000.0), "response_scale": (0.0, 5.0)}
DELEGATOR_KEYS = {"response": (-2.0, 2.0)}
SECTIONS = {"liquid_staking": LIQUID_STAKING_KEYS, "funds": FUND_KEYS, "operators": OPERATOR_KEYS, "delegators": DELEGATOR_KEYS}
DEFAULTS = {
    "liquid_staking": {"drift_per_day": 0.0, "gap_elasticity_per_day": 0.0, "defi_yield_pp": 1.5, "fee_share": 0.1},
    "funds": {"drift_per_day": 0.0, "price_elasticity": 0.0, "staked_share": None},
    "operators": {"line_avax": None, "response_scale": 1.0},
    "delegators": {"response": 0.0},
}
PRICE_RETURN_STATE = "avax_log_return"
"""The state variable a price module writes with the day's log return of the AVAX price. Absent, funds see no price move."""


@dataclass(frozen=True, eq=False)
class HolderSettings:
    """The ``holders`` dictionary checked: each section's values within their bounds, unknown keys refused."""

    liquid_staking: dict[str, float]
    funds: dict[str, float | None]
    operators: dict[str, float | None]
    delegators: dict[str, float]

    @classmethod
    def check(cls, raw: Mapping[str, Any] | None) -> HolderSettings | None:
        if raw is None:
            return None
        if not isinstance(raw, Mapping):
            raise ValueError("holders must be a mapping of sections: liquid_staking, funds, operators, delegators")
        unknown = sorted(set(raw) - set(SECTIONS))
        if unknown:
            raise ValueError(f"holders has sections the model does not read: {', '.join(unknown)}")
        sections = {}
        for name, bounds in SECTIONS.items():
            given = raw.get(name) or {}
            if not isinstance(given, Mapping):
                raise ValueError(f"holders.{name} must be a mapping")
            stray = sorted(set(given) - set(bounds))
            if stray:
                raise ValueError(f"holders.{name} has settings the model does not read: {', '.join(stray)}")
            values = dict(DEFAULTS[name])
            for key, value in given.items():
                if value is None and DEFAULTS[name][key] is None:
                    continue
                low, high = bounds[key]
                number = float(value)
                if not np.isfinite(number) or not low <= number <= high:
                    raise ValueError(f"holders.{name}.{key} must be a finite number in [{low}, {high}], not {value!r}")
                values[key] = number
            sections[name] = values
        return cls(**sections)

    @property
    def large_navax(self) -> int | None:
        line = self.operators["line_avax"]
        return None if line is None else round(line * AVAX)


@dataclass(frozen=True, eq=False)
class FundTable:
    """The funds at the origin, one row each: name, holdings, staked share, stake per validator and the duration band.
    ``staked0_navax`` is the stake each fund is taken to hold inside the record's validator set at the origin."""

    names: tuple[str, ...]
    holdings0_navax: np.ndarray
    staked_share: np.ndarray
    validator_stake_navax: np.ndarray
    min_days: np.ndarray
    max_days: np.ndarray
    staked0_navax: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))

    @classmethod
    def from_frame(cls, frame, settings: HolderSettings | None) -> FundTable:
        """The table from a ``fund_holdings`` DataFrame with the columns fund, holdings_navax, staked_share,
        validator_stake_navax, min_days and max_days. The settings' ``staked_share``, when given, replaces every fund's."""
        if frame is None or not len(frame):
            empty = np.zeros(0, dtype=np.int64)
            return cls((), empty, np.zeros(0), empty, empty, empty, empty)
        if len(frame) > MAX_FUNDS:
            raise ValueError(f"at most {MAX_FUNDS} funds")
        names = tuple(str(name) for name in frame["fund"])
        if len(set(names)) != len(names):
            raise ValueError("each fund is listed once")
        holdings = np.asarray(frame["holdings_navax"], dtype=np.int64)
        share = np.asarray(frame["staked_share"], dtype=float)
        if settings is not None and settings.funds["staked_share"] is not None:
            share = np.full(len(names), float(settings.funds["staked_share"]))
        stake = np.asarray(frame["validator_stake_navax"], dtype=np.int64)
        low, high = np.asarray(frame["min_days"], dtype=np.int64), np.asarray(frame["max_days"], dtype=np.int64)
        if (holdings < 0).any() or (share < 0).any() or (share > 1).any():
            raise ValueError("a fund needs non-negative holdings and a staked share within [0, 1]")
        if (stake < MIN_STAKE_NAVAX).any() or (stake > MAX_VALIDATOR_STAKE_NAVAX).any():
            raise ValueError("a fund's stake per validator must be within the validator bounds")
        if (low < 1).any() or (high < low).any():
            raise ValueError("a fund's duration band needs 1 <= min_days <= max_days")
        # The stake the fund already holds inside the record's validator set: its staked share of holdings unless the
        # table says otherwise, as it does for a fund whose validators the record does not carry.
        staked0 = (np.asarray(frame["staked0_navax"], dtype=np.int64) if "staked0_navax" in frame.columns
                   else (holdings * share).astype(np.int64))
        if (staked0 < 0).any():
            raise ValueError("a fund's stake at the origin cannot be negative")
        return cls(names, holdings, share, stake, low, high, staked0)

    def __len__(self) -> int:
        return len(self.names)


def fund_of(keys: np.ndarray) -> np.ndarray:
    """Each node key's fund row, or -1 for a node that is not a fund's model-made validator."""
    kind = (np.asarray(keys, dtype=np.int64) >> np.int64(48)) - FUND_KIND_BASE
    return np.where((kind >= 0) & (kind < MAX_FUNDS), kind, -1).astype(np.int64)


def fund_node_keys(fund: int, t: int, count: int) -> np.ndarray:
    """Keys for ``count`` validators the fund ``fund`` starts on day ``t``."""
    if not 0 <= fund < MAX_FUNDS:
        raise ValueError(f"fund row {fund} is out of range")
    return node_keys(FUND_KIND_BASE + fund, t, np.arange(count))


@dataclass(frozen=True, eq=False)
class HolderSetup:
    """What the holder stages read besides the state: the checked settings, the funds, BENQI's stake per start, the
    yield gap the liquid staking rule saw at the origin, and the base renewal blocks' large line."""

    settings: HolderSettings
    funds: FundTable
    benqi_stake_per_start_navax: int
    lst_gap0: float
    renewal_large: Any = None


# Liquid staking.

def lst_gap(mechanism, supply_navax: int, start, settings: HolderSettings) -> float:
    """The yield gap a liquid staker sees: the annual rate of a 14-day delegation under the reward rule at the supply,
    net of the provider's fee share, less the lending yield, as a fraction a year."""
    rate = mechanism.annual_rate(LST_DELEGATION_DAYS, int(supply_navax), start, completed_periods=0)
    return rate * (1.0 - settings.liquid_staking["fee_share"]) - settings.liquid_staking["defi_yield_pp"] / 100.0


def lst_target_next(target: float, gap: float, setup: HolderSetup) -> float:
    """The target stock for the next day: today's grown by the drift plus the elasticity times the gap's change from
    its level at the origin, never below zero."""
    rule = setup.settings.liquid_staking
    growth = rule["drift_per_day"] + rule["gap_elasticity_per_day"] * (gap - setup.lst_gap0)
    return float(max(0.0, target * np.exp(growth)))


def lst_starts(target_next: float, aged_navax: int, stake_per_start: int) -> int:
    """How many delegations BENQI starts today to bring its aged stock up to the target, none when the target is below
    the stock, since withdrawals happen only by expiry."""
    if stake_per_start <= 0:
        return 0
    return max(0, int((target_next - float(aged_navax)) // stake_per_start))


# Funds.

def fund_holdings_next(holdings: np.ndarray, log_return: float, settings: HolderSettings) -> np.ndarray:
    """Each fund's holdings tomorrow: today's grown by the drift and the price elasticity times the day's log return."""
    rule = settings.funds
    growth = rule["drift_per_day"] + rule["price_elasticity"] * float(log_return)
    return np.maximum(0, np.round(holdings.astype(float) * np.exp(growth))).astype(np.int64)


def fund_wanted(holdings: np.ndarray, funds: FundTable) -> np.ndarray:
    """How many model-made validators each fund wants: its staked share of holdings beyond what it staked at the origin,
    in whole validators of its stake, never negative."""
    beyond = holdings.astype(float) * funds.staked_share - funds.staked0_navax
    return np.maximum(0, np.floor(beyond / funds.validator_stake_navax)).astype(np.int64)


def fund_counts(keys: np.ndarray, n_funds: int) -> np.ndarray:
    """How many of ``keys`` belong to each fund."""
    rows = fund_of(keys)
    return np.bincount(rows[rows >= 0], minlength=n_funds).astype(np.int64)


def fund_days(low: np.ndarray, high: np.ndarray, u: np.ndarray) -> np.ndarray:
    """A whole number of days in each row's band from one uniform each."""
    span = (high - low + 1).astype(np.int64)
    return (low + np.minimum((u * span).astype(np.int64), span - 1)).astype(np.int64)


# Concentration.

def operator_weights(keys: np.ndarray, own: np.ndarray, delegated_on: np.ndarray) -> np.ndarray:
    """Each operator's weight: own stake plus the delegations on its validators, with a fund's model-made validators
    summed as one operator and every other node its own."""
    rows = fund_of(keys)
    operator = np.where(rows >= 0, -(rows.astype(np.int64) + 1), np.asarray(keys, dtype=np.int64))
    _, inverse = np.unique(operator, return_inverse=True)
    total = np.zeros(inverse.max() + 1 if len(inverse) else 0, dtype=np.int64)
    np.add.at(total, inverse, np.asarray(own, dtype=np.int64) + np.asarray(delegated_on, dtype=np.int64))
    return total


def nakamoto_operators(weights: np.ndarray) -> int:
    """The fewest operators whose weight together passes one third of the total. Zero when nothing is staked."""
    if not len(weights) or weights.sum() <= 0:
        return 0
    running = np.cumsum(np.sort(weights)[::-1])
    return int(np.argmax(3 * running > running[-1])) + 1


def effective_operators(weights: np.ndarray) -> float:
    """One over the Herfindahl index of weight shares. Zero when nothing is staked."""
    total = float(np.asarray(weights, dtype=float).sum())
    if total <= 0:
        return 0.0
    shares = np.asarray(weights, dtype=float) / total
    return float(1.0 / (shares ** 2).sum())


# The stages the mixin wraps around the lifecycle's.

def _large_renewals(renews: np.ndarray, ended: Mapping[str, np.ndarray], day, setup: HolderSetup) -> np.ndarray:
    """Redecide the ending commitments above the institutional line with their own renewal block and the institutional
    response, on the keyed uniforms the base stage would use for the large block."""
    large_navax = setup.settings.large_navax
    if large_navax is None or setup.renewal_large is None:
        return renews
    large = ended["stakes"] > large_navax
    if not large.any():
        return renews
    blocks, settings = day.blocks, day.settings
    shift = settings.renewal_response * setup.settings.operators["response_scale"] * day.renewal_gap + blocks.renewal_shift
    shift += float(getattr(settings, "market_renewal_shift", 0.0))
    inputs = {"done": ended["done"][large], "after_return": ended["after_return"][large], "days": ended["days"][large],
              "stake_navax": ended["stakes"][large], "returns": ended["returns"][large], "shift": shift}
    out = renews.copy()
    out[large] = day.draw.uniforms("renewal_large", ended["node_key"][large], ended["done"][large]) < setup.renewal_large.probability(inputs)
    return out


def holder_renewal_stage(state, day, earlier, *, base, setup: HolderSetup) -> dict:
    """The base renewal stage, then the institutional redecision, then each fund's mandate: its ending validators renew
    while it wants at least as many as it runs, and the ones past its want leave."""
    out = base(state, day, earlier)
    ended = out["ended"]
    renews = _large_renewals(out["renews"], ended, day, setup)
    funds = setup.funds
    if len(funds):
        rows = fund_of(ended["node_key"])
        if (rows >= 0).any():
            renews = renews.copy()
            running = fund_counts(state["node_key"], len(funds))
            wanted = fund_wanted(state["fund_holdings_navax"], funds)
            drop = np.maximum(0, running - wanted)
            for fund in np.unique(rows[rows >= 0]):
                mine = np.flatnonzero(rows == fund)
                renews[mine] = True
                renews[mine[: int(drop[fund])]] = False
    return {**out, "renews": renews}


def holder_continuation_stage(state, day, earlier, *, base, setup: HolderSetup) -> dict:
    """The base continuation, then each fund's own terms on its renewed validators, then the validators funds add today,
    funded from the unstaked pool after the base's starts."""
    out = base(state, day, earlier)
    funds = setup.funds
    if not len(funds):
        return out
    started = {name: np.asarray(value) for name, value in out["started"].items()}
    rows = fund_of(started["node_key"])
    mine = rows >= 0
    if mine.any():
        started["stakes"] = started["stakes"].copy()
        started["days"] = started["days"].copy()
        started["stakes"][mine] = funds.validator_stake_navax[rows[mine]]
        started["days"][mine] = fund_days(funds.min_days[rows[mine]], funds.max_days[rows[mine]],
                                          day.draw.uniforms("holder_days", started["node_key"][mine], started["done"][mine]))
    # Validators each fund adds today: its want beyond those it runs after today's renewals.
    running = fund_counts(np.concatenate([state["node_key"][~earlier["renewal"]["ending"]], started["node_key"]]), len(funds))
    wanted = fund_wanted(state["fund_holdings_navax"], funds)
    add = np.maximum(0, wanted - running)
    if add.sum() == 0:
        return {**out, "started": started}
    keys = np.concatenate([fund_node_keys(fund, day.t, int(count)) for fund, count in enumerate(add)])
    fund_rows = np.repeat(np.arange(len(funds)), add)
    stakes = funds.validator_stake_navax[fund_rows]
    days = fund_days(funds.min_days[fund_rows], funds.max_days[fund_rows], day.draw.uniforms("holder_days", keys, 0))
    pool = validator_pool(state, day, earlier) - int(started["stakes"].sum())
    stakes, made = funded(stakes, pool)
    keys, stakes, days = keys[made], stakes[made], days[made]
    n = len(keys)
    added = {
        "stakes": stakes, "days": days, "node_key": keys, "done": np.zeros(n, dtype=np.int64),
        "after_return": np.zeros(n, dtype=bool), "returns": np.zeros(n, dtype=np.int64),
    }
    joined = {name: np.concatenate([started[name], added[name]]) for name in started}
    return {**out, "started": joined}


def holder_assembly_stage(state, day, earlier, *, base, funds: FundTable) -> dict:
    """The base assembly, with a fund's validators that leave the set dropped rather than kept as nodes that may return."""
    out = base(state, day, earlier)
    if not len(funds) or not len(out["out_node_key"]):
        return out
    keep = fund_of(out["out_node_key"]) < 0
    if keep.all():
        return out
    names = ("out_stakes", "out_days", "out_done", "out_last_days", "out_returns", "out_node_key")
    return {**out, **{name: out[name][keep] for name in names}}


def holders_stage(state, day, earlier, *, setup: HolderSetup) -> dict:
    """The last stage: the funds' holdings for tomorrow and the day's concentration measures, on the delegations stage's
    next state."""
    out = earlier["delegations"]
    keys, own = out["node_key"], out["stakes"]
    from avalanche_research.model.parts.delegations import on_validators, stake_on

    on = stake_on(len(keys), on_validators(keys, out["delegation_validator"]), out["delegation_stakes"])
    weights = operator_weights(keys, own, on)
    funds = setup.funds
    holdings = fund_holdings_next(state["fund_holdings_navax"], float(state.get(PRICE_RETURN_STATE, 0.0)), setup.settings) \
        if len(funds) else np.zeros(0, dtype=np.int64)
    rows = fund_of(keys)
    staked = int(own[rows >= 0].sum())
    total = int(own.sum()) + int(out["delegation_stakes"].sum())
    return {
        **out,
        "fund_holdings_navax": holdings,
        "etf_holdings_navax": int(holdings.sum()),
        "etf_validators": int((rows >= 0).sum()),
        "etf_validator_stake_navax": staked,
        "liquid_staking_stake_navax": int(out["benqi_delegated_stake_navax"]) if "benqi_delegated_stake_navax" in out
        else int(out["delegation_stakes"][out["delegation_benqi"]].sum()),
        "liquid_staking_share": (int(out["delegation_stakes"][out["delegation_benqi"]].sum()) / total) if total else 0.0,
        "nakamoto_third_operators": nakamoto_operators(weights),
        "effective_operators": effective_operators(weights),
    }


__all__ = [
    "DEFAULTS", "FUND_KIND_BASE", "LST_DELEGATION_DAYS", "MAX_FUNDS", "PRICE_RETURN_STATE", "SECTIONS",
    "FundTable", "HolderSettings", "HolderSetup", "effective_operators", "fund_counts", "fund_days", "fund_holdings_next",
    "fund_node_keys", "fund_of", "fund_wanted", "holder_assembly_stage", "holder_continuation_stage",
    "holder_renewal_stage", "holders_stage", "lst_gap", "lst_starts", "lst_target_next", "nakamoto_operators",
    "operator_weights",
]
