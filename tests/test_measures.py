"""The measure registry, v0: declarations are checked, a measure reads a chain table and a run table the same way."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import duckdb
import pytest

from avalanche_research import measures
from avalanche_research.catalog import DataError, load_catalog

SHARE = measures.COMBINED_STAKED_SHARE
AM2 = measures.SAME_NODE_RENEWAL_7D


def utc(*parts: int) -> datetime:
    """A naive UTC time, as the period log stores it."""
    return datetime(*parts, tzinfo=UTC).replace(tzinfo=None)


def ledger(connection: duckdb.DuckDBPyConnection, name: str, extra: str = "") -> None:
    connection.execute(f"""CREATE TABLE "{name}" AS SELECT * FROM (VALUES
        (DATE '2026-09-01', 150::BIGINT, 50::BIGINT, 400::BIGINT, TRUE{extra}),
        (DATE '2026-09-02', 160::BIGINT, 40::BIGINT, 500::BIGINT, TRUE{extra}),
        (DATE '2026-09-03', 170::BIGINT, 30::BIGINT, 600::BIGINT, FALSE{extra}),
        (DATE '2026-09-04', 0::BIGINT, 0::BIGINT, NULL::BIGINT, TRUE{extra}))
        AS t(date_utc, active_validator_stake_wei, active_delegated_stake_wei, total_supply_close_wei, complete{", run_id" if extra else ""})""")


def test_the_registered_measures_match_the_catalog():
    assert set(measures.REGISTRY) == {"validator-staked-share", "combined-staked-share", "same-node-renewal-7d"}
    for measure in measures.REGISTRY.values():
        assert measures.check_datasets(measure, load_catalog()) == [], measure.id
    with pytest.raises(DataError, match="already registered"):
        measures.register(SHARE)


def test_a_bad_declaration_names_each_problem():
    two = (measures.Relation("ledger", SHARE.relations[0].columns, None), measures.Relation("ledger", {"x": "text"}, None))
    bad = replace(SHARE, id="Staked Share", unit="ratio", owner="anyone", relations=two, nulls="", grain=("day",), sql="SELECT $a",
                  parameters={"b": "integer"})
    assert bad.problems() == [
        "id 'Staked Share' is not lowercase words joined by hyphens", f"unit 'ratio' is not one of {', '.join(measures.UNITS)}",
        "owner 'anyone' is not one of data-science, modeling, data-engineering", "relation aliases are distinct lowercase names",
        "a measure applied to chain data names the dataset of every relation", "a measure with several relations states the common coverage it requires",
        "a measure states how it treats nulls and zeros", "every grain column is a source column or a declared computed column",
        f"column and parameter types are drawn from {', '.join(measures.TYPES)}", "the SQL does not read relation ledger",
        "the SQL does not read relation ledger", "the SQL does not use parameter $b"]


def test_a_chain_table_and_a_run_table_give_the_same_answer_on_complete_positive_supply():
    connection = duckdb.connect()
    ledger(connection, "chain")
    ledger(connection, "run", ", 'run-1'")
    chain = measures.compute(SHARE, connection, {"ledger": "chain"}).fetchall()
    # 09-03 is incomplete and 09-04 has no supply, so neither has a row.
    assert [(str(day), value) for day, value in chain] == [("2026-09-01", 0.5), ("2026-09-02", 0.4)]
    assert measures.compute(SHARE, connection, {"ledger": "run"}).fetchall() == chain


def test_a_missing_column_a_wrong_type_or_a_repeated_grain_is_refused():
    connection = duckdb.connect()
    connection.execute("CREATE TABLE short AS SELECT DATE '2026-09-01' AS date_utc")
    with pytest.raises(DataError, match="has no column active_validator_stake_wei"):
        measures.compute(SHARE, connection, {"ledger": "short"})
    connection.execute("CREATE TABLE text AS SELECT DATE '2026-09-01' AS date_utc, 'a' AS active_validator_stake_wei, 1 AS active_delegated_stake_wei,"
                       " 2 AS total_supply_close_wei, TRUE AS complete")
    with pytest.raises(DataError, match="is VARCHAR, the measure reads integer"):
        measures.compute(SHARE, connection, {"ledger": "text"})
    ledger(connection, "twice")
    connection.execute("INSERT INTO twice SELECT * FROM twice")
    with pytest.raises(DataError, match="rows repeat a grain"):
        measures.compute(SHARE, connection, {"ledger": "twice"})
    with pytest.raises(DataError, match="reads \\['ledger'\\], given \\['other'\\]"):
        measures.compute(SHARE, connection, {"other": "twice"})


def test_am2_pairs_before_selecting_endings_and_counts_what_it_excludes():
    connection = duckdb.connect()
    connection.execute("""CREATE TABLE periods AS SELECT * FROM (VALUES
        ('a1', 'validator', 'A', TIMESTAMP '2024-01-01', TIMESTAMP '2024-03-01'),
        ('a2', 'validator', 'A', TIMESTAMP '2024-03-08', TIMESTAMP '2024-06-01'),
        ('b1', 'validator', 'B', TIMESTAMP '2024-01-01', TIMESTAMP '2024-03-02'),
        ('b2', 'validator', 'B', TIMESTAMP '2024-03-10', TIMESTAMP '2024-06-01'),
        ('c1', 'validator', 'C', TIMESTAMP '2024-01-01', TIMESTAMP '2024-03-03'),
        ('c2', 'validator', 'C', TIMESTAMP '2024-02-01', TIMESTAMP '2024-06-01'),
        ('d1', 'validator', 'D', TIMESTAMP '2024-01-01', TIMESTAMP '2024-03-31'),
        ('x1', 'delegator', 'A', TIMESTAMP '2024-03-01', TIMESTAMP '2024-03-05'))
        AS t(transaction_hash, role, node_id, start_time, end_time)""")
    # March endings: a1 renews at exactly seven days, b1 after eight, c1 overlaps its successor, and d1 has no full follow-up.
    parameters = {"cohort_start": utc(2024, 3, 1), "cohort_end": utc(2024, 4, 1), "observed_through": utc(2024, 4, 5), "days": 7}
    ((start, end, value, cohort, eligible, renewed, censored, overlapping),) = measures.compute(AM2, connection, {"periods": "periods"}, parameters).fetchall()
    assert (start, end, value, cohort, eligible, renewed, censored, overlapping) == (
        utc(2024, 3, 1), utc(2024, 4, 1), 0.5, 4, 2, 1, 1, 1)
    with pytest.raises(DataError, match="takes parameters"):
        measures.compute(AM2, connection, {"periods": "periods"}, {"days": 7})
