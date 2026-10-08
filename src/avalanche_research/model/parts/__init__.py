"""The fitted lifecycle model's behaviour, one module per part.

* :mod:`~avalanche_research.model.parts.base`: the contract every part follows and the shared constants.
* :mod:`~avalanche_research.model.parts.renewal`: :class:`RenewalLogit`, renewal within seven days.
* :mod:`~avalanche_research.model.parts.arrivals`: :class:`Arrivals`, first-ever nodes each day.
* :mod:`~avalanche_research.model.parts.returns`: :class:`ReturnHazard`, returns after more than seven days out.
* :mod:`~avalanche_research.model.parts.continuation`: :class:`Continuation`, the next duration and stake of a node
  that renews or returns.
* :mod:`~avalanche_research.model.parts.duration_transition`: :class:`DurationTransition`, a fitted transition between
  duration bands that a model variant draws the next duration from in place of the continuation table.
* :mod:`~avalanche_research.model.parts.stages`: the daily step as an ordered list of stages. Each behaviour part's
  stage lives in its own module, and the rewards and assembly stages live here.

``avalanche_research.model.fitted_blocks`` offers every name the blocks had before the split, under its earlier path.
"""
