"""Strict prior observed-time price quotes, without a publication-availability claim."""

from __future__ import annotations

import hashlib
import math
import tempfile
from numbers import Number
from pathlib import Path

import duckdb
import pandas as pd

from ...core.catalog import DataError

PRICE_COLUMNS = ("observed_at", "observation_date", "price_usd", "realized_volatility_30d")


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_utc(values, name):
    """Validate known nonnumeric clocks and normalize them to nanosecond UTC.

    Naive timestamps mean UTC. Numeric values, unknown times and instants
    outside pandas' supported nanosecond range refuse rather than get guessed.
    """
    if any(isinstance(value, Number) for value in values):
        raise DataError(f"{name} must contain known timestamp clocks, not numbers")
    try:
        result = pd.to_datetime(values, utc=True, format="mixed", errors="raise")
        result = result.astype("datetime64[ns, UTC]")
    except (TypeError, ValueError, OverflowError) as error:
        raise DataError(f"{name} must contain known UTC-normalizable clocks") from error
    if result.isna().any():
        raise DataError(f"{name} contains an unknown clock")
    return result


def _value_identity(value):
    if pd.isna(value):
        return None
    if isinstance(value, float):
        return value.hex()
    return str(value)


def select_quotes(keys: pd.DataFrame, path, *, max_age_seconds=None):
    """Return one strictly earlier whole price row per unique ``quote_key``.

    Naive catalog clocks mean UTC. Nominal dates never govern selection. The
    optional nonnegative age limit is inclusive. A stale candidate's values are
    missing while its timestamp, nominal date and age remain as evidence. An
    older non-NULL observation never substitutes for it. Publication
    times are unavailable, so this selects an observed-time proxy only.

    Price catalogs are small: DuckDB reads only four columns with a private
    spill directory; pandas preserves nanosecond instants for the strict join.
    Identical duplicate quote rows collapse. Conflicting simultaneous rows
    refuse only when their instant would be selected by a requested key.
    """
    if not {"quote_key", "quote_cutoff_at"} <= set(keys.columns):
        raise DataError("keys require quote_key and quote_cutoff_at")
    if keys.quote_key.isna().any() or keys.quote_key.duplicated().any():
        raise DataError("quote_key must be unique and non-null")
    if max_age_seconds is not None:
        if isinstance(max_age_seconds, bool):
            raise DataError("max_age_seconds must be finite and nonnegative")
        try:
            max_age_seconds = float(max_age_seconds)
        except (TypeError, ValueError, OverflowError) as error:
            raise DataError("max_age_seconds must be finite and nonnegative") from error
        if not math.isfinite(max_age_seconds) or max_age_seconds < 0:
            raise DataError("max_age_seconds must be finite and nonnegative")
    requested = keys[["quote_key", "quote_cutoff_at"]].copy().reset_index(drop=True)
    requested["quote_cutoff_at"] = normalize_utc(requested.quote_cutoff_at, "quote_cutoff_at")
    requested["_order"] = range(len(requested))
    path = Path(path)
    source_sha = _sha256(path)
    with (
        tempfile.TemporaryDirectory(prefix="avalanche-observed-quotes-") as scratch,
        duckdb.connect(config={"threads": "2", "memory_limit": "2GB", "temp_directory": scratch}) as connection,
    ):
        connection.execute("SET TimeZone='UTC'")
        try:
            quotes = connection.execute(
                "SELECT observed_at, observation_date, price_usd, realized_volatility_30d FROM read_parquet(?)",
                [str(path)],
            ).df()
        except duckdb.Error as error:
            raise DataError("price source must provide the required quote columns") from error
    if _sha256(path) != source_sha:
        raise DataError("price source bytes changed during quote selection")
    quotes["observed_at"] = normalize_utc(quotes.observed_at, "observed_at")
    # Explicit row identities preserve NULLs and distinguish different float bits.
    identities = pd.Series(
        [tuple(_value_identity(value) for value in row) for row in quotes.itertuples(index=False, name=None)],
        index=quotes.index, dtype=object,
    )
    duplicate = identities.duplicated()
    input_rows = len(quotes)
    quotes = quotes.loc[~duplicate].copy()
    conflicts = quotes.loc[quotes.observed_at.duplicated(keep=False), "observed_at"].unique()
    quotes = quotes.rename(columns={"observed_at": "price_observed_at", "observation_date": "price_nominal_date",
                                    "realized_volatility_30d": "volatility_30d"})
    result = pd.merge_asof(
        requested.sort_values("quote_cutoff_at", kind="stable"),
        quotes.sort_values("price_observed_at", kind="stable"),
        left_on="quote_cutoff_at", right_on="price_observed_at", direction="backward", allow_exact_matches=False,
    ).sort_values("_order").drop(columns="_order").reset_index(drop=True)
    if result.price_observed_at.isin(conflicts).any():
        raise DataError("conflicting same-time quote rows would be selected")
    result["price_age_at_cutoff_seconds"] = (result.quote_cutoff_at - result.price_observed_at).dt.total_seconds()
    result["price_source_sha256"] = source_sha
    result["price_quote_status"] = "selected"
    result.loc[result.price_observed_at.isna(), "price_quote_status"] = "no_prior_quote"
    stale = pd.Series(False, index=result.index)
    if max_age_seconds is not None:
        stale = result.price_age_at_cutoff_seconds.gt(max_age_seconds)
        result.loc[stale, "price_quote_status"] = "stale"
        for field in ("price_usd", "volatility_30d"):
            result.loc[stale, field] = None
    result = result[["quote_key", "quote_cutoff_at", "price_usd", "volatility_30d", "price_observed_at",
                     "price_nominal_date", "price_age_at_cutoff_seconds", "price_source_sha256", "price_quote_status"]]
    result.attrs = {
        "quote_policy": "latest whole row with observed_at strictly less than cutoff; no nominal-date grouping or NULL fill",
        "clock_policy": "UTC; naive catalog clocks interpreted as UTC; nanosecond join precision",
        "availability_limit": "Observed-time proxy only. Provider publication availability is unknown.",
        "stale_policy": "Price and volatility withheld; candidate observed time, nominal date and age retained as evidence, not admitted values.",
        "quote_identity": ["price_source_sha256", "price_observed_at"],
        "source_sha256": source_sha, "input_rows": input_rows,
        "exact_duplicate_rows_removed": int(duplicate.sum()), "unused_conflicting_instants": len(conflicts),
        "max_age_seconds": max_age_seconds, "stale_keys": int(stale.sum()),
        "resources": {"duckdb_threads": 2, "duckdb_memory_limit": "2GB", "spill": "private per call"},
    }
    return result
