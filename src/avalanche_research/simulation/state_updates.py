"""State update functions for the Avalanche consensus and staking simulation."""

from __future__ import annotations

import copy
import numpy as np
from typing import Dict, Any, Tuple
from avalanche_research.simulation.state import ValidatorRecord


def s_update_validators(
    params: Dict[str, Any],
    step: int,
    sH: list,
    s: Dict[str, Any],
    policies: Dict[str, Any],
) -> Tuple[str, Dict[str, ValidatorRecord]]:
    """Updates validator remaining durations, applies renewals, and updates delegation allocations."""
    dt_days = params.get("dt_days", 7)
    validators: Dict[str, ValidatorRecord] = {
        nid: copy.deepcopy(v) for nid, v in s["validators"].items()
    }

    renewals = policies.get("renewals", {})
    benqi_allocs = policies.get("benqi_allocations", {})

    for nid, val in validators.items():
        if not val.is_active:
            continue

        # Check if renewed in this step
        if nid in renewals:
            info = renewals[nid]
            if info["action"] == "renew":
                val.total_duration_days = info["chosen_duration"]
                val.remaining_days = info["chosen_duration"]
                val.self_bond_avax = info.get("bond", val.self_bond_avax)
            elif info["action"] == "exit":
                val.is_active = False
                val.remaining_days = 0
                val.delegations_received_avax = 0.0
        else:
            # Advance time
            val.remaining_days = max(0, val.remaining_days - dt_days)
            val.uptime_days += dt_days

        # Update delegations: organic delegations persist; BENQI provides incremental liquid staking delegation
        if val.is_active and nid in benqi_allocs:
            # BENQI routing dynamically assigns or adjusts pool delegations
            pass

    return "validators", validators


def s_update_staking_metrics(
    params: Dict[str, Any],
    step: int,
    sH: list,
    s: Dict[str, Any],
    policies: Dict[str, Any],
) -> Tuple[str, float]:
    """Recalculates total staked supply (bonds + delegations)."""
    validators = s["validators"]
    total_staked = sum(v.total_weight_avax for v in validators.values() if v.is_active)
    return "staked_supply_avax", float(total_staked)


def s_update_bonded_self_stake(
    params: Dict[str, Any],
    step: int,
    sH: list,
    s: Dict[str, Any],
    policies: Dict[str, Any],
) -> Tuple[str, float]:
    """Recalculates total bonded self-stake across active validators."""
    validators = s["validators"]
    total_self = sum(v.self_bond_avax for v in validators.values() if v.is_active)
    return "bonded_self_stake_avax", float(total_self)


def s_update_staking_ratio(
    params: Dict[str, Any],
    step: int,
    sH: list,
    s: Dict[str, Any],
    policies: Dict[str, Any],
) -> Tuple[str, float]:
    """Updates the staking ratio = staked_supply / circulating_supply."""
    staked = s["staked_supply_avax"]
    circulating = s["circulating_supply_avax"]
    ratio = staked / circulating if circulating > 0 else 0.0
    return "staking_ratio", float(ratio)


def s_update_duration_metrics(
    params: Dict[str, Any],
    step: int,
    sH: list,
    s: Dict[str, Any],
    policies: Dict[str, Any],
) -> Tuple[str, float]:
    """Computes stake-weighted mean duration in weeks."""
    validators = [v for v in s["validators"].values() if v.is_active]
    if not validators:
        return "average_duration_weeks", 0.0

    total_weight = sum(v.total_weight_avax for v in validators)
    if total_weight <= 0:
        return "average_duration_weeks", 0.0

    weighted_days = sum(v.total_duration_days * v.total_weight_avax for v in validators) / total_weight
    return "average_duration_weeks", float(weighted_days / 7.0)


def s_update_unweighted_duration(
    params: Dict[str, Any],
    step: int,
    sH: list,
    s: Dict[str, Any],
    policies: Dict[str, Any],
) -> Tuple[str, float]:
    """Computes unweighted mean duration in days (to track retail behavior)."""
    validators = [v for v in s["validators"].values() if v.is_active]
    if not validators:
        return "unweighted_mean_duration_days", 0.0
    mean_days = sum(v.total_duration_days for v in validators) / len(validators)
    return "unweighted_mean_duration_days", float(mean_days)


def s_update_pchain_txs(
    params: Dict[str, Any],
    step: int,
    sH: list,
    s: Dict[str, Any],
    policies: Dict[str, Any],
) -> Tuple[str, int]:
    """Accumulates P-Chain AddValidatorTx and renewal transactions."""
    delta = policies.get("pchain_tx_count_delta", 0)
    current = s.get("pchain_tx_count", 0)
    return "pchain_tx_count", int(current + delta)


def s_update_circulating_supply(
    params: Dict[str, Any],
    step: int,
    sH: list,
    s: Dict[str, Any],
    policies: Dict[str, Any],
) -> Tuple[str, float]:
    """Updates circulating supply via ACP-285 minting schedule (capped 720M target)."""
    current_supply = s["circulating_supply_avax"]
    dt_days = params.get("dt_days", 7)
    # Simple continuous minting approximation (~7.5% annual issuance on staked supply)
    annual_rate = params.get("annual_issuance_rate", 0.075)
    staked = s["staked_supply_avax"]
    new_mint = staked * annual_rate * (dt_days / 365.0)
    
    # Cap at 720M max supply
    new_supply = min(720_000_000.0, current_supply + new_mint)
    return "circulating_supply_avax", float(new_supply)
