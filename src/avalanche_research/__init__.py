"""Avalanche Phase II research tools."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("avalanche-phase-ii-research")
except PackageNotFoundError:  # imported from a source tree that is not installed
    __version__ = "0+source"
