"""The replay through the cadCAD engine: exact against the ledger before the lockbox, and stopped by its invariants."""

from datetime import date

import pandas as pd
import pytest

pytest.importorskip("cadCAD")

from avalanche_research import datasets
from avalanche_research.catalog import DataError
from avalanche_research.model.engine import InvariantError, run
from avalanche_research.model.replay import (
    LOCKBOX_FIRST_DAY,
    MintReplay,
    Replay,
    compare,
    compare_minting,
    daily_events,
    mint_events,
    mint_rows,
    recomputed_mints,
)


def built(dataset_id):
    try:
        return str(datasets.parquet_path(dataset_id))
    except (DataError, StopIteration, FileNotFoundError):
        pytest.skip(f"no built run of {dataset_id} in this checkout")


def test_replay_equals_the_ledger_on_every_complete_day_before_the_lockbox():
    events = daily_events(built("derived.staking-periods"))
    assert events["date_utc"].iloc[-1] < LOCKBOX_FIRST_DAY
    table = run(Replay(events=events, events_source="latest"))
    result = compare(table, events, built("derived.avax-monetary-daily"))
    assert result["complete_days"] > 1_800
    assert result["exact"], result


def test_the_reward_counter_replays_the_recorded_mints_and_reversals_to_the_navax_before_the_lockbox():
    """Delegator rewards in issuance: every validator and delegator mint and every unpaid reward given back, from the
    recorded counter before the first mint, meet the recorded counter before each day's first mint exactly."""
    periods = built("derived.staking-periods")
    start = date(2025, 9, 20)
    events = mint_events(periods, start)
    assert events["date_utc"].iloc[0] == start and events["date_utc"].iloc[-1] < LOCKBOX_FIRST_DAY
    assert events["delegations_started"].sum() > 10_000 and events["minted_delegator_navax"].sum() > 0 and events["unpaid"].sum() > 0
    anchor = int(events["supply_first_navax"].dropna().iloc[0])
    table = run(MintReplay(events=events, events_source="latest", supply0_navax=anchor))
    result = compare_minting(table, events)
    assert result["days_compared"] >= 55 and result["exact"], result
    # Each mint priced by the chain's rule on the chained counter is the recorded potential reward, except where several
    # reversals of one second fall between that second's mints, which the record does not order.
    priced = recomputed_mints(mint_rows(periods, start))
    assert priced["mints"] == events["delegations_started"].sum() + (priced["mints"] - events["delegations_started"].sum())
    assert priced["priced_differently"] == priced["counter_differs"] <= 0.0001 * priced["mints"], priced
    with pytest.raises(ValueError, match="lockbox"):
        mint_events(periods, start, date(2025, 11, 20))


def test_the_mint_replay_adds_mints_takes_reversals_off_and_compares_before_each_days_first_mint():
    events = pd.DataFrame({
        "date_utc": [date(2025, 6, 1), date(2025, 6, 2), date(2025, 6, 3)],
        "minted_validator_navax": [100, 0, 50], "minted_delegator_navax": [10, 20, 0], "delegations_started": [1, 2, 0],
        # Day 2 has a 7 nAVAX reversal before its first mint and 3 after; day 3 starts with the counter after day 2.
        "supply_first_navax": pd.array([1_000, 1_000 + 110 - 7, 1_000 + 110 - 10 + 20], dtype="Int64"),
        "unpaid_navax": [0, 10, 4], "unpaid": [0, 2, 1], "unpaid_before_first_mint_navax": [0, 7, 0], "unpaid_at_first_mint_navax": [0, 0, 0],
    })
    table = run(MintReplay(events=events, events_source="synthetic", supply0_navax=1_000))
    supply = table[table["variable"] == "supply_navax"].sort_values("timestep")["value"].tolist()
    assert supply == [1_000, 1_110, 1_120, 1_166]
    result = compare_minting(table, events)
    assert result["exact"] and result["days_compared"] == 2 and result["minted_delegator_navax"] == 30 and result["unpaid_navax"] == 14
    off = events.assign(supply_first_navax=pd.array([1_000, 1_104, 1_120], dtype="Int64"))
    assert compare_minting(run(MintReplay(events=off, events_source="synthetic", supply0_navax=1_000)), off)["first_differences"] == [("2025-06-01", 1)]
    # A reversal in the same second as the first mint is taken off when the recorded counter says it came first.
    tied = events.assign(supply_first_navax=pd.array([1_000, 1_000 + 110 - 7 - 2, 1_118], dtype="Int64"), unpaid_at_first_mint_navax=[0, 2, 0], unpaid_navax=[0, 12, 4])
    resolved = compare_minting(run(MintReplay(events=tied, events_source="synthetic", supply0_navax=1_000)), tied)
    assert resolved["exact"] and resolved["same_second_ties_resolved"] == 1


def synthetic_events(validator_changes):
    days = len(validator_changes)
    return pd.DataFrame({
        "date_utc": [date(2021, 1, 1 + i) for i in range(days)],
        "d_validator_stake": validator_changes,
        "d_delegated_stake": [0] * days,
        "d_validators": [1 if c > 0 else -1 if c < 0 else 0 for c in validator_changes],
        "d_delegations": [0] * days,
        "rewards_paid": [0] * days,
    })


def test_replay_accumulates_synthetic_events():
    table = run(Replay(events=synthetic_events([5, 0, -3]), events_source="synthetic"))
    stake = table[table["variable"] == "active_validator_stake_navax"].sort_values("timestep")["value"].tolist()
    assert stake == [0, 5, 5, 2]


def test_a_stake_that_goes_negative_stops_the_run():
    with pytest.raises(InvariantError):
        run(Replay(events=synthetic_events([5, -8, 0]), events_source="broken"))


def test_the_event_table_is_an_input_not_a_setting():
    model = Replay(events=synthetic_events([1]), events_source="synthetic")
    assert "events" not in model.settings()
    assert "events" not in model.specification()
    assert model.specification()["events_source"] == "synthetic"


def test_input_column_names_enter_the_specification_hash():
    """Swapping two input column names changes the hash, so a schema change cannot reuse a result (audit F2)."""
    events = pd.DataFrame({"date_utc": [date(2021, 1, 1)], "d_validator_stake": [0], "d_delegated_stake": [0],
                           "d_validators": [1], "d_delegations": [0], "rewards_paid": [0]})
    swapped = events.rename(columns={"d_validators": "d_delegations", "d_delegations": "d_validators"})
    assert Replay(events=events).specification_hash() != Replay(events=swapped).specification_hash()


def test_long_table_names_the_model_version():
    from avalanche_research.model import MODEL_VERSION
    from avalanche_research.model.engine import run

    events = pd.DataFrame({"date_utc": [date(2021, 1, 1)], "d_validator_stake": [5], "d_delegated_stake": [0],
                           "d_validators": [1], "d_delegations": [0], "rewards_paid": [0]})
    table = run(Replay(events=events))
    assert set(table["model_version"]) == {MODEL_VERSION} == {"0.8.0"}
