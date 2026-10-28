"""Seed audit: every random draw in the library and scripts is keyed through model.streams, or is a
listed exception with its reason. A seed list built outside streams can collide with another (SeedSequence ignores
trailing zero words), an unseeded generator cannot be replayed, and global random state makes a result depend on
call order.

The rule is an allow-list, not a list of forbidden names, since a list of names always misses one: any call into the ``numpy.random``
or ``random`` modules is a violation unless it is one of the forms allowed below. Calls are matched through every import
in the file, keeping every module a name can stand for in any scope, and a star import from either module is a
violation in itself.

It is a static check, so it does not follow a random module assigned to a variable, ``getattr`` or ``importlib``.
Review catches those."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = (ROOT / "src", ROOT / "scripts")
STREAMS = Path("src/avalanche_research/model/streams.py")
RANDOM_MODULES = ("numpy.random", "random")
# Library calls kept on purpose: file, qualified name, seed kind, and the reason. Remove a row when its code goes.
ALLOWED = {
    (Path("src/avalanche_research/model/lifecycle.py"), "numpy.random.default_rng", "seed_list"):
        "v0.7 keeps its daily stream so the tagged v0.7 results reproduce",
    (Path("src/avalanche_research/analysis/rank_associations.py"), "numpy.random.default_rng", "seed_other"):
        "explicitly seeded statistical bootstrap, never a simulator or design draw",
    (Path("src/avalanche_research/analysis/sobol.py"), "numpy.random.Generator", "seed_other"):
        "explicitly seeded statistical bootstrap, never a simulator or design draw",
    (Path("src/avalanche_research/analysis/sobol.py"), "numpy.random.PCG64", "seed_other"):
        "explicitly seeded statistical bootstrap, never a simulator or design draw",
    (Path("src/avalanche_research/report/recommend.py"), "numpy.random.default_rng", "seed_other"):
        "explicitly seeded resample of scored runs for report confidence, never a simulator or design draw",
    (Path("src/avalanche_research/report/trees.py"), "numpy.random.default_rng", "seed_other"):
        "explicitly seeded permutation for held-out tree importance, never a simulator or design draw",
}
# The one form a script may use: a generator seeded from one integer literal.
SCRIPT_SEEDED = {"numpy.random.default_rng", "numpy.random.SeedSequence"}


def _aliases(tree: ast.AST) -> dict[str, set[str]]:
    """Local name to every qualified name it stands for in any scope of the file."""
    names: dict[str, set[str]] = defaultdict(set)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names[alias.asname or alias.name.split(".")[0]].add(alias.name if alias.asname else alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                names[alias.asname or alias.name].add(f"{node.module}.{alias.name}")
    return names


def _qualified(func: ast.AST, names: dict[str, set[str]]) -> set[str]:
    parts = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if not isinstance(func, ast.Name):
        return set()
    tail = list(reversed(parts))
    return {".".join([head, *tail]) for head in (names.get(func.id) or {func.id})}


def _in_random(name: str) -> bool:
    return any(name == module or name.startswith(module + ".") for module in RANDOM_MODULES)


def _seed_kind(node: ast.Call) -> str:
    seed = next((k.value for k in node.keywords if k.arg in ("seed", "entropy")), node.args[0] if node.args else None)
    if seed is None or (isinstance(seed, ast.Constant) and seed.value is None):
        return "unseeded"
    if isinstance(seed, ast.Constant) and isinstance(seed.value, int) and not isinstance(seed.value, bool):
        return "seed_literal"
    if isinstance(seed, (ast.List, ast.Tuple)) and seed.elts:
        return "seed_list"
    return "seed_other"


def random_calls(source: str) -> list[tuple[str, str, int]]:
    """(qualified name, seed kind, line) for every call into a random module, and ``("*", "star_import", line)`` for a
    star import from one."""
    tree = ast.parse(source)
    names = _aliases(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in RANDOM_MODULES and any(a.name == "*" for a in node.names):
            found.append((f"{node.module}.*", "star_import", node.lineno))
        if isinstance(node, ast.Call):
            for name in sorted(_qualified(node.func, names)):
                if _in_random(name):
                    found.append((name, _seed_kind(node), node.lineno))
    return found


def violations(path: Path, source: str) -> list[str]:
    relative = path.relative_to(ROOT) if path.is_absolute() else path
    if relative == STREAMS:
        return []
    library = relative.parts[0] == "src"
    out = []
    for name, kind, line in random_calls(source):
        if library and (relative, name, kind) in ALLOWED:
            continue
        if not library and name in SCRIPT_SEEDED and kind == "seed_literal":
            continue
        out.append(f"{relative}:{line} {name} ({kind}): draws go through model.streams" if library
                   else f"{relative}:{line} {name} ({kind}): a script seeds a generator from one integer literal")
    return out


PLANTED = {
    "a seed list": "import numpy as np\nnp.random.default_rng([seed, run])\n",
    "a seed list by keyword": "import numpy as np\nnp.random.default_rng(seed=[seed, run])\n",
    "a seed list in a variable": "import numpy as np\nparts = [seed, run]\nnp.random.default_rng(parts)\n",
    "no seed": "import numpy as np\nnp.random.default_rng()\n",
    "global state": "import numpy as np\nnp.random.seed(1)\n",
    "a global draw": "import numpy as np\nnp.random.normal(0, 1)\n",
    "a global draw not on any list": "import numpy as np\nnp.random.standard_normal(3)\n",
    "a global draw through a module alias": "import numpy.random as npr\nnpr.normal(0, 1)\n",
    "a global draw imported by name": "from numpy.random import normal\nnormal(0, 1)\n",
    "legacy state": "import numpy as np\nnp.random.RandomState(3)\n",
    "the random module": "import random as rnd\nrnd.random()\n",
    "a random-module draw imported by name": "from random import choice\nchoice([1, 2])\n",
    "a random-module instance": "import random\nrandom.Random().random()\n",
    "a bit generator with a seed list": "from numpy.random import Generator, PCG64\nGenerator(PCG64([1, 2]))\n",
    "a star import": "from numpy.random import *\nnormal()\n",
    "a draw hidden by an import in another scope": "import numpy as np\ndef f():\n    import pandas as np\ndef g():\n    np.random.normal()\n",
}


def test_the_checker_flags_every_planted_violation_in_a_script_and_in_the_library():
    for label, source in PLANTED.items():
        assert violations(Path("scripts/example.py"), source), label
        assert violations(Path("src/avalanche_research/example.py"), source), label


def test_the_checker_flags_library_seeding_even_through_an_alias():
    assert violations(Path("src/avalanche_research/example.py"), "from numpy.random import default_rng as make\nmake(7)\n")
    assert violations(Path("src/avalanche_research/example.py"), "import numpy as np\nnp.random.default_rng(7)\n")


def test_the_listed_exception_admits_only_its_own_form():
    lifecycle = Path("src/avalanche_research/model/lifecycle.py")
    assert violations(lifecycle, "import numpy as np\nnp.random.default_rng([seed, run, t])\n") == []
    assert violations(lifecycle, "import numpy as np\nnp.random.default_rng()\n")
    # A variable may hold None, which seeds from the operating system, so only a written-out list is admitted.
    assert violations(lifecycle, "import numpy as np\nseed = None\nnp.random.default_rng(seed)\n")
    assert violations(lifecycle, "import numpy as np\nnp.random.normal()\n")


def test_the_checker_accepts_a_script_seeded_from_one_literal_and_the_streams_module():
    assert violations(Path("scripts/example.py"), "import numpy as np\nrng = np.random.default_rng(20261005)\nrng.normal()\n") == []
    assert violations(STREAMS, "\n".join(PLANTED.values())) == []


def test_analysis_bootstrap_exceptions_keep_unseeded_and_global_draws_forbidden():
    rank = Path("src/avalanche_research/analysis/rank_associations.py")
    sobol = Path("src/avalanche_research/analysis/sobol.py")
    assert violations(rank, "import numpy as np\nnp.random.default_rng(spec.seed)\n") == []
    assert violations(sobol, "import numpy as np\nnp.random.Generator(np.random.PCG64(seed))\n") == []
    for path in (rank, sobol):
        assert violations(path, "import numpy as np\nnp.random.default_rng()\n")
        assert violations(path, "import numpy as np\nnp.random.PCG64()\n")
        assert violations(path, "import numpy as np\nnp.random.normal()\n")


def test_every_draw_in_the_library_and_scripts_is_keyed_or_listed():
    problems = []
    for base in SCANNED:
        for path in sorted(base.rglob("*.py")):
            problems += violations(path, path.read_text())
    assert problems == []
