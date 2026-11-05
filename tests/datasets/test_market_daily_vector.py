"""The daily market vector, built from small synthetic runs of its five inputs."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from avalanche_research.core.catalog import (
    DataError,
    canonical_bytes,
    dataset,
    load_catalog,
    sha256,
)
from avalanche_research.datasets.derived import market_daily_vector as vector

AVAX, WAVAX = vector.NATIVE_AVAX, vector.WAVAX
CUT = datetime(2025, 11, 19)


def make_run(root: Path, name: str, dataset_id: str, table: str, sql: str, rows: int) -> None:
    capture_dir, dataset_dir = root / name / "capture", root / name / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / f"{table}.parquet"
    duckdb.connect().execute(f"COPY ({sql}) TO '{parquet}' (FORMAT PARQUET)")
    capture_id = f"capture:test:{name}"
    (capture_dir / "capture.json").write_bytes(canonical_bytes({
        "schema_version": "test-capture/v1", "capture_id": capture_id, "dataset_id": dataset_id,
        "completed_at": "2026-11-05T00:00:00Z", "contract_sha256": "0" * 64,
    }))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({
        "schema_version": "test-build/v1", "dataset_id": dataset_id, "source_capture_id": capture_id,
        "completed_at": "2026-11-05T00:00:00Z", "summary": {"rows": rows},
        "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}],
    }))


def path(start: datetime, hours: int, drift: float, wiggle: float = 0.004) -> list[tuple[datetime, float]]:
    """An hourly path whose log price drifts, swings slowly, and wiggles from hour to hour, so days differ."""
    return [(start + timedelta(hours=h), 30 * math.exp(drift * h + 0.03 * math.sin(h / 5) + (wiggle if h % 2 else -wiggle)))
            for h in range(hours)]


def values(rows: list[tuple]) -> str:
    def text(item):
        if item is None:
            return "NULL"
        if isinstance(item, datetime):
            return f"TIMESTAMP '{item:%Y-%m-%d %H:%M:%S}'"
        if isinstance(item, date):
            return f"DATE '{item}'"
        return repr(item) if not isinstance(item, str) else f"'{item}'"
    return ", ".join("(" + ", ".join(text(item) for item in row) + ")" for row in rows)


SERVICE_START = datetime(2022, 6, 1, 1)
DEX_PATHS = path(datetime(2021, 2, 2, 15), 24 * 5, 0.001) + path(datetime(2022, 5, 28), 24 * 4 + 1, -0.002)
SERVICE_PATH = path(SERVICE_START, 24 * 5 - 1, 0.0015)
LATE_PATH = path(datetime(2025, 11, 15), 24 * 6, 0.001)  # runs past the cut to 2025-11-20 23:00


def service_rows(post_cut_spike: float = 1.0, drop_native: datetime | None = None) -> list[tuple]:
    rows = []
    for stamp, price in SERVICE_PATH + LATE_PATH:
        price = price * (post_cut_spike if stamp > CUT else 1.0)
        if stamp != drop_native:
            rows.append(("AVAX", AVAX, stamp, price))
        rows.append(("WAVAX", WAVAX, stamp, price * 1.0002))
    return rows


def make_inputs(root: Path, post_cut_spike: float = 1.0, drop_native: datetime | None = None, reference_scale: float = 1.0) -> None:
    service = service_rows(post_cut_spike, drop_native)
    make_run(root, "prices", "allium.prices-hourly", "prices-hourly",
             f"SELECT * FROM (VALUES {values(service)}) AS t(token, address, hour_utc, price_usd)", len(service))
    # The exchange table also covers service days, at a level 1% off, so its realised variance is computed there too.
    dex = [(WAVAX, stamp, price) for stamp, price in DEX_PATHS] + [(WAVAX, stamp, price * 1.01) for stamp, price in SERVICE_PATH]
    make_run(root, "dex", "allium.dex-token-prices-hourly", "dex-token-prices-hourly",
             f"SELECT * FROM (VALUES {values(dex)}) AS t(address, hour_utc, price_usd)", len(dex))
    days = [date(2021, 2, 1) + timedelta(days=offset) for offset in range((date(2025, 11, 22) - date(2021, 2, 1)).days)]
    gas = [(day, 50.0 + offset % 7) for offset, day in enumerate(days)]
    make_run(root, "gas", "af.economy-gas-fees-daily", "economy-gas-fees-daily",
             f"SELECT * FROM (VALUES {values(gas)}) AS t(date_utc, gas_used_avax)", len(gas))
    btc = [(day, 40_000 * math.exp(0.001 * offset), None if offset == 0 else 0.001) for offset, day in enumerate(days)]
    make_run(root, "btc", "coinmetrics.btc-usd-daily", "btc-usd-daily",
             f"SELECT * FROM (VALUES {values(btc)}) AS t(observation_date, price_usd, log_return)", len(btc))
    hourly = dict(DEX_PATHS + SERVICE_PATH + LATE_PATH)
    reference = [(stamp + timedelta(seconds=3), stamp.date(), price * reference_scale) for stamp, price in hourly.items()
                 if stamp.hour == 0]
    make_run(root, "defillama", "defillama.avax-price-daily", "avax-price-daily",
             f"SELECT * FROM (VALUES {values(reference)}) AS t(observed_at, observation_date, price_usd)", len(reference))


PINNED = {"allium.prices-hourly": "prices", "allium.dex-token-prices-hourly": "dex", "af.economy-gas-fees-daily": "gas",
          "coinmetrics.btc-usd-daily": "btc", "defillama.avax-price-daily": "defillama"}


def derive(root: Path, name: str = "vector") -> tuple[Path, dict]:
    output = root / name
    return output, vector.derive(vector.DATASET_ID, output, PINNED, root=root)


def table(output: Path) -> dict[date, dict]:
    frame = duckdb.connect().execute(
        "SELECT * FROM read_parquet(?)", [str(output / "dataset" / f"{vector.TABLE}.parquet")]).fetchdf()
    frame = frame.astype(object).where(frame.notna(), None)
    return {row.date_utc.date(): row._asdict() for row in frame.itertuples(index=False)}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    make_inputs(tmp_path)
    return tmp_path


def test_the_cut_is_the_held_back_date_and_no_row_reaches_it(root):
    assert vector.HELD_BACK_CUT == date(2025, 11, 19)
    output, result = derive(root)
    rows = table(output)
    assert max(rows) == date(2025, 11, 18) and min(rows) == date(2021, 2, 2)
    assert len(rows) == (vector.HELD_BACK_CUT - vector.FIRST_DAY).days == result["build"]["summary"]["rows"]
    assert result["capture"]["parameters"]["held_back_cut"] == "2025-11-19"


def test_close_return_and_realised_variance_follow_the_hourly_prices(root):
    rows = table(derive(root)[0])
    prices = dict(LATE_PATH)
    day = rows[date(2025, 11, 16)]
    close, previous = prices[datetime(2025, 11, 17)], prices[datetime(2025, 11, 16)]
    expected = sum(math.log(prices[datetime(2025, 11, 16) + timedelta(hours=h)] / prices[datetime(2025, 11, 16) + timedelta(hours=h - 1)]) ** 2
                   for h in range(1, 25))
    assert day["avax_close_usd"] == pytest.approx(close) and day["avax_close_at"] == datetime(2025, 11, 17)
    assert day["avax_log_return"] == pytest.approx(math.log(close / previous))
    assert day["realised_variance"] == pytest.approx(expected) and day["hourly_returns"] == 24
    assert day["price_source"] == "prices-hourly-avax"
    assert day["btc_log_return"] == 0.001 and day["log_gas_burn"] == pytest.approx(math.log(day["gas_burn_avax"]))
    # The last day closes on the price stamped at the cut's first instant, 24:00 of 18 November.
    assert rows[date(2025, 11, 18)]["avax_close_usd"] == pytest.approx(prices[CUT])


def test_the_exchange_price_fills_the_days_before_the_service_and_no_return_crosses_tables(root):
    rows = table(derive(root)[0])
    first = rows[date(2021, 2, 2)]
    assert first["price_source"] == "dex-wavax" and first["avax_log_return"] is None and first["hourly_returns"] == 9
    switch = rows[date(2022, 6, 1)]
    assert switch["price_source"] == "prices-hourly-avax" and switch["hourly_returns"] == 23
    assert rows[date(2022, 5, 31)]["price_source"] == "dex-wavax" and rows[date(2022, 5, 31)]["hourly_returns"] == 24
    assert switch["dex_hourly_returns"] == 24 and switch["dex_realised_variance"] is not None
    gap = rows[date(2023, 1, 1)]
    assert gap["avax_close_usd"] is None and gap["price_source"] is None and gap["hourly_returns"] == 0


def test_wavax_fills_a_missing_native_hour_and_marks_the_day(tmp_path):
    make_inputs(tmp_path, drop_native=datetime(2025, 11, 16, 5))
    rows = table(derive(tmp_path)[0])
    assert rows[date(2025, 11, 16)]["price_source"] == "prices-hourly-wavax" and rows[date(2025, 11, 16)]["hourly_returns"] == 24
    assert rows[date(2025, 11, 17)]["price_source"] == "prices-hourly-avax"


def test_prices_after_the_cut_change_nothing(root, tmp_path_factory):
    before = table(derive(root)[0])
    other = tmp_path_factory.mktemp("spiked")
    make_inputs(other, post_cut_spike=3.0)
    assert table(derive(other)[0]) == before


def test_check_passes_and_rebuilds_from_cut_inputs(root):
    output, _ = derive(root)
    result = vector.check(output / "capture", output / "dataset", root=root)
    assert result["status"] == "pass", result["findings"]
    assert result["summary"]["reference"]["service"]["share_within_2pct"] == 1.0
    assert result["summary"]["reference"]["exchange"]["days"] > 0


def test_check_reports_a_reference_far_from_the_closes(tmp_path):
    make_inputs(tmp_path, reference_scale=1.05)
    output, _ = derive(tmp_path)
    findings = vector.check(output / "capture", output / "dataset", root=tmp_path)["findings"]
    assert any("service closes lie within 2%" in item for item in findings)
    assert any("exchange closes lie within 2%" in item for item in findings)


def test_check_finds_a_changed_build_and_refuses_against(root):
    output, _ = derive(root)
    parquet = output / "dataset" / f"{vector.TABLE}.parquet"
    duckdb.connect().execute(f"COPY (SELECT * REPLACE (avax_close_usd * 2 AS avax_close_usd) FROM read_parquet('{parquet}')) TO '{parquet}' (FORMAT PARQUET)")
    findings = vector.check(output / "capture", output / "dataset", root=root)["findings"]
    assert any("output hash" in item for item in findings) and any("rebuild from the recorded inputs" in item for item in findings)
    with pytest.raises(DataError, match="no --against"):
        vector.check(output / "capture", output / "dataset", against=root, root=root)


def test_catalog_fields_match_the_table_and_inputs_are_declared():
    catalog = load_catalog()
    definition = dataset(catalog, vector.DATASET_ID)
    assert [field["name"] for field in definition["fields"]] == list(vector.TABLE_COLUMNS)
    derived = next(item for item in catalog["sources"] if item["id"] == "derived")
    declared = {item["id"]: item["dataset_id"] for item in derived["inputs"]}
    assert {input_id: declared[input_id] for input_id in definition["input_ids"]} == vector.INPUTS


def test_derive_refuses_an_unknown_input_and_fetch(root):
    with pytest.raises(DataError, match="not an input"):
        vector.derive(vector.DATASET_ID, root / "x", {"derived.staking-periods": "y"}, root=root)
    with pytest.raises(DataError, match="avalanche data derive"):
        vector.capture(vector.DATASET_ID, root / "y")
