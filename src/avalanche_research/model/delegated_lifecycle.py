"""The fitted validator lifecycle with delegations, and delegator rewards counted in issuance.

:class:`DelegatedLifecycle` is :class:`FittedLifecycle` with one more stage at the end of its daily step,
:func:`~avalanche_research.model.parts.delegations.delegations_stage`. That stage reads the next state's validators
from the assembly stage, so the validator stages, their draws and their tables are those of the fitted lifecycle.

The delegation limit is the protocol's: the validator's own stake times one plus the delegation multiplier, 4 on
mainnet, capped at 3,000,000 AVAX of total weight. A validator's room for a new delegation is its reserved room: that
limit, less its own stake, less its open delegations, less the delegations accepted by the origin that have not yet
started. Before Durango a stake could be accepted up to two weeks before its start, so at an origin before it the
reserved room can be smaller than the room the open delegations alone leave.

Each new delegation mints its potential reward, by the same reward rule as a validator with no tenure, on the supply
left by the stake started before it, so issuance is validator rewards plus delegator rewards and the supply never
passes the cap. The delegator reward is the whole potential reward. The validator's fee is a share of it, so it moves
no issuance. Delegations open at the origin, and those accepted by it that start after it, were minted at acceptance
and add none.

Named operators, from the operator events known at the origin (:mod:`~avalanche_research.model.operator_events`), are
tracked through their delegations. Each delegation carries the row of the named operator that owns it, and each named
operator has its delegated stake as a state variable, ``<key>_delegated_stake_navax``. BENQI's is
``benqi_delegated_stake_navax``, and when BENQI is named its delegations are exactly those flagged as BENQI's. A named
operator's new delegations are BENQI's flow for BENQI, and part of the other delegators' flow for the rest. An operator
that closes makes no new delegation from its closing day, so a closed BENQI's flow stops. Without named operators every
delegation's row is -1 and the model is unchanged.

:func:`delegation_inputs` turns the delegation tables of an origin, open delegations, validators and scheduled
periods, into this model's inputs, with each validator named by its row of the fitted lifecycle's ``initial`` or
``scheduled`` table, and with the named operators known at the origin, each delegation's owner.
:func:`delegation_terms` reads the year of new delegations each new one draws its terms from, and
:func:`historical_flow` fits the flow block to the year's daily starts.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from functools import partial

import duckdb
import numpy as np
import pandas as pd
import param

from avalanche_research.domain.protocol import (
    ACP247_CURRENT_DELEGATION_MULTIPLIER,
    MAINNET,
)
from avalanche_research.model.delegation_blocks import (
    BenqiAllocation,
    DelegationFlow,
    DelegatorChoice,
)
from avalanche_research.model.fitted_lifecycle import (
    COMMITMENT,
    OUT,
    FittedLifecycle,
    decided_by_us,
)
from avalanche_research.model.operator_events import BENQI, NamedOperators, owners
from avalanche_research.model.parts.delegations import (
    DELEGATION,
    MIN_DELEGATION_DAYS,
    MIN_DELEGATOR_STAKE,
    SCHEDULED,
    DelegationSetup,
    delegations_stage,
    limits,
    on_validators,
    stake_on,
)
from avalanche_research.model.streams import KIND_OPEN, KIND_SCHEDULED, node_keys

US_PER_DAY = 86_400_000_000
FLOW_DAYS = 365
OPEN_COLUMNS = ["validator", "stakes", "days_left", "benqi"]
SCHEDULED_COLUMNS = ["validator", "validator_scheduled", "start_day", "stakes", "days", "benqi"]
NAMED_COLUMNS = ["operator", "key", "closes_day"]
DELEGATION_VARIABLES = ("active_delegations", "active_delegated_stake_navax", "benqi_delegated_stake_navax",
                        "validator_issued_navax", "delegator_issued_navax", "unplaced_delegations")
# The keys cadCAD adds to every state.
ENGINE_KEYS = ("simulation", "subset", "run", "substep", "timestep")


def _whole(values, what: str) -> np.ndarray:
    """``values`` as int64, refusing any that is not a whole number rather than truncating it."""
    raw = np.asarray(values)
    if raw.dtype.kind in "iu":
        return raw.astype(np.int64)
    if raw.dtype.kind != "f" or not (np.isfinite(raw) & (raw == np.floor(raw))).all():
        raise ValueError(f"{what} must be whole numbers")
    return raw.astype(np.int64)


def _operators(frame: pd.DataFrame, n_named: int) -> np.ndarray:
    """Each delegation's named operator row, -1 for none, from an ``operator`` column or none."""
    rows = _whole(frame["operator"], "a delegation's operator row") if "operator" in frame else np.full(len(frame), -1, dtype=np.int64)
    if len(rows) and (rows.min() < -1 or rows.max() >= n_named):
        raise ValueError("a delegation names an operator that is not a row of named_operators")
    return rows


def _validator_keys(frame: pd.DataFrame) -> np.ndarray:
    rows = np.asarray(frame["validator"], dtype=np.int64)
    later = np.asarray(frame["validator_scheduled"], dtype=bool) if "validator_scheduled" in frame else np.zeros(len(rows), bool)
    return np.where(later, node_keys(KIND_SCHEDULED, 0, rows), node_keys(KIND_OPEN, 0, rows))


class DelegatedLifecycle(FittedLifecycle):
    """Validator commitments, the nodes out of the set, and the delegations on the active validators."""

    delegation_flow = param.ClassSelector(class_=DelegationFlow, default=DelegationFlow(), doc="The block for the day's new delegations and BENQI's share of them")
    delegator_choice = param.ClassSelector(class_=DelegatorChoice, default=DelegatorChoice(), doc="The validator choice of delegators other than BENQI")
    benqi_allocation = param.ClassSelector(class_=BenqiAllocation, default=BenqiAllocation(), doc="BENQI's allocation among its validators")
    delegation_fee_shares = param.Integer(
        default=MAINNET.min_delegation_fee_shares, bounds=(MAINNET.min_delegation_fee_shares, 1_000_000),
        doc="Every validator's delegation fee in millionths, which the choice block reads. The protocol minimum until fees are inputs",
    )
    delegation_multiplier = param.Integer(
        default=ACP247_CURRENT_DELEGATION_MULTIPLIER, bounds=(0, 100),
        doc="Delegation a validator may take per unit of its own stake: 4 on mainnet, 24 under ACP-247",
    )
    placement_batch = param.Integer(
        default=256, bounds=(1, None),
        doc="New delegations placed together on the room at the batch's start. 1 places each on the room left by the one before",
    )
    open_delegations = param.DataFrame(
        default=None, allow_None=True, precedence=-1,
        doc="Delegations open at the origin: validator (a row of initial), stakes, days_left, benqi. Already minted",
    )
    scheduled_delegations = param.DataFrame(
        default=None, allow_None=True, precedence=-1,
        doc="Delegations accepted by the origin that start after it: validator (a row of initial, or of scheduled when "
            "validator_scheduled), start_day, stakes, days, benqi. Already minted. Each reserves room on its validator until it starts",
    )
    benqi_validators = param.DataFrame(
        default=None, allow_None=True, precedence=-1,
        doc="BENQI's validator set at the origin: validator (a row of initial, or of scheduled when validator_scheduled)",
    )
    delegation_terms = param.DataFrame(
        default=None, allow_None=True, precedence=-1,
        doc="New delegations of the year before the origin, from which each new one draws its terms: stake_navax, days, benqi",
    )
    named_operators = param.DataFrame(
        default=None, allow_None=True, precedence=-1,
        doc="The named operators known at the origin: operator, key, and closes_day, the day counted from the origin from "
            "which it makes no new delegation, NaN when it does not close. A delegation's operator column names its row",
    )

    @property
    def stages(self):
        """The fitted lifecycle's stages, then the delegations stage, which reads the next state's validators."""
        return (*FittedLifecycle.stages, ("delegations", partial(delegations_stage, setup=self._setup())))

    def _named(self) -> pd.DataFrame:
        frame = self.named_operators if self.named_operators is not None else pd.DataFrame(columns=NAMED_COLUMNS)
        keys = list(frame["key"])
        if len(set(keys)) != len(keys) or len(set(frame["operator"])) != len(frame):
            raise ValueError("each named operator needs its own name and key")
        closes = np.asarray(frame["closes_day"], dtype=float)
        _whole(closes[~np.isnan(closes)], "a named operator's closing day")
        return frame

    def _tracked(self) -> list[tuple[int, str]]:
        """(row, state variable) of each named operator other than BENQI, whose stake is benqi_delegated_stake_navax.
        A name the state already has is refused, so no operator overwrites another variable."""
        frame = self._named()
        tracked = [(row, f"{key}_delegated_stake_navax") for row, (name, key) in enumerate(zip(frame["operator"], frame["key"])) if name != BENQI]
        taken = {*super().state_variables(), *self.float_variables(), *DELEGATION_VARIABLES, *DELEGATION, *SCHEDULED, *COMMITMENT, *OUT,
                 "node_key", "out_node_key", *ENGINE_KEYS}
        clashes = [name for _, name in tracked if name in taken]
        if clashes:
            raise ValueError(f"a named operator's key gives a state variable the model already has: {', '.join(clashes)}")
        return tracked

    def _benqi_row(self) -> int:
        found = np.flatnonzero(self._named()["operator"].to_numpy() == BENQI)
        return int(found[0]) if len(found) else -1

    def state_variables(self):
        return [*super().state_variables(), *DELEGATION_VARIABLES[:3], *(name for _, name in self._tracked()), *DELEGATION_VARIABLES[3:]]

    def initial_state(self):
        state = super().initial_state()
        n_open, n_later = len(state["stakes"]), len(self.scheduled) if self.scheduled is not None else 0
        frame = self.open_delegations if self.open_delegations is not None else pd.DataFrame(columns=OPEN_COLUMNS)
        rows = np.asarray(frame["validator"], dtype=np.int64)
        stakes = np.asarray(frame["stakes"], dtype=np.int64)
        days_left = np.asarray(frame["days_left"], dtype=np.int64)
        if len(rows) and (rows.min() < 0 or rows.max() >= n_open):
            raise ValueError("an open delegation names a validator that is not a row of the initial commitments")
        if (stakes < MIN_DELEGATOR_STAKE).any() or (days_left < 1).any():
            raise ValueError("an open delegation needs at least the minimum delegator stake and a day left")
        if (days_left > state["days_left"][rows]).any():
            raise ValueError("an open delegation must end by its validator's end")
        limit = limits(state["stakes"], self._chain_time(0), self.delegation_multiplier)
        if (state["stakes"] + stake_on(n_open, rows, stakes) > limit).any():
            raise ValueError("the open delegations put a validator above its delegation limit")

        later = self.scheduled_delegations if self.scheduled_delegations is not None else pd.DataFrame(columns=SCHEDULED_COLUMNS)
        on_later = np.asarray(later["validator_scheduled"], dtype=bool) if "validator_scheduled" in later else np.zeros(len(later), bool)
        later_rows = np.asarray(later["validator"], dtype=np.int64)
        start_day, days = np.asarray(later["start_day"], dtype=np.int64), np.asarray(later["days"], dtype=np.int64)
        if len(later_rows) and (later_rows.min() < 0 or (later_rows >= np.where(on_later, n_later, n_open)).any()):
            raise ValueError("a scheduled delegation names a validator that is not a row of the initial or scheduled commitments")
        if (np.asarray(later["stakes"], dtype=np.int64) < MIN_DELEGATOR_STAKE).any() or (start_day < 1).any() or (days < 1).any():
            raise ValueError("a scheduled delegation needs at least the minimum delegator stake, a start after the origin and a day")
        # A validator open at the origin is active through day days_left - 1, a scheduled one from its start_day for
        # its days, and a delegation from its start_day for its days.
        v_start, v_end = np.zeros(len(later_rows), dtype=np.int64), np.zeros(len(later_rows), dtype=np.int64)
        v_end[~on_later] = state["days_left"][later_rows[~on_later]]
        if on_later.any():
            v_start[on_later] = np.asarray(self.scheduled["start_day"], dtype=np.int64)[later_rows[on_later]]
            v_end[on_later] = v_start[on_later] + np.asarray(self.scheduled["days"], dtype=np.int64)[later_rows[on_later]]
        if (start_day < v_start).any() or (start_day + days > v_end).any():
            raise ValueError("a scheduled delegation must run inside its validator's period")

        benqi = np.asarray(frame["benqi"], dtype=bool)
        later_benqi = np.asarray(later["benqi"], dtype=bool)
        n_named, benqi_row = len(self._named()), self._benqi_row()
        operator, later_operator = _operators(frame, n_named), _operators(later, n_named)
        if benqi_row >= 0 and (((operator == benqi_row) != benqi).any() or ((later_operator == benqi_row) != later_benqi).any()):
            raise ValueError("BENQI is named, so its delegations must be exactly those flagged as BENQI's")
        delegations = {
            "delegation_stakes": stakes, "delegation_days_left": days_left, "delegation_days": days_left.copy(),
            "delegation_validator": state["node_key"][rows], "delegation_benqi": benqi,
            "delegation_rewards": np.zeros(len(stakes), dtype=np.int64), "delegation_operator": operator,
            "scheduled_stakes": np.asarray(later["stakes"], dtype=np.int64), "scheduled_start_day": start_day, "scheduled_days": days,
            "scheduled_validator": _validator_keys(later) if len(later) else np.zeros(0, dtype=np.int64),
            "scheduled_benqi": later_benqi, "scheduled_operator": later_operator,
        }
        return {
            **state, **delegations,
            "active_delegations": len(stakes),
            "active_delegated_stake_navax": int(stakes.sum()),
            "benqi_delegated_stake_navax": int(stakes[benqi].sum()),
            **{name: int(stakes[operator == row].sum()) for row, name in self._tracked()},
            "validator_issued_navax": 0,
            "delegator_issued_navax": 0,
            "unplaced_delegations": 0,
        }

    def _chain_time(self, timestep: int) -> datetime:
        return datetime.combine(self.origin + timedelta(days=timestep), time(12), tzinfo=UTC)

    def _terms(self) -> dict[bool, tuple[np.ndarray, np.ndarray]]:
        """Stake and requested days for BENQI's new delegations and for the others. A kind with no rows of its own
        draws from every row."""
        terms = self.delegation_terms
        if terms is None or not len(terms):
            if self.delegation_flow.mean_per_day > 0:
                raise ValueError("a delegation flow needs delegation_terms to draw each new delegation's stake and duration")
            return {}
        stakes, days = np.asarray(terms["stake_navax"], dtype=np.int64), np.asarray(terms["days"], dtype=np.int64)
        if (stakes < MIN_DELEGATOR_STAKE).any() or (days < MIN_DELEGATION_DAYS).any():
            raise ValueError(f"delegation terms need at least the minimum delegator stake and {MIN_DELEGATION_DAYS} days")
        benqi = np.asarray(terms["benqi"], dtype=bool) if "benqi" in terms else np.zeros(len(stakes), bool)
        return {kind: (stakes[rows], days[rows]) for kind in (True, False)
                for rows in [(benqi == kind) if (benqi == kind).any() else np.ones(len(stakes), bool)]}

    def _setup(self) -> DelegationSetup:
        frame = self.benqi_validators if self.benqi_validators is not None else pd.DataFrame(columns=["validator"])
        n_open = len(self.initial) if self.initial is not None else 0
        n_later = len(self.scheduled) if self.scheduled is not None else 0
        rows = np.asarray(frame["validator"], dtype=np.int64)
        on_later = np.asarray(frame["validator_scheduled"], dtype=bool) if "validator_scheduled" in frame else np.zeros(len(rows), bool)
        if len(rows) and (rows.min() < 0 or (rows >= np.where(on_later, n_later, n_open)).any()):
            raise ValueError("a BENQI validator is not a row of the initial or scheduled commitments")
        benqi_row = self._benqi_row()
        closes = float(self._named()["closes_day"].iloc[benqi_row]) if benqi_row >= 0 else np.nan
        return DelegationSetup(
            flow=self.delegation_flow, choice=self.delegator_choice, allocation=self.benqi_allocation,
            fee_shares=self.delegation_fee_shares, multiplier=self.delegation_multiplier,
            benqi_keys=_validator_keys(frame) if len(frame) else np.zeros(0, dtype=np.int64),
            terms=self._terms(), batch=self.placement_batch,
            benqi_operator=benqi_row, benqi_closes_day=None if np.isnan(closes) else int(closes),
        )

    def blocks(self):
        [block] = super().blocks()

        def s_copy(name):
            return lambda params, substep, history, state, signal: (name, signal[name])

        def s_scalar(name, value):
            return lambda params, substep, history, state, signal: (name, value(signal))

        block["variables"] |= {
            **{name: s_copy(name) for name in (*DELEGATION, *SCHEDULED, "validator_issued_navax", "delegator_issued_navax", "unplaced_delegations")},
            "active_delegations": s_scalar("active_delegations", lambda g: len(g["delegation_stakes"])),
            "active_delegated_stake_navax": s_scalar("active_delegated_stake_navax", lambda g: int(g["delegation_stakes"].sum())),
            "benqi_delegated_stake_navax": s_scalar("benqi_delegated_stake_navax", lambda g: int(g["delegation_stakes"][g["delegation_benqi"]].sum())),
            **{name: s_scalar(name, lambda g, row=row: int(g["delegation_stakes"][g["delegation_operator"] == row].sum()))
               for row, name in self._tracked()},
        }
        return [block]

    def invariants(self):
        multiplier = self.delegation_multiplier

        def within_limits(s):
            rows = on_validators(s["node_key"], s["delegation_validator"])
            if (rows < 0).any():
                return False
            limit = limits(s["stakes"], self._chain_time(s["timestep"]), multiplier)
            return bool((s["stakes"] + stake_on(len(s["stakes"]), rows, s["delegation_stakes"]) <= limit).all())

        def end_by_validator(s):
            rows = on_validators(s["node_key"], s["delegation_validator"])
            return bool((rows >= 0).all() and (s["delegation_days_left"] <= s["days_left"][rows]).all())

        benqi_row, tracked = self._benqi_row(), self._tracked()

        def named_stakes(s):
            mine = s["delegation_operator"]
            benqi = benqi_row < 0 or bool(((mine == benqi_row) == s["delegation_benqi"]).all())
            return benqi and all(s[name] == int(s["delegation_stakes"][mine == row].sum()) for row, name in tracked)

        return [
            *super().invariants(),
            ("each named operator's delegated stake matches its delegations, and BENQI's are those flagged", named_stakes),
            ("every delegation on an active validator within its delegation limit", within_limits),
            ("every delegation ends by its validator's end", end_by_validator),
            ("delegated stake total matches the delegations", lambda s: s["active_delegated_stake_navax"] == int(s["delegation_stakes"].sum())),
            ("issuance is validator plus delegator rewards", lambda s: s["issued_navax"] == s["validator_issued_navax"] + s["delegator_issued_navax"]),
            ("all stake within supply", lambda s: s["active_validator_stake_navax"] + s["active_delegated_stake_navax"] <= s["supply_navax"]),
        ]


def _days_after(times: pd.Series, cutoff_us: int) -> np.ndarray:
    """The UTC day, counted from the origin, whose end is the first at or after each time."""
    us = pd.to_datetime(times).astype("datetime64[us]").astype(np.int64).to_numpy()
    return (us - cutoff_us + US_PER_DAY - 1) // US_PER_DAY


def _validator_order(periods_parquet: str, origin: date) -> tuple[np.ndarray, np.ndarray]:
    """The transaction hashes of the fitted lifecycle's ``initial`` and ``scheduled`` rows, in its order, with their
    stakes: validator periods open at the origin's last instant, and those accepted by it that start after it."""
    cutoff = decided_by_us(origin)
    common = f"FROM read_parquet(?) WHERE role = 'validator' AND stake_navax IS NOT NULL AND start_time {{}} make_timestamp({cutoff})"
    opened = duckdb.execute(
        f"SELECT transaction_hash, stake_navax, end_time {common.format('<=')} ORDER BY start_time, transaction_hash", [periods_parquet]).df()
    opened = opened[opened["end_time"] > pd.Timestamp(cutoff, unit="us")]
    later = duckdb.execute(
        f"SELECT transaction_hash, stake_navax {common.format('>')} AND accepted_at <= make_timestamp({cutoff}) ORDER BY start_time, transaction_hash",
        [periods_parquet]).df()
    return opened[["transaction_hash", "stake_navax"]].reset_index(drop=True), later


def delegation_inputs(tables: dict[str, pd.DataFrame], periods_parquet: str, origin: date, state: dict,
                      named: NamedOperators | None = None) -> dict:
    """This model's delegation inputs at ``origin`` from the origin's delegation tables, ``open``, ``validators`` and
    ``scheduled``, and the fitted lifecycle's ``state`` (``initial`` and ``scheduled``) built from the same periods.

    Each delegation names its validator by transaction hash. That hash becomes a row of ``initial``, or of ``scheduled``
    for a validator period that starts after the origin. BENQI's validators are those with a BENQI delegation open or
    scheduled at the origin.

    With ``named``, the named operators known at the origin, each delegation also gets its owner's row, by its funding
    address and acceptance time, and ``named_operators`` is returned. The tables flag BENQI's delegations by their own
    rule, which the flow and terms also read, so the delegations a BENQI named by the events owns must be exactly those
    the tables flag, in ``open``, ``scheduled`` and ``starts``, and none is flagged when BENQI is not named, or the
    inputs are refused."""
    opened, later = _validator_order(periods_parquet, origin)
    if (opened["stake_navax"].to_numpy() != np.asarray(state["initial"]["stakes"])).any() or len(opened) != len(state["initial"]):
        raise ValueError("the open validator periods do not match the initial commitments row for row")
    if len(later) != len(state["scheduled"]) or (later["stake_navax"].to_numpy() != np.asarray(state["scheduled"]["stakes"])).any():
        raise ValueError("the scheduled validator periods do not match the scheduled commitments row for row")
    open_row = dict(zip(opened["transaction_hash"], range(len(opened))))
    later_row = dict(zip(later["transaction_hash"], range(len(later))))
    missing = set(tables["validators"]["transaction_hash"]) - set(open_row)
    if missing:
        raise ValueError(f"{len(missing)} validator periods open at the origin are not initial commitments")

    def where(hashes: pd.Series) -> tuple[np.ndarray, np.ndarray]:
        unknown = set(hashes) - set(open_row) - set(later_row)
        if unknown:
            raise ValueError(f"{len(unknown)} delegations name a validator period that is neither open nor scheduled at the origin")
        on_later = hashes.map(lambda h: h not in open_row).to_numpy(dtype=bool)
        return hashes.map(lambda h: open_row.get(h, later_row.get(h))).to_numpy(dtype=np.int64), on_later

    current = tables["open"]
    rows, on_later = where(current["validator_transaction_hash"])
    if on_later.any():
        raise ValueError("an open delegation names a validator period that has not started")
    open_delegations = pd.DataFrame({"validator": rows, "stakes": current["stake_navax"].to_numpy(dtype=np.int64),
                                     "days_left": current["days_left"].to_numpy(dtype=np.int64), "benqi": current["benqi"].to_numpy(dtype=bool)})

    cutoff = decided_by_us(origin)
    pending = tables["scheduled"][tables["scheduled"]["role"] == "delegator"]
    later_rows, later_on = where(pending["validator_transaction_hash"])
    start_day = _days_after(pending["start_time"], cutoff)
    scheduled_delegations = pd.DataFrame({
        "validator": later_rows, "validator_scheduled": later_on, "start_day": start_day,
        "stakes": pending["stake_navax"].to_numpy(dtype=np.int64), "days": _days_after(pending["end_time"], cutoff) - start_day,
        "benqi": pending["benqi"].to_numpy(dtype=bool),
    })

    benqi = pd.concat([open_delegations.loc[open_delegations["benqi"], ["validator"]].assign(validator_scheduled=False),
                       scheduled_delegations.loc[scheduled_delegations["benqi"], ["validator", "validator_scheduled"]]])
    benqi_validators = benqi.drop_duplicates().sort_values(["validator_scheduled", "validator"]).reset_index(drop=True)
    inputs = {"open_delegations": open_delegations, "scheduled_delegations": scheduled_delegations, "benqi_validators": benqi_validators}
    if named is None:
        return inputs
    if named.origin != origin:
        raise ValueError(f"the named operators are those known at {named.origin}, not at the origin {origin}")
    benqi_row = named.row(BENQI)
    for frame, source in ((open_delegations, current), (scheduled_delegations, pending), (None, tables.get("starts"))):
        if source is None:
            continue
        mine = owners(source["delegator_address"], source["accepted_at"], named)
        owned = (mine == benqi_row) if benqi_row >= 0 else np.zeros(len(mine), dtype=bool)
        if (owned != source["benqi"].to_numpy(dtype=bool)).any():
            raise ValueError("the operator events and the delegation tables set different delegations apart as BENQI's")
        if frame is not None:
            frame["operator"] = mine
    return {**inputs, "named_operators": named.model_table()}


def delegation_terms(periods_parquet: str, delegators_parquet: str, origin: date, benqi_funding: str, benqi_from: str) -> pd.DataFrame:
    """The delegations that started in the 365 days to the origin's last instant, in start order, each with its stake,
    its whole days from the day it starts to the day it ends, and whether it is BENQI's: funded by ``benqi_funding`` and
    accepted at or after ``benqi_from``. Its end counts its last cycle."""
    cutoff = decided_by_us(origin)
    rows = duckdb.execute(
        f"""SELECT p.stake_navax, p.start_time, greatest(p.end_time, coalesce(p.last_cycle_end_time, p.end_time)) AS end_time,
                   coalesce(f.delegator_address = ? AND p.accepted_at >= ?::TIMESTAMP, false) AS benqi
            FROM read_parquet(?) p LEFT JOIN read_parquet(?) f USING (transaction_hash)
            WHERE p.role = 'delegator' AND p.stake_navax IS NOT NULL AND p.end_time IS NOT NULL
              AND p.start_time > make_timestamp({cutoff - FLOW_DAYS * US_PER_DAY}) AND p.start_time <= make_timestamp({cutoff})
            ORDER BY p.start_time, p.transaction_hash""",
        [benqi_funding, benqi_from, periods_parquet, delegators_parquet],
    ).df()
    start_day = _days_after(rows["start_time"], cutoff)
    return pd.DataFrame({"stake_navax": rows["stake_navax"].to_numpy(dtype=np.int64),
                         "days": _days_after(rows["end_time"], cutoff) - start_day, "benqi": rows["benqi"].to_numpy(dtype=bool)})


def historical_flow(flows: pd.DataFrame, origin: date) -> DelegationFlow:
    """The flow block fitted to the daily delegation starts of the 365 UTC days to the origin day, a day with none
    counting as zero."""
    days = pd.date_range(end=pd.Timestamp(origin), periods=FLOW_DAYS, freq="D")
    started = flows.assign(date_utc=pd.to_datetime(flows["date_utc"])).pivot_table(
        index="date_utc", columns="benqi", values="started", aggfunc="sum").reindex(days).fillna(0)
    benqi = started[True].to_numpy(dtype=np.int64) if True in started else np.zeros(FLOW_DAYS, dtype=np.int64)
    others = started[False].to_numpy(dtype=np.int64) if False in started else np.zeros(FLOW_DAYS, dtype=np.int64)
    return DelegationFlow.fit(benqi + others, benqi, f"delegation starts in the {FLOW_DAYS} days to {origin}")
