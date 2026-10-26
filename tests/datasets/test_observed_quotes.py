"""Independent tiny timestamp/value fixtures for strict prior quotes."""

import hashlib

import duckdb
import pandas as pd
import pytest

from avalanche_research.core.catalog import DataError
from avalanche_research.datasets.derived.observed_quotes import select_quotes


def price_file(tmp_path, rows, *, nanoseconds=False):
    path = tmp_path / "quotes.parquet"
    with duckdb.connect() as db:
        db.execute("CREATE TABLE quotes(observed_at VARCHAR, observation_date DATE, price_usd DOUBLE, realized_volatility_30d DOUBLE)")
        if rows:
            db.executemany("INSERT INTO quotes VALUES (?,?,?,?)", rows)
        query = "SELECT * FROM quotes"
        if nanoseconds:
            query = "SELECT * REPLACE(observed_at::TIMESTAMP_NS AS observed_at) FROM quotes"
        db.execute(f"COPY ({query}) TO ? (FORMAT PARQUET)", [str(path)])
    return path


def keys(*clocks):
    return pd.DataFrame({"quote_key": [f"k{i}" for i in range(len(clocks))], "quote_cutoff_at": list(clocks)})


def test_strict_midnight_and_future_nominal_date_are_independent(tmp_path):
    path = price_file(tmp_path, [
        ("2025-11-18 23:59:00", "2025-11-21", 10, 0.1),
        ("2025-11-19 00:00:00", "2025-11-18", 20, 0.2),
        ("2025-11-19 00:01:00", "2025-11-17", 30, 0.3),
    ])
    result = select_quotes(keys("2025-11-19 00:00:00", "2025-11-19 00:01:00"), path)
    assert list(result.price_usd) == [10, 20]
    assert list(result.volatility_30d) == [0.1, 0.2]
    assert list(result.price_age_at_cutoff_seconds) == [60, 60]
    assert result.price_nominal_date.iloc[0] == pd.Timestamp("2025-11-21")
    assert result.price_observed_at.iloc[0] == pd.Timestamp("2025-11-18 23:59:00Z")
    assert result.price_source_sha256.eq(hashlib.sha256(path.read_bytes()).hexdigest()).all()
    assert "publication" in result.attrs["availability_limit"]


def test_latest_null_is_not_filled_or_columnwise_assembled(tmp_path):
    path = price_file(tmp_path, [
        ("2025-11-18 22:00:00", "2025-11-18", 10, 0.1),
        ("2025-11-18 23:00:00", "2025-11-18", None, 0.2),
    ])
    result = select_quotes(keys("2025-11-19 00:00:00Z"), path).iloc[0]
    assert pd.isna(result.price_usd)
    assert result.volatility_30d == 0.2
    assert result.price_observed_at == pd.Timestamp("2025-11-18 23:00:00Z")
    assert result.price_quote_status == "selected"


def test_age_cap_is_inclusive_and_stale_quote_is_not_admitted(tmp_path):
    path = price_file(tmp_path, [("2025-11-18 00:00:00", "2025-11-18", 10, 0.1)])
    cutoffs = keys("2025-11-19 00:00:00", "2025-11-19 00:00:00.000000001")
    result = select_quotes(cutoffs, path, max_age_seconds=86400)
    assert list(result.price_quote_status) == ["selected", "stale"]
    assert result.price_age_at_cutoff_seconds.iloc[0] == 86400
    assert result.loc[1, ["price_usd", "volatility_30d"]].isna().all()
    assert result.price_observed_at.iloc[1] == pd.Timestamp("2025-11-18T00:00:00Z")
    assert result.price_nominal_date.iloc[1] == pd.Timestamp("2025-11-18")
    assert result.price_age_at_cutoff_seconds.iloc[1] == 86400 + 1e-9
    assert "retained as evidence" in result.attrs["stale_policy"]
    assert result.price_source_sha256.notna().all()
    assert select_quotes(cutoffs, path).price_quote_status.eq("selected").all()


@pytest.mark.parametrize("changed", ["price", "null", "nominal", "signed_zero"])
def test_conflicting_same_time_selected_rows_refuse(tmp_path, changed):
    first = ["2025-11-18 23:00:00", "2025-11-18", 0.0, 0.1]
    second = first.copy()
    if changed == "price":
        second[2] = 20
    elif changed == "null":
        second[3] = None
    elif changed == "nominal":
        second[1] = "2025-11-19"
    else:
        second[2] = -0.0
    path = price_file(tmp_path, [first, second])
    with pytest.raises(DataError, match="conflicting same-time"):
        select_quotes(keys("2025-11-19"), path)


def test_unused_conflicts_and_identical_duplicates(tmp_path):
    row = ("2025-11-18 23:00:00", "2025-11-18", None, 0.2)
    path = price_file(tmp_path, [row, row,
        ("2025-11-19 01:00:00", "2025-11-19", 20, 0.3),
        ("2025-11-19 01:00:00", "2025-11-19", 30, 0.3)])
    result = select_quotes(keys("2025-11-19"), path)
    assert result.attrs["exact_duplicate_rows_removed"] == 1
    assert result.attrs["unused_conflicting_instants"] == 1
    assert pd.isna(result.price_usd.iloc[0])
    assert result.volatility_30d.iloc[0] == 0.2


@pytest.mark.parametrize("clock", [None, "not a time", 123])
def test_unknown_cutoff_refuses(tmp_path, clock):
    path = price_file(tmp_path, [("2025-11-18", "2025-11-18", 10, 0.1)])
    with pytest.raises(DataError, match="clock"):
        select_quotes(keys(clock), path)


def test_mixed_numeric_clock_is_not_silently_interpreted_as_epoch_nanoseconds(tmp_path):
    path = price_file(tmp_path, [("2025-11-18", "2025-11-18", 10, 0.1)])
    with pytest.raises(DataError, match="clock"):
        select_quotes(keys("2025-11-19", 123), path)


@pytest.mark.parametrize("clock", [None, "not a time"])
def test_unknown_source_clock_refuses(tmp_path, clock):
    path = price_file(tmp_path, [(clock, "2025-11-18", 10, 0.1)])
    with pytest.raises(DataError, match="clock"):
        select_quotes(keys("2025-11-19"), path)


def test_utc_offsets_and_original_key_order(tmp_path):
    path = price_file(tmp_path, [("2025-11-18T18:59:59-05:00", "2025-11-18", 10, 0.1)])
    result = select_quotes(keys("2025-11-18T16:00:00-08:00", "2025-11-18T23:59:59Z", "2025-11-19T09:00:00+09:00"), path)
    assert list(result.quote_key) == ["k0", "k1", "k2"]
    assert list(result.price_quote_status) == ["selected", "no_prior_quote", "selected"]
    assert result.price_observed_at.iloc[0] == pd.Timestamp("2025-11-18T23:59:59Z")
    assert result.price_age_at_cutoff_seconds.iloc[0] == result.price_age_at_cutoff_seconds.iloc[2] == 1


def test_nanosecond_source_and_cutoff_precision(tmp_path):
    path = price_file(tmp_path, [("2025-11-18 23:59:59.999999999", "2025-11-18", 10, 0.1)], nanoseconds=True)
    result = select_quotes(keys("2025-11-18 23:59:59.999999999", "2025-11-19 00:00:00"), path)
    assert list(result.price_quote_status) == ["no_prior_quote", "selected"]
    assert result.price_age_at_cutoff_seconds.iloc[1] == 1e-9


@pytest.mark.parametrize("bad_keys", [pd.DataFrame({"quote_key": ["x", "x"], "quote_cutoff_at": ["2025-11-19"] * 2}),
                                     pd.DataFrame({"quote_key": [None], "quote_cutoff_at": ["2025-11-19"]})])
def test_key_identity_refuses(tmp_path, bad_keys):
    path = price_file(tmp_path, [])
    with pytest.raises(DataError, match="quote_key"):
        select_quotes(bad_keys, path)


@pytest.mark.parametrize("cap", [-1, float("nan"), float("inf"), True])
def test_invalid_age_limit_refuses(tmp_path, cap):
    path = price_file(tmp_path, [])
    with pytest.raises(DataError, match="max_age_seconds"):
        select_quotes(keys("2025-11-19"), path, max_age_seconds=cap)


def test_empty_source_and_empty_requested_keys(tmp_path):
    path = price_file(tmp_path, [])
    result = select_quotes(keys("2025-11-19"), path)
    assert result.price_quote_status.item() == "no_prior_quote"
    assert result.price_observed_at.isna().all()
    assert select_quotes(keys(), path).empty
