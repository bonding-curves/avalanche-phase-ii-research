"""The v0.8.1 candidate: the delegation stage on the released v0.8.0 base, and the frozen delegation laws it runs under.

The laws are built one block each: the flow at the 28-day mean, the ordinary choice in proportion to own stake plus
open delegated stake, BENQI's two-stage choice over its prior-use set, and the containment choice set. A test per law
checks the block alone, then the stage, then the variant on the pinned staking periods when a built run is present.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest
from scipy import special
from test_delegated_lifecycle import (
    DELEGATIONS,
    TERMS,
    VALIDATOR_VARIABLES,
    final_states,
    validators,
    wide,
)

from avalanche_research import datasets
from avalanche_research.catalog import DataError
from avalanche_research.core.catalog import canonical_bytes, sha256
from avalanche_research.datasets import pins
from avalanche_research.datasets.derived import delegation_inputs as di
from avalanche_research.experiments.v081_inputs import (
    DELEGATORS_DATASET,
    PERIODS_DATASET,
    candidate_tables,
    pinned_inputs,
    prepare_candidate,
)
from avalanche_research.model import streams
from avalanche_research.model.delegated_lifecycle import (
    CONTAINMENT,
    DelegatedLifecycle,
    DelegatedStakeLifecycle,
    DelegationMixin,
    benqi_choices,
    delegation_inputs,
    recent_flow,
)
from avalanche_research.model.delegation_blocks import (
    BenqiAllocation,
    BenqiTwoStage,
    DelegationFlow,
    DelegatorChoice,
    ProportionalChoice,
)
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_blocks import AVAX, Arrivals, RenewalLogit
from avalanche_research.model.fitted_lifecycle import FittedLifecycle, training_events
from avalanche_research.model.parts.delegations import (
    DelegationSetup,
    load_profile,
    place_contained,
)
from avalanche_research.model.parts.operator_types import (
    ClassShift,
    class_weights,
    posterior_lookup,
)
from avalanche_research.model.parts.renewal import renewal_design
from avalanche_research.model.stake_lifecycle import StakeLifecycle
from avalanche_research.model.variants import VARIANTS, Prepared
from avalanche_research.views.model_structure import tiny_stake_lifecycle

COLUMNS = ["run", "timestep", "time", "variable", "value", "yield_gap_pp", "model_version"]


def pick(table, variables=VALIDATOR_VARIABLES):
    return table[table["variable"].isin(variables)][COLUMNS].sort_values(COLUMNS[:5]).reset_index(drop=True)


def law_blocks(new_share=0.5):
    return {"placement_rule": CONTAINMENT, "delegator_choice": ProportionalChoice(),
            "benqi_allocation": BenqiTwoStage(new_share=new_share), "placement_batch": 1}


def contained(**overrides):
    base = {"open_delegations": DELEGATIONS, "delegation_terms": TERMS, "benqi_validators": pd.DataFrame({"validator": [2, 4]}), **law_blocks()}
    return DelegatedLifecycle(**validators(**{**base, **overrides}))


# V1: the delegation stage on the released base.

def test_the_two_delegated_models_share_the_mixin_and_differ_only_in_their_base():
    assert issubclass(DelegatedLifecycle, DelegationMixin) and issubclass(DelegatedLifecycle, FittedLifecycle)
    assert issubclass(DelegatedStakeLifecycle, DelegationMixin) and issubclass(DelegatedStakeLifecycle, StakeLifecycle)
    assert VARIANTS["v0.8.1 candidate"].model is DelegatedStakeLifecycle
    assert VARIANTS["v0.8.0"].model is StakeLifecycle


def tiny_inputs(**overrides) -> dict:
    model = tiny_stake_lifecycle()
    values = {k: v for k, v in model.param.values().items() if k != "name"}
    return {**values, "timesteps": 30, "runs": 2, **overrides}


def test_with_no_new_delegations_the_stake_lifecycle_tables_are_identical_on_the_released_base():
    inputs = tiny_inputs()
    base = run(StakeLifecycle(**inputs))
    opened = pd.DataFrame({"validator": [2, 3], "stakes": [500 * AVAX, 3_000 * AVAX], "days_left": [4, 9], "benqi": [False, True]})
    ours = run(DelegatedStakeLifecycle(**inputs, open_delegations=opened, benqi_validators=pd.DataFrame({"validator": [3]})))
    pd.testing.assert_frame_equal(pick(ours), pick(base))
    table = wide(ours)
    assert (table["delegator_issued_navax"] == 0).all() and table.loc[(1, 0), "active_delegations"] == 2
    # The delegated model keeps the stake continuation of its base.
    assert "stake_continuation" in dict(DelegatedStakeLifecycle(**inputs).stages)["continuation"].__name__
    assert [name for name, _ in DelegatedStakeLifecycle(**inputs).stages] == [*(n for n, _ in FittedLifecycle.stages), "delegations"]


def test_the_specification_names_the_released_base_and_omits_the_new_settings_at_their_defaults():
    inputs = tiny_inputs()
    spec = DelegatedStakeLifecycle(**inputs).specification()
    assert spec["model"].endswith("DelegatedStakeLifecycle") and "stake_choice" in spec
    assert "placement_rule" not in spec and "operator_types" not in spec and "type_posteriors" not in spec["inputs_sha256"]
    with_laws = DelegatedStakeLifecycle(**inputs, **law_blocks(), operator_types=ClassShift()).specification()
    assert with_laws["placement_rule"] == CONTAINMENT and with_laws["operator_types"]["shifts"] == [0.0]


def test_the_containment_rule_needs_the_adopted_blocks():
    with pytest.raises(ValueError, match="containment"):
        DelegatedLifecycle(**validators(placement_rule=CONTAINMENT))
    with pytest.raises(ValueError, match="containment"):
        DelegatedLifecycle(**validators(placement_rule=CONTAINMENT, delegator_choice=ProportionalChoice(), benqi_allocation=BenqiAllocation()))


# VD1: the flow is the 28-day rate, read as an observed moment with no fit.

def test_the_recent_flow_is_the_mean_of_the_28_days_before_the_origin_split_at_that_windows_shares():
    origin = date(2024, 3, 6)
    days = pd.date_range(end=pd.Timestamp(origin), periods=60, freq="D")
    rows = []
    for i, day in enumerate(days):
        # Older days carry a large count the 28-day window must ignore. A day with no BENQI row counts zero for BENQI.
        rows.append({"date_utc": day, "benqi": False, "started": 1_000 if i < 32 else 3})
        if i >= 32 and i % 2 == 0:
            rows.append({"date_utc": day, "benqi": True, "started": 7})
    flow = recent_flow(pd.DataFrame(rows), origin)
    benqi_total, other_total = 7 * 14, 3 * 28
    assert flow.mean_per_day == pytest.approx((benqi_total + other_total) / 28)
    assert flow.benqi_share == pytest.approx(benqi_total / (benqi_total + other_total))
    sources = flow.sources()
    assert {sources["mean_per_day"]["source"], sources["benqi_share"]["source"]} == {"observed moment"}
    assert "28 days to 2024-03-06" in sources["mean_per_day"]["evidence"]
    # The annual flow of the same rows differs, so the two blocks are not the same reading.
    from avalanche_research.model.delegated_lifecycle import historical_flow
    assert historical_flow(pd.DataFrame(rows), origin).mean_per_day != flow.mean_per_day
    with pytest.raises(ValueError, match="whole numbers"):
        recent_flow(pd.DataFrame(rows).assign(started=lambda t: t["started"] + 0.5), origin)


# VD3 by VX6 and VX1: the ordinary choice in proportion to own stake plus open delegated stake.

def test_the_proportional_choice_weights_each_candidate_by_own_stake_plus_open_delegated_stake():
    block = ProportionalChoice()
    inputs = {"own_stake_navax": np.array([2_000, 10_000, 500_000]) * AVAX, "open_delegated_navax": np.array([0, 40_000, 0]) * AVAX}
    weights = np.array([2_000, 50_000, 500_000], dtype=float)
    assert block.probabilities(inputs) == pytest.approx(weights / weights.sum())
    # Inversion of a grid of uniforms reproduces the probabilities, and a candidate with no open delegations keeps a positive weight.
    picks = np.array([block.choose_from_uniform(inputs, u) for u in np.linspace(0.0005, 0.9995, 2_000)])
    assert np.bincount(picks, minlength=3) / 2_000 == pytest.approx(weights / weights.sum(), abs=0.002)
    chosen = np.array([True, False, False])
    assert block.log_prob(inputs, chosen) == pytest.approx(np.log(2_000 / 552_000))
    rng = np.random.default_rng(1)
    sets = np.repeat(np.arange(500), 3)
    many = {"choice_set": sets, "own_stake_navax": np.tile(inputs["own_stake_navax"], 500), "open_delegated_navax": np.tile(inputs["open_delegated_navax"], 500)}
    drawn = block.sample(many, rng)
    assert np.bincount(sets, weights=drawn).tolist() == [1.0] * 500
    assert drawn.reshape(500, 3).mean(axis=0) == pytest.approx(weights / weights.sum(), abs=0.05)
    with pytest.raises(ValueError, match="positive own stake"):
        block.probabilities({"own_stake_navax": np.array([0, 1]), "open_delegated_navax": np.array([1, 1])})
    assert block.sources() == {}, "the proportional rule has no parameter"


def test_the_conditional_logit_stays_in_the_code_and_out_of_the_candidate():
    assert DelegatorChoice.terms == ("fee", "log_capacity")
    assert isinstance(DelegatedLifecycle(**validators()).delegator_choice, DelegatorChoice)
    assert isinstance(contained().delegator_choice, ProportionalChoice)


# VD4 by VX2: BENQI's two-stage choice.

BENQI_INPUTS = {
    "own_stake_navax": np.array([2_000, 2_000, 10_000, 10_000]) * AVAX,
    "open_delegated_navax": np.array([0, 6_000, 0, 30_000]) * AVAX,
    "prior_use": np.array([False, False, True, True]),
    "benqi_stake_navax": np.array([0, 0, 100_000, 300_000]) * AVAX,
}


def test_benqis_choice_goes_new_with_its_share_and_repeats_in_proportion_to_its_stake_on_each_period():
    block = BenqiTwoStage(new_share=0.2)
    p = block.probabilities(BENQI_INPUTS)
    assert p[:2] == pytest.approx(0.2 * np.array([2_000, 8_000]) / 10_000)
    assert p[2:] == pytest.approx(0.8 * np.array([100_000, 300_000]) / 400_000)
    picks = np.array([block.choose_from_uniform(BENQI_INPUTS, u) for u in np.linspace(0.00025, 0.99975, 4_000)])
    assert np.bincount(picks, minlength=4) / 4_000 == pytest.approx(p, abs=0.002)
    assert block.log_prob(BENQI_INPUTS, np.array([False, False, False, True])) == pytest.approx(np.log(0.8 * 0.75))


def test_an_empty_stage_passes_its_whole_probability_to_the_other():
    block = BenqiTwoStage(new_share=0.2)
    only_new = {k: v[:2] for k, v in BENQI_INPUTS.items()}
    assert block.probabilities(only_new) == pytest.approx(np.array([2_000, 8_000]) / 10_000)
    only_repeat = {k: v[2:] for k, v in BENQI_INPUTS.items()}
    assert block.probabilities(only_repeat) == pytest.approx(np.array([100_000, 300_000]) / 400_000)
    assert block.choose_from_uniform(only_new, 0.95) == 1 and block.choose_from_uniform(only_repeat, 0.1) == 0
    with pytest.raises(ValueError, match="at least one"):
        block.probabilities({k: v[:0] for k, v in BENQI_INPUTS.items()})


def test_benqis_new_share_is_read_from_its_choices_as_an_observed_moment():
    block = BenqiTwoStage.observed(np.array([True, False, False, False]), "synthetic")
    assert block.new_share == 0.25 and block.sources()["new_share"]["source"] == "observed moment"
    assert "1 of 4" in block.sources()["new_share"]["evidence"]
    assert BenqiTwoStage().sources()["new_share"]["source"] == "assumed"


# VD2: the containment choice set.

def room_setup(batch=1):
    return DelegationSetup(flow=DelegationFlow(), choice=ProportionalChoice(), allocation=BenqiTwoStage(new_share=0.5), fee_shares=20_000,
                           multiplier=4, benqi_keys=np.zeros(0, dtype=np.int64), terms={}, batch=batch, rule=CONTAINMENT)


def test_the_load_profile_stacks_every_covering_delegation_by_day_ahead():
    load = load_profile(2, 6, rows=np.array([0, 0, 1, -1]), starts=np.array([0, 3, 1, 0]), ends=np.array([2, 5, 9, 4]), stakes=np.array([10, 20, 30, 99]))
    assert load.tolist() == [[10, 10, 0, 20, 20, 0], [0, 30, 30, 30, 30, 30]]


def test_room_covers_the_stake_after_the_largest_overlapping_load_not_the_sum():
    # One validator with 8,000 AVAX of room. An open delegation of 3,000 covers the first five days and a scheduled one of
    # 4,000 the days 10 to 19. A 4,000 AVAX delegation for 14 days fits after the largest load (4,000), not after the sum.
    load = load_profile(1, 30, rows=np.array([0, 0]), starts=np.array([0, 10]), ends=np.array([5, 20]), stakes=np.array([3_000, 4_000]) * AVAX)
    room_limit, own, days_left = np.array([8_000 * AVAX]), np.array([2_000 * AVAX]), np.array([30])
    chosen = place_contained(np.array([4_000 * AVAX]), np.array([14]), np.array([False]), np.array([0.5]), np.array([0.5]), load.copy(),
                             room_limit, days_left, own, np.zeros(1, bool), np.zeros(1, dtype=np.int64), room_setup())
    assert chosen.tolist() == [0]
    # 4,001 AVAX does not fit, and a delegation of 4,000 for 9 days, past no scheduled load, leaves room for 5,000 more.
    chosen = place_contained(np.array([4_000 * AVAX + 1]), np.array([14]), np.array([False]), np.array([0.5]), np.array([0.5]), load.copy(),
                             room_limit, days_left, own, np.zeros(1, bool), np.zeros(1, dtype=np.int64), room_setup())
    assert chosen.tolist() == [-1]
    chosen = place_contained(np.array([5_000 * AVAX]), np.array([9]), np.array([False]), np.array([0.5]), np.array([0.5]), load.copy(),
                             room_limit, days_left, own, np.zeros(1, bool), np.zeros(1, dtype=np.int64), room_setup())
    assert chosen.tolist() == [0]


def test_the_validators_period_must_contain_the_delegations_whole_interval():
    load = np.zeros((2, 40), dtype=np.int64)
    room_limit, own, days_left = np.array([8_000, 8_000]) * AVAX, np.array([2_000, 2_000]) * AVAX, np.array([13, 14])
    chosen = place_contained(np.array([100, 100]) * AVAX, np.array([14, 14]), np.array([False, False]), np.array([0.1, 0.9]), np.array([0.5, 0.5]),
                             load, room_limit, days_left, own, np.zeros(2, bool), np.zeros(2, dtype=np.int64), room_setup())
    assert chosen.tolist() == [1, 1], "only the validator with 14 days left can hold a 14-day delegation"


def test_earlier_accepted_delegations_of_the_day_count_and_same_batch_peers_are_reserved_pessimistically():
    # One validator with 5,000 AVAX of room and two delegations of 3,000 AVAX. One by one, the first takes the room and
    # the second finds none. In one batch, each counts the other against the room, so neither fits.
    args = (np.array([3_000, 3_000]) * AVAX, np.array([14, 14]), np.array([False, False]), np.array([0.5, 0.5]), np.array([0.5, 0.5]))
    rest = (np.array([5_000 * AVAX]), np.array([30]), np.array([2_000 * AVAX]), np.zeros(1, bool), np.zeros(1, dtype=np.int64))
    load = np.zeros((1, 40), dtype=np.int64)
    assert place_contained(*args, load, *rest, room_setup(batch=1)).tolist() == [0, -1]
    assert load[0, :14].tolist() == [3_000 * AVAX] * 14 and load[0, 14] == 0
    load = np.zeros((1, 40), dtype=np.int64)
    assert place_contained(*args, load, *rest, room_setup(batch=2)).tolist() == [-1, -1]
    # Two of 2,500 fit together either way.
    small = (np.array([2_500, 2_500]) * AVAX, *args[1:])
    assert place_contained(*small, np.zeros((1, 40), dtype=np.int64), *rest, room_setup(batch=2)).tolist() == [0, 0]


def test_benqis_placement_grows_its_prior_use_set_and_its_stake_there():
    load = np.zeros((2, 40), dtype=np.int64)
    prior_use, prior_stakes = np.array([False, True]), np.array([0, 1_000 * AVAX])
    # With new_share 0, BENQI repeats on validator 1; a second BENQI delegation with new_share 1 must go to validator 0.
    setup = room_setup()
    chosen = place_contained(np.array([200 * AVAX]), np.array([14]), np.array([True]), np.array([0.5]), np.array([0.99]), load,
                             np.array([8_000, 8_000]) * AVAX, np.array([30, 30]), np.array([2_000, 2_000]) * AVAX, prior_use, prior_stakes,
                             DelegationSetup(**{**setup.__dict__, "allocation": BenqiTwoStage(new_share=0.0)}))
    assert chosen.tolist() == [1] and prior_stakes.tolist() == [0, 1_200 * AVAX]
    chosen = place_contained(np.array([300 * AVAX]), np.array([14]), np.array([True]), np.array([0.5]), np.array([0.01]), load,
                             np.array([8_000, 8_000]) * AVAX, np.array([30, 30]), np.array([2_000, 2_000]) * AVAX, prior_use, prior_stakes,
                             DelegationSetup(**{**setup.__dict__, "allocation": BenqiTwoStage(new_share=1.0)}))
    assert chosen.tolist() == [0] and prior_use.tolist() == [True, True] and prior_stakes.tolist() == [300 * AVAX, 1_200 * AVAX]


STATIC = {
    "initial": pd.DataFrame({"stakes": np.array([2, 2, 10]) * 1_000 * AVAX, "days_left": [30, 10, 60], "done": [1, 1, 1],
                             "after_return": [False] * 3, "days": [60, 60, 120], "handed_on": [False] * 3}),
    "arrivals": Arrivals(mean_per_day=0.0), "renewal": RenewalLogit(intercept=20.0), "timesteps": 8, "runs": 1,
    "open_delegations": pd.DataFrame({"validator": [0], "stakes": [1_000 * AVAX], "days_left": [5], "benqi": [False]}),
    "scheduled_delegations": pd.DataFrame({"validator": [0], "validator_scheduled": [False], "start_day": [4], "stakes": [6_000 * AVAX], "days": [10], "benqi": [False]}),
    "delegation_terms": pd.DataFrame({"stake_navax": [5_000 * AVAX], "days": [14], "benqi": [False]}),
    "benqi_validators": pd.DataFrame({"validator": [2]}),
    "delegation_flow": DelegationFlow(mean_per_day=3.0, benqi_share=0.0),
}


def test_in_the_stage_a_delegation_runs_its_requested_days_on_a_validator_whose_period_contains_them():
    model = contained(**STATIC)
    states = final_states(model)
    keys = states.iloc[0]["node_key"]
    for _, state in states.iterrows():
        # The new delegations are the 5,000 AVAX terms; the 6,000 AVAX scheduled one also starts whole on its day.
        new = (state["delegation_days_left"] == state["delegation_days"]) & (state["delegation_stakes"] == 5_000 * AVAX)
        assert (state["delegation_days"][new] == 14).all(), "the requested days are never cut"
        # Validator 1 has 10 days left, too short. Validator 0 carries 7,000 AVAX of overlapping load against 8,000 of room.
        assert set(state["delegation_validator"][new].tolist()) <= {keys[2]}
    assert states["unplaced_delegations"].sum() > 0, "validator 2's 40,000 AVAX of room holds eight 5,000 AVAX delegations"
    placed = sum(int(((s["delegation_days_left"] == s["delegation_days"]) & (s["delegation_stakes"] == 5_000 * AVAX)).sum()) for _, s in states.iloc[1:].iterrows())
    assert placed == 8
    # The old rule cuts a 30-day delegation to a validator's 20 days left; the containment rule never does.
    shorter = {**STATIC, "initial": STATIC["initial"].assign(days_left=[30, 10, 20]),
               "delegation_terms": STATIC["delegation_terms"].assign(days=[30])}
    old = final_states(DelegatedLifecycle(**validators(**shorter)))
    assert any(((s["delegation_stakes"] == 5_000 * AVAX) & (s["delegation_days"] < 30)).any() for _, s in old.iterrows())
    new_rule = final_states(contained(**shorter))
    assert all(set(s["delegation_days"].tolist()) <= {5, 10, 30} for _, s in new_rule.iterrows())
    assert new_rule["unplaced_delegations"].sum() == sum(STATIC["delegation_flow"].count_from_uniform(float(u))
                                                         for u in [streams.Streams(7, 1).uniforms("delegations", t)[0] for t in range(8)])


def test_the_candidate_stage_draws_only_from_the_keyed_streams(monkeypatch):
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
    run(contained(delegation_flow=DelegationFlow(mean_per_day=6.0, benqi_share=0.4), timesteps=5, runs=1))
    assert {"delegations", "delegation_benqi", "delegation_terms", "delegator_choice", "benqi_allocation"} <= set(used) <= set(streams.PURPOSES)


def test_the_candidate_stage_keeps_the_invariants_and_replays_from_the_seed():
    model = contained(delegation_flow=DelegationFlow(mean_per_day=25.0, benqi_share=0.3), timesteps=12, runs=2,
                      delegation_terms=TERMS.assign(stake_navax=np.array([3_000, 6_000, 8_000, 25, 5_000, 25]) * AVAX))
    first, again = wide(run(model)), wide(run(model))
    pd.testing.assert_frame_equal(first, again)
    assert (first["issued_navax"] == first["validator_issued_navax"] + first["delegator_issued_navax"]).all()
    assert first["unplaced_delegations"].sum() > 0 and first["delegator_issued_navax"].sum() > 0


# The prior-use set and BENQI's new share from the tables.

ORIGIN = date(2024, 3, 1)
PERIODS = [
    # (hash, role, node, validator hash, accepted, start, end, stake AVAX, funding address)
    ("V1", "validator", "A", None, "2023-12-01 00:00", "2023-12-01 00:00", "2024-06-01 00:00", 2_000, None),
    ("V2", "validator", "B", None, "2024-01-01 00:00", "2024-01-01 00:00", "2024-07-01 00:00", 2_000, None),
    ("V0", "validator", "Z", None, "2022-12-01 00:00", "2022-12-01 00:00", "2023-11-01 00:00", 2_000, None),
    ("D1", "delegator", "A", "V1", "2024-02-01 00:00", "2024-02-01 00:00", "2024-04-15 00:00", 1_000, "avax1other"),
    # BENQI's: two on V1, the second a repeat, and one on V2 open at the origin. One on the ended V0 is on no candidate.
    ("D2", "delegator", "A", "V1", "2023-12-10 00:00", "2023-12-10 00:00", "2024-01-10 00:00", 300, di.BENQI_FUNDING),
    ("D3", "delegator", "A", "V1", "2024-01-20 00:00", "2024-01-20 00:00", "2024-02-20 00:00", 500, di.BENQI_FUNDING),
    ("D4", "delegator", "B", "V2", "2024-02-15 00:00", "2024-02-15 00:00", "2024-05-15 00:00", 8_000, di.BENQI_FUNDING),
    ("D5", "delegator", "Z", "V0", "2023-06-01 00:00", "2023-06-01 00:00", "2023-07-01 00:00", 700, di.BENQI_FUNDING),
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


def test_benqis_choices_are_new_when_no_earlier_benqi_delegation_sat_on_the_same_validator_period(tmp_path):
    periods, delegators = write_periods(tmp_path)
    choices = benqi_choices(periods, delegators, ORIGIN, di.BENQI_FUNDING, di.BENQI_EVIDENCE)
    assert choices["transaction_hash"].tolist() == ["D5", "D2", "D3", "D4"]
    assert choices["new"].tolist() == [True, True, False, True]
    assert BenqiTwoStage.observed(choices["new"].to_numpy(), "synthetic").new_share == 0.75


def test_the_prior_use_set_holds_every_candidate_period_benqi_used_in_the_year_with_its_stake_and_last_day(tmp_path):
    periods, delegators = write_periods(tmp_path)
    tables = di.build(periods, delegators, ORIGIN)
    state = training_events(periods, ORIGIN, "synthetic").state
    plain = delegation_inputs(tables, periods, ORIGIN, state)["benqi_validators"]
    assert plain.values.tolist() == [[1, False]], "the stub's set holds only the validator with a BENQI delegation open at the origin"
    prior = delegation_inputs(tables, periods, ORIGIN, state, prior_use=True)["benqi_validators"]
    # V1 (row 0): D2 and D3, 800 AVAX, the last open on 20 February, ten days before the origin. V2 (row 1): D4, open 75 days more.
    assert prior.columns.tolist() == ["validator", "validator_scheduled", "benqi_stake_navax", "benqi_until_day"]
    assert prior.values.tolist() == [[0, False, 800 * AVAX, -10], [1, False, 8_000 * AVAX, 75]]
    model = DelegatedLifecycle(**validators(initial=state["initial"], benqi_validators=prior, origin=ORIGIN))
    use = model.initial_state()
    assert use["benqi_use_navax"].tolist() == [800 * AVAX, 8_000 * AVAX] and use["benqi_use_until"].tolist() == [-10, 75]
    with pytest.raises(ValueError, match="starts"):
        delegation_inputs({k: v for k, v in tables.items() if k != "starts"}, periods, ORIGIN, state, prior_use=True)


def test_the_candidate_variant_needs_every_delegation_table(tmp_path):
    with pytest.raises(ValueError, match="benqi_choices"):
        VARIANTS["v0.8.1 candidate"].prepare("periods", ORIGIN, "synthetic", delegations={"open": pd.DataFrame()})


# V8: the class-shift interface on the renewal logit, K = 1 by default.

def test_one_class_with_no_shift_leaves_every_table_unchanged():
    inputs = tiny_inputs(timesteps=40, runs=3)
    opened = pd.DataFrame({"validator": [2, 3], "stakes": [500 * AVAX, 3_000 * AVAX], "days_left": [4, 9], "benqi": [False, True]})
    terms = pd.DataFrame({"stake_navax": [100 * AVAX, 25 * AVAX], "days": [14, 30], "benqi": [False, True]})
    shared = {**inputs, "open_delegations": opened, "benqi_validators": pd.DataFrame({"validator": [3]}), "delegation_terms": terms,
              "delegation_flow": DelegationFlow(mean_per_day=2.0, benqi_share=0.5), **law_blocks()}
    plain = run(DelegatedStakeLifecycle(**shared))
    typed = run(DelegatedStakeLifecycle(**shared, operator_types=ClassShift()))
    every = list(plain["variable"].unique())
    pd.testing.assert_frame_equal(pick(plain, every), pick(typed, every))
    assert DelegatedStakeLifecycle(**shared, operator_types=ClassShift()).specification() != DelegatedStakeLifecycle(**shared).specification()
    # A common shift moves renewals, as the released model's renewal shift would.
    shifted = run(DelegatedStakeLifecycle(**shared, operator_types=ClassShift(shifts=[-3.0])))
    assert not pick(shifted, ["active_validators"]).equals(pick(plain, ["active_validators"]))


def test_the_class_shifts_are_recovered_from_synthetic_endings_with_known_classes():
    rng = np.random.default_rng(11)
    n, truth = 60_000, np.array([-1.5, 0.0, 1.2])
    eta = rng.normal(0.8, 1.0, n)
    classes = rng.integers(0, 3, n)
    weights = np.eye(3)[classes]
    y = rng.random(n) < special.expit(eta + truth[classes])
    fitted = ClassShift.fit(eta, y, weights, "synthetic")
    assert np.asarray(fitted.shifts) == pytest.approx(truth, abs=0.08)
    assert fitted.sources()["shifts"]["source"] == "fitted" and fitted.classes == 3
    assert fitted.entrant_shares == pytest.approx(np.bincount(classes) / n, abs=0.01)
    assert fitted.log_prob({"eta": eta, "weights": weights}, y) > ClassShift(shifts=[0.0, 0.0, 0.0], entrant_shares=[1 / 3] * 3).log_prob({"eta": eta, "weights": weights}, y)
    # K = 1 fits one common shift the same way, and soft weights give a mixture probability.
    one = ClassShift.fit(eta, y, np.ones((n, 1)), "synthetic")
    assert one.classes == 1 and abs((y - special.expit(eta + one.shifts[0])).sum()) < 1e-6, "the common shift zeroes the score"
    soft = ClassShift(shifts=[-2.0, 2.0], entrant_shares=[0.5, 0.5])
    assert soft.probability(np.zeros(1), np.array([[0.5, 0.5]])) == pytest.approx([0.5 * special.expit(-2.0) + 0.5 * special.expit(2.0)])


def test_the_typed_stage_reads_each_nodes_posterior_and_defaults_to_the_entrant_shares():
    types = ClassShift(shifts=[-1.0, 1.0], entrant_shares=[0.25, 0.75])
    table = pd.DataFrame({"node_key": [7, 3], "w_0": [1.0, 0.2], "w_1": [0.0, 0.8]})
    lookup = posterior_lookup(table, types)
    assert lookup[0].tolist() == [3, 7]
    assert class_weights(np.array([3, 5, 7]), lookup, types).tolist() == [[0.2, 0.8], [0.25, 0.75], [1.0, 0.0]]
    with pytest.raises(ValueError, match="sum to one"):
        posterior_lookup(table.assign(w_1=[0.5, 0.5]), types)
    with pytest.raises(ValueError, match="one value per class"):
        ClassShift(shifts=[0.0, 1.0], entrant_shares=[1.0])
    with pytest.raises(ValueError, match="need operator_types"):
        DelegatedLifecycle(**validators(type_posteriors=table))
    # The shifted probability is the mixture of the base logit's log-odds and the class shifts.
    block = RenewalLogit(intercept=0.3)
    eta = renewal_design([1], [False], [30], [2_000 * AVAX]) @ block.coefficients()
    assert types.probability(eta, np.array([[0.2, 0.8]])) == pytest.approx([0.2 * special.expit(eta[0] - 1) + 0.8 * special.expit(eta[0] + 1)])


# The candidate on the pinned staking periods.

def built(dataset_id, run=None):
    try:
        return str(datasets.parquet_path(dataset_id, run))
    except (DataError, StopIteration, FileNotFoundError):
        pytest.skip(f"no built run of {dataset_id} in this checkout")


CANDIDATE_PIN = Path("data/pins/p9-model-v0.8.1.json")


def pinned_tables(origin):
    """The candidate's tables from its pin, never from the newest build. Skipped while the pin or its runs are absent."""
    try:
        inputs = pinned_inputs(CANDIDATE_PIN)
    except DataError as error:
        pytest.skip(f"the candidate's pin is not usable in this checkout: {error}")
    return str(inputs.periods), inputs.periods_run, candidate_tables(str(inputs.periods), str(inputs.delegators), origin)


def make_run(root: Path, run: str, dataset_id: str, built_at: str, status: str = "pass") -> Path:
    capture_dir, dataset_dir = root / run / "capture", root / run / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / "table.parquet"
    duckdb.connect().execute(f"COPY (SELECT '{run}' AS run) TO ? (FORMAT PARQUET)", [str(parquet)])
    capture_id = f"capture:test:{run}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({"capture_id": capture_id, "dataset_id": dataset_id, "completed_at": built_at}))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({"dataset_id": dataset_id, "source_capture_id": capture_id, "completed_at": built_at,
                                                              "summary": {"rows": 1}, "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}]}))
    (dataset_dir / "check.json").write_bytes(canonical_bytes({"status": status}))
    return parquet


def test_the_candidate_reads_the_pinned_runs_and_never_a_newer_build(tmp_path):
    root = tmp_path / "runs"
    pinned_periods = make_run(root, "periods-pinned", PERIODS_DATASET, "2026-09-30T00:00:00Z")
    make_run(root, "periods-newer", PERIODS_DATASET, "2026-10-14T00:00:00Z")
    pinned_delegators = make_run(root, "delegators-pinned", DELEGATORS_DATASET, "2026-09-30T00:00:00Z")
    newer = make_run(root, "delegators-newer", DELEGATORS_DATASET, "2026-10-14T00:00:00Z")
    pin = pins.pin("candidate", [PERIODS_DATASET, DELEGATORS_DATASET], {PERIODS_DATASET: "periods-pinned", DELEGATORS_DATASET: "delegators-pinned"},
                   root=root, directory=tmp_path / "pins")
    path = tmp_path / "pins" / "candidate.json"
    inputs = pinned_inputs(path, root)
    # The newest build of both datasets is the unpinned one, and neither is read.
    assert datasets.parquet_path(DELEGATORS_DATASET, root=root) == newer
    assert (inputs.periods, inputs.delegators) == (pinned_periods, pinned_delegators)
    assert (inputs.periods_run, inputs.delegators_run) == ("periods-pinned", "delegators-pinned")
    assert inputs.delegators_sha256 == pin["runs"][1]["sha256"] == sha256(pinned_delegators.read_bytes())
    # prepare_candidate reads the pinned files and no other: the one-column synthetic Parquet is refused by the first read.
    with pytest.raises(Exception, match="role|column|Binder"):
        prepare_candidate(path, ORIGIN, root=root)
    # A missing pin, a pin without the delegator stakes, and a pinned file that changed are each refused.
    with pytest.raises(DataError, match="missing"):
        pinned_inputs(tmp_path / "pins" / "absent.json", root)
    pins.pin("periods-only", [PERIODS_DATASET], {PERIODS_DATASET: "periods-pinned"}, root=root, directory=tmp_path / "pins")
    with pytest.raises(DataError, match="names no run of derived.seamed-delegator-stakes"):
        pinned_inputs(tmp_path / "pins" / "periods-only.json", root)
    pinned_delegators.write_bytes(pinned_delegators.read_bytes() + b"x")
    with pytest.raises(DataError, match="does not verify"):
        pinned_inputs(path, root)


def test_with_no_new_delegations_the_candidate_equals_variant_v080_exactly_at_a_pre_granite_origin():
    origin = date(2022, 10, 18)
    periods, run_name, tables = pinned_tables(origin)
    candidate, released = VARIANTS["v0.8.1 candidate"], VARIANTS["v0.8.0"]
    ours = candidate.prepare(periods, origin, run_name, draws=2, draw_seed=0, delegations=tables)
    theirs = released.prepare(periods, origin, run_name, draws=2, draw_seed=0)
    pd.testing.assert_frame_equal(ours.draws, theirs.draws)
    assert ours.tau == theirs.tau
    still = Prepared({**ours.inputs, "delegation_flow": DelegationFlow()}, ours.draws, ours.tau, ours.tau_source)
    mine = run(candidate.simulation(still, seed=0, timesteps=20, runs=2, draws=still.draws))
    base = run(released.simulation(theirs, seed=0, timesteps=20, runs=2, draws=theirs.draws))
    pd.testing.assert_frame_equal(pick(mine), pick(base))
    table = wide(mine)
    assert table.loc[(1, 0), "active_delegations"] == len(tables["open"]) and (table["delegator_issued_navax"] == 0).all()
    # Under the laws the candidate builds and runs at the same origin.
    flowing = candidate.simulation(ours, seed=0, timesteps=3, runs=1, draws=ours.draws)
    assert flowing.placement_rule == CONTAINMENT and flowing.delegation_flow.sources()["mean_per_day"]["source"] == "observed moment"
    assert isinstance(flowing.delegator_choice, ProportionalChoice) and isinstance(flowing.benqi_allocation, BenqiTwoStage)
    assert flowing.operator_types.classes == 1 and len(flowing.named_operators) >= 1
    moved = wide(run(flowing))
    assert moved["delegator_issued_navax"].sum() > 0
