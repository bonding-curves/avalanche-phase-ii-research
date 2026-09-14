from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pytest

from avalanche_research import pchain, rest
from avalanche_research.catalog import DataError, load_catalog


def validator(node: str, tx: str, start: int, end: int, weight: int, uptime: str = "99.5", fee: str = "2.0000", connected: bool = True) -> dict:
    return {
        "txID": tx, "startTime": str(start), "endTime": str(end), "weight": str(weight), "nodeID": node,
        "validationRewardOwner": {"locktime": "0", "threshold": "1", "addresses": [f"P-avax1{node.lower()}"]},
        "delegationRewardOwner": {"locktime": "0", "threshold": "1", "addresses": [f"P-avax1{node.lower()}d"]},
        "potentialReward": "87207412343", "accruedDelegateeReward": "12", "delegationFee": fee, "uptime": uptime,
        "connected": connected, "signer": {"publicKey": "0xab", "proofOfPossession": "0xcd"}, "delegatorCount": "3", "delegatorWeight": "5000000000000",
    }


NOW = 1789430000  # 2026-09-15T05:53:20Z, within every fixture period
VALIDATORS = [
    validator("NodeID-A", "tx-a", NOW - 86_400 * 10, NOW + 86_400 * 20, 2_000_000_000_000),
    validator("NodeID-B", "tx-b", NOW - 86_400 * 5, NOW + 86_400 * 100, 25_655_676_993_789, uptime="85.25", fee="100.0000", connected=False),
]


class Response:
    def __init__(self, validators: list[dict]):
        self.body = json.dumps({"jsonrpc": "2.0", "result": {"validators": validators}, "id": 1}).encode()
        self.status = 200
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self) -> bytes:
        return self.body


def opener(validators=VALIDATORS):
    def open_request(request, timeout):
        assert request.get_method() == "POST" and json.loads(request.data)["method"] == "platform.getCurrentValidators"
        assert request.get_header("Content-type") == "application/json"
        return Response(validators)

    return open_request


def make_capture(tmp_path: Path, validators=VALIDATORS) -> tuple[Path, dict]:
    path = tmp_path / "capture"
    return path, pchain.capture(pchain.DATASET_ID, path, opener=opener(validators))


def test_catalog_declares_the_rpc_dataset_with_a_post_body():
    catalog = load_catalog()
    definition = next(item for item in catalog["datasets"] if item["id"] == pchain.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(pchain.TABLE_COLUMNS)
    preview = pchain.capture_preview(pchain.DATASET_ID, Path("x"))
    assert preview["requests"][0]["method"] == "POST" and preview["requests"][0]["request_json"]["method"] == "platform.getCurrentValidators"


def test_capture_build_and_check_round_trip(tmp_path):
    capture_dir, receipt = make_capture(tmp_path)
    assert receipt["responses"][0]["method"] == "POST" and receipt["responses"][0]["request_json"]["id"] == 1
    dataset_dir = tmp_path / "dataset"
    build = pchain.build(pchain.DATASET_ID, capture_dir, dataset_dir)
    assert build["summary"]["rows"] == 2 and build["summary"]["connected_validators"] == 1
    assert build["summary"]["validators_below_90_percent_uptime"] == 1 and build["summary"]["delegation_fee_rate_median"] == pytest.approx(0.51)
    validation = pchain.check(capture_dir, dataset_dir)
    assert validation["status"] == "pass", validation["findings"]
    rows = duckdb.connect().execute(f"SELECT node_id, uptime, delegation_fee_rate, stake_avax, validation_reward_address FROM '{dataset_dir / 'current-validators.parquet'}' ORDER BY node_id").fetchall()
    assert rows[1] == ("NodeID-B", 0.8525, 1.0, 25655.676993789, "P-avax1nodeid-b")


def test_check_reports_domain_findings(tmp_path, monkeypatch):
    observed = datetime.fromtimestamp(NOW, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    monkeypatch.setattr(rest, "_now", lambda: observed)
    bad = [validator("NodeID-A", "tx-a", NOW - 10, NOW + 10, 1_000_000_000, uptime="120", fee="1.0000"), validator("NodeID-A", "tx-c", NOW + 100, NOW + 200, 2_000_000_000_000)]
    capture_dir, _ = make_capture(tmp_path, bad)
    validation = pchain.check(capture_dir)
    assert validation["findings"] == [
        "1 rows repeat a node or transaction",
        "1 rows have a period that does not contain the observation time",
        "1 rows have a stake outside 2,000 to 3,000,000 AVAX",
        "1 rows have a delegation fee outside 2% to 100%",
        "1 rows have an uptime outside 0 to 1",
    ]


def test_reconciliation_against_snowflake_validators(tmp_path):
    capture_dir, _ = make_capture(tmp_path)
    reference = tmp_path / "reference"
    reference.mkdir()
    stamp = lambda seconds: datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    duckdb.connect().execute(f"""
        COPY (SELECT * FROM (VALUES
            ('tx-a', 'NodeID-A', TIMESTAMP '{stamp(NOW - 86_400 * 10)}', TIMESTAMP '{stamp(NOW + 86_400 * 20)}', 2000000000000::BIGINT, 0.02, TIMESTAMP '2026-09-14 00:00:00'),
            ('tx-b', 'NodeID-B', TIMESTAMP '{stamp(NOW - 86_400 * 5)}', TIMESTAMP '{stamp(NOW + 86_400 * 100)}', 1::BIGINT, 0.5, TIMESTAMP '2026-09-14 00:00:00')
        ) t(transaction_hash, node_id, start_time, end_time, stake_navax, delegation_fee_rate, accepted_at)) TO '{reference / "primary-validator-stakes.parquet"}' (FORMAT PARQUET)
    """)
    validation = pchain.check(capture_dir, against=reference)
    assert validation["summary"]["matched_in_reference"] == 2 and validation["summary"]["missing_from_reference_before_its_last_row"] == 0
    assert validation["findings"] == [
        "1 validators disagree with the reference on node, period, or stake",
        "1 validators disagree with the reference on delegation fee",
    ]
    with pytest.raises(DataError, match="missing reference"):
        pchain.check(capture_dir, against=tmp_path)
