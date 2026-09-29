#!/usr/bin/env python3
"""Render the facts table under the first paragraph of each collection overview, from the page's frontmatter.

    python scripts/overview_tables.py build   # write the tables
    python scripts/overview_tables.py check   # exit 1 when a table is stale or a field is missing

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

TOPICS = {
    "issuance-and-rewards": ("issuance and rewards", "The reward formula, consumption rates, the issuance schedule, inflation, and the supply cap"),
    "staking-duration-and-liquidity": ("staking duration and liquidity", "How long stake is committed, what locking costs, and the option to exit"),
    "delegation-market": ("delegation market", "Delegator choice, validator fees, and competition for delegation"),
    "decentralization": ("decentralization", "Validator count against stake-weighted security, concentration, and small operators"),
    "validator-economics": ("validator economics", "Operator costs, profitability, uptime, tenure, and rewarding them"),
    "liquid-staking-and-restaking": ("liquid staking and restaking", "Stake that stays usable elsewhere, and stake reused across services"),
    "security-budget": ("security budget", "What pays for security, and the outside options that compete with staking"),
    "fees-and-value-capture": ("fees and value capture", "Gas pricing, the fee burn, fee revenue, and mechanisms that capture value for AVAX"),
    "economic-measurement": ("economic measurement", "Value added, nominal against real output, chain-weighted indexes, and income against production"),
    "token-valuation": ("token valuation", "Why people hold AVAX, and how price, staking, and liquidity are determined together"),
    "distributional-effects": ("distributional effects", "Who pays for emissions and who gains from rewards and the fee burn"),
    "mechanism-design": ("mechanism design", "Proposed rule changes and how to evaluate them"),
    "protocol-governance": ("protocol governance", "How protocol parameters change: proposals, validator voting, phased activation, and rules against discretion"),
    "market-conditions": ("market conditions", "Bull and bear markets, shocks, and how volatility changes choices"),
    "structural-estimation": ("structural estimation", "Recovering preferences from observed choices and fitting a model to data"),
    "model-structure": ("model structure", "Specifying an economic system as states, actions, and update rules"),
    "model-validation": ("model validation", "Tests that decide whether a model can be trusted for policy"),
    "sensitivity-analysis": ("sensitivity analysis", "Which parameters and inputs drive each result"),
    "kpis-and-goals": ("KPIs and goals", "Indicators of success, their thresholds, and the goals that group them"),
    "parameter-selection-under-uncertainty": ("parameter selection under uncertainty", "Choosing parameters and policies that perform well across futures that cannot be predicted"),
}


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
    problems += [f"unknown topic {t}" for t in fields.get("tags", []) if t not in TOPICS]
    problems += [f"unknown deliverable {d}" for d in fields.get("deliverables", []) if d not in routes]
    if problems:
        return text, problems
    body = re.sub(rf"\n*{re.escape(START)}.*?{re.escape(END)}\n*", "\n\n", body, flags=re.S).lstrip("\n")
    first, _, rest = body.partition("\n\n")
    return f"---\n{block}---\n\n{first}\n\n{table(fields, routes, terms)}\n\n{rest}", []


ECONOMICS = 14  # the first 14 topics are about Avalanche's economics, the rest about research method


def topic_index() -> str:
    """The all-topics page: each topic, what it covers, and how many sources carry it.

    Quartz builds a topic's page only once a source carries it, so a topic with no sources is listed without a link.
    """
    counts = {slug: 0 for slug in TOPICS}
    for path in overview_pages():
        for slug in frontmatter(path.read_text(encoding="utf-8"))[0].get("tags", []):
            counts[slug] = counts.get(slug, 0) + 1
    def rows(slugs: list[str]) -> list[str]:
        return ["| Topic | What it covers | Sources |", "| --- | --- | ---: |",
                *(f"| {f'[{TOPICS[s][0]}](/tags/{s})' if counts[s] else TOPICS[s][0]} | {TOPICS[s][1]} | {counts[s]} |" for s in slugs)]
    slugs = list(TOPICS)
    return "\n".join([
        "---", 'title: "Topics"', 'description: "Every source in the collections, filed by topic: Avalanche economics and research method."', 'cssclasses: ["topics-index"]', "---", "",
        "Every page in the [collections](/Phase-II/Wiki/Collections/) is filed under one or more topics, shown under its title and in its facts table. "
        "Each topic below opens a page listing its sources.", "",
        "## Avalanche economics", "", *rows(slugs[:ECONOMICS]), "",
        "## Research method", "", *rows(slugs[ECONOMICS:]), "",
    ])


def topic_pages() -> dict[Path, str]:
    """One page per topic, so each Quartz tag page carries its title and meaning, plus the all-topics page."""
    pages = {ROOT / "content" / "tags" / f"{slug}.md": f'---\ntitle: "Topic: {label}"\ndescription: "{meaning}."\n---\n\n{meaning}. The sources below are filed under this topic. See [all topics](/tags/).\n'
             for slug, (label, meaning) in TOPICS.items()}
    pages[ROOT / "content" / "tags" / "index.md"] = topic_index()
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("build", "check"))
    args = parser.parse_args()
    routes, terms, failed = deliverable_routes(), glossary_terms(), False
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
    for path, text in topic_pages().items():
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            continue
        if args.command == "build":
            path.parent.mkdir(exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
        else:
            print(f"{path.relative_to(ROOT)}: topic page is stale")
            failed = True
    for path in sorted((ROOT / "content" / "tags").glob("*.md")):
        if path not in topic_pages():
            if args.command == "build":
                path.unlink()
                print(f"removed {path.relative_to(ROOT)}")
            else:
                print(f"{path.relative_to(ROOT)}: not a topic in TOPICS")
                failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
