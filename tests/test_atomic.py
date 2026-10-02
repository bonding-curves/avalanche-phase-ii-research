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
    assert built["summary"] == {"rows": 2, "import_rows": 0, "export_rows": 2, "distinct_blocks": 2, "burned_navax": 80, "unsettled_rows": 0}
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


def test_an_import_with_missing_inputs_is_kept_unsettled(tmp_path):
    """The Data API lists some 2021 imports with fewer consumed UTXOs than they spent: the burn is null, not negative."""
    source_pages = pages()
    short = transaction("a", stamp(16, 9), 0, 500)
    short["consumedUtxos"] = []
    source_pages[1]["transactions"][0] = short
    capture_dir = capture_sample(tmp_path, source_pages)
    dataset_dir = tmp_path / "dataset"
    built = atomic.build(atomic.DATASET_ID, capture_dir, dataset_dir)
    assert built["summary"]["unsettled_rows"] == 1 and built["summary"]["burned_navax"] == 30
    assert atomic.check(capture_dir, dataset_dir)["status"] == "pass"
    rows = duckdb.sql(f"SELECT transaction_hash, unlocked_navax, created_navax, burned_navax FROM read_parquet('{dataset_dir / 'c-chain-atomic-burn.parquet'}') ORDER BY 1").fetchall()
    assert rows == [("a", 0, 500, None), ("b", 230, 200, 30)]


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


def test_failed_walk_keeps_pages_and_resumes(tmp_path, monkeypatch):
    monkeypatch.setattr(atomic, "PAGE_RETRY_SECONDS", 0)
    served = pages()
    calls = {"n": 0}

    def flaky(url, timeout):
        calls["n"] += 1
        if "pageToken=next" in url and calls["n"] < 10:
            raise DataError("request failed") from OSError("connection reset")
        page = served[1] if "pageToken=next" in url else served[0]
        return json.dumps(page).encode(), {"http_status": 200, "content_type": "application/json"}

    capture_dir = tmp_path / "capture"
    window = {"start": "2026-09-16", "end": "2026-09-17"}
    with pytest.raises(DataError, match="after 8 attempts; 1 pages kept"):
        atomic.capture(atomic.DATASET_ID, capture_dir, parameters=window, request=flaky)
    kept = next(tmp_path.glob(".capture.*"))
    assert (kept / "raw" / "page-00001.json").is_file() and not capture_dir.exists()
    receipt = atomic.capture(atomic.DATASET_ID, capture_dir, parameters={**window, "resume": str(kept)}, request=flaky)
    assert receipt["resumed_pages"] == 1 and receipt["retries"] == 0 and len(receipt["responses"]) == 2 and not kept.exists()
    assert not (capture_dir / atomic.PROGRESS).exists()
    assert atomic.check(capture_dir)["status"] == "pass"
    with pytest.raises(DataError, match="cannot resume"):
        atomic.capture(atomic.DATASET_ID, tmp_path / "again", parameters={**window, "resume": str(capture_dir)}, request=flaky)


def test_retried_page_counts_in_the_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(atomic, "PAGE_RETRY_SECONDS", 0)
    dropped = []
    served = pages()

    def flaky(url, timeout):
        if "pageToken=next" in url and not dropped:
            dropped.append(url)
            raise DataError("request failed") from OSError("connection reset")
        page = served[1] if "pageToken=next" in url else served[0]
        return json.dumps(page).encode(), {"http_status": 200, "content_type": "application/json"}

    receipt = atomic.capture(atomic.DATASET_ID, tmp_path / "capture", parameters={"start": "2026-09-16", "end": "2026-09-17"}, request=flaky)
    assert receipt["retries"] == 1 and len(receipt["responses"]) == 2


def test_listing_may_end_before_a_start_at_the_first_c_block(tmp_path):
    source_pages = [{"transactions": [transaction("a", stamp(17, 1), 110, 100), transaction("b", stamp(16, 15), 230, 200)], "nextPageToken": None}]
    remaining = iter(source_pages)
    request = lambda url, timeout: (json.dumps(next(remaining)).encode(), {"http_status": 200})
    with pytest.raises(DataError, match="ended before the requested start"):
        atomic.capture(atomic.DATASET_ID, tmp_path / "short", parameters={"start": "2026-09-16", "end": "2026-09-17"}, request=request)
    remaining = iter(source_pages)
    capture_dir = tmp_path / "history"
    receipt = atomic.capture(atomic.DATASET_ID, capture_dir, parameters={"start": "2020-09-23", "end": "2026-09-17"}, request=request)
    assert receipt["end_of_listing"] is True
    checked = atomic.check(capture_dir)
    assert checked["status"] == "pass" and checked["summary"]["end_of_listing"] is True and checked["summary"]["rows"] == 1


def test_pause_between_pages_is_applied(tmp_path, monkeypatch):
    slept = []
    monkeypatch.setattr(atomic.time, "sleep", lambda seconds: slept.append(seconds))
    capture_dir = tmp_path / "capture"
    remaining = iter(pages())
    request = lambda url, timeout: (json.dumps(next(remaining)).encode(), {"http_status": 200})
    atomic.capture(atomic.DATASET_ID, capture_dir, parameters={"start": "2026-09-16", "end": "2026-09-17", "pause": "0.5"}, request=request)
    assert slept == [0.5]
    with pytest.raises(DataError, match="pause"):
        atomic.capture_preview(atomic.DATASET_ID, tmp_path / "x", {"start": "2026-09-16", "end": "2026-09-17", "pause": "-1"})
