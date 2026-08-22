"""Cutoff-safe, local-first market context for v3 review checkpoints.

This module is the only network-capable *pre-bundle* boundary.  A provider is
never imported here: callers may inject an already configured HTTPS gateway,
and every renderer/replay/API/UI helper below consumes frozen bytes only.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Callable, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .artifact_io import atomic_create_bytes, canonical_json_bytes, load_json_object
from .models import (
    MARKET_FALLBACK_POLICY_VERSION,
    MARKET_FALLBACK_POLICY_VERSION_V2,
    MARKET_PROVIDER_ALLOWLIST,
    MARKET_PROVIDER_ALLOWLIST_SHA256,
    MARKET_PROVIDER_ALLOWLIST_VERSION,
    MARKET_PROVIDER_PARAMETER_ALLOWLIST,
    MARKET_PROVIDER_PARAMETER_ALLOW_EMPTY,
    MARKET_PROVIDER_PARAMETER_MAX_LENGTH,
    MARKET_PROVIDER_PARAMETER_VALUE_PATTERNS,
    MARKET_PROVIDER_SENSITIVE_PARAMETER_PATTERN,
    MARKET_REQUEST_FINGERPRINT_VERSION,
    PUBLIC_INFORMATION_POLICY_VERSION,
    _canonical_market_fallback,
    market_request_fingerprint,
)
from .store import ReviewStore, ReviewStoreError
from .time_utils import parse_datetime, utc_iso


class MarketContextError(ValueError):
    """Raised when market context cannot be frozen without violating policy."""


class MarketContextCutoffUnavailableError(MarketContextError):
    """The real cache-step time is later than the frozen knowledge cutoff."""


class MarketRequestBudgetExhaustedError(MarketContextError):
    """No HTTP attempt remains in the shared per-run market request budget."""


MARKET_CACHE_REQUIREMENT_VERSION = "investment_review.market_cache_requirement.v1"
MARKET_COVERAGE_CLASSIFIER_VERSION = "investment_review.market_coverage_classifier.v1"
MARKET_CONTEXT_RESOLUTION_VERSION = "investment_review.market_context_resolution.v1"
MARKET_CONTEXT_SOURCE_VERSION = "investment_review.market_context_source.v1"
MARKET_CACHE_ENTRY_VERSION = "investment_review.market_cache_entry.v1"
MARKET_CONTEXT_MANIFEST_VERSION = "investment_review.market_context_manifest.v1"
MARKET_SOURCE_MANIFEST_VERSION = "investment_review.market_source_manifest.v1"
MARKET_SOURCE_REPLAY_VERSION = "investment_review.market_context_source_replay.v1"
MARKET_GATEWAY_CONTRACT_VERSION = "investment_review.market_gateway.v1"
MARKET_RATE_LIMIT_POLICY_VERSION = "provider_existing_rate_limit.v1"

# v2 is additive.  The unqualified constants and every v1 builder/validator
# above and below intentionally retain their frozen v1 meaning.
MARKET_CACHE_REQUIREMENT_VERSION_V2 = "investment_review.market_cache_requirement.v2"
MARKET_COVERAGE_CLASSIFIER_VERSION_V2 = "investment_review.market_coverage_classifier.v2"
MARKET_CONTEXT_RESOLUTION_VERSION_V2 = "investment_review.market_context_resolution.v2"
MARKET_CONTEXT_SOURCE_VERSION_V2 = "investment_review.market_context_source.v2"
MARKET_CACHE_ENTRY_VERSION_V2 = "investment_review.market_cache_entry.v2"
MARKET_CONTEXT_MANIFEST_VERSION_V2 = "investment_review.market_context_manifest.v2"
MARKET_SOURCE_MANIFEST_VERSION_V2 = "investment_review.market_source_manifest.v2"
MARKET_SOURCE_REPLAY_VERSION_V2 = "investment_review.market_context_source_replay.v2"
MARKET_CONTEXT_CACHE_REPAIR_VERSION_V2 = (
    "investment_review.current_industry_effective_time_repair.v1"
)
MARKET_INFORMATION_TIME_METHOD_VERSION = "public_information_time.v1"
MARKET_EXCHANGE_PUBLICATION_RULE_VERSION = "exchange_bar_publication_time.v1"

MARKET_COMPONENTS = (
    "prior_close",
    "instrument",
    "daily",
    "minute",
    "factor",
    "current_industry",
)
DEFAULT_REQUIRED_COMPONENTS = ("prior_close", "instrument")
DEFAULT_OPTIONAL_COMPONENTS = (
    "daily",
    "minute",
    "factor",
    "current_industry",
)
DEFAULT_STALENESS_SECONDS = {
    "prior_close": 7 * 24 * 60 * 60,
    "instrument": 10 * 365 * 24 * 60 * 60,
    "daily": 7 * 24 * 60 * 60,
    "minute": 24 * 60 * 60,
    "factor": 90 * 24 * 60 * 60,
    "current_industry": 10 * 365 * 24 * 60 * 60,
}
MARKET_LIMITS = {
    "timeout_seconds": 20,
    "max_retries": 2,
    "max_concurrency": 2,
    "max_requests_per_run": 20,
}
OFFLINE_CONSUMERS = ("renderer", "source_replay", "api", "ui")
ROW_LIMIT_PER_COMPONENT = 512
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_REQUIREMENT_LOCKS_GUARD = threading.Lock()
_REQUIREMENT_LOCKS: dict[str, threading.Lock] = {}

_TABLES = {
    "prior_close": "close_prices",
    "daily": "daily_bar_observations",
    "minute": "minute_bar_observations",
    "factor": "adjustment_factor_observations",
    "instrument": "instruments",
    "current_industry": "instruments",
}


class MarketRequestBudget:
    """Thread-safe request cap shared across every episode in one run."""

    def __init__(
        self,
        max_requests: int = MARKET_LIMITS["max_requests_per_run"],
    ) -> None:
        if (
            isinstance(max_requests, bool)
            or not isinstance(max_requests, int)
            or not 0 <= max_requests <= MARKET_LIMITS["max_requests_per_run"]
        ):
            raise MarketContextError(
                "market request budget exceeds the frozen run cap"
            )
        self.max_requests = max_requests
        self._used = 0
        self._reserved = 0
        self._active = 0
        self._lock = threading.Lock()
        self._concurrency = threading.BoundedSemaphore(
            MARKET_LIMITS["max_concurrency"]
        )

    def reserve(self, requested_attempts: int = 3) -> int:
        with self._lock:
            remaining = (
                self.max_requests - self._used - self._reserved
            )
            capacity = min(max(0, int(requested_attempts)), remaining)
            self._reserved += capacity
            return capacity

    def settle(
        self, reserved_attempts: int, actual_attempts: int
    ) -> None:
        with self._lock:
            if (
                reserved_attempts < 0
                or actual_attempts < 0
                or actual_attempts > reserved_attempts
                or reserved_attempts > self._reserved
            ):
                raise MarketContextError(
                    "market request budget settlement is invalid"
                )
            self._reserved -= reserved_attempts
            self._used += actual_attempts
            if self._used > self.max_requests:
                raise MarketContextError(
                    "market request budget exceeded the frozen run cap"
                )

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "max_requests": self.max_requests,
                "used_requests": self._used,
                "reserved_requests": self._reserved,
                "active_requests": self._active,
                "remaining_requests": (
                    self.max_requests - self._used - self._reserved
                ),
            }

    def acquire_concurrency_slot(self) -> None:
        self._concurrency.acquire()
        with self._lock:
            self._active += 1
            if self._active > MARKET_LIMITS["max_concurrency"]:
                self._active -= 1
                self._concurrency.release()
                raise MarketContextError(
                    "market gateway concurrency exceeded the frozen cap"
                )

    def release_concurrency_slot(self) -> None:
        with self._lock:
            if self._active <= 0:
                raise MarketContextError(
                    "market gateway concurrency settlement is invalid"
                )
            self._active -= 1
        self._concurrency.release()


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _content_id(value: object) -> str:
    return _sha256_bytes(canonical_json_bytes(value))


def _clone(value: Any) -> Any:
    return json.loads(canonical_json_bytes(value).decode("utf-8"))


def _closed(
    value: object,
    *,
    name: str,
    required: set[str],
    optional: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MarketContextError(f"{name} must be an object")
    result = {str(key): item for key, item in value.items()}
    allowed = required | (optional or set())
    missing = sorted(required - set(result))
    extra = sorted(set(result) - allowed)
    if missing or extra:
        raise MarketContextError(
            f"{name} has an invalid closed shape; missing={missing}, extra={extra}"
        )
    return result


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MarketContextError(f"{name} must be a non-empty string")
    return value.strip()


def _timestamp(value: object, name: str) -> str:
    try:
        return utc_iso(_text(value, name), "UTC")
    except (TypeError, ValueError) as exc:
        raise MarketContextError(f"{name} must be timezone-aware") from exc


def _component_list(values: Iterable[object], name: str) -> list[str]:
    raw = [str(item).strip() for item in values]
    if any(item not in MARKET_COMPONENTS for item in raw):
        raise MarketContextError(f"{name} contains an unsupported market component")
    if len(raw) != len(set(raw)):
        raise MarketContextError(f"{name} contains duplicate components")
    return [item for item in MARKET_COMPONENTS if item in set(raw)]


def _canonical_parameters(
    *, provider_id: str, endpoint_id: str, values: Mapping[str, object]
) -> dict[str, str]:
    provider_endpoint = f"{provider_id}:{endpoint_id}"
    if provider_endpoint not in MARKET_PROVIDER_ALLOWLIST:
        raise MarketContextError("provider endpoint is not code-allowlisted")
    allowed = MARKET_PROVIDER_PARAMETER_ALLOWLIST[provider_endpoint]
    normalized: dict[str, str] = {}
    for raw_key, raw_value in values.items():
        key = _text(raw_key, "provider parameter key")
        if re.search(MARKET_PROVIDER_SENSITIVE_PARAMETER_PATTERN, key, re.I):
            raise MarketContextError("provider parameter key contains sensitive material")
        if key not in allowed:
            raise MarketContextError(
                f"provider parameter is not allowed for {provider_endpoint}: {key}"
            )
        if not isinstance(raw_value, str):
            raise MarketContextError("provider parameter values must be strings")
        text = raw_value.strip()
        if not text and key not in MARKET_PROVIDER_PARAMETER_ALLOW_EMPTY:
            raise MarketContextError(f"provider parameter {key} cannot be empty")
        if len(text) > MARKET_PROVIDER_PARAMETER_MAX_LENGTH:
            raise MarketContextError("provider parameter exceeds persistence limit")
        if re.search(MARKET_PROVIDER_SENSITIVE_PARAMETER_PATTERN, text, re.I):
            raise MarketContextError("provider parameter value contains sensitive material")
        pattern = MARKET_PROVIDER_PARAMETER_VALUE_PATTERNS.get(key)
        if pattern is None or re.fullmatch(pattern, text) is None:
            raise MarketContextError(f"invalid provider parameter value for {key}")
        normalized[key] = text
    return dict(sorted(normalized.items()))


def canonical_provider_request(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one derived request without accepting caller-owned fingerprints."""

    item = _closed(
        value,
        name="provider request",
        required={
            "component",
            "provider_id",
            "endpoint_id",
            "provider_version",
            "parameters",
        },
    )
    component = _text(item["component"], "provider request component")
    if component not in MARKET_COMPONENTS:
        raise MarketContextError("provider request component is unsupported")
    provider_id = _text(item["provider_id"], "provider_id")
    endpoint_id = _text(item["endpoint_id"], "endpoint_id")
    provider_version = _text(item["provider_version"], "provider_version")
    if not isinstance(item["parameters"], Mapping):
        raise MarketContextError("provider request parameters must be an object")
    parameters = _canonical_parameters(
        provider_id=provider_id,
        endpoint_id=endpoint_id,
        values=item["parameters"],
    )
    provider_endpoint = f"{provider_id}:{endpoint_id}"
    required_parameters = {
        "baostock:history_k_data_plus_5m": {
            "code",
            "fields",
            "start_date",
            "end_date",
            "frequency",
            "adjustflag",
        },
        "tushare:adj_factor": {"ts_code", "fields"},
        "tushare:cb_daily": {"ts_code", "fields"},
        "tushare:daily": {"ts_code", "fields"},
        "tushare:etf_basic": {"ts_code", "fields"},
        "tushare:etf_mins": {
            "ts_code",
            "fields",
            "freq",
            "start_date",
            "end_date",
        },
        "tushare:fund_adj": {"ts_code", "fields"},
        "tushare:fund_daily": {"ts_code", "fields"},
        "tushare:stk_mins": {
            "ts_code",
            "fields",
            "freq",
            "start_date",
            "end_date",
        },
        "tushare:stock_basic": {"exchange", "list_status", "fields"},
    }[provider_endpoint]
    missing_parameters = sorted(required_parameters - set(parameters))
    if missing_parameters:
        raise MarketContextError(
            "provider request is missing bounded required parameters: "
            + ",".join(missing_parameters)
        )
    dated_endpoints = {
        "tushare:adj_factor",
        "tushare:cb_daily",
        "tushare:daily",
        "tushare:fund_adj",
        "tushare:fund_daily",
    }
    if provider_endpoint in dated_endpoints and not (
        "trade_date" in parameters
        or {"start_date", "end_date"}.issubset(parameters)
    ):
        raise MarketContextError(
            "dated market requests require one bounded date scope"
        )
    minute_endpoints = {
        "tushare:etf_mins",
        "tushare:stk_mins",
        "baostock:history_k_data_plus_5m",
    }
    if provider_endpoint in minute_endpoints and not {
        "start_date",
        "end_date",
    }.issubset(parameters):
        raise MarketContextError(
            "intraday market requests require a bounded date range"
        )
    if {"start_date", "end_date"}.issubset(parameters):
        def date_prefix(raw: str) -> str:
            return raw[:10].replace("-", "")

        if date_prefix(parameters["start_date"]) > date_prefix(
            parameters["end_date"]
        ):
            raise MarketContextError(
                "provider request start_date cannot follow end_date"
            )
    fingerprint = market_request_fingerprint(
        provider_id=provider_id,
        endpoint_id=endpoint_id,
        provider_version=provider_version,
        redacted_parameters=parameters,
    )
    return {
        "component": component,
        "provider_id": provider_id,
        "endpoint_id": endpoint_id,
        "provider_version": provider_version,
        "redacted_parameters": parameters,
        "request_fingerprint_version": MARKET_REQUEST_FINGERPRINT_VERSION,
        "request_fingerprint": fingerprint,
    }


def build_market_cache_requirement(
    *,
    instrument_id: str,
    as_of: str,
    knowledge_cutoff: str,
    required_components: Sequence[str] = DEFAULT_REQUIRED_COMPONENTS,
    optional_components: Sequence[str] = DEFAULT_OPTIONAL_COMPONENTS,
    asset_type_hint: str = "unknown",
    staleness_seconds: Mapping[str, int] | None = None,
    provider_requests: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    required = _component_list(required_components, "required_components")
    optional = _component_list(optional_components, "optional_components")
    if set(required) & set(optional):
        raise MarketContextError("required and optional components must be disjoint")
    if not required:
        raise MarketContextError("at least one required market component is required")
    normalized_as_of = _timestamp(as_of, "as_of")
    normalized_cutoff = _timestamp(knowledge_cutoff, "knowledge_cutoff")
    if parse_datetime(normalized_cutoff, "UTC") < parse_datetime(normalized_as_of, "UTC"):
        raise MarketContextError("knowledge_cutoff cannot precede as_of")
    hint = str(asset_type_hint or "unknown").strip().lower()
    if hint not in {"unknown", "equity", "etf", "convertible_bond"}:
        raise MarketContextError("asset_type_hint is unsupported")
    thresholds = dict(DEFAULT_STALENESS_SECONDS)
    for component, raw_value in dict(staleness_seconds or {}).items():
        if component not in MARKET_COMPONENTS:
            raise MarketContextError("staleness threshold component is unsupported")
        if isinstance(raw_value, bool) or not isinstance(raw_value, int) or raw_value < 0:
            raise MarketContextError("staleness thresholds must be non-negative integers")
        thresholds[component] = raw_value
    requests = sorted(
        (canonical_provider_request(item) for item in provider_requests),
        key=lambda item: (item["component"], item["request_fingerprint"]),
    )
    material = {
        "schema_version": MARKET_CACHE_REQUIREMENT_VERSION,
        "policy_version": MARKET_FALLBACK_POLICY_VERSION,
        "classifier_version": MARKET_COVERAGE_CLASSIFIER_VERSION,
        "instrument_id": _text(instrument_id, "instrument_id").upper(),
        "as_of": normalized_as_of,
        "knowledge_cutoff": normalized_cutoff,
        "required_components": required,
        "optional_components": optional,
        "asset_type_hint": hint,
        "staleness_seconds": {
            component: thresholds[component] for component in MARKET_COMPONENTS
        },
        "row_limit_per_component": ROW_LIMIT_PER_COMPONENT,
        "provider_requests": requests,
    }
    material["requirement_id"] = "market_requirement_" + hashlib.sha256(
        canonical_json_bytes(material)
    ).hexdigest()
    return _clone(material)


def canonical_market_cache_requirement(value: Mapping[str, Any]) -> dict[str, Any]:
    item = _closed(
        value,
        name="market cache requirement",
        required={
            "schema_version",
            "policy_version",
            "classifier_version",
            "requirement_id",
            "instrument_id",
            "as_of",
            "knowledge_cutoff",
            "required_components",
            "optional_components",
            "asset_type_hint",
            "staleness_seconds",
            "row_limit_per_component",
            "provider_requests",
        },
    )
    rebuilt = build_market_cache_requirement(
        instrument_id=item["instrument_id"],
        as_of=item["as_of"],
        knowledge_cutoff=item["knowledge_cutoff"],
        required_components=item["required_components"],
        optional_components=item["optional_components"],
        asset_type_hint=item["asset_type_hint"],
        staleness_seconds=item["staleness_seconds"],
        provider_requests=[
            {
                "component": request["component"],
                "provider_id": request["provider_id"],
                "endpoint_id": request["endpoint_id"],
                "provider_version": request["provider_version"],
                "parameters": request["redacted_parameters"],
            }
            for request in item["provider_requests"]
        ],
    )
    if rebuilt != dict(item):
        raise MarketContextError("market cache requirement identity/content drift")
    return rebuilt


def _path_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "sha256": "sha256:" + digest.hexdigest(),
    }


def _source_snapshot(path: Path) -> dict[str, Any]:
    main = _path_state(path)
    if main is None:
        raise MarketContextError("portfolio market source does not exist")
    wal = _path_state(Path(str(path) + "-wal"))
    shm = _path_state(Path(str(path) + "-shm"))
    if wal is not None and wal["size"] != 0:
        raise MarketContextError("portfolio market source has a non-empty WAL")
    if shm is not None and wal is None:
        raise MarketContextError("portfolio market source has an unpaired SHM")
    return {"main": main, "wal": wal, "shm": shm}


def _canonical_path_state_v2(
    value: Mapping[str, Any], *, name: str
) -> dict[str, Any]:
    item = _closed(
        value,
        name=name,
        required={"size", "mtime_ns", "device", "inode", "sha256"},
    )
    for field in ("size", "mtime_ns", "device", "inode"):
        raw = item[field]
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            raise MarketContextError(f"{name}.{field} must be a non-negative integer")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", str(item["sha256"])) is None:
        raise MarketContextError(f"{name}.sha256 is invalid")
    return _clone(item)


def _canonical_source_read_v2(value: Mapping[str, Any]) -> dict[str, Any]:
    item = _closed(
        value,
        name="v2 market source read",
        required={
            "mode",
            "immutable",
            "query_only",
            "quick_check",
            "source_sha256",
            "source_size",
            "auxiliary_state",
        },
    )
    if item["mode"] == "not_read":
        expected = {
            "mode": "not_read",
            "immutable": True,
            "query_only": True,
            "quick_check": "not_run",
            "source_sha256": None,
            "source_size": None,
            "auxiliary_state": None,
        }
        if item != expected:
            raise MarketContextError("v2 absent source read proof drift")
        return expected
    if (
        item["mode"] != "ro"
        or item["immutable"] is not True
        or item["query_only"] is not True
        or item["quick_check"] != "ok"
        or re.fullmatch(
            r"sha256:[0-9a-f]{64}", str(item["source_sha256"])
        )
        is None
        or isinstance(item["source_size"], bool)
        or not isinstance(item["source_size"], int)
        or item["source_size"] < 0
    ):
        raise MarketContextError("v2 verified source read proof is invalid")
    auxiliary = _closed(
        item["auxiliary_state"],
        name="v2 market source auxiliary state",
        required={"wal", "shm"},
    )
    wal = (
        None
        if auxiliary["wal"] is None
        else _canonical_path_state_v2(
            auxiliary["wal"], name="v2 market source WAL state"
        )
    )
    shm = (
        None
        if auxiliary["shm"] is None
        else _canonical_path_state_v2(
            auxiliary["shm"], name="v2 market source SHM state"
        )
    )
    if wal is not None and wal["size"] != 0:
        raise MarketContextError("v2 market source has a non-empty WAL")
    if shm is not None and wal is None:
        raise MarketContextError("v2 market source has an unpaired SHM")
    result = {
        **item,
        "auxiliary_state": {"wal": wal, "shm": shm},
    }
    if result != item:
        raise MarketContextError("v2 market source read canonical drift")
    return _clone(result)


def _same_source_snapshot(before: Mapping[str, Any], after: Mapping[str, Any]) -> bool:
    return canonical_json_bytes(before) == canonical_json_bytes(after)


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if exists is None:
        return set()
    return {str(row[1]) for row in connection.execute(f'PRAGMA table_xinfo("{table}")')}


def _db_rows(
    connection: sqlite3.Connection, *, table: str, instrument_id: str
) -> tuple[list[dict[str, Any]], set[str]]:
    columns = _table_columns(connection, table)
    if not columns or "ts_code" not in columns:
        return [], columns
    selected = ", ".join(f'"{column}"' for column in sorted(columns))
    rows = connection.execute(
        f'SELECT {selected} FROM "{table}" WHERE ts_code=?', (instrument_id,)
    ).fetchall()
    return [dict(row) for row in rows], columns


def _date_effective(value: object) -> datetime:
    text = str(value or "").strip()
    try:
        day = datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        try:
            day = datetime.strptime(text[:8], "%Y%m%d").date()
        except ValueError as exc:
            raise MarketContextError(f"invalid market trade date: {text!r}") from exc
    return datetime.combine(day, time(15, 0), tzinfo=_SHANGHAI).astimezone(timezone.utc)


def _iso_datetime(value: object, *, default_zone: str = "UTC") -> datetime:
    try:
        return parse_datetime(value, default_zone)
    except (TypeError, ValueError) as exc:
        raise MarketContextError(f"invalid market timestamp: {value!r}") from exc


def _has_market_value(value: object) -> bool:
    return value is not None and bool(str(value).strip())


def _positive_finite_decimal(value: object) -> bool:
    if not _has_market_value(value):
        return False
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return False
    return number.is_finite() and number > 0


def _component_values_sufficient(
    component: str, values: Mapping[str, Any]
) -> bool:
    """Require the material field, not merely a timestamped row shell."""

    if component == "prior_close":
        return _positive_finite_decimal(values.get("close"))
    if component in {"daily", "minute"}:
        return _positive_finite_decimal(
            values.get("close_price")
        ) or _positive_finite_decimal(values.get("close"))
    if component == "factor":
        return _positive_finite_decimal(values.get("adj_factor"))
    if component == "instrument":
        return _has_market_value(values.get("ts_code")) and any(
            _has_market_value(values.get(key))
            for key in ("name", "asset_type", "exchange", "currency")
        )
    if component == "current_industry":
        return _has_market_value(
            values.get("industry_name")
        ) and _has_market_value(values.get("industry_source"))
    return False


def _row_source(
    *,
    component: str,
    instrument_id: str,
    effective_at: datetime,
    observed_at: datetime,
    values: Mapping[str, Any],
    source_table: str,
    source_record_id: str,
    source_provider: str,
    point_in_time: bool | None = None,
    contextual_effective_at: datetime | None = None,
) -> dict[str, Any]:
    effective = contextual_effective_at or effective_at
    knowledge = max(effective, observed_at)
    public_basis = (
        "exchange_calendar"
        if component in {"prior_close", "daily", "minute", "factor"}
        else "unknown"
    )
    temporal_role = "system_known_at_decision"
    if component == "current_industry" or observed_at > effective:
        temporal_role = "reconstructed_public_context"
    payload: dict[str, Any] = {
        "schema_version": MARKET_CONTEXT_SOURCE_VERSION,
        "source_id": "",
        "component": component,
        "origin": "portfolio_local_cache",
        "instrument_id": instrument_id,
        "effective_at": utc_iso(effective, "UTC"),
        "coverage_effective_at": utc_iso(effective_at, "UTC"),
        "publicly_available_at": (
            utc_iso(effective_at, "UTC") if public_basis != "unknown" else None
        ),
        "publicly_available_basis": public_basis,
        "fetched_at": utc_iso(observed_at, "UTC"),
        "system_observed_at": utc_iso(observed_at, "UTC"),
        "temporal_role": temporal_role,
        "source_table": source_table,
        "source_record_id": source_record_id,
        "source_provider": source_provider,
        "point_in_time": point_in_time,
        "values": {
            str(key): None if value is None else str(value)
            for key, value in sorted(values.items())
        },
    }
    source_id = "market_local_" + hashlib.sha256(
        canonical_json_bytes({**payload, "source_id": None})
    ).hexdigest()
    payload["source_id"] = source_id
    warning_codes = (
        ["CURRENT_INDUSTRY_NOT_POINT_IN_TIME"]
        if component == "current_industry"
        else []
    )
    source_kind = {
        "prior_close": "price",
        "daily": "market_context",
        "minute": "market_context",
        "factor": "market_context",
        "instrument": "other",
        "current_industry": "classification",
    }[component]
    return {
        "source_id": source_id,
        "source_kind": source_kind,
        "availability": "available",
        "effective_at": utc_iso(effective, "UTC"),
        "knowledge_at": utc_iso(knowledge, "UTC"),
        "locator": f"portfolio_cache:{source_table}:{source_record_id}",
        "warning_codes": warning_codes,
        "payload": payload,
    }


def _local_sources(
    connection: sqlite3.Connection, requirement: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    instrument_id = str(requirement["instrument_id"])
    as_of = parse_datetime(requirement["as_of"], "UTC")
    cutoff = parse_datetime(requirement["knowledge_cutoff"], "UTC")
    as_of_day = as_of.astimezone(_SHANGHAI).date()
    sources: list[dict[str, Any]] = []
    schema_gaps: dict[str, list[str]] = {component: [] for component in MARKET_COMPONENTS}

    for component in ("prior_close", "daily", "minute", "factor"):
        table = _TABLES[component]
        rows, columns = _db_rows(
            connection, table=table, instrument_id=instrument_id
        )
        if not columns:
            schema_gaps[component].append("SOURCE_TABLE_MISSING")
            continue
        time_field = "bar_time" if component == "minute" else "trade_date"
        observed_field = "fetched_at"
        if time_field not in columns or observed_field not in columns:
            schema_gaps[component].append("SOURCE_TIME_COLUMNS_MISSING")
            continue
        candidates: list[tuple[datetime, datetime, dict[str, Any]]] = []
        for row in rows:
            try:
                effective = (
                    _iso_datetime(row[time_field], default_zone="Asia/Shanghai")
                    if component == "minute"
                    else _date_effective(row[time_field])
                )
                observed = _iso_datetime(row[observed_field], default_zone="UTC")
            except MarketContextError:
                continue
            if observed > cutoff or effective > as_of:
                continue
            if observed < effective:
                schema_gaps[component].append(
                    "SOURCE_OBSERVED_BEFORE_EFFECTIVE"
                )
                continue
            if component != "minute" and effective.astimezone(_SHANGHAI).date() >= as_of_day:
                continue
            candidates.append((effective, observed, row))
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        threshold = int(requirement["staleness_seconds"][component])
        fresh = [item for item in candidates if as_of - item[0] <= timedelta(seconds=threshold)]
        selected = fresh[:ROW_LIMIT_PER_COMPONENT]
        if not selected and candidates:
            selected = candidates[:1]
        for effective, observed, row in selected:
            record_id = str(row.get("observation_id") or row.get("dedupe_key") or _content_id(row))
            provider = str(row.get("source") or "portfolio.local")
            values = {
                key: value
                for key, value in row.items()
                if key not in {"fetched_at", "observation_id", "source", "ts_code"}
            }
            if not _component_values_sufficient(component, values):
                schema_gaps[component].append(
                    "SOURCE_REQUIRED_VALUES_MISSING"
                )
                continue
            sources.append(
                _row_source(
                    component=component,
                    instrument_id=instrument_id,
                    effective_at=effective,
                    observed_at=observed,
                    values=values,
                    source_table=table,
                    source_record_id=record_id,
                    source_provider=provider,
                )
            )

    rows, columns = _db_rows(connection, table="instruments", instrument_id=instrument_id)
    if not rows or "updated_at" not in columns:
        schema_gaps["instrument"].append("INSTRUMENT_IDENTITY_MISSING")
    else:
        row = rows[0]
        try:
            observed = _iso_datetime(row["updated_at"], default_zone="UTC")
        except MarketContextError:
            schema_gaps["instrument"].append("INSTRUMENT_OBSERVATION_TIME_INVALID")
        else:
            if observed <= cutoff:
                values = {
                    key: row.get(key)
                    for key in ("ts_code", "name", "asset_type", "exchange", "currency")
                    if key in columns
                }
                if _component_values_sufficient("instrument", values):
                    sources.append(
                        _row_source(
                            component="instrument",
                            instrument_id=instrument_id,
                            effective_at=min(observed, as_of),
                            observed_at=observed,
                            contextual_effective_at=as_of,
                            values=values,
                            source_table="instruments",
                            source_record_id=instrument_id,
                            source_provider="portfolio.instruments",
                            point_in_time=None,
                        )
                    )
                else:
                    schema_gaps["instrument"].append(
                        "SOURCE_REQUIRED_VALUES_MISSING"
                    )
            else:
                schema_gaps["instrument"].append("INSTRUMENT_WITHHELD_BY_CUTOFF")

        industry_name = str(row.get("industry_name") or "").strip()
        industry_source = str(row.get("industry_source") or "").strip()
        industry_time = row.get("industry_updated_at") or row.get("updated_at")
        if industry_name and industry_source and industry_time:
            try:
                observed = _iso_datetime(industry_time, default_zone="UTC")
            except MarketContextError:
                schema_gaps["current_industry"].append("CURRENT_INDUSTRY_TIME_INVALID")
            else:
                if observed <= cutoff:
                    sources.append(
                        _row_source(
                            component="current_industry",
                            instrument_id=instrument_id,
                            effective_at=min(observed, as_of),
                            observed_at=observed,
                            contextual_effective_at=as_of,
                            values={
                                "industry_name": industry_name,
                                "industry_source": industry_source,
                                "historical_use": "forbidden",
                            },
                            source_table="instruments",
                            source_record_id=instrument_id + ":current_industry",
                            source_provider=industry_source,
                            point_in_time=False,
                        )
                    )
                else:
                    schema_gaps["current_industry"].append("CURRENT_INDUSTRY_WITHHELD_BY_CUTOFF")
        else:
            schema_gaps["current_industry"].append("CURRENT_INDUSTRY_MISSING")

    unique = {str(item["source_id"]): item for item in sources}
    return (
        sorted(unique.values(), key=lambda item: (item["source_kind"], item["source_id"])),
        schema_gaps,
    )


def _coverage(
    requirement: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    schema_gaps: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    as_of = parse_datetime(requirement["as_of"], "UTC")
    required = set(requirement["required_components"])
    details: dict[str, Any] = {}
    for component in MARKET_COMPONENTS:
        rows = [item for item in sources if item.get("payload", {}).get("component") == component]
        latest = None
        if rows:
            latest = max(
                parse_datetime(item["payload"]["coverage_effective_at"], "UTC")
                for item in rows
            )
        if not rows:
            status = "missing"
        elif latest is not None and as_of - latest > timedelta(
            seconds=int(requirement["staleness_seconds"][component])
        ):
            status = "stale"
        else:
            status = "satisfied"
        details[component] = {
            "requirement": "required" if component in required else "optional",
            "status": status,
            "row_count": len(rows),
            "latest_effective_at": utc_iso(latest, "UTC") if latest else None,
            "source_refs": sorted(str(item["source_id"]) for item in rows),
            "reason_codes": sorted(set(str(code) for code in schema_gaps.get(component, []))),
            "temporal_scope": (
                "current_non_point_in_time"
                if component == "current_industry" and rows
                else "point_in_time_or_observation"
            ),
        }
    states = [details[component]["status"] for component in requirement["required_components"]]
    ref_count = sum(len(details[component]["source_refs"]) for component in requirement["required_components"])
    if all(state == "satisfied" for state in states):
        aggregate = "satisfied"
    elif ref_count == 0 and all(state == "missing" for state in states):
        aggregate = "missing"
    elif "missing" in states:
        aggregate = "insufficient"
    elif "stale" in states:
        aggregate = "stale"
    else:
        aggregate = "insufficient"
    result = {
        "schema_version": MARKET_COVERAGE_CLASSIFIER_VERSION,
        "requirement_id": requirement["requirement_id"],
        "status": aggregate,
        "components": details,
        "source_refs": sorted(
            {
                ref
                for component in requirement["required_components"]
                for ref in details[component]["source_refs"]
            }
        ),
    }
    result["content_id"] = _content_id(result)
    return result


def _create_or_compare(path: Path, value: Mapping[str, Any]) -> None:
    data = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_create_bytes(path, data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise MarketContextError(f"create-only market cache conflict: {path.name}")


def _short_cache_name(identity: str) -> str:
    digest = str(identity).rsplit("_", 1)[-1].replace("sha256:", "")
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        digest = hashlib.sha256(str(identity).encode("utf-8")).hexdigest()
    return digest[:20] + ".json"


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


class _MarketRequirementLease:
    """Persistent-file, in-process plus OS lease for one cache requirement."""

    def __init__(self, cache_root: Path, requirement_id: str) -> None:
        lock_name = Path(_short_cache_name(requirement_id)).with_suffix(".lock")
        self.path = cache_root / "locks" / lock_name
        key = os.path.normcase(str(self.path.resolve(strict=False)))
        with _REQUIREMENT_LOCKS_GUARD:
            self._thread_lock = _REQUIREMENT_LOCKS.setdefault(
                key, threading.Lock()
            )
        self._stream: Any | None = None

    def __enter__(self) -> "_MarketRequirementLease":
        self._thread_lock.acquire()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._stream = self.path.open("a+b")
            self._stream.seek(0, os.SEEK_END)
            if self._stream.tell() == 0:
                self._stream.write(b"\0")
                self._stream.flush()
                os.fsync(self._stream.fileno())
            self._stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._stream.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_EX)
            return self
        except Exception:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
            self._thread_lock.release()
            raise

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            if self._stream is not None:
                self._stream.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(
                        self._stream.fileno(), msvcrt.LK_UNLCK, 1
                    )
                else:
                    import fcntl

                    fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
                self._stream.close()
                self._stream = None
        finally:
            self._thread_lock.release()


def market_context_resolution_path(
    cache_root: str | Path, requirement_id: str
) -> Path:
    return Path(cache_root).resolve(strict=False) / "r" / _short_cache_name(
        requirement_id
    )


def _require_cache_authority(
    *, portfolio_db: Path, review_db: Path, cache_root: Path
) -> None:
    sidecar = review_db.resolve(strict=False)
    if (
        sidecar.name != "investment_review_reviewability_v3.sqlite3"
        or sidecar.parent.name != "db"
        or sidecar.parent.parent.name != "data"
    ):
        raise MarketContextError(
            "market cache writes require the explicit v3 reviewability candidate"
        )
    repository_root = sidecar.parent.parent.parent
    authority_root = (
        repository_root
        / ".codex_tmp"
        / "investment_review_product_completion_v3"
        / "market_cache"
    ).resolve(strict=False)
    root = cache_root.resolve(strict=False)
    if not _is_within(root, authority_root):
        raise MarketContextError(
            "market cache root is outside the contract-owned v3 market cache"
        )
    if portfolio_db.resolve(strict=False) == sidecar:
        raise MarketContextError("portfolio source and v3 sidecar must be distinct")
    if root in {
        portfolio_db.resolve(strict=False),
        Path(str(portfolio_db.resolve(strict=False)) + "-wal"),
        Path(str(portfolio_db.resolve(strict=False)) + "-shm"),
    }:
        raise MarketContextError("market cache root cannot target the portfolio source")
    if not sidecar.is_file():
        raise MarketContextError(
            "the explicit v3 reviewability candidate must already exist"
        )
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            sidecar.as_uri() + "?mode=ro&immutable=1", uri=True
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        if int(connection.execute("PRAGMA query_only").fetchone()[0]) != 1:
            raise MarketContextError(
                "v3 candidate authority query_only could not be enabled"
            )
        quick = [
            str(row[0]) for row in connection.execute("PRAGMA quick_check")
        ]
        if quick != ["ok"]:
            raise MarketContextError("v3 candidate authority quick_check failed")
        ReviewStore._validate_reviewability_candidate(connection)
    except (ReviewStoreError, sqlite3.DatabaseError, OSError) as exc:
        raise MarketContextError(
            "review database is not the exact marked v3 candidate"
        ) from exc
    finally:
        if connection is not None:
            connection.close()


def _request_for_missing_close(
    requirement: Mapping[str, Any], sources: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    instrument = next(
        (
            source
            for source in sources
            if source.get("payload", {}).get("component") == "instrument"
        ),
        None,
    )
    asset_type = str(requirement.get("asset_type_hint") or "unknown")
    if instrument is not None:
        asset_type = str(
            instrument.get("payload", {}).get("values", {}).get("asset_type")
            or asset_type
        ).lower()
    endpoint = "fund_daily" if asset_type == "etf" else "daily"
    as_of_day = parse_datetime(requirement["as_of"], "UTC").astimezone(_SHANGHAI).date()
    end_day = as_of_day - timedelta(days=1)
    start_day = end_day - timedelta(days=7)
    return canonical_provider_request(
        {
            "component": "prior_close",
            "provider_id": "tushare",
            "endpoint_id": endpoint,
            "provider_version": "repository_configured_gateway.v1",
            "parameters": {
                "ts_code": str(requirement["instrument_id"]),
                "start_date": start_day.strftime("%Y%m%d"),
                "end_date": end_day.strftime("%Y%m%d"),
                "fields": "ts_code,trade_date,close,pre_close,pct_chg",
            },
        }
    )


def _request_for_missing_close_v2(
    requirement: Mapping[str, Any], sources: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    instrument = next(
        (
            source
            for source in sources
            if source.get("payload", {}).get("component") == "instrument"
            and source.get("payload", {})
            .get("perspective_eligibility", {})
            .get("status")
            == "eligible"
        ),
        None,
    )
    asset_type = str(requirement.get("asset_type_hint") or "unknown")
    if instrument is not None:
        asset_type = str(
            instrument.get("payload", {}).get("values", {}).get("asset_type")
            or asset_type
        ).lower()
    endpoint = "fund_daily" if asset_type == "etf" else "daily"
    anchor_day = parse_datetime(
        requirement["operation_anchor_at"], "UTC"
    ).astimezone(_SHANGHAI).date()
    end_day = anchor_day - timedelta(days=1)
    start_day = end_day - timedelta(days=7)
    return canonical_provider_request(
        {
            "component": "prior_close",
            "provider_id": "tushare",
            "endpoint_id": endpoint,
            "provider_version": "repository_configured_gateway.v1",
            "parameters": {
                "ts_code": str(requirement["instrument_id"]),
                "start_date": start_day.strftime("%Y%m%d"),
                "end_date": end_day.strftime("%Y%m%d"),
                "fields": "ts_code,trade_date,close,pre_close,pct_chg",
            },
        }
    )


def _logical_check_time(
    *, clock: Callable[[], datetime] | None, knowledge_cutoff: str
) -> str:
    cutoff = parse_datetime(knowledge_cutoff, "UTC")
    observed = (
        clock().astimezone(timezone.utc)
        if clock is not None
        else datetime.now(timezone.utc)
    )
    observed = observed.replace(microsecond=0)
    if observed > cutoff:
        raise MarketContextCutoffUnavailableError(
            "provider cache step occurs after knowledge_cutoff; receipt time cannot be fabricated"
        )
    return utc_iso(observed, "UTC")


def _provider_unavailable_fallback(
    requirement: Mapping[str, Any],
    *,
    coverage: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    clock: Callable[[], datetime] | None,
) -> dict[str, Any]:
    request = (
        _clone(requirement["provider_requests"][0])
        if requirement["provider_requests"]
        else _request_for_missing_close(requirement, sources)
    )
    checked_at = _logical_check_time(
        clock=clock, knowledge_cutoff=str(requirement["knowledge_cutoff"])
    )
    lineage_ref = str(requirement["requirement_id"])
    receipt = {
        "receipt_id": "",
        "provider_id": request["provider_id"],
        "endpoint_id": request["endpoint_id"],
        "provider_version": request["provider_version"],
        "redacted_parameters": request["redacted_parameters"],
        "request_fingerprint_version": MARKET_REQUEST_FINGERPRINT_VERSION,
        "request_fingerprint": request["request_fingerprint"],
        "started_at": checked_at,
        "completed_at": checked_at,
        "fetched_at": None,
        "response_status": "provider_unavailable",
        "attempt_count": 0,
        "raw_content_sha256": None,
        "normalized_content_sha256": None,
        "cache_entry_refs": [],
        "cache_lineage": [lineage_ref],
    }
    receipt["receipt_id"] = _receipt_identity(receipt)
    fallback = {
        "policy_version": MARKET_FALLBACK_POLICY_VERSION,
        "allowlist_version": MARKET_PROVIDER_ALLOWLIST_VERSION,
        "allowlist_sha256": MARKET_PROVIDER_ALLOWLIST_SHA256,
        "coverage_before": coverage["status"],
        "coverage_after": coverage["status"],
        "status": "provider_unavailable",
        "request_count": 0,
        "limits": dict(MARKET_LIMITS),
        "allowlist": sorted(MARKET_PROVIDER_ALLOWLIST),
        "cache_refs": sorted(
            {str(source["source_id"]) for source in sources}
            | {
                str(source["payload"]["cache_entry_ref"])
                for source in sources
                if source.get("payload", {}).get("cache_entry_ref")
            }
        ),
        "fetch_receipt_refs": [receipt["receipt_id"]],
        "fetch_receipts": [receipt],
        "offline_consumers": {consumer: False for consumer in OFFLINE_CONSUMERS},
    }
    return _canonical_market_fallback(fallback)


def _require_gateway_contract(gateway: Any) -> None:
    if (
        getattr(gateway, "market_gateway_contract_version", None)
        != MARKET_GATEWAY_CONTRACT_VERSION
        or getattr(gateway, "rate_limit_policy_version", None)
        != MARKET_RATE_LIMIT_POLICY_VERSION
        or getattr(gateway, "enforces_provider_rate_limit", None) is not True
        or getattr(gateway, "enforces_timeout_cap", None) is not True
        or getattr(gateway, "enforces_retry_cap", None) is not True
        or getattr(gateway, "enforces_concurrency_cap", None) is not True
    ):
        raise MarketContextError(
            "provider gateway lacks the closed limits/rate-limit contract"
        )


def _gateway_call(
    gateway: Any,
    request: Mapping[str, Any],
    *,
    max_attempts: int,
) -> Mapping[str, Any]:
    _require_gateway_contract(gateway)
    fetch = getattr(gateway, "fetch", None)
    if fetch is None and callable(gateway):
        fetch = gateway
    if fetch is None:
        raise MarketContextError("provider gateway is not callable")
    result = fetch(
        request=_clone(request),
        timeout_seconds=MARKET_LIMITS["timeout_seconds"],
        max_retries=min(
            MARKET_LIMITS["max_retries"], max(0, max_attempts - 1)
        ),
        max_concurrency=MARKET_LIMITS["max_concurrency"],
        max_requests_per_run=MARKET_LIMITS["max_requests_per_run"],
    )
    if not isinstance(result, Mapping):
        raise MarketContextError("provider gateway response must be an object")
    return result


def _receipt_identity(receipt: Mapping[str, Any]) -> str:
    material = dict(receipt)
    material.pop("receipt_id", None)
    return "market_fetch_receipt_" + hashlib.sha256(
        canonical_json_bytes(material)
    ).hexdigest()


def _cache_entry_identity_material(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": value["schema_version"],
        "origin_requirement": value["origin_requirement"],
        "component": value["component"],
        "provider_id": value["provider_id"],
        "endpoint_id": value["endpoint_id"],
        "provider_version": value["provider_version"],
        "redacted_parameters": value["redacted_parameters"],
        "request_fingerprint_version": value[
            "request_fingerprint_version"
        ],
        "request_fingerprint": value["request_fingerprint"],
        "started_at": value["started_at"],
        "completed_at": value["completed_at"],
        "fetched_at": value["fetched_at"],
        "attempt_count": value["attempt_count"],
        "rows": value["rows"],
        "raw_content_sha256": value["raw_content_sha256"],
        "normalized_content_sha256": value[
            "normalized_content_sha256"
        ],
    }


def _canonical_success_receipt(
    receipt: Mapping[str, Any],
    *,
    requirement: Mapping[str, Any],
    cache_ref: str,
) -> dict[str, Any]:
    if receipt.get("receipt_id") != _receipt_identity(receipt):
        raise MarketContextError("successful market receipt identity drift")
    attempt_count = receipt.get("attempt_count")
    if (
        isinstance(attempt_count, bool)
        or not isinstance(attempt_count, int)
        or not 1 <= attempt_count <= 3
    ):
        raise MarketContextError(
            "successful market receipt requires one to three attempts"
        )
    probe = {
        "policy_version": MARKET_FALLBACK_POLICY_VERSION,
        "allowlist_version": MARKET_PROVIDER_ALLOWLIST_VERSION,
        "allowlist_sha256": MARKET_PROVIDER_ALLOWLIST_SHA256,
        "coverage_before": "missing",
        "coverage_after": "missing",
        "status": "succeeded",
        "request_count": attempt_count,
        "limits": dict(MARKET_LIMITS),
        "allowlist": sorted(MARKET_PROVIDER_ALLOWLIST),
        "cache_refs": [cache_ref],
        "fetch_receipt_refs": [receipt["receipt_id"]],
        "fetch_receipts": [_clone(receipt)],
        "offline_consumers": {
            consumer: False for consumer in OFFLINE_CONSUMERS
        },
    }
    canonical = _canonical_market_fallback(probe)["fetch_receipts"][0]
    if canonical != dict(receipt):
        raise MarketContextError("successful market receipt canonical drift")
    if canonical["cache_entry_refs"] != [cache_ref]:
        raise MarketContextError(
            "successful market receipt cache-entry closure drift"
        )
    origin_requirement_id = str(requirement["requirement_id"])
    if canonical["cache_lineage"] != [origin_requirement_id]:
        raise MarketContextError(
            "successful market receipt origin-requirement lineage drift"
        )
    cutoff = parse_datetime(requirement["knowledge_cutoff"], "UTC")
    if any(
        parse_datetime(canonical[field], "UTC") > cutoff
        for field in ("started_at", "completed_at", "fetched_at")
    ):
        raise MarketContextError(
            "successful market receipt exceeds its origin knowledge cutoff"
        )
    return _clone(canonical)


def _canonical_cache_entry(
    value: Mapping[str, Any], *, path: Path | None = None
) -> dict[str, Any]:
    item = _closed(
        value,
        name="v3 market cache entry",
        required={
            "schema_version",
            "cache_entry_ref",
            "origin_requirement",
            "component",
            "provider_id",
            "endpoint_id",
            "provider_version",
            "redacted_parameters",
            "request_fingerprint_version",
            "request_fingerprint",
            "started_at",
            "completed_at",
            "fetched_at",
            "attempt_count",
            "rows",
            "raw_content_sha256",
            "normalized_content_sha256",
            "origin_fetch_receipt",
            "content_id",
        },
    )
    if item["schema_version"] != MARKET_CACHE_ENTRY_VERSION:
        raise MarketContextError("unsupported v3 market cache entry version")
    requirement = canonical_market_cache_requirement(
        item["origin_requirement"]
    )
    component = _text(item["component"], "cache entry component")
    if component not in MARKET_COMPONENTS:
        raise MarketContextError("v3 market cache component is unsupported")
    request = canonical_provider_request(
        {
            "component": component,
            "provider_id": item["provider_id"],
            "endpoint_id": item["endpoint_id"],
            "provider_version": item["provider_version"],
            "parameters": item["redacted_parameters"],
        }
    )
    for field in (
        "provider_id",
        "endpoint_id",
        "provider_version",
        "redacted_parameters",
        "request_fingerprint_version",
        "request_fingerprint",
    ):
        if item[field] != request[field]:
            raise MarketContextError(
                "v3 market cache request provenance drift"
            )
    started_at = _timestamp(item["started_at"], "cache started_at")
    completed_at = _timestamp(item["completed_at"], "cache completed_at")
    fetched_at = _timestamp(item["fetched_at"], "cache fetched_at")
    if not (
        parse_datetime(started_at, "UTC")
        <= parse_datetime(fetched_at, "UTC")
        <= parse_datetime(completed_at, "UTC")
    ):
        raise MarketContextError("v3 market cache receipt time order drift")
    attempt_count = item["attempt_count"]
    if (
        isinstance(attempt_count, bool)
        or not isinstance(attempt_count, int)
        or not 1 <= attempt_count <= 3
    ):
        raise MarketContextError(
            "v3 successful market cache entry requires an HTTP attempt"
        )
    rows = item["rows"]
    if (
        not isinstance(rows, (list, tuple))
        or not rows
        or len(rows) > ROW_LIMIT_PER_COMPONENT
        or any(not isinstance(row, Mapping) for row in rows)
    ):
        raise MarketContextError("v3 market cache rows are invalid")
    canonical_rows = sorted(
        (_clone(row) for row in rows), key=canonical_json_bytes
    )
    if list(rows) != canonical_rows:
        raise MarketContextError("v3 market cache rows are not canonical")
    as_of = parse_datetime(requirement["as_of"], "UTC")
    fetched = parse_datetime(fetched_at, "UTC")
    instrument_id = str(requirement["instrument_id"])
    for row in canonical_rows:
        if row.get("ts_code") != instrument_id:
            raise MarketContextError(
                "v3 market cache row instrument/requirement drift"
            )
        time_value = row.get("bar_time") or row.get("trade_time")
        if component in {"prior_close", "daily", "factor"}:
            effective = _date_effective(row.get("trade_date"))
        elif component == "minute":
            effective = _iso_datetime(
                time_value, default_zone="Asia/Shanghai"
            )
        else:
            effective = as_of
        if effective > as_of or fetched < effective:
            raise MarketContextError(
                "v3 market cache row violates origin temporal scope"
            )
        if (
            component == "prior_close"
            and effective.astimezone(_SHANGHAI).date()
            >= as_of.astimezone(_SHANGHAI).date()
        ):
            raise MarketContextError(
                "v3 prior-close cache row is not before origin as_of"
            )
        if not _component_values_sufficient(component, row):
            raise MarketContextError(
                "v3 market cache row is materially insufficient"
            )
    normalized_hash = _content_id(canonical_rows)
    if item["normalized_content_sha256"] != normalized_hash:
        raise MarketContextError(
            "v3 market cache normalized content hash drift"
        )
    if re.fullmatch(
        r"sha256:[0-9a-f]{64}", str(item["raw_content_sha256"])
    ) is None:
        raise MarketContextError("v3 market cache raw hash is invalid")
    identity_material = _cache_entry_identity_material(
        {**item, "rows": canonical_rows}
    )
    cache_ref = "market_cache_entry_" + hashlib.sha256(
        canonical_json_bytes(identity_material)
    ).hexdigest()
    if item["cache_entry_ref"] != cache_ref:
        raise MarketContextError("v3 market cache entry identity drift")
    receipt = _canonical_success_receipt(
        item["origin_fetch_receipt"],
        requirement=requirement,
        cache_ref=cache_ref,
    )
    receipt_coupling = {
        "provider_id": item["provider_id"],
        "endpoint_id": item["endpoint_id"],
        "provider_version": item["provider_version"],
        "redacted_parameters": item["redacted_parameters"],
        "request_fingerprint_version": item[
            "request_fingerprint_version"
        ],
        "request_fingerprint": item["request_fingerprint"],
        "started_at": started_at,
        "completed_at": completed_at,
        "fetched_at": fetched_at,
        "attempt_count": attempt_count,
        "raw_content_sha256": item["raw_content_sha256"],
        "normalized_content_sha256": normalized_hash,
    }
    if any(receipt.get(key) != expected for key, expected in receipt_coupling.items()):
        raise MarketContextError(
            "v3 market cache entry/origin receipt provenance drift"
        )
    content_material = dict(item)
    content_material.pop("content_id")
    if item["content_id"] != _content_id(content_material):
        raise MarketContextError("v3 market cache entry content ID drift")
    if path is not None and path.name != _short_cache_name(cache_ref):
        raise MarketContextError("v3 market cache entry filename drift")
    return _clone(
        {
            **item,
            "origin_requirement": requirement,
            "rows": canonical_rows,
            "origin_fetch_receipt": receipt,
        }
    )


def _external_projection_from_entry(
    entry: Mapping[str, Any], requirement: Mapping[str, Any]
) -> dict[str, Any] | None:
    component = str(entry["component"])
    relevant_components = set(requirement["required_components"]) | set(
        requirement["optional_components"]
    )
    if (
        component not in relevant_components
        or entry["origin_requirement"]["instrument_id"]
        != requirement["instrument_id"]
    ):
        return None
    fetched_at = str(entry["fetched_at"])
    fetched = parse_datetime(fetched_at, "UTC")
    as_of = parse_datetime(requirement["as_of"], "UTC")
    cutoff = parse_datetime(requirement["knowledge_cutoff"], "UTC")
    if fetched > cutoff:
        return None
    effective_rows: list[dict[str, Any]] = []
    effective_values: list[datetime] = []
    for row in entry["rows"]:
        time_value = row.get("bar_time") or row.get("trade_time")
        if component in {"prior_close", "daily", "factor"}:
            effective = _date_effective(row.get("trade_date"))
        elif component == "minute":
            effective = _iso_datetime(
                time_value, default_zone="Asia/Shanghai"
            )
        else:
            effective = as_of
        if effective > as_of or fetched < effective:
            continue
        if (
            component == "prior_close"
            and effective.astimezone(_SHANGHAI).date()
            >= as_of.astimezone(_SHANGHAI).date()
        ):
            continue
        if not _component_values_sufficient(component, row):
            continue
        effective_rows.append(_clone(row))
        effective_values.append(effective)
    if not effective_rows:
        return None
    effective_rows.sort(key=canonical_json_bytes)
    effective = max(effective_values)
    cache_ref = str(entry["cache_entry_ref"])
    lineage = sorted(
        {
            str(entry["origin_requirement"]["requirement_id"]),
            str(requirement["requirement_id"]),
        }
    )
    payload: dict[str, Any] = {
        "schema_version": MARKET_CONTEXT_SOURCE_VERSION,
        "source_id": None,
        "component": component,
        "origin": "external_provider_cache",
        "instrument_id": str(requirement["instrument_id"]),
        "effective_at": utc_iso(effective, "UTC"),
        "coverage_effective_at": utc_iso(effective, "UTC"),
        "publicly_available_at": None,
        "publicly_available_basis": "unknown",
        "fetched_at": fetched_at,
        "system_observed_at": fetched_at,
        "temporal_role": "reconstructed_public_context",
        "source_table": "v3_market_cache",
        "source_record_id": cache_ref,
        "source_provider": (
            f"{entry['provider_id']}:{entry['endpoint_id']}"
        ),
        "point_in_time": (
            False if component == "current_industry" else None
        ),
        "values": {"rows": effective_rows},
        "raw_content_sha256": str(entry["raw_content_sha256"]),
        "normalized_content_sha256": _content_id(effective_rows),
        "cache_entry_normalized_content_sha256": str(
            entry["normalized_content_sha256"]
        ),
        "cache_entry_ref": cache_ref,
        "origin_requirement": _clone(entry["origin_requirement"]),
        "origin_requirement_id": str(
            entry["origin_requirement"]["requirement_id"]
        ),
        "projection_requirement_id": str(requirement["requirement_id"]),
        "origin_fetch_receipt": _clone(entry["origin_fetch_receipt"]),
        "cache_lineage": lineage,
    }
    source_id = "market_external_" + hashlib.sha256(
        canonical_json_bytes(payload)
    ).hexdigest()
    payload["source_id"] = source_id
    return {
        "source_id": source_id,
        "source_kind": (
            "price"
            if component == "prior_close"
            else "classification"
            if component == "current_industry"
            else "market_context"
        ),
        "availability": "available",
        "effective_at": utc_iso(effective, "UTC"),
        "knowledge_at": fetched_at,
        "locator": f"v3_market_cache:{cache_ref}:{source_id}",
        "warning_codes": (
            ["CURRENT_INDUSTRY_NOT_POINT_IN_TIME"]
            if component == "current_industry"
            else []
        ),
        "payload": payload,
    }


def _external_source(
    *,
    request: Mapping[str, Any],
    response: Mapping[str, Any],
    requirement: Mapping[str, Any],
    cache_root: Path,
    persist: bool,
    started_at: str,
    completed_at: str,
    attempt_count: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = response.get("rows")
    if not isinstance(rows, (list, tuple)) or not rows:
        raise MarketContextError("successful provider response requires rows")
    if len(rows) > ROW_LIMIT_PER_COMPONENT:
        raise MarketContextError(
            "provider rows exceed the fixed per-component cap"
        )
    normalized_rows: list[dict[str, str | None]] = []
    effective_values: list[datetime] = []
    component = str(request["component"])
    instrument_id = str(requirement["instrument_id"])
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise MarketContextError("provider rows must contain objects")
        row = {
            str(key): None if value is None else str(value).strip()
            for key, value in sorted(raw.items())
            if str(key)
            in {
                "ts_code",
                "trade_date",
                "bar_time",
                "trade_time",
                "open",
                "high",
                "low",
                "close",
                "pre_close",
                "pct_chg",
                "vol",
                "amount",
                "adj_factor",
                "name",
                "asset_type",
                "exchange",
                "currency",
                "industry",
            }
        }
        if row.get("ts_code") != instrument_id:
            raise MarketContextError("provider row instrument does not match requirement")
        time_value = row.get("bar_time") or row.get("trade_time")
        if component in {"prior_close", "daily", "factor"}:
            time_value = row.get("trade_date")
            effective = _date_effective(time_value)
        elif component == "minute":
            effective = _iso_datetime(time_value, default_zone="Asia/Shanghai")
        else:
            effective = parse_datetime(requirement["as_of"], "UTC")
        if effective > parse_datetime(requirement["as_of"], "UTC"):
            continue
        if _component_values_sufficient(component, row):
            effective_values.append(effective)
            normalized_rows.append(row)
    if not normalized_rows:
        raise MarketContextError(
            "provider rows are not cutoff-safe or materially sufficient"
        )
    fetched_at = _timestamp(response.get("fetched_at"), "provider fetched_at")
    fetched = parse_datetime(fetched_at, "UTC")
    if fetched > parse_datetime(requirement["knowledge_cutoff"], "UTC"):
        raise MarketContextError("provider fetched_at exceeds knowledge cutoff")
    if fetched < max(effective_values):
        raise MarketContextError(
            "provider fetched_at precedes the market effective time"
        )
    normalized_rows.sort(key=lambda row: canonical_json_bytes(row))
    raw_material = response.get("raw_payload", rows)
    if isinstance(raw_material, bytes):
        raw_bytes = raw_material
    elif isinstance(raw_material, str):
        raw_bytes = raw_material.encode("utf-8")
    else:
        raw_bytes = canonical_json_bytes(raw_material)
    raw_hash = _sha256_bytes(raw_bytes)
    normalized_hash = _content_id(normalized_rows)
    cache_material: dict[str, Any] = {
        "schema_version": MARKET_CACHE_ENTRY_VERSION,
        "origin_requirement": _clone(requirement),
        "component": component,
        "provider_id": request["provider_id"],
        "endpoint_id": request["endpoint_id"],
        "provider_version": request["provider_version"],
        "redacted_parameters": _clone(request["redacted_parameters"]),
        "request_fingerprint_version": request[
            "request_fingerprint_version"
        ],
        "request_fingerprint": request["request_fingerprint"],
        "started_at": started_at,
        "completed_at": completed_at,
        "fetched_at": fetched_at,
        "attempt_count": attempt_count,
        "rows": normalized_rows,
        "raw_content_sha256": raw_hash,
        "normalized_content_sha256": normalized_hash,
    }
    cache_ref = "market_cache_entry_" + hashlib.sha256(
        canonical_json_bytes(cache_material)
    ).hexdigest()
    receipt: dict[str, Any] = {
        "receipt_id": "",
        "provider_id": request["provider_id"],
        "endpoint_id": request["endpoint_id"],
        "provider_version": request["provider_version"],
        "redacted_parameters": _clone(request["redacted_parameters"]),
        "request_fingerprint_version": MARKET_REQUEST_FINGERPRINT_VERSION,
        "request_fingerprint": request["request_fingerprint"],
        "started_at": started_at,
        "completed_at": completed_at,
        "fetched_at": fetched_at,
        "response_status": "succeeded",
        "attempt_count": attempt_count,
        "raw_content_sha256": raw_hash,
        "normalized_content_sha256": normalized_hash,
        "cache_entry_refs": [cache_ref],
        "cache_lineage": [str(requirement["requirement_id"])],
    }
    receipt["receipt_id"] = _receipt_identity(receipt)
    receipt = _canonical_success_receipt(
        receipt, requirement=requirement, cache_ref=cache_ref
    )
    entry: dict[str, Any] = {
        **cache_material,
        "cache_entry_ref": cache_ref,
        "origin_fetch_receipt": receipt,
    }
    entry["content_id"] = _content_id(entry)
    entry = _canonical_cache_entry(entry)
    source = _external_projection_from_entry(entry, requirement)
    if source is None:
        raise MarketContextError(
            "successful market cache entry produced no cutoff-safe projection"
        )
    if persist:
        _create_or_compare(
            cache_root / "e" / _short_cache_name(cache_ref), entry
        )
    return source, receipt


def _cached_external_sources(
    cache_root: Path,
    requirement: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Load bounded, hash-closed v3 entries before considering any provider."""

    entry_root = cache_root / "e"
    if not entry_root.exists():
        return []
    paths = sorted(entry_root.glob("*.json"))
    if len(paths) > 4096:
        raise MarketContextError("v3 market cache entry inventory is unbounded")
    sources: list[dict[str, Any]] = []
    for path in paths:
        item = _canonical_cache_entry(
            load_json_object(path), path=path
        )
        source = _external_projection_from_entry(item, requirement)
        if source is not None:
            sources.append(source)
    return sorted(
        {str(source["source_id"]): source for source in sources}.values(),
        key=lambda source: (source["source_kind"], source["source_id"]),
    )


def _controlled_gateway_fallback(
    requirement: Mapping[str, Any],
    *,
    coverage: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    schema_gaps: Mapping[str, Sequence[str]],
    gateway: Any,
    cache_root: Path,
    persist: bool,
    clock: Callable[[], datetime] | None,
    request_budget: MarketRequestBudget,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    if not persist or str(getattr(gateway, "transport_scheme", "")).lower() != "https":
        fallback = _provider_unavailable_fallback(
            requirement, coverage=coverage, sources=sources, clock=clock
        )
        return fallback, list(_clone(sources)), _clone(coverage)
    _require_gateway_contract(gateway)
    unresolved = {
        component
        for component in requirement["required_components"]
        if coverage["components"][component]["status"] != "satisfied"
    }
    requests = [
        _clone(request)
        for request in requirement["provider_requests"]
        if request["component"] in unresolved
    ]
    if not requests and "prior_close" in unresolved:
        requests = [_request_for_missing_close(requirement, sources)]
    if not requests:
        fallback = _provider_unavailable_fallback(
            requirement, coverage=coverage, sources=sources, clock=clock
        )
        return fallback, list(_clone(sources)), _clone(coverage)
    receipts: list[dict[str, Any]] = []
    external_sources: list[dict[str, Any]] = []
    request_count = 0
    for request in requests:
        reserved_attempts = request_budget.reserve(3)
        if reserved_attempts == 0:
            raise MarketRequestBudgetExhaustedError(
                "shared market request budget is exhausted"
            )
        budget_settled = False
        successful_receipt: dict[str, Any] | None = None
        request_budget.acquire_concurrency_slot()
        try:
            started_at = _logical_check_time(
                clock=clock,
                knowledge_cutoff=str(requirement["knowledge_cutoff"]),
            )
            response = _gateway_call(
                gateway,
                request,
                max_attempts=reserved_attempts,
            )
            completed_at = _logical_check_time(
                clock=clock,
                knowledge_cutoff=str(requirement["knowledge_cutoff"]),
            )
            if (
                parse_datetime(completed_at, "UTC")
                - parse_datetime(started_at, "UTC")
                > timedelta(seconds=MARKET_LIMITS["timeout_seconds"])
            ):
                raise MarketContextError(
                    "provider call exceeded the fixed timeout"
                )
            status = str(response.get("response_status") or "failed").lower()
            attempt_count = response.get("attempt_count")
            if (
                isinstance(attempt_count, bool)
                or not isinstance(attempt_count, int)
                or not 0 <= attempt_count <= reserved_attempts
            ):
                raise MarketContextError("gateway attempt_count exceeds fixed retry cap")
            request_budget.settle(reserved_attempts, attempt_count)
            budget_settled = True
            request_count += attempt_count
            if request_count > MARKET_LIMITS["max_requests_per_run"]:
                raise MarketContextError("gateway request total exceeds fixed run cap")
            if parse_datetime(completed_at, "UTC") < parse_datetime(started_at, "UTC"):
                raise MarketContextError("provider receipt time order is invalid")
            if parse_datetime(completed_at, "UTC") > parse_datetime(requirement["knowledge_cutoff"], "UTC"):
                raise MarketContextError("provider receipt exceeds knowledge cutoff")
            cache_refs: list[str] = []
            raw_hash = None
            normalized_hash = None
            fetched_at = None
            if status == "succeeded":
                if attempt_count < 1:
                    raise MarketContextError(
                        "successful provider response requires an HTTP attempt"
                    )
                proposed_fetched_at = _timestamp(
                    response.get("fetched_at"), "provider fetched_at"
                )
                if not (
                    parse_datetime(started_at, "UTC")
                    <= parse_datetime(proposed_fetched_at, "UTC")
                    <= parse_datetime(completed_at, "UTC")
                ):
                    raise MarketContextError(
                        "provider fetched_at is outside receipt interval"
                    )
                source, successful_receipt = _external_source(
                    request=request,
                    response=response,
                    requirement=requirement,
                    cache_root=cache_root,
                    persist=persist,
                    started_at=started_at,
                    completed_at=completed_at,
                    attempt_count=attempt_count,
                )
                fetched_at = source["payload"]["fetched_at"]
                external_sources.append(source)
                cache_refs = list(
                    successful_receipt["cache_entry_refs"]
                )
                raw_hash = successful_receipt["raw_content_sha256"]
                normalized_hash = successful_receipt[
                    "normalized_content_sha256"
                ]
            elif status not in {"failed", "timeout", "rejected", "provider_unavailable"}:
                raise MarketContextError("gateway response status is unsupported")
            if status == "provider_unavailable" and attempt_count != 0:
                raise MarketContextError("provider_unavailable must have zero attempts")
            if status in {"failed", "timeout", "rejected"} and attempt_count == 0:
                raise MarketContextError("attempted failure requires an HTTP attempt")
        except MarketContextError:
            if not budget_settled:
                request_budget.settle(
                    reserved_attempts, reserved_attempts
                )
            raise
        except Exception:
            status = "failed"
            attempt_count = reserved_attempts
            if not budget_settled:
                request_budget.settle(
                    reserved_attempts, attempt_count
                )
            request_count += attempt_count
            completed_at = _logical_check_time(
                clock=clock,
                knowledge_cutoff=str(requirement["knowledge_cutoff"]),
            )
            if (
                parse_datetime(completed_at, "UTC")
                - parse_datetime(started_at, "UTC")
                > timedelta(seconds=MARKET_LIMITS["timeout_seconds"])
            ):
                raise MarketContextError(
                    "provider call exceeded the fixed timeout"
                )
            fetched_at = None
            raw_hash = None
            normalized_hash = None
            cache_refs = []
        finally:
            request_budget.release_concurrency_slot()
        if successful_receipt is not None:
            receipt = successful_receipt
        else:
            receipt = {
                "receipt_id": "",
                "provider_id": request["provider_id"],
                "endpoint_id": request["endpoint_id"],
                "provider_version": request["provider_version"],
                "redacted_parameters": request["redacted_parameters"],
                "request_fingerprint_version": MARKET_REQUEST_FINGERPRINT_VERSION,
                "request_fingerprint": request["request_fingerprint"],
                "started_at": started_at,
                "completed_at": completed_at,
                "fetched_at": fetched_at,
                "response_status": status,
                "attempt_count": attempt_count,
                "raw_content_sha256": raw_hash,
                "normalized_content_sha256": normalized_hash,
                "cache_entry_refs": cache_refs,
                "cache_lineage": [str(requirement["requirement_id"])],
            }
            receipt["receipt_id"] = _receipt_identity(receipt)
        receipts.append(receipt)
        if status == "provider_unavailable":
            break
    combined = sorted(
        {str(source["source_id"]): _clone(source) for source in [*sources, *external_sources]}.values(),
        key=lambda source: (source["source_kind"], source["source_id"]),
    )
    coverage_after = _coverage(requirement, combined, schema_gaps)
    successful = [receipt for receipt in receipts if receipt["response_status"] == "succeeded"]
    if successful:
        fallback_status = "succeeded"
    elif request_count:
        fallback_status = "failed"
    else:
        fallback_status = "provider_unavailable"
    fallback = {
        "policy_version": MARKET_FALLBACK_POLICY_VERSION,
        "allowlist_version": MARKET_PROVIDER_ALLOWLIST_VERSION,
        "allowlist_sha256": MARKET_PROVIDER_ALLOWLIST_SHA256,
        "coverage_before": coverage["status"],
        "coverage_after": coverage_after["status"],
        "status": fallback_status,
        "request_count": request_count,
        "limits": dict(MARKET_LIMITS),
        "allowlist": sorted(MARKET_PROVIDER_ALLOWLIST),
        "cache_refs": sorted(
            {
                str(source["source_id"])
                for source in combined
            }
            | {
                str(source["payload"]["cache_entry_ref"])
                for source in combined
                if source.get("payload", {}).get("cache_entry_ref")
            }
        ),
        "fetch_receipt_refs": sorted(receipt["receipt_id"] for receipt in receipts),
        "fetch_receipts": sorted(receipts, key=lambda receipt: receipt["receipt_id"]),
        "offline_consumers": {consumer: False for consumer in OFFLINE_CONSUMERS},
    }
    return _canonical_market_fallback(fallback), combined, coverage_after


def _not_needed_fallback(
    coverage: Mapping[str, Any], sources: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    frozen_refs = sorted(
        {str(source["source_id"]) for source in sources}
        | {
            str(source["payload"]["cache_entry_ref"])
            for source in sources
            if source.get("payload", {}).get("cache_entry_ref")
        }
    )
    fallback = {
        "policy_version": MARKET_FALLBACK_POLICY_VERSION,
        "allowlist_version": MARKET_PROVIDER_ALLOWLIST_VERSION,
        "allowlist_sha256": MARKET_PROVIDER_ALLOWLIST_SHA256,
        "coverage_before": "satisfied",
        "coverage_after": "satisfied",
        "status": "not_needed",
        "request_count": 0,
        "limits": dict(MARKET_LIMITS),
        "allowlist": sorted(MARKET_PROVIDER_ALLOWLIST),
        "cache_refs": frozen_refs,
        "fetch_receipt_refs": [],
        "fetch_receipts": [],
        "offline_consumers": {consumer: False for consumer in OFFLINE_CONSUMERS},
    }
    if not fallback["cache_refs"]:
        raise MarketContextError("satisfied local coverage requires cache references")
    return _canonical_market_fallback(fallback)


def _market_axis(
    requirement: Mapping[str, Any],
    coverage: Mapping[str, Any],
    fallback: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    row_refs = sorted(str(source["source_id"]) for source in sources)
    cache_entry_refs = sorted(
        {
            str(source["payload"]["cache_entry_ref"])
            for source in sources
            if source.get("payload", {}).get("cache_entry_ref")
        }
    )
    requirement_ref = str(requirement["requirement_id"])
    price_sources = [
        source
        for source in sources
        if source.get("payload", {}).get("component")
        in {"prior_close", "daily", "minute"}
    ]
    all_sources = list(sources)
    latest_observed = max(
        (
            parse_datetime(source["payload"]["system_observed_at"], "UTC")
            for source in all_sources
        ),
        default=None,
    )
    effective_source = max(
        price_sources,
        key=lambda source: parse_datetime(source["payload"]["effective_at"], "UTC"),
        default=None,
    )
    state = str(coverage["status"])
    if state == "satisfied":
        status = "available"
    elif state == "stale":
        status = "stale"
    elif state == "insufficient":
        status = "partial" if row_refs else "insufficient"
    else:
        status = "missing"
    as_of = parse_datetime(requirement["as_of"], "UTC")
    retrospective = any(
        source.get("payload", {}).get("component") == "current_industry"
        or parse_datetime(source["payload"]["system_observed_at"], "UTC")
        > as_of
        for source in all_sources
    )
    if not row_refs:
        role = "missing"
    else:
        role = (
            "reconstructed_public_context"
            if retrospective
            else "system_known_at_decision"
        )
    effective_at = (
        str(effective_source["payload"]["effective_at"])
        if effective_source is not None
        else None
    )
    public_at = (
        effective_source["payload"].get("publicly_available_at")
        if effective_source is not None
        else None
    )
    return {
        "status": status,
        "temporal_role": role,
        "effective_at": effective_at,
        "publicly_available_at": public_at,
        "publicly_available_basis": (
            "exchange_calendar" if public_at is not None else "unknown"
        ),
        "fetched_at": utc_iso(latest_observed, "UTC") if latest_observed else None,
        "system_observed_at": (
            utc_iso(latest_observed, "UTC") if latest_observed else None
        ),
        "summary": {
            "available": "本地市场上下文已按截止时间冻结。",
            "partial": "部分市场上下文可用，其余组件保持缺失。",
            "insufficient": "市场上下文覆盖不足。",
            "stale": "本地市场上下文已过期。",
            "missing": "未取得可冻结的市场上下文。",
        }[status],
        "source_refs": sorted(
            set(row_refs) | set(cache_entry_refs) | {requirement_ref}
        ),
    }


def _market_gaps(
    requirement: Mapping[str, Any],
    coverage: Mapping[str, Any],
    fallback: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    refs = sorted(
        {str(requirement["requirement_id"])}
        | {str(source["source_id"]) for source in sources}
        | {
            str(source["payload"]["cache_entry_ref"])
            for source in sources
            if source.get("payload", {}).get("cache_entry_ref")
        }
    )
    gaps: list[dict[str, Any]] = []
    state = str(coverage["status"])
    if state != "satisfied":
        code = {
            "missing": "MARKET_CONTEXT_MISSING",
            "stale": "MARKET_CONTEXT_STALE",
            "insufficient": "MARKET_CONTEXT_INSUFFICIENT",
        }[state]
        gaps.append(
            {
                "gap_id": "market_gap_"
                + hashlib.sha256(
                    canonical_json_bytes(
                        {"requirement_id": requirement["requirement_id"], "code": code}
                    )
                ).hexdigest()[:32],
                "axis": "market",
                "code": code,
                "severity": "warning",
                "blocks_axis": False,
                "owner": "data",
                "next_step": "保留本地缺口；仅在受控前置缓存步骤补齐。",
                "source_refs": refs,
            }
        )
    if fallback["status"] == "provider_unavailable":
        gaps.append(
            {
                "gap_id": "market_gap_"
                + hashlib.sha256(
                    canonical_json_bytes(
                        {
                            "requirement_id": requirement["requirement_id"],
                            "code": "MARKET_PROVIDER_UNAVAILABLE",
                        }
                    )
                ).hexdigest()[:32],
                "axis": "market",
                "code": "MARKET_PROVIDER_UNAVAILABLE",
                "severity": "info",
                "blocks_axis": False,
                "owner": "system",
                "next_step": "保留市场轴降级；操作事实复盘继续。",
                "source_refs": refs,
            }
        )
    industry = [
        source
        for source in sources
        if source.get("payload", {}).get("component") == "current_industry"
    ]
    if industry:
        gaps.append(
            {
                "gap_id": "market_gap_"
                + hashlib.sha256(
                    canonical_json_bytes(
                        {
                            "requirement_id": requirement["requirement_id"],
                            "code": "CURRENT_INDUSTRY_NOT_POINT_IN_TIME",
                        }
                    )
                ).hexdigest()[:32],
                "axis": "market",
                "code": "CURRENT_INDUSTRY_NOT_POINT_IN_TIME",
                "severity": "info",
                "blocks_axis": False,
                "owner": "data",
                "next_step": "仅作当前分类参考，不用于历史时点断言。",
                "source_refs": sorted(str(source["source_id"]) for source in industry),
            }
        )
    return sorted(gaps, key=lambda gap: gap["gap_id"])


def _source_manifest(sources: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    entries = [
        {
            "source_id": str(source["source_id"]),
            "source_kind": str(source["source_kind"]),
            "payload_content_id": _content_id(source["payload"]),
            "envelope_content_id": _content_id(source),
        }
        for source in sources
    ]
    entries.sort(key=lambda item: (item["source_kind"], item["source_id"]))
    result = {"schema_version": MARKET_SOURCE_MANIFEST_VERSION, "sources": entries}
    result["content_id"] = _content_id(result)
    return result


def _assemble_resolution(
    *,
    requirement: Mapping[str, Any],
    coverage_before: Mapping[str, Any],
    coverage_after: Mapping[str, Any],
    fallback: Mapping[str, Any],
    market_axis: Mapping[str, Any],
    market_gaps: Sequence[Mapping[str, Any]],
    row_sources: Sequence[Mapping[str, Any]],
    source_read: Mapping[str, Any],
) -> dict[str, Any]:
    resolution_id = "market_resolution_" + str(requirement["requirement_id"]).split("_")[-1]
    canonical_rows = _clone(row_sources)
    component_states = coverage_after["components"]
    for source in canonical_rows:
        component = str(source.get("payload", {}).get("component") or "")
        if component_states.get(component, {}).get("status") == "stale":
            source["availability"] = "stale"
    market_input_projection = {
        "requirement_id": requirement["requirement_id"],
        "resolution_id": resolution_id,
        "instrument_id": requirement["instrument_id"],
        "as_of": requirement["as_of"],
        "knowledge_cutoff": requirement["knowledge_cutoff"],
        "coverage_after": coverage_after,
        "market_axis": market_axis,
        "market_fallback": fallback,
        "market_gaps": list(market_gaps),
        "component_sources": canonical_rows,
    }
    market_input_content_id = _content_id(market_input_projection)
    manifest_source_id = "market_manifest_" + market_input_content_id.split(":", 1)[1]
    manifest_payload = {
        "schema_version": MARKET_CONTEXT_MANIFEST_VERSION,
        "source_id": manifest_source_id,
        "requirement_id": requirement["requirement_id"],
        "resolution_id": resolution_id,
        "instrument_id": requirement["instrument_id"],
        "as_of": requirement["as_of"],
        "knowledge_cutoff": requirement["knowledge_cutoff"],
        "market_input_content_id": market_input_content_id,
        "market_status": market_axis["status"],
        "coverage_before": coverage_before,
        "coverage_after": coverage_after,
        "market_fallback": fallback,
        "market_axis": market_axis,
        "market_gaps": list(market_gaps),
        "component_source_ids": sorted(str(source["source_id"]) for source in canonical_rows),
        "source_verification": "verified",
        "network_allowed": False,
    }
    manifest_envelope = {
        "source_id": manifest_source_id,
        "source_kind": "market_context",
        "availability": {
            "available": "available",
            "stale": "stale",
            "partial": "ambiguous",
            "insufficient": "ambiguous",
            "missing": "missing",
            "failed": "missing",
            "withheld": "withheld_by_cutoff",
        }[str(market_axis["status"])],
        "effective_at": requirement["as_of"],
        "knowledge_at": requirement["knowledge_cutoff"],
        "locator": f"market_resolution:{resolution_id}",
        "warning_codes": sorted(gap["code"] for gap in market_gaps),
        "payload": manifest_payload,
    }
    supplementals = sorted(
        [*canonical_rows, manifest_envelope],
        key=lambda source: (source["source_kind"], source["source_id"]),
    )
    source_manifest = _source_manifest(supplementals)
    resolution: dict[str, Any] = {
        "schema_version": MARKET_CONTEXT_RESOLUTION_VERSION,
        "resolution_id": resolution_id,
        "requirement_id": requirement["requirement_id"],
        "as_of": requirement["as_of"],
        "knowledge_cutoff": requirement["knowledge_cutoff"],
        "requirement": _clone(requirement),
        "source_read": _clone(source_read),
        "coverage_before": _clone(coverage_before),
        "coverage_after": _clone(coverage_after),
        "market_axis": _clone(market_axis),
        "market_fallback": _clone(fallback),
        "market_gaps": _clone(market_gaps),
        "supplemental_sources": supplementals,
        "market_source_manifest": source_manifest,
        "market_input_content_id": market_input_content_id,
        "offline_consumers": {consumer: False for consumer in OFFLINE_CONSUMERS},
        "governance": {
            "local_first": True,
            "source_database_read_only": True,
            "current_industry_point_in_time": False,
            "no_owner_action_default_for_market": True,
            "no_network_after_freeze": True,
        },
    }
    resolution["content_id"] = _content_id(resolution)
    return _clone(resolution)


def _resolve_market_context_for_requirement(
    *,
    source_path: Path,
    root: Path,
    requirement: Mapping[str, Any],
    provider_gateway: Any | None,
    clock: Callable[[], datetime] | None,
    run_budget: MarketRequestBudget,
    persist: bool,
) -> dict[str, Any]:
    resolution_path = market_context_resolution_path(
        root, str(requirement["requirement_id"])
    )
    if resolution_path.exists():
        resolution = load_market_context_resolution(resolution_path)
        if resolution["requirement"] != requirement:
            raise MarketContextError("cached market requirement identity drift")
        return market_context_runner_projection(resolution)

    if persist:
        _create_or_compare(
            root / "q" / _short_cache_name(str(requirement["requirement_id"])),
            requirement,
        )

    before = _source_snapshot(source_path)
    uri = source_path.as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        if int(connection.execute("PRAGMA query_only").fetchone()[0]) != 1:
            raise MarketContextError("SQLite query_only could not be enabled")
        quick = [str(row[0]) for row in connection.execute("PRAGMA quick_check")]
        if quick != ["ok"]:
            raise MarketContextError("portfolio market source quick_check failed")
        local_sources, schema_gaps = _local_sources(connection, requirement)
    finally:
        connection.close()
    after = _source_snapshot(source_path)
    if not _same_source_snapshot(before, after):
        raise MarketContextError("portfolio market source changed during immutable read")
    cached_sources = _cached_external_sources(root, requirement)
    local_sources = sorted(
        {
            str(source["source_id"]): source
            for source in [*local_sources, *cached_sources]
        }.values(),
        key=lambda source: (source["source_kind"], source["source_id"]),
    )
    source_read = {
        "mode": "ro",
        "immutable": True,
        "query_only": True,
        "quick_check": "ok",
        "source_sha256": before["main"]["sha256"],
        "source_size": before["main"]["size"],
        "auxiliary_state": {"wal": before["wal"], "shm": before["shm"]},
    }
    coverage_before = _coverage(requirement, local_sources, schema_gaps)
    if coverage_before["status"] == "satisfied":
        fallback = _not_needed_fallback(coverage_before, local_sources)
        resolved_sources = local_sources
        coverage_after = _clone(coverage_before)
    elif provider_gateway is not None:
        fallback, resolved_sources, coverage_after = _controlled_gateway_fallback(
            requirement,
            coverage=coverage_before,
            sources=local_sources,
            schema_gaps=schema_gaps,
            gateway=provider_gateway,
            cache_root=root,
            persist=persist,
            clock=clock,
            request_budget=run_budget,
        )
    else:
        fallback = _provider_unavailable_fallback(
            requirement,
            coverage=coverage_before,
            sources=local_sources,
            clock=clock,
        )
        resolved_sources = local_sources
        coverage_after = _clone(coverage_before)
    axis = _market_axis(requirement, coverage_after, fallback, resolved_sources)
    successful_receipts = [
        receipt
        for receipt in fallback["fetch_receipts"]
        if receipt["response_status"] == "succeeded"
    ]
    if successful_receipts:
        latest_fetch = max(str(receipt["fetched_at"]) for receipt in successful_receipts)
        axis["temporal_role"] = "reconstructed_public_context"
        axis["fetched_at"] = latest_fetch
        axis["system_observed_at"] = latest_fetch
    gaps = _market_gaps(requirement, coverage_after, fallback, resolved_sources)
    resolution = _assemble_resolution(
        requirement=requirement,
        coverage_before=coverage_before,
        coverage_after=coverage_after,
        fallback=fallback,
        market_axis=axis,
        market_gaps=gaps,
        row_sources=resolved_sources,
        source_read=source_read,
    )
    validation = validate_market_context_resolution(resolution)
    if validation["validation_status"] != "accepted":
        raise MarketContextError("market context resolution failed validation")
    if persist:
        _create_or_compare(resolution_path, resolution)
    return market_context_runner_projection(resolution)


def resolve_market_context(
    *,
    portfolio_db: str | Path,
    review_db: str | Path,
    instrument_id: str,
    as_of: str,
    knowledge_cutoff: str,
    cache_root: str | Path,
    required_components: Sequence[str] = DEFAULT_REQUIRED_COMPONENTS,
    optional_components: Sequence[str] = DEFAULT_OPTIONAL_COMPONENTS,
    provider_gateway: Any | None = None,
    clock: Callable[[], datetime] | None = None,
    request_budget: MarketRequestBudget | None = None,
    persist: bool = True,
    asset_type_hint: str = "unknown",
    staleness_seconds: Mapping[str, int] | None = None,
    provider_requests: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Resolve one frozen market input; same requirement reuses exact bytes."""

    source_path = Path(portfolio_db).resolve(strict=False)
    sidecar_path = Path(review_db).resolve(strict=False)
    root = Path(cache_root).resolve(strict=False)
    run_budget = request_budget or MarketRequestBudget()
    _require_cache_authority(
        portfolio_db=source_path, review_db=sidecar_path, cache_root=root
    )
    requirement = build_market_cache_requirement(
        instrument_id=instrument_id,
        as_of=as_of,
        knowledge_cutoff=knowledge_cutoff,
        required_components=required_components,
        optional_components=optional_components,
        asset_type_hint=asset_type_hint,
        staleness_seconds=staleness_seconds,
        provider_requests=provider_requests,
    )
    arguments = {
        "source_path": source_path,
        "root": root,
        "requirement": requirement,
        "provider_gateway": provider_gateway,
        "clock": clock,
        "run_budget": run_budget,
        "persist": persist,
    }
    if not persist:
        return _resolve_market_context_for_requirement(**arguments)
    with _MarketRequirementLease(
        root, str(requirement["requirement_id"])
    ):
        # Recheck the immutable resolution only after the lease is held.  A
        # concurrent process/thread may have completed the exact same flight.
        return _resolve_market_context_for_requirement(**arguments)


def validate_market_context_supplemental_sources(
    values: Sequence[Mapping[str, Any]],
    *,
    expected_market_input_content_id: str | None = None,
) -> dict[str, Any]:
    if isinstance(values, (list, tuple)) and any(
        isinstance(source, Mapping)
        and isinstance(source.get("payload"), Mapping)
        and source["payload"].get("schema_version")
        in {MARKET_CONTEXT_SOURCE_VERSION_V2, MARKET_CONTEXT_MANIFEST_VERSION_V2}
        for source in values
    ):
        return validate_market_context_supplemental_sources_v2(
            values,
            expected_market_input_content_id=expected_market_input_content_id,
        )
    findings: list[dict[str, str]] = []
    try:
        if not isinstance(values, (list, tuple)):
            raise MarketContextError("supplemental_sources must be an array")
        normalized: list[dict[str, Any]] = []
        for index, raw in enumerate(values):
            source = _closed(
                raw,
                name=f"supplemental_sources[{index}]",
                required={
                    "source_id",
                    "source_kind",
                    "availability",
                    "effective_at",
                    "knowledge_at",
                    "locator",
                    "warning_codes",
                    "payload",
                },
            )
            forbidden_aliases = {
                "known_at",
                "fetched_at",
                "recorded_at",
                "occurred_at",
                "observed_at",
            }
            if forbidden_aliases & set(source):
                raise MarketContextError("supplemental envelope uses forbidden time aliases")
            source_id = _text(source["source_id"], "supplemental source_id")
            effective = _timestamp(source["effective_at"], "supplemental effective_at")
            knowledge = _timestamp(source["knowledge_at"], "supplemental knowledge_at")
            if parse_datetime(knowledge, "UTC") < parse_datetime(effective, "UTC"):
                raise MarketContextError("supplemental knowledge_at precedes effective_at")
            if not isinstance(source["payload"], Mapping):
                raise MarketContextError("supplemental payload must be an object")
            if source["payload"].get("source_id") != source_id:
                raise MarketContextError("supplemental payload/source identity mismatch")
            if not isinstance(source["warning_codes"], (list, tuple)):
                raise MarketContextError("supplemental warning_codes must be an array")
            warning_codes = [str(code) for code in source["warning_codes"]]
            if warning_codes != sorted(set(warning_codes)):
                raise MarketContextError("supplemental warning_codes are not canonical")
            if source["availability"] not in {
                "available",
                "stale",
                "ambiguous",
                "missing",
                "withheld_by_cutoff",
            }:
                raise MarketContextError("unsupported market supplemental availability")
            normalized.append(_clone(source))
        source_ids = [str(source["source_id"]) for source in normalized]
        if len(source_ids) != len(set(source_ids)):
            raise MarketContextError("supplemental source IDs must be unique")
        if normalized != sorted(
            normalized, key=lambda source: (source["source_kind"], source["source_id"])
        ):
            raise MarketContextError("supplemental sources are not canonically ordered")
        manifests = [
            source
            for source in normalized
            if source["payload"].get("schema_version") == MARKET_CONTEXT_MANIFEST_VERSION
        ]
        if len(manifests) != 1:
            raise MarketContextError("exactly one market context manifest is required")
        manifest = _closed(
            manifests[0]["payload"],
            name="market manifest payload",
            required={
                "schema_version",
                "source_id",
                "requirement_id",
                "resolution_id",
                "instrument_id",
                "as_of",
                "knowledge_cutoff",
                "market_input_content_id",
                "market_status",
                "coverage_before",
                "coverage_after",
                "market_fallback",
                "market_axis",
                "market_gaps",
                "component_source_ids",
                "source_verification",
                "network_allowed",
            },
        )
        components = [source for source in normalized if source is not manifests[0]]
        if manifest.get("component_source_ids") != sorted(
            str(source["source_id"]) for source in components
        ):
            raise MarketContextError("market manifest component source closure drift")
        if manifest.get("network_allowed") is not False:
            raise MarketContextError("frozen market manifest cannot allow network access")
        if manifest.get("source_verification") != "verified":
            raise MarketContextError("market manifest source verification is not verified")
        replay_projection = {
            "requirement_id": manifest.get("requirement_id"),
            "resolution_id": manifest.get("resolution_id"),
            "instrument_id": manifest.get("instrument_id"),
            "as_of": manifest.get("as_of"),
            "knowledge_cutoff": manifest.get("knowledge_cutoff"),
            "coverage_after": manifest.get("coverage_after"),
            "market_axis": manifest.get("market_axis"),
            "market_fallback": manifest.get("market_fallback"),
            "market_gaps": manifest.get("market_gaps"),
            "component_sources": components,
        }
        replay_input_id = _content_id(replay_projection)
        if manifest.get("market_input_content_id") != replay_input_id:
            raise MarketContextError("market supplemental input hash drift")
        if manifests[0]["source_id"] != (
            "market_manifest_" + replay_input_id.split(":", 1)[1]
        ):
            raise MarketContextError("market supplemental manifest identity drift")
        expected_manifest_availability = {
            "available": "available",
            "stale": "stale",
            "partial": "ambiguous",
            "insufficient": "ambiguous",
            "missing": "missing",
            "failed": "missing",
            "withheld": "withheld_by_cutoff",
        }.get(str(manifest.get("market_status")))
        if manifests[0]["availability"] != expected_manifest_availability:
            raise MarketContextError("market manifest availability/status coupling drift")
        manifest_instrument = _text(
            manifest.get("instrument_id"), "market manifest instrument_id"
        ).upper()
        manifest_as_of = parse_datetime(
            _timestamp(manifest.get("as_of"), "market manifest as_of"),
            "UTC",
        )
        manifest_cutoff = parse_datetime(
            _timestamp(
                manifest.get("knowledge_cutoff"),
                "market manifest knowledge_cutoff",
            ),
            "UTC",
        )
        if manifest_cutoff < manifest_as_of:
            raise MarketContextError(
                "market manifest knowledge cutoff precedes as_of"
            )
        component_states = manifest.get("coverage_after", {}).get("components", {})
        for source in components:
            component = str(source.get("payload", {}).get("component") or "")
            raw_payload = source["payload"]
            origin = str(raw_payload.get("origin") or "")
            base_payload_fields = {
                "schema_version",
                "source_id",
                "component",
                "origin",
                "instrument_id",
                "effective_at",
                "coverage_effective_at",
                "publicly_available_at",
                "publicly_available_basis",
                "fetched_at",
                "system_observed_at",
                "temporal_role",
                "source_table",
                "source_record_id",
                "source_provider",
                "point_in_time",
                "values",
            }
            if origin == "external_provider_cache":
                base_payload_fields |= {
                    "raw_content_sha256",
                    "normalized_content_sha256",
                    "cache_entry_normalized_content_sha256",
                    "cache_entry_ref",
                    "origin_requirement",
                    "origin_requirement_id",
                    "projection_requirement_id",
                    "origin_fetch_receipt",
                    "cache_lineage",
                }
            elif origin != "portfolio_local_cache":
                raise MarketContextError("unsupported market component origin")
            payload = _closed(
                raw_payload,
                name=f"market component payload {source['source_id']}",
                required=base_payload_fields,
            )
            if payload.get("schema_version") != MARKET_CONTEXT_SOURCE_VERSION:
                raise MarketContextError("unsupported market component payload version")
            if component not in MARKET_COMPONENTS:
                raise MarketContextError("unsupported market component payload")
            if payload.get("instrument_id") != manifest_instrument:
                raise MarketContextError(
                    "market component instrument/manifest drift"
                )
            effective_at = parse_datetime(
                _timestamp(
                    payload.get("effective_at"),
                    "market component effective_at",
                ),
                "UTC",
            )
            coverage_effective_at = parse_datetime(
                _timestamp(
                    payload.get("coverage_effective_at"),
                    "market component coverage_effective_at",
                ),
                "UTC",
            )
            fetched_at = parse_datetime(
                _timestamp(
                    payload.get("fetched_at"),
                    "market component fetched_at",
                ),
                "UTC",
            )
            system_observed_at = parse_datetime(
                _timestamp(
                    payload.get("system_observed_at"),
                    "market component system_observed_at",
                ),
                "UTC",
            )
            if (
                effective_at > manifest_as_of
                or coverage_effective_at > manifest_as_of
                or fetched_at > manifest_cutoff
                or system_observed_at > manifest_cutoff
                or fetched_at != system_observed_at
                or fetched_at < coverage_effective_at
            ):
                raise MarketContextError(
                    "market component temporal binding drift"
                )
            if source["effective_at"] != utc_iso(effective_at, "UTC"):
                raise MarketContextError(
                    "market component envelope effective time drift"
                )
            expected_knowledge = utc_iso(
                max(effective_at, system_observed_at), "UTC"
            )
            if source["knowledge_at"] != expected_knowledge:
                raise MarketContextError(
                    "market component envelope knowledge time drift"
                )
            values = payload.get("values")
            if not isinstance(values, Mapping):
                raise MarketContextError(
                    "market component values must be an object"
                )
            if payload.get("origin") == "portfolio_local_cache":
                local_identity_material = {**payload, "source_id": None}
                expected_source_id = "market_local_" + hashlib.sha256(
                    canonical_json_bytes(local_identity_material)
                ).hexdigest()
                if source["source_id"] != expected_source_id:
                    raise MarketContextError("local market source identity drift")
                if not _component_values_sufficient(component, values):
                    raise MarketContextError(
                        "local market source is materially insufficient"
                    )
            else:
                external_identity_material = {**payload, "source_id": None}
                expected_source_id = "market_external_" + hashlib.sha256(
                    canonical_json_bytes(external_identity_material)
                ).hexdigest()
                if source["source_id"] != expected_source_id:
                    raise MarketContextError(
                        "external market projection identity drift"
                    )
                cache_ref = _text(
                    payload.get("cache_entry_ref"),
                    "external market cache_entry_ref",
                )
                if re.fullmatch(
                    r"market_cache_entry_[0-9a-f]{64}", cache_ref
                ) is None:
                    raise MarketContextError(
                        "external market cache entry reference is invalid"
                    )
                origin_requirement = canonical_market_cache_requirement(
                    payload.get("origin_requirement")
                )
                if (
                    payload.get("origin_requirement_id")
                    != origin_requirement["requirement_id"]
                    or payload.get("projection_requirement_id")
                    != manifest.get("requirement_id")
                    or origin_requirement["instrument_id"]
                    != manifest_instrument
                ):
                    raise MarketContextError(
                        "external market requirement lineage drift"
                    )
                expected_lineage = sorted(
                    {
                        str(origin_requirement["requirement_id"]),
                        str(manifest.get("requirement_id")),
                    }
                )
                if payload.get("cache_lineage") != expected_lineage:
                    raise MarketContextError(
                        "external market cache lineage drift"
                    )
                origin_receipt = _canonical_success_receipt(
                    payload.get("origin_fetch_receipt"),
                    requirement=origin_requirement,
                    cache_ref=cache_ref,
                )
                if (
                    payload.get("raw_content_sha256")
                    != origin_receipt["raw_content_sha256"]
                    or payload.get(
                        "cache_entry_normalized_content_sha256"
                    )
                    != origin_receipt["normalized_content_sha256"]
                    or payload.get("fetched_at")
                    != origin_receipt["fetched_at"]
                    or payload.get("system_observed_at")
                    != origin_receipt["fetched_at"]
                    or payload.get("source_provider")
                    != (
                        f"{origin_receipt['provider_id']}:"
                        f"{origin_receipt['endpoint_id']}"
                    )
                    or payload.get("source_record_id") != cache_ref
                ):
                    raise MarketContextError(
                        "external market origin receipt coupling drift"
                    )
                if set(values) != {"rows"} or not isinstance(
                    values.get("rows"), (list, tuple)
                ):
                    raise MarketContextError(
                        "external market projection rows are invalid"
                    )
                projected_rows = list(values["rows"])
                if (
                    not projected_rows
                    or len(projected_rows) > ROW_LIMIT_PER_COMPONENT
                    or any(
                        not isinstance(row, Mapping)
                        for row in projected_rows
                    )
                    or projected_rows
                    != sorted(
                        (_clone(row) for row in projected_rows),
                        key=canonical_json_bytes,
                    )
                    or payload.get("normalized_content_sha256")
                    != _content_id(projected_rows)
                ):
                    raise MarketContextError(
                        "external market selected-row hash closure drift"
                    )
                projected_effective: list[datetime] = []
                for row in projected_rows:
                    if row.get("ts_code") != manifest_instrument:
                        raise MarketContextError(
                            "external market row instrument drift"
                        )
                    time_value = row.get("bar_time") or row.get(
                        "trade_time"
                    )
                    if component in {"prior_close", "daily", "factor"}:
                        row_effective = _date_effective(
                            row.get("trade_date")
                        )
                    elif component == "minute":
                        row_effective = _iso_datetime(
                            time_value, default_zone="Asia/Shanghai"
                        )
                    else:
                        row_effective = manifest_as_of
                    if (
                        row_effective > manifest_as_of
                        or fetched_at < row_effective
                        or not _component_values_sufficient(component, row)
                    ):
                        raise MarketContextError(
                            "external market row temporal/material drift"
                        )
                    if (
                        component == "prior_close"
                        and row_effective.astimezone(_SHANGHAI).date()
                        >= manifest_as_of.astimezone(_SHANGHAI).date()
                    ):
                        raise MarketContextError(
                            "external prior-close row is not before as_of"
                        )
                    projected_effective.append(row_effective)
                if utc_iso(max(projected_effective), "UTC") != payload.get(
                    "coverage_effective_at"
                ):
                    raise MarketContextError(
                        "external market effective-row projection drift"
                    )
            if component == "current_industry" and (
                payload.get("point_in_time") is not False
                or payload.get("temporal_role")
                != "reconstructed_public_context"
                or payload.get("publicly_available_at") is not None
                or payload.get("publicly_available_basis") != "unknown"
            ):
                raise MarketContextError(
                    "current industry must remain retrospective/non-point-in-time"
                )
            if (
                component != "current_industry"
                and system_observed_at > effective_at
                and payload.get("temporal_role")
                != "reconstructed_public_context"
            ):
                raise MarketContextError(
                    "later-observed market data must remain retrospective"
                )
            warning_codes = source["warning_codes"]
            if warning_codes != sorted(set(str(code) for code in warning_codes)):
                raise MarketContextError("market source warning codes are not canonical")
            if source["source_kind"] not in {
                "price",
                "market_context",
                "classification",
                "other",
            }:
                raise MarketContextError("unsupported market supplemental source kind")
            if not isinstance(source["locator"], str) or not source["locator"].strip():
                raise MarketContextError("market source locator is required")
            component_state = component_states.get(component, {}).get("status")
            expected = "stale" if component_state == "stale" else "available"
            if source.get("availability") != expected:
                raise MarketContextError("market component availability/coverage drift")
        if expected_market_input_content_id is not None and manifest.get(
            "market_input_content_id"
        ) != expected_market_input_content_id:
            raise MarketContextError("market input content ID mismatch")
    except (MarketContextError, TypeError, ValueError, KeyError) as exc:
        findings.append({"severity": "blocker", "code": "MARKET_SUPPLEMENTAL_INVALID", "message": str(exc)})
    return {
        "validation_status": "accepted" if not findings else "blocked",
        "finding_count": len(findings),
        "findings": findings,
    }


def _market_input_projection_from_resolution(
    resolution: Mapping[str, Any], component_sources: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    return {
        "requirement_id": resolution["requirement_id"],
        "resolution_id": resolution["resolution_id"],
        "instrument_id": resolution["requirement"]["instrument_id"],
        "as_of": resolution["as_of"],
        "knowledge_cutoff": resolution["knowledge_cutoff"],
        "coverage_after": resolution["coverage_after"],
        "market_axis": resolution["market_axis"],
        "market_fallback": resolution["market_fallback"],
        "market_gaps": resolution["market_gaps"],
        "component_sources": list(component_sources),
    }


def validate_market_context_resolution(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema_version") == MARKET_CONTEXT_RESOLUTION_VERSION_V2:
        return validate_market_context_resolution_v2(value)
    findings: list[dict[str, str]] = []
    try:
        root = _closed(
            value,
            name="market context resolution",
            required={
                "schema_version",
                "resolution_id",
                "requirement_id",
                "as_of",
                "knowledge_cutoff",
                "requirement",
                "source_read",
                "coverage_before",
                "coverage_after",
                "market_axis",
                "market_fallback",
                "market_gaps",
                "supplemental_sources",
                "market_source_manifest",
                "market_input_content_id",
                "offline_consumers",
                "governance",
                "content_id",
            },
        )
        if root["schema_version"] != MARKET_CONTEXT_RESOLUTION_VERSION:
            raise MarketContextError("unsupported market context resolution version")
        supplied_content_id = _text(root["content_id"], "resolution content_id")
        content_material = dict(root)
        content_material.pop("content_id")
        if supplied_content_id != _content_id(content_material):
            raise MarketContextError("market resolution content ID drift")
        requirement = canonical_market_cache_requirement(root["requirement"])
        if root["requirement_id"] != requirement["requirement_id"]:
            raise MarketContextError("market resolution requirement ID drift")
        expected_resolution_id = "market_resolution_" + str(root["requirement_id"]).split("_")[-1]
        if root["resolution_id"] != expected_resolution_id:
            raise MarketContextError("market resolution identity drift")
        if root["as_of"] != requirement["as_of"] or root["knowledge_cutoff"] != requirement["knowledge_cutoff"]:
            raise MarketContextError("market resolution cutoff drift")
        if root["source_read"] != {
            **root["source_read"],
            "mode": "ro",
            "immutable": True,
            "query_only": True,
            "quick_check": "ok",
        }:
            raise MarketContextError("market source read proof is not immutable/query_only")
        fallback = _canonical_market_fallback(root["market_fallback"])
        if fallback != root["market_fallback"]:
            raise MarketContextError("market fallback canonical drift")
        if any(root["offline_consumers"].get(consumer) is not False for consumer in OFFLINE_CONSUMERS):
            raise MarketContextError("post-freeze consumers must remain offline")
        supplemental_validation = validate_market_context_supplemental_sources(
            root["supplemental_sources"],
            expected_market_input_content_id=str(root["market_input_content_id"]),
        )
        if supplemental_validation["validation_status"] != "accepted":
            raise MarketContextError("market supplemental source closure failed")
        component_sources = [
            source
            for source in root["supplemental_sources"]
            if source.get("payload", {}).get("schema_version") != MARKET_CONTEXT_MANIFEST_VERSION
        ]
        expected_input = _content_id(
            _market_input_projection_from_resolution(root, component_sources)
        )
        if root["market_input_content_id"] != expected_input:
            raise MarketContextError("market input content hash drift")
        expected_manifest = _source_manifest(root["supplemental_sources"])
        if root["market_source_manifest"] != expected_manifest:
            raise MarketContextError("market source manifest drift")
        manifest_payload = next(
            source["payload"]
            for source in root["supplemental_sources"]
            if source.get("payload", {}).get("schema_version")
            == MARKET_CONTEXT_MANIFEST_VERSION
        )
        manifest_coupling = {
            "requirement_id": root["requirement_id"],
            "resolution_id": root["resolution_id"],
            "instrument_id": requirement["instrument_id"],
            "as_of": root["as_of"],
            "knowledge_cutoff": root["knowledge_cutoff"],
            "market_input_content_id": root["market_input_content_id"],
            "market_status": root["market_axis"]["status"],
            "coverage_before": root["coverage_before"],
            "coverage_after": root["coverage_after"],
            "market_fallback": root["market_fallback"],
            "market_axis": root["market_axis"],
            "market_gaps": root["market_gaps"],
        }
        if any(manifest_payload.get(key) != expected for key, expected in manifest_coupling.items()):
            raise MarketContextError("market manifest/resolution projection drift")
        coverage_state = str(root["coverage_after"].get("status") or "")
        allowed_market = {
            "satisfied": {"available"},
            "missing": {"missing", "failed"},
            "stale": {"stale", "failed"},
            "insufficient": {"insufficient", "partial", "failed"},
        }
        if root["market_axis"].get("status") not in allowed_market.get(coverage_state, set()):
            raise MarketContextError("market axis/coverage coupling drift")
        source_refs = set(root["market_axis"].get("source_refs", []))
        if not set(fallback["cache_refs"]).issubset(source_refs):
            raise MarketContextError("fallback cache refs are not frozen into market axis")
        expected_cache_refs = sorted(
            {str(source["source_id"]) for source in component_sources}
            | {
                str(source["payload"]["cache_entry_ref"])
                for source in component_sources
                if source.get("payload", {}).get("cache_entry_ref")
            }
        )
        if fallback["cache_refs"] != expected_cache_refs:
            raise MarketContextError(
                "market fallback/source cache reference closure drift"
            )
        cutoff = parse_datetime(root["knowledge_cutoff"], "UTC")
        for receipt in fallback["fetch_receipts"]:
            if receipt.get("receipt_id") != _receipt_identity(receipt):
                raise MarketContextError("market fetch receipt identity drift")
            for field in ("started_at", "completed_at", "fetched_at"):
                if receipt[field] is not None and parse_datetime(receipt[field], "UTC") > cutoff:
                    raise MarketContextError("fetch receipt exceeds knowledge cutoff")
        for source in component_sources:
            payload = source["payload"]
            if payload.get("component") == "current_industry" and payload.get("point_in_time") is not False:
                raise MarketContextError("current industry cannot claim point-in-time status")
    except (MarketContextError, TypeError, ValueError, KeyError) as exc:
        findings.append({"severity": "blocker", "code": "MARKET_RESOLUTION_INVALID", "message": str(exc)})
    return {
        "schema_version": MARKET_CONTEXT_RESOLUTION_VERSION,
        "validation_status": "accepted" if not findings else "blocked",
        "finding_count": len(findings),
        "findings": findings,
    }


def replay_validate_market_context_resolution(value: Mapping[str, Any]) -> dict[str, Any]:
    """Pure offline replay; no database, gateway, socket or clock is accessed."""

    if value.get("schema_version") == MARKET_CONTEXT_RESOLUTION_VERSION_V2:
        return replay_validate_market_context_resolution_v2(value)
    validation = validate_market_context_resolution(value)
    verified = validation["validation_status"] == "accepted"
    return {
        "schema_version": MARKET_SOURCE_REPLAY_VERSION,
        "validation_status": validation["validation_status"],
        "source_verification": "verified" if verified else "blocked",
        "resolution_id": value.get("resolution_id"),
        "requirement_id": value.get("requirement_id"),
        "market_input_content_id": value.get("market_input_content_id"),
        "network_allowed": False,
        "findings": validation["findings"],
    }


def load_market_context_resolution(path: str | Path) -> dict[str, Any]:
    resolution = load_json_object(path)
    if resolution.get("schema_version") == MARKET_CONTEXT_RESOLUTION_VERSION_V2:
        return load_market_context_resolution_v2(path)
    validation = validate_market_context_resolution(resolution)
    if validation["validation_status"] != "accepted":
        raise MarketContextError("cached market context resolution is invalid")
    return _clone(resolution)


def market_context_runner_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    resolution = value.get("resolution") if isinstance(value.get("resolution"), Mapping) else value
    if resolution.get("schema_version") == MARKET_CONTEXT_RESOLUTION_VERSION_V2:
        return market_context_runner_projection_v2(resolution)
    validation = validate_market_context_resolution(resolution)
    if validation["validation_status"] != "accepted":
        raise MarketContextError("cannot project an invalid market resolution")
    replay = replay_validate_market_context_resolution(resolution)
    return {
        "market_axis": _clone(resolution["market_axis"]),
        "market_fallback": _clone(resolution["market_fallback"]),
        "market_gaps": _clone(resolution["market_gaps"]),
        "supplemental_sources": _clone(resolution["supplemental_sources"]),
        "market_input_content_id": str(resolution["market_input_content_id"]),
        "market_requirement_id": str(resolution["requirement_id"]),
        "market_resolution_id": str(resolution["resolution_id"]),
        "as_of": str(resolution["as_of"]),
        "knowledge_cutoff": str(resolution["knowledge_cutoff"]),
        "market_source_manifest": _clone(resolution["market_source_manifest"]),
        "source_replay": replay,
        "resolution": _clone(resolution),
    }


def offline_market_context_for_consumer(
    value: Mapping[str, Any], *, consumer: str
) -> dict[str, Any]:
    if consumer not in OFFLINE_CONSUMERS:
        raise MarketContextError("unsupported frozen market consumer")
    projection = market_context_runner_projection(value)
    if projection["resolution"]["offline_consumers"][consumer] is not False:
        raise MarketContextError("frozen consumer network guard drift")
    return {
        "consumer": consumer,
        "network_allowed": False,
        "market_input_content_id": projection["market_input_content_id"],
        "supplemental_sources": projection["supplemental_sources"],
        "market_axis": projection["market_axis"],
        "market_fallback": projection["market_fallback"],
        "market_gaps": projection["market_gaps"],
        "source_replay": projection["source_replay"],
    }


# ---------------------------------------------------------------------------
# Perspective-aware v2 amendment
# ---------------------------------------------------------------------------

_V2_INFORMATION_BASES = {
    MARKET_EXCHANGE_PUBLICATION_RULE_VERSION,
    "provider_exact_publication_time.v1",
    "provider_publication_date_source_timezone.v1",
    "unknown",
    "conflicted",
}
_V2_ELIGIBILITY_STATES = {"eligible", "ineligible", "ambiguous", "unknown"}
_V2_FALLBACK_STATES = {
    "not_needed",
    "succeeded",
    "failed",
    "provider_unavailable",
    "withheld_by_cutoff",
    "budget_exhausted",
}
_V2_PROVIDER_ROW_KEYS = {
    "ts_code",
    "trade_date",
    "bar_time",
    "trade_time",
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "pct_chg",
    "vol",
    "amount",
    "adj_factor",
    "name",
    "asset_type",
    "exchange",
    "currency",
    "industry",
    "frequency_minutes",
    "publication_status",
    "publicly_available_at",
    "publication_date",
    "publication_timezone",
    "publication_basis",
    "revision_ref",
    "public_time_source_ref",
    "content_sha256",
}
_V2_PROVIDER_METADATA_KEYS = {
    "publication_status",
    "publicly_available_at",
    "publication_date",
    "publication_timezone",
    "publication_basis",
    "revision_ref",
    "public_time_source_ref",
    "content_sha256",
}
_V2_TRUSTED_PROVIDER_PUBLICATION_BASES = {
    "provider_revision_publication_metadata.v1",
    "official_release_metadata.v1",
}
_V2_PROVIDER_REVISION_REF_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._/-]{0,159}"
)
_V2_PROVIDER_ENDPOINT_COMPONENTS = {
    "baostock:history_k_data_plus_5m": frozenset({"minute"}),
    "tushare:adj_factor": frozenset({"factor"}),
    "tushare:cb_daily": frozenset({"prior_close", "daily"}),
    "tushare:daily": frozenset({"prior_close", "daily"}),
    "tushare:etf_basic": frozenset({"instrument"}),
    "tushare:etf_mins": frozenset({"minute"}),
    "tushare:fund_adj": frozenset({"factor"}),
    "tushare:fund_daily": frozenset({"prior_close", "daily"}),
    "tushare:stk_mins": frozenset({"minute"}),
    "tushare:stock_basic": frozenset({"instrument", "current_industry"}),
}


def _validate_provider_component_endpoint_v2(
    *, component: str, provider_id: str, endpoint_id: str
) -> None:
    allowed_components = _V2_PROVIDER_ENDPOINT_COMPONENTS.get(
        f"{provider_id}:{endpoint_id}", frozenset()
    )
    if component not in allowed_components:
        raise MarketContextError(
            "v2 provider endpoint is not allowlisted for the market component"
        )


def _actual_audit_time_v2(clock: Callable[[], datetime] | None) -> str:
    observed = clock() if clock is not None else datetime.now(timezone.utc)
    if not isinstance(observed, datetime) or observed.tzinfo is None:
        raise MarketContextError("v2 acquisition clock must be timezone-aware")
    return utc_iso(observed.astimezone(timezone.utc).replace(microsecond=0), "UTC")


def _explicit_timestamp_v2(value: object, name: str) -> str:
    text = _text(value, name)
    if re.search(r"(?:Z|[+-][0-9]{2}:[0-9]{2})$", text) is None:
        raise MarketContextError(f"{name} must carry an explicit timezone")
    return _timestamp(text, name)


def _ordering_key_v2(
    value: object,
    *,
    name: str,
    event_id: str | None = None,
    effective_at: str | None = None,
) -> list[Any]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise MarketContextError(f"{name} must contain exactly four fields")
    if isinstance(value[1], bool) or not isinstance(value[1], int):
        raise MarketContextError(f"{name}[1] must be an integer")
    tie_break = _text(value[2], f"{name}[2]")
    key_event_id = _text(value[3], f"{name}[3]")
    key_time = _explicit_timestamp_v2(value[0], f"{name}[0]")
    if event_id is not None and key_event_id != event_id:
        raise MarketContextError(f"{name} is not closed over event_id")
    if effective_at is not None and key_time != _explicit_timestamp_v2(
        effective_at, f"{name}.effective_at"
    ):
        raise MarketContextError(f"{name} time differs from event effective_at")
    return [key_time, value[1], tie_break, key_event_id]


def derive_operation_anchor(
    episode: Mapping[str, Any],
    operation_review: Mapping[str, Any],
    *,
    as_of: str,
) -> dict[str, Any]:
    """Delegate anchor truth to the checkpoint module's one canonical helper."""

    from .review_checkpoint import derive_review_checkpoint_operation_anchor

    episode_status = str(episode.get("status") or "").strip().lower()
    if episode_status == "open":
        checkpoint_type = "active_checkpoint"
        checkpoint_as_of = as_of
    elif episode_status == "closed":
        checkpoint_type = "exit"
        checkpoint_as_of = _text(episode.get("closed_at"), "episode closed_at")
    else:
        raise MarketContextError("episode lifecycle cannot select a market anchor")
    try:
        anchor = derive_review_checkpoint_operation_anchor(
            episode,
            operation_review=operation_review,
            checkpoint_type=checkpoint_type,
            checkpoint_as_of=checkpoint_as_of,
        )
    except (TypeError, ValueError) as exc:
        raise MarketContextError("cannot derive canonical operation anchor") from exc
    event_id = _text(
        anchor.get("operation_anchor_event_id"), "operation_anchor_event_id"
    )
    anchor_at = _explicit_timestamp_v2(
        anchor.get("operation_anchor_at"), "operation_anchor_at"
    )
    ordering = _ordering_key_v2(
        anchor.get("operation_anchor_ordering_key"),
        name="operation_anchor_ordering_key",
        event_id=event_id,
        effective_at=anchor_at,
    )
    return {
        "operation_anchor_event_id": event_id,
        "operation_anchor_at": anchor_at,
        "operation_anchor_ordering_key": ordering,
    }


def _validate_provider_request_anchor_scope_v2(
    request: Mapping[str, Any], *, operation_anchor_at: str
) -> None:
    anchor = parse_datetime(operation_anchor_at, "UTC")
    anchor_local = anchor.astimezone(_SHANGHAI)
    anchor_day = anchor_local.date()
    latest_prior_day = anchor_day - timedelta(days=1)
    parameters = request["redacted_parameters"]
    component = str(request["component"])
    trade_date = parameters.get("trade_date")
    if trade_date is not None:
        raw = str(trade_date)
        try:
            trade_day = datetime.strptime(
                raw[:10], "%Y-%m-%d" if "-" in raw[:10] else "%Y%m%d"
            ).date()
        except ValueError as exc:
            raise MarketContextError(
                "v2 provider trade_date is not a canonical date scope"
            ) from exc
        if component == "prior_close" and trade_day > latest_prior_day:
            raise MarketContextError(
                "v2 prior-close provider window exceeds the operation anchor"
            )
        if component != "prior_close" and _date_effective(raw) > anchor:
            raise MarketContextError(
                "v2 provider trade_date exceeds the operation anchor"
            )
    end_date = parameters.get("end_date")
    if end_date is None:
        return
    raw_end = str(end_date)
    has_clock = len(raw_end) > 10
    if has_clock:
        end_instant = _iso_datetime(raw_end, default_zone="Asia/Shanghai")
        if end_instant > anchor:
            raise MarketContextError(
                "v2 provider end_date exceeds the operation anchor"
            )
        end_day = end_instant.astimezone(_SHANGHAI).date()
    else:
        try:
            end_day = datetime.strptime(
                raw_end[:10],
                "%Y-%m-%d" if "-" in raw_end[:10] else "%Y%m%d",
            ).date()
        except ValueError as exc:
            raise MarketContextError(
                "v2 provider end_date is not a canonical date scope"
            ) from exc
    if component == "prior_close":
        if end_day > latest_prior_day:
            raise MarketContextError(
                "v2 prior-close provider window exceeds the operation anchor"
            )
    elif not has_clock and (
        end_day > anchor_day
        or (
            end_day == anchor_day
            and (
                component == "minute"
                or anchor_local.time() < time(15, 0)
            )
        )
    ):
        raise MarketContextError(
            "v2 provider date-only end_date exceeds the operation anchor"
        )


def build_market_cache_requirement_v2(
    *,
    instrument_id: str,
    perspective: str,
    operation_anchor_event_id: str,
    operation_anchor_at: str,
    operation_anchor_ordering_key: Sequence[Any],
    as_of: str,
    knowledge_cutoff: str,
    information_time_policy_version: str = PUBLIC_INFORMATION_POLICY_VERSION,
    required_components: Sequence[str] = DEFAULT_REQUIRED_COMPONENTS,
    optional_components: Sequence[str] = DEFAULT_OPTIONAL_COMPONENTS,
    asset_type_hint: str = "unknown",
    staleness_seconds: Mapping[str, int] | None = None,
    provider_requests: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    normalized_perspective = str(perspective or "").strip().lower()
    if normalized_perspective not in {"user", "system"}:
        raise MarketContextError("v2 market perspective must be user or system")
    if information_time_policy_version != PUBLIC_INFORMATION_POLICY_VERSION:
        raise MarketContextError("unsupported public information-time policy")
    anchor_event_id = _text(
        operation_anchor_event_id, "operation_anchor_event_id"
    )
    anchor_at = _explicit_timestamp_v2(
        operation_anchor_at, "operation_anchor_at"
    )
    ordering = _ordering_key_v2(
        operation_anchor_ordering_key,
        name="operation_anchor_ordering_key",
        event_id=anchor_event_id,
        effective_at=anchor_at,
    )
    normalized_as_of = _explicit_timestamp_v2(as_of, "as_of")
    normalized_cutoff = _explicit_timestamp_v2(
        knowledge_cutoff, "knowledge_cutoff"
    )
    if not (
        parse_datetime(anchor_at, "UTC")
        <= parse_datetime(normalized_as_of, "UTC")
        <= parse_datetime(normalized_cutoff, "UTC")
    ):
        raise MarketContextError(
            "v2 market time boundary requires anchor <= as_of <= knowledge_cutoff"
        )
    required = _component_list(required_components, "required_components")
    optional = _component_list(optional_components, "optional_components")
    if not required or set(required) & set(optional):
        raise MarketContextError(
            "v2 required components must be non-empty and disjoint from optional"
        )
    hint = str(asset_type_hint or "unknown").strip().lower()
    if hint not in {"unknown", "equity", "etf", "convertible_bond"}:
        raise MarketContextError("asset_type_hint is unsupported")
    thresholds = dict(DEFAULT_STALENESS_SECONDS)
    for component, raw_value in dict(staleness_seconds or {}).items():
        if component not in MARKET_COMPONENTS:
            raise MarketContextError("staleness threshold component is unsupported")
        if isinstance(raw_value, bool) or not isinstance(raw_value, int) or raw_value < 0:
            raise MarketContextError(
                "staleness thresholds must be non-negative integers"
            )
        thresholds[component] = raw_value
    requests = sorted(
        (canonical_provider_request(item) for item in provider_requests),
        key=lambda item: (item["component"], item["request_fingerprint"]),
    )
    for request in requests:
        _validate_provider_component_endpoint_v2(
            component=str(request["component"]),
            provider_id=str(request["provider_id"]),
            endpoint_id=str(request["endpoint_id"]),
        )
    for request in requests:
        _validate_provider_request_anchor_scope_v2(
            request, operation_anchor_at=anchor_at
        )
    material: dict[str, Any] = {
        "schema_version": MARKET_CACHE_REQUIREMENT_VERSION_V2,
        "policy_version": MARKET_FALLBACK_POLICY_VERSION_V2,
        "information_time_policy_version": information_time_policy_version,
        "classifier_version": MARKET_COVERAGE_CLASSIFIER_VERSION_V2,
        "instrument_id": _text(instrument_id, "instrument_id").upper(),
        "perspective": normalized_perspective,
        "operation_anchor_event_id": anchor_event_id,
        "operation_anchor_at": anchor_at,
        "operation_anchor_ordering_key": ordering,
        "as_of": normalized_as_of,
        "knowledge_cutoff": normalized_cutoff,
        "required_components": required,
        "optional_components": optional,
        "asset_type_hint": hint,
        "staleness_seconds": {
            component: thresholds[component] for component in MARKET_COMPONENTS
        },
        "row_limit_per_component": ROW_LIMIT_PER_COMPONENT,
        "provider_requests": requests,
    }
    material["requirement_id"] = "market_requirement_v2_" + hashlib.sha256(
        canonical_json_bytes(material)
    ).hexdigest()
    return _clone(material)


def canonical_market_cache_requirement_v2(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    item = _closed(
        value,
        name="v2 market cache requirement",
        required={
            "schema_version",
            "policy_version",
            "information_time_policy_version",
            "classifier_version",
            "requirement_id",
            "instrument_id",
            "perspective",
            "operation_anchor_event_id",
            "operation_anchor_at",
            "operation_anchor_ordering_key",
            "as_of",
            "knowledge_cutoff",
            "required_components",
            "optional_components",
            "asset_type_hint",
            "staleness_seconds",
            "row_limit_per_component",
            "provider_requests",
        },
    )
    if (
        item["schema_version"] != MARKET_CACHE_REQUIREMENT_VERSION_V2
        or item["policy_version"] != MARKET_FALLBACK_POLICY_VERSION_V2
        or item["classifier_version"] != MARKET_COVERAGE_CLASSIFIER_VERSION_V2
    ):
        raise MarketContextError("unsupported v2 market requirement discriminator")
    rebuilt = build_market_cache_requirement_v2(
        instrument_id=item["instrument_id"],
        perspective=item["perspective"],
        operation_anchor_event_id=item["operation_anchor_event_id"],
        operation_anchor_at=item["operation_anchor_at"],
        operation_anchor_ordering_key=item["operation_anchor_ordering_key"],
        as_of=item["as_of"],
        knowledge_cutoff=item["knowledge_cutoff"],
        information_time_policy_version=item["information_time_policy_version"],
        required_components=item["required_components"],
        optional_components=item["optional_components"],
        asset_type_hint=item["asset_type_hint"],
        staleness_seconds=item["staleness_seconds"],
        provider_requests=[
            {
                "component": request["component"],
                "provider_id": request["provider_id"],
                "endpoint_id": request["endpoint_id"],
                "provider_version": request["provider_version"],
                "parameters": request["redacted_parameters"],
            }
            for request in item["provider_requests"]
        ],
    )
    if rebuilt != dict(item):
        raise MarketContextError("v2 market requirement identity/content drift")
    return rebuilt


def _information_time_v2(
    *,
    status: str,
    lower_bound: str | None,
    upper_bound: str | None,
    basis: str,
    revision_ref: str | None,
) -> dict[str, Any]:
    if status not in {"verified", "unknown", "conflicted"}:
        raise MarketContextError("information_time status is unsupported")
    if basis not in _V2_INFORMATION_BASES:
        raise MarketContextError("information_time basis is unsupported")
    if status == "verified":
        lower = _explicit_timestamp_v2(lower_bound, "information_time.lower_bound")
        upper = _explicit_timestamp_v2(upper_bound, "information_time.upper_bound")
        revision = _text(revision_ref, "information_time.revision_ref")
        if parse_datetime(lower, "UTC") > parse_datetime(upper, "UTC"):
            raise MarketContextError("information_time interval is reversed")
        if basis in {"unknown", "conflicted"}:
            raise MarketContextError("verified information_time requires verified basis")
    else:
        if lower_bound is not None or upper_bound is not None:
            raise MarketContextError(
                "unknown/conflicted information_time cannot carry trusted bounds"
            )
        lower = upper = None
        revision = (
            None
            if revision_ref is None
            else _text(revision_ref, "information_time.revision_ref")
        )
        expected_basis = "unknown" if status == "unknown" else "conflicted"
        if basis != expected_basis:
            raise MarketContextError("information_time status/basis drift")
    return {
        "status": status,
        "lower_bound": lower,
        "upper_bound": upper,
        "basis": basis,
        "method_version": MARKET_INFORMATION_TIME_METHOD_VERSION,
        "revision_ref": revision,
    }


def _canonical_information_time_v2(value: Mapping[str, Any]) -> dict[str, Any]:
    item = _closed(
        value,
        name="information_time",
        required={
            "status",
            "lower_bound",
            "upper_bound",
            "basis",
            "method_version",
            "revision_ref",
        },
    )
    if item["method_version"] != MARKET_INFORMATION_TIME_METHOD_VERSION:
        raise MarketContextError("information_time method version drift")
    rebuilt = _information_time_v2(
        status=str(item["status"]),
        lower_bound=item["lower_bound"],
        upper_bound=item["upper_bound"],
        basis=str(item["basis"]),
        revision_ref=item["revision_ref"],
    )
    if rebuilt != dict(item):
        raise MarketContextError("information_time canonical drift")
    return rebuilt


def _version_provenance_v2(
    *,
    status: str,
    content_sha256: str,
    source_ref: str,
    revision_ref: str,
) -> dict[str, str]:
    if status not in {"verified", "unknown", "conflicted"}:
        raise MarketContextError("version provenance status is unsupported")
    content = _text(content_sha256, "version content_sha256")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", content) is None:
        raise MarketContextError("version content hash is invalid")
    source = _text(source_ref, "version source_ref")
    revision = _text(revision_ref, "version revision_ref")
    return {
        "status": status,
        "content_sha256": content,
        "source_ref": source,
        "revision_ref": revision,
    }


def _canonical_version_provenance_v2(
    value: Mapping[str, Any],
) -> dict[str, str]:
    item = _closed(
        value,
        name="version_provenance",
        required={"status", "content_sha256", "source_ref", "revision_ref"},
    )
    rebuilt = _version_provenance_v2(
        status=str(item["status"]),
        content_sha256=str(item["content_sha256"]),
        source_ref=str(item["source_ref"]),
        revision_ref=str(item["revision_ref"]),
    )
    if rebuilt != dict(item):
        raise MarketContextError("version provenance canonical drift")
    return rebuilt


def _perspective_eligibility_v2(
    *,
    requirement: Mapping[str, Any],
    component: str,
    information_time: Mapping[str, Any],
    version_provenance: Mapping[str, Any],
    system_observed_at: str | None,
) -> dict[str, Any]:
    perspective = str(requirement["perspective"])
    anchor_at = str(requirement["operation_anchor_at"])
    anchor = parse_datetime(anchor_at, "UTC")
    projected_user: str | None = None
    projected_system: str | None = None
    if component == "current_industry":
        status = "unknown"
        reason = "current_only_not_point_in_time"
        role = "publication_time_unknown"
    elif perspective == "user":
        info_status = str(information_time["status"])
        version_status = str(version_provenance["status"])
        if info_status == "conflicted" or version_status == "conflicted":
            status = "ambiguous"
            reason = "publication_time_or_revision_conflicted"
            role = "publication_time_ambiguous"
        elif info_status != "verified" or version_status != "verified":
            status = "unknown"
            reason = "publication_time_or_revision_unproven"
            role = "publication_time_unknown"
        elif information_time.get("revision_ref") != version_provenance.get(
            "revision_ref"
        ):
            status = "ambiguous"
            reason = "publication_revision_binding_conflicted"
            role = "publication_time_ambiguous"
        else:
            lower = parse_datetime(information_time["lower_bound"], "UTC")
            upper = parse_datetime(information_time["upper_bound"], "UTC")
            if upper < anchor:
                status = "eligible"
                reason = "verified_publication_strictly_before_operation"
                role = "user_known_at_operation_by_verified_publication"
                projected_user = anchor_at
            elif lower <= anchor <= upper:
                status = "ambiguous"
                reason = "publication_interval_touches_operation_anchor"
                role = "publication_time_ambiguous"
            else:
                status = "ineligible"
                reason = "post_operation_publication"
                role = "retrospective_public_context"
    else:
        information_status = str(information_time["status"])
        version_status = str(version_provenance["status"])
        if information_status == "conflicted" or version_status == "conflicted":
            status = "ambiguous"
            reason = "publication_time_or_revision_conflicted"
            role = "publication_time_ambiguous"
        elif version_status != "verified":
            status = "unknown"
            reason = "publication_time_or_revision_unproven"
            role = "publication_time_unknown"
        elif system_observed_at is None:
            status = "unknown"
            reason = "system_observation_unknown"
            role = "system_observation_unknown"
        else:
            observed = parse_datetime(system_observed_at, "UTC")
            if observed <= anchor:
                status = "eligible"
                reason = "system_observed_no_later_than_operation"
                role = "system_known_at_operation"
                projected_system = _timestamp(
                    system_observed_at, "system_observed_at"
                )
            else:
                status = "ineligible"
                reason = "system_observed_after_operation"
                role = "retrospective_public_context"
    return {
        "perspective": perspective,
        "status": status,
        "reason_code": reason,
        "temporal_role": role,
        "operation_anchor_at": anchor_at,
        "projected_user_known_at": projected_user,
        "projected_system_known_at": projected_system,
        "actual_user_observation_proven": False,
    }


def _canonical_eligibility_v2(
    value: Mapping[str, Any],
    *,
    requirement: Mapping[str, Any],
    component: str,
    information_time: Mapping[str, Any],
    version_provenance: Mapping[str, Any],
    system_observed_at: str | None,
) -> dict[str, Any]:
    item = _closed(
        value,
        name="perspective_eligibility",
        required={
            "perspective",
            "status",
            "reason_code",
            "temporal_role",
            "operation_anchor_at",
            "projected_user_known_at",
            "projected_system_known_at",
            "actual_user_observation_proven",
        },
    )
    if item["status"] not in _V2_ELIGIBILITY_STATES:
        raise MarketContextError("perspective eligibility state is unsupported")
    expected = _perspective_eligibility_v2(
        requirement=requirement,
        component=component,
        information_time=information_time,
        version_provenance=version_provenance,
        system_observed_at=system_observed_at,
    )
    if expected != dict(item):
        raise MarketContextError("perspective eligibility projection drift")
    return expected


def _source_envelope_v2(
    *,
    requirement: Mapping[str, Any],
    component: str,
    origin: str,
    effective_at: datetime,
    coverage_effective_at: datetime,
    fetched_at: datetime,
    system_observed_at: datetime,
    values: Mapping[str, Any],
    information_time: Mapping[str, Any],
    version_provenance: Mapping[str, Any],
    source_table: str,
    source_record_id: str,
    source_provider: str,
    point_in_time: bool | None,
    cache_entry_ref: str | None = None,
    origin_requirement_id: str | None = None,
    origin_fetch_receipt: Mapping[str, Any] | None = None,
    origin_cache_entry: Mapping[str, Any] | None = None,
    origin_local_record: Mapping[str, Any] | None = None,
    raw_content_sha256: str | None = None,
    normalized_content_sha256: str | None = None,
) -> dict[str, Any]:
    normalized_information = _canonical_information_time_v2(information_time)
    normalized_version = _canonical_version_provenance_v2(version_provenance)
    fetched_text = utc_iso(fetched_at, "UTC")
    observed_text = utc_iso(system_observed_at, "UTC")
    eligibility = _perspective_eligibility_v2(
        requirement=requirement,
        component=component,
        information_time=normalized_information,
        version_provenance=normalized_version,
        system_observed_at=observed_text,
    )
    public_at = (
        normalized_information["upper_bound"]
        if normalized_information["status"] == "verified"
        else None
    )
    payload: dict[str, Any] = {
        "schema_version": MARKET_CONTEXT_SOURCE_VERSION_V2,
        "source_id": None,
        "component": component,
        "origin": origin,
        "instrument_id": str(requirement["instrument_id"]),
        "effective_at": utc_iso(effective_at, "UTC"),
        "coverage_effective_at": utc_iso(coverage_effective_at, "UTC"),
        "publicly_available_at": public_at,
        "publicly_available_basis": normalized_information["basis"],
        "fetched_at": fetched_text,
        "system_observed_at": observed_text,
        "temporal_role": eligibility["temporal_role"],
        "information_time": normalized_information,
        "version_provenance": normalized_version,
        "perspective_eligibility": eligibility,
        "source_table": source_table,
        "source_record_id": source_record_id,
        "source_provider": source_provider,
        "point_in_time": point_in_time,
        "values": _clone(values),
        "raw_content_sha256": raw_content_sha256,
        "normalized_content_sha256": normalized_content_sha256,
        "cache_entry_ref": cache_entry_ref,
        "origin_requirement_id": origin_requirement_id,
        "projection_requirement_id": str(requirement["requirement_id"]),
        "origin_fetch_receipt": (
            None if origin_fetch_receipt is None else _clone(origin_fetch_receipt)
        ),
        "origin_cache_entry": (
            None if origin_cache_entry is None else _clone(origin_cache_entry)
        ),
        "origin_local_record": (
            None if origin_local_record is None else _clone(origin_local_record)
        ),
        "cache_lineage": sorted(
            {
                item
                for item in (
                    origin_requirement_id,
                    str(requirement["requirement_id"]),
                )
                if item
            }
        ),
    }
    source_id = "market_source_v2_" + hashlib.sha256(
        canonical_json_bytes(payload)
    ).hexdigest()
    payload["source_id"] = source_id
    return {
        "source_id": source_id,
        "source_kind": {
            "prior_close": "price",
            "daily": "market_context",
            "minute": "market_context",
            "factor": "market_context",
            "instrument": "other",
            "current_industry": "classification",
        }[component],
        "availability": "available",
        "effective_at": utc_iso(effective_at, "UTC"),
        "knowledge_at": observed_text,
        "locator": f"{origin}:{source_table}:{source_record_id}",
        "warning_codes": (
            ["CURRENT_INDUSTRY_NOT_POINT_IN_TIME"]
            if component == "current_industry"
            else []
        ),
        "payload": payload,
    }


def _local_row_source_v2(
    *,
    requirement: Mapping[str, Any],
    component: str,
    effective_at: datetime,
    observed_at: datetime,
    values: Mapping[str, Any],
    source_table: str,
    source_record_id: str,
    source_provider: str,
    point_in_time: bool | None = None,
    contextual_effective_at: datetime | None = None,
    origin_local_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    effective = contextual_effective_at or effective_at
    version_material = {
        "component": component,
        "instrument_id": requirement["instrument_id"],
        "source_table": source_table,
        "source_record_id": source_record_id,
        "values": {
            str(key): None if value is None else str(value)
            for key, value in sorted(values.items())
        },
    }
    content_hash = _content_id(version_material)
    source_ref = f"portfolio_cache:{source_table}:{source_record_id}"
    revision_ref = f"{source_table}:{source_record_id}:{content_hash}"
    version = _version_provenance_v2(
        status="verified",
        content_sha256=content_hash,
        source_ref=source_ref,
        revision_ref=revision_ref,
    )
    if observed_at < effective_at:
        information = _information_time_v2(
            status="conflicted",
            lower_bound=None,
            upper_bound=None,
            basis="conflicted",
            revision_ref=revision_ref,
        )
        version = {**version, "status": "conflicted"}
    elif component in {"prior_close", "daily", "minute"}:
        public_at = effective_at
        if component == "minute":
            raw_frequency = values.get("frequency_minutes")
            if (
                not isinstance(raw_frequency, bool)
                and str(raw_frequency or "").isdigit()
            ):
                public_at += timedelta(minutes=int(str(raw_frequency)))
        if observed_at < public_at:
            information = _information_time_v2(
                status="conflicted",
                lower_bound=None,
                upper_bound=None,
                basis="conflicted",
                revision_ref=revision_ref,
            )
            version = {**version, "status": "conflicted"}
        else:
            public_text = utc_iso(public_at, "UTC")
            information = _information_time_v2(
                status="verified",
                lower_bound=public_text,
                upper_bound=public_text,
                basis=MARKET_EXCHANGE_PUBLICATION_RULE_VERSION,
                revision_ref=revision_ref,
            )
    else:
        information = _information_time_v2(
            status="unknown",
            lower_bound=None,
            upper_bound=None,
            basis="unknown",
            revision_ref=revision_ref,
        )
    return _source_envelope_v2(
        requirement=requirement,
        component=component,
        origin="portfolio_local_cache",
        effective_at=effective,
        coverage_effective_at=effective_at,
        fetched_at=observed_at,
        system_observed_at=observed_at,
        values=version_material["values"],
        information_time=information,
        version_provenance=version,
        source_table=source_table,
        source_record_id=source_record_id,
        source_provider=source_provider,
        point_in_time=point_in_time,
        origin_local_record=origin_local_record,
        normalized_content_sha256=content_hash,
    )


def _canonical_local_record_v2(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not 1 <= len(value) <= 64:
        raise MarketContextError("v2 origin local record is not a bounded object")
    result: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = _text(raw_key, "v2 origin local record key")
        if len(key) > 128 or key in result:
            raise MarketContextError("v2 origin local record key is invalid")
        if isinstance(raw_value, bool) or (
            raw_value is not None
            and not isinstance(raw_value, (str, int, float))
        ):
            raise MarketContextError("v2 origin local record value is not scalar")
        if isinstance(raw_value, str) and len(raw_value) > 4096:
            raise MarketContextError("v2 origin local record value is unbounded")
        result[key] = raw_value
    return _clone(dict(sorted(result.items())))


def _local_source_from_record_v2(
    *,
    requirement: Mapping[str, Any],
    component: str,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    row = _canonical_local_record_v2(record)
    instrument_id = str(requirement["instrument_id"])
    if str(row.get("ts_code") or "").upper() != instrument_id:
        raise MarketContextError("v2 origin local record instrument drift")
    as_of = parse_datetime(requirement["as_of"], "UTC")
    if component in {"prior_close", "daily", "minute", "factor"}:
        table = _TABLES[component]
        time_field = "bar_time" if component == "minute" else "trade_date"
        if time_field not in row or "fetched_at" not in row:
            raise MarketContextError("v2 origin local record lacks time proof")
        effective = (
            _iso_datetime(row[time_field], default_zone="Asia/Shanghai")
            if component == "minute"
            else _date_effective(row[time_field])
        )
        observed = parse_datetime(
            _explicit_timestamp_v2(
                row["fetched_at"], f"{table}.fetched_at"
            ),
            "UTC",
        )
        if observed < effective:
            raise MarketContextError(
                "v2 origin local record was acquired before effective time"
            )
        record_id = str(
            row.get("observation_id")
            or row.get("dedupe_key")
            or _content_id(row)
        )
        values = {
            key: value
            for key, value in row.items()
            if key not in {"fetched_at", "observation_id", "source", "ts_code"}
        }
        source_provider = str(row.get("source") or "portfolio.local")
        point_in_time = None
        contextual_effective_at = None
    elif component == "instrument":
        if "updated_at" not in row:
            raise MarketContextError("v2 origin instrument lacks observation time")
        observed = parse_datetime(
            _explicit_timestamp_v2(
                row["updated_at"], "instruments.updated_at"
            ),
            "UTC",
        )
        if observed > as_of:
            raise MarketContextError("v2 origin instrument follows as_of")
        effective = observed
        record_id = instrument_id
        values = {
            key: row.get(key)
            for key in ("ts_code", "name", "asset_type", "exchange", "currency")
            if key in row
        }
        source_provider = "portfolio.instruments"
        table = "instruments"
        point_in_time = None
        contextual_effective_at = None
    elif component == "current_industry":
        industry_name = str(row.get("industry_name") or "").strip()
        industry_source = str(row.get("industry_source") or "").strip()
        industry_time = row.get("industry_updated_at") or row.get("updated_at")
        if not industry_name or not industry_source or not industry_time:
            raise MarketContextError("v2 origin industry record is incomplete")
        observed = parse_datetime(
            _explicit_timestamp_v2(
                industry_time, "instruments.industry_updated_at"
            ),
            "UTC",
        )
        effective = min(observed, as_of)
        record_id = instrument_id + ":current_industry"
        values = {
            "industry_name": industry_name,
            "industry_source": industry_source,
            "historical_use": "forbidden",
        }
        source_provider = industry_source
        table = "instruments"
        point_in_time = False
        contextual_effective_at = None
    else:
        raise MarketContextError("v2 origin local component is unsupported")
    if not _component_values_sufficient(component, values):
        raise MarketContextError("v2 origin local record is materially insufficient")
    return _local_row_source_v2(
        requirement=requirement,
        component=component,
        effective_at=effective,
        observed_at=observed,
        values=values,
        source_table=table,
        source_record_id=record_id,
        source_provider=source_provider,
        point_in_time=point_in_time,
        contextual_effective_at=contextual_effective_at,
        origin_local_record=row,
    )


def _local_sources_v2(
    connection: sqlite3.Connection, requirement: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    instrument_id = str(requirement["instrument_id"])
    as_of = parse_datetime(requirement["as_of"], "UTC")
    operation_anchor = parse_datetime(requirement["operation_anchor_at"], "UTC")
    anchor_day = operation_anchor.astimezone(_SHANGHAI).date()
    sources: list[dict[str, Any]] = []
    schema_gaps: dict[str, list[str]] = {
        component: [] for component in MARKET_COMPONENTS
    }
    for component in ("prior_close", "daily", "minute", "factor"):
        table = _TABLES[component]
        rows, columns = _db_rows(
            connection, table=table, instrument_id=instrument_id
        )
        if not columns:
            schema_gaps[component].append("SOURCE_TABLE_MISSING")
            continue
        time_field = "bar_time" if component == "minute" else "trade_date"
        if time_field not in columns or "fetched_at" not in columns:
            schema_gaps[component].append("SOURCE_TIME_COLUMNS_MISSING")
            continue
        candidates: list[tuple[datetime, datetime, dict[str, Any]]] = []
        for row in rows:
            try:
                effective = (
                    _iso_datetime(row[time_field], default_zone="Asia/Shanghai")
                    if component == "minute"
                    else _date_effective(row[time_field])
                )
                observed = parse_datetime(
                    _explicit_timestamp_v2(
                        row["fetched_at"], f"{table}.fetched_at"
                    ),
                    "UTC",
                )
            except MarketContextError:
                schema_gaps[component].append("SOURCE_TIME_INVALID")
                continue
            if observed < effective:
                schema_gaps[component].append(
                    "SOURCE_ACQUISITION_PRECEDES_EFFECTIVE"
                )
                continue
            if effective > operation_anchor:
                continue
            if (
                component == "prior_close"
                and effective.astimezone(_SHANGHAI).date() >= anchor_day
            ):
                continue
            candidates.append((effective, observed, row))
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        threshold = int(requirement["staleness_seconds"][component])
        fresh = [
            item
            for item in candidates
            if operation_anchor - item[0] <= timedelta(seconds=threshold)
        ]
        selected = fresh[:ROW_LIMIT_PER_COMPONENT]
        if not selected and candidates:
            selected = candidates[:1]
        for _effective, _observed, row in selected:
            try:
                sources.append(
                    _local_source_from_record_v2(
                        requirement=requirement,
                        component=component,
                        record=row,
                    )
                )
            except MarketContextError:
                schema_gaps[component].append("SOURCE_ORIGIN_PROOF_INVALID")

    rows, columns = _db_rows(
        connection, table="instruments", instrument_id=instrument_id
    )
    if not rows or "updated_at" not in columns:
        schema_gaps["instrument"].append("INSTRUMENT_IDENTITY_MISSING")
        schema_gaps["current_industry"].append("CURRENT_INDUSTRY_MISSING")
    else:
        row = rows[0]
        try:
            observed = parse_datetime(
                _explicit_timestamp_v2(
                    row["updated_at"], "instruments.updated_at"
                ),
                "UTC",
            )
        except MarketContextError:
            schema_gaps["instrument"].append("INSTRUMENT_OBSERVATION_TIME_INVALID")
        else:
            values = {
                key: row.get(key)
                for key in ("ts_code", "name", "asset_type", "exchange", "currency")
                if key in columns
            }
            if (
                observed <= as_of
                and _component_values_sufficient("instrument", values)
            ):
                try:
                    sources.append(
                        _local_source_from_record_v2(
                            requirement=requirement,
                            component="instrument",
                            record=row,
                        )
                    )
                except MarketContextError:
                    schema_gaps["instrument"].append(
                        "SOURCE_ORIGIN_PROOF_INVALID"
                    )
            elif observed > as_of:
                schema_gaps["instrument"].append("INSTRUMENT_OBSERVED_AFTER_AS_OF")
            else:
                schema_gaps["instrument"].append("SOURCE_REQUIRED_VALUES_MISSING")
        industry_name = str(row.get("industry_name") or "").strip()
        industry_source = str(row.get("industry_source") or "").strip()
        industry_time = row.get("industry_updated_at") or row.get("updated_at")
        if industry_name and industry_source and industry_time:
            try:
                observed = parse_datetime(
                    _explicit_timestamp_v2(
                        industry_time, "instruments.industry_updated_at"
                    ),
                    "UTC",
                )
            except MarketContextError:
                schema_gaps["current_industry"].append(
                    "CURRENT_INDUSTRY_TIME_INVALID"
                )
            else:
                try:
                    sources.append(
                        _local_source_from_record_v2(
                            requirement=requirement,
                            component="current_industry",
                            record=row,
                        )
                    )
                except MarketContextError:
                    schema_gaps["current_industry"].append(
                        "SOURCE_ORIGIN_PROOF_INVALID"
                    )
        else:
            schema_gaps["current_industry"].append("CURRENT_INDUSTRY_MISSING")
    unique = {str(item["source_id"]): item for item in sources}
    return (
        sorted(
            unique.values(), key=lambda item: (item["source_kind"], item["source_id"])
        ),
        schema_gaps,
    )


def _coverage_v2(
    requirement: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    schema_gaps: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    operation_anchor = parse_datetime(requirement["operation_anchor_at"], "UTC")
    required = set(requirement["required_components"])
    details: dict[str, Any] = {}
    for component in MARKET_COMPONENTS:
        evidence_rows = [
            item
            for item in sources
            if item.get("payload", {}).get("component") == component
        ]
        if any(
            item.get("payload", {})
            .get("perspective_eligibility", {})
            .get("status")
            == "eligible"
            and (
                parse_datetime(item["payload"]["effective_at"], "UTC")
                > operation_anchor
                or parse_datetime(
                    item["payload"]["coverage_effective_at"], "UTC"
                )
                > operation_anchor
            )
            for item in evidence_rows
        ):
            raise MarketContextError(
                "v2 eligible market source exceeds the operation anchor"
            )
        eligible_rows = [
            item
            for item in evidence_rows
            if item.get("payload", {})
            .get("perspective_eligibility", {})
            .get("status")
            == "eligible"
        ]
        latest = (
            max(
                parse_datetime(
                    item["payload"]["coverage_effective_at"], "UTC"
                )
                for item in eligible_rows
            )
            if eligible_rows
            else None
        )
        if not eligible_rows:
            status = "missing"
        elif latest is not None and operation_anchor - latest > timedelta(
            seconds=int(requirement["staleness_seconds"][component])
        ):
            status = "stale"
        else:
            status = "satisfied"
        retrospective = [
            str(item["source_id"])
            for item in evidence_rows
            if item not in eligible_rows
            and item.get("payload", {})
            .get("perspective_eligibility", {})
            .get("status")
            == "ineligible"
        ]
        unresolved = [
            str(item["source_id"])
            for item in evidence_rows
            if item not in eligible_rows
            and item.get("payload", {})
            .get("perspective_eligibility", {})
            .get("status")
            in {"unknown", "ambiguous"}
        ]
        reason_codes = set(str(code) for code in schema_gaps.get(component, []))
        reason_codes.update(
            str(item.get("payload", {})
                .get("perspective_eligibility", {})
                .get("reason_code") or "")
            for item in evidence_rows
            if item not in eligible_rows
        )
        reason_codes.discard("")
        details[component] = {
            "requirement": "required" if component in required else "optional",
            "status": status,
            "eligible_row_count": len(eligible_rows),
            "evidence_row_count": len(evidence_rows),
            "latest_effective_at": utc_iso(latest, "UTC") if latest else None,
            "eligible_source_refs": sorted(
                str(item["source_id"]) for item in eligible_rows
            ),
            "retrospective_source_refs": sorted(retrospective),
            "unknown_source_refs": sorted(unresolved),
            "reason_codes": sorted(reason_codes),
            "temporal_scope": (
                "current_non_point_in_time"
                if component == "current_industry" and evidence_rows
                else "perspective_eligible_operation_time"
            ),
        }
    states = [
        details[component]["status"]
        for component in requirement["required_components"]
    ]
    eligible_ref_count = sum(
        len(details[component]["eligible_source_refs"])
        for component in requirement["required_components"]
    )
    if all(state == "satisfied" for state in states):
        aggregate = "satisfied"
    elif eligible_ref_count == 0 and all(state == "missing" for state in states):
        aggregate = "missing"
    elif "missing" in states:
        aggregate = "insufficient"
    elif "stale" in states:
        aggregate = "stale"
    else:
        aggregate = "insufficient"
    result: dict[str, Any] = {
        "schema_version": MARKET_COVERAGE_CLASSIFIER_VERSION_V2,
        "requirement_id": requirement["requirement_id"],
        "perspective": requirement["perspective"],
        "status": aggregate,
        "components": details,
        "eligible_source_refs": sorted(
            {
                ref
                for component in requirement["required_components"]
                for ref in details[component]["eligible_source_refs"]
            }
        ),
        "evidence_source_refs": sorted(
            {
                str(item["source_id"])
                for item in sources
                if item.get("payload", {}).get("component")
                in requirement["required_components"]
            }
        ),
    }
    result["content_id"] = _content_id(result)
    return result


def market_row_content_sha256_v2(
    *, component: str, instrument_id: str, row: Mapping[str, Any]
) -> str:
    if component not in MARKET_COMPONENTS:
        raise MarketContextError("market row component is unsupported")
    values = {
        str(key): None if value is None else str(value).strip()
        for key, value in sorted(row.items())
        if str(key) not in _V2_PROVIDER_METADATA_KEYS
    }
    return _content_id(
        {
            "component": component,
            "instrument_id": str(instrument_id).upper(),
            "values": values,
        }
    )


def _provider_publication_source_ref_v2(
    *,
    provider_id: str,
    endpoint_id: str,
    publication_basis: str,
    revision_ref: str,
    content_sha256: str,
    information_time: Mapping[str, Any],
) -> str:
    if f"{provider_id}:{endpoint_id}" not in MARKET_PROVIDER_ALLOWLIST:
        raise MarketContextError("v2 publication source provider is not allowlisted")
    if publication_basis not in _V2_TRUSTED_PROVIDER_PUBLICATION_BASES:
        raise MarketContextError("v2 publication source basis is not trusted")
    if _V2_PROVIDER_REVISION_REF_PATTERN.fullmatch(revision_ref) is None:
        raise MarketContextError("v2 provider revision_ref is not replay-safe")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", content_sha256) is None:
        raise MarketContextError("v2 publication source content hash is invalid")
    information_content_id = _content_id(
        _canonical_information_time_v2(information_time)
    )
    return ":".join(
        (
            "provider_publication",
            provider_id,
            endpoint_id,
            publication_basis,
            revision_ref,
            content_sha256,
            information_content_id,
        )
    )


def _provider_information_candidate_v2(
    *,
    normalized: Mapping[str, Any],
    revision_ref: str,
    fetched_at: str,
) -> dict[str, Any]:
    publication_status = str(normalized.get("publication_status") or "").lower()
    publication_basis = str(normalized.get("publication_basis") or "").lower()
    if publication_basis in {
        "fetched_at",
        "fetch_time",
        "search_time",
        "system_observed_at",
    } or publication_status == "conflicted":
        return _information_time_v2(
            status="conflicted",
            lower_bound=None,
            upper_bound=None,
            basis="conflicted",
            revision_ref=revision_ref,
        )
    if publication_status in {"", "unknown"}:
        return _information_time_v2(
            status="unknown",
            lower_bound=None,
            upper_bound=None,
            basis="unknown",
            revision_ref=revision_ref,
        )
    if (
        publication_status != "verified"
        or publication_basis not in _V2_TRUSTED_PROVIDER_PUBLICATION_BASES
    ):
        return _information_time_v2(
            status="conflicted",
            lower_bound=None,
            upper_bound=None,
            basis="conflicted",
            revision_ref=revision_ref,
        )
    has_exact = bool(normalized.get("publicly_available_at"))
    has_date = bool(normalized.get("publication_date"))
    has_timezone = bool(normalized.get("publication_timezone"))
    if has_date != has_timezone:
        return _information_time_v2(
            status="conflicted" if has_exact else "unknown",
            lower_bound=None,
            upper_bound=None,
            basis="conflicted" if has_exact else "unknown",
            revision_ref=revision_ref,
        )
    publication_interval: tuple[datetime, datetime] | None = None
    if has_date:
        raw_day = str(normalized["publication_date"] or "")
        zone_name = str(normalized["publication_timezone"] or "")
        try:
            day = datetime.strptime(
                raw_day, "%Y-%m-%d" if "-" in raw_day else "%Y%m%d"
            ).date()
            zone = ZoneInfo(zone_name)
        except (ValueError, TypeError, KeyError, ZoneInfoNotFoundError):
            return _information_time_v2(
                status="unknown",
                lower_bound=None,
                upper_bound=None,
                basis="unknown",
                revision_ref=revision_ref,
            )
        interval_lower = datetime.combine(
            day, time(0, 0, 0), tzinfo=zone
        ).astimezone(timezone.utc)
        interval_upper = datetime.combine(
            day, time(23, 59, 59), tzinfo=zone
        ).astimezone(timezone.utc)
        if interval_upper > parse_datetime(fetched_at, "UTC"):
            return _information_time_v2(
                status="conflicted",
                lower_bound=None,
                upper_bound=None,
                basis="conflicted",
                revision_ref=revision_ref,
            )
        publication_interval = (interval_lower, interval_upper)
    if has_exact:
        try:
            public_at = _explicit_timestamp_v2(
                normalized["publicly_available_at"],
                "provider publicly_available_at",
            )
        except MarketContextError:
            return _information_time_v2(
                status="unknown",
                lower_bound=None,
                upper_bound=None,
                basis="unknown",
                revision_ref=revision_ref,
            )
        if parse_datetime(public_at, "UTC") > parse_datetime(fetched_at, "UTC"):
            return _information_time_v2(
                status="conflicted",
                lower_bound=None,
                upper_bound=None,
                basis="conflicted",
                revision_ref=revision_ref,
            )
        public_instant = parse_datetime(public_at, "UTC")
        if publication_interval is not None and not (
            publication_interval[0]
            <= public_instant
            <= publication_interval[1]
        ):
            return _information_time_v2(
                status="conflicted",
                lower_bound=None,
                upper_bound=None,
                basis="conflicted",
                revision_ref=revision_ref,
            )
        return _information_time_v2(
            status="verified",
            lower_bound=public_at,
            upper_bound=public_at,
            basis="provider_exact_publication_time.v1",
            revision_ref=revision_ref,
        )
    if publication_interval is not None:
        return _information_time_v2(
            status="verified",
            lower_bound=utc_iso(publication_interval[0], "UTC"),
            upper_bound=utc_iso(publication_interval[1], "UTC"),
            basis="provider_publication_date_source_timezone.v1",
            revision_ref=revision_ref,
        )
    return _information_time_v2(
        status="unknown",
        lower_bound=None,
        upper_bound=None,
        basis="unknown",
        revision_ref=revision_ref,
    )


def _external_row_information_v2(
    *,
    requirement: Mapping[str, Any],
    component: str,
    row: Mapping[str, Any],
    fetched_at: str,
    provider_id: str,
    endpoint_id: str,
) -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
    normalized = {
        str(key): None if value is None else str(value).strip()
        for key, value in sorted(row.items())
    }
    extra = sorted(set(normalized) - _V2_PROVIDER_ROW_KEYS)
    if extra:
        raise MarketContextError(
            "provider row contains unsupported persisted fields: "
            + ",".join(extra)
        )
    if any(
        value is not None and len(value) > MARKET_PROVIDER_PARAMETER_MAX_LENGTH
        for value in normalized.values()
    ):
        raise MarketContextError("v2 provider row value exceeds persistence limit")
    market_values = {
        key: value
        for key, value in normalized.items()
        if key not in _V2_PROVIDER_METADATA_KEYS
    }
    expected_hash = market_row_content_sha256_v2(
        component=component,
        instrument_id=str(requirement["instrument_id"]),
        row=market_values,
    )
    supplied_hash = str(normalized.get("content_sha256") or "")
    revision_raw = str(normalized.get("revision_ref") or "")
    source_ref_raw = str(normalized.get("public_time_source_ref") or "")
    publication_basis = str(normalized.get("publication_basis") or "").lower()
    revision_is_safe = bool(
        revision_raw
        and _V2_PROVIDER_REVISION_REF_PATTERN.fullmatch(revision_raw)
    )
    revision_ref = revision_raw or "MISSING_REVISION_REF"
    candidate_information = _provider_information_candidate_v2(
        normalized=normalized,
        revision_ref=revision_ref,
        fetched_at=fetched_at,
    )
    expected_source_ref: str | None = None
    if (
        revision_is_safe
        and publication_basis in _V2_TRUSTED_PROVIDER_PUBLICATION_BASES
        and candidate_information["status"] == "verified"
    ):
        expected_source_ref = _provider_publication_source_ref_v2(
            provider_id=provider_id,
            endpoint_id=endpoint_id,
            publication_basis=publication_basis,
            revision_ref=revision_raw,
            content_sha256=expected_hash,
            information_time=candidate_information,
        )
    source_binding_conflict = bool(source_ref_raw) and (
        expected_source_ref is None or source_ref_raw != expected_source_ref
    )
    missing_version_proof = (
        not supplied_hash
        or not revision_raw
        or not source_ref_raw
        or expected_source_ref is None
    )
    hash_conflict = bool(supplied_hash) and supplied_hash != expected_hash
    version_status = (
        "conflicted"
        if (
            hash_conflict
            or source_binding_conflict
            or (revision_raw and not revision_is_safe)
        )
        else "unknown"
        if missing_version_proof
        else "verified"
    )
    source_ref = (
        source_ref_raw
        if expected_source_ref is not None and source_ref_raw == expected_source_ref
        else "MISSING_PUBLIC_TIME_SOURCE_REF"
        if not source_ref_raw
        else "UNVERIFIED_PUBLIC_TIME_SOURCE_REF"
    )
    version = _version_provenance_v2(
        status=version_status,
        content_sha256=expected_hash,
        source_ref=source_ref,
        revision_ref=revision_ref,
    )
    if candidate_information["status"] == "conflicted" or version_status == "conflicted":
        information = _information_time_v2(
            status="conflicted",
            lower_bound=None,
            upper_bound=None,
            basis="conflicted",
            revision_ref=revision_ref,
        )
    elif candidate_information["status"] != "verified" or version_status != "verified":
        information = _information_time_v2(
            status="unknown",
            lower_bound=None,
            upper_bound=None,
            basis="unknown",
            revision_ref=revision_ref,
        )
    else:
        information = candidate_information
    return information, version, market_values


def _canonical_receipt_v2(value: Mapping[str, Any]) -> dict[str, Any]:
    item = _closed(
        value,
        name="v2 market fetch receipt",
        required={
            "receipt_id",
            "provider_id",
            "endpoint_id",
            "provider_version",
            "redacted_parameters",
            "request_fingerprint_version",
            "request_fingerprint",
            "guard_audit_at",
            "started_at",
            "completed_at",
            "fetched_at",
            "system_observed_at",
            "response_status",
            "attempt_count",
            "attempt_count_status",
            "budget_charged_attempts",
            "raw_content_sha256",
            "normalized_content_sha256",
            "cache_entry_refs",
            "cache_lineage",
        },
    )
    request = canonical_provider_request(
        {
            "component": "prior_close",
            "provider_id": item["provider_id"],
            "endpoint_id": item["endpoint_id"],
            "provider_version": item["provider_version"],
            "parameters": item["redacted_parameters"],
        }
    )
    for field in (
        "provider_id",
        "endpoint_id",
        "provider_version",
        "redacted_parameters",
        "request_fingerprint_version",
        "request_fingerprint",
    ):
        if item[field] != request[field]:
            raise MarketContextError("v2 receipt request provenance drift")
    status = str(item["response_status"])
    if status not in {
        "succeeded",
        "failed",
        "timeout",
        "rejected",
        "provider_unavailable",
        "withheld_by_cutoff",
        "budget_exhausted",
    }:
        raise MarketContextError("v2 receipt status is unsupported")
    attempt_count = item["attempt_count"]
    if (
        isinstance(attempt_count, bool)
        or not isinstance(attempt_count, int)
        or not 0 <= attempt_count <= 3
    ):
        raise MarketContextError("v2 receipt attempt_count is invalid")
    attempt_count_status = str(item["attempt_count_status"])
    if attempt_count_status not in {"verified", "unknown"}:
        raise MarketContextError("v2 receipt attempt_count_status is invalid")
    budget_charged = item["budget_charged_attempts"]
    if (
        isinstance(budget_charged, bool)
        or not isinstance(budget_charged, int)
        or not 0 <= budget_charged <= 3
    ):
        raise MarketContextError("v2 receipt budget charge is invalid")
    if attempt_count_status == "verified" and budget_charged != attempt_count:
        raise MarketContextError("verified attempt count/budget charge drift")
    if attempt_count_status == "unknown" and budget_charged < 1:
        raise MarketContextError("unknown attempt count requires a conservative budget charge")
    guard = _timestamp(item["guard_audit_at"], "receipt guard_audit_at")
    zero_status = status in {
        "provider_unavailable",
        "withheld_by_cutoff",
        "budget_exhausted",
    }
    if zero_status:
        if attempt_count_status != "verified" or attempt_count != 0 or any(
            item[field] is not None
            for field in (
                "fetched_at",
                "system_observed_at",
                "raw_content_sha256",
                "normalized_content_sha256",
            )
        ) or item["cache_entry_refs"]:
            raise MarketContextError("zero-request v2 receipt carries acquisition state")
        started = _timestamp(item["started_at"], "receipt started_at")
        completed = _timestamp(item["completed_at"], "receipt completed_at")
        if started != guard or completed != guard:
            raise MarketContextError("zero-request receipt times must equal guard audit")
        fetched = observed = None
    else:
        if attempt_count_status == "verified" and attempt_count < 1:
            raise MarketContextError("attempted v2 receipt requires an HTTP attempt")
        if attempt_count_status == "unknown" and (
            status != "failed" or attempt_count != 0
        ):
            raise MarketContextError(
                "unknown v2 attempt count must remain a zero-count failed receipt"
            )
        started = _timestamp(item["started_at"], "receipt started_at")
        completed = _timestamp(item["completed_at"], "receipt completed_at")
        observed = _timestamp(
            item["system_observed_at"], "receipt system_observed_at"
        )
        fetched = (
            None
            if item["fetched_at"] is None
            else _timestamp(item["fetched_at"], "receipt fetched_at")
        )
        if not (
            parse_datetime(guard, "UTC")
            <= parse_datetime(started, "UTC")
            <= parse_datetime(observed, "UTC")
            <= parse_datetime(completed, "UTC")
        ):
            raise MarketContextError("v2 receipt acquisition time order is invalid")
        if fetched is not None and not (
            parse_datetime(started, "UTC")
            <= parse_datetime(fetched, "UTC")
            <= parse_datetime(observed, "UTC")
        ):
            raise MarketContextError("v2 receipt fetch time is out of order")
        if status == "succeeded":
            if (
                attempt_count_status != "verified"
                or fetched is None
                or not item["cache_entry_refs"]
            ):
                raise MarketContextError("successful v2 receipt lacks cache evidence")
            for field in ("raw_content_sha256", "normalized_content_sha256"):
                if re.fullmatch(
                    r"sha256:[0-9a-f]{64}", str(item[field] or "")
                ) is None:
                    raise MarketContextError("successful v2 receipt hash is invalid")
        elif item["cache_entry_refs"] or any(
            item[field] is not None
            for field in ("raw_content_sha256", "normalized_content_sha256")
        ):
            raise MarketContextError("failed v2 receipt carries successful cache state")
    cache_refs = sorted(_text(ref, "receipt cache entry ref") for ref in item["cache_entry_refs"])
    lineage = sorted(_text(ref, "receipt cache lineage") for ref in item["cache_lineage"])
    if not lineage or cache_refs != list(item["cache_entry_refs"]) or lineage != list(
        item["cache_lineage"]
    ):
        raise MarketContextError("v2 receipt refs/lineage are not canonical")
    canonical = {
        **dict(item),
        "guard_audit_at": guard,
        "started_at": started,
        "completed_at": completed,
        "fetched_at": fetched,
        "system_observed_at": observed,
        "cache_entry_refs": cache_refs,
        "cache_lineage": lineage,
    }
    supplied_id = _text(item["receipt_id"], "receipt_id")
    identity_material = dict(canonical)
    identity_material["receipt_id"] = ""
    expected_id = "market_fetch_receipt_v2_" + hashlib.sha256(
        canonical_json_bytes(identity_material)
    ).hexdigest()
    if supplied_id != expected_id:
        raise MarketContextError("v2 market receipt identity drift")
    return _clone(canonical)


def _receipt_v2(
    *,
    request: Mapping[str, Any],
    requirement_id: str,
    guard_audit_at: str,
    response_status: str,
    attempt_count: int,
    attempt_count_status: str = "verified",
    budget_charged_attempts: int | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    fetched_at: str | None = None,
    system_observed_at: str | None = None,
    raw_content_sha256: str | None = None,
    normalized_content_sha256: str | None = None,
    cache_entry_refs: Sequence[str] = (),
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "receipt_id": "",
        "provider_id": request["provider_id"],
        "endpoint_id": request["endpoint_id"],
        "provider_version": request["provider_version"],
        "redacted_parameters": _clone(request["redacted_parameters"]),
        "request_fingerprint_version": request["request_fingerprint_version"],
        "request_fingerprint": request["request_fingerprint"],
        "guard_audit_at": _timestamp(guard_audit_at, "guard_audit_at"),
        "started_at": started_at,
        "completed_at": completed_at,
        "fetched_at": fetched_at,
        "system_observed_at": system_observed_at,
        "response_status": response_status,
        "attempt_count": attempt_count,
        "attempt_count_status": attempt_count_status,
        "budget_charged_attempts": (
            attempt_count
            if budget_charged_attempts is None
            else budget_charged_attempts
        ),
        "raw_content_sha256": raw_content_sha256,
        "normalized_content_sha256": normalized_content_sha256,
        "cache_entry_refs": sorted(str(ref) for ref in cache_entry_refs),
        "cache_lineage": [str(requirement_id)],
    }
    receipt["receipt_id"] = "market_fetch_receipt_v2_" + hashlib.sha256(
        canonical_json_bytes(receipt)
    ).hexdigest()
    return _canonical_receipt_v2(receipt)


def _canonical_fallback_v2(value: Mapping[str, Any]) -> dict[str, Any]:
    item = _closed(
        value,
        name="v2 market fallback",
        required={
            "policy_version",
            "public_information_policy_version",
            "perspective",
            "allowlist_version",
            "allowlist_sha256",
            "coverage_before",
            "coverage_after",
            "status",
            "limitation_code",
            "guard_audit_at",
            "request_count",
            "request_count_status",
            "unverified_attempt_upper_bound",
            "limits",
            "allowlist",
            "cache_refs",
            "fetch_receipt_refs",
            "fetch_receipts",
            "offline_consumers",
        },
    )
    if (
        item["policy_version"] != MARKET_FALLBACK_POLICY_VERSION_V2
        or item["public_information_policy_version"]
        != PUBLIC_INFORMATION_POLICY_VERSION
        or item["perspective"] not in {"user", "system"}
        or item["allowlist_version"] != MARKET_PROVIDER_ALLOWLIST_VERSION
        or item["allowlist_sha256"] != MARKET_PROVIDER_ALLOWLIST_SHA256
        or item["limits"] != MARKET_LIMITS
        or item["allowlist"] != sorted(MARKET_PROVIDER_ALLOWLIST)
        or item["offline_consumers"]
        != {consumer: False for consumer in OFFLINE_CONSUMERS}
    ):
        raise MarketContextError("v2 fallback frozen policy/caps drift")
    status = str(item["status"])
    if status not in _V2_FALLBACK_STATES:
        raise MarketContextError("v2 fallback status is unsupported")
    receipts = sorted(
        (_canonical_receipt_v2(receipt) for receipt in item["fetch_receipts"]),
        key=lambda receipt: receipt["receipt_id"],
    )
    if receipts != list(item["fetch_receipts"]):
        raise MarketContextError("v2 fallback receipts are not canonical")
    receipt_refs = [receipt["receipt_id"] for receipt in receipts]
    if receipt_refs != list(item["fetch_receipt_refs"]):
        raise MarketContextError("v2 fallback receipt references drift")
    request_count = sum(int(receipt["attempt_count"]) for receipt in receipts)
    if item["request_count"] != request_count or request_count > MARKET_LIMITS[
        "max_requests_per_run"
    ]:
        raise MarketContextError("v2 fallback request count drift")
    unknown_upper_bound = sum(
        int(receipt["budget_charged_attempts"])
        for receipt in receipts
        if receipt["attempt_count_status"] == "unknown"
    )
    expected_count_status = (
        "bounded_unknown" if unknown_upper_bound else "verified"
    )
    if (
        item["request_count_status"] != expected_count_status
        or item["unverified_attempt_upper_bound"] != unknown_upper_bound
        or request_count + unknown_upper_bound
        > MARKET_LIMITS["max_requests_per_run"]
    ):
        raise MarketContextError("v2 fallback attempt-count bound drift")
    cache_refs = sorted(_text(ref, "fallback cache ref") for ref in item["cache_refs"])
    if cache_refs != list(item["cache_refs"]):
        raise MarketContextError("v2 fallback cache refs are not canonical")
    successful_entry_refs = sorted(
        {
            ref
            for receipt in receipts
            if receipt["response_status"] == "succeeded"
            for ref in receipt["cache_entry_refs"]
        }
    )
    if not set(successful_entry_refs).issubset(cache_refs):
        raise MarketContextError("v2 successful cache refs are not frozen")
    zero_statuses = {
        "not_needed",
        "provider_unavailable",
        "withheld_by_cutoff",
        "budget_exhausted",
    }
    if status in zero_statuses and request_count != 0:
        raise MarketContextError("zero-request v2 fallback contains attempts")
    if status == "not_needed" and (receipts or not cache_refs):
        raise MarketContextError("v2 not_needed requires only frozen local refs")
    successful = [
        receipt for receipt in receipts if receipt["response_status"] == "succeeded"
    ]
    if status == "not_needed" and (
        item["coverage_before"] != "satisfied"
        or item["coverage_after"] != "satisfied"
    ):
        raise MarketContextError("v2 not_needed coverage drift")
    if status in {"provider_unavailable", "withheld_by_cutoff", "budget_exhausted"}:
        if (
            item["coverage_before"] == "satisfied"
            or item["coverage_after"] != item["coverage_before"]
        ):
            raise MarketContextError("v2 zero-request limitation coverage drift")
    elif status != "not_needed":
        if item["coverage_before"] == "satisfied":
            raise MarketContextError("attempted v2 fallback lacks a coverage trigger")
        if status == "succeeded" and (not successful or request_count == 0):
            raise MarketContextError(
                "successful v2 fallback requires a successful attempted receipt"
            )
        if status == "failed" and (
            not receipts
            or successful
            or request_count + unknown_upper_bound == 0
            or item["coverage_after"] != item["coverage_before"]
        ):
            raise MarketContextError(
                "failed v2 fallback requires attempts and no successful receipt"
            )
    if status == "withheld_by_cutoff" and item["perspective"] != "system":
        raise MarketContextError("withheld_by_cutoff is restricted to system")
    expected_limitation = {
        "provider_unavailable": "provider_unavailable",
        "withheld_by_cutoff": "withheld_by_cutoff",
        "budget_exhausted": "budget_exhausted",
    }.get(status)
    if expected_count_status == "bounded_unknown":
        expected_limitation = "provider_attempt_count_unknown"
    if item["limitation_code"] != expected_limitation:
        raise MarketContextError("v2 fallback limitation/status drift")
    guard = (
        None
        if item["guard_audit_at"] is None
        else _timestamp(item["guard_audit_at"], "fallback guard_audit_at")
    )
    if status in {"provider_unavailable", "withheld_by_cutoff", "budget_exhausted"}:
        if (
            guard is None
            or len(receipts) != 1
            or receipts[0]["guard_audit_at"] != guard
            or receipts[0]["response_status"] != status
        ):
            raise MarketContextError("v2 zero-request fallback lacks guard receipt")
    elif guard is not None:
        raise MarketContextError("non-limitation v2 fallback carries guard audit")
    return _clone({**dict(item), "guard_audit_at": guard, "cache_refs": cache_refs})


def _frozen_source_refs_v2(sources: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {str(source["source_id"]) for source in sources}
        | {
            str(source["payload"]["cache_entry_ref"])
            for source in sources
            if source.get("payload", {}).get("cache_entry_ref")
        }
    )


def _not_needed_fallback_v2(
    requirement: Mapping[str, Any],
    coverage: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if coverage["status"] != "satisfied":
        raise MarketContextError("v2 not_needed requires satisfied eligible coverage")
    return _canonical_fallback_v2(
        {
            "policy_version": MARKET_FALLBACK_POLICY_VERSION_V2,
            "public_information_policy_version": PUBLIC_INFORMATION_POLICY_VERSION,
            "perspective": requirement["perspective"],
            "allowlist_version": MARKET_PROVIDER_ALLOWLIST_VERSION,
            "allowlist_sha256": MARKET_PROVIDER_ALLOWLIST_SHA256,
            "coverage_before": "satisfied",
            "coverage_after": "satisfied",
            "status": "not_needed",
            "limitation_code": None,
            "guard_audit_at": None,
            "request_count": 0,
            "request_count_status": "verified",
            "unverified_attempt_upper_bound": 0,
            "limits": dict(MARKET_LIMITS),
            "allowlist": sorted(MARKET_PROVIDER_ALLOWLIST),
            "cache_refs": _frozen_source_refs_v2(sources),
            "fetch_receipt_refs": [],
            "fetch_receipts": [],
            "offline_consumers": {consumer: False for consumer in OFFLINE_CONSUMERS},
        }
    )


def _limitation_fallback_v2(
    requirement: Mapping[str, Any],
    *,
    coverage: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    status: str,
    guard_audit_at: str,
) -> dict[str, Any]:
    if status not in {
        "provider_unavailable",
        "withheld_by_cutoff",
        "budget_exhausted",
    }:
        raise MarketContextError("unsupported v2 limitation fallback")
    request = (
        _clone(requirement["provider_requests"][0])
        if requirement["provider_requests"]
        else _request_for_missing_close_v2(requirement, sources)
    )
    receipt = _receipt_v2(
        request=request,
        requirement_id=str(requirement["requirement_id"]),
        guard_audit_at=guard_audit_at,
        response_status=status,
        attempt_count=0,
        started_at=guard_audit_at,
        completed_at=guard_audit_at,
    )
    return _canonical_fallback_v2(
        {
            "policy_version": MARKET_FALLBACK_POLICY_VERSION_V2,
            "public_information_policy_version": PUBLIC_INFORMATION_POLICY_VERSION,
            "perspective": requirement["perspective"],
            "allowlist_version": MARKET_PROVIDER_ALLOWLIST_VERSION,
            "allowlist_sha256": MARKET_PROVIDER_ALLOWLIST_SHA256,
            "coverage_before": coverage["status"],
            "coverage_after": coverage["status"],
            "status": status,
            "limitation_code": status,
            "guard_audit_at": guard_audit_at,
            "request_count": 0,
            "request_count_status": "verified",
            "unverified_attempt_upper_bound": 0,
            "limits": dict(MARKET_LIMITS),
            "allowlist": sorted(MARKET_PROVIDER_ALLOWLIST),
            "cache_refs": _frozen_source_refs_v2(sources),
            "fetch_receipt_refs": [receipt["receipt_id"]],
            "fetch_receipts": [receipt],
            "offline_consumers": {consumer: False for consumer in OFFLINE_CONSUMERS},
        }
    )


def _cache_entry_identity_material_v2(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": value["schema_version"],
        "component": value["component"],
        "provider_id": value["provider_id"],
        "endpoint_id": value["endpoint_id"],
        "provider_version": value["provider_version"],
        "redacted_parameters": value["redacted_parameters"],
        "request_fingerprint_version": value["request_fingerprint_version"],
        "request_fingerprint": value["request_fingerprint"],
        "started_at": value["started_at"],
        "completed_at": value["completed_at"],
        "fetched_at": value["fetched_at"],
        "system_observed_at": value["system_observed_at"],
        "attempt_count": value["attempt_count"],
        "rows": value["rows"],
        "raw_content_sha256": value["raw_content_sha256"],
        "normalized_content_sha256": value["normalized_content_sha256"],
    }


def _canonical_cache_entry_v2(
    value: Mapping[str, Any], *, path: Path | None = None
) -> dict[str, Any]:
    item = _closed(
        value,
        name="v2 market cache entry",
        required={
            "schema_version",
            "cache_entry_ref",
            "origin_requirement",
            "component",
            "provider_id",
            "endpoint_id",
            "provider_version",
            "redacted_parameters",
            "request_fingerprint_version",
            "request_fingerprint",
            "started_at",
            "completed_at",
            "fetched_at",
            "system_observed_at",
            "attempt_count",
            "rows",
            "raw_content_sha256",
            "normalized_content_sha256",
            "origin_fetch_receipt",
            "content_id",
        },
    )
    if item["schema_version"] != MARKET_CACHE_ENTRY_VERSION_V2:
        raise MarketContextError("unsupported v2 market cache entry version")
    requirement = canonical_market_cache_requirement_v2(
        item["origin_requirement"]
    )
    component = _text(item["component"], "v2 cache component")
    if component not in MARKET_COMPONENTS:
        raise MarketContextError("v2 market cache component is unsupported")
    request = canonical_provider_request(
        {
            "component": component,
            "provider_id": item["provider_id"],
            "endpoint_id": item["endpoint_id"],
            "provider_version": item["provider_version"],
            "parameters": item["redacted_parameters"],
        }
    )
    _validate_provider_component_endpoint_v2(
        component=component,
        provider_id=str(request["provider_id"]),
        endpoint_id=str(request["endpoint_id"]),
    )
    for field in (
        "provider_id",
        "endpoint_id",
        "provider_version",
        "redacted_parameters",
        "request_fingerprint_version",
        "request_fingerprint",
    ):
        if item[field] != request[field]:
            raise MarketContextError("v2 cache request provenance drift")
    started = _timestamp(item["started_at"], "v2 cache started_at")
    completed = _timestamp(item["completed_at"], "v2 cache completed_at")
    fetched = _timestamp(item["fetched_at"], "v2 cache fetched_at")
    observed = _timestamp(
        item["system_observed_at"], "v2 cache system_observed_at"
    )
    if not (
        parse_datetime(started, "UTC")
        <= parse_datetime(fetched, "UTC")
        <= parse_datetime(completed, "UTC")
        and parse_datetime(started, "UTC")
        <= parse_datetime(observed, "UTC")
        <= parse_datetime(completed, "UTC")
    ):
        raise MarketContextError("v2 cache acquisition time order drift")
    attempt_count = item["attempt_count"]
    if (
        isinstance(attempt_count, bool)
        or not isinstance(attempt_count, int)
        or not 1 <= attempt_count <= 3
    ):
        raise MarketContextError("v2 cache requires one to three attempts")
    if (
        not isinstance(item["rows"], list)
        or not item["rows"]
        or len(item["rows"]) > ROW_LIMIT_PER_COMPONENT
        or any(not isinstance(row, Mapping) for row in item["rows"])
    ):
        raise MarketContextError("v2 cache rows are invalid")
    rows = sorted((_clone(row) for row in item["rows"]), key=canonical_json_bytes)
    if rows != list(item["rows"]):
        raise MarketContextError("v2 cache rows are not canonical")
    for row in rows:
        if set(row) - _V2_PROVIDER_ROW_KEYS:
            raise MarketContextError("v2 cache row contains unsupported fields")
        if row.get("ts_code") != requirement["instrument_id"]:
            raise MarketContextError("v2 cache row instrument drift")
    normalized_rows = _normalize_provider_rows_v2(
        response={"rows": rows},
        request=request,
        requirement=requirement,
    )
    if normalized_rows != rows:
        raise MarketContextError("v2 cache row scope/projection drift")
    fetched_instant = parse_datetime(fetched, "UTC")
    for row in rows:
        time_value = row.get("bar_time") or row.get("trade_time")
        if component in {"prior_close", "daily", "factor"}:
            row_effective = _date_effective(row.get("trade_date"))
        elif component == "minute":
            row_effective = _iso_datetime(
                time_value, default_zone="Asia/Shanghai"
            )
        else:
            row_effective = parse_datetime(
                requirement["operation_anchor_at"], "UTC"
            )
        if row_effective > fetched_instant:
            raise MarketContextError(
                "v2 cache row effective time follows acquisition"
            )
    raw_hash = str(item["raw_content_sha256"])
    if re.fullmatch(r"sha256:[0-9a-f]{64}", raw_hash) is None:
        raise MarketContextError("v2 cache raw hash is invalid")
    normalized_hash = _content_id(rows)
    if item["normalized_content_sha256"] != normalized_hash:
        raise MarketContextError("v2 cache normalized hash drift")
    identity_material = _cache_entry_identity_material_v2(
        {**item, "rows": rows}
    )
    cache_ref = "market_cache_entry_v2_" + hashlib.sha256(
        canonical_json_bytes(identity_material)
    ).hexdigest()
    if item["cache_entry_ref"] != cache_ref:
        raise MarketContextError("v2 cache entry identity drift")
    receipt = _canonical_receipt_v2(item["origin_fetch_receipt"])
    expected_receipt = {
        "provider_id": item["provider_id"],
        "endpoint_id": item["endpoint_id"],
        "provider_version": item["provider_version"],
        "redacted_parameters": item["redacted_parameters"],
        "request_fingerprint_version": item["request_fingerprint_version"],
        "request_fingerprint": item["request_fingerprint"],
        "started_at": started,
        "completed_at": completed,
        "fetched_at": fetched,
        "system_observed_at": observed,
        "attempt_count": attempt_count,
        "attempt_count_status": "verified",
        "budget_charged_attempts": attempt_count,
        "raw_content_sha256": raw_hash,
        "normalized_content_sha256": normalized_hash,
        "cache_entry_refs": [cache_ref],
    }
    if any(receipt.get(key) != expected for key, expected in expected_receipt.items()):
        raise MarketContextError("v2 cache/receipt provenance drift")
    if receipt["cache_lineage"] != [requirement["requirement_id"]]:
        raise MarketContextError("v2 cache origin lineage drift")
    content_material = dict(item)
    content_material.pop("content_id")
    content_material["origin_requirement"] = requirement
    content_material["origin_fetch_receipt"] = receipt
    content_material["rows"] = rows
    if item["content_id"] != _content_id(content_material):
        raise MarketContextError("v2 cache content ID drift")
    if path is not None and path.name != _short_cache_name(cache_ref):
        raise MarketContextError("v2 cache entry filename drift")
    return _clone({**content_material, "content_id": item["content_id"]})


def _normalize_provider_rows_v2(
    *,
    response: Mapping[str, Any],
    request: Mapping[str, Any],
    requirement: Mapping[str, Any],
) -> list[dict[str, Any]]:
    raw_rows = response.get("rows")
    if (
        not isinstance(raw_rows, (list, tuple))
        or not raw_rows
        or len(raw_rows) > ROW_LIMIT_PER_COMPONENT
    ):
        raise MarketContextError("successful v2 provider response requires bounded rows")
    component = str(request["component"])
    operation_anchor = parse_datetime(requirement["operation_anchor_at"], "UTC")
    anchor_day = operation_anchor.astimezone(_SHANGHAI).date()
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            raise MarketContextError("v2 provider rows must be objects")
        extra = sorted(str(key) for key in raw if str(key) not in _V2_PROVIDER_ROW_KEYS)
        if extra:
            raise MarketContextError(
                "v2 provider row contains unsupported fields: " + ",".join(extra)
            )
        row = {
            str(key): None if value is None else str(value).strip()
            for key, value in sorted(raw.items())
        }
        if row.get("ts_code") != requirement["instrument_id"]:
            raise MarketContextError("v2 provider row instrument mismatch")
        time_value = row.get("bar_time") or row.get("trade_time")
        if component in {"prior_close", "daily", "factor"}:
            effective = _date_effective(row.get("trade_date"))
        elif component == "minute":
            effective = _iso_datetime(time_value, default_zone="Asia/Shanghai")
        else:
            effective = operation_anchor
        if effective > operation_anchor:
            continue
        if component == "prior_close" and effective.astimezone(
            _SHANGHAI
        ).date() >= anchor_day:
            continue
        market_values = {
            key: value
            for key, value in row.items()
            if key not in _V2_PROVIDER_METADATA_KEYS
        }
        if not _component_values_sufficient(component, market_values):
            continue
        rows.append(row)
    if not rows:
        raise MarketContextError(
            "v2 provider rows are not in scope or materially sufficient"
        )
    unique_rows = {
        canonical_json_bytes(row): row
        for row in rows
    }
    return [_clone(unique_rows[key]) for key in sorted(unique_rows)]


def _external_sources_from_entry_v2(
    entry: Mapping[str, Any], requirement: Mapping[str, Any]
) -> list[dict[str, Any]]:
    component = str(entry["component"])
    relevant = set(requirement["required_components"]) | set(
        requirement["optional_components"]
    )
    if (
        component not in relevant
        or entry["origin_requirement"]["instrument_id"]
        != requirement["instrument_id"]
    ):
        return []
    fetched_at = str(entry["fetched_at"])
    fetched = parse_datetime(fetched_at, "UTC")
    observed = parse_datetime(entry["system_observed_at"], "UTC")
    operation_anchor = parse_datetime(requirement["operation_anchor_at"], "UTC")
    anchor_day = operation_anchor.astimezone(_SHANGHAI).date()
    sources: list[dict[str, Any]] = []
    for row in entry["rows"]:
        time_value = row.get("bar_time") or row.get("trade_time")
        if component in {"prior_close", "daily", "factor"}:
            effective = _date_effective(row.get("trade_date"))
        elif component == "minute":
            effective = _iso_datetime(time_value, default_zone="Asia/Shanghai")
        else:
            effective = None
        if effective is not None:
            if effective > operation_anchor or fetched < effective:
                continue
            if component == "prior_close" and effective.astimezone(
                _SHANGHAI
            ).date() >= anchor_day:
                continue
        information, version, market_values = _external_row_information_v2(
            requirement=requirement,
            component=component,
            row=row,
            fetched_at=fetched_at,
            provider_id=str(entry["provider_id"]),
            endpoint_id=str(entry["endpoint_id"]),
        )
        if effective is None:
            # Non-timeseries provider rows have no intrinsic bar/list/update
            # effective timestamp in the frozen row contract.  A verified
            # exact version becomes conservatively effective no earlier than
            # its proven publication upper bound; otherwise the first honest
            # effective boundary is the real frozen acquisition time.
            effective = (
                parse_datetime(information["upper_bound"], "UTC")
                if information["status"] == "verified"
                else fetched
            )
        if not _component_values_sufficient(component, market_values):
            continue
        row_identity = hashlib.sha256(canonical_json_bytes(row)).hexdigest()[:24]
        sources.append(
            _source_envelope_v2(
                requirement=requirement,
                component=component,
                origin="external_provider_cache",
                effective_at=effective,
                coverage_effective_at=effective,
                fetched_at=fetched,
                system_observed_at=observed,
                values=market_values,
                information_time=information,
                version_provenance=version,
                source_table="v2_market_cache",
                source_record_id=f"{entry['cache_entry_ref']}:{row_identity}",
                source_provider=f"{entry['provider_id']}:{entry['endpoint_id']}",
                point_in_time=False if component == "current_industry" else None,
                cache_entry_ref=str(entry["cache_entry_ref"]),
                origin_requirement_id=str(
                    entry["origin_requirement"]["requirement_id"]
                ),
                origin_fetch_receipt=entry["origin_fetch_receipt"],
                origin_cache_entry=entry,
                raw_content_sha256=str(entry["raw_content_sha256"]),
                normalized_content_sha256=str(version["content_sha256"]),
            )
        )
    return sorted(sources, key=lambda source: (source["source_kind"], source["source_id"]))


def _external_base_source_from_proof_v2(
    source: Mapping[str, Any], requirement: Mapping[str, Any]
) -> dict[str, Any]:
    payload = source.get("payload")
    if not isinstance(payload, Mapping):
        raise MarketContextError("v2 external source lacks a canonical payload")
    entry_raw = payload.get("origin_cache_entry")
    if not isinstance(entry_raw, Mapping):
        raise MarketContextError(
            "v2 external source lacks its complete origin cache proof"
        )
    entry = _canonical_cache_entry_v2(entry_raw)
    source_record_id = str(payload.get("source_record_id") or "")
    matches = [
        candidate
        for candidate in _external_sources_from_entry_v2(entry, requirement)
        if candidate["payload"]["source_record_id"] == source_record_id
    ]
    if len(matches) != 1:
        raise MarketContextError(
            "v2 external source does not bind exactly one origin cache row"
        )
    return matches[0]


def _external_revision_identity_v2(
    source: Mapping[str, Any],
) -> tuple[str, ...] | None:
    payload = source.get("payload", {})
    if payload.get("origin") != "external_provider_cache":
        return None
    receipt = payload.get("origin_fetch_receipt")
    version = payload.get("version_provenance")
    information = payload.get("information_time")
    if not all(isinstance(item, Mapping) for item in (receipt, version, information)):
        return None
    revision_ref = str(version.get("revision_ref") or "")
    content_hash = str(version.get("content_sha256") or "")
    source_ref = str(version.get("source_ref") or "")
    if _V2_PROVIDER_REVISION_REF_PATTERN.fullmatch(revision_ref) is None:
        return None
    for publication_basis in sorted(_V2_TRUSTED_PROVIDER_PUBLICATION_BASES):
        try:
            expected_ref = _provider_publication_source_ref_v2(
                provider_id=str(receipt["provider_id"]),
                endpoint_id=str(receipt["endpoint_id"]),
                publication_basis=publication_basis,
                revision_ref=revision_ref,
                content_sha256=content_hash,
                information_time=information,
            )
        except (KeyError, MarketContextError):
            continue
        if source_ref == expected_ref:
            return (
                str(payload.get("instrument_id")),
                str(payload.get("component")),
                str(payload.get("effective_at")),
                str(receipt["provider_id"]),
                str(receipt["endpoint_id"]),
                revision_ref,
            )
    return None


def _conflicted_external_source_v2(
    source: Mapping[str, Any], requirement: Mapping[str, Any]
) -> dict[str, Any]:
    result = _clone(source)
    payload = result["payload"]
    version = {**payload["version_provenance"], "status": "conflicted"}
    information = payload["information_time"]
    eligibility = _perspective_eligibility_v2(
        requirement=requirement,
        component=str(payload["component"]),
        information_time=information,
        version_provenance=version,
        system_observed_at=str(payload["system_observed_at"]),
    )
    payload["version_provenance"] = version
    payload["perspective_eligibility"] = eligibility
    payload["temporal_role"] = eligibility["temporal_role"]
    payload["source_id"] = None
    source_id = "market_source_v2_" + hashlib.sha256(
        canonical_json_bytes(payload)
    ).hexdigest()
    payload["source_id"] = source_id
    result["source_id"] = source_id
    return result


def _resolve_external_revision_conflicts_v2(
    sources: Sequence[Mapping[str, Any]],
    requirement: Mapping[str, Any],
) -> list[dict[str, Any]]:
    canonical_sources = [
        (
            _external_base_source_from_proof_v2(source, requirement)
            if source.get("payload", {}).get("origin")
            == "external_provider_cache"
            else _clone(source)
        )
        for source in sources
    ]
    identities: dict[tuple[str, ...], set[str]] = {}
    for source in canonical_sources:
        identity = _external_revision_identity_v2(source)
        if identity is not None:
            payload = source["payload"]
            version = payload["version_provenance"]
            identities.setdefault(identity, set()).add(
                _content_id(
                    {
                        "content_sha256": str(version["content_sha256"]),
                        "information_time": _canonical_information_time_v2(
                            payload["information_time"]
                        ),
                        "source_ref": str(version["source_ref"]),
                    }
                )
            )
    conflicted_identities = {
        identity for identity, proofs in identities.items() if len(proofs) > 1
    }
    resolved = [
        (
            _conflicted_external_source_v2(source, requirement)
            if _external_revision_identity_v2(source) in conflicted_identities
            else _clone(source)
        )
        for source in canonical_sources
    ]
    return sorted(
        {str(source["source_id"]): source for source in resolved}.values(),
        key=lambda source: (source["source_kind"], source["source_id"]),
    )


def _external_entry_v2(
    *,
    request: Mapping[str, Any],
    response: Mapping[str, Any],
    requirement: Mapping[str, Any],
    cache_root: Path,
    persist: bool,
    guard_audit_at: str,
    started_at: str,
    completed_at: str,
    attempt_count: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _normalize_provider_rows_v2(
        response=response, request=request, requirement=requirement
    )
    fetched_at = _explicit_timestamp_v2(
        response.get("fetched_at"), "provider fetched_at"
    )
    if not (
        parse_datetime(started_at, "UTC")
        <= parse_datetime(fetched_at, "UTC")
        <= parse_datetime(completed_at, "UTC")
    ):
        raise MarketContextError("provider fetched_at is outside acquisition audit")
    system_observed_at = completed_at
    raw_material = response.get("raw_payload", response.get("rows"))
    if isinstance(raw_material, bytes):
        raw_bytes = raw_material
    elif isinstance(raw_material, str):
        raw_bytes = raw_material.encode("utf-8")
    else:
        raw_bytes = canonical_json_bytes(raw_material)
    raw_hash = _sha256_bytes(raw_bytes)
    normalized_hash = _content_id(rows)
    material: dict[str, Any] = {
        "schema_version": MARKET_CACHE_ENTRY_VERSION_V2,
        "component": request["component"],
        "provider_id": request["provider_id"],
        "endpoint_id": request["endpoint_id"],
        "provider_version": request["provider_version"],
        "redacted_parameters": _clone(request["redacted_parameters"]),
        "request_fingerprint_version": request["request_fingerprint_version"],
        "request_fingerprint": request["request_fingerprint"],
        "started_at": started_at,
        "completed_at": completed_at,
        "fetched_at": fetched_at,
        "system_observed_at": system_observed_at,
        "attempt_count": attempt_count,
        "rows": rows,
        "raw_content_sha256": raw_hash,
        "normalized_content_sha256": normalized_hash,
    }
    cache_ref = "market_cache_entry_v2_" + hashlib.sha256(
        canonical_json_bytes(material)
    ).hexdigest()
    receipt = _receipt_v2(
        request=request,
        requirement_id=str(requirement["requirement_id"]),
        guard_audit_at=guard_audit_at,
        response_status="succeeded",
        attempt_count=attempt_count,
        started_at=started_at,
        completed_at=completed_at,
        fetched_at=fetched_at,
        system_observed_at=system_observed_at,
        raw_content_sha256=raw_hash,
        normalized_content_sha256=normalized_hash,
        cache_entry_refs=[cache_ref],
    )
    entry: dict[str, Any] = {
        **material,
        "cache_entry_ref": cache_ref,
        "origin_requirement": _clone(requirement),
        "origin_fetch_receipt": receipt,
    }
    entry["content_id"] = _content_id(entry)
    entry = _canonical_cache_entry_v2(entry)
    sources = _external_sources_from_entry_v2(entry, requirement)
    if not sources:
        raise MarketContextError("v2 successful cache entry produced no evidence rows")
    sources = [
        _canonical_component_source_v2(source, requirement)
        for source in sources
    ]
    if persist:
        _create_or_compare(
            cache_root / "v2" / "e" / _short_cache_name(cache_ref), entry
        )
    return sources, receipt


def _cached_external_sources_v2(
    cache_root: Path, requirement: Mapping[str, Any]
) -> list[dict[str, Any]]:
    entry_root = cache_root / "v2" / "e"
    if not entry_root.exists():
        return []
    paths = sorted(entry_root.glob("*.json"))
    if len(paths) > 4096:
        raise MarketContextError("v2 market cache inventory is unbounded")
    sources: list[dict[str, Any]] = []
    for path in paths:
        entry = _canonical_cache_entry_v2(load_json_object(path), path=path)
        sources.extend(_external_sources_from_entry_v2(entry, requirement))
    return sorted(
        {str(source["source_id"]): source for source in sources}.values(),
        key=lambda source: (source["source_kind"], source["source_id"]),
    )


def _controlled_gateway_fallback_v2(
    requirement: Mapping[str, Any],
    *,
    coverage: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    schema_gaps: Mapping[str, Sequence[str]],
    gateway: Any | None,
    cache_root: Path,
    persist: bool,
    clock: Callable[[], datetime] | None,
    request_budget: MarketRequestBudget,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    guard_at = _actual_audit_time_v2(clock)
    if (
        requirement["perspective"] == "system"
        and parse_datetime(guard_at, "UTC")
        > parse_datetime(requirement["operation_anchor_at"], "UTC")
    ):
        fallback = _limitation_fallback_v2(
            requirement,
            coverage=coverage,
            sources=sources,
            status="withheld_by_cutoff",
            guard_audit_at=guard_at,
        )
        return fallback, list(_clone(sources)), _clone(coverage)
    if (
        gateway is None
        or not persist
        or str(getattr(gateway, "transport_scheme", "")).lower() != "https"
    ):
        fallback = _limitation_fallback_v2(
            requirement,
            coverage=coverage,
            sources=sources,
            status="provider_unavailable",
            guard_audit_at=guard_at,
        )
        return fallback, list(_clone(sources)), _clone(coverage)
    try:
        _require_gateway_contract(gateway)
    except MarketContextError:
        fallback = _limitation_fallback_v2(
            requirement,
            coverage=coverage,
            sources=sources,
            status="provider_unavailable",
            guard_audit_at=guard_at,
        )
        return fallback, list(_clone(sources)), _clone(coverage)
    unresolved = {
        component
        for component in requirement["required_components"]
        if coverage["components"][component]["status"] != "satisfied"
    }
    requests = [
        _clone(request)
        for request in requirement["provider_requests"]
        if request["component"] in unresolved
    ]
    if not requests and "prior_close" in unresolved:
        requests = [_request_for_missing_close_v2(requirement, sources)]
    if not requests:
        fallback = _limitation_fallback_v2(
            requirement,
            coverage=coverage,
            sources=sources,
            status="provider_unavailable",
            guard_audit_at=guard_at,
        )
        return fallback, list(_clone(sources)), _clone(coverage)
    receipts: list[dict[str, Any]] = []
    external_sources: list[dict[str, Any]] = []
    for request in requests:
        reserved = request_budget.reserve(3)
        if reserved == 0:
            if not receipts:
                fallback = _limitation_fallback_v2(
                    requirement,
                    coverage=coverage,
                    sources=sources,
                    status="budget_exhausted",
                    guard_audit_at=guard_at,
                )
                return fallback, list(_clone(sources)), _clone(coverage)
            receipts.append(
                _receipt_v2(
                    request=request,
                    requirement_id=str(requirement["requirement_id"]),
                    guard_audit_at=guard_at,
                    response_status="budget_exhausted",
                    attempt_count=0,
                    started_at=guard_at,
                    completed_at=guard_at,
                )
            )
            break
        settled = False
        request_budget.acquire_concurrency_slot()
        started_at = _actual_audit_time_v2(clock)
        try:
            try:
                response = _gateway_call(gateway, request, max_attempts=reserved)
                completed_at = _actual_audit_time_v2(clock)
                status = str(response.get("response_status") or "failed").lower()
                attempt_count = response.get("attempt_count")
                if (
                    isinstance(attempt_count, bool)
                    or not isinstance(attempt_count, int)
                    or not 0 <= attempt_count <= reserved
                ):
                    raise MarketContextError("v2 gateway attempt_count is invalid")
                if (
                    parse_datetime(completed_at, "UTC")
                    - parse_datetime(started_at, "UTC")
                    > timedelta(seconds=MARKET_LIMITS["timeout_seconds"])
                ):
                    raise MarketContextError("v2 provider call exceeded fixed timeout")
                if status == "succeeded":
                    if attempt_count < 1:
                        raise MarketContextError(
                            "successful v2 provider response requires an attempt"
                        )
                    projected, receipt = _external_entry_v2(
                        request=request,
                        response=response,
                        requirement=requirement,
                        cache_root=cache_root,
                        persist=persist,
                        guard_audit_at=guard_at,
                        started_at=started_at,
                        completed_at=completed_at,
                        attempt_count=attempt_count,
                    )
                    external_sources.extend(projected)
                else:
                    if status not in {
                        "failed",
                        "timeout",
                        "rejected",
                        "provider_unavailable",
                    }:
                        raise MarketContextError("v2 gateway status is unsupported")
                    if status == "provider_unavailable" and attempt_count != 0:
                        raise MarketContextError(
                            "provider_unavailable must have zero attempts"
                        )
                    if status != "provider_unavailable" and attempt_count == 0:
                        raise MarketContextError("attempted failure requires an attempt")
                    receipt = _receipt_v2(
                        request=request,
                        requirement_id=str(requirement["requirement_id"]),
                        guard_audit_at=guard_at,
                        response_status=status,
                        attempt_count=attempt_count,
                        started_at=(guard_at if attempt_count == 0 else started_at),
                        completed_at=(guard_at if attempt_count == 0 else completed_at),
                        system_observed_at=(
                            None if attempt_count == 0 else completed_at
                        ),
                    )
                request_budget.settle(reserved, attempt_count)
                settled = True
            except Exception:
                if not settled:
                    request_budget.settle(reserved, reserved)
                    settled = True
                completed_at = _actual_audit_time_v2(clock)
                receipt = _receipt_v2(
                    request=request,
                    requirement_id=str(requirement["requirement_id"]),
                    guard_audit_at=guard_at,
                    response_status="failed",
                    attempt_count=0,
                    attempt_count_status="unknown",
                    budget_charged_attempts=reserved,
                    started_at=started_at,
                    completed_at=completed_at,
                    system_observed_at=completed_at,
                )
        finally:
            if not settled:
                request_budget.settle(reserved, reserved)
            request_budget.release_concurrency_slot()
        receipts.append(receipt)
        if receipt["response_status"] == "provider_unavailable":
            break
    combined = sorted(
        {
            str(source["source_id"]): _clone(source)
            for source in [*sources, *external_sources]
        }.values(),
        key=lambda source: (source["source_kind"], source["source_id"]),
    )
    combined = _resolve_external_revision_conflicts_v2(combined, requirement)
    coverage_after = _coverage_v2(requirement, combined, schema_gaps)
    successful = [
        receipt
        for receipt in receipts
        if receipt["response_status"] == "succeeded"
    ]
    request_count = sum(int(receipt["attempt_count"]) for receipt in receipts)
    has_unknown_attempt_count = any(
        receipt["attempt_count_status"] == "unknown" for receipt in receipts
    )
    if not successful and request_count == 0 and not has_unknown_attempt_count:
        fallback = _limitation_fallback_v2(
            requirement,
            coverage=coverage_after,
            sources=combined,
            status="provider_unavailable",
            guard_audit_at=guard_at,
        )
        return fallback, combined, coverage_after
    if successful:
        fallback_status = "succeeded"
    elif request_count or has_unknown_attempt_count:
        fallback_status = "failed"
    else:
        fallback_status = "provider_unavailable"
    fallback = _canonical_fallback_v2(
        {
            "policy_version": MARKET_FALLBACK_POLICY_VERSION_V2,
            "public_information_policy_version": PUBLIC_INFORMATION_POLICY_VERSION,
            "perspective": requirement["perspective"],
            "allowlist_version": MARKET_PROVIDER_ALLOWLIST_VERSION,
            "allowlist_sha256": MARKET_PROVIDER_ALLOWLIST_SHA256,
            "coverage_before": coverage["status"],
            "coverage_after": coverage_after["status"],
            "status": fallback_status,
            "limitation_code": (
                "provider_attempt_count_unknown"
                if has_unknown_attempt_count
                else None
            ),
            "guard_audit_at": None,
            "request_count": request_count,
            "request_count_status": (
                "bounded_unknown"
                if any(
                    receipt["attempt_count_status"] == "unknown"
                    for receipt in receipts
                )
                else "verified"
            ),
            "unverified_attempt_upper_bound": sum(
                int(receipt["budget_charged_attempts"])
                for receipt in receipts
                if receipt["attempt_count_status"] == "unknown"
            ),
            "limits": dict(MARKET_LIMITS),
            "allowlist": sorted(MARKET_PROVIDER_ALLOWLIST),
            "cache_refs": _frozen_source_refs_v2(combined),
            "fetch_receipt_refs": sorted(
                receipt["receipt_id"] for receipt in receipts
            ),
            "fetch_receipts": sorted(
                receipts, key=lambda receipt: receipt["receipt_id"]
            ),
            "offline_consumers": {consumer: False for consumer in OFFLINE_CONSUMERS},
        }
    )
    return fallback, combined, coverage_after


def _market_axis_v2(
    requirement: Mapping[str, Any],
    coverage: Mapping[str, Any],
    fallback: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    evidence_manifest = _source_manifest_v2(sources)
    eligible = [
        source
        for source in sources
        if source.get("payload", {})
        .get("perspective_eligibility", {})
        .get("status")
        == "eligible"
    ]
    retrospective = [
        source
        for source in sources
        if source.get("payload", {})
        .get("perspective_eligibility", {})
        .get("status")
        == "ineligible"
    ]
    unknown = [
        source
        for source in sources
        if source.get("payload", {})
        .get("perspective_eligibility", {})
        .get("status")
        in {"unknown", "ambiguous"}
    ]
    ambiguous = [
        source
        for source in unknown
        if source["payload"]["perspective_eligibility"]["status"] == "ambiguous"
    ]
    unproven = [
        source
        for source in unknown
        if source["payload"]["perspective_eligibility"]["status"] == "unknown"
    ]
    state = str(coverage["status"])
    if state == "satisfied":
        status = "available"
    elif state == "stale":
        status = "stale"
    elif state == "insufficient":
        status = "partial" if eligible else "insufficient"
    else:
        status = "missing"
    if eligible:
        role = (
            "user_known_at_operation_by_verified_publication"
            if requirement["perspective"] == "user"
            else "system_known_at_operation"
        )
    elif retrospective:
        role = "retrospective_context"
    elif unknown:
        role = "ambiguous" if ambiguous else "unknown"
    else:
        role = "missing"
    price_evidence = [
        source
        for source in sources
        if source.get("payload", {}).get("component")
        in {"prior_close", "daily", "minute"}
    ]
    eligible_prices = [source for source in price_evidence if source in eligible]
    retrospective_prices = [
        source for source in price_evidence if source in retrospective
    ]
    ambiguous_prices = [source for source in price_evidence if source in ambiguous]
    unproven_prices = [source for source in price_evidence if source in unproven]
    representative_pool = (
        eligible_prices
        or eligible
        or retrospective_prices
        or retrospective
        or ambiguous_prices
        or ambiguous
        or unproven_prices
        or unproven
    )
    display_source = max(
        representative_pool,
        key=lambda source: parse_datetime(
            source["payload"]["coverage_effective_at"], "UTC"
        ),
        default=None,
    )
    selected_fetched = (
        None
        if display_source is None
        else parse_datetime(display_source["payload"]["fetched_at"], "UTC")
    )
    selected_observed = (
        None
        if display_source is None
        else parse_datetime(
            display_source["payload"]["system_observed_at"], "UTC"
        )
    )
    public_at = (
        None
        if display_source is None
        else display_source["payload"].get("publicly_available_at")
    )
    detailed_basis = (
        None
        if display_source is None
        else str(
            display_source["payload"].get("publicly_available_basis") or "unknown"
        )
    )
    public_basis = {
        None: "not_applicable",
        MARKET_EXCHANGE_PUBLICATION_RULE_VERSION: "exchange_calendar",
        "provider_exact_publication_time.v1": "provider_declared",
        "provider_publication_date_source_timezone.v1": "verified_publication_interval",
        "unknown": "unknown",
        "conflicted": "unknown",
    }[detailed_basis]
    representative_eligibility = (
        None
        if display_source is None
        else _clone(display_source["payload"]["perspective_eligibility"])
    )
    if role in {
        "user_known_at_operation_by_verified_publication",
        "system_known_at_operation",
    } and (
        representative_eligibility is None
        or representative_eligibility["status"] != "eligible"
    ):
        raise MarketContextError(
            "v2 known market role lacks an eligible representative source"
        )
    if role == "retrospective_context" and (
        representative_eligibility is None
        or representative_eligibility["status"] != "ineligible"
    ):
        raise MarketContextError(
            "v2 retrospective market role lacks an ineligible representative source"
        )
    if role == "ambiguous" and (
        representative_eligibility is None
        or representative_eligibility["status"] != "ambiguous"
    ):
        raise MarketContextError(
            "v2 ambiguous market role lacks an ambiguous representative source"
        )
    if role == "unknown" and (
        representative_eligibility is None
        or representative_eligibility["status"] != "unknown"
    ):
        raise MarketContextError(
            "v2 unknown market role lacks an unknown representative source"
        )
    if role == "missing" and display_source is not None:
        raise MarketContextError("v2 missing market role cannot name a representative")
    summary = {
        "available": "市场信息已按当前视角证明在操作时可用。",
        "partial": "仅部分市场信息按当前视角满足操作时资格。",
        "insufficient": "存在市场证据，但不能提升为操作时可用覆盖。",
        "stale": "按当前视角可用的市场信息已过期。",
        "missing": "未证明按当前视角在操作时可用的市场信息。",
    }[status]
    evidence_manifest_ref = (
        "market_evidence_manifest:" + str(evidence_manifest["content_id"])
    )
    refs = sorted(
        set(_frozen_source_refs_v2(sources))
        | {str(requirement["requirement_id"]), evidence_manifest_ref}
    )
    return {
        "status": status,
        "temporal_role": role,
        "perspective": requirement["perspective"],
        "eligible_source_refs": sorted(str(source["source_id"]) for source in eligible),
        "retrospective_source_refs": sorted(
            str(source["source_id"]) for source in retrospective
        ),
        "unknown_source_refs": sorted(str(source["source_id"]) for source in unknown),
        "effective_at": (
            None
            if display_source is None
            else str(display_source["payload"]["effective_at"])
        ),
        "publicly_available_at": public_at,
        "publicly_available_basis": public_basis,
        "fetched_at": utc_iso(selected_fetched, "UTC") if selected_fetched else None,
        "system_observed_at": (
            utc_iso(selected_observed, "UTC") if selected_observed else None
        ),
        "representative_source_id": (
            None if display_source is None else str(display_source["source_id"])
        ),
        "representative_source_content_id": (
            None if display_source is None else _content_id(display_source)
        ),
        "information_time": (
            None
            if display_source is None
            else _clone(display_source["payload"]["information_time"])
        ),
        "version_provenance": (
            None
            if display_source is None
            else _clone(display_source["payload"]["version_provenance"])
        ),
        "perspective_eligibility": representative_eligibility,
        "market_evidence_manifest_content_id": evidence_manifest["content_id"],
        "summary": summary,
        "source_refs": refs,
    }


def _gap_v2(
    requirement: Mapping[str, Any],
    *,
    code: str,
    severity: str,
    owner: str,
    next_step: str,
    source_refs: Sequence[str],
) -> dict[str, Any]:
    return {
        "gap_id": "market_gap_v2_"
        + hashlib.sha256(
            canonical_json_bytes(
                {
                    "requirement_id": requirement["requirement_id"],
                    "code": code,
                }
            )
        ).hexdigest()[:32],
        "axis": "market",
        "code": code,
        "severity": severity,
        "blocks_axis": False,
        "owner": owner,
        "next_step": next_step,
        "source_refs": sorted(set(str(ref) for ref in source_refs)),
    }


def _market_gaps_v2(
    requirement: Mapping[str, Any],
    coverage: Mapping[str, Any],
    fallback: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    refs = sorted(
        set(_frozen_source_refs_v2(sources)) | {str(requirement["requirement_id"])}
    )
    gaps: list[dict[str, Any]] = []
    state = str(coverage["status"])
    if state != "satisfied":
        gaps.append(
            _gap_v2(
                requirement,
                code={
                    "missing": "MARKET_CONTEXT_MISSING",
                    "stale": "MARKET_CONTEXT_STALE",
                    "insufficient": "MARKET_CONTEXT_INSUFFICIENT",
                }[state],
                severity="warning",
                owner="data",
                next_step="保留当前视角的局部缺口；操作事实复盘继续。",
                source_refs=refs,
            )
        )
    reason_map = {
        "publication_time_or_revision_unproven": "PUBLICATION_OR_REVISION_UNPROVEN",
        "publication_time_or_revision_conflicted": "PUBLICATION_TIME_CONFLICTED",
        "publication_revision_binding_conflicted": "PUBLICATION_REVISION_CONFLICTED",
        "publication_interval_touches_operation_anchor": "PUBLICATION_TIME_AMBIGUOUS",
        "post_operation_publication": "POST_OPERATION_PUBLICATION",
        "system_observed_after_operation": "SYSTEM_OBSERVED_AFTER_OPERATION",
        "system_observation_unknown": "SYSTEM_OBSERVATION_UNKNOWN",
        "current_only_not_point_in_time": "CURRENT_INDUSTRY_NOT_POINT_IN_TIME",
    }
    by_reason: dict[str, list[str]] = {}
    for source in sources:
        reason = str(
            source.get("payload", {})
            .get("perspective_eligibility", {})
            .get("reason_code")
            or ""
        )
        if reason in reason_map:
            by_reason.setdefault(reason, []).append(str(source["source_id"]))
    for reason, source_refs in sorted(by_reason.items()):
        gaps.append(
            _gap_v2(
                requirement,
                code=reason_map[reason],
                severity="info",
                owner="data" if "SYSTEM_" not in reason_map[reason] else "system",
                next_step="保留真实时间与版本证据，不提升操作时覆盖。",
                source_refs=[str(requirement["requirement_id"]), *source_refs],
            )
        )
    limitation_codes = {
        "provider_unavailable": "MARKET_PROVIDER_UNAVAILABLE",
        "withheld_by_cutoff": "MARKET_WITHHELD_BY_CUTOFF",
        "budget_exhausted": "MARKET_REQUEST_BUDGET_EXHAUSTED",
        "failed": "MARKET_PROVIDER_FAILED",
    }
    if fallback["status"] in limitation_codes:
        gaps.append(
            _gap_v2(
                requirement,
                code=limitation_codes[str(fallback["status"])],
                severity="info",
                owner="system",
                next_step="市场轴保持局部限制；不得取消 active checkpoint。",
                source_refs=refs,
            )
        )
    receipt_limitations = {
        "provider_unavailable": "MARKET_PROVIDER_UNAVAILABLE",
        "budget_exhausted": "MARKET_REQUEST_BUDGET_EXHAUSTED",
    }
    for receipt_status in sorted(
        {
            str(receipt["response_status"])
            for receipt in fallback.get("fetch_receipts", [])
            if receipt.get("response_status") in receipt_limitations
        }
    ):
        gaps.append(
            _gap_v2(
                requirement,
                code=receipt_limitations[receipt_status],
                severity="info",
                owner="system",
                next_step=(
                    "保留部分成功与后续限制的完整请求证据；操作事实复盘继续。"
                ),
                source_refs=refs,
            )
        )
    if fallback.get("request_count_status") == "bounded_unknown":
        gaps.append(
            _gap_v2(
                requirement,
                code="PROVIDER_ATTEMPT_COUNT_UNKNOWN",
                severity="warning",
                owner="system",
                next_step="保留未知实际请求次数与保守预算上界；操作事实复盘继续。",
                source_refs=refs,
            )
        )
    return sorted(
        {str(gap["gap_id"]): gap for gap in gaps}.values(),
        key=lambda gap: gap["gap_id"],
    )


def _source_manifest_v2(
    sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    entries = sorted(
        (
            {
                "source_id": str(source["source_id"]),
                "source_kind": str(source["source_kind"]),
                "payload_content_id": _content_id(source["payload"]),
                "envelope_content_id": _content_id(source),
            }
            for source in sources
        ),
        key=lambda item: (item["source_kind"], item["source_id"]),
    )
    result: dict[str, Any] = {
        "schema_version": MARKET_SOURCE_MANIFEST_VERSION_V2,
        "sources": entries,
    }
    result["content_id"] = _content_id(result)
    return result


def _manifest_audit_at_v2(
    requirement: Mapping[str, Any],
    fallback: Mapping[str, Any],
    market_axis: Mapping[str, Any],
) -> str:
    candidates = [parse_datetime(requirement["knowledge_cutoff"], "UTC")]
    for value in (
        fallback.get("guard_audit_at"),
        market_axis.get("fetched_at"),
        market_axis.get("system_observed_at"),
    ):
        if value is not None:
            candidates.append(parse_datetime(value, "UTC"))
    for receipt in fallback.get("fetch_receipts", []):
        for field in (
            "guard_audit_at",
            "started_at",
            "fetched_at",
            "system_observed_at",
            "completed_at",
        ):
            if receipt.get(field) is not None:
                candidates.append(parse_datetime(receipt[field], "UTC"))
    return utc_iso(max(candidates), "UTC")


def _market_input_projection_v2(
    *,
    requirement: Mapping[str, Any],
    resolution_id: str,
    coverage_after: Mapping[str, Any],
    market_axis: Mapping[str, Any],
    market_fallback: Mapping[str, Any],
    market_gaps: Sequence[Mapping[str, Any]],
    component_sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "requirement_id": requirement["requirement_id"],
        "resolution_id": resolution_id,
        "instrument_id": requirement["instrument_id"],
        "perspective": requirement["perspective"],
        "operation_anchor_event_id": requirement["operation_anchor_event_id"],
        "operation_anchor_at": requirement["operation_anchor_at"],
        "operation_anchor_ordering_key": requirement[
            "operation_anchor_ordering_key"
        ],
        "as_of": requirement["as_of"],
        "knowledge_cutoff": requirement["knowledge_cutoff"],
        "information_time_policy_version": requirement[
            "information_time_policy_version"
        ],
        "coverage_after": coverage_after,
        "market_axis": market_axis,
        "market_fallback": market_fallback,
        "market_gaps": list(market_gaps),
        "component_sources": list(component_sources),
    }


def _assemble_resolution_v2(
    *,
    requirement: Mapping[str, Any],
    coverage_before: Mapping[str, Any],
    coverage_after: Mapping[str, Any],
    fallback: Mapping[str, Any],
    market_axis: Mapping[str, Any],
    market_gaps: Sequence[Mapping[str, Any]],
    row_sources: Sequence[Mapping[str, Any]],
    source_read: Mapping[str, Any],
) -> dict[str, Any]:
    canonical_source_read = _canonical_source_read_v2(source_read)
    resolution_id = "market_resolution_v2_" + str(
        requirement["requirement_id"]
    ).rsplit("_", 1)[-1]
    component_sources = sorted(
        _clone(row_sources), key=lambda source: (source["source_kind"], source["source_id"])
    )
    market_evidence_manifest = _source_manifest_v2(component_sources)
    if (
        market_axis.get("market_evidence_manifest_content_id")
        != market_evidence_manifest["content_id"]
    ):
        raise MarketContextError("v2 market axis/evidence manifest hash drift")
    market_input = _market_input_projection_v2(
        requirement=requirement,
        resolution_id=resolution_id,
        coverage_after=coverage_after,
        market_axis=market_axis,
        market_fallback=fallback,
        market_gaps=market_gaps,
        component_sources=component_sources,
    )
    market_input_content_id = _content_id(market_input)
    manifest_source_id = "market_manifest_v2_" + market_input_content_id.split(
        ":", 1
    )[1]
    manifest_audit_at = _manifest_audit_at_v2(requirement, fallback, market_axis)
    manifest_payload = {
        "schema_version": MARKET_CONTEXT_MANIFEST_VERSION_V2,
        "source_id": manifest_source_id,
        "requirement": _clone(requirement),
        "requirement_id": requirement["requirement_id"],
        "resolution_id": resolution_id,
        "instrument_id": requirement["instrument_id"],
        "perspective": requirement["perspective"],
        "operation_anchor_event_id": requirement["operation_anchor_event_id"],
        "operation_anchor_at": requirement["operation_anchor_at"],
        "operation_anchor_ordering_key": requirement[
            "operation_anchor_ordering_key"
        ],
        "as_of": requirement["as_of"],
        "knowledge_cutoff": requirement["knowledge_cutoff"],
        "information_time_policy_version": requirement[
            "information_time_policy_version"
        ],
        "manifest_audit_at": manifest_audit_at,
        "market_input_content_id": market_input_content_id,
        "market_status": market_axis["status"],
        "coverage_before": _clone(coverage_before),
        "coverage_after": _clone(coverage_after),
        "market_fallback": _clone(fallback),
        "market_axis": _clone(market_axis),
        "market_gaps": _clone(market_gaps),
        "component_source_ids": sorted(
            str(source["source_id"]) for source in component_sources
        ),
        "source_verification": "verified",
        "network_allowed": False,
    }
    manifest_envelope = {
        "source_id": manifest_source_id,
        "source_kind": "market_context",
        "availability": {
            "available": "available",
            "stale": "stale",
            "partial": "ambiguous",
            "insufficient": "ambiguous",
            "missing": "missing",
            "failed": "missing",
        }[str(market_axis["status"])],
        "effective_at": requirement["as_of"],
        "knowledge_at": manifest_audit_at,
        "locator": f"market_resolution_v2:{resolution_id}",
        "warning_codes": sorted(str(gap["code"]) for gap in market_gaps),
        "payload": manifest_payload,
    }
    supplementals = sorted(
        [*component_sources, manifest_envelope],
        key=lambda source: (source["source_kind"], source["source_id"]),
    )
    resolution: dict[str, Any] = {
        "schema_version": MARKET_CONTEXT_RESOLUTION_VERSION_V2,
        "resolution_id": resolution_id,
        "requirement_id": requirement["requirement_id"],
        "perspective": requirement["perspective"],
        "operation_anchor_event_id": requirement["operation_anchor_event_id"],
        "operation_anchor_at": requirement["operation_anchor_at"],
        "operation_anchor_ordering_key": requirement[
            "operation_anchor_ordering_key"
        ],
        "as_of": requirement["as_of"],
        "knowledge_cutoff": requirement["knowledge_cutoff"],
        "information_time_policy_version": requirement[
            "information_time_policy_version"
        ],
        "requirement": _clone(requirement),
        "source_read": canonical_source_read,
        "coverage_before": _clone(coverage_before),
        "coverage_after": _clone(coverage_after),
        "market_axis": _clone(market_axis),
        "market_fallback": _clone(fallback),
        "market_gaps": _clone(market_gaps),
        "supplemental_sources": supplementals,
        "market_evidence_manifest": market_evidence_manifest,
        "market_source_manifest": _source_manifest_v2(supplementals),
        "market_input_content_id": market_input_content_id,
        "offline_consumers": {consumer: False for consumer in OFFLINE_CONSUMERS},
        "governance": {
            "local_first": True,
            "source_database_read_only": True,
            "current_industry_point_in_time": False,
            "no_owner_action_default_for_market": True,
            "no_network_after_freeze": True,
            "actual_user_observation_proven": False,
            "coverage_is_perspective_eligible_only": True,
            "acquisition_audit_not_backdated": True,
        },
    }
    resolution["content_id"] = _content_id(resolution)
    return _clone(resolution)


def _canonical_component_source_v2(
    source: Mapping[str, Any], requirement: Mapping[str, Any]
) -> dict[str, Any]:
    envelope = _closed(
        source,
        name="v2 market component source",
        required={
            "source_id",
            "source_kind",
            "availability",
            "effective_at",
            "knowledge_at",
            "locator",
            "warning_codes",
            "payload",
        },
    )
    payload = _closed(
        envelope["payload"],
        name="v2 market component payload",
        required={
            "schema_version",
            "source_id",
            "component",
            "origin",
            "instrument_id",
            "effective_at",
            "coverage_effective_at",
            "publicly_available_at",
            "publicly_available_basis",
            "fetched_at",
            "system_observed_at",
            "temporal_role",
            "information_time",
            "version_provenance",
            "perspective_eligibility",
            "source_table",
            "source_record_id",
            "source_provider",
            "point_in_time",
            "values",
            "raw_content_sha256",
            "normalized_content_sha256",
            "cache_entry_ref",
            "origin_requirement_id",
            "projection_requirement_id",
            "origin_fetch_receipt",
            "origin_cache_entry",
            "origin_local_record",
            "cache_lineage",
        },
    )
    if payload["schema_version"] != MARKET_CONTEXT_SOURCE_VERSION_V2:
        raise MarketContextError("unsupported v2 market source version")
    component = _text(payload["component"], "v2 market component")
    if component not in MARKET_COMPONENTS:
        raise MarketContextError("v2 market component is unsupported")
    origin = str(payload["origin"])
    if origin not in {"portfolio_local_cache", "external_provider_cache"}:
        raise MarketContextError("v2 source origin is unsupported")
    source_id = _text(envelope["source_id"], "v2 source_id")
    if payload["source_id"] != source_id:
        raise MarketContextError("v2 source envelope/payload identity drift")
    identity_material = dict(payload)
    identity_material["source_id"] = None
    expected_source_id = "market_source_v2_" + hashlib.sha256(
        canonical_json_bytes(identity_material)
    ).hexdigest()
    if source_id != expected_source_id:
        raise MarketContextError("v2 component source identity drift")
    if (
        payload["instrument_id"] != requirement["instrument_id"]
        or payload["projection_requirement_id"] != requirement["requirement_id"]
    ):
        raise MarketContextError("v2 source requirement/instrument drift")
    effective = _timestamp(payload["effective_at"], "v2 source effective_at")
    coverage_effective = _timestamp(
        payload["coverage_effective_at"], "v2 coverage_effective_at"
    )
    fetched = _timestamp(payload["fetched_at"], "v2 source fetched_at")
    observed = _timestamp(
        payload["system_observed_at"], "v2 source system_observed_at"
    )
    if parse_datetime(fetched, "UTC") > parse_datetime(observed, "UTC"):
        raise MarketContextError("v2 source acquisition order drift")
    if (
        (
            component != "current_industry"
            and parse_datetime(effective, "UTC")
            > parse_datetime(fetched, "UTC")
        )
        or parse_datetime(coverage_effective, "UTC")
        > parse_datetime(fetched, "UTC")
    ):
        raise MarketContextError(
            "v2 source effective time follows acquisition"
        )
    if (
        parse_datetime(coverage_effective, "UTC")
        > parse_datetime(requirement["as_of"], "UTC")
        and not (
            origin == "external_provider_cache"
            and component in {"instrument", "current_industry"}
        )
    ):
        raise MarketContextError("v2 source coverage exceeds as_of")
    information = _canonical_information_time_v2(payload["information_time"])
    version = _canonical_version_provenance_v2(payload["version_provenance"])
    if version["status"] == "verified" and (
        version["source_ref"].startswith("MISSING_")
        or version["revision_ref"].startswith("MISSING_")
    ):
        raise MarketContextError("verified v2 version uses missing provenance")
    eligibility = _canonical_eligibility_v2(
        payload["perspective_eligibility"],
        requirement=requirement,
        component=component,
        information_time=information,
        version_provenance=version,
        system_observed_at=observed,
    )
    anchor = parse_datetime(requirement["operation_anchor_at"], "UTC")
    if eligibility["status"] == "eligible" and (
        parse_datetime(effective, "UTC") > anchor
        or parse_datetime(coverage_effective, "UTC") > anchor
    ):
        raise MarketContextError(
            "v2 eligible source effective scope exceeds operation anchor"
        )
    if information["status"] == "verified":
        public_upper = parse_datetime(information["upper_bound"], "UTC")
        if (
            parse_datetime(effective, "UTC") > public_upper
            or public_upper > parse_datetime(fetched, "UTC")
        ):
            raise MarketContextError(
                "v2 source effective/public/fetch order drift"
            )
    expected_public = (
        information["upper_bound"] if information["status"] == "verified" else None
    )
    if (
        payload["publicly_available_at"] != expected_public
        or payload["publicly_available_basis"] != information["basis"]
        or payload["temporal_role"] != eligibility["temporal_role"]
    ):
        raise MarketContextError("v2 public-time/source projection drift")
    if parse_datetime(fetched, "UTC") < parse_datetime(
        coverage_effective, "UTC"
    ) and eligibility["status"] == "eligible":
        raise MarketContextError("v2 eligible source was fetched before effective time")
    if (
        envelope["availability"] != "available"
        or envelope["effective_at"] != effective
        or envelope["knowledge_at"] != observed
    ):
        raise MarketContextError("v2 source envelope temporal drift")
    expected_kind = {
        "prior_close": "price",
        "daily": "market_context",
        "minute": "market_context",
        "factor": "market_context",
        "instrument": "other",
        "current_industry": "classification",
    }[component]
    if envelope["source_kind"] != expected_kind:
        raise MarketContextError("v2 source kind drift")
    if not isinstance(payload["values"], Mapping):
        raise MarketContextError("v2 source values must be an object")
    values = {
        str(key): value
        for key, value in sorted(payload["values"].items())
    }
    if any(value is not None and not isinstance(value, str) for value in values.values()):
        raise MarketContextError("v2 source values must be canonical strings")
    if not _component_values_sufficient(component, values):
        raise MarketContextError("v2 source values are materially insufficient")
    expected_warnings = (
        ["CURRENT_INDUSTRY_NOT_POINT_IN_TIME"]
        if component == "current_industry"
        else []
    )
    if (
        envelope["warning_codes"] != expected_warnings
        or payload["point_in_time"]
        != (False if component == "current_industry" else None)
    ):
        raise MarketContextError("v2 source point-in-time warning drift")
    source_table = _text(payload["source_table"], "v2 source_table")
    source_record_id = _text(
        payload["source_record_id"], "v2 source_record_id"
    )
    source_provider = _text(
        payload["source_provider"], "v2 source_provider"
    )
    if origin == "portfolio_local_cache":
        origin_record = payload["origin_local_record"]
        if not isinstance(origin_record, Mapping):
            raise MarketContextError(
                "v2 local source lacks its complete origin record proof"
            )
        expected_table = _TABLES[component]
        local_material = {
            "component": component,
            "instrument_id": requirement["instrument_id"],
            "source_table": source_table,
            "source_record_id": source_record_id,
            "values": values,
        }
        expected_content_hash = _content_id(local_material)
        expected_source_ref = f"portfolio_cache:{source_table}:{source_record_id}"
        expected_revision_ref = (
            f"{source_table}:{source_record_id}:{expected_content_hash}"
        )
        if (
            source_table != expected_table
            or version["content_sha256"] != expected_content_hash
            or payload["normalized_content_sha256"] != expected_content_hash
            or payload["raw_content_sha256"] is not None
            or version["source_ref"] != expected_source_ref
            or version["revision_ref"] != expected_revision_ref
            or payload["cache_entry_ref"] is not None
            or payload["origin_requirement_id"] is not None
            or payload["origin_fetch_receipt"] is not None
            or payload["origin_cache_entry"] is not None
            or payload["cache_lineage"] != [requirement["requirement_id"]]
            or fetched != observed
            or envelope["locator"]
            != f"portfolio_local_cache:{source_table}:{source_record_id}"
        ):
            raise MarketContextError("v2 local source provenance/content drift")
        rebuilt_local = _local_source_from_record_v2(
            requirement=requirement,
            component=component,
            record=origin_record,
        )
        if rebuilt_local != _clone(envelope):
            raise MarketContextError("v2 local source canonical proof drift")
    elif origin == "external_provider_cache":
        if payload["origin_local_record"] is not None:
            raise MarketContextError("v2 external source has local origin proof")
        receipt = _canonical_receipt_v2(payload["origin_fetch_receipt"])
        cache_ref = _text(payload["cache_entry_ref"], "v2 cache_entry_ref")
        origin_requirement_id = _text(
            payload["origin_requirement_id"], "v2 origin_requirement_id"
        )
        expected_content_hash = market_row_content_sha256_v2(
            component=component,
            instrument_id=str(requirement["instrument_id"]),
            row=values,
        )
        expected_lineage = sorted(
            {origin_requirement_id, str(requirement["requirement_id"])}
        )
        provider_id = str(receipt["provider_id"])
        endpoint_id = str(receipt["endpoint_id"])
        _validate_provider_component_endpoint_v2(
            component=component,
            provider_id=provider_id,
            endpoint_id=endpoint_id,
        )
        canonical_publication_refs = {
            _provider_publication_source_ref_v2(
                provider_id=provider_id,
                endpoint_id=endpoint_id,
                publication_basis=basis,
                revision_ref=version["revision_ref"],
                content_sha256=expected_content_hash,
                information_time=information,
            )
            for basis in _V2_TRUSTED_PROVIDER_PUBLICATION_BASES
            if _V2_PROVIDER_REVISION_REF_PATTERN.fullmatch(
                version["revision_ref"]
            )
        }
        has_canonical_publication_ref = (
            version["source_ref"] in canonical_publication_refs
        )
        if (
            source_table != "v2_market_cache"
            or re.fullmatch(
                re.escape(cache_ref) + r":[0-9a-f]{24}", source_record_id
            )
            is None
            or source_provider != f"{provider_id}:{endpoint_id}"
            or version["content_sha256"] != expected_content_hash
            or payload["normalized_content_sha256"] != expected_content_hash
            or payload["raw_content_sha256"] != receipt["raw_content_sha256"]
            or cache_ref not in receipt["cache_entry_refs"]
            or receipt["response_status"] != "succeeded"
            or receipt["cache_lineage"] != [origin_requirement_id]
            or payload["cache_lineage"] != expected_lineage
            or payload["fetched_at"] != receipt["fetched_at"]
            or payload["system_observed_at"] != receipt["system_observed_at"]
            or envelope["locator"]
            != f"external_provider_cache:{source_table}:{source_record_id}"
            or (
                version["status"] == "verified"
                and not has_canonical_publication_ref
            )
            or (
                version["source_ref"].startswith("provider_publication:")
                and not has_canonical_publication_ref
            )
        ):
            raise MarketContextError("v2 external source provenance/content drift")
        base_source = _external_base_source_from_proof_v2(
            envelope, requirement
        )
        if _clone(envelope) not in (
            base_source,
            _conflicted_external_source_v2(base_source, requirement),
        ):
            raise MarketContextError("v2 external source origin proof drift")
    else:
        raise MarketContextError("v2 source origin is unsupported")
    return _clone({**dict(envelope), "payload": payload})


def _canonical_coverage_v2(
    value: Mapping[str, Any], requirement: Mapping[str, Any]
) -> dict[str, Any]:
    item = _closed(
        value,
        name="v2 market coverage",
        required={
            "schema_version",
            "requirement_id",
            "perspective",
            "status",
            "components",
            "eligible_source_refs",
            "evidence_source_refs",
            "content_id",
        },
    )
    if (
        item["schema_version"] != MARKET_COVERAGE_CLASSIFIER_VERSION_V2
        or item["requirement_id"] != requirement["requirement_id"]
        or item["perspective"] != requirement["perspective"]
        or item["status"] not in {"satisfied", "missing", "stale", "insufficient"}
    ):
        raise MarketContextError("v2 coverage discriminator/identity drift")
    if not isinstance(item["components"], Mapping) or set(item["components"]) != set(
        MARKET_COMPONENTS
    ):
        raise MarketContextError("v2 coverage component set drift")
    for component in MARKET_COMPONENTS:
        detail = _closed(
            item["components"][component],
            name=f"v2 coverage component {component}",
            required={
                "requirement",
                "status",
                "eligible_row_count",
                "evidence_row_count",
                "latest_effective_at",
                "eligible_source_refs",
                "retrospective_source_refs",
                "unknown_source_refs",
                "reason_codes",
                "temporal_scope",
            },
        )
        if detail["status"] not in {"satisfied", "missing", "stale"}:
            raise MarketContextError("v2 component coverage status drift")
        for key in (
            "eligible_source_refs",
            "retrospective_source_refs",
            "unknown_source_refs",
            "reason_codes",
        ):
            values = list(detail[key])
            if values != sorted(set(_text(ref, f"coverage {key}") for ref in values)):
                raise MarketContextError("v2 coverage refs/codes are not canonical")
        if detail["eligible_row_count"] != len(detail["eligible_source_refs"]):
            raise MarketContextError("v2 eligible row count drift")
        if detail["evidence_row_count"] != sum(
            len(detail[key])
            for key in (
                "eligible_source_refs",
                "retrospective_source_refs",
                "unknown_source_refs",
            )
        ):
            raise MarketContextError("v2 evidence row count drift")
        if detail["latest_effective_at"] is not None:
            _timestamp(
                detail["latest_effective_at"],
                f"coverage {component} latest_effective_at",
            )
    for key in ("eligible_source_refs", "evidence_source_refs"):
        values = list(item[key])
        if values != sorted(set(_text(ref, f"coverage {key}") for ref in values)):
            raise MarketContextError("v2 aggregate coverage refs are not canonical")
    content_material = dict(item)
    supplied = content_material.pop("content_id")
    if supplied != _content_id(content_material):
        raise MarketContextError("v2 coverage content ID drift")
    return _clone(item)


def _assert_coverage_projection_matches_v2(
    actual: Mapping[str, Any],
    rebuilt: Mapping[str, Any],
    *,
    label: str,
) -> None:
    for key in ("status", "eligible_source_refs", "evidence_source_refs"):
        if actual[key] != rebuilt[key]:
            raise MarketContextError(f"v2 {label} perspective coverage/source drift")
    for component in MARKET_COMPONENTS:
        for key in (
            "status",
            "eligible_row_count",
            "evidence_row_count",
            "latest_effective_at",
            "eligible_source_refs",
            "retrospective_source_refs",
            "unknown_source_refs",
        ):
            if actual["components"][component][key] != rebuilt["components"][
                component
            ][key]:
                raise MarketContextError(
                    f"v2 {label} component coverage drift"
                )


def validate_market_context_resolution_v2(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    try:
        root = _closed(
            value,
            name="v2 market context resolution",
            required={
                "schema_version",
                "resolution_id",
                "requirement_id",
                "perspective",
                "operation_anchor_event_id",
                "operation_anchor_at",
                "operation_anchor_ordering_key",
                "as_of",
                "knowledge_cutoff",
                "information_time_policy_version",
                "requirement",
                "source_read",
                "coverage_before",
                "coverage_after",
                "market_axis",
                "market_fallback",
                "market_gaps",
                "supplemental_sources",
                "market_evidence_manifest",
                "market_source_manifest",
                "market_input_content_id",
                "offline_consumers",
                "governance",
                "content_id",
            },
        )
        if root["schema_version"] != MARKET_CONTEXT_RESOLUTION_VERSION_V2:
            raise MarketContextError("unsupported v2 market resolution version")
        content_material = dict(root)
        supplied_content_id = content_material.pop("content_id")
        if supplied_content_id != _content_id(content_material):
            raise MarketContextError("v2 market resolution content ID drift")
        requirement = canonical_market_cache_requirement_v2(root["requirement"])
        coupling = {
            "requirement_id": requirement["requirement_id"],
            "perspective": requirement["perspective"],
            "operation_anchor_event_id": requirement["operation_anchor_event_id"],
            "operation_anchor_at": requirement["operation_anchor_at"],
            "operation_anchor_ordering_key": requirement[
                "operation_anchor_ordering_key"
            ],
            "as_of": requirement["as_of"],
            "knowledge_cutoff": requirement["knowledge_cutoff"],
            "information_time_policy_version": requirement[
                "information_time_policy_version"
            ],
        }
        if any(root.get(key) != expected for key, expected in coupling.items()):
            raise MarketContextError("v2 requirement/resolution identity drift")
        expected_resolution_id = "market_resolution_v2_" + str(
            requirement["requirement_id"]
        ).rsplit("_", 1)[-1]
        if root["resolution_id"] != expected_resolution_id:
            raise MarketContextError("v2 market resolution identity drift")
        source_read = _canonical_source_read_v2(root["source_read"])
        if source_read != root["source_read"]:
            raise MarketContextError("v2 source read proof canonical drift")
        fallback = _canonical_fallback_v2(root["market_fallback"])
        if fallback != root["market_fallback"]:
            raise MarketContextError("v2 fallback canonical drift")
        coverage_before = _canonical_coverage_v2(
            root["coverage_before"], requirement
        )
        coverage_after = _canonical_coverage_v2(
            root["coverage_after"], requirement
        )
        if any(
            root["offline_consumers"].get(consumer) is not False
            for consumer in OFFLINE_CONSUMERS
        ):
            raise MarketContextError("v2 post-freeze consumers must remain offline")
        if not isinstance(root["supplemental_sources"], list):
            raise MarketContextError("v2 supplemental_sources must be an array")
        if any(
            not isinstance(source, Mapping)
            for source in root["supplemental_sources"]
        ):
            raise MarketContextError("v2 supplemental source must be an object")
        if any(
            not isinstance(source.get("payload"), Mapping)
            for source in root["supplemental_sources"]
        ):
            raise MarketContextError("v2 supplemental payload must be an object")
        component_sources = [
            _canonical_component_source_v2(source, requirement)
            for source in root["supplemental_sources"]
            if source.get("payload", {}).get("schema_version")
            == MARKET_CONTEXT_SOURCE_VERSION_V2
        ]
        if component_sources != _resolve_external_revision_conflicts_v2(
            component_sources, requirement
        ):
            raise MarketContextError(
                "v2 external revision conflict projection drift"
            )
        manifests = [
            source
            for source in root["supplemental_sources"]
            if source.get("payload", {}).get("schema_version")
            == MARKET_CONTEXT_MANIFEST_VERSION_V2
        ]
        if len(manifests) != 1 or len(component_sources) + 1 != len(
            root["supplemental_sources"]
        ):
            raise MarketContextError("v2 supplemental source discriminator closure failed")
        expected_source_manifest = _source_manifest_v2(
            root["supplemental_sources"]
        )
        if root["market_source_manifest"] != expected_source_manifest:
            raise MarketContextError("v2 market source manifest drift")
        rebuilt_after = _coverage_v2(
            requirement,
            component_sources,
            {component: [] for component in MARKET_COMPONENTS},
        )
        _assert_coverage_projection_matches_v2(
            coverage_after, rebuilt_after, label="after"
        )
        new_cache_refs = {
            str(cache_ref)
            for receipt in fallback["fetch_receipts"]
            if receipt["response_status"] == "succeeded"
            for cache_ref in receipt["cache_entry_refs"]
        }
        pre_fetch_sources = [
            source
            for source in component_sources
            if source["payload"].get("cache_entry_ref") not in new_cache_refs
        ]
        rebuilt_before = _coverage_v2(
            requirement,
            pre_fetch_sources,
            {component: [] for component in MARKET_COMPONENTS},
        )
        _assert_coverage_projection_matches_v2(
            coverage_before, rebuilt_before, label="before"
        )
        expected_axis = _market_axis_v2(
            requirement, coverage_after, fallback, component_sources
        )
        if root["market_axis"] != expected_axis:
            raise MarketContextError("v2 market axis projection drift")
        expected_evidence_manifest = _source_manifest_v2(component_sources)
        if root["market_evidence_manifest"] != expected_evidence_manifest:
            raise MarketContextError("v2 market evidence manifest drift")
        expected_gaps = _market_gaps_v2(
            requirement, coverage_after, fallback, component_sources
        )
        if root["market_gaps"] != expected_gaps:
            raise MarketContextError("v2 market gap projection drift")
        expected = _assemble_resolution_v2(
            requirement=requirement,
            coverage_before=coverage_before,
            coverage_after=coverage_after,
            fallback=fallback,
            market_axis=expected_axis,
            market_gaps=expected_gaps,
            row_sources=component_sources,
            source_read=source_read,
        )
        if expected != dict(root):
            raise MarketContextError("v2 market resolution canonical rebuild drift")
    except (MarketContextError, TypeError, ValueError, KeyError) as exc:
        findings.append(
            {
                "severity": "blocker",
                "code": "MARKET_RESOLUTION_V2_INVALID",
                "message": str(exc),
            }
        )
    return {
        "schema_version": MARKET_CONTEXT_RESOLUTION_VERSION_V2,
        "validation_status": "accepted" if not findings else "blocked",
        "finding_count": len(findings),
        "findings": findings,
    }


def replay_validate_market_context_resolution_v2(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    validation = validate_market_context_resolution_v2(value)
    verified = validation["validation_status"] == "accepted"
    return {
        "schema_version": MARKET_SOURCE_REPLAY_VERSION_V2,
        "validation_status": validation["validation_status"],
        "source_verification": "verified" if verified else "blocked",
        "resolution_id": value.get("resolution_id"),
        "requirement_id": value.get("requirement_id"),
        "market_input_content_id": value.get("market_input_content_id"),
        "perspective": value.get("perspective"),
        "operation_anchor_event_id": value.get("operation_anchor_event_id"),
        "operation_anchor_at": value.get("operation_anchor_at"),
        "network_allowed": False,
        "findings": validation["findings"],
    }


def market_context_runner_projection_v2(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    resolution = (
        value.get("resolution")
        if isinstance(value.get("resolution"), Mapping)
        else value
    )
    validation = validate_market_context_resolution_v2(resolution)
    if validation["validation_status"] != "accepted":
        raise MarketContextError("cannot project an invalid v2 market resolution")
    replay = replay_validate_market_context_resolution_v2(resolution)
    return {
        "market_axis": _clone(resolution["market_axis"]),
        "market_fallback": _clone(resolution["market_fallback"]),
        "market_gaps": _clone(resolution["market_gaps"]),
        "supplemental_sources": _clone(resolution["supplemental_sources"]),
        "market_input_content_id": str(resolution["market_input_content_id"]),
        "market_requirement_id": str(resolution["requirement_id"]),
        "market_resolution_id": str(resolution["resolution_id"]),
        "perspective": str(resolution["perspective"]),
        "operation_anchor_event_id": str(resolution["operation_anchor_event_id"]),
        "operation_anchor_at": str(resolution["operation_anchor_at"]),
        "operation_anchor_ordering_key": _clone(
            resolution["operation_anchor_ordering_key"]
        ),
        "as_of": str(resolution["as_of"]),
        "knowledge_cutoff": str(resolution["knowledge_cutoff"]),
        "information_time_policy_version": str(
            resolution["information_time_policy_version"]
        ),
        "market_source_manifest": _clone(resolution["market_source_manifest"]),
        "market_evidence_manifest": _clone(
            resolution["market_evidence_manifest"]
        ),
        "source_replay": replay,
        "resolution": _clone(resolution),
    }


def load_market_context_resolution_v2(path: str | Path) -> dict[str, Any]:
    resolution = load_json_object(path)
    validation = validate_market_context_resolution_v2(resolution)
    if validation["validation_status"] != "accepted":
        raise MarketContextError("cached v2 market resolution is invalid")
    return _clone(resolution)


def validate_market_context_supplemental_sources_v2(
    values: Sequence[Mapping[str, Any]],
    *,
    expected_market_input_content_id: str | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    try:
        if not isinstance(values, (list, tuple)):
            raise MarketContextError("v2 supplemental_sources must be an array")
        if not values or any(not isinstance(source, Mapping) for source in values):
            raise MarketContextError("v2 supplemental sources must be non-empty objects")
        raw_manifests = [
            source
            for source in values
            if isinstance(source.get("payload"), Mapping)
            and source["payload"].get("schema_version")
            == MARKET_CONTEXT_MANIFEST_VERSION_V2
        ]
        if len(raw_manifests) != 1:
            raise MarketContextError("v2 supplemental set requires one manifest")
        manifest_envelope = _closed(
            raw_manifests[0],
            name="v2 market manifest envelope",
            required={
                "source_id",
                "source_kind",
                "availability",
                "effective_at",
                "knowledge_at",
                "locator",
                "warning_codes",
                "payload",
            },
        )
        manifest = _closed(
            manifest_envelope["payload"],
            name="v2 market manifest payload",
            required={
                "schema_version",
                "source_id",
                "requirement",
                "requirement_id",
                "resolution_id",
                "instrument_id",
                "perspective",
                "operation_anchor_event_id",
                "operation_anchor_at",
                "operation_anchor_ordering_key",
                "as_of",
                "knowledge_cutoff",
                "information_time_policy_version",
                "manifest_audit_at",
                "market_input_content_id",
                "market_status",
                "coverage_before",
                "coverage_after",
                "market_fallback",
                "market_axis",
                "market_gaps",
                "component_source_ids",
                "source_verification",
                "network_allowed",
            },
        )
        if (
            manifest["schema_version"] != MARKET_CONTEXT_MANIFEST_VERSION_V2
            or manifest["perspective"] not in {"user", "system"}
            or manifest["information_time_policy_version"]
            != PUBLIC_INFORMATION_POLICY_VERSION
            or manifest["source_verification"] != "verified"
            or manifest["network_allowed"] is not False
        ):
            raise MarketContextError("v2 manifest policy discriminator drift")
        requirement = canonical_market_cache_requirement_v2(
            manifest["requirement"]
        )
        if requirement != manifest["requirement"]:
            raise MarketContextError("v2 manifest requirement canonical drift")
        for field in (
            "requirement_id",
            "instrument_id",
            "perspective",
            "operation_anchor_event_id",
            "operation_anchor_at",
            "operation_anchor_ordering_key",
            "as_of",
            "knowledge_cutoff",
            "information_time_policy_version",
        ):
            if manifest[field] != requirement[field]:
                raise MarketContextError(
                    "v2 manifest requirement projection drift"
                )
        component_sources = [
            _canonical_component_source_v2(source, requirement)
            for source in values
            if source is not raw_manifests[0]
        ]
        if component_sources != _resolve_external_revision_conflicts_v2(
            component_sources, requirement
        ):
            raise MarketContextError(
                "v2 supplemental revision conflict projection drift"
            )
        expected_order = sorted(
            [*component_sources, _clone(manifest_envelope)],
            key=lambda source: (source["source_kind"], source["source_id"]),
        )
        if list(values) != expected_order:
            raise MarketContextError("v2 supplemental source ordering drift")
        coverage_before = _canonical_coverage_v2(
            manifest["coverage_before"], requirement
        )
        coverage_after = _canonical_coverage_v2(
            manifest["coverage_after"], requirement
        )
        fallback = _canonical_fallback_v2(manifest["market_fallback"])
        if (
            coverage_before != manifest["coverage_before"]
            or coverage_after != manifest["coverage_after"]
            or fallback != manifest["market_fallback"]
        ):
            raise MarketContextError(
                "v2 manifest coverage/fallback canonical drift"
            )
        rebuilt_after = _coverage_v2(
            requirement,
            component_sources,
            {component: [] for component in MARKET_COMPONENTS},
        )
        _assert_coverage_projection_matches_v2(
            coverage_after, rebuilt_after, label="supplemental after"
        )
        new_cache_refs = {
            str(cache_ref)
            for receipt in fallback["fetch_receipts"]
            if receipt["response_status"] == "succeeded"
            for cache_ref in receipt["cache_entry_refs"]
        }
        rebuilt_before = _coverage_v2(
            requirement,
            [
                source
                for source in component_sources
                if source["payload"].get("cache_entry_ref") not in new_cache_refs
            ],
            {component: [] for component in MARKET_COMPONENTS},
        )
        _assert_coverage_projection_matches_v2(
            coverage_before, rebuilt_before, label="supplemental before"
        )
        expected_axis = _market_axis_v2(
            requirement, coverage_after, fallback, component_sources
        )
        if manifest["market_axis"] != expected_axis:
            raise MarketContextError("v2 manifest market axis drift")
        expected_gaps = _market_gaps_v2(
            requirement, coverage_after, fallback, component_sources
        )
        if manifest["market_gaps"] != expected_gaps:
            raise MarketContextError("v2 manifest market gaps drift")
        expected_input = _content_id(
            _market_input_projection_v2(
                requirement=requirement,
                resolution_id=str(manifest["resolution_id"]),
                coverage_after=coverage_after,
                market_axis=expected_axis,
                market_fallback=fallback,
                market_gaps=expected_gaps,
                component_sources=component_sources,
            )
        )
        if manifest["market_input_content_id"] != expected_input:
            raise MarketContextError("v2 manifest market input hash drift")
        if (
            expected_market_input_content_id is not None
            and expected_input != expected_market_input_content_id
        ):
            raise MarketContextError("v2 supplemental expected market hash drift")
        manifest_source_id = "market_manifest_v2_" + expected_input.split(":", 1)[1]
        if (
            manifest["source_id"] != manifest_source_id
            or manifest_envelope["source_id"] != manifest_source_id
            or manifest["component_source_ids"]
            != sorted(str(source["source_id"]) for source in component_sources)
            or manifest["market_status"] != expected_axis["status"]
        ):
            raise MarketContextError("v2 manifest source identity/closure drift")
        expected_audit = _manifest_audit_at_v2(
            requirement, fallback, expected_axis
        )
        expected_availability = {
            "available": "available",
            "stale": "stale",
            "partial": "ambiguous",
            "insufficient": "ambiguous",
            "missing": "missing",
            "failed": "missing",
        }[str(expected_axis["status"])]
        if (
            manifest["manifest_audit_at"] != expected_audit
            or manifest_envelope["source_kind"] != "market_context"
            or manifest_envelope["availability"] != expected_availability
            or manifest_envelope["effective_at"] != requirement["as_of"]
            or manifest_envelope["knowledge_at"] != expected_audit
            or manifest_envelope["locator"]
            != f"market_resolution_v2:{manifest['resolution_id']}"
            or manifest_envelope["warning_codes"]
            != sorted(str(gap["code"]) for gap in expected_gaps)
        ):
            raise MarketContextError("v2 manifest envelope drift")
    except (MarketContextError, TypeError, ValueError, KeyError, AttributeError) as exc:
        findings.append(
            {
                "severity": "blocker",
                "code": "MARKET_SUPPLEMENTAL_V2_INVALID",
                "message": str(exc),
            }
        )
    return {
        "schema_version": MARKET_CONTEXT_MANIFEST_VERSION_V2,
        "validation_status": "accepted" if not findings else "blocked",
        "finding_count": len(findings),
        "findings": findings,
    }


def market_context_resolution_path_v2(
    cache_root: str | Path, requirement_id: str
) -> Path:
    return (
        Path(cache_root).resolve(strict=False)
        / "v2"
        / "r"
        / _short_cache_name(requirement_id)
    )


def _market_context_repair_path_v2(
    cache_root: str | Path, requirement_id: str
) -> Path:
    repair_identity = (
        requirement_id + ":" + MARKET_CONTEXT_CACHE_REPAIR_VERSION_V2
    )
    return (
        Path(cache_root).resolve(strict=False)
        / "v2"
        / "r_repair"
        / _short_cache_name(repair_identity)
    )


def _is_legacy_current_industry_contextual_cache_v2(
    value: Mapping[str, Any],
    requirement: Mapping[str, Any],
) -> bool:
    """Recognize only the closed cache defect fixed by v7.

    The legacy projection promoted a current-only industry's effective time to
    the later review ``as_of`` while retaining its earlier observation time.
    Arbitrary invalid or identity-drifted cache content remains fail closed.
    """

    try:
        if value.get("requirement") != requirement:
            return False
        sources = value.get("supplemental_sources")
        if not isinstance(sources, list):
            return False
        validation = validate_market_context_resolution_v2(value)
        finding_messages = {
            str(finding.get("message") or "")
            for finding in validation.get("findings", [])
            if isinstance(finding, Mapping)
        }
        if (
            validation.get("validation_status") != "blocked"
            or finding_messages != {"v2 local source canonical proof drift"}
        ):
            return False
        legacy_sources = [
            source
            for source in sources
            if isinstance(source, Mapping)
            and isinstance(source.get("payload"), Mapping)
            and source["payload"].get("component") == "current_industry"
        ]
        for source in legacy_sources:
            payload = source["payload"]
            eligibility = payload.get("perspective_eligibility")
            fetched_at = payload.get("fetched_at")
            observed_at = payload.get("system_observed_at")
            effective_at = payload.get("effective_at")
            if (
                isinstance(eligibility, Mapping)
                and payload.get("point_in_time") is False
                and eligibility.get("status") == "unknown"
                and eligibility.get("reason_code")
                == "current_only_not_point_in_time"
                and effective_at == requirement.get("as_of")
                and payload.get("coverage_effective_at") == fetched_at
                and fetched_at == observed_at
                and parse_datetime(str(fetched_at), "UTC")
                < parse_datetime(str(effective_at), "UTC")
            ):
                return True
        return False
    except (KeyError, TypeError, ValueError):
        return False


def _resolve_market_context_for_requirement_v2(
    *,
    source_path: Path,
    root: Path,
    requirement: Mapping[str, Any],
    provider_gateway: Any | None,
    clock: Callable[[], datetime] | None,
    run_budget: MarketRequestBudget,
    persist: bool,
) -> dict[str, Any]:
    resolution_path = market_context_resolution_path_v2(
        root, str(requirement["requirement_id"])
    )
    repair_path = _market_context_repair_path_v2(
        root, str(requirement["requirement_id"])
    )
    if repair_path.exists():
        resolution = load_market_context_resolution_v2(repair_path)
        if resolution["requirement"] != requirement:
            raise MarketContextError(
                "repaired v2 market requirement identity drift"
            )
        return market_context_runner_projection_v2(resolution)
    if resolution_path.exists():
        raw_resolution = load_json_object(resolution_path)
        try:
            resolution = load_market_context_resolution_v2(resolution_path)
        except MarketContextError:
            if not _is_legacy_current_industry_contextual_cache_v2(
                raw_resolution, requirement
            ):
                raise
            resolution_path = repair_path
        else:
            if resolution["requirement"] != requirement:
                raise MarketContextError(
                    "cached v2 market requirement identity drift"
                )
            return market_context_runner_projection_v2(resolution)
    if persist:
        _create_or_compare(
            root / "v2" / "q" / _short_cache_name(str(requirement["requirement_id"])),
            requirement,
        )
    before = _source_snapshot(source_path)
    uri = source_path.as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        if int(connection.execute("PRAGMA query_only").fetchone()[0]) != 1:
            raise MarketContextError("SQLite query_only could not be enabled")
        quick = [str(row[0]) for row in connection.execute("PRAGMA quick_check")]
        if quick != ["ok"]:
            raise MarketContextError("portfolio market source quick_check failed")
        local_sources, schema_gaps = _local_sources_v2(connection, requirement)
    finally:
        connection.close()
    after = _source_snapshot(source_path)
    if not _same_source_snapshot(before, after):
        raise MarketContextError("portfolio market source changed during immutable read")
    cached_sources = _cached_external_sources_v2(root, requirement)
    initial_sources = sorted(
        {
            str(source["source_id"]): source
            for source in [*local_sources, *cached_sources]
        }.values(),
        key=lambda source: (source["source_kind"], source["source_id"]),
    )
    initial_sources = _resolve_external_revision_conflicts_v2(
        initial_sources, requirement
    )
    source_read = {
        "mode": "ro",
        "immutable": True,
        "query_only": True,
        "quick_check": "ok",
        "source_sha256": before["main"]["sha256"],
        "source_size": before["main"]["size"],
        "auxiliary_state": {"wal": before["wal"], "shm": before["shm"]},
    }
    coverage_before = _coverage_v2(requirement, initial_sources, schema_gaps)
    if coverage_before["status"] == "satisfied":
        fallback = _not_needed_fallback_v2(
            requirement, coverage_before, initial_sources
        )
        resolved_sources = initial_sources
        coverage_after = _clone(coverage_before)
    else:
        fallback, resolved_sources, coverage_after = _controlled_gateway_fallback_v2(
            requirement,
            coverage=coverage_before,
            sources=initial_sources,
            schema_gaps=schema_gaps,
            gateway=provider_gateway,
            cache_root=root,
            persist=persist,
            clock=clock,
            request_budget=run_budget,
        )
    axis = _market_axis_v2(
        requirement, coverage_after, fallback, resolved_sources
    )
    gaps = _market_gaps_v2(
        requirement, coverage_after, fallback, resolved_sources
    )
    resolution = _assemble_resolution_v2(
        requirement=requirement,
        coverage_before=coverage_before,
        coverage_after=coverage_after,
        fallback=fallback,
        market_axis=axis,
        market_gaps=gaps,
        row_sources=resolved_sources,
        source_read=source_read,
    )
    validation = validate_market_context_resolution_v2(resolution)
    if validation["validation_status"] != "accepted":
        raise MarketContextError(
            "v2 market context resolution failed validation: "
            + "; ".join(
                str(item.get("message") or "")
                for item in validation["findings"]
            )
        )
    if persist:
        _create_or_compare(resolution_path, resolution)
    return market_context_runner_projection_v2(resolution)


def resolve_market_context_v2(
    *,
    portfolio_db: str | Path,
    review_db: str | Path,
    instrument_id: str,
    perspective: str,
    operation_anchor_event_id: str,
    operation_anchor_at: str,
    operation_anchor_ordering_key: Sequence[Any],
    as_of: str,
    knowledge_cutoff: str,
    cache_root: str | Path,
    information_time_policy_version: str = PUBLIC_INFORMATION_POLICY_VERSION,
    required_components: Sequence[str] = DEFAULT_REQUIRED_COMPONENTS,
    optional_components: Sequence[str] = DEFAULT_OPTIONAL_COMPONENTS,
    provider_gateway: Any | None = None,
    clock: Callable[[], datetime] | None = None,
    request_budget: MarketRequestBudget | None = None,
    persist: bool = True,
    asset_type_hint: str = "unknown",
    staleness_seconds: Mapping[str, int] | None = None,
    provider_requests: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Freeze a perspective-aware market projection in the pre-bundle step."""

    source_path = Path(portfolio_db).resolve(strict=False)
    sidecar_path = Path(review_db).resolve(strict=False)
    root = Path(cache_root).resolve(strict=False)
    _require_cache_authority(
        portfolio_db=source_path, review_db=sidecar_path, cache_root=root
    )
    requirement = build_market_cache_requirement_v2(
        instrument_id=instrument_id,
        perspective=perspective,
        operation_anchor_event_id=operation_anchor_event_id,
        operation_anchor_at=operation_anchor_at,
        operation_anchor_ordering_key=operation_anchor_ordering_key,
        as_of=as_of,
        knowledge_cutoff=knowledge_cutoff,
        information_time_policy_version=information_time_policy_version,
        required_components=required_components,
        optional_components=optional_components,
        asset_type_hint=asset_type_hint,
        staleness_seconds=staleness_seconds,
        provider_requests=provider_requests,
    )
    arguments = {
        "source_path": source_path,
        "root": root,
        "requirement": requirement,
        "provider_gateway": provider_gateway,
        "clock": clock,
        "run_budget": request_budget or MarketRequestBudget(),
        "persist": persist,
    }
    if not persist:
        return _resolve_market_context_for_requirement_v2(**arguments)
    with _MarketRequirementLease(root / "v2", str(requirement["requirement_id"])):
        return _resolve_market_context_for_requirement_v2(**arguments)


def market_context_limitation_projection_v2(
    *,
    episode: Mapping[str, Any],
    operation_review: Mapping[str, Any],
    perspective: str,
    as_of: str,
    knowledge_cutoff: str,
    limitation_code: str,
    guard_audit_at: str,
    instrument_id: str | None = None,
) -> dict[str, Any]:
    """Pure zero-network projection for an already-classified legal limitation."""

    if limitation_code not in {
        "provider_unavailable",
        "withheld_by_cutoff",
        "budget_exhausted",
    }:
        raise MarketContextError("unsupported canonical market limitation")
    anchor = derive_operation_anchor(episode, operation_review, as_of=as_of)
    scope = episode.get("scope") if isinstance(episode.get("scope"), Mapping) else {}
    resolved_instrument = str(
        instrument_id
        or scope.get("instrument_id")
        or episode.get("instrument_id")
        or episode.get("symbol")
        or ""
    )
    requirement = build_market_cache_requirement_v2(
        instrument_id=resolved_instrument,
        perspective=perspective,
        as_of=as_of,
        knowledge_cutoff=knowledge_cutoff,
        **anchor,
    )
    schema_gaps = {component: ["SOURCE_READ_NOT_RUN"] for component in MARKET_COMPONENTS}
    coverage = _coverage_v2(requirement, [], schema_gaps)
    fallback = _limitation_fallback_v2(
        requirement,
        coverage=coverage,
        sources=[],
        status=limitation_code,
        guard_audit_at=_timestamp(guard_audit_at, "guard_audit_at"),
    )
    axis = _market_axis_v2(requirement, coverage, fallback, [])
    gaps = _market_gaps_v2(requirement, coverage, fallback, [])
    resolution = _assemble_resolution_v2(
        requirement=requirement,
        coverage_before=coverage,
        coverage_after=coverage,
        fallback=fallback,
        market_axis=axis,
        market_gaps=gaps,
        row_sources=[],
        source_read={
            "mode": "not_read",
            "immutable": True,
            "query_only": True,
            "quick_check": "not_run",
            "source_sha256": None,
            "source_size": None,
            "auxiliary_state": None,
        },
    )
    validation = validate_market_context_resolution_v2(resolution)
    if validation["validation_status"] != "accepted":
        raise MarketContextError("canonical v2 market limitation failed validation")
    return market_context_runner_projection_v2(resolution)


class MarketContextAdapter:
    """Callable runner resolver backed by one explicit create-only cache root."""

    def __init__(
        self,
        *,
        cache_root: str | Path,
        provider_gateway: Any | None = None,
        clock: Callable[[], datetime] | None = None,
        persist: bool = True,
    ) -> None:
        self.cache_root = Path(cache_root).resolve(strict=False)
        self.provider_gateway = provider_gateway
        self.clock = clock
        self.persist = persist

    def __call__(
        self,
        *,
        portfolio_db: str | Path,
        review_db: str | Path,
        episode: Mapping[str, Any],
        operation_review: Mapping[str, Any],
        knowledge_provenance: Mapping[str, Any],
        ledger_snapshot_reconstruction: Mapping[str, Any],
        perspective: str,
        as_of: str,
        knowledge_cutoff: str,
        request_budget: MarketRequestBudget | None = None,
        market_contract_version: str = "v1",
    ) -> dict[str, Any]:
        del knowledge_provenance, ledger_snapshot_reconstruction
        scope = episode.get("scope") if isinstance(episode.get("scope"), Mapping) else {}
        instrument_id = str(
            scope.get("instrument_id")
            or episode.get("instrument_id")
            or episode.get("symbol")
            or ""
        )
        if not instrument_id:
            raise MarketContextError("episode instrument_id is required")
        contract_version = str(market_contract_version or "").strip().lower()
        if contract_version == "v2":
            anchor = derive_operation_anchor(
                episode, operation_review, as_of=as_of
            )
            return resolve_market_context_v2(
                portfolio_db=portfolio_db,
                review_db=review_db,
                instrument_id=instrument_id,
                perspective=perspective,
                as_of=as_of,
                knowledge_cutoff=knowledge_cutoff,
                cache_root=self.cache_root,
                provider_gateway=self.provider_gateway,
                clock=self.clock,
                request_budget=request_budget,
                persist=self.persist,
                **anchor,
            )
        if contract_version != "v1":
            raise MarketContextError("market_contract_version must be v1 or v2")
        return resolve_market_context(
            portfolio_db=portfolio_db,
            review_db=review_db,
            instrument_id=instrument_id,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
            cache_root=self.cache_root,
            provider_gateway=self.provider_gateway,
            clock=self.clock,
            request_budget=request_budget,
            persist=self.persist,
        )
