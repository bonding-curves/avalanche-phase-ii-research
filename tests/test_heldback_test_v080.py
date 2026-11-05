"""The held-back test's registered design follows its own rule, and its verdict rule reads as specified."""

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import heldback_test_v080 as heldback  # noqa: E402

BENCHMARKS = (*heldback.POINT, *heldback.DISTRIBUTION)


def summary_rows(model_crps: float, p: float, origins: int = 8, variable: str = "active_validator_stake_navax",
                 horizon: int = 90, benchmark_crps: float = 6.0) -> pd.DataFrame:
    rows = [{"variable": variable, "horizon_days": horizon, "forecast": "model", "origins": origins, "crps": model_crps,
             "cov50": 0.5, "cov80": 0.75, "p_better_than_N1d": p, "dm_horizon": 4, "dm_note": "truncated"}]
    rows += [{"variable": variable, "horizon_days": horizon, "forecast": b, "origins": origins, "crps": benchmark_crps,
              "cov50": np.nan, "cov80": np.nan, "p_better_than_N1d": np.nan, "dm_horizon": 4, "dm_note": ""}
             for b in BENCHMARKS]
    return pd.DataFrame(rows)


def test_the_specification_follows_its_own_rule():
    spec = heldback.specification()
    fit_origin, score_until, origins, horizons, cases = heldback.check_design(spec)
    assert fit_origin == date(2025, 11, 18) and score_until == date(2026, 9, 22)
    assert len(origins) == 10 and horizons == [30, 90, 180]
    assert [len(cases[h]) for h in horizons] == [10, 8, 5]
    assert all(o + pd.Timedelta(h, unit="D").to_pytimedelta() < score_until for h in horizons for o in cases[h])
    assert spec["primary"]["origins"] == len(cases[90])


def test_the_verdict_rule_passes_fails_and_is_inconclusive_as_specified():
    spec = heldback.specification()
    assert heldback.verdict(summary_rows(5.0, 0.01), spec)["verdict"] == "PASS"
    assert heldback.verdict(summary_rows(5.0, 0.20), spec)["verdict"] == "INCONCLUSIVE"
    assert heldback.verdict(summary_rows(6.0, 0.01), spec)["verdict"] == "FAIL"
    assert heldback.verdict(summary_rows(7.0, 0.01), spec)["verdict"] == "FAIL"
    short = heldback.verdict(summary_rows(5.0, 0.01, origins=7), spec)
    assert short["verdict"] == "INCONCLUSIVE" and short["reasons"]
    coverage = {(c["interval"], c["state"]) for c in heldback.verdict(summary_rows(5.0, 0.01), spec)["coverage"]}
    assert coverage == {("cov80", "pass"), ("cov50", "pass")}


@pytest.mark.skipif(not heldback.MANIFEST.exists(), reason="the test is not registered in this checkout")
def test_the_registered_hashes_match_the_files():
    manifest = json.loads(heldback.MANIFEST.read_text())
    assert manifest["status"] == "registered" and manifest["tag"] == heldback.TAG
    for path, expected in manifest["files"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
    assert manifest["pin"]["sha256"] == hashlib.sha256((ROOT / manifest["pin"]["path"]).read_bytes()).hexdigest()
