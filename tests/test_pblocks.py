"""The P-Chain block walk, against a fake node."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from avalanche_research import pblocks
from avalanche_research.catalog import DataError, load_catalog

AVAX = pblocks.AVAX_ASSET_ID
BASE = {"networkID": 1, "blockchainID": "11111111111111111111111111111111LpoYY", "memo": "0x"}


def utxo(amount: int, key: str = "output") -> dict:
    return {"assetID": AVAX, key: {"amount": amount}}


def delegator_tx() -> dict:
    return {**BASE, "inputs": [utxo(30_000_000_000, "input")], "outputs": [utxo(4_000_000_000)], "stake": [utxo(25_000_000_000)],
            "subnetID": "11111111111111111111111111111111LpoYY", "validator": {"nodeID": "NodeID-A"}, "rewardsOwner": {}}


def auto_renewed_tx() -> dict:
    return {**BASE, "inputs": [utxo(2_001_000_000_000, "input")], "outputs": [], "stake": [utxo(2_000_000_000_000)], "nodeID": "NodeID-B",
            "signer": {}, "validationRewardsOwner": {}, "delegationRewardsOwner": {}, "validatorAuthority": {},
            "delegationShares": 20_000, "autoCompoundRewardShares": 1_000_000, "period": 1_209_600}


def blocks(count: int, start: int = 100, unknown_at: int | None = None) -> dict[int, dict]:
    """Standard, proposal, commit, repeating; the parent of each is the one below."""
    made = {}
    for height in range(start, start + count):
        block = {"id": f"B{height}", "parentID": f"B{height - 1}", "height": height, "time": 1_790_000_000 + height}
        kind = (height - start) % 3
        if kind == 0:
            body = auto_renewed_tx() if height == start + 3 else delegator_tx()
            if height == unknown_at:
                body["surprise"] = 1
            block["txs"] = [{"id": f"T{height}", "unsignedTx": body, "credentials": []}]
        elif kind == 1:
            block |= {"txs": [], "tx": {"id": f"R{height}", "unsignedTx": {"txID": f"T{height - 1}"}, "credentials": []}}
        made[height] = block
    return made


class FakeNode:
    def __init__(self, chain: dict[int, dict], head: int | None = None):
        self.chain, self.head, self.calls = chain, max(chain) if head is None else head, []

    def __call__(self, url, timeout, body_json=None, content="json"):
        method, params = body_json["method"], body_json["params"]
        if method == "platform.getHeight":
            return json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"height": str(self.head)}}).encode(), {}
        height = int(params["height"])
        self.calls.append((height, params["encoding"]))
        if params["encoding"] == "hex":
            block = "0x0000" + f"{32 if self.chain[height].get('txs') == [] and 'tx' not in self.chain[height] else 31:08x}" + "00" * 60
        else:
            block = self.chain[height]
        return json.dumps({"jsonrpc": "2.0", "id": body_json["id"], "result": {"block": block, "encoding": params["encoding"]}}).encode(), {}


def rows(dataset_dir: Path) -> list[tuple]:
    return duckdb.connect().execute(
        "SELECT block_height, block_type, tx_type, input_navax, output_navax, staked_navax FROM read_parquet(?) ORDER BY block_height",
        [str(dataset_dir / f"{pblocks.TABLE}.parquet")]).fetchall()


def test_catalog_declares_the_columns():
    fields = next(item for item in load_catalog()["datasets"] if item["id"] == pblocks.DATASET_ID)["fields"]
    assert [field["name"] for field in fields] == list(pblocks.COLUMNS)


def test_walk_builds_one_row_per_transaction_and_per_commit(tmp_path):
    node = FakeNode(blocks(6))
    receipt = pblocks.capture(pblocks.DATASET_ID, tmp_path / "capture", parameters={"from_height": "100"}, request=node)
    assert (receipt["from_height"], receipt["to_height"]) == (100, 105)
    # Only the transaction-less blocks are read again in hex.
    assert [height for height, encoding in node.calls if encoding == "hex"] == [102, 105]
    pblocks.build(pblocks.DATASET_ID, tmp_path / "capture", tmp_path / "dataset")
    assert rows(tmp_path / "dataset") == [
        (100, "standard", "AddPermissionlessDelegatorTx", 30_000_000_000, 4_000_000_000, 25_000_000_000),
        (101, "proposal", "RewardValidatorTx", 0, 0, 0),
        (102, "commit", None, None, None, None),
        (103, "standard", "AddAutoRenewedValidatorTx", 2_001_000_000_000, 0, 2_000_000_000_000),
        (104, "proposal", "RewardValidatorTx", 0, 0, 0),
        (105, "commit", None, None, None, None),
    ]
    checked = pblocks.check(tmp_path / "capture", tmp_path / "dataset")
    assert checked["status"] == "pass", checked["findings"]
    assert checked["summary"]["blocks_by_type"] == {"standard": 2, "proposal": 2, "commit": 2, "abort": 0}


def test_unknown_transaction_stops_the_walk_and_resume_continues(tmp_path):
    chain = blocks(9, unknown_at=106)
    with pytest.raises(DataError, match="fields no known type declares") as failure:
        pblocks.capture(pblocks.DATASET_ID, tmp_path / "capture", parameters={"from_height": "100", "workers": "1"}, request=FakeNode(chain))
    kept = str(failure.value).rsplit(" kept at ", 1)[1]
    chain[106]["txs"][0]["unsignedTx"].pop("surprise")
    node = FakeNode(chain)
    pblocks.capture(pblocks.DATASET_ID, tmp_path / "capture", parameters={"from_height": "100", "resume": kept}, request=node)
    assert min(height for height, _ in node.calls) == 106
    assert pblocks.check(tmp_path / "capture")["status"] == "pass"


def test_extend_reads_only_the_new_heights(tmp_path):
    chain = blocks(9)
    pblocks.capture(pblocks.DATASET_ID, tmp_path / "first", parameters={"from_height": "100"}, request=FakeNode(chain, head=104))
    node = FakeNode(chain)
    receipt = pblocks.capture(pblocks.DATASET_ID, tmp_path / "second", parameters={"extend": str(tmp_path / "first")}, request=node)
    assert (receipt["from_height"], receipt["to_height"]) == (100, 108)
    assert {height for height, _ in node.calls} == set(range(105, 109))
    assert pblocks.check(tmp_path / "second")["status"] == "pass"


def test_a_broken_parent_link_stops_the_build(tmp_path):
    chain = blocks(3)
    chain[101]["parentID"] = "elsewhere"
    pblocks.capture(pblocks.DATASET_ID, tmp_path / "capture", parameters={"from_height": "100"}, request=FakeNode(chain))
    assert "do not name the block below" in pblocks.check(tmp_path / "capture")["findings"][0]
    with pytest.raises(DataError, match="do not name the block below"):
        pblocks.build(pblocks.DATASET_ID, tmp_path / "capture", tmp_path / "dataset")


def test_an_empty_standard_block_is_one_row_without_a_transaction(tmp_path):
    chain = blocks(3)
    chain[101] = {key: value for key, value in chain[101].items() if key != "tx"}
    pblocks.capture(pblocks.DATASET_ID, tmp_path / "capture", parameters={"from_height": "100"}, request=FakeNode(chain))
    pblocks.build(pblocks.DATASET_ID, tmp_path / "capture", tmp_path / "dataset")
    assert rows(tmp_path / "dataset")[1] == (101, "standard", None, None, None, None)


def test_bare_and_based_types_are_told_apart():
    assert pblocks.tx_type({"txID": "x"}) == "RewardValidatorTx"
    assert pblocks.tx_type({**BASE, "inputs": [], "outputs": []}) == "BaseTx"
    with pytest.raises(DataError):
        pblocks.tx_type({**BASE, "inputs": [], "outputs": [], "txID": "x"})
