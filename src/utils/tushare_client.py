from __future__ import annotations

import importlib
import os
import re
import threading
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import quote, quote_plus, urlsplit


TUSHARE_TOKEN_ENV = "TUSHARE_TOKEN"
TUSHARE_ENDPOINT_ENV = "TUSHARE_HTTP_URL"
TUSHARE_DISABLE_PROXY_ENV = "TUSHARE_DISABLE_PROXY"
DEFAULT_TUSHARE_TIMEOUT_SECONDS = 45
MAX_TOKEN_LENGTH = 4096
MAX_ERROR_LENGTH = 1000

_NO_PROXY_KEYS = ("NO_PROXY", "no_proxy")
_NO_PROXY_LOCK = threading.RLock()
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:authorization|proxy-authorization|x-api-key|api[_-]?key|"
    r"access[_-]?token|token|secret|password)\b[\"']?\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;&}]+)"
)
_BEARER_VALUE = re.compile(r"(?i)\b(bearer|basic)\s+[^\s,;&}\"']+")
_SECRET_QUERY = re.compile(
    r"(?i)([?&](?:access[_-]?token|token|api[_-]?key|key|secret|password)=)[^&#\s]+"
)
_URL_USERINFO = re.compile(r"(https?://)[^/@\s]+@", re.IGNORECASE)


class TushareConfigurationError(RuntimeError):
    """Tushare local configuration is missing or unsafe."""


class TushareProviderError(RuntimeError):
    """A sanitized error returned by the configured Tushare provider."""


@dataclass(frozen=True)
class TushareConfig:
    token: str = field(repr=False)
    endpoint: str
    disable_proxy: bool
    timeout_seconds: int
    token_env: str = TUSHARE_TOKEN_ENV


def _load_tushare() -> Any:
    try:
        return importlib.import_module("tushare")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The optional 'tushare' package is required only for live Tushare access; "
            "install it before calling get_tushare_pro()."
        ) from exc


def load_env_file(path: str | Path = ".env.local") -> dict[str, str]:
    env_path = Path(path)
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _combined_values(path: str | Path, *, token_env: str) -> dict[str, str]:
    values = load_env_file(path)
    for key in (token_env, TUSHARE_ENDPOINT_ENV, TUSHARE_DISABLE_PROXY_ENV):
        if key in os.environ:
            values[key] = os.environ[key]
    return values


def _validate_token(token: str, *, token_env: str) -> str:
    normalized = token.strip()
    if not normalized:
        raise TushareConfigurationError(f"{token_env} is missing")
    if len(normalized) > MAX_TOKEN_LENGTH:
        raise TushareConfigurationError(f"{token_env} is too long")
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in normalized):
        raise TushareConfigurationError(f"{token_env} contains unsafe characters")
    return normalized


def _resolve_endpoint(values: Mapping[str, str], explicit: str | None = None) -> str:
    endpoint = (explicit if explicit is not None else values.get(TUSHARE_ENDPOINT_ENV, ""))
    endpoint = endpoint.strip().rstrip("/")
    if not endpoint:
        raise TushareConfigurationError(f"{TUSHARE_ENDPOINT_ENV} is missing")
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in endpoint):
        raise TushareConfigurationError("Tushare endpoint contains unsafe characters")
    parsed = urlsplit(endpoint)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise TushareConfigurationError("Tushare endpoint must use HTTPS and include a host")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise TushareConfigurationError(
            "Tushare endpoint must not contain credentials, query, or fragment"
        )
    try:
        parsed.port
    except ValueError as exc:
        raise TushareConfigurationError("Tushare endpoint has an invalid port") from exc
    return endpoint


def _parse_bool(value: str | None, *, key: str) -> bool:
    normalized = (value or "").strip().lower()
    if normalized in {"", "0", "false", "no", "n", "off"}:
        return False
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    raise TushareConfigurationError(f"{key} must be a boolean value")


def load_tushare_config(
    path: str | Path = ".env.local",
    *,
    endpoint: str | None = None,
    token_env: str = TUSHARE_TOKEN_ENV,
    timeout_seconds: int = DEFAULT_TUSHARE_TIMEOUT_SECONDS,
    disable_proxy: bool | None = None,
) -> TushareConfig:
    values = _combined_values(path, token_env=token_env)
    token = _validate_token(values.get(token_env, ""), token_env=token_env)
    resolved_endpoint = _resolve_endpoint(values, endpoint)
    if isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 120:
        raise ValueError("timeout_seconds must be between 1 and 120")
    resolved_disable_proxy = (
        _parse_bool(values.get(TUSHARE_DISABLE_PROXY_ENV), key=TUSHARE_DISABLE_PROXY_ENV)
        if disable_proxy is None
        else bool(disable_proxy)
    )
    return TushareConfig(
        token=token,
        endpoint=resolved_endpoint,
        disable_proxy=resolved_disable_proxy,
        timeout_seconds=timeout_seconds,
        token_env=token_env,
    )


def _no_proxy_entries(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@contextmanager
def _temporary_endpoint_no_proxy(endpoint: str) -> Iterator[None]:
    host = urlsplit(endpoint).hostname
    if not host:
        yield
        return
    with _NO_PROXY_LOCK:
        previous = {key: os.environ.get(key) for key in _NO_PROXY_KEYS}
        try:
            for key in _NO_PROXY_KEYS:
                entries = _no_proxy_entries(os.environ.get(key, ""))
                if host.lower() not in {item.lower() for item in entries}:
                    os.environ[key] = ",".join([*entries, host])
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def sanitize_provider_error(error: object, *, secrets: tuple[str, ...] = ()) -> str:
    """Return a bounded provider error with common credential forms removed."""

    text = str(error)
    for secret in secrets:
        if not secret:
            continue
        for representation in {secret, quote(secret, safe=""), quote_plus(secret)}:
            if representation:
                text = text.replace(representation, "<REDACTED>")
    text = _BEARER_VALUE.sub(r"\1 <REDACTED>", text)
    text = _SECRET_QUERY.sub(r"\1<REDACTED>", text)
    text = _SECRET_ASSIGNMENT.sub(r"\1<REDACTED>", text)
    text = _URL_USERINFO.sub(r"\1<REDACTED>@", text)
    return text[:MAX_ERROR_LENGTH]


class _SafeTushareClient:
    def __init__(self, client: Any, config: TushareConfig) -> None:
        self._client = client
        self._config = config

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._client, name)
        if not callable(value):
            return value

        @wraps(value)
        def call(*args: Any, **kwargs: Any) -> Any:
            proxy_context = (
                _temporary_endpoint_no_proxy(self._config.endpoint)
                if self._config.disable_proxy
                else nullcontext()
            )
            try:
                with proxy_context:
                    return value(*args, **kwargs)
            except Exception as exc:
                safe_message = sanitize_provider_error(exc, secrets=(self._config.token,))
                raise TushareProviderError(
                    f"Tushare provider call {name} failed: {type(exc).__name__}: {safe_message}"
                ) from None

        return call


def tushare_config_summary(path: str | Path = ".env.local") -> dict[str, Any]:
    values = _combined_values(path, token_env=TUSHARE_TOKEN_ENV)
    token = values.get(TUSHARE_TOKEN_ENV, "").strip()
    try:
        _validate_token(token, token_env=TUSHARE_TOKEN_ENV)
        token_format_valid = True
    except TushareConfigurationError:
        token_format_valid = False
    try:
        endpoint = _resolve_endpoint(values)
        endpoint_status = "valid"
    except TushareConfigurationError as exc:
        endpoint = None
        endpoint_status = "missing" if "is missing" in str(exc) else "invalid"
    try:
        disable_proxy = _parse_bool(
            values.get(TUSHARE_DISABLE_PROXY_ENV), key=TUSHARE_DISABLE_PROXY_ENV
        )
        proxy_setting_status = "valid"
    except TushareConfigurationError:
        disable_proxy = False
        proxy_setting_status = "invalid"
    return {
        "token_present": bool(token),
        "token_length": len(token),
        "token_format_valid": token_format_valid,
        "endpoint": endpoint,
        "endpoint_status": endpoint_status,
        "disable_proxy": disable_proxy,
        "proxy_setting_status": proxy_setting_status,
        "proxy_mode": "endpoint_host_bypass" if disable_proxy else "environment",
    }


def get_tushare_pro(
    path: str | Path = ".env.local",
    endpoint: str | None = None,
    *,
    token_env: str = TUSHARE_TOKEN_ENV,
    timeout_seconds: int = DEFAULT_TUSHARE_TIMEOUT_SECONDS,
    disable_proxy: bool | None = None,
) -> Any:
    config = load_tushare_config(
        path,
        endpoint=endpoint,
        token_env=token_env,
        timeout_seconds=timeout_seconds,
        disable_proxy=disable_proxy,
    )
    # Pass the token only to this client instance. Never call ts.set_token(),
    # which may persist a second credential copy in the user's home directory.
    ts = _load_tushare()
    pro = ts.pro_api(config.token, timeout=config.timeout_seconds)
    pro._DataApi__http_url = config.endpoint
    return _SafeTushareClient(pro, config)
