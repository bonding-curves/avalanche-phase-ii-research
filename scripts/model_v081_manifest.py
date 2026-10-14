#!/usr/bin/env python3
"""The review manifest of the v0.8.1 candidate's results: what was run, on which bytes, by which code.

    uv run --group model python scripts/model_v081_manifest.py replay
    uv run --group model python scripts/model_v081_manifest.py manifest --test-count N [--test-command CMD]

``replay`` runs the reward-counter replay (``model.replay``) over its windows on the staking periods run the results
used, and writes ``results/model-v0.8.1-candidate/replay.json``: for each window the day-level comparison and, for the
window from 2025-06-01, the mint-level pricing check. ``manifest`` writes ``manifest.json`` beside it: the branch head,
the source files changed since the branch left ``main`` with their git blob ids, every pin and dataset run read with its
SHA-256, the results files with theirs, the replay results, the origins table's command, and the test command and count.
Paths are relative to the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = Path("results/model-v0.8.1-candidate")
PERIODS_PIN = Path("data/pins/p2-model-v0.8.json")
CANDIDATE_PIN = Path("data/pins/p9-model-v0.8.1.json")
PERIODS_RUN = "staking-periods-2026-09-30"
WINDOWS = ((date(2024, 3, 21), False), (date(2025, 6, 1), True), (date(2025, 9, 20), True))


def sha256_of(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def replay() -> None:
    from avalanche_research import datasets
    from avalanche_research.model.engine import run
    from avalanche_research.model.replay import (
        LOCKBOX_FIRST_DAY,
        MintReplay,
        compare_minting,
        mint_events,
        mint_rows,
        recomputed_mints,
    )

    periods = str(datasets.parquet_path("derived.staking-periods", PERIODS_RUN))
    windows = []
    for start, by_mint in WINDOWS:
        events = mint_events(periods, start)
        anchor = int(events["supply_first_navax"].dropna().iloc[0])
        model = MintReplay(events=events, events_source=PERIODS_RUN, supply0_navax=anchor)
        days = compare_minting(run(model), events)
        entry = {"start": start.isoformat(), "through": LOCKBOX_FIRST_DAY.isoformat(), "anchor_supply_navax": anchor,
                 "model": "avalanche_research.model.replay.MintReplay", "specification": model.specification_hash(),
                 "command": f"mint_events(periods, date({start.year}, {start.month}, {start.day})); run(MintReplay(events, supply0_navax=anchor)); compare_minting(table, events)",
                 "days": days}
        if by_mint:
            entry["mints"] = recomputed_mints(mint_rows(periods, start))
            entry["mints_command"] = f"recomputed_mints(mint_rows(periods, date({start.year}, {start.month}, {start.day})))"
        windows.append(entry)
        print(f"{start}: {days['days_differ']} of {days['days_compared']} days differ", flush=True)
    (ROOT / RESULTS / "replay.json").write_text(json.dumps({"staking_periods_run": PERIODS_RUN, "windows": windows}, indent=2, default=str) + "\n")


def manifest(test_count: int, test_command: str) -> None:
    head = git("rev-parse", "HEAD")
    base = git("merge-base", "origin/main", "HEAD")
    changed = git("diff", "--name-only", base, head).splitlines()
    files = [{"path": path, "blob": git("rev-parse", f"{head}:{path}")} for path in changed if (ROOT / path).is_file()]
    construction = json.loads((ROOT / RESULTS / "origins" / "construction.json").read_text())
    replayed = json.loads((ROOT / RESULTS / "replay.json").read_text())
    pins = [{"path": str(PERIODS_PIN), "sha256": sha256_of(PERIODS_PIN), "role": "the staking periods run the results and the replay read"}]
    if (ROOT / CANDIDATE_PIN).is_file():
        pins.append({"path": str(CANDIDATE_PIN), "sha256": sha256_of(CANDIDATE_PIN), "role": "the candidate's pin, both runs"})
    else:
        pins.append({"path": str(CANDIDATE_PIN), "sha256": None, "role": "the candidate's pin, not yet created; the origins table cannot be rerun until it exists"})
    runs = [
        {"dataset_id": "derived.staking-periods", "run": construction["staking_periods_run"], "sha256": construction["staking_periods_sha256"],
         "read_by": ["origins", "replay"]},
        {"dataset_id": "derived.seamed-delegator-stakes", "run": construction.get("delegator_stakes_run") or Path(construction["delegator_stakes_parquet"]).parts[2],
         "sha256": construction["delegator_stakes_sha256"], "read_by": ["origins"],
         "note": "taken as the newest checked build when the origins table was produced; the script now takes it from the pin"},
    ]
    outputs = {name: {"path": str(RESULTS / "origins" / name), "sha256": sha256_of(RESULTS / "origins" / name)}
               for name in ("origins.csv", "parameters.csv", "specifications.csv", "unplaced.csv", "construction.json")}
    outputs["replay.json"] = {"path": str(RESULTS / "replay.json"), "sha256": sha256_of(RESULTS / "replay.json")}
    value = {
        "branch": "prototype/v0.8.1-v0", "head": head, "base_on_main": base, "changed_files": files,
        "inputs": {"pins": pins, "runs": runs},
        "origins": {"command": construction["command"], "code_commit": construction["code_commit"], "specification_hash": construction["specification_hash"],
                    "held_back_from": construction["held_back_from"], "outputs": outputs},
        "replay": {"command": "uv run --group model python scripts/model_v081_manifest.py replay", "staking_periods_run": replayed["staking_periods_run"],
                   "windows": [{"start": w["start"], "through": w["through"], "days_compared": w["days"]["days_compared"], "days_differ": w["days"]["days_differ"],
                                "same_second_ties_resolved": w["days"]["same_second_ties_resolved"], "delegations_started": w["days"]["delegations_started"],
                                **({"mints": w["mints"]["mints"], "priced_exactly": w["mints"]["priced_exactly"], "priced_differently": w["mints"]["priced_differently"]}
                                   if "mints" in w else {})} for w in replayed["windows"]],
                   "output": outputs["replay.json"]},
        "tests": {"command": test_command, "passed": test_count},
        "operator_types": "Not adopted. The candidate carries one type with named operators, K = 1 with no shift. One class fit the held-out "
                          "renewal endings best and two to four classes failed the adoption gates; one class is not significantly better than the "
                          "shrunk operator renewal rate (p = 0.26) and its transfer calibration error is 0.039 against a limit of 0.02.",
    }
    (ROOT / RESULTS / "manifest.json").write_text(json.dumps(value, indent=2) + "\n")
    print(f"wrote {RESULTS / 'manifest.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="what", required=True)
    sub.add_parser("replay")
    made = sub.add_parser("manifest")
    made.add_argument("--test-count", type=int, required=True)
    made.add_argument("--test-command", default="uv run pytest -q -p no:cacheprovider")
    args = parser.parse_args()
    if args.what == "replay":
        replay()
    else:
        manifest(args.test_count, args.test_command)


if __name__ == "__main__":
    sys.exit(main())
