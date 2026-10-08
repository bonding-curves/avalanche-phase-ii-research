"""The development scores pass each batch its own slice of an origin's parameter draws."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "model_development_scores.py"
spec = importlib.util.spec_from_file_location("model_development_scores", SCRIPT)
scores = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scores)


def test_batch_b_reads_rows_20b_to_20b_plus_19_renumbered_from_zero():
    draws = pd.DataFrame({"renewal.intercept": range(200), "renewal_shift": range(200)})
    third = scores.batch_draws(draws, 2)
    assert third["renewal.intercept"].tolist() == list(range(40, 60))
    assert third.index.tolist() == list(range(20))


def test_every_batch_together_reads_each_draw_once():
    draws = pd.DataFrame({"renewal.intercept": range(200)})
    seen = pd.concat([scores.batch_draws(draws, b) for b in scores.BATCH_SEEDS])
    assert sorted(seen["renewal.intercept"]) == list(range(200))
