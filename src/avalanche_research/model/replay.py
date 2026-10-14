"""Replay recorded staking periods through the cadCAD engine and compare with the monetary ledger.

The replay has no behaviour. Each day's validator and delegation starts, ends, and reward payments are
exogenous inputs taken from ``derived.staking-periods``. The model's state is the active stake and counts
and the rewards paid that day, in integer nAVAX. It must equal ``derived.avax-monetary-daily`` on every
complete day, to the nAVAX. That proves the engine, the state layout, and the day convention before any
behaviour is added.

The ledger observes stake at the last second of each UTC day: a period counts on day D when it starts at
or before D 23:59:59 and ends after it. Rewards paid on D are those whose reward transaction was accepted
on D. By default the replay stops before the validation lockbox, which starts 2025-11-19 16:00 UTC.

:class:`MintReplay` replays the chain's reward counter as the lifecycle models account for it: every validator and
delegator period mints its potential reward into the supply when it is accepted, and a period that ends without its
reward gives the potential reward back, so the counter is the supply the next reward is priced on. Stepped one UTC day
at a time from the recorded counter before the window's first mint, with the day's recorded mints and reversals, the
counter at each day's end must equal the recorded counter before the next day's first mint, to the nAVAX. That proves
the models' supply accounting with delegator rewards in issuance. :func:`recomputed_mints` walks the same window one
mint at a time, pricing each with the chain's reward rule on the chained counter, so the models' pricing path is
checked against every recorded potential reward.
"""

from __future__ import annotations

from datetime import UTC, date
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import param

from avalanche_research.mechanisms import ChainReward, RewardMechanism
from avalanche_research.model.engine import SimulationModel

WEI_PER_NAVAX = 10**9
US_PER_DAY = 86_400_000_000
INSTANT_US = 86_399_000_000
LOCKBOX_FIRST_DAY = date(2025, 11, 19)
LOCKBOX_START = pd.Timestamp("2025-11-19 16:00:00")
MINT_STOCKS = ("supply_navax", "minted_validator_navax", "minted_delegator_navax", "unpaid_navax")
ROLES = ("validator", "delegator")
STOCKS = ("active_validator_stake_navax", "active_delegated_stake_navax", "active_validators", "active_delegations")

EVENTS_SQL = f"""
WITH p AS (
    SELECT role, stake_navax,
           (epoch_us(start_time) - {INSTANT_US} + {US_PER_DAY} - 1) // {US_PER_DAY} AS enter_day,
           (epoch_us(greatest(end_time, coalesce(last_cycle_end_time, end_time))) - {INSTANT_US} + {US_PER_DAY} - 1) // {US_PER_DAY} AS leave_day
    FROM read_parquet(?)
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
FROM read_parquet(?) WHERE rewarded_at IS NOT NULL GROUP BY 1 ORDER BY 1
"""

LEDGER_SQL = """
SELECT date_utc, complete, active_validator_stake_wei::VARCHAR AS validator_wei,
       active_delegated_stake_wei::VARCHAR AS delegated_wei, issued_rewards_wei::VARCHAR AS issued_wei,
       active_validators, active_delegations
FROM read_parquet(?) ORDER BY date_utc
"""


def daily_events(periods_parquet: str, through: date = LOCKBOX_FIRST_DAY) -> pd.DataFrame:
    """One row per UTC day before ``through``: stake and count changes by role, and rewards paid.

    ``through`` may not pass the first day of the validation lockbox.
    """
    if through > LOCKBOX_FIRST_DAY:
        raise ValueError(f"through {through} reaches into the validation lockbox, which starts 2025-11-19 16:00 UTC")
    events = duckdb.execute(EVENTS_SQL, [periods_parquet]).fetchall()
    rewards = duckdb.execute(REWARDS_SQL, [periods_parquet]).fetchall()
    first = min(min(row[0] for row in events), min(row[0] for row in rewards))
    last = (pd.Timestamp(through) - pd.Timestamp(0)).days - 1
    size = last - first + 1
    columns = {name: np.zeros(size, dtype=np.int64) for name in ("d_validator_stake", "d_delegated_stake", "d_validators", "d_delegations", "rewards_paid")}
    for day, role, stake, n in events:
        if first <= day <= last:
            prefix = "validator" if role == "validator" else "delegated"
            columns[f"d_{prefix}_stake"][day - first] += stake
            columns["d_validators" if role == "validator" else "d_delegations"][day - first] += n
    for day, amount in rewards:
        if first <= day <= last:
            columns["rewards_paid"][day - first] += amount
    dates = pd.to_datetime(np.arange(first, last + 1) * US_PER_DAY, unit="us").date
    return pd.DataFrame({"date_utc": dates, **columns})


class Replay(SimulationModel):
    """Recorded stake starts, ends, and rewards, stepped one UTC day at a time."""

    events = param.DataFrame(default=None, allow_None=True, precedence=-1, doc="Daily events from daily_events")
    events_source = param.String(default="", doc="The staking-periods run the events came from")
    dt = param.Number(default=1.0, bounds=(0, None), inclusive_bounds=(False, True), doc="Days per timestep")

    def __init__(self, **params: Any):
        super().__init__(**params)
        if self.events is not None:
            self.timesteps = len(self.events)

    def initial_state(self):
        return {name: 0 for name in STOCKS} | {"rewards_paid_navax": 0}

    def blocks(self):
        table = self.events
        arrays = {name: table[name].to_numpy() for name in table.columns if name != "date_utc"}

        def p_day(params, substep, history, state):
            i = state["timestep"]
            return {name: int(values[i]) for name, values in arrays.items()}

        def add(variable, change):
            return lambda params, substep, history, state, signal: (variable, state[variable] + signal[change])

        return [{
            "policies": {"day": p_day},
            "variables": {
                "active_validator_stake_navax": add("active_validator_stake_navax", "d_validator_stake"),
                "active_delegated_stake_navax": add("active_delegated_stake_navax", "d_delegated_stake"),
                "active_validators": add("active_validators", "d_validators"),
                "active_delegations": add("active_delegations", "d_delegations"),
                "rewards_paid_navax": lambda params, substep, history, state, signal: ("rewards_paid_navax", signal["rewards_paid"]),
            },
        }]

    def invariants(self):
        return [(name, lambda state, name=name: state[name] >= 0) for name in STOCKS]


def compare(table: pd.DataFrame, events: pd.DataFrame, ledger_parquet: str) -> dict[str, Any]:
    """The replayed long table against the ledger on every complete day, exactly, in wei and counts."""
    wide = table.pivot_table(index="timestep", columns="variable", values="value", aggfunc="first")
    wide = wide[wide.index >= 1]
    wide.index = events["date_utc"].iloc[: len(wide)].to_numpy()
    ledger = duckdb.execute(LEDGER_SQL, [ledger_parquet]).df()
    ledger["date_utc"] = pd.to_datetime(ledger["date_utc"]).dt.date
    ledger = ledger[ledger["complete"] & ledger["date_utc"].isin(set(wide.index))]
    pairs = {
        "active_validator_stake": ("validator_wei", "active_validator_stake_navax", WEI_PER_NAVAX),
        "active_delegated_stake": ("delegated_wei", "active_delegated_stake_navax", WEI_PER_NAVAX),
        "issued_rewards": ("issued_wei", "rewards_paid_navax", WEI_PER_NAVAX),
        "active_validators": ("active_validators", "active_validators", 1),
        "active_delegations": ("active_delegations", "active_delegations", 1),
    }
    result: dict[str, Any] = {"complete_days": len(ledger), "first_date": str(ledger["date_utc"].min()), "last_date": str(ledger["date_utc"].max())}
    for name, (ledger_column, state_column, scale) in pairs.items():
        observed = ledger[ledger_column].map(int).to_numpy(dtype=object)
        replayed = np.array([int(v) * scale for v in wide.loc[ledger["date_utc"], state_column]], dtype=object)
        differ = [(str(d), int(o - r)) for d, o, r in zip(ledger["date_utc"], observed, replayed) if o != r]
        result[name] = {"days_differ": len(differ), "first_differences": differ[:5]}
    result["exact"] = all(result[name]["days_differ"] == 0 for name in pairs)
    return result


MINT_DAYS_SQL = f"""
WITH m AS (
    SELECT epoch_us(accepted_at) // {US_PER_DAY} AS day, accepted_at, supply_before_navax, potential_reward_navax, role, transaction_hash
    FROM read_parquet(?) WHERE accepted_at >= ?::TIMESTAMP AND accepted_at < ?::TIMESTAMP AND supply_before_navax IS NOT NULL
),
d AS (
    SELECT day, sum(potential_reward_navax) FILTER (WHERE role = 'validator')::BIGINT AS minted_validator_navax,
           sum(potential_reward_navax) FILTER (WHERE role = 'delegator')::BIGINT AS minted_delegator_navax,
           count(*) FILTER (WHERE role = 'delegator')::BIGINT AS delegations_started,
           arg_min(supply_before_navax, (accepted_at, supply_before_navax, transaction_hash))::BIGINT AS supply_first_navax
    FROM m GROUP BY 1
),
f AS (SELECT day, min(accepted_at) AS first_mint_at FROM m GROUP BY 1),
u AS (
    SELECT epoch_us(rewarded_at) // {US_PER_DAY} AS day, sum(potential_reward_navax)::BIGINT AS unpaid_navax, count(*)::BIGINT AS unpaid,
           coalesce(sum(potential_reward_navax) FILTER (WHERE rewarded_at < f.first_mint_at), 0)::BIGINT AS unpaid_before_first_mint_navax
    FROM read_parquet(?) r LEFT JOIN f ON f.day = epoch_us(r.rewarded_at) // {US_PER_DAY}
    WHERE rewarded_at >= ?::TIMESTAMP AND rewarded_at < ?::TIMESTAMP AND NOT rewarded GROUP BY 1
)
SELECT coalesce(d.day, u.day) AS day, coalesce(minted_validator_navax, 0) AS minted_validator_navax, coalesce(minted_delegator_navax, 0) AS minted_delegator_navax,
       coalesce(delegations_started, 0) AS delegations_started, supply_first_navax, coalesce(unpaid_navax, 0) AS unpaid_navax, coalesce(unpaid, 0) AS unpaid,
       coalesce(unpaid_before_first_mint_navax, 0) AS unpaid_before_first_mint_navax
FROM d FULL OUTER JOIN u USING (day) ORDER BY 1
"""

MINT_ROWS_SQL = """
WITH m AS (
    SELECT accepted_at AS at_time, supply_before_navax AS supply_navax, potential_reward_navax AS reward_navax, 0 AS kind, transaction_hash,
           stake_navax, (epoch_us(end_time) - epoch_us(start_time)) // 1000000 AS duration_seconds, start_time
    FROM read_parquet(?) WHERE accepted_at >= ?::TIMESTAMP AND accepted_at < ?::TIMESTAMP AND supply_before_navax IS NOT NULL
),
u AS (
    SELECT rewarded_at, NULL::BIGINT, potential_reward_navax, 1, transaction_hash, NULL::BIGINT, NULL::BIGINT, NULL::TIMESTAMP
    FROM read_parquet(?) WHERE rewarded_at >= ?::TIMESTAMP AND rewarded_at < ?::TIMESTAMP AND NOT rewarded
)
SELECT * FROM (SELECT * FROM m UNION ALL SELECT * FROM u) ORDER BY at_time, kind, supply_navax, transaction_hash
"""


def _window(start: date, through: date) -> tuple[pd.Timestamp, pd.Timestamp]:
    """The window's first instant and the instant it stops before, which may not pass the lockbox start."""
    first, last = pd.Timestamp(start), min(pd.Timestamp(through), LOCKBOX_START)
    if pd.Timestamp(through) > LOCKBOX_START:
        raise ValueError(f"through {through} reaches into the validation lockbox, which starts 2025-11-19 16:00 UTC")
    if first >= last:
        raise ValueError("the window needs a start before its end")
    return first, last


def mint_events(periods_parquet: str, start: date, through: date = LOCKBOX_FIRST_DAY) -> pd.DataFrame:
    """One row per UTC day from ``start`` to the day before ``through``: the potential rewards minted by the validator and
    delegator periods accepted that day, the count of delegations started, the recorded reward counter before the day's
    first mint, and the potential rewards given back by periods that ended that day without their reward, with the part
    of them given back before the day's first mint. A day with no mint carries no recorded counter. ``through`` may not pass the first day of the validation lockbox."""
    first, last = _window(start, through)
    rows = duckdb.execute(MINT_DAYS_SQL, [periods_parquet, first, last, periods_parquet, first, last]).df()
    rows["supply_first_navax"] = rows["supply_first_navax"].astype("Int64")
    first_day, last_day = (first - pd.Timestamp(0)).days, (last - pd.Timestamp(0)).days - (1 if last == last.normalize() else 0)
    days = pd.DataFrame({"day": np.arange(first_day, last_day + 1)})
    table = days.merge(rows, on="day", how="left")
    for column in ("minted_validator_navax", "minted_delegator_navax", "delegations_started", "unpaid_navax", "unpaid", "unpaid_before_first_mint_navax"):
        table[column] = table[column].fillna(0).astype(np.int64)
    table.insert(0, "date_utc", pd.to_datetime(table.pop("day").to_numpy() * US_PER_DAY, unit="us").date)
    return table


def mint_rows(periods_parquet: str, start: date, through: date = LOCKBOX_FIRST_DAY) -> pd.DataFrame:
    """Every mint and every reversal in the window, in record order: acceptance or reward instant, then mints before
    reversals at the same instant, then the recorded counter."""
    first, last = _window(start, through)
    return duckdb.execute(MINT_ROWS_SQL, [periods_parquet, first, last, periods_parquet, first, last]).df()


class MintReplay(SimulationModel):
    """The reward counter stepped one UTC day at a time from the recorded mints and reversals."""

    events = param.DataFrame(default=None, allow_None=True, precedence=-1, doc="Daily mints and reversals from mint_events")
    events_source = param.String(default="", doc="The staking-periods run the events came from")
    supply0_navax = param.Integer(default=0, bounds=(0, None), doc="The recorded reward counter before the window's first mint")
    dt = param.Number(default=1.0, bounds=(0, None), inclusive_bounds=(False, True), doc="Days per timestep")

    def __init__(self, **params: Any):
        super().__init__(**params)
        if self.events is not None:
            self.timesteps = len(self.events)

    def initial_state(self):
        return {"supply_navax": int(self.supply0_navax), "minted_validator_navax": 0, "minted_delegator_navax": 0, "unpaid_navax": 0, "issued_navax": 0}

    def blocks(self):
        table = self.events
        arrays = {name: table[name].to_numpy(dtype=np.int64) for name in ("minted_validator_navax", "minted_delegator_navax", "unpaid_navax")}

        def p_day(params, substep, history, state):
            i = state["timestep"]
            return {name: int(values[i]) for name, values in arrays.items()}

        def s_supply(params, substep, history, state, signal):
            return "supply_navax", state["supply_navax"] + signal["minted_validator_navax"] + signal["minted_delegator_navax"] - signal["unpaid_navax"]

        def s_copy(name):
            return lambda params, substep, history, state, signal: (name, signal[name])

        return [{
            "policies": {"day": p_day},
            "variables": {
                "supply_navax": s_supply,
                **{name: s_copy(name) for name in arrays},
                "issued_navax": lambda params, substep, history, state, signal: ("issued_navax", signal["minted_validator_navax"] + signal["minted_delegator_navax"]),
            },
        }]

    def invariants(self):
        return [("the counter stays within the cap", lambda state: 0 <= state["supply_navax"] <= 720_000_000 * WEI_PER_NAVAX)]


def compare_minting(table: pd.DataFrame, events: pd.DataFrame) -> dict[str, Any]:
    """The replayed counter at each day's end, less the next day's reversals before its first mint, against the recorded
    counter before that first mint, exactly. Days whose next day has no mint are not compared."""
    wide = table.pivot_table(index="timestep", columns="variable", values="value", aggfunc="first")
    recorded, early = events["supply_first_navax"], events["unpaid_before_first_mint_navax"]
    pairs = []
    # Timestep t holds the state after day t - 1 of the events, so the counter at the end of day t - 1 meets the counter
    # recorded before day t's first mint, once the reversals of day t that came before that mint are taken off.
    for t in range(1, len(events)):
        if pd.notna(recorded.iloc[t]):
            pairs.append((str(events["date_utc"].iloc[t - 1]), int(recorded.iloc[t]), int(wide.loc[t, "supply_navax"]) - int(early.iloc[t])))
    differ = [(day, observed - replayed) for day, observed, replayed in pairs if observed != replayed]
    # One difference carried unchanged through every later day is a single event the record places elsewhere, such as a
    # pending staker before Durango minted at its start; a difference that moves is a disagreement in the accounting.
    distinct = sorted({gap for _, gap in differ})
    return {"days_compared": len(pairs), "days_differ": len(differ), "first_differences": differ[:5], "exact": not differ,
            "distinct_differences": len(distinct), "constant_offset": distinct[0] if len(distinct) == 1 and len(differ) == len(pairs) - pairs.index(next(p for p in pairs if p[1] != p[2])) else None,
            "minted_delegator_navax": int(wide["minted_delegator_navax"].sum()), "minted_validator_navax": int(wide["minted_validator_navax"].sum()),
            "unpaid_navax": int(wide["unpaid_navax"].sum()), "delegations_started": int(events["delegations_started"].sum())}


def recomputed_mints(rows: pd.DataFrame, mechanism: RewardMechanism | None = None) -> dict[str, Any]:
    """Every mint of ``rows`` priced again by ``mechanism`` on the chained counter, which starts at the counter recorded
    before the first mint and moves by each recorded mint and reversal. Within one instant the record does not order a
    reversal against the mints, so a reversal is applied where the recorded counter of the next mint says the counter had
    already fallen. Returns the mints priced exactly, the mints whose counter the record contradicts, and the first of
    each kind of disagreement."""
    mechanism = mechanism or ChainReward()
    mints = rows[rows["kind"] == 0]
    if not len(mints):
        raise ValueError("the window holds no mint")
    supply = int(mints["supply_navax"].iloc[0])
    exact = priced_differently = counter_differs = 0
    first_price = first_counter = None
    for _, group in rows.groupby("at_time", sort=True):
        pending = [int(value) for value in group.loc[group["kind"] == 1, "reward_navax"]]
        remaining = list(group[group["kind"] == 0].itertuples(index=False))
        while remaining:
            # The next mint is the one the counter has reached. When none has, a reversal of the same instant came first.
            # When no reversal is left either, the record contradicts the counter and the mints go in recorded order.
            found = next((i for i, mint in enumerate(remaining) if int(mint.supply_navax) == supply), None)
            if found is None and pending:
                supply -= pending.pop(0)
                continue
            mint = remaining.pop(found if found is not None else 0)
            if supply != int(mint.supply_navax):
                counter_differs += 1
                first_counter = first_counter or (str(mint.at_time), int(mint.supply_navax), supply)
            priced = mechanism.potential_reward_navax(int(mint.stake_navax), int(mint.duration_seconds), supply,
                                                      mint.start_time.to_pydatetime().replace(tzinfo=UTC), 0)
            if priced == int(mint.reward_navax):
                exact += 1
            else:
                priced_differently += 1
                first_price = first_price or (str(mint.at_time), int(mint.reward_navax), priced)
            supply += int(mint.reward_navax)
        for value in pending:
            supply -= value
    return {"mints": len(mints), "priced_exactly": exact, "priced_differently": priced_differently, "counter_differs": counter_differs,
            "first_price_difference": first_price, "first_counter_difference": first_counter, "reversals": int((rows["kind"] == 1).sum())}
