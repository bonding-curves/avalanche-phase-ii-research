"""US Treasury daily par yield curve rates from the Treasury's public XML feed."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import duckdb

from .. import __version__
from ..core.catalog import DataError, canonical_bytes, dataset, load_catalog, now, sha256
from .capture.rest import capture, capture_preview, read_capture  # noqa: F401  shared REST capture path


DATASET_ID = "us-treasury.par-yield-daily"
TABLE = "par-yield-daily"
FIRST_YEAR = 2020
NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
    "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
}
TENORS = {
    "BC_1MONTH": ("1m", 1), "BC_1_5MONTH": ("1.5m", 1.5), "BC_2MONTH": ("2m", 2), "BC_3MONTH": ("3m", 3), "BC_4MONTH": ("4m", 4),
    "BC_6MONTH": ("6m", 6), "BC_1YEAR": ("1y", 12), "BC_2YEAR": ("2y", 24), "BC_3YEAR": ("3y", 36), "BC_5YEAR": ("5y", 60),
    "BC_7YEAR": ("7y", 84), "BC_10YEAR": ("10y", 120), "BC_20YEAR": ("20y", 240), "BC_30YEAR": ("30y", 360),
}
TABLE_COLUMNS = {
    "observation_date": "DATE",
    "tenor": "VARCHAR",
    "maturity_months": "DOUBLE",
    "yield_rate": "DOUBLE",
    "source_year": "INTEGER",
}


def parse_feed(body: str, source_year: int) -> list[dict[str, Any]]:
    """Rows of (date, tenor, maturity, rate as a fraction) from one year's Atom feed."""
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as error:
        raise DataError(f"captured feed is not well-formed XML: {error}") from error
    rows: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", NAMESPACES):
        properties = entry.find("atom:content/m:properties", NAMESPACES)
        if properties is None:
            continue
        values = {child.tag.split("}")[1]: (child.text or "").strip() for child in properties}
        stamp = values.get("NEW_DATE", "")
        if not stamp:
            raise DataError("feed entry without NEW_DATE")
        for field, (tenor, months) in TENORS.items():
            text = values.get(field, "")
            if text == "":
                continue
            try:
                percent = float(text)
            except ValueError as error:
                raise DataError(f"non-numeric yield {text!r} for {tenor} on {stamp}") from error
            rows.append({"observation_date": stamp[:10], "tenor": tenor, "maturity_months": months, "yield_rate": percent / 100, "source_year": source_year})
    return rows


def load_capture(connection: Any, capture_dir: Path, receipt: dict[str, Any]) -> None:
    """Parse every captured yearly feed and build the typed long table in DuckDB."""
    rows: list[dict[str, Any]] = []
    for record in receipt["responses"]:
        year = int(record["endpoint_id"].rsplit("-", 1)[1])
        rows.extend(parse_feed((capture_dir / record["path"]).read_text(encoding="utf-8"), year))
    if not rows:
        raise DataError("captured feeds hold no yield observations")
    typed = ", ".join(f"{name} {kind}" for name, kind in TABLE_COLUMNS.items())
    declared = ", ".join(f"{name}: '{kind}'" for name, kind in TABLE_COLUMNS.items())
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as staging:
        for row in rows:
            staging.write(json.dumps(row) + "\n")
    try:
        connection.execute(f"CREATE TABLE rows({typed})")
        connection.execute(
            f"INSERT INTO rows SELECT * FROM read_json('{staging.name}', columns={{{declared}}}, format='newline_delimited') ORDER BY observation_date, maturity_months"
        )
    except duckdb.Error as error:
        raise DataError(f"captured feed does not match the declared shape: {error}") from error
    finally:
        os.unlink(staging.name)


def summarize(connection: Any) -> dict[str, Any]:
    record = connection.execute(
        "SELECT COUNT(*), MIN(observation_date), MAX(observation_date), COUNT(DISTINCT observation_date), COUNT(DISTINCT tenor), "
        "median(yield_rate) FILTER (tenor = '3m'), median(yield_rate) FILTER (tenor = '1y'), MIN(yield_rate), MAX(yield_rate) FROM rows"
    ).fetchone()
    return {
        "rows": record[0],
        "observed_from": record[1].isoformat(),
        "observed_to": record[2].isoformat(),
        "observation_dates": record[3],
        "tenors": record[4],
        "three_month_yield_median": record[5],
        "one_year_yield_median": record[6],
        "yield_rate_min": record[7],
        "yield_rate_max": record[8],
    }


def build_preview(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    load_catalog()
    return {"dataset_id": dataset_id, "capture": str(capture_dir), "output": str(output), "writes": [f"{TABLE}.parquet", "build.json"], "overwrite": False}


def build(dataset_id: str, capture_dir: Path, output: Path) -> dict[str, Any]:
    if dataset_id != DATASET_ID:
        raise DataError(f"unknown dataset: {dataset_id}")
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    receipt, _ = read_capture(capture_dir, catalog)
    if receipt["dataset_id"] != dataset_id:
        raise DataError(f"capture belongs to {receipt['dataset_id']}, not {dataset_id}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        parquet_path = temporary / f"{TABLE}.parquet"
        connection = duckdb.connect()
        try:
            load_capture(connection, capture_dir, receipt)
            connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet_path)])
            summary = summarize(connection)
        finally:
            connection.close()
        build_receipt = {
            "schema_version": "us-treasury-build/v1",
            "dataset_id": dataset_id,
            "dataset_schema": definition["fields"],
            "source_capture_id": receipt["capture_id"],
            "completed_at": now(),
            "tool": f"avalanche-research@{__version__}",
            "summary": summary,
            "outputs": [{"path": parquet_path.name, "bytes": parquet_path.stat().st_size, "sha256": sha256(parquet_path.read_bytes())}],
        }
        (temporary / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return build_receipt


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None) -> dict[str, Any]:
    if against is not None:
        raise DataError("this dataset has no reference dataset to check against")
    catalog = load_catalog()
    receipt, _ = read_capture(capture_dir, catalog)
    findings: list[str] = []
    checked = ["capture hashes", "required endpoints", "feed shape", "unique observations", "year placement", "yield bounds", "weekday coverage"]
    connection = duckdb.connect()
    try:
        load_capture(connection, capture_dir, receipt)
        counts = connection.execute(
            """
            WITH dates AS (SELECT DISTINCT observation_date, source_year FROM rows),
                 spaced AS (SELECT observation_date, observation_date - lag(observation_date) OVER (ORDER BY observation_date) AS gap FROM dates)
            SELECT (SELECT COUNT(*) - COUNT(DISTINCT (observation_date, tenor)) FROM rows),
                   (SELECT COUNT(*) FROM dates WHERE year(observation_date) <> source_year),
                   (SELECT COUNT(*) FROM rows WHERE yield_rate < 0 OR yield_rate > 0.25),
                   (SELECT COUNT(*) FROM spaced WHERE gap > 7)
            """
        ).fetchone()
        labels = ("repeat a date and tenor", "dates sit outside their feed year", "have a yield outside 0% to 25%", "dates follow a gap of more than a week")
        findings.extend(f"{failed} {label}" for failed, label in zip(counts, labels) if failed)
        summary = summarize(connection)
        if dataset_dir is not None:
            checked.extend(["build hashes", "Parquet rows"])
            try:
                build_receipt = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
                for item in build_receipt["outputs"]:
                    body = (dataset_dir / item["path"]).read_bytes()
                    if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
                        findings.append(f"output hash or size differs: {item['path']}")
                parquet = str(dataset_dir / f"{TABLE}.parquet")
                columns = ", ".join(TABLE_COLUMNS)
                differing = connection.execute(
                    f"""
                    SELECT (SELECT COUNT(*) FROM (SELECT {columns} FROM rows EXCEPT ALL SELECT {columns} FROM read_parquet(?)))
                         + (SELECT COUNT(*) FROM (SELECT {columns} FROM read_parquet(?) EXCEPT ALL SELECT {columns} FROM rows))
                    """,
                    [parquet, parquet],
                ).fetchone()[0]
                if differing:
                    findings.append("Parquet rows differ from the captured inputs")
            except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
                findings.append(f"invalid dataset output: {error}")
    finally:
        connection.close()
    return {
        "dataset_id": receipt["dataset_id"],
        "capture_id": receipt["capture_id"],
        "status": "pass" if not findings else "attention",
        "checked": checked,
        "summary": summary,
        "findings": findings,
    }
