"""The built runs the behaviour package reads, loaded once into pandas frames cut at ``observed_through``.

Every frame holds only what was known by ``observed_through``: a staking period appears if it was accepted by then,
and a daily series row appears if its date is before it. The default is the start of the validation lockbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from .. import datasets

# The data from this instant on is held back to test the model once. Naive UTC, as the staking-period log stores it.
LOCKBOX_START = pd.Timestamp("2025-11-19 16:00:00")

# The largest delegator by count. Attributed to BENQI as an inference (data/operator-attributions.json, OA4), so
# features and labels call it the largest delegator, and only a page that cites that attribution may name it.
LARGEST_DELEGATOR = "avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy"

PERIODS = "derived.staking-periods"
VALIDATOR_STAKES = "derived.seamed-validator-stakes"
DELEGATOR_STAKES = "derived.seamed-delegator-stakes"
LEDGER = "derived.avax-monetary-daily"
PRICE = "binance.avax-usdt-daily"
TBILL = "fred.tbill-3m-daily"
OPERATORS = "derived.operators"

# The runs a result names. A caller can pass other runs, and the receipt records whichever were read.
RUNS = {
    PERIODS: "staking-periods-2026-10-01",
    VALIDATOR_STAKES: "seamed-validator-stakes-2026-10-01",
    DELEGATOR_STAKES: "seamed-delegator-stakes-2026-10-01",
    LEDGER: "avax-monetary-daily-2026-10-01",
    PRICE: "binance-avax-daily-2026-09-26",
    TBILL: "tbill-3m-daily-2026-09-29",
    OPERATORS: "operators-2026-10-01",
}

WEI_PER_AVAX = 10**18


@dataclass
class Inputs:
    """Validator periods, delegation totals per validator period, and daily market and monetary series."""

    periods: pd.DataFrame
    delegations: pd.DataFrame
    daily: pd.DataFrame
    nodes: pd.DataFrame
    observed_through: pd.Timestamp
    runs: dict[str, str] = field(default_factory=dict)

    def receipt(self) -> dict[str, Any]:
        return {"observed_through": str(self.observed_through), "runs": dict(sorted(self.runs.items())),
                "validator_periods": len(self.periods), "validator_periods_with_delegations": len(self.delegations),
                "daily_rows": len(self.daily)}


def check_cutoff(observed_through: Any, allow_lockbox: bool = False) -> pd.Timestamp:
    cutoff = pd.Timestamp(observed_through)
    if cutoff.tzinfo is not None:
        cutoff = cutoff.tz_convert("UTC").tz_localize(None)
    if cutoff > LOCKBOX_START and not allow_lockbox:
        raise ValueError(f"observed_through {cutoff} reaches into the validation lockbox, which starts {LOCKBOX_START} UTC;"
                         " pass allow_lockbox=True only for the one scoring run")
    return cutoff


def _paths(runs: dict[str, str], root: Path | None) -> dict[str, str]:
    return {dataset_id: str(datasets.parquet_path(dataset_id, run, root=root)) for dataset_id, run in runs.items()}


def load(runs: dict[str, str] | None = None, observed_through: Any = LOCKBOX_START, root: Path | None = None,
         allow_lockbox: bool = False) -> Inputs:
    runs = {**RUNS, **(runs or {})}
    cutoff = check_cutoff(observed_through, allow_lockbox)
    paths = _paths(runs, root)
    con = duckdb.connect()
    con.execute("SET threads TO 1")
    cut = f"TIMESTAMP '{cutoff}'"
    periods = con.sql(f"""
        SELECT p.transaction_hash, p.node_id, p.accepted_at, p.start_time, p.end_time, p.duration_days, p.stake_avax,
               p.delegation_fee_rate AS fee_rate, p.potential_reward_avax, p.rewarded, p.regime, p.start_kind,
               v.reward_address
        FROM '{paths[PERIODS]}' p
        LEFT JOIN '{paths[VALIDATOR_STAKES]}' v USING (transaction_hash)
        WHERE p.role = 'validator' AND p.accepted_at < {cut}
        ORDER BY p.node_id, p.start_time, p.transaction_hash""").df()
    # A delegation's reward is known when it ends. Delegations still running at the cut count toward stake attracted,
    # not toward rewards.
    delegations = con.sql(f"""
        SELECT p.validator_transaction_hash AS transaction_hash,
               count(*) AS delegations,
               count(DISTINCT s.delegator_address) AS delegators,
               sum(p.stake_avax) AS delegated_avax,
               sum(CASE WHEN s.delegator_address = '{LARGEST_DELEGATOR}' THEN p.stake_avax ELSE 0 END) AS largest_delegator_avax,
               median(p.stake_avax) AS median_delegation_avax,
               max(p.stake_avax) AS max_delegation_avax,
               sum(CASE WHEN p.end_time < {cut} AND p.rewarded THEN p.potential_reward_avax ELSE 0 END)
                   AS delegator_gross_reward_avax
        FROM '{paths[PERIODS]}' p
        LEFT JOIN '{paths[DELEGATOR_STAKES]}' s USING (transaction_hash)
        WHERE p.role = 'delegator' AND p.accepted_at < {cut}
        GROUP BY 1""").df()
    daily = con.sql(f"""
        WITH ledger AS (
            SELECT date_utc AS date,
                   CAST(total_supply_close_wei AS DOUBLE) / {WEI_PER_AVAX} AS supply_avax,
                   CAST(active_validator_stake_wei AS DOUBLE) / {WEI_PER_AVAX} AS validator_stake_avax,
                   CAST(active_delegated_stake_wei AS DOUBLE) / {WEI_PER_AVAX} AS delegated_stake_avax,
                   active_validators
            FROM '{paths[LEDGER]}'),
        price AS (SELECT observation_date AS date, close_usdt AS price_usd, realized_volatility_30d AS volatility_30d
                  FROM '{paths[PRICE]}'),
        tbill AS (SELECT CAST(date_utc AS DATE) AS date, discount_rate_pct AS tbill_pct FROM '{paths[TBILL]}')
        SELECT ledger.*, price.price_usd, price.volatility_30d, tbill.tbill_pct
        FROM ledger LEFT JOIN price USING (date) LEFT JOIN tbill USING (date)
        WHERE ledger.date < CAST({cut} AS DATE)
        ORDER BY date""").df()
    daily["date"] = pd.to_datetime(daily["date"])
    daily["tbill_pct"] = daily["tbill_pct"].ffill()
    # Named operators carry the evidence for their label in the attribution file. The label is a fixed property of the
    # node, used to report results with and without them and to group folds, never as a feature.
    nodes = con.sql(f"""SELECT node_id, named_agent FROM '{paths[OPERATORS]}'""").df().set_index("node_id")
    return Inputs(periods=periods, delegations=delegations, daily=daily, nodes=nodes, observed_through=cutoff,
                  runs=runs)
