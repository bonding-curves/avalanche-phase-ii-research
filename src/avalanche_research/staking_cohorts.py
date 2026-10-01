"""Accepted staking commitments, summarized by calendar interval or upgrade era."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, timedelta
from functools import cache
from uuid import uuid4

import duckdb
import holoviews as hv
import pandas as pd
import panel as pn
import param as pm
from bokeh.core.properties import value
from bokeh.models import (
    BoxAnnotation,
    ColumnDataSource,
    DataRange1d,
    DatetimeAxis,
    FixedTicker,
    HoverTool,
    Legend,
    LegendItem,
    Range1d,
    Span,
)
from bokeh.plotting import figure

from . import datasets
from .model.protocol import MAINNET_UPGRADES
from .palette import QUANTITY_COLORS

DAY = timedelta(days=1)
NETWORK_START = pd.Timestamp("2020-09-10")
DAYS_PER_RATE_PERIOD = {"Day": 1, "Week": 7, "Year": 365.2425}
MEASURES = (
    "commitments", "stake_avax", "stake_duration_avax_days",
    "duration_days", "observed_rewards_avax", "reward_outcomes",
)
IDENTITY_COLUMNS = ("Total Nodes", "Total Validator Reward Addresses", "Total Delegator Funding Addresses")
ADDRESS_LINK_COLUMNS = ("Validator Node-address Pairs", "Delegator Node-address Pairs")
LINKED_NODE_COLUMNS = ("Validator Nodes with Addresses", "Delegator Nodes with Addresses")
VIEWS = ("Total", "Per Calendar Unit", "Per Commitment", "Per Node", "Per Node per Calendar Unit",
         "Per Address", "Per Address per Calendar Unit")
CONTEXT_COLUMNS = ("Reporting Interval", "Start (UTC)", "End (UTC)", "Role")


def denominator_options(rate_unit: str) -> dict[str, str]:
    """Show the selected calendar unit without changing the underlying view keys."""
    return {
        "Total": "Total",
        f"Per {rate_unit}": "Per Calendar Unit",
        "Per Commitment": "Per Commitment",
        "Per Node": "Per Node",
        f"Per Node per {rate_unit}": "Per Node per Calendar Unit",
        "Per Address": "Per Address",
        f"Per Address per {rate_unit}": "Per Address per Calendar Unit",
    }


METRIC_SOURCES = {
    "Stake": "stake_avax",
    "Duration": "duration_days",
    "Stake-duration": "stake_duration_avax_days",
    "Rewards": "observed_rewards_avax",
}
QUANTITIES = ("Nodes", "Addresses", "Commitments", *METRIC_SOURCES)
METRIC_COLUMNS = {
    "Stake": {
        "Total": "Total Stake (AVAX)",
        "Per Calendar Unit": "Stake / {period} (AVAX)",
        "Per Commitment": "Stake / Commitment (AVAX)",
        "Per Node": "Stake / Node (AVAX)",
        "Per Node per Calendar Unit": "Stake / Node / {period} (AVAX)",
        "Per Address": "Stake / Address (AVAX)",
        "Per Address per Calendar Unit": "Stake / Address / {period} (AVAX)",
    },
    "Duration": {
        "Total": "Total Committed Duration (commitment-days)",
        "Per Calendar Unit": "Committed Duration / {period} (commitment-days/{period_unit})",
        "Per Commitment": "Duration / Commitment (days)",
        "Per Node": "Committed Duration / Node (commitment-days/node)",
        "Per Node per Calendar Unit": "Committed Duration / Node / {period} (commitment-days/node/{period_unit})",
        "Per Address": "Committed Duration / Address (commitment-days/address)",
        "Per Address per Calendar Unit": "Committed Duration / Address / {period} (commitment-days/address/{period_unit})",
    },
    "Stake-duration": {
        "Total": "Total Stake-duration ({stake_time_unit})",
        "Per Calendar Unit": "Stake-duration / {period} ({stake_time_unit}/{period_unit})",
        "Per Commitment": "Stake-duration / Commitment ({stake_time_unit})",
        "Per Node": "Stake-duration / Node ({stake_time_unit})",
        "Per Node per Calendar Unit": "Stake-duration / Node / {period} ({stake_time_unit}/{period_unit})",
        "Per Address": "Stake-duration / Address ({stake_time_unit})",
        "Per Address per Calendar Unit": "Stake-duration / Address / {period} ({stake_time_unit}/{period_unit})",
    },
    "Rewards": {
        "Total": "Total Rewards (AVAX)",
        "Per Calendar Unit": "Rewards / {period} (AVAX)",
        "Per Commitment": "Rewards / Commitment (AVAX)",
        "Per Node": "Rewards / Node (AVAX)",
        "Per Node per Calendar Unit": "Rewards / Node / {period} (AVAX)",
        "Per Address": "Rewards / Address (AVAX)",
        "Per Address per Calendar Unit": "Rewards / Address / {period} (AVAX)",
    },
}

_IDENTITY_COUNTS_SQL = """
WITH events AS (SELECT * FROM ({events}) {window}),
buckets AS (
    SELECT role, node_id, identity, accepted_at::DATE AS day_bucket,
           date_trunc('week', accepted_at)::DATE AS week_bucket,
           date_trunc('year', accepted_at)::DATE AS year_bucket,
           {era_bucket} AS era_bucket
    FROM events
)
SELECT role,
       CASE WHEN grouping(day_bucket) = 0 THEN 'Day'
            WHEN grouping(week_bucket) = 0 THEN 'Week'
            WHEN grouping(year_bucket) = 0 THEN 'Year'
            WHEN grouping(era_bucket) = 0 THEN 'Era' ELSE 'All' END AS grain,
       CASE WHEN grouping(day_bucket) = 0 THEN day_bucket::VARCHAR
            WHEN grouping(week_bucket) = 0 THEN week_bucket::VARCHAR
            WHEN grouping(year_bucket) = 0 THEN year_bucket::VARCHAR
            WHEN grouping(era_bucket) = 0 THEN era_bucket ELSE 'All' END AS bucket,
       count(DISTINCT node_id) AS nodes,
       count(DISTINCT identity) AS identities,
       count(DISTINCT (node_id, identity)) FILTER (WHERE node_id IS NOT NULL AND identity IS NOT NULL) AS links,
       count(DISTINCT node_id) FILTER (WHERE identity IS NOT NULL) AS linked_nodes
FROM buckets
GROUP BY GROUPING SETS ((role, day_bucket), (role, week_bucket), (role, year_bucket),
                        (role, era_bucket), (role))
"""
_IDENTITY_GRAIN_SQL = """
WITH events AS (SELECT * FROM ({events}) WHERE accepted_at >= ? AND accepted_at < ?),
buckets AS (SELECT role, node_id, identity, {bucket} AS bucket FROM events)
SELECT role, '{grain}' AS grain, bucket,
       count(DISTINCT node_id) AS nodes,
       count(DISTINCT identity) AS identities,
       count(DISTINCT (node_id, identity)) FILTER (WHERE node_id IS NOT NULL AND identity IS NOT NULL) AS links,
       count(DISTINCT node_id) FILTER (WHERE identity IS NOT NULL) AS linked_nodes
FROM buckets GROUP BY role, bucket
"""
def _era_bucket_sql() -> str:
    changes = []
    for upgrade in MAINNET_UPGRADES.upgrades:
        era = "apricot" if upgrade.name.startswith("apricot_") else upgrade.name
        if not changes or era != changes[-1][0]:
            changes.append((era, upgrade.activated_at.astimezone(UTC)))
    clauses = [f"WHEN accepted_at >= TIMESTAMP '{instant:%Y-%m-%d %H:%M:%S}' THEN '{era}'"
               for era, instant in reversed(changes)]
    return "CASE " + " ".join(clauses) + " ELSE 'genesis' END"


IDENTITY_BUCKETS = {
    "Day": "accepted_at::DATE::VARCHAR",
    "Week": "date_trunc('week', accepted_at)::DATE::VARCHAR",
    "Year": "date_trunc('year', accepted_at)::DATE::VARCHAR",
    "Era": _era_bucket_sql(),
    "All": "'All'",
}

_REWARD_ADDRESS_EVENTS = """
SELECT 'validator' AS role, validator.accepted_at, validator.node_id,
       json_extract_string(address.value, '$') AS identity
FROM read_parquet(?) validator LEFT JOIN LATERAL json_each(validator.reward_addresses) address ON TRUE
"""
_DELEGATOR_ADDRESS_EVENTS = """
SELECT 'delegator' AS role, accepted_at, node_id, delegator_address AS identity FROM read_parquet(?)
"""


def _metric_column(metric: str, view: str, period: str = "Day") -> str:
    return METRIC_COLUMNS[metric][view].format(
        period=period, period_unit=period.lower(), stake_time_unit=f"AVAX-{period.lower()}s",
    )


def accepted_commitments(parquet: str) -> pd.DataFrame:
    """Scan the pinned period log once; keep only small daily, role, era totals."""
    with duckdb.connect() as db:
        return db.execute(
            """
            SELECT accepted_at::DATE AS accepted_day, role,
                   CASE WHEN starts_with(regime, 'apricot_') THEN 'apricot' ELSE regime END AS era,
                   min(accepted_at) AS first_accepted,
                   count(*) AS commitments,
                   sum(stake_navax)::DOUBLE / 1e9 AS stake_avax,
                   sum(stake_navax::DOUBLE * duration_days) / 1e9 AS stake_duration_avax_days,
                   sum(duration_days) AS duration_days,
                   coalesce(sum(realized_reward_navax) FILTER (WHERE rewarded_at IS NOT NULL), 0)::DOUBLE / 1e9
                       AS observed_rewards_avax,
                   count(rewarded_at) AS reward_outcomes
            FROM read_parquet(?)
            GROUP BY 1, 2, 3
            """,
            [parquet],
        ).df()


def distinct_identities(validators: str, delegators: str,
                        start: pd.Timestamp | None = None,
                        end: pd.Timestamp | None = None,
                        grain: str | None = None) -> pd.DataFrame:
    """Count nodes, addresses, and distinct observed node-address links by interval."""
    sources = [
        ("Total Validator Reward Addresses", ADDRESS_LINK_COLUMNS[0], LINKED_NODE_COLUMNS[0],
         _REWARD_ADDRESS_EVENTS, validators),
        ("Total Delegator Funding Addresses", ADDRESS_LINK_COLUMNS[1], LINKED_NODE_COLUMNS[1],
         _DELEGATOR_ADDRESS_EVENTS, delegators),
    ]
    with duckdb.connect() as db:
        parts = []
        for column, links, linked_nodes, events, parquet in sources:
            if grain is None:
                window = "WHERE accepted_at >= ? AND accepted_at < ?" if start is not None else ""
                sql = _IDENTITY_COUNTS_SQL.format(events=events, window=window,
                                                  era_bucket=IDENTITY_BUCKETS["Era"])
            else:
                sql = _IDENTITY_GRAIN_SQL.format(events=events, grain=grain,
                                                  bucket=IDENTITY_BUCKETS[grain])
            part = db.execute(sql, [parquet, start, end] if start is not None else [parquet]).df()
            part = part.rename(columns={"identities": column, "nodes": "Total Nodes"})
            part = part.rename(columns={"links": links, "linked_nodes": linked_nodes})
            parts.append(part)
    return pd.concat(parts, ignore_index=True)


def _source_cutoffs(capture: Mapping) -> dict[str, pd.Timestamp]:
    inputs = {item["input_id"]: item for item in capture["inputs"]}
    return {
        role: pd.Timestamp(inputs[source]["captured_at"]).tz_convert(None)
        for role, source in (("validator", "validator-stakes"), ("delegator", "delegator-stakes"))
    }


def _era_intervals(start: pd.Timestamp, end: pd.Timestamp):
    changes = [("genesis", start)]
    for upgrade in MAINNET_UPGRADES.upgrades:
        era = "apricot" if upgrade.name.startswith("apricot_") else upgrade.name
        if era != changes[-1][0]:
            changes.append((era, pd.Timestamp(upgrade.activated_at.astimezone(UTC)).tz_localize(None)))
    for index, (era, beginning) in enumerate(changes):
        finish = changes[index + 1][1] if index + 1 < len(changes) else end
        if beginning < end and finish > start:
            yield era, max(beginning, start), min(finish, end)


def _calendar_starts(start: pd.Timestamp, end: pd.Timestamp, grain: str):
    if grain == "Day":
        first, frequency, step = start.normalize(), "D", pd.DateOffset(days=1)
    elif grain == "Week":
        first, frequency, step = start.normalize() - timedelta(days=start.weekday()), "W-MON", pd.DateOffset(weeks=1)
    else:
        first, frequency, step = pd.Timestamp(year=start.year, month=1, day=1), "YS", pd.DateOffset(years=1)
    for beginning in pd.date_range(first, end, freq=frequency):
        finish = beginning + step
        if beginning < end and finish > start:
            label = str(beginning.year) if grain == "Year" else beginning.strftime("%Y-%m-%d")
            yield beginning, label, max(beginning, start), min(finish, end)


def cohort_table(daily: pd.DataFrame, cutoffs: Mapping[str, pd.Timestamp], grain: str,
                 identities: pd.DataFrame | None = None,
                 window: tuple[pd.Timestamp, pd.Timestamp] | None = None) -> pd.DataFrame:
    """One row per covered interval and role, including intervals with no accepted commitments."""
    if grain not in {"Day", "Week", "Year", "Era", "All"}:
        raise ValueError(f"unknown time grain: {grain}")
    daily = daily.copy()
    daily["accepted_day"] = pd.to_datetime(daily["accepted_day"])
    starts = daily.groupby("role")["first_accepted"].min().to_dict()
    if window is not None:
        daily = daily[daily["accepted_day"].ge(window[0]) & daily["accepted_day"].lt(window[1])]
    rows = []
    for role, start in starts.items():
        start, end = pd.Timestamp(start), cutoffs[role]
        if window is not None:
            start, end = max(start, window[0]), min(end, window[1])
        if start >= end:
            continue
        if grain == "All":
            intervals = [("All", "All", start, end)]
        elif grain == "Era":
            intervals = [(era, era.title(), a, b) for era, a, b in _era_intervals(start, end)]
        else:
            intervals = [(key, label, a, b) for key, label, a, b in _calendar_starts(start, end, grain)]
        rows.extend({"role": role, "bucket": key, "Reporting Interval": label, "Start (UTC)": a, "End (UTC)": b}
                    for key, label, a, b in intervals)
    spine = pd.DataFrame(rows)
    if grain == "Day":
        daily["bucket"] = daily["accepted_day"]
    elif grain == "Week":
        daily["bucket"] = daily["accepted_day"] - pd.to_timedelta(daily["accepted_day"].dt.weekday, unit="D")
    elif grain == "Year":
        daily["bucket"] = daily["accepted_day"].dt.to_period("Y").dt.start_time
    else:
        daily["bucket"] = daily["era"] if grain == "Era" else "All"
    totals = daily.groupby(["role", "bucket"], as_index=False)[list(MEASURES)].sum()
    result = spine.merge(totals, on=["role", "bucket"], how="left")
    if identities is not None:
        result["bucket_key"] = result["bucket"].astype(str)
        counts = identities[identities["grain"].eq(grain)].drop(columns="grain").rename(columns={"bucket": "bucket_key"})
        result = result.merge(counts, on=["role", "bucket_key"], how="left")
        result["Total Nodes"] = result["Total Nodes"].fillna(0)
        for role, column in (("validator", IDENTITY_COLUMNS[1]), ("delegator", IDENTITY_COLUMNS[2])):
            applicable = result["role"].eq(role)
            result.loc[applicable, column] = result.loc[applicable, column].fillna(0)
        for role, columns in (("validator", (ADDRESS_LINK_COLUMNS[0], LINKED_NODE_COLUMNS[0])),
                              ("delegator", (ADDRESS_LINK_COLUMNS[1], LINKED_NODE_COLUMNS[1]))):
            for column in columns:
                if column in result:
                    applicable = result["role"].eq(role)
                    result.loc[applicable, column] = result.loc[applicable, column].fillna(0)
    else:
        for column in IDENTITY_COLUMNS:
            result[column] = float("nan")
    for column in (*ADDRESS_LINK_COLUMNS, *LINKED_NODE_COLUMNS):
        if column not in result:
            result[column] = float("nan")
    result[list(MEASURES)] = result[list(MEASURES)].fillna(0)
    result[["commitments", "reward_outcomes"]] = result[["commitments", "reward_outcomes"]].astype(int)
    days = (result["End (UTC)"] - result["Start (UTC)"]) / DAY
    count = result["commitments"].replace(0, float("nan"))
    nodes = result["Total Nodes"].replace(0, float("nan"))
    addresses = result[IDENTITY_COLUMNS[1]].combine_first(result[IDENTITY_COLUMNS[2]]).replace(0, float("nan"))
    links = result[ADDRESS_LINK_COLUMNS[0]].combine_first(result[ADDRESS_LINK_COLUMNS[1]])
    linked_nodes = result[LINKED_NODE_COLUMNS[0]].combine_first(result[LINKED_NODE_COLUMNS[1]]).replace(
        0, float("nan"),
    )
    outcome_count = result["reward_outcomes"].replace(0, float("nan"))
    result["Total Days"] = days
    result["Commitments / Day"] = result["commitments"] / days
    result["Commitments / Node"] = result["commitments"] / nodes
    result["Commitments / Node / Day"] = result["Commitments / Node"] / days
    result["Commitments / Address"] = result["commitments"] / addresses
    result["Commitments / Address / Day"] = result["Commitments / Address"] / days
    result["Addresses per Node"] = links / linked_nodes
    result["Nodes per Address"] = links / addresses
    for metric, source in METRIC_SOURCES.items():
        total = result[source]
        result[_metric_column(metric, "Total")] = total
        result[_metric_column(metric, "Per Calendar Unit")] = total / days
        result[_metric_column(metric, "Per Commitment")] = total / (outcome_count if metric == "Rewards" else count)
        result[_metric_column(metric, "Per Node")] = total / nodes
        result[_metric_column(metric, "Per Node per Calendar Unit")] = total / nodes / days
        result[_metric_column(metric, "Per Address")] = total / addresses
        result[_metric_column(metric, "Per Address per Calendar Unit")] = total / addresses / days
    result["Reward Outcomes"] = result["reward_outcomes"].astype(str) + "/" + result["commitments"].astype(str)
    result["Role"] = result["role"].str.title()
    result = result.rename(columns={"commitments": "Total Commitments"})
    columns = ["Reporting Interval", "Start (UTC)", "End (UTC)", "Role", "Total Days", "Total Nodes",
               "Total Validator Reward Addresses", "Total Delegator Funding Addresses",
               "Addresses per Node", "Nodes per Address", "Total Commitments",
               "Commitments / Day", "Commitments / Node", "Commitments / Node / Day",
               "Commitments / Address", "Commitments / Address / Day"]
    columns.extend(_metric_column(metric, view) for metric in METRIC_SOURCES for view in VIEWS)
    columns.append("Reward Outcomes")
    result = result[columns].sort_values(["Start (UTC)", "Role"], ascending=[False, True])
    return result.reset_index(drop=True)


def rates_per(table: pd.DataFrame, denominator: str) -> pd.DataFrame:
    """Change only the display rate unit; the accepted cohort and its totals stay fixed."""
    factor = DAYS_PER_RATE_PERIOD[denominator]
    result = table.copy()
    result["Total Days"] = result["Total Days"] / factor
    stake_duration_columns = [_metric_column("Stake-duration", view) for view in VIEWS]
    result[stake_duration_columns] = result[stake_duration_columns] / factor
    rate_columns = ["Commitments / Day", "Commitments / Node / Day", "Commitments / Address / Day"]
    rate_columns.extend(_metric_column(metric, view) for metric in METRIC_SOURCES
                        for view in ("Per Calendar Unit", "Per Node per Calendar Unit",
                                     "Per Address per Calendar Unit"))
    result[rate_columns] = result[rate_columns] * factor
    names = {"Total Days": f"Total {denominator}s",
             "Commitments / Day": f"Commitments / {denominator}",
             "Commitments / Node / Day": f"Commitments / Node / {denominator}",
             "Commitments / Address / Day": f"Commitments / Address / {denominator}"}
    names.update({_metric_column(metric, view): _metric_column(metric, view, denominator)
                  for metric in METRIC_SOURCES for view in VIEWS
                  if metric == "Stake-duration" or view in ("Per Calendar Unit", "Per Node per Calendar Unit",
                                                            "Per Address per Calendar Unit")})
    return result.rename(columns=names)


def for_population(table: pd.DataFrame, population: str) -> pd.DataFrame:
    """Show only the address count that applies to the selected population."""
    validator_addresses, delegator_addresses = IDENTITY_COLUMNS[1:]
    if population == "Both":
        result = table.copy()
        result.insert(result.columns.get_loc(validator_addresses), "Total Addresses",
                      result[validator_addresses].combine_first(result[delegator_addresses]))
        return result.drop(columns=[validator_addresses, delegator_addresses])
    role, unused = (("Validator", delegator_addresses) if population == "Validators"
                    else ("Delegator", validator_addresses))
    return table[table["Role"].eq(role)].drop(columns=unused)


def selected_columns(table: pd.DataFrame, metrics: list[str], views: list[str], period: str) -> pd.DataFrame:
    """Keep context, then group selected quantities by denominator."""
    columns = list(table.columns[:table.columns.get_loc("Total Nodes")])
    commitment_views = {
        "Per Calendar Unit": f"Commitments / {period}",
        "Per Node": "Commitments / Node",
        "Per Node per Calendar Unit": f"Commitments / Node / {period}",
        "Per Address": "Commitments / Address",
        "Per Address per Calendar Unit": f"Commitments / Address / {period}",
    }
    for view in VIEWS:
        if view not in views:
            continue
        for metric in QUANTITIES:
            if metric not in metrics:
                continue
            if metric == "Nodes":
                if view == "Total":
                    columns.append("Total Nodes")
                elif view == "Per Address":
                    columns.append("Nodes per Address")
            elif metric == "Addresses":
                if view == "Total":
                    columns.extend(column for column in ("Total Addresses", *IDENTITY_COLUMNS[1:])
                                   if column in table.columns)
                elif view == "Per Node":
                    columns.append("Addresses per Node")
            elif metric == "Commitments":
                if view == "Total":
                    columns.append("Total Commitments")
                elif view in commitment_views:
                    columns.append(commitment_views[view])
            else:
                columns.append(_metric_column(metric, view, period))
    if "Rewards" in metrics:
        columns.append("Reward Outcomes")
    return table[columns]


def display_column(column: str) -> str:
    """Translate an internal heading without changing its meaning or units."""
    return column.replace(" / ", " per ").replace("/", " per ")


def display_columns(table: pd.DataFrame) -> pd.DataFrame:
    """Use readable headings without changing measure keys or units."""
    return table.rename(columns=display_column)


def quantity_colors(period: str) -> dict[str, str]:
    """Resolve plotted columns from quantity definitions, independent of draw order."""
    columns = {quantity: [_metric_column(quantity, view, period) for view in VIEWS]
               for quantity in METRIC_SOURCES}
    columns.update({
        "Nodes": ["Total Nodes", "Nodes per Address"],
        "Addresses": ["Total Addresses", *IDENTITY_COLUMNS[1:], "Addresses per Node"],
        "Commitments": ["Total Commitments", f"Commitments / {period}", "Commitments / Node",
                        f"Commitments / Node / {period}", "Commitments / Address",
                        f"Commitments / Address / {period}"],
    })
    return {display_column(column): QUANTITY_COLORS[quantity.lower().replace("-", "_")]
            for quantity, names in columns.items() for column in names}


def _upgrade_axis(plot, element):
    """Label upgrade starts above the calendar axis, as in the staking canvas."""
    if "upgrade_axis" in plot.handles:
        plot.handles["upgrade_axis"].axis_label = None
        return
    ticks = {}
    for era, start, _ in _era_intervals(NETWORK_START, pd.Timestamp.max.normalize()):
        ticks[start.value / 1_000_000] = era
    axis = DatetimeAxis(ticker=FixedTicker(ticks=list(ticks)), major_label_overrides=ticks,
                        axis_line_color=None, major_label_text_font_size="8pt", major_tick_in=0)
    plot.state.above = [axis, *plot.state.above]
    plot.handles["upgrade_axis"] = axis


def _legend_interaction(plot, element):
    for legend in plot.state.legend:
        legend.click_policy = "mute"


def _hover_number(value: float) -> str:
    if 0 < abs(value) < 0.005:
        return "<0.01" if value > 0 else ">-0.01"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


@cache
def _cohort_data(run: str):
    """Build the checked cohort tables once per pinned run in this kernel."""
    receipt = datasets.receipt("derived.staking-periods", run)
    cutoffs = _source_cutoffs(receipt["capture"])
    inputs = {item["input_id"]: item for item in receipt["capture"]["inputs"]}
    paths = {name: str(datasets.parquet_path(item["dataset_id"], item["run"]))
             for name, item in inputs.items() if name in {"validator-stakes", "delegator-stakes"}}
    periods = str(datasets.parquet_path("derived.staking-periods", run))
    daily = accepted_commitments(periods)
    identities = distinct_identities(paths["validator-stakes"], paths["delegator-stakes"])
    tables = {grain: cohort_table(daily, cutoffs, grain, identities)
              for grain in StakingCohorts.param.time_grain.objects}
    reward_cutoff = pd.Timestamp(next(item["captured_at"] for item in receipt["capture"]["inputs"]
                                      if item["input_id"] == "staking-rewards"))
    return tables, cutoffs, reward_cutoff, daily, (paths["validator-stakes"], paths["delegator-stakes"])


@cache
def _window_table(run: str, start: date, end: date, grain: str):
    """Recompute exact acceptance cohorts for inclusive UTC calendar dates."""
    _, cutoffs, _, daily, sources = _cohort_data(run)
    window = (pd.Timestamp(start), pd.Timestamp(end) + DAY)
    identities = distinct_identities(*sources, *window, grain)
    return cohort_table(daily, cutoffs, grain, identities, window)


class _CohortCommGuard(pn.pane.HTML):
    """Ignore returned notebook patches instead of echoing stale widget values."""

    # Bokeh marks backend patches sync=false. Panel's notebook comm listener
    # currently buffers them anyway, unlike ClientSession. Guard only the
    # document containing these controls. Server documents have no CommManager.
    _script = """
        for (const doc of Bokeh.documents) {
            if (!Array.from(doc._all_models.values()).some(model => model.name === GUARD_NAME)) continue;
            for (const manager of doc._all_models.values()) {
                if (!manager.type.endsWith("CommManager") || manager._cohort_sync_guard) continue;
                const receive = manager._document_changed.bind(manager);
                manager._document_changed = event => {
                    if (event.sync !== false) receive(event);
                };
                manager._event_buffer = manager._event_buffer.filter(event => event.sync !== false);
                manager._cohort_sync_guard = true;
            }
        }
    """

    def __init__(self, **params):
        super().__init__("", **params)
        self._guard_name = f"cohorts-comm-guard-{uuid4().hex}"
        self.object = "<script>(() => {" + self._script.replace("GUARD_NAME", repr(self._guard_name)) + "})();</script>"

    def _get_model(self, doc, root=None, parent=None, comm=None):
        model = super()._get_model(doc, root, parent, comm)
        model.name = self._guard_name
        model.syncable = False
        return model


class _CohortChartPane(pn.pane.Bokeh):
    """Give each live notebook document its own persistent figure."""

    def __init__(self, chart):
        self._chart = chart
        self._copies = {}
        super().__init__(chart.figure, sizing_mode="stretch_width")

    def _get_model(self, doc, root=None, parent=None, comm=None):
        if root is None:
            return self.get_root(doc, comm)
        if self.object.document is None or self.object.document is doc:
            return super()._get_model(doc, root, parent, comm)
        copy = _CohortChart(self._chart.explorer, isolated=True)
        model = copy.pane._get_model(doc, root, parent, comm)
        self._copies[root.id] = copy
        self._models[root.id] = (model, parent)
        return model

    def update_copies(self):
        for copy in tuple(self._copies.values()):
            copy.update()

    def _cleanup(self, root=None):
        if root is not None:
            copy = self._copies.pop(root.id, None)
            if copy is not None:
                copy.pane._cleanup(root)
        super()._cleanup(root)


class _CohortChart:
    """Keep the notebook's model graph stable; selection changes only visibility."""

    _fields = ("Date", "Index", "Value", "Title", "DisplayValue", "DisplayIndex")

    def __init__(self, explorer, *, isolated=False):
        self.explorer = explorer
        self.figure = figure(
            title="New staking commitments over time", x_axis_type="datetime",
            x_range=Range1d(0, 1),
            x_axis_label="Calendar time", height=600, sizing_mode="stretch_width",
            tools="pan,wheel_zoom,box_zoom,reset,save", active_scroll="wheel_zoom",
            y_range=DataRange1d(only_visible=True),
        )
        # Display-only models do not need browser-to-kernel traffic on zoom,
        # hover or legend mute, including Bokeh's scalar-color serialization.
        self.figure.x_range.syncable = self.figure.y_range.syncable = False
        self.reference = Span(location=1, dimension="width", line_color="#888888",
                              line_dash="dotted", line_width=1, syncable=False)
        self.figure.add_layout(self.reference)
        self.bands = {}
        for era, start, end in _era_intervals(
            NETWORK_START, pd.Timestamp(explorer.param.date_range.bounds[1]) + DAY,
        ):
            band = BoxAnnotation(left=start, right=end, fill_color="#d9d9d9", fill_alpha=0.35,
                                 line_alpha=0, visible=False, syncable=False)
            self.bands[era] = band
            self.figure.add_layout(band)
        ticks = {start.value / 1_000_000: era for era, start, _ in
                 _era_intervals(NETWORK_START, pd.Timestamp.max.normalize())}
        self.figure.add_layout(DatetimeAxis(
            ticker=FixedTicker(ticks=list(ticks)), major_label_overrides=ticks,
            axis_line_color=None, major_label_text_font_size="8pt", major_tick_in=0,
        ), "above")
        self.series = {}
        self._catalog = {}
        self._context = None
        self._groups = {}
        legend_items = []
        colors = quantity_colors(explorer.periodic_denominator)
        for (quantity, view), measure in self._columns().items():
            for role in ("Validator", "Delegator"):
                source = ColumnDataSource({name: [] for name in self._fields}, syncable=False)
                common = {"source": source, "name": measure, "visible": False, "syncable": False,
                          "color": colors[measure], "muted_alpha": 0.08}
                line = self.figure.line("Date", "Index", line_width=4, line_alpha=0.75,
                                        hover_line_width=6, hover_line_alpha=1, **common)
                point = self.figure.scatter("Date", "Index", size=7, **common)
                for renderer in (line, point):
                    renderer.syncable = False
                    for glyph in (renderer.glyph, renderer.hover_glyph, renderer.muted_glyph,
                                  renderer.nonselection_glyph):
                        if hasattr(glyph, "syncable"):
                            glyph.syncable = False
                item = LegendItem(label=value(measure), renderers=[line, point], visible=False, syncable=False)
                legend_items.append(item)
                self.series[role, quantity, view] = {"source": source, "line": line, "point": point,
                                                     "legend": item, "context": None}
        self.figure.add_layout(Legend(items=legend_items, location="top_right", click_policy="mute",
                                      syncable=False))
        self.figure.add_tools(HoverTool(
            renderers=[renderer for series in self.series.values() for renderer in
                       (series["line"], series["point"])],
            tooltips=[("Measure", "@Title"), ("Date", "@Date{%F}"),
                      ("Value", "@DisplayValue"), ("Chart value", "@DisplayIndex")],
            formatters={"@Date": "datetime"}, syncable=False,
        ))
        self.pane = (pn.pane.Bokeh(self.figure, sizing_mode="stretch_width") if isolated
                     else _CohortChartPane(self))
        self.empty = pn.pane.Markdown(
            "Select a Per denominator and a quantity with observed values to draw the chart.", visible=False,
        )
        self.update()

    def _columns(self):
        period = self.explorer.periodic_denominator
        if period not in self._catalog:
            # Use the same column projection as the table, including the
            # intentionally unsupported quantity/denominator combinations.
            table = rates_per(for_population(self.explorer._tables["All"].iloc[:0], "Both"), period)
            context = (*CONTEXT_COLUMNS, f"Total {period}s", "Reward Outcomes")
            self._catalog[period] = {
                (quantity, view): display_column(column)
                for quantity in QUANTITIES for view in VIEWS if view != "Total"
                for column in selected_columns(table, [quantity], [view], period)
                if column not in context
            }
        return self._catalog[period]

    def update(self, *events):
        explorer = self.explorer
        context = (explorer.time_grain, explorer.population, explorer.periodic_denominator,
                   explorer.normalization, explorer.date_range)
        if context != self._context:
            frame = explorer._plot_frame(metrics=list(QUANTITIES), views=list(VIEWS))
            self._groups = dict(tuple(frame.groupby(["Role", "Measure"], sort=False)))
            self._context = context
        visible_groups = []
        columns = self._columns()
        for (role, quantity, view), series in self.series.items():
            measure = columns[quantity, view]
            values = self._groups.get((role, measure))
            visible = quantity in explorer.metrics and view in explorer.views and values is not None
            if visible:
                visible_groups.append(values)
                if series["context"] != context:
                    label = f"{role}: {measure}" if explorer.population == "Both" else measure
                    series["source"].data = {
                        "Date": values["Date"].to_numpy(), "Index": values["Index"].to_numpy(),
                        "Value": values["Value"].to_numpy(), "Title": [label] * len(values),
                        "DisplayValue": values["Value"].map(_hover_number).tolist(),
                        "DisplayIndex": values["Index"].map(_hover_number).tolist(),
                    }
                    series["legend"].label = value(label)
                    series["line"].name = series["point"].name = label
                    series["context"] = context
            series["line"].visible = visible and len(values) > 1
            series["point"].visible = visible and len(values) == 1
            series["legend"].visible = visible
        self.figure.visible = bool(visible_groups)
        self.pane.visible = bool(visible_groups)
        self.empty.visible = not visible_groups
        self.reference.visible = explorer.normalization != "None"
        self.figure.yaxis.axis_label = ("Value (original units)" if explorer.normalization == "None"
                                       else f"Relative to {explorer.normalization.lower()}")
        if visible_groups:
            start = min(values["Date"].min() for values in visible_groups)
            end = max(values["Date"].max() for values in visible_groups)
            if start == end:
                start = min(values["Start (UTC)"].min() for values in visible_groups)
                end = max(values["End (UTC)"].max() for values in visible_groups)
            self.figure.x_range.update(start=start, end=end, reset_start=start, reset_end=end)
            bands = {era: (index, left, right) for index, (era, left, right) in enumerate(_era_intervals(
                min(values["Start (UTC)"].min() for values in visible_groups),
                max(values["End (UTC)"].max() for values in visible_groups),
            ))}
            for era, band in self.bands.items():
                band.visible = era in bands and bool(bands[era][0] % 2)
                if band.visible:
                    _, band.left, band.right = bands[era]
        # A table control may live in a different notebook document. Flush this
        # figure's held changes rather than waiting for its next widget event.
        if isinstance(self.pane, _CohortChartPane):
            self.pane.update_copies()
        pn.io.push_notebook(self.pane)


class StakingCohorts(pm.Parameterized):
    """Fast notebook view of one checked staking-period release."""

    time_grain = pm.Selector(default="Era", objects=["Day", "Week", "Year", "Era", "All"], label="Group by")
    population = pm.Selector(default="Validators", objects=["Validators", "Delegators", "Both"])
    periodic_denominator = pm.Selector(default="Day", objects=["Day", "Week", "Year"], label="Rate Unit")
    metrics = pm.ListSelector(default=list(QUANTITIES), objects=list(QUANTITIES), label="Quantities")
    views = pm.ListSelector(default=["Total", "Per Calendar Unit", "Per Commitment"], objects=list(VIEWS),
                            label="Denominators")
    normalization = pm.Selector(default="Mean", objects=["None", "First nonzero", "Mean", "Median"],
                                label="Normalize by")
    date_range = pm.CalendarDateRange(default=None, allow_None=True, label="Accepted dates (UTC)")

    def __init__(self, run: str, **params):
        super().__init__(**params)
        self.run = run
        self._tables, self._cutoffs, self._reward_cutoff, self._daily, self._sources = _cohort_data(run)
        first = pd.Timestamp(self._daily["first_accepted"].min()).date()
        last = max(self._cutoffs.values()).date()
        self.param.date_range.bounds = (first, last)
        if self.date_range is None:
            self.date_range = (first, last)

    def _selected_table(self):
        full_range = self.param.date_range.bounds
        if self.date_range == full_range:
            return self._tables[self.time_grain]
        return _window_table(self.run, *self.date_range, self.time_grain)

    def _frame(self):
        table = for_population(self._selected_table(), self.population)
        table = selected_columns(rates_per(table, self.periodic_denominator), self.metrics, self.views,
                                 self.periodic_denominator)
        return display_columns(table).round(2)

    def _full_frame(self):
        table = for_population(self._selected_table(), self.population)
        table = selected_columns(rates_per(table, self.periodic_denominator), list(QUANTITIES), list(VIEWS),
                                 self.periodic_denominator)
        return display_columns(table).round(2)

    def _plot_frame(self, *, metrics=None, views=None):
        """Selected per-denominator quantities on the same reporting intervals as the table."""
        metrics = self.metrics if metrics is None else metrics
        views = [view for view in (self.views if views is None else views) if view != "Total"]
        table = rates_per(for_population(self._selected_table(), self.population),
                          self.periodic_denominator)
        table = display_columns(selected_columns(table, metrics, views, self.periodic_denominator))
        measures = [column for column in table if column not in (*CONTEXT_COLUMNS,
                    f"Total {self.periodic_denominator}s", "Reward Outcomes")]
        if not measures:
            return pd.DataFrame(columns=["Date", "Role", "Measure", "Value", "Index"])
        frame = table.melt(id_vars=["Start (UTC)", "End (UTC)", "Role"], value_vars=measures,
                           var_name="Measure", value_name="Value")
        frame["Date"] = frame["Start (UTC)"] + (frame["End (UTC)"] - frame["Start (UTC)"]) / 2
        frame = frame.sort_values("Date")
        grouped = frame.groupby(["Role", "Measure"], sort=False)["Value"]
        if self.normalization == "None":
            frame["Index"] = frame["Value"]
            return frame.dropna(subset=["Index"])
        if self.normalization == "First nonzero":
            baseline = grouped.transform(lambda values: values[values.ne(0)].iloc[0]
                                         if values.ne(0).any() else float("nan"))
        elif self.normalization == "Median":
            baseline = grouped.transform("median")
        else:
            baseline = grouped.transform("mean")
        frame["Index"] = frame["Value"] / baseline.replace(0, float("nan"))
        return frame.dropna(subset=["Index"])

    @pm.depends("time_grain", "population", "periodic_denominator", "metrics", "views", "normalization",
                "date_range")
    def plot(self):
        frame = self._plot_frame()
        if frame.empty:
            return pn.pane.Markdown("Select a Per denominator and a quantity with observed values to draw the chart.")
        bands = [hv.VSpan(start, end).opts(color="#d9d9d9", alpha=0.35, line_alpha=0)
                 for index, (_, start, end) in enumerate(_era_intervals(frame["Start (UTC)"].min(),
                                                                          frame["End (UTC)"].max()))
                 if index % 2]
        curves = []
        colors = quantity_colors(self.periodic_denominator)
        for (role, measure), values in frame.groupby(["Role", "Measure"], sort=False):
            label = f"{role}: {measure}" if self.population == "Both" else measure
            element = hv.Scatter if len(values) == 1 else hv.Curve
            values = values.assign(Title=label, DisplayValue=values["Value"].map(_hover_number),
                                   DisplayIndex=values["Index"].map(_hover_number))
            style = {"color": colors[measure], "tools": ["hover"], "muted_alpha": 0.08,
                     "hover_tooltips": [("Measure", "@Title"), ("Date", "@Date{%F}"),
                                        ("Value", "@DisplayValue"), ("Chart value", "@DisplayIndex")],
                     "hover_formatters": {"@Date": "datetime"}}
            style.update({"line_width": 4, "line_alpha": 0.75,
                          "hover_line_width": 6, "hover_line_alpha": 1}
                         if element is hv.Curve else {"size": 7})
            curves.append(element(values, "Date", ["Index", "Value", "Title", "DisplayValue", "DisplayIndex"],
                                  label=label)
                          .opts(**style))
        reference = [] if self.normalization == "None" else [
            hv.HLine(1).opts(color="#888888", line_dash="dotted", line_width=1)
        ]
        return hv.Overlay([*bands, *reference, *curves]).opts(
            title="New staking commitments over time", xlabel="Calendar time",
            ylabel=("Value (original units)" if self.normalization == "None"
                    else f"Relative to {self.normalization.lower()}"), responsive=True, height=600,
            xlim=((frame["Date"].min(), frame["Date"].max()) if frame["Date"].nunique() > 1
                  else (frame["Start (UTC)"].min(), frame["End (UTC)"].max())),
            padding=0,
            legend_position="top_right", hooks=[_upgrade_axis, _legend_interaction],
        )

    def chart(self):
        """A second set of controls edits the same parameters as the table."""
        if getattr(self, "_chart", None) is None:
            controls = self._controls(normalization=True)
            self._chart_plot = _CohortChart(self)
            self._chart = pn.Column(
                controls, self._chart_plot.pane, self._chart_plot.empty,
                pn.pane.Markdown("Selected Per measures share one axis. Choose Normalize by None only when "
                                 "their original units are comparable. Totals stay in the table. "
                                 "Legend clicks mute curves; hovering a curve emphasizes it. "
                                 "Helicon is partial; rewards include known outcomes only."),
                sizing_mode="stretch_width",
            )
            self.param.watch(self._chart_plot.update, ["time_grain", "population", "periodic_denominator",
                                                      "metrics", "views", "normalization", "date_range"])
        return self._chart

    def view(self):
        full = self._full_frame()
        selected = self._frame().columns
        hidden = [column for column in full if column not in selected]
        return pn.widgets.Tabulator(full, hidden_columns=hidden, show_index=False, disabled=True,
                                    pagination="remote", page_size=20, height=350, sizing_mode="stretch_width")

    def _controls(self, normalization=False):
        # Each notebook output owns its widget models. Sharing one widget object
        # across documents can echo an older selection into the active output.
        attribute = "_chart_widgets" if normalization else "_table_widgets"
        widgets = getattr(self, attribute, None)
        if widgets is None:
            widgets = {name: pn.widgets.Select.from_param(self.param[name], width=220)
                             for name in ("time_grain", "population", "periodic_denominator", "normalization")}
            widgets["date_range"] = pn.widgets.DateRangeSlider.from_param(
                self.param.date_range, start=self.param.date_range.bounds[0],
                end=self.param.date_range.bounds[1], step=1, format="%Y-%m-%d", width=660, throttled=True,
            )
            widgets["metrics"] = pn.widgets.CheckButtonGroup.from_param(
                self.param.metrics, orientation="vertical", variant="outline", color="primary", width=190,
            )
            widgets["views"] = pn.widgets.CheckButtonGroup.from_param(
                self.param.views, options=denominator_options(self.periodic_denominator),
                orientation="vertical", variant="outline", color="primary", width=220,
            )
            self.param.watch(lambda event: setattr(widgets["views"], "options",
                                                  denominator_options(event.new)), "periodic_denominator")
            setattr(self, attribute, widgets)
        names = ["time_grain", "population", "periodic_denominator"]
        if normalization:
            names.append("normalization")
        grouping = pn.Column(*(widgets[name] for name in names), width=220)
        return pn.Column(
            pn.Row(
                grouping, pn.Spacer(width=16),
                pn.Column(pn.pane.Markdown("Quantities", margin=(0, 0, 4, 0)), widgets["metrics"], width=190),
                pn.Spacer(width=16),
                pn.Column(pn.pane.Markdown("Denominators", margin=(0, 0, 4, 0)), widgets["views"], width=220),
                _CohortCommGuard(width=0, height=0, margin=0),
            ),
            widgets["date_range"],
        )

    def panel(self):
        if getattr(self, "_panel", None) is not None:
            return self._panel
        cutoffs = ", ".join(f"{role} extract captured {time:%Y-%m-%d %H:%M} UTC"
                            for role, time in self._cutoffs.items())
        note = (f"Pinned run `{self.run}`. {cutoffs}. Reward records through "
                f"{self._reward_cutoff:%Y-%m-%d %H:%M} UTC. "
                "Rewards include known outcomes only. `Reward Outcomes` is n known outcomes / m total commitments; "
                "Rewards per Commitment divides by n, not all m commitments. "
                "Rewards per Node divides known rewards by all cohort nodes. "
                "Rewards per Address divides known rewards by all cohort addresses. "
                "Nodes are distinct validator NodeIDs receiving these commitments. Validator reward addresses count "
                "all reward-owner addresses; delegator funding addresses count the largest funder per delegation, "
                "not unique people. "
                "Addresses per Node divides distinct node-address links by nodes with a recorded address; "
                "Nodes per Address divides those links by distinct recorded addresses. "
                "Total Committed Duration sums each new commitment's duration; it is not the row's elapsed time. "
                "Reporting intervals group commitments by acceptance time. Accepted dates select inclusive UTC "
                "calendar dates, and partial reporting intervals are recomputed from the selected commitments. "
                "Rate Unit changes only the calendar-time "
                "denominator, so reward rates are cohort-normalized, not payout flows. "
                "Year rates use 365.2425 days. Start is inclusive; End is exclusive.")
        table = self.view()
        def update_visibility(event):
            selected = self._frame().columns
            table.hidden_columns = [column for column in table.value if column not in selected]

        def update_data(event):
            nonlocal table
            full = self._full_frame()
            selected = self._frame().columns
            hidden = [column for column in full if column not in selected]
            if not full.columns.equals(table.value.columns):
                # Tabulator rebuilds columns asynchronously. Changing hidden
                # columns in that same patch can redraw a torn-down table.
                # Initialize a new table atomically only when its schema changes.
                table = pn.widgets.Tabulator(
                    full, hidden_columns=hidden, show_index=False, disabled=True,
                    pagination="remote", page_size=20, height=350, sizing_mode="stretch_width",
                )
                self._panel[1] = table
            else:
                table.param.update(value=full, hidden_columns=hidden)

        self.param.watch(update_visibility, ["metrics", "views"])
        self.param.watch(update_data, ["time_grain", "population", "periodic_denominator", "date_range"])
        self._panel = pn.Column(self._controls(), table, pn.pane.Markdown(note), sizing_mode="stretch_width")
        return self._panel
