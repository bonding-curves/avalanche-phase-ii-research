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
SAME_NODE_RENEWAL_7D = register(Measure(
    id="same-node-renewal-7d",
    name="Same-node renewal within seven days (AM2)",
    definition="Share of fully followed-up ending validator commitments whose next same-node commitment starts between "
               "the end and seven days after it, both boundaries included.",
    unit="share",
    grain=("cohort_start", "cohort_end"),
    relations=(Relation("periods", {"transaction_hash": "string", "role": "string", "node_id": "string", "start_time": "timestamp",
                                    "end_time": "timestamp"}, PERIODS),),
    computed={"cohort_start": "the cohort_start parameter", "cohort_end": "the cohort_end parameter"},
    counts=("cohort_ends", "eligible_ends", "renewed_ends", "censored_ends", "overlapping_ends"),
    parameters={"cohort_start": "timestamp", "cohort_end": "timestamp", "observed_through": "timestamp", "days": "integer"},
    sql="""
        WITH paired AS (
            SELECT end_time, epoch(lead(start_time) OVER (PARTITION BY node_id ORDER BY start_time, transaction_hash) - end_time) / 86400.0 AS gap_days
            FROM periods WHERE role = 'validator'
        ), cohort AS (
            SELECT gap_days, end_time + to_days($days) <= $observed_through AS complete, coalesce(gap_days < 0, FALSE) AS overlapping
            FROM paired WHERE end_time >= $cohort_start AND end_time < $cohort_end
        )
        SELECT $cohort_start AS cohort_start, $cohort_end AS cohort_end,
               count(*) FILTER (WHERE complete AND NOT overlapping AND gap_days BETWEEN 0 AND $days)::DOUBLE
                   / nullif(count(*) FILTER (WHERE complete AND NOT overlapping), 0) AS value,
               count(*) AS cohort_ends,
               count(*) FILTER (WHERE complete AND NOT overlapping) AS eligible_ends,
               count(*) FILTER (WHERE complete AND NOT overlapping AND gap_days BETWEEN 0 AND $days) AS renewed_ends,
               count(*) FILTER (WHERE NOT complete) AS censored_ends,
               count(*) FILTER (WHERE complete AND overlapping) AS overlapping_ends
        FROM cohort""",
    owner="data-science",
    nulls="an ending without a later commitment on its node is not renewed; an ending without the full follow-up is censored "
          "and counted; a successor that starts before the end is excluded and counted; no eligible ending gives a null value",
    window="endings in [cohort_start, cohort_end), follow-up of days after each end, observed through the input's last acceptance",
    weighting="one equal observation per ending commitment, not per node",
    citation="client 7ca051e, staking_renewal.renewal_summary",
))
