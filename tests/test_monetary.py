"""The monetary ledger is derived from small synthetic runs of every input, not from network access."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from avalanche_research import monetary
from avalanche_research.catalog import DataError, canonical_bytes, contract_hash, load_catalog, sha256

NAVAX = 10**9
WEI = 10**18
BIG = f"{NAVAX}::BIGINT"
CATALOG = load_catalog()


def make_run(root: Path, name: str, dataset_id: str, table: str, sql: str, captured_at: str, capture_extra: dict | None = None) -> None:
    capture_dir, dataset_dir = root / name / "capture", root / name / "dataset"
    capture_dir.mkdir(parents=True), dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / f"{table}.parquet"
    connection = duckdb.connect()
    try:
        connection.execute(f"COPY ({sql}) TO '{parquet}' (FORMAT PARQUET)")
        rows = connection.execute(f"SELECT COUNT(*) FROM ({sql})").fetchone()[0]
    finally:
        connection.close()
    capture_id = f"capture:test:{captured_at}:{name}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({
        "schema_version": "test-capture/v1", "capture_id": capture_id, "dataset_id": dataset_id, "completed_at": captured_at,
        "contract_sha256": contract_hash(CATALOG, dataset_id), **(capture_extra or {}),
    }))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({
        "schema_version": "test-build/v1", "dataset_id": dataset_id, "source_capture_id": capture_id, "completed_at": captured_at,
        "summary": {"rows": rows}, "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}],
    }))


def window(start: str, end: str) -> dict:
    return {"queries": [{"parameters": {"start": start, "end": end}}]}


# Five days from genesis: 2020-09-10 to 2020-09-14 with the C-Chain "first block" moved into the window by the fixture below.
DAYS = ["2020-09-10", "2020-09-11", "2020-09-12", "2020-09-13", "2020-09-14"]


@pytest.fixture
def root(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(monetary, "C_CHAIN_FIRST_DATE", monetary.date(2020, 9, 12))
    runs = tmp_path / "runs"
    # P and X daily: day 3 (09-12) carries one unresolved P hash 'u1'; every other day is recorded.
    burn_rows = []
    for day in DAYS:
        unresolved = "u1" if day == "2020-09-12" else None
        burn_rows.append(f"(DATE '{day}', 'P', 10, 1000, 8, 1, 0, 0, {1 if unresolved else 0}, {repr(unresolved) if unresolved else 'NULL'}::VARCHAR, 0, {500 if day >= '2020-09-13' else 0})")
        burn_rows.append(f"(DATE '{day}', 'X', 3, 300, 3, 0, 0, 0, 0, NULL::VARCHAR, 0, 0)")
    make_run(runs, "burn-daily", "snowflake.primary-burn-daily", "primary-burn-daily",
             f"SELECT * FROM (VALUES {', '.join(burn_rows)}) AS t(date_utc, chain, transactions, burned_navax, recorded_transactions, system_transactions, genesis_transactions, utxo_derived_transactions, unresolved_transactions, unresolved_hashes, l1_balance_deposited_navax, l1_validator_fees_navax)",
             "2026-09-23T18:00:00Z", window("2020-09-10", "2020-09-15"))
    make_run(runs, "p-transactions", "p-chain-rpc.transactions", "transactions",
             "SELECT 'u1' AS transaction_hash, 'ImportTx' AS tx_kind, 1000000 AS input_navax, 995865 AS output_navax, 4135 AS burned_navax, 1 AS input_count, 1 AS output_count",
             "2026-09-23T18:05:00Z")
    make_run(runs, "rewards", "snowflake.primary-staking-rewards", "primary-staking-rewards",
             f"SELECT * FROM (VALUES ('r1', TIMESTAMP '2020-09-11 05:00:00', 1, 's1', 'AddValidatorTx', 'NodeID-1', TIMESTAMP '2020-09-10 00:00:00', TIMESTAMP '2020-09-11 00:00:00', TRUE, 50 * {BIG}, 50.0, 50 * {BIG}, 50.0, 0, 0.0, 1), ('r2', TIMESTAMP '2020-09-13 23:00:00', 2, 's2', 'AddDelegatorTx', 'NodeID-1', TIMESTAMP '2020-09-10 00:00:00', TIMESTAMP '2020-09-13 00:00:00', TRUE, 20 * {BIG}, 20.0, 19 * {BIG}, 19.0, -{BIG}, -1.0, 1)) AS t(reward_transaction_hash, rewarded_at, block_height, staking_transaction_hash, staking_tx_type, node_id, period_start_time, period_end_time, rewarded, potential_reward_navax, potential_reward_avax, realized_reward_navax, realized_reward_avax, fee_transfer_navax, fee_transfer_avax, reward_utxo_count)",
             "2026-09-23T18:10:00Z", window("2020-09-10", "2026-09-24"))
    periods = f"SELECT * FROM (VALUES ('s1', 'validator', TIMESTAMP '2020-09-10 00:00:00', TIMESTAMP '2020-09-10 00:00:00', TIMESTAMP '2020-09-13 12:00:00', 2000 * {BIG}, 50 * {BIG}, TIMESTAMP '2020-09-11 05:00:00'), ('s2', 'delegator', TIMESTAMP '2020-09-10 00:00:00', TIMESTAMP '2020-09-11 00:00:00', TIMESTAMP '2020-09-20 00:00:00', 25 * {BIG}, 20 * {BIG}, TIMESTAMP '2020-09-13 23:00:00'), ('s3', 'validator', TIMESTAMP '2020-09-12 00:00:00', TIMESTAMP '2020-09-12 00:00:00', TIMESTAMP '2021-09-12 00:00:00', 3000 * {BIG}, 100 * {BIG}, NULL::TIMESTAMP)) AS t(transaction_hash, role, accepted_at, start_time, end_time, stake_navax, potential_reward_navax, rewarded_at)"
    make_run(runs, "periods", "derived.staking-periods", "staking-periods", periods, "2026-09-23T18:12:00Z",
             {"inputs": [{"input_id": "validator-stakes", "captured_at": "2026-09-23T08:00:00Z"}, {"input_id": "delegator-stakes", "captured_at": "2026-09-23T08:30:00Z"}]})
    make_run(runs, "staking-supply", "snowflake.primary-staking-supply", "primary-staking-supply",
             f"SELECT 's3' AS transaction_hash, TIMESTAMP '2020-09-12 00:00:00' AS accepted_at, 'AddValidatorTx' AS tx_type, 5 AS block_height, 0 AS tx_block_position, 360000050 * {BIG} AS previous_block_supply_navax, (360000050 + 20 + 100) * {BIG} AS block_supply_navax, 0 AS in_block_prior_delta_navax, 120 * {BIG} AS in_block_total_delta_navax, 360000050 * {BIG} AS supply_before_navax",
             "2026-09-23T18:13:00Z", window("2020-09-10", "2026-09-24"))
    # C EVM daily: 09-12 complete, 09-13 has one absent block (height 7) and is repaired below, 09-14 has a short block (height 12) with no fee record.
    evm = f"""SELECT * FROM (VALUES
        (DATE '2020-09-12', 4 * {WEI}::DECIMAL(38,0), 5, 1, 5, 0, 0, 0, NULL::BIGINT, 6, 9, 9, 9, 0, 1599868800, 1599955199),
        (DATE '2020-09-13', 3 * {WEI}::DECIMAL(38,0), 4, 6, 10, 1, 0, 0, 5, 11, 8, 8, 8, 0, 1599955200, 1600041599),
        (DATE '2020-09-14', 2 * {WEI}::DECIMAL(38,0), 3, 11, 13, 0, 1, 4, 10, 14, 10, 10, 6, 0, 1600041600, 1600127999)
    ) AS t(date_utc, burned_wei, block_count, first_block, last_block, absent_blocks, short_blocks, short_block_transactions, previous_last_block, next_first_block, expected_receipts, receipt_rows, distinct_receipts, missing_fee_inputs, first_epoch, last_epoch)"""
    make_run(runs, "c-evm", "snowflake.c-chain-evm-burn-daily", "c-chain-evm-burn-daily", evm, "2026-09-23T18:20:00Z", window("2020-09-12", "2020-09-15"))
    make_run(runs, "c-gaps", "snowflake.c-chain-block-gaps", "c-chain-block-gaps",
             "SELECT * FROM (VALUES (7, 'absent', DATE '2020-09-13', NULL::BIGINT, NULL::BIGINT), (12, 'short', DATE '2020-09-14', 4, 2)) AS t(block_height, kind, date_utc, declared_transactions, distinct_receipts)",
             "2026-09-23T18:21:00Z", window("2020-09-12", "2020-09-15"))
    make_run(runs, "c-fees", "data-api.c-chain-block-fees", "c-chain-block-fees",
             f"SELECT 7 AS block_height, '0x7' AS block_hash, TIMESTAMP '2020-09-13 12:00:00' AS block_timestamp, DATE '2020-09-13' AS date_utc, 3 AS transactions, 63000 AS gas_used, 25000000000::DECIMAL(38,0) AS base_fee_wei, ({WEI} / 2)::DECIMAL(38,0) AS fees_wei",
             "2026-09-23T18:22:00Z")
    # The node's receipts give block 7 the same fee as the Data API record: the two sources share one block and agree.
    make_run(runs, "c-receipt-fees", "c-chain-rpc.block-receipt-fees", "c-chain-block-receipt-fees",
             f"SELECT 7 AS block_height, '0x7' AS block_hash, TIMESTAMP '2020-09-13 12:00:00' AS block_timestamp, DATE '2020-09-13' AS date_utc, 3 AS transactions, 63000 AS gas_used, 25000000000::DECIMAL(38,0) AS base_fee_wei, ({WEI} / 2)::DECIMAL(38,0) AS fees_wei",
             "2026-09-23T18:22:30Z")
    # Atomic: 'a1' burns one AVAX; 'a2' is an import the API lists with no consumed UTXOs, unsettled, and the node settles it at zero.
    make_run(runs, "c-atomic", "data-api.c-chain-atomic-burn", "c-chain-atomic-burn",
             f"SELECT 'a1' AS transaction_hash, 'ImportTx' AS tx_type, TIMESTAMP '2020-09-13 01:00:00' AS accepted_at, 6 AS block_height, '0x6' AS block_hash, 2 * {BIG} AS unlocked_navax, {BIG} AS created_navax, {BIG} AS burned_navax"
             f" UNION ALL SELECT 'a2', 'ImportTx', TIMESTAMP '2020-09-13 02:00:00', 6, '0x6', 0, {BIG} // 2, NULL::BIGINT",
             "2026-09-23T18:23:00Z", {"start_timestamp": 1599868800, "end_timestamp": 1600128000})
    make_run(runs, "c-atomic-transactions", "c-chain-rpc.atomic-transactions", "atomic-transactions",
             f"SELECT 'a2' AS transaction_hash, 'ImportTx' AS tx_kind, 6 AS block_height, {BIG} // 2 AS input_navax, {BIG} // 2 AS output_navax, 0 AS burned_navax, 1 AS input_count, 1 AS output_count",
             "2026-09-23T18:23:30Z")
    make_run(runs, "supply-2020-09-14", "data-api.avax-supply", "avax-supply",
             "SELECT TIMESTAMP '2020-09-14 12:00:00' AS observed_at, 360000067.5 AS total_supply_avax, 0.0 AS circulating_supply_avax, 0.0 AS total_staked_avax, 0.0 AS total_locked_avax, 69.0 AS total_rewards_avax, 0.000006 AS total_p_burned_avax, 0.0000012 AS total_x_burned_avax, 8.5 AS total_c_burned_avax, 0.0 AS l1_validator_fees_avax, 360000000.0 AS genesis_unlock_avax, 0.0 AS supply_identity_gap_avax",
             "2026-09-23T18:24:00Z")
    return runs


def test_catalog_declares_the_ledger():
    definition = next(item for item in CATALOG["datasets"] if item["id"] == monetary.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(monetary.TABLE_COLUMNS)
    assert definition["input_ids"] == [*monetary.SINGLE_INPUTS, *monetary.MANY_INPUTS]


def test_derive_replays_supply_until_the_first_incomplete_day(root):
    output = root / "ledger"
    result = monetary.derive(monetary.DATASET_ID, output, None, root)
    summary = result["build"]["summary"]
    relation = duckdb.sql(f"SELECT * FROM read_parquet('{output / 'dataset' / 'avax-monetary-daily.parquet'}') ORDER BY date_utc")
    rows = {str(record[0]): dict(zip(relation.columns, record)) for record in relation.fetchall()}
    # 09-10 (genesis): P 1000 nAVAX and X 300 nAVAX burned, nothing issued, C before its first block: complete.
    day = rows["2020-09-10"]
    assert day["complete"] and day["c_evm_coverage"] == "complete" and day["c_atomic_coverage"] == "complete"
    assert int(day["total_supply_close_wei"]) == 360_000_000 * WEI - 1300 * NAVAX
    # 09-11: 50 AVAX rewarded.
    assert int(rows["2020-09-11"]["issued_rewards_wei"]) == 50 * WEI
    # 09-12: the unresolved P import is settled by the node record: 4,135 nAVAX more, coverage repaired.
    day = rows["2020-09-12"]
    assert day["p_coverage"] == "repaired" and int(day["burned_p_transactions_wei"]) == (1000 + 4135) * NAVAX
    assert day["c_evm_coverage"] == "complete" and int(day["burned_c_evm_wei"]) == 4 * WEI and day["complete"]
    # 09-13: the absent block's fee comes from the block record, the atomic import burns one AVAX and the node settles
    # the other at zero, L1 fees start.
    day = rows["2020-09-13"]
    assert day["c_atomic_coverage"] == "repaired" and day["c_evm_coverage"] == "repaired" and int(day["burned_c_evm_gap_wei"]) == WEI // 2 and int(day["burned_c_evm_wei"]) == 3 * WEI + WEI // 2
    assert int(day["burned_c_atomic_wei"]) == WEI and int(day["burned_p_l1_validator_fees_wei"]) == 500 * NAVAX
    assert int(day["issued_rewards_wei"]) == 19 * WEI and day["complete"]
    expected_close = 360_000_000 * WEI + 69 * WEI - (4 * 1300 + 4135 + 500) * NAVAX - (4 * WEI) - (3 * WEI + WEI // 2) - WEI
    assert int(day["total_supply_close_wei"]) == expected_close and int(day["total_supply_open_wei"]) == int(rows["2020-09-12"]["total_supply_close_wei"])
    # 09-14: the short block has no fee record, so the day is incomplete and carries no supply.
    day = rows["2020-09-14"]
    assert day["c_evm_coverage"] == "incomplete" and not day["complete"] and day["total_supply_close_wei"] is None
    assert summary["complete_days"] == 4 and summary["first_incomplete_date"] == "2020-09-14" and summary["supply_through"] == "2020-09-13"
    # Stake at 23:59:59: on 09-12 both validators and the delegator are active; on 09-13 s1 has ended.
    assert (rows["2020-09-12"]["active_validators"], rows["2020-09-13"]["active_validators"], rows["2020-09-12"]["active_delegations"]) == (2, 1, 1)
    assert int(rows["2020-09-12"]["active_validator_stake_wei"]) == 5000 * WEI
    # The checkpoint on 09-14 cannot be bracketed (no supply that day) except by the day before, and the counter reconciles.
    point = summary["checkpoints"][0]
    assert point["rewards"]["within"] is None and point["ledger_complete_through_that_day"] is False
    assert abs(summary["counter"]["gap_avax"]) < 1e-6
    checked = monetary.check(output / "capture", output / "dataset", root=root)
    assert checked["status"] == "pass", checked["findings"]
    assert "daily conservation" in checked["checked"]


def gap_fee_run(root, fee_sql: str, heights: str) -> None:
    import shutil

    shutil.rmtree(root / "c-receipt-fees")
    make_run(root, "c-receipt-fees", "c-chain-rpc.block-receipt-fees", "c-chain-block-receipt-fees",
             f"SELECT block_height, '0x' || block_height AS block_hash, date_utc::TIMESTAMP + INTERVAL 12 HOUR AS block_timestamp, date_utc, 3 AS transactions, 63000 AS gas_used, "
             f"25000000000::DECIMAL(38,0) AS base_fee_wei, ({fee_sql})::DECIMAL(38,0) AS fees_wei FROM (VALUES {heights}) AS t(block_height, date_utc)",
             "2026-09-23T18:22:30Z")


def test_receipt_fees_settle_a_gap_block_and_agree_with_the_data_api(root):
    gap_fee_run(root, f"CASE block_height WHEN 7 THEN {WEI} // 2 ELSE {WEI} // 4 END", "(7, DATE '2020-09-13'), (12, DATE '2020-09-14')")
    output = root / "ledger"
    summary = monetary.derive(monetary.DATASET_ID, output, None, root)["build"]["summary"]
    assert summary["gap_fee_sources"] == {"shared_blocks": 1, "differing_blocks": 0}
    assert summary["supply_through"] == "2020-09-14" and summary["c_evm_incomplete_days"] == 0
    day = duckdb.sql(f"SELECT c_evm_coverage, burned_c_evm_gap_wei FROM read_parquet('{output / 'dataset' / 'avax-monetary-daily.parquet'}') WHERE date_utc = DATE '2020-09-14'").fetchone()
    assert day == ("repaired", WEI // 4)
    checked = monetary.check(output / "capture", output / "dataset", root=root)
    assert not any("gap blocks carry different fees" in finding for finding in checked["findings"]), checked["findings"]


def test_a_gap_block_whose_two_sources_differ_is_reported(root):
    gap_fee_run(root, f"{WEI} // 2 + 1", "(7, DATE '2020-09-13')")
    output = root / "ledger"
    assert monetary.derive(monetary.DATASET_ID, output, None, root)["build"]["summary"]["gap_fee_sources"] == {"shared_blocks": 1, "differing_blocks": 1}
    checked = monetary.check(output / "capture", output / "dataset", root=root)
    assert "1 of 1 gap blocks carry different fees from the Data API and the node's receipts" in checked["findings"]


def test_an_unsettled_import_without_a_node_record_stops_the_supply(root):
    import shutil

    shutil.rmtree(root / "c-atomic-transactions")
    output = root / "ledger"
    result = monetary.derive(monetary.DATASET_ID, output, None, root)
    relation = duckdb.sql(f"SELECT date_utc, c_atomic_coverage, burned_c_atomic_wei FROM read_parquet('{output / 'dataset' / 'avax-monetary-daily.parquet'}') ORDER BY date_utc")
    rows = {str(record[0]): record[1:] for record in relation.fetchall()}
    assert rows["2020-09-13"] == ("incomplete", WEI)
    assert result["build"]["summary"]["supply_through"] == "2020-09-12"


def test_check_reports_a_changed_input_and_a_checkpoint_gap(root):
    output = root / "ledger"
    monetary.derive(monetary.DATASET_ID, output, None, root)
    parquet = root / "c-fees" / "dataset" / "c-chain-block-fees.parquet"
    parquet.write_bytes(parquet.read_bytes() + b"\n")
    checked = monetary.check(output / "capture", output / "dataset", root=root)
    assert checked["status"] == "attention" and any("differs from the capture receipt: c-fees" in finding for finding in checked["findings"])
    build = json.loads((output / "dataset" / "build.json").read_text())
    build["summary"]["checkpoints"][0]["p_burned"] = {"within": False, "gap_avax": 7.5}
    (output / "dataset" / "build.json").write_bytes(canonical_bytes(build))
    findings = monetary.check(output / "capture", output / "dataset", root=root)["findings"]
    assert any("Data API p_burned" in finding and "7.500 AVAX" in finding for finding in findings)


def test_a_stale_many_input_run_is_skipped_and_a_required_one_is_demanded(root):
    stale = json.loads((root / "c-fees" / "capture" / "capture.json").read_text())
    stale["contract_sha256"] = "0" * 64
    (root / "c-fees" / "capture" / "capture.json").write_bytes(canonical_bytes(stale))
    inputs = monetary.select_inputs(None, root, CATALOG)
    assert not any(item["input_id"] == "c-block-fees" for item in inputs)
    broken = json.loads((root / "c-atomic" / "capture" / "capture.json").read_text())
    broken["contract_sha256"] = "0" * 64
    (root / "c-atomic" / "capture" / "capture.json").write_bytes(canonical_bytes(broken))
    with pytest.raises(DataError, match="no built run of data-api.c-chain-atomic-burn"):
        monetary.select_inputs(None, root, CATALOG)
