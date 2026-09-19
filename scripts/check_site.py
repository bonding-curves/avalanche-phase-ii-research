#!/usr/bin/env python3
"""Validate the standalone client research site and its publication boundary."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


REQUIRED_CONTENT = (
    "content/index.md",
    "content/Phase I/index.md",
    "content/Phase II/index.md",
    "content/Phase II/Validator Interviews/index.md",
    "content/Phase II/Studies/index.md",
    "content/Phase II/Studies/Essential Readings/index.md",
    "content/Phase II/Studies/Essential Readings/The Avalanche Foundation Unveils its Economic Research Agenda/index.md",
    "content/Phase II/Studies/Essential Readings/The Avalanche Foundation Unveils its Economic Research Agenda/Source Article.md",
    "content/Phase II/Studies/Essential Readings/Value Accrual as Equilibrium How We Think About AVAX Tokenomics/index.md",
    "content/Phase II/Studies/Essential Readings/Value Accrual as Equilibrium How We Think About AVAX Tokenomics/Source Article.md",
    "content/Phase II/Studies/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/index.md",
    "content/Phase II/Studies/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/Source Article.md",
    "content/Phase II/Studies/Essential Readings/From Gross Chain Product to Gross Chain Income Where the Value Goes/index.md",
    "content/Phase II/Studies/Essential Readings/From Gross Chain Product to Gross Chain Income Where the Value Goes/Source Article.md",
    "content/Phase II/Studies/Essential Readings/ACP 285 Avalanche Community Call Staking Reward Curve Adjustment/index.md",
    "content/Phase II/Studies/Essential Readings/ACP 285 Avalanche Community Call Staking Reward Curve Adjustment/Source Video.md",
    "content/Phase II/Studies/Essential Readings/January Staking and Price Model A Three-Image Reconstruction/index.md",
    "content/Phase II/Studies/Essential Readings/January Staking and Price Model A Three-Image Reconstruction/Source Model Artifact.md",
    "content/Phase II/Milestone 1/1-1 Data Ingestion.md",
    "content/Phase II/Milestone 1/1-2 Data Manifest.md",
    "content/Phase II/Milestone 1/1-3 Staking Model Spec.md",
    "content/Phase II/Milestone 1/1-4 Behavioral Calibration.md",
    "content/Wiki/Avalanche/index.md",
)

REQUIRED_PUBLIC = (
    ".site/public/index.html",
    ".site/public/Phase-II/index.html",
    ".site/public/Phase-II/Validator-Interviews/index.html",
    ".site/public/Phase-II/Studies/index.html",
    ".site/public/Phase-II/Studies/Essential-Readings/index.html",
    ".site/public/Phase-II/Studies/Essential-Readings/The-Avalanche-Foundation-Unveils-its-Economic-Research-Agenda/index.html",
    ".site/public/Phase-II/Studies/Essential-Readings/The-Avalanche-Foundation-Unveils-its-Economic-Research-Agenda/Source-Article.html",
    ".site/public/Phase-II/Studies/Essential-Readings/Value-Accrual-as-Equilibrium-How-We-Think-About-AVAX-Tokenomics/index.html",
    ".site/public/Phase-II/Studies/Essential-Readings/Value-Accrual-as-Equilibrium-How-We-Think-About-AVAX-Tokenomics/Source-Article.html",
    ".site/public/Phase-II/Studies/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/index.html",
    ".site/public/Phase-II/Studies/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/Source-Article.html",
    ".site/public/Phase-II/Studies/Essential-Readings/From-Gross-Chain-Product-to-Gross-Chain-Income-Where-the-Value-Goes/index.html",
    ".site/public/Phase-II/Studies/Essential-Readings/From-Gross-Chain-Product-to-Gross-Chain-Income-Where-the-Value-Goes/Source-Article.html",
    ".site/public/Phase-II/Studies/Essential-Readings/ACP-285-Avalanche-Community-Call-Staking-Reward-Curve-Adjustment/index.html",
    ".site/public/Phase-II/Studies/Essential-Readings/ACP-285-Avalanche-Community-Call-Staking-Reward-Curve-Adjustment/Source-Video.html",
    ".site/public/Phase-II/Studies/Essential-Readings/January-Staking-and-Price-Model-A-Three-Image-Reconstruction/index.html",
    ".site/public/Phase-II/Studies/Essential-Readings/January-Staking-and-Price-Model-A-Three-Image-Reconstruction/Source-Model-Artifact.html",
    ".site/public/Phase-II/Milestone-1/1-1-Data-Ingestion.html",
    ".site/public/Phase-II/Milestone-1/1-2-Data-Manifest.html",
    ".site/public/Phase-II/Milestone-1/1-3-Staking-Model-Spec.html",
    ".site/public/Phase-II/Milestone-1/1-4-Behavioral-Calibration.html",
    ".site/public/Wiki/Avalanche/index.html",
)

REQUIRED_TEXT = {
    "content/Phase II/Studies/Essential Readings/index.md": (
        "The Avalanche Foundation Unveils its Economic Research Agenda",
        "Value Accrual as Equilibrium: How We Think About AVAX Tokenomics",
        "How Do Avalanche Validators Actually Think About Staking Rewards?",
        "From Gross Chain Product to Gross Chain Income: Where the Value Goes",
        "ACP 285 - Avalanche Community Call - Staking Reward Curve Adjustment",
        "January Staking and Price Model: A Three-Image Reconstruction",
    ),
    "content/Phase II/Studies/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/index.md": (
        "Source Article",
    ),
    "content/Phase II/Studies/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/Source Article.md": (
        "## The Question",
        "## The Model",
    ),
    "content/Phase II/Studies/Essential Readings/ACP 285 Avalanche Community Call Staking Reward Curve Adjustment/Source Video.md": (
        "timestamped analytical reading view",
        "ACP-285: Reduce Minimum Consumption Rate",
        "automatic captions were used to locate sections",
    ),
    "content/Phase II/Studies/Essential Readings/January Staking and Price Model A Three-Image Reconstruction/Source Model Artifact.md": (
        "Original evidence",
        "Mathematical reconstruction",
        "Unresolved",
        "status: conceptual-reconstruction",
    ),
    "content/Phase II/Validator Interviews/index.md": (
        "No interview findings are published yet.",
    ),
    "content/Phase II/Milestone 1/1-1 Data Ingestion.md": (
        "generated by scripts/milestone_pages.py",
        "## Coverage by contract quantity",
    ),
    "content/Phase II/Milestone 1/1-2 Data Manifest.md": (
        "generated by scripts/milestone_pages.py",
        "### Latest runs",
    ),
}

FORBIDDEN_PATHS = (
    "content/Wiki/BCRG",
    ".site/public/Wiki/BCRG",
    "content/Wiki/Avalanche/Essential Readings",
    ".site/public/Wiki/Avalanche/Essential-Readings",
    "content/Phase II/Studies/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/Exploratory Data Analysis.md",
    "content/Phase II/Studies/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/Reproduction.md",
    "content/Phase II/Studies/Essential Readings/How Do Avalanche Validators Actually Think About Staking Rewards/Dynamic Model.md",
)

FORBIDDEN_TEXT = (
    "/home/",
    ".codex/",
    "Wiki/BCRG",
    "bcrg-private",
    "B or higher",
    "promotion gate",
    "notebook grade",
)

IMAGE_LINK = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
HTML_IMAGE = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']', re.IGNORECASE)


def _local_asset(root: Path, page: Path, target: str) -> Path | None:
    parsed = urlsplit(target.strip().strip("<>"))
    if parsed.scheme or parsed.netloc:
        return None
    decoded = unquote(parsed.path)
    if decoded.startswith("/"):
        public_route = decoded.lstrip("/")
        for candidate in (root / "content").rglob(Path(public_route).name):
            relative = candidate.relative_to(root / "content")
            candidate_route = "/".join(part.replace(" ", "-") for part in relative.parts)
            if candidate_route == public_route:
                return candidate
        return root / "content" / public_route
    return page.parent / decoded


def _public_asset(root: Path, page: Path, target: str) -> Path | None:
    parsed = urlsplit(target.strip())
    if parsed.scheme or parsed.netloc or target.startswith("data:"):
        return None
    decoded = unquote(parsed.path)
    public = root / ".site" / "public"
    if decoded.startswith("/"):
        return public / decoded.lstrip("/")
    return page.parent / decoded


def check(root: Path) -> dict[str, object]:
    root = root.resolve()
    missing = [path for path in REQUIRED_CONTENT + REQUIRED_PUBLIC if not (root / path).is_file()]
    forbidden_paths = [path for path in FORBIDDEN_PATHS if (root / path).exists()]
    forbidden_matches = []
    missing_required_text = []
    missing_local_assets = []
    broken_public_images = []
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
            for target in IMAGE_LINK.findall(text):
                asset = _local_asset(root, page, target)
                if asset is not None and not asset.is_file():
                    missing_local_assets.append(
                        {
                            "file": page.relative_to(root).as_posix(),
                            "target": target,
                        }
                    )
            for forbidden in FORBIDDEN_TEXT:
                if forbidden.casefold() in text.casefold():
                    forbidden_matches.append(
                        {
                            "file": page.relative_to(root).as_posix(),
                            "text": forbidden,
                        }
                    )
    public = root / ".site" / "public"
    if public.is_dir():
        for page in sorted(public.rglob("*.html")):
            text = page.read_text(errors="replace")
            for target in HTML_IMAGE.findall(text):
                asset = _public_asset(root, page, target)
                if asset is not None and not asset.resolve().is_file():
                    broken_public_images.append(
                        {
                            "file": page.relative_to(root).as_posix(),
                            "target": target,
                        }
                    )
    result = {
        "status": (
            "pass"
            if not missing
            and not forbidden_paths
            and not forbidden_matches
            and not missing_required_text
            and not missing_local_assets
            and not broken_public_images
            else "fail"
        ),
        "missing_required_files": missing,
        "missing_required_text": missing_required_text,
        "missing_local_assets": missing_local_assets,
        "broken_public_images": broken_public_images,
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
