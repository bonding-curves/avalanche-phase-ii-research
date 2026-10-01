"""Decision events: one row per validator staking period that ended, and what its node did next.

A node's next period is the one with the next start time on the same node. The gap is that start minus this end, in
days. The outcome is:

* ``renew``: the next period starts within ``renew_days`` of the end (7 by default, the registered measure's window).
* ``return``: it starts later, but within ``horizon_days`` (365).
* ``leave``: no next period starts within ``horizon_days``.
* ``overlap``: the next period started before this one ended. These are kept and labelled, not dropped.
* ``censored``: no next period yet, and the horizon has not passed by ``observed_through``.

A binary ``renewed`` label needs only ``renew_days`` of follow-up, so it is known for more rows than the outcome.
When the node stakes again, the choice it made is recorded: the next duration, stake and fee, and their change.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .inputs import LOCKBOX_START, check_cutoff

OUTCOMES = ("renew", "return", "leave")
DAY = pd.Timedelta(days=1)
# Duration classes of the next period, on the boundaries the protocol's menu and the observed modes suggest.
DURATION_CLASSES = ((0, 21, "up to 3 weeks"), (21, 45, "3 to 6 weeks"), (45, 100, "6 weeks to 3 months"),
                    (100, 200, "3 to 6 months"), (200, 400, "over 6 months"))


def duration_class(days: pd.Series) -> pd.Series:
    bins = [low for low, _, _ in DURATION_CLASSES] + [DURATION_CLASSES[-1][1]]
    return pd.cut(days, bins=bins, labels=[label for _, _, label in DURATION_CLASSES], right=False)


def decision_events(periods: pd.DataFrame, observed_through=LOCKBOX_START, renew_days: int = 7,
                    horizon_days: int = 365, allow_lockbox: bool = False) -> pd.DataFrame:
    """Every validator period that ended by ``observed_through``, with its node's next period and the outcome."""
    cutoff = check_cutoff(observed_through, allow_lockbox)
    columns = ["transaction_hash", "node_id", "start_time", "end_time", "duration_days", "stake_avax", "fee_rate"]
    missing = set(columns) - set(periods.columns)
    if missing:
        raise ValueError(f"periods lack columns {sorted(missing)}")
    known = periods.loc[periods.accepted_at.lt(cutoff)] if "accepted_at" in periods else periods
    rows = known.sort_values(["node_id", "start_time", "transaction_hash"]).reset_index(drop=True)
    by_node = rows.groupby("node_id", sort=False)
    rows["period_number"] = by_node.cumcount() + 1
    for name in ("transaction_hash", "start_time", "duration_days", "stake_avax", "fee_rate"):
        rows[f"next_{name}"] = by_node[name].shift(-1)
    # A next period only counts once it has started by the cut: an accepted future start is not yet a return.
    late = rows.next_start_time.gt(cutoff)
    rows.loc[late, [c for c in rows.columns if c.startswith("next_")]] = np.nan
    rows["next_start_time"] = pd.to_datetime(rows.next_start_time)
    events = rows.loc[rows.end_time.le(cutoff)].copy()
    events["gap_days"] = (events.next_start_time - events.end_time) / DAY
    has_next = events.next_start_time.notna()
    horizon_passed = events.end_time.add(horizon_days * DAY).le(cutoff)
    outcome = np.select(
        [has_next & events.gap_days.lt(0),
         has_next & events.gap_days.le(renew_days),
         has_next & events.gap_days.le(horizon_days),
         horizon_passed],
        ["overlap", "renew", "return", "leave"], default="censored")
    events["outcome"] = pd.Categorical(outcome, categories=[*OUTCOMES, "overlap", "censored"])
    renew_known = (has_next & events.gap_days.le(renew_days)) | events.end_time.add(renew_days * DAY).le(cutoff)
    events["renewed"] = np.where(renew_known & ~events.outcome.eq("overlap"),
                                 events.outcome.eq("renew").astype(float), np.nan)
    events["next_duration_class"] = duration_class(events.next_duration_days)
    events["stake_change_log"] = np.log(events.next_stake_avax / events.stake_avax)
    events["fee_change"] = events.next_fee_rate - events.fee_rate
    events.attrs.update(observed_through=str(cutoff), renew_days=renew_days, horizon_days=horizon_days)
    return events.reset_index(drop=True)


def summary(events: pd.DataFrame) -> pd.DataFrame:
    """Counts and AVAX by outcome, the observed picture behind a principal-flow Sankey."""
    table = events.groupby("outcome", observed=False).agg(events=("transaction_hash", "size"),
                                                          stake_avax=("stake_avax", "sum"))
    table["share_of_events"] = table.events / table.events.sum()
    table["share_of_stake"] = table.stake_avax / table.stake_avax.sum()
    return table
