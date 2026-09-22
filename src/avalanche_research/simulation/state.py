"""State definitions for the Avalanche consensus and staking simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any
import numpy as np


@dataclass
class ValidatorRecord:
    """Represents an active validator entity in the simulation."""
    node_id: str
    self_bond_avax: float
    total_duration_days: int
    remaining_days: int
    commission_fee: float  # e.g., 0.02 = 2%
    delegations_received_avax: float = 0.0
    uptime_days: int = 15
    is_active: bool = True

    @property
    def total_weight_avax(self) -> float:
        return self.self_bond_avax + self.delegations_received_avax


def get_initial_pchain_state(
    sample_nodes: List[Dict[str, Any]] | None = None,
    total_supply_avax: float = 450_000_000.0,
) -> Dict[str, Any]:
    """Generates the initial state dictionary for gds-sim."""
    validators: Dict[str, ValidatorRecord] = {}

    if sample_nodes:
        for idx, row in enumerate(sample_nodes):
            nid = row.get("node_id", f"NodeID-Sim-{idx:04d}")
            validators[nid] = ValidatorRecord(
                node_id=nid,
                self_bond_avax=float(row.get("bond_avax", 2000.0)),
                total_duration_days=int(row.get("duration_days", 14)),
                remaining_days=int(row.get("remaining_days", row.get("duration_days", 14))),
                commission_fee=float(row.get("commission_fee", 0.02)),
                delegations_received_avax=float(row.get("delegation_volume_received_avax", 0.0)),
            )
    else:
        # Default representative demographic based on empirical renewal panel:
        # In Avalanche, ~245-250M AVAX staked out of ~450M circulating (~54-55% staking ratio).
        # Whales (>=6k) hold >98% of capital.
        # Empirically, whale stints average 64.8d (unweighted) and 81.0d (stake-weighted, ~11.6 weeks).
        # We assign an empirical mixture across [14d, 30d, 60d, 90d, 180d, 365d]
        whale_durations = [14, 30, 60, 90, 180, 365]
        whale_weights = [0.25, 0.25, 0.20, 0.15, 0.10, 0.05]
        for i in range(175):
            d_choice = int(np.random.choice(whale_durations, p=whale_weights))
            validators[f"Whale-{i:03d}"] = ValidatorRecord(
                node_id=f"Whale-{i:03d}",
                self_bond_avax=1_100_000.0 if i < 50 else 400_000.0,
                total_duration_days=d_choice,
                remaining_days=max(7, d_choice // 2),
                commission_fee=0.02,
                delegations_received_avax=1_100_000.0 if i < 50 else 600_000.0,
            )
        # 600 retail stakers (<6k) holding ~2k AVAX each (~1.2M AVAX self stake)
        for i in range(600):
            validators[f"Retail-{i:03d}"] = ValidatorRecord(
                node_id=f"Retail-{i:03d}",
                self_bond_avax=2000.0,
                total_duration_days=14 if i % 3 == 0 else 30,
                remaining_days=7 if i % 3 == 0 else 14,
                commission_fee=0.05,
                delegations_received_avax=2000.0,
            )

    total_staked = sum(v.total_weight_avax for v in validators.values())
    staked_self = sum(v.self_bond_avax for v in validators.values())

    return {
        "validators": validators,
        "staked_supply_avax": total_staked,
        "bonded_self_stake_avax": staked_self,
        "circulating_supply_avax": total_supply_avax,
        "staking_ratio": total_staked / total_supply_avax if total_supply_avax > 0 else 0.5,
        "average_duration_weeks": 10.0,
        "unweighted_mean_duration_days": 45.6,
        "pchain_tx_count": 0,
        "total_minted_rewards_avax": 0.0,
        "total_burned_fees_avax": 0.0,
    }
