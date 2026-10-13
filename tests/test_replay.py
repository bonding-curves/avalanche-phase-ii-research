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
    Replay,
    compare,
    daily_events,
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
