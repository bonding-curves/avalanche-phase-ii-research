"""One row per node: its whole observed history as a vector, the unit for unsupervised learning.

A lifetime summarises the node's decision events and their features up to ``observed_through``. Columns describe
behaviour (how long, how often, how large, how it renews, what it charges, what it attracts) and, separately, context
(when it entered and what the market did since). Clustering uses the behaviour columns. Context columns are for
reading the clusters, so a cluster is not just an entry cohort. A share with no defined value, such as the renewal
share of a node with no completed decision, stays missing for the learner's imputer to handle.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DAY = pd.Timedelta(days=1)

BEHAVIOUR = (
    "periods_log", "tenure_days_log", "active_share", "median_duration_days", "duration_cv", "short_share",
    "long_share", "first_stake_log10", "max_stake_log10", "stake_growth_log", "stake_changes_share", "mean_fee_rate",
    "fee_changes", "renew_share", "return_share", "median_gap_days", "failed_share", "delegation_ratio_mean",
    "delegations_log", "largest_delegator_share", "operator_nodes_log",
)
CONTEXT = ("entry_year", "first_regime", "entry_price_log10", "return_since_entry_last", "departed", "censored_last",
           "stake_avax_days")


def build(events: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    """Lifetimes from events and their features, one row per node, indexed by node_id."""
    e = events.join(features[["delegation_ratio", "delegations_log", "largest_delegator_share", "price_log10",
                              "return_since_entry", "operator_nodes_to_date"]])
    e = e.sort_values(["node_id", "period_number"])
    g = e.groupby("node_id", sort=True)
    first, last = g.first(), g.last()
    tenure = (g.end_time.max() - g.start_time.min()) / DAY
    out = pd.DataFrame(index=first.index)
    out["periods_log"] = np.log1p(g.size())
    out["tenure_days_log"] = np.log1p(tenure)
    out["active_share"] = (g.duration_days.sum() / tenure).clip(upper=1)
    out["median_duration_days"] = g.duration_days.median()
    out["duration_cv"] = (g.duration_days.std() / g.duration_days.mean()).fillna(0)
    out["short_share"] = g.duration_days.apply(lambda s: s.le(21).mean())
    out["long_share"] = g.duration_days.apply(lambda s: s.ge(180).mean())
    out["first_stake_log10"] = np.log10(first.stake_avax)
    out["max_stake_log10"] = np.log10(g.stake_avax.max())
    out["stake_growth_log"] = np.log(last.stake_avax / first.stake_avax)
    change = e.stake_avax.ne(g.stake_avax.shift(1)) & e.period_number.gt(1)
    out["stake_changes_share"] = (change.groupby(e.node_id).sum() / (g.size() - 1).replace(0, np.nan)).fillna(0)
    out["mean_fee_rate"] = g.fee_rate.mean()
    fee_change = e.fee_rate.ne(g.fee_rate.shift(1)) & e.period_number.gt(1)
    out["fee_changes"] = fee_change.groupby(e.node_id).sum()
    known = e.outcome.isin(["renew", "return", "leave"])
    out["renew_share"] = e.outcome.eq("renew").where(known).groupby(e.node_id).mean()
    out["return_share"] = e.outcome.eq("return").where(known).groupby(e.node_id).mean()
    out["median_gap_days"] = e.gap_days.where(e.gap_days.ge(0)).groupby(e.node_id).median()
    out["failed_share"] = (~e.rewarded.fillna(True).astype(bool)).groupby(e.node_id).mean()
    out["delegation_ratio_mean"] = g.delegation_ratio.mean()
    out["delegations_log"] = np.log1p(np.expm1(e.delegations_log).groupby(e.node_id).sum())
    # AVAX-weighted share of delegated stake from the largest delegator address, over the node's periods.
    weights = e.delegation_ratio * e.stake_avax
    out["largest_delegator_share"] = ((e.largest_delegator_share * weights).groupby(e.node_id).sum()
                                      / weights.groupby(e.node_id).sum().replace(0, np.nan)).fillna(0)
    out["operator_nodes_log"] = np.log1p(g.operator_nodes_to_date.max())
    out["entry_year"] = first.start_time.dt.year
    out["first_regime"] = first.regime
    out["entry_price_log10"] = first.price_log10
    out["return_since_entry_last"] = last.return_since_entry
    out["departed"] = last.outcome.eq("leave")
    out["censored_last"] = last.outcome.eq("censored")
    out["stake_avax_days"] = (e.stake_avax * e.duration_days).groupby(e.node_id).sum()
    return out[list(BEHAVIOUR + CONTEXT)]
