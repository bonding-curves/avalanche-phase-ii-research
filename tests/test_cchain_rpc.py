from __future__ import annotations

import json
from pathlib import Path

import pytest

from avalanche_research import cchain_rpc
from avalanche_research.catalog import DataError


def fake_request(url, timeout, body_json):
    assert url == "https://api.avax.network/ext/bc/C/rpc" and timeout == 20
    method = body_json["method"]
    if method == "eth_getBlockByNumber":
        result = {
            "number": "0xa", "hash": "0xblock", "timestamp": "0x5f5a1000",
            "transactions": ["0xaaa", "0xbbb"],
        }
    else:
        index = body_json["id"] - 1
        result = {
            "transactionHash": ["0xaaa", "0xbbb"][index],
            "blockHash": "0xblock", "blockNumber": "0xa",
            "transactionIndex": hex(index), "gasUsed": "0x5208",
            "effectiveGasPrice": hex(1_000_000_000 + index),
        }
    body = json.dumps({"jsonrpc": "2.0", "id": body_json["id"], "result": result}).encode()
    return body, {"http_status": 200, "content_type": "application/json"}


def test_c_receipt_gap_capture_build_check_and_tamper(tmp_path: Path):
    capture = tmp_path / "capture"
    dataset = tmp_path / "dataset"
    receipt = cchain_rpc.capture(cchain_rpc.DATASET_ID, capture, parameters={"block": "10"}, request=fake_request)
    assert len(receipt["responses"]) == 3
    built = cchain_rpc.build(cchain_rpc.DATASET_ID, capture, dataset)
    expected = 21_000 * 1_000_000_000 + 21_000 * 1_000_000_001
    assert built["summary"] == {"block_height": 10, "transactions": 2, "burned_wei": expected}
    checked = cchain_rpc.check(capture, dataset)
    assert checked["status"] == "pass" and checked["summary"]["burned_wei"] == expected

    raw = capture / "raw" / "receipt-00000.json"
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(DataError, match="hash or size differs"):
        cchain_rpc.read_rows(capture)


def test_c_receipt_gap_rejects_a_receipt_from_another_block(tmp_path: Path):
    def wrong_block(url, timeout, body_json):
        body, metadata = fake_request(url, timeout, body_json)
        value = json.loads(body)
        if body_json["method"] == "eth_getTransactionReceipt":
            value["result"]["blockHash"] = "0xwrong"
        return json.dumps(value).encode(), metadata

    capture = tmp_path / "capture"
    cchain_rpc.capture(cchain_rpc.DATASET_ID, capture, parameters={"block": "10"}, request=wrong_block)
    with pytest.raises(DataError, match="does not belong"):
        cchain_rpc.build(cchain_rpc.DATASET_ID, capture, tmp_path / "dataset")


@pytest.mark.parametrize("parameters", [{}, {"block": "0"}, {"block": "a"}, {"block": "10", "date": "today"}])
def test_c_receipt_gap_requires_one_positive_block(parameters, tmp_path):
    with pytest.raises(DataError):
        cchain_rpc.capture_preview(cchain_rpc.DATASET_ID, tmp_path / "capture", parameters)
