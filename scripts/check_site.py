#!/usr/bin/env python3
"""Validate the standalone client research site and its publication boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_CONTENT = (
    "content/index.md",
    "content/Phase I/index.md",
    "content/Phase II/index.md",
    "content/Phase II/Studies/index.md",
    "content/Phase II/Studies/Essential Readings/index.md",
    "content/Phase II/Studies/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/index.md",
    "content/Phase II/Studies/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/Exploratory Data Analysis.md",
    "content/Phase II/Studies/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/Reproduction.md",
    "content/Phase II/Studies/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/Dynamic Model.md",
    "content/Phase II/Milestone 1/1-1 Data Ingestion.md",
    "content/Phase II/Milestone 1/1-2 Data Manifest.md",
    "content/Phase II/Milestone 1/1-3 Staking Model Spec.md",
    "content/Phase II/Milestone 1/1-4 Behavioral Calibration.md",
    "content/Wiki/Avalanche/index.md",
    "content/Wiki/Avalanche/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/index.md",
)

REQUIRED_PUBLIC = (
    "public/index.html",
    "public/Phase-II/index.html",
    "public/Phase-II/Studies/index.html",
    "public/Phase-II/Studies/Essential-Readings/index.html",
    "public/Phase-II/Studies/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/index.html",
    "public/Phase-II/Studies/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/Exploratory-Data-Analysis.html",
    "public/Phase-II/Studies/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/Reproduction.html",
    "public/Phase-II/Studies/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/Dynamic-Model.html",
    "public/Phase-II/Milestone-1/1-1-Data-Ingestion.html",
    "public/Phase-II/Milestone-1/1-2-Data-Manifest.html",
    "public/Phase-II/Milestone-1/1-3-Staking-Model-Spec.html",
    "public/Phase-II/Milestone-1/1-4-Behavioral-Calibration.html",
    "public/Wiki/Avalanche/index.html",
)

REQUIRED_TEXT = {
    "content/Phase II/Studies/Essential Readings/index.md": (
        "How Do Avalanche Validators Actually Think About Staking Rewards?",
    ),
    "content/Phase II/Studies/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/index.md": (
        "/Wiki/Avalanche/Essential%20Readings/How%20Do%20Avalanche%20Validators%20Actually%20Think%20About%20Staking%20Rewards/",
    ),
    "content/Wiki/Avalanche/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/index.md": (
        "/Phase-II/Studies/Essential%20Readings/How%20Do%20Avalanche%20Validators%20Actually%20Think%20About%20Staking%20Rewards/",
    ),
}

FORBIDDEN_TEXT = (
    "/home/",
    ".codex/",
    "Wiki/BCRG",
    "bcrg-private",
    "B or higher",
    "promotion gate",
    "notebook grade",
)


def check(root: Path) -> dict[str, object]:
    root = root.resolve()
    missing = [path for path in REQUIRED_CONTENT + REQUIRED_PUBLIC if not (root / path).is_file()]
    forbidden_paths = [
        path
        for path in ("content/Wiki/BCRG", "public/Wiki/BCRG")
        if (root / path).exists()
    ]
    forbidden_matches = []
    missing_required_text = []
    for relative, required_values in REQUIRED_TEXT.items():
        page = root / relative
        if not page.is_file():
            continue
        text = page.read_text(errors="replace")
        for required in required_values:
            if required not in text:
                missing_required_text.append({"file": relative, "text": required})
    content = root / "content"
    if content.is_dir():
        for page in sorted(content.rglob("*.md")):
            text = page.read_text(errors="replace")
            for forbidden in FORBIDDEN_TEXT:
                if forbidden.casefold() in text.casefold():
                    forbidden_matches.append(
                        {
                            "file": page.relative_to(root).as_posix(),
                            "text": forbidden,
                        }
                    )
    result = {
        "status": (
            "pass"
            if not missing
            and not forbidden_paths
            and not forbidden_matches
            and not missing_required_text
            else "fail"
        ),
        "missing_required_files": missing,
        "missing_required_text": missing_required_text,
        "forbidden_paths": forbidden_paths,
        "forbidden_text_matches": forbidden_matches,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = check(args.root)
    print(json.dumps(result, indent=2))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
