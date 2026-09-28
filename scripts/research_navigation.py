#!/usr/bin/env python3
"""Build and validate collection navigation from one normalized registry."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "research-navigation.json"
ID = re.compile(r"^[a-z][a-z0-9:_-]+$")
SOURCE_TYPES = {
    "article": "Article",
    "video": "Video",
    "model_artifact": "Model artifact",
}
SOURCE_PAGE_TITLES = {
    "article": "Source Article",
    "video": "Source Video",
    "model_artifact": "Source Model Artifact",
}


class RegistryError(ValueError):
    pass


def load(path: Path = REGISTRY) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RegistryError("registry must be a JSON object")
    return value


def _records(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise RegistryError(f"{name} must be an array of objects")
    return value


def _unique(records: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        record_id = record.get("id")
        if not isinstance(record_id, str) or not ID.fullmatch(record_id):
            raise RegistryError(f"{name} has an invalid id: {record_id!r}")
        if record_id in result:
            raise RegistryError(f"duplicate {name} id: {record_id}")
        result[record_id] = record
    return result


def _page(root: Path, value: Any, field: str) -> Path:
    if not isinstance(value, str) or not value.startswith("content/"):
        raise RegistryError(f"{field} must be a content-relative path")
    path = (root / value).resolve()
    content = (root / "content").resolve()
    if path != content and content not in path.parents:
        raise RegistryError(f"{field} escapes content: {value}")
    return path


def _title(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', text, re.MULTILINE)
    return match.group(1) if match else None


def _route(root: Path, page: Path) -> str:
    relative = page.relative_to(root / "content")
    parts = list(relative.parts)
    trailing = parts[-1] == "index.md"
    if trailing:
        parts.pop()
    else:
        parts[-1] = Path(parts[-1]).stem
    if parts and parts[0] in {"Phase I", "Phase II"}:
        parts[0] = parts[0].replace(" ", "-")
    route = "/" + "/".join(quote(part, safe="-") for part in parts)
    return route + "/" if trailing else route


def _relative_link(source: Path, target: Path) -> str:
    relative = Path(os.path.relpath(target, source.parent))
    parts = list(relative.parts)
    trailing = parts[-1] == "index.md"
    if trailing:
        parts.pop()
    else:
        parts[-1] = Path(parts[-1]).stem
    link = "/".join(quote(part, safe=".-") for part in parts)
    return link + "/" if trailing else link


def validate(registry: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    if registry.get("schema_version") != "research-navigation/v3":
        raise RegistryError("unsupported schema_version")
    sources = _unique(_records(registry.get("sources"), "sources"), "source")
    collections = _unique(_records(registry.get("collections"), "collections"), "collection")
    studies = _unique(_records(registry.get("studies"), "studies"), "study")

    for source in sources.values():
        if not isinstance(source.get("title"), str) or not source["title"].strip():
            raise RegistryError(f"{source['id']}: title is required")
        source_type = source.get("source_type")
        if source_type not in SOURCE_TYPES:
            raise RegistryError(f"{source['id']}: unsupported source_type {source_type!r}")
        url = source.get("canonical_url")
        if source_type == "model_artifact" and url is None:
            pass
        else:
            parsed = urlparse(url) if isinstance(url, str) else None
            if not parsed or parsed.scheme != "https" or not parsed.netloc:
                raise RegistryError(f"{source['id']}: canonical_url must be HTTPS")
        if source.get("local_page") is not None:
            page = _page(root, source["local_page"], f"{source['id']}.local_page")
            if not page.is_file():
                raise RegistryError(f"{source['id']}: missing local page")
            if _title(page) != SOURCE_PAGE_TITLES[source_type]:
                raise RegistryError(f"{source['id']}: source page title drift")

    for collection in collections.values():
        if not isinstance(collection.get("title"), str) or not collection["title"].strip():
            raise RegistryError(f"{collection['id']}: title is required")
        member_ids = collection.get("source_ids")
        if not isinstance(member_ids, list) or len(member_ids) != len(set(member_ids)):
            raise RegistryError(f"{collection['id']}: source_ids must be a unique array")
        missing = [source_id for source_id in member_ids if source_id not in sources]
        if missing:
            raise RegistryError(f"{collection['id']}: missing sources {missing}")
        _page(root, collection.get("index"), f"{collection['id']}.index")

    for study in studies.values():
        source_id = study.get("source_id")
        collection_id = study.get("collection_id")
        if source_id not in sources:
            raise RegistryError(f"{study['id']}: unknown source {source_id}")
        if collection_id not in collections:
            raise RegistryError(f"{study['id']}: unknown collection {collection_id}")
        if source_id not in collections[collection_id]["source_ids"]:
            raise RegistryError(f"{study['id']}: source is not a collection member")
        page = _page(root, study.get("page"), f"{study['id']}.page")
        source_page = _page(root, sources[source_id]["local_page"], f"{source_id}.local_page")
        if page != source_page.parent / "index.md":
            raise RegistryError(f"{study['id']}: study page must be the source package index")
        if page.is_file() and _title(page) != sources[source_id]["title"]:
            raise RegistryError(f"{study['id']}: study page title drift")
        for component in _records(study.get("components"), f"{study['id']}.components"):
            component_page = _page(root, component.get("page"), f"{study['id']}.component.page")
            if not component_page.is_file() or _title(component_page) != component.get("title"):
                raise RegistryError(f"{study['id']}: missing component or title drift")

    return {"sources": sources, "collections": collections, "studies": studies}


def render(registry: dict[str, Any], root: Path = ROOT) -> dict[Path, str]:
    resolved = validate(registry, root)
    sources = resolved["sources"]
    studies = resolved["studies"]
    studies_by_source = {study["source_id"]: study for study in studies.values()}
    outputs: dict[Path, str] = {}
    for collection in resolved["collections"].values():
        collection_index = _page(root, collection["index"], "index")
        collection_items = []
        for source_id in collection["source_ids"]:
            source = sources[source_id]
            source_page = _page(root, source["local_page"], "local_page")
            package_index = source_page.parent / "index.md"
            source_type = SOURCE_TYPES[source["source_type"]]
            collection_items.append(
                f"- [{source['title']}]({_relative_link(collection_index, package_index)}) · {source_type}"
            )
            study = studies_by_source.get(source_id)
            component_items = [
                f"- [{SOURCE_PAGE_TITLES[source['source_type']]}]({_relative_link(package_index, source_page)})"
            ]
            if study:
                component_items.extend(
                    f"- [{component['title']}]({_relative_link(package_index, _page(root, component['page'], 'component.page'))})"
                    for component in study["components"]
                )
                description = "The source, and the research built on it as each part is delivered."
            else:
                description = "Source material admitted to the Essential Readings collection."
            outputs[package_index] = (
                "---\n"
                f"title: \"{source['title']}\"\n"
                f"description: \"{description}\"\n"
                f"source_id: \"{source_id}\"\n"
                "---\n\n"
                f"{description}\n\n"
                "## Contents\n\n"
                + "\n".join(component_items)
                + "\n"
            )
        outputs[collection_index] = (
            "---\n"
            f"title: {collection['title']}\n"
            "description: The Foundation articles and sources the Phase II research reproduces and builds on.\n"
            "---\n\n"
            + "\n".join(collection_items)
            + "\n"
        )
    return outputs


def _write(path: Path, text: str) -> bool:
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def result(command: str, root: Path = ROOT, registry_path: Path = REGISTRY) -> dict[str, Any]:
    registry = load(registry_path)
    outputs = render(registry, root)
    stale = [path.relative_to(root).as_posix() for path, text in outputs.items() if not path.is_file() or path.read_text(encoding="utf-8") != text]
    if command == "build":
        changed = [path.relative_to(root).as_posix() for path, text in outputs.items() if _write(path, text)]
        stale = []
    else:
        changed = []
    resolved = validate(registry, root)
    coverage = []
    for collection in resolved["collections"].values():
        members = collection["source_ids"]
        coverage.append(
            {
                "collection_id": collection["id"],
                "members": len(members),
                "local_editions": sum(bool(resolved["sources"][item].get("local_page")) for item in members),
                "studies": sum(study["collection_id"] == collection["id"] for study in resolved["studies"].values()),
            }
        )
    return {"status": "pass" if not stale else "fail", "stale_outputs": stale, "changed": changed, "coverage": coverage}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check", "status"), nargs="?", default="check")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    args = parser.parse_args()
    try:
        report = result(args.command, args.root.resolve(), args.registry.resolve())
    except (OSError, json.JSONDecodeError, RegistryError) as error:
        report = {"status": "fail", "error": str(error)}
    print(json.dumps(report, indent=2))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
