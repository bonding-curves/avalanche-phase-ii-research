"""The contract every behaviour part follows, and the constants more than one part reads.

A part is a :class:`BehaviourBlock`: a Param class for one decision that declares what it reads and writes and the
source of every parameter, draws decisions with ``sample`` and scores observed ones with ``log_prob``. Each fitted
part also has a ``fit`` class method that returns an instance whose every parameter is labelled ``fitted``.
"""

from __future__ import annotations

from avalanche_research.model.blocks import BehaviourBlock, _outcomes, behavioural

__all__ = [
    "AVAX", "DURATION_EDGES", "RECORDED_MODULE", "RENEWAL_DAYS", "RETURN_DAYS", "BehaviourBlock", "_outcomes", "behavioural",
]

AVAX = 10**9
RENEWAL_DAYS = 7
RETURN_DAYS = 365

# Ranges in whole days and AVAX. A value equal to a bound falls in the lower bin.
DURATION_EDGES = (20, 40, 100)

# The module the fitted blocks were defined in before the split, which specification hashes record.
RECORDED_MODULE = "avalanche_research.model.fitted_blocks"
