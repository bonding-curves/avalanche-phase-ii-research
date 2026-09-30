"""The measure registry: each KPI and moment defined once, and applied to chain tables and simulated run tables alike.

v0, unreviewed. A schema draft for the package layer ``measures``: it reads tables only and imports neither the
mechanisms nor the model, so a run's output table and a chain dataset go through the same definition.

A measure declares the columns it reads, the grain of its answer, one unit, and one SQL ``SELECT`` over a relation named
``source``. The answer is a table of the grain columns and one ``value`` column, one row per grain. Definitions are
written by the lane named as owner: data science for empirical measures and moments, the modeling lead for model
measures, data engineering for this schema and the dataset side.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .catalog import DataError, dataset

OWNERS = ("data-science", "modeling", "data-engineering")
UNITS = ("share", "AVAX", "nAVAX", "count", "days", "percent per year", "USD")
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


@dataclass(frozen=True)
class Measure:
    """One definition. ``columns`` maps each column the SQL reads to its catalog type; ``grain`` names the output's key."""

    id: str
    name: str
    definition: str
    unit: str
    grain: tuple[str, ...]
    columns: dict[str, str]
    sql: str
    owner: str
    applies_to: tuple[str, ...] = ("chain", "run")
    datasets: tuple[str, ...] = ()
    window: str | None = None
    weighting: str | None = None
    citation: str | None = None
    version: int = 1
    notes: tuple[str, ...] = field(default=())

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
        if "chain" in self.applies_to and not self.datasets:
            found.append("a measure applied to chain data names the datasets it reads")
        if not self.grain or set(self.grain) - set(self.columns):
            found.append("every grain column is one of the declared columns")
        if set(self.columns.values()) - set(TYPES):
            found.append(f"column types are drawn from {', '.join(TYPES)}")
        if not re.search(r"\bsource\b", self.sql):
            found.append("the SQL reads the relation named source")
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
    """Each chain dataset the measure names carries every column it reads, with the declared catalog type."""
    found = []
    for dataset_id in measure.datasets:
        try:
            fields = {item["name"]: item["type"] for item in dataset(catalog, dataset_id)["fields"]}
        except DataError as error:
            found.append(str(error))
            continue
        for name, kind in measure.columns.items():
            if name not in fields:
                found.append(f"{dataset_id} has no column {name}")
            elif fields[name] != kind and not (kind == "date" and fields[name] == "string"):
                found.append(f"{dataset_id}.{name} is {fields[name]}, the measure reads {kind}")
    return found


def compute(measure: Measure, connection: Any, relation: str) -> Any:
    """The measure over a table or view in ``connection``: grain columns and ``value``, one row per grain."""
    described = {row[0]: row[1] for row in connection.execute(f'DESCRIBE SELECT * FROM "{relation}"').fetchall()}
    for name, kind in measure.columns.items():
        if name not in described:
            raise DataError(f"measure {measure.id}: {relation} has no column {name}")
        if described[name].split("(")[0] not in TYPES[kind]:
            raise DataError(f"measure {measure.id}: {relation}.{name} is {described[name]}, the measure reads {kind}")
    connection.execute(f'CREATE OR REPLACE TEMP VIEW source AS SELECT * FROM "{relation}"')
    result = connection.sql(measure.sql)
    if result.columns != [*measure.grain, "value"]:
        raise DataError(f"measure {measure.id}: the SQL returns {result.columns}, not {[*measure.grain, 'value']}")
    keys = ", ".join(f'"{name}"' for name in measure.grain)
    repeated = connection.execute(f"SELECT count(*) - count(DISTINCT ({keys})) FROM ({measure.sql})").fetchone()[0]
    if repeated:
        raise DataError(f"measure {measure.id}: {repeated} rows repeat a grain")
    return result


# An example that proves the schema on a real dataset. It is not a reviewed definition: the data scientist's
# definitions replace it as they arrive.
STAKED_SHARE_DAILY = register(Measure(
    id="staked-share-daily",
    name="Staked share of supply",
    definition="Active validator and delegated stake at the day's last second, over total supply at the day's close.",
    unit="share",
    grain=("date_utc",),
    columns={"date_utc": "date", "active_validator_stake_wei": "integer", "active_delegated_stake_wei": "integer",
             "total_supply_close_wei": "integer"},
    sql="SELECT date_utc, (active_validator_stake_wei + active_delegated_stake_wei)::DOUBLE / total_supply_close_wei AS value"
        " FROM source WHERE total_supply_close_wei IS NOT NULL ORDER BY date_utc",
    owner="data-engineering",
    datasets=("derived.avax-monetary-daily",),
    notes=("Example for the v0 schema, not a reviewed definition.",),
))
