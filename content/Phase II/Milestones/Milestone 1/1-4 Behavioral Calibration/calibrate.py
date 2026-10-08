"""Deliverable 1.4: the v0.8 candidate's fitted behaviour at origin 2025-11-18, with 95% intervals.

Run from an export of commit 1c891a4 of the research repository, with the staking periods run
staking-periods-2026-09-30 available to its data catalog (deliverables 1.1 and 1.2):

    uv run python calibrate.py <output folder>

Origin 2025-11-18 is the last day before the held-back period, which starts 2025-11-19 16:00 UTC. Every fit reads
only events before it, through fitted_inputs' own selection. Intervals:
  renewal logit   Laplace (inverse penalized Hessian) and a node-cluster bootstrap, 300 replicates
  profiles        renewal probability of typical nodes, node-cluster bootstrap
  arrivals        mean and dispersion, moving-block bootstrap of daily counts, 14-day blocks, 1,000 replicates
  return hazard   exact Poisson (Garwood) interval per cell, events over node-days at risk
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import special, stats

from avalanche_research import datasets
from avalanche_research.model import fitted_blocks as fb
from avalanche_research.model import fitted_lifecycle as fl

RUN = "staking-periods-2026-09-30"
ORIGIN = date(2025, 11, 18)
B_RENEWAL, B_ARRIVALS = 300, 1000
rng = np.random.default_rng(20261006)


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    periods = str(datasets.parquet_path("derived.staking-periods", RUN))
    fitted = fl.fitted_inputs(periods, ORIGIN, RUN)

    # The same selections fitted_inputs makes.
    day = fl._day(ORIGIN)
    cutoff = day * fl.US_PER_DAY + fl.INSTANT_US
    rows = fl.validator_periods(periods, cutoff)
    follow = fb.RENEWAL_DAYS * fl.US_PER_DAY
    ended = fl.renewal_endings(rows, cutoff - 365 * fl.US_PER_DAY - follow, cutoff - follow)
    inputs = fl.renewal_inputs(ended)
    y = ended["renewed"].to_numpy().astype(float)

    # Renewal logit: point fit, Laplace and node-cluster bootstrap.
    renewal = fb.RenewalLogit.fit(inputs, y, "calibration")
    beta = renewal.coefficients()
    assert np.allclose(beta, fitted["renewal"].coefficients()), "selection differs from fitted_inputs"
    design = fb.renewal_design(inputs["done"], inputs["after_return"], inputs["days"], inputs["stake_navax"])
    p = special.expit(design @ beta)
    penalty = np.ones(design.shape[1]); penalty[0] = 0.0
    hessian = (design * (p * (1 - p))[:, None]).T @ design + np.diag(penalty)
    laplace_se = np.sqrt(np.diag(np.linalg.inv(hessian)))
    nodes = ended["node_id"].to_numpy()
    unique = np.unique(nodes)
    index = {n: np.flatnonzero(nodes == n) for n in unique}
    boot = np.empty((B_RENEWAL, len(beta)))
    profiles = {
        "first commitment, 14 to 20 days, 2,000 to 2,100 AVAX": {"done": 0, "after_return": False, "days": 15, "stake": 2_000},
        "second commitment, 14 to 20 days, 2,000 to 2,100 AVAX": {"done": 1, "after_return": False, "days": 15, "stake": 2_000},
        "seventh or later, 14 to 20 days, 2,000 to 2,100 AVAX": {"done": 7, "after_return": False, "days": 15, "stake": 2_000},
        "seventh or later, 100 days or more, 100k to 1M AVAX": {"done": 7, "after_return": False, "days": 180, "stake": 500_000},
        "after a return, 14 to 20 days, 2,000 to 2,100 AVAX": {"done": 3, "after_return": True, "days": 15, "stake": 2_000},
        "seventh or later, 14 to 20 days, above 1M AVAX": {"done": 7, "after_return": False, "days": 15, "stake": 2_000_000},
    }
    profile_x = np.vstack([fb.renewal_design(np.array([v["done"]]), np.array([v["after_return"]]), np.array([v["days"]]),
                                              np.array([v["stake"] * fb.AVAX])) for v in profiles.values()])
    profile_boot = np.empty((B_RENEWAL, len(profiles)))
    for b in range(B_RENEWAL):
        picked = np.concatenate([index[n] for n in rng.choice(unique, len(unique))])
        fit_b = fb.RenewalLogit.fit({k: v[picked] for k, v in inputs.items()}, y[picked], "bootstrap")
        boot[b] = fit_b.coefficients()
        profile_boot[b] = special.expit(profile_x @ boot[b])
    terms = pd.DataFrame({
        "term": fb.RENEWAL_TERMS, "estimate": beta, "laplace_se": laplace_se,
        "laplace_low": beta - 1.96 * laplace_se, "laplace_high": beta + 1.96 * laplace_se,
        "bootstrap_low": np.percentile(boot, 2.5, axis=0), "bootstrap_high": np.percentile(boot, 97.5, axis=0),
    })
    terms["bootstrap_over_laplace_width"] = (terms.bootstrap_high - terms.bootstrap_low) / (terms.laplace_high - terms.laplace_low)
    terms.to_csv(out / "renewal-terms.csv", index=False)
    prof = pd.DataFrame({"profile": list(profiles), "renewal_probability": special.expit(profile_x @ beta),
                         "low": np.percentile(profile_boot, 2.5, axis=0), "high": np.percentile(profile_boot, 97.5, axis=0)})
    prof.to_csv(out / "renewal-profiles.csv", index=False)

    # Arrivals: moving-block bootstrap of the 365 daily first-ever counts.
    enter_day = fl._whole_days(rows["s"])
    year = rows[(enter_day > day - 365) & (enter_day <= day)]
    first = year[year["done"] == 0]
    counts = np.bincount((fl._whole_days(first["s"]) - (day - 364)).to_numpy(dtype=np.int64), minlength=365)
    arrivals = fb.Arrivals.fit(counts, "calibration")
    assert np.isclose(arrivals.mean_per_day, fitted["arrivals"].mean_per_day)
    block, n = 14, len(counts)
    stats_boot = []
    for _ in range(B_ARRIVALS):
        starts = rng.integers(0, n - block + 1, int(np.ceil(n / block)))
        sample = np.concatenate([counts[s:s + block] for s in starts])[:n]
        a = fb.Arrivals.fit(sample, "bootstrap")
        stats_boot.append((a.mean_per_day, a.dispersion))
    stats_boot = np.array(stats_boot)
    arr = pd.DataFrame({
        "parameter": ["mean_per_day", "dispersion"],
        "estimate": [arrivals.mean_per_day, arrivals.dispersion],
        "low": np.percentile(stats_boot, 2.5, axis=0), "high": np.percentile(stats_boot, 97.5, axis=0),
    })
    arr.to_csv(out / "arrivals.csv", index=False)

    # Return hazard: exact Poisson intervals per cell from the counts fitted_inputs used.
    returns = fitted["returns"]
    rows_h = []
    for cell in fb.RETURN_CELLS:
        evidence = returns.sources()[cell]["evidence"]
        events = int(evidence.split("; ")[-1].split(" returns in ")[0])
        at_risk = int(evidence.split(" returns in ")[1].split(" node-days")[0])
        low = stats.chi2.ppf(0.025, 2 * events) / 2 / at_risk if events else 0.0
        high = stats.chi2.ppf(0.975, 2 * events + 2) / 2 / at_risk
        rows_h.append({"cell": cell, "returns": events, "node_days": at_risk, "daily_hazard": events / at_risk if at_risk else 0.0,
                       "low": low, "high": high})
    pd.DataFrame(rows_h).to_csv(out / "return-hazard.csv", index=False)

    summary = {
        "origin": str(ORIGIN), "run": RUN, "client_commit": "1c891a4fc07e9c4f570682c7d204f3cddb85e700",
        "renewal_endings": len(ended), "renewal_nodes": len(unique), "renewal_share": float(y.mean()),
        "first_ever_in_year": len(first), "bootstrap_replicates": {"renewal": B_RENEWAL, "arrivals": B_ARRIVALS},
        "median_bootstrap_over_laplace_width": float(terms.bootstrap_over_laplace_width.median()),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    print(terms.round(3).to_string(index=False)); print(prof.round(3).to_string(index=False))
    print(arr.round(3).to_string(index=False)); print(pd.DataFrame(rows_h).round(5).to_string(index=False))


if __name__ == "__main__":
    main()
