"""Named operator events: every row names known attributions, dates in UTC, and a forecast use that follows its evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVENTS = json.loads((ROOT / "data" / "operator-events.json").read_text())["events"]
ATTRIBUTIONS = {row["attribution_id"]: row for row in json.loads((ROOT / "data" / "operator-attributions.json").read_text())["attributions"]}
WHEN = re.compile(r"^\d{4}-\d{2}(-\d{2}(T\d{2}:\d{2}:\d{2}Z)?)?$")


def test_event_ids_are_unique_and_name_known_attributions_of_their_subject():
    assert len({event["event_id"] for event in EVENTS}) == len(EVENTS)
    for event in EVENTS:
        assert event["attributions"] and all(ATTRIBUTIONS[code]["subject"] == event["subject"] for code in event["attributions"])


def test_dates_are_utc_and_evidence_never_precedes_a_known_instant():
    for event in EVENTS:
        for field in ("happened_at", "evidence_public_at"):
            assert event[field] is None or WHEN.match(event[field]), (event["event_id"], field)
        if event["evidence_public_at"] and event["happened_at"] and len(event["happened_at"]) == len(event["evidence_public_at"]) == 20:
            assert event["evidence_public_at"] >= event["happened_at"]


def test_only_events_with_public_evidence_are_schedulable():
    for event in EVENTS:
        assert event["forecast_use"] == ("schedulable" if event["evidence_public_at"] else "record-only"), event["event_id"]
        assert event["evidence_note"] and (event["evidence"] or event["forecast_use"] == "record-only")
