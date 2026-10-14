"""Accepted staking commitments, summarized by calendar interval or upgrade era."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, timedelta
from functools import cache
from uuid import uuid4

import duckdb
import holoviews as hv
import pandas as pd
import panel as pn
import param as pm
from bokeh.core.properties import value
from bokeh.models import (
    BoxAnnotation,
    ColumnDataSource,
    DataRange1d,
    DatetimeAxis,
    FixedTicker,
    HoverTool,
    Legend,
    LegendItem,
    Range1d,
    Span,
)
from bokeh.plotting import figure

from . import datasets
from .model.protocol import MAINNET_UPGRADES
from .palette import QUANTITY_COLORS

DAY = timedelta(days=1)
NETWORK_START = pd.Timestamp("2020-09-10")
DAYS_PER_RATE_PERIOD = {"Day": 1, "Week": 7, "Year": 365.2425}
MEASURES = (
    "commitments", "stake_avax", "stake_duration_avax_days",
    "duration_days", "observed_rewards_avax", "reward_outcomes",
)
IDENTITY_COLUMNS = ("Total Nodes", "Total Validator Reward Addresses", "Total Delegator Funding Addresses")
ADDRESS_LINK_COLUMNS = ("Validator Node-address Pairs", "Delegator Node-address Pairs")
LINKED_NODE_COLUMNS = ("Validator Nodes with Addresses", "Delegator Nodes with Addresses")
VIEWS = ("Total", "Per Calendar Unit", "Per Commitment", "Per Node", "Per Node per Calendar Unit",
         "Per Address", "Per Address per Calendar Unit")
CONTEXT_COLUMNS = ("Reporting Interval", "Start (UTC)", "End (UTC)", "Role")


def denominator_options(rate_unit: str) -> dict[str, str]:
    """Show the selected calendar unit without changing the underlying view keys."""
    return {
        "Total": "Total",
        f"Per {rate_unit}": "Per Calendar Unit",
        "Per Commitment": "Per Commitment",
        "Per Node": "Per Node",
        f"Per Node per {rate_unit}": "Per Node per Calendar Unit",
        "Per Address": "Per Address",
        f"Per Address per {rate_unit}": "Per Address per Calendar Unit",
    }


METRIC_SOURCES = {
    "Stake": "stake_avax",
    "Duration": "duration_days",
    "Stake-duration": "stake_duration_avax_days",
    "Rewards": "observed_rewards_avax",
}
QUANTITIES = ("Nodes", "Addresses", "Commitments", *METRIC_SOURCES)
METRIC_COLUMNS = {
    "Stake": {
        "Total": "Total Stake (AVAX)",
        "Per Calendar Unit": "Stake / {period} (AVAX)",
        "Per Commitment": "Stake / Commitment (AVAX)",
        "Per Node": "Stake / Node (AVAX)",
        "Per Node per Calendar Unit": "Stake / Node / {period} (AVAX)",
        "Per Address": "Stake / Address (AVAX)",
        "Per Address per Calendar Unit": "Stake / Address / {period} (AVAX)",
    },
    "Duration": {
        "Total": "Total Committed Duration (commitment-days)",
        "Per Calendar Unit": "Committed Duration / {period} (commitment-days/{period_unit})",
        "Per Commitment": "Duration / Commitment (days)",
        "Per Node": "Committed Duration / Node (commitment-days/node)",
        "Per Node per Calendar Unit": "Committed Duration / Node / {period} (commitment-days/node/{period_unit})",
        "Per Address": "Committed Duration / Address (commitment-days/address)",
        "Per Address per Calendar Unit": "Committed Duration / Address / {period} (commitment-days/address/{period_unit})",
    },
    "Stake-duration": {
        "Total": "Total Stake-duration ({stake_time_unit})",
        "Per Calendar Unit": "Stake-duration / {period} ({stake_time_unit}/{period_unit})",
        "Per Commitment": "Stake-duration / Commitment ({stake_time_unit})",
        "Per Node": "Stake-duration / Node ({stake_time_unit})",
        "Per Node per Calendar Unit": "Stake-duration / Node / {period} ({stake_time_unit}/{period_unit})",
        "Per Address": "Stake-duration / Address ({stake_time_unit})",
        "Per Address per Calendar Unit": "Stake-duration / Address / {period} ({stake_time_unit}/{period_unit})",
    },
    "Rewards": {
        "Total": "Total Rewards (AVAX)",
        "Per Calendar Unit": "Rewards / {period} (AVAX)",
        "Per Commitment": "Rewards / Commitment (AVAX)",
        "Per Node": "Rewards / Node (AVAX)",
        "Per Node per Calendar Unit": "Rewards / Node / {period} (AVAX)",
        "Per Address": "Rewards / Address (AVAX)",
        "Per Address per Calendar Unit": "Rewards / Address / {period} (AVAX)",
    },
}

_IDENTITY_COUNTS_SQL = """
WITH events AS (SELECT * FROM ({events}) {window}),
buckets AS (
    SELECT role, node_id, identity, accepted_at::DATE AS day_bucket,
           date_trunc('week', accepted_at)::DATE AS week_bucket,
           date_trunc('year', accepted_at)::DATE AS year_bucket,
           {era_bucket} AS era_bucket
    FROM events
)
SELECT role,
       CASE WHEN grouping(day_bucket) = 0 THEN 'Day'
            WHEN grouping(week_bucket) = 0 THEN 'Week'
            WHEN grouping(year_bucket) = 0 THEN 'Year'
            WHEN grouping(era_bucket) = 0 THEN 'Era' ELSE 'All' END AS grain,
       CASE WHEN grouping(day_bucket) = 0 THEN day_bucket::VARCHAR
            WHEN grouping(week_bucket) = 0 THEN week_bucket::VARCHAR
            WHEN grouping(year_bucket) = 0 THEN year_bucket::VARCHAR
            WHEN grouping(era_bucket) = 0 THEN era_bucket ELSE 'All' END AS bucket,
       count(DISTINCT node_id) AS nodes,
       count(DISTINCT identity) AS identities,
       count(DISTINCT (node_id, identity)) FILTER (WHERE node_id IS NOT NULL AND identity IS NOT NULL) AS links,
       count(DISTINCT node_id) FILTER (WHERE identity IS NOT NULL) AS linked_nodes
FROM buckets
GROUP BY GROUPING SETS ((role, day_bucket), (role, week_bucket), (role, year_bucket),
                        (role, era_bucket), (role))
"""
_IDENTITY_GRAIN_SQL = """
WITH events AS (SELECT * FROM ({events}) WHERE accepted_at >= ? AND accepted_at < ?),
buckets AS (SELECT role, node_id, identity, {bucket} AS bucket FROM events)
SELECT role, '{grain}' AS grain, bucket,
       count(DISTINCT node_id) AS nodes,
       count(DISTINCT identity) AS identities,
       count(DISTINCT (node_id, identity)) FILTER (WHERE node_id IS NOT NULL AND identity IS NOT NULL) AS links,
       count(DISTINCT node_id) FILTER (WHERE identity IS NOT NULL) AS linked_nodes
FROM buckets GROUP BY role, bucket
"""
def _era_bucket_sql() -> str:
    changes = []
    for upgrade in MAINNET_UPGRADES.upgrades:
        era = "apricot" if upgrade.name.startswith("apricot_") else upgrade.name
        if not changes or era != changes[-1][0]:
            changes.append((era, upgrade.activated_at.astimezone(UTC)))
    clauses = [f"WHEN accepted_at >= TIMESTAMP '{instant:%Y-%m-%d %H:%M:%S}' THEN '{era}'"
               for era, instant in reversed(changes)]
    return "CASE " + " ".join(clauses) + " ELSE 'genesis' END"


IDENTITY_BUCKETS = {
    "Day": "accepted_at::DATE::VARCHAR",
    "Week": "date_trunc('week', accepted_at)::DATE::VARCHAR",
    "Year": "date_trunc('year', accepted_at)::DATE::VARCHAR",
    "Era": _era_bucket_sql(),
    "All": "'All'",
}

_REWARD_ADDRESS_EVENTS = """
SELECT 'validator' AS role, validator.accepted_at, validator.node_id,
       json_extract_string(address.value, '$') AS identity
FROM read_parquet(?) validator LEFT JOIN LATERAL json_each(validator.reward_addresses) address ON TRUE
"""
_DELEGATOR_ADDRESS_EVENTS = """
SELECT 'delegator' AS role, accepted_at, node_id, delegator_address AS identity FROM read_parquet(?)
"""


def _metric_column(metric: str, view: str, period: str = "Day") -> str:
    return METRIC_COLUMNS[metric][view].format(
        period=period, period_unit=period.lower(), stake_time_unit=f"AVAX-{period.lower()}s",
    )


def accepted_commitments(parquet: str) -> pd.DataFrame:
    """Scan the pinned period log once; keep only small daily, role, era totals."""
    with duckdb.connect() as db:
        return db.execute(
            """
            SELECT accepted_at::DATE AS accepted_day, role,
                   CASE WHEN starts_with(regime, 'apricot_') THEN 'apricot' ELSE regime END AS era,
                   min(accepted_at) AS first_accepted,
                   count(*) AS commitments,
                   sum(stake_navax)::DOUBLE / 1e9 AS stake_avax,
                   sum(stake_navax::DOUBLE * duration_days) / 1e9 AS stake_duration_avax_days,
                   sum(duration_days) AS duration_days,
                   coalesce(sum(realized_reward_navax) FILTER (WHERE rewarded_at IS NOT NULL), 0)::DOUBLE / 1e9
                       AS observed_rewards_avax,
                   count(rewarded_at) AS reward_outcomes
            FROM read_parquet(?)
            GROUP BY 1, 2, 3
            """,
            [parquet],
        ).df()


def distinct_identities(validators: str, delegators: str,
                        start: pd.Timestamp | None = None,
                        end: pd.Timestamp | None = None,
                        grain: str | None = None) -> pd.DataFrame:
    """Count nodes, addresses, and distinct observed node-address links by interval."""
    sources = [
        ("Total Validator Reward Addresses", ADDRESS_LINK_COLUMNS[0], LINKED_NODE_COLUMNS[0],
         _REWARD_ADDRESS_EVENTS, validators),
        ("Total Delegator Funding Addresses", ADDRESS_LINK_COLUMNS[1], LINKED_NODE_COLUMNS[1],
         _DELEGATOR_ADDRESS_EVENTS, delegators),
    ]
    with duckdb.connect() as db:
        parts = []
        for column, links, linked_nodes, events, parquet in sources:
            if grain is None:
                window = "WHERE accepted_at >= ? AND accepted_at < ?" if start is not None else ""
                sql = _IDENTITY_COUNTS_SQL.format(events=events, window=window,
                                                  era_bucket=IDENTITY_BUCKETS["Era"])
            else:
                sql = _IDENTITY_GRAIN_SQL.format(events=events, grain=grain,
                                                  bucket=IDENTITY_BUCKETS[grain])
            part = db.execute(sql, [parquet, start, end] if start is not None else [parquet]).df()
            part = part.rename(columns={"identities": column, "nodes": "Total Nodes"})
            part = part.rename(columns={"links": links, "linked_nodes": linked_nodes})
            parts.append(part)
    return pd.concat(parts, ignore_index=True)


def _source_cutoffs(capture: Mapping) -> dict[str, pd.Timestamp]:
    inputs = {item["input_id"]: item for item in capture["inputs"]}
    return {
        role: pd.Timestamp(inputs[source]["captured_at"]).tz_convert(None)
        for role, source in (("validator", "validator-stakes"), ("delegator", "delegator-stakes"))
    }


def _era_intervals(start: pd.Timestamp, end: pd.Timestamp):
    changes = [("genesis", start)]
    for upgrade in MAINNET_UPGRADES.upgrades:
        era = "apricot" if upgrade.name.startswith("apricot_") else upgrade.name
        if era != changes[-1][0]:
            changes.append((era, pd.Timestamp(upgrade.activated_at.astimezone(UTC)).tz_localize(None)))
    for index, (era, beginning) in enumerate(changes):
        finish = changes[index + 1][1] if index + 1 < len(changes) else end
        if beginning < end and finish > start:
            yield era, max(beginning, start), min(finish, end)


# Canonical reporting is separate from the interactive explorer's aggregations.
CANONICAL_ERA_FAMILIES = (
    "Window",
    "Complete ledger days",
    "Commitments",
    "Nodes",
    "Operators",
    "Commitments per node, per day",
    "Gross stake committed",
    "Stake per commitment",
    "Stake-weighted median stake",
    "Duration",
    "Stake-weighted duration",
    "Auto-renewed share",
    "Committed AVAX-days",
    "Committed AVAX-days per day",
    "Calendar AVAX-days",
    "Closed share",
    "Failed share",
    "Realized rewards of the cohort",
    "Cohort earned rate",
    "Fee rate",
    "Delegations and delegated stake",
    "Mean supply",
    "Mean active stake",
    "Staking ratio",
    "Issued in the window",
    "Burned in the window",
    "Calendar earned rate",
    "Net inflation",
    "Concentration",
)
_CANONICAL_INPUTS = {
    "derived.staking-periods": "periods",
    "derived.avax-monetary-daily": "ledger",
    "derived.seamed-validator-stakes": "validators",
    "derived.seamed-delegator-stakes": "delegators",
    "derived.p-chain-staking-cycles": "cycles",
}


def _report_digest(path):
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _report_utc(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError(f"source cutoff needs an explicit UTC offset: {value}")
    return stamp.tz_convert("UTC").tz_localize(None)


def _report_iso(value):
    return None if value is None else pd.Timestamp(value).isoformat() + "Z"


def _canonical_inputs(pin, root):
    """Verify explicit pin bytes and receipts before opening any analytical relation."""
    import json
    from pathlib import Path

    from .core.catalog import DataError
    from .datasets import pins

    pin = Path(pin)
    value = pins.read(pin)
    entries = value.get("runs", [])
    if len(entries) != len(_CANONICAL_INPUTS) or {
        e["dataset_id"] for e in entries
    } != set(_CANONICAL_INPUTS):
        raise DataError(
            "canonical era table needs exactly the five staking-record datasets, each once"
        )
    findings = pins.code_findings(value["code"]) if "code" in value else []
    if findings:
        raise DataError("; ".join(findings))
    directory = datasets.RUNS if root is None else Path(root)
    records, paths, bindings = {}, {}, []
    for entry in entries:
        for key in ("run", "parquet"):
            if (
                not isinstance(entry[key], str)
                or Path(entry[key]).name != entry[key]
                or entry[key] in {".", ".."}
            ):
                raise DataError(f"unsafe pinned {key}")
        run = directory / entry["run"]
        path = run / "dataset" / entry["parquet"]
        try:
            receipts = {
                name: json.loads((run / name).read_text())
                for name in (
                    "capture/capture.json",
                    "dataset/build.json",
                    "dataset/check.json",
                )
            }
            capture, build, check = (receipts[name] for name in receipts)
            if (
                path.stat().st_size != entry["bytes"]
                or _report_digest(path) != entry["sha256"]
                or capture["dataset_id"] != entry["dataset_id"]
                or build["dataset_id"] != entry["dataset_id"]
                or capture["capture_id"] != entry["capture_id"]
                or build["source_capture_id"] != entry["capture_id"]
                or check["status"] != "pass"
                or entry["check"] != "pass"
            ):
                raise DataError(
                    f"pinned input differs or its check does not pass: {entry['dataset_id']}"
                )
            output = next(o for o in build["outputs"] if o["path"] == entry["parquet"])
            if (
                output.get("sha256") != entry["sha256"]
                or output.get("bytes") != entry["bytes"]
            ):
                raise DataError(f"build output differs from pin: {entry['dataset_id']}")
            if entry.get("captured_at") != capture["completed_at"]:
                raise DataError(
                    f"capture cutoff differs from pin: {entry['dataset_id']}"
                )
            for name, expected in entry.get("receipt_hashes", {}).items():
                if name not in receipts or _report_digest(run / name) != expected:
                    raise DataError(
                        f"pinned receipt differs: {entry['dataset_id']} {name}"
                    )
        except (OSError, KeyError, StopIteration, ValueError) as error:
            raise DataError(
                f"unreadable pinned input {entry['dataset_id']}: {error}"
            ) from error
        records[entry["dataset_id"]] = capture
        paths[_CANONICAL_INPUTS[entry["dataset_id"]]] = path
        bindings.append(
            {
                **entry,
                "receipt_hashes": {
                    name: _report_digest(run / name) for name in receipts
                },
            }
        )
    period_inputs = {
        i["dataset_id"]: i for i in records["derived.staking-periods"]["inputs"]
    }
    for entry in entries:
        if entry["dataset_id"] in {
            "derived.seamed-validator-stakes",
            "derived.seamed-delegator-stakes",
            "derived.p-chain-staking-cycles",
        }:
            upstream = period_inputs.get(entry["dataset_id"], {})
            if any(
                upstream.get(k) != entry[k] for k in ("run", "sha256", "capture_id")
            ):
                raise DataError(
                    f"period receipt does not bind pinned input: {entry['dataset_id']}"
                )
    ledger_inputs = {
        i["dataset_id"]: i for i in records["derived.avax-monetary-daily"]["inputs"]
    }
    period_entry = next(
        e for e in entries if e["dataset_id"] == "derived.staking-periods"
    )
    upstream = ledger_inputs.get("derived.staking-periods", {})
    if any(upstream.get(k) != period_entry[k] for k in ("run", "sha256", "capture_id")):
        raise DataError("ledger receipt does not bind the pinned staking periods")
    return records, paths, {"pin_sha256": _report_digest(pin), "inputs": bindings}


def _canonical_windows(cutoffs):
    changes = [("genesis", NETWORK_START)]
    for upgrade in MAINNET_UPGRADES.upgrades:
        era = "apricot" if upgrade.name.startswith("apricot_") else upgrade.name
        if era != changes[-1][0]:
            changes.append((era, pd.Timestamp(upgrade.activated_at).tz_convert(None)))
    rows = []
    for role, cutoff in cutoffs.items():
        windows = [("All", NETWORK_START, None)] + [
            (era.title(), start, changes[i + 1][1] if i + 1 < len(changes) else None)
            for i, (era, start) in enumerate(changes)
        ]
        for era, start, scheduled in windows:
            end = min(cutoff, scheduled) if scheduled is not None else cutoff
            rows.append(
                {
                    "role": role,
                    "era": era,
                    "start": start,
                    "end": end,
                    "scheduled": scheduled,
                    "partial": scheduled is None or cutoff < scheduled,
                    "days": max(0.0, (end - start).total_seconds() / 86400),
                }
            )
    return rows


def _canonical_relations(db, paths, cutoffs, reward_cutoff, cycle_cutoff):
    from .core.catalog import DataError

    for name, path in paths.items():
        quoted = str(path).replace("'", "''")
        db.execute(f"CREATE TEMP VIEW {name} AS SELECT * FROM read_parquet('{quoted}')")
    bad = db.execute("""
        SELECT count(*) FROM periods WHERE transaction_hash IS NULL OR node_id IS NULL
        OR role IS NULL OR role NOT IN ('validator','delegator') OR tx_type IS NULL OR accepted_at IS NULL OR start_time IS NULL OR end_time IS NULL
        OR stake_navax IS NULL OR stake_navax <= 0 OR end_time <= start_time OR NOT isfinite(duration_days)
        OR duration_days IS NULL OR duration_days <= 0 OR (realized_reward_navax IS NOT NULL AND realized_reward_navax < 0)
        UNION ALL SELECT count(*)-count(DISTINCT transaction_hash) FROM periods
        UNION ALL SELECT count(*) FROM cycles c LEFT JOIN periods p ON p.transaction_hash=c.validator_transaction_hash
        WHERE p.transaction_hash IS NULL OR p.role<>'validator' OR p.tx_type<>'AddAutoRenewedValidatorTx'
        OR c.node_id IS NULL OR c.start_time IS NULL OR c.end_time IS NULL
        OR c.restaked_validation_navax<0 OR c.restaked_delegatee_navax<0
        OR c.withdrawn_validation_navax<0 OR c.withdrawn_delegatee_navax<0
        OR c.node_id<>p.node_id OR c.weight_navax IS NULL OR c.weight_navax<=0 OR c.end_time<=c.start_time
        OR c.cycle IS NULL OR c.cycle<1
        UNION ALL SELECT count(*) FROM (SELECT validator_transaction_hash,cycle,count(*) n FROM cycles GROUP BY 1,2 HAVING n<>1)
        UNION ALL SELECT count(*) FROM (SELECT validator_transaction_hash FROM cycles GROUP BY 1 HAVING min(cycle)<>1 OR max(cycle)<>count(*))
        UNION ALL SELECT count(*) FROM ledger WHERE date_utc IS NULL OR complete IS NULL
        OR (complete AND (total_supply_close_wei IS NULL OR total_supply_close_wei<=0
        OR issued_rewards_wei IS NULL OR issued_rewards_wei<0 OR burned_wei IS NULL OR burned_wei<0
        OR active_validator_stake_wei IS NULL OR active_validator_stake_wei<0
        OR active_delegated_stake_wei IS NULL OR active_delegated_stake_wei<0))
        UNION ALL SELECT count(*)-count(DISTINCT date_utc) FROM ledger
    """).fetchall()
    if any(n for (n,) in bad):
        raise DataError(
            "canonical inputs contain invalid or duplicate period/cycle/ledger rows"
        )
    missing = db.execute(
        """SELECT count(*) FROM periods p WHERE tx_type='AddAutoRenewedValidatorTx'
        AND accepted_at < ? AND NOT EXISTS (SELECT 1 FROM cycles c WHERE c.validator_transaction_hash=p.transaction_hash)""",
        [cutoffs["validator"]],
    ).fetchone()[0]
    if missing:
        raise DataError("an accepted auto-renewed validator has no pinned cycles")
    db.execute(
        """CREATE TEMP TABLE commitments AS
        SELECT transaction_hash, role, node_id, accepted_at AS decision_at, accepted_at AS parent_accepted_at,
               start_time, end_time, stake_navax, duration_days, delegation_fee_rate,
               false AS auto_renew, false AS renewal_cycle,
               (rewarded_at IS NOT NULL AND rewarded_at < ? AND realized_reward_navax IS NOT NULL
                AND rewarded IS NOT NULL AND end_time <= ?) AS closed_known,
               rewarded, realized_reward_navax AS reward_navax
        FROM periods WHERE tx_type IS DISTINCT FROM 'AddAutoRenewedValidatorTx'
        AND accepted_at < CASE WHEN role='validator' THEN ? ELSE ? END
        UNION ALL
        SELECT p.transaction_hash, p.role, p.node_id,
               CASE WHEN c.cycle=1 THEN p.accepted_at ELSE c.start_time END, p.accepted_at,
               c.start_time, c.end_time, c.weight_navax,
               epoch(c.end_time-c.start_time)/86400.0, p.delegation_fee_rate,
               true, c.cycle>1,
               (c.reward_transaction_hash IS NOT NULL AND c.rewarded IS NOT NULL AND c.end_time <= ?
                AND c.restaked_validation_navax IS NOT NULL AND c.restaked_delegatee_navax IS NOT NULL
                AND c.withdrawn_validation_navax IS NOT NULL AND c.withdrawn_delegatee_navax IS NOT NULL),
               c.rewarded, c.restaked_validation_navax::HUGEINT+c.restaked_delegatee_navax::HUGEINT
                          +c.withdrawn_validation_navax::HUGEINT+c.withdrawn_delegatee_navax::HUGEINT
        FROM periods p JOIN cycles c ON c.validator_transaction_hash=p.transaction_hash
        WHERE (CASE WHEN c.cycle=1 THEN p.accepted_at ELSE c.start_time END) < ?
    """,
        [
            reward_cutoff,
            reward_cutoff,
            cutoffs["validator"],
            cutoffs["delegator"],
            cycle_cutoff,
            cutoffs["validator"],
        ],
    )
    db.execute(
        f"CREATE TEMP VIEW era_commitments AS SELECT *, {_era_bucket_sql().replace('accepted_at', 'decision_at')} AS era_key FROM commitments"
    )


def _canonical_statistics(db):
    """Exact row medians and cumulative-stake medians. Never median of daily medians."""
    return (
        db.execute("""
        WITH expanded AS (SELECT * EXCLUDE(era_key), era_key AS bucket FROM era_commitments
                          UNION ALL SELECT * EXCLUDE(era_key), 'All' FROM era_commitments),
        weighted AS (
            SELECT *, sum(stake_navax::HUGEINT) OVER(PARTITION BY role,bucket) total_weight,
                   sum(stake_navax::HUGEINT) OVER(PARTITION BY role,bucket ORDER BY stake_navax ROWS UNBOUNDED PRECEDING) size_weight,
                   sum(stake_navax::HUGEINT) OVER(PARTITION BY role,bucket ORDER BY duration_days,stake_navax ROWS UNBOUNDED PRECEDING) duration_weight
            FROM expanded)
        SELECT role,bucket,count(*) n,count(DISTINCT node_id) nodes,
          sum(stake_navax::HUGEINT)::DOUBLE/1e9 stake, sum(stake_navax::DOUBLE*duration_days)/1e9 avax_days,
          avg(stake_navax)::DOUBLE/1e9 mean_stake, median(stake_navax)::DOUBLE/1e9 median_stake,
          min(stake_navax) FILTER(WHERE 2*size_weight>=total_weight)::DOUBLE/1e9 weighted_median_stake,
          avg(duration_days) mean_duration,median(duration_days) median_duration,
          min(duration_days) FILTER(WHERE 2*duration_weight>=total_weight) weighted_median_duration,
          count(*) FILTER(WHERE auto_renew) auto_count,coalesce(sum(stake_navax::HUGEINT) FILTER(WHERE auto_renew),0)::DOUBLE/1e9 auto_stake,
          count(*) FILTER(WHERE renewal_cycle) renewal_count,
          coalesce(sum(stake_navax::HUGEINT) FILTER(WHERE renewal_cycle),0)::DOUBLE/1e9 renewal_stake,
          count(*) FILTER(WHERE closed_known) closed_count,
          coalesce(sum(stake_navax::HUGEINT) FILTER(WHERE closed_known),0)::DOUBLE/1e9 closed_stake,
          sum(stake_navax::DOUBLE*duration_days) FILTER(WHERE closed_known)/1e9 closed_avax_days,
          sum(reward_navax::HUGEINT) FILTER(WHERE closed_known)::DOUBLE/1e9 rewards,
          count(*) FILTER(WHERE closed_known AND NOT rewarded) failed_count,
          coalesce(sum(stake_navax::HUGEINT) FILTER(WHERE closed_known AND NOT rewarded),0)::DOUBLE/1e9 failed_stake,
          avg(delegation_fee_rate) fee_mean,median(delegation_fee_rate) fee_median,
          count(delegation_fee_rate) fee_count,
          sum(stake_navax::HUGEINT) FILTER(WHERE delegation_fee_rate IS NOT NULL)::DOUBLE/1e9 fee_stake,
          sum(stake_navax::DOUBLE*delegation_fee_rate)/sum(stake_navax::DOUBLE) FILTER(WHERE delegation_fee_rate IS NOT NULL) fee_weighted_mean
        FROM weighted GROUP BY role,bucket
    """)
        .df()
        .set_index(["role", "bucket"])
    )


def era_stocks(db, start, end):
    """Complete UTC days whose 23:59:59 stock observation lies in [start,end).

    Flow sums and rate denominators use this identical support. Day-close assignment does
    not prorate an upgrade day. It is distinct from fractional protocol-window duration.
    """
    return (
        db.execute(
            """WITH supported AS (SELECT *, date_utc::TIMESTAMP+INTERVAL '23:59:59' AS close_at
        FROM ledger WHERE complete AND date_utc::TIMESTAMP+INTERVAL '23:59:59' >= ?
        AND date_utc::TIMESTAMP+INTERVAL '23:59:59' < ?),
        weights AS (SELECT l.*, coalesce((SELECT sum(c.weight_navax::HUGEINT-p.stake_navax::HUGEINT)
            FROM cycles c JOIN periods p ON p.transaction_hash=c.validator_transaction_hash
            WHERE c.start_time<=l.close_at AND c.end_time>l.close_at),0) AS restaked_navax FROM supported l)
        SELECT count(*) AS "days",
        avg(total_supply_close_wei::DOUBLE)/1e18 supply,
        avg(active_validator_stake_wei::DOUBLE)/1e18 validator_stake,
        avg(active_delegated_stake_wei::DOUBLE)/1e18 delegated_stake,
        avg(active_validator_stake_wei::DOUBLE/1e9+restaked_navax::DOUBLE)/1e9 validator_cycle_stake,
        avg(restaked_navax::DOUBLE)/1e9 active_restaked_increment,
        sum(active_validator_stake_wei::DECIMAL(38,0))::DOUBLE/1e18 validator_days,
        sum(active_delegated_stake_wei::DECIMAL(38,0))::DOUBLE/1e18 delegated_days,
        avg(100*active_validator_stake_wei::DOUBLE/total_supply_close_wei::DOUBLE) validator_ratio,
        avg(100*(active_validator_stake_wei::DOUBLE+active_delegated_stake_wei::DOUBLE)/total_supply_close_wei::DOUBLE) combined_ratio,
        sum(issued_rewards_wei::DECIMAL(38,0))::DOUBLE/1e18 issued,
        sum(burned_wei::DECIMAL(38,0))::DOUBLE/1e18 burned
        FROM weights""",
            [start, end],
        )
        .df()
        .iloc[0]
        .to_dict()
    )


def _canonical_identity(db, paths, windows):
    """Dated address groups on transaction-base stock, the monetary ledger's basis."""
    from .core.catalog import DataError
    from .datasets.derived import identity

    path = str(paths["validators"]).replace("'", "''")
    edge_table = db.execute(identity.EDGES_SQL.format(validators=path)).df()
    ties = edge_table.groupby(["node_id", "evidence_at"])["transaction_hash"].nunique()
    if (ties > 1).any():
        raise DataError(
            "validator dated addresses are ambiguous at a tied acceptance instant"
        )
    edge_table = edge_table.sort_values(
        ["evidence_at", "transaction_hash", "address"], kind="stable"
    )
    stocks = db.execute("""SELECT transaction_hash,node_id,start_time,
        greatest(end_time,coalesce(last_cycle_end_time,end_time)) AS stake_end,stake_navax
        FROM periods WHERE role='validator'""").df()
    cohort_nodes = db.execute(
        "SELECT DISTINCT node_id,decision_at FROM commitments WHERE role='validator'"
    ).df()
    days = db.execute(
        "SELECT date_utc,active_validator_stake_wei FROM ledger WHERE complete ORDER BY date_utc"
    ).fetchall()
    daily = []
    for day, ledger_weight in days:
        at = pd.Timestamp(f"{day}T23:59:59")
        active = stocks[stocks.start_time.le(at) & stocks.stake_end.gt(at)]
        groups = identity.groups(edge_table, at)
        joined = active.merge(
            groups[["node_id", "group_id"]],
            on="node_id",
            how="left",
            validate="many_to_one",
        )
        weight = sum(int(x) for x in active.stake_navax)
        known = joined.group_id.notna()
        supported = bool(
            weight and known.all() and weight * 10**9 == int(ledger_weight)
        )
        share = None
        if supported:
            by_group = {}
            for group, amount in zip(joined.group_id, joined.stake_navax, strict=True):
                by_group[group] = by_group.get(group, 0) + int(amount)
            share = 100 * sum(sorted(by_group.values(), reverse=True)[:10]) / weight
        daily.append((at, share, supported))
    result = {}
    for window in windows:
        if window["role"] != "validator":
            continue
        start, end = window["start"], window["end"]
        nodes = cohort_nodes[
            cohort_nodes.decision_at.ge(start) & cohort_nodes.decision_at.lt(end)
        ].node_id.unique()
        groups = identity.groups(
            edge_table, end.to_pydatetime() - timedelta(microseconds=1)
        )
        known = groups[groups.node_id.isin(nodes)]
        supported_days = [
            share for at, share, supported in daily if start <= at < end and supported
        ]
        eligible_days = sum(start <= at < end for at, _, _ in daily)
        result[window["era"]] = {
            "operators": known.group_id.nunique() if len(known) == len(nodes) else None,
            "operator_nodes": len(known),
            "cohort_nodes": len(nodes),
            "concentration": sum(supported_days) / len(supported_days)
            if supported_days
            else None,
            "supported_days": len(supported_days),
            "eligible_days": eligible_days,
        }
    return result


def canonical_era_table(
    pin, *, root=None, threads=4, memory_limit="2GB", temporary_directory=None
):
    """Return a pure, pinned long table of 29 measure families for both roles and All plus nine eras.

    Only the small final table and validator identity history enter pandas. Exact medians
    use raw commitment rows inside bounded DuckDB. A missing input, changed pin, duplicate
    grain or unusable complete-ledger row is refused. Existing explorer behavior is untouched.
    Unknown rewards and unsupported delegator ownership remain null, with explicit support.
    Cycle renewal starts are decision-clock proxies, not transaction acceptance timestamps.
    The resulting frame's ``attrs['metadata']`` binds inputs, clocks and stock/reward bases.
    """
    import tempfile
    from contextlib import nullcontext

    from .core.catalog import DataError

    if (
        not isinstance(threads, int)
        or isinstance(threads, bool)
        or not 1 <= threads <= 8
    ):
        raise DataError("threads must be an integer from 1 to 8")
    records, paths, metadata = _canonical_inputs(pin, root)
    period_capture = records["derived.staking-periods"]
    source_cutoffs = _source_cutoffs(period_capture)
    cycle_cutoff = _report_utc(
        records["derived.p-chain-staking-cycles"]["completed_at"]
    )
    cutoffs = {
        "validator": min(source_cutoffs["validator"], cycle_cutoff),
        "delegator": source_cutoffs["delegator"],
    }
    reward_input = next(
        i for i in period_capture["inputs"] if i["input_id"] == "staking-rewards"
    )
    reward_cutoff = _report_utc(reward_input["captured_at"])
    windows = _canonical_windows(cutoffs)
    rows = []
    config = {
        "threads": threads,
        "memory_limit": memory_limit,
        "TimeZone": "UTC",
        "preserve_insertion_order": False,
    }
    scratch = (
        tempfile.TemporaryDirectory(prefix="staking-era-")
        if temporary_directory is None
        else nullcontext(str(temporary_directory))
    )
    with (
        scratch as spill_directory,
        duckdb.connect(config={**config, "temp_directory": spill_directory}) as db,
    ):
        _canonical_relations(db, paths, cutoffs, reward_cutoff, cycle_cutoff)
        stats = _canonical_statistics(db)
        identities = _canonical_identity(db, paths, windows)
        first_nodes = db.execute(
            "SELECT role,node_id,min(decision_at) first_at FROM commitments GROUP BY 1,2"
        ).df()
        for w in windows:
            role, era, start, end, days = (
                w[k] for k in ("role", "era", "start", "end", "days")
            )
            key = (role, "All" if era == "All" else era.lower())
            s = stats.loc[key].to_dict() if key in stats.index else {}
            n, stake = int(s.get("n", 0)), s.get("stake", 0.0)
            closed, closed_stake = (
                int(s.get("closed_count", 0)),
                s.get("closed_stake", 0.0),
            )
            stocks = era_stocks(db, start, end)
            eligible = sum(
                start <= pd.Timestamp(f"{d.date()}T23:59:59") < end
                for d in pd.date_range(
                    start.normalize(), max(start, end).normalize(), freq="D"
                )
            )
            count_coverage = closed / n if n else None
            stake_coverage = closed_stake / stake if stake else None
            context = {
                "role": role,
                "era": era,
                "window_start_utc": _report_iso(start),
                "scheduled_end_utc": _report_iso(w["scheduled"]),
                "effective_cutoff_utc": _report_iso(end),
                "source_capture_cutoff_utc": _report_iso(source_cutoffs[role]),
                "fractional_days": days,
                "partial": w["partial"],
                "ledger_complete_days": int(stocks["days"]),
                "ledger_eligible_days": eligible,
                "ledger_missing_or_incomplete_days": eligible - int(stocks["days"]),
                "closed_count_fraction": count_coverage,
                "closed_stake_fraction": stake_coverage,
                "closed_count_below_95_percent": count_coverage is not None
                and count_coverage < 0.95,
                "closed_stake_below_95_percent": stake_coverage is not None
                and stake_coverage < 0.95,
            }

            def add(
                family,
                statistic,
                value,
                unit,
                weight,
                reduction,
                *,
                population=None,
                clock="Acceptance; renewal-cycle start proxy",
                support=None,
                numerator=None,
                denominator=None,
                support_count=None,
                support_stake=None,
                _context=context,
                _population=f"{role} commitments",
                _n=n,
                _stake=stake,
            ):
                if pd.isna(value):
                    value = None
                if support is None:
                    support = (
                        "Observed" if value is not None else "No supported observations"
                    )
                rows.append(
                    {
                        **_context,
                        "measure_family": family,
                        "statistic": statistic,
                        "value": value,
                        "unit": unit,
                        "population": population or _population,
                        "clock": clock,
                        "weight": weight,
                        "reduction": reduction,
                        "support_status": support,
                        "support_count": _n if support_count is None else support_count,
                        "support_stake_avax": _stake
                        if support_stake is None
                        else support_stake,
                        "numerator_value": numerator,
                        "denominator_value": denominator,
                    }
                )

            def ratio(a, b):
                return (
                    None
                    if a is None or b is None or pd.isna(a) or pd.isna(b) or b == 0
                    else a / b
                )

            add(
                "Window",
                "fractional days",
                days,
                "days",
                "time",
                "elapsed seconds / 86400",
                clock="UTC protocol boundaries",
            )
            add(
                "Complete ledger days",
                "complete close observations",
                stocks["days"],
                "days",
                "time",
                "count",
                clock="23:59:59 UTC close",
                population="Whole-network ledger",
            )
            transactions = db.execute(
                "SELECT count(*) FROM periods WHERE role=? AND accepted_at>=? AND accepted_at<?",
                [role, start, end],
            ).fetchone()[0]
            add(
                "Commitments",
                "commitments including cycles",
                n,
                "commitments",
                "count",
                "count",
            )
            add(
                "Commitments",
                "transactions",
                transactions,
                "transactions",
                "count",
                "count",
                clock="Parent transaction acceptance",
            )
            nodes = int(s.get("nodes", 0))
            add("Nodes", "distinct nodes", nodes, "nodes", "count", "distinct count")
            new = first_nodes[
                first_nodes.role.eq(role)
                & first_nodes.first_at.ge(start)
                & first_nodes.first_at.lt(end)
            ]
            add(
                "Nodes",
                "new nodes",
                len(new),
                "nodes",
                "count",
                "first-ever commitment in window",
            )
            ident = identities.get(era, {}) if role == "validator" else {}
            add(
                "Operators",
                "dated address groups of cohort nodes",
                ident.get("operators"),
                "groups",
                "count",
                "distinct count",
                clock="Exclusive window end minus 1 microsecond",
                population="Validator cohort nodes, shared-reward-address groups",
                support=(
                    "Unsupported delegator ownership"
                    if role == "delegator"
                    else "Observed dated address groups"
                    if ident.get("operators") is not None
                    else "Incomplete dated address coverage"
                ),
                support_count=ident.get("operator_nodes", 0),
            )
            add(
                "Commitments per node, per day",
                "per node",
                ratio(n, nodes),
                "commitments/node",
                "count",
                "ratio of counts",
                numerator=n,
                denominator=nodes,
            )
            add(
                "Commitments per node, per day",
                "per day",
                ratio(n, days),
                "commitments/day",
                "count",
                "count / fractional window days",
                numerator=n,
                denominator=days,
            )
            add(
                "Gross stake committed",
                "total entry flow",
                stake,
                "AVAX",
                "stake",
                "sum",
            )
            add(
                "Gross stake committed",
                "per node",
                ratio(stake, nodes),
                "AVAX/node",
                "stake",
                "sum / distinct nodes",
                numerator=stake,
                denominator=nodes,
            )
            add(
                "Stake per commitment",
                "mean",
                s.get("mean_stake"),
                "AVAX",
                "count",
                "mean",
            )
            add(
                "Stake per commitment",
                "median",
                s.get("median_stake"),
                "AVAX",
                "count",
                "median",
            )
            add(
                "Stake-weighted median stake",
                "median",
                s.get("weighted_median_stake"),
                "AVAX",
                "stake",
                "first ordered value reaching half total stake",
            )
            add("Duration", "mean", s.get("mean_duration"), "days", "count", "mean")
            add(
                "Duration",
                "median",
                s.get("median_duration"),
                "days",
                "count",
                "median",
            )
            add(
                "Stake-weighted duration",
                "mean",
                ratio(s.get("avax_days"), stake),
                "days",
                "stake",
                "ratio of sums",
                numerator=s.get("avax_days"),
                denominator=stake,
            )
            add(
                "Stake-weighted duration",
                "median",
                s.get("weighted_median_duration"),
                "days",
                "stake",
                "first ordered value reaching half total stake",
            )
            for statistic, a, b, weight in (
                ("auto-renew-enabled commitments", s.get("auto_count", 0), n, "count"),
                ("auto-renew-enabled stake", s.get("auto_stake", 0), stake, "stake"),
                ("renewal cycles", s.get("renewal_count", 0), n, "count"),
                ("renewal-cycle stake", s.get("renewal_stake", 0), stake, "stake"),
            ):
                add(
                    "Auto-renewed share",
                    statistic,
                    ratio(100 * a, b),
                    "percent",
                    weight,
                    "ratio of sums",
                    numerator=a,
                    denominator=b,
                )
            add(
                "Committed AVAX-days",
                "total",
                s.get("avax_days", 0.0),
                "AVAX-days",
                "stake",
                "sum of stake times cycle/period duration",
            )
            add(
                "Committed AVAX-days per day",
                "per day",
                ratio(s.get("avax_days", 0), days),
                "AVAX-days/day",
                "stake",
                "sum / fractional window days",
                numerator=s.get("avax_days", 0),
                denominator=days,
            )
            calendar = stocks[
                "validator_days" if role == "validator" else "delegated_days"
            ]
            combined_days = stocks["validator_days"] + stocks["delegated_days"]
            ledger_support = (
                "Complete ledger observations"
                if stocks["days"] == eligible and eligible
                else "Missing or incomplete ledger support"
            )

            def ledger_add(
                family,
                statistic,
                value,
                unit,
                reduction,
                *,
                _support=ledger_support,
                _days=int(stocks["days"]),
                _calendar=calendar,
                _add=add,
                **kw,
            ):
                _add(
                    family,
                    statistic,
                    value,
                    unit,
                    "time",
                    reduction,
                    population="Whole-network ledger",
                    clock="Complete UTC days, 23:59:59 stock observation",
                    support=_support,
                    support_count=_days,
                    support_stake=_calendar,
                    **kw,
                )

            ledger_add(
                "Calendar AVAX-days",
                "role stock",
                calendar,
                "AVAX-days",
                "sum of role daily-close stake",
            )
            ledger_add(
                "Calendar AVAX-days",
                "combined stock",
                combined_days,
                "AVAX-days",
                "sum of validator plus delegated daily-close stake",
            )
            for weight, a, b in (("count", closed, n), ("stake", closed_stake, stake)):
                add(
                    "Closed share",
                    "closed-known coverage",
                    ratio(100 * a, b),
                    "percent",
                    weight,
                    "ratio of sums",
                    numerator=a,
                    denominator=b,
                )
                failed = s.get(
                    "failed_count" if weight == "count" else "failed_stake", 0
                )
                add(
                    "Failed share",
                    "failed among closed-known",
                    ratio(100 * failed, a),
                    "percent",
                    weight,
                    "ratio of sums",
                    numerator=failed,
                    denominator=a,
                    support_count=closed,
                    support_stake=closed_stake,
                )
            add(
                "Realized rewards of the cohort",
                "closed-known total including restaked cycle rewards",
                s.get("rewards"),
                "AVAX",
                "count",
                "sum",
                clock="Acceptance cohort; ordinary outcomes timed, cycle outcomes known at capture without payment timestamp",
                support_count=closed,
                support_stake=closed_stake,
            )
            add(
                "Realized rewards of the cohort",
                "per closed-known commitment",
                ratio(s.get("rewards"), closed),
                "AVAX/commitment",
                "count",
                "ratio of sums",
                numerator=s.get("rewards"),
                denominator=closed,
                support_count=closed,
                support_stake=closed_stake,
            )
            add(
                "Cohort earned rate",
                "matched closed-known AVAX-day rate",
                ratio(36500 * (s.get("rewards") or 0), s.get("closed_avax_days"))
                if closed
                else None,
                "percent/year (365 days)",
                "AVAX-days",
                "ratio of sums",
                numerator=s.get("rewards"),
                denominator=s.get("closed_avax_days"),
                support_count=closed,
                support_stake=closed_stake,
            )
            for statistic, value, weight in (
                ("mean", s.get("fee_mean"), "count"),
                ("median", s.get("fee_median"), "count"),
                ("mean", s.get("fee_weighted_mean"), "stake"),
            ):
                add(
                    "Fee rate",
                    statistic,
                    None if value is None or pd.isna(value) else 100 * value,
                    "percent",
                    weight,
                    statistic,
                    support="Not applicable to delegators"
                    if role == "delegator"
                    else None,
                    support_count=int(s.get("fee_count", 0)),
                    support_stake=s.get("fee_stake", 0),
                )
            delegations = (
                db.execute(
                    """SELECT count(*) n,sum(d.stake_navax::HUGEINT)::DOUBLE/1e9 stake
                FROM periods v JOIN periods d ON d.validator_transaction_hash=v.transaction_hash AND d.role='delegator'
                WHERE v.role='validator' AND v.accepted_at>=? AND v.accepted_at<? AND d.accepted_at<?""",
                    [start, end, cutoffs["delegator"]],
                ).fetchone()
                if role == "validator"
                else (None, None)
            )
            for statistic, value, unit, weight in (
                (
                    "attached delegation transactions",
                    delegations[0],
                    "delegations",
                    "count",
                ),
                (
                    "attached delegated stake",
                    delegations[1]
                    if delegations[0]
                    else 0
                    if role == "validator"
                    else None,
                    "AVAX",
                    "stake",
                ),
            ):
                add(
                    "Delegations and delegated stake",
                    statistic,
                    value,
                    unit,
                    weight,
                    "sum",
                    population="Delegations attached to validator parent transactions accepted in window",
                    clock="Parent validator transaction acceptance",
                    support="Not applicable to delegators"
                    if role == "delegator"
                    else None,
                )
            ledger_add(
                "Mean supply",
                "daily closing supply",
                stocks["supply"],
                "AVAX",
                "mean of daily close stocks",
            )
            ledger_add(
                "Mean active stake",
                "validator transaction-base stock",
                stocks["validator_stake"],
                "AVAX",
                "mean of daily close stocks",
            )
            ledger_add(
                "Mean active stake",
                "validator cycle-weight stock including restaking",
                stocks["validator_cycle_stake"],
                "AVAX",
                "mean of daily close stocks",
            )
            ledger_add(
                "Mean active stake",
                "active restaked reward increment",
                stocks["active_restaked_increment"],
                "AVAX",
                "mean of daily cycle-weight minus original-stake increments",
            )
            ledger_add(
                "Mean active stake",
                "delegated transaction-base stock",
                stocks["delegated_stake"],
                "AVAX",
                "mean of daily close stocks",
            )
            ledger_add(
                "Staking ratio",
                "validator",
                stocks["validator_ratio"],
                "percent",
                "mean of daily ratios",
            )
            ledger_add(
                "Staking ratio",
                "combined validator and delegated",
                stocks["combined_ratio"],
                "percent",
                "mean of daily ratios",
            )
            ledger_add(
                "Issued in the window",
                "paid issuance",
                stocks["issued"],
                "AVAX",
                "sum by ledger payment day",
            )
            ledger_add(
                "Burned in the window",
                "burn",
                stocks["burned"],
                "AVAX",
                "sum by ledger day",
            )
            ledger_add(
                "Calendar earned rate",
                "combined role rate",
                ratio(36500 * stocks["issued"], combined_days),
                "percent/year (365 days)",
                "ratio of sums",
                numerator=stocks["issued"],
                denominator=combined_days,
            )
            ledger_add(
                "Net inflation",
                "annualized net issuance",
                ratio(
                    36500 * (stocks["issued"] - stocks["burned"]),
                    stocks["supply"] * stocks["days"],
                ),
                "percent/year (365 days)",
                "net issuance / complete-day supply-days",
                numerator=stocks["issued"] - stocks["burned"],
                denominator=stocks["supply"] * stocks["days"],
            )
            add(
                "Concentration",
                "mean daily top-ten address-group stake share",
                ident.get("concentration"),
                "percent",
                "time",
                "mean of daily top-ten stake shares",
                population="Active validator original transaction stake, shared-reward-address groups",
                clock="Complete UTC days, 23:59:59 stock observation",
                support=(
                    "Unsupported delegator ownership"
                    if role == "delegator"
                    else "Complete dated identity support"
                    if ident.get("supported_days") == ident.get("eligible_days")
                    and ident.get("supported_days")
                    else "Partial or missing dated identity support"
                ),
                support_count=ident.get("supported_days", 0),
            )
    frame = pd.DataFrame(rows)
    metadata.update(
        {
            "schema_version": "canonical-era-table/v1",
            "measure_families": list(CANONICAL_ERA_FAMILIES),
            "annualization_days": 365,
            "cycle_capture_cutoff_utc": _report_iso(cycle_cutoff),
            "reward_capture_cutoff_utc": _report_iso(reward_cutoff),
            "commitment_basis": "Ordinary periods plus every observed auto-renewed cycle; parent transactions counted separately.",
            "cycle_clock": "Initial cycle uses parent accepted_at; subsequent cycle start is a renewal decision-clock proxy. No config-at-acceptance or payment-time claim.",
            "cycle_reward_basis": "Ordinary realized validator rewards include delegation fees. Auto-cycle totals replace the parent reward: restaked_validation_navax + withdrawn_validation_navax + restaked_delegatee_navax + withdrawn_delegatee_navax on closed-known cycles. The first two are validation rewards; the last two are delegatee fees. Unknown components remain null. No cycle payment-day attribution.",
            "cohort_weight_basis": "Ordinary original stake, auto-renewed cycle weight including restaking.",
            "ledger_stock_basis": "Original transaction stake through greatest(end_time,last_cycle_end_time), without restaked cycle weights.",
            "identity_basis": "Dated latest reward addresses form inferred shared-address groups, not proven owners. Cohort groups at exclusive window end; concentration uses transaction-base stock and refuses unsupported days.",
            "calendar_support": "Ledger day-close assignment, not prorated fractional era days. Rates use identical complete-day numerator/denominator support.",
            "capture_qualification": "Capture completion is a source cutoff, not a proof of chain inactivity or full chain coverage.",
            "duckdb": {
                "threads": threads,
                "memory_limit": memory_limit,
                "spill": "Automatic cleaned scratch, or caller-supplied temporary directory",
            },
            "scientific_acceptance": False,
        }
    )
    frame.attrs["metadata"] = metadata
    return frame


def _calendar_starts(start: pd.Timestamp, end: pd.Timestamp, grain: str):
    if grain == "Day":
        first, frequency, step = start.normalize(), "D", pd.DateOffset(days=1)
    elif grain == "Week":
        first, frequency, step = start.normalize() - timedelta(days=start.weekday()), "W-MON", pd.DateOffset(weeks=1)
    else:
        first, frequency, step = pd.Timestamp(year=start.year, month=1, day=1), "YS", pd.DateOffset(years=1)
    for beginning in pd.date_range(first, end, freq=frequency):
        finish = beginning + step
        if beginning < end and finish > start:
            label = str(beginning.year) if grain == "Year" else beginning.strftime("%Y-%m-%d")
            yield beginning, label, max(beginning, start), min(finish, end)


def cohort_table(daily: pd.DataFrame, cutoffs: Mapping[str, pd.Timestamp], grain: str,
                 identities: pd.DataFrame | None = None,
                 window: tuple[pd.Timestamp, pd.Timestamp] | None = None) -> pd.DataFrame:
    """One row per covered interval and role, including intervals with no accepted commitments."""
    if grain not in {"Day", "Week", "Year", "Era", "All"}:
        raise ValueError(f"unknown time grain: {grain}")
    daily = daily.copy()
    daily["accepted_day"] = pd.to_datetime(daily["accepted_day"])
    starts = daily.groupby("role")["first_accepted"].min().to_dict()
    if window is not None:
        daily = daily[daily["accepted_day"].ge(window[0]) & daily["accepted_day"].lt(window[1])]
    rows = []
    for role, start in starts.items():
        start, end = pd.Timestamp(start), cutoffs[role]
        if window is not None:
            start, end = max(start, window[0]), min(end, window[1])
        if start >= end:
            continue
        if grain == "All":
            intervals = [("All", "All", start, end)]
        elif grain == "Era":
            intervals = [(era, era.title(), a, b) for era, a, b in _era_intervals(start, end)]
        else:
            intervals = [(key, label, a, b) for key, label, a, b in _calendar_starts(start, end, grain)]
        rows.extend({"role": role, "bucket": key, "Reporting Interval": label, "Start (UTC)": a, "End (UTC)": b}
                    for key, label, a, b in intervals)
    spine = pd.DataFrame(rows)
    if grain == "Day":
        daily["bucket"] = daily["accepted_day"]
    elif grain == "Week":
        daily["bucket"] = daily["accepted_day"] - pd.to_timedelta(daily["accepted_day"].dt.weekday, unit="D")
    elif grain == "Year":
        daily["bucket"] = daily["accepted_day"].dt.to_period("Y").dt.start_time
    else:
        daily["bucket"] = daily["era"] if grain == "Era" else "All"
    totals = daily.groupby(["role", "bucket"], as_index=False)[list(MEASURES)].sum()
    result = spine.merge(totals, on=["role", "bucket"], how="left")
    if identities is not None:
        result["bucket_key"] = result["bucket"].astype(str)
        counts = identities[identities["grain"].eq(grain)].drop(columns="grain").rename(columns={"bucket": "bucket_key"})
        result = result.merge(counts, on=["role", "bucket_key"], how="left")
        result["Total Nodes"] = result["Total Nodes"].fillna(0)
        for role, column in (("validator", IDENTITY_COLUMNS[1]), ("delegator", IDENTITY_COLUMNS[2])):
            applicable = result["role"].eq(role)
            result.loc[applicable, column] = result.loc[applicable, column].fillna(0)
        for role, columns in (("validator", (ADDRESS_LINK_COLUMNS[0], LINKED_NODE_COLUMNS[0])),
                              ("delegator", (ADDRESS_LINK_COLUMNS[1], LINKED_NODE_COLUMNS[1]))):
            for column in columns:
                if column in result:
                    applicable = result["role"].eq(role)
                    result.loc[applicable, column] = result.loc[applicable, column].fillna(0)
    else:
        for column in IDENTITY_COLUMNS:
            result[column] = float("nan")
    for column in (*ADDRESS_LINK_COLUMNS, *LINKED_NODE_COLUMNS):
        if column not in result:
            result[column] = float("nan")
    result[list(MEASURES)] = result[list(MEASURES)].fillna(0)
    result[["commitments", "reward_outcomes"]] = result[["commitments", "reward_outcomes"]].astype(int)
    days = (result["End (UTC)"] - result["Start (UTC)"]) / DAY
    count = result["commitments"].replace(0, float("nan"))
    nodes = result["Total Nodes"].replace(0, float("nan"))
    addresses = result[IDENTITY_COLUMNS[1]].combine_first(result[IDENTITY_COLUMNS[2]]).replace(0, float("nan"))
    links = result[ADDRESS_LINK_COLUMNS[0]].combine_first(result[ADDRESS_LINK_COLUMNS[1]])
    linked_nodes = result[LINKED_NODE_COLUMNS[0]].combine_first(result[LINKED_NODE_COLUMNS[1]]).replace(
        0, float("nan"),
    )
    outcome_count = result["reward_outcomes"].replace(0, float("nan"))
    result["Total Days"] = days
    result["Commitments / Day"] = result["commitments"] / days
    result["Commitments / Node"] = result["commitments"] / nodes
    result["Commitments / Node / Day"] = result["Commitments / Node"] / days
    result["Commitments / Address"] = result["commitments"] / addresses
    result["Commitments / Address / Day"] = result["Commitments / Address"] / days
    result["Addresses per Node"] = links / linked_nodes
    result["Nodes per Address"] = links / addresses
    for metric, source in METRIC_SOURCES.items():
        total = result[source]
        result[_metric_column(metric, "Total")] = total
        result[_metric_column(metric, "Per Calendar Unit")] = total / days
        result[_metric_column(metric, "Per Commitment")] = total / (outcome_count if metric == "Rewards" else count)
        result[_metric_column(metric, "Per Node")] = total / nodes
        result[_metric_column(metric, "Per Node per Calendar Unit")] = total / nodes / days
        result[_metric_column(metric, "Per Address")] = total / addresses
        result[_metric_column(metric, "Per Address per Calendar Unit")] = total / addresses / days
    result["Reward Outcomes"] = result["reward_outcomes"].astype(str) + "/" + result["commitments"].astype(str)
    result["Role"] = result["role"].str.title()
    result = result.rename(columns={"commitments": "Total Commitments"})
    columns = ["Reporting Interval", "Start (UTC)", "End (UTC)", "Role", "Total Days", "Total Nodes",
               "Total Validator Reward Addresses", "Total Delegator Funding Addresses",
               "Addresses per Node", "Nodes per Address", "Total Commitments",
               "Commitments / Day", "Commitments / Node", "Commitments / Node / Day",
               "Commitments / Address", "Commitments / Address / Day"]
    columns.extend(_metric_column(metric, view) for metric in METRIC_SOURCES for view in VIEWS)
    columns.append("Reward Outcomes")
    result = result[columns].sort_values(["Start (UTC)", "Role"], ascending=[False, True])
    return result.reset_index(drop=True)


def rates_per(table: pd.DataFrame, denominator: str) -> pd.DataFrame:
    """Change only the display rate unit; the accepted cohort and its totals stay fixed."""
    factor = DAYS_PER_RATE_PERIOD[denominator]
    result = table.copy()
    result["Total Days"] = result["Total Days"] / factor
    stake_duration_columns = [_metric_column("Stake-duration", view) for view in VIEWS]
    result[stake_duration_columns] = result[stake_duration_columns] / factor
    rate_columns = ["Commitments / Day", "Commitments / Node / Day", "Commitments / Address / Day"]
    rate_columns.extend(_metric_column(metric, view) for metric in METRIC_SOURCES
                        for view in ("Per Calendar Unit", "Per Node per Calendar Unit",
                                     "Per Address per Calendar Unit"))
    result[rate_columns] = result[rate_columns] * factor
    names = {"Total Days": f"Total {denominator}s",
             "Commitments / Day": f"Commitments / {denominator}",
             "Commitments / Node / Day": f"Commitments / Node / {denominator}",
             "Commitments / Address / Day": f"Commitments / Address / {denominator}"}
    names.update({_metric_column(metric, view): _metric_column(metric, view, denominator)
                  for metric in METRIC_SOURCES for view in VIEWS
                  if metric == "Stake-duration" or view in ("Per Calendar Unit", "Per Node per Calendar Unit",
                                                            "Per Address per Calendar Unit")})
    return result.rename(columns=names)


def for_population(table: pd.DataFrame, population: str) -> pd.DataFrame:
    """Show only the address count that applies to the selected population."""
    validator_addresses, delegator_addresses = IDENTITY_COLUMNS[1:]
    if population == "Both":
        result = table.copy()
        result.insert(result.columns.get_loc(validator_addresses), "Total Addresses",
                      result[validator_addresses].combine_first(result[delegator_addresses]))
        return result.drop(columns=[validator_addresses, delegator_addresses])
    role, unused = (("Validator", delegator_addresses) if population == "Validators"
                    else ("Delegator", validator_addresses))
    return table[table["Role"].eq(role)].drop(columns=unused)


def selected_columns(table: pd.DataFrame, metrics: list[str], views: list[str], period: str) -> pd.DataFrame:
    """Keep context, then group selected quantities by denominator."""
    columns = list(table.columns[:table.columns.get_loc("Total Nodes")])
    commitment_views = {
        "Per Calendar Unit": f"Commitments / {period}",
        "Per Node": "Commitments / Node",
        "Per Node per Calendar Unit": f"Commitments / Node / {period}",
        "Per Address": "Commitments / Address",
        "Per Address per Calendar Unit": f"Commitments / Address / {period}",
    }
    for view in VIEWS:
        if view not in views:
            continue
        for metric in QUANTITIES:
            if metric not in metrics:
                continue
            if metric == "Nodes":
                if view == "Total":
                    columns.append("Total Nodes")
                elif view == "Per Address":
                    columns.append("Nodes per Address")
            elif metric == "Addresses":
                if view == "Total":
                    columns.extend(column for column in ("Total Addresses", *IDENTITY_COLUMNS[1:])
                                   if column in table.columns)
                elif view == "Per Node":
                    columns.append("Addresses per Node")
            elif metric == "Commitments":
                if view == "Total":
                    columns.append("Total Commitments")
                elif view in commitment_views:
                    columns.append(commitment_views[view])
            else:
                columns.append(_metric_column(metric, view, period))
    if "Rewards" in metrics:
        columns.append("Reward Outcomes")
    return table[columns]


def display_column(column: str) -> str:
    """Translate an internal heading without changing its meaning or units."""
    return column.replace(" / ", " per ").replace("/", " per ")


def display_columns(table: pd.DataFrame) -> pd.DataFrame:
    """Use readable headings without changing measure keys or units."""
    return table.rename(columns=display_column)


def quantity_colors(period: str) -> dict[str, str]:
    """Resolve plotted columns from quantity definitions, independent of draw order."""
    columns = {quantity: [_metric_column(quantity, view, period) for view in VIEWS]
               for quantity in METRIC_SOURCES}
    columns.update({
        "Nodes": ["Total Nodes", "Nodes per Address"],
        "Addresses": ["Total Addresses", *IDENTITY_COLUMNS[1:], "Addresses per Node"],
        "Commitments": ["Total Commitments", f"Commitments / {period}", "Commitments / Node",
                        f"Commitments / Node / {period}", "Commitments / Address",
                        f"Commitments / Address / {period}"],
    })
    return {display_column(column): QUANTITY_COLORS[quantity.lower().replace("-", "_")]
            for quantity, names in columns.items() for column in names}


def _upgrade_axis(plot, element):
    """Label upgrade starts above the calendar axis, as in the staking canvas."""
    if "upgrade_axis" in plot.handles:
        plot.handles["upgrade_axis"].axis_label = None
        return
    ticks = {}
    for era, start, _ in _era_intervals(NETWORK_START, pd.Timestamp.max.normalize()):
        ticks[start.value / 1_000_000] = era
    axis = DatetimeAxis(ticker=FixedTicker(ticks=list(ticks)), major_label_overrides=ticks,
                        axis_line_color=None, major_label_text_font_size="8pt", major_tick_in=0)
    plot.state.above = [axis, *plot.state.above]
    plot.handles["upgrade_axis"] = axis


def _legend_interaction(plot, element):
    for legend in plot.state.legend:
        legend.click_policy = "mute"


def _hover_number(value: float) -> str:
    if 0 < abs(value) < 0.005:
        return "<0.01" if value > 0 else ">-0.01"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


@cache
def _cohort_data(run: str):
    """Build the checked cohort tables once per pinned run in this kernel."""
    receipt = datasets.receipt("derived.staking-periods", run)
    cutoffs = _source_cutoffs(receipt["capture"])
    inputs = {item["input_id"]: item for item in receipt["capture"]["inputs"]}
    paths = {name: str(datasets.parquet_path(item["dataset_id"], item["run"]))
             for name, item in inputs.items() if name in {"validator-stakes", "delegator-stakes"}}
    periods = str(datasets.parquet_path("derived.staking-periods", run))
    daily = accepted_commitments(periods)
    identities = distinct_identities(paths["validator-stakes"], paths["delegator-stakes"])
    tables = {grain: cohort_table(daily, cutoffs, grain, identities)
              for grain in StakingCohorts.param.time_grain.objects}
    reward_cutoff = pd.Timestamp(next(item["captured_at"] for item in receipt["capture"]["inputs"]
                                      if item["input_id"] == "staking-rewards"))
    return tables, cutoffs, reward_cutoff, daily, (paths["validator-stakes"], paths["delegator-stakes"])


@cache
def _window_table(run: str, start: date, end: date, grain: str):
    """Recompute exact acceptance cohorts for inclusive UTC calendar dates."""
    _, cutoffs, _, daily, sources = _cohort_data(run)
    window = (pd.Timestamp(start), pd.Timestamp(end) + DAY)
    identities = distinct_identities(*sources, *window, grain)
    return cohort_table(daily, cutoffs, grain, identities, window)


class _CohortCommGuard(pn.pane.HTML):
    """Ignore returned notebook patches instead of echoing stale widget values."""

    # Bokeh marks backend patches sync=false. Panel's notebook comm listener
    # currently buffers them anyway, unlike ClientSession. Guard only the
    # document containing these controls. Server documents have no CommManager.
    _script = """
        for (const doc of Bokeh.documents) {
            if (!Array.from(doc._all_models.values()).some(model => model.name === GUARD_NAME)) continue;
            for (const manager of doc._all_models.values()) {
                if (!manager.type.endsWith("CommManager") || manager._cohort_sync_guard) continue;
                const receive = manager._document_changed.bind(manager);
                manager._document_changed = event => {
                    if (event.sync !== false) receive(event);
                };
                manager._event_buffer = manager._event_buffer.filter(event => event.sync !== false);
                manager._cohort_sync_guard = true;
                // Batch nearby clicks without the default 50 ms input delay.
                manager.setv({debounce: 10}, {sync: false});
            }
        }
    """

    def __init__(self, **params):
        super().__init__("", **params)
        self._guard_name = f"cohorts-comm-guard-{uuid4().hex}"
        self.object = "<script>(() => {" + self._script.replace("GUARD_NAME", repr(self._guard_name)) + "})();</script>"

    def _get_model(self, doc, root=None, parent=None, comm=None):
        model = super()._get_model(doc, root, parent, comm)
        model.name = self._guard_name
        model.syncable = False
        return model


class _CohortChartPane(pn.pane.Bokeh):
    """Give each live notebook document its own persistent figure."""

    def __init__(self, chart):
        self._chart = chart
        self._copies = {}
        super().__init__(chart.figure, sizing_mode="stretch_width")

    def _get_model(self, doc, root=None, parent=None, comm=None):
        if root is None:
            return self.get_root(doc, comm)
        if self.object.document is None or self.object.document is doc:
            return super()._get_model(doc, root, parent, comm)
        copy = _CohortChart(self._chart.explorer, isolated=True)
        model = copy.pane._get_model(doc, root, parent, comm)
        self._copies[root.id] = copy
        self._models[root.id] = (model, parent)
        return model

    def update_copies(self):
        for copy in tuple(self._copies.values()):
            copy.update()

    def _cleanup(self, root=None):
        if root is not None:
            copy = self._copies.pop(root.id, None)
            if copy is not None:
                copy.pane._cleanup(root)
        super()._cleanup(root)


class _CohortChart:
    """Keep the notebook's model graph stable; selection changes only visibility."""

    _fields = ("Date", "Index", "Value", "Title", "DisplayValue", "DisplayIndex")

    def __init__(self, explorer, *, isolated=False):
        self.explorer = explorer
        self.figure = figure(
            title="New staking commitments over time", x_axis_type="datetime",
            x_range=Range1d(0, 1),
            x_axis_label="Calendar time", height=600, sizing_mode="stretch_width",
            tools="pan,wheel_zoom,box_zoom,reset,save", active_scroll="wheel_zoom",
            y_range=DataRange1d(only_visible=True),
        )
        # Display-only models do not need browser-to-kernel traffic on zoom,
        # hover or legend mute, including Bokeh's scalar-color serialization.
        self.figure.x_range.syncable = self.figure.y_range.syncable = False
        self.reference = Span(location=1, dimension="width", line_color="#888888",
                              line_dash="dotted", line_width=1, syncable=False)
        self.figure.add_layout(self.reference)
        self.bands = {}
        for era, start, end in _era_intervals(
            NETWORK_START, pd.Timestamp(explorer.param.date_range.bounds[1]) + DAY,
        ):
            band = BoxAnnotation(left=start, right=end, fill_color="#d9d9d9", fill_alpha=0.35,
                                 line_alpha=0, visible=False, syncable=False)
            self.bands[era] = band
            self.figure.add_layout(band)
        ticks = {start.value / 1_000_000: era for era, start, _ in
                 _era_intervals(NETWORK_START, pd.Timestamp.max.normalize())}
        self.figure.add_layout(DatetimeAxis(
            ticker=FixedTicker(ticks=list(ticks)), major_label_overrides=ticks,
            axis_line_color=None, major_label_text_font_size="8pt", major_tick_in=0,
        ), "above")
        self.series = {}
        self._catalog = {}
        self._context = None
        self._groups = {}
        legend_items = []
        colors = quantity_colors(explorer.periodic_denominator)
        for (quantity, view), measure in self._columns().items():
            for role in ("Validator", "Delegator"):
                source = ColumnDataSource({name: [] for name in self._fields}, syncable=False)
                common = {"source": source, "name": measure, "visible": False, "syncable": False,
                          "color": colors[measure], "muted_alpha": 0.08}
                line = self.figure.line("Date", "Index", line_width=4, line_alpha=0.75,
                                        hover_line_width=6, hover_line_alpha=1, **common)
                point = self.figure.scatter("Date", "Index", size=7, **common)
                for renderer in (line, point):
                    renderer.syncable = False
                    for glyph in (renderer.glyph, renderer.hover_glyph, renderer.muted_glyph,
                                  renderer.nonselection_glyph):
                        if hasattr(glyph, "syncable"):
                            glyph.syncable = False
                item = LegendItem(label=value(measure), renderers=[line, point], visible=False, syncable=False)
                legend_items.append(item)
                self.series[role, quantity, view] = {"source": source, "line": line, "point": point,
                                                     "legend": item, "context": None}
        self.figure.add_layout(Legend(items=legend_items, location="top_right", click_policy="mute",
                                      syncable=False))
        self.figure.add_tools(HoverTool(
            renderers=[renderer for series in self.series.values() for renderer in
                       (series["line"], series["point"])],
            tooltips=[("Measure", "@Title"), ("Date", "@Date{%F}"),
                      ("Value", "@DisplayValue"), ("Chart value", "@DisplayIndex")],
            formatters={"@Date": "datetime"}, syncable=False,
        ))
        self.pane = (pn.pane.Bokeh(self.figure, sizing_mode="stretch_width") if isolated
                     else _CohortChartPane(self))
        self.empty = pn.pane.Markdown(
            "Select a Per denominator and a quantity with observed values to draw the chart.", visible=False,
        )
        self.update()

    def _columns(self):
        period = self.explorer.periodic_denominator
        if period not in self._catalog:
            # Use the same column projection as the table, including the
            # intentionally unsupported quantity/denominator combinations.
            table = rates_per(for_population(self.explorer._tables["All"].iloc[:0], "Both"), period)
            context = (*CONTEXT_COLUMNS, f"Total {period}s", "Reward Outcomes")
            self._catalog[period] = {
                (quantity, view): display_column(column)
                for quantity in QUANTITIES for view in VIEWS if view != "Total"
                for column in selected_columns(table, [quantity], [view], period)
                if column not in context
            }
        return self._catalog[period]

    def update(self, *events):
        explorer = self.explorer
        context = (explorer.time_grain, explorer.population, explorer.periodic_denominator,
                   explorer.normalization, explorer.date_range)
        if context != self._context:
            frame = explorer._plot_frame(metrics=list(QUANTITIES), views=list(VIEWS))
            self._groups = dict(tuple(frame.groupby(["Role", "Measure"], sort=False)))
            self._context = context
        visible_groups = []
        columns = self._columns()
        for (role, quantity, view), series in self.series.items():
            measure = columns[quantity, view]
            values = self._groups.get((role, measure))
            visible = quantity in explorer.metrics and view in explorer.views and values is not None
            if visible:
                visible_groups.append(values)
                if series["context"] != context:
                    label = f"{role}: {measure}" if explorer.population == "Both" else measure
                    series["source"].data = {
                        "Date": values["Date"].to_numpy(), "Index": values["Index"].to_numpy(),
                        "Value": values["Value"].to_numpy(), "Title": [label] * len(values),
                        "DisplayValue": values["Value"].map(_hover_number).tolist(),
                        "DisplayIndex": values["Index"].map(_hover_number).tolist(),
                    }
                    series["legend"].label = value(label)
                    series["line"].name = series["point"].name = label
                    series["context"] = context
            series["line"].visible = visible and len(values) > 1
            series["point"].visible = visible and len(values) == 1
            series["legend"].visible = visible
        self.figure.visible = bool(visible_groups)
        self.pane.visible = bool(visible_groups)
        self.empty.visible = not visible_groups
        self.reference.visible = explorer.normalization != "None"
        self.figure.yaxis.axis_label = ("Value (original units)" if explorer.normalization == "None"
                                       else f"Relative to {explorer.normalization.lower()}")
        if visible_groups:
            start = min(values["Date"].min() for values in visible_groups)
            end = max(values["Date"].max() for values in visible_groups)
            if start == end:
                start = min(values["Start (UTC)"].min() for values in visible_groups)
                end = max(values["End (UTC)"].max() for values in visible_groups)
            self.figure.x_range.update(start=start, end=end, reset_start=start, reset_end=end)
            bands = {era: (index, left, right) for index, (era, left, right) in enumerate(_era_intervals(
                min(values["Start (UTC)"].min() for values in visible_groups),
                max(values["End (UTC)"].max() for values in visible_groups),
            ))}
            for era, band in self.bands.items():
                band.visible = era in bands and bool(bands[era][0] % 2)
                if band.visible:
                    _, band.left, band.right = bands[era]
        # A table control may live in a different notebook document. Flush this
        # figure's held changes rather than waiting for its next widget event.
        if isinstance(self.pane, _CohortChartPane):
            self.pane.update_copies()
        pn.io.push_notebook(self.pane)


class StakingCohorts(pm.Parameterized):
    """Fast notebook view of one checked staking-period release."""

    time_grain = pm.Selector(default="Era", objects=["Day", "Week", "Year", "Era", "All"], label="Group by")
    population = pm.Selector(default="Validators", objects=["Validators", "Delegators", "Both"])
    periodic_denominator = pm.Selector(default="Day", objects=["Day", "Week", "Year"], label="Rate Unit")
    metrics = pm.ListSelector(default=list(QUANTITIES), objects=list(QUANTITIES), label="Quantities")
    views = pm.ListSelector(default=["Total", "Per Calendar Unit", "Per Commitment"], objects=list(VIEWS),
                            label="Denominators")
    normalization = pm.Selector(default="Mean", objects=["None", "First nonzero", "Mean", "Median"],
                                label="Normalize by")
    date_range = pm.CalendarDateRange(default=None, allow_None=True, label="Accepted dates (UTC)")

    def __init__(self, run: str, **params):
        super().__init__(**params)
        self.run = run
        self._tables, self._cutoffs, self._reward_cutoff, self._daily, self._sources = _cohort_data(run)
        first = pd.Timestamp(self._daily["first_accepted"].min()).date()
        last = max(self._cutoffs.values()).date()
        self.param.date_range.bounds = (first, last)
        if self.date_range is None:
            self.date_range = (first, last)

    def _selected_table(self):
        full_range = self.param.date_range.bounds
        if self.date_range == full_range:
            return self._tables[self.time_grain]
        return _window_table(self.run, *self.date_range, self.time_grain)

    def _frame(self):
        table = for_population(self._selected_table(), self.population)
        table = selected_columns(rates_per(table, self.periodic_denominator), self.metrics, self.views,
                                 self.periodic_denominator)
        return display_columns(table).round(2)

    def _full_frame(self):
        table = for_population(self._selected_table(), self.population)
        table = selected_columns(rates_per(table, self.periodic_denominator), list(QUANTITIES), list(VIEWS),
                                 self.periodic_denominator)
        return display_columns(table).round(2)

    def _plot_frame(self, *, metrics=None, views=None):
        """Selected per-denominator quantities on the same reporting intervals as the table."""
        metrics = self.metrics if metrics is None else metrics
        views = [view for view in (self.views if views is None else views) if view != "Total"]
        table = rates_per(for_population(self._selected_table(), self.population),
                          self.periodic_denominator)
        table = display_columns(selected_columns(table, metrics, views, self.periodic_denominator))
        measures = [column for column in table if column not in (*CONTEXT_COLUMNS,
                    f"Total {self.periodic_denominator}s", "Reward Outcomes")]
        if not measures:
            return pd.DataFrame(columns=["Date", "Role", "Measure", "Value", "Index"])
        frame = table.melt(id_vars=["Start (UTC)", "End (UTC)", "Role"], value_vars=measures,
                           var_name="Measure", value_name="Value")
        frame["Date"] = frame["Start (UTC)"] + (frame["End (UTC)"] - frame["Start (UTC)"]) / 2
        frame = frame.sort_values("Date")
        grouped = frame.groupby(["Role", "Measure"], sort=False)["Value"]
        if self.normalization == "None":
            frame["Index"] = frame["Value"]
            return frame.dropna(subset=["Index"])
        if self.normalization == "First nonzero":
            baseline = grouped.transform(lambda values: values[values.ne(0)].iloc[0]
                                         if values.ne(0).any() else float("nan"))
        elif self.normalization == "Median":
            baseline = grouped.transform("median")
        else:
            baseline = grouped.transform("mean")
        frame["Index"] = frame["Value"] / baseline.replace(0, float("nan"))
        return frame.dropna(subset=["Index"])

    @pm.depends("time_grain", "population", "periodic_denominator", "metrics", "views", "normalization",
                "date_range")
    def plot(self):
        frame = self._plot_frame()
        if frame.empty:
            return pn.pane.Markdown("Select a Per denominator and a quantity with observed values to draw the chart.")
        bands = [hv.VSpan(start, end).opts(color="#d9d9d9", alpha=0.35, line_alpha=0)
                 for index, (_, start, end) in enumerate(_era_intervals(frame["Start (UTC)"].min(),
                                                                          frame["End (UTC)"].max()))
                 if index % 2]
        curves = []
        colors = quantity_colors(self.periodic_denominator)
        for (role, measure), values in frame.groupby(["Role", "Measure"], sort=False):
            label = f"{role}: {measure}" if self.population == "Both" else measure
            element = hv.Scatter if len(values) == 1 else hv.Curve
            values = values.assign(Title=label, DisplayValue=values["Value"].map(_hover_number),
                                   DisplayIndex=values["Index"].map(_hover_number))
            style = {"color": colors[measure], "tools": ["hover"], "muted_alpha": 0.08,
                     "hover_tooltips": [("Measure", "@Title"), ("Date", "@Date{%F}"),
                                        ("Value", "@DisplayValue"), ("Chart value", "@DisplayIndex")],
                     "hover_formatters": {"@Date": "datetime"}}
            style.update({"line_width": 4, "line_alpha": 0.75,
                          "hover_line_width": 6, "hover_line_alpha": 1}
                         if element is hv.Curve else {"size": 7})
            curves.append(element(values, "Date", ["Index", "Value", "Title", "DisplayValue", "DisplayIndex"],
                                  label=label)
                          .opts(**style))
        reference = [] if self.normalization == "None" else [
            hv.HLine(1).opts(color="#888888", line_dash="dotted", line_width=1)
        ]
        return hv.Overlay([*bands, *reference, *curves]).opts(
            title="New staking commitments over time", xlabel="Calendar time",
            ylabel=("Value (original units)" if self.normalization == "None"
                    else f"Relative to {self.normalization.lower()}"), responsive=True, height=600,
            xlim=((frame["Date"].min(), frame["Date"].max()) if frame["Date"].nunique() > 1
                  else (frame["Start (UTC)"].min(), frame["End (UTC)"].max())),
            padding=0,
            legend_position="top_right", hooks=[_upgrade_axis, _legend_interaction],
        )

    def chart(self):
        """A second set of controls edits the same parameters as the table."""
        if getattr(self, "_chart", None) is None:
            controls = self._controls(normalization=True)
            self._chart_plot = _CohortChart(self)
            self._chart = pn.Column(
                controls, self._chart_plot.pane, self._chart_plot.empty,
                pn.pane.Markdown("Selected Per measures share one axis. Choose Normalize by None only when "
                                 "their original units are comparable. Totals stay in the table. "
                                 "Legend clicks mute curves; hovering a curve emphasizes it. "
                                 "Helicon is partial; rewards include known outcomes only."),
                sizing_mode="stretch_width",
            )
            self.param.watch(self._chart_plot.update, ["time_grain", "population", "periodic_denominator",
                                                      "metrics", "views", "normalization", "date_range"])
        return self._chart

    def view(self):
        full = self._full_frame()
        selected = self._frame().columns
        hidden = [column for column in full if column not in selected]
        return pn.widgets.Tabulator(full, hidden_columns=hidden, show_index=False, disabled=True,
                                    pagination="remote", page_size=20, height=350, sizing_mode="stretch_width")

    def _controls(self, normalization=False):
        # Each notebook output owns its widget models. Sharing one widget object
        # across documents can echo an older selection into the active output.
        attribute = "_chart_widgets" if normalization else "_table_widgets"
        widgets = getattr(self, attribute, None)
        if widgets is None:
            widgets = {name: pn.widgets.Select.from_param(self.param[name], width=220)
                             for name in ("time_grain", "population", "periodic_denominator", "normalization")}
            widgets["date_range"] = pn.widgets.DateRangeSlider.from_param(
                self.param.date_range, start=self.param.date_range.bounds[0],
                end=self.param.date_range.bounds[1], step=1, format="%Y-%m-%d", width=660, throttled=True,
            )
            widgets["metrics"] = pn.widgets.CheckButtonGroup.from_param(
                self.param.metrics, orientation="vertical", variant="outline", color="primary", width=190,
            )
            widgets["views"] = pn.widgets.CheckButtonGroup.from_param(
                self.param.views, options=denominator_options(self.periodic_denominator),
                orientation="vertical", variant="outline", color="primary", width=220,
            )
            self.param.watch(lambda event: setattr(widgets["views"], "options",
                                                  denominator_options(event.new)), "periodic_denominator")
            setattr(self, attribute, widgets)
        names = ["time_grain", "population", "periodic_denominator"]
        if normalization:
            names.append("normalization")
        grouping = pn.Column(*(widgets[name] for name in names), width=220)
        return pn.Column(
            pn.Row(
                grouping, pn.Spacer(width=16),
                pn.Column(pn.pane.Markdown("Quantities", margin=(0, 0, 4, 0)), widgets["metrics"], width=190),
                pn.Spacer(width=16),
                pn.Column(pn.pane.Markdown("Denominators", margin=(0, 0, 4, 0)), widgets["views"], width=220),
                _CohortCommGuard(width=0, height=0, margin=0),
            ),
            widgets["date_range"],
        )

    def panel(self):
        if getattr(self, "_panel", None) is not None:
            return self._panel
        cutoffs = ", ".join(f"{role} extract captured {time:%Y-%m-%d %H:%M} UTC"
                            for role, time in self._cutoffs.items())
        note = (f"Pinned run `{self.run}`. {cutoffs}. Reward records through "
                f"{self._reward_cutoff:%Y-%m-%d %H:%M} UTC. "
                "Rewards include known outcomes only. `Reward Outcomes` is n known outcomes / m total commitments; "
                "Rewards per Commitment divides by n, not all m commitments. "
                "Rewards per Node divides known rewards by all cohort nodes. "
                "Rewards per Address divides known rewards by all cohort addresses. "
                "Nodes are distinct validator NodeIDs receiving these commitments. Validator reward addresses count "
                "all reward-owner addresses; delegator funding addresses count the largest funder per delegation, "
                "not unique people. "
                "Addresses per Node divides distinct node-address links by nodes with a recorded address; "
                "Nodes per Address divides those links by distinct recorded addresses. "
                "Total Committed Duration sums each new commitment's duration; it is not the row's elapsed time. "
                "Reporting intervals group commitments by acceptance time. Accepted dates select inclusive UTC "
                "calendar dates, and partial reporting intervals are recomputed from the selected commitments. "
                "Rate Unit changes only the calendar-time "
                "denominator, so reward rates are cohort-normalized, not payout flows. "
                "Year rates use 365.2425 days. Start is inclusive; End is exclusive.")
        table = self.view()
        def update_visibility(event):
            selected = self._frame().columns
            table.hidden_columns = [column for column in table.value if column not in selected]

        def update_data(event):
            nonlocal table
            full = self._full_frame()
            selected = self._frame().columns
            hidden = [column for column in full if column not in selected]
            if not full.columns.equals(table.value.columns):
                # Tabulator rebuilds columns asynchronously. Changing hidden
                # columns in that same patch can redraw a torn-down table.
                # Initialize a new table atomically only when its schema changes.
                table = pn.widgets.Tabulator(
                    full, hidden_columns=hidden, show_index=False, disabled=True,
                    pagination="remote", page_size=20, height=350, sizing_mode="stretch_width",
                )
                self._panel[1] = table
            else:
                table.param.update(value=full, hidden_columns=hidden)

        self.param.watch(update_visibility, ["metrics", "views"])
        self.param.watch(update_data, ["time_grain", "population", "periodic_denominator", "date_range"])
        self._panel = pn.Column(self._controls(), table, pn.pane.Markdown(note), sizing_mode="stretch_width")
        return self._panel
