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
    # The eighteen definitions of the data scientist's table of 2026-09-30 15:28 and the five Helicon forecast quantities, with AM2's fourteen-day sensitivity.
    assert len(measures.REGISTRY) == 24 and {"same-node-renewal-7d", "combined-staked-share", "node-address-pairs"} <= set(measures.REGISTRY)
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
    parameters = {"cohort_start": utc(2024, 3, 1), "cohort_end": utc(2024, 4, 1), "observed_through": utc(2024, 4, 5)}
    ((start, end, value, cohort, eligible, renewed, censored, overlapping),) = measures.compute(AM2, connection, {"periods": "periods"}, parameters).fetchall()
    assert (start, end, value, cohort, eligible, renewed, censored, overlapping) == (
        utc(2024, 3, 1), utc(2024, 4, 1), 0.5, 4, 2, 1, 1, 1)
    with pytest.raises(DataError, match="takes parameters"):
        measures.compute(AM2, connection, {"periods": "periods"}, {"days": 7})


def test_a_cohort_sum_keeps_a_recorded_zero_apart_from_a_missing_outcome():
    connection = duckdb.connect()
    connection.execute("""CREATE TABLE periods AS SELECT * FROM (VALUES
        ('t1', 'validator', TIMESTAMP '2026-09-01 01:00', 2000.0, 14.0, 5.0),
        ('t2', 'validator', TIMESTAMP '2026-09-01 02:00', 3000.0, 28.0, 0.0),
        ('t3', 'validator', TIMESTAMP '2026-09-01 03:00', 1000.0, 14.0, NULL),
        ('t4', 'delegator', TIMESTAMP '2026-09-01 04:00', 25.0, 14.0, NULL))
        AS t(transaction_hash, role, accepted_at, stake_avax, duration_days, realized_reward_avax)""")
    def rows(measure_id):
        return measures.compute(measures.REGISTRY[measure_id], connection, {"periods": "periods"}).fetchall()
    day = utc(2026, 9, 1).date()
    assert rows("commitments-accepted") == [(day, "delegator", 1), (day, "validator", 3)]
    assert rows("committed-stake-duration") == [(day, "delegator", 350.0), (day, "validator", 2000 * 14 + 3000 * 28 + 1000 * 14.0)]
    # t2's zero is a known outcome; t3 and t4 have none, so the delegator cohort has no reward row at all.
    assert rows("cohort-realized-rewards") == [(day, "validator", 5.0)]
    assert rows("cohort-reward-outcomes") == [(day, "delegator", 0), (day, "validator", 2)]


def test_node_address_pairs_expand_reward_lists_and_keep_roles_apart():
    connection = duckdb.connect()
    connection.execute("""CREATE TABLE validators AS SELECT * FROM (VALUES
        (TIMESTAMP '2026-09-02', 'N1', '["a", "b"]'), (TIMESTAMP '2026-09-03', 'N1', '["a"]'), (TIMESTAMP '2026-09-04', 'N2', NULL),
        (TIMESTAMP '2026-10-02', 'N3', '["z"]')) AS t(accepted_at, node_id, reward_addresses)""")
    connection.execute("""CREATE TABLE delegators AS SELECT * FROM (VALUES
        (TIMESTAMP '2026-09-02', 'N1', 'a'), (TIMESTAMP '2026-09-05', 'N2', 'a'), (TIMESTAMP '2026-09-06', 'N2', NULL))
        AS t(accepted_at, node_id, delegator_address)""")
    interval = {"interval_start": utc(2026, 9, 1), "interval_end": utc(2026, 10, 1)}
    tables = {"validators": "validators", "delegators": "delegators"}
    pairs = measures.compute(measures.REGISTRY["node-address-pairs"], connection, tables, interval).fetchall()
    assert [(role, value) for _, _, role, value in pairs] == [("delegator", 2), ("validator", 2)]
    addresses = measures.compute(measures.REGISTRY["validator-reward-addresses"], connection, {"validators": "validators"}, interval).fetchall()
    assert addresses[0][2:] == (2, 3, 1)


def test_the_helicon_forecast_quantities_score_only_the_window():
    connection = duckdb.connect()
    # Commit at 09-30 00:00, scoring date 10-22. c0 starts before the commit and is not scored; c5 starts on 10-23.
    connection.execute("""CREATE TABLE cycles AS SELECT * FROM (VALUES
        ('N0', 't0', TIMESTAMP '2026-09-29 12:00', 3.0, 1, 'returning', TRUE),
        ('N1', 't1', TIMESTAMP '2026-10-01 00:00', 3.0, 1, 'returning', TRUE),
        ('N1', 't1', TIMESTAMP '2026-10-04 00:00', 3.0, 2, 'returning', FALSE),
        ('N2', 't2', TIMESTAMP '2026-10-02 00:00', 30.0, 1, 'returning', FALSE),
        ('N3', 't3', TIMESTAMP '2026-10-22 23:00', 14.0, 1, 'new', NULL),
        ('N3', 't3', TIMESTAMP '2026-11-05 23:00', 14.0, 2, 'new', NULL),
        ('N4', 't4', TIMESTAMP '2026-10-23 00:00', 2.0, 1, 'returning', TRUE))
        AS t(node_id, transaction_hash, cycle_start, duration_days, cycle_number, node_status, lowered)""")
    connection.execute("""CREATE TABLE ledger AS SELECT * FROM (VALUES
        (DATE '2026-10-21', 590::BIGINT, 160::BIGINT, 40::BIGINT, 500::BIGINT, TRUE),
        (DATE '2026-10-22', 588::BIGINT, 150::BIGINT, 50::BIGINT, 400::BIGINT, TRUE))
        AS t(date_utc, active_validators, active_validator_stake_wei, active_delegated_stake_wei, total_supply_close_wei, complete)""")
    window = {"window_start": utc(2026, 9, 30), "scoring_date": utc(2026, 10, 22).date()}

    def score(measure, alias):
        return measures.compute(measure, connection, {alias: alias}, window).fetchall()[0][2:]

    # Cycles scored: t1 twice, t2, t3's first. Two of four are under 7 days.
    assert score(measures.F1_SHORT_CYCLES, "cycles") == (0.5, 4, 2)
    # Transactions first seen in the window: t1, t2, t3. Only t1 renewed by 10-22; t3's renewal on 11-05 is too late.
    assert score(measures.F2_AUTO_RENEWED, "cycles") == (1 / 3, 3, 1)
    # Returning cycles with a previous period: t1 twice and t2. One lowered, on one of two nodes.
    assert score(measures.F3_LOWERED, "cycles") == (1 / 3, 3, 1, 2, 1)
    assert score(measures.F4_ACTIVE_VALIDATORS, "ledger") == (588,)
    assert score(measures.F5_STAKING_RATIO, "ledger") == (0.5,)


def test_a_pair_with_an_unknown_node_or_address_is_not_counted():
    # MR1 of the data scientist's 15:59 review: every pair below has a null side, so no role has a pair.
    connection = duckdb.connect()
    connection.execute("""CREATE TABLE validators AS SELECT * FROM (VALUES
        (TIMESTAMP '2026-09-02', NULL, '["v"]'), (TIMESTAMP '2026-09-03', 'N1', '[null]')) AS t(accepted_at, node_id, reward_addresses)""")
    connection.execute("CREATE TABLE delegators AS SELECT TIMESTAMP '2026-09-02' AS accepted_at, NULL::VARCHAR AS node_id, 'd' AS delegator_address")
    interval = {"interval_start": utc(2026, 9, 1), "interval_end": utc(2026, 10, 1)}
    pairs = measures.compute(measures.NODE_ADDRESS_PAIRS, connection, {"validators": "validators", "delegators": "delegators"}, interval).fetchall()
    assert pairs == []


def test_a_commitment_with_no_usable_address_is_counted_as_missing():
    # MR2 of the data scientist's 15:59 review: four of five commitments have no usable address.
    connection = duckdb.connect()
    connection.execute("""CREATE TABLE validators AS SELECT * FROM (VALUES
        (TIMESTAMP '2026-09-02', 'N1', '["v"]'), (TIMESTAMP '2026-09-02', 'N2', '[null]'), (TIMESTAMP '2026-09-02', 'N3', '[]'),
        (TIMESTAMP '2026-09-02', 'N4', 'null'), (TIMESTAMP '2026-09-02', 'N5', NULL)) AS t(accepted_at, node_id, reward_addresses)""")
    interval = {"interval_start": utc(2026, 9, 1), "interval_end": utc(2026, 10, 1)}
    ((_, _, value, commitments, missing),) = measures.compute(measures.VALIDATOR_REWARD_ADDRESSES, connection, {"validators": "validators"}, interval).fetchall()
    assert (value, commitments, missing) == (1, 5, 4)
    connection.execute("""CREATE TABLE delegators AS SELECT * FROM (VALUES
        (TIMESTAMP '2026-09-02', 'N1', 'd'), (TIMESTAMP '2026-09-02', 'N1', ''), (TIMESTAMP '2026-09-02', 'N1', NULL)) AS t(accepted_at, node_id, delegator_address)""")
    ((_, _, value, commitments, missing),) = measures.compute(measures.DELEGATOR_FUNDING_ADDRESSES, connection, {"delegators": "delegators"}, interval).fetchall()
    assert (value, commitments, missing) == (1, 3, 2)


def test_am2_refuses_invalid_input_and_keeps_its_horizon_fixed():
    # MR3 of the data scientist's 15:59 review.
    window = {"cohort_start": utc(2024, 3, 1), "cohort_end": utc(2024, 4, 1), "observed_through": utc(2024, 6, 1)}
    good = [("a1", "validator", "A", "2024-01-01", "2024-03-01"), ("a2", "validator", "A", "2024-03-11", "2024-06-01")]

    def run(rows, measure=AM2, parameters=window):
        connection = duckdb.connect()
        values = ", ".join(f"({t!r}, {r!r}, {'NULL' if n is None else repr(n)}, TIMESTAMP {s!r}, TIMESTAMP {e!r})" for t, r, n, s, e in rows)
        connection.execute(f"CREATE TABLE periods AS SELECT * FROM (VALUES {values}) AS t(transaction_hash, role, node_id, start_time, end_time)")
        return measures.compute(measure, connection, {"periods": "periods"}, parameters).fetchall()

    # A ten-day gap renews under the fourteen-day sensitivity and not under AM2.
    assert run(good)[0][2] == 0.0 and run(good, measures.SAME_NODE_RENEWAL_14D)[0][2] == 1.0
    with pytest.raises(DataError, match="1 validator commitments with a null transaction, node"):
        run([("n1", "validator", None, "2024-01-01", "2024-03-01"), *good])
    with pytest.raises(DataError, match="1 validator transactions listed more than once"):
        run([*good, good[0]])
    with pytest.raises(DataError, match="end at or before their start"):
        run([*good, ("z1", "validator", "Z", "2024-03-05", "2024-03-05")])
    with pytest.raises(DataError, match="a cohort whose end does not follow its start"):
        run(good, parameters={**window, "cohort_end": utc(2024, 2, 1)})
