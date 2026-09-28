#!/usr/bin/env python3
"""Check local hyperlinks in every rendered Quartz HTML page.

External URLs are reported as skipped, not fetched. Run this against any Quartz
``public`` directory after building the site.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit


class LinksAndIds(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.slug: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "body":
            self.slug = attributes.get("data-slug")
        if attributes.get("id"):
            self.ids.add(attributes["id"] or "")
        if tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"] or "")


def _route(public: Path, page: Path) -> str:
    relative = page.relative_to(public).as_posix()
    if relative == "index.html":
        return "/"
    if relative.endswith("/index.html"):
        return "/" + relative[: -len("index.html")]
    return "/" + relative[: -len(".html")]


def _target_file(public: Path, route: str) -> Path | None:
    relative = unquote(route).lstrip("/")
    base = public / relative
    candidates = (
        [base / "index.html", base]
        if route.endswith("/") or not relative
        else [Path(f"{base}.html"), base / "index.html", base]
    )
    for candidate in candidates:
        if candidate.is_file() and candidate.resolve().is_relative_to(public.resolve()):
            return candidate
    return None


def _source_index(content: Path) -> dict[str, str]:
    """Map unambiguous Quartz body slugs to input Markdown paths."""
    candidates: dict[str, list[str]] = {}
    for source in sorted(content.rglob("*.md")):
        relative = source.relative_to(content).as_posix()
        slug = relative[:-3]
        slug = "/".join(
            re.sub(r"\s", "-", part)
            .replace("&", "-and-")
            .replace("%", "-percent")
            .replace("?", "")
            .replace("#", "")
            for part in slug.split("/")
        )
        if slug.endswith("_index"):
            slug = slug[:-6] + "index"
        candidates.setdefault(slug, []).append(relative)
    return {slug: paths[0] for slug, paths in candidates.items() if len(paths) == 1}


def check(public: Path, content: Path | None = None, site: str | None = None) -> dict[str, object]:
    public = public.resolve()
    if not public.is_dir():
        raise ValueError(f"Quartz public directory does not exist: {public}")
    if not (public / "index.html").is_file():
        raise ValueError(f"Quartz build is incomplete (no index.html): {public}")
    if content is not None and not content.is_dir():
        raise ValueError(f"Quartz content directory does not exist: {content}")
    sources = _source_index(content.resolve()) if content else {}
    pages: dict[Path, LinksAndIds] = {}
    digest = hashlib.sha256()
    for page in sorted(public.rglob("*.html")):
        parsed = LinksAndIds()
        data = page.read_bytes()
        digest.update(page.relative_to(public).as_posix().encode() + b"\0" + data + b"\0")
        parsed.feed(data.decode("utf-8", errors="replace"))
        pages[page] = parsed

    broken: list[dict[str, str]] = []
    checked = 0
    external = 0
    for page, parsed in pages.items():
        base_url = "https://quartz.invalid" + _route(public, page)
        for href in parsed.links:
            raw = urlsplit(href)
            if raw.scheme or raw.netloc:
                external += 1
                continue
            resolved = urlsplit(urljoin(base_url, href))
            if resolved.netloc != "quartz.invalid":
                external += 1
                continue
            checked += 1
            target = _target_file(public, resolved.path)
            reason = ""
            if target is None:
                target_path = public / unquote(resolved.path).lstrip("/")
                reason = "missing index" if target_path.is_dir() else "missing target"
            if target is not None and resolved.fragment:
                target_parser = pages.get(target)
                if target_parser is None:
                    target_parser = LinksAndIds()
                    target_parser.feed(target.read_text(encoding="utf-8", errors="replace"))
                if unquote(resolved.fragment) not in target_parser.ids:
                    reason = "missing fragment"
            if reason:
                destination = unquote(resolved.path)
                if resolved.fragment:
                    destination += "#" + unquote(resolved.fragment)
                broken.append({
                    "page": _route(public, page),
                    "source": sources.get(parsed.slug or ""),
                    "href": href,
                    "destination": destination,
                    "reason": reason,
                })
    groups: dict[tuple[str, str], dict[str, object]] = {}
    for finding in broken:
        key = (finding["destination"], finding["reason"])
        group = groups.setdefault(key, {
            "destination": key[0], "reason": key[1], "occurrences": 0,
            "pages": set(), "sources": set(),
        })
        group["occurrences"] += 1
        group["pages"].add(finding["page"])
        if finding["source"]:
            group["sources"].add(finding["source"])
    grouped = [
        {
            "destination": group["destination"],
            "reason": group["reason"],
            "occurrences": group["occurrences"],
            "affected_pages": len(group["pages"]),
            "sources": sorted(group["sources"]),
        }
        for group in groups.values()
    ]
    grouped.sort(key=lambda group: (-group["occurrences"], group["destination"]))
    return {
        "status": "pass" if not broken else "fail",
        "site": site,
        "build_sha256": digest.hexdigest(),
        "pages": len(pages),
        "local_links_checked": checked,
        "external_links_skipped": external,
        "affected_pages": len({finding["page"] for finding in broken}),
        "failing_destinations": len(grouped),
        "groups": grouped,
        "broken_links": broken,
    }


def _fingerprints(report: dict[str, object]) -> Counter[tuple[str, str, str]]:
    return Counter(
        (item["page"], item["destination"], item["reason"])
        for item in report["broken_links"]
    )


def make_baseline(report: dict[str, object], revision: str) -> dict[str, object]:
    if not report["site"] or not revision:
        raise ValueError("A site label and source revision are required for a baseline")
    return {
        "schema_version": "quartz-link-baseline/v1",
        "site": report["site"],
        "source_revision": revision,
        "build_sha256": report["build_sha256"],
        "known": [list(item) + [count] for item, count in sorted(_fingerprints(report).items())],
    }


def compare_baseline(report: dict[str, object], baseline: dict[str, object]) -> dict[str, object]:
    if baseline.get("schema_version") != "quartz-link-baseline/v1":
        raise ValueError("Unsupported link baseline schema")
    if not report["site"] or baseline.get("site") != report["site"]:
        raise ValueError("Link baseline site does not match the checked site")
    known_rows = baseline.get("known")
    if not isinstance(known_rows, list) or any(
        not isinstance(row, list) or len(row) != 4
        or not all(isinstance(part, str) for part in row[:3])
        or not isinstance(row[3], int) or isinstance(row[3], bool) or row[3] < 1
        for row in known_rows
    ):
        raise ValueError("Malformed link baseline fingerprints")
    known = {tuple(row[:3]): row[3] for row in known_rows}
    if len(known) != len(known_rows):
        raise ValueError("Duplicate link baseline fingerprints")
    current = _fingerprints(report)
    known_counter = Counter(known)
    added = current - known_counter
    removed = known_counter - current
    return {
        "status": "pass" if not added else "fail",
        "new": [list(item) + [count] for item, count in sorted(added.items())],
        "known_remaining": sum((current & known_counter).values()),
        "resolved": sum(removed.values()),
        "baseline_revision": baseline.get("source_revision"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public", type=Path, help="Built Quartz public directory")
    parser.add_argument("--content", type=Path, help="Input Markdown directory for source attribution")
    parser.add_argument("--site", help="Site label in the report, such as client or bcrg")
    parser.add_argument("--json", action="store_true", help="Print every finding as JSON")
    baseline_mode = parser.add_mutually_exclusive_group()
    baseline_mode.add_argument("--baseline", type=Path, help="Fail only on new link failures")
    baseline_mode.add_argument("--write-baseline", type=Path, help="Explicitly capture known failures")
    parser.add_argument("--revision", help="Source revision label required when writing a baseline")
    args = parser.parse_args()
    if args.write_baseline and (not args.site or not args.revision):
        parser.error("--write-baseline requires --site and --revision")
    if args.baseline and not args.site:
        parser.error("--baseline requires --site")
    result = check(args.public, content=args.content, site=args.site)
    if args.write_baseline:
        baseline = make_baseline(result, args.revision or "")
        args.write_baseline.write_text(json.dumps(baseline, indent=2) + "\n")
        print(f"Captured {len(baseline['known'])} known failures for {baseline['site']}")
        return
    comparison = None
    if args.baseline:
        comparison = compare_baseline(result, json.loads(args.baseline.read_text()))
        result["baseline_comparison"] = comparison
    gate_status = (comparison or result)["status"]
    result["gate_status"] = gate_status
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"{gate_status}: {result['pages']} pages, "
            f"{result['local_links_checked']} local links checked, "
            f"{len(result['broken_links'])} broken occurrences across "
            f"{result['affected_pages']} pages and {result['failing_destinations']} destinations, "
            f"{result['external_links_skipped']} external links skipped"
        )
        for group in result["groups"][:12]:
            print(f"{group['occurrences']:>4} {group['destination']} ({group['reason']})")
        if len(result["groups"]) > 12:
            print(f"... {len(result['groups']) - 12} more destinations; use --json for all findings")
        if comparison:
            print(
                f"baseline: {len(comparison['new'])} new, "
                f"{comparison['known_remaining']} known remaining, "
                f"{comparison['resolved']} resolved"
            )
            for page, destination, reason, count in comparison["new"][:12]:
                print(f"NEW {page}: {destination} ({reason}, +{count})")
    if gate_status != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
