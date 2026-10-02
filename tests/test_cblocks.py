"""C-Chain block-fee captures use Data-API-shaped block records and a built gaps run, not network access."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from avalanche_research import cblocks
from avalanche_research.catalog import DataError, canonical_bytes, load_catalog, sha256

HEIGHTS = [100, 101, 205]


def make_gaps_run(root: Path, name: str = "gaps") -> Path:
    capture_dir, dataset_dir = root / name / "capture", root / name / "dataset"
    capture_dir.mkdir(parents=True), dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / "c-chain-block-gaps.parquet"
    duckdb.sql(f"""COPY (SELECT * FROM (VALUES (100, 'absent', DATE '2023-10-06', NULL, NULL), (101, 'absent', DATE '2023-10-06', NULL, NULL), (205, 'short', DATE '2025-03-07', 9, 4))
                   AS t(block_height, kind, date_utc, declared_transactions, distinct_receipts)) TO '{parquet}' (FORMAT PARQUET)""")
    capture_id = "capture:test:gaps"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({"schema_version": "test/v1", "capture_id": capture_id, "dataset_id": cblocks.GAPS_ID, "completed_at": "2026-09-23T00:00:00Z"}))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({"schema_version": "test/v1", "dataset_id": cblocks.GAPS_ID, "source_capture_id": capture_id, "completed_at": "2026-09-23T00:00:00Z",
                                                              "summary": {"rows": 3}, "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}]}))
    return root


def block(height):
    return {"chainId": "43114", "blockNumber": str(height), "blockTimestamp": 1696550401 + height, "blockHash": f"0x{height}", "txCount": 2,
            "baseFee": "25000000000", "gasUsed": str(1000 * height), "gasLimit": "15000000", "gasCost": "0", "parentHash": "0x", "feesSpent": str(10**15 + height), "cumulativeTransactions": "1"}


def fake_request(url, timeout):
    assert url.startswith("https://glacier-api.avax.network/v1/chains/43114/blocks/")
    return json.dumps(block(int(url.rsplit("/", 1)[1]))).encode(), {"http_status": 200, "content_type": "application/json"}


def test_catalog_declares_the_dataset():
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == cblocks.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(cblocks.COLUMNS)


def test_capture_build_check_against_the_gaps_run(tmp_path):
    root = make_gaps_run(tmp_path / "runs")
    capture, dataset = tmp_path / "capture", tmp_path / "dataset"
    receipt = cblocks.capture(cblocks.DATASET_ID, capture, parameters={"gaps": "gaps"}, request=fake_request, root=root)
    assert [item["block_height"] for item in receipt["blocks"]] == HEIGHTS and receipt["blocks_listed"] == 3 and receipt["retries"] == 0
    assert not (capture / cblocks.PROGRESS).exists()
    built = cblocks.build(cblocks.DATASET_ID, capture, dataset)
    assert built["summary"]["rows"] == 3 and built["summary"]["fees_wei"] == 3 * 10**15 + sum(HEIGHTS)
    checked = cblocks.check(capture, dataset, against=root / "gaps" / "dataset")
    assert checked["status"] == "pass" and checked["summary"]["unlisted_blocks"] == 0
    rows = duckdb.sql(f"SELECT block_height, date_utc, fees_wei FROM read_parquet('{dataset / 'c-chain-block-fees.parquet'}') ORDER BY 1").fetchall()
    assert rows[0][0] == 100 and str(rows[0][1]) == "2023-10-06" and int(rows[0][2]) == 10**15 + 100
    only_short = cblocks.capture(cblocks.DATASET_ID, tmp_path / "short", parameters={"gaps": "gaps", "kind": "short"}, request=fake_request, root=root)
    assert [item["block_height"] for item in only_short["blocks"]] == [205]


def test_failed_walk_keeps_lines_and_resumes(tmp_path, monkeypatch):
    monkeypatch.setattr(cblocks, "PAGE_RETRY_SECONDS", 0)
    root = make_gaps_run(tmp_path / "runs")
    calls = {"n": 0}

    def flaky(url, timeout):
        calls["n"] += 1
        if url.endswith("/101") and calls["n"] < 12:
            raise DataError("request failed") from OSError("429")
        return fake_request(url, timeout)

    capture = tmp_path / "capture"
    with pytest.raises(DataError, match="1 blocks kept"):
        cblocks.capture(cblocks.DATASET_ID, capture, parameters={"gaps": "gaps"}, request=flaky, root=root)
    kept = next(tmp_path.glob(".capture.*"))
    receipt = cblocks.capture(cblocks.DATASET_ID, capture, parameters={"gaps": "gaps", "resume": str(kept)}, request=flaky, root=root)
    assert [item["block_height"] for item in receipt["blocks"]] == HEIGHTS and not kept.exists()
    assert cblocks.check(capture)["status"] == "pass"


def test_wrong_block_and_tampered_line_are_rejected(tmp_path):
    root = make_gaps_run(tmp_path / "runs")

    def wrong(url, timeout):
        body, metadata = fake_request(url, timeout)
        value = json.loads(body)
        value["blockNumber"] = "999"
        return json.dumps(value).encode(), metadata

    with pytest.raises(DataError, match="answered block 999"):
        cblocks.capture(cblocks.DATASET_ID, tmp_path / "wrong", parameters={"gaps": "gaps"}, request=wrong, root=root)
    capture = tmp_path / "capture"
    cblocks.capture(cblocks.DATASET_ID, capture, parameters={"gaps": "gaps"}, request=fake_request, root=root)
    raw = capture / cblocks.RAW
    raw.write_bytes(raw.read_bytes().replace(b'"txCount": 2', b'"txCount": 3', 1))
    with pytest.raises(DataError, match="hash or size differs"):
        cblocks.read_rows(capture)


@pytest.mark.parametrize("parameters", [{}, {"gaps": "gaps", "kind": "odd"}, {"gaps": "gaps", "limit": "0"}, {"gaps": "gaps", "block": "1"}])
def test_parameters_are_checked(parameters, tmp_path):
    root = make_gaps_run(tmp_path / "runs")
    with pytest.raises(DataError):
        cblocks.capture_preview(cblocks.DATASET_ID, tmp_path / "capture", parameters, root=root)


def test_parallel_workers_keep_height_order(tmp_path):
    import time as clock
    root = make_gaps_run(tmp_path / "runs")

    def slow_first(url, timeout):
        if url.endswith("/100"):
            clock.sleep(0.05)
        return fake_request(url, timeout)

    capture = tmp_path / "capture"
    receipt = cblocks.capture(cblocks.DATASET_ID, capture, parameters={"gaps": "gaps", "workers": "3"}, request=slow_first, root=root)
    assert [item["block_height"] for item in receipt["blocks"]] == HEIGHTS
    assert cblocks.check(capture)["status"] == "pass"


def test_resume_cuts_back_a_walk_stopped_between_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(cblocks, "PAGE_RETRY_SECONDS", 0)
    root = make_gaps_run(tmp_path / "runs")

    def dies_at_205(url, timeout):
        if url.endswith("/205"):
            raise DataError("request failed") from OSError("reset")
        return fake_request(url, timeout)

    capture = tmp_path / "capture"
    with pytest.raises(DataError, match="2 blocks kept"):
        cblocks.capture(cblocks.DATASET_ID, capture, parameters={"gaps": "gaps"}, request=dies_at_205, root=root)
    kept = next(tmp_path.glob(".capture.*"))
    progress = kept / cblocks.PROGRESS
    progress.write_text("".join(progress.read_text().splitlines(keepends=True)[:-1]))  # the second record never written
    receipt = cblocks.capture(cblocks.DATASET_ID, capture, parameters={"gaps": "gaps", "resume": str(kept)}, request=fake_request, root=root)
    assert [item["block_height"] for item in receipt["blocks"]] == HEIGHTS
    assert cblocks.check(capture)["status"] == "pass"


def node_batch(height, receipt_gas=(21_000, 40_000), prices=(30_000_000_000, 26_000_000_000), header_gas=None, other_hash=False):
    """A node's JSON-RPC batch answer: the header, then one receipt per transaction."""
    header = {"number": hex(height), "hash": f"0x{height:064x}", "timestamp": hex(1696550401 + height), "baseFeePerGas": hex(25_000_000_000),
              "gasUsed": hex(header_gas if header_gas is not None else sum(receipt_gas)), "transactions": [f"0xt{index}" for index in range(len(receipt_gas))]}
    receipts = [{"blockHash": "0xother" if other_hash else header["hash"], "blockNumber": hex(height), "gasUsed": hex(gas), "effectiveGasPrice": hex(price)}
                for gas, price in zip(receipt_gas, prices)]
    return [{"jsonrpc": "2.0", "id": 2, "result": receipts}, {"jsonrpc": "2.0", "id": 1, "result": header}]


def rpc_request(answer):
    def request(url, timeout, body_json=None, content="json"):
        assert url == "https://avalanche-mainnet.gateway.tenderly.co" and content == "json-list"
        assert [item["method"] for item in body_json] == ["eth_getBlockByNumber", "eth_getBlockReceipts"]
        return json.dumps(answer(int(body_json[1]["params"][0], 16))).encode(), {"http_status": 200, "content_type": "application/json"}
    return request


def test_the_receipt_source_computes_fees_and_checks_them_against_the_header(tmp_path):
    definition = next(item for item in load_catalog()["datasets"] if item["id"] == cblocks.RPC_DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(cblocks.COLUMNS)
    root = make_gaps_run(tmp_path / "runs")
    capture, dataset = tmp_path / "capture", tmp_path / "dataset"
    receipt = cblocks.capture(cblocks.RPC_DATASET_ID, capture, parameters={"gaps": "gaps", "workers": "2"}, request=rpc_request(node_batch), root=root)
    assert receipt["dataset_id"] == cblocks.RPC_DATASET_ID and [item["block_height"] for item in receipt["blocks"]] == HEIGHTS
    built = cblocks.build(cblocks.RPC_DATASET_ID, capture, dataset)
    fee = 21_000 * 30_000_000_000 + 40_000 * 26_000_000_000
    assert built["summary"]["fees_wei"] == 3 * fee and built["summary"]["transactions"] == 6
    assert cblocks.check(capture, dataset, against=root / "gaps" / "dataset")["status"] == "pass"
    rows = duckdb.sql(f"SELECT block_height, date_utc, gas_used, fees_wei FROM read_parquet('{dataset / 'c-chain-block-receipt-fees.parquet'}') ORDER BY 1").fetchall()
    assert rows[0][0] == 100 and str(rows[0][1]) == "2023-10-06" and rows[0][2] == 61_000 and int(rows[0][3]) == fee
    with pytest.raises(DataError, match="the capture is of c-chain-rpc"):
        cblocks.build(cblocks.DATASET_ID, capture, tmp_path / "wrong")


@pytest.mark.parametrize(("answer", "message"), [
    (lambda height: node_batch(height, header_gas=1), "do not add to the header's gas"),
    (lambda height: node_batch(height, other_hash=True), "not the header's transactions"),
    (lambda height: node_batch(height, receipt_gas=(21_000,), prices=(1,))[:1] + [{"jsonrpc": "2.0", "id": 1, "result": {**node_batch(height)[1]["result"]}}], "not the header's transactions"),
    (lambda height: node_batch(height + 1), "another block"),
    (lambda height: [{"jsonrpc": "2.0", "id": 1, "error": {"code": -32000}}, {"jsonrpc": "2.0", "id": 2, "result": []}], "did not answer both"),
])
def test_the_receipt_source_refuses_receipts_that_are_not_the_blocks(tmp_path, answer, message):
    root = make_gaps_run(tmp_path / "runs")
    with pytest.raises(DataError, match=message):
        cblocks.capture(cblocks.RPC_DATASET_ID, tmp_path / "capture", parameters={"gaps": "gaps"}, request=rpc_request(answer), root=root)
