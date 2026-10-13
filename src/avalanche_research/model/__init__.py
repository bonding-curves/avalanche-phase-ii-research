"""Avalanche staking subsystem model: typed units, source-linked protocol rules, and checks."""

# The model version the Foundation sees. v0.6 was the July behaviour work; v0.7 is the lifecycle model on the cadCAD and
# Param engine; v0.8 fits its behaviour to the chain. Each run's long table carries it, so a stored result names the
# model that made it.
MODEL_VERSION = "0.8.0"

# The variant in ``variants.VARIANTS`` that is the released model. ``avalanche model run`` runs it by default.
RELEASED_MODEL = "v0.8.0"
