"""The lockbox token: the only key that lets the model fit, select or tune on rows from the boundary on.

The held-back period starts at ``clock.LOCKBOX_START``. Until the pre-registered unseal, no fit, feature, variable or
specification choice may use a row from that instant on. A model entry point that fits, selects or tunes calls
``require`` with the latest instant its rows reach and the token it was given, and refuses a lockbox row without a valid
token. General loaders stay open: people and descriptive work may read every row.

``issue`` is the only way to build a token, and it builds one only after the unseal is on record: the annotated tag
``lockbox-unsealed`` exists on the remote. So any code holding a token runs after the lock, and any lockbox score
counts as the unseal. This stops accidents, not intent.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .clock import LOCKBOX_START, as_utc
from .errors import ModelError

TAG = "lockbox-unsealed"
_ISSUER = object()


@dataclass(frozen=True)
class Unseal:
    """Proof that the unseal tag was on the remote when the token was issued."""

    tag_object: str
    issued_by: object

    def __post_init__(self) -> None:
        if self.issued_by is not _ISSUER:
            raise ModelError("an Unseal token is built only by lockbox.issue, after the unseal tag is on the remote")


def remote_tag(repo: Path, remote: str = "origin", tag: str = TAG) -> str | None:
    """The tag's object id on the remote, or None when the remote has no such tag."""
    listed = subprocess.run(["git", "-C", str(repo), "ls-remote", "--tags", remote, f"refs/tags/{tag}"], capture_output=True,
                            text=True, check=True).stdout.split()
    return listed[0] if listed else None


def issue(repo: Path, remote: str = "origin", tag: str = TAG) -> Unseal:
    found = remote_tag(repo, remote, tag)
    if found is None:
        raise ModelError(f"no {tag} tag on {remote}: the unseal is not on record, so no lockbox token is issued")
    return Unseal(found, _ISSUER)


def require(latest: datetime, token: Unseal | None) -> None:
    """Refuse rows that reach the boundary unless a token built by ``issue`` is given. A token is an accident guard: it
    proves the unseal tag was on the remote when issued, not that the holder is the only scorer."""
    valid = isinstance(token, Unseal) and getattr(token, "issued_by", None) is _ISSUER and bool(getattr(token, "tag_object", ""))
    if as_utc(latest) >= LOCKBOX_START and not valid:
        raise ModelError(f"rows reach {latest}, at or after the lockbox boundary {LOCKBOX_START}, and no Unseal token was given")
