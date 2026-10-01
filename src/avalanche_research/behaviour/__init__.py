"""Validator behaviour from empirical data: decision events, point-in-time features, and learning.

v0, unreviewed. The package turns the staking-period log into the two units a learner needs:

* ``events``: one row per validator staking period that ended, with what the node did next (stake again within a week,
  return later, or leave) and what it chose if it staked again. This is the supervised unit.
* ``lifetimes``: one row per node, summarising its whole observed history. This is the unsupervised unit.

``features`` computes every input as of the moment of the decision and records each one in a registry, so a model
never reads a value from after the decision it predicts. ``unsupervised`` and ``supervised`` wrap scikit-learn
estimators behind small functions that notebooks call. ``views`` holds the Param objects the notebooks display.

Nothing here reads data from the validation lockbox, which starts 2025-11-19 16:00 UTC, unless a caller asks for it
explicitly with ``observed_through``.
"""

from .inputs import LOCKBOX_START, RUNS, Inputs, load

__all__ = ["LOCKBOX_START", "RUNS", "Inputs", "load"]
