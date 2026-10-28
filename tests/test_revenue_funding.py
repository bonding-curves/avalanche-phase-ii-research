"""Revenue-funded rewards: a share of each reward paid from a revenue pool instead of minted, behind settings whose
defaults reproduce the branch this one was cut from.

The reproduction hashes were recorded on branch ``prototype/v0.8.1-supply-cap`` at commit c1d03bd on 2026-10-28,
from three small reference scenarios: the fitted lifecycle with renewals and arrivals, the stake lifecycle of
``test_stake_lifecycle.model_on`` and the delegated lifecycle of ``test_delegated_lifecycle.delegated`` with a flow of
new delegations. The long table's hash leaves out the ``time`` and ``dt`` columns and is taken over the rows in a
fixed order, so it reads every state variable, every float variable and every setting column of every run and day.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cadCAD")
pytest.importorskip("scipy")

from test_delegated_lifecycle import delegated, flowing
from test_fitted_lifecycle import model, path
from test_stake_lifecycle import model_on

from avalanche_research.mechanisms import ChainReward, Funding, RevenueFunded, RewardContext
from avalanche_research.model import runner
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_blocks import Arrivals, RenewalLogit
from avalanche_research.model.fitted_lifecycle import REVENUE_VARIABLES

AVAX = 10**9
SUPPLY = 465_370_000 * AVAX
START = datetime(2025, 11, 19, 12, tzinfo=UTC)
NEED_AVAX_PA = 5_640_000
"""Half of the potential rewards of the year before the Milestone 2 origin, the Foundation's proposal at full coverage."""

RECORDED = {
    "fitted": ("88c8bbdc796634fc", "d016bd2b2004f56e3a399502efcf16ebfd603e85904212cdd4ef8db127fbbeb7"),
    "stake": ("62a6e11f79e1b94b", "f00db1205a6b7d5b8bb401400f103c410f27f129fa423ca990fe5a8b4c70ec17"),
    "delegated": ("fa9899b5a83c62cf", "b605be8865300d0131b314071a2131f626acb53c870d345aa248eceb96dafbad"),
}
"""Per reference scenario: the specification hash and the long table's SHA-256 on the parent branch."""

REFERENCE = {
    "fitted": lambda **extra: model(renewal=RenewalLogit(intercept=0.5), arrivals=Arrivals(mean_per_day=2.0), timesteps=12, runs=2, seed=11, **extra),
    "stake": lambda **extra: model_on(**extra),
    "delegated": lambda **extra: delegated(delegation_flow=flowing(), timesteps=8, **extra),
}
NEW_SETTINGS = ("revenue_avax_pa", "count_revenue_in_supply")


def table_sha256(table: pd.DataFrame) -> str:
    kept = table.drop(columns=[c for c in ("time", "dt") if c in table.columns])
    body = kept.sort_values(["simulation", "run", "timestep", "variable"]).reset_index(drop=True).to_csv(index=False, float_format="%.12g")
    return hashlib.sha256(body.encode()).hexdigest()


def context(pool_navax: int) -> RewardContext:
    return RewardContext(day=START, supply_navax=SUPPLY, pool_navax=pool_navax, validator_stake_navax=200_000_000 * AVAX)


def comparable(table: pd.DataFrame) -> pd.DataFrame:
    """The long table without the mechanism and specification columns and without the revenue variables, so a run under
    one rule can be compared with a run under another."""
    kept = table[~table["variable"].isin(REVENUE_VARIABLES)]
    return kept.drop(columns=[c for c in ("mechanism", "specification", *NEW_SETTINGS) if c in kept.columns]).reset_index(drop=True)


# Defaults reproduce the parent branch.

@pytest.mark.parametrize("name", list(REFERENCE))
def test_the_defaults_reproduce_the_parent_specification_and_table_byte_for_byte(name):
    built = REFERENCE[name]()
    specification, table = RECORDED[name]
    assert built.specification_hash() == specification
    for key in NEW_SETTINGS:
        assert key not in built.specification() and key not in built.settings()
    assert not built.funded
    long = run(built)
    assert not set(REVENUE_VARIABLES) & set(long["variable"])
    assert table_sha256(long) == table


def test_each_new_setting_enters_the_specification_only_when_set():
    base = REFERENCE["fitted"]()
    assert base.with_settings(revenue_avax_pa=0.0, count_revenue_in_supply=False).specification_hash() == base.specification_hash()
    streamed = base.with_settings(revenue_avax_pa=NEED_AVAX_PA)
    assert streamed.specification()["revenue_avax_pa"] == NEED_AVAX_PA and streamed.specification_hash() != base.specification_hash()
    counted = base.with_settings(count_revenue_in_supply=True)
    assert counted.specification()["count_revenue_in_supply"] is True and counted.specification_hash() != base.specification_hash()
    assert streamed.funded and counted.funded and base.with_settings(mechanism=RevenueFunded()).funded


@pytest.mark.parametrize("name", list(REFERENCE))
def test_a_revenue_share_of_zero_reproduces_the_parent_run_column_for_column(name):
    parent = run(REFERENCE[name]())
    neutral = run(REFERENCE[name](mechanism=RevenueFunded(revenue_share=0.0), revenue_avax_pa=NEED_AVAX_PA))
    assert set(REVENUE_VARIABLES) <= set(neutral["variable"])
    pd.testing.assert_frame_equal(comparable(parent), comparable(neutral))
    # The pool only fills: nothing is paid and nothing is owed.
    assert all(x == 0 for x in path(neutral, "revenue_paid_navax")) and all(x == 0 for x in path(neutral, "unpaid_need_navax"))
    inflow = round(NEED_AVAX_PA * AVAX / 365)
    assert path(neutral, "revenue_pool_navax") == [t * inflow for t in range(len(path(neutral, "revenue_pool_navax")))]


# The funding split of one reward.

def test_the_chain_mints_every_reward_and_reads_nothing_from_the_context():
    chain = ChainReward()
    assert not chain.funds_from_revenue
    assert chain.funding(12_345, context(0)) == Funding(minted_navax=12_345, revenue_navax=0, unpaid_navax=0)
    assert chain.funding(12_345, context(10**18)) == Funding(minted_navax=12_345, revenue_navax=0, unpaid_navax=0)


@pytest.mark.parametrize("share", [0.0, 0.25, 0.5, 0.75, 1.0])
@pytest.mark.parametrize("shortfall", ["top_up", "cut"])
def test_minted_plus_revenue_plus_unpaid_equals_the_priced_reward(share, shortfall):
    rule = RevenueFunded(revenue_share=share, shortfall=shortfall)
    assert rule.funds_from_revenue
    for reward in (0, 1, 999, 12_345_678_901, 3_000_000 * AVAX):
        for pool in (0, 1, reward // 3, reward, 10**18):
            funding = rule.funding(reward, context(pool))
            assert funding.minted_navax + funding.revenue_navax + funding.unpaid_navax == reward
            assert 0 <= funding.revenue_navax <= pool and funding.revenue_navax <= rule.revenue_part_navax(reward)
            assert funding.minted_navax >= 0 and funding.unpaid_navax >= 0


def test_the_share_is_taken_to_the_millionth_in_integer_arithmetic():
    rule = RevenueFunded(revenue_share=0.5)
    assert rule.revenue_part_navax(1001) == 500 and rule.revenue_part_navax(2) == 1
    assert RevenueFunded(revenue_share=1 / 3).revenue_part_navax(3_000_000) == 999_999
    assert RevenueFunded(revenue_share=0.0).revenue_part_navax(10**15) == 0
    assert RevenueFunded(revenue_share=1.0).revenue_part_navax(10**15) == 10**15


def test_a_full_pool_pays_the_share_and_an_empty_pool_follows_the_shortfall_rule():
    reward = 1_000_000
    full = RevenueFunded(revenue_share=0.5).funding(reward, context(10**12))
    assert full == Funding(minted_navax=500_000, revenue_navax=500_000, unpaid_navax=0) and full.received_navax == reward
    topped = RevenueFunded(revenue_share=0.5, shortfall="top_up").funding(reward, context(100_000))
    assert topped == Funding(minted_navax=900_000, revenue_navax=100_000, unpaid_navax=0) and topped.received_navax == reward
    cut = RevenueFunded(revenue_share=0.5, shortfall="cut").funding(reward, context(100_000))
    assert cut == Funding(minted_navax=500_000, revenue_navax=100_000, unpaid_navax=400_000) and cut.received_navax == 600_000
    with pytest.raises(ValueError, match="never negative"):
        RevenueFunded(revenue_share=0.5).funding(-1, context(0))


def test_the_neutral_rule_prices_and_offers_what_the_chain_does():
    neutral, chain = RevenueFunded(), ChainReward()
    for days in (2, 14, 30, 90, 365):
        for stake in (2_000 * AVAX, 123_456_789_012, 3_000_000 * AVAX):
            assert neutral.potential_reward_navax(stake, days * 86_400, SUPPLY, START, 2) == chain.potential_reward_navax(stake, days * 86_400, SUPPLY, START, 2)
    half = RevenueFunded(revenue_share=0.5)
    assert half.annual_rate(30, SUPPLY, START) == chain.annual_rate(30, SUPPLY, START)
    assert neutral.check(SUPPLY, START) == [] and half.check(SUPPLY, START) == []
    assert RevenueFunded(acp285=False).config(START) == RevenueFunded(acp285=True).config(START)


# Conservation and the counter in a run.

SHARED = {"renewal": RenewalLogit(intercept=0.5), "arrivals": Arrivals(mean_per_day=2.0), "timesteps": 12, "runs": 1, "seed": 11}


def test_with_the_counter_switch_on_minted_plus_paid_equals_the_chains_issuance_every_day():
    chain = run(model(**SHARED))
    half = run(model(**SHARED, mechanism=RevenueFunded(revenue_share=0.5), revenue_avax_pa=NEED_AVAX_PA, count_revenue_in_supply=True))
    minted, paid, unpaid = (path(half, name) for name in ("issued_navax", "revenue_paid_navax", "unpaid_need_navax"))
    assert path(chain, "supply_navax") == path(half, "supply_navax")
    assert [m + p for m, p in zip(minted, paid)] == path(chain, "issued_navax")
    assert all(u == 0 for u in unpaid) and sum(paid) > 0
    # Half the rewards at a full pool: the minted part exceeds the paid part only by the rounding of each reward.
    assert all(0 <= m - p <= 2 * 10 for m, p in zip(minted, paid))
    # The run's other paths are the chain's: the rate the responses read is the chain's rate.
    for name in ("active_validators", "active_validator_stake_navax", "started_stake_navax", "offered_rate_30d", "yield_gap_pp"):
        assert path(chain, name) == path(half, name)


def test_without_the_switch_the_counter_adds_only_the_minted_part():
    half = run(model(**SHARED, mechanism=RevenueFunded(revenue_share=0.5), revenue_avax_pa=NEED_AVAX_PA))
    minted, paid, supply = path(half, "issued_navax"), path(half, "revenue_paid_navax"), path(half, "supply_navax")
    assert supply == [supply[0] + sum(minted[: t + 1]) for t in range(len(supply))]
    assert sum(paid) > 0
    # The counter sits below the chain's from the first payment on, so the formula pays a little more later.
    chain = path(run(model(**SHARED)), "supply_navax")
    assert supply[1] < chain[1] and all(s <= c for s, c in zip(supply, chain))


def test_the_pool_fills_each_day_before_it_pays_and_never_goes_negative():
    inflow = round(NEED_AVAX_PA * AVAX / 365)
    half = run(model(**SHARED, mechanism=RevenueFunded(revenue_share=0.5), revenue_avax_pa=NEED_AVAX_PA))
    pool, paid = path(half, "revenue_pool_navax"), path(half, "revenue_paid_navax")
    assert pool[0] == 0
    for t in range(1, len(pool)):
        assert pool[t] == pool[t - 1] + inflow - paid[t] and pool[t] >= 0 and paid[t] <= pool[t - 1] + inflow


def test_an_empty_pool_mints_everything_under_top_up_and_leaves_the_need_unpaid_under_cut():
    chain = run(model(**SHARED))
    topped = run(model(**SHARED, mechanism=RevenueFunded(revenue_share=0.5, shortfall="top_up")))
    assert comparable(chain).equals(comparable(topped))
    assert all(x == 0 for x in path(topped, "revenue_paid_navax")) and all(x == 0 for x in path(topped, "unpaid_need_navax"))
    cut = run(model(**SHARED, mechanism=RevenueFunded(revenue_share=0.5, shortfall="cut"), count_revenue_in_supply=True))
    minted, unpaid = path(cut, "issued_navax"), path(cut, "unpaid_need_navax")
    # On the first day both runs price on the origin's counter, so minted plus unpaid is the chain's issuance exactly.
    assert minted[1] + unpaid[1] == path(chain, "issued_navax")[1] and sum(unpaid) > 0
    assert all(x == 0 for x in path(cut, "revenue_paid_navax"))
    # Under cut nothing is paid, so even with the switch on the counter adds only the minted part and sits below the
    # chain's from the first day on, and later rewards are priced a little higher on that lower counter.
    assert path(cut, "supply_navax")[1] < path(chain, "supply_navax")[1]
    assert all(s <= c for s, c in zip(path(cut, "supply_navax"), path(chain, "supply_navax")))
    assert all(0 <= m - u <= 2 * 10 for m, u in zip(minted, unpaid))


def test_a_small_pool_pays_what_it_holds_and_tops_up_the_rest():
    stream = 36_500  # 100 nAVAX a day
    half = run(model(**SHARED, mechanism=RevenueFunded(revenue_share=0.5), revenue_avax_pa=stream / AVAX))
    paid, pool, unpaid = path(half, "revenue_paid_navax"), path(half, "revenue_pool_navax"), path(half, "unpaid_need_navax")
    assert max(paid) <= 100 * len(paid) and sum(paid) > 0 and all(x == 0 for x in unpaid)
    assert all(p >= 0 for p in pool)


def test_the_delegated_lifecycle_keeps_its_issuance_identity_and_mints_delegator_rewards_in_full():
    chain = run(REFERENCE["delegated"]())
    half = run(REFERENCE["delegated"](mechanism=RevenueFunded(revenue_share=0.5), revenue_avax_pa=NEED_AVAX_PA, count_revenue_in_supply=True))
    for table in (chain, half):
        issued, validators, delegators = (np.array(path(table, n)) for n in ("issued_navax", "validator_issued_navax", "delegator_issued_navax"))
        assert (issued == validators + delegators).all()
    assert path(chain, "supply_navax") == path(half, "supply_navax")
    assert path(chain, "delegator_issued_navax") == path(half, "delegator_issued_navax")
    paid = path(half, "revenue_paid_navax")
    assert [v + p for v, p in zip(path(half, "validator_issued_navax"), paid)] == path(chain, "validator_issued_navax")
    assert sum(paid) > 0


def test_a_sweep_row_names_the_rule_and_its_settings_by_class_name():
    values = runner.model_settings({"design": "d", "index": 0, "seed": 1, "mechanism": {"name": "RevenueFunded", "revenue_share": 0.5, "shortfall": "cut"},
                                    "revenue_avax_pa": NEED_AVAX_PA})
    rule = values["mechanism"]
    assert isinstance(rule, RevenueFunded) and rule.revenue_share == 0.5 and rule.shortfall == "cut" and values["revenue_avax_pa"] == NEED_AVAX_PA
    with pytest.raises(ValueError):
        RevenueFunded(shortfall="defer")
    with pytest.raises(ValueError):
        RevenueFunded(revenue_share=1.5)
