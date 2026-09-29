"""The P-Chain backup tables, over a fake walk with a delegation, an auto-renewed validator, and an abort of an older stake."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd
import pytest
from test_pblocks import FakeNode, blocks
from test_pstakers import data_api, node

from avalanche_research import pblocks, pstakers, pstaking
from avalanche_research.catalog import DataError, canonical_bytes, load_catalog, sha256
from avalanche_research.model import protocol

ANCHOR = 474_000_000_000_000_000


class AbortingNode(FakeNode):
    """Answers height 105 in hex as an abort block."""

    def __call__(self, url, timeout, body_json=None, content="json"):
        body, metadata = super().__call__(url, timeout, body_json, content)
        if body_json["method"] == "platform.getBlockByHeight" and body_json["params"]["encoding"] == "hex" and body_json["params"]["height"] == "105":
            value = json.loads(body)
            value["result"]["block"] = "0x0000" + f"{30:08x}" + "00" * 60
            body = json.dumps(value).encode()
        return body, metadata


def chain() -> dict[int, dict]:
    made = blocks(6)
    time = made[100]["time"]
    made[100]["txs"][0]["unsignedTx"]["validator"] = {"nodeID": "NodeID-A", "start": str(time - 30), "end": str(time + 14 * 86400), "weight": "25000000000"}
    made[104]["tx"]["unsignedTx"]["txID"] = "OLD"
    # The auto-renewed validator of block 103 ends its first 14-day cycle and renews, restaking everything.
    end = made[103]["time"] + 1_209_600
    made[106] = {"id": "B106", "parentID": "B105", "height": 106, "time": made[105]["time"] + 1, "txs": [],
                 "tx": {"id": "RA106", "unsignedTx": {"txID": "T103", "timestamp": str(end)}, "credentials": []}}
    made[107] = {"id": "B107", "parentID": "B106", "height": 107, "time": made[105]["time"] + 2}
    return made


def make_current_validators(root: Path) -> None:
    capture_dir, dataset_dir = root / "current" / "capture", root / "current" / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / "current-validators.parquet"
    duckdb.connect().execute(
        "COPY (SELECT 'V1' AS transaction_hash, 'NodeID-A' AS node_id, TIMESTAMP '2026-01-01' AS start_time,"
        " TIMESTAMP '2027-01-01' AS end_time) TO ? (FORMAT PARQUET)", [str(parquet)])
    capture_id = "capture:test:current"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({"schema_version": "test/v1", "capture_id": capture_id,
                                                                "dataset_id": "p-chain-rpc.current-validators", "completed_at": "2026-09-29T00:00:00Z"}))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({"schema_version": "test/v1", "dataset_id": "p-chain-rpc.current-validators",
                                                              "source_capture_id": capture_id, "completed_at": "2026-09-29T00:00:00Z", "summary": {"rows": 1},
                                                              "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}]}))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    pblocks.capture(pblocks.DATASET_ID, runs / "walk" / "capture", parameters={"from_height": "100"}, request=AbortingNode(chain()))
    pblocks.build(pblocks.DATASET_ID, runs / "walk" / "capture", runs / "walk" / "dataset")
    for name, dataset_id, request in (("records", pstakers.STAKING_ID, data_api), ("paid", pstakers.REWARDS_ID, node)):
        pstakers.capture(dataset_id, runs / name / "capture", parameters={"blocks": "walk"}, request=request, root=runs)
        pstakers.build(dataset_id, runs / name / "capture", runs / name / "dataset")
    make_current_validators(runs)
    return runs


def rows(output: Path) -> list[dict]:
    frame = duckdb.connect().execute("SELECT * FROM read_parquet(?)", [str(next((output / "dataset").glob("*.parquet")))]).fetchdf()
    return [row._asdict() for row in frame.itertuples(index=False)]


def test_catalog_columns_equal_the_backed_up_datasets():
    catalog = {item["id"]: item for item in load_catalog()["datasets"]}
    for dataset_id, (_, columns) in pstaking.SPECS.items():
        assert [field["name"] for field in catalog[dataset_id]["fields"]] == list(columns)


def test_the_counter_replays_onto_the_node_anchor(root):
    output = root / "supply"
    result = pstaking.derive(pstaking.SUPPLY_ID, output, root=root)
    summary = result["build"]["summary"]
    assert summary["end_supply_navax"] == ANCHOR and summary["start_supply_solutions"] >= 1
    start = summary["start_supply_navax"]
    time = datetime.fromtimestamp(chain()[100]["time"], UTC)
    delegation, after = protocol.start_stake(time, 14 * 86400, 25_000_000_000, start)
    (row,) = rows(output)
    assert (row["transaction_hash"], row["previous_block_supply_navax"], row["block_supply_navax"]) == ("T100", start, after)
    assert row["in_block_total_delta_navax"] == delegation and row["supply_before_navax"] == start
    # The auto-renewed validator adds its reward, and the abort of the older stake removes the Data API's 427,836,158.
    assert summary["stakes_closed_unrewarded"] == 1
    assert pstaking.check(output / "capture", output / "dataset", root=root)["status"] == "pass"


def test_stakes_and_rewards_carry_the_share_columns(root):
    delegators = rows(pstaking_run(root, pstaking.DELEGATORS_ID))
    (delegation,) = delegators
    assert delegation["validator_transaction_hash"] == "V1" and delegation["rewarded"] is True
    assert delegation["duration_days"] == 14 and delegation["staked_utxo_count"] == 1
    validators = rows(pstaking_run(root, pstaking.VALIDATORS_ID))
    assert [row["tx_type"] for row in validators] == ["AddAutoRenewedValidatorTx"]
    assert validators[0]["delegation_fee_shares"] == 20_000
    rewards = {row["staking_transaction_hash"]: row for row in rows(pstaking_run(root, pstaking.REWARDS_ID))}
    assert rewards["T100"]["realized_reward_navax"] == 1_586_601_847 and rewards["T100"]["rewarded"] is True
    assert rewards["OLD"]["rewarded"] is False and rewards["OLD"]["potential_reward_navax"] == 427_836_158
    assert rewards["OLD"]["realized_reward_navax"] == 0 and rewards["OLD"]["staking_tx_type"] == "AddPermissionlessDelegatorTx"


def pstaking_run(root: Path, dataset_id: str) -> Path:
    output = root / dataset_id
    pstaking.derive(dataset_id, output, root=root)
    return output


def test_a_walk_without_the_node_anchor_is_refused(root, tmp_path):
    runs = tmp_path / "other"
    pblocks.capture(pblocks.DATASET_ID, runs / "walk" / "capture", parameters={"from_height": "100", "to_height": "103"}, request=AbortingNode(chain()))
    pblocks.build(pblocks.DATASET_ID, runs / "walk" / "capture", runs / "walk" / "dataset")
    with pytest.raises(DataError):
        pstaking.select_inputs(None, runs)


def test_the_replay_needs_records_only_for_older_stakes_that_end_unrewarded(root):
    assert pstakers.staking_hashes("walk", root, "unrewarded-before-walk")[1] == ["OLD"]


def test_an_auto_renewed_cycle_restakes_and_starts_the_next(root):
    output = pstaking_run(root, pstaking.CYCLES_ID)
    first, second = rows(output)
    assert (first["cycle"], first["rewarded"], first["reward_transaction_hash"], first["withdrawn_validation_navax"]) == (1, True, "RA106", 0)
    assert first["restaked_validation_navax"] == first["potential_reward_navax"] > 0
    assert (second["cycle"], second["start_time"]) == (2, first["end_time"]) and second["rewarded"] is pd.NA
    assert second["weight_navax"] == first["weight_navax"] + first["restaked_validation_navax"]
    assert pstaking.check(output / "capture", output / "dataset", root=root)["status"] == "pass"
