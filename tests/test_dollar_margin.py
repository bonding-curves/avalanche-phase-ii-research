"""The concave dollar margin in renewal (ML13, D16): off by default, zero at the origin, concave in the reward."""

from __future__ import annotations

import numpy as np
import pytest
from test_fitted_lifecycle import path
from test_v09_price_security import AVAX, REFERENCE, START

from avalanche_research.mechanisms import ChainReward
from avalanche_research.model.engine import run
from avalanche_research.model.parts.renewal import margin_shift
from avalanche_research.model.parts.stages import Day, RunSettings

ORIGIN_RATE, ORIGIN_PRICE, COST = 0.0595, 14.5, 5000.0
FLAT = {"price0_usd": ORIGIN_PRICE, "price_drift_pa": 0.0, "price_volatility_pa": 0.0}


def shift(per_avax: float, stake_avax: float = 2000.0) -> float:
    settings = RunSettings(large_navax=None, renewal_response=0.0, entry_response=0.0, mechanism=ChainReward(), scheduled={},
                           margin_response=0.19, node_cost_usd_pa=COST, margin_curvature_usd=1000.0,
                           margin_reference_usd_per_avax=ORIGIN_RATE * ORIGIN_PRICE)
    day = Day(t=0, start=START, draw=None, blocks=None, renewal_gap=0.0, entry_gap=0.0, settings=settings,
              margin_usd_per_avax=per_avax)
    return float(margin_shift(np.array([int(stake_avax * AVAX)]), day)[0])


def test_the_margin_needs_a_price_path():
    with pytest.raises(ValueError, match="price path"):
        REFERENCE["fitted"](margin_response=0.19)


def test_the_margin_is_zero_at_the_origin_and_a_lower_price_lowers_renewal():
    assert shift(ORIGIN_RATE * ORIGIN_PRICE) == 0.0
    assert shift(ORIGIN_RATE * ORIGIN_PRICE / 2) < 0.0 < shift(ORIGIN_RATE * ORIGIN_PRICE * 2)


def test_a_rate_cut_matters_most_near_break_even():
    # A 2,000 AVAX validator at 5.95% breaks even on a 5,000 dollar cost near 42 dollars. A one-point cut lowers its
    # log-odds by more as the price rises toward break-even, so from the origin's 14.50 a bear market shrinks the cut's
    # effect and a bull market toward break-even enlarges it (D16-F16).
    def cut(price):
        return shift((ORIGIN_RATE - 0.01) * price) - shift(ORIGIN_RATE * price)

    assert cut(5.0) > cut(14.5) > cut(42.0) and cut(42.0) < 0.0
    assert cut(42.0) < cut(200.0)


def test_at_a_flat_price_under_the_chains_rule_the_margin_changes_nothing():
    off, on = run(REFERENCE["fitted"](**FLAT)), run(REFERENCE["fitted"](**FLAT, margin_response=0.19))
    for variable in ("active_validators", "active_validator_stake_navax"):
        assert path(off, variable) == path(on, variable)


def test_the_margin_settings_enter_the_specification_only_when_set():
    plain, priced = REFERENCE["fitted"](**FLAT), REFERENCE["fitted"](**FLAT, margin_response=0.19)
    assert plain.specification_hash() != priced.specification_hash()
    assert REFERENCE["fitted"](**FLAT, margin_response=0.0).specification_hash() == plain.specification_hash()


def test_a_falling_price_with_the_margin_on_lowers_renewal():
    # A strong response makes the direction plain in a 12-day run: the price falls about 30%, every renewing
    # validator's margin falls with it, and fewer renew than with the margin off.
    fall = {"price0_usd": ORIGIN_PRICE, "price_drift_pa": -10.0, "price_volatility_pa": 0.0}
    off, on = run(REFERENCE["fitted"](**fall)), run(REFERENCE["fitted"](**fall, margin_response=5.0))
    assert path(on, "active_validators")[-1] < path(off, "active_validators")[-1]
