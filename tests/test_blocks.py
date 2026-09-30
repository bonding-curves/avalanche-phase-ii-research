"""The behaviour block interface: sources, one writer per variable, and sample against log_prob."""

import numpy as np
import pytest

from avalanche_research.model.blocks import (
    BehaviourBlock,
    Renewal,
    behavioural,
    check_sources,
    check_writers,
)


def test_renewal_declares_its_source_and_evidence():
    sources = Renewal().sources()
    assert sources["probability"]["source"] == "observed moment"
    assert "7ca051e" in sources["probability"]["evidence"]
    check_sources([Renewal()])


def test_a_parameter_without_a_listed_source_or_evidence_cannot_be_declared():
    with pytest.raises(ValueError):
        behavioural(0.5, (0, 1), "guess", "doc", "evidence")
    with pytest.raises(ValueError):
        behavioural(0.5, (0, 1), "assumed", "doc", "")


def test_two_writers_of_one_variable_are_refused():
    class Other(BehaviourBlock):
        writes = ("renewed_commitments",)

    check_writers([Renewal()])
    with pytest.raises(ValueError):
        check_writers([Renewal(), Other()])


def test_an_undeclared_numeric_parameter_is_refused():
    import param

    class Loose(BehaviourBlock):
        rate = param.Number(default=0.1)

    with pytest.raises(ValueError):
        check_sources([Loose()])


def test_sampled_share_recovers_the_probability_and_log_prob_peaks_there():
    rng = np.random.default_rng(7)
    inputs = {"ending_commitments": np.zeros(200_000)}
    decisions = Renewal().sample(inputs, rng)
    assert decisions.mean() == pytest.approx(0.801541, abs=0.005)
    scores = {p: Renewal().with_value("probability", p, "assumed", "grid").log_prob(inputs, decisions) for p in (0.70, 0.80, 0.90)}
    assert max(scores, key=scores.get) == 0.80


def test_probability_outside_bounds_raises():
    with pytest.raises(ValueError):
        Renewal(probability=1.2)


def test_boundary_probabilities_give_the_exact_likelihood():
    inputs = {"ending_commitments": np.zeros(2)}
    never = Renewal().with_value("probability", 0.0, "assumed", "boundary test")
    always = Renewal().with_value("probability", 1.0, "assumed", "boundary test")
    assert never.log_prob(inputs, [True, False]) == float("-inf")
    assert never.log_prob(inputs, [False, False]) == 0.0
    assert always.log_prob(inputs, [True, False]) == float("-inf")
    assert always.log_prob(inputs, [True, True]) == 0.0


def test_decisions_must_match_the_inputs_one_for_one():
    with pytest.raises(ValueError):
        Renewal().log_prob({"ending_commitments": np.zeros(1)}, [True, False, True])
    with pytest.raises(ValueError):
        Renewal().log_prob({"ending_commitments": np.zeros(2)}, [0.5, 1])


def test_an_instance_value_needs_its_own_source():
    unlabelled = Renewal(probability=0.5)
    assert unlabelled.sources()["probability"]["source"] == "unlabelled"
    with pytest.raises(ValueError):
        check_sources([unlabelled])
    labelled = Renewal().with_value("probability", 0.5, "fitted", "a fit, run and commit")
    assert labelled.sources()["probability"] == {"value": 0.5, "bounds": (0.0, 1.0), "source": "fitted", "evidence": "a fit, run and commit"}
    check_sources([labelled])
    assert Renewal().sources()["probability"]["source"] == "observed moment"
    with pytest.raises(ValueError):
        Renewal(provenance={"probability": {"source": "guess", "evidence": "x"}})
