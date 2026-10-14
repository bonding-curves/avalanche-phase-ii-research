"""Complete paired KPI tables with original design labels and cost views."""
from __future__ import annotations

import numpy as np

from .m2_contract import ContractError, rescore_costs, row_metadata
from .paired_sweep import relative_kpis


def analysis_table(absolute, bundle):
    """One row per source trajectory/horizon, including matched relative KPIs.

    The caller authenticates the complete absolute table through read_outputs.
    This transformation repeats completeness checks and never silently drops a
    failed or nonfinite value. Baseline rows retain explicit absent ratios.
    """
    if absolute.duplicated(["index", "horizon_days", "measure"]).any():
        raise ContractError("duplicate measure or unexpected multiple cost levels")
    if not np.isfinite(absolute.value.to_numpy(dtype=float)).all():
        raise ContractError("nonfinite absolute KPI")
    wide = absolute.pivot(index=["index", "horizon_days"], columns="measure", values="value").reset_index()
    if len(wide) != len(bundle.rows) * 2 or wide.isna().any().any():
        raise ContractError("incomplete trajectory/horizon measure grid")
    if set(wide.horizon_days) != {180, 365}:
        raise ContractError("both horizons required")
    ratios = relative_kpis(absolute, bundle)
    paired = ratios.pivot(index=["index", "horizon_days"], columns="measure", values="value").reset_index()
    wide = wide.merge(paired, on=["index", "horizon_days"], how="left", validate="one_to_one")
    metadata = row_metadata(bundle)
    wide = wide.merge(metadata, on="index", how="left", validate="many_to_one")
    design = wide.block != "baseline"
    for name in ("issuance_saved", "validator_stake_retained", "active_validators_retained"):
        if not np.isfinite(wide.loc[design, name]).all():
            raise ContractError("incomplete paired design grid")
    identities = absolute[["index", "row_id"]].drop_duplicates()
    if identities["index"].duplicated().any():
        raise ContractError("multiple source row identities")
    wide = wide.merge(identities, on="index", validate="many_to_one")
    wide["baseline_row_id"] = wide.baseline.map(identities.set_index("index").row_id)
    wide["horizon"] = wide.horizon_days
    result = rescore_costs(wide).sort_values(["horizon_days", "index"], kind="stable").reset_index(drop=True)
    result.attrs["cell_accounting"] = {"expected": len(result), "success": len(result), "failed": 0}
    result.attrs["bundle_sha256"] = bundle.hashes
    return result
