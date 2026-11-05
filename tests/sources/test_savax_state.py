"""The daily sAVAX state read at each day's last block, with a fake node and a small block run."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import duckdb
import pytest

from avalanche_research.core.catalog import DataError, canonical_bytes, dataset, load_catalog, sha256
from avalanche_research.domain.keys import keccak256
from avalanche_research.sources import savax_state as state

DAYS = 4


def block_run(tmp_path, days=DAYS, captured="2022-01-31T06:00:00Z"):
    run = tmp_path / "blocks"
    (run / "capture").mkdir(parents=True)
    (run / "dataset").mkdir()
    parquet = run / "dataset" / "c-chain-daily-last-blocks.parquet"
    rows = ", ".join(
        f"(DATE '{state.FIRST_DAY + timedelta(days=k)}', {1000 + 10 * k}, '0xhash{k}', "
        f"TIMESTAMP '{state.FIRST_DAY + timedelta(days=k)} 23:59:58', {991 + 10 * k}, 10)" for k in range(days + 1))
    duckdb.connect().execute(f"COPY (SELECT * FROM (VALUES {rows}) AS t(date_utc, last_block_number, last_block_hash, "
                             f"last_block_timestamp, first_block_number, blocks)) TO '{parquet}' (FORMAT PARQUET)")
    (run / "capture" / "capture.json").write_bytes(canonical_bytes({"capture_id": "capture:test:blocks", "completed_at": captured}))
    body = parquet.read_bytes()
    (run / "dataset" / "build.json").write_bytes(canonical_bytes({
        "dataset_id": state.BLOCKS_ID, "source_capture_id": "capture:test:blocks",
        "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}]}))
    return run / "dataset"


def word(value: int) -> str:
    return "0x" + value.to_bytes(32, "big").hex()


def node(supply=lambda k: (100 + k) * 10**18, rate=lambda k: 10**18 + k * 10**15, hash_of=lambda k: f"0xhash{k}"):
    """A fake node that answers each batch: the block, the supply, the pooled AVAX and the rate of one share."""
    sent = []

    def request(url, timeout, body_json=None, content=None):
        assert url == "https://api.avax.network/ext/bc/C/rpc" and content == "json-list"
        sent.append(body_json)
        answers = []
        for item in body_json:
            k, place = divmod(item["id"], state.CALLS_PER_DAY)
            stamp = int(datetime.combine(state.FIRST_DAY + timedelta(days=k), datetime.min.time(), UTC).timestamp()) + 86398
            result = [{"number": hex(1000 + 10 * k), "hash": hash_of(k), "timestamp": hex(stamp)},
                      word(supply(k)), word(supply(k) * rate(k) // 10**18), word(rate(k))][place]
            answers.append({"jsonrpc": "2.0", "id": item["id"], "result": result})
        return json.dumps(answers).encode(), {"status": 200}

    return request, sent


def capture(tmp_path, request, name="run"):
    run = tmp_path / name
    blocks = block_run(tmp_path) if not (tmp_path / "blocks").exists() else tmp_path / "blocks" / "dataset"
    state.capture(state.DATASET_ID, run / "capture", parameters={"blocks": str(blocks)}, request=request, sleep=lambda _: None)
    return run


def test_selectors_are_the_keccak_of_the_three_view_functions():
    assert state.SUPPLY_SELECTOR == "0x" + keccak256(b"totalSupply()").hex()[:8]
    assert state.POOLED_SELECTOR == "0x" + keccak256(b"totalPooledAvax()").hex()[:8]
    assert state.RATE_SELECTOR == "0x" + keccak256(b"getPooledAvaxByShares(uint256)").hex()[:8]


def test_catalog_fields_match_the_table():
    assert [field["name"] for field in dataset(load_catalog(), state.DATASET_ID)["fields"]] == list(state.COLUMNS)


def test_capture_reads_every_day_before_the_block_run_capture_and_the_build_passes(tmp_path):
    request, sent = node()
    run = capture(tmp_path, request)
    receipt = json.loads((run / "capture" / "capture.json").read_text())
    assert receipt["days"] == DAYS and receipt["first_day"] == "2022-01-27" and receipt["last_day"] == "2022-01-30"
    assert receipt["calls"] == DAYS * 4 and len(sent) == 2 and receipt["blocks_input"]["run"] == "blocks"
    built = state.build(state.DATASET_ID, run / "capture", run / "dataset")
    assert built["summary"]["rows"] == DAYS and built["summary"]["rate_falls"] == 0
    rows = duckdb.connect().execute(
        f"SELECT date_utc, block_number, savax_supply, avax_per_savax, held_back FROM read_parquet('{run / 'dataset' / 'savax-state-daily.parquet'}')"
        " ORDER BY 1").fetchall()
    assert rows[0] == (date(2022, 1, 27), 1000, 100.0, 1.0, False) and rows[3][3] == pytest.approx(1.003)
    result = state.check(run / "capture", run / "dataset")
    assert result["status"] == "pass", result["findings"]


def test_check_finds_a_differing_hash_a_falling_rate_and_a_changed_response(tmp_path):
    request, _ = node(rate=lambda k: 10**18 - k * 10**15, hash_of=lambda k: "0xother" if k == 2 else f"0xhash{k}")
    run = capture(tmp_path, request)
    result = state.check(run / "capture")
    assert result["findings"] == ["1 days read a block whose hash differs from Allium's"]
    assert result["summary"]["rate_falls"] == 3
    batch = run / "capture" / "raw" / "batch-00000.json"
    batch.write_bytes(batch.read_bytes().replace(b"0xother", b"0xhash2"))
    with pytest.raises(DataError, match="hash or size differs"):
        state.check(run / "capture")


def test_capture_refuses_a_block_run_missing_a_day_or_another_parameter(tmp_path):
    request, _ = node()
    blocks = block_run(tmp_path, captured="2022-02-05T00:00:00Z")
    with pytest.raises(DataError, match="holds 5 of the 9 days"):
        state.capture(state.DATASET_ID, tmp_path / "x", parameters={"blocks": str(blocks)}, request=request, sleep=lambda _: None)
    with pytest.raises(DataError, match="the one parameter is blocks"):
        state.capture_preview(state.DATASET_ID, tmp_path / "x", {"blocks_run": "x"})


def test_a_batch_the_node_times_out_on_is_sent_again(tmp_path):
    request, sent = node()
    tries = {"left": 2}

    def flaky(url, timeout, body_json=None, content=None):
        if tries["left"]:
            tries["left"] -= 1
            return json.dumps([{"jsonrpc": "2.0", "id": item["id"], "error": {"code": -32002, "message": "request timed out"}}
                               for item in body_json]).encode(), {"status": 200}
        return request(url, timeout, body_json=body_json, content=content)

    run = capture(tmp_path, flaky)
    receipt = json.loads((run / "capture" / "capture.json").read_text())
    assert receipt["retries"] == 2 and state.check(run / "capture")["status"] == "pass"
