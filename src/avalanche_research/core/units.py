"""Units as AvalancheGo uses them: amounts in nAVAX integers, rates in millionths, durations in seconds."""

from __future__ import annotations

NAVAX_PER_AVAX = 1_000_000_000
NANOSECONDS_PER_SECOND = 1_000_000_000
SECONDS_PER_DAY = 86_400
# vms/platformvm/reward/config.go: PercentDenominator = 1_000_000
PERCENT_DENOMINATOR = 1_000_000
