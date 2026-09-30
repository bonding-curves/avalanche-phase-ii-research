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
    scores = {p: Renewal(probability=p).log_prob(inputs, decisions) for p in (0.70, 0.80, 0.90)}
    assert max(scores, key=scores.get) == 0.80


def test_probability_outside_bounds_raises():
    with pytest.raises(ValueError):
        Renewal(probability=1.2)
