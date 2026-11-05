import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "results" / "model-v0.8.1-selection"


def selection():
    spec = importlib.util.spec_from_file_location("model_v081_selection", ROOT / "scripts" / "model_v081_selection.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_committed_scores_give_the_committed_verdict():
    got = selection().verdict(FOLDER)
    want = json.loads((FOLDER / "verdict.json").read_text())
    assert got == want


def test_a_missing_origin_is_refused(tmp_path):
    scores = pd.read_csv(FOLDER / "development-distribution.csv")
    dropped = sorted(scores.origin.unique())[0]
    scores[scores.origin != dropped].to_csv(tmp_path / "development-distribution.csv", index=False)
    with pytest.raises(ValueError, match="every origin"):
        selection().verdict(tmp_path)
