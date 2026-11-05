"""Minipool records read by eth_call at one block, from a fake C-Chain node."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from avalanche_research.catalog import DataError
from avalanche_research.domain.keys import keccak256
from avalanche_research.sources import minipools
from avalanche_research.sources.catx import cb58

HEIGHT = 1_000
MULTISIG = "0x" + "b4" * 20
OWNERS = ["0x" + "a1" * 20, "0x" + "a1" * 20, "0x" + "c3" * 20]
NODE_BYTES = [bytes([index + 1]) * 20 for index in range(3)]


def word(value: int | bytes) -> bytes:
    return value.rjust(32, b"\0") if isinstance(value, bytes) else value.to_bytes(32, "big")


def struct(index: int) -> str:
    """One ABI-encoded Minipool struct: the tuple offset, 22 head words, then the dynamic BLS bytes."""
    head = [
        word(index), word(NODE_BYTES[index]), word(4), word(15 * 86400), word(20_000),
        word(bytes.fromhex(OWNERS[index][2:])), word(bytes.fromhex(MULTISIG[2:])),
        word(1_000 * 10**18), word(1_000 * 10**18), word(1_000 * 10**18), word(32 * 22),
        hashlib.sha256(bytes([index])).digest(), word(0 if index == 0 else 1_700_000_000), word(1_700_000_100),
        word(1_700_000_200), word(1_700_000_200 + 15 * 86400), word(5 * 10**18), word(0), word(0),
        word(2 * 10**18), word(3 * 10**18), word(keccak256(b"Artifact")),
    ]
    tail = word(0)
    return "0x" + (word(32) + b"".join(head) + tail).hex()


def fake_request(url, timeout, body_json, content="json", count=3, height=HEIGHT):
    assert url == "https://api.avax.network/ext/bc/C/rpc"

    def answer(call):
        method, params = call["method"], call["params"]
        if method == "eth_blockNumber":
            result = hex(height)
        elif method == "eth_getBlockByNumber":
            result = {"number": params[0], "hash": "0xblock", "timestamp": hex(1_760_000_000)}
        else:
            data = params[0]["data"]
            assert params[0]["to"] == minipools.MANAGER and params[1] == hex(height)
            if data == minipools.COUNT_SELECTOR:
                result = "0x" + word(count).hex()
            else:
                result = struct(int(data[10:], 16))
        return {"jsonrpc": "2.0", "id": call["id"], "result": result}

    value = [answer(call) for call in reversed(body_json)] if isinstance(body_json, list) else answer(body_json)
    return json.dumps(value).encode(), {"http_status": 200, "content_type": "application/json"}


def test_selectors_are_the_keccak_of_the_two_view_functions():
    assert minipools.COUNT_SELECTOR == "0x" + keccak256(b"getMinipoolCount()").hex()[:8]
    assert minipools.RECORD_SELECTOR == "0x" + keccak256(b"getMinipool(int256)").hex()[:8]


def test_catalog_declares_the_columns():
    from avalanche_research.core.catalog import dataset, load_catalog

    assert [field["name"] for field in dataset(load_catalog(), minipools.DATASET_ID)["fields"]] == list(minipools.COLUMNS)


def test_capture_reads_every_index_at_one_block_and_builds_and_checks(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(minipools, "BATCH_SIZE", 2)
    pauses = []
    capture_dir, dataset_dir = tmp_path / "capture", tmp_path / "dataset"
    receipt = minipools.capture(minipools.DATASET_ID, capture_dir, request=fake_request, sleep=pauses.append)
    assert receipt["block_number"] == HEIGHT and receipt["minipool_count"] == 3 and receipt["calls"] == 4
    # block number, block, count, then two batches of record calls, with a pause before each batch
    assert len(receipt["responses"]) == 5 and pauses == [minipools.PAUSE_SECONDS] * 2
    built = minipools.build(minipools.DATASET_ID, capture_dir, dataset_dir)
    assert built["summary"]["rows"] == 3 and built["summary"]["owners"] == 2
    assert built["summary"]["multisig_addresses"] == [MULTISIG]
    rows = duckdb.connect().execute(
        "SELECT * FROM read_parquet(?) ORDER BY minipool_index", [str(dataset_dir / f"{minipools.TABLE}.parquet")]).fetchdf()
    first = rows.iloc[0]
    assert first.node_id == "NodeID-" + cb58(NODE_BYTES[0]) and first.status == "Finished"
    assert first.owner == OWNERS[0] and first.delegation_fee_rate == 0.02 and first.duration_days == 15
    assert first.tx_id == cb58(hashlib.sha256(bytes([0])).digest()) and first.error_code is None
    assert str(first.creation_time) == "NaT" and str(rows.iloc[1].creation_time) == "2023-11-14 22:13:20"
    assert first.hardware_provider == "0x" + keccak256(b"Artifact").hex()
    assert (rows.block_number == HEIGHT).all()
    checked = minipools.check(capture_dir, dataset_dir)
    assert checked["status"] == "pass", checked["findings"]


def test_the_block_parameter_skips_the_newest_block_and_bounds_every_call(tmp_path: Path):
    receipt = minipools.capture(minipools.DATASET_ID, tmp_path / "capture", parameters={"block": "777"},
                                request=lambda *a, **k: fake_request(*a, **k, height=777), sleep=lambda _: None)
    assert receipt["block_number"] == 777 and not any("block-number" in item["path"] for item in receipt["responses"])


def test_a_call_at_another_block_or_a_changed_response_is_refused(tmp_path: Path):
    capture_dir = tmp_path / "capture"
    minipools.capture(minipools.DATASET_ID, capture_dir, request=fake_request, sleep=lambda _: None)
    receipt = json.loads((capture_dir / "capture.json").read_text())
    batch = next(item for item in receipt["responses"] if isinstance(item["request_json"], list))
    batch["request_json"][0]["params"][1] = hex(HEIGHT - 1)
    (capture_dir / "capture.json").write_text(json.dumps(receipt))
    with pytest.raises(DataError, match="capture's block"):
        minipools.read_rows(capture_dir)

    other = tmp_path / "other"
    minipools.capture(minipools.DATASET_ID, other, request=fake_request, sleep=lambda _: None)
    raw = other / "raw" / "records-00000.json"
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(DataError, match="hash or size differs"):
        minipools.read_rows(other)


@pytest.mark.parametrize("parameters", [{"block": "0"}, {"block": "a"}, {"date": "today"}])
def test_parameters_are_a_positive_block_or_nothing(parameters, tmp_path):
    with pytest.raises(DataError):
        minipools.capture_preview(minipools.DATASET_ID, tmp_path / "capture", parameters)
