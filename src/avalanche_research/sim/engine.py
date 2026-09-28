"""The daily staking economy model: one trajectory, vectorised over cohorts with numpy. Callers loop over seeds.

Block order of each day t (the specification's section on the daily block):

1. Environment: price and external yield from the scenario.
2. Quote: the annualized reward rate of a new stake of ``quote_duration_days`` at the opening counter, and the
   spread against the external yield.
3. Expiry: cohorts in slot t leave. Their reserved rewards are paid at the pass rate, the rest returns to the
   reserve (the counter drops by it). Realized supply rises by the rewards paid, and by nothing else.
4. Renewal: each expiring validator renews with the renewal probability (binomial).
5. Entry: new validators arrive (Poisson), each with the entrant self stake, capped at the maximum weight.
6. Duration choice: renewing and new validators choose menu durations (multinomial). Each new cohort's potential
   reward comes from the registered mechanism at the counter, is reserved in the counter, and is paid at expiry.
7. Delegation: capacity from the active validators. Delegated stake moves toward the previous level plus the net
   flow, never below the committed (unexpired) delegations and never above capacity. New delegations of
   ``delegation_duration_days`` are priced and reserved like validator stake.
8. Measures: the KPI columns at the close of the day.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import invariants, policies, updates
from .params import Params
from .scenario import Scenario
from .state import SYNTHETIC_2025, State, synthetic_state

DAYS_PER_MONTH = 365.25 / 12
COLUMNS = (
    "day", "date", "supply_avax", "validator_stake_avax", "delegated_stake_avax", "staking_ratio", "validator_count",
    "rewards_paid_avax", "reward_apr", "hhi", "net_inflation_annual", "validator_profit_usd_month",
    # Diagnostics beyond the shared interface.
    "supply_counter_avax", "rewards_due_avax", "delegation_capacity_avax", "spread", "new_validators",
    "renewed_validators", "expired_validators", "delegation_forced_exit_avax",
)


def run(params: Params, scenario: Scenario, seed: int, days: int, initial_state: State | None = None,
        check_invariants: bool = False) -> pd.DataFrame:
    """Simulate ``days`` days from ``initial_state`` (the synthetic 2025-01-01 start when None).

    Returns one row per day with the columns in ``COLUMNS``. With ``check_invariants`` every day is checked by
    ``invariants.check_step`` and the first violation raises ``invariants.InvariantError``.
    """
    if days > scenario.days:
        raise ValueError(f"scenario {scenario.name} has {scenario.days} days, fewer than {days}")
    behaviour = params.behaviour
    rng = np.random.default_rng(seed)
    mechanism = policies.get_mechanism(params.mechanism)
    menu, base_probabilities = policies.effective_menu(behaviour, params.min_stake_days, params.max_stake_days)
    menu_float = menu.astype(float)
    delegation_days = int(min(max(behaviour.delegation_duration_days, params.min_stake_days), params.max_stake_days))
    quote_days = np.array([float(min(max(behaviour.quote_duration_days, params.min_stake_days), params.max_stake_days))])
    one = np.ones(1)
    context = policies.MechanismContext(params=params)
    cap = params.supply_cap_avax
    horizon = max(int(menu.max()) + 1, delegation_days + 1, int(quote_days[0]) + 1)

    if initial_state is None:
        # Open periods were priced under mainnet rules, whatever the parameter set being simulated.
        reference = policies.MechanismContext(params=Params(), supply_counter_avax=SYNTHETIC_2025["counter_avax"])
        initial_state = synthetic_state(menu, delegation_days, lambda s, d: policies.linear(s, d, reference), horizon)
    ring = updates.ring_from_state(initial_state, menu, horizon)
    horizon = ring.horizon
    supply = float(initial_state.supply_avax)
    counter = float(initial_state.counter_avax)
    accrual_v = float(ring.validator_accrual.sum())
    accrual_d = float(ring.delegated_accrual.sum())
    delegated = float(ring.delegated_stake.sum())
    validator_stake = float(ring.validator_stake.sum())
    validator_count = float(ring.validator_count.sum())
    initial_supply = supply
    weight_factor = float(params.max_weight_factor)
    max_weight = float(params.max_validator_stake_avax)
    entry_stake = float(min(max(behaviour.entry_stake_avax, params.min_validator_stake_avax), max_weight))
    pass_v = behaviour.validator_reward_pass_rate
    pass_d = behaviour.delegated_reward_pass_rate
    fee_share = behaviour.validator_fee_share
    renewal_fixed = behaviour.renewal_spread_elasticity == 0.0
    renewal_p = behaviour.renewal_probability

    out = np.zeros((days, len(COLUMNS) - 1))
    for t in range(days):
        price = scenario.price_usd[t]
        external = scenario.external_yield[t]
        slot = t % horizon
        supply_open = supply

        # 2. Quote at the opening state.
        context.day = t
        context.supply_counter_avax = counter
        context.supply_avax = supply
        context.staking_ratio = (validator_stake + delegated) / supply
        context.validator_count = validator_count
        context.external_yield = external
        context.price_usd = price
        context.role = "validator"
        apr = float(mechanism(one, quote_days, context)[0]) * 365.0 / quote_days[0]
        spread = apr - external

        # 3. Expiry and payment.
        gone = updates.expire(ring, slot)
        due = gone.validator_reward_due + gone.delegated_reward_due
        paid = gone.validator_reward_due * pass_v + gone.delegated_reward_due * pass_d
        supply += paid
        counter -= due - paid
        accrual_v -= gone.validator_accrual
        accrual_d -= gone.delegated_accrual
        committed = delegated - gone.delegated_stake

        # 4. Renewal.
        expired_n = gone.validator_count
        expired_total = float(expired_n.sum())
        renewed_total = 0.0
        renewed_stake = 0.0
        if expired_total > 0:
            p = renewal_p if renewal_fixed else policies.renewal_probability(behaviour, spread)
            if p >= 1.0:
                renewed = expired_n
            elif p <= 0.0:
                renewed = np.zeros_like(expired_n)
            else:
                renewed = rng.binomial(expired_n.astype(np.int64), p).astype(float)
            renewed_total = float(renewed.sum())
            if renewed_total > 0:
                share = np.divide(renewed, expired_n, out=np.zeros_like(renewed), where=expired_n > 0)
                renewed_stake = float((gone.validator_stake * share).sum())

        # 5. Entry.
        rate = policies.entry_rate(behaviour, spread)
        entrants = int(rng.poisson(rate)) if rate > 0 else 0

        # 6. Duration choice and reward pricing.
        starting = renewed_total + entrants
        if starting > 0:
            probabilities = policies.duration_probabilities(behaviour, menu_float, base_probabilities, spread)
            count_r = rng.multinomial(int(renewed_total), probabilities) if renewed_total > 0 else 0.0
            count_e = rng.multinomial(entrants, probabilities) if entrants > 0 else 0.0
            stake_k = count_r * (renewed_stake / renewed_total if renewed_total > 0 else 0.0) + count_e * entry_stake
            count_k = np.asarray(count_r + count_e, dtype=float)
            reward_k = mechanism(stake_k, menu_float, context)
            room = cap - counter
            total_reward = float(reward_k.sum())
            if total_reward > room:
                reward_k = reward_k * (max(room, 0.0) / total_reward)
                total_reward = max(room, 0.0)
            counter += total_reward
            accrual_v += updates.start_validators(ring, t, stake_k, count_k, reward_k)
        validator_stake = float(ring.validator_stake.sum())
        validator_count = float(ring.validator_count.sum())

        # 7. Delegation.
        cells = updates.cell_capacity(ring, weight_factor, max_weight)
        capacity = float(cells.sum())
        forced = 0.0
        if committed > capacity:
            keep = capacity / committed if committed > 0 else 0.0
            forced, released, removed_accrual = updates.shrink_delegations(ring, keep)
            paid_now = released * pass_d
            supply += paid_now
            counter -= released - paid_now
            paid += paid_now
            due += released
            accrual_d -= removed_accrual
            committed = capacity
        unstaked = supply - validator_stake - delegated
        target = delegated + policies.delegation_flow(behaviour, spread, unstaked)
        target = min(max(target, committed), capacity)
        new_delegation = target - committed
        if new_delegation > 0:
            context.role = "delegator"
            reward = float(mechanism(np.array([new_delegation]), np.array([float(delegation_days)]), context)[0])
            reward = min(reward, max(cap - counter, 0.0))
            counter += reward
            accrual_d += updates.start_delegation(ring, t, new_delegation, reward, delegation_days)
        delegated = target

        # 8. Measures.
        staked = validator_stake + delegated
        profit = ((accrual_v + fee_share * accrual_d) / validator_count * DAYS_PER_MONTH * price
                  if validator_count > 0 else 0.0) - params.operating_cost_usd_month
        out[t] = (
            t, supply, validator_stake, delegated, staked / supply, validator_count, paid, apr,
            updates.hhi(ring, delegated, cells), paid * 365.0 / supply_open, profit,
            counter, due, capacity, spread, entrants, renewed_total, expired_total, forced,
        )
        if check_invariants:
            row = dict(zip(COLUMNS[:1] + COLUMNS[2:], out[t]))
            invariants.check_step(row, supply_open, cap)

    frame = pd.DataFrame(out, columns=[c for c in COLUMNS if c != "date"])
    frame["day"] = frame["day"].astype(np.int64)
    start = date.fromisoformat(scenario.start_date)
    frame.insert(1, "date", [start + timedelta(days=int(i)) for i in range(days)])
    frame.attrs.update({
        "initial_supply_avax": initial_supply, "seed": seed, "scenario": scenario.name, "mechanism": params.mechanism,
        "behaviour": behaviour.version, "menu_days": menu.tolist(), "delegation_duration_days": delegation_days,
        "initial_state_date": initial_state.date,
    })
    return frame
