"""The command line: every command's help, the model group's option help, the released model as the run default, and
what --version prints."""

from __future__ import annotations

import re
import subprocess

import click
from click.testing import CliRunner

from avalanche_research import __version__, cli
from avalanche_research.model import MODEL_VERSION, RELEASED_MODEL


def command_paths(group: click.Group, prefix: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], click.Command]]:
    """Every command under ``group``, groups included, with the words that reach it."""
    found = []
    for name, command in group.commands.items():
        path = (*prefix, name)
        found.append((path, command))
        if isinstance(command, click.Group):
            found.extend(command_paths(command, path))
    return found


def test_the_released_model_is_a_registered_variant_of_the_model_version():
    from avalanche_research.model.variants import VARIANTS

    assert RELEASED_MODEL in VARIANTS
    assert RELEASED_MODEL == f"v{MODEL_VERSION}"


def test_every_command_shows_its_help(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths = command_paths(cli.cli)
    assert ("model", "run") in {path for path, _ in paths} and ("data", "fetch") in {path for path, _ in paths}
    for path in [(), *(path for path, _ in paths)]:
        result = CliRunner().invoke(cli.cli, [*path, "--help"])
        assert result.exit_code == 0, (path, result.output)
        assert "Usage:" in result.output


def test_every_option_of_the_model_commands_has_help():
    missing = [(path, param.name) for path, command in command_paths(cli.cli.commands["model"], ("model",))
               for param in command.params if isinstance(param, click.Option) and not (param.help or "").strip()]
    assert missing == []


def test_the_run_command_runs_the_released_model_by_default():
    option = next(param for param in cli.cli.commands["model"].commands["run"].params if param.name == "model_name")
    assert option.default == RELEASED_MODEL


def test_version_names_the_package_the_released_model_and_the_commit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli.cli, ["--version"])
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0] == f"avalanche-phase-ii-research {__version__}"
    assert lines[1] == f"released model {RELEASED_MODEL} (model version {MODEL_VERSION})"
    assert re.fullmatch(r"code commit ([0-9a-f]{40}( \(modified\))?|unknown)", lines[2])


def test_the_commit_is_unknown_outside_a_checkout(monkeypatch):
    def no_checkout(*args, **kwargs):
        raise subprocess.CalledProcessError(128, args[0])

    monkeypatch.setattr(cli.subprocess, "run", no_checkout)
    assert cli.code_commit() == "unknown"
    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("git")))
    assert cli.code_commit() == "unknown"
