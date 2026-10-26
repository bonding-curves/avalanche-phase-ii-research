"""The monetary ledger is derived from small synthetic runs of every input, not from network access."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from hashlib import md5
from pathlib import Path
from threading import Barrier

import duckdb
import pytest

from avalanche_research.core.catalog import (
    DataError,
    canonical_bytes,
    contract_hash,
    load_catalog,
    sha256,
)
from avalanche_research.datasets.derived import monetary

NAVAX = 10**9
WEI = 10**18
BIG = f"{NAVAX}::BIGINT"
CATALOG = load_catalog()


def test_overlapping_accounting_connections_spill_independently_and_clean_up(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    barrier = Barrier(2)
    count = 200_000

    def spill(owner):
        with monetary.accounting_connection() as connection:
            scratch = Path(connection.execute("SELECT current_setting('temp_directory')").fetchone()[0])
            assert scratch.is_absolute() and scratch.is_dir()
            assert connection.execute("SELECT current_setting('threads'),current_setting('memory_limit')").fetchone() == (2, '3.7 GiB')
            connection.execute("SET memory_limit='16MB'")
            connection.execute("SET preserve_insertion_order=false")
            connection.execute("CREATE TABLE data AS SELECT i AS id,? AS owner,repeat(md5(? || i::VARCHAR),4) AS payload FROM range(?) t(i)",
                               [owner, owner, count])
            barrier.wait(timeout=30)
            spilled = sum(path.stat().st_size for path in scratch.iterdir() if path.is_file())
            assert spilled > 0  # Both live databases must have actual disk-backed pages, not only configured paths.
            result = connection.execute("SELECT count(*),sum(id),min(owner),max(owner),sum(length(payload)) FROM data").fetchone()
            first = connection.execute("SELECT payload FROM data WHERE id=0").fetchone()[0]
            assert result == (count, count*(count-1)//2, owner, owner, count*128)
            assert first == md5((owner+'0').encode()).hexdigest()*4
            barrier.wait(timeout=30)
        assert not scratch.exists()
        return scratch

    with ThreadPoolExecutor(max_workers=2) as pool:
        paths = list(pool.map(spill, ['first', 'second']))
    assert paths[0] != paths[1]
    assert not (tmp_path / '.tmp').exists()


@pytest.mark.parametrize('failure', ['query', 'consumer', 'connect'])
def test_accounting_scratch_is_removed_on_errors(monkeypatch, failure):
    paths = []
    if failure == 'connect':
        def refuse_connection(*args, **kwargs):
            paths.append(Path(kwargs['config']['temp_directory']))
            assert paths[-1].is_dir()
            raise RuntimeError('connection refused')
        monkeypatch.setattr(monetary.duckdb, 'connect', refuse_connection)
    expected = duckdb.Error if failure == 'query' else RuntimeError
    with pytest.raises(expected), monetary.accounting_connection() as connection:
        paths.append(Path(connection.execute("SELECT current_setting('temp_directory')").fetchone()[0]))
        if failure == 'query':
            connection.execute('SELECT nonexistent_column')
        else:
            raise RuntimeError('consumer failed')
    assert len(paths) == 1 and not paths[0].exists()


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
    periods = f"SELECT * FROM (VALUES ('s1', 'validator', TIMESTAMP '2020-09-10 00:00:00', TIMESTAMP '2020-09-10 00:00:00', TIMESTAMP '2020-09-13 12:00:00', 2000 * {BIG}, 50 * {BIG}, TIMESTAMP '2020-09-11 05:00:00', NULL, TRUE, 'genesis', 0, NULL::TIMESTAMP), ('s2', 'delegator', TIMESTAMP '2020-09-10 00:00:00', TIMESTAMP '2020-09-11 00:00:00', TIMESTAMP '2020-09-20 00:00:00', 25 * {BIG}, 20 * {BIG}, TIMESTAMP '2020-09-13 23:00:00', 's1', TRUE, 'genesis', -{BIG}, NULL::TIMESTAMP), ('s3', 'validator', TIMESTAMP '2020-09-12 00:00:00', TIMESTAMP '2020-09-12 00:00:00', TIMESTAMP '2021-09-12 00:00:00', 3000 * {BIG}, 100 * {BIG}, NULL::TIMESTAMP, NULL, NULL, 'genesis', 0, NULL::TIMESTAMP)) AS t(transaction_hash, role, accepted_at, start_time, end_time, stake_navax, potential_reward_navax, rewarded_at, validator_transaction_hash, rewarded, regime, fee_transfer_navax, last_cycle_end_time)"
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
    assert set(definition["input_ids"]) == {
        *monetary.SINGLE_INPUTS, *monetary.MANY_INPUTS, *monetary.CYCLE_INPUTS,
        "seamed-burn-daily", "seamed-staking-rewards", "seamed-staking-supply", "seamed-c-evm-daily",
    }


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
    # The check judges from the stored values, not a stored verdict: 8 AVAX above the bracket is 6 beyond the 2 AVAX allowance.
    build["summary"]["checkpoints"][0]["p_burned"] = {"api_avax": 100.0, "ledger_before_avax": 90.0, "ledger_after_avax": 92.0,
                                                      "gap_avax": 0.0, "within": True}
    (output / "dataset" / "build.json").write_bytes(canonical_bytes(build))
    findings = monetary.check(output / "capture", output / "dataset", root=root)["findings"]
    assert any("Data API p_burned" in finding and "6.000 AVAX beyond the 2.000 AVAX allowance" in finding for finding in findings)


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


def test_the_api_c_burn_is_bracketed_by_evm_fees_only(root, monkeypatch):
    """The Data API's totalCBurned leaves out import and export burns, so the bracket is the ledger's EVM burns."""
    monkeypatch.setattr(monetary, "CHECKPOINT_TOLERANCE_AVAX", 0.01)
    make_run(root, "supply-2020-09-13", "data-api.avax-supply", "avax-supply",
             "SELECT TIMESTAMP '2020-09-13 12:00:00' AS observed_at, 360000000.0 AS total_supply_avax, 0.0 AS circulating_supply_avax, 0.0 AS total_staked_avax, 0.0 AS total_locked_avax, 69.0 AS total_rewards_avax, 0.0 AS total_p_burned_avax, 0.0 AS total_x_burned_avax, 7.2 AS total_c_burned_avax, 0.0 AS l1_validator_fees_avax, 360000000.0 AS genesis_unlock_avax, 0.0 AS supply_identity_gap_avax",
             "2026-09-23T18:25:00Z")
    summary = monetary.derive(monetary.DATASET_ID, root / "ledger", None, root)["build"]["summary"]
    point = next(item for item in summary["checkpoints"] if item["observed_at"].startswith("2020-09-13"))
    # EVM fees: 4 AVAX through 09-12, 7.5 through 09-13. The 1 AVAX atomic burn of 09-13 is not in the bracket.
    assert (point["c_burned"]["ledger_before_avax"], point["c_burned"]["ledger_after_avax"], point["c_burned"]["within"]) == (4.0, 7.5, True)


def test_checkpoint_allowances_hold_the_observed_differences_and_fail_a_deficit_beyond_them():
    """C-Chain at 5.09M AVAX allows 0.01%, about 509 AVAX. P-Chain allows 2 AVAX. Other totals keep the 1 AVAX allowance.
    Each deficit here moves the API value against fixed ledger endpoints."""
    def judged(name, api, before, after):
        return monetary.judge_checkpoint(name, {"api_avax": api, "ledger_before_avax": before, "ledger_after_avax": after})

    c_before = 5_090_458.5
    assert judged("c_burned", c_before - 252, c_before, c_before + 1_650)["within"]
    missing_day = judged("c_burned", c_before - 694, c_before, c_before + 1_650)
    assert not missing_day["within"] and missing_day["allowance_avax"] == pytest.approx(509.0458, abs=1e-3)
    assert judged("p_burned", 19_160.0 - 1.34, 19_160.0, 19_185.5)["within"]
    assert not judged("p_burned", 19_160.0 - 25.5, 19_160.0, 19_185.5)["within"]
    assert not judged("x_burned", 45_000.0 - 1.34, 45_000.0, 45_010.0)["within"]
    assert judged("x_burned", 45_000.0, None, None)["within"] is None


def test_a_missing_earlier_ledger_day_shows_only_when_it_exceeds_the_day_and_the_allowance():
    """An omitted earlier day lowers both ledger endpoints. With true cumulative B, omission D, the day's burns T and the
    API ahead of the day's start by r, the API sits D + r - T above the upper endpoint: caught only beyond the allowance."""
    true_before, r = 5_090_458.5, 150.0

    def omitted(d, t):
        before = true_before - d
        return monetary.judge_checkpoint("c_burned", {"api_avax": true_before + r, "ledger_before_avax": before,
                                                      "ledger_after_avax": before + t})

    assert omitted(693.6, 1_650.0)["within"]  # a typical missing day passes the bracket: coverage checks must catch it
    caught = omitted(2_500.0, 1_000.0)
    assert not caught["within"] and caught["gap_avax"] == pytest.approx(2_500.0 + r - 1_000.0 - caught["allowance_avax"])


def test_the_check_returns_the_verdicts_it_judged_in_both_directions(root):
    output = root / "ledger"
    monetary.derive(monetary.DATASET_ID, output, None, root)
    build = json.loads((output / "dataset" / "build.json").read_text())
    stale_fail = {"api_avax": 91.0, "ledger_before_avax": 90.0, "ledger_after_avax": 92.0, "gap_avax": 99.0, "within": False}
    stale_pass = {"api_avax": 100.0, "ledger_before_avax": 90.0, "ledger_after_avax": 92.0, "gap_avax": 0.0, "within": True}
    build["summary"]["checkpoints"][0]["p_burned"], build["summary"]["checkpoints"][0]["x_burned"] = stale_fail, stale_pass
    (output / "dataset" / "build.json").write_bytes(canonical_bytes(build))
    checked = monetary.check(output / "capture", output / "dataset", root=root)
    point = checked["summary"]["checkpoints"][0]
    assert point["p_burned"]["within"] is True and point["p_burned"]["gap_avax"] == 0.0
    assert point["x_burned"]["within"] is False and point["x_burned"]["gap_avax"] == pytest.approx(7.0)
    assert not any("p_burned" in finding for finding in checked["findings"])
    assert any("x_burned" in finding and "7.000 AVAX beyond the 1.000 AVAX allowance" in finding for finding in checked["findings"])


def reconciliation_tables() -> duckdb.DuckDBPyConnection:
    """One paid validator, a delegation to a running post-Cortina validator, and one to a pre-Cortina validator."""
    connection = duckdb.connect()
    connection.execute(f"""CREATE TABLE staking_rewards AS SELECT * FROM (VALUES (TIMESTAMP '2026-01-05 00:00:00', 40 * {BIG}), (TIMESTAMP '2026-01-06 00:00:00', 18 * {BIG}),
        (TIMESTAMP '2026-01-07 00:00:00', 9 * {BIG})) AS t(rewarded_at, realized_reward_navax)""")
    connection.execute(f"""CREATE TABLE staking_periods AS SELECT * FROM (VALUES
        ('v1', 'validator', NULL, TIMESTAMP '2026-01-01', TIMESTAMP '2026-01-01', TIMESTAMP '2026-01-05', 40 * {BIG}, TIMESTAMP '2026-01-05', TRUE, 'durango', 0),
        ('v2', 'validator', NULL, TIMESTAMP '2026-01-01', TIMESTAMP '2026-01-01', TIMESTAMP '2026-01-11', 100 * {BIG}, NULL::TIMESTAMP, NULL, 'durango', 0),
        ('d1', 'delegator', 'v2', TIMESTAMP '2026-01-02', TIMESTAMP '2026-01-02', TIMESTAMP '2026-01-06', 20 * {BIG}, TIMESTAMP '2026-01-06', TRUE, 'durango', -2 * {BIG}),
        ('v3', 'validator', NULL, TIMESTAMP '2022-01-01', TIMESTAMP '2022-01-01', TIMESTAMP '2027-01-01', 0, NULL::TIMESTAMP, NULL, 'banff', 0),
        ('d2', 'delegator', 'v3', TIMESTAMP '2026-01-02', TIMESTAMP '2026-01-02', TIMESTAMP '2026-01-06', 10 * {BIG}, TIMESTAMP '2026-01-06', TRUE, 'banff', -{BIG}))
        AS t(transaction_hash, role, validator_transaction_hash, accepted_at, start_time, end_time, potential_reward_navax, rewarded_at, rewarded, regime, fee_transfer_navax)""")
    return connection


def test_the_api_rewards_reconcile_as_paid_plus_held_fees_plus_earned_open_shares():
    connection = reconciliation_tables()
    at = monetary.datetime(2026, 1, 6, 12)
    # Paid by then: 40 + 18. Held: d1's 2 AVAX fee waits for v2, which runs to 01-11; banff's d2 was paid in full. Earned: v2 at 5.5 of 10 days.
    result = monetary.rewards_reconciliation(connection, at, 115.0)
    assert (result["paid_avax"], result["held_fees_avax"], result["earned_open_avax"]) == pytest.approx((58.0, 2.0, 55.0))
    assert result["covered"] and result["within"] is True and result["gap_avax"] == 0.0
    assert monetary.rewards_reconciliation(connection, at, 116.0)["within"] is False
    # After the last paid reward the inputs do not cover the instant, so nothing is compared.
    late = monetary.rewards_reconciliation(connection, monetary.datetime(2026, 1, 8), 1.0)
    assert late["covered"] is False and late["within"] is None


def test_check_reports_a_rewards_snapshot_that_stops_reconciling(root):
    make_run(root, "supply-2020-09-11", "data-api.avax-supply", "avax-supply",
             "SELECT TIMESTAMP '2020-09-11 12:00:00' AS observed_at, 360000000.0 AS total_supply_avax, 0.0 AS circulating_supply_avax, 0.0 AS total_staked_avax, 0.0 AS total_locked_avax, 60.0 AS total_rewards_avax, 0.0 AS total_p_burned_avax, 0.0 AS total_x_burned_avax, 0.0 AS total_c_burned_avax, 0.0 AS l1_validator_fees_avax, 360000000.0 AS genesis_unlock_avax, 0.0 AS supply_identity_gap_avax",
             "2026-09-23T18:25:00Z")
    output = root / "ledger"
    summary = monetary.derive(monetary.DATASET_ID, output, None, root)["build"]["summary"]
    point = next(item for item in summary["checkpoints"] if item["observed_at"].startswith("2020-09-11"))
    # Paid 50 by 05:00, and s2 has earned half a day of its nine: 20 / 18.
    assert point["rewards_reconciliation"]["model_avax"] == pytest.approx(50 + 20 / 18)
    findings = monetary.check(output / "capture", output / "dataset", root=root)["findings"]
    assert [finding for finding in findings if "rewards" in finding or "total_supply" in finding] == [
        "Data API rewards at 2020-09-11T12:00:00 differ from rewards paid plus held fees plus earned open shares by 9 AVAX (14.8148%), beyond 0.02%"]


def test_a_gap_after_the_api_drift_began_is_reported_not_a_finding(root):
    make_run(root, "supply-2020-09-11", "data-api.avax-supply", "avax-supply",
             "SELECT TIMESTAMP '2020-09-11 12:00:00' AS observed_at, 360000000.0 AS total_supply_avax, 0.0 AS circulating_supply_avax, 0.0 AS total_staked_avax, 0.0 AS total_locked_avax, 60.0 AS total_rewards_avax, 0.0 AS total_p_burned_avax, 0.0 AS total_x_burned_avax, 0.0 AS total_c_burned_avax, 0.0 AS l1_validator_fees_avax, 360000000.0 AS genesis_unlock_avax, 0.0 AS supply_identity_gap_avax",
             "2026-09-23T18:25:00Z")
    output = root / "ledger"
    monetary.derive(monetary.DATASET_ID, output, None, root)
    build = json.loads((output / "dataset" / "build.json").read_text())
    point = next(item for item in build["summary"]["checkpoints"] if item["observed_at"].startswith("2020-09-11"))
    point["observed_at"] = "2026-09-29T11:00:16"
    (output / "dataset" / "build.json").write_bytes(canonical_bytes(build))
    checked = monetary.check(output / "capture", output / "dataset", root=root)
    assert not [finding for finding in checked["findings"] if "rewards" in finding]
    assert checked["summary"]["reported"] == [
        "Data API rewards at 2026-09-29T11:00:16 differ from the reconciliation by 9 AVAX (14.8148%); reported, not a finding, from 2026-09-20"]


def test_original_weight_extent_without_cycle_support_is_not_accepted(root):
    # From Helicon one AddAutoRenewedValidatorTx keeps one period row: end_time closes its first cycle, and
    # last_cycle_end_time the latest. A validator whose first cycle ended on 09-12 and whose latest ends on 09-14 is active on 09-13.
    earlier = root / "periods" / "dataset" / "staking-periods.parquet"
    make_run(root, "periods-renewed", "derived.staking-periods", "staking-periods",
             f"SELECT * FROM read_parquet('{earlier}') UNION ALL SELECT 'a1', 'validator', TIMESTAMP '2020-09-10 00:00:00', TIMESTAMP '2020-09-10 00:00:00',"
             f" TIMESTAMP '2020-09-12 12:00:00', 7 * {BIG}, 0, NULL::TIMESTAMP, NULL, NULL, 'genesis', 0, TIMESTAMP '2020-09-14 12:00:00'",
             "2026-09-23T18:12:30Z",
             {"inputs": [{"input_id": "validator-stakes", "captured_at": "2026-09-23T08:00:00Z"}, {"input_id": "delegator-stakes", "captured_at": "2026-09-23T08:30:00Z"}]})
    output = root / "ledger"
    with pytest.raises(DataError, match="complete cycle histories"):
        monetary.derive(monetary.DATASET_ID, output, {"derived.staking-periods": "periods-renewed"}, root)
    assert not output.exists()


def evm_revision(root, name, amount, captured_at="2026-09-23T19:00:00Z", *, seamed=False):
    """A revised complete row, not a maximum-value selection oracle."""
    source = root / "c-evm" / "dataset" / "c-chain-evm-burn-daily.parquet"
    expression = "NULL::DECIMAL(38,0)" if amount is None else f"{amount}::DECIMAL(38,0)"
    sql = (f"SELECT * REPLACE (CASE WHEN date_utc = DATE '2020-09-12' THEN {expression} ELSE burned_wei END AS burned_wei, "
           f"first_epoch + 1 AS first_epoch) FROM read_parquet('{source}')")
    dataset_id = "derived.seamed-c-chain-evm-burn-daily" if seamed else "snowflake.c-chain-evm-burn-daily"
    if seamed:
        sql = f"SELECT *, 'backup' AS source FROM ({sql})"
    make_run(root, name, dataset_id, "c-chain-evm-burn-daily", sql, captured_at,
             {"window": {"start": "2020-09-12", "end": "2020-09-15"}} if seamed else window("2020-09-12", "2020-09-15"))


@pytest.mark.parametrize("amount", [6 * WEI, None])
def test_overlaps_retain_the_whole_newest_row_and_null_state(root, amount):
    evm_revision(root, "c-evm-corrected", amount)
    inputs = monetary.select_inputs(None, root, CATALOG)
    # Input list order cannot decide the winner, and a nullable field cannot come from the older row.
    for supplied in (inputs, list(reversed(inputs))):
        with duckdb.connect() as connection:
            meta = monetary.load_inputs(connection, supplied)
            selected = connection.execute("SELECT burned_wei, first_epoch, run FROM c_evm_daily WHERE date_utc=DATE '2020-09-12'").fetchall()
            assert selected == [(amount, 1599868801, "c-evm-corrected")]
            assert meta["selected_input_rows"]["c-evm-daily"] == [{"run": "c-evm-corrected", "rows": 3}]
    output = root / "ledger"
    result = monetary.derive(monetary.DATASET_ID, output, root=root)
    assert result["capture"]["input_selection_policy"]["version"] == "monetary-whole-row/v1"
    with duckdb.connect() as connection:
        row = connection.execute("SELECT burned_c_evm_wei, c_evm_coverage, complete, total_supply_close_wei FROM read_parquet(?) WHERE date_utc=DATE '2020-09-12'",
                                 [str(output / "dataset" / "avax-monetary-daily.parquet")]).fetchone()
    if amount is None:
        assert row == (None, "incomplete", False, None)
    else:
        assert row[0] == amount and row[1:3] == ("complete", True)


def sparse_evm_inputs(root, *, hole=False, unresolved=False):
    """The daily query emits present block dates only; gap dates are predecessor proxies."""
    source = root / "c-evm/dataset/c-chain-evm-burn-daily.parquet"
    # Last height 5 on the 12th is followed by first height 6 (no blocks on the 13th),
    # or height 8 (the two missing heights are recovered with their actual 13th timestamps).
    next_height = 8 if hole else 6
    make_run(root, "evm-sparse", "snowflake.c-chain-evm-burn-daily", "c-chain-evm-burn-daily",
             f"SELECT * REPLACE (CASE WHEN date_utc=DATE '2020-09-14' THEN {next_height} ELSE first_block END AS first_block, "
             f"CASE WHEN date_utc=DATE '2020-09-14' THEN {next_height+4} ELSE last_block END AS last_block, "
             "5 AS block_count,0 AS absent_blocks,0 AS short_blocks) FROM read_parquet('" + str(source) + "') WHERE date_utc<>DATE '2020-09-13'",
             "2026-09-23T19:00:00Z", window("2020-09-12", "2020-09-15"))
    gap_sql = "SELECT * FROM (VALUES (6,'absent',DATE '2020-09-12',NULL::BIGINT,NULL::BIGINT),(7,'absent',DATE '2020-09-12',NULL::BIGINT,NULL::BIGINT)) t(block_height,kind,date_utc,declared_transactions,distinct_receipts)"
    if not hole:
        gap_sql += " WHERE FALSE"
    make_run(root, "sparse-gaps", "snowflake.c-chain-block-gaps", "c-chain-block-gaps", gap_sql, "2026-09-23T19:01:00Z", window("2020-09-12", "2020-09-15"))
    pins = {"snowflake.c-chain-evm-burn-daily": "evm-sparse", "snowflake.c-chain-block-gaps": "sparse-gaps"}
    if hole:
        fees = root / "c-fees/dataset/c-chain-block-fees.parquet"
        amount = "NULL::DECIMAL(38,0)" if unresolved else f"{2*WEI}::DECIMAL(38,0)"
        make_run(root, "sparse-fees", "data-api.c-chain-block-fees", "c-chain-block-fees",
                 f"SELECT * FROM read_parquet('{fees}') UNION ALL BY NAME SELECT 6 AS block_height,'0x6' AS block_hash, "
                 f"TIMESTAMP '2020-09-13 00:00:00' AS block_timestamp,DATE '2020-09-13' AS date_utc,{amount} AS fees_wei",
                 "2026-09-23T19:02:00Z")
        pins["data-api.c-chain-block-fees"] = "sparse-fees"
    return pins


def test_sparse_daily_query_omits_a_genuine_no_block_day_inside_its_window(root):
    pins = sparse_evm_inputs(root)
    output = root / "ledger"
    monetary.derive(monetary.DATASET_ID, output, pins, root)
    with duckdb.connect() as c:
        row = c.execute("SELECT burned_c_evm_wei,c_evm_coverage,complete,total_supply_close_wei IS NOT NULL FROM read_parquet(?) WHERE date_utc=DATE '2020-09-13'",
                        [str(output / "dataset/avax-monetary-daily.parquet")]).fetchone()
    assert row == (0, "complete", True, True)


def test_gap_fee_with_unknown_actual_date_does_not_settle_its_proxy(root):
    pins = sparse_evm_inputs(root, hole=True)
    source = root / "sparse-fees/dataset/c-chain-block-fees.parquet"
    make_run(root, "fees-without-clock", "data-api.c-chain-block-fees", "c-chain-block-fees",
             "SELECT * REPLACE (CASE WHEN block_height=6 THEN NULL::DATE ELSE date_utc END AS date_utc, "
             "CASE WHEN block_height=6 THEN NULL::TIMESTAMP ELSE block_timestamp END AS block_timestamp) "
             f"FROM read_parquet('{source}')", "2026-09-23T19:03:00Z")
    pins["data-api.c-chain-block-fees"] = "fees-without-clock"
    output = root / "ledger"
    monetary.derive(monetary.DATASET_ID, output, pins, root)
    with duckdb.connect() as c:
        row = c.execute("SELECT c_evm_coverage,complete,total_supply_close_wei IS NULL "
                        "FROM read_parquet(?) WHERE date_utc=DATE '2020-09-12'",
                        [str(output / "dataset/avax-monetary-daily.parquet")]).fetchone()
    assert row == ("incomplete", False, True)


@pytest.mark.parametrize("unresolved", [False, True])
def test_absent_only_next_day_burn_uses_fee_clock_and_proxy_gap_settlement(root, unresolved):
    pins = sparse_evm_inputs(root, hole=True, unresolved=unresolved)
    output = root / "ledger"
    monetary.derive(monetary.DATASET_ID, output, pins, root)
    with duckdb.connect() as c:
        rows = c.execute("SELECT date_utc,burned_c_evm_wei,burned_c_evm_gap_wei,c_evm_coverage,complete,total_supply_close_wei IS NOT NULL FROM read_parquet(?) WHERE date_utc BETWEEN DATE '2020-09-12' AND DATE '2020-09-13' ORDER BY date_utc",
                         [str(output / "dataset/avax-monetary-daily.parquet")]).fetchall()
    assert rows[0][1:4] == (4*WEI, 0, "incomplete" if unresolved else "repaired")
    assert rows[1][1:4] == (WEI//2 if unresolved else 25*WEI//10, WEI//2 if unresolved else 25*WEI//10, "complete")
    # An unresolved proxy height stops the conserved supply at the proxy day, even though the next day's known
    # partial fee amount can be shown. No fee is shifted to that proxy day and no older non-null row is used.
    assert rows[0][4:] == (not unresolved, not unresolved)
    assert rows[1][5] is (not unresolved)


@pytest.mark.parametrize("captured_at", ["2026-09-23T18:20:00Z", "2026-09-23T19:20:00+01:00"])
def test_equal_time_conflict_refuses_until_an_exact_run_is_pinned(root, captured_at):
    evm_revision(root, "c-evm-conflict", 6 * WEI, captured_at)
    with duckdb.connect() as connection, pytest.raises(DataError, match="conflicting equal-priority input rows for c-evm-daily"):
        monetary.load_inputs(connection, monetary.select_inputs(None, root, CATALOG))
    for run, expected in [("c-evm", 4 * WEI), ("c-evm-conflict", 6 * WEI)]:
        inputs = monetary.select_inputs({"snowflake.c-chain-evm-burn-daily": run}, root, CATALOG)
        assert [item["run"] for item in inputs if item["input_id"] == "c-evm-daily"] == [run]
        with duckdb.connect() as connection:
            monetary.load_inputs(connection, inputs)
            assert connection.execute("SELECT burned_wei, run FROM c_evm_daily WHERE date_utc=DATE '2020-09-12'").fetchone() == (expected, run)


def test_identical_capture_time_rows_have_deterministic_run_lineage(root):
    source = root / "c-evm" / "dataset" / "c-chain-evm-burn-daily.parquet"
    make_run(root, "c-evm-z-identical", "snowflake.c-chain-evm-burn-daily", "c-chain-evm-burn-daily",
             f"SELECT * FROM read_parquet('{source}')", "2026-09-23T18:20:00Z", window("2020-09-12", "2020-09-15"))
    with duckdb.connect() as connection:
        monetary.load_inputs(connection, monetary.select_inputs(None, root, CATALOG))
        assert connection.execute("SELECT DISTINCT run FROM c_evm_daily").fetchall() == [("c-evm-z-identical",)]


def test_seamed_authority_and_explicit_archival_pin_are_distinct(root):
    evm_revision(root, "seamed-evm", 8 * WEI, "2026-09-22T18:00:00Z", seamed=True)
    for pins, run, expected in [(None, "seamed-evm", 8 * WEI),
                                ({"snowflake.c-chain-evm-burn-daily": "c-evm"}, "c-evm", 4 * WEI),
                                ({"derived.seamed-c-chain-evm-burn-daily": "seamed-evm"}, "seamed-evm", 8 * WEI)]:
        with duckdb.connect() as connection:
            monetary.load_inputs(connection, monetary.select_inputs(pins, root, CATALOG))
            assert connection.execute("SELECT burned_wei, run FROM c_evm_daily WHERE date_utc=DATE '2020-09-12'").fetchone() == (expected, run)
    capture = root / "c-evm" / "capture" / "capture.json"
    old = json.loads(capture.read_text())
    old["contract_sha256"] = "0" * 64
    capture.write_bytes(canonical_bytes(old))
    selected = monetary.select_inputs({"snowflake.c-chain-evm-burn-daily": "c-evm"}, root, CATALOG)
    assert [item["run"] for item in selected if item["input_id"] == "c-evm-daily"] == ["c-evm"]
    with pytest.raises(DataError, match="pin only one source"):
        monetary.select_inputs({"snowflake.c-chain-evm-burn-daily": "c-evm", "derived.seamed-c-chain-evm-burn-daily": "seamed-evm"}, root, CATALOG)


def test_equal_time_seamed_conflict_cannot_hide_in_latest_run_lookup(root):
    evm_revision(root, "seamed-a", 8 * WEI, seamed=True)
    evm_revision(root, "seamed-b", 9 * WEI, seamed=True)
    with duckdb.connect() as connection, pytest.raises(DataError, match="conflicting equal-priority input rows"):
        monetary.load_inputs(connection, monetary.select_inputs(None, root, CATALOG))


def test_a_required_family_can_be_supplied_by_seamed_runs_alone(root):
    import shutil

    evm_revision(root, "seamed-only", 8 * WEI, seamed=True)
    shutil.rmtree(root / "c-evm")
    with duckdb.connect() as connection:
        monetary.load_inputs(connection, monetary.select_inputs(None, root, CATALOG))
        assert connection.execute("SELECT DISTINCT run FROM c_evm_daily").fetchall() == [("seamed-only",)]


def test_newer_null_transaction_burn_is_not_a_settled_repair(root):
    source = root / "p-transactions" / "dataset" / "transactions.parquet"
    make_run(root, "p-transactions-new", "p-chain-rpc.transactions", "transactions",
             f"SELECT * REPLACE (NULL::BIGINT AS burned_navax) FROM read_parquet('{source}')", "2026-09-23T19:00:00Z")
    output = root / "ledger"
    monetary.derive(monetary.DATASET_ID, output, root=root)
    with duckdb.connect() as connection:
        row = connection.execute("SELECT p_coverage,complete,total_supply_close_wei FROM read_parquet(?) WHERE date_utc=DATE '2020-09-12'",
                                 [str(output / "dataset" / "avax-monetary-daily.parquet")]).fetchone()
    assert row == ("incomplete", False, None)


@pytest.mark.parametrize("column", ["burned_c_evm_wei", "burned_p_l1_validator_fees_wei", "burned_c_evm_gap_wei"])
def test_component_mutations_fail_even_when_total_burn_is_unchanged(root, column):
    output = root / "ledger"
    monetary.derive(monetary.DATASET_ID, output, root=root)
    parquet = output / "dataset" / "avax-monetary-daily.parquet"
    with duckdb.connect() as connection:
        connection.execute(f"CREATE TABLE changed AS SELECT * REPLACE ({column} + {WEI}::DECIMAL(38,0) AS {column}) FROM read_parquet(?)", [str(parquet)])
        connection.execute("COPY changed TO ? (FORMAT PARQUET)", [str(parquet)])
    build_path = output / "dataset" / "build.json"
    build = json.loads(build_path.read_text())
    body = parquet.read_bytes()
    build["outputs"][0].update(bytes=len(body), sha256=sha256(body))
    build_path.write_bytes(canonical_bytes(build))
    checked = monetary.check(output / "capture", output / "dataset", root=root)
    assert checked["status"] == "attention"
    assert any("burn component" in finding or "burn subcomponents" in finding or "gap burn" in finding for finding in checked["findings"])


def run_reference(root, run, input_id):
    capture = json.loads((root / run / 'capture/capture.json').read_text())
    build = json.loads((root / run / 'dataset/build.json').read_text())
    output = build['outputs'][0]
    return {'input_id': input_id, 'dataset_id': build['dataset_id'], 'run': run,
            'capture_id': capture['capture_id'], 'captured_at': capture['completed_at'],
            'parquet': output['path'], 'bytes': output['bytes'], 'sha256': output['sha256']}


def add_auto_cycles(root, *, passed=True):
    """Two hand-countable cycles. First restakes 6 nAVAX, then terminal current recognition is 24 or 4."""
    from avalanche_research.datasets.derived.pstaking import CYCLE_COLUMNS

    weight = 2000 * NAVAX
    at1, at2 = '2020-09-12 00:00:00', '2020-09-14 00:00:00'
    epoch1 = int(monetary.datetime.fromisoformat(at1).replace(tzinfo=monetary.UTC).timestamp())
    epoch2 = int(monetary.datetime.fromisoformat(at2).replace(tzinfo=monetary.UTC).timestamp())
    unsigned1 = json.dumps({'txID': 'a', 'timestamp': epoch1})
    unsigned2 = json.dumps({'txID': 'a', 'timestamp': epoch2})
    blocksql = f"""SELECT * FROM (VALUES
        (10,'p1','prev',TIMESTAMP '{at1}','proposal','r-auto1','RewardAutoRenewedValidatorTx','{unsigned1}'),
        (11,'o1','p1',TIMESTAMP '{at1}','commit',NULL,NULL,'{{}}'),
        (20,'p2','prev2',TIMESTAMP '{at2}','proposal','r-auto2','RewardAutoRenewedValidatorTx','{unsigned2}'),
        (21,'o2','p2',TIMESTAMP '{at2}','{'commit' if passed else 'abort'}',NULL,NULL,'{{}}')
    ) t(block_height,block_id,parent_id,block_time,block_type,transaction_hash,tx_type,unsigned_tx)"""
    make_run(root, 'cycle-walk', 'p-chain-rpc.blocks', 'blocks', blocksql, '2026-09-23T18:30:00Z')
    cycles = f"""SELECT * FROM (VALUES
        ('a','node-a',1,TIMESTAMP '2020-09-10',TIMESTAMP '{at1}',{weight}::BIGINT,10,500000,172800,'r-auto1',TRUE,2,5,1,5,1),
        ('a','node-a',2,TIMESTAMP '{at1}',TIMESTAMP '{at2}',{weight+6}::BIGINT,20,500000,0,'r-auto2',{'TRUE' if passed else 'FALSE'},4,0,0,{20 if passed else 0},4)
    ) t({','.join(CYCLE_COLUMNS)})"""
    make_run(root, 'cycles', 'derived.p-chain-staking-cycles', 'cycles', cycles, '2026-09-23T18:31:00Z',
             {'inputs': [run_reference(root, 'cycle-walk', 'blocks')]})
    original = root / 'periods/dataset/staking-periods.parquet'
    periods = f"""SELECT *, CASE role WHEN 'validator' THEN 'AddValidatorTx' ELSE 'AddDelegatorTx' END AS tx_type,
                       'old-'||transaction_hash AS node_id,0::BIGINT AS block_height,1 AS cycles FROM read_parquet('{original}')
    UNION ALL BY NAME SELECT 'a' AS transaction_hash,'validator' AS role,'AddAutoRenewedValidatorTx' AS tx_type,'node-a' AS node_id,
      TIMESTAMP '2020-09-10' AS accepted_at,TIMESTAMP '2020-09-10' AS start_time,TIMESTAMP '{at1}' AS end_time,
      {weight}::BIGINT AS stake_navax,10::BIGINT AS potential_reward_navax,TIMESTAMP '{at2}' AS rewarded_at,
      {'TRUE' if passed else 'FALSE'} AS rewarded,'durango' AS regime,0::BIGINT AS block_height,2 AS cycles,TIMESTAMP '{at2}' AS last_cycle_end_time
    UNION ALL BY NAME SELECT 'ad1' AS transaction_hash,'delegator' AS role,'AddDelegatorTx' AS tx_type,'node-a' AS node_id,
      'a' AS validator_transaction_hash,TIMESTAMP '2020-09-10' AS accepted_at,TIMESTAMP '2020-09-10' AS start_time,TIMESTAMP '{at1}' AS end_time,
      {25*NAVAX}::BIGINT AS stake_navax,10::BIGINT AS potential_reward_navax,TIMESTAMP '{at1}' AS rewarded_at,
      TRUE AS rewarded,'durango' AS regime,-2::BIGINT AS fee_transfer_navax,1::BIGINT AS block_height,1 AS cycles
    UNION ALL BY NAME SELECT 'ad2' AS transaction_hash,'delegator' AS role,'AddDelegatorTx' AS tx_type,'node-a' AS node_id,
      'a' AS validator_transaction_hash,TIMESTAMP '{at1}' AS accepted_at,TIMESTAMP '{at1}' AS start_time,TIMESTAMP '{at2}' AS end_time,
      {25*NAVAX}::BIGINT AS stake_navax,20::BIGINT AS potential_reward_navax,TIMESTAMP '{at2}' AS rewarded_at,
      TRUE AS rewarded,'durango' AS regime,-4::BIGINT AS fee_transfer_navax,12::BIGINT AS block_height,1 AS cycles"""
    base_capture = json.loads((root / 'periods/capture/capture.json').read_text())
    make_run(root, 'periods-auto', 'derived.staking-periods', 'staking-periods', periods, '2026-09-23T18:32:00Z',
             {'inputs': base_capture['inputs'] + [run_reference(root, 'cycles', 'p-staking-cycles')]})
    rewards = root / 'rewards/dataset/primary-staking-rewards.parquet'
    reward_sql = f"""SELECT * FROM read_parquet('{rewards}')
    UNION ALL BY NAME SELECT 'd-auto1' AS reward_transaction_hash,'ad1' AS staking_transaction_hash,'AddDelegatorTx' AS staking_tx_type,
      TIMESTAMP '{at1}' AS rewarded_at,9 AS block_height,8::BIGINT AS realized_reward_navax
    UNION ALL BY NAME SELECT 'd-auto2' AS reward_transaction_hash,'ad2' AS staking_transaction_hash,'AddDelegatorTx' AS staking_tx_type,
      TIMESTAMP '{at2}' AS rewarded_at,19 AS block_height,16::BIGINT AS realized_reward_navax
    UNION ALL BY NAME SELECT 'auto-cash' AS reward_transaction_hash,'a' AS staking_transaction_hash,'AddAutoRenewedValidatorTx' AS staking_tx_type,
      TIMESTAMP '{at2}' AS rewarded_at,21 AS block_height,999::BIGINT AS realized_reward_navax"""
    make_run(root, 'rewards-auto', 'snowflake.primary-staking-rewards', 'primary-staking-rewards', reward_sql,
             '2026-09-23T18:33:00Z', window('2020-09-10', '2026-09-24'))
    recognised = 60 if passed else 40
    counter = 360000169 * NAVAX + recognised
    make_run(root, 'supply-auto', 'snowflake.primary-staking-supply', 'primary-staking-supply',
             f"SELECT 'last' AS transaction_hash,TIMESTAMP '{at2}' AS accepted_at,21 AS block_height,{counter}::BIGINT AS block_supply_navax",
             '2026-09-23T18:34:00Z', window('2020-09-10', '2026-09-24'))
    return recognised


@pytest.mark.parametrize('passed', [True, False])
def test_cycle_recognition_stock_and_terminal_release_reach_the_actual_ledger(root, passed):
    recognised = add_auto_cycles(root, passed=passed)
    output = root / 'ledger'
    result = monetary.derive(monetary.DATASET_ID, output, root=root)
    summary = result['build']['summary']['cycle_accounting']
    assert summary['cycle_recognised_navax'] == (36 if passed else 16)
    assert summary['prior_accrual_released_navax'] == 6
    assert summary['excluded_ordinary_auto_payout_rows'] == 1 and summary['excluded_ordinary_auto_payout_navax'] == '999'
    assert result['capture']['reward_accounting_basis'] == monetary.REWARD_ACCOUNTING_BASIS
    assert {'staking-cycles', 'cycle-blocks'} <= {item['input_id'] for item in result['capture']['inputs']}
    with duckdb.connect() as c:
        ledger = str(output / 'dataset/avax-monetary-daily.parquet')
        assert c.execute('SELECT sum(issued_rewards_wei) FROM read_parquet(?)', [ledger]).fetchone()[0] == 69 * WEI + recognised * NAVAX
        assert c.execute("SELECT active_validator_stake_wei,active_validators FROM read_parquet(?) WHERE date_utc=DATE '2020-09-13'", [ledger]).fetchone() == ((5000 * NAVAX + 6) * NAVAX, 2)
        assert c.execute("SELECT active_validators FROM read_parquet(?) WHERE date_utc=DATE '2020-09-14'", [ledger]).fetchone()[0] == 1
        events = str(output / 'dataset' / monetary.CYCLE_EVENTS_FILE)
        assert c.execute('SELECT prior_validation_release_navax,prior_delegatee_release_navax FROM read_parquet(?) WHERE cycle=2', [events]).fetchone() == (5,1)
    assert result['build']['summary']['counter']['gap_avax'] == 0
    checked = monetary.check(output / 'capture', output / 'dataset', root=root)
    assert checked['status'] == 'pass', checked['findings']


@pytest.mark.parametrize('which', ['cycles', 'blocks'])
def test_cycle_dependency_pin_must_match_the_recorded_parent(root, which):
    add_auto_cycles(root)
    dataset_id = 'derived.p-chain-staking-cycles' if which == 'cycles' else 'p-chain-rpc.blocks'
    with pytest.raises(DataError, match="pin differs"):
        monetary.select_inputs({dataset_id: 'unrelated-run'}, root, CATALOG)
    selected = monetary.select_inputs({'derived.p-chain-staking-cycles': 'cycles', 'p-chain-rpc.blocks': 'cycle-walk'}, root, CATALOG)
    assert {x['run'] for x in selected if x['input_id'] in monetary.CYCLE_INPUTS} == {'cycles', 'cycle-walk'}


@pytest.mark.parametrize('source', ['periods-auto', 'cycles'])
def test_referenced_cycle_or_block_hash_cannot_be_replaced_by_latest(root, source):
    add_auto_cycles(root)
    path = root / source / 'capture/capture.json'
    capture = json.loads(path.read_text())
    reference = next(i for i in capture['inputs'] if i['input_id'] == ('p-staking-cycles' if source == 'periods-auto' else 'blocks'))
    reference['sha256'] = '0' * 64
    path.write_bytes(canonical_bytes(capture))
    with pytest.raises(DataError, match="source differs"):
        monetary.derive(monetary.DATASET_ID, root / 'ledger', root=root)
    assert not (root / 'ledger').exists()


def test_rehashed_cycle_companion_corruption_fails_semantic_replay(root):
    add_auto_cycles(root)
    output = root / 'ledger'
    monetary.derive(monetary.DATASET_ID, output, root=root)
    path = output / 'dataset' / monetary.CYCLE_EVENTS_FILE
    with duckdb.connect() as c:
        c.execute('CREATE TABLE changed AS SELECT * REPLACE (recognised_reward_navax+1 AS recognised_reward_navax) FROM read_parquet(?)', [str(path)])
        c.execute('COPY changed TO ? (FORMAT PARQUET)', [str(path)])
    build_path = output / 'dataset/build.json'
    build = json.loads(build_path.read_text())
    record = next(r for r in build['outputs'] if r['path'] == monetary.CYCLE_EVENTS_FILE)
    record.update(bytes=path.stat().st_size, sha256=sha256(path.read_bytes()))
    build_path.write_bytes(canonical_bytes(build))
    checked = monetary.check(output / 'capture', output / 'dataset', root=root)
    assert checked['status'] == 'attention'
    assert 'cycle_events differs from the recorded accounting projection' in checked['findings']


def test_cycle_diagnostics_do_not_recognise_a_proposal_before_its_option(root):
    add_auto_cycles(root)
    with duckdb.connect() as c:
        meta = monetary.load_inputs(c, monetary.select_inputs(None, root, CATALOG))
        monetary.compute(c, meta)
        at = monetary.datetime(2020,9,12)
        proposed = monetary._cycle_diagnostic_amounts(c,at,10)
        committed = monetary._cycle_diagnostic_amounts(c,at,11)
        assert proposed['recognised'] == 50*NAVAX+8 and proposed['held'] == 2
        assert committed['recognised'] == 50*NAVAX+20 and committed['held'] == 0
        assert proposed['pending'] == 120*NAVAX+10
        assert committed['pending'] == 120*NAVAX+20
        # The still-open ordinary delegator has earned one of its nine days (20/9 AVAX).
        reconciled = monetary.rewards_reconciliation(c, at, 50 + 20e-9 + 20/9)
        assert reconciled['basis'] == monetary.REWARD_ACCOUNTING_BASIS
        assert reconciled['paid_avax'] is None
        assert reconciled['held_fees_avax'] == 0
        assert reconciled['recognised_avax'] == (50*NAVAX+20)/NAVAX
        assert reconciled['earned_open_avax'] == pytest.approx(20/9)
        assert reconciled['covered'] and reconciled['within']
