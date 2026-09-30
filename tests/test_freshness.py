"""The freshness monitor's rule, with fixed probes and a fixed clock."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from avalanche_research import freshness
from avalanche_research.catalog import DataError

CLOCK = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def test_stale_fresh_and_unreadable_sources():
    result = freshness.measure({
        "stalled share": lambda: datetime(2026, 9, 22, 8, 35, 40, tzinfo=UTC),
        "live node": lambda: datetime(2026, 9, 29, 11, 59, tzinfo=UTC),
        "edge": lambda: datetime(2026, 9, 28, 0, 0, tzinfo=UTC),
        "down": lambda: DataError("request failed"),
    }, clock=CLOCK)
    assert result["status"] == "attention"
    assert [(row["source"], row["status"], row["age_hours"]) for row in result["sources"]] == [
        ("stalled share", "stale", 171.4), ("live node", "fresh", 0.0), ("edge", "fresh", 36.0), ("down", "error", None),
    ]


def test_a_known_stop_passes_until_a_new_stop():
    known = {"share": ("2026-09-22T08:35:40Z", "stopped")}
    stopped = lambda: datetime(2026, 9, 22, 8, 35, 40, tzinfo=UTC)
    result = freshness.measure({"share": stopped}, clock=CLOCK, known=known)
    assert result["status"] == "pass" and result["sources"][0]["status"] == "known stale"
    # A newer record that is again stale is a new stop, and so is a source that has stopped without being known.
    later = lambda: datetime(2026, 9, 25, tzinfo=UTC)
    assert freshness.measure({"share": later}, clock=CLOCK, known=known)["status"] == "attention"
    assert freshness.measure({"other": stopped}, clock=CLOCK, known=known)["status"] == "attention"


def test_all_fresh_passes():
    assert freshness.measure({"node": lambda: CLOCK}, clock=CLOCK)["status"] == "pass"


def test_a_daily_metrics_point_counts_from_the_end_of_its_day():
    body = json.dumps({"results": [{"value": 1, "timestamp": 1790294400}, {"value": 2, "timestamp": 1790208000}]}).encode()
    newest = freshness.metrics_point("https://metrics.example/x")(10, request=lambda url, timeout: (body, {}))
    assert newest == datetime(2026, 9, 26, tzinfo=UTC)


def test_p_chain_head_reads_the_head_block_time():
    answers = iter([{"result": {"height": "7"}}, {"result": {"block": {"time": 1790683200}}}])
    newest = freshness.p_chain_head(10, request=lambda url, timeout, body_json=None: (json.dumps(next(answers)).encode(), {}))
    assert newest == datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
