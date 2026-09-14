"""Recompute captured potential rewards from the protocol formula and report disagreement by regime."""

from __future__ import annotations

from datetime import timezone
from pathlib import Path
from typing import Any

import duckdb

from ..catalog import DataError
from .protocol import MAINNET_REWARD, MAINNET_UPGRADES, primary_network_reward
from .types import ModelError, RewardConfig, UpgradeSchedule


SUPPLY_CANDIDATES = {
    "supply_before": "previous block supply plus earlier in-block deltas",
    "previous_block": "previous block supply",
    "block_before_later": "own block supply minus this and later in-block deltas",
    "block_after": "own block supply",
}
FETCH_SIZE = 50_000


def _parquet(dataset_dir: Path, name: str) -> str:
    path = dataset_dir / f"{name}.parquet"
    if not path.is_file():
        raise DataError(f"missing dataset output: {path}")
    return str(path)


def backtest(
    validators: Path,
    delegators: Path,
    supply: Path,
    config: RewardConfig = MAINNET_REWARD,
    upgrades: UpgradeSchedule = MAINNET_UPGRADES,
) -> dict[str, Any]:
    """Recompute potential_reward_navax for every validator and delegator row from the formula.

    Each row is evaluated with four candidate supply readings from the supply dataset. The default candidate,
    supply_before, is the previous block's supply plus the deltas of earlier supply-changing transactions in the
    same block. The per-regime table records which candidate reproduces the captured value most often, which is
    the empirical statement of the provider's block semantics.

    Rows whose staking period starts after the transaction was accepted are reported separately. Before Durango a
    staker waited in the pending set and the protocol computed its potential reward when the start time arrived,
    with the supply of that later block, so the acceptance-block supply cannot reproduce those rows. Mismatches on
    rows that start at acceptance are the formula disagreement this check exists to expose.
    """
    connection = duckdb.connect()
    try:
        connection.execute(
            f"""
            CREATE VIEW stakes AS
            SELECT transaction_hash, accepted_at, tx_type, start_time, end_time, stake_navax, potential_reward_navax
            FROM read_parquet('{_parquet(validators, "primary-validator-stakes")}')
            UNION ALL
            SELECT transaction_hash, accepted_at, tx_type, start_time, end_time, stake_navax, potential_reward_navax
            FROM read_parquet('{_parquet(delegators, "primary-delegator-stakes")}')
            """
        )
        connection.execute(f"CREATE VIEW supply AS SELECT * FROM read_parquet('{_parquet(supply, 'primary-staking-supply')}')")
        unmatched = connection.execute(
            "SELECT COUNT(*) FROM stakes s LEFT JOIN supply u USING (transaction_hash) WHERE u.transaction_hash IS NULL"
        ).fetchone()[0]
        cursor = connection.execute(
            """
            SELECT s.transaction_hash, s.accepted_at, s.tx_type, s.start_time,
                   date_diff('second', s.start_time, s.end_time), s.stake_navax, s.potential_reward_navax,
                   u.previous_block_supply_navax, u.block_supply_navax, u.in_block_prior_delta_navax, u.in_block_total_delta_navax
            FROM stakes s JOIN supply u USING (transaction_hash)
            ORDER BY s.accepted_at, s.transaction_hash
            """
        )
        regimes: dict[str, dict[str, Any]] = {}
        totals = {
            "rows": 0, "without_supply_context": 0, "without_potential_reward": 0,
            "immediate_rows": 0, "immediate_matched": 0, "immediate_mismatched": 0,
            "pending_rows": 0, "pending_matched": 0, "pending_mismatched": 0,
        }
        first_mismatch = last_mismatch = None
        while batch := cursor.fetchmany(FETCH_SIZE):
            for (hash_, accepted_at, tx_type, start_time, duration, stake, potential, previous, block, prior, total) in batch:
                totals["rows"] += 1
                regime = upgrades.regime(accepted_at.replace(tzinfo=timezone.utc))
                bucket = regimes.setdefault(regime, {
                    "rows": 0, "evaluated": 0,
                    "immediate_matched": 0, "immediate_mismatched": 0, "pending_matched": 0, "pending_mismatched": 0,
                    "candidate_matches": {name: 0 for name in SUPPLY_CANDIDATES},
                    "first_immediate_mismatch": None, "last_immediate_mismatch": None,
                })
                bucket["rows"] += 1
                if previous is None or block is None:
                    totals["without_supply_context"] += 1
                    continue
                if potential is None:
                    totals["without_potential_reward"] += 1
                    continue
                candidates = {
                    "supply_before": previous + prior,
                    "previous_block": previous,
                    "block_before_later": block - (total - prior),
                    "block_after": block,
                }
                computed: dict[int, int | None] = {}
                for name, value in candidates.items():
                    if value not in computed:
                        try:
                            computed[value] = primary_network_reward(start_time.replace(tzinfo=timezone.utc), duration, stake, value, config, upgrades)
                        except ModelError:
                            computed[value] = None
                    if computed[value] == potential:
                        bucket["candidate_matches"][name] += 1
                bucket["evaluated"] += 1
                kind = "pending" if start_time > accepted_at else "immediate"
                totals[f"{kind}_rows"] += 1
                if computed[candidates["supply_before"]] == potential:
                    bucket[f"{kind}_matched"] += 1
                    totals[f"{kind}_matched"] += 1
                else:
                    bucket[f"{kind}_mismatched"] += 1
                    totals[f"{kind}_mismatched"] += 1
                    if kind == "immediate":
                        stamp = accepted_at.isoformat() + "Z"
                        bucket["first_immediate_mismatch"] = bucket["first_immediate_mismatch"] or stamp
                        bucket["last_immediate_mismatch"] = stamp
                        first_mismatch = first_mismatch or stamp
                        last_mismatch = stamp
    finally:
        connection.close()
    findings: list[str] = []
    if unmatched:
        findings.append(f"{unmatched} staking rows have no supply context row")
    if totals["immediate_mismatched"]:
        affected = sorted(name for name, bucket in regimes.items() if bucket["immediate_mismatched"])
        findings.append(
            f"{totals['immediate_mismatched']} of {totals['immediate_rows']} rows starting at acceptance do not reproduce "
            f"potential_reward_navax from supply_before (regimes {', '.join(affected)}; {first_mismatch} to {last_mismatch})"
        )
    if totals["pending_mismatched"]:
        findings.append(
            f"{totals['pending_mismatched']} of {totals['pending_rows']} rows starting after acceptance are not reproducible "
            "from the acceptance-block supply because the protocol computed their reward at the start time"
        )
    for name, bucket in regimes.items():
        best = max(bucket["candidate_matches"], key=bucket["candidate_matches"].get)
        bucket["best_candidate"] = best if bucket["evaluated"] else None
    order = ["genesis", *(item.name for item in upgrades.upgrades)]
    ordered = {name: regimes[name] for name in order if name in regimes}
    return {
        "status": "pass" if not findings else "attention",
        "checked": ["supply context coverage", "potential reward reproduction"],
        "candidates": SUPPLY_CANDIDATES,
        "summary": {**totals, "unmatched_supply_rows": unmatched},
        "regimes": ordered,
        "findings": findings,
    }
