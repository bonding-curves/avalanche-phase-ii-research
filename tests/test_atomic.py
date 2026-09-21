"""C-Chain atomic capture checks use provider-shaped pages, not network access."""

import json
from datetime import UTC, datetime

import duckdb
import pytest

from avalanche_research import atomic
from avalanche_research.catalog import DataError


def stamp(day, hour=0):
    return int(datetime(2026, 9, day, hour, tzinfo=UTC).timestamp())


def asset(amount):
    return {"assetId": atomic.AVAX_ASSET_ID, "symbol": "AVAX", "denomination": 9, "amount": str(amount)}


def transaction(identity, timestamp, unlocked, created):
    kind = "ImportTx" if identity == "a" else "ExportTx"
    return {
        "txHash": identity, "txType": kind,
        "timestamp": timestamp, "blockHeight": 100 + ord(identity), "blockHash": f"0x{identity}",
        "amountUnlocked": [asset(unlocked)], "amountCreated": [asset(created)],
        **({"consumedUtxos": [{"asset": asset(unlocked)}], "evmOutputs": [{"asset": asset(created)}]}
           if kind == "ImportTx" else {"evmInputs": [{"asset": asset(unlocked)}], "emittedUtxos": [{"asset": asset(created)}]}),
    }


def pages():
    return [
        {"transactions": [transaction("a", stamp(17, 1), 110, 100), transaction("b", stamp(16, 15), 230, 200)], "nextPageToken": "next"},
        {"transactions": [transaction("c", stamp(16, 9), 350, 300), transaction("d", stamp(15, 23), 470, 400)], "nextPageToken": None},
    ]


def capture_sample(tmp_path, source_pages=None):
    remaining = iter(source_pages or pages())

    def request(url, timeout):
        page = next(remaining)
        return json.dumps(page).encode(), {"http_status": 200, "content_type": "application/json"}

    capture_dir = tmp_path / "capture"
    atomic.capture(atomic.DATASET_ID, capture_dir, parameters={"start": "2026-09-16", "end": "2026-09-17"}, request=request)
    return capture_dir


def test_atomic_capture_build_check(tmp_path):
    capture_dir = capture_sample(tmp_path)
    dataset_dir = tmp_path / "dataset"
    built = atomic.build(atomic.DATASET_ID, capture_dir, dataset_dir)
    checked = atomic.check(capture_dir, dataset_dir)
    assert built["summary"] == {"rows": 2, "import_rows": 0, "export_rows": 2, "distinct_blocks": 2, "burned_navax": 80}
    assert checked["status"] == "pass" and checked["summary"]["pages"] == 2
    rows = duckdb.sql(f"SELECT transaction_hash, burned_navax FROM read_parquet('{dataset_dir / 'c-chain-atomic-burn.parquet'}') ORDER BY 1").fetchall()
    assert rows == [("b", 30), ("c", 50)]


def test_atomic_rejects_disconnected_or_changed_page(tmp_path):
    capture_dir = capture_sample(tmp_path)
    receipt = json.loads((capture_dir / "capture.json").read_text())
    receipt["responses"][1]["request_page_token"] = "wrong"
    (capture_dir / "capture.json").write_text(json.dumps(receipt))
    with pytest.raises(DataError, match="disconnected page"):
        atomic.read_rows(capture_dir)


def test_atomic_rejects_negative_burn_and_missing_history(tmp_path):
    broken = pages()
    broken[0]["transactions"][1]["amountCreated"] = [asset(231)]
    broken[0]["transactions"][1]["emittedUtxos"] = [{"asset": asset(231)}]
    capture_dir = capture_sample(tmp_path, broken)
    with pytest.raises(DataError, match="invalid atomic AVAX balance"):
        atomic.read_rows(capture_dir)
    with pytest.raises(DataError, match="exceeded max_pages"):
        atomic.capture(
            atomic.DATASET_ID, tmp_path / "short", parameters={"start": "2026-09-16", "end": "2026-09-17", "max_pages": "1"},
            request=lambda url, timeout: (json.dumps(pages()[0]).encode(), {"http_status": 200}),
        )


def test_atomic_rejects_tampered_body(tmp_path):
    capture_dir = capture_sample(tmp_path)
    (capture_dir / "raw/page-00002.json").write_text("{}")
    with pytest.raises(DataError, match="hash or size differs"):
        atomic.read_rows(capture_dir)


def test_complete_empty_window_is_zero_burn(tmp_path):
    source_pages = [
        {"transactions": [transaction("a", stamp(17, 1), 110, 100)], "nextPageToken": "next"},
        {"transactions": [transaction("b", stamp(15, 23), 230, 200)], "nextPageToken": None},
    ]
    capture_dir = capture_sample(tmp_path, source_pages)
    dataset_dir = tmp_path / "dataset"
    assert atomic.build(atomic.DATASET_ID, capture_dir, dataset_dir)["summary"]["burned_navax"] == 0
    assert atomic.check(capture_dir, dataset_dir)["status"] == "pass"
