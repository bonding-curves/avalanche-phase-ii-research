"""Build or verify portable GitHub reading copies of the research manual.

Uses the research-review exporter's link, dependency and hash checks.
No model, provider, notebook or site server is executed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from export_research_review import ExportError, Exporter

SOURCE = "content/Phase II/Wiki/Manual"
CHAPTERS = (
    "index", "foundations", "modeling", "architecture", "components", "data",
    "experiments", "analysis", "usage", "advanced", "workshop", "cli", "modules", "datasets",
)
DOCUMENTS = {f"{SOURCE}/{name}.md": "README.md" if name == "index" else f"{name}.md"
             for name in CHAPTERS}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("docs/manual"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(Exporter(args.project, args.output, DOCUMENTS).run(args.check), sort_keys=True))
    except (ExportError, OSError, subprocess.CalledProcessError, UnicodeError, json.JSONDecodeError) as error:
        parser.exit(1, f"FAIL | research manual export | {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
