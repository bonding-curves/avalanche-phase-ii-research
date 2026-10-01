"""C-Chain atomic transaction captures use node-shaped avax.getAtomicTx responses built from real codec bytes, not network access."""

from __future__ import annotations

import hashlib
import json
import struct

import pytest

from avalanche_research.sources import catx
from avalanche_research.catalog import DataError, load_catalog

AVAX = bytes.fromhex("21e67317cbc4be2aeb00677ad6462778a8f52274b9d605df2591b23027a87dff")
OTHER = bytes(32)


def signed_import(inputs: list[tuple[bytes, int]], outputs: list[tuple[bytes, int]], kind: int = 0) -> bytes:
    """A signed C-Chain import in codec version 0: header, imported inputs, EVM outputs, and one credential."""
    body = struct.pack(">HII", 0, kind, 1) + bytes(32) + bytes(32)
    body += struct.pack(">I", len(inputs))
    for index, (asset, amount) in enumerate(inputs):
        body += bytes(32) + struct.pack(">I", index) + asset + struct.pack(">IQI", 5, amount, 1) + struct.pack(">I", 0)
    body += struct.pack(">I", len(outputs))
    for asset, amount in outputs:
        body += bytes(20) + struct.pack(">Q", amount) + asset
    return body + struct.pack(">III", 1, 9, 1) + bytes(65)


TRANSACTIONS = {
    "partial": signed_import([(AVAX, 1_000_000_000), (AVAX, 3_000_000_000), (OTHER, 7)], [(AVAX, 3_999_000_000), (OTHER, 7)]),
    "even": signed_import([(AVAX, 500_000_000)], [(AVAX, 500_000_000)]),
}
HASHES = {catx.cb58(hashlib.sha256(signed).digest()): signed for signed in TRANSACTIONS.values()}
PARTIAL, EVEN = (catx.cb58(hashlib.sha256(TRANSACTIONS[name]).digest()) for name in ("partial", "even"))


def response(signed: bytes, request_id: int, height: int = 111_616) -> bytes:
    text = "0x" + (signed + hashlib.sha256(signed).digest()[-4:]).hex()
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": {"tx": text, "encoding": "hex", "blockHeight": str(height)}}).encode()


def fake_request(url, timeout, body_json):
    assert url == "https://api.avax.network/ext/bc/C/avax" and body_json["method"] == "avax.getAtomicTx"
    return response(HASHES[body_json["params"]["txID"]], body_json["id"]), {"http_status": 200, "content_type": "application/json"}


def test_catalog_declares_the_dataset():
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == catx.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(catx.COLUMNS)


def test_cb58_matches_the_avax_asset_id():
    assert catx.cb58(AVAX) == catx.AVAX_ASSET_ID


def test_capture_build_check_and_tamper(tmp_path):
    capture, dataset = tmp_path / "capture", tmp_path / "dataset"
    receipt = catx.capture(catx.DATASET_ID, capture, parameters={"hashes": f"{PARTIAL}, {EVEN}"}, request=fake_request)
    assert receipt["hashes"] == [PARTIAL, EVEN]
    built = catx.build(catx.DATASET_ID, capture, dataset)
    assert built["summary"] == {"rows": 2, "transactions": 2, "burned_navax": 1_000_000, "imports": 2}
    assert catx.check(capture, dataset)["status"] == "pass"
    _, rows = catx.read_rows(capture)
    assert rows[0] == (PARTIAL, "ImportTx", 111_616, 4_000_000_000, 3_999_000_000, 1_000_000, 2, 1)
    assert rows[1] == (EVEN, "ImportTx", 111_616, 500_000_000, 500_000_000, 0, 1, 1)
    raw = capture / "raw" / "tx-00001.json"
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(DataError, match="hash or size differs"):
        catx.read_rows(capture)


@pytest.mark.parametrize(("change", "message"), [
    (lambda signed, request_id: response(TRANSACTIONS["even"], request_id), "not the requested transaction"),
    (lambda signed, request_id: response(signed, request_id).replace(b'", "encoding"', b'00", "encoding"'), "hex checksum"),
    (lambda signed, request_id: response(signed_import([(AVAX, 1)], [(AVAX, 2)]), request_id), "not the requested transaction"),
])
def test_rejects_another_transaction_or_a_broken_checksum(tmp_path, change, message):
    def request(url, timeout, body_json):
        return change(HASHES[body_json["params"]["txID"]], body_json["id"]), {"http_status": 200}

    catx.capture(catx.DATASET_ID, tmp_path / "capture", parameters={"hashes": PARTIAL}, request=request)
    with pytest.raises(DataError, match=message):
        catx.read_rows(tmp_path / "capture")


def test_decoding_refuses_exports_and_reads_every_byte():
    with pytest.raises(DataError, match="not an import"):
        catx.decode_import(signed_import([(AVAX, 1)], [(AVAX, 1)], kind=1), "x")
    with pytest.raises(DataError, match="unread bytes"):
        catx.decode_import(TRANSACTIONS["even"] + b"\0", "x")
    with pytest.raises(DataError, match="ends early"):
        catx.decode_import(TRANSACTIONS["even"][:-1], "x")


def test_rejects_an_import_that_creates_more_than_it_consumes(tmp_path):
    inflated = signed_import([(AVAX, 1)], [(AVAX, 2)])
    inflated_hash = catx.cb58(hashlib.sha256(inflated).digest())

    def request(url, timeout, body_json):
        return response(inflated, body_json["id"]), {"http_status": 200}

    catx.capture(catx.DATASET_ID, tmp_path / "capture", parameters={"hashes": inflated_hash}, request=request)
    with pytest.raises(DataError, match="creates more AVAX"):
        catx.read_rows(tmp_path / "capture")


@pytest.mark.parametrize("parameters", [{}, {"hashes": ""}, {"hashes": "a,a"}, {"hashes": "a", "block": "1"}, {"hashes": "not base58!"}])
def test_requires_distinct_hashes(parameters, tmp_path):
    with pytest.raises(DataError):
        catx.capture_preview(catx.DATASET_ID, tmp_path / "capture", parameters)
