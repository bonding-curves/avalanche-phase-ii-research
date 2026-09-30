"""Stable light-chart quantity hues with stroke patterns for duration weighting."""

QUANTITY_COLORS = {
    "nodes": "#3566a3",
    "addresses": "#7b4b94",
    "commitments": "#62676f",
    "stake": "#237a57",
    "duration": "#b85c00",
    "stake_duration": "#087f8c",
    "rewards": "#b84055",
}

DURATION_COMPARISON_COLORS = {
    "commitment_weighted": QUANTITY_COLORS["duration"],
    "stake_weighted": QUANTITY_COLORS["duration"],
}

WEIGHTING_LINE_DASH = {"commitment_weighted": "solid", "stake_weighted": "dashed"}
