"""The current time as receipts record it, instants read in UTC, and the lockbox boundary."""

from __future__ import annotations

from datetime import UTC, datetime

# Granite's activation. Data from this instant on is held back until the pre-registered unseal, so every reader that
# can return a later row checks against this one constant.
LOCKBOX_START = datetime(2025, 11, 19, 16, tzinfo=UTC)
# The first calendar day the lockbox touches, for daily series.
LOCKBOX_FIRST_DAY = LOCKBOX_START.date()


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
