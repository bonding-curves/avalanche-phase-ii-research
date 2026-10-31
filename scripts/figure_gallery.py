"""Build/check the portable client figure gallery from tracked delivered assets.

python scripts/figure_gallery.py build
python scripts/figure_gallery.py check

Only the gallery directory is written. No plot, data source or model is executed.
The maintained registry supplies explicit classifications. Document usage, hashes,
available exports and captions are derived from the current tracked checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import posixpath
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

DIRECTORY = "content/Phase II/Wiki/Figures"
IMAGE_SUFFIXES = {".png", ".svg", ".jpg", ".jpeg", ".webp", ".gif"}
DEFAULTS = {"models": ["Unspecified"], "family": "Unspecified", "horizons": ["Unspecified"],
            "evidence": "Unspecified", "classification_basis": "No explicit classification recorded."}
IMAGE = re.compile(r'!\[([^\]]*)\]\((<[^>]+>|[^\n)]+)\)|<img\b[^>]*\bsrc=[\"\']([^\"\']+)[\"\'][^>]*>', re.IGNORECASE)


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def safe(root: Path, relative: str) -> Path:
    path = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Path leaves the repository: {relative}")
    if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root and parent.is_relative_to(root)):
        raise ValueError(f"Symlink is not an authenticated gallery source: {relative}")
    return path


def slug(value: str) -> str:
    value = re.sub(r"\s", "-", value).replace("&", "-and-").replace("%", "-percent")
    return re.sub(r"_index$", "index", value.replace("?", "").replace("#", ""))


def links(path: str, *, page: bool = False) -> dict:
    """Two relative addresses: Quartz's published slug and a source-checkout file."""
    source = path.removeprefix("content/")
    destination = slug(source)
    if page:
        destination = destination.removesuffix(".md")
        if destination.endswith("/index"):
            destination = destination[:-5]
    return {
        "href": quote(posixpath.relpath(destination, slug(DIRECTORY.removeprefix("content/")))),
        "file_href": quote(posixpath.relpath(path, DIRECTORY)),
    }


def scalar(text: str, key: str, fallback: str) -> str:
    front = re.match(r"\A---\n(.*?)\n---", text, re.DOTALL)
    match = re.search(r"^" + re.escape(key) + r":\s*(.+)$", front[1], re.MULTILINE) if front else None
    if not match:
        return fallback
    value = match[1].strip()
    if value.startswith('"'):
        try:
            return str(json.loads(value))
        except ValueError:
            return fallback
    return value.strip("'").replace("''", "'")


def tracked(root: Path) -> list[str]:
    output = subprocess.run(["git", "ls-files", "-z", "--cached"], cwd=root, check=True,
                            capture_output=True, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}).stdout
    return sorted(set(output.decode("utf-8").split("\0")) - {""})


def _caption(text: str, end: int, alt: str) -> str:
    following = text[end:].lstrip().split("\n\n", 1)[0]
    if re.match(r"\*?(?:Figure|Suggested caption:)", following):
        return re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", following).strip("* \n")
    return alt or "Caption not recorded. Open the source document for context."


def usages(root: Path, paths: list[str], images: list[str]) -> tuple[dict, dict]:
    routes = {"/" + slug(name.removeprefix("content/")): name for name in images}
    by_name = defaultdict(list)
    for name in images:
        by_name[Path(name).name].append(name)
    found = defaultdict(list)
    documents = {}
    for name in paths:
        if not name.startswith("content/") or not name.endswith(".md") or name.startswith(DIRECTORY + "/"):
            continue
        text = safe(root, name).read_text(encoding="utf-8")
        title = scalar(text, "title", Path(name).stem)
        documents[name] = {"path": name, "title": title, "question": scalar(text, "question", ""), **links(name, page=True)}
        # Ignore fenced examples. Keep offsets so captions remain attached to their images.
        visible = re.sub(r"(?ms)^```.*?^```[^\n]*", lambda m: " " * len(m[0]), text)
        matches = [(m[0], m[1], m[2], m.end()) for m in IMAGE.finditer(visible)]
        matches += [(m[0], m[1].split("|")[-1], m[1].split("|")[0], m.end())
                    for m in re.finditer(r"!\[\[([^\]]+)\]\]", visible)]
        for markup, alt, target, end in matches:
            if markup.lower().startswith("<img"):
                target = re.search(r'\bsrc=[\"\']([^\"\']+)', markup, re.IGNORECASE)[1]
                alt_match = re.search(r'\balt=[\"\']([^\"\']*)', markup, re.IGNORECASE)
                alt = alt_match[1] if alt_match else ""
            elif target is None:
                # Markdown image matches have their URL in group 2.
                target = re.match(r"!\[[^\]]*\]\((.*)\)", markup)[1]
            target = target.strip().strip("<>")
            target = re.sub(r'\s+[\"\'][^\"\']*[\"\']$', "", target)
            parsed = urlsplit(html.unescape(target))
            if parsed.scheme or parsed.netloc:
                continue
            target = unquote(parsed.path)
            if target.startswith("/"):
                resolved = routes.get(target)
            else:
                candidate = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
                resolved = candidate if candidate in images else routes.get("/" + slug(candidate.removeprefix("content/")))
                if not resolved and len(by_name[Path(target).name]) == 1:
                    resolved = by_name[Path(target).name][0]
            if resolved:
                entry = {**documents[name], "alt": alt or "", "caption": _caption(text, end, alt or "")}
                if entry not in found[resolved]:
                    found[resolved].append(entry)
    return found, documents


def asset(root: Path, name: str) -> dict:
    body = safe(root, name).read_bytes()
    return {"path": name, "sha256": digest(body), "bytes": len(body),
            "format": Path(name).suffix[1:].upper(), **links(name)}


def collect(root: Path) -> tuple[dict, dict[str, bytes]]:
    registry = json.loads(safe(root, DIRECTORY + "/registry.json").read_text())
    paths = tracked(root)
    images = [name for name in paths if Path(name).suffix.lower() in IMAGE_SUFFIXES
              and name.startswith(("content/", "src/avalanche_research/model/images/", "results/"))
              and not name.startswith(DIRECTORY + "/")]
    for name in images:
        if not safe(root, name).is_file():
            raise ValueError(f"Tracked gallery image is missing: {name}")
    usage, documents = usages(root, paths, images)
    groups = defaultdict(list)
    for name in images:
        groups[str(Path(name).with_suffix(""))].append(name)
    figures = {}
    copies = {}
    for stem, names in sorted(groups.items()):
        names.sort(key=lambda n: (Path(n).suffix.lower() != ".png", n))
        primary = names[0]
        metadata = dict(DEFAULTS)
        for rule in registry.get("rules", []):
            if primary.startswith(rule["prefix"]):
                metadata.update({key: value for key, value in rule.items() if key != "prefix"})
        metadata.update(registry.get("figures", {}).get(stem, {}))
        sources = metadata.pop("sources", [])
        entries = []
        for name in names:
            entry = asset(root, name)
            if not name.startswith("content/"):
                copied = DIRECTORY + "/assets/" + entry["sha256"][:16] + Path(name).suffix
                copies[copied] = safe(root, name).read_bytes()
                entry.update(links(copied))
                entry["published_copy"] = copied
            entries.append(entry)
        identity = entries[0]["sha256"]
        used = [item for name in names for item in usage[name]]
        used = list({item["path"]: item for item in used}.values())
        identities = list(registry.get("legacy_ids_by_sha256", {}).get(identity, []))
        for name in names:
            match = re.search(r"-(f\d+)\.", name, re.IGNORECASE)
            if match and match[1].lower() not in identities:
                identities.append(match[1].lower())
        downloads = entries.copy()
        for suffix in (".csv", ".json", ".pdf", ".html"):
            if stem + suffix in paths:
                downloads.append(asset(root, stem + suffix))
        for candidate in metadata.pop("related_files", []):
            if candidate not in paths:
                raise ValueError(f"Related download is not delivered: {candidate}")
            downloads.append(asset(root, candidate))
        available_records = []
        for filename in ("figure-manifest.json", "figure-sources.json", "explanatory-figure-sources.json", "provenance.json", "export-spec.json"):
            candidate = str(Path(primary).parent / filename)
            if candidate in paths:
                record = json.loads(safe(root, candidate).read_text())
                available_records.append({"path": candidate, **links(candidate)})
                for row in record.get("figures", []):
                    if row.get("file") == Path(primary).name and row.get("render_command"):
                        metadata.setdefault("producing_command", row["render_command"])
                if record.get("generator") in paths:
                    metadata.setdefault("producing_source", record["generator"])
        source_records = []
        if metadata.get("producing_source"):
            sources = [*sources, metadata["producing_source"]]
        for source in dict.fromkeys(sources):
            if source not in paths:
                raise ValueError(f"Classification source is not delivered: {source}")
            body = safe(root, source).read_bytes()
            reference = {"path": source, "sha256": digest(body), "bytes": len(body)}
            if source.startswith("content/"):
                reference.update(links(source, page=source.endswith(".md")))
            else:
                copied = DIRECTORY + "/sources/" + digest(body)[:16] + "-" + Path(source).name + ".txt"
                copies[copied] = body
                reference.update({"published_copy": copied, **links(copied)})
            source_records.append(reference)
            if source.endswith(".json"):
                available_records.append(reference)
        title = metadata.pop("title", None)
        if not title:
            candidate = next((u["alt"] for u in used if len(u["alt"]) > 12 and not u["alt"].endswith(tuple(IMAGE_SUFFIXES))), "")
            title = candidate or Path(stem).name.replace("-", " ").replace("_", " ")
        caption = metadata.pop("caption", used[0]["caption"] if used else "No document caption recorded.")
        figure = {
            "key": "asset-" + identity[:16], "ids": identities, "title": title, **metadata,
            "availability": "Built", "caption": caption,
            "assets": entries, "downloads": downloads, "usages": used,
            "classification_sources": source_records, "source_records": available_records,
            "identity_basis": "Retained gallery ID binding" if identities else "Content SHA-256; no prior gallery ID recorded",
            "metadata_gaps": [],
        }
        # Prefer explicitly classified copies, retaining every artifact and document use.
        if identity in figures:
            existing = figures[identity]
            if (len(existing["classification_sources"]), existing["models"] != ["Unspecified"]) > (len(figure["classification_sources"]), figure["models"] != ["Unspecified"]):
                figure, existing = existing, figure
            for field in ("assets", "downloads", "usages", "classification_sources", "source_records"):
                figure[field] = list({item["path"]: item for item in existing[field] + figure[field]}.values())
            figure["ids"] = sorted(set(existing["ids"] + figure["ids"]))
            for field in ("models", "horizons"):
                values = set(existing[field] + figure[field])
                figure[field] = sorted(values - {"Unspecified"} if len(values) > 1 else values)
        figures[identity] = figure
    for figure in figures.values():
        figure["downloads"] = list({item["sha256"]: item for item in figure["downloads"]}.values())
        gaps = figure["metadata_gaps"]
        for field in ("family", "evidence"):
            if figure[field] == "Unspecified":
                gaps.append(field + " not recorded")
        for field in ("models", "horizons"):
            if figure[field] == ["Unspecified"]:
                gaps.append(field + " not recorded")
        if not figure.get("producing_command"):
            gaps.append("producing command not recorded")
        if not figure["source_records"]:
            gaps.append("figure-specific source receipt not delivered")
        if not figure["usages"]:
            gaps.append("no embedded use found in tracked Markdown")
        figure["usages"].sort(key=lambda item: item["path"])
    manifest = {
        "schema": "avalanche-figure-gallery/v1", "inventory_scope": "Tracked delivered content, model images and results images",
        "registry_sha256": digest(safe(root, DIRECTORY + "/registry.json").read_bytes()),
        "inventory_images": len(images), "figures": sorted(figures.values(), key=lambda f: (f["models"] != ["v0.8.0"], f["title"].casefold(), f["key"])),
        "usage_method": "Embedded Markdown/HTML images and wiki embeds in tracked content; not inferred from links or filenames.",
        "documents": sorted(documents.values(), key=lambda item: item["path"]),
    }
    return manifest, copies


def card(figure: dict) -> str:
    esc = html.escape
    def anchor(item, label):
        return f'<a href="{esc(item["href"], quote=True)}" data-file-href="{esc(item["file_href"], quote=True)}" target="_blank" rel="noopener">{esc(label)}</a>'
    image = figure["assets"][0]
    image_link = anchor(image, "Open full size")
    preview = (f'<a href="{esc(image["href"], quote=True)}" data-file-href="{esc(image["file_href"], quote=True)}" target="_blank" rel="noopener">'
               f'<img src="{esc(image["href"], quote=True)}" data-file-src="{esc(image["file_href"], quote=True)}" loading="lazy" alt="{esc(figure["title"], quote=True)}"></a>')
    downloads = " · ".join(anchor(item, item["format"]) for item in figure["downloads"])
    used = "".join(f'<li>{anchor(item, item["title"])}</li>' for item in figure["usages"])
    references = {item["path"]: item for item in figure["source_records"] + figure["classification_sources"]}
    records = "".join(f'<li>{anchor(item, Path(item["path"]).name)}</li>' for item in references.values())
    command = f'<p>Recorded command</p><pre>{esc(figure["producing_command"])}</pre>' if figure.get("producing_command") else ""
    source = f'<p>Producing source: <code>{esc(figure["producing_source"])}</code></p>' if figure.get("producing_source") else ""
    caption = esc(figure["caption"])
    return (f'<article class="card" data-key="{figure["key"]}"><div class="preview">{preview}</div>'
            f'<div class="body"><p class="eyebrow">{esc(" · ".join(figure["ids"]) or "Delivered asset")} · {esc(figure["family"])}</p>'
            f'<h2>{esc(figure["title"])}</h2><p class="scope">{esc(", ".join(figure["models"]))} · {esc(figure["evidence"])}</p>'
            f'<p>{caption}</p><p class="actions">{image_link} · {downloads}</p>'
            f'<details><summary>Sources and use</summary><p>Horizon: {esc(", ".join(figure["horizons"]))}. Availability: Built.</p>'
            f'<p>{esc(figure["classification_basis"])}</p><ul>{records}</ul>{command}{source}'
            f'<h3>Used in</h3><ul>{used or "<li>No embedded use found.</li>"}</ul>'
            f'<p class="gaps">{esc(". ".join(figure["metadata_gaps"]))}.</p>'
            f'<p class="hash">SHA-256: {esc(image["sha256"])}</p></details></div></article>')


def outputs(root: Path) -> dict[str, bytes]:
    manifest, copies = collect(root)
    encoded = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    template = safe(root, DIRECTORY + "/gallery.template.html").read_text()
    payload = json.dumps(manifest, ensure_ascii=False).replace("<", "\\u003c")
    generated = template.replace("<!-- GALLERY_CARDS -->", "\n".join(card(f) for f in manifest["figures"]))
    generated = generated.replace("/* GALLERY_DATA */", payload)
    copies[DIRECTORY + "/manifest.json"] = encoded.encode()
    copies[DIRECTORY + "/gallery.html"] = generated.encode()
    return copies


def run(root: Path, *, check: bool = False) -> dict:
    generated = outputs(root)
    stale = []
    for name, body in generated.items():
        path = safe(root, name)
        if check:
            if not path.is_file() or path.read_bytes() != body:
                stale.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
    if stale:
        raise ValueError("Gallery is stale. Run python scripts/figure_gallery.py build: " + ", ".join(stale))
    manifest = json.loads(generated[DIRECTORY + "/manifest.json"])
    return {"status": "pass", "images": manifest["inventory_images"], "figures": len(manifest["figures"]), "outputs": sorted(generated)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.project.resolve(), check=args.command == "check"), sort_keys=True))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"FAIL | figure gallery | {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
