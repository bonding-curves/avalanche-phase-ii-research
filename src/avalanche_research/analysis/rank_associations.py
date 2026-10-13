"""Synthetic MM1 rank associations on caller-validated, complete memory tables.

No files, RNG globals, outcome filtering, KPI reduction, fitted model or causal
claim. Bootstrap percentiles summarize the declared design conditionally.
"""

import math
from dataclasses import dataclass
from numbers import Real

import numpy as np
import pandas as pd
from scipy.stats import rankdata


class ContractError(ValueError):
    """Unsupported input or owner resampling/outcome policy."""


@dataclass(frozen=True)
class Resampling:
    unit: str
    block_column: str | None
    independence_statement: str
    replicates: int
    confidence: float
    seed: int

    def __post_init__(self):
        if self.unit not in ("row", "block"):
            raise ContractError("declare row or block resampling")
        if (
            not isinstance(self.independence_statement, str)
            or not self.independence_statement.strip()
        ):
            raise ContractError("caller must declare independence of resampling units")
        if self.unit == "block" and (
            not isinstance(self.block_column, str) or not self.block_column.strip()
        ):
            raise ContractError("block resampling needs a declared block column")
        if self.unit == "row" and self.block_column is not None:
            raise ContractError("row resampling cannot name a block column")
        if type(self.replicates) is not int or self.replicates < 2:
            raise ContractError("declare at least two bootstrap replicates")
        if type(self.seed) is not int or not 0 <= self.seed < 2**64:
            raise ContractError(
                "declare a nonnegative uint64-range Python integer seed"
            )
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, Real)
            or not 0 < self.confidence < 1
        ):
            raise ContractError("confidence must be finite and between zero and one")


def _names(values, label):
    if isinstance(values, str):
        raise ContractError(label + " must be a declared sequence")
    values = tuple(values)
    if (
        not values
        or any(not isinstance(v, str) or not v.strip() for v in values)
        or len(set(values)) != len(values)
    ):
        raise ContractError(label + " must be nonempty unique column names")
    return values


def _finite(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError):
        return False


def _validate(table, parameters, kpis, response_column, spec):
    if (
        not isinstance(table, pd.DataFrame)
        or not table.columns.is_unique
        or table.empty
    ):
        raise ContractError(
            "nonempty already validated DataFrame with unique columns required"
        )
    if not isinstance(spec, Resampling):
        raise ContractError("explicit Resampling declaration required")
    if not isinstance(response_column, str) or not response_column.strip():
        raise ContractError("caller must name the response design column")
    if response_column in {
        "row_id",
        "run",
        "pair_id",
        "variant",
        "status",
        "disposition",
        "seed",
        "model_pin",
        "data_pin",
        "design_pin",
        spec.block_column,
    }:
        raise ContractError("response must be a distinct declared design column")
    required = {
        "row_id",
        "run",
        "pair_id",
        "variant",
        "status",
        "disposition",
        response_column,
        *parameters,
        *kpis,
    }
    if spec.unit == "block":
        required.add(spec.block_column)
    if not required <= set(table.columns):
        raise ContractError("missing declared design, outcome or analysis columns")
    metadata = {
        "row_id",
        "run",
        "pair_id",
        "variant",
        "status",
        "disposition",
        "seed",
        "model_pin",
        "data_pin",
        "design_pin",
        response_column,
        spec.block_column,
    }
    if set(parameters) & set(kpis) or (set(parameters) | set(kpis)) & metadata:
        raise ContractError(
            "parameter/KPI declarations overlap or include stratum/metadata columns"
        )
    accounting = table.attrs.get("cell_accounting")
    if accounting != {"expected": len(table), "success": len(table), "failed": 0}:
        raise ContractError(
            "complete upstream cell accounting required; failed/missing cells need owner policy"
        )
    if any(not isinstance(v, str) or v != "success" for v in table.status):
        raise ContractError(
            "failed or unknown outcomes require owner policy; no row is dropped"
        )
    if any(not isinstance(v, str) or v != "" for v in table.disposition):
        raise ContractError(
            "only empty successful disposition is supported; owner policy required"
        )
    if table.duplicated(["row_id", "run"]).any():
        raise ContractError("duplicate upstream run cell")
    if any(not isinstance(v, str) or not v.strip() for v in table.variant):
        raise ContractError("variant strata must be nonempty strings")
    for v in table[response_column]:
        if not ((isinstance(v, str) and v.strip()) or _finite(v)):
            raise ContractError("response strata must be known finite scalars")
    for column in (*parameters, *kpis):
        if any(not _finite(v) for v in table[column]):
            raise ContractError(
                "all parameter/KPI values must be finite real scalars; no pairwise dropping"
            )
    if spec.unit == "row":
        if any(v != "" for v in table.pair_id) or table.row_id.duplicated().any():
            raise ContractError(
                "paired or replicated design requires whole independent blocks, not row iid"
            )
    elif any(not isinstance(v, str) or not v.strip() for v in table[spec.block_column]):
        raise ContractError("block IDs must be known nonempty strings")
    elif table[spec.block_column].nunique() < 2:
        raise ContractError(
            "bootstrap requires at least two declared independent blocks"
        )


def _coefficient(x, y):
    x, y = x - np.mean(x), y - np.mean(y)
    nx, ny = np.linalg.norm(x), np.linalg.norm(y)
    if nx == 0 or ny == 0:
        return None
    return float(np.clip(np.dot(x / nx, y / ny), -1, 1))


def _point(frame, parameters, kpi, target, method):
    n = len(frame)
    support = {
        "rows": n,
        "parameter_unique": int(frame[target].nunique()),
        "kpi_unique": int(frame[kpi].nunique()),
    }

    def undefined(reason, **more):
        return {
            "status": "undefined",
            "reason": reason,
            "coefficient": None,
            **support,
            **more,
        }

    if n < 2:
        return undefined("insufficient_rows")
    if support["parameter_unique"] < 2:
        return undefined("constant_parameter")
    if support["kpi_unique"] < 2:
        return undefined("constant_kpi")
    # Rank original integer/object values before float arithmetic, preserving
    # adjacent integer values above 2**53. Average ranks explicitly handle ties.
    x = rankdata(frame[target].to_numpy(), method="average")
    y = rankdata(frame[kpi].to_numpy(), method="average")
    detail = {}
    if method == "prcc":
        controls = [p for p in parameters if p != target]
        design = np.column_stack(
            [
                np.ones(n),
                *[rankdata(frame[p].to_numpy(), method="average") for p in controls],
            ]
        )
        singular = np.linalg.svd(design, compute_uv=False)
        tolerance = np.finfo(float).eps * max(design.shape) * singular[0]
        rank = int(np.sum(singular > tolerance))
        detail = {
            "control_columns": controls,
            "control_rank": rank,
            "control_columns_including_intercept": design.shape[1],
            "rank_tolerance": float(tolerance),
            "residual_df": n - rank - 1,
        }
        if rank != design.shape[1]:
            return undefined("rank_deficient_controls", **detail)
        if n - rank - 1 <= 0:
            return undefined("nonpositive_residual_df", **detail)
        q, _ = np.linalg.qr(design, mode="reduced")
        rx, ry = x - q @ (q.T @ x), y - q @ (q.T @ y)
        # Refuse numerically unresolved residual variation instead of treating
        # QR roundoff as a precise partial correlation.
        eps = 64 * np.finfo(float).eps
        if np.linalg.norm(rx) <= eps * np.linalg.norm(x - np.mean(x)):
            return undefined("unresolved_parameter_residual", **detail)
        if np.linalg.norm(ry) <= eps * np.linalg.norm(y - np.mean(y)):
            return undefined("unresolved_kpi_residual", **detail)
        x, y = rx, ry
    return {
        "status": "assessable",
        "reason": None,
        "coefficient": _coefficient(x, y),
        **support,
        **detail,
    }


def _draw_indices(table, spec, rng):
    """Global units: a block crossing variant/response strata travels together."""
    if spec.unit == "row":
        return rng.integers(0, len(table), size=len(table))
    blocks = tuple(dict.fromkeys(table[spec.block_column]))
    members = [
        np.flatnonzero(table[spec.block_column].to_numpy() == block) for block in blocks
    ]
    draw = rng.integers(0, len(blocks), size=len(blocks))
    return np.concatenate([members[i] for i in draw])


def analyze_mm1(table, parameter_columns, kpi_columns, *, response_column, resampling):
    """Per variant/response Spearman and PRCC plus conditional percentile intervals.

    Caller supplies the frozen upstream validated table, numeric column roles,
    independent-unit assertion, resample count, confidence and local seed.
    Any failed/missing cell or nonempty disposition refuses the whole call.
    No rowwise removal, averaging across strata, KPI threshold or causal claim.
    """
    parameters, kpis = (
        _names(parameter_columns, "parameters"),
        _names(kpi_columns, "KPIs"),
    )
    _validate(table, parameters, kpis, response_column, resampling)
    groups = list(table.groupby(["variant", response_column], sort=False, dropna=False))
    records = []
    for (variant, response), frame in groups:
        for kpi in kpis:
            for target in parameters:
                for method in ("spearman", "prcc"):
                    records.append(
                        {
                            "variant": variant,
                            "response": response,
                            "parameter": target,
                            "kpi": kpi,
                            "method": method,
                            "point": _point(frame, parameters, kpi, target, method),
                            "independent_units": len(frame)
                            if resampling.unit == "row"
                            else int(frame[resampling.block_column].nunique()),
                            "bootstrap_values": [],
                            "bootstrap_undefined_reasons": {},
                        }
                    )
    rng = np.random.default_rng(resampling.seed)
    for _ in range(resampling.replicates):
        sampled = table.iloc[_draw_indices(table, resampling, rng)]
        for record in records:
            frame = sampled[
                (sampled.variant == record["variant"])
                & (sampled[response_column] == record["response"])
            ]
            point = _point(
                frame, parameters, record["kpi"], record["parameter"], record["method"]
            )
            if point["status"] == "assessable":
                record["bootstrap_values"].append(point["coefficient"])
            else:
                reasons = record["bootstrap_undefined_reasons"]
                reasons[point["reason"]] = reasons.get(point["reason"], 0) + 1
    alpha = (1 - float(resampling.confidence)) / 2
    for record in records:
        values = record.pop("bootstrap_values")
        if (
            record["point"]["status"] == "assessable"
            and len(values) == resampling.replicates
            and record["independent_units"] >= 2
        ):
            interval = np.quantile(values, [alpha, 1 - alpha], method="linear").tolist()
            record["interval"] = {
                "status": "assessable",
                "bounds": interval,
                "reason": None,
            }
        else:
            record["interval"] = {
                "status": "unassessable",
                "bounds": None,
                "reason": "undefined point/resamples or insufficient independent units; no invalid draw is silently discarded",
            }
        record["bootstrap_assessable"] = len(values)
        record["bootstrap_total"] = resampling.replicates
    return {
        "scope": "synthetic MM1 scaffold; no scientific, empirical or causal acceptance",
        "input_rows": len(table),
        "strata_columns": ["variant", response_column],
        "resampling": {
            "unit": resampling.unit,
            "block_column": resampling.block_column,
            "independence_statement": resampling.independence_statement,
            "replicates": resampling.replicates,
            "confidence": float(resampling.confidence),
            "seed": resampling.seed,
            "draw": "global whole units; cross-stratum blocks remain together; input design order fixes unit enumeration",
            "interval_interpretation": "conditional design percentile summaries, not empirical coverage or causal uncertainty",
        },
        "relationships": records,
    }
