"""The fitted lifecycle model's behaviour blocks, under the path they had before they moved to one module per part.

Every name this module offered before the move still imports from here and is the same object as in its part module
under :mod:`avalanche_research.model.parts`:

* :class:`RenewalLogit`: whether an ending commitment renews on the same node within seven days.
* :class:`Arrivals`: how many first-ever nodes start a commitment each day.
* :class:`ReturnHazard`: whether a node that did not renew returns, for up to 365 days.
* :class:`Continuation`: the next duration and stake of a node that renews or returns.
"""

from __future__ import annotations

# The modules and names the single file imported, kept so that every name it offered still imports from here.
from collections.abc import Mapping  # noqa: F401
from math import lgamma  # noqa: F401

import numpy as np  # noqa: F401
from scipy import optimize, special, stats  # noqa: F401

from avalanche_research.model.parts.arrivals import (  # noqa: F401
    Arrivals,
    _negative_binomial_log_prob,
)
from avalanche_research.model.parts.base import (  # noqa: F401
    AVAX,
    DURATION_EDGES,
    RENEWAL_DAYS,
    RETURN_DAYS,
    BehaviourBlock,
    _outcomes,
    behavioural,
)
from avalanche_research.model.parts.continuation import (  # noqa: F401
    MOVE_STAKE_EDGES,
    Continuation,
)
from avalanche_research.model.parts.renewal import (  # noqa: F401
    NODE_PRIOR_GRID,
    RENEWAL_STAKE_EDGES,
    RENEWAL_TERMS,
    TENURE_BINS,
    RenewalLogit,
    _coefficient,
    _newton,
    renewal_design,
    tenure_bin,
)
from avalanche_research.model.parts.returns import (  # noqa: F401
    RETURN_CELLS,
    RETURN_DAY_EDGES,
    RETURN_STAKE_EDGES,
    ReturnHazard,
    _hazard,
    return_cell,
)
