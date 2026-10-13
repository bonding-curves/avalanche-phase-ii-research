"""The stake decision tables: renewals, returns and first-ever commitments, with the next stake and when it was decided."""

from __future__ import annotations

import hashlib
from datetime import date

import duckdb
import numpy as np
import pandas as pd
import pytest

from avalanche_research.model.fitted_blocks import AVAX
from avalanche_research.model.fitted_lifecycle import (
    STAKE_DECISION_COLUMNS,
    checked_stake_decisions,
    stake_decisions,
    training_events,
)

ORIGIN = date(2024, 3, 1)
# The origin's end is 2024-03-01 23:59:59 UTC. Its window runs from just after 2023-03-02 23:59:59 to that instant.
# (hash, node, start, end, stake AVAX)
PERIODS = [
    # A renews within seven days, then returns 18 days after its second commitment ends, keeping its stake.
    ("A1", "A", "2023-01-01 00:00:00", "2023-04-01 00:00:00", 2_000),
    ("A2", "A", "2023-04-03 00:00:00", "2023-07-02 00:00:00", 2_500),
    ("A3", "A", "2023-07-20 00:00:00", "2023-10-18 00:00:00", 2_500),
    # B enters in the window, renews exactly seven days after its end and returns one second later than that.
    ("B1", "B", "2023-06-01 00:00:00", "2023-09-01 00:00:00", 10_000),
    ("B2", "B", "2023-09-08 00:00:00", "2023-12-08 00:00:00", 12_000),
    ("B3", "B", "2023-12-15 00:00:01", "2024-12-14 00:00:01", 3_000_000),
    # C enters at the origin's last instant, which the window includes.
    ("C1", "C", "2024-03-01 23:59:59", "2024-03-15 23:59:59", 2_000),
    # E renews at the window's opening instant, which the window excludes. Its first commitment is older than a year.
    ("E1", "E", "2022-12-01 00:00:00", "2023-03-01 00:00:00", 4_000),
    ("E2", "E", "2023-03-02 23:59:59", "2023-06-01 23:59:59", 4_000),
    # F's second commitment starts before its first ends, so it made no decision. Its first is an entry.
    ("F1", "F", "2023-05-01 00:00:00", "2023-11-01 00:00:00", 5_000),
    ("F2", "F", "2023-08-01 00:00:00", "2024-01-01 00:00:00", 6_000),
    # G starts after the origin and is not read.
    ("G1", "G", "2024-03-02 00:00:00", "2024-04-02 00:00:00", 2_000),
]


def us(text: str) -> int:
    return int(pd.Timestamp(text).value // 1_000)


def write_periods(tmp_path, periods=PERIODS) -> str:
    frame = pd.DataFrame(periods, columns=["transaction_hash", "node_id", "start_time", "end_time", "stake_avax"])
    for column in ("start_time", "end_time"):
        frame[column] = pd.to_datetime(frame[column])
    frame["accepted_at"] = frame["start_time"]
    frame["role"] = "validator"
    frame["stake_navax"] = frame.pop("stake_avax").astype("int64") * AVAX
    frame["supply_before_navax"] = 450_000_000 * AVAX
    path = str(tmp_path / "periods.parquet")
    duckdb.from_df(frame).write_parquet(path)
    return path


def table(rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=list(STAKE_DECISION_COLUMNS)).astype(np.int64)


EXPECTED = {
    "renewal": table([
        (2_000 * AVAX, 90, 2_500 * AVAX, us("2023-04-03")),
        (10_000 * AVAX, 91, 12_000 * AVAX, us("2023-09-08")),
    ]),
    "return": table([
        (2_500 * AVAX, 90, 2_500 * AVAX, us("2023-07-20")),
        (12_000 * AVAX, 365, 3_000_000 * AVAX, us("2023-12-15 00:00:01")),
    ]),
    "entry": table([
        (0, 184, 5_000 * AVAX, us("2023-05-01")),
        (0, 92, 10_000 * AVAX, us("2023-06-01")),
        (0, 14, 2_000 * AVAX, us("2024-03-01 23:59:59")),
    ]),
}


def test_each_context_holds_its_decisions_in_the_window_with_the_next_commitments_start(tmp_path):
    tables = stake_decisions(write_periods(tmp_path), ORIGIN, "synthetic")
    assert list(tables) == ["renewal", "return", "entry"]
    for context, expected in EXPECTED.items():
        got = tables[context]
        assert list(got.columns) == list(STAKE_DECISION_COLUMNS)
        assert (got.dtypes == np.int64).all()
        pd.testing.assert_frame_equal(got.reset_index(drop=True), expected)
        assert got.attrs["context"] == context


def test_the_decisions_are_the_moves_and_first_commitments_that_training_events_returns_row_for_row(tmp_path):
    periods = write_periods(tmp_path)
    tables = stake_decisions(periods, ORIGIN, "synthetic")
    events = training_events(periods, ORIGIN, "synthetic")
    # Each table's index is the row's position in training_events' table, so renewal and return together rebuild the
    # moves table in its own order.
    rebuilt = pd.concat([tables["renewal"], tables["return"]]).sort_index()
    assert rebuilt.index.tolist() == list(range(len(events.moves))) == [0, 1, 2, 3]
    assert tables["renewal"].index.tolist() == [0, 2] and tables["return"].index.tolist() == [1, 3]
    columns = ["previous_stake_navax", "next_days", "next_stake_navax"]
    pd.testing.assert_frame_equal(rebuilt[columns], events.moves[columns])
    entry = tables["entry"]
    assert entry.index.tolist() == list(range(len(events.first_commitments)))
    first = events.first_commitments.rename(columns={"days": "next_days", "stake_navax": "next_stake_navax"})
    pd.testing.assert_frame_equal(entry[["next_days", "next_stake_navax"]], first[["next_days", "next_stake_navax"]])
    assert (entry["previous_stake_navax"] == 0).all()


def test_training_events_still_return_the_same_moves_and_first_commitments(tmp_path):
    events = training_events(write_periods(tmp_path), ORIGIN, "synthetic")
    moves = events.moves
    assert list(moves.columns) == ["previous_days", "next_days", "previous_stake_navax", "next_stake_navax", "node_code"]
    assert moves[["previous_stake_navax", "next_days", "next_stake_navax"]].values.tolist() == [
        [2_000 * AVAX, 90, 2_500 * AVAX], [2_500 * AVAX, 90, 2_500 * AVAX],
        [10_000 * AVAX, 91, 12_000 * AVAX], [12_000 * AVAX, 365, 3_000_000 * AVAX],
    ]
    assert moves["previous_days"].tolist() == [90, 90, 92, 91]
    assert events.first_commitments[["days", "stake_navax"]].values.tolist() == [
        [184, 5_000 * AVAX], [92, 10_000 * AVAX], [14, 2_000 * AVAX]]
    assert events.first_total == 3


def test_each_table_carries_its_run_origin_window_and_hash(tmp_path):
    tables = stake_decisions(write_periods(tmp_path), ORIGIN, "synthetic")
    for got in tables.values():
        digest = hashlib.sha256(got.to_csv(index=False).encode()).hexdigest()
        assert got.attrs["run"] == "synthetic"
        assert got.attrs["origin"] == "2024-03-01"
        assert got.attrs["window"] == "after 2023-03-02 23:59:59 UTC up to and including 2024-03-01 23:59:59 UTC"
        assert got.attrs["sha256"] == digest
        assert got.attrs["source"] == f"synthetic; origin 2024-03-01; 365 days; sha256 {digest}"


def test_a_changed_row_changes_the_tables_hash(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first = stake_decisions(write_periods(tmp_path / "a"), ORIGIN, "x")
    changed = [row if row[0] != "B2" else (*row[:4], 12_001) for row in PERIODS]
    second = stake_decisions(write_periods(tmp_path / "b", changed), ORIGIN, "x")
    assert first["renewal"].attrs["sha256"] != second["renewal"].attrs["sha256"]
    assert first["entry"].attrs["sha256"] == second["entry"].attrs["sha256"]


@pytest.mark.parametrize(("extra", "words"), [
    # An entrant below the minimum stake.
    ([("H1", "H", "2023-08-01 00:00:00", "2023-09-01 00:00:00", 1_999)], "entry"),
    # A renewal from a stake above the maximum.
    ([("H1", "H", "2023-08-01 00:00:00", "2023-09-01 00:00:00", 3_000_001),
      ("H2", "H", "2023-09-02 00:00:00", "2023-10-02 00:00:00", 2_000)], "renewal"),
    # A return to a 366-day commitment.
    ([("H1", "H", "2022-01-01 00:00:00", "2022-02-01 00:00:00", 2_000),
      ("H2", "H", "2023-08-01 00:00:00", "2024-08-01 00:00:00", 2_000)], "return"),
])
def test_a_stake_or_duration_outside_the_fit_domain_is_refused_not_dropped(tmp_path, extra, words):
    with pytest.raises(ValueError, match=words):
        stake_decisions(write_periods(tmp_path, PERIODS + extra), ORIGIN, "synthetic")


@pytest.mark.parametrize("origin", [date(2025, 11, 19), date(2025, 11, 20)])
def test_an_origin_whose_window_reaches_the_lockbox_is_refused_before_any_read(origin):
    with pytest.raises(ValueError, match="lockbox"):
        stake_decisions("unused.parquet", origin, "synthetic")


def test_the_day_before_the_lockbox_is_a_valid_origin(tmp_path):
    late = [("K1", "K", "2025-11-18 23:59:59", "2025-12-02 23:59:59", 2_000)]
    tables = stake_decisions(write_periods(tmp_path, PERIODS + late), date(2025, 11, 18), "synthetic")
    assert tables["entry"]["decided_us"].tolist() == [us("2025-11-18 23:59:59")]
    assert len(tables["renewal"]) == len(tables["return"]) == 0


LOCKBOX_US = us("2025-11-19 16:00:00")


@pytest.mark.parametrize(("context", "row", "words"), [
    ("renewal", (2_000 * AVAX, 30, 2_000 * AVAX, LOCKBOX_US), "lockbox"),
    ("renewal", (2_000 * AVAX, 30, 2_000 * AVAX, LOCKBOX_US + 1), "lockbox"),
    ("return", (2_000 * AVAX, 0, 2_000 * AVAX, LOCKBOX_US - 1), "days"),
    ("return", (2_000 * AVAX, 366, 2_000 * AVAX, LOCKBOX_US - 1), "days"),
    ("renewal", (1_999 * AVAX, 30, 2_000 * AVAX, LOCKBOX_US - 1), "previous stake"),
    ("renewal", (0, 30, 2_000 * AVAX, LOCKBOX_US - 1), "previous stake"),
    ("entry", (2_000 * AVAX, 30, 2_000 * AVAX, LOCKBOX_US - 1), "previous stake"),
    ("entry", (0, 30, 3_000_000 * AVAX + 1, LOCKBOX_US - 1), "next stake"),
])
def test_the_check_refuses_each_invalid_row(context, row, words):
    with pytest.raises(ValueError, match=words):
        checked_stake_decisions(context, table([row]))


@pytest.mark.parametrize(("context", "row"), [
    ("renewal", (2_000 * AVAX, 1, 3_000_000 * AVAX, LOCKBOX_US - 1)),
    ("return", (3_000_000 * AVAX, 365, 2_000 * AVAX, LOCKBOX_US - 1)),
    ("entry", (0, 14, 2_000 * AVAX, LOCKBOX_US - 1)),
])
def test_the_check_passes_rows_at_the_edges_of_the_range(context, row):
    assert checked_stake_decisions(context, table([row])).equals(table([row]))


def test_the_check_refuses_an_unknown_context_or_a_column_that_is_not_int64():
    with pytest.raises(ValueError, match="context"):
        checked_stake_decisions("arrival", table([(0, 14, 2_000 * AVAX, 0)]))
    with pytest.raises(ValueError, match="int64"):
        checked_stake_decisions("entry", table([(0, 14, 2_000 * AVAX, 0)]).astype({"next_days": float}))


def test_a_table_changed_after_it_was_built_is_refused_and_an_unchanged_one_passes(tmp_path):
    tables = stake_decisions(write_periods(tmp_path), ORIGIN, "synthetic")
    entry = tables["entry"]
    assert checked_stake_decisions("entry", entry) is entry
    entry.loc[entry.index[0], "next_stake_navax"] += AVAX
    with pytest.raises(ValueError, match="changed after they were built"):
        checked_stake_decisions("entry", entry)


def test_a_one_day_commitment_is_in_the_fit_domain_although_the_protocol_refused_it():
    one_day = pd.DataFrame({"previous_stake_navax": [0], "next_days": [1], "next_stake_navax": [2_000 * AVAX],
                            "decided_us": [1_704_067_200_000_000]}, dtype=np.int64)
    assert checked_stake_decisions("entry", one_day) is one_day
