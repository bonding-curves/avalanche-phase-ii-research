"""ML29: Helicon's rules as swept settings, each of whose default reproduces v0.9.0.

The reference scenarios and their recorded hashes are those of ``test_v09_price_security``. The runs here are small,
30 to 60 days on the ``test_fitted_lifecycle.model`` fixture, from an origin after Helicon or one that crosses it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cadCAD")
pytest.importorskip("scipy")

from test_fitted_lifecycle import model, path
from test_v09_price_security import RECORDED, REFERENCE, table_sha256

from avalanche_research.mechanisms import ChainReward, RevenueFunded
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_blocks import Arrivals, RenewalLogit, ReturnHazard
from avalanche_research.model.delegation_blocks import DelegationFlow
from avalanche_research.model.parts import helicon
from avalanche_research.model.parts.delegations import on_validators
from avalanche_research.model.parts.stages import Day, RunSettings
from avalanche_research.model.streams import Streams

AVAX = 10**9
SETTINGS = ("auto_renew_share", "auto_renew_exit_hazard", "auto_compound_share", "short_period_share", "uptime_miss_increase")
AFTER = date(2026, 10, 7)
"""An origin after Helicon, so every day of the run is from Helicon on."""
ACROSS = date(2026, 9, 10)
"""An origin before Helicon: the run's first day from Helicon on is 2026-09-23, timestep 13."""
FIRST_AFTER = 13
NO_RETURNS = ReturnHazard(**{name: 0.0 for name in ReturnHazard().sources()})


def arrivals_only(origin=AFTER, stake_avax=7_000, days=5, timesteps=40, runs=2, **settings):
    """No open commitments, no renewal by the logit and no returns: every commitment is a first-ever arrival of
    ``stake_avax`` for ``days``, so the Helicon rules alone decide what continues."""
    return model(origin=origin, initial=pd.DataFrame(columns=["stakes", "days_left", "done", "after_return", "days", "handed_on"]),
                 first_commitments=pd.DataFrame({"days": [days], "stake_navax": [stake_avax * AVAX]}),
                 renewal=RenewalLogit(intercept=-20.0), returns=NO_RETURNS, arrivals=Arrivals(mean_per_day=3.0),
                 timesteps=timesteps, runs=runs, seed=5, record_turnover=True, **settings)


def by_run(table, variable):
    return {r: np.array(path(table, variable, r), dtype=object) for r in sorted(table["run"].unique())}


# Defaults reproduce v0.9.0.

@pytest.mark.parametrize("name", list(REFERENCE))
def test_every_helicon_setting_at_its_default_reproduces_the_v090_reference_hashes(name):
    specification, table = RECORDED[name]
    for built in (REFERENCE[name](), REFERENCE[name](**{key: 0.0 for key in SETTINGS})):
        assert built.specification_hash() == specification
        assert not set(SETTINGS) & (set(built.specification()) | set(built.settings()))
        assert table_sha256(run(built)) == table


@pytest.mark.parametrize("key", SETTINGS)
def test_each_helicon_setting_enters_the_specification_only_when_set(key):
    base = REFERENCE["fitted"]()
    assert base.with_settings(**{key: 0.0}).specification_hash() == base.specification_hash()
    built = base.with_settings(**{key: 0.25})
    assert built.specification()[key] == 0.25 and built.specification_hash() != base.specification_hash()
    assert built.param[key].metadata == {"omit_at_default": True, "source": "scenario"} and built.param[key].bounds == (0.0, 1.0)


def test_a_helicon_rule_is_refused_on_the_holder_model_of_v0100():
    stages = (*((name, None) for name in ("renewal", "continuation", "rewards", "assembly", "delegations")), ("holders", None))
    with pytest.raises(ValueError, match="holder model of v0.10.0"):
        helicon.HeliconRules(auto_renew_share=0.5).stages(stages)
    assert helicon.HeliconRules().stages(stages) == stages


# Automatic renewal.

def test_with_every_start_auto_renewed_and_no_exit_hazard_no_auto_renewed_validator_exits():
    table = run(arrivals_only(auto_renew_share=1.0))
    for r, arrived in by_run(table, "first_ever_validators").items():
        assert arrived.sum() > 0
        assert list(by_run(table, "active_validators")[r]) == list(np.cumsum(arrived))
        assert set(by_run(table, "returning_nodes")[r]) == {0}
    # Without automatic renewal the same arrivals end after their five days and leave.
    plain = run(arrivals_only())
    assert max(path(plain, "returning_nodes")) > 0
    assert path(plain, "first_ever_validators") == path(table, "first_ever_validators")


def test_a_higher_exit_hazard_lowers_active_stake():
    stake = {h: by_run(run(arrivals_only(auto_renew_share=1.0, auto_renew_exit_hazard=h)), "active_validator_stake_navax")
             for h in (0.0, 0.2, 0.6)}
    for r in stake[0.0]:
        assert (stake[0.6][r] <= stake[0.2][r]).all() and (stake[0.2][r] <= stake[0.0][r]).all()
        assert stake[0.6][r][-1] < stake[0.2][r][-1] < stake[0.0][r][-1]


def test_auto_renewal_starts_only_from_helicon_on():
    base, auto = run(arrivals_only(origin=ACROSS)), run(arrivals_only(origin=ACROSS, auto_renew_share=1.0))
    shared = ["active_validators", "active_validator_stake_navax", "issued_navax", "supply_navax"]
    for variable in shared:
        # A commitment started before Helicon ends as before. The first auto-renewed one starts on day 13 and ends after.
        assert path(base, variable)[:FIRST_AFTER + 5] == path(auto, variable)[:FIRST_AFTER + 5]
    assert path(auto, "active_validators")[-1] > path(base, "active_validators")[-1]


# Reward restaking.

def test_restaking_raises_the_stake_by_the_restaked_reward_and_supply_is_conserved():
    days = 5
    full, none = (run(arrivals_only(auto_renew_share=1.0, auto_compound_share=c, days=days)) for c in (1.0, 0.0))
    for table, compounding in ((full, True), (none, False)):
        for r, stake in by_run(table, "active_validator_stake_navax").items():
            arrived = np.cumsum(by_run(table, "first_ever_validators")[r]) * 7_000 * AVAX
            issued = by_run(table, "issued_navax")[r]
            # A cycle started on day s ends on day s + 5, when the whole of its reward is restaked.
            restaked = np.array([issued[1:max(1, t - days + 1)].sum() for t in range(len(stake))], dtype=object)
            assert list(stake) == list(arrived + (restaked if compounding else 0))
            supply = by_run(table, "supply_navax")[r]
            assert list(supply) == list(supply[0] + np.cumsum(issued))
    assert path(full, "issued_navax")[-1] > path(none, "issued_navax")[-1]


def test_restaking_never_lifts_a_stake_above_the_maximum_validator_stake():
    top = 3_000_000 * AVAX
    assert helicon.restaked_navax(np.array([100 * AVAX, 100 * AVAX]), np.array([top - 10 * AVAX, top]), 1.0).tolist() == [10 * AVAX, 0]
    assert helicon.restaked_navax(np.array([100 * AVAX]), np.array([2_000 * AVAX]), 0.25).tolist() == [25 * AVAX]
    table = run(arrivals_only(auto_renew_share=1.0, auto_compound_share=1.0, stake_avax=3_000_000, timesteps=30))
    for r, stake in by_run(table, "active_validator_stake_navax").items():
        assert list(stake) == list(np.cumsum(by_run(table, "first_ever_validators")[r]) * top)


# The 48-hour minimum.

def _starts(n: int) -> dict:
    return {"stakes": np.full(n, 7_000 * AVAX), "days": np.full(n, 30), "node_key": np.arange(n, dtype=np.int64),
            "done": np.zeros(n, dtype=np.int64), "after_return": np.zeros(n, bool), "returns": np.zeros(n, dtype=np.int64)}


@pytest.mark.parametrize(("start", "short"), [(datetime(2026, 9, 23, 12, tzinfo=UTC), True), (datetime(2026, 9, 22, 12, tzinfo=UTC), False)])
def test_with_every_start_short_every_start_from_helicon_on_has_a_period_of_2_to_13_days(start, short):
    rules = helicon.HeliconRules(short_period_share=1.0)
    stage = helicon._Continuation(lambda state, day, earlier: {"started": _starts(500)}, rules)
    settings = RunSettings(large_navax=None, renewal_response=0.0, entry_response=0.0, mechanism=ChainReward(), scheduled={})
    day = Day(t=0, start=start, draw=Streams(3, 1), blocks=None, renewal_gap=0.0, entry_gap=0.0, settings=settings)
    days = stage({}, day, {})["started"]["days"]
    if short:
        assert set(days.tolist()) == set(range(2, 14))
    else:
        assert set(days.tolist()) == {30}


def test_in_a_run_short_periods_leave_starts_before_helicon_unchanged_and_shorten_those_after():
    # Every start is a 30-day arrival of the same stake, so a day's stake-days over its stake is its mean period.
    base, short = (run(arrivals_only(origin=ACROSS, days=30, short_period_share=s)) for s in (0.0, 1.0))
    for r in (1, 2):
        rows = [t[t["run"] == r].drop_duplicates("timestep").sort_values("timestep") for t in (base, short)]
        stake = by_run(short, "started_stake_navax")[r]
        before = slice(0, FIRST_AFTER)
        assert rows[0]["started_stake_days_navax"].to_numpy()[before].tolist() == rows[1]["started_stake_days_navax"].to_numpy()[before].tolist()
        assert list(by_run(base, "started_stake_navax")[r][before]) == list(stake[before])
        periods = rows[1]["started_stake_days_navax"].to_numpy() / np.where(stake > 0, stake, 1).astype(float)
        assert all(periods[t] == 30 for t in range(1, FIRST_AFTER) if stake[t] > 0)
        after = [periods[t] for t in range(FIRST_AFTER, len(stake)) if stake[t] > 0]
        assert after and all(2 <= p <= 13 for p in after)


# The 90% uptime rule.

def test_a_higher_uptime_miss_lowers_paid_issuance_and_supply_is_issued_less_forfeited():
    paid = {}
    for miss in (0.0, 0.3, 0.8):
        table = run(arrivals_only(uptime_miss_increase=miss, timesteps=60))
        paid[miss] = 0
        for r, issued in by_run(table, "issued_navax").items():
            forfeited = by_run(table, helicon.FORFEIT)[r] if miss else np.zeros(len(issued), dtype=object)
            supply = by_run(table, "supply_navax")[r]
            assert list(supply) == list(supply[0] + np.cumsum(issued) - np.cumsum(forfeited))
            assert 0 <= forfeited.sum() <= issued.sum() and (forfeited.sum() > 0) == (miss > 0)
            paid[miss] += issued.sum() - forfeited.sum()
    assert paid[0.8] < paid[0.3] < paid[0.0]


def test_a_period_that_starts_before_helicon_and_ends_after_it_is_never_missed():
    # 30-day arrivals: those started on timesteps 1 to 12, before Helicon, end on timesteps 31 to 42, after it.
    base, missed = (run(arrivals_only(origin=ACROSS, days=30, timesteps=42, uptime_miss_increase=m)) for m in (0.0, 1.0))
    ended = sum(path(missed, "ended_validators")[31:])
    assert ended > 0 and sum(path(missed, helicon.FORFEIT)) == 0
    assert path(missed, "supply_navax") == path(base, "supply_navax")
    # Those started from Helicon on, which end from timestep 43, all miss.
    later = run(arrivals_only(origin=ACROSS, days=30, timesteps=50, uptime_miss_increase=1.0))
    forfeits = path(later, helicon.FORFEIT)
    assert sum(forfeits[:43]) == 0 and sum(forfeits[43:]) == sum(path(later, "issued_navax")[13:21])


def test_the_responses_read_the_expected_reward_received_under_the_uptime_rule():
    shared = {"renewal_response": 0.5, "entry_response": 0.5, "timesteps": 10, "runs": 1, "origin": AFTER}
    base, missing = model(**shared), model(**shared, uptime_miss_increase=0.4)
    gaps = [t[t["timestep"] > 0].drop_duplicates("timestep").sort_values("timestep")["yield_gap_pp"].to_numpy()
            for t in (run(base), run(missing))]
    expected = [base.response_rate_pp(AFTER + timedelta(days=t), base.renewal_tenure) * 0.4 for t in range(1, 11)]
    assert gaps[1] == pytest.approx(gaps[0] - np.array(expected), abs=1e-12)


def test_the_uptime_rule_is_refused_with_revenue_funding():
    with pytest.raises(ValueError, match="revenue"):
        model(mechanism=RevenueFunded(), uptime_miss_increase=0.1)


# The rules on the delegated candidate (DelegatedStakeLifecycle with the v0.8.1 laws).

CANDIDATE_ORIGIN = date(2025, 11, 18)
"""The candidate's latest origin, as its stake law refuses one in the held-back period: its first day from Helicon on is
timestep 309, so a run of 400 days has 92 days after it."""


def candidate(origin=CANDIDATE_ORIGIN, timesteps=400, runs=2, **settings):
    """The released base's tiny state (views.model_structure.tiny_stake_lifecycle) at ``origin``, with delegations
    under the containment laws, the stake law fitted on synthetic tables labelled with that origin."""
    import hashlib

    from avalanche_research.model.delegated_lifecycle import DelegatedStakeLifecycle
    from avalanche_research.model.fitted_lifecycle import decided_by_us
    from avalanche_research.model.parts.return_hazard import ReturnLogitHazard
    from avalanche_research.model.stake_lifecycle import fitted_stake_settings
    from test_delegated_lifecycle import TERMS
    from test_v081_candidate import law_blocks

    tables = {}
    for context in ("renewal", "return", "entry"):
        table = pd.DataFrame({
            "previous_stake_navax": np.full(60, 0 if context == "entry" else 2_000 * AVAX, dtype=np.int64),
            "next_days": np.full(60, 30, dtype=np.int64),
            "next_stake_navax": np.repeat(np.array([2_000, 4_000], dtype=np.int64) * AVAX, 30),
            "decided_us": np.full(60, decided_by_us(origin) - 30 * 86_400_000_000, dtype=np.int64),
        })
        sha = hashlib.sha256(table.to_csv(index=False).encode()).hexdigest()
        table.attrs = {"context": context, "run": "synthetic", "origin": origin.isoformat(), "window": "365 days",
                       "sha256": sha, "source": f"synthetic; origin {origin}; 365 days; sha256 {sha}"}
        tables[context] = table
    initial = pd.DataFrame({"stakes": np.full(4, 2_000 * AVAX), "days_left": [1, 1, 5, 9], "done": [0, 2, 1, 0],
                            "after_return": np.zeros(4, bool), "days": np.full(4, 30), "handed_on": np.zeros(4, bool),
                            "returns": np.zeros(4, dtype=np.int64)})
    return DelegatedStakeLifecycle(
        origin=origin, inputs_source="synthetic", initial=initial,
        out_of_set=pd.DataFrame({"out_stakes": [2_000 * AVAX], "out_days": [8], "out_done": [1], "out_last_days": [30], "out_returns": [0]}),
        moves=pd.DataFrame({"previous_days": [30], "next_days": [30], "previous_stake_navax": [2_000 * AVAX], "next_stake_navax": [2_000 * AVAX]}),
        first_commitments=pd.DataFrame({"days": [30], "stake_navax": [2_000 * AVAX]}),
        renewal=RenewalLogit(intercept=0.0), returns=ReturnLogitHazard(intercept=-1.0), arrivals=Arrivals(mean_per_day=2),
        move_stake_bands="three", move_stake_weighted=False, timesteps=timesteps, runs=runs, seed=3,
        **fitted_stake_settings(tables, origin, "synthetic"),
        open_delegations=pd.DataFrame({"validator": [2, 3], "stakes": [500 * AVAX, 3_000 * AVAX], "days_left": [4, 9], "benqi": [False, True]}),
        benqi_validators=pd.DataFrame({"validator": [3]}), delegation_terms=TERMS,
        delegation_flow=DelegationFlow(mean_per_day=4.0, benqi_share=0.3), **law_blocks(), **settings)


def states(model):
    from test_delegated_lifecycle import final_states

    return final_states(model)


def test_at_defaults_the_delegated_candidate_is_unchanged_by_the_helicon_settings():
    base, zero = candidate(timesteps=40), candidate(timesteps=40, **{key: 0.0 for key in SETTINGS})
    assert zero.specification_hash() == base.specification_hash()
    pd.testing.assert_frame_equal(run(base), run(zero))


def test_on_the_candidate_with_every_start_auto_renewed_the_delegation_invariants_hold_across_helicon():
    model = candidate(auto_renew_share=1.0, auto_compound_share=0.5, short_period_share=0.2)
    raw = states(model)  # the engine checks every invariant, delegation ones included, after every day
    on_auto = 0
    for _, row in raw.iterrows():
        auto_keys = set(row["node_key"][row["auto_renew"]].tolist())
        on_auto += int(np.isin(row["delegation_validator"], list(auto_keys)).sum())
        rows = on_validators(row["node_key"], row["delegation_validator"])
        assert (rows >= 0).all() and (row["delegation_days_left"] <= row["days_left"][rows]).all()
    assert on_auto > 0 and raw["timestep"].max() == 400
    # No auto-renewed validator leaves at hazard 0 with no uptime miss.
    for _, run_rows in raw.groupby("run"):
        before = [set(r["node_key"][r["auto_renew"]].tolist()) for _, r in run_rows.iterrows()]
        assert all(a <= set(r["node_key"].tolist()) for a, (_, r) in zip(before, list(run_rows.iterrows())[1:]))


def test_on_the_candidate_delegations_to_auto_renewed_validators_that_exit_end_with_them():
    raw = states(candidate(auto_renew_share=1.0, auto_renew_exit_hazard=1.0))
    exited_with_delegations = 0
    for _, run_rows in raw.groupby("run"):
        rows = [r for _, r in run_rows.sort_values("timestep").iterrows()]
        for previous, current in zip(rows, rows[1:]):
            gone = set(previous["node_key"][previous["auto_renew"]].tolist()) - set(current["node_key"].tolist())
            assert not set(current["delegation_validator"].tolist()) & gone
            held = [rows[i]["delegation_validator"] for i in range(len(rows)) if rows[i]["timestep"] < current["timestep"]]
            exited_with_delegations += sum(bool(set(h.tolist()) & gone) for h in held)
    assert exited_with_delegations > 0


def test_on_the_candidate_a_missed_period_forfeits_its_validator_and_delegator_rewards():
    raw = states(candidate(uptime_miss_increase=1.0))
    delegator_forfeit = 0
    for _, run_rows in raw.groupby("run"):
        rows = [r for _, r in run_rows.sort_values("timestep").iterrows()]
        supply0 = rows[0]["supply_navax"]
        assert [r["supply_navax"] for r in rows] == list(supply0 + np.cumsum([r["issued_navax"] for r in rows])
                                                         - np.cumsum([r[helicon.FORFEIT] for r in rows]))
        for previous, current in zip(rows, rows[1:]):
            start = datetime.combine(CANDIDATE_ORIGIN + timedelta(days=int(current["timestep"])), datetime.min.time(), tzinfo=UTC).replace(hour=12)
            ends = previous["days_left"] - 1 <= 0
            missed = ends & helicon.started_from_helicon(start, previous["days"], previous["days_left"])
            ending = previous["delegation_days_left"] - 1 <= 0
            on = on_validators(previous["node_key"], previous["delegation_validator"][ending])
            judged = helicon.started_from_helicon(start, previous["days"][on], previous["days_left"][on])
            delegators = int(previous["delegation_rewards"][ending][judged].sum())
            assert current[helicon.FORFEIT] == int(previous["cycle_reward_navax"][missed].sum()) + delegators
            delegator_forfeit += delegators
    assert delegator_forfeit > 0


def restake_day(mechanism):
    """A continuing auto-renewed 2,000 AVAX validator whose cycle reward of 1 AVAX sits in the unstaked supply, and a
    2,100 AVAX start that the supply limit funds from the same pool, the case review RV-20261105-17 F1 found."""
    from avalanche_research.model.parts.participation import cap_started
    from avalanche_research.model.parts.stages import assembly_stage, rewards_stage

    none, flags = np.array([], dtype=np.int64), np.array([], dtype=bool)
    state = {"stakes": np.array([2000 * AVAX]), "days_left": np.array([1]), "days": np.array([5]), "done": np.array([0]),
             "after_return": np.array([False]), "handed_on": np.array([False]), "returns": np.array([0]),
             "node_key": np.array([1]), "out_stakes": none, "out_days": none, "out_done": none, "out_last_days": none,
             "out_returns": none, "out_node_key": none, "supply_navax": 4100 * AVAX,
             "active_validator_stake_navax": 2000 * AVAX, "revenue_pool_navax": 0, "auto_renew": np.array([True]),
             "cycle_reward_navax": np.array([AVAX])}
    started = {"stakes": np.array([2100 * AVAX]), "days": np.array([5]), "done": np.array([0]),
               "after_return": np.array([False]), "returns": np.array([0]), "node_key": np.array([2])}
    scheduled = {k: (flags if k == "after_return" else none) for k in
                 ("start_day", "stakes", "days", "done", "after_return", "returns", "node_key")}
    day = Day(t=0, start=datetime(2026, 10, 7, 12, tzinfo=UTC), draw=Streams(1, 1), blocks=None, renewal_gap=0.0,
              entry_gap=0.0, settings=RunSettings(large_navax=None, renewal_response=0.0, entry_response=0.0,
                                                  mechanism=mechanism, scheduled=scheduled))
    renewal = {"days_left": np.array([5]), "ending": np.array([False]), "renews": flags, "continued": np.array([True]),
               "missed": np.array([False]), "ended": {k: none for k in ("stakes", "done", "days", "returns", "node_key")}}
    earlier = {"renewal": renewal, "returns": {"out_days": none, "comes_back": flags}}
    earlier["continuation"] = cap_started(state, day, earlier, started, 0, 0)
    rules = helicon.HeliconRules(auto_renew_share=1.0, auto_compound_share=1.0)
    earlier["rewards"] = helicon._Rewards(rewards_stage, rules)(state, day, earlier)
    out = helicon._Assembly(assembly_stage, rules)(state, day, earlier)
    return state, earlier, out


@pytest.mark.parametrize("mechanism", [ChainReward(), RevenueFunded(revenue_share=1.0, shortfall="cut")],
                         ids=["minted", "revenue-funded"])
def test_restaking_never_lifts_the_stake_above_the_supply_when_the_days_starts_take_the_pool(mechanism):
    state, earlier, out = restake_day(mechanism)
    supply = int(state["supply_navax"]) + int(out["issued_navax"]) - int(out[helicon.FORFEIT])
    assert int(earlier["continuation"]["started"]["stakes"].sum()) == 2100 * AVAX  # the start took the whole pool
    assert int(out["stakes"].sum()) <= supply
    # The restake that did not fit is paid out, so the continuing validator keeps its own stake.
    assert int(earlier["rewards"]["restaked"].sum()) == 0 and int(out["stakes"][0]) == 2000 * AVAX


def test_restaking_takes_only_the_room_left_in_order():
    assert helicon.within_room(np.array([5, 4, 3]), 7).tolist() == [5, 2, 0]
    assert helicon.within_room(np.array([5, 4]), 20).tolist() == [5, 4]
    assert helicon.within_room(np.array([5]), -3).tolist() == [0]
