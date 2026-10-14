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


def test_the_expected_cells_are_the_design_and_the_committed_table_fills_them_exactly():
    import pandas as pd

    expected = selection.expected_cells()
    assert len(expected) == 108 and all(len(forecasts) == 10 for forecasts in expected.values())
    # Only the three late origins lose horizons: 2025-07-01 keeps 30 and 90 days, 2025-10-01 keeps 30 days.
    horizons = {origin: sorted(h for (o, v, h) in expected if o == origin and v == "active_validators") for origin in ("Fortuna", "2025-07-01", "2025-10-01")}
    assert horizons == {"Fortuna": [30, 90, 180], "2025-07-01": [30, 90], "2025-10-01": [30]}
    scores = pd.read_csv(selection.FOLDER / "development-distribution.csv")
    assert len(scores) == sum(len(forecasts) for forecasts in expected.values()) == 1080
    checked = selection.checked_scores(scores)
    assert len(checked) == 1080 and checked.horizon_days.dtype.kind == "i"


@pytest.mark.parametrize("plant", ["fractional horizon", "duplicate score", "missing origin", "missing variable",
                                   "missing whole cell", "missing one model in a cell", "missing benchmark in a cell",
                                   "unexpected cell", "unknown forecast"])
def test_a_score_table_that_is_not_the_design_is_refused(plant):
    import pandas as pd

    scores = pd.read_csv(selection.FOLDER / "development-distribution.csv")
    cell = (scores.origin == "Banff") & (scores.variable == "active_validators") & (scores.horizon_days == 30)
    if plant == "fractional horizon":
        scores.loc[scores.horizon_days == 90, "horizon_days"] = 90.5
    elif plant == "duplicate score":
        scores = pd.concat([scores, scores[scores.forecast == selection.CHALLENGER].head(1)])
    elif plant == "missing origin":
        scores = scores[scores.origin != "Banff"]
    elif plant == "missing variable":
        scores = scores[scores.variable != "active_validators"]
    elif plant == "missing whole cell":
        # Every row of one cell, both models, their pools and every benchmark: ten rows gone, no group left to inspect.
        assert cell.sum() == 10
        scores = scores[~cell]
    elif plant == "missing one model in a cell":
        scores = scores[~(cell & (scores.forecast == selection.INCUMBENT))]
    elif plant == "missing benchmark in a cell":
        scores = scores[~(cell & (scores.forecast == "N1d"))]
    elif plant == "unexpected cell":
        # 2025-10-01 at 90 days would reach the held-back period, so the design does not score it.
        extra = scores[cell].assign(origin="2025-10-01", horizon_days=90)
        scores = pd.concat([scores, extra])
    else:
        scores.loc[cell & (scores.forecast == "N4"), "forecast"] = "N5"
    with pytest.raises(ValueError):
        selection.checked_scores(scores)
