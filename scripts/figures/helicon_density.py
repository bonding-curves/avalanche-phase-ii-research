"""AVAX-day weighted descriptive KDE and exact marginal histograms for F1."""

import numpy as np
from scipy.special import ndtr

BANDWIDTH_DEX = (0.10, 0.20)
DURATION_EDGES = np.unique(np.r_[np.geomspace(2, 365, 21), 7, 14, 30, 90])
STAKE_EDGES = np.geomspace(2000, 7e6, 25)


def density(frame):
    """Product Gaussian KDE in log10 coordinates over the full displayed domain.

    Each transaction contributes its full AVAX-days as weight. Both eras use the
    same fixed bandwidths, not separately estimated bandwidths. Each kernel is
    normalized within the shared plot rectangle. Tails outside observed or
    protocol bounds are smoothing, not additional recorded commitments.
    """
    log_x = np.unique(
        np.r_[np.linspace(np.log10(1.8), np.log10(410), 181), np.log10([2, 14, 365])]
    )
    log_y = np.unique(
        np.r_[np.linspace(np.log10(1600), np.log10(7e6), 181), np.log10(2000)]
    )
    hx, hy = BANDWIDTH_DEX
    u, v = (
        np.log10(frame.duration_days.to_numpy()),
        np.log10(frame.stake_avax.to_numpy()),
    )
    weights = frame.avax_days.to_numpy()
    weights = weights / weights.sum()
    norm_x = ndtr((log_x[-1] - u) / hx) - ndtr((log_x[0] - u) / hx)
    norm_y = ndtr((log_y[-1] - v) / hy) - ndtr((log_y[0] - v) / hy)
    kx = np.exp(-0.5 * ((log_x[:, None] - u) / hx) ** 2) / (
        np.sqrt(2 * np.pi) * hx * norm_x
    )
    ky = np.exp(-0.5 * ((log_y[:, None] - v) / hy) ** 2) / (
        np.sqrt(2 * np.pi) * hy * norm_y
    )
    z = 100 * (ky * weights) @ kx.T
    # The numerical integral is an independent check on boundary normalization.
    mass = np.trapezoid(
        np.trapezoid(z, log_x, axis=1),
        log_y,
    )
    if not np.isclose(mass, 100, atol=0.2):
        raise ValueError(f"KDE does not conserve normalized weight: {mass}")
    return 10**log_x, 10**log_y, z, float(mass)


def marginals(frame):
    result = []
    for column, edges in (
        ("duration_days", DURATION_EDGES),
        ("stake_avax", STAKE_EDGES),
    ):
        weights, _ = np.histogram(frame[column], bins=edges, weights=frame.avax_days)
        counts, _ = np.histogram(frame[column], bins=edges)
        if counts.sum() != len(frame) or not np.isclose(
            weights.sum(), frame.avax_days.sum()
        ):
            raise ValueError(f"Histogram omitted commitments: {column}")
        result.append(
            {
                "lo": edges[:-1],
                "hi": edges[1:],
                "avax_days": weights,
                "share": 100 * weights / frame.avax_days.sum(),
                "count": counts,
            }
        )
    return result
