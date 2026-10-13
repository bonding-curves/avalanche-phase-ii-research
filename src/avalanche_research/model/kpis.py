"""The key performance indicators of a run or of the chain, each one function of a daily table.

A daily table has one row per UTC day, indexed by date (a ``DatetimeIndex``), with these columns, all amounts in nAVAX:

==================================  ==========================================================================
``active_validators``               validators active at 23:59:59 UTC
``active_validator_stake_navax``    validator self-stake active at 23:59:59 UTC
``supply_counter_navax``            the P-Chain reward counter at the end of the day, which the reward formula reads
``issued_navax``                    potential rewards of validator commitments started that day: issuance on the
                                    counter's clock, validators only
``started_stake_navax``             stake of the validator commitments started that day
``started_stake_days_navax``        stake times committed days, summed over the same commitments
``offered_rate_30d``                the annual rate the reward rule offers a 30-day stake at the previous day's counter
``nakamoto_third_nodes``            fewest nodes whose self-stake exceeds one third of all validator self-stake
``burned_navax``                    AVAX burned on all chains, on complete days
``total_supply_navax``              realized total supply: minted less burned
``active_delegated_stake_navax``    delegated stake, for the chain-side comparison
==================================  ==========================================================================

For a run the table is the engine's long table of one run, pivoted (``run_daily_table``). Before the origin a run's
table is the chain's (``chain_daily_table``), so a trailing window can reach back. ``supply_navax`` in the model is
``supply_counter_navax`` here.

Every KPI takes the table, an ``origin`` (the last observed day) and a ``horizon`` in days, and reads the days
``origin + 1`` to ``origin + horizon``. Three read more. Stake volatility reads the origin day, for the first daily
change. Net inflation reads the 365 days that end at the horizon, which start before the origin when the horizon is
shorter than a year. The mean daily burn reads the 365 complete days that end at the origin. No function reads any
other day, so a KPI on a table that ends before the held-back test period (from 2025-11-19 16:00 UTC) reads nothing in
it.

The definitions follow these choices. Issuance is counted on the supply counter's clock, validators only, the
quantity the model computes exactly. A run's baseline is the chain's rule as it runs. Net inflation divides by
realized total supply. On a run that supply is built from the supply at the origin, with the burn held at the mean
daily burn of the 365 complete days to the origin. The return margin and the stake-weighted duration average over
commitments started in the run, not those accepted before the origin and scheduled to start after it. A run holds those
as scheduled and counts neither their issuance nor their stake, so the chain's table is built for an origin and leaves
them out of every started-commitment column after it (``chain_daily_table``). A chain table is scored only from the
origin it was built for. Decentralisation is the Nakamoto coefficient on nodes and self-stake. The operating cost is a
parameter, so a sweep can score three levels. Standard deviations are sample standard deviations.

A table with two rows for one day, a value that is not finite, or a ratio over a zero is refused with ``ValueError``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

import duckdb
import numpy as np
import pandas as pd

from avalanche_research.mechanisms import ChainReward
from avalanche_research.model.protocol import MAINNET_REWARD
from avalanche_research.model.replay import LOCKBOX_FIRST_DAY, daily_events

HORIZONS = (365, 180)
TRAILING_DAYS = 365
FALL_DAYS = 30
CAP_NAVAX = MAINNET_REWARD.supply_cap_navax
WEI_PER_NAVAX = 10**9
US_PER_DAY = 86_400_000_000
INSTANT_US = 86_399_000_000

DAILY_COLUMNS = (
    "active_validators",
    "active_validator_stake_navax",
    "supply_counter_navax",
    "issued_navax",
    "started_stake_navax",
    "started_stake_days_navax",
    "offered_rate_30d",
    "nakamoto_third_nodes",
    "burned_navax",
    "total_supply_navax",
    "active_delegated_stake_navax",
)
STARTED_COLUMNS = frozenset({
    "issued_navax", "issued_all_roles_navax", "started_stake_navax", "started_stake_days_navax", "started_validators",
})
NOT_IN_MODEL_YET: dict[str, str] = {}
"""Daily-table columns the model does not write yet, each with the reason a missing-column error gives. Empty since
the fitted lifecycle and every model built on it write started stake, stake-days, the Nakamoto count and the offered
rate."""


class MissingColumn(ValueError):
    """A KPI's input column is not in the daily table."""


@dataclass(frozen=True)
class Threshold:
    """Where a KPI fails. ``level`` is a fixed line, or None when the line is one minus the KPI ``complement_of``."""

    fails: str
    level: float | None
    complement_of: str | None
    source: str


@dataclass(frozen=True)
class Kpi:
    label: str
    unit: str
    better: str
    goal: str
    horizon: str
    threshold: Threshold | None


REPORTED = None
KPIS: dict[str, Kpi] = {
    "issuance_saved": Kpi(
        "Issuance saved", "share", "higher", "issuance saved, lower inflation", "365 and 180 days", REPORTED),
    "validator_stake_retained": Kpi(
        "Validator stake retained", "share", "higher", "stake-weighted security", "365 and 180 days",
        Threshold("below", None, "issuance_saved",
                  "A team default, not a Foundation figure: a run fails when its validator stake falls by a larger "
                  "share than its issuance is saved. It follows from stake-weighted security as the main limit")),
    "active_validators": Kpi(
        "Active validators", "count", "higher", "validator participation", "365 and 180 days", REPORTED),
    "net_inflation": Kpi(
        "Net inflation", "share a year", "lower", "lower inflation", "365 and 180 days",
        Threshold("above", 0.05, None,
                  "The Foundation called net inflation above 5% a year high, and said it should have no fixed "
                  "target (research call of 2026-07-03)")),
    "validator_staking_ratio": Kpi(
        "Validator staking ratio", "share", "within a band", "stake-weighted security", "365 and 180 days", REPORTED),
    "nakamoto_coefficient": Kpi(
        "Nakamoto coefficient", "count", "higher", "decentralisation", "365 and 180 days", REPORTED),
    "return_margin": Kpi(
        "Return margin", "share a year", "higher", "incentive alignment", "whole run",
        Threshold("below", 0.0, None, "The grant proposal's validator profitability above zero")),
    "stake_weighted_duration": Kpi(
        "Stake-weighted committed duration", "days", "higher", "longer duration", "whole run", REPORTED),
    "reward_rate_volatility": Kpi(
        "Reward-rate volatility", "percentage points", "lower", "incentive alignment, stability", "whole run", REPORTED),
    "stake_volatility": Kpi(
        "Stake volatility", "share a day", "lower", "stability", "whole run", REPORTED),
    "issuance_half_life": Kpi(
        "Issuance half-life", "years", "higher", "issuance saved", "365 days", REPORTED),
    "burn_to_issuance": Kpi(
        "Burn-to-issuance ratio", "share", "higher", "issuance saved", "chain only", REPORTED),
}


# Reading the table.

def _day(value) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def _require(daily: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [name for name in columns if name not in daily.columns]
    if missing:
        reasons = [NOT_IN_MODEL_YET[name] for name in missing if name in NOT_IN_MODEL_YET]
        raise MissingColumn(f"the daily table has no {', '.join(missing)} column" + "".join(f". Today {r}" for r in reasons))


def _one_row_a_day(daily: pd.DataFrame) -> None:
    if not isinstance(daily.index, pd.DatetimeIndex):
        raise TypeError("the daily table must be indexed by day, as a DatetimeIndex")
    days = daily.index.normalize()
    if not days.is_unique:
        raise ValueError(f"the daily table has more than one row for {days[days.duplicated()][0].date()}")
    if (daily.index != days).any():
        raise ValueError("each row of the daily table must be dated at midnight of its day")
    if not daily.index.is_monotonic_increasing:
        raise ValueError("the daily table's days must be in increasing order")


def _finite(rows: pd.DataFrame) -> None:
    """Refuse an infinite value. A missing value is left to the caller."""
    values = rows.to_numpy(dtype=float, na_value=np.nan)
    bad = np.isinf(values)
    if bad.any():
        row, column = np.argwhere(bad)[0]
        raise ValueError(f"the daily table's {rows.columns[column]} on {rows.index[row].date()} is not finite")


def _same_origin(daily: pd.DataFrame, origin, columns: Iterable[str]) -> None:
    """Refuse to read a chain table's started commitments from another origin than the one it was built for."""
    built = daily.attrs.get("origin")
    if built is not None and _day(built) != _day(origin) and STARTED_COLUMNS.intersection(columns):
        raise ValueError(f"the chain table was built for the origin {_day(built).date()}, so its started commitments "
                         f"after that day leave out those it held as scheduled. Build it for {_day(origin).date()}")


def _rows(daily: pd.DataFrame, first, last, columns: Iterable[str], complete: bool = True) -> pd.DataFrame:
    """The rows from ``first`` to ``last`` inclusive, every day present once, every value finite, and every value
    present when ``complete``."""
    columns = list(columns)
    _require(daily, columns)
    _one_row_a_day(daily)
    days = pd.date_range(_day(first), _day(last), freq="D")
    absent = days.difference(daily.index)
    if len(absent):
        raise ValueError(f"the daily table has no row for {absent[0].date()}")
    rows = daily.loc[days, columns]
    if complete and rows.isna().any().any():
        column = rows.columns[rows.isna().any()][0]
        raise ValueError(f"the daily table has no {column} on {rows.index[rows[column].isna()][0].date()}")
    _finite(rows)
    return rows


def _run(daily: pd.DataFrame, origin, horizon: int, columns: Iterable[str], complete: bool = True) -> pd.DataFrame:
    """Days 1 to ``horizon`` after the origin."""
    if horizon < 1:
        raise ValueError("the horizon must be at least one day")
    _same_origin(daily, origin, columns)
    start = _day(origin) + pd.Timedelta(1, unit="D")
    return _rows(daily, start, _day(origin) + pd.Timedelta(horizon, unit="D"), columns, complete)


def _at_horizon(daily: pd.DataFrame, origin, horizon: int, column: str) -> float:
    return _run(daily, origin, horizon, [column])[column].iloc[-1]


def _nonzero(value: float, what: str, origin, horizon: int) -> float:
    if value == 0:
        day = (_day(origin) + pd.Timedelta(horizon, unit="D")).date()
        raise ValueError(f"{what} on {day} is zero, so the ratio is undefined")
    return value


# The KPIs.

def issuance_saved(daily: pd.DataFrame, baseline: pd.DataFrame, origin, horizon: int) -> float:
    """One minus the run's issuance over the baseline's, from the day after the origin to the horizon."""
    ours = _run(daily, origin, horizon, ["issued_navax"])["issued_navax"].sum()
    theirs = _run(baseline, origin, horizon, ["issued_navax"])["issued_navax"].sum()
    if theirs <= 0:
        raise ValueError("the baseline issues nothing over the horizon")
    return float(1 - ours / theirs)


def validator_stake_retained(daily: pd.DataFrame, baseline: pd.DataFrame, origin, horizon: int) -> float:
    """Validator stake at the horizon over the baseline's."""
    column = "active_validator_stake_navax"
    theirs = _nonzero(_at_horizon(baseline, origin, horizon, column), "the baseline's validator stake", origin, horizon)
    return float(_at_horizon(daily, origin, horizon, column) / theirs)


def validator_stake_at_horizon(daily: pd.DataFrame, origin, horizon: int) -> int:
    """Validator stake at the horizon, in nAVAX."""
    return int(_at_horizon(daily, origin, horizon, "active_validator_stake_navax"))


def lowest_validator_stake(daily: pd.DataFrame, origin, horizon: int) -> int:
    """The lowest validator stake from the day after the origin to the horizon, in nAVAX."""
    return int(_run(daily, origin, horizon, ["active_validator_stake_navax"])["active_validator_stake_navax"].min())


def active_validators(daily: pd.DataFrame, origin, horizon: int) -> int:
    """Validators active at the horizon."""
    return int(_at_horizon(daily, origin, horizon, "active_validators"))


def active_validators_retained(daily: pd.DataFrame, baseline: pd.DataFrame, origin, horizon: int) -> float:
    """Validators active at the horizon over the baseline's."""
    theirs = _nonzero(active_validators(baseline, origin, horizon), "the baseline's active validators", origin, horizon)
    return active_validators(daily, origin, horizon) / theirs


def _complete_days(rows: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """The rows of complete ledger days. With the ledger's ``ledger_complete`` flag, a complete day missing a value is
    refused and an incomplete day is skipped. Without the flag, a missing value marks an incomplete day."""
    if "ledger_complete" in rows.columns:
        complete = rows[rows["ledger_complete"].eq(True)]
        if complete[columns].isna().any().any():
            raise ValueError(f"a complete ledger day is missing a value in {', '.join(columns)}")
        return complete[columns]
    return rows[columns].dropna()


def mean_daily_burn(daily: pd.DataFrame, origin) -> float:
    """The mean burn of the 365 complete days that end at the origin, skipping days without a burn."""
    _require(daily, ["burned_navax"])
    _one_row_a_day(daily)
    known = _complete_days(daily.loc[daily.index <= _day(origin)], ["burned_navax"])
    _finite(known)
    known = known["burned_navax"]
    if len(known) < TRAILING_DAYS:
        raise ValueError(f"fewer than {TRAILING_DAYS} complete days of burn up to the origin")
    return float(known.iloc[-TRAILING_DAYS:].mean())


def with_realized_supply(daily: pd.DataFrame, origin, starting_supply_navax: float, burn_navax_per_day: float) -> pd.DataFrame:
    """The table with burn and realized supply filled after the origin: the burn held fixed, and supply equal to the
    starting supply plus the run's issuance less that burn, day by day. Days up to the origin are unchanged."""
    _require(daily, ["issued_navax"])
    _one_row_a_day(daily)
    if not (math.isfinite(starting_supply_navax) and math.isfinite(burn_navax_per_day)):
        raise ValueError("the starting supply or the burn a day is not finite")
    filled = daily.sort_index().copy()
    after = filled.index > _day(origin)
    issued = filled.loc[after, "issued_navax"]
    if issued.isna().any():
        raise ValueError(f"the daily table has no issued_navax on {issued.index[issued.isna()][0].date()}")
    _finite(filled.loc[after, ["issued_navax"]])
    filled.loc[after, "burned_navax"] = float(burn_navax_per_day)
    filled.loc[after, "total_supply_navax"] = float(starting_supply_navax) + (issued - float(burn_navax_per_day)).cumsum()
    return filled


def _supplied(daily, origin, starting_supply_navax, burn_navax_per_day) -> pd.DataFrame:
    if (starting_supply_navax is None) != (burn_navax_per_day is None):
        raise ValueError("give both the starting supply and the burn, or neither")
    if starting_supply_navax is None:
        return daily
    return with_realized_supply(daily, origin, starting_supply_navax, burn_navax_per_day)


def net_inflation(daily: pd.DataFrame, origin, horizon: int, starting_supply_navax: float | None = None,
                  burn_navax_per_day: float | None = None, issuance: str = "issued_navax") -> float:
    """Issuance less burn over the 365 days that end at the horizon, over realized supply at the horizon.

    On a run, give the realized supply at the origin and the burn a day, and both are built after the origin
    (``with_realized_supply``). ``issuance`` names another issuance column, such as the chain's rewards paid.
    """
    daily = _supplied(daily, origin, starting_supply_navax, burn_navax_per_day)
    _same_origin(daily, origin, [issuance])
    end = _day(origin) + pd.Timedelta(horizon, unit="D")
    rows = _rows(daily, end - pd.Timedelta(TRAILING_DAYS - 1, unit="D"), end, [issuance, "burned_navax", "total_supply_navax"])
    supply = _nonzero(rows["total_supply_navax"].iloc[-1], "realized supply", origin, horizon)
    return float((rows[issuance].sum() - rows["burned_navax"].sum()) / supply)


def validator_staking_ratio(daily: pd.DataFrame, origin, horizon: int, with_delegations: bool = False,
                            starting_supply_navax: float | None = None, burn_navax_per_day: float | None = None) -> float:
    """Validator stake at the horizon, with delegated stake when asked, over realized supply."""
    daily = _supplied(daily, origin, starting_supply_navax, burn_navax_per_day)
    columns = ["active_validator_stake_navax", "total_supply_navax"] + (["active_delegated_stake_navax"] if with_delegations else [])
    row = _run(daily, origin, horizon, columns).iloc[-1]
    staked = row["active_validator_stake_navax"] + (row["active_delegated_stake_navax"] if with_delegations else 0)
    return float(staked / _nonzero(row["total_supply_navax"], "realized supply", origin, horizon))


def nakamoto_count(stakes: Iterable[float]) -> int:
    """The fewest holders whose stakes together exceed one third of the total."""
    ordered = sorted((int(s) for s in stakes), reverse=True)
    total, held = sum(ordered), 0
    for count, stake in enumerate(ordered, start=1):
        held += stake
        if 3 * held > total:
            return count
    raise ValueError("no stake")


def nakamoto_coefficient(daily: pd.DataFrame, origin, horizon: int) -> int:
    """The fewest nodes whose self-stake exceeds one third of all validator self-stake, at the horizon."""
    return int(_at_horizon(daily, origin, horizon, "nakamoto_third_nodes"))


def earned_rate(daily: pd.DataFrame, origin, horizon: int) -> float:
    """The annual reward rate on the commitments started in the run: 365 times issuance over stake-days."""
    rows = _run(daily, origin, horizon, ["issued_navax", "started_stake_days_navax"])
    stake_days = rows["started_stake_days_navax"].sum()
    if stake_days <= 0:
        raise ValueError("no commitment starts in the run")
    return float(365 * rows["issued_navax"].sum() / stake_days)


def return_margin(daily: pd.DataFrame, origin, horizon: int, competing_yield: float, operating_cost: float) -> float:
    """The earned rate less the competing yield and the operating cost, each a share of stake a year."""
    return earned_rate(daily, origin, horizon) - competing_yield - operating_cost


def stake_weighted_duration(daily: pd.DataFrame, origin, horizon: int) -> float:
    """Committed days of the commitments started in the run, weighted by stake."""
    rows = _run(daily, origin, horizon, ["started_stake_navax", "started_stake_days_navax"])
    stake = rows["started_stake_navax"].sum()
    if stake <= 0:
        raise ValueError("no commitment starts in the run")
    return float(rows["started_stake_days_navax"].sum() / stake)


def reward_rate_volatility(daily: pd.DataFrame, origin, horizon: int) -> float:
    """The standard deviation of the rate offered to a 30-day stake, in percentage points."""
    return float(100 * _run(daily, origin, horizon, ["offered_rate_30d"])["offered_rate_30d"].std())


def _stake_from_origin(daily, origin, horizon) -> np.ndarray:
    column = "active_validator_stake_navax"
    stake = _rows(daily, origin, _day(origin) + pd.Timedelta(horizon, unit="D"), [column])[column]
    if (stake <= 0).any():
        raise ValueError(f"validator stake on {stake.index[stake <= 0][0].date()} is not positive, so its change is undefined")
    return stake.to_numpy(dtype=float)


def stake_volatility(daily: pd.DataFrame, origin, horizon: int) -> float:
    """The standard deviation of the daily change in the log of validator stake, from the origin to the horizon."""
    if horizon < 2:
        raise ValueError("the horizon must be at least two days")
    return float(np.std(np.diff(np.log(_stake_from_origin(daily, origin, horizon))), ddof=1))


def worst_30_day_stake_fall(daily: pd.DataFrame, origin, horizon: int) -> float:
    """The largest fall in validator stake over any 30 days from the origin to the horizon, as a negative share."""
    if horizon < FALL_DAYS:
        raise ValueError(f"the horizon must be at least {FALL_DAYS} days")
    stake = _stake_from_origin(daily, origin, horizon)
    return float(np.min(stake[FALL_DAYS:] / stake[:-FALL_DAYS] - 1))


def issuance_half_life(daily: pd.DataFrame, origin, horizon: int) -> float:
    """Years for the issuance left under the cap to halve at the pace of the last ``min(365, horizon)`` days."""
    _same_origin(daily, origin, ["issued_navax"])
    days = min(TRAILING_DAYS, horizon)
    end = _day(origin) + pd.Timedelta(horizon, unit="D")
    issued = _rows(daily, end - pd.Timedelta(days - 1, unit="D"), end, ["issued_navax"])["issued_navax"].sum()
    remaining = CAP_NAVAX - _rows(daily, end, end, ["supply_counter_navax"])["supply_counter_navax"].iloc[-1]
    if issued <= 0:
        raise ValueError("nothing is issued in the window")
    return float(math.log(2) * remaining / (issued * 365 / days))


def burn_to_issuance(daily: pd.DataFrame, origin, horizon: int) -> float:
    """AVAX burned per AVAX of rewards paid, over the complete days of the window. The chain only."""
    columns = ["burned_navax", "rewards_paid_navax"]
    flag = ["ledger_complete"] if "ledger_complete" in daily.columns else []
    rows = _complete_days(_run(daily, origin, horizon, [*columns, *flag], complete=False), columns)
    if rows.empty or rows["rewards_paid_navax"].sum() <= 0:
        raise ValueError("no complete day with rewards paid in the window")
    return float(rows["burned_navax"].sum() / rows["rewards_paid_navax"].sum())


# Every KPI for one run or the chain.

def kpi_table(daily: pd.DataFrame, origin, horizons: Iterable[int] = HORIZONS, *, competing_yield: float,
              operating_costs: Mapping[str, float], baseline: pd.DataFrame | None = None,
              starting_supply_navax: float | None = None, burn_navax_per_day: float | None = None,
              missing: str = "raise") -> pd.DataFrame:
    """Every KPI at each horizon, one row per measure, horizon and cost level.

    The measures relative to a baseline need ``baseline``, the same run under the chain's rule. The return margin has
    one row per entry of ``operating_costs``. The chain's rewards paid, when the table has them, add net inflation on
    rewards paid and the burn-to-issuance ratio. Delegated stake, when present, adds the staking ratio with
    delegations. ``missing="skip"`` leaves out a measure whose column the table lacks instead of raising.
    """
    if missing not in ("raise", "skip"):
        raise ValueError("missing is 'raise' or 'skip'")
    daily = _supplied(daily, origin, starting_supply_navax, burn_navax_per_day)
    rows = []

    def add(measure, horizon, function, *args, cost_level="", **kwargs):
        try:
            value = function(*args, **kwargs)
        except MissingColumn:
            if missing == "raise":
                raise
            return
        rows.append({"measure": measure, "horizon_days": horizon, "cost_level": cost_level, "value": value})

    paid = "rewards_paid_navax" in daily.columns
    for h in horizons:
        if baseline is not None:
            add("issuance_saved", h, issuance_saved, daily, baseline, origin, h)
            add("validator_stake_retained", h, validator_stake_retained, daily, baseline, origin, h)
        add("validator_stake_navax", h, validator_stake_at_horizon, daily, origin, h)
        add("lowest_validator_stake_navax", h, lowest_validator_stake, daily, origin, h)
        add("active_validators", h, active_validators, daily, origin, h)
        if baseline is not None:
            add("active_validators_retained", h, active_validators_retained, daily, baseline, origin, h)
        add("net_inflation", h, net_inflation, daily, origin, h)
        if paid:
            add("net_inflation_on_rewards_paid", h, net_inflation, daily, origin, h, issuance="rewards_paid_navax")
        add("validator_staking_ratio", h, validator_staking_ratio, daily, origin, h)
        if "active_delegated_stake_navax" in daily.columns:
            add("staking_ratio_with_delegations", h, validator_staking_ratio, daily, origin, h, with_delegations=True)
        add("nakamoto_coefficient", h, nakamoto_coefficient, daily, origin, h)
        add("earned_rate", h, earned_rate, daily, origin, h)
        for level, cost in operating_costs.items():
            add("return_margin", h, return_margin, daily, origin, h, competing_yield, cost, cost_level=level)
        add("stake_weighted_duration", h, stake_weighted_duration, daily, origin, h)
        add("reward_rate_volatility", h, reward_rate_volatility, daily, origin, h)
        add("stake_volatility", h, stake_volatility, daily, origin, h)
        add("worst_30_day_stake_fall", h, worst_30_day_stake_fall, daily, origin, h)
        add("issuance_half_life", h, issuance_half_life, daily, origin, h)
        if paid:
            add("burn_to_issuance", h, burn_to_issuance, daily, origin, h)
    return pd.DataFrame(rows, columns=["measure", "horizon_days", "cost_level", "value"])


# Daily tables.

CHAIN_REBUILT_COLUMNS = ("burned_navax", "total_supply_navax")
"""Chain columns a run does not produce but the measures rebuild after the origin from the chain's days before it."""


def run_daily_table(table: pd.DataFrame, origin, chain: pd.DataFrame | None = None) -> pd.DataFrame:
    """One run of the engine's long table as a daily table, after the chain's days up to the origin when given.

    Timestep ``t`` is the day ``origin + t``. With ``chain``, the origin and every day before it come from the chain,
    in the daily-table columns the run also produces, plus burn and realized supply, and the chain's table must be
    built for the same origin. A variable with two
    values at one timestep is refused.
    """
    keys = [key for key in ("simulation", "run") if key in table.columns]
    if len(table[keys].drop_duplicates()) != 1:
        raise ValueError("run_daily_table takes one run of one simulation: filter the long table first")
    repeated = table[table.duplicated(["timestep", "variable"])]
    if len(repeated):
        first = repeated.iloc[0]
        raise ValueError(f"the long table has more than one {first['variable']} at timestep {first['timestep']}")
    wide = table.pivot_table(index="timestep", columns="variable", values="value", aggfunc="first")
    for column in DAILY_COLUMNS:
        if column in table.columns:
            values = table.groupby("timestep")[column]
            conflicting = values.nunique(dropna=False) > 1
            if conflicting.any():
                raise ValueError(f"the long table has more than one {column} at timestep {conflicting.idxmax()}")
            wide[column] = values.first()
    wide = wide.rename(columns={"supply_navax": "supply_counter_navax"})
    wide.columns.name = None
    wide.index = _day(origin) + pd.to_timedelta(wide.index, unit="D")
    if chain is None:
        return wide
    _same_origin(chain, origin, STARTED_COLUMNS)
    # The chain supplies the days up to the origin in the columns the run continues after it, and burn and realized
    # supply, which the measures rebuild after the origin. Any other chain column would be empty after the origin.
    kept = [c for c in chain.columns if c in DAILY_COLUMNS and (c in wide.columns or c in CHAIN_REBUILT_COLUMNS)]
    before = chain.loc[chain.index <= _day(origin), kept]
    return pd.concat([before, wide.loc[wide.index > _day(origin)]])


def _start_day(column: str) -> str:
    """The UTC day whose 23:59:59 is the first at or after a timestamp, as the replay counts days."""
    return f"(epoch_us({column}) - {INSTANT_US} + {US_PER_DAY} - 1) // {US_PER_DAY}"


STARTS_SQL = f"""
WITH p AS (
    SELECT role, stake_navax, duration_days, potential_reward_navax, supply_before_navax, start_time,
           {_start_day("start_time")} AS day,
           coalesce(epoch_us(start_time) > $cutoff AND epoch_us(accepted_at) <= $cutoff, false) AS scheduled
    FROM read_parquet($periods) WHERE start_time IS NOT NULL
)
SELECT day,
       sum(potential_reward_navax) FILTER (WHERE role = 'validator' AND NOT scheduled)::BIGINT AS issued_navax,
       sum(potential_reward_navax) FILTER (WHERE NOT scheduled)::BIGINT AS issued_all_roles_navax,
       sum(stake_navax) FILTER (WHERE role = 'validator' AND NOT scheduled)::BIGINT AS started_stake_navax,
       sum(stake_navax::DOUBLE * duration_days) FILTER (WHERE role = 'validator' AND NOT scheduled) AS started_stake_days_navax,
       count(*) FILTER (WHERE role = 'validator' AND NOT scheduled) AS started_validators,
       arg_max(supply_before_navax + potential_reward_navax, (start_time, supply_before_navax))
           FILTER (WHERE supply_before_navax IS NOT NULL AND potential_reward_navax IS NOT NULL) AS supply_counter_navax
FROM p GROUP BY 1 ORDER BY 1
"""

NAKAMOTO_SQL = f"""
WITH v AS (
    SELECT node_id, stake_navax, {_start_day("start_time")} AS enter_day,
           {_start_day("greatest(end_time, coalesce(last_cycle_end_time, end_time))")} AS leave_day
    FROM read_parquet(?)
    WHERE role = 'validator' AND start_time IS NOT NULL AND end_time IS NOT NULL AND stake_navax IS NOT NULL
),
days AS (SELECT range AS day FROM range(?, ?)),
held AS (
    SELECT d.day, v.node_id, sum(v.stake_navax) AS stake
    FROM days d JOIN v ON v.enter_day <= d.day AND d.day < v.leave_day
    GROUP BY 1, 2
),
ranked AS (
    SELECT day, coalesce(sum(stake) OVER (PARTITION BY day ORDER BY stake DESC, node_id
                                          ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS above,
           sum(stake) OVER (PARTITION BY day) AS total
    FROM held
)
SELECT day, count(*) FILTER (WHERE 3 * above <= total) AS nakamoto_third_nodes FROM ranked GROUP BY 1 ORDER BY 1
"""

LEDGER_SQL = """
SELECT date_utc, complete, burned_wei::VARCHAR AS burned, total_supply_close_wei::VARCHAR AS supply,
       issued_rewards_wei::VARCHAR AS paid
FROM read_parquet(?) ORDER BY date_utc
"""


def chain_daily_table(periods_parquet: str, ledger_parquet: str, origin: date,
                      through: date = LOCKBOX_FIRST_DAY) -> pd.DataFrame:
    """The chain's daily table for a run from ``origin``, every day before ``through``, which may not pass the
    held-back test period.

    Active stake and counts are the replay of the staking periods. Issuance, started stake and the counter come from
    the periods by start day. After the origin, issuance, started stake, stake-days and the count of starts leave out
    the commitments accepted by the end of the origin day that start after it. A run from that origin holds them as
    scheduled and counts none of them, so the two count the same commitments. The table records its origin, and a KPI
    that reads those columns refuses another origin. The counter reads every start. At a day's end it is the reading
    after the day's last start, carried over days without one. It leaves out a fall in the counter after that start,
    when a commitment ends without its reward.
    The offered rate prices a 30-day stake at noon by the chain's rule at the previous day's counter.
    Burn, realized supply and rewards paid come from the ledger, on complete days only. Four columns serve the chain
    side alone: ``issued_all_roles_navax`` (validators and delegators on the counter's clock), ``rewards_paid_navax``
    (all roles, when paid), ``started_validators`` and ``ledger_complete``, whether the ledger's day is complete.
    """
    if _day(origin) >= _day(through):
        raise ValueError(f"the origin {origin} must be before {through}, the day the table stops")
    events = daily_events(periods_parquet, through)
    first = (pd.Timestamp(events["date_utc"].iloc[0]) - pd.Timestamp(0)).days
    last = first + len(events) - 1
    index = pd.DatetimeIndex(pd.to_datetime(events["date_utc"]), name="date")
    daily = pd.DataFrame(index=index)
    daily["active_validators"] = events["d_validators"].cumsum().to_numpy()
    daily["active_validator_stake_navax"] = events["d_validator_stake"].cumsum().to_numpy()
    daily["active_delegated_stake_navax"] = events["d_delegated_stake"].cumsum().to_numpy()

    def by_day(frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame[(frame["day"] >= first) & (frame["day"] <= last)]
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame["day"] * 86_400, unit="s"), name="date")
        frame = frame.drop(columns="day")
        # Integer columns become nullable integers first, so the days the reindex adds do not pass them through float.
        integers = [c for c in frame.columns if pd.api.types.is_integer_dtype(frame[c])]
        frame[integers] = frame[integers].astype("Int64")
        return frame.reindex(index)

    cutoff = _day(origin).value // 1_000 + INSTANT_US
    starts = by_day(duckdb.execute(STARTS_SQL, {"periods": periods_parquet, "cutoff": cutoff}).df())
    for column in ("issued_navax", "issued_all_roles_navax", "started_stake_navax", "started_validators"):
        daily[column] = starts[column].fillna(0).astype(np.int64)
    daily["started_stake_days_navax"] = starts["started_stake_days_navax"].fillna(0.0)
    daily["supply_counter_navax"] = starts["supply_counter_navax"].astype("Int64").ffill()

    held = by_day(duckdb.execute(NAKAMOTO_SQL, [periods_parquet, first, last + 1]).df())
    daily["nakamoto_third_nodes"] = held["nakamoto_third_nodes"].astype("float64")

    reward = ChainReward()
    previous = daily["supply_counter_navax"].shift(1)
    daily["offered_rate_30d"] = [
        np.nan if pd.isna(s) else reward.annual_rate(30, int(s), datetime.combine(day.date(), time(12), tzinfo=UTC))
        for day, s in previous.items()
    ]

    ledger = duckdb.execute(LEDGER_SQL, [ledger_parquet]).df()
    ledger.index = pd.DatetimeIndex(pd.to_datetime(ledger["date_utc"]), name="date")
    ledger = ledger.reindex(index)
    complete = ledger["complete"].eq(True)
    for column, source in (("burned_navax", "burned"), ("total_supply_navax", "supply"), ("rewards_paid_navax", "paid")):
        values = [int(v) / WEI_PER_NAVAX if ok and v is not None else np.nan for v, ok in zip(ledger[source], complete)]
        daily[column] = np.asarray(values, dtype=float)
    daily["ledger_complete"] = complete.to_numpy()
    daily = daily[[*DAILY_COLUMNS, "issued_all_roles_navax", "rewards_paid_navax", "started_validators", "ledger_complete"]]
    daily.attrs["origin"] = _day(origin)
    return daily
