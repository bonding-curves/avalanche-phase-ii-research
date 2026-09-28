"""Replay observed staking commitments into the monetary ledger's daily stake and reward quantities.

The ledger (``derived.avax-monetary-daily``, built by ``monetary.py``) observes stake at the last second of each UTC
day: a period counts on day D when ``start_time <= D 23:59:59`` and ``end_time > D 23:59:59``. Rewards paid on D are
the realized rewards whose reward transaction was accepted on D. The replay rebuilds the same series from
``derived.staking-periods`` alone, as entry and expiry events accumulated the way the engine moves stake:
stake[D] = stake[D-1] + entries[D] - expiries[D]. Everything stays in integer nAVAX until the wei conversion,
which is exact (1 nAVAX = 10**9 wei).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

WEI_PER_NAVAX = 10**9
US_PER_DAY = 86_400_000_000
# The ledger's observation instant is 23:59:59 (monetary.STAKE_INSTANT), so day D is observed at D + 86,399 s.
INSTANT_US = 86_399_000_000
COMPONENTS = (
    ("active_validator_stake", "active_validator_stake_navax", "active_validator_stake_wei"),
    ("active_delegated_stake", "active_delegated_stake_navax", "active_delegated_stake_wei"),
    ("issued_rewards", "rewards_paid_navax", "issued_rewards_wei"),
)
COUNTS = (("active_validators", "active_validators"), ("active_delegations", "active_delegations"))

EVENTS_SQL = f"""
WITH p AS (
    SELECT role, stake_navax,
           -- first day D with start_time <= D + 23:59:59, and first day D with end_time <= D + 23:59:59
           (epoch_us(start_time) - {INSTANT_US} + {US_PER_DAY} - 1) // {US_PER_DAY} AS enter_day,
           (epoch_us(end_time) - {INSTANT_US} + {US_PER_DAY} - 1) // {US_PER_DAY} AS leave_day
    FROM staking_periods
    WHERE start_time IS NOT NULL AND end_time IS NOT NULL AND stake_navax IS NOT NULL
),
e AS (
    SELECT role, enter_day AS day, stake_navax AS stake, 1 AS n FROM p WHERE leave_day > enter_day
    UNION ALL
    SELECT role, leave_day AS day, -stake_navax AS stake, -1 AS n FROM p WHERE leave_day > enter_day
)
SELECT day, role, sum(stake)::BIGINT AS stake_navax, sum(n)::BIGINT AS n FROM e GROUP BY 1, 2 ORDER BY 1, 2
"""

REWARDS_SQL = f"""
SELECT epoch_us(rewarded_at) // {US_PER_DAY} AS day, sum(realized_reward_navax)::BIGINT AS rewards_navax
FROM staking_periods WHERE rewarded_at IS NOT NULL GROUP BY 1 ORDER BY 1
"""

LEDGER_SQL = """
SELECT date_utc, complete, active_validator_stake_wei::VARCHAR, active_delegated_stake_wei::VARCHAR,
       issued_rewards_wei::VARCHAR, active_validators, active_delegations
FROM avax_monetary_daily ORDER BY date_utc
"""


def replay(con: Any) -> pd.DataFrame:
    """Daily active validator stake, delegated stake, counts, and rewards paid, in nAVAX, from staking periods.

    One row per UTC date from the first event to the last. Columns: date_utc, active_validator_stake_navax,
    active_delegated_stake_navax, active_validators, active_delegations, rewards_paid_navax.
    """
    events = con.execute(EVENTS_SQL).fetchall()
    rewards = con.execute(REWARDS_SQL).fetchall()
    first = min(min(row[0] for row in events), min(row[0] for row in rewards))
    last = max(max(row[0] for row in events), max(row[0] for row in rewards))
    size = last - first + 1
    dv, dd, nv, nd, paid = (np.zeros(size, dtype=np.int64) for _ in range(5))
    for day, role, stake, n in events:
        stake_delta, count_delta = (dv, nv) if role == "validator" else (dd, nd)
        stake_delta[day - first] += stake
        count_delta[day - first] += n
    for day, amount in rewards:
        paid[day - first] += amount
    return pd.DataFrame({
        "date_utc": pd.to_datetime(np.arange(first, last + 1) * US_PER_DAY, unit="us").date,
        "active_validator_stake_navax": np.cumsum(dv),
        "active_delegated_stake_navax": np.cumsum(dd),
        "active_validators": np.cumsum(nv),
        "active_delegations": np.cumsum(nd),
        "rewards_paid_navax": paid,
    })


def compare(con: Any, frame: pd.DataFrame | None = None) -> dict[str, Any]:
    """Replay against the ledger on every complete day, exactly, in wei.

    Returns per component the number of complete days compared, the days that differ, the summed absolute
    residual in wei, and the first differing dates, plus the same for the two counts. ``exact`` is true when every
    component and count agrees on every complete day.
    """
    frame = replay(con) if frame is None else frame
    by_date = {row.date_utc: row for row in frame.itertuples(index=False)}
    ledger = con.execute(LEDGER_SQL).fetchall()
    result: dict[str, Any] = {"complete_days": 0, "components": {}, "counts": {}}
    diffs: dict[str, list[tuple[Any, int]]] = {name: [] for name, _, _ in COMPONENTS}
    diffs.update({name: [] for name, _ in COUNTS})
    complete = [row for row in ledger if row[1]]
    result["complete_days"] = len(complete)
    result["first_date"] = str(complete[0][0]) if complete else None
    result["last_date"] = str(complete[-1][0]) if complete else None
    for date_utc, _, validator_wei, delegated_wei, issued_wei, validators, delegations in complete:
        row = by_date.get(date_utc)
        observed = {"active_validator_stake": int(validator_wei), "active_delegated_stake": int(delegated_wei), "issued_rewards": int(issued_wei)}
        for name, navax_column, _ in COMPONENTS:
            replayed = 0 if row is None else int(getattr(row, navax_column)) * WEI_PER_NAVAX
            if replayed != observed[name]:
                diffs[name].append((date_utc, observed[name] - replayed))
        for name, column in COUNTS:
            replayed = 0 if row is None else int(getattr(row, column))
            ledger_value = validators if name == "active_validators" else delegations
            if replayed != ledger_value:
                diffs[name].append((date_utc, ledger_value - replayed))
    for name, _, wei_column in COMPONENTS:
        items = diffs[name]
        result["components"][wei_column] = {
            "days_differ": len(items),
            "abs_residual_wei": sum(abs(value) for _, value in items),
            "first_differences": [(str(day), value) for day, value in items[:5]],
        }
    for name, _ in COUNTS:
        items = diffs[name]
        result["counts"][name] = {"days_differ": len(items), "first_differences": [(str(day), value) for day, value in items[:5]]}
    result["exact"] = all(item["days_differ"] == 0 for item in result["components"].values()) and all(
        item["days_differ"] == 0 for item in result["counts"].values())
    return result
