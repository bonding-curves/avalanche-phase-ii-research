from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pytest

from avalanche_research import cli, etf
from avalanche_research.catalog import DataError, load_catalog, source

# Trimmed from the issuers' responses of 2026-09-28.
BAVA_DATA = {
    "fundDetails": {"netAssets": 27850180.23, "sharesOutstanding": 980000, "asOfDate": "2026-09-25",
                    "stakingMetrics": {"currentPercentageOfAssetsStaked": 0.6305686475478604, "asOfDate": "2026-09-27"}},
    "holdings": {"basket": [{"companyName": "AVALANCHE", "shares": 2664322.97740779, "marketValue": 27856029.59, "weight": 1}], "asOfDate": "2026-09-25"},
    "navAndMarketPrice": {"nav": 28.41, "asOfDate": "2026-09-25",
                          "chart": {"nav": [[1776196800000, 25], [1790280000000, 28.371122], [1790366400000, 28.411395]],
                                    "marketPrice": [[1790366400000, 28.44]]}},
    "wallets": {"walletBalances": [{"active": True, "address": "0x6181ed1D30050DF3cDFe6f3444fA51f20640bADD", "balance": 763695.7341916952},
                                   {"active": True, "address": "0x15d237AF71282A26cC0C487bc4e0bF51E595F1dE", "balance": 1900357.0}]},
}
VAVX_NAV = {"data": {"AsOfDate": "09/25/2026", "Navs": [
    {"Key": "Total Net Assets", "Value": "20,724,615"}, {"Key": "AVAX per 1,000 Shares", "Value": "2,086.848"},
    {"Key": "AVAX per Basket", "Value": "52,171.183"}, {"Key": "Shares Outstanding", "Value": "950,000"},
    {"Key": "AVAX in Trust", "Value": "1,982,504.938"}]}, "blockId": 353894}
VAVX_STAKING = {"data": {"Ticker": "VAVX", "LongVersionAsOfDate": "09/25/2026", "Values": [
    {"Title": "Percentage Staked", "Value": "80.00"}, {"Title": "Net Staking Yield", "Value": "4.55%"}]}, "blockId": 353892}
VAVX_PRICES = {"data": {"Ticker": "VAVX", "AsOfDate": "09/25/2026", "PricesViewModel": {"NavCurrent": "$21.82", "LastPriceCurrent": "$21.83"}}, "blockId": 164035}


def ts_details(ticker: str, name: str, units: float, nav: float, constituents: list[dict]) -> dict:
    return {"success": True, "data": {"ticker": ticker, "product_name": name, "total_units_outstanding": units, "total_nav": nav,
                                      "nav_per_unit": nav / units, "valuation_date": "2026-09-28", "constituents": constituents}}


TS_DETAILS = {
    "AVAX": ts_details("AVAX", "21shares Avalanche Staking ETP", 11320000, 21146778.1790981, [
        {"ticker": "AVAX", "weight": 1, "quantity": 0.1824703904, "price": 10.2370690909, "coin_entitlement_per_share": 0.182470390421}]),
    "MOON": ts_details("MOON", "Sygnum Platform Winners Index ETP", 2125000, 25283090.536743015, [
        {"ticker": "BTC", "weight": 0.9601558791, "quantity": 0.000137, "price": 82981.58, "coin_entitlement_per_share": 0.000137},
        {"ticker": "AVAX", "weight": 0.0398441209, "quantity": 0.0463372327, "price": 10.23, "coin_entitlement_per_share": 0.0463372326855}]),
    "KEYS": ts_details("KEYS", "21shares Bitwise Select 10 ETP", 750000, 19598439.32776942, [
        {"ticker": "BTC", "weight": 0.9979824447, "quantity": 0.0003143, "price": 82999.78, "coin_entitlement_per_share": 0.0003143},
        {"ticker": "AVAX", "weight": 0.0020175553, "quantity": 0.0051482066, "price": 10.24, "coin_entitlement_per_share": 0.005148206643}]),
}


def ts_point(day: str, nav_per_share: float, units: float, total_nav: float, index: float, underlying: dict) -> dict:
    return {"valuation_date": day, "nav_per_share": nav_per_share, "total_units_outstanding": units, "total_nav": total_nav, "index": index, "underlying": underlying}


TS_HISTORY = {
    "AVAX": {"success": True, "data": [
        ts_point("2026-09-28", 1.868, 11320000, 21146778.1790981, 10.2370690909, {"AVAX": 10.2370690909}),
        ts_point("2026-09-25", 1.89, 11320000, 21402725.5298784, 10.3621272727, {"AVAX": 10.3621272727}),
        ts_point("2026-09-15", 1.95, 11000000, 21450000.0, 10.70, {"AVAX": 10.70}),
    ]},
    "MOON": {"success": True, "data": [ts_point("2026-09-28", 11.897, 2125000, 25283090.536743015, 512.45, {"BTC": 82981.58, "AVAX": 10.23})]},
    "KEYS": {"success": True, "data": [ts_point("2026-09-28", 26.129, 750000, 19598439.32776942, 84807.8, {"BTC": 82999.78, "AVAX": 10.24})]},
}


def fact(end: str, value: float, filed: str, accn: str = "0002035053-26-000023") -> dict:
    return {"end": end, "val": value, "accn": accn, "fy": 2026, "fp": "Q2", "form": "10-Q", "filed": filed}


SEC_FACTS = {"cik": 2035053, "entityName": "Grayscale Avalanche Staking ETF", "facts": {"us-gaap": {
    "InvestmentOwnedBalanceContracts": {"units": {"Avax": [
        fact("2026-03-31", 590000.0, "2026-05-08", "0001193125-26-214576"), fact("2026-03-31", 597200.873296, "2026-08-07"),
        fact("2026-06-30", 649890.86615, "2026-08-07")]}},
    "SharesOutstanding": {"units": {"shares": [fact("2026-03-31", 247980, "2026-08-07"), fact("2026-06-30", 267980, "2026-08-07")]}},
    "NetAssetValuePerShare": {"units": {"USD/shares": [fact("2026-03-31", 21.41, "2026-08-07"), fact("2026-06-30", 15.93, "2026-08-07")]}},
    "AssetsNet": {"units": {"USD": [fact("2026-03-31", 5309000, "2026-08-07"), fact("2026-06-30", 4270000, "2026-08-07")]}},
    "InvestmentOwnedPercentOfNetAssets": {"units": {"pure": [fact("2026-06-30", 1, "2026-08-07")]}},
    "Assets": {"units": {"USD": [{"start": "2026-04-01", "end": "2026-06-30", "val": 1, "accn": "x", "filed": "2026-08-07"}]}},
}}}


def bava_page(data: dict) -> bytes:
    payload = json.dumps({"props": {"pageProps": {"fundData": {"data": data}}}, "page": "/"})
    return f'<html><head></head><body><script id="__NEXT_DATA__" type="application/json">{payload}</script></body></html>'.encode()


def bodies() -> dict[str, bytes]:
    values = {etf.BAVA: bava_page(BAVA_DATA), etf.VAVX_NAV: VAVX_NAV, etf.VAVX_STAKING: VAVX_STAKING, etf.VAVX_PRICES: VAVX_PRICES, etf.SEC_GAVA: SEC_FACTS}
    for ticker in etf.TS_TICKERS:
        values[f"{etf.TS_PREFIX}{ticker.lower()}-details"] = TS_DETAILS[ticker]
        values[f"{etf.TS_PREFIX}{ticker.lower()}-history"] = TS_HISTORY[ticker]
    return {key: value if isinstance(value, bytes) else json.dumps(value).encode() for key, value in values.items()}


class Response:
    def __init__(self, body: bytes, content_type: str):
        self.body, self.status, self.headers = body, 200, {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self) -> bytes:
        return self.body


def opener(overrides: dict[str, bytes] | None = None, failures: dict[str, int] | None = None, seen: list | None = None):
    catalog = load_catalog()
    by_url = {item["url"]: item["id"] for item in source(catalog, etf.SOURCE_ID)["endpoints"]}
    served = {**bodies(), **(overrides or {})}
    remaining = dict(failures or {})

    def open_request(request, timeout):
        endpoint_id = by_url[request.full_url]
        if seen is not None:
            seen.append((endpoint_id, dict(request.header_items())))
        if remaining.get(endpoint_id):
            remaining[endpoint_id] -= 1
            raise OSError("fixture connection reset")
        body = served[endpoint_id]
        # 21Shares answers gzip whether asked or not.
        return Response(gzip.compress(body) if endpoint_id.startswith(etf.TS_PREFIX) else body,
                        "text/html" if endpoint_id == etf.BAVA else "application/json")

    return open_request


def run(tmp_path: Path, dataset_id: str, **options) -> tuple[Path, Path, dict]:
    capture_dir, dataset_dir = tmp_path / "capture", tmp_path / "dataset"
    etf.capture(dataset_id, capture_dir, opener=opener(**options), sleep=lambda _: None)
    etf.build(dataset_id, capture_dir, dataset_dir)
    return capture_dir, dataset_dir, etf.check(capture_dir, dataset_dir)


def table(dataset_dir: Path, dataset_id: str) -> Any:
    connection = duckdb.connect()
    try:
        frame = connection.execute("SELECT * FROM read_parquet(?)", [str(dataset_dir / f"{etf.TABLES[dataset_id]}.parquet")]).fetchdf()
    finally:
        connection.close()
    return frame


def test_catalog_declares_both_datasets_and_the_cli_routes_them():
    catalog = load_catalog()
    endpoints = {item["id"] for item in source(catalog, etf.SOURCE_ID)["endpoints"]}
    for dataset_id in etf.DATASET_IDS:
        definition = next(item for item in catalog["datasets"] if item["id"] == dataset_id)
        assert set(definition["endpoint_ids"]) <= endpoints
        assert [field["name"] for field in definition["fields"]] == list(etf.COLUMNS[dataset_id])
        assert cli.module_for(dataset_id) is etf


def test_snapshot_capture_builds_one_row_per_fund_and_passes(tmp_path):
    seen: list = []
    capture_dir, dataset_dir, checked = run(tmp_path, etf.SNAPSHOT_ID, seen=seen)
    assert checked["status"] == "pass", checked["findings"]
    assert checked["summary"]["bava_wallets"] == 2
    receipt = json.loads((capture_dir / "capture.json").read_text())
    assert receipt["responses"][0]["path"] == "raw/bava-page.html"
    assert b"walletBalances" in (capture_dir / "raw/bava-page.html").read_bytes()
    assert json.loads((capture_dir / "raw/twentyone-shares-avax-details.json").read_bytes())["data"]["ticker"] == "AVAX"
    headers = dict(seen)
    assert headers[etf.SEC_GAVA]["User-agent"].startswith(etf.USER_AGENT)
    assert "@" not in headers[etf.SEC_GAVA]["User-agent"]
    assert headers[etf.VAVX_NAV]["User-agent"].startswith("Mozilla/5.0")
    rows = table(dataset_dir, etf.SNAPSHOT_ID).set_index("ticker")
    assert list(rows.index) == ["AVAX", "BAVA", "GAVA", "KEYS", "MOON", "VAVX"]
    assert rows.loc["BAVA", "avax_held"] == 2664322.97740779 and not rows.loc["BAVA", "avax_held_derived"]
    assert rows.loc["BAVA", "staked_share"] == pytest.approx(0.6305686475478604)
    assert rows.loc["VAVX", "avax_held"] == 1982504.938 and rows.loc["VAVX", "nav_usd"] == 21.82
    assert rows.loc["VAVX", "avax_per_share"] == pytest.approx(2.086848) and rows.loc["VAVX", "staked_share"] == pytest.approx(0.8)
    assert rows.loc["VAVX", "as_of"].date() == date(2026, 9, 25)
    assert rows.loc["AVAX", "avax_held"] == pytest.approx(0.182470390421 * 11320000) and rows.loc["AVAX", "avax_held_derived"]
    assert rows.loc["MOON", "avax_weight"] == pytest.approx(0.0398441209)
    assert rows.loc["GAVA", "as_of"].date() == date(2026, 6, 30) and rows.loc["GAVA", "avax_held"] == 649890.86615
    assert rows.loc["GAVA", "shares_outstanding"] == 267980 and rows.loc["GAVA", "avax_weight"] == 1


def test_history_derives_single_asset_units_and_keeps_reported_ones(tmp_path):
    _, dataset_dir, checked = run(tmp_path, etf.HISTORY_ID)
    assert checked["status"] == "pass", checked["findings"]
    rows = table(dataset_dir, etf.HISTORY_ID)
    assert len(rows) == 3 + 1 + 1 + 3 + 2
    avax = rows[rows.ticker == "AVAX"].set_index("valuation_date")
    first = avax.loc["2026-09-15"]
    assert first["avax_held"] == pytest.approx(21450000.0 / 10.70) and first["avax_held_derived"]
    assert first["avax_per_share"] == pytest.approx(21450000.0 / 10.70 / 11000000)
    assert rows[rows.ticker == "MOON"]["avax_held"].isna().all() and rows[rows.ticker == "MOON"]["avax_price_usd"].iloc[0] == 10.23
    bava = rows[rows.ticker == "BAVA"].set_index("valuation_date")
    assert [str(day.date()) for day in bava.index] == ["2026-04-14", "2026-09-24", "2026-09-25"]
    assert bava.loc["2026-09-25", "avax_held"] == 2664322.97740779 and not bava.loc["2026-09-25", "avax_held_derived"]
    assert bava.loc["2026-04-14", ["avax_held", "shares_outstanding", "avax_held_derived"]].isna().all()
    gava = rows[rows.ticker == "GAVA"].set_index("valuation_date")
    # A later filing's restatement of a period replaces the earlier value.
    assert gava.loc["2026-03-31", "avax_held"] == 597200.873296


def test_check_reports_a_21shares_entitlement_off_its_nav(tmp_path):
    changed = json.loads(json.dumps(TS_DETAILS["AVAX"]))
    changed["data"]["constituents"][0]["coin_entitlement_per_share"] *= 1.01
    _, _, checked = run(tmp_path, etf.SNAPSHOT_ID, overrides={"twentyone-shares-avax-details": json.dumps(changed).encode()})
    assert checked["status"] == "attention"
    assert any(finding.startswith("21Shares AVAX: AVAX held") for finding in checked["findings"])


def test_check_reports_negative_and_missing_holdings(tmp_path):
    data = json.loads(json.dumps(BAVA_DATA))
    data["holdings"]["basket"][0]["shares"] = -1
    data["fundDetails"]["netAssets"] = None
    _, _, checked = run(tmp_path, etf.SNAPSHOT_ID, overrides={etf.BAVA: bava_page(data)})
    assert "1 rows hold negative AVAX: BAVA" in checked["findings"]
    assert any(finding.startswith("1 required values are missing: BAVA net_assets_usd") for finding in checked["findings"])


def test_history_reports_nav_share_gaps_without_failing(tmp_path):
    history = json.loads(json.dumps(TS_HISTORY["MOON"]))
    history["data"][0]["total_nav"] *= 1.2
    _, _, checked = run(tmp_path, etf.HISTORY_ID, overrides={"twentyone-shares-moon-history": json.dumps(history).encode()})
    assert checked["status"] == "pass"
    assert checked["summary"]["nav_times_shares_off_net_assets"] == ["MOON 2026-09-28"]


def test_capture_retries_dropped_connections(tmp_path):
    receipt = etf.capture(etf.SNAPSHOT_ID, tmp_path / "capture", opener=opener(failures={etf.VAVX_NAV: 2}), sleep=lambda _: None)
    assert next(item for item in receipt["responses"] if item["endpoint_id"] == etf.VAVX_NAV)["attempts"] == 3


def test_capture_fails_cleanly_on_a_page_without_embedded_data(tmp_path):
    output = tmp_path / "capture"
    with pytest.raises(DataError, match="__NEXT_DATA__"):
        etf.capture(etf.SNAPSHOT_ID, output, opener=opener(overrides={etf.BAVA: b"<html>blocked</html>"}), sleep=lambda _: None)
    assert not output.exists() and not list(tmp_path.iterdir())


def test_a_changed_raw_file_is_refused(tmp_path):
    capture_dir, _, _ = run(tmp_path, etf.SNAPSHOT_ID)
    path = capture_dir / "raw/sec-gava-facts.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(DataError, match="hash or size differs"):
        etf.check(capture_dir)


def test_parameters_and_against_are_rejected(tmp_path):
    with pytest.raises(DataError, match="accepts no parameters"):
        etf.capture_preview(etf.SNAPSHOT_ID, tmp_path / "x", {"start": "2026-01-01"})
    capture_dir, _, _ = run(tmp_path, etf.SNAPSHOT_ID)
    with pytest.raises(DataError, match="no --against"):
        etf.check(capture_dir, against=tmp_path)
