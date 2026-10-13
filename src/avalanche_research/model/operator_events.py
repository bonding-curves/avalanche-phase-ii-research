"""Named operators in the delegated lifecycle: which delegations each one owns, and when it closes, from the operator
events known at an origin.

The operator events, ``data/operator-events.json``, date each event twice: when it happened, and when public evidence of
it can first be shown. A forecast from an origin reads an event only when its evidence was surely public by the
origin's last instant, 23:59:59 UTC. An evidence time with a clock reading is that instant. A date alone means public at
some moment of that UTC day, so it is surely public only from the day's end, as in the identity groups. An event with no
public evidence before it happened is record-only, and no forecast reads it.

Two kinds of event act on the model:

* ``identity`` names addresses of its operator: the subjects of the attributions it cites that are tier AS1 evidence
  and not replaced by a later row. An address is named from the earliest instant at which an identity event citing it
  was surely public. A delegation is the operator's when one of its named addresses funds it and it was accepted at or
  after that instant, so no delegation is set apart before public evidence existed, as the delegation inputs do for
  BENQI.
* ``shutdown`` closes its operator from the UTC day it happened. From that day the operator makes no new delegation.
  The delegations it made before stay to their end, because the chain already holds them.

The other kinds, ``announcement``, ``fleet-start``, ``fleet-end`` and ``redemption-end``, describe validator fleets or a
protocol's notices, and move nothing in the delegated lifecycle. A kind not listed here is refused, so a new kind is
never ignored silently.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
EVENTS = ROOT / "data" / "operator-events.json"
ATTRIBUTIONS = ROOT / "data" / "operator-attributions.json"
BENQI = "BENQI"
ACTING = ("identity", "shutdown")
PASSIVE = ("announcement", "fleet-start", "fleet-end", "redemption-end")
OPERATOR_COLUMNS = ["operator", "key", "closes_on"]
ADDRESS_COLUMNS = ["address", "operator", "named_from"]
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?$")


@dataclass(frozen=True, eq=False)
class NamedOperators:
    """The named operators known at one origin. ``operators``: one row per operator with a named address, its name, a
    key for state variable names, and the day it closes, or None. ``addresses``: one row per named address, its
    operator, and the naive UTC instant from which it is named."""

    origin: date
    operators: pd.DataFrame
    addresses: pd.DataFrame

    def row(self, operator: str) -> int:
        """The operator's row of ``operators``, or -1 when it is not named at the origin."""
        found = np.flatnonzero(self.operators["operator"].to_numpy() == operator)
        return int(found[0]) if len(found) else -1

    def model_table(self) -> pd.DataFrame:
        """The delegated lifecycle's ``named_operators`` input: operator, key, and ``closes_day``, the day counted from
        the origin from which the operator makes no new delegation, NaN when it does not close."""
        closes = [float((day - self.origin).days) if day is not None else np.nan for day in self.operators["closes_on"]]
        return pd.DataFrame({"operator": self.operators["operator"].to_numpy(dtype=object),
                             "key": self.operators["key"].to_numpy(dtype=object), "closes_day": np.asarray(closes, dtype=float)})


def load(events_path: Path = EVENTS, attributions_path: Path = ATTRIBUTIONS) -> tuple[list[dict], list[dict]]:
    """The operator events and attributions, as the files list them."""
    return json.loads(events_path.read_text())["events"], json.loads(attributions_path.read_text())["attributions"]


def surely_public(value: str) -> pd.Timestamp:
    """The naive UTC instant from which evidence was surely public: the instant itself, or the end of a date's UTC day."""
    stamp = pd.Timestamp(value)
    stamp = (stamp.tz_convert("UTC").tz_localize(None) if stamp.tzinfo else stamp).as_unit("us")
    return stamp + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1) if len(value.strip()) == 10 else stamp


def origin_instant(origin: date) -> pd.Timestamp:
    """The origin's last instant, 23:59:59 UTC, as naive UTC."""
    return pd.Timestamp(origin).as_unit("us") + pd.Timedelta(seconds=86_399)


def known_events(events: list[dict], origin: date) -> list[dict]:
    """The schedulable events whose evidence was surely public by the origin's last instant."""
    unknown = sorted({event["kind"] for event in events} - set(ACTING) - set(PASSIVE))
    if unknown:
        raise ValueError(f"operator events of an unknown kind: {', '.join(unknown)}")
    instant = origin_instant(origin)
    return [event for event in events if event["forecast_use"] == "schedulable" and event["evidence_public_at"]
            and surely_public(event["evidence_public_at"]) <= instant]


def key(operator: str) -> str:
    """A name for state variables: the operator's name in lower case, with every other run of characters as one underscore."""
    return re.sub(r"[^a-z0-9]+", "_", operator.lower()).strip("_")


def named_operators(origin: date, events: list[dict] | None = None, attributions: list[dict] | None = None) -> NamedOperators:
    """The operators named at ``origin`` by the identity events known then, with the day each closes by the shutdown
    events known then. The files are read when ``events`` or ``attributions`` is not given."""
    if events is None or attributions is None:
        loaded = load()
        events = loaded[0] if events is None else events
        attributions = loaded[1] if attributions is None else attributions
    by_id = {row["attribution_id"]: row for row in attributions}
    replaced = {row["replaces"] for row in attributions if row["replaces"]}
    named: dict[str, tuple[str, pd.Timestamp]] = {}
    closes: dict[str, date] = {}
    for event in known_events(events, origin):
        operator = event["operator"]
        if event["kind"] == "identity":
            at = surely_public(event["evidence_public_at"])
            for code in event["attributions"]:
                row = by_id[code]
                if row["tier"] != "AS1" or row["class"] != "EVIDENCE" or code in replaced:
                    continue
                if row["name"] != operator:
                    raise ValueError(f"{event['event_id']} names {code} for {operator}, but {code} names {row['name']}")
                owner, since = named.get(row["subject"], (operator, at))
                if owner != operator:
                    raise ValueError(f"address {row['subject']} is named for both {owner} and {operator}")
                named[row["subject"]] = (operator, min(since, at))
        elif event["kind"] == "shutdown":
            when = event["happened_at"]
            if not when or not DAY.match(when):
                raise ValueError(f"{event['event_id']} is a shutdown without the day it happened, so no forecast can schedule it")
            day = date.fromisoformat(when[:10])
            closes[operator] = min(closes.get(operator, day), day)
    addresses = pd.DataFrame([{"address": address, "operator": operator, "named_from": at} for address, (operator, at) in named.items()],
                             columns=ADDRESS_COLUMNS).sort_values(["operator", "address"], kind="stable").reset_index(drop=True)
    names = list(dict.fromkeys(addresses["operator"]))
    keys = [key(name) for name in names]
    if len(set(keys)) != len(keys):
        raise ValueError(f"two named operators share a key: {keys}")
    operators = pd.DataFrame({"operator": names, "key": keys, "closes_on": [closes.get(name) for name in names]}, columns=OPERATOR_COLUMNS)
    return NamedOperators(origin, operators, addresses)


def owners(funding: pd.Series, accepted_at: pd.Series, named: NamedOperators) -> np.ndarray:
    """Each delegation's row of ``named.operators``: the operator whose named address funds it, when it was accepted at
    or after that address's naming instant, else -1."""
    rows = dict(zip(named.operators["operator"], range(len(named.operators))))
    found = dict(zip(named.addresses["address"], zip(named.addresses["operator"], named.addresses["named_from"])))
    accepted = pd.to_datetime(accepted_at).dt.tz_localize(None) if getattr(accepted_at.dtype, "tz", None) else pd.to_datetime(accepted_at)
    out = np.full(len(funding), -1, dtype=np.int64)
    for i, (address, at) in enumerate(zip(funding.tolist(), accepted.tolist())):
        if isinstance(address, str) and address in found and at >= found[address][1]:
            out[i] = rows[found[address][0]]
    return out

