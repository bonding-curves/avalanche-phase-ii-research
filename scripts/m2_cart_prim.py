"""Resume grouped CART and A-discovery/B-confirmation PRIM on a bound wide cache.

No simulations or threshold selection. Bootstrap NPZ keys are family__yield,
for example before__3.0. Whole-scope JSON retains full OOF and tree receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import time
from functools import partial
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import sklearn

from avalanche_research.analysis import cart, m2_contract, paired_sweep, prim

MEASURES = (*paired_sweep.MEASURES, "return_margin", "issuance_saved", "validator_stake_retained", "active_validators_retained")
CLASSIFIED = {"issuance_saved", "validator_stake_retained", "net_inflation", "return_margin"}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic(path, value):
    pending = path.with_suffix(path.suffix+".tmp")
    pending.write_text(json.dumps(value, allow_nan=False, separators=(",", ":"))+"\n")
    pending.replace(path)


def targets(frame):
    """Prospectively fixed primary and stated-alternative failure indicators."""
    primary = m2_contract.failure_labels(frame, cost="zero")
    for name in ("issuance_saved", "validator_stake_retained", "net_inflation"):
        yield name+"__primary", name, primary[name].to_numpy(), "primary", "zero"
    strict = m2_contract.failure_labels(frame, cost="zero", strict_stake=True)
    yield "validator_stake_retained__strict", "validator_stake_retained", strict.validator_stake_retained.to_numpy(), "stake_ge_1", "zero"
    lower = m2_contract.failure_labels(frame, cost="zero", inflation=m2_contract.CHAIN_INFLATION)
    yield "net_inflation__chain", "net_inflation", lower.net_inflation.to_numpy(), "chain_trailing_year", "zero"
    for column, cost in margin_columns():
        yield "return_margin__"+cost, "return_margin", (frame[column] < 0).to_numpy(), "margin_ge_0", cost


def margin_columns():
    yield "return_margin", "zero"
    for cost in ("low", "mid", "high"):
        yield f"return_margin_{cost}", cost
        yield f"return_margin_{cost}_fitting_price", cost+"_fitting_price"


def regression_columns():
    for name in MEASURES:
        if name not in CLASSIFIED:
            yield name, name, "zero"


def task(path, run_key, function):
    if path.exists():
        previous = json.loads(path.read_bytes())
        if previous.get("run_key") != run_key or previous.get("task_id") != path.stem:
            raise ValueError("resume source/config binding differs: "+str(path))
        digest = previous.get("result_sha256")
        body = json.dumps(previous["result"], allow_nan=False, sort_keys=True).encode()
        if hashlib.sha256(body).hexdigest() != digest:
            raise ValueError("saved result bytes do not match their digest")
        return {"path": path.name, "sha256": sha(path), "resumed": True,
                "status": previous["result"].get("status", "ok")}
    began = time.monotonic(); result = function()
    body = json.dumps(result, allow_nan=False, sort_keys=True).encode()
    atomic(path, {"run_key": run_key, "task_id": path.stem, "seconds": time.monotonic()-began,
                  "result_sha256": hashlib.sha256(body).hexdigest(), "result": result})
    return {"path": path.name, "sha256": sha(path), "resumed": False,
            "status": result.get("status", "ok")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("wide", "bootstrap", "output", "manifest"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--family", choices=tuple(m2_contract.FAMILY_INPUTS))
    parser.add_argument("--yield-pp", type=float)
    parser.add_argument("--horizon", type=int, choices=(180, 365))
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.manifest.read_bytes())
    wide_sha, bootstrap_sha = sha(args.wide), sha(args.bootstrap)
    if manifest["wide_sha256"] != wide_sha or manifest["bootstrap"]["file_sha256"] != bootstrap_sha:
        raise ValueError("caller-authenticated input manifest differs")
    configuration = {"wide_sha256": wide_sha, "bootstrap_sha256": bootstrap_sha, "input_manifest_sha256": sha(args.manifest),
        "source_sha256": {"runner": sha(Path(__file__)), "cart": sha(cart.__file__),
                          "prim": sha(prim.__file__), "contract": sha(m2_contract.__file__)},
        "measure_inventory": sorted(MEASURES),
        "reported_only_regression": [name for name in MEASURES if name not in CLASSIFIED],
        "outer_folds": 10, "inner_folds": 5, "ccp_alphas": list(cart.CCP_ALPHAS),
        "bootstrap_replicates": 1000, "bootstrap_seed_from_caller": 20261005,
        "peel_alpha": .05, "paste_alpha": .05, "min_mass": .05,
        "PRIM_A_qualification": {"coverage": .7, "density": .7},
        "PRIM_selection": "max coverage, density, min restricted dimensions, canonical bounds",
        "regression": "Reported-only measures, no invented thresholds; fixed inner negative MSE; no informative verdict",
        "primary_inflation": .05, "alternative_inflation": m2_contract.CHAIN_INFLATION,
        "costs": m2_contract.COSTS, "price_factor": m2_contract.PRICE_FACTOR,
        "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "sklearn": sklearn.__version__,
        "thread_environment": {key: os.environ.get(key) for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS")}}
    key = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
    config_path = args.output/"configuration.json"
    if config_path.exists() and json.loads(config_path.read_bytes()).get("run_key") != key:
        raise ValueError("output directory binds another input/configuration")
    atomic(config_path, {"run_key": key, "configuration": configuration})
    db = duckdb.connect(config={"threads": 1, "memory_limit": "1GB"})
    frame = db.execute("SELECT * FROM read_parquet(?)", [str(args.wide)]).df(); draws = np.load(args.bootstrap)
    for name, binding in manifest["bootstrap"]["matrices"].items():
        draw = draws[name]
        if list(draw.shape) != binding["shape"] or draw.dtype.kind not in "iu" or hashlib.sha256(np.asarray(draw, dtype="<i8").tobytes()).hexdigest() != binding["sha256"]:
            raise ValueError("joint bootstrap matrix differs from manifest")
    if frame.duplicated(["index", "horizon_days"]).any():
        raise ValueError("duplicate source trajectory/horizon")
    for family, inputs in m2_contract.FAMILY_INPUTS.items():
        if args.family and args.family != family:
            continue
        scopes = frame.loc[(frame.family == family) & frame.block.isin(["A", "B"])]
        for (yield_pp, horizon), part in scopes.groupby(["yield_pp", "horizon_days"], sort=True):
            if args.yield_pp is not None and args.yield_pp != yield_pp or args.horizon and args.horizon != horizon:
                continue
            part = part.sort_values(["i", "block"], kind="stable").reset_index(drop=True)
            A = part.loc[part.block == "A"].sort_values("i").reset_index(drop=True)
            B = part.loc[part.block == "B"].sort_values("i").reset_index(drop=True)
            if len(A) != 512 or len(B) != 512 or not np.array_equal(A.i, np.arange(512)) or not np.array_equal(B.i, np.arange(512)):
                raise ValueError("complete A/B base index membership required")
            scope = {"family": family, "competing_yield_pp": float(yield_pp), "horizon_days": int(horizon),
                     "response_context": "responses are varying inputs; no response pooling across family/yield/horizon"}
            bootstrap = draws[f"{family}__{float(yield_pp)}"]
            ids = part.row_id.tolist(); groups = [f"i{int(i):04d}" for i in part.i]
            X = part[list(inputs)].to_numpy(); receipts = []
            common = {"sample_ids": ids, "block_ids": groups, "feature_names": inputs, "scope": scope,
                      "bootstrap_indices": bootstrap, "independence_statement": "Saltelli base i conditional design units; A/B travel together; not empirical iid uncertainty"}
            prefix = f"{family}__{float(yield_pp)}__{int(horizon)}"
            for column, measure, cost in regression_columns():
                context = scope | {"measure": measure, "cost_level": cost}
                filename = prefix+"__regression__"+column+".json"
                receipts.append(task(args.output/filename, key, partial(cart.analyze_regression_cart,
                    X, part[column].to_numpy(), **(common | {"scope": context}))))
            A_values = {tag: values for tag, _, values, _, _ in targets(A)}
            B_values = {tag: values for tag, _, values, _, _ in targets(B)}
            for tag, measure, failed, alternative, cost in targets(part):
                context = scope | {"measure": measure, "cost_level": cost, "threshold_alternative": alternative}
                receipts.append(task(args.output/(prefix+"__classification__"+tag+".json"), key,
                    partial(cart.analyze_cart, X, ~failed, **(common | {"scope": context}), label_definition="Complement of frozen failure condition")))
                receipts.append(task(args.output/(prefix+"__prim__"+tag+".json"), key,
                    partial(prim.discover_confirm, A[list(inputs)].to_numpy(), A_values[tag], B[list(inputs)].to_numpy(), B_values[tag],
                        feature_names=inputs, scope=context, sample_ids_A=A.row_id.tolist(), sample_ids_B=B.row_id.tolist())))
            atomic(args.output/(prefix+"__scope-receipt.json"), {"run_key": key, "scope": scope, "tasks": receipts})
            print(json.dumps({"scope": scope, "tasks": len(receipts), "resumed": sum(r["resumed"] for r in receipts)}), flush=True)


if __name__ == "__main__":
    main()
