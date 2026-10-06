"""Entities and what was known about them at an instant: the as-of history (``EF1``), the forward-fold splitter that
carries it (``FS1``), and the effect table every consumer reads (``EF4``).

An entity is a node (tier ``node``) or a group of nodes at an identity tier. Until the identity resolver (``EF2``) lands,
``members`` is a table of ``node_id`` and ``entity_id`` the caller supplies; ``node_members`` gives the node tier.

Every function here keeps one rule: nothing at or after ``as_of`` is read. A decision enters an entity's history only once
its label was observable before ``as_of``, its end plus the label's follow-up window strictly before it. ``as_of`` at or
after the lockbox's first instant is refused unless the caller passes ``allow_lockbox``, the one scoring run.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import pandas as pd

from .inputs import LOCKBOX_START, check_cutoff
from .supervised import TARGETS, Fold, protocol_folds

DAY = pd.Timedelta(days=1)
EFFECT_COLUMNS = ["entity_id", "effect_id", "estimate", "sd", "n", "prior_id"]


def node_members(decisions: pd.DataFrame) -> pd.DataFrame:
    """The node tier: every node is its own entity."""
    nodes = decisions.node_id.drop_duplicates().sort_values()
    return pd.DataFrame({"node_id": nodes.to_numpy(), "entity_id": nodes.to_numpy()})


def entity_history(decisions: pd.DataFrame, members: pd.DataFrame, as_of, *, tier: str = "node", label: str = "renewed",
                   follow_up_days: int = 7, lookback_days: int | None = None, allow_lockbox: bool = False) -> pd.DataFrame:
    """``EF1``: one row per past decision of each entity whose label was observable before ``as_of``.

    ``decisions`` is the decision panel (``events.decision_events``). A decision counts when its end plus
    ``follow_up_days`` is strictly before ``as_of`` and its ``label`` is known. ``lookback_days`` keeps only decisions
    that ended in that many days before ``as_of``."""
    cut = check_cutoff(as_of, allow_lockbox)
    if label not in decisions:
        raise ValueError(f"decisions have no label column {label!r}")
    if set(members.columns) < {"node_id", "entity_id"} or members.node_id.duplicated().any():
        raise ValueError("members must map each node_id to one entity_id")
    visible = decisions.end_time.add(follow_up_days * DAY).lt(cut) & decisions[label].notna()
    if lookback_days is not None:
        visible &= decisions.end_time.ge(cut - lookback_days * DAY)
    history = decisions.loc[visible].merge(members[["node_id", "entity_id"]], on="node_id", how="inner")
    history = history.sort_values(["entity_id", "end_time", "transaction_hash"]).reset_index(drop=True)
    history.attrs.update(as_of=str(cut), tier=tier, label=label, follow_up_days=follow_up_days)
    return history


@dataclass(frozen=True)
class EntityFold:
    """``FS1``: a protocol fold, and the history of every entity as of its start, built from pre-fold decisions only."""

    fold: Fold
    history: pd.DataFrame


def entity_folds(decisions: pd.DataFrame, members: pd.DataFrame, target: str = "renewed", *, tier: str = "node",
                 origins: pd.Series | None = None, horizons=(30, 90, 180),
                 observed_through=LOCKBOX_START) -> list[EntityFold]:
    """``FS1``: the protocol's folds over ``decisions``, each with the as-of entity history at its origin. Every learner
    that needs an entity effect reads it from here, so no rung sees a different notion of the past.

    The label column and its follow-up come from the registered target (``supervised.TARGETS``): ``next_duration``
    reads ``next_duration_class``, and ``outcome`` and ``next_duration`` mature 365 days after a period ends. Each
    fold's history holds exactly its training rows that carry a label."""
    if target not in TARGETS:
        raise ValueError(f"unknown target {target!r}; registered targets are {sorted(TARGETS)}")
    spec = TARGETS[target]
    folds = protocol_folds(decisions, target, origins=origins, horizons=horizons, observed_through=observed_through)
    histories: dict[pd.Timestamp, pd.DataFrame] = {}
    out = []
    for fold in folds:
        if fold.start not in histories:
            histories[fold.start] = entity_history(decisions, members, fold.start, tier=tier, label=spec.column,
                                                   follow_up_days=spec.follow_up_days)
        out.append(EntityFold(fold, histories[fold.start]))
    return out


@dataclass(frozen=True)
class EffectTable:
    """``EF4``: entity effects estimated from data strictly before ``as_of``, plus the prior row for an unseen entity."""

    rows: pd.DataFrame
    prior: pd.DataFrame
    as_of: pd.Timestamp
    tier: str
    map_version: str
    receipt_id: str

    def at(self, entity_ids, when) -> pd.DataFrame:
        """The effect of each entity for use at ``when``. A lookup before ``as_of`` is refused, because the table holds
        data the past did not have. An entity with no row gets the prior, with ``n = 0``."""
        when = pd.Timestamp(when)
        if when < self.as_of:
            raise ValueError(f"an effect table as of {self.as_of} cannot be read at the earlier {when}")
        wanted = pd.DataFrame({"entity_id": list(entity_ids)})
        known = wanted.merge(self.rows, on="entity_id", how="inner")
        unseen = wanted.loc[~wanted.entity_id.isin(self.rows.entity_id)]
        priors = unseen.merge(self.prior, how="cross")
        return pd.concat([known, priors], ignore_index=True)[EFFECT_COLUMNS]


def effects(fit, as_of, tier: str = "node", map_version: str = "node", allow_lockbox: bool = False) -> EffectTable:
    """``EF4``'s writer: an ``EffectTable`` from a fit (``shrink.shrink``), with a receipt id that hashes its content.

    The fit must carry the cut of the history it was fitted on (``entity_history`` sets it), and ``as_of`` may not be
    earlier: a table stamped before its own data were observable would hand the future to an earlier origin."""
    cut = check_cutoff(as_of, allow_lockbox)
    if fit.as_of is None:
        raise ValueError("the fit carries no as-of cut: fit it on a history from entity_history")
    if cut < pd.Timestamp(fit.as_of):
        raise ValueError(f"the fit used data observable before {fit.as_of}; a table cannot be stamped earlier, at {cut}")
    rows = fit.rows[EFFECT_COLUMNS].sort_values(["entity_id", "effect_id"]).reset_index(drop=True)
    prior = fit.prior[[c for c in EFFECT_COLUMNS if c != "entity_id"]].reset_index(drop=True)
    content = {"as_of": str(cut), "fit_as_of": fit.as_of, "support": fit.support, "tier": tier, "map_version": map_version,
               "family": fit.family, "categories": list(fit.categories), "hyperparameters": fit.hyperparameters,
               "rows": rows.to_csv(index=False), "prior": prior.to_csv(index=False)}
    receipt_id = "effects:" + hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return EffectTable(rows, prior, cut, tier, map_version, receipt_id)


__all__ = ["EffectTable", "EntityFold", "effects", "entity_folds", "entity_history", "node_members"]
