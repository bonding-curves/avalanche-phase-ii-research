"""The polite download shared by the public market captures, with a fake opener and clock, no network."""

from __future__ import annotations

import io
import urllib.error
from email.message import Message

import pytest

from avalanche_research.catalog import DataError
from avalanche_research.sources import public_market


def opener(answers):
    """Answers in order: bytes for a body, an int for an HTTP error with that status."""
    queue = list(answers)

    def open_(request, timeout):
        answer = queue.pop(0)
        if isinstance(answer, int):
            headers = Message()
            if answer == 429:
                headers["Retry-After"] = "7"
            raise urllib.error.HTTPError(request.full_url, answer, "error", headers, io.BytesIO())
        return io.BytesIO(answer)
    return open_


def test_each_request_waits_and_a_rate_refusal_is_retried_after_retry_after():
    waits = []
    body = public_market.download("https://example.org/a", 5, opener=opener([429, 418, b"ok"]), sleep=waits.append)
    assert body == b"ok"
    assert waits == [0.5, 7.0, 0.5, 10.0, 0.5]


def test_not_found_is_not_published_and_other_errors_stop():
    with pytest.raises(public_market.NotPublished):
        public_market.download("https://example.org/a", 5, opener=opener([404]), sleep=lambda _: None)
    with pytest.raises(DataError, match="HTTP 403"):
        public_market.download("https://example.org/a", 5, opener=opener([403]), sleep=lambda _: None)
    with pytest.raises(DataError, match="HTTP 503"):
        public_market.download("https://example.org/a", 5, opener=opener([503] * 4), sleep=lambda _: None)


def test_correlation():
    assert public_market.correlation([(1, 2), (2, 4), (3, 6)]) == pytest.approx(1.0)
    assert public_market.correlation([(1, 2), (2, 2), (3, 2)]) is None
    assert public_market.correlation([(1, 2)]) is None
