"""The staking rules in force at an instant (``RT1``) and the dated calendar of rule events (``EV1``).

The calendar keeps two clocks apart: ``event_time``, when the event takes effect, and ``available_at``, when it was
public. ``calendar(as_of=...)`` returns only events public before ``as_of`` and refuses while any row's publication time
is unsourced (``availability == "unsourced"``), unless the caller asks for ``retrospective=True``, a description of the
past that no forecast at ``as_of`` could have read. Upgrade activations are unsourced until each release's publication
time is captured; registered-actor rows are dated by their evidence, public from that date.

Rules as features let a model read what changed at an upgrade, not only which era a decision fell in. Every value is
computed by the protocol module, so a feature and the model's reward kernel cannot disagree. Columns:

| Code | Column | Meaning |
| --- | --- | --- |
| | ``regime`` | The upgrade in force |
| ``RF1`` | ``reward_14d_pct``, ``reward_365d_pct`` | Annualized reward for 2,000 AVAX staked from the instant, at a fixed reference supply |
| ``RF2`` | ``duration_premium_pp`` | ``reward_365d_pct`` minus the rate at the validator minimum duration |
| ``RF3`` | ``min_validator_days``, ``min_delegator_days`` | Minimum stake duration by role |
| ``RF4`` | ``uptime_requirement`` | Uptime a validator starting at the instant must meet |
| ``RF5`` | ``rule_*`` | 1 once a dated rule from ``protocol.MECHANISMS`` is active, else 0 |
| ``RF6`` | ``ramp_position`` | Share of ACP-285's 90-day ramp elapsed: 0 before Helicon, 1 from its end |

The reference supply is fixed so that ``RF1`` and ``RF2`` move only when a rule moves, never with supply.
"""

from __future__ import annotations

from datetime import UTC

import numpy as np
import pandas as pd

from ..model.protocol import (
    ACP285_RAMP_SECONDS,
    MAINNET,
    MAINNET_UPGRADES,
    MECHANISMS,
    annualized_reward_rate,
    min_stake_duration_seconds,
    uptime_requirement,
)
from .inputs import EVIDENCE_DATES, regime_at

REFERENCE_SUPPLY_NAVAX = 450_000_000 * 10**9
QUOTE_STAKE_NAVAX = 2_000 * 10**9
SECONDS_PER_DAY = 86_400
DATED_RULES = {f"rule_{m.acp.lower().replace('-', '')}_{m.upgrade}": m for m in MECHANISMS if m.upgrade}
RULE_COLUMNS = ["regime", "reward_14d_pct", "reward_365d_pct", "duration_premium_pp", "min_validator_days",
                "min_delegator_days", "uptime_requirement", *DATED_RULES, "ramp_position"]
CALENDAR_COLUMNS = ["event_time", "kind", "name", "detail", "source", "available_at", "availability"]


def _utc(time: pd.Timestamp):
    return pd.Timestamp(time).tz_localize(UTC).to_pydatetime() if pd.Timestamp(time).tzinfo is None \
        else pd.Timestamp(time).tz_convert(UTC).to_pydatetime()


def _rate(start, days: float) -> float:
    return annualized_reward_rate(start, int(days * SECONDS_PER_DAY), QUOTE_STAKE_NAVAX, REFERENCE_SUPPLY_NAVAX) * 100


def rules_in_force(times: pd.Series) -> pd.DataFrame:
    """One row per time (naive UTC, as the staking-period log stores it) with the rules a decision then faced."""
    helicon = pd.Timestamp(next(u.activated_at for u in MAINNET_UPGRADES.upgrades if u.name == "helicon")).tz_convert(UTC)
    rows = []
    for time in times:
        at = _utc(time)
        minimum = min_stake_duration_seconds(at, MAINNET, MAINNET_UPGRADES, role="validator") / SECONDS_PER_DAY
        long, short = _rate(at, 365), _rate(at, minimum)
        elapsed = (pd.Timestamp(at) - helicon).total_seconds()
        rows.append({
            "reward_14d_pct": _rate(at, 14),
            "reward_365d_pct": long,
            "duration_premium_pp": long - short,
            "min_validator_days": minimum,
            "min_delegator_days": min_stake_duration_seconds(at, MAINNET, MAINNET_UPGRADES, role="delegator") / SECONDS_PER_DAY,
            "uptime_requirement": uptime_requirement(at, MAINNET, MAINNET_UPGRADES),
            **{column: int(MAINNET_UPGRADES.activated(m.upgrade, at)) for column, m in DATED_RULES.items()},
            "ramp_position": float(np.clip(elapsed / ACP285_RAMP_SECONDS, 0, 1)),
        })
    frame = pd.DataFrame(rows, index=times.index)
    frame.insert(0, "regime", regime_at(times))
    return frame[RULE_COLUMNS]


def calendar(as_of=None, *, retrospective: bool = False) -> pd.DataFrame:
    """``EV1``'s scripted rows: each upgrade's activation, ACP-285's ramp end, and each dated registered-actor rule.

    Releases and ACP stages need their own sources and are not scripted here yet. With ``as_of``, only rows public
    strictly before it; rows with an unsourced publication time are refused unless ``retrospective``."""
    rows = [{"event_time": pd.Timestamp(u.activated_at).tz_convert(UTC).tz_localize(None), "kind": "activation", "name": u.name,
             "detail": "; ".join(f"{m.acp}: {m.name}" for m in MECHANISMS if m.upgrade == u.name),
             "source": "model.protocol.MAINNET_UPGRADES"} for u in MAINNET_UPGRADES.upgrades]
    helicon = next(row for row in rows if row["name"] == "helicon")["event_time"]
    rows.append({"event_time": helicon + pd.Timedelta(seconds=ACP285_RAMP_SECONDS), "kind": "ramp_end", "name": "ACP-285",
                 "detail": "Minimum consumption rate reaches 7.5% for stakes starting from here", "source": "model.protocol"})
    for row in rows:
        row.update(available_at=pd.NaT, availability="unsourced")
    rows += [{"event_time": date, "kind": "registered_actor_evidence", "name": attribution,
              "detail": "Periods on this attribution's reward address are set apart from here", "source": "behaviour.inputs.EVIDENCE_DATES",
              "available_at": date, "availability": "evidence date"}
             for attribution, date in EVIDENCE_DATES.items()]
    table = pd.DataFrame(rows, columns=CALENDAR_COLUMNS).sort_values(["event_time", "kind", "name"]).reset_index(drop=True)
    if as_of is None:
        return table
    cut = pd.Timestamp(as_of)
    unsourced = table.availability.eq("unsourced")
    if unsourced.any() and not retrospective:
        raise ValueError(f"{int(unsourced.sum())} calendar rows have no sourced publication time; pass retrospective=True "
                         "only for a description of the past, never for a forecast at as_of")
    known = table.available_at.lt(cut) | (unsourced & table.event_time.lt(cut))
    return table.loc[known].reset_index(drop=True)
