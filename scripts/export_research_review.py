"""Export selected research pages as linked GitHub Markdown and checked assets.

    python scripts/export_research_review.py --project . --output docs/review/2026-10-30
    python scripts/export_research_review.py --project . --output docs/review/2026-10-30 --check

The maintained pages remain unchanged. The manifest binds source bytes, rewritten
links, copied dependencies and export bytes. Upstream artifact identities in JSON
remain provenance rather than promises that historical outputs are distributed.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import posixpath
import re
import subprocess
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit

SOURCE_DIRECTORY = "content/Phase II/Wiki/Memos/drafts/2026-10-30-research"
DOCUMENTS = {f"{SOURCE_DIRECTORY}/{name}.md": exported for name, exported in (
    ("methodology", "modeling.md"), ("evidence", "evidence.md"), ("results", "results.md"),
)}
MANIFEST = "export-manifest.json"
POINTERS = {"file", "editable_file", "inputs_file", "source_receipt", "generator", "script", "path", "source_file"}
FILE_SUFFIX = re.compile(r"\.(?:md|json|png|svg|csv|tsv|parquet|py|pdf|html|txt|ya?ml)$", re.IGNORECASE)


class ExportError(ValueError):
    """An input or export cannot satisfy the review-package contract."""


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def slug(path: str) -> str:
    """Quartz file slugs, matching quartz/util/path.ts and check_links.py."""
    path = re.sub(r"\s", "-", path).replace("&", "-and-").replace("%", "-percent")
    path = path.replace("?", "").replace("#", "")
    return re.sub(r"_index$", "index", path)


def aliases(text: str) -> list[str]:
    """Read scalar, inline-list and block-list aliases from YAML front matter."""
    if not text.startswith("---\n"):
        return []
    front = text.split("\n---", 1)[0].splitlines()[1:]
    result, collecting = [], False
    for line in front:
        match = re.match(r"(?:aliases|alias):\s*(.*)$", line)
        if match:
            value = match[1].strip()
            collecting = not value
            if value.startswith("["):
                try:
                    values = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    values = [item.strip().strip("\"'") for item in value[1:-1].split(",")]
                if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                    raise ExportError("aliases must be strings")
                result.extend(values)
            elif value:
                result.append(value.strip("\"'"))
        elif collecting and re.match(r"\s+-\s+", line):
            result.append(re.sub(r"^\s+-\s+", "", line).strip().strip("\"'"))
        elif line and not line[0].isspace():
            collecting = False
    return result


def review_presentation(text: str) -> str:
    """Replace a titled page's metadata with its GitHub review heading."""
    front = re.match(r"\A---\n(.*?)\n---(?:\n|\Z)", text, re.DOTALL)
    if front is None:
        return text
    title = re.search(r"^title:\s*([^\n]+)$", front[1], re.MULTILINE)
    if title is None:
        return text
    value = title[1].strip()
    if value.startswith('"'):
        value = json.loads(value)
    elif value.startswith("'") and value.endswith("'"):
        value = value[1:-1].replace("''", "'")
    elif value.startswith(("[", "{", "|", ">", "&", "*", "!", "'")):
        raise ExportError("review title must be a scalar string")
    else:
        value = re.sub(r"\s+#.*$", "", value)
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        raise ExportError("review title must be a nonempty single-line string")
    historical = re.search(r"^kind: (?:archival-edition|historical-record|research-history)$", front[1], re.MULTILINE)
    status = "" if historical else "*Draft for review.*\n\n"
    return f"# {value}\n\n{status}" + text[front.end():].lstrip("\n")


def visible(text: str, inline_code: bool = False) -> str:
    """Mask metadata, fenced code and inline code while retaining offsets."""
    lines, fence, front = [], None, text.startswith("---\n")
    for number, line in enumerate(text.splitlines(keepends=True)):
        if front:
            if number and line.strip() == "---":
                front = False
            lines.append(re.sub(r"[^\n]", " ", line))
            continue
        marker = re.match(r"\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            lines.append(re.sub(r"[^\n]", " ", line))
        elif fence:
            lines.append(re.sub(r"[^\n]", " ", line))
        else:
            lines.append(line if inline_code else re.sub(r"(`+)(.+?)\1", lambda m: " " * len(m[0]), line))
    return "".join(lines)


def anchors(text: str) -> set[str]:
    found, used = set(), set()
    body = visible(text, inline_code=True)
    headings = re.findall(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$|^([^\n]+)\n {0,3}(?:=+|-+)\s*$", body, re.MULTILINE)
    for atx, setext in headings:
        heading = atx or setext
        heading = re.sub(r"\[([^]]*)\]\([^)]*\)", r"\1", heading)
        base = re.sub(r"[^\w\s-]", "", html.unescape(re.sub(r"<[^>]*>", "", heading)).lower()).replace(" ", "-")
        candidate, count = base, 0
        while candidate in used:
            count += 1
            candidate = f"{base}-{count}"
        found.add(candidate)
        used.add(candidate)
    found.update(re.findall(r"\bid=[\"']([^\"']+)[\"']", body))
    return found


def links(text: str) -> list[tuple[int, int, str]]:
    """Locate destinations without changing labels, titles or surrounding prose."""
    masked = visible(text)
    if "[[" in masked:
        raise ExportError("wiki links must be explicit Markdown links before export")
    definitions = {" ".join(name.lower().split())
                   for name in re.findall(r"^ {0,3}\[([^]\n]+)\]:", masked, re.MULTILINE)}
    for label, name in re.findall(r"!?\[([^]\n]+)\]\[([^]\n]*)\]", masked):
        if " ".join((name or label).lower().split()) not in definitions:
            raise ExportError(f"undefined Markdown reference: {name or label}")
    spans = []
    for match in re.finditer(r"!?\[[^\]\n]*\]\(\s*", masked):
        start = match.end()
        if start < len(text) and text[start] == "<":
            end = text.find(">", start + 1)
            if end < 0:
                raise ExportError("unterminated angle-bracket link")
            spans.append((start + 1, end, text[start + 1:end]))
            continue
        end, depth = start, 0
        while end < len(text):
            char = text[end]
            if char == "\\":
                end += 2
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            elif char.isspace() and depth == 0:
                break
            end += 1
        spans.append((start, end, text[start:end]))
    for pattern in (r"^ {0,3}\[[^]\n]+\]:\s*(?:<([^>]+)>|(\S+))", r"\b(?:href|src)=[\"']([^\"']+)[\"']"):
        for match in re.finditer(pattern, masked, re.MULTILINE):
            group = next(i for i in range(1, len(match.groups()) + 1) if match[i] is not None)
            spans.append((*match.span(group), text[slice(*match.span(group))]))
    return sorted(set(spans))


class Exporter:
    def __init__(self, project: Path, output: Path, documents: dict[str, str] | None = None):
        self.root = project.resolve()
        self.output = self.safe(output)
        if self.output == self.root or self.output.is_relative_to(self.root / "content"):
            raise ExportError("output must be a separate directory outside content")
        raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=self.root)
        self.tracked = {item.decode() for item in raw.split(b"\0") if item}
        self.documents = {self.safe(Path(source)): self.safe(self.output / target)
                          for source, target in (DOCUMENTS if documents is None else documents).items()}
        if len(set(self.documents.values())) != len(self.documents):
            raise ExportError("document export collision")
        for destination in self.documents.values():
            if destination.parent != self.output or destination.name == MANIFEST:
                raise ExportError("document destinations must be distinct top-level Markdown files")
        self.sources: dict[Path, bytes] = {}
        self.exports: dict[Path, bytes] = {}
        self.routes: dict[str, set[Path]] = {}
        self.references: list[dict] = []
        self.upstream: list[dict] = []
        self.assets: set[Path] = set()
        self.repository_references: set[Path] = set()

    def safe(self, path: Path) -> Path:
        if ".." in path.parts:
            raise ExportError(f"path traversal is not allowed: {path}")
        resolved = (path if path.is_absolute() else self.root / path).resolve()
        if not resolved.is_relative_to(self.root):
            raise ExportError("path escapes project")
        return resolved

    def relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def read(self, path: Path) -> bytes:
        path = self.safe(path)
        if not path.is_file():
            raise ExportError(f"missing dependency: {self.relative(path)}")
        if path.is_relative_to(self.output):
            raise ExportError("export cannot be its own source")
        if path not in self.sources:
            self.sources[path] = path.read_bytes()
        return self.sources[path]

    def index(self) -> None:
        for source in sorted((self.root / "content").rglob("*")):
            if not source.is_file():
                continue
            source = self.safe(source)
            relative = source.relative_to(self.root / "content").as_posix()
            route = slug(relative.removesuffix(".md") if source.suffix == ".md" else relative)
            names = [route]
            if source.suffix == ".md":
                names = [route]
                for alias in aliases(source.read_text()):
                    if ".." in PurePosixPath(alias).parts or "\\" in alias or urlsplit(alias).scheme:
                        raise ExportError(f"invalid declared alias: {alias}")
                    names.append(slug(alias.removesuffix(".md").strip("/")))
            for name in names:
                self.routes.setdefault("/" + name.rstrip("/"), set()).add(source)
                if name == "index" or name.endswith("/index"):
                    self.routes.setdefault("/" + name[:-5].rstrip("/"), set()).add(source)

    def resolve(self, source: Path, href: str) -> tuple[Path, str] | None:
        url = urlsplit(html.unescape(href))
        if url.scheme or url.netloc:
            if source.suffix == ".svg" and re.match(r"^data:image/(?:png|jpeg|gif|webp);base64,", href):
                return None  # Embedded raster bytes already belong to the copied SVG.
            if url.scheme not in ("", "https", "http", "mailto", "tel"):
                raise ExportError(f"unsupported URL scheme: {url.scheme}")
            return None
        decoded = unquote(url.path)
        if "\\" in decoded or ".." in PurePosixPath(decoded).parts or "\0" in decoded:
            raise ExportError(f"path traversal is not allowed: {href}")
        if url.query:
            raise ExportError(f"local link queries are unsupported: {href}")
        if not decoded:
            target = source
        else:
            candidates = self.routes.get(decoded.rstrip("/") or "/", set()) if decoded.startswith("/") else set()
            if not decoded.startswith("/"):
                direct = self.safe(source.parent / decoded)
                root_file = self.safe(Path(decoded))
                if direct.is_file():
                    candidates = {direct}
                elif root_file.is_file():
                    candidates = {root_file}
                else:
                    if source.is_relative_to(self.root / "content"):
                        parent_route = slug(source.parent.relative_to(self.root / "content").as_posix())
                        candidates = self.routes.get("/" + parent_route + "/" + slug(decoded).rstrip("/"), set())
            if len(candidates) != 1:
                raise ExportError(f"unknown or ambiguous route in {self.relative(source)}: {href}")
            target = next(iter(candidates))
        body = self.read(target)
        fragment = unquote(url.fragment)
        if fragment and (target.suffix not in (".md", ".svg", ".html") or fragment not in anchors(body.decode())):
            raise ExportError(f"missing fragment in {self.relative(target)}: {fragment}")
        return target, fragment

    def destination(self, target: Path) -> Path:
        if target in self.documents:
            return self.documents[target]
        if target.suffix == ".md":
            if self.relative(target) not in self.tracked:
                raise ExportError(f"repository Markdown reference is not tracked: {self.relative(target)}")
            self.repository_references.add(target)
            return target
        self.assets.add(target)
        return self.output / "assets" / self.relative(target)

    def rewrite(self, source: Path, destination: Path) -> bytes:
        text = self.read(source).decode()
        replacements = []
        for start, end, href in links(text):
            resolved = self.resolve(source, href)
            if resolved is None:
                continue
            target, fragment = resolved
            exported = self.destination(target)
            relative = posixpath.relpath(exported.as_posix(), destination.parent.as_posix())
            rewritten = quote(relative, safe="/-._~") + ("#" + quote(fragment, safe="-._~") if fragment else "")
            self.references.append({"source": self.relative(source), "href": href, "target": self.relative(target),
                                    "fragment": fragment, "destination": self.relative(exported), "rewritten": rewritten})
            replacements.append((start, end, rewritten))
        for start, end, value in reversed(replacements):
            text = text[:start] + value + text[end:]
        if source in self.documents:
            text = review_presentation(text)
        return text.encode()

    def json_dependencies(self, source: Path, value, location: str = ""):
        if isinstance(value, list):
            return [self.json_dependencies(source, item, f"{location}/{index}")
                    for index, item in enumerate(value)]
        elif isinstance(value, dict):
            result = dict(value)
            for key, item in value.items():
                field = f"{location}/{key}"
                if key in ("artifact", "pin_relative_path") and isinstance(item, str):
                    record = {"source": self.relative(source), "field": field,
                              "artifact": item, "status": "not-delivered"}
                    if key == "artifact":
                        record.update({k: value[k] for k in ("sha256", "bytes") if k in value})
                    self.upstream.append(record)
                elif isinstance(item, str) and (key in POINTERS or
                        (key == "source" and FILE_SUFFIX.search(item))):
                    resolved = self.resolve(source, item)
                    if resolved is not None:
                        target, fragment = resolved
                        destination = self.destination(target)
                        origin = self.output / "assets" / self.relative(source)
                        rewritten = posixpath.relpath(destination.as_posix(), origin.parent.as_posix())
                        if fragment:
                            rewritten += "#" + fragment
                        result[key] = rewritten
                        self.references.append({"source": self.relative(source), "field": field,
                                                "target": self.relative(target), "fragment": fragment,
                                                "destination": self.relative(destination), "rewritten": rewritten})
                else:
                    result[key] = self.json_dependencies(source, item, field)
            return result
        return value

    def plan(self) -> tuple[dict[Path, bytes], dict]:
        self.index()
        for source, destination in self.documents.items():
            if re.search(r"\\operatorname\b", visible(self.read(source).decode())):
                raise ExportError(f"GitHub rejects operatorname: {self.relative(source)}; use mathrm")
            self.exports[destination] = self.rewrite(source, destination)
        done = set()
        while self.assets - done:
            source = min(self.assets - done)
            body = self.read(source)
            destination = self.output / "assets" / self.relative(source)
            self.exports[destination] = body
            done.add(source)
            if source.suffix == ".json":
                original = json.loads(body)
                resolved = self.json_dependencies(source, original)
                if resolved != original:
                    self.exports[destination] = (json.dumps(resolved, indent=2, ensure_ascii=False) + "\n").encode()
            elif source.suffix == ".svg":
                # SVGs retain their bytes and directory structure. Local dependencies
                # must resolve to files copied beside them, rather than a site route.
                for _, _, href in links(body.decode()):
                    resolved = self.resolve(source, href)
                    if resolved and resolved[0] != source:
                        direct = self.safe(source.parent / unquote(urlsplit(href).path))
                        if href.startswith("/") or resolved[0].suffix == ".md" or direct != resolved[0]:
                            raise ExportError("SVG dependencies must be relative asset files")
                        exported = self.destination(resolved[0])
                        self.references.append({"source": self.relative(source), "href": href,
                                                "target": self.relative(resolved[0]), "fragment": resolved[1],
                                                "destination": self.relative(exported), "rewritten": href})
        entries = []
        for source in sorted(self.sources):
            destination = self.documents.get(source)
            if source in self.assets:
                destination = self.output / "assets" / self.relative(source)
            entry = {"source": self.relative(source), "source_sha256": digest(self.sources[source]),
                     "kind": "repository-reference" if destination is None else "export"}
            if destination is not None:
                entry.update({"export": destination.relative_to(self.output).as_posix(),
                              "export_sha256": digest(self.exports[destination])})
            entries.append(entry)
        manifest = {"schema": "research-review-export/v1", "output": self.relative(self.output),
                    "documents": {self.relative(s): d.name for s, d in self.documents.items()},
                    "files": entries, "references": self.references, "upstream_artifacts": self.upstream}
        return self.exports, manifest

    def run(self, check: bool = False) -> dict:
        exports, manifest = self.plan()
        expected = {**exports, self.output / MANIFEST: (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()}
        for source, body in self.sources.items():
            if source.read_bytes() != body:
                raise ExportError(f"source changed during export: {self.relative(source)}")
        existing = set(self.output.rglob("*")) if self.output.exists() else set()
        unexpected = sorted(p for p in existing if p.is_file() and p not in expected)
        if unexpected:
            raise ExportError(f"unexpected export files: {[self.relative(p) for p in unexpected]}")
        if check:
            changed = [self.relative(p) for p, body in expected.items()
                       if not p.is_file() or self.safe(p).read_bytes() != body]
            if changed:
                raise ExportError(f"export is missing or changed: {changed}")
        else:
            for path, body in expected.items():
                self.safe(path).parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
        return {"status": "pass", "documents": len(self.documents), "assets": len(self.assets),
                "repository_references": len(self.repository_references), "output": self.relative(self.output)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("docs/review/2026-10-30"))
    parser.add_argument("--check", action="store_true", help="Verify sources, mappings and every exported byte without writing")
    args = parser.parse_args()
    try:
        print(json.dumps(Exporter(args.project, args.output).run(args.check), sort_keys=True))
    except (ExportError, OSError, subprocess.CalledProcessError, UnicodeError, json.JSONDecodeError) as error:
        parser.exit(1, f"FAIL | research review export | {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
