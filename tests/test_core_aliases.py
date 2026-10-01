"""An old import path, after its module moves, is the new module itself (gate LG6)."""

from __future__ import annotations

import importlib
import sys
import textwrap

import pytest


@pytest.fixture
def package(tmp_path, monkeypatch):
    root = tmp_path / "aliaspkg"
    root.mkdir()
    (root / "__init__.py").write_text("")
    (root / "new.py").write_text(textwrap.dedent('''
        LIMIT = 3

        def _private():
            return LIMIT

        def public():
            return _private()
    '''))
    (root / "old.py").write_text(textwrap.dedent('''
        from avalanche_research.core.aliases import alias
        alias(__name__, "aliaspkg.new")
    '''))
    monkeypatch.syspath_prepend(str(tmp_path))
    yield "aliaspkg"
    for name in [n for n in sys.modules if n == "aliaspkg" or n.startswith("aliaspkg.")]:
        del sys.modules[name]


def test_the_old_path_is_the_new_module(package):
    new = importlib.import_module(f"{package}.new")
    old = importlib.import_module(f"{package}.old")
    assert old is new
    from aliaspkg import old as imported
    assert imported is new and sys.modules[f"{package}.old"] is new
    assert old._private() == 3


def test_patching_through_the_old_path_reaches_the_new_module(package, monkeypatch):
    new = importlib.import_module(f"{package}.new")
    old = importlib.import_module(f"{package}.old")
    monkeypatch.setattr(old, "LIMIT", 7)
    assert new.public() == 7
