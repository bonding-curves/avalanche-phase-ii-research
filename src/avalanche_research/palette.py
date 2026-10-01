"""Stable light-chart quantity hues with stroke patterns for duration weighting."""

QUANTITY_COLORS = {
    "nodes": "#3566a3",
    "addresses": "#7b4b94",
    "commitments": "#62676f",
    "stake": "#237a57",
    "duration": "#b85c00",
    "stake_duration": "#787500",
    "rewards": "#b84055",
}

DURATION_COMPARISON_COLORS = {
    "commitment_weighted": QUANTITY_COLORS["duration"],
    "stake_weighted": QUANTITY_COLORS["stake_duration"],
}

WEIGHTING_LINE_DASH = {"commitment_weighted": "solid", "stake_weighted": "dashed"}

# Reward and admission designs, in hues no quantity uses. Today's chain is drawn in ink.
MECHANISM_COLORS = {
    "Chain today": "#1b1b1b",
    "ACP-285 settings": "#0e7c86",
    "Tenure boost": "#9c3d8f",
    "Quadratic curve": "#7a5230",
    "Quadratic curve, today's issuance": "#50607a",
}
