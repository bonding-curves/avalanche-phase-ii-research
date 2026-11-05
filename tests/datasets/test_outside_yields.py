"""The filled Aave WAVAX series and the three outside yields, built from small synthetic runs."""

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
from avalanche_research.datasets.derived import aave_wavax_filled as aave
from avalanche_research.datasets.derived import outside_yields as yields

WAVAX, AVAX, SAVAX = yields.WAVAX, yields.NATIVE_AVAX, yields.SAVAX


def make_run(root: Path, name: str, dataset_id: str, table: str, sql: str) -> None:
    capture_dir, dataset_dir = root / name / "capture", root / name / "dataset"
    capture_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    parquet = dataset_dir / f"{table}.parquet"
    duckdb.connect().execute(f"COPY ({sql}) TO '{parquet}' (FORMAT PARQUET)")
    capture_id = f"capture:test:{name}"
    queries = [{"snowflake_query_id": "01c8-fixture", "sql_sha256": "f" * 64}] if dataset_id.startswith("allium.") else []
    (capture_dir / "capture.json").write_bytes(canonical_bytes({
        "schema_version": "test-capture/v1", "capture_id": capture_id, "dataset_id": dataset_id,
        "completed_at": "2026-11-05T00:00:00Z", "contract_sha256": "0" * 64, "queries": queries,
    }))
    body = parquet.read_bytes()
    (dataset_dir / "build.json").write_bytes(canonical_bytes({
        "schema_version": "test-build/v1", "dataset_id": dataset_id, "source_capture_id": capture_id,
        "completed_at": "2026-11-05T00:00:00Z", "summary": {"rows": 1},
        "outputs": [{"path": parquet.name, "bytes": len(body), "sha256": sha256(body)}],
    }))


def text(item) -> str:
    if item is None:
        return "NULL"
    if isinstance(item, datetime):
        return f"TIMESTAMP '{item:%Y-%m-%d %H:%M:%S}'"
    if isinstance(item, date):
        return f"DATE '{item}'"
    return f"'{item}'" if isinstance(item, str) else repr(item)


def values(rows: list[tuple]) -> str:
    return ", ".join("(" + ", ".join(text(item) for item in row) + ")" for row in rows)


def days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


DEFILLAMA_DAYS = [day for day in days(date(2023, 12, 20), date(2025, 12, 5))
                  if not (date(2024, 1, 4) <= day <= date(2024, 1, 10) or date(2024, 10, 9) <= day <= date(2025, 3, 9))]


def defillama_rate(day: date) -> float:
    return 2.0 + 0.3 * math.sin(day.toordinal() / 9)


def lending_rows(first: date, last: date, aave_offset: float = 0.01) -> list[tuple]:
    """Aave v3 WAVAX updates near DefiLlama's rate, an Aave v2 WAVAX market at 4% with a third of the supply, and an
    unrated BENQI AVAX market."""
    rows = []
    for day in days(first, last):
        for hour in (1, 13):
            stamp = datetime(day.year, day.month, day.day, hour)
            rows.append(("aave", "aave_v3", "0xv3", WAVAX, "WAVAX", stamp, f"v3-{day}-{hour}", defillama_rate(day) + aave_offset, 2e6))
            rows.append(("aave", "aave_v2", "0xv2", WAVAX, "WAVAX", stamp, f"v2-{day}-{hour}", 4.0, 1e6))
            rows.append(("benqi", "compound_v2", "0xqi", AVAX, "AVAX", stamp, f"qi-{day}-{hour}", None, 5e6))
            rows.append(("aave", "aave_v3", "0xusdc", "0xusdc", "USDC", stamp, f"u-{day}-{hour}", 5.0, 9e7))
    return rows


def make_inputs(root: Path) -> None:
    opportunity = [(day, "aave-wavax", defillama_rate(day), "defillama.pool-history") for day in DEFILLAMA_DAYS]
    opportunity += [(day, "aave-usdc", 5.0, "defillama.pool-history") for day in DEFILLAMA_DAYS[:5]]
    make_run(root, "opportunity", "derived.opportunity-costs-daily", "opportunity-costs-daily",
             f"SELECT * FROM (VALUES {values(opportunity)}) AS t(date_utc, series, rate_pct, source_dataset)")
    lending = lending_rows(date(2023, 12, 1), date(2025, 4, 30))
    make_run(root, "lending", "allium.lending-interest-rates", "lending-interest-rates",
             f"SELECT * FROM (VALUES {values(lending)}) AS t(project, protocol, market_address, token_address, token_symbol, "
             "block_timestamp, unique_id, supply_apy, supplied_amount)")


def make_yield_inputs(root: Path, post_cut: float = 1.0) -> None:
    make_inputs(root)
    aave.derive(aave.DATASET_ID, root / "aave-filled", {"derived.opportunity-costs-daily": "opportunity",
                                                        "allium.lending-interest-rates": "lending"}, root=root)
    prices = []
    for offset, day in enumerate(days(date(2023, 10, 1), date(2025, 11, 25))):
        stamp = datetime(day.year, day.month, day.day)
        late = post_cut if stamp > datetime(2025, 11, 19) else 1.0
        prices.append((AVAX, stamp, 30.0 * late))
        prices.append((SAVAX, stamp, 30.0 * 1.1 * math.exp(0.06 * offset / 365) * late))
    make_run(root, "prices", "allium.prices-hourly", "prices-hourly",
             f"SELECT * FROM (VALUES {values(prices)}) AS t(address, hour_utc, price_usd)")
    benchmark = [(day, "DTB3", 0.05, "FRED DTB3 bfill" if day == date(2024, 1, 1) else "FRED DTB3") for day in days(date(2024, 1, 1), date(2025, 11, 25))]
    make_run(root, "benchmark", "af.benchmark-rates-daily", "benchmark-rates-daily",
             f"SELECT * FROM (VALUES {values(benchmark)}) AS t(date_utc, rate_id, rate_annual, source)")
    tbill = [(day, 4.0) for day in days(date(2020, 8, 1), date(2025, 11, 25)) if day.weekday() < 5]
    make_run(root, "tbill", "fred.tbill-3m-daily", "tbill-3m-daily",
             f"SELECT * FROM (VALUES {values(tbill)}) AS t(date_utc, discount_rate_pct)")
    funding = [(datetime(day.year, day.month, day.day, hour), day, 0.0001 * late)
               for day in days(date(2020, 9, 23), date(2025, 11, 25)) for hour in (0, 8, 16)
               for late in [post_cut if day >= date(2025, 11, 19) else 1.0]]
    make_run(root, "funding", "binance.avax-usdt-perp-funding", "avax-usdt-perp-funding",
             f"SELECT * FROM (VALUES {values(funding)}) AS t(funding_time, observation_date, funding_rate_per_8h)")


AAVE_PINNED = {"derived.opportunity-costs-daily": "opportunity", "allium.lending-interest-rates": "lending"}
YIELD_PINNED = {"allium.lending-interest-rates": "lending", "derived.aave-wavax-filled": "aave-filled",
                "allium.prices-hourly": "prices", "af.benchmark-rates-daily": "benchmark", "fred.tbill-3m-daily": "tbill",
                "binance.avax-usdt-perp-funding": "funding"}


def table(output: Path, name: str) -> dict[date, dict]:
    frame = duckdb.connect().execute("SELECT * FROM read_parquet(?)", [str(output / "dataset" / f"{name}.parquet")]).fetchdf()
    frame = frame.astype(object).where(frame.notna(), None)
    return {row.date_utc.date(): row._asdict() for row in frame.itertuples(index=False)}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    make_inputs(tmp_path)
    return tmp_path


def test_aave_fill_keeps_defillama_and_fills_both_windows_from_allium(root):
    output = root / "filled"
    result = aave.derive(aave.DATASET_ID, output, AAVE_PINNED, root=root)
    rows = table(output, aave.TABLE)
    summary = result["build"]["summary"]
    assert summary["filled_days"] == 7 + 152 and summary["days_without_rate"] == 0
    assert rows[date(2024, 1, 5)]["source"] == aave.ALLIUM and rows[date(2024, 1, 5)]["rate_pct"] == pytest.approx(defillama_rate(date(2024, 1, 5)) + 0.01)
    assert rows[date(2024, 1, 3)]["source"] == aave.DEFILLAMA and rows[date(2024, 1, 3)]["rate_pct"] == defillama_rate(date(2024, 1, 3))
    assert rows[date(2024, 1, 3)]["allium_updates"] == 2
    assert date(2025, 12, 5) in rows and rows[date(2025, 12, 5)]["source"] == aave.DEFILLAMA
    shared = summary["agreement"]["review_window"]
    assert shared["days"] == 60 and shared["mean_difference_pp"] == pytest.approx(0.01)
    assert result["capture"]["inputs"][1]["snowflake_query_id"] == "01c8-fixture"
    check = aave.check(output / "capture", output / "dataset", root=root)
    assert check["status"] == "pass", check["findings"]


def test_aave_check_finds_a_changed_defillama_value(root):
    output = root / "filled"
    aave.derive(aave.DATASET_ID, output, AAVE_PINNED, root=root)
    parquet = output / "dataset" / f"{aave.TABLE}.parquet"
    duckdb.connect().execute(f"COPY (SELECT * REPLACE (CASE WHEN date_utc = DATE '2024-09-02' THEN 9.0 ELSE rate_pct END AS rate_pct) "
                             f"FROM read_parquet('{parquet}')) TO '{parquet}' (FORMAT PARQUET)")
    findings = aave.check(output / "capture", output / "dataset", root=root)["findings"]
    assert any("DefiLlama days changed" in item for item in findings) and any("rebuild" in item for item in findings)


def test_aave_check_reports_disagreement_on_the_shared_days(tmp_path):
    make_inputs(tmp_path)
    far = lending_rows(date(2023, 12, 1), date(2025, 4, 30), aave_offset=0.5)
    make_run(tmp_path, "lending-far", "allium.lending-interest-rates", "lending-interest-rates",
             f"SELECT * FROM (VALUES {values(far)}) AS t(project, protocol, market_address, token_address, token_symbol, "
             "block_timestamp, unique_id, supply_apy, supplied_amount)")
    output = tmp_path / "filled"
    aave.derive(aave.DATASET_ID, output, {**AAVE_PINNED, "allium.lending-interest-rates": "lending-far"}, root=tmp_path)
    findings = aave.check(output / "capture", output / "dataset", root=tmp_path)["findings"]
    assert any("Allium differs from DefiLlama" in item for item in findings)


def test_outside_yields_read_only_days_before_the_decision(tmp_path):
    make_yield_inputs(tmp_path)
    assert yields.HELD_BACK_CUT == date(2025, 11, 19)
    output = tmp_path / "yields"
    result = yields.derive(yields.DATASET_ID, output, YIELD_PINNED, root=tmp_path)
    rows = table(output, yields.TABLE)
    assert min(rows) == date(2021, 2, 2) and max(rows) == date(2025, 11, 18) and len(rows) == (yields.HELD_BACK_CUT - yields.FIRST_DAY).days
    day = rows[date(2024, 6, 2)]
    before = date(2024, 6, 1)
    # Aave v3 holds 2e6 at its rate, Aave v2 1e6 at 4%; BENQI's 5e6 has no supply rate.
    composite = (2e6 * (defillama_rate(before) + 0.01) + 1e6 * 4.0) / 3e6
    assert day["lending_pct"] == pytest.approx(composite) and day["lending_source"] == "allium-composite"
    assert day["lending_markets"] == 2 and day["lending_supplied_avax"] == 3e6 and day["lending_unrated_supplied_avax"] == 5e6
    window = [(2e6 * (defillama_rate(before - timedelta(days=k)) + 0.01) + 4e6) / 3e6 for k in range(7)]
    assert day["lending_median_7d_pct"] == pytest.approx(sorted(window)[3]) and day["lending_days_7d"] == 7
    assert day["savax_growth_30d_pct"] == pytest.approx((math.exp(0.06 * 30 / 365) ** (365 / 30) - 1) * 100)
    assert day["savax_exchange_rate"] > 1.1 and day["savax_days_7d"] == 7
    funding = 0.0001 * 3 * 365 * 100
    assert day["bill_pct"] == pytest.approx(5.0) and day["bill_source"] == "af-benchmark"
    assert day["funding_pct"] == pytest.approx(funding) and day["funding_events"] == 3
    assert day["hedged_bill_pct"] == pytest.approx(5.0 - funding) and day["hedged_median_7d_pct"] == pytest.approx(5.0 - funding)
    # Before the benchmark table, and on its filled-back first day, the bill rate is FRED's last published value.
    assert rows[date(2023, 6, 5)]["bill_source"] == "fred-tbill" and rows[date(2023, 6, 5)]["bill_pct"] == 4.0
    assert rows[date(2024, 1, 2)]["bill_source"] == "fred-tbill" and rows[date(2024, 1, 3)]["bill_source"] == "af-benchmark"
    # Before Allium's lending rows the composite is empty; the median needs four of seven days.
    assert rows[date(2023, 11, 1)]["lending_pct"] is None and rows[date(2023, 12, 3)]["lending_median_7d_pct"] is None
    assert rows[date(2023, 12, 6)]["lending_days_7d"] == 5 and rows[date(2023, 12, 6)]["lending_median_7d_pct"] is not None
    assert result["build"]["summary"]["days_by_lending_source"]["allium-composite"] > 0


def test_outside_yields_fall_back_to_the_filled_aave_rate(tmp_path):
    make_yield_inputs(tmp_path)
    rows = table(_derive(tmp_path), yields.TABLE)
    # Allium's synthetic lending stops on 2025-04-30; DefiLlama's Aave series continues.
    day = rows[date(2025, 6, 2)]
    assert day["lending_source"] == "aave-wavax-filled" and day["lending_pct"] == pytest.approx(defillama_rate(date(2025, 6, 1)))
    assert day["lending_markets"] == 0


def _derive(root: Path, name: str = "yields") -> Path:
    yields.derive(yields.DATASET_ID, root / name, YIELD_PINNED, root=root)
    return root / name


def test_outside_yields_ignore_data_after_the_cut_and_check_passes(tmp_path, tmp_path_factory):
    make_yield_inputs(tmp_path)
    output = _derive(tmp_path)
    other = tmp_path_factory.mktemp("late")
    make_yield_inputs(other, post_cut=5.0)
    assert table(_derive(other), yields.TABLE) == table(output, yields.TABLE)
    result = yields.check(output / "capture", output / "dataset", root=tmp_path)
    assert result["status"] == "pass", result["findings"]


def test_catalog_declares_both_tables_and_their_inputs():
    catalog = load_catalog()
    derived = {item["id"]: item["dataset_id"] for item in next(s for s in catalog["sources"] if s["id"] == "derived")["inputs"]}
    for module in (aave, yields):
        definition = dataset(catalog, module.DATASET_ID)
        assert [field["name"] for field in definition["fields"]] == list(module.TABLE_COLUMNS)
        assert {input_id: derived[input_id] for input_id in definition["input_ids"]} == module.INPUTS
    with pytest.raises(DataError, match="avalanche data derive"):
        yields.capture(yields.DATASET_ID, Path("x"))
    with pytest.raises(DataError, match="not an input"):
        aave.derive(aave.DATASET_ID, Path("x"), {"derived.staking-periods": "y"})
