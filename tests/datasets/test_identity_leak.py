"""The identity truncation test on real data: groups built as of each origin before a cut are identical whether the stake
log ends at the cut or at the lockbox boundary, and a leaky control, grouping by each node's latest addresses, differs.

A node's grouping is compared as the set of nodes in its group, the comparison of the version-leak check. Skips when no
seamed validator stakes run is built in this checkout.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from avalanche_research import datasets
from avalanche_research.catalog import DataError
from avalanche_research.core.clock import LOCKBOX_START
from avalanche_research.datasets.derived import identity

CUT = datetime(2024, 6, 1, tzinfo=UTC)
ORIGINS = ["2022-07-01", "2022-10-01", "2022-10-18", "2023-01-01", "2023-04-01", "2023-04-25", "2023-07-01", "2023-10-01",
           "2024-01-01", "2024-03-06", "2024-04-01"]


def instant(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC) + timedelta(days=1, seconds=-1)


def members(table: pd.DataFrame) -> dict[str, frozenset[str]]:
    nodes = table.groupby("group_id")["node_id"].agg(frozenset)
    return dict(zip(table["node_id"], table["group_id"].map(nodes), strict=True))


@pytest.fixture(scope="module")
def builds():
    try:
        path = str(datasets.parquet_path("derived.seamed-validator-stakes"))
    except (DataError, StopIteration, FileNotFoundError):
        pytest.skip("no built run of derived.seamed-validator-stakes in this checkout")
    edges = identity.edges(path)
    full = edges[edges["evidence_at"] < identity.utc_naive(LOCKBOX_START)]
    return full, full[full["evidence_at"] < identity.utc_naive(CUT)], identity.dated_names()


def test_origins_are_before_the_cut():
    assert all(instant(text) < CUT for text in ORIGINS)


@pytest.mark.parametrize("origin", ORIGINS)
def test_groups_at_an_origin_are_identical_with_history_cut(builds, origin):
    full, cut, names = builds
    at_full, at_cut = identity.groups(full, instant(origin), names), identity.groups(cut, instant(origin), names)
    pd.testing.assert_frame_equal(at_full, at_cut)


def test_grouping_by_the_latest_addresses_differs(builds):
    full, cut, _ = builds
    latest_full = members(identity.groups(full, LOCKBOX_START - timedelta(seconds=1)))
    latest_cut = members(identity.groups(cut, CUT - timedelta(seconds=1)))
    changed = {}
    for origin in ORIGINS:
        known = identity.groups(cut, instant(origin))["node_id"]
        changed[origin] = sum(latest_full[node] & set(known) != latest_cut[node] & set(known) for node in known)
    assert all(count > 0 for count in changed.values()), changed
