"""The committed v0.8.0 selection scores give the committed verdict under the variant rule."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import model_v080_selection as selection


def test_the_committed_scores_give_the_committed_verdict():
    got = selection.verdict()
    assert got == json.loads((selection.FOLDER / "verdict.json").read_text())
    assert got["verdict"] == "adopt" and got["origins"] == 19
    assert got["stake_90_day_difference"] < 0


def test_the_verdict_command_passes_and_an_altered_verdict_fails(tmp_path, monkeypatch, capsys):
    assert selection.main(["verdict"]) == 0
    folder = tmp_path / "selection"
    folder.mkdir()
    for name in ("development-distribution.csv", "verdict.json"):
        (folder / name).write_bytes((selection.FOLDER / name).read_bytes())
    altered = json.loads((folder / "verdict.json").read_text()) | {"verdict": "reject"}
    (folder / "verdict.json").write_text(json.dumps(altered))
    monkeypatch.setattr(selection, "FOLDER", folder)
    assert selection.main(["verdict"]) == 1


@pytest.mark.parametrize("plant", ["fractional horizon", "duplicate score", "missing origin", "missing variable"])
def test_a_score_table_that_is_not_the_design_is_refused(plant):
    import pandas as pd

    scores = pd.read_csv(selection.FOLDER / "development-distribution.csv")
    if plant == "fractional horizon":
        scores.loc[scores.horizon_days == 90, "horizon_days"] = 90.5
    elif plant == "duplicate score":
        scores = pd.concat([scores, scores[scores.forecast == selection.CHALLENGER].head(1)])
    elif plant == "missing origin":
        scores = scores[scores.origin != "Banff"]
    else:
        scores = scores[scores.variable != "active_validators"]
    with pytest.raises(ValueError):
        selection.checked_scores(scores)
