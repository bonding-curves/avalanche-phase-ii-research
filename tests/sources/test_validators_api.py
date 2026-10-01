"""Data API validator datasets: active with uptime and capacity, completed with rewards, both paginated."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from avalanche_research.sources import validators_api as va
from avalanche_research.catalog import DataError, load_catalog
from test_dataapi import Response

PRIMARY = "11111111111111111111111111111111LpoYY"


def active(tx, node, uptime=99.5, staked=2_000 * 10**9, delegated=0, start=1_790_000_000, end=1_792_000_000, fee="2.0", extra=None):
    row = {"txHash": tx, "nodeId": node, "subnetId": PRIMARY, "validationStatus": "active", "stakingType": "fixed",
           "startTimestamp": start, "endTimestamp": end, "amountStaked": str(staked), "delegationFee": fee, "delegatorCount": 1 if delegated else 0,
           "amountDelegated": str(delegated), "uptimePerformance": uptime, "delegationCapacity": str(4 * staked - delegated), "stakePercentage": 0.01,
           "avalancheGoVersion": "avalanchego/1.15.0", "validatorHealth": {"reachabilityPercent": 100, "benchedPChainRequestsPercent": 0, "benchedXChainRequestsPercent": 0, "benchedCChainRequestsPercent": 0},
           "geolocation": {"city": "Berlin", "country": "DE", "latitude": 52.5, "longitude": 13.4}, "potentialRewards": {"validationRewardAmount": "1000", "delegationRewardAmount": "0"}}
    row.update(extra or {})
    return row


def completed(tx, node, reward="262631202395", address="avax1owner", start=1_780_000_000, end=1_781_500_000):
    return {"txHash": tx, "nodeId": node, "subnetId": PRIMARY, "validationStatus": "completed", "stakingType": "fixed",
            "startTimestamp": start, "endTimestamp": end, "amountStaked": str(2_000 * 10**9), "delegationFee": "2.0", "delegatorCount": 0, "amountDelegated": "0",
            "rewards": {"validationRewardAmount": reward, "delegationRewardAmount": "0", "rewardAddresses": [address], "rewardTxHash": f"reward-{tx}"}}


def paged(pages):
    def opener(request, timeout):
        url = request.full_url
        index = int(url.split("pageToken=t")[1]) if "pageToken=" in url else 0
        body = {"validators": pages[index]}
        if index + 1 < len(pages):
            body["nextPageToken"] = f"t{index + 1}"
        return Response(body)
    return opener


def make_run(tmp_path: Path, dataset_id: str, pages) -> tuple[Path, Path]:
    capture_dir, dataset_dir = tmp_path / "capture", tmp_path / "dataset"
    va.capture(dataset_id, capture_dir, opener=paged(pages))
    va.build(dataset_id, capture_dir, dataset_dir)
    return capture_dir, dataset_dir


def test_catalog_declares_both_datasets():
    catalog = load_catalog()
    for dataset_id, columns in va.TABLE_COLUMNS.items():
        definition = next(item for item in catalog["datasets"] if item["id"] == dataset_id)
        assert [field["name"] for field in definition["fields"]] == list(columns)
        endpoint = next(e for s in catalog["sources"] if s["id"] == "avalanche-data-api" for e in s["endpoints"] if e["id"] == va.ENDPOINTS[dataset_id])
        assert endpoint["page"]["token_field"] == "nextPageToken" and "subnetId=" in endpoint["url"]


def test_active_pages_build_and_reconcile_against_the_rpc_snapshot(tmp_path):
    pages = [[active("tx-a", "NodeID-A", uptime=99.9, delegated=1_000 * 10**9), active("tx-b", "NodeID-B", uptime=85.0)], [active("tx-c", "NodeID-C", uptime=70.0)]]
    capture_dir, dataset_dir = make_run(tmp_path, va.ACTIVE_ID, pages)
    table = duckdb.connect().execute("SELECT node_id, uptime_performance_pct, delegation_fill, country FROM read_parquet(?) ORDER BY node_id", [str(dataset_dir / "validators-active.parquet")]).fetchall()
    assert table == [("NodeID-A", 99.9, 0.125, "DE"), ("NodeID-B", 85.0, 0.0, "DE"), ("NodeID-C", 70.0, 0.0, "DE")]
    reference = tmp_path / "reference"
    reference.mkdir()
    duckdb.connect().execute(
        "COPY (SELECT * FROM (VALUES ('NodeID-A', 0.999, 1000000000000::BIGINT), ('NodeID-B', 0.851, 0::BIGINT), ('NodeID-C', 0.70, 0::BIGINT)) AS t(node_id, uptime, delegator_weight_navax)) TO ? (FORMAT PARQUET)",
        [str(reference / "current-validators.parquet")],
    )
    validation = va.check(capture_dir, dataset_dir, reference)
    assert validation["status"] == "pass", validation["findings"]
    assert validation["summary"]["validators_below_90_percent_uptime"] == 2
    assert validation["summary"]["rpc_nodes_missing_from_api"] == 0 and validation["summary"]["delegated_weight_equal"] == 3


def test_active_check_reports_a_missing_rpc_node_and_bad_uptime(tmp_path):
    capture_dir, dataset_dir = make_run(tmp_path, va.ACTIVE_ID, [[active("tx-a", "NodeID-A", uptime=101.0)]])
    reference = tmp_path / "reference"
    reference.mkdir()
    duckdb.connect().execute(
        "COPY (SELECT * FROM (VALUES ('NodeID-A', 0.99, 0::BIGINT), ('NodeID-Z', 0.99, 0::BIGINT)) AS t(node_id, uptime, delegator_weight_navax)) TO ? (FORMAT PARQUET)",
        [str(reference / "current-validators.parquet")],
    )
    validation = va.check(capture_dir, dataset_dir, reference)
    assert "1 validations have uptime outside 0 to 100" in validation["findings"]
    assert "1 RPC validators are absent from the API snapshot" in validation["findings"]


def test_completed_pages_build_and_reconcile_against_snowflake(tmp_path):
    unrewarded = completed("tx-2", "NodeID-B", reward="0")
    unrewarded["rewards"]["rewardTxHash"] = None  # one 2021 validation in the real history has no reward transaction
    # A completed row sums every delegation over the period, so it can exceed four times the stake without any fault.
    busy = completed("tx-1", "NodeID-A")
    busy.update({"delegatorCount": 3, "amountDelegated": str(9_000 * 10**9)})
    pages = [[busy, unrewarded], [completed("tx-3", "NodeID-A", address="avax1other")]]
    capture_dir, dataset_dir = make_run(tmp_path, va.COMPLETED_ID, pages)
    summary = json.loads((dataset_dir / "build.json").read_text())["summary"]
    assert (summary["rows"], summary["distinct_nodes"], summary["validations_with_zero_reward"], summary["distinct_reward_addresses"]) == (3, 2, 1, 2)
    assert summary["validations_without_reward_transaction"] == 1
    reference = tmp_path / "reference"
    reference.mkdir()
    connection = duckdb.connect()
    connection.execute(
        """COPY (SELECT * FROM (VALUES ('tx-1', 'avax1owner', 2000000000000::BIGINT, 262631202395::BIGINT, true),
                                      ('tx-3', 'avax1owner', 2000000000000::BIGINT, 262631202395::BIGINT, false))
                 AS t(transaction_hash, reward_address, stake_navax, potential_reward_navax, rewarded)) TO ? (FORMAT PARQUET)""",
        [str(reference / "primary-validator-stakes.parquet")],
    )
    connection.execute(
        """COPY (SELECT * FROM (VALUES ('tx-1', 4000000000000::BIGINT), ('tx-1', 3000000000000::BIGINT), ('tx-1', 2000000000000::BIGINT))
                 AS t(validator_transaction_hash, stake_navax)) TO ? (FORMAT PARQUET)""",
        [str(reference / "primary-delegator-stakes.parquet")],
    )
    validation = va.check(capture_dir, dataset_dir, reference)
    assert validation["summary"]["validations_in_both"] == 2
    assert validation["summary"]["reward_equals_potential"] == 2 and validation["summary"]["unrewarded_per_snowflake"] == 1
    assert validation["summary"]["delegated_validations_in_both"] == 1 and validation["summary"]["delegation_sum_and_count_equal"] == 1
    assert validation["findings"] == ["reward address differs from the Snowflake capture on 1 validations"]


def test_recent_sweep_overlaps_the_history_and_spans_enough_days(tmp_path, monkeypatch):
    day = 86_400
    rows = [completed(f"tx-{i}", "NodeID-A", start=1_770_000_000, end=1_781_500_000 - i * 3 * day) for i in range(8)]  # newest end first, 21 days
    pages = [rows[:3], rows[3:6], rows[6:]]
    monkeypatch.setattr(va, "SWEEP_DAYS", 20)
    capture_dir, dataset_dir = make_run(tmp_path, va.RECENT_ID, pages)
    assert json.loads((capture_dir / "capture.json").read_text())["responses"][0]["pages"] == 3
    assert json.loads((dataset_dir / "build.json").read_text())["summary"]["rows"] == 8
    history = tmp_path / "history"
    history.mkdir()
    changed = rows[4]["txHash"]
    built, kept = dataset_dir / f"{va.TABLES[va.RECENT_ID]}.parquet", history / f"{va.TABLES[va.COMPLETED_ID]}.parquet"
    duckdb.connect().execute(
        f"""COPY (SELECT * REPLACE (CASE WHEN transaction_hash = '{changed}' THEN 1 ELSE validation_reward_navax END AS validation_reward_navax)
                  FROM read_parquet('{built}') WHERE transaction_hash <> 'tx-0') TO '{kept}' (FORMAT PARQUET)"""
    )
    validation = va.check(capture_dir, dataset_dir, history)
    assert "sweep span" in validation["checked"] and validation["summary"]["sweep_days"] == 21
    assert validation["summary"]["validations_in_history"] == 7 and validation["summary"]["validations_new_since_history"] == 1
    assert validation["findings"] == ["1 validations read differently from the full history"]
    monkeypatch.setattr(va, "SWEEP_DAYS", 30)
    assert "sweep spans 21 days of end times, fewer than 30; raise first_pages on the endpoint" in va.check(capture_dir, dataset_dir, history)["findings"]


def test_first_pages_ends_a_walk_without_error(tmp_path):
    catalog = json.loads(json.dumps(load_catalog()))
    endpoint = next(e for s in catalog["sources"] if s["id"] == "avalanche-data-api" for e in s["endpoints"] if e["id"] == va.ENDPOINTS[va.RECENT_ID])
    endpoint["page"]["first_pages"] = 2
    pages = [[completed("tx-1", "NodeID-A")], [completed("tx-2", "NodeID-A")], [completed("tx-3", "NodeID-A")]]
    receipt = va.capture(va.RECENT_ID, tmp_path / "capture", catalog=catalog, opener=paged(pages))
    assert receipt["responses"][0]["pages"] == 2


def test_subnet_rows_without_a_fee_are_rejected(tmp_path):
    row = active("tx-s", "NodeID-S")
    del row["delegationFee"]
    with pytest.raises(DataError, match="miss a required field"):
        make_run(tmp_path, va.ACTIVE_ID, [[row]])
