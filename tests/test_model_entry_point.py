"""The recipient's entry point runs the delegated candidate, the base of every v0.9 model, from its pin.

``avalanche model run`` builds a model through ``experiments.sweep.builder``. A variant that reads the origin's
delegation tables gets them from the pin's runs (``sweep.TABLE_VARIANTS``), so the command runs the candidate as the
selection does. Skipped while the pin or its runs are absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

pytest.importorskip("cadCAD")

from avalanche_research import cli
from avalanche_research.catalog import DataError
from avalanche_research.experiments import sweep
from avalanche_research.experiments.v081_inputs import pinned_inputs

PIN = Path("data/pins/p2-model-v0.8.1.json")


def test_model_run_builds_the_delegated_candidate_from_its_pin(tmp_path):
    try:
        pinned_inputs(PIN)
    except (DataError, FileNotFoundError) as error:
        pytest.skip(f"the candidate's pin is not usable in this checkout: {error}")
    assert "v0.8.1 candidate" in sweep.TABLE_VARIANTS
    out = tmp_path / "run"
    result = CliRunner().invoke(cli.cli, ["model", "run", str(PIN), str(out), "--origin", "2022-07-01",
                                          "--model", "v0.8.1 candidate", "--runs", "1", "--timesteps", "5",
                                          "--workers", "1", "--json"])
    assert result.exit_code == 0, result.output
    receipt = json.loads((out / "receipt.json").read_text())
    assert receipt["output"]["rows"] >= 1 and list(out.glob("*.parquet"))
