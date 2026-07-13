from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener

from src.ingest.http_acquisition import (
    HttpAcquisitionError,
    HttpRequestSpec,
    PoliteHttpClient,
    RateLimitPolicy,
    RetryPolicy,
)


@dataclass(frozen=True)
class PublicResponse:
    body: bytes
    url: str
    status: int
    attempts: int
    transport: str


def market_prefix(stock_code: str) -> str:
    if stock_code.startswith(("6", "9")):
        return "sh"
    if stock_code.startswith(("4", "8")):
        return "bj"
    return "sz"


def secid(stock_code: str) -> str:
    market = "1" if stock_code.startswith(("6", "9")) else "0"
    return f"{market}.{stock_code}"


def request_public(
    *,
    url: str,
    source_name: str,
    capability: str,
    params: Mapping[str, Any] | None = None,
    method: str = "GET",
    body: bytes | None = None,
    headers: Mapping[str, str] | None = None,
    referer: str | None = None,
    timeout_seconds: float = 20.0,
    min_interval_seconds: float = 0.8,
) -> PublicResponse:
    query_url = f"{url}?{urlencode(params, doseq=True)}" if params else url

    def run(proxy_mode: str) -> PublicResponse:
        opener = build_opener(ProxyHandler({})) if proxy_mode == "direct" else build_opener()
        client = PoliteHttpClient(
            opener=opener,
            retry_policy=RetryPolicy(max_attempts=3),
            rate_limit_policy=RateLimitPolicy(
                min_interval_seconds=min_interval_seconds,
                serial_only=True,
            ),
        )
        response = client.request(
            HttpRequestSpec(
                url=query_url,
                source_name=source_name,
                capability=capability,
                method=method,
                headers=dict(headers or {}),
                body=body,
                timeout_seconds=timeout_seconds,
                referer=referer,
            )
        )
        return PublicResponse(
            body=response.body,
            url=query_url,
            status=response.status,
            attempts=response.attempts,
            transport=proxy_mode,
        )

    try:
        return run("inherit")
    except HttpAcquisitionError as exc:
        if exc.status is not None:
            raise
        fallback = run("direct")
        return PublicResponse(
            body=fallback.body,
            url=fallback.url,
            status=fallback.status,
            attempts=exc.attempts + fallback.attempts,
            transport="direct_fallback",
        )


def decode_json(body: bytes, *, encoding: str = "utf-8-sig") -> Any:
    text = body.decode(encoding, errors="replace").strip()
    if text.startswith(("{", "[")):
        return json.loads(text)
    match = re.match(r"^[^(=]+(?:=|\()(.*?)(?:\)|;)?$", text, flags=re.DOTALL)
    if match:
        candidate = match.group(1).strip().strip(";")
        if candidate.startswith(("{", "[")):
            return json.loads(candidate)
    left_candidates = [index for index in (text.find("{"), text.find("[")) if index >= 0]
    if left_candidates:
        left = min(left_candidates)
        right = max(text.rfind("}"), text.rfind("]"))
        if right > left:
            return json.loads(text[left : right + 1])
    raise ValueError("response is not JSON or JSONP")
