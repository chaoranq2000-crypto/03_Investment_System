from __future__ import annotations

from email.message import Message
from io import BytesIO
from urllib.error import HTTPError

import pytest

from src.ingest.http_acquisition import (
    HttpAcquisitionError,
    HttpRequestSpec,
    PoliteHttpClient,
    RateLimitPolicy,
    RetryPolicy,
)


class FakeResponse:
    def __init__(self, body: bytes = b"{}", status: int = 200) -> None:
        self.status = status
        self.headers = Message()
        self._body = BytesIO(body)

    def read(self) -> bytes:
        return self._body.read()


class SequenceOpener:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    def open(self, request: object, timeout: float) -> FakeResponse:
        del request, timeout
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, FakeResponse)
        return outcome


def _http_error(status: int) -> HTTPError:
    return HTTPError(
        url="https://example.invalid",
        code=status,
        msg="error",
        hdrs=Message(),
        fp=None,
    )


def test_403_is_not_retried() -> None:
    opener = SequenceOpener([_http_error(403), FakeResponse()])
    client = PoliteHttpClient(
        opener=opener,
        retry_policy=RetryPolicy(max_attempts=3),
        rate_limit_policy=RateLimitPolicy(min_interval_seconds=0),
        sleep=lambda _: None,
        monotonic=lambda: 1.0,
    )
    with pytest.raises(HttpAcquisitionError) as exc_info:
        client.request(
            HttpRequestSpec(
                url="https://example.invalid",
                source_name="test",
                capability="test",
            )
        )
    assert exc_info.value.status == 403
    assert opener.calls == 1


def test_503_retries_then_succeeds() -> None:
    opener = SequenceOpener([_http_error(503), FakeResponse(b'{"ok": true}')])
    clock = iter([0.0, 0.0, 0.1, 0.1, 0.2, 0.2])
    client = PoliteHttpClient(
        opener=opener,
        retry_policy=RetryPolicy(max_attempts=3, jitter_ratio=0),
        rate_limit_policy=RateLimitPolicy(min_interval_seconds=0),
        sleep=lambda _: None,
        monotonic=lambda: next(clock),
    )
    response = client.request(
        HttpRequestSpec(
            url="https://example.invalid",
            source_name="test",
            capability="test",
        )
    )
    assert response.attempts == 2
    assert response.body == b'{"ok": true}'
