"""Stylised-fact tests SF1 to SF10 for simulated Avalanche staking paths.

The ten facts are measured on the Avalanche record before the held-back period, which starts on 19 November 2025.
Each test computes one statistic per path with the same rule the record is measured by, takes the median over paths,
and compares it with a band. SF1 to SF3 follow the price generator's pass rule, fixed before any generator ran: causal
labels, a two-state Markov-switching fit and the Lunde-Timmermann rule, with the record's recomputed value as the
target. SF4 to SF10 follow the record study's estimators.

Dependencies: numpy, pandas, scipy. Nothing reads data outside the frames passed in.

Input: a list of paths. Each path is a pandas DataFrame indexed by consecutive calendar days, with these columns.
Only price_usd is required. A test whose columns are missing returns passed=None and is reported as not applicable.

| Column | Meaning | Tests |
| --- | --- | --- |
| price_usd | AVAX price, USD | all |
| staked_avax | validator plus delegated stake at the day's close, AVAX | SF4, SF5 |
| active_validators | validators active at the day's close | SF6 |
| endings | validator commitments that ended that day | SF7, SF8 |
| renewed | of those, how many the same node followed with a new commitment within 7 days | SF7, SF8 |
| first_ever | first-ever validator commitments started that day | SF9 |
| reward_rate_pct_pa | one-year validator reward rate offered that day, percent of stake a year | SF10a |
| lending_yield_pct_pa | AVAX lending yield (Aave v3 WAVAX supply in the record), percent a year | SF10b |
| regime | optional "bull", "bear" or "range" label; SF9 and SF10b use it when present, the causal rule otherwise | SF9, SF10b |

Use:
    results = evaluate(paths)          # pandas DataFrame, one row per check
    failures(results)                  # rows that ran and failed
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

YEAR = 365
LOOK = 91          # pass rule: trailing window of the causal class rule, days
THR = 0.20         # pass rule: bull above +0.20 log, bear below -0.20 log over the trailing window
MIN_CLASS_N = 30   # pass rule: a path's class volatility needs 30 returns in the class


@dataclass(frozen=True)
class Band:
    code: str
    part: str
    lo: float
    hi: float
    record: float      # the record's value under the same estimator, recomputed by record_check.py
    source: str


# Targets. SF1 to SF3 are the generator pass rule's checks around the recomputed record values. SF4 to SF10 are the
# record study's bands.
BANDS = {
    ("SF1", "bull"): Band("SF1", "bull", 1.3929 - 0.2, 1.3929 + 0.2, 1.3929, "pass rule, causal classes, record recomputed"),
    ("SF1", "bear"): Band("SF1", "bear", 1.0414 - 0.2, 1.0414 + 0.2, 1.0414, "pass rule, causal classes, record recomputed"),
    ("SF1", "range"): Band("SF1", "range", 1.0000 - 0.2, 1.0000 + 0.2, 1.0000, "pass rule, causal classes, record recomputed"),
    ("SF2", "calm_days"): Band("SF2", "calm_days", 39.525 * 0.5, 39.525 * 1.5, 39.525, "pass rule, Markov switching, +-50%"),
    ("SF2", "turbulent_days"): Band("SF2", "turbulent_days", 13.058 * 0.5, 13.058 * 1.5, 13.058, "pass rule, Markov switching, +-50%"),
    ("SF2", "turbulent_share"): Band("SF2", "turbulent_share", 0.15, 0.35, 0.2375, "pass rule, Markov switching"),
    ("SF3", "swings_30"): Band("SF3", "swings_30", 30, 55, 41, "pass rule, Lunde-Timmermann swings"),
    ("SF3", "swings_50"): Band("SF3", "swings_50", 11, 24, 17, "pass rule, Lunde-Timmermann swings"),
    ("SF4", "staked_26w"): Band("SF4", "staked_26w", -0.09, 0.09, 0.004, "record, weekly lag regression"),
    ("SF5", "staked_through_fall"): Band("SF5", "staked_through_fall", -0.05, 0.20, 0.083, "record, the 2021 to 2023 fall"),
    ("SF6", "validators_26w"): Band("SF6", "validators_26w", 0.15 - 0.09, 0.15 + 0.09, 0.147, "record, weekly lag regression"),
    ("SF6", "validators_13w"): Band("SF6", "validators_13w", 0.10 - 0.05, 0.10 + 0.05, 0.111, "record, weekly lag regression"),
    ("SF7", "renewal_pp_per_log_move"): Band("SF7", "renewal_pp_per_log_move", 1.2, 4.7, 2.95, "record, renewal after price moves"),
    ("SF8", "turbulent_logodds"): Band("SF8", "turbulent_logodds", -0.6, 0.0, -0.21, "record, renewal by volatility state, year effects"),
    ("SF9", "bull_arrivals_log"): Band("SF9", "bull_arrivals_log", 0.03, 0.68, 0.39, "record, arrivals by class, year effects"),
    ("SF10", "usd_min"): Band("SF10", "usd_min", 677 / 1.5, 677 * 1.5, 677, "record, dollar reward on 2,000 AVAX"),
    ("SF10", "usd_max"): Band("SF10", "usd_max", 28369 / 1.5, 28369 * 1.5, 28369, "record, dollar reward on 2,000 AVAX"),
    ("SF10", "lending_bear_minus_bull_pp"): Band("SF10", "lending_bear_minus_bull_pp", 0.0, 2.5, 1.56, "record, lending yield by class"),
}


# ---------------------------------------------------------------- shared helpers

def _check(df: pd.DataFrame) -> None:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("a path must be indexed by a DatetimeIndex of calendar days")
    gaps = df.index.to_series().diff().dropna()
    if len(gaps) and not (gaps == pd.Timedelta(days=1)).all():
        raise ValueError("a path's days must be consecutive")
    if "price_usd" not in df or df.price_usd.isna().any() or (df.price_usd <= 0).any():
        raise ValueError("price_usd must be present, positive and complete")


def _has(df, *cols):
    return all(c in df.columns and df[c].notna().any() for c in cols)


def causal_class(log_price: pd.Series) -> pd.Series:
    """Bull if the 91-day trailing log change exceeds +0.20, bear below -0.20, range otherwise; NaN for 91 days."""
    c = log_price - log_price.shift(LOOK)
    lab = pd.Series(np.where(c > THR, "bull", np.where(c < -THR, "bear", "range")), index=log_price.index, dtype=object)
    lab[c.isna()] = None
    return lab


def _labels(df):
    if "regime" in df.columns and df.regime.notna().any():
        return df.regime.where(df.regime.isin(["bull", "bear", "range"])), "regime column"
    return causal_class(np.log(df.price_usd)), "causal 91-day rule"


def _irls(X, y, family, n=None, alpha=1.0, iters=100):
    """Point estimate of a binomial (grouped, n trials) logit or a negative-binomial (fixed alpha) log-link GLM."""
    b = np.zeros(X.shape[1])
    if family == "binomial":
        p0 = np.clip(y.sum() / n.sum(), 1e-6, 1 - 1e-6)
        b[0] = np.log(p0 / (1 - p0))
    else:
        b[0] = np.log(max(y.mean(), 1e-6))
    for _ in range(iters):
        eta = X @ b
        if family == "binomial":
            mu = 1 / (1 + np.exp(-eta))
            w = n * mu * (1 - mu)
            z = eta + (y - n * mu) / np.maximum(w, 1e-12)
        else:
            mu = np.exp(eta)
            w = mu / (1 + alpha * mu)
            z = eta + (y - mu) / np.maximum(mu, 1e-12)
        wx = X * w[:, None]
        nb = np.linalg.lstsq(wx.T @ X, wx.T @ z, rcond=None)[0]
        if np.max(np.abs(nb - b)) < 1e-10:
            return nb
        b = nb
    return b


def _design(index, dummies: dict[str, np.ndarray]):
    """Constant, the named 0/1 columns and calendar-year effects (first year dropped)."""
    years = np.asarray(index.year)
    cols = [np.ones(len(index))] + list(dummies.values())
    for yr in np.unique(years)[1:]:
        cols.append((years == yr).astype(float))
    X = np.column_stack(cols)
    keep = X.std(0) > 0
    keep[0] = True
    names = ["const"] + list(dummies)
    return X[:, keep], [n for n, k in zip(names + [""] * (X.shape[1] - len(names)), keep) if k and n]


# ---------------------------------------------------------------- SF1 to SF3: price paths

def sf1_class_vol(df):
    """Annualised volatility of daily log returns in each causal class."""
    lp = np.log(df.price_usd)
    r = lp.diff().shift(-1)                 # the return from day t to t+1 takes day t's class
    c = causal_class(lp)
    out = {}
    for cls in ("bull", "bear", "range"):
        x = r[(c == cls) & r.notna()]
        out[cls] = float(x.std() * np.sqrt(YEAR)) if len(x) >= MIN_CLASS_N else np.nan
    return out


def _forward_backward(dens, P, pi):
    """Scaled forward-backward for N paths, 2 states. dens (N, T, 2), P (N, 2, 2) row = from."""
    N, T, K = dens.shape
    a = np.empty((N, T, K))
    c = np.empty((N, T))
    x = pi * dens[:, 0]
    c[:, 0] = x.sum(1)
    a[:, 0] = x / c[:, :1]
    for t in range(1, T):
        x = np.einsum("ni,nij->nj", a[:, t - 1], P) * dens[:, t]
        c[:, t] = x.sum(1)
        a[:, t] = x / c[:, t:t + 1]
    b = np.ones((N, T, K))
    xi = np.zeros((N, K, K))
    for t in range(T - 2, -1, -1):
        bd = b[:, t + 1] * dens[:, t + 1]
        b[:, t] = np.einsum("nij,nj->ni", P, bd) / c[:, t + 1:t + 2]
        xi += a[:, t, :, None] * P * bd[:, None, :] / c[:, t + 1, None, None]
    g = a * b
    return g / g.sum(2, keepdims=True), xi, np.log(c).sum(1)


def ms2_fit(R, iters=1000, tol=1e-9):
    """Two-state Markov switching with switching mean and variance, Gaussian, by EM. R (N, T) daily returns.

    State 0 is the low-variance (calm) state. Returns durations 1/(1 - stay), the share of days whose smoothed
    probability of the turbulent state exceeds 0.5, state volatilities a year and the smoothed probabilities.
    """
    R = np.atleast_2d(np.asarray(R, float))
    N, _ = R.shape
    s = R.std(1)
    mu = np.tile(R.mean(1)[:, None], (1, 2))
    sd = np.stack([0.6 * s, 1.6 * s], 1)
    P = np.tile(np.array([[0.97, 0.03], [0.08, 0.92]]), (N, 1, 1))
    pi = np.tile([0.7, 0.3], (N, 1))
    prev = np.full(N, -np.inf)
    for _ in range(iters):
        z = (R[:, :, None] - mu[:, None, :]) / sd[:, None, :]
        dens = np.maximum(np.exp(-0.5 * z * z) / (np.sqrt(2 * np.pi) * sd[:, None, :]), 1e-300)
        g, xi, ll = _forward_backward(dens, P, pi)
        P = xi / xi.sum(2, keepdims=True)
        pi = g[:, 0]
        mu = (g * R[:, :, None]).sum(1) / g.sum(1)
        sd = np.maximum(np.sqrt((g * (R[:, :, None] - mu[:, None, :]) ** 2).sum(1) / g.sum(1)), 1e-6)
        if np.all(np.abs(ll - prev) < tol * np.abs(ll)):
            break
        prev = ll
    swap = sd[:, 0] > sd[:, 1]
    sd = np.where(swap[:, None], sd[:, ::-1], sd)
    P = np.where(swap[:, None, None], P[:, ::-1, ::-1], P)
    g = np.where(swap[:, None, None], g[:, :, ::-1], g)
    with np.errstate(divide="ignore"):   # a stay probability of 1 is an infinite duration, which fails its band
        calm_days, turbulent_days = 1 / (1 - P[:, 0, 0]), 1 / (1 - P[:, 1, 1])
    return dict(calm_days=calm_days, turbulent_days=turbulent_days,
                turbulent_share=(g[:, :, 1] > 0.5).mean(1), calm_vol=sd[:, 0] * np.sqrt(YEAR),
                turbulent_vol=sd[:, 1] * np.sqrt(YEAR), turbulent_prob=g[:, :, 1])


def lt_switches(price: np.ndarray, lam: float) -> int:
    """Switches (turns minus one) of the Lunde-Timmermann peak-trough rule."""
    p = np.asarray(price, float)
    state, ext, hi, lo, turns = 0, 0, 0, 0, 0
    for i in range(1, len(p)):
        if state == 0:
            if p[i] > p[hi]:
                hi = i
            if p[i] < p[lo]:
                lo = i
            if p[i] >= p[lo] * (1 + lam):
                state, ext, turns = 1, i, turns + 1
            elif p[i] <= p[hi] * (1 - lam):
                state, ext, turns = -1, i, turns + 1
        elif state == 1:
            if p[i] >= p[ext]:
                ext = i
            elif p[i] <= p[ext] * (1 - lam):
                state, ext, turns = -1, i, turns + 1
        else:
            if p[i] <= p[ext]:
                ext = i
            elif p[i] >= p[ext] * (1 + lam):
                state, ext, turns = 1, i, turns + 1
    return max(turns - 1, 0)


# ---------------------------------------------------------------- SF4 to SF6: stocks on price

def weekly_lag_response(df, col, horizons=(13, 26), lags=26, min_weeks=130):
    """Cumulative response of the weekly log change of `col` to weekly log price changes at lags 0..26 .

    Weeks end on Tuesday. Returns {horizon: cumulative} or NaNs.
    """
    w = df[["price_usd", col]].resample("W-TUE").last()
    w = w.iloc[1:] if len(w) and (df.index[0] != w.index[0] - pd.Timedelta(days=6)) else w   # drop a partial first week
    s = pd.DataFrame({"y": np.log(w[col]).diff(), "p0": np.log(w.price_usd).diff()})
    for k in range(1, lags + 1):
        s[f"p{k}"] = s.p0.shift(k)
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    if len(s) < min_weeks - lags:
        return {h: np.nan for h in horizons}
    X = np.column_stack([np.ones(len(s))] + [s[f"p{k}"].values for k in range(lags + 1)])
    b = np.linalg.lstsq(X, s.y.values, rcond=None)[0]
    return {h: float(b[1:h + 2].sum()) for h in horizons}


def deepest_fall(price: pd.Series, window=410):
    """The deepest fall from a peak to a later day within `window` days: (fall, peak day, trough day)."""
    p = price.values
    best = (0.0, None, None)
    for j in range(1, len(p)):
        i0 = max(0, j - window)
        i = i0 + int(np.argmax(p[i0:j + 1]))
        f = 1 - p[j] / p[i]
        if f > best[0]:
            best = (f, i, j)
    f, i, j = best
    return f, (price.index[i] if i is not None else None), (price.index[j] if j is not None else None)


# ---------------------------------------------------------------- SF7: renewal after price moves

def renewal_move_slope(df, step=7, before=(120, 31), after=90):
    """Slope of renewal after minus before (pp) on the 30-day log price move, over every 7th day."""
    lp = np.log(df.price_usd)
    n = df.endings.fillna(0).values
    r = df.renewed.fillna(0).values
    cn, cr = np.concatenate([[0], np.cumsum(n)]), np.concatenate([[0], np.cumsum(r)])

    def share(a, b):  # days a..b inclusive, positions
        tot = cn[b + 1] - cn[a]
        return (cr[b + 1] - cr[a]) / tot if tot > 0 else np.nan

    xs, ys = [], []
    for t in range(before[0], len(df) - after, step):
        rb = share(t - before[0], t - before[1])
        ra = share(t + 1, t + after)
        x = lp.iloc[t] - lp.iloc[t - 30]
        if np.isfinite(rb) and np.isfinite(ra):
            xs.append(x)
            ys.append(100 * (ra - rb))
    if len(xs) < 52:
        return np.nan
    X = np.column_stack([np.ones(len(xs)), xs])
    return float(np.linalg.lstsq(X, np.array(ys), rcond=None)[0][1])


# ---------------------------------------------------------------- evaluation

def _median(values):
    v = np.array([x for x in values if x is not None and np.isfinite(x)], float)
    return (float(np.median(v)) if len(v) else np.nan), len(v)


def path_statistics(paths: list[pd.DataFrame], ms_start: str | None = None) -> pd.DataFrame:
    """One row per path, one column per (code, part) statistic. NaN where a test does not apply.

    ms_start: first day of the returns fed to the Markov-switching fit and the swing count (the record uses
    2020-10-01, after the launch week). None uses the whole path.
    """
    for df in paths:
        _check(df)
    rows = [dict() for _ in paths]

    # SF1
    for row, df in zip(rows, paths):
        for cls, v in sf1_class_vol(df).items():
            row[("SF1", cls)] = v

    # SF2 and SF8 share the Markov-switching fit; batch paths of equal length.
    rets = []
    for df in paths:
        lp = np.log(df.price_usd)
        if ms_start is not None:
            lp = lp[lp.index >= pd.Timestamp(ms_start)]
        rets.append(lp.diff().dropna())
    probs = [None] * len(paths)
    by_len: dict[int, list[int]] = {}
    for k, r in enumerate(rets):
        if len(r) >= 1500:
            by_len.setdefault(len(r), []).append(k)
    for _, ks in by_len.items():
        fit = ms2_fit(np.stack([rets[k].values for k in ks]))
        for m, k in enumerate(ks):
            for part in ("calm_days", "turbulent_days", "turbulent_share"):
                rows[k][("SF2", part)] = float(fit[part][m])
            rows[k][("SF2", "calm_vol (diagnostic)")] = float(fit["calm_vol"][m])
            rows[k][("SF2", "turbulent_vol (diagnostic)")] = float(fit["turbulent_vol"][m])
            probs[k] = pd.Series(fit["turbulent_prob"][m], index=rets[k].index)

    for row, df in zip(rows, paths):
        p = df.price_usd if ms_start is None else df.price_usd[df.index >= pd.Timestamp(ms_start)]
        if len(p) >= 1500:
            row[("SF3", "swings_30")] = lt_switches(p.values, 0.3)
            row[("SF3", "swings_50")] = lt_switches(p.values, 0.5)

        if _has(df, "staked_avax"):
            row[("SF4", "staked_26w")] = weekly_lag_response(df, "staked_avax")[26]
            fall, a, b = deepest_fall(df.price_usd)
            if fall >= 0.75:
                row[("SF5", "staked_through_fall")] = float(df.staked_avax[b] / df.staked_avax[a] - 1)
        if _has(df, "active_validators"):
            resp = weekly_lag_response(df, "active_validators")
            row[("SF6", "validators_26w")] = resp[26]
            row[("SF6", "validators_13w")] = resp[13]
        if _has(df, "endings", "renewed"):
            row[("SF7", "renewal_pp_per_log_move")] = renewal_move_slope(df)

    # SF8: renewal log-odds in the turbulent state against the calm state, with calendar-year effects.
    for k, (row, df) in enumerate(zip(rows, paths)):
        if probs[k] is None or not _has(df, "endings", "renewed"):
            continue
        d = df.loc[probs[k].index, ["endings", "renewed"]].fillna(0)
        turb = (probs[k] > 0.5).astype(float).values
        m = d.endings.values > 0
        if m.sum() < 365:
            continue
        X, names = _design(d.index[m], {"turbulent": turb[m]})
        b = _irls(X, d.renewed.values[m], "binomial", n=d.endings.values[m])
        row[("SF8", "turbulent_logodds")] = float(b[names.index("turbulent")])

    # SF9 and SF10.
    for row, df in zip(rows, paths):
        lab, _ = _labels(df)
        if _has(df, "first_ever"):
            m = lab.notna()
            if ms_start is not None:
                m &= df.index >= pd.Timestamp(ms_start)
            if (lab[m] == "bull").sum() >= 60 and (lab[m] == "range").sum() >= 60:
                X, names = _design(df.index[m], {"bull": (lab[m] == "bull").astype(float).values,
                                                 "bear": (lab[m] == "bear").astype(float).values})
                b = _irls(X, df.first_ever[m].fillna(0).values.astype(float), "negbin")
                row[("SF9", "bull_arrivals_log")] = float(b[names.index("bull")])
        if _has(df, "reward_rate_pct_pa") and len(df) >= 4 * YEAR:
            usd = 2000 * df.reward_rate_pct_pa / 100 * df.price_usd
            row[("SF10", "usd_min")] = float(usd.min())
            row[("SF10", "usd_max")] = float(usd.max())
        if _has(df, "lending_yield_pct_pa"):
            y = df.lending_yield_pct_pa
            ok = y.notna() & lab.notna()
            if (lab[ok] == "bear").sum() >= 60 and (lab[ok] == "bull").sum() >= 60:
                row[("SF10", "lending_bear_minus_bull_pp")] = float(y[ok & (lab == "bear")].mean()
                                                                   - y[ok & (lab == "bull")].mean())
    out = pd.DataFrame(rows)
    out.columns = pd.MultiIndex.from_tuples(out.columns) if len(out.columns) else out.columns
    return out


def evaluate(paths: list[pd.DataFrame], ms_start: str | None = None) -> pd.DataFrame:
    """Median over paths of each statistic against its band. passed is None where no path supports the test."""
    stats = path_statistics(paths, ms_start=ms_start)
    rows = []
    for key, band in BANDS.items():
        vals = stats[key].tolist() if key in stats.columns else []
        v, n = _median(vals)
        rows.append(dict(code=band.code, part=band.part, value=v, lo=band.lo, hi=band.hi, record=band.record,
                         passed=(bool(band.lo <= v <= band.hi) if n else None), paths=n, source=band.source))
    for key in stats.columns:
        if "diagnostic" in key[1]:
            v, n = _median(stats[key].tolist())
            rows.append(dict(code=key[0], part=key[1], value=v, lo=np.nan, hi=np.nan, record=np.nan, passed=None,
                             paths=n, source="diagnostic, outside the rule"))
    return pd.DataFrame(rows)


def failures(results: pd.DataFrame) -> pd.DataFrame:
    return results[results.passed.eq(False)]
