"""AVAX-day weighted descriptive KDE and exact marginal histograms for F1."""

import numpy as np
from scipy.special import ndtr

BANDWIDTH_DEX = (0.10, 0.20)
DURATION_EDGES = np.unique(np.r_[np.geomspace(2, 365, 21), 7, 14, 30, 90])
STAKE_EDGES = np.geomspace(2000, 7e6, 25)


def density(frame, minimum_days):
    """Product Gaussian KDE in log10 coordinates, truncated per kernel to support.

    Each transaction contributes its full AVAX-days as weight. Both eras use the
    same fixed bandwidths, not separately estimated bandwidths. Truncation uses
    the era's duration minimum, 365-day maximum and 2,000-AVAX stake minimum.
    The upper stake limit is the displayed 7M AVAX, not a protocol limit.
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
    norm_x = ndtr((np.log10(365) - u) / hx) - ndtr((np.log10(minimum_days) - u) / hx)
    norm_y = ndtr((np.log10(7e6) - v) / hy) - ndtr((np.log10(2000) - v) / hy)
    kx = np.exp(-0.5 * ((log_x[:, None] - u) / hx) ** 2) / (
        np.sqrt(2 * np.pi) * hx * norm_x
    )
    ky = np.exp(-0.5 * ((log_y[:, None] - v) / hy) ** 2) / (
        np.sqrt(2 * np.pi) * hy * norm_y
    )
    z = 100 * (ky * weights) @ kx.T
    z[:, (log_x < np.log10(minimum_days)) | (log_x > np.log10(365))] = np.nan
    z[log_y < np.log10(2000), :] = np.nan
    # The numerical integral is an independent check on boundary normalization.
    valid_x = (log_x >= np.log10(minimum_days)) & (log_x <= np.log10(365))
    valid_y = log_y >= np.log10(2000)
    mass = np.trapezoid(
        np.trapezoid(z[np.ix_(valid_y, valid_x)], log_x[valid_x], axis=1),
        log_y[valid_y],
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
