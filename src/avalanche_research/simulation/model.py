"""Avalanche GDS Simulation Model Assembly."""

from __future__ import annotations

from typing import Dict, Any, List
from gds_sim import Model, StateUpdateBlock

from avalanche_research.simulation.state import get_initial_pchain_state
from avalanche_research.simulation.policies import (
    p_admission_filter,
    p_validator_renewal_and_entry,
    p_benqi_routing,
)
from avalanche_research.simulation.state_updates import (
    s_update_validators,
    s_update_staking_metrics,
    s_update_bonded_self_stake,
    s_update_staking_ratio,
    s_update_duration_metrics,
    s_update_unweighted_duration,
    s_update_pchain_txs,
    s_update_circulating_supply,
)


def build_avalanche_model(
    params: Dict[str, List[Any]] | None = None,
    initial_state: Dict[str, Any] | None = None,
) -> Model:
    """Builds and returns the canonical gds_sim.Model for Avalanche Staking."""
    default_params = {
        "s_short": [20_000.0],
        "p": [0.642],
        "gamma_return": [2.5],
        "gamma_illiquidity": [1.8],
        "benqi_pool_avax": [15_000_000.0],
        "annual_issuance_rate": [0.075],
        "delegation_subsidy_ratio": [1.0],  # Multiplier of self-bond received in delegations (e.g. 1.0 = 1x self-bond, 2.0 = 2x, 4.0 = 4x)
        "dt_days": [7],
    }
    if params is not None:
        merged_params = dict(default_params)
        merged_params.update(params)
    else:
        merged_params = default_params

    if initial_state is None:
        initial_state = get_initial_pchain_state()

    # Block 1: Admission filter evaluation & Validator renewal choices
    sub_1 = StateUpdateBlock(
        policies={
            "admission": p_admission_filter,
            "renewals": p_validator_renewal_and_entry,
            "benqi": p_benqi_routing,
        },
        variables={
            "validators": s_update_validators,
            "pchain_tx_count": s_update_pchain_txs,
        },
    )

    # Block 2: Staking aggregates and market dynamics
    sub_2 = StateUpdateBlock(
        policies={},
        variables={
            "staked_supply_avax": s_update_staking_metrics,
            "bonded_self_stake_avax": s_update_bonded_self_stake,
            "circulating_supply_avax": s_update_circulating_supply,
        },
    )

    # Block 3: Ratio and duration KPI tracking
    sub_3 = StateUpdateBlock(
        policies={},
        variables={
            "staking_ratio": s_update_staking_ratio,
            "average_duration_weeks": s_update_duration_metrics,
            "unweighted_mean_duration_days": s_update_unweighted_duration,
        },
    )

    return Model(
        params=merged_params,
        initial_state=initial_state,
        state_update_blocks=[sub_1, sub_2, sub_3],
    )
