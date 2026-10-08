"""The fitted lifecycle model's behaviour, one module per part.

* :mod:`~avalanche_research.model.parts.base`: the contract every part follows and the shared constants.
* :mod:`~avalanche_research.model.parts.renewal`: :class:`RenewalLogit`, renewal within seven days.
* :mod:`~avalanche_research.model.parts.arrivals`: :class:`Arrivals`, first-ever nodes each day.
* :mod:`~avalanche_research.model.parts.returns`: :class:`ReturnHazard`, returns after more than seven days out.
* :mod:`~avalanche_research.model.parts.continuation`: :class:`Continuation`, the next duration and stake of a node
  that renews or returns.

``avalanche_research.model.fitted_blocks`` offers every name of these modules under its earlier path.
"""
