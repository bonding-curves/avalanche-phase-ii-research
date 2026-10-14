"""Standalone Bokeh figures over exact report-summary frames.

These builders perform no scientific estimation, aggregation or row sampling.
Every source retains the supplied CSV columns, including status and reasons.
Callers supply the producer provenance and export the same frames as CSV.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
from bokeh.embed import file_html
from bokeh.layouts import column
from bokeh.models import (
    ColorBar,
    ColumnDataSource,
    CustomJS,
    DataTable,
    Div,
    HoverTool,
    LinearColorMapper,
    Select,
    Span,
    TableColumn,
    Title,
)
from bokeh.palettes import RdBu11, Viridis256
from bokeh.plotting import figure
from bokeh.resources import INLINE
from bokeh.transform import transform


class FigureContractError(ValueError):
    """A summary lacks fields needed for an honest figure."""


CONTEXT = (
    "Design family",
    "Competing yield (%)",
    "Horizon (days)",
    "Renewal response",
    "Entry response",
    "Cost level",
    "Threshold alternative",
)


def _require(frame: pd.DataFrame, columns: Sequence[str]) -> None:
    missing = set(columns) - set(frame.columns)
    if missing:
        raise FigureContractError(f"Missing report columns: {sorted(missing)}")


def _source(
    frame: pd.DataFrame, *, csv_frame: pd.DataFrame | None = None
) -> ColumnDataSource:
    if not frame.columns.is_unique:
        raise FigureContractError("CSV column names must be unique")
    source = ColumnDataSource({name: frame[name].tolist() for name in frame.columns})
    original = frame if csv_frame is None else csv_frame
    source.tags = [
        {
            "canonical_frame_csv_sha256": hashlib.sha256(
                original.to_csv(index=False).encode()
            ).hexdigest(),
            "rows": len(frame),
            "columns": list(original.columns),
        }
    ]
    return source


def _table(frame: pd.DataFrame, height: int = 260) -> DataTable:
    return DataTable(
        source=_source(frame),
        columns=[TableColumn(field=name, title=name) for name in frame],
        height=height,
        sizing_mode="stretch_width",
        index_position=None,
    )


def _hover(frame: pd.DataFrame) -> HoverTool:
    return HoverTool(tooltips=[(name, f"@{{{name}}}") for name in frame])


def _star_label(value):
    if isinstance(value, (bool, np.bool_)):
        return "*" if value else ""
    if isinstance(value, str) and value in ("True", "False"):
        return "*" if value == "True" else ""
    return "?"


def _panels(frame: pd.DataFrame, facets: Sequence[str]):
    present = [name for name in facets if name in frame]
    if frame.empty:
        return []
    if not present:
        return [("Declared scope", frame)]
    output = []
    for key, rows in frame.groupby(present, sort=False, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        title = " | ".join(
            f"{name}: {value}" for name, value in zip(present, key, strict=True)
        )
        output.append((title, rows))
    return output


def _wrap(title: str, panels: list, provenance: Mapping[str, str], note: str):
    required = ("sweep_id", "model_version", "code_sha")
    if any(not provenance.get(name) for name in required):
        raise FigureContractError(
            "Provenance requires sweep_id, model_version and code_sha"
        )
    stamp = " | ".join(f"{name}: {provenance[name]}" for name in required)
    description = Div(
        text=f"<h2>{escape(title)}</h2><p>{escape(stamp)}</p><p>{escape(note)}</p>"
    )
    if not panels:
        panels = [Div(text="<p>No rows supplied. No result inferred.</p>")]
    if len(panels) > 1:
        options = []
        for index, panel in enumerate(panels):
            title_model = getattr(panel, "title", None)
            label = (
                getattr(title_model, "text", None)
                or panel.name
                or f"Details {index + 1}"
            )
            options.append((str(index), label))
        visible = column(panels[0], sizing_mode="stretch_width")
        selector = Select(
            title="Scope", value="0", options=options, sizing_mode="stretch_width"
        )
        selector.js_on_change(
            "value",
            CustomJS(
                args={"container": visible, "panels": panels},
                code="container.children = [panels[Number(cb_obj.value)]];",
            ),
        )
        return column(description, selector, visible, sizing_mode="stretch_width")
    return column(description, *panels, sizing_mode="stretch_width")


def correlation_heatmap(
    frame: pd.DataFrame,
    *,
    provenance: Mapping[str, str],
    facets: Sequence[str] = (*CONTEXT, "Coefficient (Spearman or partial rank)"),
):
    """Signed coefficient cells, explicit missing values and unqualified stars."""
    _require(
        frame,
        (
            "Measure",
            "Input",
            "Coefficient value",
            "Interval low (95%)",
            "Interval high (95%)",
        ),
    )
    panels = []
    for title, rows in _panels(frame, facets):
        if rows.duplicated(["Measure", "Input"]).any():
            raise FigureContractError(
                "Heatmap cells overlap; declare additional facets"
            )
        values = pd.to_numeric(rows["Coefficient value"], errors="raise").to_numpy(
            float
        )
        finite = values[np.isfinite(values)]
        extent = max(1.0, float(np.abs(finite).max())) if len(finite) else 1.0
        mapper = LinearColorMapper(
            palette=RdBu11[::-1], low=-extent, high=extent, nan_color="#bdbdbd"
        )
        plot = figure(
            title=title,
            x_range=list(dict.fromkeys(rows.Input)),
            y_range=list(reversed(list(dict.fromkeys(rows.Measure)))),
            width=900,
            height=max(240, 55 * rows.Measure.nunique()),
            tools="pan,wheel_zoom,reset,save",
        )
        source = _source(rows)
        star_column = "Starred (Benjamini-Hochberg 5%)"
        source.data["_star"] = (
            [_star_label(value) for value in rows[star_column]]
            if star_column in rows
            else ["?"] * len(rows)
        )
        plot.rect(
            x="Input",
            y="Measure",
            width=0.96,
            height=0.96,
            source=source,
            fill_color=transform("Coefficient value", mapper),
            line_color="white",
        )
        plot.text(
            x="Input",
            y="Measure",
            text="_star",
            source=source,
            text_align="center",
            text_baseline="middle",
            text_font_size="18px",
            text_color="black",
        )
        plot.add_layout(
            ColorBar(color_mapper=mapper, title="Signed coefficient"), "right"
        )
        plot.add_tools(_hover(rows))
        panels.append(plot)
    return _wrap(
        "Rank associations",
        panels,
        provenance,
        "Diverging scale centered at zero. Gray is undefined. * is a supplied Benjamini-Hochberg 5% rejection, blank is supplied false, and ? is unknown. Hover retains intervals, status and p-value qualification; no stars are inferred from intervals.",
    )


def _tree_positions(
    rows: pd.DataFrame,
) -> tuple[list[float], list[float], list[tuple[int, int]]]:
    keys = rows["Node"].tolist()
    if len(set(keys)) != len(keys):
        raise FigureContractError("Tree node identities must be unique within a panel")
    index = {node: j for j, node in enumerate(keys)}
    children = {j: [] for j in range(len(rows))}
    roots, edges = [], []
    for j, parent in enumerate(rows["Parent node"]):
        if pd.isna(parent) or parent == "":
            roots.append(j)
        elif parent in index:
            parent_j = index[parent]
            children[parent_j].append(j)
            edges.append((parent_j, j))
        else:
            raise FigureContractError("Tree parent is absent from its panel")
    if len(roots) != 1:
        raise FigureContractError("Each tree panel requires exactly one root")
    xs, ys, visiting, done = {}, {}, set(), set()
    leaf_count = 0

    def visit(node, depth):
        nonlocal leaf_count
        if node in visiting:
            raise FigureContractError("Tree contains a cycle")
        visiting.add(node)
        if children[node]:
            for child in children[node]:
                visit(child, depth + 1)
            xs[node] = float(np.mean([xs[child] for child in children[node]]))
        else:
            xs[node] = float(leaf_count)
            leaf_count += 1
        ys[node] = float(-depth)
        visiting.remove(node)
        done.add(node)

    visit(roots[0], 0)
    if len(done) != len(rows):
        raise FigureContractError("Tree has disconnected or cyclic nodes")
    return [xs[j] for j in range(len(rows))], [ys[j] for j in range(len(rows))], edges


def tree_figure(
    frame: pd.DataFrame,
    *,
    provenance: Mapping[str, str],
    facets: Sequence[str] = (*CONTEXT, "Measure", "Target type"),
):
    """Descriptive final trees; OOF validation belongs in its separate table."""
    _require(
        frame,
        (
            "Node",
            "Parent node",
            "Split input",
            "Split value",
            "Leaf",
            "Runs at node",
        ),
    )
    panels = []
    for title, rows in _panels(frame, facets):
        target_type = (
            rows["Target type"].iloc[0] if "Target type" in rows else "classification"
        )
        if target_type not in ("classification", "regression"):
            raise FigureContractError("Unknown tree target type")
        if target_type == "regression":
            prediction_column = (
                "Node mean target" if "Node mean target" in rows else "Prediction value"
            )
        else:
            prediction_column = "Share meeting threshold"
        _require(rows, (prediction_column,))
        xs, ys, edges = _tree_positions(rows)
        plotted = rows.copy()
        plotted["_x"], plotted["_y"] = xs, ys
        plotted["_label"] = [
            f"leaf: {share:.3g}" if leaf else f"{feature} ≤ {value:.4g}"
            for leaf, share, feature, value in zip(
                rows.Leaf,
                rows[prediction_column],
                rows["Split input"],
                rows["Split value"],
                strict=True,
            )
        ]
        x_padding = max(0.4, (max(xs) - min(xs)) * 0.12)
        y_padding = max(0.4, (max(ys) - min(ys)) * 0.06)
        plot = figure(
            title=title,
            width=1000,
            height=min(900, max(300, int(130 * (1 - min(ys))))),
            x_range=(min(xs) - x_padding, max(xs) + x_padding),
            y_range=(min(ys) - y_padding, max(ys) + y_padding),
            tools="pan,wheel_zoom,reset,save",
        )
        plot.segment(
            x0=[xs[a] for a, _ in edges],
            y0=[ys[a] for a, _ in edges],
            x1=[xs[b] for _, b in edges],
            y1=[ys[b] for _, b in edges],
            line_color="#888888",
        )
        mapper = (
            LinearColorMapper(palette=Viridis256, low=0, high=1, nan_color="#bdbdbd")
            if target_type == "classification"
            else None
        )
        source = _source(plotted, csv_frame=rows)
        nodes = plot.scatter(
            x="_x",
            y="_y",
            size=24,
            source=source,
            color=transform(prediction_column, mapper)
            if mapper is not None
            else "#2166ac",
        )
        plot.text(
            x="_x",
            y="_y",
            text="_label",
            source=source,
            text_align="center",
            y_offset=18,
            text_font_size="10px",
        )
        plot.add_tools(HoverTool(renderers=[nodes], tooltips=_hover(rows).tooltips))
        plot.xaxis.visible = False
        plot.yaxis.visible = False
        panels.append(plot)
    return _wrap(
        "Decision trees",
        panels,
        provenance,
        "Descriptive fitted tree. Classification node shares or regression node target means and run counts are training descriptions, not cross-validated accuracy or evidence of informativeness. Regression has no invented threshold or pass share.",
    )


def sobol_figure(
    frame: pd.DataFrame,
    *,
    provenance: Mapping[str, str],
    facets: Sequence[str] = (
        "Design family",
        "Competing yield (%)",
        "Horizon (days)",
        "Measure",
    ),
):
    """First/total indices with raw intervals, including values outside [0,1]."""
    _require(
        frame,
        (
            "Input",
            "First-order index",
            "First-order low (95%)",
            "First-order high (95%)",
            "Total-order index",
            "Total-order low (95%)",
            "Total-order high (95%)",
            "Converged",
            "Largest change when the sample size doubled",
            "Base sample size",
            "status",
            "convergence_status",
        ),
    )
    panels = []
    for title, rows in _panels(frame, facets):
        if rows.Input.duplicated().any():
            raise FigureContractError("Sobol inputs overlap; declare additional facets")
        plotted = rows.copy()
        movement_name = "Largest change when the sample size doubled"
        movements = pd.to_numeric(rows[movement_name], errors="raise").to_numpy(float)
        flags = []
        for value, movement in zip(rows.Converged, movements, strict=True):
            if pd.isna(value):
                flag = None
            elif isinstance(value, (bool, np.bool_)):
                flag = bool(value)
            elif isinstance(value, str) and value in ("True", "False"):
                flag = value == "True"
            else:
                raise FigureContractError("Converged must be Boolean or undefined")
            if np.isnan(movement):
                if flag is not None:
                    raise FigureContractError(
                        "Undefined movement requires undefined convergence"
                    )
            elif (
                not np.isfinite(movement)
                or movement < 0
                or flag is None
                or flag != (movement <= 0.02)
            ):
                raise FigureContractError(
                    "Convergence flag differs from the frozen 0.02 movement rule"
                )
            flags.append(flag)
        failed = sum(flag is False for flag in flags)
        passed = sum(flag is True for flag in flags)
        undefined_count = sum(flag is None for flag in flags)
        state = (
            "FAILED"
            if failed
            else "UNDEFINED"
            if undefined_count == len(flags)
            else "PARTLY UNDEFINED"
            if undefined_count
            else "CONVERGED"
        )
        finite_movements = movements[np.isfinite(movements)]
        maximum = (
            f"{finite_movements.max():.9f}" if len(finite_movements) else "undefined"
        )
        bases = pd.to_numeric(rows["Base sample size"], errors="raise").to_numpy(float)
        if (
            not np.isfinite(bases).all()
            or (bases < 2).any()
            or (bases != np.floor(bases)).any()
        ):
            raise FigureContractError("Base sample size must be a known integer >=2")
        base_label = ", ".join(str(int(value)) for value in sorted(set(bases)))
        qualification = f"Convergence: {state} | max movement: {maximum} | limit: 0.02 | N={base_label}"
        status_label = ", ".join(dict.fromkeys(rows.status.astype(str)))
        convergence_label = ", ".join(
            dict.fromkeys(rows.convergence_status.astype(str))
        )
        plotted["Convergence interpretation"] = [
            "undefined" if flag is None else "converged" if flag else "failed"
            for flag in flags
        ]
        plotted["_y_first"] = np.arange(len(rows)) + 0.12
        plotted["_y_total"] = np.arange(len(rows)) - 0.12
        source = _source(plotted, csv_frame=rows)
        plot = figure(
            title=title,
            width=950,
            height=max(260, len(rows) * 65),
            tools="pan,wheel_zoom,reset,save",
        )
        plot.add_layout(Title(text=qualification, text_font_size="12px"), "above")
        for name, y, color in (
            ("First-order", "_y_first", "#2166ac"),
            ("Total-order", "_y_total", "#b2182b"),
        ):
            plot.segment(
                x0=f"{name} low (95%)",
                x1=f"{name} high (95%)",
                y0=y,
                y1=y,
                source=source,
                line_color=color,
                line_width=2,
            )
            plot.scatter(
                x=f"{name} index",
                y=y,
                source=source,
                color=color,
                size=9,
                legend_label=name,
            )
        plot.yaxis.ticker = list(range(len(rows)))
        plot.yaxis.major_label_overrides = dict(enumerate(rows.Input))
        plot.xaxis.axis_label = (
            "Variance sensitivity index (95% conditional bootstrap interval)"
        )
        for location in (0, 1):
            plot.add_layout(
                Span(
                    location=location,
                    dimension="height",
                    line_color="#888888",
                    line_dash="dashed",
                )
            )
        plot.add_tools(
            _hover(
                rows.assign(
                    **{
                        "Convergence interpretation": plotted[
                            "Convergence interpretation"
                        ]
                    }
                )
            )
        )
        annotation = Div(
            text=(
                f"<p><strong>{escape(qualification)}</strong><br>"
                f"Source status: {escape(status_label)}. Convergence source status: {escape(convergence_label)}. "
                f"Input rows: {passed} converged, {failed} failed, {undefined_count} undefined. "
                "The measure's maximum movement across all first/total input indices supplies each repeated flag. "
                "Undefined indices are not zero importance.</p>"
            )
        )
        facet_children = [annotation, plot]
        undefined = rows[
            [
                name
                for name in (
                    "Input",
                    "status",
                    "reason",
                    "Converged",
                    movement_name,
                    "convergence_status",
                    "convergence_reason",
                )
                if name in rows
            ]
        ]
        if any(
            rows[name].isna().any()
            for name in ("First-order index", "Total-order index")
        ):
            facet_children.append(_table(undefined))
        panels.append(
            column(
                *facet_children, name=f"{title} | {state}", sizing_mode="stretch_width"
            )
        )
    return _wrap(
        "Variance sensitivity",
        panels,
        provenance,
        "Responses are inputs, not filters. Finite indices outside [0,1] are retained. Convergence uses the unchanged maximum movement limit 0.02. Each selected facet displays its own source status and movement; hover retains every supplied value and interval.",
    )


def region_figure(
    points: pd.DataFrame,
    boxes: pd.DataFrame,
    *,
    provenance: Mapping[str, str],
    x_input: str | None = None,
    y_input: str | None = None,
    facets: Sequence[str] = (*CONTEXT, "Failure condition"),
):
    """Saved points and optional two-dimensional projection of frozen boxes."""
    _require(
        points, ("First input value", "Second input value", "Failed", "Inside box")
    )
    panels = []
    for title, rows in _panels(points, facets):
        plotted = rows.copy()
        for name in ("Failed", "Inside box"):
            if not all(isinstance(value, (bool, np.bool_)) for value in rows[name]):
                raise FigureContractError(
                    f"{name} must be Boolean; undefined is not false"
                )
        plotted["_color"] = [
            "#b2182b" if failed else "#2166ac" for failed in rows.Failed
        ]
        plotted["_size"] = [10 if inside else 6 for inside in rows["Inside box"]]
        plot = figure(
            title=title,
            width=850,
            height=420,
            tools="pan,wheel_zoom,box_zoom,reset,save",
            x_axis_label=x_input or "First input value",
            y_axis_label=y_input or "Second input value",
        )
        plot.scatter(
            x="First input value",
            y="Second input value",
            source=_source(plotted, csv_frame=rows),
            color="_color",
            size="_size",
            alpha=0.65,
        )
        plot.add_tools(_hover(rows))
        if x_input and y_input and not boxes.empty:
            _require(boxes, ("Box", "Input", "Lower bound", "Upper bound"))
            matching = boxes
            for facet in facets:
                if facet in rows and facet in boxes:
                    value = rows[facet].iloc[0]
                    matching = (
                        matching[matching[facet].isna()]
                        if pd.isna(value)
                        else matching[matching[facet].eq(value)]
                    )
            for _, bounds in matching.groupby("Box", sort=False):
                selected = bounds[bounds.Input.isin([x_input, y_input])]
                if selected.Input.duplicated().any():
                    raise FigureContractError("Box has duplicate input bounds")
                if len(selected) == 2:
                    selected = selected.set_index("Input")
                    plot.quad(
                        left=[selected.loc[x_input, "Lower bound"]],
                        right=[selected.loc[x_input, "Upper bound"]],
                        bottom=[selected.loc[y_input, "Lower bound"]],
                        top=[selected.loc[y_input, "Upper bound"]],
                        fill_alpha=0.08,
                        line_color="black",
                        line_width=2,
                    )
        panels.append(plot)
    if not boxes.empty:
        panels.append(_table(boxes))
    return _wrap(
        "Failure regions",
        panels,
        provenance,
        "Red points fail the declared condition, blue points pass. Larger points are inside the saved full box. Rectangles show a two-input projection; membership can depend on additional inputs. Acceptance uses B confirmation, not the pictured A fit.",
    )


def design_ranking_figure(
    frame: pd.DataFrame,
    *,
    provenance: Mapping[str, str],
    facets: Sequence[str] = (
        *(name for name in CONTEXT if name != "Design family"),
        "Measure",
    ),
):
    """Family means and p10/p90 run spread, never mislabeled as mean CIs."""
    _require(
        frame, ("Design", "Mean", "10th percentile", "90th percentile", "Rank", "Runs")
    )
    if "Horizon (days)" in frame:
        family = frame.get("Design family", frame.Design)
        if (family.eq("before") & frame["Horizon (days)"].eq(180)).any():
            raise FigureContractError(
                "before at 180 days cannot enter a ranking figure"
            )
    panels = []
    for title, rows in _panels(frame, facets):
        if rows.Design.duplicated().any():
            raise FigureContractError("Designs overlap; declare additional facets")
        source = _source(rows)
        plot = figure(
            title=title,
            x_range=list(rows.Design),
            width=900,
            height=340,
            tools="pan,wheel_zoom,reset,save",
        )
        plot.segment(
            x0="Design",
            x1="Design",
            y0="10th percentile",
            y1="90th percentile",
            source=source,
            line_width=3,
            color="#777777",
        )
        plot.scatter(x="Design", y="Mean", source=source, size=12, color="#2166ac")
        plot.yaxis.axis_label = "Mean and 10th–90th percentile run spread"
        plot.add_tools(_hover(rows))
        panels.append(plot)
    return _wrap(
        "Design comparison",
        panels,
        provenance,
        "Matched relative outcomes under each family's declared input distribution. Bars show run spread, not confidence intervals for means. before at 180 days is excluded from ranking by the summary producer.",
    )


def recommendation_table(frame: pd.DataFrame, *, provenance: Mapping[str, str]):
    """Display the exact exported recommendation rows and unsupported states."""
    _require(
        frame,
        (
            "Recommendation",
            "Goal",
            "Input",
            "Tier",
            "Value or range",
            "Confidence rating",
            "Confidence basis",
            "Evidence",
        ),
    )
    table = _table(frame, max(250, min(700, len(frame) * 32 + 50)))
    for table_column in table.columns:
        if table_column.field == "Confidence rating":
            table_column.title = "Family-vs-baseline confidence"
            table_column.width = 550
    comparison_basis = " | ".join(
        dict.fromkeys(frame["Confidence basis"].fillna("unspecified").astype(str))
    )
    return _wrap(
        "Provisional recommendations",
        [table],
        provenance,
        "Family-vs-baseline confidence is the view label for CSV Confidence rating, with its comparison scope in Confidence basis. It does not rate a selected optimum or an individual box. Selected A points have no validated point interval. Ranges are sampled A-selected/B-confirmed candidates, provisional until fresh-seed reruns. Pass-share intervals do not certify every point in a continuous range. Not found, not applicable and unassessable remain separate states. "
        + f"Supplied comparison basis: {comparison_basis}.",
    )


def write_standalone_html(layout, path: str | Path, *, title: str) -> Path:
    """Write self-contained HTML with inline Bokeh resources, no CDN request."""
    destination = Path(path)
    destination.write_text(file_html(layout, INLINE, title=title), encoding="utf-8")
    return destination
