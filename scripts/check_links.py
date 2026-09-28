#!/usr/bin/env python3
"""Check local hyperlinks in every rendered Quartz HTML page.

External URLs are reported as skipped, not fetched. Run this against any Quartz
``public`` directory after building the site.
"""

from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit


class LinksAndIds(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
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


def check(public: Path) -> dict[str, object]:
    public = public.resolve()
    if not public.is_dir():
        raise ValueError(f"Quartz public directory does not exist: {public}")
    pages: dict[Path, LinksAndIds] = {}
    for page in sorted(public.rglob("*.html")):
        parsed = LinksAndIds()
        parsed.feed(page.read_text(encoding="utf-8", errors="replace"))
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
            reason = "missing target" if target is None else ""
            if target is not None and resolved.fragment:
                target_parser = pages.get(target)
                if target_parser is None:
                    target_parser = LinksAndIds()
                    target_parser.feed(target.read_text(encoding="utf-8", errors="replace"))
                if unquote(resolved.fragment) not in target_parser.ids:
                    reason = "missing fragment"
            if reason:
                broken.append({"page": _route(public, page), "href": href, "reason": reason})
    return {
        "status": "pass" if not broken else "fail",
        "pages": len(pages),
        "local_links_checked": checked,
        "external_links_skipped": external,
        "broken_links": broken,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public", type=Path, help="Built Quartz public directory")
    parser.add_argument("--json", action="store_true", help="Print every finding as JSON")
    args = parser.parse_args()
    result = check(args.public)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"{result['status']}: {result['pages']} pages, "
            f"{result['local_links_checked']} local links checked, "
            f"{len(result['broken_links'])} broken, "
            f"{result['external_links_skipped']} external links skipped"
        )
        for item in result["broken_links"][:20]:
            print(f"{item['page']}: {item['href']} ({item['reason']})")
        if len(result["broken_links"]) > 20:
            print(f"... {len(result['broken_links']) - 20} more; use --json for all findings")
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
