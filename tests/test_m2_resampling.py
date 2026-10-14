"""Whole-unit weight and incomplete-member controls."""
import numpy as np
import pandas as pd
import pytest

from avalanche_research.analysis.m2_contract import ContractError
from avalanche_research.analysis.m2_resampling import (
    cluster_statistics,
    replicated_noise_share,
    scope_draws,
    validate_indices,
)


def test_unequal_cluster_sizes_use_ratio_of_sums():
    draws = np.array([[0, 1], [1, 1], [0, 0]])
    actual = cluster_statistics([1., 3., 11.], ["a", "a", "b"], draws)
    assert actual.tolist() == pytest.approx([5., 11., 2.])


def test_out_of_range_float_and_truncated_draws_refuse():
    for bad in [np.array([[0, 2], [0, 1]]), np.array([[0., 1.], [1., 0.]]), np.array([[0], [1]])]:
        with pytest.raises(ContractError):
            validate_indices(bad, 2)


def test_incomplete_saltelli_base_refuses_before_rng():
    labels = pd.DataFrame({"family": ["ramp", "ramp"], "yield_pp": [3., 3.],
                           "i": [0, 0], "block": ["A", "AB"]})
    with pytest.raises(ContractError, match="incomplete"):
        scope_draws(labels, None)


def test_replicated_noise_matches_balanced_anova_and_fixed_draws():
    values = np.arange(64)[:, None] * 10 + np.array([-3., -2., -1., 0., 0., 1., 2., 3.])
    draws = np.tile(np.arange(64), (1000, 1))
    result = replicated_noise_share(values, draws)
    within = 28 / 7
    between = np.var(np.arange(64) * 10, ddof=1) - within / 8
    expected = within / (within + between)
    assert result["noise_share"] == pytest.approx(expected)
    assert result["within_variance"] == pytest.approx(within)
    assert result["between_variance_raw"] == pytest.approx(between)
    assert result["ci_low"] == pytest.approx(expected)
    assert result["ci_high"] == pytest.approx(expected)
    assert result["status"] == "assessable"
    assert replicated_noise_share(values * 3 + 17, draws)["noise_share"] == pytest.approx(expected)


def test_noise_boundary_constant_and_missing_repeat_are_explicit():
    draws = np.tile(np.arange(64), (1000, 1))
    repeated = np.tile(np.arange(8.), (64, 1))
    result = replicated_noise_share(repeated, draws)
    assert result["noise_share"] == 1 and result["between_truncated"]
    assert replicated_noise_share(np.ones((64, 8)), draws)["status"] == "unassessable"
    with pytest.raises(ContractError):
        replicated_noise_share(repeated[:, :7], draws)
