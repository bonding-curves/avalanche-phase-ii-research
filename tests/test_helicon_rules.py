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
from avalanche_research.model.parts import helicon
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


def test_a_helicon_rule_is_refused_on_a_model_with_delegations():
    with pytest.raises(ValueError, match="validator lifecycle"):
        REFERENCE["delegated"](auto_renew_share=0.5).blocks()


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
