"""Build or check CLI and Python-module references without invoking commands.

uv run --frozen python scripts/manual_reference.py build
uv run --frozen python scripts/manual_reference.py check

Click supplies command help and parameters. AST parsing supplies module contents.
Only reference pages and their inventory JSON are written. Provider and model
callbacks are never invoked. Review command-effect notes when implementations change.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
from pathlib import Path

import click

DIRECTORY = Path("content/Phase II/Wiki/Manual")
SOURCE_URL = "https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/"


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def plain(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return str(value)


def command_inventory(command: click.Command, name: str = "avalanche", parent=None) -> list[dict]:
    context = click.Context(command, info_name=name.split()[-1], parent=parent, terminal_width=88)
    callback = command.callback
    params = []
    for parameter in command.get_params(context):
        item = plain(parameter.to_info_dict())
        default = parameter.get_default(context)
        item["effective_default"] = None if str(default) == "Sentinel.UNSET" else plain(default)
        params.append(item)
    record = {"command": name, "group": isinstance(command, click.Group),
              "help": command.get_help(context), "parameters": params,
              "callback": f"{callback.__module__}.{callback.__qualname__}" if callback else None}
    result = [record]
    if isinstance(command, click.Group):
        for child in command.list_commands(context):
            result.extend(command_inventory(command.get_command(context, child), name + " " + child, context))
    return result


def module_inventory(root: Path) -> list[dict]:
    result = []
    package = root / "src/avalanche_research"
    for path in sorted(package.rglob("*.py")):
        body = path.read_bytes()
        tree = ast.parse(body, filename=path.name)
        doc = ast.get_docstring(tree) or ""
        relative = path.relative_to(root).as_posix()
        symbols = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                summary = (ast.get_docstring(node) or "").split("\n\n", 1)[0].replace("\n", " ")
                symbols.append({"name": node.name, "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                                "line": node.lineno, "summary": summary})
        imports = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append({"module": "." * node.level + node.module,
                                "names": [n.name for n in node.names]})
        result.append({"repository_path": relative, "sha256": digest(body),
                       "summary": doc.split("\n\n", 1)[0].replace("\n", " "),
                       "symbols": symbols, "imports": imports})
    return result


def front(title: str, kind: str = "reference") -> str:
    return f'---\ntitle: "{title}"\nkind: {kind}\nreader: "Researchers and engineers using the staking repository"\nquestion: "What does the checked source implement?"\n---\n\n'


def paragraph(value: str) -> str:
    return value.replace("|", "\\|").strip()


def build(root: Path) -> dict[Path, bytes]:
    from avalanche_research.cli import MODULES, cli

    notes = json.loads((root / DIRECTORY / "command-notes.json").read_text())
    commands = command_inventory(cli)
    leaves = {c["command"] for c in commands if not c["group"]}
    if set(notes) != leaves:
        raise ValueError(f"Review command-effect notes: missing {sorted(leaves - set(notes))}, extra {sorted(set(notes) - leaves)}")
    modules = module_inventory(root)
    dispatch = [{"dataset_id": key, "implementation": module.__name__}
                for key, module in sorted(MODULES.items())]
    source_hashes = {p: digest((root / p).read_bytes()) for p in (
        "src/avalanche_research/cli.py", "src/avalanche_research/research.py", "data/data-catalog.json",
        "content/Phase II/Wiki/Manual/command-notes.json")}
    inventory = {"schema": "research-manual-reference/v1", "source_hashes": source_hashes,
                 "commands": commands, "dataset_dispatch": dispatch, "modules": modules}
    cli_text = front("Complete CLI reference")
    cli_text += (f"The installed Click definitions supply every command, argument, option and default below. "
                 f"There are {len(leaves)} executable commands and {len(commands)-len(leaves)} groups including the root. "
                 "Help inspection invokes no command callbacks. Effects and input requirements are reviewed annotations. "
                 "The [CLI walkthrough](/Phase-II/Wiki/Manual/usage) explains the working sequence.\n\n")
    for command in commands:
        cli_text += "## " + command["command"] + "\n\n"
        if command["command"] in notes:
            for key, value in notes[command["command"]].items():
                cli_text += key.capitalize() + ": " + value + "\n\n"
        cli_text += "```text\n" + command["help"] + "\n```\n\n"
    cli_text += "## Structured inventory\n\nThe [reference inventory](/Phase-II/Wiki/Manual/reference-inventory.json) retains typed parameter metadata, including repeatability and required arguments, plus source hashes. Regenerate with `uv run --frozen python scripts/manual_reference.py build`; use `check` to detect changes.\n"
    module_text = front("Complete Python module reference")
    module_text += (f"The package contains {len(modules)} Python files. This reference parses source without importing "
                    "the modules being inventoried. Each entry gives the module's source description and its defined "
                    "classes and functions. Imported compatibility names appear separately. A source description describes "
                    "code, not scientific acceptance. The [architecture](/Phase-II/Wiki/Manual/architecture) and "
                    "[component explanations](/Phase-II/Wiki/Manual/components) identify the released execution path and development alternatives.\n\n")
    for module in modules:
        module_text += "## " + module["repository_path"].removeprefix("src/avalanche_research/") + "\n\n"
        module_text += (paragraph(module["summary"]) or "Package initialization or compatibility import surface.") + "\n\n"
        module_text += "[Source](" + SOURCE_URL + module["repository_path"] + ")\n\n"
        if module["symbols"]:
            module_text += "| Component | Purpose from source |\n| --- | --- |\n"
            for symbol in module["symbols"]:
                description = paragraph(symbol["summary"]) or "Implementation helper. Open its source for the algorithm."
                module_text += f"| `{symbol['name']}` ({symbol['kind']}) | {description} |\n"
            module_text += "\n"
        elif module["imports"]:
            names = ["`" + n + "`" for item in module["imports"] for n in item["names"]]
            module_text += "Imported components: " + ", ".join(names) + ".\n\n"
    datasets_text = front("Dataset dispatch reference")
    datasets_text += (f"The CLI dispatches {len(dispatch)} dataset identifiers to the implementations below. "
                      "These identifiers describe supported contracts, not local data availability. "
                      "Use `avalanche data describe ID` for its catalog description and `avalanche data runs ID` for installed runs. "
                      "Provider-specific parameters belong to the corresponding source module.\n\n")
    datasets_text += "| Dataset identifier | Implementation |\n| --- | --- |\n"
    for row in dispatch:
        datasets_text += f"| `{row['dataset_id']}` | `{row['implementation']}` |\n"
    return {DIRECTORY / "cli.md": cli_text.encode(), DIRECTORY / "modules.md": (module_text.rstrip() + "\n").encode(),
            DIRECTORY / "datasets.md": datasets_text.encode(),
            DIRECTORY / "reference-inventory.json": (json.dumps(inventory, indent=2, ensure_ascii=False) + "\n").encode()}


def run(root: Path, check: bool = False) -> dict:
    outputs = build(root)
    changed = []
    for name, body in outputs.items():
        path = root / name
        if check:
            if not path.is_file() or path.read_bytes() != body:
                changed.append(str(name))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
    if changed:
        raise ValueError("Reference differs from source: " + ", ".join(changed))
    return {"status": "pass", "outputs": len(outputs)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.project.resolve(), args.command == "check")))
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
