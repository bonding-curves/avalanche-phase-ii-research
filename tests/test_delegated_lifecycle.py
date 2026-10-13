"""The delegated lifecycle: the fitted validator lifecycle with a delegations stage, built against simple blocks, and
its inputs from the delegation tables of an origin."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import duckdb
import numpy as np
import pandas as pd
import pytest

from avalanche_research.datasets.derived import delegation_inputs as di
from avalanche_research.domain.protocol import (
    MAINNET_REWARD,
    delegation_weight_limit_navax,
)
from avalanche_research.model import streams, variants
from avalanche_research.model.delegated_lifecycle import (
    DelegatedLifecycle,
    delegation_inputs,
    delegation_terms,
)
from avalanche_research.model.delegation_blocks import (
    BenqiAllocation,
    DelegationFlow,
    DelegatorChoice,
)
from avalanche_research.model.engine import _execute, run
from avalanche_research.model.fitted_blocks import AVAX, Arrivals, RenewalLogit
from avalanche_research.model.fitted_lifecycle import FittedLifecycle, training_events
from avalanche_research.model.operator_events import load, named_operators, owners
from avalanche_research.model.parts.delegations import limits, on_validators, stake_on
from avalanche_research.model.variants import DEVELOPMENT_MODELS, VARIANTS, Prepared

VALIDATOR_VARIABLES = ["active_validators", "active_validator_stake_navax", "returning_nodes", "supply_navax", "issued_navax"]
DELEGATION_PURPOSES = {"delegations", "delegation_benqi", "delegation_terms", "delegator_choice", "benqi_allocation"}


def validators(**overrides):
    base = {
        "initial": pd.DataFrame({
            "stakes": np.array([2, 5, 10, 40, 100, 2]) * 1_000 * AVAX, "days_left": [3, 40, 90, 20, 200, 15],
            "done": [0, 1, 3, 5, 9, 2], "after_return": [False] * 6, "days": [14, 60, 120, 30, 365, 30], "handed_on": [False] * 6,
        }),
        "moves": pd.DataFrame({"previous_days": [14, 60, 120], "next_days": [30, 60, 180],
                               "previous_stake_navax": np.array([2, 10, 100]) * 1_000 * AVAX,
                               "next_stake_navax": np.array([3, 10, 90]) * 1_000 * AVAX}),
        "first_commitments": pd.DataFrame({"days": [20, 60], "stake_navax": np.array([2, 8]) * 1_000 * AVAX}),
        "renewal": RenewalLogit(),
        "arrivals": Arrivals(mean_per_day=1.5, dispersion=1.0),
        "timesteps": 20, "runs": 2, "seed": 7, "inputs_source": "synthetic",
    }
    return {**base, **overrides}


DELEGATIONS = pd.DataFrame({"validator": [1, 2, 2, 4], "stakes": np.array([500, 1_000, 25, 50_000]) * AVAX,
                            "days_left": [30, 60, 14, 200], "benqi": [False, True, False, True]})
TERMS = pd.DataFrame({"stake_navax": np.array([25, 300, 2_000, 6_000, 25, 1_500]) * AVAX,
                      "days": [14, 30, 60, 365, 14, 90], "benqi": [False, False, False, False, True, True]})
BENQI = pd.DataFrame({"validator": [2, 4]})


def delegated(**overrides):
    base = {"open_delegations": DELEGATIONS, "delegation_terms": TERMS, "benqi_validators": BENQI}
    return DelegatedLifecycle(**validators(**{**base, **overrides}))


def flowing(mean=6.0, share=0.4):
    return DelegationFlow(mean_per_day=mean, benqi_share=share)


def wide(table):
    return table.pivot_table(index=["run", "timestep"], columns="variable", values="value", aggfunc="first")


def final_states(model):
    """The state after each day, one row per run and timestep, with every array the engine carried."""
    raw = _execute([model])
    last = raw.groupby(["run", "timestep"])["substep"].transform("max")
    return raw[raw["substep"] == last].sort_values(["run", "timestep"]).reset_index(drop=True)


# Without new delegations, the subclass is the validator lifecycle.

def test_with_no_new_delegations_the_validator_tables_are_identical_to_the_fitted_lifecycle():
    ours = run(delegated(delegation_flow=DelegationFlow()))
    theirs = run(FittedLifecycle(**validators()))
    columns = ["run", "timestep", "time", "variable", "value", "yield_gap_pp", "model_version"]
    pick = lambda t: t[t["variable"].isin(VALIDATOR_VARIABLES)][columns].sort_values(columns[:5]).reset_index(drop=True)
    pd.testing.assert_frame_equal(pick(ours), pick(theirs))
    # The open delegations stay on their validators and add nothing to issuance: they were minted before the origin.
    ours = wide(ours)
    assert (ours["delegator_issued_navax"] == 0).all()
    assert ours.loc[(1, 0), "active_delegations"] == 4


def test_delegations_draw_from_their_own_streams_so_they_move_no_validator_decision():
    ours = wide(run(delegated(delegation_flow=flowing())))
    theirs = wide(run(FittedLifecycle(**validators())))
    for variable in ("active_validators", "active_validator_stake_navax", "returning_nodes"):
        assert ours[variable].tolist() == theirs[variable].tolist()
    assert ours["delegator_issued_navax"].sum() > 0


# Issuance and the supply cap.

def test_issuance_is_validator_rewards_plus_delegator_rewards_and_supply_grows_by_issuance():
    table = wide(run(delegated(delegation_flow=flowing())))
    assert (table["issued_navax"] == table["validator_issued_navax"] + table["delegator_issued_navax"]).all()
    for _, path in table.groupby(level="run"):
        assert (path["supply_navax"].diff().iloc[1:] == path["issued_navax"].iloc[1:]).all()
    assert table["delegator_issued_navax"].sum() > 0 and table["validator_issued_navax"].sum() > 0


def test_each_new_delegation_is_priced_by_the_reward_rule_on_the_supply_left_by_the_one_before():
    model = delegated(delegation_flow=flowing(mean=4.0), runs=1, timesteps=6)
    states = final_states(model)
    for t in range(1, len(states)):
        before, after = states.iloc[t - 1], states.iloc[t]
        new = after["delegation_days_left"] == after["delegation_days"]
        supply = int(before["supply_navax"]) + int(after["validator_issued_navax"])
        start = datetime.combine(model.origin + timedelta(days=t), time(12), tzinfo=UTC)
        for stake, d, reward in zip(after["delegation_stakes"][new], after["delegation_days"][new], after["delegation_rewards"][new]):
            assert reward == model.mechanism.potential_reward_navax(int(stake), int(d) * 86_400, supply, start, 0)
            supply += int(reward)
        assert supply == after["supply_navax"]


def test_supply_never_passes_the_cap_even_from_just_below_it():
    near = MAINNET_REWARD.supply_cap_navax - 50 * AVAX
    table = wide(run(delegated(delegation_flow=flowing(mean=20.0), supply0_navax=near)))
    assert (table["supply_navax"] <= MAINNET_REWARD.supply_cap_navax).all()
    assert (table["issued_navax"] == table["validator_issued_navax"] + table["delegator_issued_navax"]).all()


# The delegation cap.

@pytest.mark.parametrize("batch", [1, 3, 256])
def test_no_validator_ever_carries_more_than_its_delegation_limit(batch):
    large = TERMS.assign(stake_navax=np.array([3_000, 6_000, 8_000, 25, 5_000, 25]) * AVAX)
    model = delegated(delegation_flow=flowing(mean=25.0, share=0.3), delegation_terms=large, timesteps=15, placement_batch=batch)
    states = final_states(model)
    assert states["unplaced_delegations"].sum() > 0, "the flow should be large enough for the limit to bind"
    for _, state in states.iterrows():
        chain_time = datetime.combine(model.origin + timedelta(days=int(state["timestep"])), time(23, 59, 59), tzinfo=UTC)
        order = np.argsort(state["node_key"])
        where = order[np.searchsorted(state["node_key"], state["delegation_validator"], sorter=order)]
        assert (state["node_key"][where] == state["delegation_validator"]).all(), "every delegation is on an active validator"
        assert (state["delegation_days_left"] <= state["days_left"][where]).all(), "every delegation ends by its validator's end"
        on = np.zeros(len(state["stakes"]), dtype=np.int64)
        np.add.at(on, where, state["delegation_stakes"])
        for self_stake, delegated_stake in zip(state["stakes"], on):
            assert int(self_stake) + int(delegated_stake) <= delegation_weight_limit_navax(int(self_stake), chain_time)


def test_benqi_delegates_only_to_its_own_validators_and_others_to_any():
    states = final_states(delegated(delegation_flow=flowing(mean=10.0, share=0.5)))
    benqi_keys = set(states.iloc[0]["node_key"][BENQI["validator"].to_numpy()].tolist())
    every = pd.concat([pd.DataFrame({"key": s["delegation_validator"], "benqi": s["delegation_benqi"]}) for _, s in states.iterrows()])
    assert set(every.loc[every["benqi"], "key"]) <= benqi_keys
    assert not set(every.loc[~every["benqi"], "key"]) <= benqi_keys


def test_open_delegations_above_the_limit_or_past_their_validator_are_refused():
    over = DELEGATIONS.assign(stakes=np.array([500, 1_000, 25, 450_000]) * AVAX)
    with pytest.raises(ValueError, match="limit"):
        delegated(open_delegations=over).initial_state()
    late = DELEGATIONS.assign(days_left=[30, 60, 14, 201])
    with pytest.raises(ValueError, match="end"):
        delegated(open_delegations=late).initial_state()


# Randomness.

def test_every_draw_comes_from_the_keyed_streams(monkeypatch):
    used = []
    keyed = streams.Streams.uniforms

    def record(self, purpose, *keys):
        used.append(purpose)
        return keyed(self, purpose, *keys)

    def refuse(*args, **kwargs):
        raise AssertionError("a draw outside the keyed streams")

    monkeypatch.setattr(streams.Streams, "uniforms", record)
    for name in ("default_rng", "random", "Generator", "RandomState", "seed"):
        monkeypatch.setattr(np.random, name, refuse)
    run(delegated(delegation_flow=flowing(), timesteps=5, runs=1))
    assert DELEGATION_PURPOSES <= set(used) <= set(streams.PURPOSES)


def test_runs_replay_from_the_seed_and_differ_by_seed_and_run():
    first = wide(run(delegated(delegation_flow=flowing())))
    again = wide(run(delegated(delegation_flow=flowing())))
    other = wide(run(delegated(delegation_flow=flowing(), seed=8)))
    pd.testing.assert_frame_equal(first, again)
    assert first["active_delegated_stake_navax"].tolist() != other["active_delegated_stake_navax"].tolist()
    by_run = first["active_delegated_stake_navax"].unstack(level="run")
    assert not by_run[1].equals(by_run[2])


# The blocks follow the behaviour block contract, so fitted blocks replace them.

def test_the_choice_blocks_recover_known_coefficients_from_their_own_draws():
    rng = np.random.default_rng(3)
    sets = np.repeat(np.arange(800), 12)
    inputs = {"choice_set": sets, "fee_shares": rng.integers(20_000, 200_000, len(sets)),
              "remaining_navax": (np.exp(rng.uniform(np.log(25), np.log(2_000_000), len(sets))) * AVAX).astype(np.int64)}
    truth = DelegatorChoice(fee=-20.0, log_capacity=0.8)
    chosen = truth.sample(inputs, rng)
    assert np.bincount(sets, weights=chosen).tolist() == [1.0] * 800
    fitted = DelegatorChoice.fit(inputs, chosen, "synthetic")
    assert fitted.fee == pytest.approx(-20.0, abs=6.0) and fitted.log_capacity == pytest.approx(0.8, abs=0.1)
    assert fitted.log_prob(inputs, chosen) >= DelegatorChoice().log_prob(inputs, chosen)
    assert fitted.sources()["fee"]["source"] == "fitted"
    benqi = BenqiAllocation.fit(inputs, BenqiAllocation(capacity_power=1.5).sample(inputs, rng), "synthetic")
    assert benqi.capacity_power == pytest.approx(1.5, abs=0.1)


def test_the_flow_block_fits_its_mean_and_benqi_share_and_counts_by_inversion():
    rng = np.random.default_rng(4)
    days = np.array([DelegationFlow(mean_per_day=30.0, benqi_share=0.25).sample({}, rng) for _ in range(400)])
    fitted = DelegationFlow.fit(days[:, 0], days[:, 1], "synthetic")
    assert fitted.mean_per_day == pytest.approx(30.0, rel=0.05) and fitted.benqi_share == pytest.approx(0.25, abs=0.03)
    assert fitted.log_prob({}, days) > DelegationFlow(mean_per_day=10.0, benqi_share=0.5).log_prob({}, days)
    counts = [fitted.count_from_uniform(u) for u in np.linspace(0.005, 0.995, 200)]
    assert counts == sorted(counts) and np.mean(counts) == pytest.approx(30.0, rel=0.05)
    assert DelegationFlow().count_from_uniform(0.99) == 0


# The delegations stage, and the reserved room.

def test_the_delegations_stage_runs_after_the_fitted_lifecycles_stages_which_are_unchanged():
    names = [name for name, _ in FittedLifecycle.stages]
    assert names == ["renewal", "returns", "arrivals", "continuation", "rewards", "assembly"]
    assert [name for name, _ in delegated().stages] == [*names, "delegations"]
    assert FittedLifecycle(**validators()).stages == FittedLifecycle.stages


ORIGIN = date(2024, 3, 1)
# (hash, role, node, validator hash, accepted, start, end, stake AVAX, funding address)
PERIODS = [
    ("V1", "validator", "A", None, "2023-12-01 00:00", "2023-12-01 00:00", "2024-06-01 00:00", 2_000, None),
    ("V2", "validator", "B", None, "2024-01-01 00:00", "2024-01-01 00:00", "2024-07-01 00:00", 2_000, None),
    # Accepted before the origin, starting after it, as a stake could be before Durango.
    ("V3", "validator", "C", None, "2024-02-28 10:00", "2024-03-05 00:00", "2024-06-05 00:00", 2_000, None),
    ("D1", "delegator", "A", "V1", "2024-02-01 00:00", "2024-02-01 00:00", "2024-04-15 00:00", 1_000, "avax1other"),
    ("D2", "delegator", "A", "V1", "2024-02-29 10:00", "2024-03-08 00:00", "2024-03-28 00:00", 6_000, "avax1other"),
    ("D3", "delegator", "C", "V3", "2024-03-01 10:00", "2024-03-06 00:00", "2024-04-06 00:00", 4_000, "avax1other"),
    ("D4", "delegator", "B", "V2", "2024-02-15 00:00", "2024-02-15 00:00", "2024-05-15 00:00", 8_000, di.BENQI_FUNDING),
]


def write_periods(tmp_path) -> tuple[str, str]:
    frame = pd.DataFrame(PERIODS, columns=["transaction_hash", "role", "node_id", "validator_transaction_hash", "accepted_at",
                                           "start_time", "end_time", "stake_avax", "delegator_address"])
    for column in ("accepted_at", "start_time", "end_time"):
        frame[column] = pd.to_datetime(frame[column])
    frame["last_cycle_end_time"] = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[us]")
    frame["stake_navax"] = frame.pop("stake_avax").astype("int64") * AVAX
    frame["delegation_fee_rate"] = np.where(frame["role"] == "validator", 0.02, np.nan)
    frame["supply_before_navax"] = 450_000_000 * AVAX
    periods, delegators = str(tmp_path / "periods.parquet"), str(tmp_path / "delegators.parquet")
    duckdb.from_df(frame.drop(columns="delegator_address")).write_parquet(periods)
    duckdb.from_df(frame.loc[frame["role"] == "delegator", ["transaction_hash", "delegator_address"]]).write_parquet(delegators)
    return periods, delegators


def origin_model(tmp_path, **overrides) -> tuple[DelegatedLifecycle, dict]:
    periods, delegators = write_periods(tmp_path)
    tables = di.build(periods, delegators, ORIGIN)
    state = training_events(periods, ORIGIN, "synthetic").state
    inputs = delegation_inputs(tables, periods, ORIGIN, state)
    terms = pd.DataFrame({"stake_navax": [5_000 * AVAX], "days": [14], "benqi": [False]})
    model = DelegatedLifecycle(**validators(**{
        **state, **inputs, "origin": ORIGIN, "delegation_terms": terms, "arrivals": Arrivals(mean_per_day=0.0),
        "delegation_flow": flowing(mean=3.0, share=0.0), "runs": 1, **overrides,
    }))
    return model, tables


def test_delegation_inputs_name_each_validator_by_its_row_and_give_the_reserved_room_of_the_tables(tmp_path):
    model, tables = origin_model(tmp_path)
    # V1 and V2 are open, in start order. V3 starts after the origin and is the first scheduled commitment.
    assert model.initial["stakes"].tolist() == [2_000 * AVAX] * 2 and len(model.scheduled) == 1
    assert model.open_delegations[["validator", "benqi"]].values.tolist() == [[0, False], [1, True]]
    assert model.scheduled_delegations[["validator", "validator_scheduled", "start_day", "days"]].values.tolist() == [[0, True, 5, 31], [0, False, 7, 20]]
    assert model.benqi_validators.values.tolist() == [[1, False]]
    state = model.initial_state()
    keys, stakes = state["node_key"], state["stakes"]
    room = (limits(stakes, datetime(2024, 3, 2, 12, tzinfo=UTC), 4) - stakes
            - stake_on(len(keys), on_validators(keys, state["delegation_validator"]), state["delegation_stakes"])
            - stake_on(len(keys), on_validators(keys, state["scheduled_validator"]), state["scheduled_stakes"]))
    by_hash = tables["validators"].set_index("transaction_hash")["room_reserved_navax"]
    assert room.tolist() == [by_hash["V1"], by_hash["V2"]] == [1_000 * AVAX, 0]


def test_a_delegation_scheduled_before_durango_reserves_room_the_instantaneous_room_would_give_away(tmp_path):
    # V1 has 2,000 AVAX of its own and 1,000 delegated: 7,000 AVAX of room now, but D2's 6,000 AVAX, accepted before the
    # origin, starts on day 7. A new 5,000 AVAX delegation fits the room now and not the reserved room.
    reserved, _ = origin_model(tmp_path, timesteps=20)
    table = wide(run(reserved))
    assert table["unplaced_delegations"].sum() > 0
    assert table["unplaced_delegations"].sum() == sum(reserved.delegation_flow.count_from_uniform(float(u))
                                                      for u in [streams.Streams(7, 1).uniforms("delegations", t)[0] for t in range(20)])
    assert (table["delegator_issued_navax"] == 0).all()
    # Started on day 7, D2 and D3 are open delegations from then on, within their validators' limits.
    assert table.loc[(1, 7), "active_delegations"] == 4 and table.loc[(1, 6), "active_delegations"] == 3

    instantaneous, _ = origin_model(tmp_path, timesteps=6, scheduled_delegations=None)
    states = final_states(instantaneous)
    on_v1 = states.iloc[-1]["delegation_validator"] == states.iloc[-1]["node_key"][0]
    placed = int(states.iloc[-1]["delegation_stakes"][on_v1].sum())
    assert placed > 1_000 * AVAX, "the instantaneous room places new delegations on V1"
    limit = delegation_weight_limit_navax(2_000 * AVAX, datetime(2024, 3, 8, tzinfo=UTC))
    assert 2_000 * AVAX + placed + 6_000 * AVAX > limit, "and V1 would pass its limit when D2 starts"


def test_delegation_terms_are_the_years_new_delegations_with_whole_days_and_benqi_by_funding_and_date(tmp_path):
    periods, delegators = write_periods(tmp_path)
    terms = delegation_terms(periods, delegators, ORIGIN, di.BENQI_FUNDING, di.BENQI_EVIDENCE)
    # Started in the year to the origin: D1 and D4. D2 and D3 start after it.
    assert terms.values.tolist() == [[1_000 * AVAX, 74, False], [8_000 * AVAX, 90, True]]


def test_the_stub_variant_is_built_from_the_origins_delegation_tables_and_kept_out_of_the_development_scores(tmp_path, monkeypatch):
    # Four periods are too few to fit the validator blocks, so the variant takes the origin's state with default blocks.
    synthetic = {key: validators()[key] for key in ("moves", "first_commitments")}
    monkeypatch.setattr(variants, "switched_inputs", lambda events, switches: {"origin": events.origin, **events.state, **synthetic})
    variant = VARIANTS["v0.8.1 stub"]
    assert variant.model is DelegatedLifecycle and "v0.8.1 stub" not in DEVELOPMENT_MODELS
    periods, delegators = write_periods(tmp_path)
    with pytest.raises(ValueError, match="delegation tables"):
        variant.prepare(periods, ORIGIN, "synthetic")
    tables = {**di.build(periods, delegators, ORIGIN), "terms": delegation_terms(periods, delegators, ORIGIN, di.BENQI_FUNDING, di.BENQI_EVIDENCE)}
    inputs = variant.prepare(periods, ORIGIN, "synthetic", delegations=tables).inputs
    # Two delegations started in the 365 days to the origin, one of them BENQI's.
    assert inputs["delegation_flow"].mean_per_day == pytest.approx(2 / 365) and inputs["delegation_flow"].benqi_share == 0.5
    assert len(inputs["open_delegations"]) == 2 and len(inputs["scheduled_delegations"]) == 2
    assert wide(run(variant.simulation(Prepared(inputs), seed=0, timesteps=10, runs=1)))["active_delegations"].iloc[-1] >= 3


# Named operators from the operator events known at the origin.

EVENTS, ATTRIBUTIONS = load()
BENQI_KEY = "avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy"
HOLDER = "avax1dwkwval9epuwxpy0g2m6xg2l00fx4yxtzah80t"
HOLDER_NAME = "mainnet genesis allocation holder"


def named_at(origin, events=EVENTS, attributions=ATTRIBUTIONS):
    return named_operators(origin, events, attributions)


def closes_at(origin, events=EVENTS):
    operators = named_at(origin, events).operators
    return {name: day for name, day in zip(operators["operator"], operators["closes_on"]) if day is not None}


def test_an_operator_is_named_only_from_the_end_of_the_instant_or_day_its_evidence_was_public():
    # The genesis allocation's evidence is a date alone, so it is surely public only from the end of 10 September 2020.
    assert named_at(date(2020, 9, 10)).operators.empty
    assert named_at(date(2020, 9, 11)).operators["operator"].tolist() == [HOLDER_NAME]
    # BENQI's key is named at 12:22:21 on 26 January 2022, inside that origin day, and its reward owner the next day.
    before, on, after = named_at(date(2022, 1, 25)), named_at(date(2022, 1, 26)), named_at(date(2022, 1, 27))
    assert before.row("BENQI") == -1 and on.row("BENQI") >= 0
    assert on.addresses.set_index("address").loc[BENQI_KEY, "named_from"] == pd.Timestamp("2022-01-26 12:22:21")
    assert len(on.addresses[on.addresses["operator"] == "BENQI"]) == 1
    assert len(after.addresses[after.addresses["operator"] == "BENQI"]) == 2
    latest = named_at(date(2025, 10, 1))
    assert latest.operators[["operator", "key"]].values.tolist() == [
        ["BENQI", "benqi"], ["GoGoPool (Hypha)", "gogopool_hypha"], [HOLDER_NAME, "mainnet_genesis_allocation_holder"]]


def test_a_closure_is_scheduled_only_once_its_evidence_was_public_and_record_only_events_never():
    # GoGoPool's end of support, 15 August 2026, can be shown only from 29 September 2026, a date alone.
    assert closes_at(date(2025, 10, 1)) == closes_at(date(2026, 9, 29)) == {}
    assert closes_at(date(2026, 9, 30)) == {"GoGoPool (Hypha)": date(2026, 8, 15)}
    table = named_at(date(2026, 9, 30)).model_table().set_index("operator")["closes_day"]
    assert table["GoGoPool (Hypha)"] == -46 and np.isnan(table["BENQI"])
    # The 2025 fleet ends had no public evidence before they happened, so no origin reads them, even as shutdowns.
    record_only = [event for event in EVENTS if event["forecast_use"] == "record-only"]
    assert record_only and all(event["evidence_public_at"] is None for event in record_only)
    shut = [dict(event, kind="shutdown", happened_at="2025-08-01") for event in record_only]
    assert closes_at(date(2030, 1, 1), EVENTS + shut) == closes_at(date(2030, 1, 1))


def test_events_of_an_unknown_kind_a_shutdown_without_its_day_and_a_mismatched_name_are_refused():
    with pytest.raises(ValueError, match="unknown kind"):
        named_at(date(2024, 1, 1), EVENTS + [dict(EVENTS[0], kind="merger")])
    undated = dict(EVENTS[3], happened_at="2026-08", evidence_public_at="2023-01-01")
    with pytest.raises(ValueError, match="day it happened"):
        named_at(date(2024, 1, 1), EVENTS + [undated])
    with pytest.raises(ValueError, match="names"):
        named_at(date(2024, 1, 1), EVENTS + [dict(EVENTS[5], operator="GoGoPool (Hypha)")])


def test_a_delegation_is_its_operators_when_a_named_address_funds_it_on_or_after_the_naming_instant():
    named = named_at(date(2025, 10, 1))
    funding = pd.Series([BENQI_KEY, BENQI_KEY, HOLDER, "avax1other", None])
    accepted = pd.Series(pd.to_datetime(["2022-01-26 12:22:21", "2022-01-26 12:22:20", "2025-08-29 14:22:52", "2025-01-01 00:00:00", "2025-01-01 00:00:00"]))
    assert owners(funding, accepted, named).tolist() == [named.row("BENQI"), -1, named.row(HOLDER_NAME), -1, -1]


NAMED = pd.DataFrame({"operator": ["BENQI", HOLDER_NAME], "key": ["benqi", "holder"], "closes_day": [np.nan, np.nan]})
OWNED = DELEGATIONS.assign(operator=[-1, 0, 1, 0])


def named(**overrides):
    return delegated(**{"open_delegations": OWNED, "named_operators": NAMED, **overrides})


def test_each_named_operator_is_tracked_through_its_delegations_and_benqis_new_ones_are_benqis():
    model = named(delegation_flow=flowing(mean=8.0, share=0.5))
    assert "holder_delegated_stake_navax" in model.state_variables()
    states = final_states(model)
    for _, state in states.iterrows():
        owner = state["delegation_operator"]
        assert ((owner == 0) == state["delegation_benqi"]).all()
        assert state["holder_delegated_stake_navax"] == int(state["delegation_stakes"][owner == 1].sum())
        assert state["benqi_delegated_stake_navax"] == int(state["delegation_stakes"][owner == 0].sum())
    # The holder's one delegation, 25 AVAX with 14 days left, runs off and is not replaced: its new delegations are
    # part of the other delegators' flow.
    holder = states.set_index(["run", "timestep"])["holder_delegated_stake_navax"]
    assert holder.loc[(1, 0)] == holder.loc[(1, 13)] == 25 * AVAX and holder.loc[(1, 14)] == 0
    assert states.iloc[-1]["benqi_delegated_stake_navax"] > 0


def test_named_operators_keep_the_golden_properties():
    # With no new delegations the validator tables are the fitted lifecycle's.
    columns = ["run", "timestep", "time", "variable", "value", "yield_gap_pp", "model_version"]

    def pick(table):
        return table[table["variable"].isin(VALIDATOR_VARIABLES)][columns].sort_values(columns[:5]).reset_index(drop=True)

    pd.testing.assert_frame_equal(pick(run(named(delegation_flow=DelegationFlow()))), pick(run(FittedLifecycle(**validators()))))
    # With a flow that binds the cap and a BENQI that closes, issuance is validator plus delegator rewards and no
    # validator passes its limit. The engine checks both every day, and the table shows the first.
    large = TERMS.assign(stake_navax=np.array([3_000, 6_000, 8_000, 25, 5_000, 25]) * AVAX)
    closing = NAMED.assign(closes_day=[6.0, np.nan])
    table = wide(run(named(delegation_flow=flowing(mean=25.0, share=0.3), delegation_terms=large, named_operators=closing, timesteps=15)))
    assert table["unplaced_delegations"].sum() > 0
    assert (table["issued_navax"] == table["validator_issued_navax"] + table["delegator_issued_navax"]).all()


def new_benqi(state) -> bool:
    return bool(((state["delegation_days_left"] == state["delegation_days"]) & state["delegation_benqi"]).any())


def test_from_its_closing_day_benqi_makes_no_new_delegation_and_before_it_nothing_changes():
    flow = flowing(mean=10.0, share=0.5)
    open_ = final_states(named(delegation_flow=flow))
    closed = final_states(named(delegation_flow=flow, named_operators=NAMED.assign(closes_day=[5.0, np.nan])))
    for (_, a), (_, b) in zip(open_.iterrows(), closed.iterrows()):
        if b["timestep"] < 5:
            for name in ("delegation_stakes", "delegation_validator", "delegation_benqi", "delegation_operator", "supply_navax"):
                assert np.array_equal(a[name], b[name])
        else:
            assert not new_benqi(b)
    assert any(new_benqi(s) for _, s in open_[open_["timestep"] >= 5].iterrows())
    # BENQI's open delegations stay to their end.
    assert closed.set_index(["run", "timestep"]).loc[(1, 10), "benqi_delegated_stake_navax"] >= 50_000 * AVAX


def test_delegations_naming_an_operator_that_is_not_named_or_benqi_rows_that_disagree_are_refused():
    with pytest.raises(ValueError, match="not a row of named_operators"):
        named(open_delegations=DELEGATIONS.assign(operator=[-1, 0, 2, 0])).initial_state()
    with pytest.raises(ValueError, match="exactly those flagged"):
        named(open_delegations=DELEGATIONS.assign(operator=[0, 0, 1, 0])).initial_state()


def events_inputs(tmp_path, monkeypatch, events=EVENTS, attributions=ATTRIBUTIONS):
    synthetic = {key: validators()[key] for key in ("moves", "first_commitments")}
    monkeypatch.setattr(variants, "switched_inputs", lambda events, switches: {"origin": events.origin, **events.state, **synthetic})
    periods, delegators = write_periods(tmp_path)
    tables = {**di.build(periods, delegators, ORIGIN), "terms": delegation_terms(periods, delegators, ORIGIN, di.BENQI_FUNDING, di.BENQI_EVIDENCE)}
    return VARIANTS["v0.8.1 events"].prepare(periods, ORIGIN, "synthetic", delegations=tables, operator_events=events,
                                             operator_attributions=attributions).inputs


def other_operator(evidence_at: str) -> tuple[list[dict], list[dict]]:
    """An identity event naming avax1other, which funds D1 to D3, and a BENQI shutdown on 5 March 2024, both with
    evidence at ``evidence_at``."""
    attribution = dict(ATTRIBUTIONS[0], attribution_id="OA99", subject="avax1other", subject_kind="funding-address",
                       name="Operator X", replaces=None)
    identity = dict(EVENTS[6], event_id="NE99", operator="Operator X", attributions=["OA99"], subject="avax1other",
                    happened_at="2023-01-01", evidence_public_at=evidence_at)
    shutdown = dict(EVENTS[5], event_id="NE98", kind="shutdown", happened_at="2024-03-05", evidence_public_at=evidence_at)
    return [identity, shutdown], [attribution]


def same_inputs(a: dict, b: dict) -> bool:
    """Every input table equal, and every other input with the same settings."""
    if a.keys() != b.keys():
        return False
    for name, value in a.items():
        if isinstance(value, pd.DataFrame):
            if not value.equals(b[name]):
                return False
        elif DelegatedLifecycle(**{name: value}).specification() != DelegatedLifecycle(**{name: b[name]}).specification():
            return False
    return True


def events_run(inputs, runs=2):
    return wide(run(VARIANTS["v0.8.1 events"].simulation(Prepared(inputs), seed=3, timesteps=10, runs=runs)))


def test_an_event_dated_after_the_origin_changes_nothing(tmp_path, monkeypatch):
    base = events_inputs(tmp_path, monkeypatch)
    # The synthetic origin, 1 March 2024, sees three named operators, and BENQI's key funds D4.
    assert base["named_operators"]["operator"].tolist() == ["BENQI", "GoGoPool (Hypha)", HOLDER_NAME]
    assert base["open_delegations"]["operator"].tolist() == [-1, 0] and base["scheduled_delegations"]["operator"].tolist() == [-1, -1]
    # Public just after the origin's last instant, on the origin day as a date alone, or a year later.
    for evidence in ("2024-03-02T00:00:00Z", "2024-03-01", "2025-06-01"):
        events, attributions = other_operator(evidence)
        later = events_inputs(tmp_path, monkeypatch, EVENTS + events, ATTRIBUTIONS + attributions)
        assert same_inputs(base, later), evidence
        pd.testing.assert_frame_equal(events_run(base), events_run(later))
    # The same events public before D1 to D3 were accepted name their funder's delegations and close BENQI from day 4.
    events, attributions = other_operator("2024-01-15T00:00:00Z")
    sooner = events_inputs(tmp_path, monkeypatch, EVENTS + events, ATTRIBUTIONS + attributions)
    table = sooner["named_operators"].set_index("operator")
    assert table.loc["BENQI", "closes_day"] == 4 and "Operator X" in table.index
    x = list(table.index).index("Operator X")
    assert sooner["open_delegations"]["operator"].tolist() == [x, 0] and sooner["scheduled_delegations"]["operator"].tolist() == [x, x]
    simulated = events_run(sooner, runs=1)
    assert simulated.loc[(1, 0), "operator_x_delegated_stake_navax"] == 1_000 * AVAX
    assert simulated.loc[(1, 7), "operator_x_delegated_stake_navax"] == 11_000 * AVAX


def test_the_events_variant_refuses_tables_that_set_benqi_apart_by_another_rule(tmp_path, monkeypatch):
    # BENQI named only from 20 February 2024 would not own D4, accepted on 15 February, which the tables flag as BENQI's.
    moved = [dict(event, evidence_public_at="2024-02-20T00:00:00Z") if event["event_id"] == "NE6" else event for event in EVENTS]
    with pytest.raises(ValueError, match="different delegations apart as BENQI's"):
        events_inputs(tmp_path, monkeypatch, moved)
    with pytest.raises(ValueError, match="with starts"):
        VARIANTS["v0.8.1 events"].prepare("periods", ORIGIN, "synthetic", delegations={"open": pd.DataFrame()})


def holder_replacement(evidence_at: str | None, captured_on: str) -> tuple[list[dict], list[dict]]:
    """A row that replaces the genesis holder's attribution, captured on ``captured_on``, and an identity event citing it
    with evidence at ``evidence_at``, or none."""
    old = next(row for row in ATTRIBUTIONS if row["attribution_id"] == "OA5")
    new = dict(old, attribution_id="OA99", captured_on=captured_on, replaces="OA5")
    if evidence_at is None:
        return EVENTS, ATTRIBUTIONS + [new]
    event = dict(next(e for e in EVENTS if e["event_id"] == "NE8"), event_id="NE99", attributions=["OA99"],
                 happened_at=evidence_at[:10], evidence_public_at=evidence_at)
    return EVENTS + [event], ATTRIBUTIONS + [new]


def test_a_replacement_applies_only_from_when_the_replacing_row_was_public():
    events, attributions = holder_replacement("2026-10-01T00:00:00Z", "2026-10-01")
    past = date(2024, 3, 1)
    assert named_at(past, events, attributions).operators.equals(named_at(past).operators)
    assert named_at(past, events, attributions).addresses.equals(named_at(past).addresses)
    # From the replacing row's evidence, the replaced row names nothing, and the holder is named from that instant.
    later = named_at(date(2026, 10, 1), events, attributions).addresses.set_index("address")
    assert later.loc[HOLDER, "named_from"] == pd.Timestamp("2026-10-01 00:00:00")
    # A replacing row that no event cites is public from the end of the day it was captured.
    events, attributions = holder_replacement(None, "2026-10-01")
    assert named_at(date(2026, 10, 1), events, attributions).row(HOLDER_NAME) >= 0
    assert named_at(date(2026, 10, 2), events, attributions).row(HOLDER_NAME) == -1


def test_acceptance_times_with_an_offset_are_compared_in_utc():
    named = named_at(date(2025, 10, 1))
    funding = pd.Series([BENQI_KEY])
    # 13:22:21 at UTC+2 is 11:22:21 UTC, before BENQI's naming at 12:22:21 UTC. 10:22:21 at UTC-2 is that instant.
    assert owners(funding, pd.Series(pd.to_datetime(["2022-01-26 13:22:21+02:00"])), named).tolist() == [-1]
    assert owners(funding, pd.Series(pd.to_datetime(["2022-01-26 10:22:21-02:00"])), named).tolist() == [named.row("BENQI")]


def test_an_operator_key_whose_state_variable_already_exists_is_refused():
    with pytest.raises(ValueError, match="state variable"):
        named(named_operators=NAMED.assign(key=["benqi", "active"])).initial_state()
    with pytest.raises(ValueError, match="state variable"):
        named(named_operators=NAMED.assign(key=["benqi_main", "benqi"])).state_variables()


def test_a_fractional_operator_row_or_closing_day_is_refused():
    with pytest.raises(ValueError, match="whole"):
        named(open_delegations=OWNED.assign(operator=[-1, 0, 1.5, 0])).initial_state()
    with pytest.raises(ValueError, match="whole"):
        run(named(delegation_flow=flowing(), named_operators=NAMED.assign(closes_day=[5.5, np.nan]), timesteps=3, runs=1))


def new_owned(state, row) -> bool:
    return bool(((state["delegation_days_left"] == state["delegation_days"]) & (state["delegation_operator"] == row)).any())


def test_a_named_operator_other_than_benqi_owns_the_new_delegations_that_take_its_terms_and_makes_none_from_its_closing_day():
    # The holder, row 1, owned two of the year's other delegations, so it owns the new ones that take their terms.
    owned_terms = TERMS.assign(operator=[1, 1, -1, -1, 0, 0])
    flow = flowing(mean=10.0, share=0.3)
    open_ = final_states(named(delegation_flow=flow, delegation_terms=owned_terms))
    closed = final_states(named(delegation_flow=flow, delegation_terms=owned_terms, named_operators=NAMED.assign(closes_day=[np.nan, 6.0])))
    assert any(new_owned(s, 1) for _, s in open_[open_["timestep"] >= 6].iterrows())
    for (_, a), (_, b) in zip(open_.iterrows(), closed.iterrows()):
        assert b["holder_delegated_stake_navax"] == int(b["delegation_stakes"][b["delegation_operator"] == 1].sum())
        if b["timestep"] < 6:
            for name in ("delegation_stakes", "delegation_validator", "delegation_operator", "supply_navax"):
                assert np.array_equal(a[name], b[name])
        else:
            assert not new_owned(b, 1)
    assert any(new_owned(s, 1) for _, s in closed[(closed["timestep"] >= 1) & (closed["timestep"] < 6)].iterrows())
    # BENQI does not close, so its new delegations go on.
    assert any(new_owned(s, 0) for _, s in closed[closed["timestep"] >= 6].iterrows())


def test_the_events_variant_gives_each_delegation_term_its_owner(tmp_path, monkeypatch):
    events, attributions = other_operator("2024-01-15T00:00:00Z")
    inputs = events_inputs(tmp_path, monkeypatch, EVENTS + events, ATTRIBUTIONS + attributions)
    x = list(inputs["named_operators"]["operator"]).index("Operator X")
    # The year's starts are D1, funded by avax1other, and D4, funded by BENQI's key.
    assert inputs["delegation_terms"]["operator"].tolist() == [x, 0]
    misaligned = {"terms": lambda tables: tables["terms"].iloc[:1]}
    with pytest.raises(ValueError, match="row for row"):
        events_inputs_with(tmp_path, monkeypatch, misaligned)


def events_inputs_with(tmp_path, monkeypatch, changes):
    synthetic = {key: validators()[key] for key in ("moves", "first_commitments")}
    monkeypatch.setattr(variants, "switched_inputs", lambda events, switches: {"origin": events.origin, **events.state, **synthetic})
    periods, delegators = write_periods(tmp_path)
    tables = {**di.build(periods, delegators, ORIGIN), "terms": delegation_terms(periods, delegators, ORIGIN, di.BENQI_FUNDING, di.BENQI_EVIDENCE)}
    tables |= {name: change(tables) for name, change in changes.items()}
    return VARIANTS["v0.8.1 events"].prepare(periods, ORIGIN, "synthetic", delegations=tables).inputs
