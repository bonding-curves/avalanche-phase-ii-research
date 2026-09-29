"""Accepted staking commitments, summarized by calendar interval or upgrade era."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta, timezone

import duckdb
import pandas as pd
import panel as pn
import param as pm

from . import datasets
from .model.protocol import MAINNET_UPGRADES


DAY = timedelta(days=1)
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
WITH events AS ({events}),
buckets AS (
    SELECT role, node_id, identity, accepted_at::DATE AS day_bucket,
           date_trunc('week', accepted_at)::DATE AS week_bucket,
           date_trunc('year', accepted_at)::DATE AS year_bucket,
           CASE WHEN starts_with(era, 'apricot_') THEN 'apricot' ELSE era END AS era_bucket
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
       count(DISTINCT identity) AS identities,
       count(DISTINCT (node_id, identity)) FILTER (WHERE node_id IS NOT NULL AND identity IS NOT NULL) AS links,
       count(DISTINCT node_id) FILTER (WHERE identity IS NOT NULL) AS linked_nodes
FROM buckets
GROUP BY GROUPING SETS ((role, day_bucket), (role, week_bucket), (role, year_bucket),
                        (role, era_bucket), (role))
"""

_NODE_EVENTS = """
SELECT role, accepted_at, regime AS era, node_id, node_id AS identity FROM read_parquet(?)
"""
_REWARD_ADDRESS_EVENTS = """
SELECT 'validator' AS role, source.accepted_at, coalesce(upgrades.regime, 'genesis') AS era,
       source.node_id, source.identity
FROM (
    SELECT validator.accepted_at, validator.node_id, json_extract_string(address.value, '$') AS identity
    FROM read_parquet(?) validator, json_each(validator.reward_addresses) address
) source
ASOF LEFT JOIN upgrades ON source.accepted_at >= upgrades.activated_at
"""
_DELEGATOR_ADDRESS_EVENTS = """
SELECT 'delegator' AS role, source.accepted_at, coalesce(upgrades.regime, 'genesis') AS era,
       source.node_id, source.delegator_address AS identity
FROM read_parquet(?) source
ASOF LEFT JOIN upgrades ON source.accepted_at >= upgrades.activated_at
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


def distinct_identities(periods: str, validators: str, delegators: str) -> pd.DataFrame:
    """Count nodes, addresses, and distinct observed node-address links by interval."""
    sources = (
        ("Total Nodes", None, None, _NODE_EVENTS, periods),
        ("Total Validator Reward Addresses", ADDRESS_LINK_COLUMNS[0], LINKED_NODE_COLUMNS[0],
         _REWARD_ADDRESS_EVENTS, validators),
        ("Total Delegator Funding Addresses", ADDRESS_LINK_COLUMNS[1], LINKED_NODE_COLUMNS[1],
         _DELEGATOR_ADDRESS_EVENTS, delegators),
    )
    with duckdb.connect() as db:
        db.execute("CREATE TEMP TABLE upgrades(regime VARCHAR, activated_at TIMESTAMP)")
        db.executemany("INSERT INTO upgrades VALUES (?, ?)",
                       [(item.name, item.activated_at.replace(tzinfo=None))
                        for item in MAINNET_UPGRADES.upgrades])
        counts = None
        for column, links, linked_nodes, events, parquet in sources:
            part = db.execute(_IDENTITY_COUNTS_SQL.format(events=events), [parquet]).df()
            part = part.rename(columns={"identities": column})
            if links is None:
                part = part.drop(columns=["links", "linked_nodes"])
            else:
                part = part.rename(columns={"links": links, "linked_nodes": linked_nodes})
            counts = part if counts is None else counts.merge(part, on=["role", "grain", "bucket"], how="outer")
    return counts


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
            changes.append((era, pd.Timestamp(upgrade.activated_at.astimezone(timezone.utc)).tz_localize(None)))
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
                 identities: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per covered interval and role, including intervals with no accepted commitments."""
    if grain not in {"Day", "Week", "Year", "Era", "All"}:
        raise ValueError(f"unknown time grain: {grain}")
    daily = daily.copy()
    daily["accepted_day"] = pd.to_datetime(daily["accepted_day"])
    starts = daily.groupby("role")["first_accepted"].min().to_dict()
    rows = []
    for role, start in starts.items():
        start, end = pd.Timestamp(start), cutoffs[role]
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
    """Keep cohort context and show only the selected metric and view intersections."""
    columns = list(table.columns[:table.columns.get_loc("Total Nodes")])
    if "Nodes" in metrics:
        if "Total" in views:
            columns.append("Total Nodes")
        if "Per Address" in views:
            columns.append("Nodes per Address")
    if "Addresses" in metrics:
        if "Total" in views:
            columns.extend(column for column in ("Total Addresses", *IDENTITY_COLUMNS[1:]) if column in table.columns)
        if "Per Node" in views:
            columns.append("Addresses per Node")
    if "Total" in views and "Commitments" in metrics:
        columns.append("Total Commitments")
    commitment_views = {
        "Per Calendar Unit": f"Commitments / {period}",
        "Per Node": "Commitments / Node",
        "Per Node per Calendar Unit": f"Commitments / Node / {period}",
        "Per Address": "Commitments / Address",
        "Per Address per Calendar Unit": f"Commitments / Address / {period}",
    }
    if "Commitments" in metrics:
        columns.extend(commitment_views[view] for view in VIEWS if view in views and view in commitment_views)
    columns.extend(_metric_column(metric, view, period)
                   for metric in METRIC_SOURCES if metric in metrics for view in VIEWS if view in views)
    if "Rewards" in metrics:
        columns.append("Reward Outcomes")
    return table[columns]


class StakingCohorts(pm.Parameterized):
    """Fast notebook view of one checked staking-period release."""

    time_grain = pm.Selector(default="Era", objects=["Day", "Week", "Year", "Era", "All"], label="Group by")
    population = pm.Selector(default="Validators", objects=["Validators", "Delegators", "Both"])
    periodic_denominator = pm.Selector(default="Day", objects=["Day", "Week", "Year"], label="Rate Unit")
    metrics = pm.ListSelector(default=list(QUANTITIES), objects=list(QUANTITIES), label="Quantities")
    views = pm.ListSelector(default=["Total", "Per Calendar Unit", "Per Commitment"], objects=list(VIEWS),
                            label="Denominators")

    def __init__(self, run: str, **params):
        super().__init__(**params)
        self.run = run
        receipt = datasets.receipt("derived.staking-periods", run)
        cutoffs = _source_cutoffs(receipt["capture"])
        inputs = {item["input_id"]: item for item in receipt["capture"]["inputs"]}
        paths = {name: str(datasets.parquet_path(item["dataset_id"], item["run"]))
                 for name, item in inputs.items() if name in {"validator-stakes", "delegator-stakes"}}
        periods = str(datasets.parquet_path("derived.staking-periods", run))
        daily = accepted_commitments(periods)
        identities = distinct_identities(periods, paths["validator-stakes"], paths["delegator-stakes"])
        self._tables = {grain: cohort_table(daily, cutoffs, grain, identities)
                        for grain in self.param.time_grain.objects}
        self._cutoffs = cutoffs
        self._reward_cutoff = pd.Timestamp(next(item["captured_at"] for item in receipt["capture"]["inputs"]
                                                if item["input_id"] == "staking-rewards"))

    def _frame(self):
        table = for_population(self._tables[self.time_grain], self.population)
        table = selected_columns(rates_per(table, self.periodic_denominator), self.metrics, self.views,
                                 self.periodic_denominator)
        return table.round(2)

    def view(self):
        return pn.widgets.Tabulator(self._frame(), show_index=False, disabled=True,
                                    pagination="remote", page_size=20, sizing_mode="stretch_width")

    def panel(self):
        cutoffs = ", ".join(f"{role} extract captured {time:%Y-%m-%d %H:%M} UTC"
                            for role, time in self._cutoffs.items())
        note = (f"Pinned run `{self.run}`. {cutoffs}. Reward records through "
                f"{self._reward_cutoff:%Y-%m-%d %H:%M} UTC. "
                "Rewards include known outcomes only. `Reward Outcomes` is n known outcomes / m total commitments; "
                "Rewards / Commitment divides by n, not all m commitments. "
                "Rewards / Node divides known rewards by all cohort nodes. "
                "Rewards / Address divides known rewards by all cohort addresses. "
                "Nodes are distinct validator NodeIDs receiving these commitments. Validator reward addresses count "
                "all reward-owner addresses; delegator funding addresses count the largest funder per delegation, "
                "not unique people. "
                "Addresses per Node divides distinct node-address links by nodes with a recorded address; "
                "Nodes per Address divides those links by distinct recorded addresses. "
                "Total Committed Duration sums each new commitment's duration; it is not the row's elapsed time. "
                "Reporting intervals group commitments by acceptance time. Rate Unit changes only the calendar-time "
                "denominator, so reward rates are cohort-normalized, not payout flows. "
                "Year rates use 365.2425 days. Start is inclusive; End is exclusive.")
        grouping = pn.Column(
            *(pn.widgets.Select.from_param(parameter, width=220)
              for parameter in (self.param.time_grain, self.param.population,
                                self.param.periodic_denominator)),
            width=220,
        )
        quantities = pn.widgets.CheckButtonGroup.from_param(
            self.param.metrics, orientation="vertical", variant="outline", color="primary", width=190,
        )
        denominators = pn.widgets.CheckButtonGroup.from_param(
            self.param.views, options=denominator_options(self.periodic_denominator),
            orientation="vertical", variant="outline", color="primary", width=220,
        )
        self.param.watch(lambda event: setattr(denominators, "options", denominator_options(event.new)),
                         "periodic_denominator")
        table = self.view()
        self.param.watch(lambda event: setattr(table, "value", self._frame()),
                         ["time_grain", "population", "periodic_denominator", "metrics", "views"])
        controls = pn.Row(
            grouping,
            pn.Spacer(width=16),
            pn.Column(pn.pane.Markdown("Quantities", margin=(0, 0, 4, 0)), quantities, width=190),
            pn.Spacer(width=16),
            pn.Column(pn.pane.Markdown("Denominators", margin=(0, 0, 4, 0)), denominators, width=220),
        )
        return pn.Column(controls,
                         table, pn.pane.Markdown(note), sizing_mode="stretch_width")
