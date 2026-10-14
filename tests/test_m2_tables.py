"""Complete paired transformation with independent source-level references."""
from types import SimpleNamespace

import pandas as pd
import pytest

from avalanche_research.analysis.m2_contract import ContractError
from avalanche_research.analysis.m2_tables import analysis_table
from avalanche_research.analysis.paired_sweep import MEASURES


def fixture():
    row = {"seed": 1, "draw": 0, "origin": "2025-11-18", "model": "fixture",
           "mechanism": {"name": "ACP285Ramp", "activation": "2025-11-18T16:00:00+00:00",
                         "ramp_days": 90, "target_min_rate": .075},
           "renewal_response": .04, "entry_response": .02,
           "outside_yield_pp": 5., "fitted_outside_yield_pp": 4.}
    rows = (row, {**row, "mechanism": {"name": "ChainReward"}})
    labels = pd.DataFrame([
        {"index": 0, "family": "ramp", "yield_pp": 5., "block": "A", "i": 0,
         "j": None, "u1": .5, "u2": .4, "u3": .2, "baseline": 1},
        {"index": 1, "family": "chain", "yield_pp": 5., "block": "baseline", "i": 0,
         "j": None, "u1": None, "u2": None, "u3": None, "baseline": None}])
    labels["baseline"] = pd.Series([1, None], dtype=object)
    bundle = SimpleNamespace(rows=rows, labels=labels, hashes={"test": "frozen"},
                             design={"reducer": {"horizons": [180, 365]}})
    records = []
    for i in range(2):
        for h in (180, 365):
            for m in (*MEASURES, "return_margin"):
                v = {"issued_navax": 100. if i == 0 else 200., "validator_stake_navax": 1000.,
                     "active_validators": 50. if i == 0 else 100.}.get(m, .2)
                records.append({"index": i, "run": 1, "horizon_days": h, "measure": m,
                                "cost_level": "zero" if m == "return_margin" else "", "value": v,
                                "row_id": f"r{i}"})
    return bundle, pd.DataFrame(records)


def test_complete_transform_preserves_identity_bands_and_baselines():
    bundle, absolute = fixture()
    for column in ("u1", "u2", "u3"):
        bundle.labels[column] = bundle.labels[column].map(lambda v: "" if pd.isna(v) else repr(v))
    result = analysis_table(absolute, bundle)
    assert len(result) == 4
    one = result.loc[(result["index"] == 0) & (result.horizon_days == 365)].iloc[0]
    assert one.issuance_saved == .5
    assert one.u1 == .5 and one.u2 == .4 and one.u3 == .2
    assert one.validator_stake_retained == 1
    assert one.active_validators_retained == .5
    assert one.renewal_band == "middle" and one.entry_band == "low"
    assert one.baseline_row_id == "r1" and one.target_min_rate == .075
    assert one.return_margin_high == pytest.approx(.17)
    assert result.loc[result.block == "baseline", "issuance_saved"].isna().all()


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "horizon", "identity", "nonfinite"])
def test_changed_support_never_silently_drops(mutation):
    bundle, absolute = fixture()
    if mutation == "missing":
        absolute = absolute.iloc[1:]
    elif mutation == "duplicate":
        absolute = pd.concat([absolute, absolute.iloc[[0]]])
    elif mutation == "horizon":
        absolute.loc[absolute.horizon_days == 180, "horizon_days"] = 90
    elif mutation == "identity":
        absolute.loc[0, "row_id"] = "changed"
    else:
        absolute.loc[0, "value"] = float("nan")
    with pytest.raises((ContractError, ValueError)):
        analysis_table(absolute, bundle)
