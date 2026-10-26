"""Qualified figure adoption uses byte-bound sources and explicit native clocks."""

import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import duckdb
import pandas as pd
import pytest
from bokeh.models import Div


@pytest.fixture
def exhibit(monkeypatch):
    directory = Path(__file__).parents[1] / "scripts" / "figures"
    monkeypatch.syspath_prepend(str(directory))
    spec = importlib.util.spec_from_file_location("opportunity_figure_test", directory / "opportunity_costs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def frames(exhibit):
    day = pd.Timestamp("2026-09-28")
    raw = pd.DataFrame({
        "date_utc": [day] * 4,
        "series": ["native-14d", "native-365d", "savax", "tbill-3m"],
        "rate_pct": [4.2, 5.1, 4.4, 3.5],
        "native_supply_basis": [exhibit.NATIVE_SUPPLY_BASIS] * 4,
        "native_quote_at": [day] * 4,
        "native_supply_navax": [Decimal(450_000_000 * 10**9 + 17)] * 4,
    })
    ledger = pd.DataFrame({"date_utc": [day], "complete": [True],
                           "total_supply_open_wei": [Decimal((450_000_000 * 10**9 + 17) * 10**9 + 23)]})
    pool = pd.DataFrame({"observation_date": [day - pd.Timedelta(days=30), day],
                         "label": ["savax"] * 2, "price_per_share": [1.0, 1.004], "apy": [4.0, 4.4]})
    return dict(zip(exhibit.NEEDED, (raw, ledger, pool), strict=True))


def bind_pin(exhibit, monkeypatch, tmp_path, frames, name):
    records, paths = [], {}
    for index, (dataset, frame) in enumerate(frames.items()):
        directory = tmp_path / str(index)
        directory.mkdir()
        path = directory / "fixture.parquet"
        with duckdb.connect() as connection:
            connection.register("fixture", frame)
            connection.execute("COPY fixture TO ? (FORMAT PARQUET)", [str(path)])
        run = f"selected-source-{index}"
        records.append({"dataset_id": dataset, "run": run, "parquet": path.name,
                        "bytes": path.stat().st_size, "sha256": exhibit.sha256(path), "capture_id": "fixture"})
        paths[dataset, run] = path
    pin = tmp_path / "pin.json"
    pin.write_text(json.dumps({"name": name, "runs": records}))
    monkeypatch.setattr(exhibit.datasets, "parquet_path", lambda dataset, run, root: paths[dataset, run])
    monkeypatch.setattr(exhibit.datasets, "load", lambda dataset, run, root: frames[dataset].copy())
    return pin


@pytest.mark.parametrize("qualified", [False, True])
def test_explicit_pin_replay_and_source_footer(exhibit, frames, monkeypatch, tmp_path, qualified):
    if not qualified:
        frames[exhibit.NEEDED[0]] = frames[exhibit.NEEDED[0]].drop(columns=list(exhibit.NATIVE_METADATA))
    name = exhibit.QUALIFIED_PIN if qualified else "p4-opportunity-costs"
    pin = bind_pin(exhibit, monkeypatch, tmp_path, frames, name)
    loaded, sources = exhibit.inputs(pin, tmp_path)
    table, _, extras = exhibit.tables(loaded, sources, pd.Timestamp("2026-09-28"))
    layout = exhibit.chart(table, extras, pd.Timestamp("2026-09-28"))
    text = " ".join(item.text for item in layout.select({"type": Div}))
    assert all(record["run"] in text for record in sources.values())
    assert "opportunity-costs-daily-2026-10-06" not in text
    assert "not verified offered chain APR" in text
    if qualified:
        assert extras["native_basis"] == exhibit.NATIVE_SUPPLY_BASIS
        assert extras["native_metadata"][0] == {
            "series": "native-14d", "native_supply_basis": exhibit.NATIVE_SUPPLY_BASIS,
            "native_quote_at": "2026-09-28T00:00:00+00:00",
            "native_supply_navax": "450000000000000017",
        }
        assert table.loc[table.series == "native-365d", "native_supply_basis"].item() == exhibit.NATIVE_SUPPLY_BASIS
    else:
        assert "metadata unavailable" in extras["native_basis"]
        assert extras["native_metadata"][0]["native_quote_at"] is None


@pytest.mark.parametrize("mutation", ["basis", "missing", "clock", "supply"])
def test_qualified_native_metadata_refuses(exhibit, frames, monkeypatch, tmp_path, mutation):
    raw = frames[exhibit.NEEDED[0]]
    if mutation == "basis":
        raw.loc[0, "native_supply_basis"] = "verified-protocol-counter"
    elif mutation == "missing":
        frames[exhibit.NEEDED[0]] = raw.drop(columns="native_quote_at")
    elif mutation == "clock":
        raw.loc[0, "native_quote_at"] += pd.Timedelta(hours=1)
    else:
        raw.loc[0, "native_supply_navax"] += 1
    pin = bind_pin(exhibit, monkeypatch, tmp_path, frames, exhibit.QUALIFIED_PIN)
    with pytest.raises(ValueError, match="native"):
        exhibit.inputs(pin, tmp_path)


def test_payload_hash_refuses_before_render(exhibit, frames, monkeypatch, tmp_path):
    pin = bind_pin(exhibit, monkeypatch, tmp_path, frames, exhibit.QUALIFIED_PIN)
    path = exhibit.datasets.parquet_path(exhibit.NEEDED[0], "selected-source-0", tmp_path)
    path.write_bytes(path.read_bytes() + b"mutation")
    with pytest.raises(ValueError, match="frozen pin mismatch"):
        exhibit.inputs(pin, tmp_path)
