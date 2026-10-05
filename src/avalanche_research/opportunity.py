"""What else AVAX could earn each day, beside what the protocol pays for staking it.

``derived.opportunity-costs-daily`` has one row per UTC day and series. A series is the native staking rate itself or an
alternative: a dollar rate (the 3-month bill, the 1-year Treasury par yield) or a DefiLlama pool (liquid staking,
lending, other chains' staking). Every row carries the native rates of the same day beside it, and the spread of the
series over each.

The native rate is the protocol kernel's annualized reward rate for a 2,000 AVAX validator starting at 00:00 UTC that
day, for 14 and 365 days, against the supply open of that day on the monetary ledger. It is gross of fees and of
uptime, so it is what the protocol offers, not what a staker received. A day with no ledger supply has no native rate.
An alternative appears only on the days its source reports. Gaps stay gaps.

Rates are percent per year. The Treasury feed's fractions are scaled to percent. The 3-month bill is FRED's DTB3, a discount
rate, not a bond-equivalent yield.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from . import __version__, datasets
from .catalog import DataError, canonical_bytes, contract_hash, dataset, load_catalog, now, sha256
from .model.protocol import annualized_reward_rate

DATASET_ID = "derived.opportunity-costs-daily"
DATASET_IDS = (DATASET_ID,)
SOURCE_ID = "derived"
TABLE = "opportunity-costs-daily"
INPUTS = {
    "ledger": "derived.avax-monetary-daily",
    "tbill": "fred.tbill-3m-daily",
    "treasury": "us-treasury.par-yield-daily",
    "pools": "defillama.pool-history",
}
QUOTE_STAKE_NAVAX = 2_000 * 10**9
NATIVE_DAYS = (14, 365)
NAVAX_PER_WEI = 10**9
# Series name, category and how its rate is read. Pool series name their pool-history label.
POOL_SERIES = {
    "savax": "avax-liquid-staking", "ggavax": "avax-liquid-staking", "aave-wavax": "avax-lending", "benqi-avax": "avax-lending",
    "aave-usdc": "dollar-lending", "aave-usdt": "dollar-lending", "benqi-usdc": "dollar-lending",
    "steth": "other-chain-staking", "jitosol": "other-chain-staking",
}
COLUMNS = {
    "date_utc": "DATE",
    "series": "VARCHAR",
    "category": "VARCHAR",
    "rate_pct": "DOUBLE",
    "native_14d_pct": "DOUBLE",
    "native_365d_pct": "DOUBLE",
    "spread_vs_14d_pp": "DOUBLE",
    "spread_vs_365d_pp": "DOUBLE",
    "source_dataset": "VARCHAR",
}


def _reject(dataset_id: str) -> None:
    if dataset_id != DATASET_ID:
        raise DataError(f"{dataset_id} is not a derived dataset of this module")


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    _reject(dataset_id)
    raise DataError(f"{dataset_id} is built with `avalanche data derive`, not fetched")


def capture(dataset_id: str, output: Path, timeout: float = 20, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    return capture_preview(dataset_id, output, parameters)


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    _reject(dataset_id)
    raise DataError(f"{dataset_id} is built with `avalanche data derive`, which writes capture and dataset together")


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    return build_preview(dataset_id, capture_dir, output)


def select_inputs(pinned: dict[str, str] | None, root: Path | None) -> list[dict[str, Any]]:
    """The newest built run of each input, or the run ``pinned`` names for its dataset."""
    pinned = pinned or {}
    unknown = sorted(set(pinned) - set(INPUTS.values()))
    if unknown:
        raise DataError(f"not an input of {DATASET_ID}: {', '.join(unknown)}")
    selected = []
    for input_id, dataset_id in INPUTS.items():
        record = datasets.receipt(dataset_id, pinned.get(dataset_id), root)
        parquet = datasets.parquet_path(dataset_id, record["run"], root)
        body = parquet.read_bytes()
        selected.append({
            "input_id": input_id, "dataset_id": dataset_id, "run": record["run"], "capture_id": record["capture"]["capture_id"],
            "rows": record["build"].get("summary", {}).get("rows"), "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body),
            "path": parquet,
        })
    return selected


def native_rates(connection: Any) -> None:
    """``native``: the kernel's 14-day and 365-day rates for each ledger day with a supply."""
    days = connection.execute(
        "SELECT date_utc, total_supply_open_wei::HUGEINT FROM ledger WHERE total_supply_open_wei IS NOT NULL ORDER BY date_utc"
    ).fetchall()
    rows = []
    for day, supply_wei in days:
        start = datetime(day.year, day.month, day.day, tzinfo=UTC)
        supply = int(supply_wei) // NAVAX_PER_WEI
        rows.append((day, *(annualized_reward_rate(start, length * 86_400, QUOTE_STAKE_NAVAX, supply) * 100 for length in NATIVE_DAYS)))
    connection.execute("CREATE TABLE native(date_utc DATE, native_14d_pct DOUBLE, native_365d_pct DOUBLE)")
    if rows:
        connection.executemany("INSERT INTO native VALUES (?, ?, ?)", rows)


def compute(connection: Any) -> None:
    """``result`` from the input views ``ledger``, ``tbill``, ``treasury`` and ``pools``."""
    native_rates(connection)
    pools = ", ".join(f"('{label}', '{category}')" for label, category in POOL_SERIES.items())
    connection.execute(
        f"""
        CREATE TABLE series AS
        SELECT date_utc, 'native-14d' AS series, 'avax-native-staking' AS category, native_14d_pct AS rate_pct,
               '{INPUTS["ledger"]}' AS source_dataset FROM native
        UNION ALL
        SELECT date_utc, 'native-365d', 'avax-native-staking', native_365d_pct, '{INPUTS["ledger"]}' FROM native
        UNION ALL
        SELECT date_utc, 'tbill-3m', 'dollar-risk-free', discount_rate_pct, '{INPUTS["tbill"]}' FROM tbill
        WHERE discount_rate_pct IS NOT NULL
        UNION ALL
        SELECT observation_date, 'treasury-1y', 'dollar-risk-free', yield_rate * 100, '{INPUTS["treasury"]}' FROM treasury
        WHERE tenor = '1y' AND yield_rate IS NOT NULL
        UNION ALL
        SELECT p.observation_date, p.label, m.category, p.apy, '{INPUTS["pools"]}'
        FROM pools AS p JOIN (VALUES {pools}) AS m(label, category) ON m.label = p.label
        WHERE p.apy IS NOT NULL
        """
    )
    names = ", ".join(COLUMNS)
    connection.execute(
        f"""
        CREATE TABLE result AS
        SELECT {names} FROM (
          SELECT s.date_utc, s.series, s.category, s.rate_pct, n.native_14d_pct, n.native_365d_pct,
                 s.rate_pct - n.native_14d_pct AS spread_vs_14d_pp, s.rate_pct - n.native_365d_pct AS spread_vs_365d_pp,
                 s.source_dataset
          FROM series AS s LEFT JOIN native AS n USING (date_utc)
        )
        ORDER BY date_utc, series
        """
    )


def summarize(connection: Any) -> dict[str, Any]:
    rows, keys = connection.execute("SELECT count(*), count(DISTINCT (date_utc, series)) FROM result").fetchone()
    series = connection.execute(
        "SELECT series, count(*), min(date_utc)::VARCHAR, max(date_utc)::VARCHAR, count(native_14d_pct) FROM result GROUP BY series ORDER BY series"
    ).fetchall()
    latest = connection.execute(
        "SELECT max(date_utc)::VARCHAR, any_value(native_14d_pct), any_value(native_365d_pct) FROM native WHERE date_utc = (SELECT max(date_utc) FROM native)"
    ).fetchone()
    return {
        "rows": rows, "distinct_keys": keys,
        "series": {name: {"days": days, "first": first, "last": last, "days_with_native": paired} for name, days, first, last, paired in series},
        "latest_native": {"date_utc": latest[0], "native_14d_pct": latest[1], "native_365d_pct": latest[2]},
    }


def _load(connection: Any, paths: dict[str, Path]) -> None:
    for input_id, path in paths.items():
        connection.execute(f"CREATE OR REPLACE VIEW {input_id} AS SELECT * FROM read_parquet('{str(path).replace(chr(39), chr(39) * 2)}')")


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    """Build the table into a new run directory holding ``capture/`` and ``dataset/``."""
    _reject(dataset_id)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    inputs = select_inputs(pinned, root)
    completed_at = now()
    records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    parameters = {"quote_stake_navax": QUOTE_STAKE_NAVAX, "native_days": list(NATIVE_DAYS), "pool_series": POOL_SERIES}
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records, "parameters": parameters}))
    capture_receipt = {
        "schema_version": "derived-capture/v1", "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
        "dataset_id": dataset_id, "source_id": SOURCE_ID, "completed_at": completed_at,
        "contract_sha256": contract_hash(catalog, dataset_id), "tool": f"avalanche-research@{__version__}",
        "inputs": records, "parameters": parameters,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "capture").mkdir()
        (temporary / "dataset").mkdir()
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet_path = temporary / "dataset" / f"{TABLE}.parquet"
        connection = duckdb.connect()
        try:
            _load(connection, {item["input_id"]: item["path"] for item in inputs})
            compute(connection)
            connection.execute("COPY result TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection)
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "derived-build/v1", "dataset_id": dataset_id, "dataset_schema": definition["fields"],
            "source_capture_id": capture_receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": summary,
            "outputs": [{"path": parquet_path.name, "bytes": parquet_path.stat().st_size, "sha256": sha256(parquet_path.read_bytes())}],
        }
        (temporary / "dataset" / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"capture": capture_receipt, "build": build_receipt}


def read_capture(capture_dir: Path) -> dict[str, Any]:
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"unreadable capture receipt: {error}") from error
    if receipt.get("schema_version") != "derived-capture/v1" or receipt.get("dataset_id") != DATASET_ID:
        raise DataError(f"not an opportunity-cost capture: {capture_dir}")
    return receipt


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """Input hashes, the contract, one row per day and series, and the table rebuilt from its inputs row for row."""
    if against is not None:
        raise DataError("the opportunity-cost table takes no --against directory")
    catalog = load_catalog()
    receipt = read_capture(capture_dir)
    findings: list[str] = []
    checked = ["input run hashes", "catalog contract", "unique keys", "spreads", "rebuild"]
    if receipt.get("contract_sha256") != contract_hash(catalog, DATASET_ID):
        findings.append("catalog contract changed since the capture")
    paths = {}
    for item in receipt["inputs"]:
        path = datasets.parquet_path(item["dataset_id"], item["run"], root)
        if sha256(path.read_bytes()) != item["sha256"]:
            findings.append(f"input {item['run']} differs from the receipt")
        paths[item["input_id"]] = path
    connection = duckdb.connect()
    try:
        _load(connection, paths)
        compute(connection)
        summary = summarize(connection)
        repeated, wrong_spread = connection.execute(
            """
            SELECT count(*) - count(DISTINCT (date_utc, series)),
                   count_if(abs(spread_vs_14d_pp - (rate_pct - native_14d_pct)) > 1e-12)
            FROM result
            """
        ).fetchone()
        if repeated:
            findings.append(f"{repeated} rows repeat a day and series")
        if wrong_spread:
            findings.append(f"{wrong_spread} spreads differ from rate minus native rate")
        if dataset_dir is not None:
            checked.append("build hashes")
            try:
                build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
                for output in build_receipt["outputs"]:
                    body = (dataset_dir / output["path"]).read_bytes()
                    if len(body) != output["bytes"] or sha256(body) != output["sha256"]:
                        findings.append(f"output hash or size differs: {output['path']}")
                parquet = str(dataset_dir / f"{TABLE}.parquet")
                names = ", ".join(COLUMNS)
                differing = connection.execute(
                    f"""
                    SELECT (SELECT count(*) FROM (SELECT {names} FROM result EXCEPT ALL SELECT {names} FROM read_parquet(?)))
                         + (SELECT count(*) FROM (SELECT {names} FROM read_parquet(?) EXCEPT ALL SELECT {names} FROM result))
                    """,
                    [parquet, parquet],
                ).fetchone()[0]
                if differing:
                    findings.append("Parquet rows differ from a rebuild from the inputs")
            except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
                findings.append(f"invalid dataset output: {error}")
    finally:
        connection.close()
    return {
        "dataset_id": DATASET_ID, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
        "checked": checked, "summary": summary, "findings": findings,
    }
