"""``derived.gci-monthly``: one row per month of the Gross Chain Income study, from its captured inputs.

The inputs are the token supplies, the bill rate and DefiLlama's fees captured by ``sources.gci``, the C-Chain burn in
the monetary ledger, and the AVAX price. ``sources.gci`` describes each input and the income rules. This module moves to
``datasets.derived`` at restructure step M4.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from ... import __version__, datasets
from ...core.catalog import (
    DataError,
    canonical_bytes,
    contract_hash,
    dataset,
    load_catalog,
    now,
    sha256,
)
from ...sources.gci import FEES_ID, RATE_ID, SUPPLY_ID, _write

MONTHLY_ID = "derived.gci-monthly"
DATASET_IDS = (MONTHLY_ID,)
DATASET_ID = MONTHLY_ID
COLUMNS = {
    MONTHLY_ID: {
        "month": "DATE", "month_end_block": "BIGINT", "tether_float_usd": "DOUBLE", "circle_float_usd": "DOUBLE", "bridged_float_usd": "DOUBLE",
        "bill_rate_pct": "DOUBLE", "rate_days": "INTEGER", "issuer_income_tether_usd": "DOUBLE", "issuer_income_circle_usd": "DOUBLE",
        "issuer_income_usd": "DOUBLE", "buidl_float_usd": "DOUBLE", "jaaa_float_usd": "DOUBLE", "savusd_assets_usd": "DOUBLE",
        "savusd_income_usd": "DOUBLE", "savbtc_assets_btc": "DOUBLE", "savbtc_income_btc": "DOUBLE", "fees_usd": "DOUBLE",
        "revenue_usd": "DOUBLE", "fee_days": "INTEGER", "burn_c_evm_avax": "DOUBLE", "burn_c_evm_usd": "DOUBLE", "burn_days": "INTEGER",
        "priced_burn_days": "INTEGER",
    },
}
TABLES = {MONTHLY_ID: "gci-monthly"}


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    raise DataError(f"{dataset_id} is derived; use `avalanche data derive`")


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    raise DataError(f"{dataset_id} is derived; use `avalanche data derive`")


MONTHLY_SQL = """
WITH s AS (SELECT * FROM supply WHERE month BETWEEN ? AND ?),
     m AS (SELECT DISTINCT month, block_number FROM s),
     rate AS (SELECT date_trunc('month', date_utc)::DATE AS month, avg(discount_rate_pct) AS pct, count(discount_rate_pct) AS days FROM rate GROUP BY 1),
     fees AS (SELECT date_trunc('month', date_utc)::DATE AS month, sum(fees_usd) AS fees, sum(revenue_usd) AS revenue, count(*) AS days FROM fees GROUP BY 1),
     burn AS (SELECT date_trunc('month', l.date_utc)::DATE AS month, sum(l.burned_c_evm_wei) / 1e18 AS avax,
                     sum(l.burned_c_evm_wei / 1e18 * p.close_usdt) AS usd, count(*) AS days, count(p.close_usdt) AS priced
              FROM ledger l LEFT JOIN price p ON p.observation_date = l.date_utc GROUP BY 1),
     vault AS (SELECT token, month, total_supply, total_assets, assets_per_share,
                      lag(total_supply) OVER (PARTITION BY token ORDER BY month) AS shares_before,
                      lag(assets_per_share) OVER (PARTITION BY token ORDER BY month) AS aps_before
               FROM supply WHERE token IN ('savUSD', 'savBTC'))
SELECT m.month, m.block_number,
       (SELECT total_supply FROM s WHERE s.month = m.month AND token = 'USDT'),
       (SELECT total_supply FROM s WHERE s.month = m.month AND token = 'USDC'),
       (SELECT sum(total_supply) FROM s WHERE s.month = m.month AND role = 'bridged'),
       rate.pct, rate.days,
       (SELECT total_supply FROM s WHERE s.month = m.month AND token = 'USDT') * rate.pct / 100 / 12,
       (SELECT total_supply FROM s WHERE s.month = m.month AND token = 'USDC') * rate.pct / 100 / 12,
       (SELECT sum(total_supply) FROM s WHERE s.month = m.month AND role = 'issuer') * rate.pct / 100 / 12,
       (SELECT total_supply FROM s WHERE s.month = m.month AND token = 'BUIDL'),
       (SELECT total_supply FROM s WHERE s.month = m.month AND token = 'JAAA'),
       (SELECT total_assets FROM vault v WHERE v.month = m.month AND token = 'savUSD'),
       (SELECT (assets_per_share - aps_before) * shares_before FROM vault v WHERE v.month = m.month AND token = 'savUSD'),
       (SELECT total_assets FROM vault v WHERE v.month = m.month AND token = 'savBTC'),
       (SELECT (assets_per_share - aps_before) * shares_before FROM vault v WHERE v.month = m.month AND token = 'savBTC'),
       fees.fees, fees.revenue, fees.days, burn.avax, burn.usd, burn.days, burn.priced
FROM m LEFT JOIN rate USING (month) LEFT JOIN fees USING (month) LEFT JOIN burn USING (month)
ORDER BY m.month
"""
MONTHLY_INPUTS = {"supply": SUPPLY_ID, "rate": RATE_ID, "fees": FEES_ID, "ledger": "derived.avax-monetary-daily", "price": "binance.avax-usdt-daily"}


def _monthly_inputs(pinned: dict[str, str] | None, root: Path | None) -> list[dict[str, Any]]:
    pinned = pinned or {}
    if set(pinned) - set(MONTHLY_INPUTS.values()):
        raise DataError(f"not an input of {MONTHLY_ID}: {', '.join(sorted(set(pinned) - set(MONTHLY_INPUTS.values())))}")
    inputs = []
    for view, dataset_id in MONTHLY_INPUTS.items():
        record = datasets.receipt(dataset_id, pinned.get(dataset_id), root)
        parquet = datasets.parquet_path(dataset_id, record["run"], root)
        body = parquet.read_bytes()
        inputs.append({"input_id": view, "dataset_id": dataset_id, "run": record["run"], "capture_id": record["capture"]["capture_id"],
                       "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet})
    return inputs


def monthly_rows(inputs: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    """The monthly table, over the months every input covers whole."""
    connection = duckdb.connect()
    try:
        for item in inputs:
            quoted = str(item["path"]).replace("'", "''")
            connection.execute(f"CREATE VIEW {item['input_id']} AS SELECT * FROM read_parquet('{quoted}')")
        first = connection.execute("SELECT min(month) FROM supply").fetchone()[0]
        last = connection.execute("""SELECT least((SELECT max(month) FROM supply),
                                                  (SELECT date_trunc('month', max(date_utc) + 1)::DATE - INTERVAL 1 MONTH FROM ledger))""").fetchone()[0]
        return connection.execute(MONTHLY_SQL, [first, last]).fetchall()
    finally:
        connection.close()


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    if dataset_id != MONTHLY_ID:
        raise DataError(f"{dataset_id} is captured; use `avalanche data fetch` and `build`")
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    inputs = _monthly_inputs(pinned, root)
    rows = monthly_rows(inputs)
    records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    completed_at = now()
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records}))
    capture_receipt = {
        "schema_version": "derived-capture/v1", "capture_id": f"capture:derived:{completed_at}:{identity[:12]}", "dataset_id": MONTHLY_ID,
        "source_id": "derived", "completed_at": completed_at, "contract_sha256": contract_hash(catalog, MONTHLY_ID),
        "tool": f"avalanche-research@{__version__}", "inputs": records,
        "parameters": {"issuer_income": "native USDT and USDC supply at the month's last block, times the month's mean DTB3, over 12",
                       "vault_income": "the rise in assets per share over the month times the shares at its start",
                       "burn_usd": "each day's C-Chain EVM burn times Binance's AVAX/USDT daily close"},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "capture").mkdir()
        (temporary / "dataset").mkdir()
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet = temporary / "dataset" / f"{TABLES[MONTHLY_ID]}.parquet"
        _write(parquet, COLUMNS[MONTHLY_ID], rows)
        build_receipt = {
            "schema_version": "derived-build/v1", "dataset_id": MONTHLY_ID, "dataset_schema": dataset(catalog, MONTHLY_ID)["fields"],
            "source_capture_id": capture_receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": {"rows": len(rows), "first_month": str(rows[0][0]) if rows else None, "last_month": str(rows[-1][0]) if rows else None,
                        "issuer_income_usd": sum(row[9] or 0 for row in rows)},
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "dataset" / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"capture": capture_receipt, "build": build_receipt}


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """The monthly table: inputs unchanged and a rebuild equal."""
    if against is not None:
        raise DataError("the GCI datasets take no --against directory")
    receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    dataset_id = receipt.get("dataset_id")
    if dataset_id != MONTHLY_ID:
        raise DataError(f"not a {MONTHLY_ID} capture: {capture_dir}")
    findings: list[str] = []
    summary: dict[str, Any] = {}
    root_dir = datasets.RUNS if root is None else root
    inputs = []
    for item in receipt["inputs"]:
        parquet = root_dir / item["run"] / "dataset" / item["parquet"]
        if not parquet.is_file() or sha256(parquet.read_bytes()) != item["sha256"]:
            findings.append(f"input run missing or changed: {item['run']}")
        inputs.append({**item, "path": parquet})
    if dataset_dir is not None and not findings:
        built = duckdb.connect().execute("SELECT * FROM read_parquet(?) ORDER BY month", [str(dataset_dir / f"{TABLES[MONTHLY_ID]}.parquet")]).fetchall()
        if [tuple(map(str, row)) for row in built] != [tuple(map(str, row)) for row in monthly_rows(inputs)]:
            findings.append("a rebuild from the recorded inputs differs")
        summary = {"rows": len(built)}
    checked = ["input run hashes", "rebuild from inputs"]
    return {"dataset_id": dataset_id, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}
