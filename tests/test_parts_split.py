"""The behaviour blocks moved from one file into a module per part without changing any result.

The expected hashes were recorded on the single-file code before the move. A small lifecycle that uses every part,
with blocks fitted on synthetic events, must give the same specification hash and the same simulated table. The fitted
values are rounded to ten decimals before the lifecycle uses them, since the renewal fit's last digits differ between
processors, so the hashes are the same on every machine.

Three settings were added after the recording: the fitted menu and the outside yield with its fitted level, the point
the behaviour responses count from. They change the specification hash, so its expected value is the one the recorded
code gives with those settings added at their defaults. The table carries every setting as a column and the
specification hash, so the table is compared with those three columns dropped and the hash it was recorded with.
"""

import hashlib
import importlib

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cadCAD")
pytest.importorskip("scipy")

from avalanche_research.model import fitted_blocks
from avalanche_research.model.engine import run
from avalanche_research.model.fitted_blocks import (
    AVAX,
    Arrivals,
    RenewalLogit,
    ReturnHazard,
)
from avalanche_research.model.fitted_lifecycle import FittedLifecycle

EXPECTED_SPECIFICATION_HASH = "f223799dee2fe217"
RECORDED_SPECIFICATION_HASH = "becbdac26d612e50"
EXPECTED_TABLE_SHA256 = "05a448d503bf035ed222ad19d65c7d2b23bbf8974dafc8b51c25824d6c7373e0"

# Every name the single-file module offered, and the module of the package that now defines it. None is a name the
# module imported from elsewhere and still offers.
NAMES = {
    "AVAX": "base", "RENEWAL_DAYS": "base", "RETURN_DAYS": "base", "DURATION_EDGES": "base",
    "BehaviourBlock": "base", "_outcomes": "base", "behavioural": "base",
    "TENURE_BINS": "renewal", "RENEWAL_STAKE_EDGES": "renewal", "RENEWAL_TERMS": "renewal", "NODE_PRIOR_GRID": "renewal",
    "tenure_bin": "renewal", "renewal_design": "renewal", "_coefficient": "renewal", "RenewalLogit": "renewal",
    "_newton": "renewal",
    "Arrivals": "arrivals", "_negative_binomial_log_prob": "arrivals",
    "RETURN_STAKE_EDGES": "returns", "RETURN_DAY_EDGES": "returns", "RETURN_CELLS": "returns",
    "return_cell": "returns", "_hazard": "returns", "ReturnHazard": "returns",
    "MOVE_STAKE_EDGES": "continuation", "Continuation": "continuation",
    "Mapping": None, "annotations": None, "lgamma": None, "np": None, "optimize": None, "special": None, "stats": None,
}


def rounded(block):
    """The block with every fitted value rounded to ten decimals."""
    values = {name: round(float(value), 10) for name, value in block.param.values().items() if name != "name"}
    provenance = {name: {"source": "fitted", "evidence": "synthetic", "value": value} for name, value in values.items()}
    return type(block)(provenance=provenance, **values)


def fitted_blocks_on_synthetic_events():
    rng = np.random.default_rng(11)
    n = 3_000
    done = rng.integers(0, 12, n)
    inputs = {
        "done": done,
        "after_return": rng.random(n) < 0.2,
        "days": rng.choice([14, 30, 60, 180], n),
        "stake_navax": rng.choice([2_000, 50_000, 500_000, 2_000_000], n) * AVAX,
        "returns": np.minimum(done, rng.integers(0, 3, n)),
    }
    renewal = RenewalLogit.fit(inputs, rng.random(n) < 0.8, "synthetic")
    large = RenewalLogit.fit({k: v for k, v in inputs.items() if k != "returns"}, rng.random(n) < 0.6, "synthetic large")
    arrivals = Arrivals.fit(rng.negative_binomial(1.5, 1.5 / 4.5, size=400), "synthetic")
    days_out = rng.integers(1, 500, 2_000)
    returns = ReturnHazard.fit(rng.choice([2_000, 50_000, 500_000], 2_000) * AVAX, days_out, rng.random(2_000) < 0.5, "synthetic")
    return tuple(rounded(block) for block in (renewal, large, arrivals, returns))


def small_lifecycle():
    renewal, large, arrivals, returns = fitted_blocks_on_synthetic_events()
    initial = pd.DataFrame({
        "stakes": np.array([2, 10, 20, 30, 40, 150, 1_200, 2_500]) * 1_000 * AVAX,
        "days_left": [1, 2, 3, 5, 8, 13, 21, 60], "done": [0, 1, 2, 3, 5, 8, 0, 12],
        "after_return": [False, True, False, False, True, False, False, True], "days": [14, 30, 60, 14, 180, 30, 60, 14],
        "handed_on": [False] * 7 + [True], "returns": [0, 1, 0, 1, 2, 0, 0, 3],
    })
    out = pd.DataFrame({"out_stakes": np.array([2, 50, 400, 2_000]) * 1_000 * AVAX, "out_days": [3, 20, 100, 300],
                        "out_done": [1, 2, 4, 7], "out_last_days": [14, 30, 60, 180], "out_returns": [0, 1, 1, 2]})
    scheduled = pd.DataFrame({"start_day": [2, 9], "stakes": [12_000 * AVAX, 2_600_000 * AVAX], "days": [30, 14],
                              "done": [13, 1], "after_return": [False, False], "returns": [3, 0]})
    moves = pd.DataFrame({
        "previous_days": [14, 14, 30, 60, 180, 14, 30], "next_days": [7, 14, 30, 60, 90, 180, 21],
        "previous_stake_navax": np.array([2, 10, 50, 400, 2_000, 10, 2_500]) * 1_000 * AVAX,
        "next_stake_navax": np.array([2, 12, 45, 500, 1_900, 20, 3_100]) * 1_000 * AVAX,
    })
    first = pd.DataFrame({"days": [14, 30, 60], "stake_navax": np.array([2, 7, 100]) * 1_000 * AVAX})
    return FittedLifecycle(
        initial=initial, out_of_set=out, scheduled=scheduled, moves=moves, first_commitments=first,
        renewal=renewal, renewal_large=large, large_above_avax=1_000_000.0, arrivals=arrivals, returns=returns,
        seed=7, timesteps=40, runs=2, inputs_source="synthetic",
    )


# Settings added after the tables were recorded, at their defaults in every test here.
ADDED_SETTINGS = ["fitted_menu", "outside_yield_pp", "fitted_outside_yield_pp"]


# The golden tables were recorded while MODEL_VERSION read 0.7.0. The version names a release, not behaviour.
RECORDED_MODEL_VERSION = "0.7.0"


def as_recorded(table: pd.DataFrame, specification_hash: str) -> pd.DataFrame:
    """The table as the recorded code wrote it: without the settings added since, with its specification hash and the
    model version it was recorded under."""
    return table.drop(columns=ADDED_SETTINGS).assign(specification=specification_hash, model_version=RECORDED_MODEL_VERSION)


def table_sha256(table: pd.DataFrame) -> str:
    ordered = table.sort_values(list(table.columns)).reset_index(drop=True)
    return hashlib.sha256(ordered.to_csv(index=False).encode()).hexdigest()


def test_the_specification_hash_is_unchanged_by_the_move():
    assert small_lifecycle().specification_hash() == EXPECTED_SPECIFICATION_HASH


def test_the_simulated_table_is_unchanged_by_the_move():
    assert table_sha256(as_recorded(run(small_lifecycle()), RECORDED_SPECIFICATION_HASH)) == EXPECTED_TABLE_SHA256


@pytest.mark.parametrize("name", sorted(NAMES))
def test_every_name_of_the_old_module_still_imports_and_is_the_part_module_object(name):
    value = getattr(fitted_blocks, name)
    if NAMES[name] is not None:
        part = importlib.import_module(f"avalanche_research.model.parts.{NAMES[name]}")
        assert value is getattr(part, name)


def test_the_old_module_offers_no_name_this_test_does_not_list():
    assert {k for k in vars(fitted_blocks) if not k.startswith("__")} <= set(NAMES)
