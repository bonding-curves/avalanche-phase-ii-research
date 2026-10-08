"""Delegation inputs at an origin, from a small synthetic staking-period log and delegator table."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from avalanche_research.core.catalog import DataError
from avalanche_research.datasets.derived import delegation_inputs as di

NAVAX = 10**9
BENQI = di.BENQI_FUNDING
ORIGIN = date(2023, 4, 1)

# (hash, role, node, validator hash, accepted and start, end, last cycle end, stake AVAX, fee, funding address)
ROWS = [
    ("V1", "validator", "A", None, "2021-11-01 00:00", "2023-12-01 00:00", None, 2_000, 0.02, None),
    ("V2", "validator", "B", None, "2022-06-01 00:00", "2023-03-01 00:00", "2023-06-01 00:00", 1_000_000, 0.05, None),
    ("V3", "validator", "C", None, "2023-04-02 00:00", "2023-12-01 00:00", None, 2_000, 0.02, None),
    # Open at the origin: started by 23:59:59 on 1 April and ending after it.
    ("D1", "delegator", "A", "V1", "2023-03-01 00:00", "2023-05-01 00:00", None, 5_000, None, BENQI),
    ("D2", "delegator", "A", "V1", "2023-04-01 23:59", "2023-06-01 00:00", None, 1_000, None, "avax1other"),
    ("D3", "delegator", "B", "V2", "2022-07-01 00:00", "2023-03-01 00:00", "2023-05-01 00:00", 2_000_000, None, BENQI),
    # Not open: ended on the origin day, or starts the next day.
    ("D4", "delegator", "A", "V1", "2023-02-01 00:00", "2023-04-01 12:00", None, 700, None, "avax1other"),
    ("D5", "delegator", "C", "V3", "2023-04-02 00:00", "2023-06-01 00:00", None, 300, None, "avax1other"),
    # Funded by BENQI's key before its evidence date, so not set apart.
    ("D6", "delegator", "A", "V1", "2021-12-01 00:00", "2023-09-01 00:00", None, 400, None, BENQI),
    # Accepted on the origin day, starting two days later: scheduled, so it reserves room on V1.
    ("D7", "delegator", "A", "V1", "2023-04-03 00:00", "2023-05-03 00:00", None, 250, None, "avax1other"),
]
ACCEPTED_EARLY = {"D7": "2023-04-01 08:00"}


def write(tmp_path: Path, rows=ROWS, accepted_early=ACCEPTED_EARLY, extra_funding=()) -> tuple[str, str]:
    frame = pd.DataFrame(rows, columns=["transaction_hash", "role", "node_id", "validator_transaction_hash", "start_time", "end_time",
                                        "last_cycle_end_time", "stake_avax", "delegation_fee_rate", "delegator_address"])
    for column in ("start_time", "end_time", "last_cycle_end_time"):
        frame[column] = pd.to_datetime(frame[column])
    frame["accepted_at"] = frame["start_time"]
    for name, accepted in accepted_early.items():
        frame.loc[frame["transaction_hash"] == name, "accepted_at"] = pd.Timestamp(accepted)
    frame["stake_navax"] = frame["stake_avax"].astype("int64") * NAVAX
    periods, delegators = tmp_path / "periods.parquet", tmp_path / "delegators.parquet"
    duckdb.from_df(frame.drop(columns=["delegator_address"])).write_parquet(str(periods))
    funding = frame[frame.role == "delegator"][["transaction_hash", "delegator_address"]]
    funding = pd.concat([funding, pd.DataFrame(extra_funding, columns=["transaction_hash", "delegator_address"])])
    duckdb.from_df(funding).write_parquet(str(delegators))
    return str(periods), str(delegators)


def test_open_delegations_follow_the_replay_rule_and_date_benqi_from_its_evidence(tmp_path):
    made = di.build(*write(tmp_path), ORIGIN)
    opened = made["open"].set_index("transaction_hash")
    assert sorted(opened.index) == ["D1", "D2", "D3", "D6"]
    assert opened["benqi"].to_dict() == {"D1": True, "D2": False, "D3": True, "D6": False}
    assert opened.loc["D3", "end_time"] == pd.Timestamp("2023-05-01")
    assert opened.loc["D1", "days_left"] == 30 and opened.loc["D1", "delegation_fee_rate"] == 0.02


def test_room_is_the_weight_limit_less_own_and_open_delegated_stake(tmp_path):
    rooms = di.build(*write(tmp_path), ORIGIN)["validators"].set_index("transaction_hash")
    assert sorted(rooms.index) == ["V1", "V2"]
    assert rooms.loc["V1", "room_navax"] == (5 * 2_000 - 2_000 - 5_000 - 1_000 - 400) * NAVAX
    assert rooms.loc["V2", "max_weight_navax"] == 3_000_000 * NAVAX
    assert rooms.loc["V2", "room_navax"] == 0 and rooms.loc["V2", "delegations"] == 1


def test_flows_cover_the_year_to_the_origin_day_only(tmp_path):
    flow = di.build(*write(tmp_path), ORIGIN)["flows"]
    assert flow["date_utc"].max() <= pd.Timestamp(ORIGIN) and flow["date_utc"].min() > pd.Timestamp(2022, 4, 1)
    started = flow.groupby("benqi")["started"].sum().to_dict()
    assert started == {False: 2, True: 2}
    assert flow["ended"].sum() == 1


def test_check_compares_with_the_replay_and_origins_in_the_lockbox_are_refused(tmp_path):
    made = di.build(*write(tmp_path), ORIGIN)
    replay = pd.Series({"active_delegations": 4, "active_delegated_stake_navax": (5_000 + 1_000 + 2_000_000 + 400) * NAVAX})
    assert di.check(made, replay)["equal"]
    assert not di.check(made, replay.replace({4: 5}))["equal"]
    with pytest.raises(ValueError, match="lockbox"):
        di.origin_instant(date(2025, 11, 19))



def test_commitments_accepted_by_the_origin_that_start_later_are_scheduled_and_reserve_room(tmp_path):
    made = di.build(*write(tmp_path), ORIGIN)
    assert made["scheduled"]["transaction_hash"].tolist() == ["D7"]
    assert "D7" not in set(made["open"]["transaction_hash"])
    room = made["validators"].set_index("transaction_hash").loc["V1"]
    assert room["scheduled_delegated_navax"] == 250 * NAVAX and room["room_reserved_navax"] == room["room_navax"] - 250 * NAVAX


def test_a_negative_reserved_room_is_counted_apart_and_keeps_the_scheduled_commitment(tmp_path):
    rows = [("V1", "validator", "A", None, "2023-01-01 00:00", "2023-12-01 00:00", None, 2_000, 0.02, None),
            ("D1", "delegator", "A", "V1", "2023-03-03 00:00", "2023-04-03 00:00", None, 5_000, None, "avax1one"),
            ("D2", "delegator", "A", "V1", "2023-04-03 00:00", "2023-05-03 00:00", None, 5_000, None, "avax1two")]
    made = di.build(*write(tmp_path, rows, {"D2": "2023-04-01 00:00"}), ORIGIN)
    room = made["validators"].set_index("transaction_hash").loc["V1"]
    assert room["room_navax"] == 3_000 * NAVAX and room["room_reserved_navax"] == -2_000 * NAVAX
    replay = pd.Series({"active_delegations": 1, "active_delegated_stake_navax": 5_000 * NAVAX})
    assert di.check(made, replay)["negative_reserved_room"] == 1
    assert made["scheduled"]["transaction_hash"].tolist() == ["D2"]


def changed(name: str, **fields) -> list[tuple]:
    columns = ["transaction_hash", "role", "node_id", "validator_transaction_hash", "start_time", "end_time", "last_cycle_end_time",
               "stake_avax", "delegation_fee_rate", "delegator_address"]
    return [tuple(fields.get(column, value) for column, value in zip(columns, row, strict=True)) if row[0] == name else row
            for row in ROWS]


@pytest.mark.parametrize(("rows", "extra_funding", "refusal"), [
    (ROWS, [("D2", "avax1again")], "repeated_funding 1"),
    (changed("D2", validator_transaction_hash=None), [], "no_validator_period 1"),
    (changed("D2", node_id="B"), [], "other_node 1"),
    (changed("D2", end_time="2024-01-01 00:00"), [], "outside_validator_period 1"),
    (changed("D5", end_time=None), [], "missing_fields 1"),
    (changed("D5", end_time="2023-04-02 00:00"), [], "empty_interval 1"),
    (changed("D5", role="observer"), [], "unknown_role 1"),
    (ROWS + [ROWS[-1]], [], "repeated_hash 1"),
    (changed("D2", node_id=None), [], "missing_fields 1"),
    (changed("D7", validator_transaction_hash="V3"), [], "validator_accepted_after_origin 1"),
])
def test_inputs_the_consumer_would_misread_are_refused(tmp_path, rows, extra_funding, refusal):
    with pytest.raises(DataError, match=refusal):
        di.build(*write(tmp_path, rows, extra_funding=extra_funding), ORIGIN)
