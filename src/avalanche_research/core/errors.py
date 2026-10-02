"""The package's two error types."""

from __future__ import annotations


class DataError(RuntimeError):
    """The requested data operation could not complete safely."""


class ModelError(ValueError):
    """A protocol rule was asked to evaluate an input outside its domain."""
