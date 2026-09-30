"""The measure registry: each KPI and moment defined once, and applied to chain tables and simulated run tables alike.

v0, unreviewed. A schema draft for the package layer ``measures``: it reads tables only and imports neither the
mechanisms nor the model, so a run's output table and a chain dataset go through the same definition.

A measure reads one or more named relations. Each relation has an alias the SQL uses, the dataset it comes from on the
chain side, and the source columns it must carry with their catalog types. Columns the SQL computes, such as an
acceptance date or a cohort bound, are declared apart from source columns. The answer is a table of the grain columns,
``value``, and any declared count columns, one row per grain. A measure with several relations states the common
coverage it requires, and every measure states how it treats nulls and zeros. Parameters, such as a cohort window,
reach the SQL as named DuckDB parameters.

Definitions are written by the lane named as owner: data science for empirical measures and moments, the modeling lead
for model measures, data engineering for this schema and the dataset side.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .catalog import DataError, dataset

OWNERS = ("data-science", "modeling", "data-engineering")
UNITS = ("share", "AVAX", "nAVAX", "count", "days", "AVAX-days", "commitment-days", "percent per year", "USD")
APPLIES_TO = ("chain", "run")
# The catalog's field types and the DuckDB types a relation may carry for each.
TYPES = {
    "integer": ("TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", "UBIGINT", "DECIMAL"),
    "number": ("FLOAT", "DOUBLE", "DECIMAL"),
    "string": ("VARCHAR",),
    "timestamp": ("TIMESTAMP", "TIMESTAMP WITH TIME ZONE"),
    "date": ("DATE",),
    "boolean": ("BOOLEAN",),
}
ID = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
ALIAS = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class Relation:
    """One input the SQL reads under ``alias``. ``dataset`` is the catalog dataset on the chain side."""

    alias: str
    columns: dict[str, str]
    dataset: str | None = None


@dataclass(frozen=True)
class Measure:
    id: str
    name: str
    definition: str
    unit: str
    grain: tuple[str, ...]
    relations: tuple[Relation, ...]
    sql: str
    owner: str
    nulls: str
    applies_to: tuple[str, ...] = ("chain", "run")
    computed: dict[str, str] = field(default_factory=dict)
    counts: tuple[str, ...] = ()
    parameters: dict[str, str] = field(default_factory=dict)
    coverage: str | None = None
    validations: tuple[tuple[str, str], ...] = ()
    window: str | None = None
    weighting: str | None = None
    citation: str | None = None
    version: int = 1
    notes: tuple[str, ...] = ()

    def problems(self) -> list[str]:
        """What is wrong with the declaration itself, before any data is read."""
        found = []
        if not ID.match(self.id):
            found.append(f"id {self.id!r} is not lowercase words joined by hyphens")
        if self.unit not in UNITS:
            found.append(f"unit {self.unit!r} is not one of {', '.join(UNITS)}")
        if self.owner not in OWNERS:
            found.append(f"owner {self.owner!r} is not one of {', '.join(OWNERS)}")
        if not self.applies_to or set(self.applies_to) - set(APPLIES_TO):
            found.append(f"applies_to must be drawn from {', '.join(APPLIES_TO)}")
        if not self.relations:
            found.append("a measure reads at least one relation")
        aliases = [relation.alias for relation in self.relations]
        if len(set(aliases)) != len(aliases) or any(not ALIAS.match(alias) for alias in aliases):
            found.append("relation aliases are distinct lowercase names")
        if "chain" in self.applies_to and any(relation.dataset is None for relation in self.relations):
            found.append("a measure applied to chain data names the dataset of every relation")
        if len(self.relations) > 1 and not self.coverage:
            found.append("a measure with several relations states the common coverage it requires")
        if not self.nulls:
            found.append("a measure states how it treats nulls and zeros")
        known = {name for relation in self.relations for name in relation.columns} | set(self.computed)
        if not self.grain or set(self.grain) - known:
            found.append("every grain column is a source column or a declared computed column")
        if set(self.counts) & set(self.grain):
            found.append("a count column is not also a grain column")
        if any(set(relation.columns.values()) - set(TYPES) for relation in self.relations) or set(self.parameters.values()) - set(TYPES):
            found.append(f"column and parameter types are drawn from {', '.join(TYPES)}")
        for alias in aliases:
            if not re.search(rf"\b{alias}\b", self.sql):
                found.append(f"the SQL does not read relation {alias}")
        for name in self.parameters:
            if f"${name}" not in self.sql:
                found.append(f"the SQL does not use parameter ${name}")
        for message, query in self.validations:
            if not message or not query.lstrip().upper().startswith("SELECT"):
                found.append("each validation is a message and a SELECT that counts violations")
        return found


REGISTRY: dict[str, Measure] = {}


def register(measure: Measure) -> Measure:
    """Add a measure once. A second measure with the same id is refused, so every definition has one home."""
    found = measure.problems()
    if measure.id in REGISTRY:
        found.append(f"{measure.id} is already registered")
    if found:
        raise DataError(f"measure {measure.id}: " + "; ".join(found))
    REGISTRY[measure.id] = measure
    return measure


def check_datasets(measure: Measure, catalog: dict[str, Any]) -> list[str]:
    """Each chain dataset a measure names carries every source column it reads, with the declared catalog type."""
    found = []
    for relation in measure.relations:
        if relation.dataset is None:
            continue
        try:
            fields = {item["name"]: item["type"] for item in dataset(catalog, relation.dataset)["fields"]}
        except DataError as error:
            found.append(str(error))
            continue
        for name, kind in relation.columns.items():
            if name not in fields:
                found.append(f"{relation.dataset} has no column {name}")
            elif fields[name] != kind and not (kind == "date" and fields[name] == "string"):
                found.append(f"{relation.dataset}.{name} is {fields[name]}, the measure reads {kind}")
    return found


def compute(measure: Measure, connection: Any, tables: dict[str, str], parameters: dict[str, Any] | None = None) -> Any:
    """The measure over the tables or views that ``tables`` maps each alias to. Returns grain, ``value``, counts."""
    parameters = parameters or {}
    if set(parameters) != set(measure.parameters):
        raise DataError(f"measure {measure.id} takes parameters {sorted(measure.parameters)}, given {sorted(parameters)}")
    if set(tables) != {relation.alias for relation in measure.relations}:
        raise DataError(f"measure {measure.id} reads {sorted(relation.alias for relation in measure.relations)}, given {sorted(tables)}")
    for relation in measure.relations:
        table = tables[relation.alias]
        described = {row[0]: row[1] for row in connection.execute(f'DESCRIBE SELECT * FROM "{table}"').fetchall()}
        for name, kind in relation.columns.items():
            if name not in described:
                raise DataError(f"measure {measure.id}: {table} has no column {name}")
            if described[name].split("(")[0] not in TYPES[kind]:
                raise DataError(f"measure {measure.id}: {table}.{name} is {described[name]}, the measure reads {kind}")
        if table != relation.alias:
            connection.execute(f'CREATE OR REPLACE TEMP VIEW "{relation.alias}" AS SELECT * FROM "{table}"')
    for message, query in measure.validations:
        used = {name: value for name, value in parameters.items() if f"${name}" in query}
        violations = connection.execute(query, used or None).fetchone()[0]
        if violations:
            raise DataError(f"measure {measure.id}: {violations} {message}")
    result = connection.sql(measure.sql, params=parameters or None)
    expected = [*measure.grain, "value", *measure.counts]
    if result.columns != expected:
        raise DataError(f"measure {measure.id}: the SQL returns {result.columns}, not {expected}")
    keys = ", ".join(f'"{name}"' for name in measure.grain)
    repeated = connection.execute(f"SELECT count(*) - count(DISTINCT ({keys})) FROM ({measure.sql})", parameters or None).fetchone()[0]
    if repeated:
        raise DataError(f"measure {measure.id}: {repeated} rows repeat a grain")
    return result


LEDGER = "derived.avax-monetary-daily"
PERIODS = "derived.staking-periods"
LEDGER_STAKE = {"date_utc": "date", "active_validator_stake_wei": "integer", "total_supply_close_wei": "integer", "complete": "boolean"}

# The first definitions from the data scientist's table of 2026-09-30 15:28, in their words where they give them.
VALIDATOR_STAKED_SHARE = register(Measure(
    id="validator-staked-share",
    name="Validator staked share",
    definition="Active validator self-stake at 23:59:59 UTC divided by contemporaneous realized total supply.",
    unit="share",
    grain=("date_utc",),
    relations=(Relation("ledger", LEDGER_STAKE, LEDGER),),
    sql="SELECT date_utc, active_validator_stake_wei::DOUBLE / total_supply_close_wei AS value FROM ledger"
        " WHERE complete AND total_supply_close_wei > 0 ORDER BY date_utc",
    owner="data-science",
    nulls="complete days with positive supply only; an incomplete day or a missing supply has no row",
    window="same complete day",
    weighting="unweighted across days for a time mean",
    citation="measurement atlas",
))
COMBINED_STAKED_SHARE = register(Measure(
    id="combined-staked-share",
    name="Combined staked share",
    definition="Active validator plus delegated stake at 23:59:59 UTC divided by contemporaneous realized total supply.",
    unit="share",
    grain=("date_utc",),
    relations=(Relation("ledger", {**LEDGER_STAKE, "active_delegated_stake_wei": "integer"}, LEDGER),),
    sql="SELECT date_utc, (active_validator_stake_wei + active_delegated_stake_wei)::DOUBLE / total_supply_close_wei AS value"
        " FROM ledger WHERE complete AND total_supply_close_wei > 0 ORDER BY date_utc",
    owner="data-science",
    nulls="complete days with positive supply only; an incomplete day or a missing supply has no row",
    window="same complete day",
    weighting="compute the daily ratio before reducing",
    citation="measurement atlas",
))
# AM2. Successive commitments on a node are paired before endings are selected, as in client 7ca051e.
RENEWAL_CHECKS = (
    ("validator commitments with a null transaction, node, start, or end",
     "SELECT count(*) FROM periods WHERE role = 'validator' AND (transaction_hash IS NULL OR node_id IS NULL OR start_time IS NULL OR end_time IS NULL)"),
    ("validator transactions listed more than once", "SELECT count(*) - count(DISTINCT transaction_hash) FROM periods WHERE role = 'validator'"),
    ("validator commitments that end at or before their start", "SELECT count(*) FROM periods WHERE role = 'validator' AND end_time <= start_time"),
    ("a cohort whose end does not follow its start", "SELECT ($cohort_end <= $cohort_start)::INTEGER"),
)


def _renewal(days: int, measure_id: str, name: str, notes: tuple[str, ...] = ()) -> Measure:
    """Same-node renewal within a fixed horizon. Successive commitments on a node are paired before endings are selected."""
    return register(Measure(
        id=measure_id, name=name,
        definition=f"Share of fully followed-up ending validator commitments whose next same-node commitment starts between "
                   f"the end and {days} days after it, both boundaries included.",
        unit="share",
        grain=("cohort_start", "cohort_end"),
        relations=(Relation("periods", {"transaction_hash": "string", "role": "string", "node_id": "string", "start_time": "timestamp",
                                        "end_time": "timestamp"}, PERIODS),),
        computed={"cohort_start": "the cohort_start parameter", "cohort_end": "the cohort_end parameter"},
        counts=("cohort_ends", "eligible_ends", "renewed_ends", "censored_ends", "overlapping_ends"),
        parameters={"cohort_start": "timestamp", "cohort_end": "timestamp", "observed_through": "timestamp"},
        validations=RENEWAL_CHECKS,
        sql=f"""
            WITH paired AS (
                SELECT end_time, epoch(lead(start_time) OVER (PARTITION BY node_id ORDER BY start_time, transaction_hash) - end_time) / 86400.0 AS gap_days
                FROM periods WHERE role = 'validator'
            ), cohort AS (
                SELECT gap_days, end_time + INTERVAL {days} DAY <= $observed_through AS complete, coalesce(gap_days < 0, FALSE) AS overlapping
                FROM paired WHERE end_time >= $cohort_start AND end_time < $cohort_end
            )
            SELECT $cohort_start AS cohort_start, $cohort_end AS cohort_end,
                   count(*) FILTER (WHERE complete AND NOT overlapping AND gap_days BETWEEN 0 AND {days})::DOUBLE
                       / nullif(count(*) FILTER (WHERE complete AND NOT overlapping), 0) AS value,
                   count(*) AS cohort_ends,
                   count(*) FILTER (WHERE complete AND NOT overlapping) AS eligible_ends,
                   count(*) FILTER (WHERE complete AND NOT overlapping AND gap_days BETWEEN 0 AND {days}) AS renewed_ends,
                   count(*) FILTER (WHERE NOT complete) AS censored_ends,
                   count(*) FILTER (WHERE complete AND overlapping) AS overlapping_ends
            FROM cohort""",
        owner="data-science",
        nulls="an ending without a later commitment on its node is not renewed; an ending without the full follow-up is censored "
              "and counted; a successor that starts before the end is excluded and counted; no eligible ending gives a null value; "
              "a null identity, a repeated transaction, or a commitment that does not end after it starts refuses the input",
        window=f"endings in [cohort_start, cohort_end), follow-up of {days} days after each end, observed through the input's last acceptance",
        weighting="one equal observation per ending commitment, not per node",
        citation="client 7ca051e, staking_renewal.renewal_summary",
        notes=notes,
    ))


# AM2 is fixed at seven days. Fourteen days is a sensitivity with its own identity, never AM2 under another horizon.
SAME_NODE_RENEWAL_7D = _renewal(7, "same-node-renewal-7d", "Same-node renewal within seven days (AM2)")
SAME_NODE_RENEWAL_14D = _renewal(14, "same-node-renewal-14d", "Same-node renewal within fourteen days, a sensitivity of AM2",
                                 ("A sensitivity of AM2, not a moment of its own.",))

# Daily cohorts on the acceptance clock, one row per acceptance date and role, from the period log.
COHORT_GRAIN = ("acceptance_date", "role")
COHORT_COMPUTED = {"acceptance_date": "the UTC date of accepted_at"}
COHORT_NULLS = "a date and role with no accepted commitment has no row; a zero amount is kept"


def _cohort(measure_id: str, name: str, definition: str, unit: str, columns: dict[str, str], value: str, weighting: str,
            citation: str, where: str = "TRUE", nulls: str = COHORT_NULLS) -> Measure:
    return register(Measure(
        id=measure_id, name=name, definition=definition, unit=unit, grain=COHORT_GRAIN,
        relations=(Relation("periods", {"accepted_at": "timestamp", "role": "string", **columns}, PERIODS),),
        computed=COHORT_COMPUTED,
        sql=f"SELECT accepted_at::DATE AS acceptance_date, role, {value} AS value FROM periods WHERE {where} GROUP BY ALL ORDER BY ALL",
        owner="data-science", nulls=nulls, window="acceptance window", weighting=weighting, citation=citation,
    ))


COMMITMENTS_ACCEPTED = _cohort(
    "commitments-accepted", "Commitments accepted", "Count of distinct accepted commitment transactions, separated by role.",
    "count", {"transaction_hash": "string"}, "count(DISTINCT transaction_hash)", "one vote per commitment", "SP contract and cohort explorer")
ENTRY_STAKE = _cohort(
    "entry-stake", "Entry stake", "Sum of the stake of commitments accepted in the window, not concurrent active stake.",
    "AVAX", {"stake_avax": "number"}, "sum(stake_avax)", "additive entry amounts", "measurement primitives and cohort explorer")
COMMITTED_DURATION = _cohort(
    "committed-duration", "Committed duration", "Sum of full scheduled commitment durations, including duration after the acceptance window ends.",
    "commitment-days", {"duration_days": "number"}, "sum(duration_days)", "sum of full durations", "measurement atlas and cohort explorer")
COMMITTED_STAKE_DURATION = _cohort(
    "committed-stake-duration", "Committed stake-duration", "Sum of entry stake multiplied by full commitment duration.",
    "AVAX-days", {"stake_avax": "number", "duration_days": "number"}, "sum(stake_avax * duration_days)", "additive commitment exposure",
    "measurement primitives and cohort explorer")
COHORT_REALIZED_REWARDS = _cohort(
    "cohort-realized-rewards", "Cohort realized rewards", "Sum of known realized reward outcomes of commitments accepted in the window.",
    "AVAX", {"realized_reward_avax": "number"}, "sum(realized_reward_avax)", "known outcomes only, never impute missing rewards",
    "SP reward contract and cohort explorer", where="realized_reward_avax IS NOT NULL",
    nulls="a commitment without a reward outcome is left out, not counted as zero; a recorded zero is kept; outcome coverage is cohort-reward-outcomes")
COHORT_REWARD_OUTCOMES = _cohort(
    "cohort-reward-outcomes", "Cohort reward outcomes", "Count of accepted commitments with a known realized reward, including a recorded zero.",
    "count", {"realized_reward_avax": "number"}, "count(realized_reward_avax)", "known-outcome denominator", "cohort explorer")

# Daily stocks and flows from the ledger, complete days only, converted from integer wei.
_LEDGER_NULLS = "complete days only; an incomplete day has no row"


def _ledger(measure_id: str, name: str, definition: str, column: str, weighting: str, citation: str = "monetary ledger contract") -> Measure:
    return register(Measure(
        id=measure_id, name=name, definition=definition, unit="AVAX", grain=("date_utc",),
        relations=(Relation("ledger", {"date_utc": "date", column: "integer", "complete": "boolean"}, LEDGER),),
        sql=f"SELECT date_utc, {column}::DOUBLE / 1e18 AS value FROM ledger WHERE complete AND {column} IS NOT NULL ORDER BY date_utc",
        owner="data-science", nulls=_LEDGER_NULLS + f", and a day without {column} has no row", window="UTC day",
        weighting=weighting, citation=citation,
    ))


ACTIVE_VALIDATOR_STAKE = _ledger("active-validator-stake", "Active validator stake", "Validator self-stake active at 23:59:59 UTC.",
                                 "active_validator_stake_wei", "daily stock, never summed across days")
ACTIVE_DELEGATED_STAKE = _ledger("active-delegated-stake", "Active delegated stake", "Delegated stake active at 23:59:59 UTC.",
                                 "active_delegated_stake_wei", "daily stock, never summed across days")
REALIZED_TOTAL_SUPPLY = _ledger(
    "realized-total-supply", "Realized total supply",
    "Genesis allocation plus realized issuance less burns at the UTC day's close, not circulating supply or the reserved-reward counter.",
    "total_supply_close_wei", "daily stock, never summed across days", "monetary ledger contract and source audit")
REALIZED_ISSUANCE = _ledger("realized-issuance", "Realized issuance", "Rewards issued during the UTC date, not cohort rewards.",
                            "issued_rewards_wei", "payout clock, additive flow")
REALIZED_BURN = _ledger("realized-burn", "Realized burn", "P-, X-, and C-Chain AVAX burned during the UTC date.",
                        "burned_wei", "burn clock, additive flow; source-component coverage stays in the ledger")

# Distinct identities over one reporting interval [interval_start, interval_end), never summed across intervals.
INTERVAL = {"interval_start": "timestamp", "interval_end": "timestamp"}
INTERVAL_COMPUTED = {"interval_start": "the interval_start parameter", "interval_end": "the interval_end parameter"}
IN_INTERVAL = "accepted_at >= $interval_start AND accepted_at < $interval_end"
VALIDATOR_STAKES = Relation("validators", {"accepted_at": "timestamp", "node_id": "string", "reward_addresses": "string"},
                            "derived.seamed-validator-stakes")
DELEGATOR_STAKES = Relation("delegators", {"accepted_at": "timestamp", "node_id": "string", "delegator_address": "string"},
                            "derived.seamed-delegator-stakes")
# The validator side's normalized address relation. Each commitment's reward list is parsed once and keeps only usable
# addresses, so a SQL null, a JSON null, an empty list, and a list of nulls or empty strings all leave no address.
VALIDATOR_LISTS = (f"SELECT accepted_at, node_id, list_filter(coalesce(from_json(reward_addresses, '[\"VARCHAR\"]'), []::VARCHAR[]),"
                   f" x -> x IS NOT NULL AND x <> '') AS addresses FROM validators WHERE {IN_INTERVAL}")
VALIDATOR_ADDRESSES = f"SELECT accepted_at, node_id, unnest(addresses) AS address FROM ({VALIDATOR_LISTS})"

COHORT_NODES = register(Measure(
    id="cohort-nodes", name="Cohort nodes", definition="Count of distinct NodeIDs receiving commitments in the interval, by role.",
    unit="count", grain=("interval_start", "interval_end", "role"),
    relations=(Relation("periods", {"accepted_at": "timestamp", "role": "string", "node_id": "string"}, PERIODS),),
    computed=INTERVAL_COMPUTED, parameters=INTERVAL,
    sql=f"SELECT $interval_start AS interval_start, $interval_end AS interval_end, role, count(DISTINCT node_id) AS value"
        f" FROM periods WHERE {IN_INTERVAL} GROUP BY ALL ORDER BY ALL",
    owner="data-science", nulls="a role with no commitment in the interval has no row",
    window="distinct over the whole interval, not a sum of daily counts", weighting="one per distinct node", citation="cohort explorer identity queries",
))
VALIDATOR_REWARD_ADDRESSES = register(Measure(
    id="validator-reward-addresses", name="Validator reward addresses",
    definition="Count of distinct addresses in the reward-owner lists of validator commitments accepted in the interval, not operators.",
    unit="count", grain=("interval_start", "interval_end"), relations=(VALIDATOR_STAKES,), computed=INTERVAL_COMPUTED, parameters=INTERVAL,
    counts=("commitments", "commitments_without_addresses"),
    sql=f"""SELECT $interval_start AS interval_start, $interval_end AS interval_end,
               (SELECT count(DISTINCT address) FROM ({VALIDATOR_ADDRESSES})) AS value, count(*) AS commitments,
               count(*) FILTER (WHERE len(addresses) = 0) AS commitments_without_addresses
            FROM ({VALIDATOR_LISTS})""",
    owner="data-science", nulls="address lists are normalized before the distinct count; a commitment with no usable address, "
                             "including an empty list, is left out and counted",
    window="distinct over the interval", weighting="one per distinct address", citation="validator receipt and cohort explorer",
))
DELEGATOR_FUNDING_ADDRESSES = register(Measure(
    id="delegator-funding-addresses", name="Delegator funding addresses",
    definition="Count of distinct recorded funding addresses of delegations accepted in the interval, not reward addresses or persons.",
    unit="count", grain=("interval_start", "interval_end"), relations=(DELEGATOR_STAKES,), computed=INTERVAL_COMPUTED, parameters=INTERVAL,
    counts=("commitments", "commitments_without_addresses"),
    sql=f"""SELECT $interval_start AS interval_start, $interval_end AS interval_end, count(DISTINCT nullif(delegator_address, '')) AS value,
               count(*) AS commitments, count(*) FILTER (WHERE nullif(delegator_address, '') IS NULL) AS commitments_without_addresses
            FROM delegators WHERE {IN_INTERVAL}""",
    owner="data-science", nulls="a delegation with a null or empty address is left out of the distinct count and counted",
    window="distinct over the interval", weighting="one per distinct address", citation="delegator receipt and cohort explorer",
))
NODE_ADDRESS_PAIRS = register(Measure(
    id="node-address-pairs", name="Node and address pairs",
    definition="Count of distinct linked NodeID and address pairs in the interval, separately for each role.",
    unit="count", grain=("interval_start", "interval_end", "role"), relations=(VALIDATOR_STAKES, DELEGATOR_STAKES),
    computed={**INTERVAL_COMPUTED, "role": "validator or delegator, from the relation"}, parameters=INTERVAL,
    sql=f"""SELECT $interval_start AS interval_start, $interval_end AS interval_end, role, count(DISTINCT (node_id, address)) AS value
            FROM (SELECT 'validator' AS role, node_id, address FROM ({VALIDATOR_ADDRESSES})
                  UNION ALL SELECT 'delegator', node_id, nullif(delegator_address, '') FROM delegators WHERE {IN_INTERVAL})
            WHERE node_id IS NOT NULL AND address IS NOT NULL
            GROUP BY ALL ORDER BY role""",
    owner="data-science", nulls="known identities only: a pair with a null node or a null address, after list expansion, is not counted",
    coverage="both relations cover the whole interval: the seamed stake tables of one day's derivation",
    window="distinct over the interval", weighting="one per distinct pair", citation="cohort explorer incidence queries",
))

# The Helicon forecast quantities F1 to F5 of the validation protocol (section 5, scoring in section 7.1). Each is scored
# over (window_start, end of scoring_date]: window_start is the forecast file's commit time, and only cycles that start
# after it count. The scoring date is a UTC date and counts whole, matching the ledger's stock at 23:59:59.
HELICON = "derived.helicon-commitments"
FORECAST = {"window_start": "timestamp", "scoring_date": "date"}
FORECAST_COMPUTED = {"window_start": "the window_start parameter", "scoring_date": "the scoring_date parameter"}
SCORED = "cycle_start > $window_start AND cycle_start < $scoring_date::TIMESTAMP + INTERVAL 1 DAY"
CYCLES = Relation("cycles", {"node_id": "string", "transaction_hash": "string", "cycle_start": "timestamp", "duration_days": "number",
                             "cycle_number": "integer", "node_status": "string", "lowered": "boolean"}, HELICON)
_FORECAST_CITATION = "validation protocol, section 5 and 7.1 (modeling lead)"

F1_SHORT_CYCLES = register(Measure(
    id="helicon-short-cycle-share", name="F1: share of new validation cycles under 7 days",
    definition="Share of validation cycles started in the scoring window whose duration is under 7 days.",
    unit="share", grain=("window_start", "scoring_date"), relations=(CYCLES,), computed=FORECAST_COMPUTED, parameters=FORECAST,
    counts=("cycles", "short_cycles"),
    sql=f"""SELECT $window_start AS window_start, $scoring_date AS scoring_date,
               count(*) FILTER (WHERE duration_days < 7)::DOUBLE / nullif(count(*), 0) AS value,
               count(*) AS cycles, count(*) FILTER (WHERE duration_days < 7) AS short_cycles
            FROM (SELECT DISTINCT transaction_hash, cycle_start, duration_days FROM cycles WHERE {SCORED})""",
    owner="modeling", nulls="a cycle is a distinct transaction and start; no cycle in the window gives a null value",
    window="cycles started after window_start and by the end of scoring_date", weighting="one per cycle", citation=_FORECAST_CITATION,
))
F2_AUTO_RENEWED = register(Measure(
    id="helicon-auto-renewed-share", name="F2: share of transactions auto-renewed at least once",
    definition="Share of validation transactions whose first cycle started in the scoring window that began a second cycle by the "
               "end of the scoring date.",
    unit="share", grain=("window_start", "scoring_date"), relations=(CYCLES,), computed=FORECAST_COMPUTED, parameters=FORECAST,
    counts=("transactions", "renewed_transactions"),
    sql=f"""WITH first AS (SELECT DISTINCT transaction_hash FROM cycles WHERE cycle_number = 1 AND {SCORED}),
                 renewed AS (SELECT DISTINCT transaction_hash FROM cycles WHERE cycle_number > 1 AND {SCORED})
            SELECT $window_start AS window_start, $scoring_date AS scoring_date,
                   count(r.transaction_hash)::DOUBLE / nullif(count(*), 0) AS value,
                   count(*) AS transactions, count(r.transaction_hash) AS renewed_transactions
            FROM first f LEFT JOIN renewed r USING (transaction_hash)""",
    owner="modeling", nulls="a renewal after the scoring date does not count, whatever the auto_renewed flag of a later build says; "
                             "no transaction in the window gives a null value",
    window="first cycles started after window_start and by the end of scoring_date", weighting="one per transaction", citation=_FORECAST_CITATION,
))
F3_LOWERED = register(Measure(
    id="helicon-lowered-share", name="F3: share of returning nodes' new cycles more than 1 day shorter",
    definition="Share of cycles started in the scoring window by returning nodes that are shorter than the node's previous period "
               "by more than 1 day, the tracker's lowered rule.",
    unit="share", grain=("window_start", "scoring_date"), relations=(CYCLES,), computed=FORECAST_COMPUTED, parameters=FORECAST,
    counts=("cycles", "lowered_cycles", "nodes", "lowered_nodes"),
    sql=f"""SELECT $window_start AS window_start, $scoring_date AS scoring_date,
               count(*) FILTER (WHERE lowered)::DOUBLE / nullif(count(*), 0) AS value,
               count(*) AS cycles, count(*) FILTER (WHERE lowered) AS lowered_cycles,
               count(DISTINCT node_id) AS nodes, count(DISTINCT node_id) FILTER (WHERE lowered) AS lowered_nodes
            FROM cycles WHERE node_status = 'returning' AND lowered IS NOT NULL AND {SCORED}""",
    owner="modeling", nulls="a cycle without a previous period has a null lowered flag and is left out; the node counts beside the "
                             "value give the per-node share the origin benchmark used",
    window="cycles started after window_start and by the end of scoring_date", weighting="one per cycle", citation=_FORECAST_CITATION,
))
_AT_SCORING_DATE = "WHERE date_utc = $scoring_date AND complete AND $window_start < $scoring_date::TIMESTAMP + INTERVAL 1 DAY"
F4_ACTIVE_VALIDATORS = register(Measure(
    id="helicon-active-validators", name="F4: active validators at the scoring date",
    definition="Validators active at 23:59:59 UTC on the scoring date.",
    unit="count", grain=("window_start", "scoring_date"),
    relations=(Relation("ledger", {"date_utc": "date", "active_validators": "integer", "complete": "boolean"}, LEDGER),),
    computed=FORECAST_COMPUTED, parameters=FORECAST,
    sql=f"SELECT $window_start AS window_start, $scoring_date AS scoring_date, active_validators AS value FROM ledger {_AT_SCORING_DATE}",
    owner="modeling", nulls="no row unless the ledger holds the scoring date as a complete day", window="the scoring date",
    weighting="daily stock", citation=_FORECAST_CITATION,
))
F5_STAKING_RATIO = register(Measure(
    id="helicon-staking-ratio", name="F5: staking ratio at the scoring date",
    definition="Active validator plus delegated stake over total supply at the close of the scoring date.",
    unit="share", grain=("window_start", "scoring_date"),
    relations=(Relation("ledger", {**LEDGER_STAKE, "active_delegated_stake_wei": "integer"}, LEDGER),),
    computed=FORECAST_COMPUTED, parameters=FORECAST,
    sql=f"""SELECT $window_start AS window_start, $scoring_date AS scoring_date,
               (active_validator_stake_wei + active_delegated_stake_wei)::DOUBLE / total_supply_close_wei AS value
            FROM ledger {_AT_SCORING_DATE} AND total_supply_close_wei > 0""",
    owner="modeling", nulls="no row unless the ledger holds the scoring date as a complete day with positive supply",
    window="the scoring date", weighting="daily stock", citation=_FORECAST_CITATION,
))
