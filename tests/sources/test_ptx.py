"""P-Chain transaction captures use node-shaped platform.getTx responses, not network access."""

from __future__ import annotations

import json

import pytest

from avalanche_research.sources import ptx
from avalanche_research.catalog import DataError, load_catalog

AVAX = ptx.AVAX_ASSET_ID


def entry(amount, key="input", asset=AVAX):
    return {"txID": "source", "assetID": asset, key: {"amount": amount}}


def fake_request(url, timeout, body_json):
    assert url == "https://api.avax.network/ext/bc/P" and body_json["method"] == "platform.getTx"
    tx_hash = body_json["params"]["txID"]
    unsigned = {"networkID": 1, "outputs": [entry(475_999_995_865, "output")], "inputs": [], "importedInputs": [entry(476_000_000_000), entry(5, asset="other")]}
    if tx_hash == "export":
        unsigned = {"networkID": 1, "outputs": [entry(10, "output")], "inputs": [entry(1_000_010)], "exportedOutputs": [entry(0, "output")]}
    body = json.dumps({"jsonrpc": "2.0", "id": body_json["id"], "result": {"tx": {"unsignedTx": unsigned, "credentials": [], "id": tx_hash}, "encoding": "json"}}).encode()
    return body, {"http_status": 200, "content_type": "application/json"}


def test_catalog_declares_the_dataset():
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == ptx.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(ptx.COLUMNS)


def test_capture_build_check_and_tamper(tmp_path):
    capture, dataset = tmp_path / "capture", tmp_path / "dataset"
    receipt = ptx.capture(ptx.DATASET_ID, capture, parameters={"hashes": "import1, export"}, request=fake_request)
    assert receipt["hashes"] == ["import1", "export"] and len(receipt["responses"]) == 2
    built = ptx.build(ptx.DATASET_ID, capture, dataset)
    assert built["summary"] == {"rows": 2, "transactions": 2, "burned_navax": 4_135 + 1_000_000, "imports": 1}
    checked = ptx.check(capture, dataset)
    assert checked["status"] == "pass" and checked["summary"]["burned_navax"] == 1_004_135
    _, rows = ptx.read_rows(capture)
    assert rows[0] == ("import1", "ImportTx", 476_000_000_000, 475_999_995_865, 4_135, 1, 1)
    assert rows[1] == ("export", "ExportTx", 1_000_010, 10, 1_000_000, 1, 2)
    raw = capture / "raw" / "tx-00001.json"
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(DataError, match="hash or size differs"):
        ptx.read_rows(capture)


def test_rejects_another_transaction_or_more_output_than_input(tmp_path):
    def wrong(url, timeout, body_json):
        body, metadata = fake_request(url, timeout, body_json)
        value = json.loads(body)
        value["result"]["tx"]["id"] = "someone-else"
        return json.dumps(value).encode(), metadata

    ptx.capture(ptx.DATASET_ID, tmp_path / "wrong", parameters={"hashes": "import1"}, request=wrong)
    with pytest.raises(DataError, match="not the requested transaction"):
        ptx.read_rows(tmp_path / "wrong")

    def inflated(url, timeout, body_json):
        body, metadata = fake_request(url, timeout, body_json)
        value = json.loads(body)
        value["result"]["tx"]["unsignedTx"]["outputs"] = [entry(476_000_000_001, "output")]
        return json.dumps(value).encode(), metadata

    ptx.capture(ptx.DATASET_ID, tmp_path / "inflated", parameters={"hashes": "import1"}, request=inflated)
    with pytest.raises(DataError, match="creates more AVAX"):
        ptx.read_rows(tmp_path / "inflated")


@pytest.mark.parametrize("parameters", [{}, {"hashes": ""}, {"hashes": "a,a"}, {"hashes": "a", "block": "1"}, {"hashes": "not base58!"}])
def test_requires_distinct_hashes(parameters, tmp_path):
    with pytest.raises(DataError):
        ptx.capture_preview(ptx.DATASET_ID, tmp_path / "capture", parameters)
