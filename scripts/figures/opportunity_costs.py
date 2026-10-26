#!/usr/bin/env python3
"""Draw a source-labelled opportunity-cost exhibit from the frozen P4 runs.

Run from the checkout with its notebook dependencies and separately supplied data:
    uv run --group notebook python scripts/figures/opportunity_costs.py OUTPUT

Use --runs-root to supply the named raw runs outside the checkout. No captures,
latest-run selection, interpolation, fitted response or matched spread is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from html import escape
from pathlib import Path

import duckdb
import pandas as pd
from bokeh.layouts import column
from bokeh.models import ColumnDataSource, Div, LabelSet, Range1d
from bokeh.plotting import figure, save
from bokeh.resources import INLINE
from png import save_png

from avalanche_research import datasets
from avalanche_research.datasets.derived.opportunity import NATIVE_SUPPLY_BASIS

CLIENT = Path(__file__).resolve().parents[2]
NEEDED = ("derived.opportunity-costs-daily", "derived.avax-monetary-daily", "defillama.pool-history")
QUALIFIED_PIN = "p4-opportunity-costs-qualified-2026-10-26"
NATIVE_METADATA = ("native_supply_basis", "native_quote_at", "native_supply_navax")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(pin_path, runs_root):
    pin = json.loads(pin_path.read_text())
    if pin["name"] not in ("p4-opportunity-costs", QUALIFIED_PIN):
        raise ValueError("expected an explicitly supported P4 pin")
    records = {r["dataset_id"]: r for r in pin["runs"]}
    if len(records) != len(pin["runs"]):
        raise ValueError("duplicate pinned dataset ID")
    frames, sources = {}, {}
    for dataset in NEEDED:
        r = records[dataset]
        path = datasets.parquet_path(dataset, run=r["run"], root=runs_root)
        if path.name != r["parquet"] or path.stat().st_size != r["bytes"] or sha256(path) != r["sha256"]:
            raise ValueError(f"frozen pin mismatch: {dataset}")
        # DuckDB's pandas conversion turns DECIMAL(38,0) into lossy float64.
        # Keep the actual qualified source integers as strings before conversion.
        integer = {NEEDED[0]: "native_supply_navax", NEEDED[1]: "total_supply_open_wei"}.get(dataset)
        if pin["name"] == QUALIFIED_PIN and integer:
            with duckdb.connect() as connection:
                columns = {row[0] for row in connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()}
                if integer not in columns:
                    raise ValueError("qualified native source lacks its supply column")
                frames[dataset] = connection.execute(
                    f"SELECT * REPLACE ({integer}::VARCHAR AS {integer}) FROM read_parquet(?)", [str(path)]).df()
        else:
            frames[dataset] = datasets.load(dataset, run=r["run"], root=runs_root)
        sources[dataset] = r
    if pin["name"] == QUALIFIED_PIN:
        validate_native_metadata(frames[NEEDED[0]], frames[NEEDED[1]])
    return frames, sources


def validate_native_metadata(raw, ledger):
    """Check the qualified approximation against its actual ledger opening and UTC clock."""
    if not set(NATIVE_METADATA).issubset(raw.columns):
        raise ValueError("qualified native source lacks basis, quote clock or supply")
    native = raw[raw.series.isin(["native-14d", "native-365d"])].copy()
    if native.empty or native.duplicated(["date_utc", "series"]).any():
        raise ValueError("qualified native rows must have unique date/series keys")
    if native[list(NATIVE_METADATA)].isna().any().any() or not native.native_supply_basis.eq(NATIVE_SUPPLY_BASIS).all():
        raise ValueError("unsupported or missing qualified native basis/clock/supply")
    quote = pd.to_datetime(native.native_quote_at, utc=True, errors="raise")
    midnight = pd.to_datetime(native.date_utc, utc=True, errors="raise")
    if not quote.eq(midnight).all() or not midnight.eq(midnight.dt.normalize()).all():
        raise ValueError("qualified native quote clock must be nominal UTC midnight")
    joined = native.merge(ledger[["date_utc", "total_supply_open_wei"]], on="date_utc", how="left", validate="many_to_one")
    if joined.total_supply_open_wei.isna().any():
        raise ValueError("qualified native supply lacks its ledger opening")
    for row in joined.itertuples():
        supply = Decimal(str(row.native_supply_navax))
        opening = Decimal(str(row.total_supply_open_wei))
        if not supply.is_finite() or supply <= 0 or supply != supply.to_integral_value() or supply != opening // 10**9:
            raise ValueError("qualified native supply differs from integer ledger opening")


def tables(frames, sources, day):
    raw, ledger, pool = (frames[d] for d in NEEDED)
    selected = raw[(raw.date_utc == day) & raw.series.isin(["native-14d", "native-365d", "savax", "tbill-3m"])].copy()
    if len(selected) != 4 or selected.series.duplicated().any() or selected.rate_pct.isna().any():
        raise ValueError("headline date needs four unique non-null source rates")
    stock = ledger[ledger.date_utc == day]
    if len(stock) != 1 or not bool(stock.iloc[0].complete):
        raise ValueError("headline date requires one complete ledger day")
    pool = pool.copy()
    pool["observation_date"] = pd.to_datetime(pool.observation_date)
    pps = pool[(pool.label == "savax") & ((pool.observation_date == day - pd.Timedelta(days=30)) | (pool.observation_date == day))].sort_values("observation_date")
    if len(pps) != 2 or pps.observation_date.duplicated().any() or pps.price_per_share.isna().any() or (pps.price_per_share <= 0).any():
        raise ValueError("PPS needs unique positive calendar-day endpoints; no fill")
    growth = float(pps.iloc[1].price_per_share / pps.iloc[0].price_per_share - 1)
    geometric = 100 * ((1 + growth) ** (365 / 30) - 1)
    simple = 100 * growth * 365 / 30
    today = pps.iloc[1]
    definitions = {
        "native-14d": ("P4R1", "Native, 14 days", "AVAX", "gross simple annualization; ledger-supply benchmark", 14, "prospective", "before node costs / delegator commission", "locked to commitment end", NEEDED[0]),
        "native-365d": ("P4R2", "Native, 365 days", "AVAX", "gross simple annualization; ledger-supply benchmark", 365, "prospective", "before node costs / delegator commission", "locked to commitment end", NEEDED[0]),
        "savax": ("P4R3", "sAVAX, 30-day PPS", "AVAX", "geometric annualization of observed share entitlement", 30, "trailing", "observed PPS; no extra protocol fee deduction", "15-day unlock then 2-day redemption, or market swap", NEEDED[2]),
        "tbill-3m": ("P4R4", "3-month bill, DTB3", "USD", "discount quote, ACT/360; no actual maturity observed", None, "source quote", "no execution / conversion costs", "maturity or secondary market", NEEDED[0]),
    }
    rows = []
    for series, definition in definitions.items():
        code, label, denomination, basis, duration, window, fees, exit_route, dataset = definition
        value = float(selected.loc[selected.series == series, "rate_pct"].iloc[0])
        if series == "savax":
            value = geometric
        native = selected.loc[selected.series == series].iloc[0]
        metadata = {key: None for key in NATIVE_METADATA}
        if series.startswith("native-") and set(NATIVE_METADATA).issubset(raw.columns):
            metadata = {"native_supply_basis": native.native_supply_basis,
                        "native_quote_at": pd.to_datetime(native.native_quote_at, utc=True).isoformat(),
                        "native_supply_navax": str(native.native_supply_navax)}
        rows.append({"code": code, "series": series, "label": label, "date_utc": str(day.date()), "rate_pct": value,
                         "denomination": denomination, "basis": basis, "duration_days": duration, "window": window,
                         "fees": fees, "exit_route": exit_route, "dataset": dataset, "run": sources[dataset]["run"],
                         "sha256": sources[dataset]["sha256"], "capture_id": sources[dataset]["capture_id"], **metadata})
    history = raw[raw.series.isin(definitions)].sort_values(["series", "date_utc"])[["date_utc", "series", "rate_pct"]].copy()
    if history.duplicated(["date_utc", "series"]).any():
        raise ValueError("duplicate historical date/series key")
    history["basis"] = history.series.map({k: v[3] for k, v in definitions.items()})
    # Historical sAVAX is the provider's one-day APY, not the headline 30-day rate.
    history.loc[history.series == "savax", "basis"] = "provider one-day reported APY; not headline 30-day PPS measure"
    extras = {"pps_endpoints": [{"date": str(r.observation_date.date()), "avax_per_savax": float(r.price_per_share)} for r in pps.itertuples()],
                  "source_runs": [sources[key]["run"] for key in NEEDED],
                  "native_metadata": [{"series": row["series"], **{key: row[key] for key in NATIVE_METADATA}}
                                      for row in rows if row["series"].startswith("native-")],
                  "native_basis": NATIVE_SUPPLY_BASIS if set(NATIVE_METADATA).issubset(raw.columns)
                      else "legacy ledger-supply benchmark; source clock/supply metadata unavailable",
                  "savax_simple_30d_pct": simple, "savax_provider_one_day_apy_pct": float(today.apy),
                  "native_opening_supply_wei": str(stock.iloc[0].total_supply_open_wei),
                  "history_coverage": {k: {"first": str(g.date_utc.min().date()), "last": str(g.date_utc.max().date()),
                                       "observations": len(g), "null_rates": int(g.rate_pct.isna().sum())}
                                    for k, g in history.groupby("series")}}
    full_pps = pool[pool.label == "savax"].sort_values("observation_date").copy()
    full_pps["previous_pps"] = full_pps.price_per_share.shift()
    full_pps["gap_days"] = full_pps.observation_date.diff().dt.days
    spikes = full_pps.nlargest(3, "apy")
    extras["largest_provider_daily_apy_checks"] = [
        {"date": str(r.observation_date.date()), "provider_apy_pct": float(r.apy),
         "pps": float(r.price_per_share), "previous_pps": float(r.previous_pps), "gap_days": int(r.gap_days),
         "geometric_pct_from_rounded_daily_pps": 100 * ((r.price_per_share / r.previous_pps) ** 365 - 1)}
        for r in spikes.itertuples() if r.gap_days == 1 and r.previous_pps > 0
    ]
    summary = history.groupby(["series", "basis"], sort=True).agg(
        first_observation=("date_utc", "min"), last_observation=("date_utc", "max"),
        observations=("date_utc", "size"), nonnull_rates=("rate_pct", "count"),
        minimum_rate_pct=("rate_pct", "min"), maximum_rate_pct=("rate_pct", "max"),
    ).reset_index()
    return pd.DataFrame(rows), summary, extras


def chart(table, extras, day):
    panels = []
    for denomination, height in [("AVAX", 245), ("USD", 160)]:
        part = table[table.denomination == denomination].iloc[::-1].copy()
        part["text"] = [f"{v:.2f}%" for v in part.rate_pct]
        part["text_x"] = part.rate_pct + 0.14
        plot = figure(width=1040, height=height, y_range=list(part.label), x_range=Range1d(0, 8.2),
                      title=f"{denomination} denomination", toolbar_location=None,
                      x_axis_label="Annual percentage measure (source bases differ)")
        source = ColumnDataSource(part)
        plot.segment(x0=0, y0="label", x1="rate_pct", y1="label", source=source, line_width=4, color="#cbd5e1")
        plot.scatter(x="rate_pct", y="label", source=source, size=12, color="#2563a5" if denomination == "AVAX" else "#526477")
        plot.add_layout(LabelSet(x="text_x", y="label", text="text", source=source, text_font_size="15px", y_offset=-7))
        plot.yaxis.major_label_text_font_size = "15px"
        plot.xaxis.axis_label_text_font_size = "14px"
        plot.xaxis.major_label_text_font_size = "13px"
        plot.title.text_font_size = "17px"
        plot.outline_line_color = None
        plot.ygrid.grid_line_color = None
        panels.append(plot)
    title = Div(text=f"<h2 style='margin:8px 0'>Outside-option rate menu, {day.date()}</h2>", width=1040)
    notes = Div(text=("<div style='font:15px/1.55 sans-serif'>"
                      "<b>Native:</b> gross simple annualization using realized ledger supply, not verified offered chain APR.<br>"
                      f"<b>sAVAX:</b> 30-day PPS geometric annualization; simple equivalent {extras['savax_simple_30d_pct']:.2f}%. "
                      f"One-day provider APY {extras['savax_provider_one_day_apy_pct']:.2f}% is a separate measure.<br>"
                      "<b>Bill:</b> DTB3 discount quote, 360-day convention. Different denomination and quote basis.<br>"
                      "These measures do not identify a matched spread, liquidity price or investment ranking.<br>"
                      f"Sources: {'; '.join(escape(run) for run in extras['source_runs'])}.</div>"), width=1040)
    return column(title, *panels, notes, spacing=10, width=1060)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--runs-root", type=Path, default=CLIENT / "data/runs")
    parser.add_argument("--pin", type=Path, default=CLIENT / "data/pins/p4-opportunity-costs.json")
    parser.add_argument("--date", default="2026-09-28")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    frames, sources = inputs(args.pin, args.runs_root)
    day = pd.Timestamp(args.date)
    table, history, extras = tables(frames, sources, day)
    table.to_csv(args.output / "opportunity-costs.csv", index=False, float_format="%.17g")
    history.to_csv(args.output / "opportunity-costs-history.csv", index=False, float_format="%.17g")
    provenance = {"schema": "opportunity-costs-exhibit/v1", "observation_date": str(day.date()),
                      "pin_sha256": sha256(args.pin), "sources": sources, "native_basis": extras["native_basis"],
                      "decision": "labelled benchmark fallback; no canonical-offer or matched-spread claim",
                      "derivations": extras, "missingness": "No interpolation or forward filling", "fitting": False}
    (args.output / "opportunity-costs-runs.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    html = args.output / "opportunity-costs.html"
    save(chart(table, extras, day), filename=str(html), resources=INLINE, title="Outside-option rate menu")
    save_png(html, args.output / "opportunity-costs.png", 1080, 720)
    print(table[["code", "label", "rate_pct", "basis"]].to_string(index=False))


if __name__ == "__main__":
    main()
