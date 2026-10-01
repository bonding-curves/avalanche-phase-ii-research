"""The staker captures, against a fake Data API and a fake node, over a walk built from the fake chain."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_pblocks import FakeNode, blocks

from avalanche_research import datasets, pblocks, pstakers
from avalanche_research.catalog import DataError, load_catalog

# A reward UTXO the node returned on 2026-09-29 for 2eLyKrgXUPBLikPkTwUHii4FB7tXQ53wfgqaGaPJxuDeE6Rhjx: 1,586,601,847 nAVAX.
REAL_UTXO = ("0x0000d87dafd6e6d9de16244d397926ce4913844e52ad1e33f04c92ce70e2000e5e0a0000000221e67317cbc4be2aeb00677ad6462778a8f52274"
             "b9d605df2591b23027a87dff00000007000000005e919f77000000000000000000000001000000015630756a9d9ce85da21753054d411aa8ab3eb59bf8903b2d")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    pblocks.capture(pblocks.DATASET_ID, runs / "walk" / "capture", parameters={"from_height": "100"}, request=FakeNode(blocks(6)))
    pblocks.build(pblocks.DATASET_ID, runs / "walk" / "capture", runs / "walk" / "dataset")
    return runs


def data_api(url, timeout):
    tx_hash = url.rsplit("/", 1)[1]
    return json.dumps({"txHash": tx_hash, "txType": "AddPermissionlessDelegatorTx", "nodeId": "NodeID-A", "blockNumber": "90",
                       "blockTimestamp": 1789000000, "startTimestamp": 1789000000, "endTimestamp": 1790209600,
                       "estimatedReward": "427836158", "rewardTxHash": "R"}).encode(), {}


def node(url, timeout, body_json=None):
    tx_hash = body_json["params"]["txID"]
    utxos = [REAL_UTXO] if tx_hash == "T100" else []
    return json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"numFetched": str(len(utxos)), "utxos": utxos, "encoding": "hex"}}).encode(), {}


def test_catalog_declares_the_columns():
    catalog = {item["id"]: item for item in load_catalog()["datasets"]}
    for dataset_id in pstakers.DATASET_IDS:
        assert [field["name"] for field in catalog[dataset_id]["fields"]] == list(pstakers.COLUMNS[dataset_id])


def test_both_captures_read_the_stakes_the_walk_closes(root):
    hashes = pstakers.staking_hashes(datasets.readings(pstakers.READS, {"blocks": "walk"}, root)["blocks"])
    assert hashes == ["T100", "T103"]
    for dataset_id, request in ((pstakers.STAKING_ID, data_api), (pstakers.REWARDS_ID, node)):
        out = root / dataset_id
        pstakers.capture(dataset_id, out / "capture", parameters={"blocks": "walk"}, request=request, readings=datasets.readings(pstakers.READS, {"blocks": "walk"}, root))
        pstakers.build(dataset_id, out / "capture", out / "dataset")
        checked = pstakers.check(out / "capture", out / "dataset")
        assert checked["status"] == "pass", checked["findings"]
    _, rows = pstakers.read_rows(root / pstakers.REWARDS_ID / "capture")
    assert rows == [("T100", 1, 1_586_601_847), ("T103", 0, 0)]
    _, rows = pstakers.read_rows(root / pstakers.STAKING_ID / "capture")
    assert rows[0][7] == 427_836_158 and rows[0][3] == 90


def test_a_reward_output_of_another_asset_is_refused():
    other = REAL_UTXO[:78] + "00" + REAL_UTXO[80:]
    with pytest.raises(DataError, match="not AVAX"):
        pstakers.reward_outputs([other], "x")


def test_extend_reads_only_stakes_the_earlier_capture_lacks(root):
    first = root / "first"
    pstakers.capture(pstakers.REWARDS_ID, first / "capture", parameters={"blocks": "walk"}, request=node, readings=datasets.readings(pstakers.READS, {"blocks": "walk"}, root))
    asked = []

    def counting(url, timeout, body_json=None):
        asked.append(body_json["params"]["txID"])
        return node(url, timeout, body_json)

    pstakers.capture(pstakers.REWARDS_ID, root / "second" / "capture", parameters={"blocks": "walk", "extend": str(first / "capture")},
                     request=counting, readings=datasets.readings(pstakers.READS, {"blocks": "walk"}, root))
    assert asked == []
    assert pstakers.read_rows(root / "second" / "capture")[1] == pstakers.read_rows(first / "capture")[1]


def test_a_capture_is_given_its_walk_and_reads_no_dataset_code(tmp_path):
    """IB4: the command line resolves the walk run. The capture refuses a run it was not given."""
    assert not hasattr(pstakers, "datasets")
    with pytest.raises(DataError, match="not resolved"):
        pstakers.capture_preview(pstakers.STAKING_ID, tmp_path / "capture", {"blocks": "walk"})
