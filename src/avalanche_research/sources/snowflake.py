"""Avalanche Snowflake share capture, transformation, and validation."""

from __future__ import annotations

import gzip
import json
import os
import shutil
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Callable

import duckdb

from .. import __version__
from ..core.catalog import (
    DATA_DIR, DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256, source,
)


SOURCE_ID = "avalanche-snowflake"
CONNECTION_VARIABLE = "AVALANCHE_SNOWFLAKE_CONNECTION"
DEFAULT_CONNECTION = "avalanche"
QUERY_TAG = "avalanche-phase-ii-research"
GENESIS_DATE = "2020-09-10"
C_CHAIN_FIRST_DATE = "2020-09-23"
NAVAX_PER_AVAX = 1_000_000_000
FEE_SHARES_PER_UNIT = 1_000_000
VALIDATOR_TYPES = ("AddValidatorTx", "AddPermissionlessValidatorTx")
DELEGATOR_TYPES = ("AddDelegatorTx", "AddPermissionlessDelegatorTx")
STAKING_TYPES = (*VALIDATOR_TYPES, *DELEGATOR_TYPES)
REWARD_TYPE = "RewardValidatorTx"
DURATION_DAYS = (14, 365)
VALIDATOR_STAKE_NAVAX = (2_000 * NAVAX_PER_AVAX, 3_000_000 * NAVAX_PER_AVAX)
DELEGATOR_STAKE_NAVAX = (25 * NAVAX_PER_AVAX, 3_000_000 * NAVAX_PER_AVAX)
FEE_SHARES = (20_000, FEE_SHARES_PER_UNIT)
GENESIS_SUPPLY_NAVAX = 360_000_000 * NAVAX_PER_AVAX
SUPPLY_CAP_NAVAX = 720_000_000 * NAVAX_PER_AVAX
SESSION_SQL = "SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_VERSION()"
FETCH_SIZE = 10_000


@dataclass(frozen=True)
class DatasetSpec:
    """One Snowflake dataset: its capture columns, typed table, and SQL checks.

    validity_sql counts rows that make the capture unusable; any count raises.
    check_sql counts rows that fail a domain check; any count becomes a finding.
    Both run over the typed ``rows`` table; check_params binds the ``?`` placeholders from the capture window.
    """

    dataset_id: str
    query_id: str
    tx_types: tuple[str, ...]
    raw_types: dict[str, str]
    table_columns: dict[str, str]
    transform_sql: str
    validity_sql: str
    validity_labels: tuple[str, ...]
    check_names: tuple[str, ...]
    check_sql: str
    check_labels: tuple[str, ...]
    check_params: Callable[[dict[str, str]], list[Any]]
    summary_sql: str
    summary_keys: tuple[str, ...]


def _avax_range(bounds: tuple[int, int]) -> str:
    return f"{bounds[0] // NAVAX_PER_AVAX:,} to {bounds[1] // NAVAX_PER_AVAX:,} AVAX"


_COMMON_RAW = {
    "transaction_hash": "VARCHAR",
    "accepted_at": "TIMESTAMP",
    "block_height": "BIGINT",
    "tx_type": "VARCHAR",
    "node_id": "VARCHAR",
}
_COMMON_TAIL_RAW = {
    "start_time": "TIMESTAMP",
    "end_time": "TIMESTAMP",
    "stake_navax": "BIGINT",
    "potential_reward_navax": "BIGINT",
    "rewarded": "BOOLEAN",
    "staked_utxo_count": "INTEGER",
    "utxo_stake_navax": "BIGINT",
}
_STAKE_VALIDITY_SQL = """
    COUNT_IF(transaction_hash IS NULL OR transaction_hash = '' OR node_id IS NULL OR node_id = ''
             OR accepted_at IS NULL OR start_time IS NULL OR end_time IS NULL OR block_height IS NULL
             OR stake_navax IS NULL OR staked_utxo_count IS NULL),
    COUNT_IF(tx_type IS NULL OR tx_type NOT IN (?, ?)),
    COUNT_IF(stake_navax < 0 OR potential_reward_navax < 0 OR staked_utxo_count < 0 OR utxo_stake_navax < 0)"""
_STAKE_VALIDITY_LABELS = ("miss a required field", "have an unexpected transaction type", "carry a negative amount")
_STAKE_CHECK_NAMES = (
    "unique transaction hashes", "acceptance window", "time ordering", "duration bounds", "stake bounds",
    "staked-UTXO reconciliation",
)
_STAKE_CHECK_SQL = """
    COUNT(*) - COUNT(DISTINCT transaction_hash),
    COUNT_IF(accepted_at::DATE < ?::DATE OR accepted_at::DATE >= ?::DATE),
    COUNT_IF(start_time < accepted_at OR end_time <= start_time),
    COUNT_IF(duration_days < ? OR duration_days > ?),
    COUNT_IF(stake_navax < ? OR stake_navax > ?),
    COUNT_IF(utxo_stake_navax IS NOT NULL AND utxo_stake_navax <> stake_navax)"""
_STAKE_CHECK_LABELS = (
    "repeat a transaction hash",
    "were accepted outside the requested window",
    "start before acceptance or end before start",
    "have a duration outside 14 to 365 days",
    "have a stake outside {stake}",
    "have staked UTXOs that do not sum to the declared stake",
)
_COMMON_SUMMARY_SQL = """
    COUNT(*), MIN(accepted_at), MAX(accepted_at), COUNT_IF(tx_type = ?), COUNT_IF(tx_type = ?), COUNT(DISTINCT node_id),
    COUNT_IF(staked_utxo_count = 0), COUNT_IF(rewarded IS NULL), COUNT_IF(potential_reward_navax IS NULL)"""
_COMMON_SUMMARY_KEYS = (
    "rows", "accepted_from", "accepted_to", "rows_by_tx_type", "rows_by_tx_type", "distinct_node_ids",
    "rows_without_staked_utxo", "rows_without_reward_status", "rows_without_potential_reward",
)

VALIDATOR_STAKES = DatasetSpec(
    dataset_id="snowflake.primary-validator-stakes",
    query_id="primary-validator-stakes",
    tx_types=VALIDATOR_TYPES,
    raw_types={
        **_COMMON_RAW,
        "start_time": "TIMESTAMP",
        "end_time": "TIMESTAMP",
        "stake_navax": "BIGINT",
        "delegation_fee_shares": "INTEGER",
        "potential_reward_navax": "BIGINT",
        "rewarded": "BOOLEAN",
        "reward_addresses": "VARCHAR",
        "reward_address": "VARCHAR",
        "reward_address_count": "INTEGER",
        "staked_utxo_count": "INTEGER",
        "utxo_stake_navax": "BIGINT",
    },
    table_columns={
        **_COMMON_RAW,
        "start_time": "TIMESTAMP",
        "end_time": "TIMESTAMP",
        "duration_days": "DOUBLE",
        "stake_navax": "BIGINT",
        "stake_avax": "DOUBLE",
        "delegation_fee_shares": "INTEGER",
        "delegation_fee_rate": "DOUBLE",
        "potential_reward_navax": "BIGINT",
        "potential_reward_avax": "DOUBLE",
        "rewarded": "BOOLEAN",
        "reward_addresses": "VARCHAR",
        "reward_address": "VARCHAR",
        "reward_address_count": "INTEGER",
        "staked_utxo_count": "INTEGER",
        "utxo_stake_navax": "BIGINT",
    },
    transform_sql="""
        SELECT transaction_hash, accepted_at, block_height, tx_type, node_id, start_time, end_time,
               date_diff('second', start_time, end_time)::DOUBLE / 86400 AS duration_days,
               stake_navax, stake_navax::DOUBLE / 1e9 AS stake_avax,
               delegation_fee_shares, delegation_fee_shares::DOUBLE / 1e6 AS delegation_fee_rate,
               potential_reward_navax, potential_reward_navax::DOUBLE / 1e9 AS potential_reward_avax,
               rewarded, reward_addresses, reward_address, reward_address_count, staked_utxo_count, utxo_stake_navax
        FROM capture
        ORDER BY accepted_at, transaction_hash""",
    validity_sql=_STAKE_VALIDITY_SQL,
    validity_labels=_STAKE_VALIDITY_LABELS,
    check_names=(*_STAKE_CHECK_NAMES[:5], "delegation fee bounds", "reward address present", _STAKE_CHECK_NAMES[5]),
    check_sql=_STAKE_CHECK_SQL + """,
    COUNT_IF(delegation_fee_shares IS NULL OR delegation_fee_shares < ? OR delegation_fee_shares > ?),
    COUNT_IF(reward_address IS NULL OR reward_address_count < 1)""",
    check_labels=(
        *_STAKE_CHECK_LABELS[:5],
        "have a delegation fee outside 2% to 100%",
        "have no reward address",
        _STAKE_CHECK_LABELS[5],
    ),
    check_params=lambda window: [window["start"], window["end"], *DURATION_DAYS, *VALIDATOR_STAKE_NAVAX, *FEE_SHARES],
    summary_sql=_COMMON_SUMMARY_SQL,
    summary_keys=_COMMON_SUMMARY_KEYS,
)

DELEGATOR_STAKES = DatasetSpec(
    dataset_id="snowflake.primary-delegator-stakes",
    query_id="primary-delegator-stakes",
    tx_types=DELEGATOR_TYPES,
    raw_types={
        **_COMMON_RAW,
        "validator_transaction_hash": "VARCHAR",
        "delegator_address": "VARCHAR",
        "delegator_address_count": "INTEGER",
        **_COMMON_TAIL_RAW,
    },
    table_columns={
        **_COMMON_RAW,
        "validator_transaction_hash": "VARCHAR",
        "delegator_address": "VARCHAR",
        "delegator_address_count": "INTEGER",
        "start_time": "TIMESTAMP",
        "end_time": "TIMESTAMP",
        "duration_days": "DOUBLE",
        "stake_navax": "BIGINT",
        "stake_avax": "DOUBLE",
        "potential_reward_navax": "BIGINT",
        "potential_reward_avax": "DOUBLE",
        "rewarded": "BOOLEAN",
        "staked_utxo_count": "INTEGER",
        "utxo_stake_navax": "BIGINT",
    },
    transform_sql="""
        SELECT transaction_hash, accepted_at, block_height, tx_type, node_id, validator_transaction_hash,
               delegator_address, delegator_address_count, start_time, end_time,
               date_diff('second', start_time, end_time)::DOUBLE / 86400 AS duration_days,
               stake_navax, stake_navax::DOUBLE / 1e9 AS stake_avax,
               potential_reward_navax, potential_reward_navax::DOUBLE / 1e9 AS potential_reward_avax,
               rewarded, staked_utxo_count, utxo_stake_navax
        FROM capture
        ORDER BY accepted_at, transaction_hash""",
    validity_sql=_STAKE_VALIDITY_SQL,
    validity_labels=_STAKE_VALIDITY_LABELS,
    check_names=(*_STAKE_CHECK_NAMES, "validator period containment"),
    check_sql=_STAKE_CHECK_SQL + """,
    COUNT_IF(validator_transaction_hash IS NULL)""",
    check_labels=(*_STAKE_CHECK_LABELS, "fall outside every validator staking period on their node"),
    check_params=lambda window: [window["start"], window["end"], *DURATION_DAYS, *DELEGATOR_STAKE_NAVAX],
    summary_sql=_COMMON_SUMMARY_SQL + """,
    COUNT(DISTINCT delegator_address), COUNT_IF(delegator_address IS NULL), COUNT_IF(delegator_address_count > 1)""",
    summary_keys=(
        *_COMMON_SUMMARY_KEYS,
        "distinct_delegator_addresses", "rows_without_delegator_address", "rows_with_several_delegator_addresses",
    ),
)

STAKING_REWARDS = DatasetSpec(
    dataset_id="snowflake.primary-staking-rewards",
    query_id="primary-staking-rewards",
    tx_types=STAKING_TYPES,
    raw_types={
        "reward_transaction_hash": "VARCHAR",
        "rewarded_at": "TIMESTAMP",
        "block_height": "BIGINT",
        "staking_transaction_hash": "VARCHAR",
        "staking_tx_type": "VARCHAR",
        "node_id": "VARCHAR",
        "period_start_time": "TIMESTAMP",
        "period_end_time": "TIMESTAMP",
        "rewarded": "BOOLEAN",
        "potential_reward_navax": "BIGINT",
        "realized_reward_navax": "BIGINT",
        "reward_utxo_count": "INTEGER",
    },
    table_columns={
        "reward_transaction_hash": "VARCHAR",
        "rewarded_at": "TIMESTAMP",
        "block_height": "BIGINT",
        "staking_transaction_hash": "VARCHAR",
        "staking_tx_type": "VARCHAR",
        "node_id": "VARCHAR",
        "period_start_time": "TIMESTAMP",
        "period_end_time": "TIMESTAMP",
        "rewarded": "BOOLEAN",
        "potential_reward_navax": "BIGINT",
        "potential_reward_avax": "DOUBLE",
        "realized_reward_navax": "BIGINT",
        "realized_reward_avax": "DOUBLE",
        "fee_transfer_navax": "BIGINT",
        "fee_transfer_avax": "DOUBLE",
        "reward_utxo_count": "INTEGER",
    },
    transform_sql="""
        SELECT reward_transaction_hash, rewarded_at, block_height, staking_transaction_hash, staking_tx_type, node_id,
               period_start_time, period_end_time, rewarded,
               potential_reward_navax, potential_reward_navax::DOUBLE / 1e9 AS potential_reward_avax,
               realized_reward_navax, realized_reward_navax::DOUBLE / 1e9 AS realized_reward_avax,
               realized_reward_navax - potential_reward_navax AS fee_transfer_navax,
               (realized_reward_navax - potential_reward_navax)::DOUBLE / 1e9 AS fee_transfer_avax,
               reward_utxo_count
        FROM capture
        ORDER BY rewarded_at, reward_transaction_hash""",
    validity_sql="""
    COUNT_IF(reward_transaction_hash IS NULL OR reward_transaction_hash = '' OR rewarded_at IS NULL OR block_height IS NULL
             OR staking_transaction_hash IS NULL OR staking_transaction_hash = '' OR realized_reward_navax IS NULL
             OR reward_utxo_count IS NULL),
    COUNT_IF(staking_tx_type IS NOT NULL AND staking_tx_type NOT IN (?, ?, ?, ?)),
    COUNT_IF(realized_reward_navax < 0 OR potential_reward_navax < 0 OR reward_utxo_count < 0)""",
    validity_labels=("miss a required field", "have an unexpected staking transaction type", "carry a negative amount"),
    check_names=(
        "unique reward and staking hashes", "reward window", "staking period link", "reward timing",
        "reward status agreement", "validator fee direction", "delegator fee direction",
    ),
    check_sql="""
    (COUNT(*) - COUNT(DISTINCT reward_transaction_hash)) + (COUNT(*) - COUNT(DISTINCT staking_transaction_hash)),
    COUNT_IF(rewarded_at::DATE < ?::DATE OR rewarded_at::DATE >= ?::DATE),
    COUNT_IF(staking_tx_type IS NULL),
    COUNT_IF(period_end_time IS NOT NULL AND (rewarded_at < period_end_time OR rewarded_at > period_end_time + INTERVAL 1 DAY)),
    COUNT_IF((rewarded = TRUE AND reward_utxo_count > 0 AND realized_reward_navax = 0)
             OR (rewarded = FALSE AND staking_tx_type IN (?, ?) AND realized_reward_navax > 0)
             OR (rewarded = FALSE AND realized_reward_navax > potential_reward_navax)),
    COUNT_IF(staking_tx_type IN (?, ?) AND rewarded = TRUE AND realized_reward_navax < potential_reward_navax),
    COUNT_IF(staking_tx_type IN (?, ?) AND realized_reward_navax > potential_reward_navax)""",
    check_labels=(
        "repeat a reward or staking transaction hash",
        "were rewarded outside the requested window",
        "have no Primary Network staking period",
        "were rewarded before the period end or more than a day after it",
        "disagree between the rewarded flag and the paid amount",
        "are rewarded validator periods paid less than the potential reward",
        "are delegator periods paid more than the potential reward",
    ),
    check_params=lambda window: [window["start"], window["end"], *DELEGATOR_TYPES, *VALIDATOR_TYPES, *DELEGATOR_TYPES],
    summary_sql="""
    COUNT(*), MIN(rewarded_at), MAX(rewarded_at),
    COUNT_IF(staking_tx_type = ?), COUNT_IF(staking_tx_type = ?), COUNT_IF(staking_tx_type = ?), COUNT_IF(staking_tx_type = ?),
    COUNT(DISTINCT node_id), COUNT_IF(rewarded = TRUE), COUNT_IF(rewarded = FALSE), COUNT_IF(rewarded IS NULL),
    COUNT_IF(reward_utxo_count = 0), COUNT_IF(rewarded = TRUE AND reward_utxo_count = 0),
    SUM(realized_reward_navax), SUM(fee_transfer_navax)""",
    summary_keys=(
        "rows", "rewarded_from", "rewarded_to", "rows_by_tx_type", "rows_by_tx_type", "rows_by_tx_type", "rows_by_tx_type",
        "distinct_node_ids", "rows_rewarded", "rows_unrewarded", "rows_without_reward_status",
        "rows_without_reward_utxo", "rows_rewarded_without_reward_utxo", "realized_reward_navax_total", "fee_transfer_navax_total",
    ),
)

STAKING_SUPPLY = DatasetSpec(
    dataset_id="snowflake.primary-staking-supply",
    query_id="primary-staking-supply",
    tx_types=STAKING_TYPES,
    raw_types={
        "transaction_hash": "VARCHAR",
        "accepted_at": "TIMESTAMP",
        "tx_type": "VARCHAR",
        "block_height": "BIGINT",
        "tx_block_position": "INTEGER",
        "previous_block_supply_navax": "BIGINT",
        "block_supply_navax": "BIGINT",
        "in_block_prior_delta_navax": "BIGINT",
        "in_block_total_delta_navax": "BIGINT",
    },
    table_columns={
        "transaction_hash": "VARCHAR",
        "accepted_at": "TIMESTAMP",
        "tx_type": "VARCHAR",
        "block_height": "BIGINT",
        "tx_block_position": "INTEGER",
        "previous_block_supply_navax": "BIGINT",
        "block_supply_navax": "BIGINT",
        "in_block_prior_delta_navax": "BIGINT",
        "in_block_total_delta_navax": "BIGINT",
        "supply_before_navax": "BIGINT",
    },
    transform_sql="""
        SELECT transaction_hash, accepted_at, tx_type, block_height, tx_block_position,
               previous_block_supply_navax, block_supply_navax, in_block_prior_delta_navax, in_block_total_delta_navax,
               previous_block_supply_navax + in_block_prior_delta_navax AS supply_before_navax
        FROM capture
        ORDER BY accepted_at, transaction_hash""",
    validity_sql="""
    COUNT_IF(transaction_hash IS NULL OR transaction_hash = '' OR accepted_at IS NULL OR block_height IS NULL),
    COUNT_IF(tx_type IS NULL OR tx_type NOT IN (?, ?, ?, ?)),
    COUNT_IF(previous_block_supply_navax < 0 OR block_supply_navax < 0)""",
    validity_labels=("miss a required field", "have an unexpected transaction type", "carry a negative supply"),
    check_names=("unique transaction hashes", "acceptance window", "supply bounds", "block position"),
    check_sql="""
    COUNT(*) - COUNT(DISTINCT transaction_hash),
    COUNT_IF(accepted_at::DATE < ?::DATE OR accepted_at::DATE >= ?::DATE),
    COUNT_IF(supply_before_navax < ? OR supply_before_navax > ? OR block_supply_navax > ?),
    COUNT_IF(block_height >= 0 AND tx_block_position IS NULL)""",
    check_labels=(
        "repeat a transaction hash",
        "were accepted outside the requested window",
        "have a supply outside the genesis supply and the 720,000,000 AVAX cap",
        "lack a block position",
    ),
    check_params=lambda window: [window["start"], window["end"], GENESIS_SUPPLY_NAVAX, SUPPLY_CAP_NAVAX, SUPPLY_CAP_NAVAX],
    summary_sql="""
    COUNT(*), MIN(accepted_at), MAX(accepted_at),
    COUNT_IF(tx_type = ?), COUNT_IF(tx_type = ?), COUNT_IF(tx_type = ?), COUNT_IF(tx_type = ?),
    COUNT_IF(block_height < 0), COUNT_IF(block_height >= 0 AND (previous_block_supply_navax IS NULL OR block_supply_navax IS NULL)),
    COUNT_IF(in_block_prior_delta_navax <> 0),
    COUNT_IF(block_height >= 0 AND block_supply_navax - previous_block_supply_navax <> in_block_total_delta_navax),
    COUNT_IF(block_height >= 0 AND previous_block_supply_navax > block_supply_navax + in_block_total_delta_navax),
    MIN(supply_before_navax), MAX(supply_before_navax)""",
    summary_keys=(
        "rows", "accepted_from", "accepted_to", "rows_by_tx_type", "rows_by_tx_type", "rows_by_tx_type", "rows_by_tx_type",
        "genesis_rows", "rows_without_block_supply", "rows_after_earlier_supply_changes_in_block",
        "rows_in_blocks_where_supply_change_differs_from_staking_deltas", "rows_in_blocks_where_supply_falls_beyond_removals",
        "supply_before_navax_min", "supply_before_navax_max",
    ),
)

PRIMARY_BURN_EVENTS = DatasetSpec(
    dataset_id="snowflake.primary-burn-events",
    query_id="primary-burn-events",
    tx_types=(),
    raw_types={
        "chain": "VARCHAR", "transaction_hash": "VARCHAR", "accepted_at": "TIMESTAMP",
        "block_height": "BIGINT", "tx_type": "VARCHAR", "burned_navax": "BIGINT", "fee_navax": "BIGINT",
    },
    table_columns={
        "chain": "VARCHAR", "transaction_hash": "VARCHAR", "accepted_at": "TIMESTAMP",
        "block_height": "BIGINT", "tx_type": "VARCHAR", "burned_navax": "BIGINT", "fee_navax": "BIGINT",
    },
    transform_sql="""
        SELECT chain, transaction_hash, accepted_at, block_height, tx_type,
               CASE WHEN burned_navax IS NULL AND chain = 'P'
                         AND tx_type IN ('AdvanceTimeTx', 'RewardValidatorTx')
                    THEN 0 ELSE burned_navax END AS burned_navax,
               fee_navax
        FROM capture
        ORDER BY accepted_at, chain, transaction_hash""",
    validity_sql="""
        COUNT_IF(chain NOT IN ('P', 'X') OR chain IS NULL OR transaction_hash IS NULL
                 OR transaction_hash = '' OR accepted_at IS NULL OR tx_type IS NULL),
        COUNT_IF(burned_navax < 0 OR fee_navax < 0)""",
    validity_labels=("miss an identity or have an unexpected chain", "have a negative amount"),
    check_names=("unique chain and transaction hashes", "acceptance window", "burn amounts available"),
    check_sql="""
        COUNT(*) - COUNT(DISTINCT chain || ':' || transaction_hash),
        COUNT_IF(accepted_at::DATE < ?::DATE OR accepted_at::DATE >= ?::DATE),
        COUNT_IF(burned_navax IS NULL)""",
    check_labels=("repeat a transaction on the same chain", "were accepted outside the requested window", "have no recorded burn"),
    check_params=lambda window: [window["start"], window["end"]],
    summary_sql="""
        COUNT(*), MIN(accepted_at), MAX(accepted_at),
        COUNT_IF(chain = 'P'), COUNT_IF(chain = 'X'),
        SUM(CASE WHEN chain = 'P' THEN burned_navax ELSE 0 END),
        SUM(CASE WHEN chain = 'X' THEN burned_navax ELSE 0 END),
        COUNT_IF(burned_navax IS NULL)""",
    summary_keys=(
        "rows", "accepted_from", "accepted_to", "p_transactions", "x_transactions",
        "p_burned_navax", "x_burned_navax", "unknown_burn_rows",
    ),
)

C_CHAIN_EVM_BURN_DAILY = DatasetSpec(
    dataset_id="snowflake.c-chain-evm-burn-daily",
    query_id="c-chain-evm-burn-daily",
    tx_types=(),
    raw_types={
        "date_utc": "DATE", "burned_wei": "DECIMAL(38,0)",
        "block_count": "BIGINT", "first_block": "BIGINT", "last_block": "BIGINT",
        "absent_blocks": "BIGINT", "short_blocks": "BIGINT", "short_block_transactions": "BIGINT",
        "previous_last_block": "BIGINT", "next_first_block": "BIGINT",
        "expected_receipts": "BIGINT", "receipt_rows": "BIGINT", "distinct_receipts": "BIGINT",
        "missing_fee_inputs": "BIGINT", "first_epoch": "BIGINT", "last_epoch": "BIGINT",
    },
    table_columns={
        "date_utc": "DATE", "burned_wei": "DECIMAL(38,0)",
        "block_count": "BIGINT", "first_block": "BIGINT", "last_block": "BIGINT",
        "absent_blocks": "BIGINT", "short_blocks": "BIGINT", "short_block_transactions": "BIGINT",
        "previous_last_block": "BIGINT", "next_first_block": "BIGINT",
        "expected_receipts": "BIGINT", "receipt_rows": "BIGINT", "distinct_receipts": "BIGINT",
        "missing_fee_inputs": "BIGINT", "first_epoch": "BIGINT", "last_epoch": "BIGINT",
    },
    transform_sql="SELECT * FROM capture ORDER BY date_utc",
    validity_sql="""
        COUNT_IF(date_utc IS NULL OR burned_wei IS NULL OR block_count IS NULL
                 OR first_block IS NULL OR last_block IS NULL OR expected_receipts IS NULL
                 OR absent_blocks IS NULL OR short_blocks IS NULL OR first_epoch IS NULL OR last_epoch IS NULL),
        COUNT_IF(burned_wei < 0 OR block_count < 0 OR expected_receipts < 0 OR absent_blocks < 0 OR short_blocks < 0
                 OR receipt_rows < 0 OR distinct_receipts < 0 OR missing_fee_inputs < 0)""",
    validity_labels=("miss a required daily field", "have a negative count or burn"),
    check_names=(
        "unique dates", "acceptance window", "calendar coverage", "block accounting",
        "consecutive days", "receipt accounting", "absent blocks", "short blocks", "repeated rows", "fee inputs", "block timestamps",
    ),
    check_sql="""
        COUNT(*) - COUNT(DISTINCT date_utc),
        COUNT_IF(date_utc < ?::DATE OR date_utc >= ?::DATE),
        date_diff('day', ?::DATE, ?::DATE) - COUNT(*),
        COUNT_IF(last_block - first_block + 1 <> block_count + absent_blocks),
        COUNT_IF((date_utc > ?::DATE
                  AND (previous_last_block IS NULL OR first_block <> previous_last_block + 1))
                 OR next_first_block IS NULL OR next_first_block <> last_block + 1),
        COUNT_IF(distinct_receipts + (short_block_transactions - (expected_receipts - distinct_receipts)) < 0 OR distinct_receipts > expected_receipts),
        COUNT_IF(absent_blocks > 0),
        COUNT_IF(short_blocks > 0),
        COUNT_IF(receipt_rows <> distinct_receipts),
        SUM(missing_fee_inputs),
        COUNT_IF(first_epoch < epoch(date_utc) OR last_epoch >= epoch(date_utc + INTERVAL 1 DAY))""",
    check_labels=(
        "repeat a UTC date", "are outside the requested UTC window", "calendar days are missing",
        "have blocks that are neither present nor counted absent", "do not connect to adjacent C block days",
        "have more distinct receipts than block transactions",
        "have absent C blocks, to read from the Data API block record", "have short C blocks, to read from the Data API block record",
        "have receipts loaded more than once, read once here", "receipts are missing gas used or effective gas price",
        "have block timestamps outside their UTC date",
    ),
    check_params=lambda window: [window["start"], window["end"], window["start"], window["end"], C_CHAIN_FIRST_DATE],
    summary_sql="""
        COUNT(*), MIN(date_utc), MAX(date_utc), SUM(burned_wei), SUM(block_count), SUM(absent_blocks), SUM(short_blocks),
        SUM(expected_receipts), SUM(distinct_receipts), SUM(receipt_rows - distinct_receipts), SUM(missing_fee_inputs),
        COUNT_IF(absent_blocks = 0 AND short_blocks = 0 AND missing_fee_inputs = 0)""",
    summary_keys=(
        "days", "first_date", "last_date", "burned_wei", "blocks", "absent_blocks", "short_blocks",
        "expected_receipts", "distinct_receipts", "repeated_receipt_rows", "missing_fee_inputs", "complete_days",
    ),
)

PRIMARY_BURN_DAILY = DatasetSpec(
    dataset_id="snowflake.primary-burn-daily",
    query_id="primary-burn-daily",
    tx_types=(),
    raw_types={
        "date_utc": "DATE", "chain": "VARCHAR", "transactions": "BIGINT", "burned_navax": "BIGINT",
        "recorded_transactions": "BIGINT", "system_transactions": "BIGINT", "genesis_transactions": "BIGINT",
        "utxo_derived_transactions": "BIGINT", "unresolved_transactions": "BIGINT", "unresolved_hashes": "VARCHAR",
        "l1_balance_deposited_navax": "BIGINT", "l1_validator_fees_navax": "BIGINT",
    },
    table_columns={
        "date_utc": "DATE", "chain": "VARCHAR", "transactions": "BIGINT", "burned_navax": "BIGINT",
        "recorded_transactions": "BIGINT", "system_transactions": "BIGINT", "genesis_transactions": "BIGINT",
        "utxo_derived_transactions": "BIGINT", "unresolved_transactions": "BIGINT", "unresolved_hashes": "VARCHAR",
        "l1_balance_deposited_navax": "BIGINT", "l1_validator_fees_navax": "BIGINT",
    },
    transform_sql="SELECT * REPLACE (nullif(unresolved_hashes, '') AS unresolved_hashes) FROM capture ORDER BY date_utc, chain",
    validity_sql="""
        COUNT_IF(date_utc IS NULL OR chain NOT IN ('P', 'X') OR chain IS NULL OR transactions IS NULL OR burned_navax IS NULL
                 OR l1_balance_deposited_navax IS NULL OR l1_validator_fees_navax IS NULL),
        COUNT_IF(burned_navax < 0 OR transactions < 0 OR l1_balance_deposited_navax < 0 OR l1_validator_fees_navax < 0)""",
    validity_labels=("miss a required daily field", "have a negative count or amount"),
    check_names=("unique dates and chains", "acceptance window", "calendar coverage", "transaction accounting", "unresolved burns", "X-Chain L1 columns"),
    check_sql="""
        COUNT(*) - COUNT(DISTINCT date_utc || chain),
        COUNT_IF(date_utc < ?::DATE OR date_utc >= ?::DATE),
        2 * date_diff('day', ?::DATE, ?::DATE) - COUNT(*),
        COUNT_IF(transactions <> recorded_transactions + system_transactions + genesis_transactions + utxo_derived_transactions + unresolved_transactions
                 OR unresolved_transactions <> coalesce(len(string_split(unresolved_hashes, ',')), 0)),
        COUNT_IF(unresolved_transactions > 0),
        COUNT_IF(chain = 'X' AND (system_transactions > 0 OR l1_balance_deposited_navax > 0 OR l1_validator_fees_navax > 0))""",
    check_labels=(
        "repeat a UTC date and chain", "are outside the requested UTC window", "date and chain rows are missing",
        "do not account for every transaction once", "carry unresolved burns to settle from the P-Chain node's transaction record",
        "are X-Chain rows with P-Chain system or L1 validator amounts",
    ),
    check_params=lambda window: [window["start"], window["end"], window["start"], window["end"]],
    summary_sql="""
        COUNT(*), MIN(date_utc), MAX(date_utc),
        SUM(transactions) FILTER (WHERE chain = 'P'), SUM(transactions) FILTER (WHERE chain = 'X'),
        SUM(burned_navax) FILTER (WHERE chain = 'P'), SUM(burned_navax) FILTER (WHERE chain = 'X'),
        SUM(l1_validator_fees_navax), SUM(l1_balance_deposited_navax),
        SUM(utxo_derived_transactions), SUM(genesis_transactions), SUM(unresolved_transactions)""",
    summary_keys=(
        "rows", "first_date", "last_date", "p_transactions", "x_transactions", "p_burned_navax", "x_burned_navax",
        "p_l1_validator_fees_navax", "p_l1_balance_deposited_navax", "utxo_derived_transactions", "genesis_transactions", "unresolved_transactions",
    ),
)

C_CHAIN_BLOCK_GAPS = DatasetSpec(
    dataset_id="snowflake.c-chain-block-gaps",
    query_id="c-chain-block-gaps",
    tx_types=(),
    raw_types={"block_height": "BIGINT", "kind": "VARCHAR", "date_utc": "DATE", "declared_transactions": "BIGINT", "distinct_receipts": "BIGINT"},
    table_columns={"block_height": "BIGINT", "kind": "VARCHAR", "date_utc": "DATE", "declared_transactions": "BIGINT", "distinct_receipts": "BIGINT"},
    transform_sql="SELECT * FROM capture ORDER BY block_height",
    validity_sql="""
        COUNT_IF(block_height IS NULL OR kind NOT IN ('absent', 'short') OR kind IS NULL OR date_utc IS NULL
                 OR (kind = 'short' AND (declared_transactions IS NULL OR distinct_receipts IS NULL))),
        COUNT_IF(block_height < 0 OR declared_transactions < 0 OR distinct_receipts < 0 OR distinct_receipts >= declared_transactions)""",
    validity_labels=("miss a required field or carry an unknown kind", "have a negative count or a short block that is not short"),
    check_names=("unique heights", "acceptance window"),
    check_sql="""
        COUNT(*) - COUNT(DISTINCT block_height),
        COUNT_IF(date_utc < ?::DATE OR date_utc >= ?::DATE)""",
    check_labels=("repeat a block height", "are outside the requested UTC window"),
    check_params=lambda window: [window["start"], window["end"]],
    summary_sql="""
        COUNT(*), COUNT_IF(kind = 'absent'), COUNT_IF(kind = 'short'), SUM(declared_transactions - distinct_receipts),
        COUNT(DISTINCT date_utc), MIN(date_utc), MAX(date_utc)""",
    summary_keys=("rows", "absent_blocks", "short_blocks", "missing_receipts", "days", "first_date", "last_date"),
)

SUBNET_TYPES = ("AddSubnetValidatorTx", "RemoveSubnetValidatorTx", "ConvertSubnetToL1Tx", "RegisterL1ValidatorTx",
                "DisableL1ValidatorTx")

SUBNET_VALIDATOR_TRANSACTIONS = DatasetSpec(
    dataset_id="snowflake.subnet-validator-transactions",
    query_id="subnet-validator-transactions",
    tx_types=(),
    raw_types={
        "tx_type": "VARCHAR", "transaction_hash": "VARCHAR", "accepted_at": "TIMESTAMP", "block_height": "BIGINT",
        "node_id": "VARCHAR", "subnet_id": "VARCHAR", "start_time": "TIMESTAMP", "end_time": "TIMESTAMP",
        "removal_time": "TIMESTAMP", "l1_validator_weight": "BIGINT",
    },
    table_columns={
        "tx_type": "VARCHAR", "transaction_hash": "VARCHAR", "accepted_at": "TIMESTAMP", "block_height": "BIGINT",
        "node_id": "VARCHAR", "subnet_id": "VARCHAR", "start_time": "TIMESTAMP", "end_time": "TIMESTAMP",
        "removal_time": "TIMESTAMP", "l1_validator_weight": "BIGINT",
    },
    transform_sql="SELECT * FROM capture ORDER BY accepted_at, transaction_hash, node_id",
    validity_sql=f"""
        COUNT_IF(tx_type IS NULL OR tx_type NOT IN ({", ".join(repr(t) for t in SUBNET_TYPES)})
                 OR transaction_hash IS NULL OR accepted_at IS NULL OR subnet_id IS NULL),
        COUNT_IF(tx_type <> 'RemoveSubnetValidatorTx' AND node_id IS NULL)""",
    validity_labels=("miss an identity or have an unexpected type", "add, convert, register, or disable without a node"),
    check_names=("unique transaction and node", "acceptance window", "Subnet periods ordered", "early removals inside their period"),
    check_sql="""
        COUNT(*) - COUNT(DISTINCT transaction_hash || ':' || COALESCE(node_id, '')),
        COUNT_IF(accepted_at::DATE < ?::DATE OR accepted_at::DATE >= ?::DATE),
        COUNT_IF(tx_type = 'AddSubnetValidatorTx' AND (start_time IS NULL OR end_time IS NULL OR end_time <= start_time)),
        COUNT_IF(removal_time IS NOT NULL AND (removal_time < start_time OR removal_time > end_time))""",
    check_labels=(
        "repeat a transaction and node", "were accepted outside the requested window",
        "are Subnet additions without an ordered period", "were removed outside their period",
    ),
    check_params=lambda window: [window["start"], window["end"]],
    summary_sql="""
        COUNT(*), MIN(accepted_at), MAX(accepted_at),
        COUNT_IF(tx_type = 'AddSubnetValidatorTx'), COUNT_IF(tx_type = 'RemoveSubnetValidatorTx'),
        COUNT(DISTINCT CASE WHEN tx_type = 'ConvertSubnetToL1Tx' THEN subnet_id END),
        COUNT_IF(tx_type = 'RegisterL1ValidatorTx'), COUNT_IF(tx_type = 'DisableL1ValidatorTx'),
        COUNT(DISTINCT node_id), COUNT(DISTINCT subnet_id)""",
    summary_keys=(
        "rows", "accepted_from", "accepted_to", "subnet_additions", "subnet_removals", "converted_subnets",
        "l1_registrations", "l1_disables", "nodes", "subnets",
    ),
)

SPECS = {spec.dataset_id: spec for spec in (
    VALIDATOR_STAKES, DELEGATOR_STAKES, STAKING_REWARDS, STAKING_SUPPLY,
    PRIMARY_BURN_EVENTS, C_CHAIN_EVM_BURN_DAILY, PRIMARY_BURN_DAILY, C_CHAIN_BLOCK_GAPS, SUBNET_VALIDATOR_TRANSACTIONS,
)}
DATASET_IDS = tuple(SPECS)
DATASET_ID = VALIDATOR_STAKES.dataset_id


def spec_for(dataset_id: str) -> DatasetSpec:
    try:
        return SPECS[dataset_id]
    except KeyError:
        raise DataError(f"unknown Snowflake dataset: {dataset_id}") from None


def connection_name() -> str:
    return os.environ.get(CONNECTION_VARIABLE, DEFAULT_CONNECTION)


def connect(name: str, timeout: float) -> Any:
    """Open a Snowflake connection through the connector's named-connection configuration."""
    try:
        import snowflake.connector
    except ImportError as error:
        raise DataError(
            "snowflake-connector-python is not installed; run: uv sync --locked --extra snowflake"
        ) from error
    try:
        return snowflake.connector.connect(
            connection_name=name,
            login_timeout=int(timeout),
            network_timeout=int(timeout),
            session_parameters={"QUERY_TAG": QUERY_TAG, "STATEMENT_TIMEOUT_IN_SECONDS": int(timeout)},
        )
    except snowflake.connector.errors.Error as error:
        raise DataError(f"Snowflake connection {name!r} failed: {error}") from error


def _connector_error(error: BaseException) -> bool:
    return type(error).__module__.startswith("snowflake.")


def query_definition(catalog: dict[str, Any], dataset_id: str) -> dict[str, Any]:
    spec = spec_for(dataset_id)
    definition = dataset(catalog, dataset_id)
    provider = source(catalog, definition["source_id"])
    if "queries" not in provider or definition.get("query_ids") != [spec.query_id]:
        raise DataError(f"dataset is not a Snowflake query dataset: {dataset_id}")
    return next(item for item in provider["queries"] if item["id"] == spec.query_id)


def read_sql(query: dict[str, Any]) -> str:
    try:
        return (DATA_DIR / query["sql"]).read_text(encoding="utf-8")
    except OSError as error:
        raise DataError(f"missing query text: {query['sql']}") from error


def resolve_parameters(parameters: dict[str, str] | None) -> dict[str, str]:
    values = dict(parameters or {})
    unknown = sorted(set(values) - {"start", "end"})
    if unknown:
        raise DataError(f"unknown parameters: {', '.join(unknown)}; expected start and end dates")
    today = datetime.now(timezone.utc).date()
    resolved = {"start": values.get("start", GENESIS_DATE), "end": values.get("end", (today + timedelta(days=1)).isoformat())}
    bounds: dict[str, date] = {}
    for key, text in resolved.items():
        try:
            bounds[key] = date.fromisoformat(text)
        except ValueError as error:
            raise DataError(f"{key} must be an ISO date (YYYY-MM-DD): {text}") from error
    if bounds["start"] >= bounds["end"]:
        raise DataError(f"start must precede end: {resolved['start']} >= {resolved['end']}")
    return {key: bounds[key].isoformat() for key in ("start", "end")}


def capture_preview(
    dataset_id: str,
    output: Path,
    parameters: dict[str, str] | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    spec = spec_for(dataset_id)
    query = query_definition(catalog, dataset_id)
    sql_text = read_sql(query)
    values = dict(parameters or {})
    if dataset_id == C_CHAIN_EVM_BURN_DAILY.dataset_id:
        values.setdefault("start", C_CHAIN_FIRST_DATE)
        values.setdefault("end", (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat())
    if dataset_id == C_CHAIN_BLOCK_GAPS.dataset_id:
        values.setdefault("start", C_CHAIN_FIRST_DATE)
    if dataset_id == PRIMARY_BURN_DAILY.dataset_id:
        # The last complete UTC day: today's row would change with every transaction accepted after the capture.
        values.setdefault("end", datetime.now(timezone.utc).date().isoformat())
    return {
        "dataset_id": dataset_id,
        "source_id": SOURCE_ID,
        "output": str(output),
        "connection": connection_name(),
        "query_id": spec.query_id,
        "sql": query["sql"],
        "sql_sha256": sha256(sql_text.encode()),
        "parameters": resolve_parameters(values),
        "writes": [f"raw/{spec.query_id}.sql", f"raw/{spec.query_id}.jsonl.gz", "capture.json"],
        "overwrite": False,
    }


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        spec = "seconds" if value.microsecond == 0 else "microseconds"
        return value.isoformat(timespec=spec) + "Z"
    if isinstance(value, date):
        return value.isoformat()
    raise DataError(f"unsupported value type from Snowflake: {type(value).__name__}")


def _session(connection: Any) -> dict[str, Any]:
    cursor = connection.cursor()
    try:
        cursor.execute(SESSION_SQL)
        role, warehouse, database, schema, version = cursor.fetchall()[0]
    finally:
        cursor.close()
    return {"role": role, "warehouse": warehouse, "database": database, "schema": schema, "server_version": version}


def capture(
    dataset_id: str,
    output: Path,
    timeout: float = 20,
    parameters: dict[str, str] | None = None,
    catalog: dict[str, Any] | None = None,
    connector: Callable[[str, float], Any] = connect,
) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    spec = spec_for(dataset_id)
    preview = capture_preview(dataset_id, output, parameters, catalog)
    sql_text = read_sql(query_definition(catalog, dataset_id))
    expected_columns = tuple(spec.raw_types)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        raw = temporary / "raw"
        raw.mkdir()
        sql_path = raw / f"{spec.query_id}.sql"
        rows_path = raw / f"{spec.query_id}.jsonl.gz"
        sql_path.write_text(sql_text, encoding="utf-8")
        started_at = now()
        connection = connector(preview["connection"], timeout)
        try:
            session = _session(connection)
            cursor = connection.cursor()
            try:
                cursor.execute(sql_text, preview["parameters"])
                columns = tuple(item[0].lower() for item in cursor.description)
                if columns != expected_columns:
                    raise DataError(f"query returned unexpected columns: {', '.join(columns)}")
                rows = 0
                with rows_path.open("wb") as file, gzip.GzipFile(fileobj=file, mode="wb", mtime=0) as handle:
                    while batch := cursor.fetchmany(FETCH_SIZE):
                        for record in batch:
                            values = dict(zip(columns, (_json_value(value) for value in record)))
                            handle.write((json.dumps(values, ensure_ascii=False, sort_keys=True) + "\n").encode())
                            rows += 1
                snowflake_query_id = cursor.sfqid
            finally:
                cursor.close()
        finally:
            connection.close()
        completed_at = now()
        body = rows_path.read_bytes()
        record = {
            "query_id": spec.query_id,
            "sql_path": f"raw/{sql_path.name}",
            "sql_sha256": preview["sql_sha256"],
            "parameters": preview["parameters"],
            "snowflake_query_id": snowflake_query_id,
            "started_at": started_at,
            "completed_at": completed_at,
            "columns": list(columns),
            "rows": rows,
            "path": f"raw/{rows_path.name}",
            "bytes": len(body),
            "sha256": sha256(body),
        }
        identity = sha256(canonical_bytes({"completed_at": completed_at, "queries": [record]}))
        receipt = {
            "schema_version": "snowflake-capture/v1",
            "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
            "dataset_id": dataset_id,
            "source_id": SOURCE_ID,
            "completed_at": completed_at,
            "contract_sha256": contract_hash(catalog, dataset_id),
            "tool": f"avalanche-research@{__version__}",
            "session": session,
            "queries": [record],
        }
        (temporary / "capture.json").write_bytes(canonical_bytes(receipt))
        os.replace(temporary, output)
    except Exception as error:
        shutil.rmtree(temporary, ignore_errors=True)
        if _connector_error(error):
            raise DataError(f"Snowflake query failed: {error}") from error
        raise
    return receipt


def read_capture(capture_dir: Path, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verify a capture's receipt, query text, and result hash, and return the receipt."""
    catalog = catalog or load_catalog()
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"invalid capture receipt: {error}") from error
    if receipt.get("schema_version") != "snowflake-capture/v1":
        raise DataError("unsupported capture receipt schema")
    spec = spec_for(receipt.get("dataset_id", ""))
    if receipt.get("contract_sha256") != contract_hash(catalog, spec.dataset_id):
        raise DataError("capture contract hash differs from the current data contract")
    if len(receipt.get("queries", [])) != 1 or receipt["queries"][0].get("query_id") != spec.query_id:
        raise DataError("capture does not contain the expected query")
    record = receipt["queries"][0]
    current_sql = read_sql(query_definition(catalog, spec.dataset_id))
    try:
        captured_sql = (capture_dir / record["sql_path"]).read_bytes()
        body = (capture_dir / record["path"]).read_bytes()
    except (OSError, KeyError) as error:
        raise DataError(f"missing captured query output: {error}") from error
    if sha256(captured_sql) != record.get("sql_sha256") or captured_sql != current_sql.encode():
        raise DataError("captured query text differs from the current data contract")
    if sha256(body) != record.get("sha256") or len(body) != record.get("bytes"):
        raise DataError(f"captured result hash or size differs: {record['path']}")
    if tuple(record.get("columns", ())) != tuple(spec.raw_types) or not isinstance(record.get("rows"), int):
        raise DataError("captured result columns differ from the data contract")
    return receipt


def load_capture(connection: Any, spec: DatasetSpec, capture_dir: Path, receipt: dict[str, Any]) -> None:
    """Read the compressed capture into DuckDB with the declared types and build the typed rows table."""
    record = receipt["queries"][0]
    declared = ", ".join(f"{name}: '{kind}'" for name, kind in spec.raw_types.items())
    typed = ", ".join(f"{name} {kind}" for name, kind in spec.table_columns.items())
    path = str(capture_dir / record["path"]).replace("'", "''")
    try:
        connection.execute(
            f"CREATE VIEW capture AS SELECT * FROM read_json('{path}', columns={{{declared}}}, format='newline_delimited')"
        )
        connection.execute(f"CREATE TABLE rows({typed})")
        connection.execute(f"INSERT INTO rows {spec.transform_sql}")
        count = connection.execute("SELECT COUNT(*) FROM rows").fetchone()[0]
    except duckdb.Error as error:
        raise DataError(f"captured rows do not match the declared types: {error}") from error
    if count != record["rows"]:
        raise DataError(f"captured result holds {count} rows, receipt declares {record['rows']}")
    invalid = connection.execute(f"SELECT {spec.validity_sql} FROM rows", list(spec.tx_types)).fetchone()
    for failed, label in zip(invalid, spec.validity_labels):
        if failed:
            raise DataError(f"{failed} captured rows {label}")


def summarize(connection: Any, spec: DatasetSpec) -> dict[str, Any]:
    record = connection.execute(f"SELECT {spec.summary_sql} FROM rows", list(spec.tx_types)).fetchone()
    summary: dict[str, Any] = {}
    for key, value in zip(spec.summary_keys, record):
        if key == "rows_by_tx_type":
            summary.setdefault(key, {})[spec.tx_types[len(summary[key])]] = value
        else:
            summary[key] = _json_value(value)
    return summary


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    catalog = load_catalog()
    spec = spec_for(dataset_id)
    query_definition(catalog, dataset_id)
    return {
        "dataset_id": dataset_id,
        "capture": str(capture_dir),
        "output": str(output),
        "writes": [f"{spec.query_id}.parquet", "build.json"],
        "overwrite": False,
    }


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    spec = spec_for(dataset_id)
    definition = dataset(catalog, dataset_id)
    query_definition(catalog, dataset_id)
    receipt = read_capture(capture_dir, catalog)
    if receipt["dataset_id"] != dataset_id:
        raise DataError(f"capture belongs to {receipt['dataset_id']}, not {dataset_id}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet_path = temporary / f"{spec.query_id}.parquet"
        connection = duckdb.connect()
        try:
            load_capture(connection, spec, capture_dir, receipt)
            connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection, spec)
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "snowflake-build/v1",
            "dataset_id": dataset_id,
            "dataset_schema": definition["fields"],
            "source_capture_id": receipt["capture_id"],
            "completed_at": now(),
            "tool": f"avalanche-research@{__version__}",
            "summary": summary,
            "outputs": [
                {"path": parquet_path.name, "bytes": parquet_path.stat().st_size, "sha256": sha256(parquet_path.read_bytes())},
            ],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return build_receipt


def read_parquet(path: Path, spec: DatasetSpec = VALIDATOR_STAKES) -> list[dict[str, Any]]:
    columns = list(spec.table_columns)
    connection = duckdb.connect()
    try:
        records = connection.execute(
            f"SELECT {', '.join(columns)} FROM read_parquet(?) ORDER BY {columns[1]}, {columns[0]}", [str(path)]
        ).fetchall()
    finally:
        connection.close()
    return [dict(zip(columns, (_json_value(value) for value in record))) for record in records]


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    if against is not None:
        raise DataError("this dataset has no reference dataset to check against")
    catalog = load_catalog()
    receipt = read_capture(capture_dir, catalog)
    spec = spec_for(receipt["dataset_id"])
    window = receipt["queries"][0]["parameters"]
    stake = _avax_range(VALIDATOR_STAKE_NAVAX if spec is VALIDATOR_STAKES else DELEGATOR_STAKE_NAVAX)
    findings: list[str] = []
    checked = ["capture hashes", "query text", "field types", *spec.check_names]
    connection = duckdb.connect()
    try:
        load_capture(connection, spec, capture_dir, receipt)
        counts = connection.execute(f"SELECT {spec.check_sql} FROM rows", spec.check_params(window)).fetchone()
        findings.extend(
            f"{failed} rows {label.format(stake=stake)}" for failed, label in zip(counts, spec.check_labels) if failed
        )
        summary = summarize(connection, spec)
        if dataset_dir is not None:
            checked.extend(["build hashes", "Parquet rows"])
            try:
                build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
                for item in build_receipt["outputs"]:
                    body = (dataset_dir / item["path"]).read_bytes()
                    if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                        findings.append(f"output hash or size differs: {item['path']}")
                parquet = str(dataset_dir / f"{spec.query_id}.parquet")
                schema = connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [parquet]).fetchall()
                if [(item[0], item[1]) for item in schema] != list(spec.table_columns.items()):
                    findings.append("Parquet schema differs from the dataset contract")
                else:
                    columns = ", ".join(spec.table_columns)
                    differing = connection.execute(
                        f"""
                        SELECT (SELECT COUNT(*) FROM (SELECT {columns} FROM rows EXCEPT ALL SELECT {columns} FROM read_parquet(?)))
                             + (SELECT COUNT(*) FROM (SELECT {columns} FROM read_parquet(?) EXCEPT ALL SELECT {columns} FROM rows))
                        """,
                        [parquet, parquet],
                    ).fetchone()[0]
                    if differing:
                        findings.append("Parquet rows differ from the captured inputs")
            except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
                findings.append(f"invalid dataset output: {error}")
    finally:
        connection.close()
    return {
        "dataset_id": receipt["dataset_id"],
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summary,
        "findings": findings,
    }
