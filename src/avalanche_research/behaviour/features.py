"""Point-in-time features of each decision event, and the registry that documents them.

Every feature is computed from what was known when the period ended: the period itself, the node's earlier periods,
the delegations it received, the reward address's earlier nodes, and the daily series up to the day before the end.
Daily values are read on the day before the end date so that no same-day value reaches a decision. The registry is the
contract: ``build`` returns exactly the registered columns, and a test checks that each family reads no later row.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd

from .inputs import Inputs

DAY = pd.Timedelta(days=1)


@dataclass(frozen=True)
class Feature:
    name: str
    family: str
    description: str
    source: str
    kind: str = "numeric"


REGISTRY: tuple[Feature, ...] = (
    # The period that ended.
    Feature("stake_log10", "period", "log10 of the period's stake, AVAX", "staking-periods.stake_avax"),
    Feature("duration_days", "period", "Length of the period, days", "staking-periods.duration_days"),
    Feature("fee_rate", "period", "Declared delegation fee, 0.02 to 1", "staking-periods.delegation_fee_rate"),
    Feature("failed", "period", "1 if the period earned no reward, the uptime rule", "staking-periods.rewarded"),
    Feature("reward_rate_annual", "period", "Potential reward over stake, annualised over the period",
            "staking-periods.potential_reward_avax"),
    Feature("pending_start", "period", "1 if the period was accepted before it started", "staking-periods.start_kind"),
    Feature("at_stake_floor", "period", "1 if the stake is the 2,000 AVAX minimum", "staking-periods.stake_avax"),
    Feature("fee_at_floor", "period", "1 if the fee is the 2% minimum", "staking-periods.delegation_fee_rate"),
    Feature("regime", "period", "Network upgrade regime when the period was accepted", "staking-periods.regime",
            "categorical"),
    # The node's history up to and including this period.
    Feature("period_number", "history", "This period's place in the node's sequence, from 1", "staking-periods"),
    Feature("node_age_days", "history", "Days from the node's first start to this end", "staking-periods"),
    Feature("prior_renew_share", "history", "Share of the node's earlier periods followed by a start within 7 days",
            "events"),
    Feature("prev_gap_days", "history", "Gap after the node's previous period, days", "events"),
    Feature("reward_address_changed", "history", "1 if the reward address differs from the previous period's",
            "seamed-validator-stakes.reward_address"),
    Feature("prior_mean_gap_days", "history", "Mean gap after the node's earlier periods, days", "events"),
    Feature("prior_mean_duration_days", "history", "Mean duration of the node's earlier periods", "staking-periods"),
    Feature("duration_vs_prior_log", "history", "log of this duration over the earlier mean", "staking-periods"),
    Feature("stake_change_prev_log", "history", "log of this stake over the previous period's", "staking-periods"),
    Feature("stake_vs_max_log", "history", "log of this stake over the node's largest stake so far", "staking-periods"),
    Feature("fee_changes_to_date", "history", "Number of fee changes on the node so far", "staking-periods"),
    Feature("failed_to_date", "history", "Number of the node's periods without reward so far", "staking-periods"),
    # Delegation the period attracted.
    Feature("delegations_log", "delegation", "log1p of delegations to this period", "staking-periods delegator rows"),
    Feature("delegators_log", "delegation", "log1p of distinct delegator addresses", "seamed-delegator-stakes"),
    Feature("delegated_avax_log", "delegation", "log1p of AVAX delegated to this period", "staking-periods"),
    Feature("delegation_ratio", "delegation", "Delegated AVAX over the validator's own stake", "staking-periods"),
    Feature("largest_delegator_share", "delegation", "Share of delegated AVAX from the largest delegator address",
            "seamed-delegator-stakes.delegator_address"),
    Feature("median_delegation_log", "delegation", "log1p of the median delegation size, AVAX", "staking-periods"),
    Feature("fee_income_log", "delegation", "log1p of fees on rewarded delegations to this period, AVAX",
            "staking-periods"),
    # The reward address, the operator proxy.
    Feature("operator_nodes_to_date", "operator", "Nodes that had used this reward address by the end",
            "seamed-validator-stakes.reward_address"),
    # Market, read the day before the end.
    Feature("price_log10", "market", "log10 AVAX price in USDT", "binance.avax-usdt-daily"),
    Feature("return_30d", "market", "log price change over 30 days", "binance.avax-usdt-daily"),
    Feature("return_90d", "market", "log price change over 90 days", "binance.avax-usdt-daily"),
    Feature("volatility_30d", "market", "30-day realised volatility", "binance.avax-usdt-daily"),
    Feature("return_over_period", "market", "log price change from the period's start to its end",
            "binance.avax-usdt-daily"),
    Feature("return_since_entry", "market", "log price change since the node's first start",
            "binance.avax-usdt-daily"),
    # Network and money, read the day before the end.
    Feature("staking_ratio", "monetary", "Active stake over realised total supply", "avax-monetary-daily"),
    Feature("staking_ratio_change_90d", "monetary", "Change of the staking ratio over 90 days", "avax-monetary-daily"),
    Feature("network_delegated_share", "monetary", "Delegated stake over all active stake", "avax-monetary-daily"),
    Feature("active_validators", "monetary", "Active validators on the network", "avax-monetary-daily"),
    Feature("stake_share_of_network_bp", "monetary", "This stake over all validator stake, basis points",
            "avax-monetary-daily"),
    Feature("tbill_pct", "monetary", "US 3-month T-bill discount rate, percent", "fred.tbill-3m-daily"),
    Feature("reward_spread_pct", "monetary", "Annual reward rate minus the T-bill rate, percentage points",
            "staking-periods, fred.tbill-3m-daily"),
)

NAMES = tuple(feature.name for feature in REGISTRY)
CATEGORICAL = tuple(feature.name for feature in REGISTRY if feature.kind == "categorical")
FAMILIES = tuple(dict.fromkeys(feature.family for feature in REGISTRY))


def registry_frame() -> pd.DataFrame:
    return pd.DataFrame([feature.__dict__ for feature in REGISTRY])


def names(families: tuple[str, ...] | None = None) -> list[str]:
    return [f.name for f in REGISTRY if families is None or f.family in families]


def _history(events: pd.DataFrame) -> pd.DataFrame:
    e = events.sort_values(["node_id", "period_number"])
    g = e.groupby("node_id", sort=False)
    out = pd.DataFrame(index=e.index)
    out["period_number"] = e.period_number
    out["node_age_days"] = (e.end_time - g.start_time.transform("min")) / DAY
    renewed = e.outcome.eq("renew").astype(float)
    earlier = g.cumcount()
    out["prior_renew_share"] = (renewed.groupby(e.node_id).cumsum() - renewed) / earlier.replace(0, np.nan)
    # Sum and count earlier gaps without letting this event's own gap, unknown at its end, reach the result. A plain
    # cumulative sum is missing wherever this gap is missing, which would tell a model that the node did not return.
    gap = e.gap_days.where(e.gap_days.ge(0))
    filled, present = gap.fillna(0), gap.notna().astype(float)
    gap_sum = filled.groupby(e.node_id).cumsum() - filled
    gap_count = present.groupby(e.node_id).cumsum() - present
    out["prior_mean_gap_days"] = gap_sum / gap_count.replace(0, np.nan)
    out["prev_gap_days"] = gap.groupby(e.node_id).shift(1)
    previous_address = g.reward_address.shift(1)
    out["reward_address_changed"] = (e.reward_address.ne(previous_address) & previous_address.notna()).astype(int)
    duration_sum = e.duration_days.groupby(e.node_id).cumsum() - e.duration_days
    out["prior_mean_duration_days"] = duration_sum / earlier.replace(0, np.nan)
    out["duration_vs_prior_log"] = np.log(e.duration_days / out.prior_mean_duration_days)
    out["stake_change_prev_log"] = np.log(e.stake_avax / g.stake_avax.shift(1))
    out["stake_vs_max_log"] = np.log(e.stake_avax / g.stake_avax.cummax())
    changed = e.fee_rate.ne(g.fee_rate.shift(1)) & earlier.gt(0)
    out["fee_changes_to_date"] = changed.astype(int).groupby(e.node_id).cumsum()
    out["failed_to_date"] = (~e.rewarded.fillna(True).astype(bool)).astype(int).groupby(e.node_id).cumsum()
    return out.reindex(events.index)


def _operator_nodes(events: pd.DataFrame, periods: pd.DataFrame) -> pd.Series:
    con = duckdb.connect()
    con.execute("SET threads TO 1")
    con.register("p", periods[["node_id", "reward_address", "start_time"]])
    con.register("e", events[["transaction_hash", "reward_address", "end_time"]])
    counts = con.sql("""
        WITH first_use AS (SELECT reward_address, node_id, min(start_time) AS first_start FROM p
                           WHERE reward_address IS NOT NULL GROUP BY 1, 2)
        SELECT e.transaction_hash, count(f.node_id) AS nodes
        FROM e LEFT JOIN first_use f ON f.reward_address = e.reward_address AND f.first_start <= e.end_time
        GROUP BY 1""").df().set_index("transaction_hash").nodes
    return events.transaction_hash.map(counts).astype(float)


def _daily(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.set_index("date").sort_index().asfreq("D")
    out = pd.DataFrame(index=d.index)
    price = d.price_usd
    out["price_log10"] = np.log10(price)
    out["return_30d"] = np.log(price / price.shift(30))
    out["return_90d"] = np.log(price / price.shift(90))
    out["volatility_30d"] = d.volatility_30d
    staked = d.validator_stake_avax + d.delegated_stake_avax
    out["staking_ratio"] = staked / d.supply_avax
    out["staking_ratio_change_90d"] = out.staking_ratio - out.staking_ratio.shift(90)
    out["network_delegated_share"] = d.delegated_stake_avax / staked
    out["active_validators"] = d.active_validators
    out["validator_stake_avax"] = d.validator_stake_avax
    out["tbill_pct"] = d.tbill_pct.ffill()
    out["price_usd"] = price
    return out


def build(events: pd.DataFrame, inputs: Inputs) -> pd.DataFrame:
    """The registered features for every event, indexed like ``events``."""
    e = events
    out = pd.DataFrame(index=e.index)
    out["stake_log10"] = np.log10(e.stake_avax)
    out["duration_days"] = e.duration_days
    out["fee_rate"] = e.fee_rate
    out["failed"] = (~e.rewarded.fillna(True).astype(bool)).astype(int)
    out["reward_rate_annual"] = e.potential_reward_avax / e.stake_avax * 365 / e.duration_days
    out["pending_start"] = e.start_kind.eq("pending").astype(int)
    out["at_stake_floor"] = e.stake_avax.round(6).eq(2000).astype(int)
    out["fee_at_floor"] = e.fee_rate.round(6).eq(0.02).astype(int)
    out["regime"] = pd.Categorical(e.regime)
    out = out.join(_history(e))

    d = inputs.delegations.set_index("transaction_hash").reindex(e.transaction_hash)
    d.index = e.index
    delegated = d.delegated_avax.fillna(0)
    out["delegations_log"] = np.log1p(d.delegations.fillna(0))
    out["delegators_log"] = np.log1p(d.delegators.fillna(0))
    out["delegated_avax_log"] = np.log1p(delegated)
    out["delegation_ratio"] = delegated / e.stake_avax
    out["largest_delegator_share"] = (d.largest_delegator_avax / d.delegated_avax).fillna(0)
    out["median_delegation_log"] = np.log1p(d.median_delegation_avax.fillna(0))
    out["fee_income_log"] = np.log1p(d.delegator_gross_reward_avax.fillna(0) * e.fee_rate)
    out["operator_nodes_to_date"] = _operator_nodes(e, inputs.periods)

    daily = _daily(inputs.daily)
    asof = e.end_time.dt.normalize() - DAY
    first_start = e.groupby("node_id").start_time.transform("min").dt.normalize() - DAY
    start = e.start_time.dt.normalize() - DAY

    def at(column: str, dates: pd.Series) -> np.ndarray:
        return daily[column].reindex(dates.values).to_numpy()

    for column in ("price_log10", "return_30d", "return_90d", "volatility_30d", "staking_ratio",
                   "staking_ratio_change_90d", "network_delegated_share", "active_validators", "tbill_pct"):
        out[column] = at(column, asof)
    price_end = at("price_usd", asof)
    out["return_over_period"] = np.log(price_end / at("price_usd", start))
    out["return_since_entry"] = np.log(price_end / at("price_usd", first_start))
    out["stake_share_of_network_bp"] = 1e4 * e.stake_avax.to_numpy() / at("validator_stake_avax", asof)
    out["reward_spread_pct"] = 100 * out.reward_rate_annual - out.tbill_pct
    return out[list(NAMES)]
