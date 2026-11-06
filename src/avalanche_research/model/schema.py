"""The fixed output schema of the staking model: every output of the engine's long table and every KPI measure, with
its unit.

The schema covers the fitted lifecycle and every model built on it: the delegated lifecycles and the holder
lifecycles. Each :class:`Output` names one output, where it appears (``PLACEMENTS``), its dtype, its unit with its
base, the group of settings that makes it appear (``GROUPS``) and what it is. Every column of the long table that the
schema does not list is a Param setting of the model, whose unit is in that setting's ``doc``.
:func:`setting_names` gives them for a model.

:func:`expected` gives the outputs a model's long table carries, by name, and :func:`render` writes the schema as the
Markdown of ``OUTPUTS.md`` beside this module. A test checks that the file equals the rendering.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from avalanche_research.model.engine import SimulationModel

PLACEMENTS = {
    "identifier": "a column of its own on every row of the long table, which names the row",
    "variable": "a value of the long table's `variable` column, whose amount is in the `value` column, one row per run, "
                "day and variable",
    "float": "a column of its own in the long table, one value per run and day, repeated on each of that day's rows",
    "kpi": "a value of the `measure` column of the table of key performance indicators that the function "
           "`kpis.kpi_table` returns, whose number is in its `value` column, one row per horizon in days and "
           "operating-cost level",
    "kpi_column": "a column of its own in the table of key performance indicators that the function `kpis.kpi_table` "
                  "returns",
    "daily": "a column of the daily table that the function `kpis.run_daily_table` builds from one run of the long "
             "table, one row per day, beside the run's state variables and the float columns a measure reads",
}
"""Where an output appears, by placement code."""

GROUPS = {
    "always": "every run of the fitted lifecycle and of every model built on it",
    "delegations": "a model with delegations, such as the v0.8.1 candidate",
    "turnover": "a run with the `record_turnover` setting switched on",
    "revenue": "a run with revenue funding, which is a reward rule that pays from the revenue pool, a revenue stream "
               "set above zero by the `revenue_avax_pa` setting, or the `count_revenue_in_supply` setting switched on",
    "price": "a run with a price path, set by the `price0_usd`, `price_drift_pa` and `price_volatility_pa` settings",
    "holders": "a holder model with the `holders` setting given, such as the v0.9 holders variant",
}
"""The group of settings that makes an output appear, by group code."""

NAVAX = "nAVAX, 10^-9 AVAX"
STOCK = f"{NAVAX}, a stock at the end of the day"
FLOW = f"{NAVAX} on the day, a flow"
NAMED_OPERATOR = "<key>_delegated_stake_navax"
"""The name pattern of a named operator's delegated stake, one variable per operator named at the origin other than
BENQI, with ``<key>`` the operator's key."""


@dataclass(frozen=True)
class Output:
    """One output of the model: its name, placement code, dtype, unit with its base, group code and meaning."""

    name: str
    placement: str
    dtype: str
    unit: str
    group: str
    description: str


OUTPUTS: tuple[Output, ...] = (
    # Identifiers.
    Output("simulation", "identifier", "int64", "an index from 0, no unit", "always",
           "The setting combination of a sweep, one per model, and 0 for a single run."),
    Output("run", "identifier", "int64", "an index from 1, no unit", "always",
           "The Monte Carlo run within the setting combination, each with its own random draws."),
    Output("timestep", "identifier", "int64", "days since the origin, a whole number", "always",
           "The day the row describes: 0 is the state at the end of the origin day and t the state at the end of day "
           "origin + t."),
    Output("time", "identifier", "float64", "days since the origin, timestep times `dt`", "always",
           "The model time of the row, which equals the timestep because the lifecycle clock is one UTC day per step."),
    Output("variable", "identifier", "object (str)", "text, no unit", "always",
           "The name of the whole-number state variable whose amount the row's `value` holds."),
    Output("value", "identifier", "int64", "the unit of the row's variable, listed in that variable's entry", "always",
           "The exact whole-number amount of the row's variable at the end of the row's day."),
    Output("specification", "identifier", "object (str)", "text, 16 hexadecimal characters, no unit", "always",
           "The first 16 characters of the SHA-256 hash of everything that decides the result: the model class, the run "
           "controls, the settings and the hashes of the input tables."),
    Output("model_version", "identifier", "object (str)", "text, no unit", "always",
           "The model version of the package that made the table."),

    # Whole-number state variables, always present.
    Output("active_validators", "variable", "int64", "a count of validator commitments, a stock at the end of the day", "always",
           "The validator commitments open at the end of the day."),
    Output("active_validator_stake_navax", "variable", "int64", STOCK, "always",
           "The validators' own stake in the commitments open at the end of the day, without delegations."),
    Output("returning_nodes", "variable", "int64", "a count of nodes, a stock at the end of the day", "always",
           "The nodes out of the active set that left within the last 365 days and can still return."),
    Output("supply_navax", "variable", "int64", STOCK, "always",
           "The P-Chain supply counter that the reward formula reads: the supply at the origin plus every potential "
           "reward minted since, and the part paid from revenue when `count_revenue_in_supply` is set. Realized total "
           "supply, which subtracts burned fees, is lower."),
    Output("issued_navax", "variable", "int64", FLOW, "always",
           "The potential rewards minted on the day for the commitments started that day, counted at their start as the "
           "supply counter counts them. Under revenue funding the count holds only the minted part, and in a model with "
           "delegations it holds the delegators' rewards as well as the validators'."),
    Output("started_stake_navax", "variable", "int64", FLOW, "always",
           "The stake of the validator commitments the model started on the day, without the commitments accepted before "
           "the origin that start that day."),
    Output("nakamoto_third_nodes", "variable", "int64", "a count of nodes, at the end of the day", "always",
           "The fewest nodes whose open own stake, each node's commitments summed, exceeds one third of all open validator "
           "own stake, and 0 when nothing is open."),

    # Float state variables, always present.
    Output("yield_gap_pp", "float", "float64", "percentage points of stake a year, a difference of two annual rates, on the day",
           "always",
           "The reward gap renewal reads on the day: the design's annual rate for a 30-day stake at the renewal tenure "
           "above the fitted reward formula's rate, less the outside yield's change from its fitting-window level, and "
           "less the share a funding rule left unpaid. The value at timestep 0 is 0."),
    Output("started_stake_days_navax", "float", "float64", "nAVAX times days on the day, a flow", "always",
           "The stake of each validator commitment the model started on the day times its committed days, summed."),
    Output("offered_rate_30d", "float", "float64", "a fraction of stake a year, 0.07 for 7% a year, on the day", "always",
           "The annual rate the reward rule offers a 30-day stake with no tenure, priced at noon of the day at the supply "
           "counter of the start of the day. The value at timestep 0 is missing, NaN."),

    # Delegations.
    Output("active_delegations", "variable", "int64", "a count of delegations, a stock at the end of the day", "delegations",
           "The delegations open at the end of the day."),
    Output("active_delegated_stake_navax", "variable", "int64", STOCK, "delegations",
           "The stake of the delegations open at the end of the day."),
    Output("benqi_delegated_stake_navax", "variable", "int64", STOCK, "delegations",
           "The stake of the open delegations of BENQI, the liquid staking provider."),
    Output(NAMED_OPERATOR, "variable", "int64", STOCK, "delegations",
           "One variable per operator named at the origin other than BENQI, with `<key>` the operator's key: the stake of "
           "the open delegations that operator owns. A model with no named operator has none."),
    Output("validator_issued_navax", "variable", "int64", FLOW, "delegations",
           "The potential rewards minted on the day for the validator commitments started that day, the validators' part "
           "of `issued_navax`."),
    Output("delegator_issued_navax", "variable", "int64", FLOW, "delegations",
           "The potential rewards minted on the day for the delegations placed that day, the delegators' part of "
           "`issued_navax`. Delegations open or accepted at the origin add none."),
    Output("unplaced_delegations", "variable", "int64", "a count of delegations on the day, a flow", "delegations",
           "The new delegations drawn on the day that were not made, because no validator had room for them or the "
           "unstaked supply did not cover their stake."),

    # Turnover.
    Output("ended_validators", "variable", "int64", "a count of validator commitments on the day, a flow", "turnover",
           "The validator commitments whose period ended on the day, renewed or not."),
    Output("renewed_validators", "variable", "int64", "a count of validator commitments on the day, a flow", "turnover",
           "The commitments that ended on the day and renewed at once on the same node, after the supply limit."),
    Output("first_ever_validators", "variable", "int64", "a count of validator commitments on the day, a flow", "turnover",
           "The commitments started on the day by nodes with no earlier commitment that are not returns, with those "
           "accepted before the origin and due that day."),

    # Revenue funding.
    Output("revenue_paid_navax", "variable", "int64", FLOW, "revenue",
           "The part of the day's priced rewards paid from the revenue pool instead of minted."),
    Output("unpaid_need_navax", "variable", "int64", FLOW, "revenue",
           "The revenue share of the day's priced rewards that the pool could not pay and the rule left unpaid. A rule that "
           "mints the shortfall leaves 0."),
    Output("revenue_pool_navax", "variable", "int64", STOCK, "revenue",
           "The revenue pool after the day's inflow of one 365th of `revenue_avax_pa` and the day's payments."),

    # Price.
    Output("price_usd", "float", "float64", "US dollars per AVAX, at the end of the day", "price",
           "The AVAX price on the run's seeded price path, which starts at `price0_usd` on the origin day."),

    # Holders.
    Output("etf_holdings_navax", "variable", "int64", STOCK, "holders",
           "The AVAX the funds of `fund_holdings` hold, summed, after the day's growth by their drift plus the price "
           "elasticity times the day's log return of the price."),
    Output("etf_validators", "variable", "int64", "a count of validators, a stock at the end of the day", "holders",
           "The validators the model made for the funds that are open at the end of the day."),
    Output("etf_validator_stake_navax", "variable", "int64", STOCK, "holders",
           "The own stake of the validators the model made for the funds that are open at the end of the day."),
    Output("liquid_staking_stake_navax", "variable", "int64", STOCK, "holders",
           "The liquid staking provider's open delegated stake, which equals `benqi_delegated_stake_navax`."),
    Output("nakamoto_third_operators", "variable", "int64", "a count of operators, at the end of the day", "holders",
           "The fewest operators whose weight, own stake plus the delegations on their validators, exceeds one third of "
           "all weight. A fund's model-made validators count as one operator, and every other node as its own."),
    Output("lst_target_navax", "float", "float64", f"{NAVAX}, a target stock held as a float, at the end of the day", "holders",
           "The liquid staking provider's target stock of delegated stake, grown each day by its drift plus the gap "
           "elasticity times the change in the liquid staker's yield gap since the origin. The provider starts "
           "delegations to bring its stake up to the target."),
    Output("liquid_staking_share", "float", "float64", "a share of all stake, own and delegated, 0 to 1, at the end of the day",
           "holders",
           "The liquid staking provider's open delegated stake over all open stake, validators' own and delegated."),
    Output("effective_operators", "float", "float64", "a number of operators, at least 1 when anything is staked, at the end of the day",
           "holders",
           "One over the Herfindahl index of the operators' shares of weight, own stake plus delegations, and 0 when "
           "nothing is staked."),

    # Daily-table columns that are not engine outputs, from kpis.run_daily_table and kpis.with_realized_supply.
    Output("supply_counter_navax", "daily", "int64", STOCK, "always",
           "The run's `supply_navax`, the P-Chain supply counter, under the name the chain's daily table gives it."),
    Output("issued_all_roles_navax", "daily", "int64", FLOW, "delegations",
           "The run's `issued_navax` in a model with delegations, validators' and delegators' rewards minted on the "
           "day. The daily table's `issued_navax` then holds `validator_issued_navax`, validators only, as the chain's "
           "table does."),
    Output("burned_navax", "daily", "float64", f"{NAVAX}, AVAX burned on the day, a flow", "always",
           "The transaction fees burned on the day. After the origin the function `kpis.with_realized_supply` holds it "
           "at the mean daily burn it is given, and a daily table without that step has no such column."),
    Output("total_supply_navax", "daily", "float64", STOCK, "always",
           "Realized total supply, minted less burned. After the origin the function `kpis.with_realized_supply` "
           "builds it from the supply at the origin plus each day's issuance of every role less the burn, and a "
           "daily table without that step has no such column."),

    # The columns of kpis.kpi_table.
    Output("measure", "kpi_column", "object (str)", "text, no unit", "always",
           "The name of the row's measure, one of the `kpi` entries."),
    Output("horizon_days", "kpi_column", "int64", "days after the origin", "always",
           "The horizon the measure reads up to, counted in days from the origin."),
    Output("cost_level", "kpi_column", "object (str)", "text, no unit", "always",
           "The operating-cost level of a `return_margin` row, and the empty string on every other row."),
    Output("value", "kpi_column", "float64", "the unit of the row's measure, listed in that measure's `kpi` entry",
           "always", "The number of the row's measure at the row's horizon and cost level."),

    # KPI measures of kpis.kpi_table.
    Output("issued_navax", "kpi", "float64", f"{NAVAX}, minted from the day after the origin to the horizon, a flow summed",
           "always",
           "The validators' issuance over the horizon, as the 64-bit float that issuance saved divides. A run with "
           "delegations counts its validators' part, `validator_issued_navax`."),
    Output("issuance_saved", "kpi", "float64", "a share of the baseline's issuance over the same days, negative when the run issues more",
           "always",
           "One minus the run's issuance over the baseline's, the same run under the chain's rule. Given only with a "
           "baseline."),
    Output("validator_stake_retained", "kpi", "float64", "a ratio of validator stake to the baseline's at the horizon, 1 when equal",
           "always", "The validator stake at the horizon over the baseline's. Given only with a baseline."),
    Output("validator_stake_navax", "kpi", "float64", f"{NAVAX}, a stock at the end of the horizon day", "always",
           "The validators' own stake at the horizon."),
    Output("lowest_validator_stake_navax", "kpi", "float64",
           f"{NAVAX}, the lowest end-of-day stock from the day after the origin to the horizon", "always",
           "The lowest validator stake of any day of the horizon."),
    Output("active_validators", "kpi", "float64", "a count of validator commitments at the end of the horizon day", "always",
           "The validators active at the horizon."),
    Output("active_validators_retained", "kpi", "float64",
           "a ratio of active validators to the baseline's at the horizon, 1 when equal", "always",
           "The validators active at the horizon over the baseline's. Given only with a baseline."),
    Output("net_inflation", "kpi", "float64",
           "a share of realized total supply at the horizon, over the 365 days that end at the horizon", "always",
           "Issuance less burn over the 365 days that end at the horizon, over realized total supply at the horizon."),
    Output("net_inflation_on_rewards_paid", "kpi", "float64",
           "a share of realized total supply at the horizon, over the 365 days that end at the horizon", "always",
           "Net inflation with the rewards the chain paid in place of issuance. Only the chain's table has rewards paid."),
    Output("validator_staking_ratio", "kpi", "float64", "a share of realized total supply, 0 to 1, at the horizon", "always",
           "The validators' own stake at the horizon over realized total supply."),
    Output("staking_ratio_with_delegations", "kpi", "float64", "a share of realized total supply, 0 to 1, at the horizon",
           "delegations",
           "The validators' own stake plus delegated stake at the horizon over realized total supply."),
    Output("nakamoto_coefficient", "kpi", "float64", "a count of nodes at the horizon", "always",
           "The fewest nodes whose own stake exceeds one third of all validator own stake, at the horizon."),
    Output("liquid_staking_share", "kpi", "float64", "a share of all stake, own and delegated, 0 to 1, at the horizon", "holders",
           "The liquid staking provider's delegated stake over all stake at the horizon."),
    Output("nakamoto_operators", "kpi", "float64", "a count of operators at the horizon", "holders",
           "The fewest operators whose weight, own stake plus delegations, exceeds one third of all weight, at the horizon."),
    Output("effective_operators", "kpi", "float64", "a number of operators at the horizon", "holders",
           "One over the Herfindahl index of operator weights at the horizon."),
    Output("earned_rate", "kpi", "float64", "a fraction of stake a year, 0.07 for 7% a year", "always",
           "The annual reward rate on the commitments started over the horizon: 365 times issuance over stake-days."),
    Output("return_margin", "kpi", "float64", "a fraction of stake a year, one row per operating-cost level", "always",
           "The earned rate less the competing yield and the operating cost, each a fraction of stake a year."),
    Output("stake_weighted_duration", "kpi", "float64", "days", "always",
           "The committed days of the commitments started over the horizon, weighted by their stake."),
    Output("reward_rate_volatility", "kpi", "float64", "percentage points of stake a year, a sample standard deviation", "always",
           "The sample standard deviation of `offered_rate_30d` over the horizon, times 100."),
    Output("stake_volatility", "kpi", "float64", "natural-log units a day, a sample standard deviation", "always",
           "The sample standard deviation of the daily change in the natural log of validator stake, from the origin to "
           "the horizon."),
    Output("worst_30_day_stake_fall", "kpi", "float64", "a share of the stake 30 days earlier, negative for a fall", "always",
           "The largest fall in validator stake over any 30 days from the origin to the horizon."),
    Output("issuance_half_life", "kpi", "float64", "years", "always",
           "The years for the issuance left under the supply cap to halve at the pace of the last 365 days, or of the "
           "horizon when it is shorter."),
    Output("burn_to_issuance", "kpi", "float64", "AVAX burned per AVAX of rewards paid, a ratio", "always",
           "The AVAX burned per AVAX of rewards paid over the complete days of the horizon. Only the chain's table has "
           "rewards paid."),
    Output("price_usd", "kpi", "float64", "US dollars per AVAX at the horizon", "price",
           "The AVAX price at the horizon, from the run's price path."),
    Output("cost_of_attack_third_usd", "kpi", "float64", "US dollars at the horizon's price", "price",
           "The dollars of fresh stake an attacker needs to hold one third of all stake at the horizon, enough to halt "
           "the chain: half of the honest stake, own and delegated, times the price."),
    Output("cost_of_attack_two_thirds_usd", "kpi", "float64", "US dollars at the horizon's price", "price",
           "The dollars of fresh stake an attacker needs to hold two thirds of all stake at the horizon, enough to finalize "
           "at will: twice the honest stake, own and delegated, times the price."),
    Output("security_cover", "kpi", "float64", "a ratio of US dollars to US dollars, above 1 when an attack costs more", "price",
           "The cost of a one-third attack over the dollar value the stake is asked to secure. Given only with "
           "`secured_value_usd`."),
)

SETTINGS_NOTE = ("Every other column of the long table is a Param setting of the model, one column per setting, "
                 "holding the setting's value for the row's setting combination. A setting's unit is in its `doc` "
                 "string, and the function `schema.setting_names` lists the settings of a model.")


def entries(placement: str | None = None) -> list[Output]:
    """The schema's outputs, or those of one placement."""
    return [o for o in OUTPUTS if placement is None or o.placement == placement]


def lookup(name: str, placement: str) -> Output | None:
    """The output of ``name`` at ``placement``, with a named operator's stake matched by ``NAMED_OPERATOR``, or None."""
    for output in entries(placement):
        if output.name == name:
            return output
    if placement == "variable" and re.fullmatch(r".+_delegated_stake_navax", name):
        return next(o for o in OUTPUTS if o.name == NAMED_OPERATOR)
    return None


def groups(model: SimulationModel) -> frozenset[str]:
    """The groups whose outputs the model's long table carries."""
    from avalanche_research.model.delegated_lifecycle import DelegationMixin

    present = {"always"}
    if isinstance(model, DelegationMixin):
        present.add("delegations")
    if getattr(model, "record_turnover", False):
        present.add("turnover")
    if getattr(model, "funded", False):
        present.add("revenue")
    if getattr(model, "has_price", lambda: False)():
        present.add("price")
    if getattr(model, "_holder_settings", None) is not None:
        present.add("holders")
    return frozenset(present)


def expected(model: SimulationModel) -> dict[str, dict[str, Output]]:
    """The outputs the model's long table carries, by placement and then by name: the identifiers and float columns,
    and the state variables, with one entry per named operator's stake in place of ``NAMED_OPERATOR``."""
    present = groups(model)
    named = [name for _, name in model._tracked()] if "delegations" in present else []
    found: dict[str, dict[str, Output]] = {"identifier": {}, "variable": {}, "float": {}}
    for output in OUTPUTS:
        if output.placement not in found or output.group not in present:
            continue
        for name in (named if output.name == NAMED_OPERATOR else [output.name]):
            found[output.placement][name] = output
    return found


def setting_names(model: SimulationModel) -> list[str]:
    """The setting columns of the model's long table, one per Param setting the blocks read."""
    return list(model.settings())


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def render() -> str:
    """The schema as Markdown: one table of every output, after the placement and group codes it uses."""
    lines = [
        "# Outputs of the staking model",
        "",
        "`model.engine.run` returns one long table, and `model.kpis` derives a daily table and a table of measures from it. "
        "Each row below is one output of the fitted lifecycle or of a model built on it, with its unit and the group "
        "of settings that makes it appear. The module `model.schema` holds the entries, and its function `render` "
        "writes this table.",
        "",
        "Placements:",
        "",
        *(f"- `{code}`: {_cell(text)}." for code, text in PLACEMENTS.items()),
        "",
        "Groups:",
        "",
        *(f"- `{code}`: {_cell(text)}." for code, text in GROUPS.items()),
        "",
        "| Name | Placement | Group | Dtype | Unit | Description |",
        "| --- | --- | --- | --- | --- | --- |",
        *(f"| `{o.name}` | {o.placement} | {o.group} | {o.dtype} | {_cell(o.unit)} | {_cell(o.description)} |"
          for o in OUTPUTS),
        "",
        SETTINGS_NOTE,
        "",
    ]
    return "\n".join(lines)
