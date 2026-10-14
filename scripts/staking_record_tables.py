"""Export the canonical staking era table from an explicit, checked five-dataset pin.

Example from the repository root::

    uv run --group notebook python scripts/staking_record_tables.py \
        --pin data/pins/p9-staking-records.json --out /absolute/external/export-directory

The output directory must be new and outside Git. It contains a long CSV, metadata
and a compact byte-hash receipt. This command reads cached datasets only. It never
fetches providers, runs a model or changes the pin. Temporary DuckDB spill files
remain in the external staging directory and are removed before publication.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from avalanche_research import __version__
from avalanche_research.core.catalog import DataError
from avalanche_research.staking_cohorts import _report_digest, canonical_era_table


def export_table(
    pin: Path,
    out: Path,
    *,
    runs_root: Path | None = None,
    threads: int = 4,
    memory_limit: str = "2GB",
) -> dict:
    """Write one external export atomically. Failure publishes no result directory."""
    out = out.resolve()
    if out.exists():
        raise DataError("output directory already exists")
    ancestor = out.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    location = subprocess.run(
        ["git", "-C", str(ancestor), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if location.returncode == 0:
        raise DataError("export output must be outside a Git checkout")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="staking-era-", dir=out.parent
    ) as temporary:
        staging = Path(temporary)
        spill = staging / "spill"
        spill.mkdir()
        frame = canonical_era_table(
            pin,
            root=runs_root,
            threads=threads,
            memory_limit=memory_limit,
            temporary_directory=spill,
        )
        frame.to_csv(staging / "era-table.csv", index=False, float_format="%.17g")
        metadata = frame.attrs["metadata"]
        (staging / "metadata.json").write_text(
            json.dumps(metadata, indent=2, allow_nan=False) + "\n"
        )
        repo = Path(__file__).resolve().parents[1]

        def git(*args):
            result = subprocess.run(
                ["git", "-C", str(repo), *args],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.stdout.strip() if result.returncode == 0 else None

        receipt = {
            "schema_version": "staking-era-export-receipt/v1",
            "created_at": datetime.now(UTC).isoformat(),
            "pin_sha256": _report_digest(pin),
            "source": {
                "commit": git("rev-parse", "HEAD"),
                "tracked_changes": git("status", "--short", "--untracked-files=no"),
                "sha256": {
                    str(p.relative_to(repo)): _report_digest(p)
                    for p in (
                        repo / name
                        for name in (
                            "src/avalanche_research/staking_cohorts.py",
                            "scripts/staking_record_tables.py",
                            "src/avalanche_research/datasets/derived/identity.py",
                            "src/avalanche_research/model/protocol.py",
                            "src/avalanche_research/domain/protocol/__init__.py",
                            "src/avalanche_research/domain/protocol/types.py",
                            "src/avalanche_research/datasets/pins.py",
                            "src/avalanche_research/datasets/__init__.py",
                            "src/avalanche_research/core/catalog.py",
                            "uv.lock",
                        )
                    )
                },
            },
            "versions": {
                "python": platform.python_version(),
                "package": __version__,
                "duckdb": duckdb.__version__,
                "pandas": pd.__version__,
            },
            "rows": len(frame),
            "measure_families": int(frame.measure_family.nunique()),
            "role_era_pairs": len(frame[["role", "era"]].drop_duplicates()),
            "outputs": [
                {
                    "path": name,
                    "bytes": (staging / name).stat().st_size,
                    "sha256": _report_digest(staging / name),
                }
                for name in ("era-table.csv", "metadata.json")
            ],
            "scientific_acceptance": False,
        }
        (staging / "receipt.json").write_text(
            json.dumps(receipt, indent=2, allow_nan=False) + "\n"
        )
        shutil.rmtree(spill)
        staging.rename(out)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pin", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--runs-root", type=Path)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--memory-limit", default="2GB")
    args = parser.parse_args()
    try:
        receipt = export_table(
            args.pin,
            args.out,
            runs_root=args.runs_root,
            threads=args.threads,
            memory_limit=args.memory_limit,
        )
    except (DataError, ValueError, OSError, duckdb.Error) as error:
        parser.exit(1, f"staking era export refused: {error}\n")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
