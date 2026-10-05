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


def _check_identity(periods: pd.DataFrame) -> None:
    """Refuse periods that cannot be keyed or ordered: a repeated transaction, or a missing node, start or end."""
    duplicated = periods.transaction_hash.duplicated(keep=False)
    if duplicated.any():
        raise ValueError(f"{int(duplicated.sum())} periods repeat a transaction hash")
    for column in ("transaction_hash", "node_id", "start_time", "end_time"):
        missing = periods[column].isna()
        if missing.any():
            raise ValueError(f"{int(missing.sum())} periods miss {column}")


def decision_events(periods: pd.DataFrame, observed_through=LOCKBOX_START, renew_days: int = 7,
                    horizon_days: int = 365, allow_lockbox: bool = False) -> pd.DataFrame:
    """Every validator period that ended before ``observed_through``, with its node's next period and the outcome.

    ``observed_through`` is the first instant not observed. A period, a next start, or a follow-up window counts only if
    it lies strictly before it, so nothing touching the lockbox's first instant is an event or a label.
    """
    cutoff = check_cutoff(observed_through, allow_lockbox)
    columns = ["transaction_hash", "node_id", "start_time", "end_time", "duration_days", "stake_avax", "fee_rate"]
    missing = set(columns) - set(periods.columns)
    if missing:
        raise ValueError(f"periods lack columns {sorted(missing)}")
    _check_identity(periods)
    known = periods.loc[periods.accepted_at.lt(cutoff)] if "accepted_at" in periods else periods
    rows = known.sort_values(["node_id", "start_time", "transaction_hash"]).reset_index(drop=True)
    by_node = rows.groupby("node_id", sort=False)
    rows["period_number"] = by_node.cumcount() + 1
    for name in ("transaction_hash", "start_time", "duration_days", "stake_avax", "fee_rate"):
        rows[f"next_{name}"] = by_node[name].shift(-1)
    # A next period only counts once it has started by the cut: an accepted future start is not yet a return.
    late = rows.next_start_time.ge(cutoff)
    rows.loc[late, [c for c in rows.columns if c.startswith("next_")]] = np.nan
    rows["next_start_time"] = pd.to_datetime(rows.next_start_time)
    events = rows.loc[rows.end_time.lt(cutoff)].copy()
    events["gap_days"] = (events.next_start_time - events.end_time) / DAY
    has_next = events.next_start_time.notna()
    horizon_passed = events.end_time.add(horizon_days * DAY).lt(cutoff)
    outcome = np.select(
        [has_next & events.gap_days.lt(0),
         has_next & events.gap_days.le(renew_days),
         has_next & events.gap_days.le(horizon_days),
         horizon_passed],
        ["overlap", "renew", "return", "leave"], default="censored")
    events["outcome"] = pd.Categorical(outcome, categories=[*OUTCOMES, "overlap", "censored"])
    # Known only once the whole window has passed before the cut, so a window that reaches the cut is never labelled.
    renew_known = events.end_time.add(renew_days * DAY).lt(cutoff)
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


def principal_flow(events: pd.DataFrame, periods: pd.DataFrame, start, end, renew_days: int = 7) -> pd.DataFrame:
    """Validator stake moving through period ends and starts in ``[start, end)``, as conserved flows in AVAX.

    The observed counterpart of a principal-flow Sankey. Stake whose period ended in the window either starts again on
    the same node within ``renew_days`` or is out for longer. A renewal can add or withdraw stake, so the renewed flow
    reaches the next period's stake through two explicit nodes. Fresh principal is stake whose period started in the
    window without being a renewal: a node's first period, a return after a gap of up to a year, or a return after
    longer. Gross starts are renewed stake plus fresh principal. Every node's inflow equals its outflow, except the
    sources and the two ends.

    The renewed leg follows the periods that ended in the window, so gross starts include renewals that start up to
    ``renew_days`` after it and exclude renewals of periods that ended just before it: it is not exactly the stake that
    started in the window. Periods whose next one started before they ended (one in the history) are left out.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    ended = events.loc[events.end_time.ge(start) & events.end_time.lt(end) & events.renewed.notna()]
    renewed = ended.loc[ended.renewed.eq(1)]
    added = (renewed.next_stake_avax - renewed.stake_avax).clip(lower=0).sum()
    withdrawn = (renewed.stake_avax - renewed.next_stake_avax).clip(lower=0).sum()
    rows = periods.sort_values(["node_id", "start_time", "transaction_hash"])
    previous_end = rows.groupby("node_id", sort=False).end_time.shift(1)
    gap = (rows.start_time - previous_end) / DAY
    started = rows.start_time.ge(start) & rows.start_time.lt(end)
    first = rows.loc[started & previous_end.isna(), "stake_avax"].sum()
    returned = rows.loc[started & gap.gt(renew_days) & gap.le(365), "stake_avax"].sum()
    back_later = rows.loc[started & gap.gt(365), "stake_avax"].sum()
    flows = [
        ("Ended stake", "Renewed in place", renewed.stake_avax.sum()),
        ("Ended stake", "Out for more than a week", ended.loc[ended.renewed.eq(0), "stake_avax"].sum()),
        ("Added at renewal", "Renewed in place", added),
        ("Renewed in place", "Withdrawn at renewal", withdrawn),
        ("Renewed in place", "Gross starts", renewed.next_stake_avax.sum()),
        ("First period of a new node", "Fresh principal", first),
        ("Returned within a year", "Fresh principal", returned),
        ("Returned after more than a year", "Fresh principal", back_later),
        ("Fresh principal", "Gross starts", first + returned + back_later),
    ]
    table = pd.DataFrame(flows, columns=["source", "target", "avax"])
    table.attrs.update(window_start=str(start), window_end=str(end), renew_days=renew_days)
    return table.loc[table.avax.gt(0)].reset_index(drop=True)
