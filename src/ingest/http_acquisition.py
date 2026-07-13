from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from email.message import Message
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import OpenerDirector, Request, build_opener


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    retry_http_statuses: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504)
    no_retry_http_statuses: tuple[int, ...] = (400, 401, 403, 404)
    base_delay_seconds: float = 1.5
    max_delay_seconds: float = 15.0
    jitter_ratio: float = 0.25


@dataclass(frozen=True)
class RateLimitPolicy:
    min_interval_seconds: float = 0.8
    serial_only: bool = True


@dataclass(frozen=True)
class HttpRequestSpec:
    url: str
    source_name: str
    capability: str
    method: str = "GET"
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None
    timeout_seconds: float = 15.0
    referer: str | None = None


@dataclass(frozen=True)
class HttpResponseData:
    status: int
    headers: Mapping[str, str]
    body: bytes
    attempts: int
    elapsed_ms: int


class HttpAcquisitionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status: int | None,
        attempts: int,
        retriable: bool,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.attempts = attempts
        self.retriable = retriable


class PoliteHttpClient:
    """Serial, throttled HTTP helper for public endpoints.

    This helper does not know any vendor-specific URL. It centralizes the operational rules
    that every public HTTP adapter must obey: session reuse, minimum spacing, bounded retry,
    jitter, Retry-After handling and no immediate retry for 401/403/404.
    """

    def __init__(
        self,
        *,
        opener: OpenerDirector | Any | None = None,
        retry_policy: RetryPolicy | None = None,
        rate_limit_policy: RateLimitPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        random_uniform: Callable[[float, float], float] = random.uniform,
        user_agent: str = "A-share-Research-OS/0.1 evidence-ingest",
    ) -> None:
        self._opener = opener or build_opener()
        self._retry = retry_policy or RetryPolicy()
        self._rate = rate_limit_policy or RateLimitPolicy()
        self._sleep = sleep
        self._monotonic = monotonic
        self._random_uniform = random_uniform
        self._user_agent = user_agent
        self._last_request_at: float | None = None
        self._lock = threading.Lock()

    def request(self, spec: HttpRequestSpec) -> HttpResponseData:
        if self._rate.serial_only:
            with self._lock:
                return self._request_with_retry(spec)
        return self._request_with_retry(spec)

    def _wait_for_slot(self) -> None:
        now = self._monotonic()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            remaining = self._rate.min_interval_seconds - elapsed
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = self._monotonic()

    def _request_with_retry(self, spec: HttpRequestSpec) -> HttpResponseData:
        started_at = self._monotonic()
        last_status: int | None = None
        last_message = "request failed"

        for attempt in range(1, self._retry.max_attempts + 1):
            self._wait_for_slot()
            request = self._build_request(spec)
            try:
                response = self._opener.open(request, timeout=spec.timeout_seconds)
                status = int(getattr(response, "status", 200))
                headers = self._headers_to_dict(getattr(response, "headers", {}))
                body = response.read()
                elapsed_ms = int((self._monotonic() - started_at) * 1000)
                return HttpResponseData(
                    status=status,
                    headers=headers,
                    body=body,
                    attempts=attempt,
                    elapsed_ms=elapsed_ms,
                )
            except HTTPError as exc:
                last_status = int(exc.code)
                last_message = f"HTTP {exc.code}: {exc.reason}"
                if not self._should_retry(last_status, attempt):
                    raise HttpAcquisitionError(
                        last_message,
                        status=last_status,
                        attempts=attempt,
                        retriable=False,
                    ) from exc
                self._sleep(self._retry_delay(attempt, exc.headers))
            except URLError as exc:
                last_message = f"network error: {exc.reason}"
                if attempt >= self._retry.max_attempts:
                    raise HttpAcquisitionError(
                        last_message,
                        status=None,
                        attempts=attempt,
                        retriable=True,
                    ) from exc
                self._sleep(self._retry_delay(attempt, None))

        raise HttpAcquisitionError(
            last_message,
            status=last_status,
            attempts=self._retry.max_attempts,
            retriable=True,
        )

    def _build_request(self, spec: HttpRequestSpec) -> Request:
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/json,text/plain,*/*",
            **dict(spec.headers),
        }
        if spec.referer:
            headers.setdefault("Referer", spec.referer)
        return Request(
            spec.url,
            data=spec.body,
            headers=headers,
            method=spec.method,
        )

    def _should_retry(self, status: int, attempt: int) -> bool:
        if attempt >= self._retry.max_attempts:
            return False
        if status in self._retry.no_retry_http_statuses:
            return False
        return status in self._retry.retry_http_statuses or status >= 500

    def _retry_delay(self, attempt: int, headers: Message | Mapping[str, str] | None) -> float:
        retry_after = self._retry_after(headers)
        if retry_after is not None:
            return min(retry_after, self._retry.max_delay_seconds)
        base = min(
            self._retry.base_delay_seconds * (2 ** max(attempt - 1, 0)),
            self._retry.max_delay_seconds,
        )
        jitter = base * self._retry.jitter_ratio
        return max(0.0, base + self._random_uniform(-jitter, jitter))

    @staticmethod
    def _retry_after(headers: Message | Mapping[str, str] | None) -> float | None:
        if headers is None:
            return None
        raw_value = headers.get("Retry-After")
        if raw_value is None:
            return None
        try:
            return max(0.0, float(raw_value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _headers_to_dict(headers: Message | Mapping[str, str]) -> dict[str, str]:
        if hasattr(headers, "items"):
            return {str(key): str(value) for key, value in headers.items()}
        return {}
