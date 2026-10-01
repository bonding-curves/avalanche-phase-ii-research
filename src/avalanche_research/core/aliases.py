"""Keep an old import path working after its module moves.

A moved module's old file becomes two lines::

    from avalanche_research.core.aliases import alias
    alias(__name__, "avalanche_research.core.catalog")

The old name then refers to the new module itself, not to a copy. Patching a global through either name patches the
one module, and private names stay reachable, which a star re-export would not give.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType


def alias(old_name: str, new_name: str) -> ModuleType:
    """Make ``old_name`` resolve to the module at ``new_name`` and return that module."""
    module = importlib.import_module(new_name)
    sys.modules[old_name] = module
    parent, _, child = old_name.rpartition(".")
    if parent and parent in sys.modules:
        setattr(sys.modules[parent], child, module)
    return module
