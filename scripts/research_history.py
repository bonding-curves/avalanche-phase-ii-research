"""Verify historical editions and export their GitHub reading copies.

python scripts/research_history.py
python scripts/research_history.py --export
python scripts/research_history.py --export --check

Original or explicitly redacted UTF-8 source editions are retained as .txt.
Metadata-only records carry no source body. Rendered editions change heading
depth, metadata line breaks, image routes, currency escapes and historical links.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from pathlib import Path
from urllib.parse import unquote

from export_research_review import DOCUMENTS as REVIEW_DOCUMENTS
from export_research_review import Exporter, ExportError, links, slug

DIRECTORY = "content/Phase II/Wiki/Research History"
START = "<!-- historical-original:start -->\n"
END = "<!-- historical-original:end -->"


def route(path: str) -> str:
    return "/" + slug(path.removeprefix("content/").removesuffix(".md"))


def safe(root: Path, relative: str) -> Path:
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("historical file must stay inside the checkout")
    return path


def original_edition(root: Path, entry: dict) -> str:
    """Apply the documented display transformations to the retained original."""
    text = safe(root, entry["original"]).read_bytes().decode("utf-8")
    assets = {asset["source_href"]: asset for asset in entry["assets"]}
    references = {}
    replacements = []
    for start, end, href in links(text):
        asset = assets.get(unquote(href))
        if asset:
            target = route(asset["file"])
        elif (href.startswith(("https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/main/",
                               "https://www.notion.so/"))
              or not href.startswith(("http://", "https://", "#", "mailto:"))):
            number = references.setdefault(href, len(references) + 1)
            target = f"#historical-reference-{number}"
        else:
            target = href
        replacements.append((start, end, target))
    for start, end, target in reversed(replacements):
        text = text[:start] + target + text[end:]
    text = re.sub(r"^(#{1,4}) ", lambda match: "##" + match[1] + " ", text, flags=re.MULTILINE)
    text = re.sub(r"^((?:Created By|Creation Time|Description|Last Edited Time|Sprint|Status|"
                  r"\*\*(?:Date|To|From|Subject)\*\*):[^\n]+)\n", r"\1  \n", text, flags=re.MULTILINE)
    text = re.sub(r"(?<!\\)\$(129)(?= per month)", r"\\$\1", text)
    if references:
        text = text.rstrip("\n") + "\n\n### Historical references\n\n"
        text += ("The original links below name earlier project references. Their availability "
                 "has not been established. The text above links here, and the original export "
                 "retains every URL.\n\n")
        text += "\n\n".join(f'#### Historical reference {number}\n\n`{url}`'
                              for url, number in references.items()) + "\n"
    return text


def verify(root: Path) -> dict:
    manifest = json.loads((root / DIRECTORY / "manifest.json").read_text())
    if manifest["schema"] != "research-history/v1":
        raise ValueError("unknown research-history schema")
    seen = set()
    assets = 0
    forms = {"original": 0, "redacted": 0, "metadata-only": 0}
    for entry in manifest["entries"]:
        identity = str(uuid.UUID(entry["id"]))
        form = entry.get("source_form", "original")
        if identity in seen or form not in forms:
            raise ValueError("duplicate or inconsistent source identity")
        seen.add(identity)
        forms[form] += 1
        page = safe(root, entry["page"]).read_text()
        if f"source_id: {identity}\n" not in page.split("\n---", 1)[0]:
            raise ValueError("edition source identity differs")
        if form == "metadata-only":
            if entry.get("original") is not None or START in page or END in page:
                raise ValueError("metadata-only record must not contain an original body")
            if "Metadata record only" not in page:
                raise ValueError("metadata-only status must be visible")
            continue
        prefix = "source" if form == "redacted" else "original"
        if not entry["original"].endswith(f"{prefix}-{identity}.txt"):
            raise ValueError("source text identity differs")
        raw = safe(root, entry["original"]).read_bytes()
        expected_bytes = entry["text_bytes"] if form == "redacted" else entry["original_bytes"]
        expected_hash = entry["text_sha256"] if form == "redacted" else entry["original_sha256"]
        if len(raw) != expected_bytes or hashlib.sha256(raw).hexdigest() != expected_hash:
            raise ValueError(f"original bytes differ: {entry['original']}")
        if form == "redacted" and ("Redacted source edition" not in page or "[REDACTED:" not in raw.decode()):
            raise ValueError("redacted status and omissions must be visible")
        source = raw.decode("utf-8")
        if source.splitlines()[0] != "# " + entry["title"]:
            raise ValueError("original title differs")
        for label, key in (("Created By", "creator"), ("Creation Time", "created"), ("Last Edited Time", "edited")):
            if not re.search(r"^" + label + ": " + re.escape(entry[key]) + r"$", source, re.MULTILINE):
                raise ValueError(f"source metadata differs: {label}")
        if page.count(START) != 1 or page.count(END) != 1:
            raise ValueError("edition must contain one bounded original")
        actual = page.split(START, 1)[1].split(END, 1)[0]
        if actual != original_edition(root, entry):
            raise ValueError(f"historical text or figure routes differ: {entry['page']}")
        for asset in entry["assets"]:
            body = safe(root, asset["file"]).read_bytes()
            if len(body) != asset["bytes"] or hashlib.sha256(body).hexdigest() != asset["sha256"]:
                raise ValueError(f"historical figure differs: {asset['file']}")
            assets += 1
    return {"status": "pass", "entries": len(seen), "figures": assets, "source_forms": forms}


def export(root: Path, check: bool = False) -> dict:
    manifest = json.loads((root / DIRECTORY / "manifest.json").read_text())
    documents = {f"{DIRECTORY}/index.md": "README.md"}
    for entry in manifest["entries"]:
        documents[entry["page"]] = Path(entry["page"]).parent.name + ".md"
    class HistoryExporter(Exporter):
        def destination(self, target: Path) -> Path:
            review_name = REVIEW_DOCUMENTS.get(self.relative(target))
            if review_name is not None:
                reading_copy = self.root / "docs/review/2026-10-30" / review_name
                self.read(reading_copy)
                self.repository_references.add(reading_copy)
                return reading_copy
            return super().destination(target)

    return HistoryExporter(root, Path("docs/research-history"), documents).run(check=check)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--check", action="store_true", help="Check an existing GitHub export without writing")
    args = parser.parse_args()
    try:
        result = verify(args.project)
        if args.export:
            result["export"] = export(args.project, args.check)
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError, ExportError) as error:
        parser.exit(1, f"FAIL | research history | {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
