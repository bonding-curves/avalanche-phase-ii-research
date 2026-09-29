#!/usr/bin/env python3
"""Render the facts table on each collection overview, and the topic pages that list every tagged page.

    python scripts/overview_tables.py build   # write the tables and topic pages
    python scripts/overview_tables.py check   # exit 1 when a table or topic page is stale, or a field or topic is wrong

Topics: any content page may carry `tags`, one to four slugs from TOPICS, written inline. Each topic page is a table of
every page on that topic, grouped by page type. TOPICS has one owner. Every add, merge, or rename is its own commit with
a one-line reason. A retired slug goes into RETIRED with its replacement and is never reused.

A page opts in with `authors`. Its frontmatter then holds `authors`, `published`, `venue`, `tags` (topics from TOPICS),
`key_terms`, and `deliverables`, and optionally `url`, the public original, and `full_text`, a site route to the full
source. `published` is a date, or text such as "Unpublished" when no date is known. Lists are
written inline, for example `authors: ["Tarun Chitra"]`.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = ROOT / "content" / "Phase II" / "Wiki" / "Collections"
MILESTONES = ROOT / "content" / "Phase II" / "Milestones"
GLOSSARY = ROOT / "content" / "Phase II" / "Wiki" / "Reference" / "Glossary and Notation.md"
GLOSSARY_ROUTE = "/Phase-II/Wiki/Reference/Glossary-and-Notation"
START, END = "<!-- overview-table:start -->", "<!-- overview-table:end -->"
REQUIRED = ("authors", "published", "venue", "tags", "key_terms", "deliverables")

# slug: (label, what it covers, which neighbouring topic to use instead)
TOPICS = {
    "issuance-and-rewards": ("issuance and rewards", "The reward formula, consumption rates, the issuance schedule, inflation, and the supply cap", ""),
    "staking-duration-and-liquidity": ("staking duration and liquidity", "How long stake is committed, what locking costs, and the option to exit", ""),
    "delegation-market": ("delegation market", "Delegator choice, validator fees, and competition for delegation", "For concentration of stake across operators, see decentralization"),
    "decentralization": ("decentralization", "Validator count against stake-weighted security, concentration, and small operators", "For how delegators choose a validator, see delegation market"),
    "validator-economics": ("validator economics", "Operator costs, profitability, uptime, tenure, and rewarding them", "For what funds the network's security as a whole, see security budget"),
    "liquid-staking-and-restaking": ("liquid staking and restaking", "Stake that stays usable elsewhere, and stake reused across services", ""),
    "security-budget": ("security budget", "What pays for security, and the outside options that compete with staking", "For one operator's costs and income, see validator economics"),
    "fees-and-value-capture": ("fees and value capture", "Gas pricing, the fee burn, fee revenue, and mechanisms that capture value for AVAX", ""),
    "economic-measurement": ("economic measurement", "Value added, nominal against real output, chain-weighted indexes, and income against production", ""),
    "token-valuation": ("token valuation", "Why people hold AVAX, and how price, staking, and liquidity are determined together", ""),
    "distributional-effects": ("distributional effects", "Who pays for emissions and who gains from rewards and the fee burn", "For how rewards are computed, see issuance and rewards"),
    "mechanism-design": ("mechanism design", "Proposed rule changes and how to evaluate them", "For how a change is proposed and adopted, see protocol governance"),
    "protocol-governance": ("protocol governance", "How protocol parameters change: proposals, validator voting, phased activation, and rules against discretion", "For the design and evaluation of the rule itself, see mechanism design"),
    "market-conditions": ("market conditions", "Bull and bear markets, shocks, and how volatility changes choices", ""),
    "structural-estimation": ("structural estimation", "Recovering preferences from observed choices and fitting a model to data", ""),
    "model-structure": ("model structure", "Specifying an economic system as states, actions, and update rules", "For whether a model can be trusted, see model validation"),
    "model-validation": ("model validation", "Tests that decide whether a model can be trusted for policy", "For how a model is specified, see model structure"),
    "sensitivity-analysis": ("sensitivity analysis", "Which parameters and inputs drive each result", ""),
    "kpis-and-goals": ("KPIs and goals", "Indicators of success, their thresholds, and the goals that group them", ""),
    "parameter-selection-under-uncertainty": ("parameter selection under uncertainty", "Choosing parameters and policies that perform well across futures that cannot be predicted", ""),
}
# Authors are written on each page as the source prints them. The index groups variants under one canonical name.
AUTHOR_ALIASES = {"Eric Lu": "Siyu (Eric) Lu", "Siyu (Eric) Lu, PhD": "Siyu (Eric) Lu", "Matias A.": "Matias Antonio"}
ORGANIZATIONS = {"Avalanche", "Avalanche Foundation", "BENQI"}
HANDLES = {"CaptainDoubleBlade": "GitHub handle"}
AUTHORS_PAGE = ROOT / "content" / "Phase II" / "Wiki" / "Collections" / "Authors.md"

RETIRED: dict[str, str] = {}  # retired slug -> the topic that replaced it
CONTENT = ROOT / "content"


def frontmatter(text: str) -> tuple[dict, str, str]:
    """The parsed fields, the raw frontmatter block, and the body."""
    _, block, body = text.split("---\n", 2)
    fields = {}
    for line in block.splitlines():
        key, sep, value = line.partition(":")
        if not sep or line.startswith(" "):
            continue
        value = value.strip()
        try:
            fields[key] = json.loads(value) if value[:1] in '["' else value
        except json.JSONDecodeError:
            fields[key] = value
    return fields, block, body


def overview_pages() -> list[Path]:
    pages = list(COLLECTIONS.glob("*/*/index.md")) + [p for p in COLLECTIONS.glob("*/*.md") if p.name != "index.md"]
    return sorted(p for p in pages if "\nauthors:" in p.read_text(encoding="utf-8").split("---\n", 2)[1])


def deliverable_routes() -> dict[str, str]:
    """`1.3` -> `/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/`."""
    routes = {}
    for folder in MILESTONES.glob("Milestone */*"):
        match = re.match(r"(\d)-(\d) ", folder.name)
        if folder.is_dir() and match:
            routes[f"{match[1]}.{match[2]}"] = f"/Phase-II/Milestones/{folder.parent.name.replace(' ', '-')}/{folder.name.replace(' ', '-')}/"
    return routes


def glossary_terms() -> set[str]:
    return {m.lower() for m in re.findall(r"^\| ([^|]+?) \|", GLOSSARY.read_text(encoding="utf-8"), flags=re.M)}


def published(value: str) -> str:
    parts = value.split("-")
    if len(parts) == 3:
        return datetime.date(*map(int, parts)).strftime("%B %-d, %Y")
    if len(parts) == 2:
        return datetime.date(int(parts[0]), int(parts[1]), 1).strftime("%B %Y")
    return value


def table(fields: dict, routes: dict[str, str], terms: set[str]) -> str:
    source = fields["venue"] + (f", [original]({fields['url']})" if fields.get("url") else "")
    if fields.get("full_text"):
        source += f", [full text]({fields['full_text']})"
    topics = ", ".join(f"[{TOPICS[t][0]}](/tags/{t})" for t in fields["tags"])
    key_terms = ", ".join(f"[{t}]({GLOSSARY_ROUTE})" if t.lower() in terms else t for t in fields["key_terms"])
    serves = ", ".join(f"[{d}]({routes[d]})" for d in fields["deliverables"]) or "Background only"
    rows = [("Authors", ", ".join(fields["authors"])), ("Published", published(fields["published"])), ("Source", source),
            ("Topics", topics), ("Key terms", key_terms), ("Serves deliverables", serves)]
    return "\n".join([START, "", "| | |", "| --- | --- |", *(f"| **{k}** | {v} |" for k, v in rows), "", END])


def render(path: Path, routes: dict[str, str], terms: set[str]) -> tuple[str, list[str]]:
    text = path.read_text(encoding="utf-8")
    fields, block, body = frontmatter(text)
    problems = [f"missing {key}" for key in REQUIRED if key not in fields]
    problems += [f"unknown deliverable {d}" for d in fields.get("deliverables", []) if d not in routes]
    if problems:
        return text, problems
    body = re.sub(rf"\n*{re.escape(START)}.*?{re.escape(END)}\n*", "\n\n", body, flags=re.S).lstrip("\n")
    first, _, rest = body.partition("\n\n")
    return f"---\n{block}---\n\n{first}\n\n{table(fields, routes, terms)}\n\n{rest}", []


ECONOMICS = 14  # the first 14 topics are about Avalanche's economics, the rest about research method

# Page types in the order a topic page lists them, matched on the page's path under content/Phase II.
PAGE_TYPES = (
    ("Deliverables", lambda parts: parts[:1] == ("Milestones",) and "Milestone 0" not in parts),
    ("Memos", lambda parts: parts[:2] == ("Wiki", "Memos")),
    ("Briefs", lambda parts: parts[:2] == ("Wiki", "Briefs")),
    ("Reference", lambda parts: parts[:2] == ("Wiki", "Reference")),
    ("Interviews", lambda parts: parts[:1] == ("Interviews",)),
    ("Essential Readings", lambda parts: parts[:3] == ("Wiki", "Collections", "Essential Readings")),
    ("Economic ACPs", lambda parts: parts[:3] == ("Wiki", "Collections", "Economic ACPs")),
    ("Research papers", lambda parts: parts[:3] == ("Wiki", "Collections", "Supplementary Research Papers")),
    ("Contract", lambda parts: parts[:2] == ("Milestones", "Milestone 0")),
)


def page_type(path: Path) -> str:
    parts = path.relative_to(CONTENT / "Phase II").parts if (CONTENT / "Phase II") in path.parents else ()
    return next((name for name, match in PAGE_TYPES if match(parts)), "Other")


def route(path: Path) -> str:
    """The published route: spaces become hyphens, and a folder's index.md is the folder."""
    parts = list(path.relative_to(CONTENT).parts)
    if parts[-1] == "index.md":
        return "/" + "/".join(part.replace(" ", "-") for part in parts[:-1]) + "/"
    parts[-1] = Path(parts[-1]).stem
    return "/" + "/".join(part.replace(" ", "-") for part in parts)


def tagged_pages() -> list[Path]:
    """Every content page with a tags field, outside the generated topic pages."""
    pages = []
    for path in sorted(CONTENT.rglob("*.md")):
        if CONTENT / "tags" in path.parents:
            continue
        text = path.read_text(encoding="utf-8")
        if text.startswith("---\n") and re.search(r"^tags:", text.split("---\n", 2)[1], flags=re.M):
            pages.append(path)
    return pages


def topic_problems(path: Path) -> list[str]:
    fields, block, _ = frontmatter(path.read_text(encoding="utf-8"))
    tags = fields.get("tags")
    if not isinstance(tags, list):
        return ["tags must be an inline list, for example tags: [\"security-budget\"]"]
    problems = [f"retired topic {s}, use {RETIRED[s]}" for s in tags if s in RETIRED]
    problems += [f"unknown topic {s}" for s in tags if s not in TOPICS and s not in RETIRED]
    if not 1 <= len(tags) <= 4:
        problems.append(f"{len(tags)} topics, a page carries one to four")
    return problems


def cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def page_date(fields: dict) -> str:
    value = fields.get("published") or fields.get("date") or ""
    try:
        return published(str(value).strip('"'))
    except ValueError:
        return str(value)


def page_authors(fields: dict, kind: str) -> str:
    """The source's authors for a collection page, and BCRG for the research's own pages. More than three become et al."""
    authors = fields.get("authors")
    if not isinstance(authors, list) or not authors:
        return "" if kind in ("Essential Readings", "Economic ACPs", "Research papers") else "BCRG"
    return ", ".join(authors) if len(authors) <= 3 else f"{authors[0]} et al."


def topic_members() -> dict[str, list[tuple[str, Path, dict]]]:
    members: dict[str, list[tuple[str, Path, dict]]] = {slug: [] for slug in TOPICS}
    for path in tagged_pages():
        fields = frontmatter(path.read_text(encoding="utf-8"))[0]
        for slug in fields.get("tags", []) if isinstance(fields.get("tags"), list) else []:
            if slug in members:
                members[slug].append((page_type(path), path, fields))
    return members


def topic_page(slug: str, pages: list[tuple[str, Path, dict]]) -> str:
    label, meaning, instead = TOPICS[slug]
    lines = ["---", f'title: "Topic: {label}"', f'description: "{meaning}."']
    retired = [old for old, new in RETIRED.items() if new == slug]
    if retired:
        lines.append("aliases: [" + ", ".join(f'"tags/{old}"' for old in retired) + "]")
    lines += ["---", "", f"{meaning}." + (f" {instead}." if instead else ""), "",
              f"{len(pages)} pages are filed under this topic. See [all topics](/tags/).", ""]
    order = [name for name, _ in PAGE_TYPES] + ["Other"]
    for kind in order:
        # Oldest first, except memos and briefs, which read newest first. Sort on the raw ISO date, not the display text.
        raw = lambda p: str(p[2].get("published") or p[2].get("date") or "").strip('"')
        chosen = sorted((p for p in pages if p[0] == kind), key=lambda p: (raw(p), p[1].name), reverse=kind in ("Memos", "Briefs"))
        if not chosen:
            continue
        lines += [f"## {kind}", "", "| Page | Authors | Date | Summary |", "| --- | --- | --- | --- |"]
        lines += [f"| [{cell(f.get('title', path.stem))}]({route(path)}) | {cell(page_authors(f, kind))} | {cell(page_date(f))} | {cell(f.get('description', ''))} |" for _, path, f in chosen]
        lines.append("")
    return "\n".join(lines)


def topic_index(members: dict[str, list]) -> str:
    """The all-topics page: each topic, what it covers, and how many pages carry it.

    Quartz builds a topic's page only once a page carries it, so a topic with no pages is listed without a link.
    """
    def rows(slugs: list[str]) -> list[str]:
        out = ["| Topic | What it covers | Pages |", "| --- | --- | ---: |"]
        for s in slugs:
            label, meaning, instead = TOPICS[s]
            name = f"[{label}](/tags/{s})" if members[s] else label
            out.append(f"| {name} | {meaning}." + (f" *{instead}.*" if instead else "") + f" | {len(members[s])} |")
        return out
    slugs = list(TOPICS)
    return "\n".join([
        "---", 'title: "Topics"', 'description: "Every content page on the site, filed by topic: Avalanche economics and research method."', "---", "",
        "Every content page on the site is filed under one to four topics, shown under its title. Each topic opens a table of its pages: "
        "deliverables, memos, briefs, reference pages, interviews, and the [collections](/Phase-II/Wiki/Collections/).", "",
        "## Avalanche economics", "", *rows(slugs[:ECONOMICS]), "",
        "## Research method", "", *rows(slugs[ECONOMICS:]), "",
    ])


def surname(name: str) -> str:
    return name.split()[-1].lower() if " " in name else name.lower()


def authors_page() -> str:
    """Every author of a collection page, variants grouped under one name, people apart from organizations."""
    works: dict[str, list[tuple[str, str, str]]] = {}
    for path in overview_pages():
        fields = frontmatter(path.read_text(encoding="utf-8"))[0]
        year = str(fields.get("published", "")).strip('"')[:4]
        link = f"[{cell(fields.get('title', path.stem))}]({route(path)})"
        for author in fields.get("authors", []):
            works.setdefault(AUTHOR_ALIASES.get(author, author), []).append((year, link, page_type(path)))
    def rows(names: list[str]) -> list[str]:
        out = ["| Author | Sources |", "| --- | --- |"]
        for name in names:
            listed = "<br>".join(f"{link}, {year}" for year, link, _ in sorted(works[name]))
            label = f"{name} ({HANDLES[name]})" if name in HANDLES else name
            out.append(f"| {label} | {listed} |")
        return out
    people = sorted((n for n in works if n not in ORGANIZATIONS), key=lambda n: (surname(n), n))
    orgs = sorted(n for n in works if n in ORGANIZATIONS)
    return "\n".join([
        "---", 'title: "Authors"', 'description: "Every author of the Essential Readings, Economic ACPs, and Supplementary Research Papers, with their sources."', "---", "",
        f"The {len(people)} people and {len(orgs)} organizations who wrote the sources in the [collections](/Phase-II/Wiki/Collections/). "
        "Names are written as each source prints them, with variants of one name grouped together. Sources can also be browsed by [topic](/tags/).", "",
        "## People", "", *rows(people), "",
        "## Organizations", "", *rows(orgs), "",
    ])


def topic_pages() -> dict[Path, str]:
    """One page per topic with its table of pages, plus the all-topics page."""
    members = topic_members()
    pages = {CONTENT / "tags" / f"{slug}.md": topic_page(slug, members[slug]) for slug in TOPICS}
    pages[CONTENT / "tags" / "index.md"] = topic_index(members)
    pages[AUTHORS_PAGE] = authors_page()
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("build", "check"))
    args = parser.parse_args()
    routes, terms, failed = deliverable_routes(), glossary_terms(), False
    for path in tagged_pages():
        problems = topic_problems(path)
        if problems:
            print(f"{path.relative_to(CONTENT)}: {', '.join(problems)}")
            failed = True
    for path in overview_pages():
        text, problems = render(path, routes, terms)
        name = path.relative_to(COLLECTIONS)
        if problems:
            print(f"{name}: {', '.join(problems)}")
            failed = True
        elif text != path.read_text(encoding="utf-8"):
            if args.command == "build":
                path.write_text(text, encoding="utf-8")
                print(f"wrote {name}")
            else:
                print(f"{name}: table is stale, run: python scripts/overview_tables.py build")
                failed = True
    generated = topic_pages()
    for path, text in generated.items():
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            continue
        if args.command == "build":
            path.parent.mkdir(exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
        else:
            print(f"{path.relative_to(ROOT)}: topic page is stale")
            failed = True
    for path in sorted((CONTENT / "tags").glob("*.md")):
        if path not in generated:
            if args.command == "build":
                path.unlink()
                print(f"removed {path.relative_to(ROOT)}")
            else:
                print(f"{path.relative_to(ROOT)}: not a topic in TOPICS")
                failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
