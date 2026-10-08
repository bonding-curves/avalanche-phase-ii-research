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
