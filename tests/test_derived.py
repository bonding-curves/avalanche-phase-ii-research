from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pytest

from avalanche_research import derived
from avalanche_research.catalog import DataError, canonical_bytes, load_catalog, sha256
from avalanche_research.model.protocol import primary_network_reward


SUPPLY = 450_000_000 * 10**9
NAVAX = 10**9


def reward(start: str, days: int, stake: int) -> int:
    begin = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    return primary_network_reward(begin, days * 86_400, stake, SUPPLY)


# Two validators and two delegators: one pre-Durango pending start, three immediate starts after Durango.
# The pending row's recorded reward is deliberately off by one so the kernel does not reproduce it.
STAKES = [
    # hash, role, tx_type, node, validator_hash, accepted, start, end, stake, potential, rewarded, fee
    ("v1", "validator", "AddValidatorTx", "NodeID-1", None, "2023-01-01 00:00:00", "2023-01-01 00:10:00", "2023-12-31 00:10:00", 2_000 * NAVAX, reward("2023-01-01 00:10:00", 364, 2_000 * NAVAX) + 1, True, 0.02),
    ("v2", "validator", "AddPermissionlessValidatorTx", "NodeID-2", None, "2024-06-01 00:00:00", "2024-06-01 00:00:00", "2025-06-01 00:00:00", 3_000 * NAVAX, reward("2024-06-01 00:00:00", 365, 3_000 * NAVAX), False, 0.05),
    ("d1", "delegator", "AddPermissionlessDelegatorTx", "NodeID-2", "v2", "2024-07-01 00:00:00", "2024-07-01 00:00:00", "2024-10-01 00:00:00", 25 * NAVAX, reward("2024-07-01 00:00:00", 92, 25 * NAVAX), True, None),
    ("d2", "delegator", "AddPermissionlessDelegatorTx", "NodeID-2", "v2", "2026-09-01 00:00:00", "2026-09-01 00:00:00", "2027-01-01 00:00:00", 40 * NAVAX, reward("2026-09-01 00:00:00", 122, 40 * NAVAX), False, None),
]
REWARDS = [
    # staking hash, rewarded_at, realized, fee transfer
    ("v1", "2023-12-31 00:11:00", STAKES[0][9], 0),
    ("v2", "2025-06-01 00:01:00", 0, 0),
    ("d1", "2024-10-01 00:01:00", STAKES[2][9], STAKES[2][9] // 20),
]


def make_run(root: Path, name: str, dataset_id: str, table: str, sql: str, captured_at: str) -> None:
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
        "schema_version": "test-capture/v1", "capture_id": capture_id, "dataset_id": dataset_id, "completed_at": captured_at, "contract_sha256": "0" * 64,
    }))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({
        "schema_version": "test-build/v1", "dataset_id": dataset_id, "source_capture_id": capture_id, "completed_at": captured_at,
        "summary": {"rows": rows}, "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}],
    }))


def values(rows: list[tuple]) -> str:
    def literal(value):
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return repr(value)
        return f"TIMESTAMP '{value}'" if value[:2] == "20" and " " in value else f"'{value}'"
    return ", ".join("(" + ", ".join(literal(v) for v in row) + ")" for row in rows)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    stake_columns = "(transaction_hash, role, tx_type, node_id, validator_transaction_hash, accepted_at, start_time, end_time, stake_navax, potential_reward_navax, rewarded, delegation_fee_rate)"
    base = f"SELECT *, 7 AS block_height, date_diff('second', start_time, end_time) / 86400.0 AS duration_days, stake_navax / 1e9 AS stake_avax, potential_reward_navax / 1e9 AS potential_reward_avax, 1 AS staked_utxo_count, stake_navax AS utxo_stake_navax FROM (VALUES {values(STAKES)}) AS t{stake_columns}"
    make_run(runs, "validators", "snowflake.primary-validator-stakes", "primary-validator-stakes",
             f"SELECT transaction_hash, accepted_at, block_height, tx_type, node_id, start_time, end_time, duration_days, stake_navax, stake_avax, 50 AS delegation_fee_shares, delegation_fee_rate, potential_reward_navax, potential_reward_avax, rewarded, staked_utxo_count, utxo_stake_navax FROM ({base}) WHERE role = 'validator'", "2026-09-19T10:00:00Z")
    make_run(runs, "delegators", "snowflake.primary-delegator-stakes", "primary-delegator-stakes",
             f"SELECT transaction_hash, accepted_at, block_height, tx_type, node_id, validator_transaction_hash, 'P-avax1' AS delegator_address, 1 AS delegator_address_count, start_time, end_time, duration_days, stake_navax, stake_avax, potential_reward_navax, potential_reward_avax, rewarded, staked_utxo_count, utxo_stake_navax FROM ({base}) WHERE role = 'delegator'", "2026-09-19T10:01:00Z")
    make_run(runs, "rewards", "snowflake.primary-staking-rewards", "primary-staking-rewards",
             f"SELECT 'r-' || staking_transaction_hash AS reward_transaction_hash, rewarded_at, 9 AS block_height, staking_transaction_hash, 'RewardValidatorTx' AS staking_tx_type, 'NodeID-x' AS node_id, rewarded_at AS period_start_time, rewarded_at AS period_end_time, realized_reward_navax > 0 AS rewarded, realized_reward_navax AS potential_reward_navax, realized_reward_navax / 1e9 AS potential_reward_avax, realized_reward_navax, realized_reward_navax / 1e9 AS realized_reward_avax, fee_transfer_navax, fee_transfer_navax / 1e9 AS fee_transfer_avax, 1 AS reward_utxo_count FROM (VALUES {values(REWARDS)}) AS t(staking_transaction_hash, rewarded_at, realized_reward_navax, fee_transfer_navax)", "2026-09-19T10:02:00Z")
    make_run(runs, "supply", "snowflake.primary-staking-supply", "primary-staking-supply",
             f"SELECT transaction_hash, accepted_at, tx_type, 7 AS block_height, 0 AS tx_block_position, {SUPPLY} AS previous_block_supply_navax, {SUPPLY} + potential_reward_navax AS block_supply_navax, 0 AS in_block_prior_delta_navax, potential_reward_navax AS in_block_total_delta_navax, {SUPPLY} AS supply_before_navax FROM ({base}) WHERE transaction_hash <> 'd2'", "2026-09-19T10:03:00Z")
    return runs


def test_catalog_declares_the_staking_period_log():
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == derived.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(derived.TABLE_COLUMNS)
    assert definition["input_ids"] == list(derived.INPUTS)


def test_derive_joins_regimes_and_kernel(root):
    output = root / "staking-periods"
    result = derived.derive(derived.DATASET_ID, output, None, root)
    capture, build = result["capture"], result["build"]
    assert [item["dataset_id"] for item in capture["inputs"]] == list(derived.INPUTS.values())
    assert build["source_capture_id"] == capture["capture_id"]
    summary = build["summary"]
    assert (summary["rows"], summary["validators"], summary["delegators"]) == (4, 2, 2)
    assert (summary["immediate_rows"], summary["immediate_reproduced"], summary["immediate_reproduced_share"]) == (2, 2, 1.0)
    assert (summary["pending_rows"], summary["pending_reproduced"]) == (1, 0)
    assert summary["gap_without_supply_row"] == 1 and summary["kernel_failed"] == 0
    assert summary["with_reward_row"] == 3 and summary["open_periods"] == 1 and summary["zero_realized"] == 1
    table = duckdb.connect().execute("SELECT transaction_hash, regime, start_kind, reproduced, kernel_gap_navax, realized_reward_navax FROM read_parquet(?) ORDER BY transaction_hash", [str(output / "dataset" / "staking-periods.parquet")]).fetchall()
    assert table == [
        ("d1", "durango", "immediate", True, 0, STAKES[2][9]),
        ("d2", "granite", "immediate", None, None, None),
        ("v1", "banff", "pending", False, -1, STAKES[0][9]),
        ("v2", "durango", "immediate", True, 0, 0),
    ]
    validation = derived.check(output / "capture", output / "dataset", root=root)
    assert validation["status"] == "pass", validation["findings"]
    assert validation["summary"]["rows"] == 4
    with pytest.raises(DataError):
        derived.derive(derived.DATASET_ID, output, None, root)


def test_derive_pins_input_runs_and_rejects_unknown(root):
    with pytest.raises(DataError):
        derived.derive(derived.DATASET_ID, root / "x", {"coingecko.avax-market-daily": "nope"}, root)
    result = derived.derive(derived.DATASET_ID, root / "pinned", {"snowflake.primary-staking-supply": "supply"}, root)
    assert next(item for item in result["capture"]["inputs"] if item["input_id"] == "staking-supply")["run"] == "supply"


def test_check_flags_changed_inputs_and_outputs(root):
    output = root / "staking-periods"
    derived.derive(derived.DATASET_ID, output, None, root)
    parquet = root / "supply" / "dataset" / "primary-staking-supply.parquet"
    parquet.write_bytes(parquet.read_bytes() + b" ")
    validation = derived.check(output / "capture", output / "dataset", root=root)
    assert "input run differs from the capture receipt: supply" in validation["findings"]
    receipt = json.loads((output / "capture" / "capture.json").read_text())
    receipt["contract_sha256"] = "0" * 64
    (output / "capture" / "capture.json").write_bytes(canonical_bytes(receipt))
    validation = derived.check(output / "capture", None, root=root)
    assert "catalog contract changed since the capture" in validation["findings"]
    with pytest.raises(DataError):
        derived.check(output / "capture", None, against=root)
    with pytest.raises(DataError):
        derived.capture(derived.DATASET_ID, root / "capture")
