from datetime import date

from avalanche_research.core import clock
from avalanche_research.model.protocol import MAINNET_UPGRADES


def test_the_lockbox_starts_at_granite():
    granite = next(u for u in MAINNET_UPGRADES.upgrades if u.name == "granite")
    assert clock.LOCKBOX_START == granite.activated_at
    assert clock.LOCKBOX_START.utcoffset().total_seconds() == 0
    assert clock.LOCKBOX_FIRST_DAY == date(2025, 11, 19)


def test_today_s_three_definitions_agree_with_it():
    from avalanche_research import staking_renewal
    from avalanche_research.mechanisms import cohort
    from avalanche_research.model import replay

    assert cohort.LOCKBOX_START == clock.LOCKBOX_START
    assert staking_renewal.LOCKBOX_START.to_pydatetime() == clock.LOCKBOX_START
    assert replay.LOCKBOX_FIRST_DAY == clock.LOCKBOX_FIRST_DAY
