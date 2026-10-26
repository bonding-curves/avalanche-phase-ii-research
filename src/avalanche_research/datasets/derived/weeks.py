"""The validator-week panel and the observed delegations it is read against, derived from the staking-period log.

``derived.validator-weeks`` has one row per Primary Network validator node per UTC week, Monday 00:00 to the next
Monday, for every week the node is validating at the Monday cutoff or first starts to validate during it. Every
feature is computed from staking transactions accepted before the cutoff, so a row never changes when later events are
appended: the check rebuilds the early weeks from truncated inputs and compares them. Outcomes are the delegations
accepted during the week, counted with and without the one address that made 93% of all delegations.

``derived.observed-delegations`` has one row per delegation accepted in the window, with its exact duration, its
week, and whether its validator was on offer at that week's cutoff. No delegation is dropped: one whose validator has no
row in its week is flagged, and the panel's summary counts it. Each delegation also carries its event-time eligibility:
the validator's room at acceptance over the delegation's own interval, from the delegations accepted in earlier blocks,
and a reason code for every delegation not offered at the cutoff and for every one the reconstruction finds ineligible.

``derived.market-weeks`` has one row per week with what belongs to the week rather than to a node: the unstaked supply
stock at the Monday cutoff, the week's delegated volume by stratum, the concentrated address's share of events and
AVAX, the AVAX price and 30-day volatility at the last completed day before the cutoff, and coverage.

Yield quotes follow the S2 decision: the protocol kernel's annualized reward rate for a 25 AVAX delegation starting at
the cutoff, against the P-Chain supply counter last read before it, times one minus the validator's fee.

The window, the concentrated address, and the protocol limits are parameters in the capture receipt.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from ... import __version__, datasets
from ...core.catalog import (
    DataError,
    canonical_bytes,
    contract_hash,
    dataset,
    load_catalog,
    now,
    sha256,
)
from ...domain.protocol import MAINNET_UPGRADES, annualized_reward_rate
from . import seam

WEEKS_ID = "derived.validator-weeks"
DELEGATIONS_ID = "derived.observed-delegations"
MARKET_ID = "derived.market-weeks"
DATASET_IDS = (WEEKS_ID, DELEGATIONS_ID, MARKET_ID)
SOURCE_ID = "derived"
TABLES = {WEEKS_ID: "validator-weeks", DELEGATIONS_ID: "observed-delegations", MARKET_ID: "market-weeks"}
INPUTS = {
    "staking-periods": "derived.staking-periods",
    "validator-stakes": "snowflake.primary-validator-stakes",
    "delegator-stakes": "snowflake.primary-delegator-stakes",
    "staking-supply": "snowflake.primary-staking-supply",
}
MARKET_INPUTS = {
    "monetary-daily": "derived.avax-monetary-daily",
    "binance-daily": "binance.avax-usdt-daily",
    "defillama-daily": "defillama.avax-price-daily",
}
VIEW_NAMES = {"staking-periods": "periods", "validator-stakes": "validators", "delegator-stakes": "delegators", "staking-supply": "supply",
              "monetary-daily": "ledger", "binance-daily": "binance", "defillama-daily": "defillama"}
QUOTE_STAKE_NAVAX = 25 * 10**9
# The pre-Helicon window of decision SD10: the first Monday week holding a captured delegation to the last full week
# before Helicon activated on 2026-09-22 15:00 UTC.
WINDOW_START = "2020-09-21"
WINDOW_END = "2026-09-21"
# The one address behind 93% of delegation events (node table NK2); its stratum is decision SD8. Not named as an operator.
CONCENTRATED_ADDRESS = "avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy"
# AvalancheGo e9a8b75: MaxValidatorWeightFactor 5 (proposal_tx_executor.go:32), MaxValidatorStake 3M AVAX and
# MinDelegatorStake 25 AVAX (genesis_mainnet.go:57-58), MinStakeDuration two weeks (line 60, before Helicon).
WEIGHT_FACTOR = 5
MAX_WEIGHT_AVAX = 3_000_000
MIN_DELEGATION_AVAX = 25
MIN_DURATION_DAYS = 14
SECONDS_PER_WEEK = 604_800
NAVAX_PER_AVAX = 10**9
# AvalancheGo v1.4.5 (2021-05-21) to v1.4.x checked delegated weight against five times the validator's stake only; v1.5.0
# restored min(5x, MaxValidatorStake) from Apricot Phase 3 (add_delegator_tx.go isAP3), which also fixed the heap used for
# the peak (fixedMaxStakeAmount). Delegations accepted before this instant are judged against both limits separately.
AP3_ACTIVATION = MAINNET_UPGRADES.time("apricot_phase_3").strftime("%Y-%m-%d %H:%M:%S")


def max_weight_sql(week: str, stake: str) -> str:
    """A validator's weight limit at a week start: five times its stake, and from Apricot Phase 3 at most 3M AVAX.
    AvalancheGo v1.4.5 checked only the factor until Apricot Phase 3 restored the cap (observed-delegations record RR2)."""
    return (f"CASE WHEN {week} < TIMESTAMP '{AP3_ACTIVATION}' THEN {WEIGHT_FACTOR} * {stake}"
            f" ELSE least({WEIGHT_FACTOR} * {stake}, {MAX_WEIGHT_AVAX * NAVAX_PER_AVAX}) END")
# Reason codes. A delegation not offered at its week's cutoff gets exactly one NOT_OFFERED code; a delegation the
# event-time reconstruction finds ineligible gets exactly one INELIGIBLE code. Both are null otherwise.
NOT_OFFERED_REASONS = ("no_node_week_row", "validator_not_active_at_cutoff", "other_period_than_cutoff", "period_ends_within_14d",
                       "full_at_cutoff_room_at_accept", "full_at_cutoff_no_room_at_accept", "unclassified")
INELIGIBLE_REASONS = ("no_validator_period", "outside_validator_period", "over_3m_cap_before_ap3", "over_weight_before_ap3", "over_capacity")
# A row of the check's rebuild from inputs truncated here must equal the full build's row.
INVARIANCE_CUTOFF = "2025-01-06"

WEEK_COLUMNS = {
    "node_id": "VARCHAR", "week_start_utc": "TIMESTAMP", "active_at_week_start": "BOOLEAN", "offered_at_week_start": "BOOLEAN",
    "validator_transaction_hash": "VARCHAR", "period_start": "TIMESTAMP", "period_end": "TIMESTAMP", "days_remaining": "DOUBLE",
    "self_stake_avax": "DOUBLE", "delegation_fee_rate": "DOUBLE",
    "first_start_known": "TIMESTAMP", "node_age_weeks": "DOUBLE", "days_staked_weeks": "DOUBLE",
    "completed_periods": "BIGINT", "started_periods": "BIGINT", "reward_address_asof": "VARCHAR",
    "delegated_avax_at_week_start": "DOUBLE", "max_delegated_avax_14d": "DOUBLE", "max_weight_avax": "DOUBLE",
    "capacity_left_avax": "DOUBLE", "capacity_left_avax_14d": "DOUBLE",
    "delegations_all": "BIGINT", "delegated_avax_all": "DOUBLE", "delegations_excl_concentrated": "BIGINT", "delegated_avax_excl_concentrated": "DOUBLE",
    "supply_counter_avax": "DOUBLE", "supply_read_at": "TIMESTAMP",
    "gross_rate_14d": "DOUBLE", "net_rate_14d": "DOUBLE", "log_net_apy_14d": "DOUBLE",
    "gross_rate_remaining": "DOUBLE", "net_rate_remaining": "DOUBLE", "log_net_apy_remaining": "DOUBLE",
}
DELEGATION_COLUMNS = {
    "transaction_hash": "VARCHAR", "node_id": "VARCHAR", "validator_transaction_hash": "VARCHAR", "delegator_address": "VARCHAR",
    "concentrated_address": "BOOLEAN", "accepted_at": "TIMESTAMP", "week_start_utc": "TIMESTAMP",
    "start_time": "TIMESTAMP", "end_time": "TIMESTAMP", "duration_seconds": "BIGINT", "duration_weeks": "DOUBLE",
    "stake_avax": "DOUBLE", "node_week_row": "BOOLEAN", "validator_offered_at_week_start": "BOOLEAN", "not_in_week_start_risk_set": "BOOLEAN",
    "validator_fee_rate": "DOUBLE", "supply_counter_avax": "DOUBLE", "gross_rate": "DOUBLE", "net_rate": "DOUBLE", "log_net_apy": "DOUBLE",
    "capacity_at_accept_avax": "DOUBLE", "eligible_at_accept": "BOOLEAN", "ineligibility_reason": "VARCHAR", "not_offered_reason": "VARCHAR",
}
MARKET_COLUMNS = {
    "week_start_utc": "TIMESTAMP", "supply_date": "DATE", "total_supply_avax": "DOUBLE", "active_validator_stake_avax": "DOUBLE",
    "active_delegated_stake_avax": "DOUBLE", "unstaked_supply_avax": "DOUBLE", "supply_checked": "BOOLEAN",
    "validators_active": "BIGINT", "validators_offered": "BIGINT",
    "delegations_all": "BIGINT", "delegated_avax_all": "DOUBLE", "delegations_excl_concentrated": "BIGINT", "delegated_avax_excl_concentrated": "DOUBLE",
    "concentrated_event_share": "DOUBLE", "concentrated_avax_share": "DOUBLE",
    "price_date": "DATE", "price_usdt": "DOUBLE", "volatility_30d": "DOUBLE", "price_usd_defillama": "DOUBLE", "volatility_30d_defillama": "DOUBLE",
    "price_present": "BOOLEAN",
}

# Every feature of week w reads only transactions accepted before w. A period starts no earlier than its acceptance, so
# a period started before w was accepted before it; the SQL states both conditions so the rule reads off the query.
PANEL_SQL = f"""
CREATE OR REPLACE TABLE weeks AS
SELECT unnest(generate_series(TIMESTAMP '{{window_start}}', TIMESTAMP '{{window_end}}' - INTERVAL 7 DAY, INTERVAL 7 DAY)) AS week_start_utc;

CREATE OR REPLACE TABLE v AS
SELECT p.node_id, p.transaction_hash, p.accepted_at, p.start_time, p.end_time, p.stake_navax, p.delegation_fee_rate, s.reward_address
FROM periods p LEFT JOIN validators s USING (transaction_hash)
WHERE p.role = 'validator' AND p.accepted_at < TIMESTAMP '{{known_until}}';

CREATE OR REPLACE TABLE d AS
SELECT p.transaction_hash, p.node_id, p.validator_transaction_hash, s.delegator_address, p.accepted_at, p.block_height, p.start_time, p.end_time, p.stake_navax
FROM periods p LEFT JOIN delegators s USING (transaction_hash)
WHERE p.role = 'delegator' AND p.accepted_at < TIMESTAMP '{{known_until}}';

-- Disjoint validating intervals per node: a period overlapping an earlier one extends it.
CREATE OR REPLACE TABLE islands AS
WITH ordered AS (
    SELECT node_id, start_time, end_time,
           max(end_time) OVER (PARTITION BY node_id ORDER BY start_time, transaction_hash ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prior_end
    FROM v
), numbered AS (
    SELECT *, sum(CASE WHEN prior_end IS NULL OR start_time > prior_end THEN 1 ELSE 0 END) OVER (PARTITION BY node_id ORDER BY start_time, end_time) AS island
    FROM ordered
)
SELECT node_id, island, min(start_time) AS island_start, max(end_time) AS island_end FROM numbered GROUP BY node_id, island;

-- Rows: validating at the cutoff, or starting a period during the week without validating at the cutoff.
CREATE OR REPLACE TABLE active AS
SELECT w.week_start_utc, v.node_id,
       arg_max(v.transaction_hash, v.start_time) AS validator_transaction_hash,
       max(v.start_time) AS period_start, arg_max(v.end_time, v.start_time) AS period_end,
       arg_max(v.stake_navax, v.start_time) AS stake_navax, arg_max(v.delegation_fee_rate, v.start_time) AS delegation_fee_rate
FROM weeks w JOIN v ON v.accepted_at < w.week_start_utc AND v.start_time < w.week_start_utc AND v.end_time > w.week_start_utc
GROUP BY 1, 2;

CREATE OR REPLACE TABLE keys AS
SELECT week_start_utc, node_id, TRUE AS active_at_week_start FROM active
UNION ALL
SELECT DISTINCT w.week_start_utc, v.node_id, FALSE
FROM weeks w JOIN v ON v.start_time >= w.week_start_utc AND v.start_time < w.week_start_utc + INTERVAL 7 DAY
WHERE NOT EXISTS (SELECT 1 FROM active a WHERE a.week_start_utc = w.week_start_utc AND a.node_id = v.node_id);

CREATE OR REPLACE TABLE history AS
SELECT k.week_start_utc, k.node_id,
       min(v.start_time) FILTER (WHERE v.start_time < k.week_start_utc) AS first_start_known,
       count(*) FILTER (WHERE v.end_time <= k.week_start_utc) AS completed_periods,
       count(*) FILTER (WHERE v.start_time < k.week_start_utc) AS started_periods,
       arg_max(v.reward_address, v.accepted_at) AS reward_address_asof
FROM keys k LEFT JOIN v ON v.node_id = k.node_id AND v.accepted_at < k.week_start_utc
GROUP BY 1, 2;

CREATE OR REPLACE TABLE staked AS
SELECT k.week_start_utc, k.node_id,
       coalesce(sum(epoch(least(i.island_end, k.week_start_utc) - i.island_start)), 0) / {SECONDS_PER_WEEK} AS days_staked_weeks
FROM keys k LEFT JOIN islands i ON i.node_id = k.node_id AND i.island_start < k.week_start_utc
GROUP BY 1, 2;

-- Delegated weight on the cutoff's validation, known at the cutoff: at the cutoff and at every scheduled start within
-- the next fourteen days, the shortest delegation a new delegator could make.
CREATE OR REPLACE TABLE known_d AS
SELECT a.week_start_utc, a.node_id, d.start_time, d.end_time, d.stake_navax
FROM active a JOIN d ON d.validator_transaction_hash = a.validator_transaction_hash AND d.accepted_at < a.week_start_utc
WHERE d.end_time > a.week_start_utc AND d.start_time < a.week_start_utc + INTERVAL {MIN_DURATION_DAYS} DAY;

CREATE OR REPLACE TABLE points AS
SELECT week_start_utc, node_id, week_start_utc AS point FROM active
UNION
SELECT week_start_utc, node_id, start_time FROM known_d WHERE start_time > week_start_utc;

CREATE OR REPLACE TABLE weight AS
SELECT p.week_start_utc, p.node_id, p.point, coalesce(sum(k.stake_navax), 0) AS delegated_navax
FROM points p LEFT JOIN known_d k ON k.week_start_utc = p.week_start_utc AND k.node_id = p.node_id AND k.start_time <= p.point AND k.end_time > p.point
GROUP BY 1, 2, 3;

-- Room is computed in integer nAVAX and converted once: subtracting AVAX doubles left full validators at -1e-10.
CREATE OR REPLACE TABLE capacity AS
SELECT c.week_start_utc, c.node_id, c.delegated_navax_at_week_start, c.max_delegated_navax_14d,
       {max_weight_sql("c.week_start_utc", "a.stake_navax")} AS max_weight_navax,
       max_weight_navax - a.stake_navax - c.delegated_navax_at_week_start AS capacity_left_navax,
       max_weight_navax - a.stake_navax - c.max_delegated_navax_14d AS capacity_left_navax_14d
FROM (SELECT week_start_utc, node_id, max(delegated_navax) FILTER (WHERE point = week_start_utc) AS delegated_navax_at_week_start,
             max(delegated_navax) AS max_delegated_navax_14d
      FROM weight GROUP BY 1, 2) c
JOIN active a USING (week_start_utc, node_id);

-- The P-Chain supply counter last read before each cutoff: the supply the reward formula uses (decision RD8).
CREATE OR REPLACE TABLE cutoff_supply AS
SELECT w.week_start_utc, s.block_supply_navax AS supply_navax, s.accepted_at AS supply_read_at
FROM weeks w ASOF LEFT JOIN (
    SELECT accepted_at, block_supply_navax FROM supply WHERE block_supply_navax IS NOT NULL AND accepted_at < TIMESTAMP '{{known_until}}'
) s ON w.week_start_utc > s.accepted_at;

CREATE OR REPLACE TABLE outcomes AS
SELECT k.week_start_utc, k.node_id,
       count(d.transaction_hash) AS delegations_all, coalesce(sum(d.stake_navax), 0) / 1e9 AS delegated_avax_all,
       count(d.transaction_hash) FILTER (WHERE d.delegator_address IS DISTINCT FROM '{CONCENTRATED_ADDRESS}') AS delegations_excl_concentrated,
       coalesce(sum(d.stake_navax) FILTER (WHERE d.delegator_address IS DISTINCT FROM '{CONCENTRATED_ADDRESS}'), 0) / 1e9 AS delegated_avax_excl_concentrated
FROM keys k LEFT JOIN d ON d.node_id = k.node_id AND d.accepted_at >= k.week_start_utc AND d.accepted_at < k.week_start_utc + INTERVAL 7 DAY
GROUP BY 1, 2;

CREATE OR REPLACE TABLE panel AS
SELECT k.node_id, k.week_start_utc, k.active_at_week_start,
       coalesce(k.active_at_week_start AND epoch(a.period_end - k.week_start_utc) >= {MIN_DURATION_DAYS} * 86400
                AND c.capacity_left_navax_14d >= {MIN_DELEGATION_AVAX * NAVAX_PER_AVAX}, FALSE) AS offered_at_week_start,
       a.validator_transaction_hash, a.period_start, a.period_end, epoch(a.period_end - k.week_start_utc) / 86400 AS days_remaining,
       a.stake_navax / 1e9 AS self_stake_avax, a.delegation_fee_rate,
       h.first_start_known, epoch(k.week_start_utc - h.first_start_known) / {SECONDS_PER_WEEK} AS node_age_weeks, s.days_staked_weeks,
       h.completed_periods, h.started_periods, h.reward_address_asof,
       c.delegated_navax_at_week_start / 1e9 AS delegated_avax_at_week_start, c.max_delegated_navax_14d / 1e9 AS max_delegated_avax_14d,
       ({max_weight_sql("k.week_start_utc", "a.stake_navax")}) / 1e9 AS max_weight_avax,
       c.capacity_left_navax / 1e9 AS capacity_left_avax, c.capacity_left_navax_14d / 1e9 AS capacity_left_avax_14d,
       o.delegations_all, o.delegated_avax_all, o.delegations_excl_concentrated, o.delegated_avax_excl_concentrated,
       q.supply_navax / 1e9 AS supply_counter_avax, q.supply_read_at,
       CASE WHEN k.active_at_week_start THEN annual_rate(k.week_start_utc, {MIN_DURATION_DAYS} * 86400, q.supply_navax) END AS gross_rate_14d,
       gross_rate_14d * (1 - a.delegation_fee_rate) AS net_rate_14d,
       CASE WHEN net_rate_14d > 0 THEN ln(net_rate_14d) END AS log_net_apy_14d,
       CASE WHEN k.active_at_week_start AND epoch(a.period_end - k.week_start_utc) >= {MIN_DURATION_DAYS} * 86400
            THEN annual_rate(k.week_start_utc, epoch(a.period_end - k.week_start_utc)::BIGINT, q.supply_navax) END AS gross_rate_remaining,
       gross_rate_remaining * (1 - a.delegation_fee_rate) AS net_rate_remaining,
       CASE WHEN net_rate_remaining > 0 THEN ln(net_rate_remaining) END AS log_net_apy_remaining
FROM keys k
JOIN cutoff_supply q USING (week_start_utc)
LEFT JOIN active a USING (week_start_utc, node_id)
JOIN history h USING (week_start_utc, node_id)
JOIN staked s USING (week_start_utc, node_id)
LEFT JOIN capacity c USING (week_start_utc, node_id)
JOIN outcomes o USING (week_start_utc, node_id)
ORDER BY k.week_start_utc, k.node_id;

-- Event-time eligibility. A delegation X is checked against the delegations to the same validator period accepted in
-- earlier blocks (the order inside one block is not in the data, so block peers do not count against each other). Their
-- weight is a step function over half-open [start, end) intervals. Its peak over X's [start_time, end_time) is at X's
-- start or at the start of an earlier-accepted delegation still pending inside the interval.
CREATE OR REPLACE TABLE stake_steps AS
WITH ev AS (
    SELECT validator_transaction_hash AS vh, start_time AS t, stake_navax::HUGEINT AS delta FROM d
    UNION ALL
    SELECT validator_transaction_hash, end_time, -stake_navax::HUGEINT FROM d
)
SELECT vh, t, sum(sum(delta)) OVER (PARTITION BY vh ORDER BY t) AS active_navax FROM ev GROUP BY vh, t;

-- Everything active at X's start that X may not count: X itself, block peers, and later-accepted delegations that
-- start no later than X.
CREATE OR REPLACE TABLE not_prior_at_start AS
SELECT x.transaction_hash, sum(y.stake_navax) AS navax
FROM d x JOIN d y ON y.validator_transaction_hash = x.validator_transaction_hash AND y.block_height >= x.block_height
     AND y.start_time <= x.start_time AND y.end_time > x.start_time
GROUP BY 1;

CREATE OR REPLACE TABLE pending_points AS
SELECT DISTINCT x.transaction_hash, x.validator_transaction_hash AS vh, x.block_height, y.start_time AS point
FROM d x JOIN d y ON y.validator_transaction_hash = x.validator_transaction_hash AND y.block_height < x.block_height
     AND y.start_time > x.start_time AND y.start_time < x.end_time;

CREATE OR REPLACE TABLE pending_peak AS
SELECT transaction_hash, max(navax) AS navax FROM (
    SELECT p.transaction_hash, p.point, coalesce(sum(z.stake_navax), 0) AS navax
    FROM pending_points p LEFT JOIN d z ON z.validator_transaction_hash = p.vh AND z.block_height < p.block_height
         AND z.start_time <= p.point AND z.end_time > p.point
    GROUP BY 1, 2
) GROUP BY 1;

CREATE OR REPLACE TABLE eligibility AS
WITH peak AS (
    SELECT x.transaction_hash, x.accepted_at, x.start_time, x.end_time, x.stake_navax,
           greatest(s.active_navax - n.navax, coalesce(pp.navax, 0)) AS peak_navax,
           vv.transaction_hash IS NOT NULL AS has_period, vv.start_time AS period_start, vv.end_time AS period_end, vv.stake_navax AS self_navax
    FROM d x
    JOIN stake_steps s ON s.vh = x.validator_transaction_hash AND s.t = x.start_time
    JOIN not_prior_at_start n USING (transaction_hash)
    LEFT JOIN pending_peak pp USING (transaction_hash)
    LEFT JOIN v vv ON vv.transaction_hash = x.validator_transaction_hash
), room AS (
    SELECT *, least({WEIGHT_FACTOR} * self_navax, {MAX_WEIGHT_AVAX * NAVAX_PER_AVAX}) - self_navax - peak_navax AS capacity_navax,
           ({WEIGHT_FACTOR} - 1) * self_navax - peak_navax AS factor_room_navax
    FROM peak
)
SELECT transaction_hash, capacity_navax / 1e9 AS capacity_at_accept_avax,
       CASE WHEN NOT has_period THEN 'no_validator_period'
            WHEN start_time < period_start OR end_time > period_end THEN 'outside_validator_period'
            WHEN capacity_navax >= stake_navax THEN NULL
            WHEN accepted_at < TIMESTAMP '{AP3_ACTIVATION}' AND factor_room_navax >= stake_navax THEN 'over_3m_cap_before_ap3'
            WHEN accepted_at < TIMESTAMP '{AP3_ACTIVATION}' THEN 'over_weight_before_ap3'
            ELSE 'over_capacity' END AS ineligibility_reason,
       ineligibility_reason IS NULL AS eligible_at_accept
FROM room;

CREATE OR REPLACE TABLE observed AS
SELECT d.transaction_hash, d.node_id, d.validator_transaction_hash, d.delegator_address,
       d.delegator_address IS NOT DISTINCT FROM '{CONCENTRATED_ADDRESS}' AS concentrated_address,
       d.accepted_at, date_trunc('week', d.accepted_at) AS week_start_utc, d.start_time, d.end_time,
       epoch(d.end_time - d.start_time)::BIGINT AS duration_seconds, epoch(d.end_time - d.start_time) / {SECONDS_PER_WEEK} AS duration_weeks,
       d.stake_navax / 1e9 AS stake_avax,
       p.node_id IS NOT NULL AS node_week_row, coalesce(p.offered_at_week_start, FALSE) AS validator_offered_at_week_start,
       NOT coalesce(p.offered_at_week_start, FALSE) AS not_in_week_start_risk_set,
       vv.delegation_fee_rate AS validator_fee_rate, q.supply_navax / 1e9 AS supply_counter_avax,
       annual_rate(date_trunc('week', d.accepted_at), epoch(d.end_time - d.start_time)::BIGINT, q.supply_navax) AS gross_rate,
       gross_rate * (1 - vv.delegation_fee_rate) AS net_rate,
       CASE WHEN net_rate > 0 THEN ln(net_rate) END AS log_net_apy,
       e.capacity_at_accept_avax, e.eligible_at_accept, e.ineligibility_reason,
       CASE WHEN p.offered_at_week_start THEN NULL
            WHEN p.node_id IS NULL THEN 'no_node_week_row'
            WHEN NOT p.active_at_week_start THEN 'validator_not_active_at_cutoff'
            WHEN p.validator_transaction_hash <> d.validator_transaction_hash THEN 'other_period_than_cutoff'
            WHEN p.days_remaining < {MIN_DURATION_DAYS} THEN 'period_ends_within_14d'
            WHEN p.capacity_left_avax_14d < {MIN_DELEGATION_AVAX} AND e.eligible_at_accept THEN 'full_at_cutoff_room_at_accept'
            WHEN p.capacity_left_avax_14d < {MIN_DELEGATION_AVAX} THEN 'full_at_cutoff_no_room_at_accept'
            ELSE 'unclassified' END AS not_offered_reason
FROM d LEFT JOIN panel p ON p.node_id = d.node_id AND p.week_start_utc = date_trunc('week', d.accepted_at)
LEFT JOIN v vv ON vv.transaction_hash = d.validator_transaction_hash
LEFT JOIN cutoff_supply q ON q.week_start_utc = date_trunc('week', d.accepted_at)
LEFT JOIN eligibility e ON e.transaction_hash = d.transaction_hash
WHERE d.accepted_at >= TIMESTAMP '{{window_start}}' AND d.accepted_at < TIMESTAMP '{{window_end}}'
ORDER BY d.accepted_at, d.transaction_hash;
"""

# Market facts of each week: the stock at the cutoff from the ledger's close of the Sunday before, the week's flows from
# the observed delegations, and the price and volatility of that Sunday, the last completed day (decision SD7).
MARKET_SQL = """
CREATE OR REPLACE TABLE market AS
WITH flows AS (
    SELECT week_start_utc, count(*) AS delegations_all, sum(stake_avax) AS delegated_avax_all,
           count(*) FILTER (WHERE NOT concentrated_address) AS delegations_excl_concentrated,
           coalesce(sum(stake_avax) FILTER (WHERE NOT concentrated_address), 0) AS delegated_avax_excl_concentrated,
           count(*) FILTER (WHERE concentrated_address) / count(*) AS concentrated_event_share,
           coalesce(sum(stake_avax) FILTER (WHERE concentrated_address), 0) / sum(stake_avax) AS concentrated_avax_share
    FROM observed GROUP BY 1
), llama AS (
    -- DefiLlama stamps its points at 00:00, 00:01, or 23:59, sometimes two on one date: take the one nearest the cutoff.
    SELECT w.week_start_utc, arg_min(y.price_usd, abs(epoch(y.observed_at - w.week_start_utc))) AS price_usd,
           arg_min(y.realized_volatility_30d, abs(epoch(y.observed_at - w.week_start_utc))) AS realized_volatility_30d
    FROM weeks w JOIN defillama y ON y.observed_at BETWEEN w.week_start_utc - INTERVAL 1 DAY AND w.week_start_utc + INTERVAL 1 DAY
    GROUP BY 1
), offers AS (
    SELECT week_start_utc, count(*) FILTER (WHERE active_at_week_start) AS validators_active, count(*) FILTER (WHERE offered_at_week_start) AS validators_offered
    FROM panel GROUP BY 1
)
SELECT w.week_start_utc, (w.week_start_utc - INTERVAL 1 DAY)::DATE AS supply_date,
       l.total_supply_close_wei::DOUBLE / 1e18 AS total_supply_avax,
       l.active_validator_stake_wei::DOUBLE / 1e18 AS active_validator_stake_avax,
       l.active_delegated_stake_wei::DOUBLE / 1e18 AS active_delegated_stake_avax,
       (l.total_supply_close_wei - l.active_validator_stake_wei - l.active_delegated_stake_wei)::DOUBLE / 1e18 AS unstaked_supply_avax,
       coalesce(l.complete AND l.total_supply_close_wei IS NOT NULL, FALSE) AS supply_checked,
       coalesce(o.validators_active, 0) AS validators_active, coalesce(o.validators_offered, 0) AS validators_offered,
       coalesce(f.delegations_all, 0) AS delegations_all, coalesce(f.delegated_avax_all, 0) AS delegated_avax_all,
       coalesce(f.delegations_excl_concentrated, 0) AS delegations_excl_concentrated,
       coalesce(f.delegated_avax_excl_concentrated, 0) AS delegated_avax_excl_concentrated,
       f.concentrated_event_share, f.concentrated_avax_share,
       (w.week_start_utc - INTERVAL 1 DAY)::DATE AS price_date,
       b.close_usdt AS price_usdt, b.realized_volatility_30d AS volatility_30d,
       y.price_usd AS price_usd_defillama, y.realized_volatility_30d AS volatility_30d_defillama,
       b.close_usdt IS NOT NULL AS price_present
FROM weeks w
LEFT JOIN ledger l ON l.date_utc = (w.week_start_utc - INTERVAL 1 DAY)::DATE
LEFT JOIN offers o USING (week_start_utc)
LEFT JOIN flows f USING (week_start_utc)
LEFT JOIN binance b ON b.observation_date = (w.week_start_utc - INTERVAL 1 DAY)::DATE
LEFT JOIN llama y USING (week_start_utc)
ORDER BY w.week_start_utc
"""

SUMMARY_SQL = """
SELECT (SELECT count(*) FROM panel), (SELECT count(DISTINCT (node_id, week_start_utc)) FROM panel), (SELECT count(DISTINCT node_id) FROM panel),
       (SELECT count(DISTINCT week_start_utc) FROM panel), (SELECT count(*) FILTER (WHERE active_at_week_start) FROM panel),
       (SELECT count(*) FILTER (WHERE offered_at_week_start) FROM panel),
       (SELECT count(*) FROM observed), (SELECT count(*) FILTER (WHERE node_week_row) FROM observed),
       (SELECT count(*) FILTER (WHERE not_in_week_start_risk_set) FROM observed),
       (SELECT coalesce(sum(delegations_all), 0) FROM panel),
       (SELECT round(coalesce(sum(stake_avax), 0), 6) FROM observed),
       (SELECT count(*) FILTER (WHERE concentrated_address) FROM observed),
       (SELECT round(coalesce(sum(stake_avax) FILTER (WHERE concentrated_address), 0), 6) FROM observed)
"""
SUMMARY_KEYS = ("rows", "distinct_keys", "nodes", "weeks", "active_rows", "offered_rows", "delegations", "delegations_with_row",
                "delegations_not_in_week_start_risk_set", "panel_delegations", "delegated_avax", "concentrated_delegations", "concentrated_avax")


def _reject(dataset_id: str) -> None:
    if dataset_id not in DATASET_IDS:
        raise DataError(f"{dataset_id} is not a derived dataset of this module")


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    _reject(dataset_id)
    raise DataError(f"{dataset_id} is built with `avalanche data derive`, not fetched")


def capture(dataset_id: str, output: Path, timeout: float = 20, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    return capture_preview(dataset_id, output, parameters)


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    _reject(dataset_id)
    raise DataError(f"{dataset_id} is built with `avalanche data derive`, which writes capture and dataset together")


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    return build_preview(dataset_id, capture_dir, output)


def inputs_of(dataset_id: str) -> dict[str, str]:
    return {**INPUTS, **MARKET_INPUTS} if dataset_id == MARKET_ID else dict(INPUTS)


def select_inputs(dataset_id: str, pinned: dict[str, str] | None, root: Path | None) -> list[dict[str, Any]]:
    pinned = pinned or {}
    wanted = inputs_of(dataset_id)
    unknown = sorted(set(pinned) - set(wanted.values()) - set(seam.SEAMED.values()))
    if unknown:
        raise DataError(f"not an input of {dataset_id}: {', '.join(unknown)}")
    selected = []
    for input_id, share_id in wanted.items():
        input_dataset, run = seam.resolve(share_id, pinned, root)
        record = datasets.receipt(input_dataset, run, root)
        parquet = datasets.parquet_path(input_dataset, run, root)
        body = parquet.read_bytes()
        selected.append({
            "input_id": input_id, "dataset_id": input_dataset, "run": record["run"], "capture_id": record["capture"]["capture_id"],
            "contract_sha256": record["capture"].get("contract_sha256"), "captured_at": record["capture"].get("completed_at"),
            "rows": record["build"].get("summary", {}).get("rows"), "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet,
        })
    return selected


def load_inputs(connection: Any, paths: dict[str, Path]) -> None:
    for input_id, path in paths.items():
        connection.execute(f"CREATE OR REPLACE VIEW {VIEW_NAMES[input_id]} AS SELECT * FROM read_parquet('{str(path).replace(chr(39), chr(39) * 2)}')")


def quote(start: datetime, duration_seconds: int, supply_navax: int) -> float:
    """The protocol kernel's annualized reward rate of a 25 AVAX delegation starting at the cutoff (decision SD9)."""
    return annualized_reward_rate(start, duration_seconds, QUOTE_STAKE_NAVAX, supply_navax)


def with_observed_market_prices(frame, price_parquet):
    """Named successor of a weekly market table using strictly earlier quotes at most24h old.

    Existing derives and frozen panels retain their original selection. This
    projection replaces only DefiLlama price/volatility and adds quote lineage.
    Observation timestamps are proxies, not historical publication vintages.
    """
    import pandas as pd

    from .observed_quotes import select_quotes

    if "week_start_utc" not in frame or frame.week_start_utc.isna().any() or frame.week_start_utc.duplicated().any():
        raise DataError("weekly market projection needs unique known week_start_utc keys")
    keys = pd.DataFrame({"quote_key": frame.week_start_utc, "quote_cutoff_at": frame.week_start_utc})
    quotes = select_quotes(keys, price_parquet, max_age_seconds=86400)
    metadata = dict(quotes.attrs)
    names = {"quote_key": "week_start_utc", "quote_cutoff_at": "defillama_price_cutoff_at",
             "price_usd": "price_usd_defillama", "volatility_30d": "volatility_30d_defillama"}
    names.update({name: "defillama_" + name for name in quotes if name not in names})
    quotes = quotes.rename(columns=names)
    result = frame.drop(columns=["price_usd_defillama", "volatility_30d_defillama"], errors="ignore").merge(
        quotes, on="week_start_utc", how="left", validate="one_to_one")
    result["defillama_price_clock"] = "observed-before-week-cutoff-24h/v1"
    result.attrs = {**frame.attrs, "defillama_price_clock": "observed-before-week-cutoff-24h/v1", "defillama_price_selection": metadata,
                    "scope": "DefiLlama price projection only; other weekly fields are retained; scientific fitness is not assessed."}
    return result


def compute(connection: Any, window_start: str = WINDOW_START, window_end: str = WINDOW_END, known_until: str | None = None) -> None:
    """Build ``panel`` and ``observed`` from the input views. ``known_until`` drops every transaction accepted from then on,
    which is how the check proves that earlier rows do not depend on later events."""
    sql = PANEL_SQL.format(window_start=window_start, window_end=window_end, known_until=known_until or window_end)
    try:
        from duckdb.sqltypes import BIGINT, DOUBLE, TIMESTAMP

        if not connection.execute("SELECT count(*) FROM duckdb_functions() WHERE function_name = 'annual_rate'").fetchone()[0]:
            connection.create_function("annual_rate", quote, [TIMESTAMP, BIGINT, BIGINT], DOUBLE)
        for statement in [item.strip() for item in sql.split(";") if item.strip()]:
            connection.execute(statement)
        if connection.execute("SELECT count(*) FROM duckdb_views() WHERE view_name = 'ledger'").fetchone()[0]:
            connection.execute(MARKET_SQL)
    except duckdb.Error as error:
        raise DataError(f"validator-week computation failed: {error}") from error


def reason_counts(connection: Any, table: str = "observed") -> dict[str, dict[str, int]]:
    """Delegations per reason code, the null code named ``offered`` or ``eligible``, so each set sums to the row count."""
    counts: dict[str, dict[str, int]] = {}
    for column, null_name, codes in (("not_offered_reason", "offered", NOT_OFFERED_REASONS), ("ineligibility_reason", "eligible", INELIGIBLE_REASONS)):
        found = dict(connection.execute(f"SELECT coalesce({column}, '{null_name}'), count(*) FROM {table} GROUP BY 1").fetchall())
        counts[column] = {name: int(found.pop(name, 0)) for name in (null_name, *codes)} | {name: int(value) for name, value in found.items()}
    return counts


def summarize(connection: Any) -> dict[str, Any]:
    summary = {key: (float(value) if key.endswith("avax") else value) for key, value in zip(SUMMARY_KEYS, connection.execute(SUMMARY_SQL).fetchone())}
    counts = reason_counts(connection)
    summary["delegations_by_not_offered_reason"] = counts["not_offered_reason"]
    summary["delegations_by_ineligibility_reason"] = counts["ineligibility_reason"]
    summary["node_weeks_capacity_below_zero"] = connection.execute(
        "SELECT count(*) FILTER (WHERE capacity_left_avax < 0 OR capacity_left_avax_14d < 0) FROM panel").fetchone()[0]
    return summary


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    """Build one of the two tables into a new run directory holding ``capture/`` and ``dataset/``."""
    _reject(dataset_id)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    inputs = select_inputs(dataset_id, pinned, root)
    completed_at = now()
    records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    parameters = {"window_start": WINDOW_START, "window_end": WINDOW_END, "concentrated_address": CONCENTRATED_ADDRESS,
                  "weight_factor": WEIGHT_FACTOR, "max_weight_avax": MAX_WEIGHT_AVAX, "min_delegation_avax": MIN_DELEGATION_AVAX,
                  "min_duration_days": MIN_DURATION_DAYS, "invariance_cutoff": INVARIANCE_CUTOFF}
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records, "parameters": parameters}))
    capture_receipt = {
        "schema_version": "derived-capture/v1", "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
        "dataset_id": dataset_id, "source_id": SOURCE_ID, "completed_at": completed_at,
        "contract_sha256": contract_hash(catalog, dataset_id), "tool": f"avalanche-research@{__version__}",
        "inputs": records, "parameters": parameters,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "capture").mkdir()
        (temporary / "dataset").mkdir()
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet_path = temporary / "dataset" / f"{TABLES[dataset_id]}.parquet"
        connection = duckdb.connect()
        try:
            load_inputs(connection, {item["input_id"]: item["path"] for item in inputs})
            compute(connection)
            table = {WEEKS_ID: "panel", DELEGATIONS_ID: "observed", MARKET_ID: "market"}[dataset_id]
            connection.execute(f"COPY {table} TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection)
            # The shared summary counts the panel. Rows and keys on the receipt describe the table this run holds.
            key = {WEEKS_ID: "node_id, week_start_utc", DELEGATIONS_ID: "transaction_hash", MARKET_ID: "week_start_utc"}[dataset_id]
            summary["rows"], summary["distinct_keys"] = connection.execute(f"SELECT count(*), count(DISTINCT ({key})) FROM {table}").fetchone()
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "derived-build/v1", "dataset_id": dataset_id, "dataset_schema": definition["fields"],
            "source_capture_id": capture_receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": summary,
            "outputs": [{"path": parquet_path.name, "bytes": parquet_path.stat().st_size, "sha256": sha256(parquet_path.read_bytes())}],
        }
        (temporary / "dataset" / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"capture": capture_receipt, "build": build_receipt}


def read_capture(capture_dir: Path) -> dict[str, Any]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"unreadable capture receipt: {error}") from error
    if receipt.get("schema_version") != "derived-capture/v1" or receipt.get("dataset_id") not in DATASET_IDS:
        raise DataError(f"not a validator-week capture: {capture_dir}")
    return receipt


def invariance(paths: dict[str, Path], cutoff: str = INVARIANCE_CUTOFF) -> dict[str, Any]:
    """Rows for weeks before ``cutoff`` built from every input against the same rows built from transactions accepted
    before ``cutoff`` only. No row in either set and not the other proves no early row reads a later event."""
    connection = duckdb.connect()
    try:
        load_inputs(connection, paths)
        compute(connection)
        connection.execute("ALTER TABLE panel RENAME TO panel_full")
        compute(connection, known_until=cutoff)
        early = f"week_start_utc < TIMESTAMP '{cutoff}'"
        rows, only_full, only_truncated = connection.execute(f"""
            SELECT (SELECT count(*) FROM panel_full WHERE {early}),
                   (SELECT count(*) FROM (SELECT * FROM panel_full WHERE {early} EXCEPT ALL SELECT * FROM panel WHERE {early})),
                   (SELECT count(*) FROM (SELECT * FROM panel WHERE {early} EXCEPT ALL SELECT * FROM panel_full WHERE {early}))
        """).fetchone()
    finally:
        connection.close()
    return {"cutoff": cutoff, "rows": int(rows), "rows_only_in_full": int(only_full), "rows_only_in_truncated": int(only_truncated),
            "equal": only_full == 0 and only_truncated == 0}


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """Input hashes, the contract, the columns, one row per key, every delegation accounted for, and the append-future
    rule: early rows rebuilt from truncated inputs equal the full build's."""
    if against is not None:
        raise DataError("the validator-week tables take no --against directory")
    catalog = load_catalog()
    receipt = read_capture(capture_dir)
    dataset_id = receipt["dataset_id"]
    findings: list[str] = []
    checked = ["input run hashes", "catalog contract"]
    if receipt.get("contract_sha256") != contract_hash(catalog, dataset_id):
        findings.append("catalog contract changed since the capture")
    root_dir = datasets.RUNS if root is None else root
    paths: dict[str, Path] = {}
    for item in receipt.get("inputs", []):
        parquet = root_dir / item["run"] / "dataset" / item["parquet"]
        if not parquet.is_file():
            findings.append(f"input run missing: {item['run']}")
            continue
        body = parquet.read_bytes()
        if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
            findings.append(f"input run differs from the capture receipt: {item['run']}")
        paths[item["input_id"]] = parquet
    summary: dict[str, Any] = {"inputs": len(receipt.get("inputs", []))}
    if dataset_dir is not None:
        checked.extend(["build hashes", "columns", "one row per key", "every delegation accounted for"])
        try:
            build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
            if build_receipt.get("source_capture_id") != receipt.get("capture_id"):
                findings.append("build does not belong to this capture")
            for item in build_receipt["outputs"]:
                body = (dataset_dir / item["path"]).read_bytes()
                if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                    findings.append(f"output hash or size differs: {item['path']}")
            connection = duckdb.connect()
            try:
                parquet = str(dataset_dir / f"{TABLES[dataset_id]}.parquet").replace("'", "''")
                connection.execute(f"CREATE VIEW built AS SELECT * FROM read_parquet('{parquet}')")
                columns = [row[0] for row in connection.execute("DESCRIBE built").fetchall()]
                expected = {WEEKS_ID: WEEK_COLUMNS, DELEGATIONS_ID: DELEGATION_COLUMNS, MARKET_ID: MARKET_COLUMNS}[dataset_id]
                if columns != list(expected):
                    findings.append("Parquet columns differ from the declared fields")
                key = {WEEKS_ID: "node_id, week_start_utc", DELEGATIONS_ID: "transaction_hash", MARKET_ID: "week_start_utc"}[dataset_id]
                rows, keys = connection.execute(f"SELECT count(*), count(DISTINCT ({key})) FROM built").fetchone()
                summary.update({"rows": rows, "distinct_keys": keys})
                if rows != keys:
                    findings.append(f"{rows - keys} rows repeat a key")
                if dataset_id == DELEGATIONS_ID:
                    checked.append("every delegation classified")
                    counts = reason_counts(connection, "built")
                    summary["reasons"] = counts
                    for column, values in counts.items():
                        if sum(values.values()) != rows:
                            findings.append(f"{column} counts sum to {sum(values.values())}, not {rows}")
                    mismatched = connection.execute(
                        "SELECT count(*) FILTER (WHERE (not_offered_reason IS NULL) <> validator_offered_at_week_start), "
                        "count(*) FILTER (WHERE (ineligibility_reason IS NULL) IS DISTINCT FROM eligible_at_accept), "
                        "count(*) FILTER (WHERE not_offered_reason = 'unclassified') FROM built").fetchone()
                    for count, text in zip(mismatched, ("not_offered_reason disagrees with the cutoff flag",
                                                        "ineligibility_reason disagrees with eligible_at_accept", "delegations unclassified")):
                        if count:
                            findings.append(f"{count} {text}")
            finally:
                connection.close()
            built = build_receipt["summary"]
            summary.update({name: built[name] for name in SUMMARY_KEYS if name in built})
            if built["panel_delegations"] != built["delegations_with_row"]:
                findings.append(f"the panel's outcomes count {built['panel_delegations']} delegations, the rows own {built['delegations_with_row']}")
            summary["delegations_without_row"] = built["delegations"] - built["delegations_with_row"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
            findings.append(f"invalid dataset output: {error}")
    if dataset_id == WEEKS_ID and set(paths) == set(INPUTS):
        checked.append("rows before the invariance cutoff do not read later events")
        result = invariance(paths, receipt.get("parameters", {}).get("invariance_cutoff", INVARIANCE_CUTOFF))
        summary["invariance"] = result
        if not result["equal"]:
            findings.append(f"rows before {result['cutoff']} change when later events are added")
    return {"dataset_id": dataset_id, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}
