#!/usr/bin/env python3
"""The released v0.8.0 model's structure, traced from its code and drawn with Graphviz.

    uv run --group model python scripts/figures/model_v08_structure.py [output folder]

Builds the model class of the variant ``v0.8.0`` on a small synthetic state, records what each stage of its daily
step reads and returns, and writes ``v0.8-structure.{dot,svg,png}`` (``views.model_structure.fitted_lifecycle_dot``).
The default folder is ``src/avalanche_research/model/images``, where the model README shows the image. Needs no data,
only Graphviz's ``dot``. Run it again whenever the model's stages change.
"""

from __future__ import annotations

import sys
from pathlib import Path

from avalanche_research.views.model_structure import fitted_lifecycle_dot, render

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "src" / "avalanche_research" / "model" / "images"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    for path in render(fitted_lifecycle_dot(), out / "v0.8-structure"):
        print(path)


if __name__ == "__main__":
    main()
