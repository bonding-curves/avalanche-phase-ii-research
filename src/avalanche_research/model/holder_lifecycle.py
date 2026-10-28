"""The delegated lifecycle with holder types: liquid staking, funds, institutional and small operators, and delegators.

:class:`HolderMixin` adds the holder rules of :mod:`~avalanche_research.model.parts.holders` to a delegated lifecycle
behind one setting, ``holders``, a dictionary of the four sections' values. At its default, None, the mixin changes
nothing: the stages, the state variables, the specification and its hash are the delegated lifecycle's, so every run
recorded with v0.8.1 keeps its hash and table. :class:`HolderLifecycle` puts it on
:class:`~avalanche_research.model.delegated_lifecycle.DelegatedLifecycle`, the v0.8 build with delegations, and
:class:`HolderStakeLifecycle` on :class:`~avalanche_research.model.delegated_lifecycle.DelegatedStakeLifecycle`, the
v0.8.1 candidate's build.

With ``holders`` set, the daily step becomes: the renewal stage with the institutional redecision and the funds'
mandate, the returns and arrivals stages unchanged, the continuation stage with the funds' terms and the validators
they add, the rewards stage, the assembly stage with a fund's leavers dropped, the delegations stage with BENQI's count
from its target stock and the other delegators' response, and last the holders stage, which writes the concentration
measures and the funds' holdings for tomorrow. Three inputs feed the rules: ``fund_holdings``, one row per fund at the
origin; ``benqi_stake_per_start_navax``, the mean stake of BENQI's starts over the 28 days before the origin; and
``holder_renewal_large``, the renewal logit fitted on the endings above the institutional line, a point estimate that
the parameter draws do not resample. When ``holders`` is None the three are left out of the specification, so a model
given them and not asked to use them keeps the delegated lifecycle's hash.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from functools import partial

import numpy as np
import pandas as pd
import param

from avalanche_research.model.delegated_lifecycle import (
    DelegatedLifecycle,
    DelegatedStakeLifecycle,
    DelegationMixin,
)
from avalanche_research.model.fitted_lifecycle import FittedLifecycle
from avalanche_research.model.parts.holders import (
    FundTable,
    HolderSettings,
    HolderSetup,
    fund_of,
    holder_assembly_stage,
    holder_continuation_stage,
    holder_renewal_stage,
    holders_stage,
    lst_gap,
)
from avalanche_research.model.parts.renewal import RenewalLogit
from avalanche_research.model.stake_lifecycle import StakeLifecycle

HOLDER_VARIABLES = ("etf_holdings_navax", "etf_validators", "etf_validator_stake_navax", "liquid_staking_stake_navax",
                    "nakamoto_third_operators")
HOLDER_FLOAT_VARIABLES = ("lst_target_navax", "liquid_staking_share", "effective_operators")
HOLDER_INPUTS = ("fund_holdings", "holder_renewal_large", "benqi_stake_per_start_navax")
FUND_COLUMNS = ["fund", "holdings_navax", "staked_share", "validator_stake_navax", "min_days", "max_days"]
WRAPPED = ("renewal", "continuation", "assembly")


class HolderMixin(param.Parameterized):
    """The holder rules on a delegated lifecycle, off unless ``holders`` is given. Combined with a delegated lifecycle
    class, the mixin first in the base list."""

    holders = param.Dict(
        default=None, allow_None=True, metadata={"omit_at_default": True},
        doc="The holder rules' settings by section: liquid_staking (drift_per_day, gap_elasticity_per_day, defi_yield_pp, "
            "fee_share), funds (drift_per_day, price_elasticity, staked_share), operators (line_avax, response_scale) and "
            "delegators (response). None leaves the model as the delegated lifecycle",
    )
    fund_holdings = param.DataFrame(
        default=None, allow_None=True, precedence=-1,
        doc="The funds at the origin, one row each: fund, holdings_navax, staked_share, validator_stake_navax, min_days, max_days",
    )
    holder_renewal_large = param.ClassSelector(
        class_=RenewalLogit, default=None, allow_None=True,
        doc="The renewal block for commitments above the institutional line, a point estimate not resampled by the draws. "
            "None uses the base renewal block for every commitment",
    )
    benqi_stake_per_start_navax = param.Integer(
        default=0, bounds=(0, None),
        doc="The mean stake of BENQI's delegation starts over the 28 days before the origin, which each of its new "
            "delegations takes under the holder rules",
    )

    def __init__(self, **params):
        super().__init__(**params)
        self._holder_settings = HolderSettings.check(self.holders)
        if self._holder_settings is None:
            return
        if self._holder_settings.large_navax is not None and self.holder_renewal_large is None:
            raise ValueError("holders.operators.line_avax needs holder_renewal_large, the renewal block fitted above the line")
        self._funds = FundTable.from_frame(self.fund_holdings, self._holder_settings)
        if self.fund_holdings is not None and len(self.fund_holdings):
            missing = [c for c in FUND_COLUMNS if c not in self.fund_holdings.columns]
            if missing:
                raise ValueError(f"fund_holdings needs the columns {', '.join(missing)}")
        self._setup_cache = None
        stages = list(self.stages)
        names = [name for name, _ in stages]
        if names[-1] != "delegations" or not all(name in names for name in WRAPPED):
            raise ValueError("the holder rules need the delegated lifecycle's stages, ending in delegations")
        wrapped = []
        for name, stage in stages:
            if name == "renewal":
                stage = _Wrapped(self, holder_renewal_stage, stage)
            elif name == "continuation":
                stage = _Wrapped(self, holder_continuation_stage, stage)
            elif name == "assembly":
                stage = partial(holder_assembly_stage, base=stage, funds=self._funds)
            wrapped.append((name, stage))
        self.stages = (*wrapped, ("holders", _Wrapped(self, holders_stage, None)))

    # The holder setup, built on the first day a run steps, as the delegation setup is.

    def _holder_setup(self) -> HolderSetup:
        if self._setup_cache is None:
            start = datetime.combine(self.origin + timedelta(days=1), time(12), tzinfo=UTC)
            gap0 = lst_gap(self.mechanism, int(self.supply0_navax), start, self._holder_settings)
            self._setup_cache = HolderSetup(settings=self._holder_settings, funds=self._funds,
                                            benqi_stake_per_start_navax=int(self.benqi_stake_per_start_navax), lst_gap0=gap0,
                                            renewal_large=self.holder_renewal_large)
        return self._setup_cache

    def _setup(self):
        setup = super()._setup()
        if self._holder_settings is None:
            return setup
        from dataclasses import replace

        return replace(setup, holders=self._holder_setup())

    # What the engine records.

    # The delegated class each holder class is when its rules are off, which the specification then names.
    off_model: type | None = None

    def specification(self):
        specification = super().specification()
        if self._holder_settings is None:
            for name in HOLDER_INPUTS:
                specification.pop(name, None)
                specification["inputs_sha256"].pop(name, None)
            off = self.off_model
            if off is not None and specification.get("model") == f"{type(self).__module__}.{type(self).__qualname__}":
                specification["model"] = f"{off.__module__}.{off.__qualname__}"
        return specification

    def settings(self):
        settings = super().settings()
        if self._holder_settings is None:
            for name in HOLDER_INPUTS:
                settings.pop(name, None)
        return settings

    def state_variables(self):
        base = super().state_variables()
        return base if self._holder_settings is None else [*base, *HOLDER_VARIABLES]

    def float_variables(self):
        base = super().float_variables()
        return base if self._holder_settings is None else [*base, *HOLDER_FLOAT_VARIABLES]

    def initial_state(self):
        state = super().initial_state()
        if self._holder_settings is None:
            return state
        benqi = int(state["delegation_stakes"][state["delegation_benqi"]].sum())
        total = int(state["stakes"].sum()) + int(state["delegation_stakes"].sum())
        from avalanche_research.model.parts.delegations import on_validators, stake_on
        from avalanche_research.model.parts.holders import (
            effective_operators,
            nakamoto_operators,
            operator_weights,
        )

        on = stake_on(len(state["node_key"]), on_validators(state["node_key"], state["delegation_validator"]), state["delegation_stakes"])
        weights = operator_weights(state["node_key"], state["stakes"], on)
        return {
            **state,
            "fund_holdings_navax": self._funds.holdings0_navax.copy(),
            "lst_target_navax": float(benqi),
            "etf_holdings_navax": int(self._funds.holdings0_navax.sum()),
            "etf_validators": 0,
            "etf_validator_stake_navax": 0,
            "liquid_staking_stake_navax": benqi,
            "liquid_staking_share": (benqi / total) if total else 0.0,
            "nakamoto_third_operators": nakamoto_operators(weights),
            "effective_operators": effective_operators(weights),
        }

    def blocks(self):
        [block] = super().blocks()
        if self._holder_settings is None:
            return [block]

        def s_copy(name):
            return lambda params, substep, history, state, signal: (name, signal[name])

        block["variables"] |= {name: s_copy(name) for name in ("fund_holdings_navax", *HOLDER_VARIABLES, *HOLDER_FLOAT_VARIABLES)}
        return [block]

    def invariants(self):
        checks = super().invariants()
        if self._holder_settings is None:
            return checks
        funds = self._funds

        def fund_validators_are_the_funds(s):
            rows = fund_of(s["node_key"])
            return bool((rows < len(funds)).all()) and s["etf_validators"] == int((rows >= 0).sum()) \
                and s["etf_validator_stake_navax"] == int(s["stakes"][rows >= 0].sum())

        return [
            *checks,
            ("fund holdings and the liquid staking target are never negative",
             lambda s: bool((s["fund_holdings_navax"] >= 0).all()) and s["lst_target_navax"] >= 0.0),
            ("each fund's validators are counted as its own", fund_validators_are_the_funds),
            ("the liquid staking stake is BENQI's delegated stake",
             lambda s: s["liquid_staking_stake_navax"] == int(s["delegation_stakes"][s["delegation_benqi"]].sum())),
        ]


class _Wrapped:
    """A holder stage bound to its model, whose setup is built on the first day it runs."""

    def __init__(self, model, stage, base):
        self.model, self.stage, self.base = model, stage, base

    def __call__(self, state, day, earlier):
        setup = self.model._holder_setup()
        if self.base is None:
            return self.stage(state, day, earlier, setup=setup)
        return self.stage(state, day, earlier, base=self.base, setup=setup)


class HolderLifecycle(HolderMixin, DelegationMixin, FittedLifecycle):
    """The holder rules on the v0.8 build with delegations."""

    off_model = DelegatedLifecycle


class HolderStakeLifecycle(HolderMixin, DelegationMixin, StakeLifecycle):
    """The holder rules on the v0.8.1 candidate's build: the stake hurdle, the return hazard and delegations."""

    off_model = DelegatedStakeLifecycle


def fund_table(rows: list[dict]) -> pd.DataFrame:
    """A ``fund_holdings`` table from plain rows, each with the columns of ``FUND_COLUMNS``."""
    frame = pd.DataFrame(rows, columns=FUND_COLUMNS)
    return frame.astype({"holdings_navax": np.int64, "staked_share": float, "validator_stake_navax": np.int64,
                         "min_days": np.int64, "max_days": np.int64})


def benqi_stake_per_start(starts: pd.DataFrame, origin, days: int = 28) -> int:
    """The mean stake, in nAVAX, of BENQI's delegation starts in the ``days`` UTC days to the origin day, from the
    origin's ``starts`` table, or zero when it had none."""
    if starts is None or not len(starts):
        return 0
    when = pd.to_datetime(starts["start_time"], utc=True).dt.tz_localize(None).dt.normalize()
    first = pd.Timestamp(origin) - pd.Timedelta(days=days - 1)
    mine = starts["benqi"].to_numpy(dtype=bool) & (when >= first).to_numpy() & (when <= pd.Timestamp(origin)).to_numpy()
    if not mine.any():
        return 0
    return round(float(starts.loc[mine, "stake_navax"].astype(float).mean()))
