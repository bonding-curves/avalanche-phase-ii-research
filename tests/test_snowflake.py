from __future__ import annotations

import gzip
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pytest
from click.testing import CliRunner

from avalanche_research import cli, snowflake
from avalanche_research.catalog import DataError, load_catalog


def test_primary_burn_events_preserve_recorded_burn_and_zero_system_transactions():
    spec = snowflake.PRIMARY_BURN_EVENTS
    connection = duckdb.connect()
    try:
        connection.execute("""
            CREATE TABLE capture (
                chain VARCHAR, transaction_hash VARCHAR, accepted_at TIMESTAMP,
                block_height BIGINT, tx_type VARCHAR, burned_navax BIGINT, fee_navax BIGINT
            )
        """)
        connection.execute("""
            INSERT INTO capture VALUES
                ('P', 'reward', '2026-09-16', 1, 'RewardValidatorTx', NULL, 0),
                ('P', 'stake', '2026-09-16', 2, 'AddValidatorTx', 500000000, 50000),
                ('X', 'send', '2026-09-16', 3, 'BaseTx', 1000000, 1000000)
        """)
        connection.execute(f"CREATE TABLE rows AS {spec.transform_sql}")
        assert connection.execute(
            "SELECT transaction_hash, burned_navax FROM rows ORDER BY transaction_hash"
        ).fetchall() == [("reward", 0), ("send", 1_000_000), ("stake", 500_000_000)]
    finally:
        connection.close()


def c_burn_day(day, burned_wei, first_block, last_block, previous_last_block, receipts):
    epoch = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())
    return {
        "date_utc": day, "burned_wei": burned_wei,
        "block_count": last_block - first_block + 1,
        "distinct_blocks": last_block - first_block + 1,
        "first_block": first_block, "last_block": last_block,
        "previous_last_block": previous_last_block,
        "next_first_block": last_block + 1,
        "expected_receipts": receipts, "receipt_count": receipts,
        "distinct_receipts": receipts, "missing_fee_inputs": 0,
        "first_epoch": epoch, "last_epoch": epoch + 86399,
    }


def test_c_evm_burn_daily_preserves_wei_and_checks_coverage(tmp_path):
    assert snowflake.capture_preview(
        snowflake.C_CHAIN_EVM_BURN_DAILY.dataset_id, tmp_path / "preview"
    )["parameters"]["start"] == snowflake.C_CHAIN_FIRST_DATE
    rows = [
        c_burn_day(date(2026, 9, 16), 1_000_000_001, 10, 11, 9, 3),
        c_burn_day(date(2026, 9, 17), 20, 12, 13, 11, 2),
    ]
    window = {"start": "2026-09-16", "end": "2026-09-18"}
    capture_dir, _ = make_capture(tmp_path, rows, window, snowflake.C_CHAIN_EVM_BURN_DAILY)
    dataset_dir = tmp_path / "dataset"
    build = snowflake.build(snowflake.C_CHAIN_EVM_BURN_DAILY.dataset_id, capture_dir, dataset_dir)
    assert build["summary"]["burned_wei"] == 1_000_000_021
    assert snowflake.check(capture_dir, dataset_dir)["status"] == "pass"

    broken = [dict(row) for row in rows]
    broken[1]["receipt_count"] = 1
    broken[1]["first_block"] = 15
    broken_capture, _ = make_capture(tmp_path / "broken", broken, window, snowflake.C_CHAIN_EVM_BURN_DAILY)
    findings = snowflake.check(broken_capture)["findings"]
    assert any("receipt count" in finding for finding in findings)
    assert any("adjacent C block days" in finding for finding in findings)

    no_next_day = [dict(row) for row in rows]
    no_next_day[1]["next_first_block"] = None
    no_next_capture, _ = make_capture(tmp_path / "no-next", no_next_day, window, snowflake.C_CHAIN_EVM_BURN_DAILY)
    assert any("adjacent C block days" in finding for finding in snowflake.check(no_next_capture)["findings"])


def raw_row(**overrides):
    row = {
        "transaction_hash": "tx-legacy-1",
        "accepted_at": datetime(2021, 3, 1, 12, 0, 0),
        "block_height": 1200,
        "tx_type": "AddValidatorTx",
        "node_id": "NodeID-A",
        "start_time": datetime(2021, 3, 1, 12, 5, 0),
        "end_time": datetime(2021, 5, 1, 12, 5, 0),
        "stake_navax": 2_000_000_000_000,
        "delegation_fee_shares": 20_000,
        "potential_reward_navax": 41_095_890_410,
        "rewarded": True,
        "reward_addresses": '["P-avax1owner"]',
        "reward_address": "P-avax1owner",
        "reward_address_count": 1,
        "staked_utxo_count": 1,
        "utxo_stake_navax": 2_000_000_000_000,
    }
    row.update(overrides)
    return row


DELEGATOR_ROWS = [
    {
        "transaction_hash": "del-1", "accepted_at": datetime(2021, 3, 2, 9, 0, 0), "block_height": 1300,
        "tx_type": "AddDelegatorTx", "node_id": "NodeID-A", "validator_transaction_hash": "tx-legacy-1",
        "delegator_address": "P-avax1delegator", "delegator_address_count": 1,
        "start_time": datetime(2021, 3, 2, 9, 5, 0), "end_time": datetime(2021, 3, 30, 9, 5, 0),
        "stake_navax": 25_000_000_000, "potential_reward_navax": 100_000_000, "rewarded": True,
        "staked_utxo_count": 1, "utxo_stake_navax": 25_000_000_000,
    },
    {
        "transaction_hash": "del-2", "accepted_at": datetime(2025, 1, 3, 0, 0, 0), "block_height": 9000,
        "tx_type": "AddPermissionlessDelegatorTx", "node_id": "NodeID-B", "validator_transaction_hash": None,
        "delegator_address": None, "delegator_address_count": 0,
        "start_time": datetime(2025, 1, 3, 0, 5, 0), "end_time": datetime(2025, 1, 17, 0, 5, 0),
        "stake_navax": 30_000_000_000, "potential_reward_navax": 90_000_000, "rewarded": None,
        "staked_utxo_count": 0, "utxo_stake_navax": None,
    },
]

REWARD_ROWS = [
    {
        "reward_transaction_hash": "rw-1", "rewarded_at": datetime(2021, 5, 1, 12, 6, 0), "block_height": 5000,
        "staking_transaction_hash": "tx-legacy-1", "staking_tx_type": "AddValidatorTx", "node_id": "NodeID-A",
        "period_start_time": datetime(2021, 3, 1, 12, 5, 0), "period_end_time": datetime(2021, 5, 1, 12, 5, 0),
        "rewarded": True, "potential_reward_navax": 41_095_890_410, "realized_reward_navax": 43_000_000_000, "reward_utxo_count": 2,
    },
    {
        "reward_transaction_hash": "rw-2", "rewarded_at": datetime(2021, 3, 30, 9, 6, 0), "block_height": 4000,
        "staking_transaction_hash": "del-1", "staking_tx_type": "AddDelegatorTx", "node_id": "NodeID-A",
        "period_start_time": datetime(2021, 3, 2, 9, 5, 0), "period_end_time": datetime(2021, 3, 30, 9, 5, 0),
        "rewarded": True, "potential_reward_navax": 100_000_000, "realized_reward_navax": 98_000_000, "reward_utxo_count": 1,
    },
    {
        "reward_transaction_hash": "rw-4", "rewarded_at": datetime(2021, 6, 1, 0, 0, 0), "block_height": 5500,
        "staking_transaction_hash": "del-9", "staking_tx_type": "AddDelegatorTx", "node_id": "NodeID-A",
        "period_start_time": datetime(2021, 5, 1, 0, 0, 0), "period_end_time": datetime(2021, 5, 31, 23, 59, 0),
        "rewarded": True, "potential_reward_navax": 50_000_000, "realized_reward_navax": 0, "reward_utxo_count": 0,
    },
    {
        "reward_transaction_hash": "rw-3", "rewarded_at": datetime(2022, 1, 1, 0, 0, 0), "block_height": 6000,
        "staking_transaction_hash": "unknown", "staking_tx_type": None, "node_id": None,
        "period_start_time": None, "period_end_time": None,
        "rewarded": None, "potential_reward_navax": None, "realized_reward_navax": 0, "reward_utxo_count": 0,
    },
]

ROWS = [
    raw_row(),
    raw_row(
        transaction_hash="tx-genesis", accepted_at=datetime(2020, 9, 10), block_height=-1,
        start_time=datetime(2020, 9, 10), end_time=datetime(2021, 9, 10), potential_reward_navax=None, rewarded=None,
    ),
    raw_row(
        transaction_hash="tx-permissionless-1", accepted_at=datetime(2025, 1, 2, 3, 4, 5),
        tx_type="AddPermissionlessValidatorTx", node_id="NodeID-B", start_time=datetime(2025, 1, 2, 3, 10, 0),
        end_time=datetime(2025, 1, 16, 3, 10, 0), stake_navax=25_655_676_993_789, delegation_fee_shares=1_000_000,
        potential_reward_navax=6_000_000_000, rewarded=None, staked_utxo_count=0, utxo_stake_navax=None,
    ),
]


class FakeCursor:
    def __init__(self, rows, fail: bool, columns):
        self.rows, self.fail, self.sfqid, self.columns = rows, fail, "01c7-fixture", columns
        self.description = []
        self.pending = []

    def execute(self, sql, params=None):
        if sql == snowflake.SESSION_SQL:
            self.description = [("CURRENT_ROLE()",)]
            self.pending = [("RESEARCH", "COMPUTE_WH", "AVALANCHE_PRIMARY_NETWORK_DATA", "PRIMARY", "10.32.102")]
            return
        assert "%(start)s" in sql and set(params) == {"start", "end"}
        if self.fail:
            raise OSError("fixture failure")
        self.description = [(name.upper(),) for name in self.columns]
        self.pending = [tuple(row[name] for name in self.columns) for row in self.rows]

    def fetchall(self):
        rows, self.pending = self.pending, []
        return rows

    def fetchmany(self, size):
        batch, self.pending = self.pending[:size], self.pending[size:]
        return batch

    def close(self):
        pass


class FakeConnection:
    def __init__(self, rows, fail, columns):
        self.rows, self.fail, self.columns, self.closed = rows, fail, columns, False

    def cursor(self):
        return FakeCursor(self.rows, self.fail, self.columns)

    def close(self):
        self.closed = True


def connector(rows=ROWS, fail=False, spec=snowflake.VALIDATOR_STAKES):
    def connect(name, timeout):
        assert name == "avalanche" and 1 <= timeout <= 600
        return FakeConnection(rows, fail, tuple(spec.raw_types))

    return connect


def make_capture(tmp_path: Path, rows=ROWS, parameters=None, spec=snowflake.VALIDATOR_STAKES) -> tuple[Path, dict]:
    path = tmp_path / "capture"
    receipt = snowflake.capture(spec.dataset_id, path, parameters=parameters, connector=connector(rows, spec=spec))
    return path, receipt


@pytest.mark.parametrize("spec", list(snowflake.SPECS.values()))
def test_catalog_declares_each_snowflake_query_dataset(spec):
    catalog = load_catalog()
    query = snowflake.query_definition(catalog, spec.dataset_id)
    assert len(query["relations"]) == 2
    assert "%(start)s" in snowflake.read_sql(query) and "%(end)s" in snowflake.read_sql(query)
    definition = next(item for item in catalog["datasets"] if item["id"] == spec.dataset_id)
    assert [field["name"] for field in definition["fields"]] == list(spec.table_columns)
    assert len(spec.check_names) == len(spec.check_labels) == spec.check_sql.count(",\n") + 1


def test_parameters_default_to_full_history_and_reject_bad_input():
    resolved = snowflake.resolve_parameters(None)
    assert resolved["start"] == "2020-09-10" and resolved["end"] > resolved["start"]
    assert snowflake.resolve_parameters({"start": "2024-01-01", "end": "2024-02-01"}) == {"start": "2024-01-01", "end": "2024-02-01"}
    with pytest.raises(DataError, match="ISO date"):
        snowflake.resolve_parameters({"start": "yesterday"})
    with pytest.raises(DataError, match="precede"):
        snowflake.resolve_parameters({"start": "2024-02-01", "end": "2024-01-01"})
    with pytest.raises(DataError, match="unknown parameters"):
        snowflake.resolve_parameters({"limit": "5"})


def test_capture_preserves_query_rows_and_receipt(tmp_path):
    path, receipt = make_capture(tmp_path, parameters={"start": "2020-09-01", "end": "2026-01-01"})
    record = receipt["queries"][0]
    assert receipt["session"]["role"] == "RESEARCH" and "account" not in receipt["session"]
    assert record["rows"] == 3 and record["snowflake_query_id"] == "01c7-fixture"
    assert (path / record["sql_path"]).read_text() == snowflake.read_sql(
        snowflake.query_definition(load_catalog(), snowflake.DATASET_ID)
    )
    assert snowflake.read_capture(path) == receipt
    rows = [json.loads(line) for line in gzip.decompress((path / record["path"]).read_bytes()).decode().splitlines()]
    assert rows[1]["accepted_at"] == "2020-09-10T00:00:00Z" and rows[1]["block_height"] == -1


def test_failed_query_does_not_publish_partial_output(tmp_path):
    path = tmp_path / "capture"
    with pytest.raises(OSError, match="fixture failure"):
        snowflake.capture(snowflake.DATASET_ID, path, connector=connector(fail=True))
    assert not path.exists()


def test_missing_connector_reports_install_instruction(monkeypatch):
    monkeypatch.setitem(sys.modules, "snowflake.connector", None)
    with pytest.raises(DataError, match="--extra snowflake"):
        snowflake.connect("avalanche", 20)


def test_build_and_check_round_trip_parquet(tmp_path):
    capture_dir, _ = make_capture(tmp_path)
    dataset_dir = tmp_path / "dataset"
    receipt = snowflake.build(snowflake.DATASET_ID, capture_dir, dataset_dir)
    assert receipt["summary"] == {
        "rows": 3,
        "accepted_from": "2020-09-10T00:00:00Z",
        "accepted_to": "2025-01-02T03:04:05Z",
        "rows_by_tx_type": {"AddValidatorTx": 2, "AddPermissionlessValidatorTx": 1},
        "distinct_node_ids": 2,
        "rows_without_staked_utxo": 1,
        "rows_without_reward_status": 2,
        "rows_without_potential_reward": 1,
    }
    validation = snowflake.check(capture_dir, dataset_dir)
    assert validation["status"] == "pass", validation["findings"]
    table = snowflake.read_parquet(dataset_dir / "primary-validator-stakes.parquet")
    assert [row["transaction_hash"] for row in table] == ["tx-genesis", "tx-legacy-1", "tx-permissionless-1"]
    assert table[1]["duration_days"] == 61 and table[1]["stake_avax"] == 2_000 and table[1]["delegation_fee_rate"] == 0.02
    assert table[2]["potential_reward_avax"] == 6 and table[2]["rewarded"] is None and table[2]["utxo_stake_navax"] is None


def test_check_reports_domain_findings(tmp_path):
    rows = [
        raw_row(end_time=datetime(2021, 3, 3, 12, 5, 0)),
        raw_row(transaction_hash="tx-dup", stake_navax=1_000_000_000, utxo_stake_navax=999, start_time=datetime(2021, 3, 1, 11, 0, 0)),
        raw_row(transaction_hash="tx-dup", delegation_fee_shares=10, accepted_at=datetime(2019, 1, 1), reward_addresses="[]", reward_address=None, reward_address_count=0),
    ]
    capture_dir, _ = make_capture(tmp_path, rows, parameters={"start": "2020-09-10", "end": "2022-01-01"})
    validation = snowflake.check(capture_dir)
    assert validation["status"] == "attention"
    assert validation["findings"] == [
        "1 rows repeat a transaction hash",
        "1 rows were accepted outside the requested window",
        "1 rows start before acceptance or end before start",
        "1 rows have a duration outside 14 to 365 days",
        "1 rows have a stake outside 2,000 to 3,000,000 AVAX",
        "1 rows have a delegation fee outside 2% to 100%",
        "1 rows have no reward address",
        "1 rows have staked UTXOs that do not sum to the declared stake",
    ]


def test_tampered_or_stale_capture_is_rejected(tmp_path):
    capture_dir, receipt = make_capture(tmp_path)
    target = capture_dir / receipt["queries"][0]["path"]
    lines = gzip.decompress(target.read_bytes()).decode().splitlines()
    target.write_bytes(gzip.compress(("\n".join(lines[:-1]) + "\n").encode(), mtime=0))
    with pytest.raises(DataError, match="hash or size differs"):
        snowflake.read_capture(capture_dir)
    stale_dir, _ = make_capture(tmp_path / "stale")
    (stale_dir / "raw/primary-validator-stakes.sql").write_text("SELECT 1")
    with pytest.raises(DataError, match="query text differs"):
        snowflake.read_capture(stale_dir)


def test_malformed_capture_values_are_rejected(tmp_path):
    capture_dir, receipt = make_capture(tmp_path)
    target = capture_dir / receipt["queries"][0]["path"]
    lines = gzip.decompress(target.read_bytes()).decode().splitlines()
    lines[0] = lines[0].replace('"stake_navax": 2000000000000', '"stake_navax": "two thousand"')
    body = gzip.compress(("\n".join(lines) + "\n").encode(), mtime=0)
    target.write_bytes(body)
    receipt["queries"][0].update({"sha256": snowflake.sha256(body), "bytes": len(body)})
    (capture_dir / "capture.json").write_bytes(snowflake.canonical_bytes(receipt))
    with pytest.raises(DataError, match="declared types"):
        snowflake.check(capture_dir)


def test_delegator_dataset_builds_checks_and_reports_containment(tmp_path):
    spec = snowflake.DELEGATOR_STAKES
    capture_dir, receipt = make_capture(tmp_path, DELEGATOR_ROWS, spec=spec)
    assert receipt["queries"][0]["columns"] == list(spec.raw_types)
    dataset_dir = tmp_path / "dataset"
    build = snowflake.build(spec.dataset_id, capture_dir, dataset_dir)
    assert build["summary"]["rows_by_tx_type"] == {"AddDelegatorTx": 1, "AddPermissionlessDelegatorTx": 1}
    assert build["summary"]["distinct_delegator_addresses"] == 1 and build["summary"]["rows_without_delegator_address"] == 1
    validation = snowflake.check(capture_dir, dataset_dir)
    assert validation["checked"][-3:] == ["validator period containment", "build hashes", "Parquet rows"]
    assert validation["findings"] == ["1 rows fall outside every validator staking period on their node"]
    table = snowflake.read_parquet(dataset_dir / "primary-delegator-stakes.parquet", spec)
    assert table[0]["stake_avax"] == 25 and table[0]["validator_transaction_hash"] == "tx-legacy-1"
    assert "delegation_fee_shares" not in table[0]
    with pytest.raises(DataError, match="belongs to"):
        snowflake.build(snowflake.DATASET_ID, capture_dir, tmp_path / "wrong")


def test_capture_stays_valid_when_an_unrelated_catalog_record_changes(tmp_path, monkeypatch):
    capture_dir, receipt = make_capture(tmp_path)
    catalog = load_catalog()
    supply = next(item for item in catalog["datasets"] if item["id"] == "snowflake.primary-staking-supply")
    catalog["datasets"].append({**supply, "id": "snowflake.something-else", "query_ids": ["primary-delegator-stakes"]})
    monkeypatch.setattr(snowflake, "load_catalog", lambda: catalog)
    assert snowflake.read_capture(capture_dir) == receipt
    catalog["datasets"][1]["studies"] = ["Another study"]
    catalog["datasets"][1]["description"] = "reworded"
    share = next(item for item in catalog["sources"] if item["id"] == "avalanche-snowflake")
    share["queries"][0]["observed_semantics"].append("a new note")
    assert snowflake.read_capture(capture_dir) == receipt
    share["queries"][0]["relations"].append("P_BLOCKS")
    with pytest.raises(DataError, match="contract hash differs"):
        snowflake.read_capture(capture_dir)


def test_reward_dataset_builds_checks_and_reports_unlinked_rewards(tmp_path):
    spec = snowflake.STAKING_REWARDS
    capture_dir, _ = make_capture(tmp_path, REWARD_ROWS, spec=spec)
    dataset_dir = tmp_path / "dataset"
    build = snowflake.build(spec.dataset_id, capture_dir, dataset_dir)
    assert build["summary"]["rows_by_tx_type"] == {
        "AddValidatorTx": 1, "AddPermissionlessValidatorTx": 0, "AddDelegatorTx": 2, "AddPermissionlessDelegatorTx": 0,
    }
    assert build["summary"]["fee_transfer_navax_total"] == 1_904_109_590 - 2_000_000 - 50_000_000
    assert build["summary"]["rows_rewarded_without_reward_utxo"] == 1 and build["summary"]["rows_without_reward_utxo"] == 2
    validation = snowflake.check(capture_dir, dataset_dir)
    assert validation["checked"][3:] == [*spec.check_names, "build hashes", "Parquet rows"]
    assert validation["findings"] == ["1 rows have no Primary Network staking period"]
    table = snowflake.read_parquet(dataset_dir / "primary-staking-rewards.parquet", spec)
    assert [row["reward_transaction_hash"] for row in table] == ["rw-2", "rw-1", "rw-4", "rw-3"]
    assert table[1]["fee_transfer_avax"] == pytest.approx(1.90410959) and table[0]["fee_transfer_navax"] == -2_000_000


def test_cli_preview_resolves_parameters_without_writing(tmp_path):
    runner = CliRunner()
    output = tmp_path / "capture"
    preview = runner.invoke(cli.cli, [
        "data", "fetch", snowflake.DATASET_ID, "--output", str(output),
        "--param", "start=2024-01-01", "--param", "end=2024-02-01", "--preview", "--json",
    ])
    assert preview.exit_code == 0, preview.output
    assert not output.exists()
    value = json.loads(preview.output)["preview"]
    assert value["parameters"] == {"start": "2024-01-01", "end": "2024-02-01"}
    assert value["connection"] == "avalanche" and value["sql"] == "queries/primary-validator-stakes.sql"
    manifest = runner.invoke(cli.cli, ["data", "manifest", "--json"])
    assert [item["id"] for item in json.loads(manifest.output)["records"]] == [
        "snowpeer.network-summary", *snowflake.DATASET_IDS, "coingecko.avax-market-daily", "defillama.avax-price-daily",
        "c-chain-rpc.receipt-gap-repairs", "p-chain-rpc.current-validators", "defillama.pool-yields", "us-treasury.par-yield-daily",
            "metrics-api.primary-staking-daily", "metrics-api.c-chain-activity-daily", "data-api.avax-supply",
        "data-api.validators-active",
        "data-api.validators-completed",
            "data-api.c-chain-atomic-burn",
        "derived.staking-periods",
        "derived.node-table",
    ]


def test_cli_check_with_findings_exits_one(tmp_path, monkeypatch, capsys):
    capture_dir, _ = make_capture(tmp_path, DELEGATOR_ROWS, spec=snowflake.DELEGATOR_STAKES)
    monkeypatch.setattr(sys, "argv", ["avalanche", "data", "check", snowflake.DELEGATOR_STAKES.dataset_id, "--capture", str(capture_dir)])
    assert cli.main() == 1
    assert "ATTENTION" in capsys.readouterr().out


def test_cli_rejects_parameters_for_snowpeer_and_malformed_values(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["avalanche", "data", "fetch", "snowpeer.network-summary", "--output", "x", "--param", "start=2024-01-01", "--preview"])
    assert cli.main() == 2
    assert "accepts no parameters" in capsys.readouterr().err
    monkeypatch.setattr(sys, "argv", ["avalanche", "data", "fetch", snowflake.DATASET_ID, "--output", "x", "--param", "start", "--preview"])
    assert cli.main() == 2
    assert "key=value" in capsys.readouterr().err
