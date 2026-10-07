"""The validator-week panel is derived from small synthetic runs of the staking-period log, not from network access."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from avalanche_research.core.catalog import (
    canonical_bytes,
    contract_hash,
    load_catalog,
    sha256,
)
from avalanche_research.datasets.derived import weeks
from avalanche_research.domain.protocol import annualized_reward_rate

NAVAX = 10**9
CATALOG = load_catalog()
CONCENTRATED = weeks.CONCENTRATED_ADDRESS

# (hash, role, node, validator hash, accepted, start, end, stake AVAX, fee, address)
PERIODS = [
    # Node A: four weeks, a gap, then six weeks with a new reward address.
    ("P1", "validator", "A", None, "2020-09-22 01:00", "2020-09-22 02:00", "2020-10-20 02:00", 2_000, 0.02, "addrA1"),
    ("P2", "validator", "A", None, "2020-11-05 00:00", "2020-11-05 01:00", "2020-12-17 01:00", 3_000, 0.05, "addrA2"),
    # Node B starts on a Wednesday with a million AVAX, so its weight limit is the 3M cap, not five times its stake.
    ("P3", "validator", "B", None, "2020-09-30 00:00", "2020-09-30 01:00", "2021-09-30 01:00", 1_000_000, 0.10, "addrB"),
    # Node C is accepted on a Friday to start the next Wednesday.
    ("P4", "validator", "C", None, "2020-10-09 00:00", "2020-10-14 00:00", "2021-01-14 00:00", 2_000, 1.00, "addrC"),
    ("D1", "delegator", "A", "P1", "2020-09-23 00:00", "2020-09-23 00:00", "2020-10-15 00:00", 100, None, CONCENTRATED),
    ("D2", "delegator", "A", "P1", "2020-09-24 00:00", "2020-09-24 00:00", "2020-10-10 00:00", 50, None, "d2"),
    ("D3", "delegator", "B", "P3", "2020-09-30 03:00", "2020-09-30 03:00", "2020-12-01 00:00", 1_999_000, None, "d3"),
    # Accepted before the 10-05 cutoff, scheduled to start inside its next fourteen days: it uses the capacity.
    ("D4", "delegator", "B", "P3", "2020-10-03 00:00", "2020-10-12 00:00", "2020-12-01 00:00", 990, None, "d4"),
    # Delegated to C before C starts: C has no row in that week.
    ("D5", "delegator", "C", "P4", "2020-10-09 01:00", "2020-10-14 00:00", "2020-11-14 00:00", 30, None, "d5"),
    # Node F is full to the nAVAX: its room, 4 x 2,841.235 AVAX, is where subtracting AVAX doubles gives -1.8e-12.
    ("P5", "validator", "F", None, "2020-10-01 00:00", "2020-10-01 01:00", "2021-03-01 00:00", 2_841.235, 0.05, "addrF"),
    ("D6", "delegator", "F", "P5", "2020-10-06 00:00", "2020-10-06 00:00", "2020-10-21 00:00", 11_364.94, None, CONCENTRATED),
    # A midweek refill: accepted on the Wednesday D6 ends, starting the instant it ends.
    ("D7", "delegator", "F", "P5", "2020-10-21 00:00", "2020-10-21 00:00", "2020-11-20 00:00", 11_364.94, None, CONCENTRATED),
    # Pending: accepted on 11-10 to start on 11-25, after D7 has ended.
    ("D8", "delegator", "F", "P5", "2020-11-10 00:00", "2020-11-25 00:00", "2020-12-20 00:00", 25, None, "d8"),
    # Starts after D7 ends, but D8 starts inside its interval: 25 AVAX of the room is taken.
    ("D9", "delegator", "F", "P5", "2020-11-21 00:00", "2020-11-21 00:00", "2020-12-21 00:00", 11_350, None, "d9"),
    # B has 10 AVAX left under the 3M cap, and 2M under five times its stake: before Apricot Phase 3 that was accepted.
    ("D10", "delegator", "B", "P3", "2020-10-20 00:00", "2020-10-20 00:00", "2020-11-20 00:00", 20, None, "d10"),
    # After Apricot Phase 3, one nAVAX over the 3M cap on an empty validator.
    ("D11", "delegator", "B", "P3", "2021-09-01 00:00", "2021-09-01 00:00", "2021-09-20 00:00", 2_000_001, None, "d11"),
    # Ends after C's period ends.
    ("D12", "delegator", "C", "P4", "2020-10-20 00:00", "2020-10-20 00:00", "2021-02-01 00:00", 30, None, "d12"),
]


def make_run(root: Path, name: str, dataset_id: str, table: str, sql: str) -> Path:
    capture_dir, dataset_dir = root / name / "capture", root / name / "dataset"
    capture_dir.mkdir(parents=True), dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / f"{table}.parquet"
    duckdb.sql(f"COPY ({sql}) TO '{parquet}' (FORMAT PARQUET)")
    capture_id = f"capture:test:{name}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({
        "schema_version": "test-capture/v1", "capture_id": capture_id, "dataset_id": dataset_id, "completed_at": "2026-09-27T00:00:00Z",
        "contract_sha256": contract_hash(CATALOG, dataset_id)}))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({
        "schema_version": "test-build/v1", "dataset_id": dataset_id, "source_capture_id": capture_id, "completed_at": "2026-09-27T00:00:00Z",
        "summary": {"rows": 1}, "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}]}))
    return parquet


@pytest.fixture
def runs(tmp_path: Path) -> Path:
    root = tmp_path / "runs"
    values = ", ".join(
        f"('{h}', '{role}', '{node}', {repr(vh) if vh else 'NULL'}::VARCHAR, TIMESTAMP '{acc}', TIMESTAMP '{start}', TIMESTAMP '{end}', "
        f"{round(stake * NAVAX)}::BIGINT, {fee if fee is not None else 'NULL'}::DOUBLE)"
        for h, role, node, vh, acc, start, end, stake, fee, _ in PERIODS)
    # One transaction per block, in order of acceptance.
    make_run(root, "periods", "derived.staking-periods", "staking-periods",
             f"SELECT *, row_number() OVER (ORDER BY accepted_at, transaction_hash)::BIGINT AS block_height FROM (VALUES {values}) "
             "AS t(transaction_hash, role, node_id, validator_transaction_hash, accepted_at, start_time, end_time, stake_navax, delegation_fee_rate)")
    rows = lambda role: ", ".join(f"('{h}', '{address}')" for h, r, *_, address in PERIODS if r == role)
    make_run(root, "validators", "snowflake.primary-validator-stakes", "primary-validator-stakes",
             f"SELECT * FROM (VALUES {rows('validator')}) AS t(transaction_hash, reward_address)")
    make_run(root, "delegators", "snowflake.primary-delegator-stakes", "primary-delegator-stakes",
             f"SELECT * FROM (VALUES {rows('delegator')}) AS t(transaction_hash, delegator_address)")
    # The supply counter is read at 400M before 10-01 and 401M from then; no reading exists before 09-15.
    make_run(root, "supply", "snowflake.primary-staking-supply", "primary-staking-supply",
             f"SELECT * FROM (VALUES (TIMESTAMP '2020-09-15 00:00', {400_000_000 * NAVAX}::BIGINT), (TIMESTAMP '2020-10-01 00:00', {401_000_000 * NAVAX}::BIGINT), "
             f"(TIMESTAMP '2020-10-02 00:00', NULL::BIGINT)) AS t(accepted_at, block_supply_navax)")
    return root


@pytest.fixture
def market_runs(runs: Path) -> Path:
    wei = 10**18
    days = "range(DATE '2020-09-15', DATE '2020-10-20', INTERVAL 1 DAY)"
    make_run(runs, "ledger", "derived.avax-monetary-daily", "avax-monetary-daily",
             f"SELECT d::DATE AS date_utc, '{400_000_000 * wei}'::DECIMAL(38,0) AS total_supply_close_wei, '{100_000_000 * wei}'::DECIMAL(38,0) AS active_validator_stake_wei, "
             f"'{20_000_000 * wei}'::DECIMAL(38,0) AS active_delegated_stake_wei, d::DATE <> DATE '2020-10-11' AS complete FROM {days} t(d)")
    make_run(runs, "binance", "binance.avax-usdt-daily", "avax-usdt-daily",
             f"SELECT d::DATE AS observation_date, (4 + day(d) / 100)::DOUBLE AS close_usdt, 0.5::DOUBLE AS realized_volatility_30d FROM {days} t(d)")
    # DefiLlama has two points on 2020-10-04: 00:00 and 23:59. The second is nearer the 10-05 cutoff.
    make_run(runs, "defillama", "defillama.avax-price-daily", "avax-price-daily",
             "SELECT observed_at, observation_date, price_usd::DOUBLE AS price_usd, volatility::DOUBLE AS realized_volatility_30d FROM (VALUES "
             "(TIMESTAMP '2020-10-04 00:00', DATE '2020-10-04', 4.0, 0.6), (TIMESTAMP '2020-10-04 23:59', DATE '2020-10-04', 4.1, 0.61), "
             "(TIMESTAMP '2020-09-28 00:01', DATE '2020-09-28', 3.9, 0.7)) AS t(observed_at, observation_date, price_usd, volatility)")
    return runs


def built(runs: Path, dataset_id: str) -> dict:
    output = runs / f"out-{dataset_id}"
    weeks.derive(dataset_id, output, None, runs)
    table = duckdb.sql(f"SELECT * FROM read_parquet('{output / 'dataset' / (weeks.TABLES[dataset_id] + '.parquet')}')")
    return {"output": output, "rows": [dict(zip(table.columns, row)) for row in table.fetchall()]}


def row(rows: list[dict], node: str, week: str) -> dict | None:
    return next((item for item in rows if item["node_id"] == node and str(item["week_start_utc"])[:10] == week), None)


def paths_of(runs: Path) -> dict[str, Path]:
    return {"staking-periods": runs / "periods/dataset/staking-periods.parquet", "validator-stakes": runs / "validators/dataset/primary-validator-stakes.parquet",
            "delegator-stakes": runs / "delegators/dataset/primary-delegator-stakes.parquet", "staking-supply": runs / "supply/dataset/primary-staking-supply.parquet"}


def test_catalog_declares_the_three_tables():
    for dataset_id, columns in ((weeks.WEEKS_ID, weeks.WEEK_COLUMNS), (weeks.DELEGATIONS_ID, weeks.DELEGATION_COLUMNS), (weeks.MARKET_ID, weeks.MARKET_COLUMNS)):
        definition = next(item for item in CATALOG["datasets"] if item["id"] == dataset_id)
        assert [field["name"] for field in definition["fields"]] == list(columns)


def test_rows_features_and_outcomes(runs):
    rows = built(runs, weeks.WEEKS_ID)["rows"]
    # A starts during the week of 09-21: a row, not active at its cutoff, holding the week's two delegations.
    entry = row(rows, "A", "2020-09-21")
    assert entry["active_at_week_start"] is False and entry["offered_at_week_start"] is False and entry["node_age_weeks"] is None
    assert (entry["delegations_all"], entry["delegated_avax_all"], entry["delegations_excl_concentrated"], entry["delegated_avax_excl_concentrated"]) == (2, 150.0, 1, 50.0)
    week = row(rows, "A", "2020-09-28")
    assert week["active_at_week_start"] and week["validator_transaction_hash"] == "P1" and week["self_stake_avax"] == 2_000
    assert week["node_age_weeks"] == pytest.approx((6 * 24 - 2) / 168) and (week["completed_periods"], week["started_periods"]) == (0, 1)
    assert week["reward_address_asof"] == "addrA1" and week["delegated_avax_at_week_start"] == 150.0 and week["max_weight_avax"] == 10_000
    assert week["days_remaining"] == pytest.approx(22 + 2 / 24) and week["offered_at_week_start"]
    # The gap weeks of A have no row: whether A returns is not known at their cutoffs.
    assert row(rows, "A", "2020-10-26") is None
    later = row(rows, "A", "2020-11-09")
    assert (later["completed_periods"], later["started_periods"], later["reward_address_asof"]) == (1, 2, "addrA2")
    assert later["node_age_weeks"] == pytest.approx((48 * 24 - 2) / 168)
    assert later["days_staked_weeks"] == pytest.approx(4 + (4 * 24 - 1) / 168), "four weeks of P1 and the part of P2 before the cutoff, the gap excluded"


def test_capacity_uses_the_factor_before_apricot_3_and_the_3m_cap_after(runs):
    rows = built(runs, weeks.WEEKS_ID)["rows"]
    entry = row(rows, "B", "2020-09-28")
    assert entry["active_at_week_start"] is False and entry["delegations_all"] == 2, "D3 and D4 are both accepted in the week of 09-28"
    # Before Apricot Phase 3 (2021-08-24) AvalancheGo checked only five times the stake: B's 1M AVAX allowed 5M.
    week = row(rows, "B", "2020-10-05")
    assert week["max_weight_avax"] == 5_000_000
    assert week["delegated_avax_at_week_start"] == 1_999_000 and week["max_delegated_avax_14d"] == 1_999_990
    assert week["capacity_left_avax"] == 2_001_000 and week["capacity_left_avax_14d"] == pytest.approx(2_000_010)
    assert week["offered_at_week_start"] is True
    # From Apricot Phase 3 the 3M AVAX cap applies again.
    assert row(rows, "B", "2021-08-30")["max_weight_avax"] == 3_000_000


def test_quotes_are_the_kernel_at_the_cutoff_supply(runs):
    rows = built(runs, weeks.WEEKS_ID)["rows"]
    week = row(rows, "A", "2020-09-28")
    cutoff = datetime(2020, 9, 28, tzinfo=UTC)
    assert week["supply_counter_avax"] == 400_000_000 and str(week["supply_read_at"]) == "2020-09-15 00:00:00"
    assert week["gross_rate_14d"] == annualized_reward_rate(cutoff, 14 * 86_400, 25 * NAVAX, 400_000_000 * NAVAX)
    assert week["net_rate_14d"] == pytest.approx(week["gross_rate_14d"] * 0.98)
    remaining = int((datetime(2020, 10, 20, 2, tzinfo=UTC) - cutoff).total_seconds())
    assert week["gross_rate_remaining"] == annualized_reward_rate(cutoff, remaining, 25 * NAVAX, 400_000_000 * NAVAX)
    later = row(rows, "B", "2020-10-05")
    assert later["supply_counter_avax"] == 401_000_000, "the null reading of 10-02 is skipped"
    assert row(rows, "A", "2020-09-21")["gross_rate_14d"] is None, "no quote for a row not active at its cutoff"
    full_fee = row(rows, "C", "2020-10-19")
    assert full_fee["net_rate_14d"] == 0 and full_fee["log_net_apy_14d"] is None and full_fee["offered_at_week_start"], "a 100% fee stays an offer"


def test_the_market_week(market_runs):
    rows = {str(item["week_start_utc"])[:10]: item for item in built(market_runs, weeks.MARKET_ID)["rows"]}
    assert len(rows) == 313
    week = rows["2020-09-28"]
    assert (week["total_supply_avax"], week["unstaked_supply_avax"], week["supply_checked"]) == (400_000_000, 280_000_000, True)
    assert (week["delegations_all"], week["delegations_excl_concentrated"], week["validators_active"]) == (2, 2, 1)
    first = rows["2020-09-21"]
    assert first["concentrated_event_share"] == 0.5 and first["concentrated_avax_share"] == pytest.approx(100 / 150)
    assert str(week["price_date"]) == "2020-09-27" and week["price_usdt"] == pytest.approx(4.27) and week["price_usd_defillama"] == 3.9
    assert rows["2020-10-05"]["price_usd_defillama"] == 4.1, "of two points on one date, the one nearest the cutoff"
    assert rows["2020-10-12"]["supply_checked"] is False, "the Sunday before is incomplete in the ledger"
    assert rows["2020-11-02"]["price_present"] is False and rows["2020-11-02"]["delegations_all"] == 0


def test_every_delegation_is_kept_and_flagged(runs):
    delegations = {item["transaction_hash"]: item for item in built(runs, weeks.DELEGATIONS_ID)["rows"]}
    assert set(delegations) == {f"D{number}" for number in range(1, 13)}
    assert delegations["D1"]["concentrated_address"] and not delegations["D2"]["concentrated_address"]
    assert delegations["D4"]["duration_seconds"] == 50 * 86_400 and delegations["D4"]["duration_weeks"] == pytest.approx(50 / 7)
    assert delegations["D5"]["node_week_row"] is False and delegations["D5"]["not_in_week_start_risk_set"] is True
    assert delegations["D3"]["node_week_row"] is True and delegations["D3"]["not_in_week_start_risk_set"] is True, "B was not active at the 09-28 cutoff"
    assert str(delegations["D1"]["week_start_utc"])[:10] == "2020-09-21"
    assert delegations["D1"]["gross_rate"] == annualized_reward_rate(datetime(2020, 9, 21, tzinfo=UTC), 22 * 86_400, 25 * NAVAX, 400_000_000 * NAVAX)
    d4 = delegations["D4"]
    assert d4["validator_fee_rate"] == 0.10 and d4["supply_counter_avax"] == 400_000_000
    assert d4["gross_rate"] == annualized_reward_rate(datetime(2020, 9, 28, tzinfo=UTC), 50 * 86_400, 25 * NAVAX, 400_000_000 * NAVAX)
    assert d4["log_net_apy"] == pytest.approx(__import__("math").log(d4["gross_rate"] * 0.9))


def test_early_rows_do_not_read_later_events(runs):
    result = weeks.invariance(paths_of(runs), "2020-10-12")
    assert result["equal"] and result["rows"] > 0


def test_a_leak_would_be_caught(runs, monkeypatch):
    """Counting every period in completed_periods, not only those accepted before the cutoff, must break the check."""
    leaky = weeks.PANEL_SQL.replace("FROM keys k LEFT JOIN v ON v.node_id = k.node_id AND v.accepted_at < k.week_start_utc",
                                    "FROM keys k LEFT JOIN v ON v.node_id = k.node_id")
    assert leaky != weeks.PANEL_SQL
    monkeypatch.setattr(weeks, "PANEL_SQL", leaky)
    assert weeks.invariance(paths_of(runs), "2020-10-12")["equal"] is False


def test_check_passes_and_counts_every_delegation(runs):
    output = built(runs, weeks.WEEKS_ID)["output"]
    result = weeks.check(output / "capture", output / "dataset", root=runs)
    assert result["status"] == "pass", result["findings"]
    assert result["summary"]["delegations"] == 12 and result["summary"]["delegations_without_row"] == 1
    assert result["summary"]["invariance"]["equal"]


def test_exactly_full_validator_has_zero_room(runs):
    """Room is integer nAVAX: the same quantities as AVAX doubles give -1.8e-12 here."""
    stake, delegated = 2_841_235_000_000, 11_364_940_000_000
    assert 5 * stake / 1e9 - stake / 1e9 - delegated / 1e9 < 0
    week = row(built(runs, weeks.WEEKS_ID)["rows"], "F", "2020-10-19")
    assert week["capacity_left_avax"] == 0 and week["capacity_left_avax_14d"] == 0 and week["offered_at_week_start"] is False


def test_event_time_eligibility(runs):
    delegations = {item["transaction_hash"]: item for item in built(runs, weeks.DELEGATIONS_ID)["rows"]}
    # D6 ends at the instant D7 starts: half-open intervals, so D7 sees the whole room. F was full at the Monday cutoff.
    d7 = delegations["D7"]
    assert d7["eligible_at_accept"] and d7["ineligibility_reason"] is None and d7["capacity_at_accept_avax"] == pytest.approx(11_364.94)
    assert d7["validator_offered_at_week_start"] is False and d7["not_offered_reason"] == "full_at_cutoff_room_at_accept"
    d8 = delegations["D8"]
    assert d8["eligible_at_accept"] and d8["not_offered_reason"] == "full_at_cutoff_room_at_accept", "D7 ends before D8 starts"
    # D9 starts on an empty validator, but the pending D8 starts inside its interval.
    d9 = delegations["D9"]
    assert d9["capacity_at_accept_avax"] == pytest.approx(11_364.94 - 25) and d9["eligible_at_accept"] is False
    assert d9["ineligibility_reason"] == "over_weight_before_ap3" and d9["not_offered_reason"] == "full_at_cutoff_no_room_at_accept"
    d10 = delegations["D10"]
    assert d10["capacity_at_accept_avax"] == pytest.approx(10) and d10["ineligibility_reason"] == "over_3m_cap_before_ap3"
    d11 = delegations["D11"]
    assert d11["capacity_at_accept_avax"] == 2_000_000 and d11["ineligibility_reason"] == "over_capacity"
    assert d11["validator_offered_at_week_start"] and d11["not_offered_reason"] is None
    assert delegations["D12"]["ineligibility_reason"] == "outside_validator_period"
    # D4 is accepted after D3 but D3 is active at D4's start: 1,999,000 of B's 2,000,000 room is taken.
    assert delegations["D4"]["capacity_at_accept_avax"] == pytest.approx(1_000) and delegations["D4"]["eligible_at_accept"]
    assert delegations["D5"]["not_offered_reason"] == "no_node_week_row"
    assert delegations["D3"]["not_offered_reason"] == "validator_not_active_at_cutoff"


def test_every_delegation_has_one_reason_and_the_reasons_sum_to_the_total(runs):
    output = built(runs, weeks.DELEGATIONS_ID)["output"]
    result = weeks.check(output / "capture", output / "dataset", root=runs)
    assert result["status"] == "pass", result["findings"]
    assert "every delegation classified" in result["checked"]
    reasons = result["summary"]["reasons"]
    for counts in reasons.values():
        assert sum(counts.values()) == result["summary"]["delegations"] == 12
    assert reasons["not_offered_reason"]["unclassified"] == 0
    assert reasons["not_offered_reason"]["offered"] == result["summary"]["delegations"] - result["summary"]["delegations_not_in_week_start_risk_set"]
    assert reasons["ineligibility_reason"] == {"eligible": 8, "no_validator_period": 0, "outside_validator_period": 1,
                                               "over_3m_cap_before_ap3": 1, "over_weight_before_ap3": 1, "over_capacity": 1}


def test_a_broken_classification_is_a_finding(runs, monkeypatch):
    """Dropping a reason must make the check report unclassified delegations."""
    broken = weeks.PANEL_SQL.replace("THEN 'no_node_week_row'", "THEN 'unclassified'")
    assert broken != weeks.PANEL_SQL
    monkeypatch.setattr(weeks, "PANEL_SQL", broken)
    output = built(runs, weeks.DELEGATIONS_ID)["output"]
    result = weeks.check(output / "capture", output / "dataset", root=runs)
    assert result["status"] == "attention" and "1 delegations unclassified" in result["findings"]


def test_receipt_rows_count_the_table_built(market_runs):
    for dataset_id, expected in ((weeks.WEEKS_ID, None), (weeks.DELEGATIONS_ID, 12), (weeks.MARKET_ID, 313)):
        result = built(market_runs, dataset_id)
        summary = __import__("json").loads((result["output"] / "dataset" / "build.json").read_text())["summary"]
        assert summary["rows"] == summary["distinct_keys"] == len(result["rows"]) == (expected or len(result["rows"]))
