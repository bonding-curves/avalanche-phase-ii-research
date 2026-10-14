"""Summary-only rendering controls with embedded raw values and provenance."""

import hashlib

import numpy as np
import pandas as pd
import pytest
from bokeh.models import (
    ColumnDataSource,
    CustomJS,
    DataTable,
    Div,
    HoverTool,
    LinearColorMapper,
    Plot,
    Select,
    Title,
)

from avalanche_research.analysis.report_figures import (
    FigureContractError,
    correlation_heatmap,
    design_ranking_figure,
    recommendation_table,
    region_figure,
    sobol_figure,
    tree_figure,
    write_standalone_html,
)

PROVENANCE = {
    "sweep_id": "synthetic-fixture",
    "model_version": "fixture-v1",
    "code_sha": "fixture-code",
}
CONTEXT = {
    "Design family": "after",
    "Competing yield (%)": 3.0,
    "Horizon (days)": 365,
    "Renewal response": "low",
    "Entry response": "middle",
}


def sources(layout):
    return list(layout.select({"type": ColumnDataSource}))


def correlation_data():
    return pd.DataFrame(
        [
            {
                **CONTEXT,
                "Measure": "issuance_saved",
                "Input": "rate",
                "Coefficient value": -0.6,
                "Interval low (95%)": -0.8,
                "Interval high (95%)": -0.3,
                "Status": "assessable",
                "Starred (Benjamini-Hochberg 5%)": None,
            },
            {
                **CONTEXT,
                "Measure": "constant",
                "Input": "rate",
                "Coefficient value": np.nan,
                "Interval low (95%)": np.nan,
                "Interval high (95%)": np.nan,
                "Status": "constant_kpi",
                "Starred (Benjamini-Hochberg 5%)": None,
            },
        ]
    )


def tree_data():
    return pd.DataFrame(
        [
            {
                **CONTEXT,
                "Measure": "margin",
                "Node": 0,
                "Parent node": np.nan,
                "Split input": "rate",
                "Split value": 0.5,
                "Leaf": False,
                "Runs at node": 10,
                "Share meeting threshold": 0.6,
            },
            {
                **CONTEXT,
                "Measure": "margin",
                "Node": 1,
                "Parent node": 0,
                "Split input": "",
                "Split value": np.nan,
                "Leaf": True,
                "Runs at node": 4,
                "Share meeting threshold": 0.25,
            },
            {
                **CONTEXT,
                "Measure": "margin",
                "Node": 2,
                "Parent node": 0,
                "Split input": "",
                "Split value": np.nan,
                "Leaf": True,
                "Runs at node": 6,
                "Share meeting threshold": 5 / 6,
            },
        ]
    )


def sobol_data():
    return pd.DataFrame(
        [
            {
                **CONTEXT,
                "Measure": "issuance_saved",
                "Input": "renewal_response",
                "First-order index": -0.12,
                "First-order low (95%)": -0.3,
                "First-order high (95%)": 0.2,
                "Total-order index": 1.2,
                "Total-order low (95%)": 0.9,
                "Total-order high (95%)": 1.4,
                "Converged": False,
                "Largest change when the sample size doubled": 0.027211364,
                "Base sample size": 512,
                "status": "assessable",
                "convergence_status": "assessable",
            }
        ]
    )


def design_data():
    return pd.DataFrame(
        [
            {
                **CONTEXT,
                "Measure": "issuance_saved",
                "Design": "after",
                "Mean": 0.2,
                "10th percentile": -0.3,
                "90th percentile": 0.6,
                "Rank": 1,
                "Runs": 128,
            }
        ]
    )


def recommendation_data():
    return pd.DataFrame(
        [
            {
                "Recommendation": "provisional box",
                "Goal": "issuance_saved",
                "Input": "rate",
                "Tier": "per-goal range",
                "Value or range": "not found",
                "Confidence rating": "not rated",
                "Confidence basis": "Family against matched baseline across nine cells and shared anchors",
                "Evidence": "synthetic.csv",
                "Status": "not_found",
                "Pass share": 0.7,
            }
        ]
    )


def test_heatmap_exact_values_missing_state_and_symmetric_diverging_scale():
    frame = correlation_data()
    layout = correlation_heatmap(frame, provenance=PROVENANCE)
    source = next(
        source for source in sources(layout) if "Coefficient value" in source.data
    )
    assert source.data["Coefficient value"][0] == -0.6
    assert np.isnan(source.data["Coefficient value"][1])
    assert source.data["Status"] == ["assessable", "constant_kpi"]
    assert source.data["Starred (Benjamini-Hochberg 5%)"] == [None, None]
    assert (
        source.tags[0]["canonical_frame_csv_sha256"]
        == hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()
    )
    mapper = next(iter(layout.select({"type": LinearColorMapper})))
    assert mapper.low == -mapper.high
    assert mapper.nan_color == "#bdbdbd"


def test_heatmap_stars_use_only_supplied_BH_verdicts():
    base = correlation_data().iloc[:1]
    frame = pd.concat(
        [base.assign(Measure="a"), base.assign(Measure="b"), base.assign(Measure="c")]
    )
    frame["Starred (Benjamini-Hochberg 5%)"] = [True, False, None]
    layout = correlation_heatmap(frame, provenance=PROVENANCE)
    source = next(
        source for source in sources(layout) if "Coefficient value" in source.data
    )
    assert source.data["_star"] == ["*", "", "?"]
    frame["Starred (Benjamini-Hochberg 5%)"] = ["True", "False", "unassessable"]
    csv_layout = correlation_heatmap(frame, provenance=PROVENANCE)
    csv_source = next(
        source for source in sources(csv_layout) if "Coefficient value" in source.data
    )
    assert csv_source.data["_star"] == ["*", "", "?"]


def test_horizons_yields_and_responses_are_separate_panels():
    frame = correlation_data().iloc[:1]
    data = pd.concat(
        [
            frame,
            frame.assign(**{"Horizon (days)": 180}),
            frame.assign(**{"Competing yield (%)": 7}),
            frame.assign(**{"Entry response": "high"}),
        ]
    )
    layout = correlation_heatmap(data, provenance=PROVENANCE)
    assert sum("Coefficient value" in source.data for source in sources(layout)) == 4
    with pytest.raises(FigureContractError, match="overlap"):
        correlation_heatmap(data, provenance=PROVENANCE, facets=[])


def test_multi_scope_browser_has_one_visible_panel_and_retains_hidden_models(tmp_path):
    frame = correlation_data().iloc[:1]
    data = pd.concat(
        [
            frame,
            frame.assign(**{"Horizon (days)": 180}),
            frame.assign(**{"Competing yield (%)": 7}),
        ]
    )
    layout = correlation_heatmap(data, provenance=PROVENANCE)
    selector = next(iter(layout.select({"type": Select})))
    assert len(selector.options) == 3
    assert selector.value == "0"
    callback = next(iter(layout.select({"type": CustomJS})))
    assert len(callback.args["panels"]) == 3
    assert callback.args["container"].children == [callback.args["panels"][0]]
    assert "container.children" in callback.code
    assert (
        len(
            [source for source in sources(layout) if "Coefficient value" in source.data]
        )
        == 3
    )
    html = write_standalone_html(
        layout, tmp_path / "browser.html", title="Scopes"
    ).read_text()
    assert "Number(cb_obj.value)" in html
    assert "Horizon (days): 180" in html


def test_tree_graph_uses_real_parents_and_retains_all_node_counts():
    layout = tree_figure(tree_data(), provenance=PROVENANCE)
    source = next(source for source in sources(layout) if "Node" in source.data)
    assert source.data["Runs at node"] == [10, 4, 6]
    assert source.data["_x"] == [0.5, 0, 1]
    assert source.data["_y"] == [0, -1, -1]
    plot = next(iter(layout.select({"type": Plot})))
    assert plot.x_range.start <= -0.4 and plot.x_range.end >= 1.4
    assert plot.y_range.start <= -1.4 and plot.y_range.end >= 0.4
    invalid = tree_data()
    invalid.loc[1, "Parent node"] = 99
    with pytest.raises(FigureContractError, match="parent"):
        tree_figure(invalid, provenance=PROVENANCE)


def test_deep_tree_has_integer_capped_viewport_without_dropping_nodes(tmp_path):
    data = pd.concat([tree_data().iloc[:1]] * 25, ignore_index=True)
    data["Node"] = range(25)
    data["Parent node"] = [np.nan, *[2 * ((node - 1) // 2) for node in range(1, 25)]]
    data["Leaf"] = [node % 2 == 1 or node == 24 for node in range(25)]
    layout = tree_figure(data, provenance=PROVENANCE)
    plot = next(iter(layout.select({"type": Plot})))
    assert plot.height == 900
    assert isinstance(plot.height, int)
    source = next(source for source in sources(layout) if "Node" in source.data)
    assert source.data["Node"] == list(range(25))
    assert min(source.data["_y"]) == -12
    assert plot.y_range.start < -12.4 and plot.y_range.end > 0.4
    html = write_standalone_html(layout, tmp_path / "deep.html", title="Deep")
    assert html.exists()


def test_tree_disconnected_cycle_is_not_silently_dropped():
    data = tree_data()
    data.loc[1, "Parent node"] = 2
    data.loc[2, "Parent node"] = 1
    with pytest.raises(FigureContractError, match="cyclic"):
        tree_figure(data, provenance=PROVENANCE)


def test_regression_tree_displays_target_values_without_invented_share_mapper():
    frame = tree_data().drop(columns="Share meeting threshold")
    frame["Target type"] = "regression"
    frame["Node mean target"] = [20.0, -5.0, 40.0]
    layout = tree_figure(frame, provenance=PROVENANCE)
    source = next(source for source in sources(layout) if "Node" in source.data)
    assert source.data["Node mean target"] == [20.0, -5.0, 40.0]
    assert "leaf: -5" in source.data["_label"]
    assert "Share meeting threshold" not in source.data
    assert not list(layout.select({"type": LinearColorMapper}))


def test_sobol_values_outside_unit_interval_are_retained_with_intervals():
    layout = sobol_figure(sobol_data(), provenance=PROVENANCE)
    source = next(
        source for source in sources(layout) if "First-order index" in source.data
    )
    assert source.data["First-order index"] == [-0.12]
    assert source.data["Total-order high (95%)"] == [1.4]
    assert source.data["Converged"] == [False]


def test_region_points_and_all_box_bounds_remain_available():
    points = pd.DataFrame(
        [
            {
                **CONTEXT,
                "Failure condition": "margin",
                "Run": "a",
                "First input value": 0.2,
                "Second input value": 0.3,
                "Failed": True,
                "Inside box": True,
            },
            {
                **CONTEXT,
                "Failure condition": "margin",
                "Run": "b",
                "First input value": 0.5,
                "Second input value": 0.6,
                "Failed": False,
                "Inside box": False,
            },
        ]
    )
    boxes = pd.DataFrame(
        [
            {
                **CONTEXT,
                "Failure condition": "margin",
                "Box": 0,
                "Input": name,
                "Lower bound": 0,
                "Upper bound": 0.4,
                "Found": False,
            }
            for name in ("rate", "renewal", "entry")
        ]
    )
    layout = region_figure(
        points, boxes, provenance=PROVENANCE, x_input="rate", y_input="renewal"
    )
    source = next(source for source in sources(layout) if "Failed" in source.data)
    assert source.data["Failed"] == [True, False]
    assert source.data["_color"] == ["#b2182b", "#2166ac"]
    table = next(source for source in sources(layout) if "Lower bound" in source.data)
    assert table.data["Input"] == ["rate", "renewal", "entry"]


def test_design_run_spread_is_not_mean_confidence_interval():
    layout = design_ranking_figure(design_data(), provenance=PROVENANCE)
    source = next(
        source for source in sources(layout) if "10th percentile" in source.data
    )
    assert source.data["10th percentile"] == [-0.3]
    text = " ".join(div.text for div in layout.select({"type": Div}))
    assert "run spread" in text
    assert "not confidence intervals for means" in text


def test_before180_cannot_appear_in_ranking_figure():
    data = design_data().assign(**{"Design family": "before", "Horizon (days)": 180})
    with pytest.raises(FigureContractError, match="before at 180"):
        design_ranking_figure(data, provenance=PROVENANCE)


def test_unknown_box_membership_is_not_plotted_as_false():
    data = pd.DataFrame(
        {
            "First input value": [0.1],
            "Second input value": [0.2],
            "Failed": [True],
            "Inside box": [None],
        }
    )
    with pytest.raises(FigureContractError, match="Inside box must be Boolean"):
        region_figure(data, pd.DataFrame(), provenance=PROVENANCE)


@pytest.mark.parametrize(
    "builder,data",
    [
        (correlation_heatmap, correlation_data),
        (tree_figure, tree_data),
        (sobol_figure, sobol_data),
        (design_ranking_figure, design_data),
        (recommendation_table, recommendation_data),
    ],
)
def test_each_figure_serializes_standalone_with_provenance_and_raw_source(
    tmp_path, builder, data
):
    frame = data()
    layout = builder(frame, provenance=PROVENANCE)
    path = write_standalone_html(layout, tmp_path / "figure.html", title="Fixture")
    html = path.read_text()
    assert "synthetic-fixture" in html
    assert "fixture-v1" in html
    assert "fixture-code" in html
    assert 'src="https://cdn.bokeh.org' not in html
    assert "canonical_frame_csv_sha256" in html
    assert len(html) > 100_000


def test_region_serializes_standalone_and_no_result_empty_frame(tmp_path):
    points = pd.DataFrame(
        columns=["First input value", "Second input value", "Failed", "Inside box"]
    )
    layout = region_figure(points, pd.DataFrame(), provenance=PROVENANCE)
    html = write_standalone_html(
        layout, tmp_path / "region.html", title="Empty"
    ).read_text()
    assert "No rows supplied. No result inferred." in html


def test_required_schema_and_provenance_refused():
    with pytest.raises(FigureContractError, match="Missing report columns"):
        correlation_heatmap(pd.DataFrame(), provenance=PROVENANCE)
    with pytest.raises(FigureContractError, match="Provenance"):
        recommendation_table(recommendation_data(), provenance={})


def test_sobol_selected_facet_visibly_displays_failed_rule_and_source_status():
    frame = sobol_data()
    layout = sobol_figure(frame, provenance=PROVENANCE)
    titles = [model.text for model in layout.select({"type": Title})]
    assert any(
        "Convergence: FAILED" in title
        and "0.027211364" in title
        and "limit: 0.02" in title
        and "N=512" in title
        for title in titles
    )
    visible_text = " ".join(model.text for model in layout.select({"type": Div}))
    assert "Source status: assessable" in visible_text
    assert "1 failed" in visible_text
    assert "maximum movement across all first/total input indices" in visible_text
    hover = next(iter(layout.select({"type": HoverTool})))
    assert ("status", "@{status}") in hover.tooltips
    assert ("convergence_status", "@{convergence_status}") in hover.tooltips
    assert (
        "Largest change when the sample size doubled",
        "@{Largest change when the sample size doubled}",
    ) in hover.tooltips
    source = next(s for s in sources(layout) if "First-order index" in s.data)
    assert source.data["Convergence interpretation"] == ["failed"]
    assert (
        source.tags[0]["canonical_frame_csv_sha256"]
        == hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()
    )
    assert frame.columns.tolist() == source.tags[0]["columns"]


def test_sobol_status_and_undefined_details_switch_with_whole_facet(tmp_path):
    failed = sobol_data()
    passed = failed.assign(
        **{
            "Competing yield (%)": 7.0,
            "Converged": True,
            "Largest change when the sample size doubled": 0.0123,
        }
    )
    undefined = failed.assign(
        **{
            "Horizon (days)": 180,
            "Converged": pd.NA,
            "Largest change when the sample size doubled": np.nan,
            "First-order index": np.nan,
            "Total-order index": np.nan,
            "status": "unassessable",
            "convergence_status": "unassessable",
            "reason": "constant KPI",
            "convergence_reason": "undefined index",
        }
    )
    layout = sobol_figure(pd.concat((failed, passed, undefined)), provenance=PROVENANCE)
    selector = next(iter(layout.select({"type": Select})))
    callback = next(iter(layout.select({"type": CustomJS})))
    assert len(selector.options) == len(callback.args["panels"]) == 3
    labels = [label for _, label in selector.options]
    assert "FAILED" in labels[0] and "3.0" in labels[0]
    assert "CONVERGED" in labels[1] and "7.0" in labels[1]
    assert "UNDEFINED" in labels[2] and "180" in labels[2]
    assert callback.args["container"].children == [callback.args["panels"][0]]
    for panel, label in zip(callback.args["panels"], labels, strict=True):
        assert panel.name == label
        assert len(list(panel.select({"type": Plot}))) == 1
    missing_panel = callback.args["panels"][2]
    assert len(list(missing_panel.select({"type": DataTable}))) == 1
    assert "UNDEFINED" in missing_panel.children[0].text
    assert "Source status: unassessable" in missing_panel.children[0].text
    assert "max movement: undefined" in missing_panel.children[0].text
    # The undefined table is a child of its facet, never an extra Scope option.
    html = write_standalone_html(
        layout, tmp_path / "scoped-sobol.html", title="Sobol"
    ).read_text()
    assert "container.children = [panels[Number(cb_obj.value)]]" in html
    assert "Details 4" not in html


@pytest.mark.parametrize(
    "flag,movement",
    [
        (True, 0.027),
        (False, 0.02),
        (False, np.nan),
        (None, 0.03),
        ("unknown", 0.03),
        (1, 0.03),
        (False, float("inf")),
        (False, -0.03),
    ],
)
def test_sobol_flag_or_movement_mutation_cannot_hide_a_failure(flag, movement):
    frame = sobol_data().assign(
        **{"Converged": flag, "Largest change when the sample size doubled": movement}
    )
    with pytest.raises(FigureContractError, match="Converged|convergence|Convergence"):
        sobol_figure(frame, provenance=PROVENANCE)


def test_sobol_exact_limit_is_visibly_converged_and_missing_source_status_refuses():
    frame = sobol_data().assign(
        **{"Converged": True, "Largest change when the sample size doubled": 0.02}
    )
    layout = sobol_figure(frame, provenance=PROVENANCE)
    assert any(
        "Convergence: CONVERGED" in model.text
        for model in layout.select({"type": Title})
    )
    for column in (
        "status",
        "convergence_status",
        "Converged",
        "Largest change when the sample size doubled",
    ):
        with pytest.raises(FigureContractError, match="Missing report columns"):
            sobol_figure(frame.drop(columns=column), provenance=PROVENANCE)


def test_recommendation_confidence_alias_and_point_range_limits_are_visible():
    frame = recommendation_data().assign(
        **{
            "Confidence rating": "High",
            "Value or range": 0.052418318344280124,
            "Tier": "point estimate",
            "Evidence": "Observed A-only point; no validated point interval",
        }
    )
    layout = recommendation_table(frame, provenance=PROVENANCE)
    table = next(iter(layout.select({"type": DataTable})))
    confidence = next(c for c in table.columns if c.field == "Confidence rating")
    assert confidence.title == "Family-vs-baseline confidence"
    assert any(c.field == "Confidence basis" for c in table.columns)
    assert any(c.field == "Evidence" for c in table.columns)
    assert table.source.data["Confidence rating"] == ["High"]
    assert table.source.data["Confidence basis"] == frame["Confidence basis"].tolist()
    assert table.source.data["Evidence"] == frame.Evidence.tolist()
    visible = " ".join(model.text for model in layout.select({"type": Div}))
    assert "view label for CSV Confidence rating" in visible
    assert frame["Confidence basis"].iloc[0] in visible
    assert "does not rate a selected optimum or an individual box" in visible
    assert "Selected A points have no validated point interval" in visible
    assert (
        "sampled A-selected/B-confirmed candidates, provisional until fresh-seed reruns"
        in visible
    )
    assert (
        table.source.tags[0]["canonical_frame_csv_sha256"]
        == hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()
    )
    assert "Family-vs-baseline confidence" not in frame.columns


def test_recommendation_confidence_basis_cannot_be_dropped_from_view():
    with pytest.raises(FigureContractError, match="Confidence basis"):
        recommendation_table(
            recommendation_data().drop(columns="Confidence basis"),
            provenance=PROVENANCE,
        )
