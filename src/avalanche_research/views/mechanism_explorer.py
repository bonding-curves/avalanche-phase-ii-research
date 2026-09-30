"""Notebook views of the mechanisms: rate curves, issuance on a cohort, admission, and a slider explorer.

Every function reads mechanism objects and a grouped cohort and returns a table, a plot, or a Panel layout.
Nothing here runs a simulation.
"""

from __future__ import annotations

from datetime import datetime

import holoviews as hv
import hvplot.pandas  # noqa: F401
import pandas as pd
import panel as pn

from avalanche_research.mechanisms import (
    AdmissionRule,
    ChainAdmission,
    ChainReward,
    RewardMechanism,
)

AVAX = 10**9


def repriced(cohort: pd.DataFrame, start: datetime) -> pd.DataFrame:
    """The cohort as if every stake started at ``start``."""
    out = cohort.copy()
    out["start"] = start
    return out


def issuance_table(mechanisms: list[RewardMechanism], cohort: pd.DataFrame, supply_navax: int, start: datetime) -> pd.DataFrame:
    """AVAX each mechanism would mint for the cohort, and its change against the chain."""
    stakes = repriced(cohort, start)
    chain = ChainReward().issuance_navax(stakes, supply_navax)
    rows = []
    for mechanism in mechanisms:
        minted = mechanism.issuance_navax(stakes, supply_navax)
        rows.append({"mechanism": mechanism.label, "issuance_avax": minted / AVAX, "change_vs_chain": minted / chain - 1})
    return pd.DataFrame(rows)


def curves_plot(mechanisms: list[RewardMechanism], supply_navax: int, start: datetime, completed_periods: int = 0) -> hv.Element:
    curves = pd.concat([m.curve(supply_navax, start, completed_periods=completed_periods) for m in mechanisms])
    return curves.hvplot.line(
        x="duration_days", y="annual_rate", by="mechanism", xlabel="Staking duration, days", ylabel="Annual rate",
        title="Annual reward rate by staking duration", height=360, width=640, legend="bottom_right",
    )


def admission_table(rules: list[AdmissionRule], validators: pd.DataFrame, start: datetime) -> pd.DataFrame:
    """Share of real validator periods each rule admits, by count and by AVAX. One row per period."""
    stakes = repriced(validators, start)
    rows = []
    for rule in rules:
        admitted = rule.admitted(stakes)["admitted"]
        rows.append({
            "rule": rule.label,
            "periods_admitted": admitted.mean(),
            "avax_admitted": stakes.loc[admitted, "stake_navax"].sum() / stakes["stake_navax"].sum(),
        })
    return pd.DataFrame(rows)


def admission_plot(rules: list[AdmissionRule]) -> hv.Element:
    curves = pd.concat([rule.curve() for rule in rules])
    return curves.hvplot.line(
        x="duration_days", y="min_stake_avax", by="mechanism", xlabel="Staking duration, days", ylabel="Minimum stake, AVAX",
        title="Minimum validator stake by duration", height=360, width=640, legend="top_right",
    )


def explorer(mechanism: RewardMechanism, cohort: pd.DataFrame, supply_navax: int, start: datetime) -> pn.viewable.Viewable:
    """Sliders for one mechanism's settings beside its curve against the chain and its issuance on the cohort."""
    stakes = repriced(cohort, start)
    chain_minted = ChainReward().issuance_navax(stakes, supply_navax)

    def view(**_changed):
        curve = curves_plot([ChainReward(), mechanism], supply_navax, start)
        minted = mechanism.issuance_navax(stakes, supply_navax)
        note = pn.pane.Markdown(
            f"**Issuance on the cohort:** {minted / AVAX:,.0f} AVAX, {minted / chain_minted - 1:+.1%} against the chain."
        )
        return pn.Column(curve, note)

    settings = [name for name in mechanism.param if name not in ("name", "label")]
    return pn.Row(pn.Param(mechanism, parameters=settings, show_name=False, width=260), pn.bind(view, **{s: mechanism.param[s] for s in settings}))


def admission_explorer(rule: AdmissionRule, validators: pd.DataFrame, start: datetime) -> pn.viewable.Viewable:
    """Sliders for an admission rule beside its curve against the chain and the share of real stakes it admits."""

    def view(**_changed):
        table = admission_table([ChainAdmission(), rule], validators, start)
        return pn.Column(admission_plot([ChainAdmission(), rule]), pn.pane.DataFrame(table.round(3), index=False))

    settings = [name for name in rule.param if name not in ("name", "label")]
    return pn.Row(pn.Param(rule, parameters=settings, show_name=False, width=260), pn.bind(view, **{s: rule.param[s] for s in settings}))
