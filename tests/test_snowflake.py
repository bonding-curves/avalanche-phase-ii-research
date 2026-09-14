from __future__ import annotations

import gzip
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from avalanche_research import cli, snowflake
from avalanche_research.catalog import DataError, load_catalog


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
        "staked_utxo_count": 1,
        "utxo_stake_navax": 2_000_000_000_000,
    }
    row.update(overrides)
    return row


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
    def __init__(self, rows, fail: bool):
        self.rows, self.fail, self.sfqid = rows, fail, "01c7-fixture"
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
        self.description = [(name.upper(),) for name in snowflake.RAW_COLUMNS]
        self.pending = [tuple(row[name] for name in snowflake.RAW_COLUMNS) for row in self.rows]

    def fetchall(self):
        rows, self.pending = self.pending, []
        return rows

    def fetchmany(self, size):
        batch, self.pending = self.pending[:size], self.pending[size:]
        return batch

    def close(self):
        pass


class FakeConnection:
    def __init__(self, rows, fail=False):
        self.rows, self.fail, self.closed = rows, fail, False

    def cursor(self):
        return FakeCursor(self.rows, self.fail)

    def close(self):
        self.closed = True


def connector(rows=ROWS, fail=False):
    def connect(name, timeout):
        assert name == "avalanche" and 1 <= timeout <= 600
        return FakeConnection(rows, fail)

    return connect


def make_capture(tmp_path: Path, rows=ROWS, parameters=None) -> tuple[Path, dict]:
    path = tmp_path / "capture"
    receipt = snowflake.capture(snowflake.DATASET_ID, path, parameters=parameters, connector=connector(rows))
    return path, receipt


def test_catalog_declares_the_snowflake_query_dataset():
    catalog = load_catalog()
    query = snowflake.query_definition(catalog, snowflake.DATASET_ID)
    assert query["relations"] == ["P_TRANSACTIONS", "UTXOS"]
    assert "%(start)s" in snowflake.read_sql(query) and "%(end)s" in snowflake.read_sql(query)


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
        raw_row(transaction_hash="tx-dup", delegation_fee_shares=10, accepted_at=datetime(2019, 1, 1)),
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
        "snowpeer.network-summary", snowflake.DATASET_ID,
    ]


def test_cli_rejects_parameters_for_snowpeer_and_malformed_values(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["avalanche", "data", "fetch", "snowpeer.network-summary", "--output", "x", "--param", "start=2024-01-01", "--preview"])
    assert cli.main() == 2
    assert "accepts no parameters" in capsys.readouterr().err
    monkeypatch.setattr(sys, "argv", ["avalanche", "data", "fetch", snowflake.DATASET_ID, "--output", "x", "--param", "start", "--preview"])
    assert cli.main() == 2
    assert "key=value" in capsys.readouterr().err
