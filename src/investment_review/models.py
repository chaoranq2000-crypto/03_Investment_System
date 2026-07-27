"""Canonical objects used by the Phase 1 review data layer."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .artifact_io import canonical_json_bytes
from .time_utils import ensure_known_not_before_occurred, utc_iso


class ModelValidationError(ValueError):
    """Raised when canonical data violates the review contract."""


OPERATION_CHECKPOINT_SCHEMA_VERSION = "investment_review.operation_checkpoint.v1"
OPERATION_CHECKPOINT_SCHEMA_VERSION_V1 = OPERATION_CHECKPOINT_SCHEMA_VERSION
OPERATION_CHECKPOINT_SCHEMA_VERSION_V2 = "investment_review.operation_checkpoint.v2"
MARKET_FALLBACK_POLICY_VERSION = "local_first_controlled_fallback_v1"
MARKET_FALLBACK_POLICY_VERSION_V1 = MARKET_FALLBACK_POLICY_VERSION
MARKET_FALLBACK_POLICY_VERSION_V2 = "local_first_controlled_fallback_v2"
PUBLIC_INFORMATION_POLICY_VERSION = "public_availability_user_knowledge_v1"
MARKET_PROVIDER_ALLOWLIST_VERSION = "market_provider_allowlist.v1"
MARKET_REQUEST_FINGERPRINT_VERSION = "market_request_fingerprint.v1"
MARKET_PROVIDER_ALLOWLIST = frozenset(
    {
        "baostock:history_k_data_plus_5m",
        "tushare:adj_factor",
        "tushare:cb_daily",
        "tushare:daily",
        "tushare:etf_basic",
        "tushare:etf_mins",
        "tushare:fund_adj",
        "tushare:fund_daily",
        "tushare:stk_mins",
        "tushare:stock_basic",
    }
)
MARKET_PROVIDER_PARAMETER_ALLOWLIST = {
    "baostock:history_k_data_plus_5m": frozenset(
        {"code", "fields", "start_date", "end_date", "frequency", "adjustflag"}
    ),
    "tushare:adj_factor": frozenset(
        {"ts_code", "trade_date", "start_date", "end_date", "fields"}
    ),
    "tushare:cb_daily": frozenset(
        {"ts_code", "trade_date", "start_date", "end_date", "fields"}
    ),
    "tushare:daily": frozenset(
        {"ts_code", "trade_date", "start_date", "end_date", "fields"}
    ),
    "tushare:etf_basic": frozenset({"ts_code", "fields"}),
    "tushare:etf_mins": frozenset(
        {"ts_code", "freq", "start_date", "end_date", "fields"}
    ),
    "tushare:fund_adj": frozenset(
        {"ts_code", "trade_date", "start_date", "end_date", "fields"}
    ),
    "tushare:fund_daily": frozenset(
        {"ts_code", "trade_date", "start_date", "end_date", "fields"}
    ),
    "tushare:stk_mins": frozenset(
        {"ts_code", "freq", "start_date", "end_date", "fields"}
    ),
    "tushare:stock_basic": frozenset({"exchange", "list_status", "fields"}),
}
MARKET_PROVIDER_PARAMETER_VALUE_PATTERNS = {
    "adjustflag": r"3",
    "code": r"(?:sh|sz|bj)\.[0-9]{6}",
    "end_date": (
        r"(?:[0-9]{8}|[0-9]{4}-[0-9]{2}-[0-9]{2}"
        r"(?: [0-9]{2}:[0-9]{2}:[0-9]{2})?)"
    ),
    "exchange": r"(?:SSE|SZSE|BSE)?",
    "fields": r"[A-Za-z_][A-Za-z0-9_]*(?:,[A-Za-z_][A-Za-z0-9_]*)*",
    "freq": r"1min",
    "frequency": r"5",
    "list_status": r"[LDP]",
    "start_date": (
        r"(?:[0-9]{8}|[0-9]{4}-[0-9]{2}-[0-9]{2}"
        r"(?: [0-9]{2}:[0-9]{2}:[0-9]{2})?)"
    ),
    "trade_date": r"(?:[0-9]{8}|[0-9]{4}-[0-9]{2}-[0-9]{2})",
    "ts_code": r"[0-9]{6}\.(?:SH|SZ|BJ)",
}
MARKET_PROVIDER_PARAMETER_ALLOW_EMPTY = frozenset({"exchange"})
MARKET_PROVIDER_PARAMETER_MAX_LENGTH = 512
MARKET_PROVIDER_SENSITIVE_PARAMETER_PATTERN = (
    r"(?:token|secret|password|api[_ -]?key|credential|authorization|"
    r"auth|headers?|cookies?|session|bearer|proxy|access[_ -]?key|"
    r"private[_ -]?key|signature)"
)
_MARKET_PROVIDER_ALLOWLIST_MANIFEST = {
    "version": MARKET_PROVIDER_ALLOWLIST_VERSION,
    "endpoints": sorted(MARKET_PROVIDER_ALLOWLIST),
    "parameter_keys": {
        endpoint: sorted(keys)
        for endpoint, keys in sorted(MARKET_PROVIDER_PARAMETER_ALLOWLIST.items())
    },
    "parameter_value_patterns": dict(
        sorted(MARKET_PROVIDER_PARAMETER_VALUE_PATTERNS.items())
    ),
    "parameter_allow_empty": sorted(MARKET_PROVIDER_PARAMETER_ALLOW_EMPTY),
    "parameter_max_length": MARKET_PROVIDER_PARAMETER_MAX_LENGTH,
    "sensitive_parameter_pattern": MARKET_PROVIDER_SENSITIVE_PARAMETER_PATTERN,
}
_COMPUTED_MARKET_PROVIDER_ALLOWLIST_SHA256 = "sha256:" + hashlib.sha256(
    canonical_json_bytes(_MARKET_PROVIDER_ALLOWLIST_MANIFEST)
).hexdigest()
MARKET_PROVIDER_ALLOWLIST_SHA256 = (
    "sha256:1e612c7bf6090fcbfd32aaaef9ca7c73db8441ba939726b9d610238b29b3790a"
)
if _COMPUTED_MARKET_PROVIDER_ALLOWLIST_SHA256 != MARKET_PROVIDER_ALLOWLIST_SHA256:
    raise RuntimeError(
        "market_provider_allowlist.v1 changed without a version/hash update"
    )
REVIEWABILITY_STATUS_AXES = (
    "operation",
    "decision",
    "snapshot_cash_valuation",
    "market",
    "lifecycle",
    "outcome",
)
REVIEWABILITY_SNAPSHOT_FIELDS = (
    "position_quantity",
    "cost_basis",
    "cash",
    "price",
    "nav",
    "weight",
    "industry",
)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def market_request_fingerprint(
    *,
    provider_id: str,
    endpoint_id: str,
    provider_version: str,
    redacted_parameters: Mapping[str, str],
) -> str:
    """Derive the v1 request identity from the exact safe request projection."""

    material = {
        "schema_version": MARKET_REQUEST_FINGERPRINT_VERSION,
        "provider_id": provider_id,
        "endpoint_id": endpoint_id,
        "provider_version": provider_version,
        "redacted_parameters": dict(sorted(redacted_parameters.items())),
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_decimal(value: object, *, field_name: str = "number") -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = (
        text.strip("()")
        .replace(",", "")
        .replace("，", "")
        .replace("￥", "")
        .replace("¥", "")
        .replace("元", "")
        .strip()
    )
    try:
        number = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ModelValidationError(f"Invalid {field_name}: {value!r}") from exc
    if not number.is_finite():
        raise ModelValidationError(f"Non-finite {field_name}: {value!r}")
    return -number if negative else number


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    kind: str
    uri: str
    timezone: str = "Asia/Shanghai"
    read_only: bool = True
    identity_key: str | None = None
    config: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.name.strip():
            raise ModelValidationError("Source name is required")
        if not self.kind.strip():
            raise ModelValidationError("Source kind is required")
        if not self.uri.strip():
            raise ModelValidationError("Source URI is required")
        if self.identity_key is not None and not self.identity_key.strip():
            raise ModelValidationError("Source identity_key cannot be blank")

    @property
    def source_id(self) -> str:
        self.validate()
        # Keep the legacy material shape for backward compatibility. An explicit
        # identity_key replaces only the location component so copied/renamed
        # exports remain the same logical source.
        identity = canonical_json(
            {
                "kind": self.kind.strip(),
                "name": self.name.strip(),
                "uri": (self.identity_key or self.uri).strip(),
            }
        )
        return f"src_{sha256_text(identity)[:24]}"

    @property
    def fingerprint(self) -> str:
        material = canonical_json(
            {
                "name": self.name,
                "kind": self.kind,
                "uri": self.uri,
                "timezone": self.timezone,
                "read_only": self.read_only,
                "identity_key": self.identity_key,
                "config": dict(self.config),
            }
        )
        return sha256_text(material)


@dataclass(frozen=True)
class CanonicalTradeEvent:
    source_id: str
    event_type: str
    occurred_at: str
    known_at: str
    symbol: str
    source_record_id: str | None = None
    account: str | None = None
    market: str | None = None
    side: str | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    gross_amount: Decimal | None = None
    cash_amount: Decimal | None = None
    fees: Decimal | None = None
    currency: str = "CNY"
    raw_payload: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.source_id.strip():
            raise ModelValidationError("source_id is required")
        if not self.event_type.strip():
            raise ModelValidationError("event_type is required")
        if not self.symbol.strip():
            raise ModelValidationError("symbol is required")
        if not self.side:
            raise ModelValidationError("side is required")
        if self.quantity is None:
            raise ModelValidationError("quantity is required")
        if self.price is None:
            raise ModelValidationError("price is required")
        if self.quantity < 0:
            raise ModelValidationError("quantity must be non-negative; use side for direction")
        if self.price < 0:
            raise ModelValidationError("price must be non-negative")
        if self.fees is not None and self.fees < 0:
            raise ModelValidationError("fees must be non-negative")
        if self.side and self.side not in {"BUY", "SELL", "TRANSFER_IN", "TRANSFER_OUT", "OTHER"}:
            raise ModelValidationError(f"Unsupported side: {self.side!r}")
        ensure_known_not_before_occurred(self.occurred_at, self.known_at)

    @property
    def payload_sha256(self) -> str:
        # Import metadata such as row order may change while the source record
        # itself stays identical. Drift detection therefore hashes the raw
        # source row when available, not incidental ingest metadata.
        payload = dict(self.raw_payload)
        stable_payload = payload.get("source_row", payload)
        return sha256_text(canonical_json(stable_payload))

    def identity_payload(self) -> dict[str, Any]:
        if self.source_record_id:
            return {
                "source_id": self.source_id,
                "source_record_id": self.source_record_id,
            }
        return {
            "source_id": self.source_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "known_at": self.known_at,
            "symbol": self.symbol,
            "account": self.account,
            "market": self.market,
            "side": self.side,
            "quantity": str(self.quantity) if self.quantity is not None else None,
            "price": str(self.price) if self.price is not None else None,
            "gross_amount": str(self.gross_amount) if self.gross_amount is not None else None,
            "cash_amount": str(self.cash_amount) if self.cash_amount is not None else None,
            "fees": str(self.fees) if self.fees is not None else None,
            "currency": self.currency,
            "payload_sha256": self.payload_sha256,
        }

    @property
    def event_id(self) -> str:
        self.validate()
        return f"evt_{sha256_text(canonical_json(self.identity_payload()))[:32]}"

    @classmethod
    def build(
        cls,
        *,
        source_id: str,
        event_type: object,
        occurred_at: object,
        known_at: object | None,
        symbol: object,
        timezone: str,
        source_record_id: object | None = None,
        account: object | None = None,
        market: object | None = None,
        side: object | None = None,
        quantity: object | None = None,
        price: object | None = None,
        gross_amount: object | None = None,
        cash_amount: object | None = None,
        fees: object | None = None,
        currency: object | None = "CNY",
        raw_payload: Mapping[str, Any] | None = None,
    ) -> "CanonicalTradeEvent":
        occurred = utc_iso(occurred_at, timezone)
        known = utc_iso(known_at if known_at not in (None, "") else occurred_at, timezone)
        event = cls(
            source_id=source_id.strip(),
            source_record_id=str(source_record_id).strip() if source_record_id not in (None, "") else None,
            event_type=str(event_type or "fill").strip().lower(),
            occurred_at=occurred,
            known_at=known,
            symbol=str(symbol).strip().upper(),
            account=str(account).strip() if account not in (None, "") else None,
            market=str(market).strip().upper() if market not in (None, "") else None,
            side=str(side).strip().upper() if side not in (None, "") else None,
            quantity=parse_decimal(quantity, field_name="quantity"),
            price=parse_decimal(price, field_name="price"),
            gross_amount=parse_decimal(gross_amount, field_name="gross_amount"),
            cash_amount=parse_decimal(cash_amount, field_name="cash_amount"),
            fees=parse_decimal(fees, field_name="fees"),
            currency=str(currency or "CNY").strip().upper(),
            raw_payload=dict(raw_payload or {}),
        )
        event.validate()
        return event


@dataclass(frozen=True)
class DecisionRecord:
    symbol: str
    occurred_at: str
    known_at: str
    thesis: str
    market: str | None = None
    status: str = "OPEN"
    trigger_text: str | None = None
    invalidation_text: str | None = None
    expected_horizon: str | None = None
    portfolio_role: str | None = None
    direct_reason: str | None = None
    risk_notes: str | None = None
    raw_note: str | None = None
    decision_id: str = field(default_factory=lambda: f"dec_{uuid.uuid4().hex}")

    def validate(self) -> None:
        if not self.symbol.strip():
            raise ModelValidationError("Decision symbol is required")
        if not self.thesis.strip():
            raise ModelValidationError("Decision thesis is required")
        if self.status not in {"OPEN", "CLOSED", "INVALIDATED", "WATCHING"}:
            raise ModelValidationError(f"Unsupported decision status: {self.status!r}")
        ensure_known_not_before_occurred(self.occurred_at, self.known_at)

    @classmethod
    def build(
        cls,
        *,
        symbol: object,
        occurred_at: object,
        known_at: object | None,
        thesis: object,
        timezone: str = "Asia/Shanghai",
        **kwargs: Any,
    ) -> "DecisionRecord":
        if known_at in (None, ""):
            raise ModelValidationError(
                "Decision known_at is required; historical notes must not be backdated implicitly"
            )
        decision = cls(
            symbol=str(symbol).strip().upper(),
            occurred_at=utc_iso(occurred_at, timezone),
            known_at=utc_iso(known_at, timezone),
            thesis=str(thesis).strip(),
            market=str(kwargs["market"]).strip().upper() if kwargs.get("market") else None,
            status=str(kwargs.get("status", "OPEN")).strip().upper(),
            trigger_text=kwargs.get("trigger_text"),
            invalidation_text=kwargs.get("invalidation_text"),
            expected_horizon=kwargs.get("expected_horizon"),
            portfolio_role=kwargs.get("portfolio_role"),
            direct_reason=kwargs.get("direct_reason"),
            risk_notes=kwargs.get("risk_notes"),
            raw_note=kwargs.get("raw_note"),
        )
        decision.validate()
        return decision


FEE_STATUSES = frozenset({"actual", "estimated", "unknown"})
FEE_ESTIMATION_METHOD = "historical_median_rate"
FEE_ESTIMATION_METHOD_VERSION = "historical_median_rate_v1"
SOURCE_ACTUAL_FEE_METHOD = "source_fee"
SOURCE_ACTUAL_FEE_METHOD_VERSION = "source_fee_actual_v1"
REVIEW_RUN_SCOPES = frozenset({"sync", "catch_up", "single", "weekly", "monthly"})
REVIEW_RUN_STATUSES = frozenset(
    {"queued", "running", "succeeded", "partial", "blocked", "failed"}
)


def _required_text(value: object, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ModelValidationError(f"{field_name} is required")
    return text


def _mapping(value: object, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ModelValidationError(f"{field_name} must be an object")
    return dict(value)


@dataclass(frozen=True)
class FeeProfileRecord:
    """Immutable metadata for one reproducible fee-estimation sample set."""

    profile_id: str
    profile_key: str
    method: str
    method_version: str
    sample_count: int
    computed_at: str
    rate: Decimal | None = None
    currency: str = "CNY"
    fallback_level: str = "none"
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        _required_text(self.profile_id, "profile_id")
        _required_text(self.profile_key, "profile_key")
        _required_text(self.method, "method")
        _required_text(self.method_version, "method_version")
        _required_text(self.computed_at, "computed_at")
        _required_text(self.currency, "currency")
        _required_text(self.fallback_level, "fallback_level")
        if self.sample_count < 0:
            raise ModelValidationError("sample_count must be non-negative")
        if self.rate is not None and self.rate < 0:
            raise ModelValidationError("rate must be non-negative")
        if (self.method, self.method_version) != (
            FEE_ESTIMATION_METHOD,
            FEE_ESTIMATION_METHOD_VERSION,
        ):
            raise ModelValidationError(
                "fee profile must use historical_median_rate_v1"
            )
        if self.sample_count < 5:
            raise ModelValidationError(
                "historical_median_rate_v1 requires at least 5 samples"
            )
        if self.rate is None or self.rate <= 0:
            raise ModelValidationError(
                "historical_median_rate_v1 requires a positive rate"
            )
        utc_iso(self.computed_at, "UTC")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "profile_id": self.profile_id,
            "profile_key": self.profile_key,
            "method": self.method,
            "method_version": self.method_version,
            "sample_count": self.sample_count,
            "computed_at": utc_iso(self.computed_at, "UTC"),
            "rate": str(self.rate) if self.rate is not None else None,
            "currency": self.currency.strip().upper(),
            "fallback_level": self.fallback_level,
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FeeProfileRecord":
        try:
            sample_count = int(value.get("sample_count", 0))
        except (TypeError, ValueError) as exc:
            raise ModelValidationError("sample_count must be an integer") from exc
        record = cls(
            profile_id=_required_text(value.get("profile_id"), "profile_id"),
            profile_key=_required_text(value.get("profile_key"), "profile_key"),
            method=_required_text(value.get("method"), "method"),
            method_version=_required_text(
                value.get("method_version", value.get("version")), "method_version"
            ),
            sample_count=sample_count,
            computed_at=utc_iso(value.get("computed_at"), "UTC"),
            rate=parse_decimal(value.get("rate"), field_name="rate"),
            currency=_required_text(value.get("currency", "CNY"), "currency").upper(),
            fallback_level=_required_text(
                value.get("fallback_level", "none"), "fallback_level"
            ),
            provenance=_mapping(value.get("provenance"), "provenance"),
        )
        record.validate()
        return record


@dataclass(frozen=True)
class FeeProjectionRecord:
    """Immutable fee state for one canonical trade event at one projection time."""

    projection_id: str
    event_id: str
    status: str
    amount: Decimal | None
    currency: str
    projected_at: str
    source_fees: Decimal | None = None
    method: str | None = None
    method_version: str | None = None
    sample_count: int = 0
    profile_id: str | None = None
    reason_code: str | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        _required_text(self.projection_id, "projection_id")
        _required_text(self.event_id, "event_id")
        if self.status not in FEE_STATUSES:
            raise ModelValidationError(f"Unsupported fee status: {self.status!r}")
        _required_text(self.currency, "currency")
        utc_iso(self.projected_at, "UTC")
        if self.amount is not None and self.amount < 0:
            raise ModelValidationError("fee amount must be non-negative")
        if self.source_fees is not None and self.source_fees < 0:
            raise ModelValidationError("source_fees must be non-negative")
        if self.sample_count < 0:
            raise ModelValidationError("sample_count must be non-negative")
        if self.status == "actual":
            if self.amount is None or self.amount <= 0:
                raise ModelValidationError("actual fee requires a positive amount")
            if self.source_fees is None or self.source_fees <= 0:
                raise ModelValidationError(
                    "actual fee requires a positive, explicitly confirmed source_fees value"
                )
            if self.amount != self.source_fees:
                raise ModelValidationError("actual fee amount must equal source_fees")
            if dict(self.provenance).get("source_fee_actual") is not True:
                raise ModelValidationError(
                    "actual fee requires provenance.source_fee_actual=true"
                )
            if (self.method, self.method_version) != (
                SOURCE_ACTUAL_FEE_METHOD,
                SOURCE_ACTUAL_FEE_METHOD_VERSION,
            ):
                raise ModelValidationError(
                    "actual fee must use source_fee_actual_v1"
                )
            if self.sample_count != 0 or self.profile_id is not None:
                raise ModelValidationError(
                    "actual fee must not reference estimation samples or a profile"
                )
        elif self.status == "estimated":
            if self.amount is None:
                raise ModelValidationError("estimated fee requires amount")
            if self.sample_count < 5:
                raise ModelValidationError("estimated fee requires at least 5 samples")
            if (self.method, self.method_version) != (
                FEE_ESTIMATION_METHOD,
                FEE_ESTIMATION_METHOD_VERSION,
            ):
                raise ModelValidationError(
                    "estimated fee must use historical_median_rate_v1"
                )
            _required_text(self.profile_id, "profile_id")
        elif self.amount is not None:
            raise ModelValidationError("unknown fee must preserve amount as missing")
        if self.status == "unknown":
            _required_text(self.reason_code, "reason_code")
            if self.profile_id is not None:
                raise ModelValidationError("unknown fee must not reference a fee profile")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "projection_id": self.projection_id,
            "event_id": self.event_id,
            "status": self.status,
            "amount": str(self.amount) if self.amount is not None else None,
            "currency": self.currency.strip().upper(),
            "source_fees": str(self.source_fees) if self.source_fees is not None else None,
            "method": self.method,
            "method_version": self.method_version,
            "sample_count": self.sample_count,
            "profile_id": self.profile_id,
            "reason_code": self.reason_code,
            "projected_at": utc_iso(self.projected_at, "UTC"),
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FeeProjectionRecord":
        try:
            sample_count = int(value.get("sample_count", 0))
        except (TypeError, ValueError) as exc:
            raise ModelValidationError("sample_count must be an integer") from exc
        record = cls(
            projection_id=_required_text(value.get("projection_id"), "projection_id"),
            event_id=_required_text(value.get("event_id"), "event_id"),
            status=_required_text(value.get("status"), "status").lower(),
            amount=parse_decimal(value.get("amount"), field_name="fee amount"),
            currency=_required_text(value.get("currency", "CNY"), "currency").upper(),
            projected_at=utc_iso(value.get("projected_at"), "UTC"),
            source_fees=parse_decimal(value.get("source_fees"), field_name="source_fees"),
            method=(str(value["method"]).strip() if value.get("method") else None),
            method_version=(
                str(value.get("method_version", value.get("version"))).strip()
                if value.get("method_version", value.get("version"))
                else None
            ),
            sample_count=sample_count,
            profile_id=(
                str(value["profile_id"]).strip() if value.get("profile_id") else None
            ),
            reason_code=(
                str(value["reason_code"]).strip() if value.get("reason_code") else None
            ),
            provenance=_mapping(value.get("provenance"), "provenance"),
        )
        record.validate()
        return record


@dataclass(frozen=True)
class FeeCorrectionRecord:
    """Append-only human correction of a projected fee state."""

    correction_id: str
    event_id: str
    status: str
    amount: Decimal | None
    currency: str
    effective_at: str
    known_at: str
    reviewer_ref: str
    reason: str
    supersedes_correction_id: str | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        _required_text(self.correction_id, "correction_id")
        _required_text(self.event_id, "event_id")
        if self.status not in {"actual", "unknown"}:
            raise ModelValidationError(
                "fee correction status must be 'actual' or 'unknown'"
            )
        _required_text(self.currency, "currency")
        _required_text(self.reviewer_ref, "reviewer_ref")
        _required_text(self.reason, "reason")
        ensure_known_not_before_occurred(self.effective_at, self.known_at)
        if self.status == "actual" and (self.amount is None or self.amount <= 0):
            raise ModelValidationError("actual fee correction requires a positive amount")
        if self.status == "unknown" and self.amount is not None:
            raise ModelValidationError("unknown fee correction must preserve amount as missing")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "correction_id": self.correction_id,
            "event_id": self.event_id,
            "status": self.status,
            "amount": str(self.amount) if self.amount is not None else None,
            "currency": self.currency.strip().upper(),
            "effective_at": utc_iso(self.effective_at, "UTC"),
            "known_at": utc_iso(self.known_at, "UTC"),
            "reviewer_ref": self.reviewer_ref,
            "reason": self.reason,
            "supersedes_correction_id": self.supersedes_correction_id,
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FeeCorrectionRecord":
        record = cls(
            correction_id=_required_text(value.get("correction_id"), "correction_id"),
            event_id=_required_text(value.get("event_id"), "event_id"),
            status=_required_text(value.get("status"), "status").lower(),
            amount=parse_decimal(value.get("amount"), field_name="fee amount"),
            currency=_required_text(value.get("currency", "CNY"), "currency").upper(),
            effective_at=utc_iso(value.get("effective_at"), "UTC"),
            known_at=utc_iso(value.get("known_at"), "UTC"),
            reviewer_ref=_required_text(value.get("reviewer_ref"), "reviewer_ref"),
            reason=_required_text(value.get("reason"), "reason"),
            supersedes_correction_id=(
                str(value["supersedes_correction_id"]).strip()
                if value.get("supersedes_correction_id")
                else None
            ),
            provenance=_mapping(value.get("provenance"), "provenance"),
        )
        record.validate()
        return record


@dataclass(frozen=True)
class ReviewRunRecord:
    """Create-only request metadata for one product review run."""

    run_id: str
    run_key: str
    scope: str
    requested_at: str
    source_cutoff: str | None = None
    trigger: str = "manual"
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        _required_text(self.run_id, "run_id")
        _required_text(self.run_key, "run_key")
        if self.scope not in REVIEW_RUN_SCOPES:
            raise ModelValidationError(f"Unsupported review run scope: {self.scope!r}")
        utc_iso(self.requested_at, "UTC")
        if self.source_cutoff is not None:
            utc_iso(self.source_cutoff, "UTC")
        _required_text(self.trigger, "trigger")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "run_id": self.run_id,
            "run_key": self.run_key,
            "scope": self.scope,
            "requested_at": utc_iso(self.requested_at, "UTC"),
            "source_cutoff": (
                utc_iso(self.source_cutoff, "UTC")
                if self.source_cutoff is not None
                else None
            ),
            "trigger": self.trigger,
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ReviewRunRecord":
        record = cls(
            run_id=_required_text(value.get("run_id"), "run_id"),
            run_key=_required_text(value.get("run_key"), "run_key"),
            scope=_required_text(value.get("scope"), "scope").lower(),
            requested_at=utc_iso(value.get("requested_at"), "UTC"),
            source_cutoff=(
                utc_iso(value["source_cutoff"], "UTC")
                if value.get("source_cutoff")
                else None
            ),
            trigger=_required_text(value.get("trigger", "manual"), "trigger"),
            parameters=_mapping(value.get("parameters"), "parameters"),
        )
        record.validate()
        return record


@dataclass(frozen=True)
class ReviewRunStatusEvent:
    """Immutable status event used to project retry-safe run state."""

    run_event_id: str
    run_id: str
    status: str
    occurred_at: str
    known_at: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        _required_text(self.run_event_id, "run_event_id")
        _required_text(self.run_id, "run_id")
        if self.status not in REVIEW_RUN_STATUSES:
            raise ModelValidationError(f"Unsupported review run status: {self.status!r}")
        ensure_known_not_before_occurred(self.occurred_at, self.known_at)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "run_event_id": self.run_event_id,
            "run_id": self.run_id,
            "status": self.status,
            "occurred_at": utc_iso(self.occurred_at, "UTC"),
            "known_at": utc_iso(self.known_at, "UTC"),
            "details": dict(self.details),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ReviewRunStatusEvent":
        record = cls(
            run_event_id=_required_text(value.get("run_event_id"), "run_event_id"),
            run_id=_required_text(value.get("run_id"), "run_id"),
            status=_required_text(value.get("status"), "status").lower(),
            occurred_at=utc_iso(value.get("occurred_at"), "UTC"),
            known_at=utc_iso(value.get("known_at"), "UTC"),
            details=_mapping(value.get("details"), "details"),
        )
        record.validate()
        return record


_TIME_BASES = frozenset(
    {
        "source_occurred_at",
        "source_effective_at",
        "owner_action_default",
        "explicit_user_record",
        "system_observation",
        "recorded_later",
        "ingest_observation",
        "not_observed",
        "unknown",
    }
)
_OPERATION_STATUSES = frozenset({"ready", "partial", "blocked"})
_DECISION_STATUSES = frozenset(
    {"complete", "partial", "not_recorded", "not_applicable", "blocked"}
)
_SNAPSHOT_STATUSES = frozenset({"available", "partial", "missing", "blocked"})
_SNAPSHOT_FIELD_STATUSES = frozenset(
    {"available", "partial", "missing", "not_applicable"}
)
_MARKET_STATUSES = frozenset(
    {"available", "partial", "missing", "stale", "insufficient", "failed", "withheld"}
)
_MARKET_TEMPORAL_ROLES = frozenset(
    {
        "system_known_at_decision",
        "reconstructed_public_context",
        "withheld",
        "missing",
    }
)
_LIFECYCLE_STATUSES = frozenset({"open", "closed", "ambiguous", "unknown"})
_OUTCOME_STATUSES = frozenset({"interim", "final", "not_applicable", "missing"})
_CHECKPOINT_TYPES = frozenset(
    {"entry", "active_checkpoint", "adjustment", "exit", "postmortem"}
)
_REVIEW_KINDS = frozenset({"operation_review", "active_checkpoint", "postmortem"})
_PERSPECTIVES = frozenset({"user", "system"})
_GAP_SEVERITIES = frozenset({"info", "warning", "blocker"})
_MARKET_COVERAGE_STATES = frozenset(
    {"satisfied", "missing", "stale", "insufficient"}
)
_MARKET_FALLBACK_STATUSES = frozenset(
    {
        "not_needed",
        "succeeded",
        "failed",
        "provider_unavailable",
    }
)
_FALLBACK_TRIGGER_STATES = frozenset({"missing", "stale", "insufficient"})
_AWARE_TIMESTAMP = re.compile(r"(?:Z|[+-]\d{2}:\d{2})$")


def _closed_object(
    value: object,
    *,
    name: str,
    required: set[str],
    optional: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ModelValidationError(f"{name} must be an object")
    result = {str(key): item for key, item in value.items()}
    allowed = required | (optional or set())
    missing = sorted(required - set(result))
    extra = sorted(set(result) - allowed)
    if missing:
        raise ModelValidationError(f"{name} is missing required fields: {missing}")
    if extra:
        raise ModelValidationError(f"{name} has unsupported fields: {extra}")
    return result


def _strict_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ModelValidationError(f"{name} must be a string")
    text = value.strip()
    if not text:
        raise ModelValidationError(f"{name} is required")
    return text


def _canonical_market_parameter_value(
    value: object,
    *,
    key: str,
    name: str,
) -> str:
    if not isinstance(value, str):
        raise ModelValidationError(f"{name} must be a string")
    text = value.strip()
    if not text and key not in MARKET_PROVIDER_PARAMETER_ALLOW_EMPTY:
        raise ModelValidationError(f"{name} is required")
    if len(text) > MARKET_PROVIDER_PARAMETER_MAX_LENGTH:
        raise ModelValidationError(f"{name} exceeds the safe persistence limit")
    if re.search(MARKET_PROVIDER_SENSITIVE_PARAMETER_PATTERN, text, re.I):
        raise ModelValidationError(
            "market fetch receipt parameter values must not contain secret material"
        )
    pattern = MARKET_PROVIDER_PARAMETER_VALUE_PATTERNS.get(key)
    if pattern is None or re.fullmatch(pattern, text) is None:
        raise ModelValidationError(
            f"market fetch receipt parameter value is invalid for {key}"
        )
    return text


def _enum_text(value: object, *, name: str, allowed: frozenset[str]) -> str:
    text = _strict_text(value, name).lower()
    if text not in allowed:
        raise ModelValidationError(f"Unsupported {name}: {text!r}")
    return text


def _aware_utc(value: object, *, name: str) -> str:
    text = _strict_text(value, name)
    if _AWARE_TIMESTAMP.search(text) is None:
        raise ModelValidationError(f"{name} must include an explicit timezone")
    return utc_iso(text, "UTC")


def _string_set(value: object, *, name: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise ModelValidationError(f"{name} must be an array")
    normalized = sorted({_strict_text(item, name) for item in value})
    if len(normalized) != len(value):
        raise ModelValidationError(f"{name} must not contain duplicates")
    return normalized


def _time_projection(
    value: object,
    *,
    name: str,
    nullable: bool,
    allowed_available_bases: frozenset[str],
) -> dict[str, Any]:
    item = _closed_object(
        value,
        name=name,
        required={"value", "basis", "source_refs"},
    )
    basis = _enum_text(item["basis"], name=f"{name}.basis", allowed=_TIME_BASES)
    raw_timestamp = item["value"]
    timestamp = (
        None
        if raw_timestamp is None
        else _aware_utc(raw_timestamp, name=f"{name}.value")
    )
    if timestamp is None and not nullable:
        raise ModelValidationError(f"{name}.value cannot be null")
    if timestamp is None and basis not in {"not_observed", "unknown"}:
        raise ModelValidationError(
            f"{name}.basis must preserve an explicit missing-observation state"
        )
    if timestamp is not None and basis in {"not_observed", "unknown"}:
        raise ModelValidationError(
            f"{name}.basis cannot hide an available timestamp"
        )
    if timestamp is not None and basis not in allowed_available_bases:
        if name == "time_provenance.system_observed_at":
            raise ModelValidationError(
                f"{name}.basis cannot prove system observation: {basis!r}"
            )
        raise ModelValidationError(
            f"{name}.basis is incompatible with this time field: {basis!r}"
        )
    refs = _string_set(item["source_refs"], name=f"{name}.source_refs")
    if timestamp is not None and not refs:
        raise ModelValidationError(f"{name} requires source references")
    return {
        "value": timestamp,
        "basis": basis,
        "source_refs": refs,
    }


def _axis_base(
    value: object,
    *,
    name: str,
    allowed_statuses: frozenset[str],
) -> tuple[dict[str, Any], str, list[str], str | None]:
    item = _closed_object(
        value,
        name=name,
        required={"status", "source_refs"},
        optional={"summary"},
    )
    status = _enum_text(
        item["status"], name=f"{name}.status", allowed=allowed_statuses
    )
    refs = _string_set(item["source_refs"], name=f"{name}.source_refs")
    summary = (
        _strict_text(item["summary"], f"{name}.summary")
        if item.get("summary") is not None
        else None
    )
    return item, status, refs, summary


def _canonical_status_axes(value: object) -> dict[str, Any]:
    axes = _closed_object(
        value,
        name="status_axes",
        required=set(REVIEWABILITY_STATUS_AXES),
    )
    result: dict[str, Any] = {}
    for axis, allowed in (
        ("operation", _OPERATION_STATUSES),
        ("decision", _DECISION_STATUSES),
        ("lifecycle", _LIFECYCLE_STATUSES),
        ("outcome", _OUTCOME_STATUSES),
    ):
        _, status, refs, summary = _axis_base(
            axes[axis], name=f"status_axes.{axis}", allowed_statuses=allowed
        )
        result[axis] = {"status": status, "source_refs": refs}
        if summary is not None:
            result[axis]["summary"] = summary

    snapshot = _closed_object(
        axes["snapshot_cash_valuation"],
        name="status_axes.snapshot_cash_valuation",
        required={"status", "fields", "source_refs"},
        optional={"summary"},
    )
    snapshot_status = _enum_text(
        snapshot["status"],
        name="status_axes.snapshot_cash_valuation.status",
        allowed=_SNAPSHOT_STATUSES,
    )
    fields = _closed_object(
        snapshot["fields"],
        name="status_axes.snapshot_cash_valuation.fields",
        required=set(REVIEWABILITY_SNAPSHOT_FIELDS),
    )
    canonical_fields: dict[str, Any] = {}
    for field_name in REVIEWABILITY_SNAPSHOT_FIELDS:
        field_value = _closed_object(
            fields[field_name],
            name=f"snapshot field {field_name}",
            required={"status", "value", "unit", "source_refs"},
        )
        field_status = _enum_text(
            field_value["status"],
            name=f"snapshot field {field_name}.status",
            allowed=_SNAPSHOT_FIELD_STATUSES,
        )
        raw_value = field_value["value"]
        if isinstance(raw_value, float):
            raise ModelValidationError(
                f"snapshot field {field_name}.value cannot be a binary float"
            )
        if field_status in {"missing", "not_applicable"} and raw_value is not None:
            raise ModelValidationError(
                f"snapshot field {field_name} cannot supply a value while {field_status}"
            )
        if field_status == "available" and raw_value is None:
            raise ModelValidationError(
                f"snapshot field {field_name} requires a value while available"
            )
        field_refs = _string_set(
            field_value["source_refs"],
            name=f"snapshot field {field_name}.source_refs",
        )
        if field_status in {"available", "partial"} and not field_refs:
            raise ModelValidationError(
                f"snapshot field {field_name} {field_status} requires source references"
            )
        canonical_fields[field_name] = {
            "status": field_status,
            "value": None if raw_value is None else str(raw_value),
            "unit": (
                None
                if field_value["unit"] is None
                else _strict_text(
                    field_value["unit"], f"snapshot field {field_name}.unit"
                )
            ),
            "source_refs": field_refs,
        }
    result["snapshot_cash_valuation"] = {
        "status": snapshot_status,
        "fields": canonical_fields,
        "source_refs": _string_set(
            snapshot["source_refs"],
            name="status_axes.snapshot_cash_valuation.source_refs",
        ),
    }
    if snapshot.get("summary") is not None:
        result["snapshot_cash_valuation"]["summary"] = _strict_text(
            snapshot["summary"], "status_axes.snapshot_cash_valuation.summary"
        )

    market = _closed_object(
        axes["market"],
        name="status_axes.market",
        required={
            "status",
            "temporal_role",
            "effective_at",
            "publicly_available_at",
            "publicly_available_basis",
            "fetched_at",
            "system_observed_at",
            "source_refs",
        },
        optional={"summary"},
    )
    market_status = _enum_text(
        market["status"], name="status_axes.market.status", allowed=_MARKET_STATUSES
    )
    market_role = _enum_text(
        market["temporal_role"],
        name="status_axes.market.temporal_role",
        allowed=_MARKET_TEMPORAL_ROLES,
    )
    market_times: dict[str, str | None] = {}
    for key in (
        "effective_at",
        "publicly_available_at",
        "fetched_at",
        "system_observed_at",
    ):
        market_times[key] = (
            None
            if market[key] is None
            else _aware_utc(market[key], name=f"status_axes.market.{key}")
        )
    public_basis = _strict_text(
        market["publicly_available_basis"],
        "status_axes.market.publicly_available_basis",
    ).lower()
    if public_basis not in {
        "source_declared",
        "exchange_calendar",
        "provider_declared",
        "unknown",
        "not_applicable",
    }:
        raise ModelValidationError(
            "Unsupported status_axes.market.publicly_available_basis"
        )
    if public_basis == "owner_action_default":
        raise ModelValidationError("owner_action_default is forbidden for market data")
    if market_role == "system_known_at_decision" and market_times["system_observed_at"] is None:
        raise ModelValidationError(
            "system_known_at_decision requires a real system_observed_at"
        )
    if market_role == "reconstructed_public_context" and market_times["fetched_at"] is None:
        raise ModelValidationError(
            "reconstructed_public_context requires the real fetched_at"
        )
    result["market"] = {
        "status": market_status,
        "temporal_role": market_role,
        **market_times,
        "publicly_available_basis": public_basis,
        "source_refs": _string_set(
            market["source_refs"], name="status_axes.market.source_refs"
        ),
    }
    if market.get("summary") is not None:
        result["market"]["summary"] = _strict_text(
            market["summary"], "status_axes.market.summary"
        )
    return result


def _canonical_market_fallback(value: object) -> dict[str, Any]:
    item = _closed_object(
        value,
        name="market_fallback",
        required={
            "policy_version",
            "allowlist_version",
            "allowlist_sha256",
            "coverage_before",
            "coverage_after",
            "status",
            "request_count",
            "limits",
            "allowlist",
            "cache_refs",
            "fetch_receipt_refs",
            "fetch_receipts",
            "offline_consumers",
        },
    )
    if item["policy_version"] != MARKET_FALLBACK_POLICY_VERSION:
        raise ModelValidationError("Unsupported market fallback policy version")
    if item["allowlist_version"] != MARKET_PROVIDER_ALLOWLIST_VERSION:
        raise ModelValidationError("Unsupported market provider allowlist version")
    if item["allowlist_sha256"] != MARKET_PROVIDER_ALLOWLIST_SHA256:
        raise ModelValidationError("Market provider allowlist hash does not match v1")
    coverage_before = _enum_text(
        item["coverage_before"],
        name="market_fallback.coverage_before",
        allowed=_MARKET_COVERAGE_STATES,
    )
    coverage_after = _enum_text(
        item["coverage_after"],
        name="market_fallback.coverage_after",
        allowed=_MARKET_COVERAGE_STATES,
    )
    status = _enum_text(
        item["status"],
        name="market_fallback.status",
        allowed=_MARKET_FALLBACK_STATUSES,
    )
    if isinstance(item["request_count"], bool) or not isinstance(
        item["request_count"], int
    ):
        raise ModelValidationError("market_fallback.request_count must be an integer")
    request_count = int(item["request_count"])
    if not 0 <= request_count <= 20:
        raise ModelValidationError("market_fallback.request_count exceeds 20")
    limits = _closed_object(
        item["limits"],
        name="market_fallback.limits",
        required={
            "timeout_seconds",
            "max_retries",
            "max_concurrency",
            "max_requests_per_run",
        },
    )
    expected_limits = {
        "timeout_seconds": 20,
        "max_retries": 2,
        "max_concurrency": 2,
        "max_requests_per_run": 20,
    }
    if limits != expected_limits:
        raise ModelValidationError("market fallback limits must match the frozen policy")
    offline = _closed_object(
        item["offline_consumers"],
        name="market_fallback.offline_consumers",
        required={"renderer", "source_replay", "api", "ui"},
    )
    if any(value is not False for value in offline.values()):
        raise ModelValidationError(
            "renderer, source replay, API and UI must remain offline"
        )
    allowlist = _string_set(item["allowlist"], name="market_fallback.allowlist")
    if frozenset(allowlist) != MARKET_PROVIDER_ALLOWLIST:
        raise ModelValidationError(
            "market provider allowlist must match the code-owned frozen allowlist"
        )
    fetch_receipts: list[dict[str, Any]] = []
    if not isinstance(item["fetch_receipts"], (list, tuple)):
        raise ModelValidationError("market_fallback.fetch_receipts must be an array")
    if len(item["fetch_receipts"]) > 20:
        raise ModelValidationError(
            "market_fallback.fetch_receipts cannot exceed 20 entries"
        )
    for index, raw_receipt in enumerate(item["fetch_receipts"]):
        receipt = _closed_object(
            raw_receipt,
            name=f"market_fallback.fetch_receipts[{index}]",
            required={
                "receipt_id",
                "provider_id",
                "endpoint_id",
                "provider_version",
                "redacted_parameters",
                "request_fingerprint_version",
                "request_fingerprint",
                "started_at",
                "completed_at",
                "fetched_at",
                "response_status",
                "attempt_count",
                "raw_content_sha256",
                "normalized_content_sha256",
                "cache_entry_refs",
                "cache_lineage",
            },
        )
        provider_id = _strict_text(
            receipt["provider_id"], f"fetch_receipts[{index}].provider_id"
        )
        endpoint_id = _strict_text(
            receipt["endpoint_id"], f"fetch_receipts[{index}].endpoint_id"
        )
        provider_endpoint = f"{provider_id}:{endpoint_id}"
        if provider_endpoint not in allowlist:
            raise ModelValidationError(
                "market fetch receipt provider/endpoint is not allowlisted"
            )
        parameters = receipt["redacted_parameters"]
        if not isinstance(parameters, Mapping):
            raise ModelValidationError(
                f"fetch_receipts[{index}].redacted_parameters must be an object"
            )
        canonical_parameters: dict[str, str] = {}
        allowed_parameter_keys = MARKET_PROVIDER_PARAMETER_ALLOWLIST[
            provider_endpoint
        ]
        for raw_key, raw_value in parameters.items():
            key = _strict_text(raw_key, f"fetch_receipts[{index}] parameter key")
            if re.search(MARKET_PROVIDER_SENSITIVE_PARAMETER_PATTERN, key, re.I):
                raise ModelValidationError(
                    "market fetch receipt parameters must not contain secret fields"
                )
            if key not in allowed_parameter_keys:
                raise ModelValidationError(
                    "market fetch receipt parameter is not allowlisted for "
                    f"{provider_endpoint}: {key}"
                )
            if key in canonical_parameters:
                raise ModelValidationError(
                    "market fetch receipt parameters contain duplicate normalized keys"
                )
            canonical_parameters[key] = _canonical_market_parameter_value(
                raw_value,
                key=key,
                name=f"fetch_receipts[{index}].redacted_parameters.{key}",
            )
        provider_version = _strict_text(
            receipt["provider_version"],
            f"fetch_receipts[{index}].provider_version",
        )
        if (
            receipt["request_fingerprint_version"]
            != MARKET_REQUEST_FINGERPRINT_VERSION
        ):
            raise ModelValidationError(
                "Unsupported market request fingerprint version"
            )
        fingerprint = _strict_text(
            receipt["request_fingerprint"],
            f"fetch_receipts[{index}].request_fingerprint",
        )
        expected_fingerprint = market_request_fingerprint(
            provider_id=provider_id,
            endpoint_id=endpoint_id,
            provider_version=provider_version,
            redacted_parameters=canonical_parameters,
        )
        if fingerprint != expected_fingerprint:
            raise ModelValidationError(
                "market request fingerprint does not match canonical request"
            )
        response_status = _enum_text(
            receipt["response_status"],
            name=f"fetch_receipts[{index}].response_status",
            allowed=frozenset(
                {
                    "succeeded",
                    "failed",
                    "timeout",
                    "provider_unavailable",
                    "rejected",
                }
            ),
        )
        attempt_count = receipt["attempt_count"]
        if (
            isinstance(attempt_count, bool)
            or not isinstance(attempt_count, int)
            or not 0 <= attempt_count <= 3
        ):
            raise ModelValidationError(
                "market fetch receipt attempt_count must be between 0 and 3"
            )
        raw_hash = receipt["raw_content_sha256"]
        normalized_hash = receipt["normalized_content_sha256"]
        for label, hash_value in (
            ("raw_content_sha256", raw_hash),
            ("normalized_content_sha256", normalized_hash),
        ):
            if hash_value is not None and re.fullmatch(
                r"sha256:[0-9a-f]{64}", str(hash_value)
            ) is None:
                raise ModelValidationError(
                    f"market fetch receipt {label} must be SHA-256 or null"
                )
        fetched_at = (
            None
            if receipt["fetched_at"] is None
            else _aware_utc(
                receipt["fetched_at"],
                name=f"fetch_receipts[{index}].fetched_at",
            )
        )
        cache_entry_refs = _string_set(
            receipt["cache_entry_refs"],
            name=f"fetch_receipts[{index}].cache_entry_refs",
        )
        cache_lineage = _string_set(
            receipt["cache_lineage"],
            name=f"fetch_receipts[{index}].cache_lineage",
        )
        if not cache_lineage:
            raise ModelValidationError(
                "every market fetch receipt must bind the triggering cache requirement"
            )
        if response_status == "succeeded" and (
            attempt_count == 0
            or fetched_at is None
            or raw_hash is None
            or normalized_hash is None
            or not cache_entry_refs
            or not cache_lineage
        ):
            raise ModelValidationError(
                "successful market fetch requires attempts, fetched time, hashes, cache refs and lineage"
            )
        if response_status == "provider_unavailable" and (
            attempt_count != 0
            or fetched_at is not None
            or raw_hash is not None
            or normalized_hash is not None
            or cache_entry_refs
        ):
            raise ModelValidationError(
                "provider_unavailable receipt must prove a zero-request, uncached outcome"
            )
        if response_status in {"failed", "timeout", "rejected"} and attempt_count == 0:
            raise ModelValidationError(
                "attempted market fetch outcomes require at least one HTTP attempt"
            )
        started_at = _aware_utc(
            receipt["started_at"],
            name=f"fetch_receipts[{index}].started_at",
        )
        completed_at = _aware_utc(
            receipt["completed_at"],
            name=f"fetch_receipts[{index}].completed_at",
        )
        ensure_known_not_before_occurred(started_at, completed_at)
        if fetched_at is not None:
            ensure_known_not_before_occurred(started_at, fetched_at)
            ensure_known_not_before_occurred(fetched_at, completed_at)
        fetch_receipts.append(
            {
                "receipt_id": _strict_text(
                    receipt["receipt_id"], f"fetch_receipts[{index}].receipt_id"
                ),
                "provider_id": provider_id,
                "endpoint_id": endpoint_id,
                "provider_version": provider_version,
                "redacted_parameters": dict(sorted(canonical_parameters.items())),
                "request_fingerprint_version": MARKET_REQUEST_FINGERPRINT_VERSION,
                "request_fingerprint": fingerprint,
                "started_at": started_at,
                "completed_at": completed_at,
                "fetched_at": fetched_at,
                "response_status": response_status,
                "attempt_count": attempt_count,
                "raw_content_sha256": raw_hash,
                "normalized_content_sha256": normalized_hash,
                "cache_entry_refs": cache_entry_refs,
                "cache_lineage": cache_lineage,
            }
        )
    fetch_receipts.sort(key=lambda receipt: receipt["receipt_id"])
    receipt_ids = [receipt["receipt_id"] for receipt in fetch_receipts]
    if len(receipt_ids) != len(set(receipt_ids)):
        raise ModelValidationError("market fetch receipt IDs must be unique")
    fetch_receipt_refs = _string_set(
        item["fetch_receipt_refs"],
        name="market_fallback.fetch_receipt_refs",
    )
    if fetch_receipt_refs != receipt_ids:
        raise ModelValidationError(
            "market fetch receipt refs must exactly bind the embedded receipts"
        )
    cache_refs = _string_set(
        item["cache_refs"], name="market_fallback.cache_refs"
    )
    if coverage_before == "satisfied":
        if (
            coverage_after != "satisfied"
            or status != "not_needed"
            or request_count != 0
            or not cache_refs
        ):
            raise ModelValidationError(
                "satisfied local coverage requires frozen local cache refs, must "
                "remain satisfied and forbids external market requests"
            )
        if fetch_receipt_refs:
            raise ModelValidationError(
                "satisfied local coverage cannot have fetch receipts"
            )
        if fetch_receipts:
            raise ModelValidationError(
                "satisfied local coverage cannot embed fetch receipts"
            )
    actual_request_count = sum(
        int(receipt["attempt_count"]) for receipt in fetch_receipts
    )
    if request_count != actual_request_count:
        raise ModelValidationError(
            "market request_count must match all HTTP attempts in fetch receipts"
        )
    successful_receipts = [
        receipt
        for receipt in fetch_receipts
        if receipt["response_status"] == "succeeded"
    ]
    if status == "succeeded" and (
        not successful_receipts or not cache_refs or request_count == 0
    ):
        raise ModelValidationError(
            "successful market fallback requires a successful receipt and cache refs"
        )
    if status == "failed" and (
        not fetch_receipts
        or successful_receipts
        or request_count == 0
        or coverage_after == "satisfied"
    ):
        raise ModelValidationError(
            "failed market fallback requires attempted receipts and no success"
        )
    if status == "provider_unavailable":
        unavailable = [
            receipt
            for receipt in fetch_receipts
            if receipt["response_status"] == "provider_unavailable"
            and receipt["attempt_count"] == 0
        ]
        if (
            len(unavailable) != 1
            or len(fetch_receipts) != 1
            or request_count != 0
            or coverage_after == "satisfied"
        ):
            raise ModelValidationError(
                "provider_unavailable requires one zero-attempt provenance receipt"
            )
    if status in {"succeeded", "failed", "provider_unavailable"}:
        if coverage_before not in _FALLBACK_TRIGGER_STATES:
            raise ModelValidationError(
                "market fallback requires missing, stale or insufficient local coverage"
            )
    if status == "not_needed" and coverage_before != "satisfied":
        raise ModelValidationError(
            "market fallback is not_needed only when local coverage is satisfied"
        )
    if coverage_after == "satisfied" and status not in {"not_needed", "succeeded"}:
        raise ModelValidationError(
            "satisfied post-fallback coverage requires local satisfaction or a successful fetch"
        )
    successful_cache_refs = {
        cache_ref
        for receipt in successful_receipts
        for cache_ref in receipt["cache_entry_refs"]
    }
    if not successful_cache_refs.issubset(set(cache_refs)):
        raise ModelValidationError(
            "market fallback cache refs must include every successful receipt cache entry"
        )
    if request_count > 0 and status in {"not_needed", "provider_unavailable"}:
        raise ModelValidationError(
            "market fallback status is inconsistent with request_count"
        )
    return {
        "policy_version": MARKET_FALLBACK_POLICY_VERSION,
        "allowlist_version": MARKET_PROVIDER_ALLOWLIST_VERSION,
        "allowlist_sha256": MARKET_PROVIDER_ALLOWLIST_SHA256,
        "coverage_before": coverage_before,
        "coverage_after": coverage_after,
        "status": status,
        "request_count": request_count,
        "limits": expected_limits,
        "allowlist": allowlist,
        "cache_refs": cache_refs,
        "fetch_receipt_refs": fetch_receipt_refs,
        "fetch_receipts": fetch_receipts,
        "offline_consumers": {
            "renderer": False,
            "source_replay": False,
            "api": False,
            "ui": False,
        },
    }


def _canonical_gaps(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        raise ModelValidationError("gaps must be an array")
    gaps: list[dict[str, Any]] = []
    for index, raw_gap in enumerate(value):
        gap = _closed_object(
            raw_gap,
            name=f"gaps[{index}]",
            required={
                "gap_id",
                "axis",
                "code",
                "severity",
                "blocks_axis",
                "owner",
                "next_step",
                "source_refs",
            },
        )
        code = _strict_text(gap["code"], f"gaps[{index}].code").upper()
        if code == "OPEN_EPISODE_OUTCOME_NOT_FINAL":
            raise ModelValidationError(
                "open/interim is a lifecycle notice, not a review gap"
            )
        axis = _strict_text(gap["axis"], f"gaps[{index}].axis")
        if axis not in REVIEWABILITY_STATUS_AXES:
            raise ModelValidationError(f"Unsupported gap axis: {axis!r}")
        severity = _enum_text(
            gap["severity"],
            name=f"gaps[{index}].severity",
            allowed=_GAP_SEVERITIES,
        )
        if not isinstance(gap["blocks_axis"], bool):
            raise ModelValidationError(f"gaps[{index}].blocks_axis must be boolean")
        gaps.append(
            {
                "gap_id": _strict_text(gap["gap_id"], f"gaps[{index}].gap_id"),
                "axis": axis,
                "code": code,
                "severity": severity,
                "blocks_axis": gap["blocks_axis"],
                "owner": _strict_text(gap["owner"], f"gaps[{index}].owner"),
                "next_step": _strict_text(
                    gap["next_step"], f"gaps[{index}].next_step"
                ),
                "source_refs": _string_set(
                    gap["source_refs"], name=f"gaps[{index}].source_refs"
                ),
            }
        )
    gaps.sort(key=lambda item: item["gap_id"])
    gap_ids = [item["gap_id"] for item in gaps]
    if len(gap_ids) != len(set(gap_ids)):
        raise ModelValidationError("gap_id values must be unique")
    return gaps


@dataclass(frozen=True)
class OperationCheckpointRecord:
    """Closed, deterministic v3 reviewability checkpoint projection."""

    payload: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "OperationCheckpointRecord":
        root = _closed_object(
            value,
            name="operation checkpoint",
            required={
                "episode_id",
                "position_case_id",
                "review_kind",
                "checkpoint_type",
                "perspective",
                "as_of",
                "knowledge_cutoff",
                "time_provenance",
                "status_axes",
                "market_fallback",
                "gaps",
                "source_refs",
                "governance",
            },
            optional={
                "schema_version",
                "checkpoint_id",
                "checkpoint_key",
                "content_id",
            },
        )
        if root.get("schema_version", OPERATION_CHECKPOINT_SCHEMA_VERSION) != (
            OPERATION_CHECKPOINT_SCHEMA_VERSION
        ):
            raise ModelValidationError("Unsupported operation checkpoint schema")

        times = _closed_object(
            root["time_provenance"],
            name="time_provenance",
            required={
                "effective_at",
                "user_known_at",
                "system_observed_at",
                "recorded_at",
            },
        )
        canonical_times = {
            "effective_at": _time_projection(
                times["effective_at"],
                name="time_provenance.effective_at",
                nullable=False,
                allowed_available_bases=frozenset(
                    {"source_occurred_at", "source_effective_at"}
                ),
            ),
            "user_known_at": _time_projection(
                times["user_known_at"],
                name="time_provenance.user_known_at",
                nullable=True,
                allowed_available_bases=frozenset(
                    {
                        "owner_action_default",
                        "explicit_user_record",
                        "source_occurred_at",
                        "source_effective_at",
                    }
                ),
            ),
            "system_observed_at": _time_projection(
                times["system_observed_at"],
                name="time_provenance.system_observed_at",
                nullable=True,
                allowed_available_bases=frozenset(
                    {
                        "system_observation",
                        "recorded_later",
                        "ingest_observation",
                    }
                ),
            ),
            "recorded_at": _time_projection(
                times["recorded_at"],
                name="time_provenance.recorded_at",
                nullable=False,
                allowed_available_bases=frozenset(
                    {"recorded_later", "ingest_observation", "system_observation"}
                ),
            ),
        }
        effective = canonical_times["effective_at"]["value"]
        for key in ("user_known_at", "system_observed_at", "recorded_at"):
            projected = canonical_times[key]["value"]
            if projected is not None:
                ensure_known_not_before_occurred(effective, projected)
        if canonical_times["user_known_at"]["basis"] == "owner_action_default":
            if canonical_times["user_known_at"]["value"] != effective:
                raise ModelValidationError(
                    "owner_action_default must preserve user knowledge at effective time"
                )
        if canonical_times["system_observed_at"]["basis"] == "owner_action_default":
            raise ModelValidationError(
                "owner_action_default cannot prove system observation"
            )

        governance = _closed_object(
            root["governance"],
            name="governance",
            required={
                "facts_only",
                "no_motive",
                "no_advice",
                "no_score",
                "no_diagnosis",
            },
        )
        if any(governance[key] is not True for key in governance):
            raise ModelValidationError(
                "reviewability governance flags must all remain true"
            )

        as_of = _aware_utc(root["as_of"], name="as_of")
        knowledge_cutoff = _aware_utc(
            root["knowledge_cutoff"], name="knowledge_cutoff"
        )
        effective = canonical_times["effective_at"]["value"]
        ensure_known_not_before_occurred(effective, as_of)
        ensure_known_not_before_occurred(as_of, knowledge_cutoff)
        for key in ("user_known_at", "system_observed_at", "recorded_at"):
            projected = canonical_times[key]["value"]
            if projected is not None:
                ensure_known_not_before_occurred(projected, knowledge_cutoff)

        status_axes = _canonical_status_axes(root["status_axes"])
        market_fallback = _canonical_market_fallback(root["market_fallback"])
        gaps = _canonical_gaps(root["gaps"])
        if status_axes["operation"]["status"] in {
            "ready",
            "partial",
        } and not status_axes["operation"]["source_refs"]:
            raise ModelValidationError(
                "operation ready or partial requires explicit source references"
            )
        if status_axes["decision"]["status"] in {
            "complete",
            "partial",
        } and not status_axes["decision"]["source_refs"]:
            raise ModelValidationError(
                "decision complete or partial requires explicit source references"
            )
        snapshot = status_axes["snapshot_cash_valuation"]
        field_statuses = [
            item["status"] for item in snapshot["fields"].values()
        ]
        if snapshot["status"] == "available" and any(
            status not in {"available", "not_applicable"}
            for status in field_statuses
        ):
            raise ModelValidationError(
                "snapshot available cannot contain missing or partial fields"
            )
        if snapshot["status"] == "available" and not any(
            status == "available" for status in field_statuses
        ):
            raise ModelValidationError(
                "snapshot available requires at least one available component"
            )
        if snapshot["status"] == "missing" and any(
            status not in {"missing", "not_applicable"} for status in field_statuses
        ):
            raise ModelValidationError(
                "snapshot missing cannot hide available component fields"
            )
        if snapshot["status"] == "missing" and not any(
            status == "missing" for status in field_statuses
        ):
            raise ModelValidationError(
                "snapshot missing requires at least one explicitly missing component"
            )
        if snapshot["status"] == "partial" and (
            not any(
                status in {"available", "partial"} for status in field_statuses
            )
            or not any(status in {"partial", "missing"} for status in field_statuses)
        ):
            raise ModelValidationError(
                "snapshot partial requires both available and limited components"
            )
        if snapshot["status"] in {"available", "partial"} and not snapshot[
            "source_refs"
        ]:
            raise ModelValidationError(
                "snapshot available or partial requires explicit source references"
            )
        market_axis = status_axes["market"]
        if market_axis["status"] in {
            "available",
            "partial",
            "stale",
            "insufficient",
        } and not market_axis["source_refs"]:
            raise ModelValidationError(
                "material market states require explicit source references"
            )
        market_effective_at = market_axis["effective_at"]
        if market_effective_at is not None:
            ensure_known_not_before_occurred(market_effective_at, as_of)
        market_public_at = market_axis["publicly_available_at"]
        if market_public_at is not None:
            if market_effective_at is not None:
                ensure_known_not_before_occurred(
                    market_effective_at, market_public_at
                )
            ensure_known_not_before_occurred(market_public_at, knowledge_cutoff)
        for market_time_name in ("fetched_at", "system_observed_at"):
            market_time = market_axis[market_time_name]
            if market_time is not None:
                if market_effective_at is not None:
                    ensure_known_not_before_occurred(
                        market_effective_at, market_time
                    )
                if market_public_at is not None:
                    ensure_known_not_before_occurred(market_public_at, market_time)
                ensure_known_not_before_occurred(market_time, knowledge_cutoff)
        if (
            market_axis["fetched_at"] is not None
            and market_axis["system_observed_at"] is not None
        ):
            ensure_known_not_before_occurred(
                market_axis["fetched_at"],
                market_axis["system_observed_at"],
            )
        if market_axis["status"] == "available" and (
            not market_axis["source_refs"] or market_effective_at is None
        ):
            raise ModelValidationError(
                "market available requires effective time and source references"
            )
        if market_axis["temporal_role"] == "system_known_at_decision":
            observed = market_axis["system_observed_at"]
            ensure_known_not_before_occurred(observed, as_of)
            ensure_known_not_before_occurred(observed, knowledge_cutoff)
            if market_axis["fetched_at"] is not None:
                ensure_known_not_before_occurred(
                    market_axis["fetched_at"], as_of
                )
            if market_public_at is not None:
                ensure_known_not_before_occurred(market_public_at, as_of)
        if (
            market_axis["temporal_role"] == "withheld"
            and market_axis["status"] != "withheld"
        ) or (
            market_axis["status"] == "withheld"
            and market_axis["temporal_role"] != "withheld"
        ):
            raise ModelValidationError(
                "withheld market status and temporal role must agree"
            )
        if (
            market_axis["temporal_role"] == "missing"
            and market_axis["status"] not in {"missing", "failed", "insufficient"}
        ):
            raise ModelValidationError(
                "missing market temporal role requires a missing or failed market state"
            )
        coverage_market_states = {
            "satisfied": frozenset({"available"}),
            "missing": frozenset({"missing", "failed"}),
            "stale": frozenset({"stale", "failed"}),
            "insufficient": frozenset({"insufficient", "partial", "failed"}),
        }
        coverage_after = market_fallback["coverage_after"]
        if market_axis["status"] not in coverage_market_states[coverage_after]:
            raise ModelValidationError(
                "market axis status is inconsistent with fallback coverage_after"
            )
        fallback_cache_refs = set(market_fallback["cache_refs"])
        market_source_refs = set(market_axis["source_refs"])
        if not fallback_cache_refs.issubset(market_source_refs):
            raise ModelValidationError(
                "market source refs must include every frozen fallback cache ref"
            )
        for receipt in market_fallback["fetch_receipts"]:
            for timestamp_name in ("started_at", "completed_at", "fetched_at"):
                timestamp = receipt[timestamp_name]
                if timestamp is not None:
                    ensure_known_not_before_occurred(timestamp, knowledge_cutoff)
        successful_receipts = [
            receipt
            for receipt in market_fallback["fetch_receipts"]
            if receipt["response_status"] == "succeeded"
        ]
        if successful_receipts:
            successful_cache_refs = {
                cache_ref
                for receipt in successful_receipts
                for cache_ref in receipt["cache_entry_refs"]
            }
            if not successful_cache_refs.issubset(market_source_refs):
                raise ModelValidationError(
                    "successful market cache entries must enter the frozen market context"
                )
            if market_axis["temporal_role"] != "reconstructed_public_context":
                raise ModelValidationError(
                    "externally fetched market context must remain retrospective"
                )
            latest_fetched_at = max(
                str(receipt["fetched_at"]) for receipt in successful_receipts
            )
            if market_axis["fetched_at"] != latest_fetched_at:
                raise ModelValidationError(
                    "market fetched_at must bind the latest successful fetch receipt"
                )
        if (
            status_axes["lifecycle"]["status"] in {"open", "closed"}
            and not status_axes["lifecycle"]["source_refs"]
        ):
            raise ModelValidationError(
                "known lifecycle state requires source references"
            )
        if (
            status_axes["outcome"]["status"] in {"interim", "final"}
            and not status_axes["outcome"]["source_refs"]
        ):
            raise ModelValidationError(
                "outcome maturity requires source references"
            )
        blocking_status = {
            "operation": "blocked",
            "decision": "blocked",
            "snapshot_cash_valuation": "blocked",
            "market": "failed",
            "lifecycle": "ambiguous",
            "outcome": "missing",
        }
        for gap in gaps:
            if gap["blocks_axis"] and (
                gap["severity"] != "blocker"
                or not gap["source_refs"]
                or status_axes[gap["axis"]]["status"]
                != blocking_status[gap["axis"]]
            ):
                raise ModelValidationError(
                    "axis-blocking gaps require blocker severity, evidence and a blocked axis state"
                )
            if gap["severity"] == "blocker" and not gap["blocks_axis"]:
                raise ModelValidationError(
                    "blocker severity must explicitly block its axis"
                )
        blocked_gap_axes = {
            gap["axis"] for gap in gaps if gap["blocks_axis"]
        }
        for axis, blocked_state in blocking_status.items():
            if (
                status_axes[axis]["status"] == blocked_state
                and axis not in blocked_gap_axes
            ):
                raise ModelValidationError(
                    f"blocked {axis} axis requires an explicit blocker gap"
                )

        episode_id = _strict_text(root["episode_id"], "episode_id")
        position_case_id = _strict_text(
            root["position_case_id"], "position_case_id"
        )
        review_kind = _enum_text(
            root["review_kind"], name="review_kind", allowed=_REVIEW_KINDS
        )
        checkpoint_type = _enum_text(
            root["checkpoint_type"],
            name="checkpoint_type",
            allowed=_CHECKPOINT_TYPES,
        )
        perspective = _enum_text(
            root["perspective"], name="perspective", allowed=_PERSPECTIVES
        )
        if (review_kind == "active_checkpoint") != (
            checkpoint_type == "active_checkpoint"
        ):
            raise ModelValidationError(
                "active_checkpoint review kind and checkpoint type must agree"
            )
        if (review_kind == "postmortem") != (
            checkpoint_type == "postmortem"
        ):
            raise ModelValidationError(
                "postmortem review kind and checkpoint type must agree"
            )
        lifecycle_status = status_axes["lifecycle"]["status"]
        outcome_status = status_axes["outcome"]["status"]
        if review_kind == "active_checkpoint" and (
            lifecycle_status != "open" or outcome_status != "interim"
        ):
            raise ModelValidationError(
                "active checkpoint requires open lifecycle and interim outcome"
            )
        if review_kind == "postmortem" and (
            lifecycle_status != "closed" or outcome_status != "final"
        ):
            raise ModelValidationError(
                "postmortem requires closed lifecycle and final outcome"
            )
        if checkpoint_type == "exit" and (
            lifecycle_status != "closed" or outcome_status != "final"
        ):
            raise ModelValidationError(
                "exit checkpoint requires closed lifecycle and final outcome"
            )
        if lifecycle_status == "open" and outcome_status == "final":
            raise ModelValidationError(
                "open lifecycle cannot claim a final outcome"
            )
        if lifecycle_status == "closed" and outcome_status == "interim":
            raise ModelValidationError(
                "closed lifecycle cannot retain an interim outcome"
            )
        if outcome_status == "final" and lifecycle_status != "closed":
            raise ModelValidationError(
                "final outcome requires a closed lifecycle"
            )
        identity_material = {
            "episode_id": episode_id,
            "review_kind": review_kind,
            "checkpoint_type": checkpoint_type,
            "perspective": perspective,
            "as_of": as_of,
            "knowledge_cutoff": knowledge_cutoff,
        }
        identity_digest = hashlib.sha256(
            canonical_json_bytes(identity_material)
        ).hexdigest()
        checkpoint_key = f"review_checkpoint_key_{identity_digest}"
        if root.get("checkpoint_key") not in (None, checkpoint_key):
            raise ModelValidationError(
                "checkpoint_key does not match canonical semantic identity"
            )

        source_refs = _string_set(root["source_refs"], name="source_refs")
        if not source_refs:
            raise ModelValidationError(
                "operation checkpoint requires root source references"
            )
        normalized: dict[str, Any] = {
            "schema_version": OPERATION_CHECKPOINT_SCHEMA_VERSION,
            "checkpoint_key": checkpoint_key,
            "episode_id": episode_id,
            "position_case_id": position_case_id,
            "review_kind": review_kind,
            "checkpoint_type": checkpoint_type,
            "perspective": perspective,
            "as_of": as_of,
            "knowledge_cutoff": knowledge_cutoff,
            "time_provenance": canonical_times,
            "status_axes": status_axes,
            "market_fallback": market_fallback,
            "gaps": gaps,
            "source_refs": source_refs,
            "governance": {
                "facts_only": True,
                "no_motive": True,
                "no_advice": True,
                "no_score": True,
                "no_diagnosis": True,
            },
        }
        checkpoint_id = "review_checkpoint_" + identity_digest[:32]
        if root.get("checkpoint_id") not in (None, checkpoint_id):
            raise ModelValidationError("checkpoint_id does not match canonical identity")
        normalized["checkpoint_id"] = checkpoint_id
        content_id = "sha256:" + hashlib.sha256(
            canonical_json_bytes(normalized)
        ).hexdigest()
        if root.get("content_id") not in (None, content_id):
            raise ModelValidationError("content_id does not match canonical content")
        normalized["content_id"] = content_id
        # Serialize and parse to detach nested mutable inputs and reject floats.
        detached = json.loads(canonical_json_bytes(normalized).decode("utf-8"))
        return cls(payload=detached)

    @property
    def checkpoint_id(self) -> str:
        return str(self.payload["checkpoint_id"])

    @property
    def checkpoint_key(self) -> str:
        return str(self.payload["checkpoint_key"])

    @property
    def content_id(self) -> str:
        return str(self.payload["content_id"])

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.canonical_bytes.decode("utf-8"))


_MARKET_FALLBACK_STATUSES_V2 = frozenset(
    {
        "not_needed",
        "succeeded",
        "failed",
        "provider_unavailable",
        "withheld_by_cutoff",
        "budget_exhausted",
    }
)
_MARKET_STATUSES_V2 = frozenset(
    {"available", "partial", "missing", "stale", "insufficient", "failed"}
)
_MARKET_TEMPORAL_ROLES_V2 = frozenset(
    {
        "user_known_at_operation_by_verified_publication",
        "system_known_at_operation",
        "retrospective_context",
        "ambiguous",
        "unknown",
        "missing",
    }
)
_MARKET_LIMITATION_CODES_V2 = frozenset(
    {
        "withheld_by_cutoff",
        "budget_exhausted",
        "provider_unavailable",
        "provider_attempt_count_unknown",
    }
)
_MARKET_PUBLIC_BASES_V2 = frozenset(
    {
        "source_declared",
        "exchange_calendar",
        "provider_declared",
        "verified_publication_interval",
        "unknown",
        "not_applicable",
    }
)
_MARKET_INFORMATION_TIME_BASES_V2 = frozenset(
    {
        "exchange_bar_publication_time.v1",
        "provider_exact_publication_time.v1",
        "provider_publication_date_source_timezone.v1",
        "unknown",
        "conflicted",
    }
)
_MARKET_ELIGIBILITY_REASON_CODES_V2 = frozenset(
    {
        "current_only_not_point_in_time",
        "publication_time_or_revision_conflicted",
        "publication_time_or_revision_unproven",
        "publication_revision_binding_conflicted",
        "verified_publication_strictly_before_operation",
        "publication_interval_touches_operation_anchor",
        "post_operation_publication",
        "system_observation_unknown",
        "system_observed_no_later_than_operation",
        "system_observed_after_operation",
    }
)
_MARKET_ELIGIBILITY_TEMPORAL_ROLES_V2 = frozenset(
    {
        "user_known_at_operation_by_verified_publication",
        "system_known_at_operation",
        "retrospective_public_context",
        "publication_time_ambiguous",
        "publication_time_unknown",
        "system_observation_unknown",
    }
)


def _sha256_content_id(value: object, *, name: str) -> str:
    content_id = _strict_text(value, name)
    if re.fullmatch(r"sha256:[0-9a-f]{64}", content_id) is None:
        raise ModelValidationError(f"{name} must be a canonical SHA-256 content ID")
    return content_id


def _canonical_market_information_time_v2(value: object) -> dict[str, Any]:
    item = _closed_object(
        value,
        name="status_axes.market.information_time",
        required={
            "status",
            "lower_bound",
            "upper_bound",
            "basis",
            "method_version",
            "revision_ref",
        },
    )
    status = _enum_text(
        item["status"],
        name="status_axes.market.information_time.status",
        allowed=frozenset({"verified", "unknown", "conflicted"}),
    )
    basis = _enum_text(
        item["basis"],
        name="status_axes.market.information_time.basis",
        allowed=_MARKET_INFORMATION_TIME_BASES_V2,
    )
    if item["method_version"] != "public_information_time.v1":
        raise ModelValidationError("market information-time method version drift")
    revision_ref = (
        None
        if item["revision_ref"] is None
        else _strict_text(
            item["revision_ref"],
            "status_axes.market.information_time.revision_ref",
        )
    )
    if status == "verified":
        lower_bound = _aware_utc(
            item["lower_bound"],
            name="status_axes.market.information_time.lower_bound",
        )
        upper_bound = _aware_utc(
            item["upper_bound"],
            name="status_axes.market.information_time.upper_bound",
        )
        ensure_known_not_before_occurred(lower_bound, upper_bound)
        if basis in {"unknown", "conflicted"} or revision_ref is None:
            raise ModelValidationError(
                "verified market information time requires versioned provenance"
            )
    else:
        if item["lower_bound"] is not None or item["upper_bound"] is not None:
            raise ModelValidationError(
                "unknown/conflicted information time cannot carry trusted bounds"
            )
        lower_bound = upper_bound = None
        if basis != status:
            raise ModelValidationError(
                "market information-time status and basis must agree"
            )
    return {
        "status": status,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "basis": basis,
        "method_version": "public_information_time.v1",
        "revision_ref": revision_ref,
    }


def _canonical_market_version_provenance_v2(value: object) -> dict[str, str]:
    item = _closed_object(
        value,
        name="status_axes.market.version_provenance",
        required={"status", "content_sha256", "source_ref", "revision_ref"},
    )
    status = _enum_text(
        item["status"],
        name="status_axes.market.version_provenance.status",
        allowed=frozenset({"verified", "unknown", "conflicted"}),
    )
    return {
        "status": status,
        "content_sha256": _sha256_content_id(
            item["content_sha256"],
            name="status_axes.market.version_provenance.content_sha256",
        ),
        "source_ref": _strict_text(
            item["source_ref"], "status_axes.market.version_provenance.source_ref"
        ),
        "revision_ref": _strict_text(
            item["revision_ref"],
            "status_axes.market.version_provenance.revision_ref",
        ),
    }


def _canonical_market_eligibility_v2(
    value: object,
    *,
    perspective: str,
    operation_anchor_at: str,
) -> dict[str, Any]:
    item = _closed_object(
        value,
        name="status_axes.market.perspective_eligibility",
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
    eligibility_perspective = _enum_text(
        item["perspective"],
        name="status_axes.market.perspective_eligibility.perspective",
        allowed=_PERSPECTIVES,
    )
    if eligibility_perspective != perspective:
        raise ModelValidationError("market eligibility perspective drift")
    eligibility_status = _enum_text(
        item["status"],
        name="status_axes.market.perspective_eligibility.status",
        allowed=frozenset({"eligible", "ineligible", "ambiguous", "unknown"}),
    )
    reason_code = _enum_text(
        item["reason_code"],
        name="status_axes.market.perspective_eligibility.reason_code",
        allowed=_MARKET_ELIGIBILITY_REASON_CODES_V2,
    )
    eligibility_role = _enum_text(
        item["temporal_role"],
        name="status_axes.market.perspective_eligibility.temporal_role",
        allowed=_MARKET_ELIGIBILITY_TEMPORAL_ROLES_V2,
    )
    eligibility_anchor = _aware_utc(
        item["operation_anchor_at"],
        name="status_axes.market.perspective_eligibility.operation_anchor_at",
    )
    if eligibility_anchor != operation_anchor_at:
        raise ModelValidationError("market eligibility operation anchor drift")
    projected_user = (
        None
        if item["projected_user_known_at"] is None
        else _aware_utc(
            item["projected_user_known_at"],
            name=(
                "status_axes.market.perspective_eligibility."
                "projected_user_known_at"
            ),
        )
    )
    projected_system = (
        None
        if item["projected_system_known_at"] is None
        else _aware_utc(
            item["projected_system_known_at"],
            name=(
                "status_axes.market.perspective_eligibility."
                "projected_system_known_at"
            ),
        )
    )
    if item["actual_user_observation_proven"] is not False:
        raise ModelValidationError(
            "public-information policy cannot prove actual user observation"
        )
    return {
        "perspective": eligibility_perspective,
        "status": eligibility_status,
        "reason_code": reason_code,
        "temporal_role": eligibility_role,
        "operation_anchor_at": eligibility_anchor,
        "projected_user_known_at": projected_user,
        "projected_system_known_at": projected_system,
        "actual_user_observation_proven": False,
    }


def _canonical_market_axis_v2(
    value: object,
    *,
    perspective: str,
    operation_anchor_at: str,
) -> dict[str, Any]:
    item = _closed_object(
        value,
        name="status_axes.market",
        required={
            "status",
            "temporal_role",
            "perspective",
            "eligible_source_refs",
            "retrospective_source_refs",
            "unknown_source_refs",
            "effective_at",
            "publicly_available_at",
            "publicly_available_basis",
            "fetched_at",
            "system_observed_at",
            "representative_source_id",
            "representative_source_content_id",
            "information_time",
            "version_provenance",
            "perspective_eligibility",
            "market_evidence_manifest_content_id",
            "source_refs",
        },
        optional={"summary"},
    )
    status = _enum_text(
        item["status"], name="status_axes.market.status", allowed=_MARKET_STATUSES_V2
    )
    temporal_role = _enum_text(
        item["temporal_role"],
        name="status_axes.market.temporal_role",
        allowed=_MARKET_TEMPORAL_ROLES_V2,
    )
    axis_perspective = _enum_text(
        item["perspective"],
        name="status_axes.market.perspective",
        allowed=_PERSPECTIVES,
    )
    if axis_perspective != perspective:
        raise ModelValidationError(
            "status_axes.market perspective must match the checkpoint"
        )
    refs_by_role = {
        key: _string_set(item[key], name=f"status_axes.market.{key}")
        for key in (
            "eligible_source_refs",
            "retrospective_source_refs",
            "unknown_source_refs",
        )
    }
    role_sets = [set(refs) for refs in refs_by_role.values()]
    if any(role_sets[left].intersection(role_sets[right]) for left in range(3) for right in range(left + 1, 3)):
        raise ModelValidationError(
            "market eligible, retrospective and unknown source refs must be disjoint"
        )
    source_refs = _string_set(
        item["source_refs"], name="status_axes.market.source_refs"
    )
    classified_refs = set().union(*role_sets)
    if not classified_refs.issubset(set(source_refs)):
        raise ModelValidationError(
            "market source_refs must cover every perspective-classified source"
        )
    market_evidence_manifest_content_id = _sha256_content_id(
        item["market_evidence_manifest_content_id"],
        name="status_axes.market.market_evidence_manifest_content_id",
    )
    market_evidence_manifest_ref = (
        "market_evidence_manifest:" + market_evidence_manifest_content_id
    )
    if market_evidence_manifest_ref not in source_refs:
        raise ModelValidationError(
            "market source refs must bind the frozen evidence manifest"
        )
    representative_source_id = (
        None
        if item["representative_source_id"] is None
        else _strict_text(
            item["representative_source_id"],
            "status_axes.market.representative_source_id",
        )
    )
    if representative_source_id is None:
        if any(
            item[field] is not None
            for field in (
                "representative_source_content_id",
                "information_time",
                "version_provenance",
                "perspective_eligibility",
            )
        ):
            raise ModelValidationError(
                "source-less market axis cannot carry representative proof"
            )
        if classified_refs:
            raise ModelValidationError(
                "classified market sources require one representative proof"
            )
        representative_source_content_id = None
        information_time = None
        version_provenance = None
        perspective_eligibility = None
    else:
        if representative_source_id not in source_refs:
            raise ModelValidationError(
                "representative market source must be frozen in source_refs"
            )
        membership_count = sum(
            representative_source_id in role_set for role_set in role_sets
        )
        if membership_count != 1:
            raise ModelValidationError(
                "representative market source must have one perspective category"
            )
        if any(
            item[field] is None
            for field in (
                "representative_source_content_id",
                "information_time",
                "version_provenance",
                "perspective_eligibility",
            )
        ):
            raise ModelValidationError(
                "representative market source requires complete closed proof"
            )
        representative_source_content_id = _sha256_content_id(
            item["representative_source_content_id"],
            name="status_axes.market.representative_source_content_id",
        )
        information_time = _canonical_market_information_time_v2(
            item["information_time"]
        )
        version_provenance = _canonical_market_version_provenance_v2(
            item["version_provenance"]
        )
        perspective_eligibility = _canonical_market_eligibility_v2(
            item["perspective_eligibility"],
            perspective=perspective,
            operation_anchor_at=operation_anchor_at,
        )
        category_by_status = {
            "eligible": "eligible_source_refs",
            "ineligible": "retrospective_source_refs",
            "ambiguous": "unknown_source_refs",
            "unknown": "unknown_source_refs",
        }
        expected_category = category_by_status[perspective_eligibility["status"]]
        if representative_source_id not in refs_by_role[expected_category]:
            raise ModelValidationError(
                "representative source category disagrees with eligibility proof"
            )
    times = {
        key: (
            None
            if item[key] is None
            else _aware_utc(item[key], name=f"status_axes.market.{key}")
        )
        for key in (
            "effective_at",
            "publicly_available_at",
            "fetched_at",
            "system_observed_at",
        )
    }
    public_basis = _enum_text(
        item["publicly_available_basis"],
        name="status_axes.market.publicly_available_basis",
        allowed=_MARKET_PUBLIC_BASES_V2,
    )
    if representative_source_id is None:
        if (
            status != "missing"
            or temporal_role != "missing"
            or any(value is not None for value in times.values())
            or public_basis != "not_applicable"
        ):
            raise ModelValidationError(
                "source-less market axis must remain an explicit missing projection"
            )
    if representative_source_id is not None:
        if any(
            times[field] is None
            for field in ("effective_at", "fetched_at", "system_observed_at")
        ):
            raise ModelValidationError(
                "representative market source requires effective, fetched and observed times"
            )
        ensure_known_not_before_occurred(
            times["effective_at"], times["fetched_at"]
        )
        expected_axis_role = {
            "user_known_at_operation_by_verified_publication": (
                "user_known_at_operation_by_verified_publication"
            ),
            "system_known_at_operation": "system_known_at_operation",
            "retrospective_public_context": "retrospective_context",
            "publication_time_ambiguous": "ambiguous",
            "publication_time_unknown": "unknown",
            "system_observation_unknown": "unknown",
        }[perspective_eligibility["temporal_role"]]
        if temporal_role != expected_axis_role:
            raise ModelValidationError(
                "market temporal role disagrees with representative eligibility"
            )
        expected_eligibility_status = {
            "user_known_at_operation_by_verified_publication": "eligible",
            "system_known_at_operation": "eligible",
            "retrospective_public_context": "ineligible",
            "publication_time_ambiguous": "ambiguous",
            "publication_time_unknown": "unknown",
            "system_observation_unknown": "unknown",
        }[perspective_eligibility["temporal_role"]]
        if perspective_eligibility["status"] != expected_eligibility_status:
            raise ModelValidationError(
                "market eligibility status and temporal role disagree"
            )
        allowed_reasons_by_role = {
            "user_known_at_operation_by_verified_publication": frozenset(
                {"verified_publication_strictly_before_operation"}
            ),
            "system_known_at_operation": frozenset(
                {"system_observed_no_later_than_operation"}
            ),
            "retrospective_public_context": frozenset(
                {"post_operation_publication", "system_observed_after_operation"}
            ),
            "publication_time_ambiguous": frozenset(
                {
                    "publication_time_or_revision_conflicted",
                    "publication_revision_binding_conflicted",
                    "publication_interval_touches_operation_anchor",
                }
            ),
            "publication_time_unknown": frozenset(
                {
                    "current_only_not_point_in_time",
                    "publication_time_or_revision_unproven",
                }
            ),
            "system_observation_unknown": frozenset(
                {"system_observation_unknown"}
            ),
        }
        if perspective_eligibility["reason_code"] not in allowed_reasons_by_role[
            perspective_eligibility["temporal_role"]
        ]:
            raise ModelValidationError(
                "market eligibility reason and temporal role disagree"
            )
        if information_time["status"] == "verified":
            expected_public_basis = {
                "exchange_bar_publication_time.v1": "exchange_calendar",
                "provider_exact_publication_time.v1": "provider_declared",
                "provider_publication_date_source_timezone.v1": (
                    "verified_publication_interval"
                ),
            }[information_time["basis"]]
            if (
                times["publicly_available_at"] != information_time["upper_bound"]
                or public_basis != expected_public_basis
            ):
                raise ModelValidationError(
                    "market public-time projection disagrees with representative proof"
                )
        elif times["publicly_available_at"] is not None or public_basis != "unknown":
            raise ModelValidationError(
                "unverified market information time cannot project public availability"
            )
        eligibility_role = perspective_eligibility["temporal_role"]
        projected_user = perspective_eligibility["projected_user_known_at"]
        projected_system = perspective_eligibility["projected_system_known_at"]
        if eligibility_role == "user_known_at_operation_by_verified_publication":
            if (
                perspective != "user"
                or information_time["status"] != "verified"
                or version_provenance["status"] != "verified"
                or information_time["revision_ref"]
                != version_provenance["revision_ref"]
                or information_time["upper_bound"] >= operation_anchor_at
                or projected_user != operation_anchor_at
                or projected_system is not None
            ):
                raise ModelValidationError(
                    "policy-known user market proof is not strictly pre-operation"
                )
        elif eligibility_role == "system_known_at_operation":
            if (
                perspective != "system"
                or projected_system is None
                or projected_system > operation_anchor_at
                or projected_system != times["system_observed_at"]
                or projected_user is not None
            ):
                raise ModelValidationError(
                    "system-known market proof lacks timely real observation"
                )
        elif projected_user is not None or projected_system is not None:
            raise ModelValidationError(
                "ineligible or uncertain market proof cannot project known time"
            )
    if times["effective_at"] is not None and times["publicly_available_at"] is not None:
        ensure_known_not_before_occurred(
            times["effective_at"], times["publicly_available_at"]
        )
    if times["fetched_at"] is not None and times["system_observed_at"] is not None:
        ensure_known_not_before_occurred(
            times["fetched_at"], times["system_observed_at"]
        )
    if status in {"available", "partial", "stale", "insufficient"} and not source_refs:
        raise ModelValidationError(
            "material market states require explicit source references"
        )
    if status == "available" and (
        times["effective_at"] is None or not refs_by_role["eligible_source_refs"]
    ):
        raise ModelValidationError(
            "market available requires effective time and perspective-eligible evidence"
        )
    if temporal_role == "user_known_at_operation_by_verified_publication":
        if perspective != "user" or not refs_by_role["eligible_source_refs"]:
            raise ModelValidationError(
                "publication-policy known role requires user perspective and eligible evidence"
            )
        public_at = times["publicly_available_at"]
        if public_at is None or public_at >= operation_anchor_at:
            raise ModelValidationError(
                "verified publication must be strictly before the operation anchor"
            )
    if temporal_role == "system_known_at_operation":
        observed = times["system_observed_at"]
        if (
            perspective != "system"
            or observed is None
            or observed > operation_anchor_at
            or not refs_by_role["eligible_source_refs"]
        ):
            raise ModelValidationError(
                "system known role requires real observation no later than the operation anchor"
            )
    if temporal_role == "retrospective_context" and not refs_by_role[
        "retrospective_source_refs"
    ]:
        raise ModelValidationError(
            "retrospective market role requires retrospective source references"
        )
    if temporal_role in {"ambiguous", "unknown"} and not refs_by_role[
        "unknown_source_refs"
    ]:
        raise ModelValidationError(
            "ambiguous or unknown market role requires unknown source references"
        )
    result: dict[str, Any] = {
        "status": status,
        "temporal_role": temporal_role,
        "perspective": axis_perspective,
        **refs_by_role,
        **times,
        "publicly_available_basis": public_basis,
        "representative_source_id": representative_source_id,
        "representative_source_content_id": representative_source_content_id,
        "information_time": information_time,
        "version_provenance": version_provenance,
        "perspective_eligibility": perspective_eligibility,
        "market_evidence_manifest_content_id": (
            market_evidence_manifest_content_id
        ),
        "source_refs": source_refs,
    }
    if item.get("summary") is not None:
        result["summary"] = _strict_text(
            item["summary"], "status_axes.market.summary"
        )
    return result


def _canonical_market_receipt_v2(value: object, *, index: int) -> dict[str, Any]:
    receipt = _closed_object(
        value,
        name=f"market_fallback.fetch_receipts[{index}]",
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
    provider_id = _strict_text(
        receipt["provider_id"], f"fetch_receipts[{index}].provider_id"
    )
    endpoint_id = _strict_text(
        receipt["endpoint_id"], f"fetch_receipts[{index}].endpoint_id"
    )
    provider_endpoint = f"{provider_id}:{endpoint_id}"
    if provider_endpoint not in MARKET_PROVIDER_ALLOWLIST:
        raise ModelValidationError(
            "v2 market fetch receipt provider/endpoint is not allowlisted"
        )
    parameters = receipt["redacted_parameters"]
    if not isinstance(parameters, Mapping):
        raise ModelValidationError(
            f"fetch_receipts[{index}].redacted_parameters must be an object"
        )
    canonical_parameters: dict[str, str] = {}
    for raw_key, raw_value in parameters.items():
        key = _strict_text(raw_key, f"fetch_receipts[{index}] parameter key")
        if re.search(MARKET_PROVIDER_SENSITIVE_PARAMETER_PATTERN, key, re.I):
            raise ModelValidationError(
                "v2 market fetch receipt parameters must not contain secret fields"
            )
        if key not in MARKET_PROVIDER_PARAMETER_ALLOWLIST[provider_endpoint]:
            raise ModelValidationError(
                "v2 market fetch receipt parameter is not allowlisted for "
                f"{provider_endpoint}: {key}"
            )
        if key in canonical_parameters:
            raise ModelValidationError(
                "v2 market fetch receipt parameters contain duplicate normalized keys"
            )
        canonical_parameters[key] = _canonical_market_parameter_value(
            raw_value,
            key=key,
            name=f"fetch_receipts[{index}].redacted_parameters.{key}",
        )
    provider_version = _strict_text(
        receipt["provider_version"], f"fetch_receipts[{index}].provider_version"
    )
    if receipt["request_fingerprint_version"] != MARKET_REQUEST_FINGERPRINT_VERSION:
        raise ModelValidationError("Unsupported v2 market request fingerprint version")
    fingerprint = _strict_text(
        receipt["request_fingerprint"],
        f"fetch_receipts[{index}].request_fingerprint",
    )
    if fingerprint != market_request_fingerprint(
        provider_id=provider_id,
        endpoint_id=endpoint_id,
        provider_version=provider_version,
        redacted_parameters=canonical_parameters,
    ):
        raise ModelValidationError(
            "v2 market request fingerprint does not match canonical request"
        )
    response_status = _enum_text(
        receipt["response_status"],
        name=f"fetch_receipts[{index}].response_status",
        allowed=frozenset(
            {
                "succeeded",
                "failed",
                "timeout",
                "rejected",
                "provider_unavailable",
                "withheld_by_cutoff",
                "budget_exhausted",
            }
        ),
    )
    attempt_count = receipt["attempt_count"]
    if (
        isinstance(attempt_count, bool)
        or not isinstance(attempt_count, int)
        or not 0 <= attempt_count <= 3
    ):
        raise ModelValidationError(
            "v2 market fetch receipt attempt_count must be between 0 and 3"
        )
    attempt_count_status = _enum_text(
        receipt["attempt_count_status"],
        name=f"fetch_receipts[{index}].attempt_count_status",
        allowed=frozenset({"verified", "unknown"}),
    )
    budget_charged_attempts = receipt["budget_charged_attempts"]
    if (
        isinstance(budget_charged_attempts, bool)
        or not isinstance(budget_charged_attempts, int)
        or not 0 <= budget_charged_attempts <= 3
    ):
        raise ModelValidationError(
            "v2 receipt budget_charged_attempts must be between 0 and 3"
        )
    if attempt_count_status == "verified":
        if budget_charged_attempts != attempt_count:
            raise ModelValidationError(
                "verified v2 receipt must charge its exact attempt count"
            )
    elif (
        response_status != "failed"
        or attempt_count != 0
        or budget_charged_attempts < 1
    ):
        raise ModelValidationError(
            "unknown attempt count is only valid for bounded failed acquisition"
        )
    guard_audit_at = _aware_utc(
        receipt["guard_audit_at"],
        name=f"fetch_receipts[{index}].guard_audit_at",
    )
    submitted_cache_entry_refs = _string_set(
        receipt["cache_entry_refs"],
        name=f"fetch_receipts[{index}].cache_entry_refs",
    )
    zero_status = response_status in {
        "provider_unavailable",
        "withheld_by_cutoff",
        "budget_exhausted",
    }
    if zero_status:
        started_at = _aware_utc(
            receipt["started_at"], name=f"fetch_receipts[{index}].started_at"
        )
        completed_at = _aware_utc(
            receipt["completed_at"], name=f"fetch_receipts[{index}].completed_at"
        )
        if started_at != guard_audit_at or completed_at != guard_audit_at:
            raise ModelValidationError(
                "zero-attempt v2 guard receipt must bind start/completion to guard audit"
            )
        if (
            attempt_count != 0
            or attempt_count_status != "verified"
            or budget_charged_attempts != 0
            or receipt["fetched_at"] is not None
            or receipt["system_observed_at"] is not None
            or receipt["raw_content_sha256"] is not None
            or receipt["normalized_content_sha256"] is not None
            or submitted_cache_entry_refs
        ):
            raise ModelValidationError(
                "zero-attempt v2 guard receipt cannot carry acquisition evidence"
            )
        fetched_at = None
        system_observed_at = None
        raw_hash = None
        normalized_hash = None
        cache_entry_refs: list[str] = []
    else:
        if attempt_count_status == "verified" and attempt_count < 1:
            raise ModelValidationError(
                "attempted v2 market receipt requires at least one HTTP attempt"
            )
        started_at = _aware_utc(
            receipt["started_at"], name=f"fetch_receipts[{index}].started_at"
        )
        completed_at = _aware_utc(
            receipt["completed_at"], name=f"fetch_receipts[{index}].completed_at"
        )
        ensure_known_not_before_occurred(started_at, completed_at)
        ensure_known_not_before_occurred(guard_audit_at, started_at)
        system_observed_at = _aware_utc(
            receipt["system_observed_at"],
            name=f"fetch_receipts[{index}].system_observed_at",
        )
        ensure_known_not_before_occurred(started_at, system_observed_at)
        ensure_known_not_before_occurred(system_observed_at, completed_at)
        fetched_at = (
            None
            if receipt["fetched_at"] is None
            else _aware_utc(
                receipt["fetched_at"], name=f"fetch_receipts[{index}].fetched_at"
            )
        )
        if fetched_at is not None:
            ensure_known_not_before_occurred(started_at, fetched_at)
            ensure_known_not_before_occurred(fetched_at, system_observed_at)
        raw_hash = receipt["raw_content_sha256"]
        normalized_hash = receipt["normalized_content_sha256"]
        for label, hash_value in (
            ("raw_content_sha256", raw_hash),
            ("normalized_content_sha256", normalized_hash),
        ):
            if hash_value is not None and re.fullmatch(
                r"sha256:[0-9a-f]{64}", str(hash_value)
            ) is None:
                raise ModelValidationError(
                    f"v2 market fetch receipt {label} must be SHA-256 or null"
                )
        cache_entry_refs = submitted_cache_entry_refs
        if response_status == "succeeded":
            if (
                fetched_at is None
                or raw_hash is None
                or normalized_hash is None
                or not cache_entry_refs
            ):
                raise ModelValidationError(
                    "successful v2 market receipt lacks fetched/hash/cache evidence"
                )
        elif cache_entry_refs or raw_hash is not None or normalized_hash is not None:
            raise ModelValidationError(
                "failed v2 market receipt cannot carry successful cache evidence"
            )
        if attempt_count_status == "unknown" and fetched_at is not None:
            raise ModelValidationError(
                "unknown-count failed v2 receipt cannot claim fetched content"
            )
    cache_lineage = _string_set(
        receipt["cache_lineage"], name=f"fetch_receipts[{index}].cache_lineage"
    )
    if not cache_lineage:
        raise ModelValidationError(
            "every v2 market receipt must bind the triggering requirement"
        )
    canonical = {
        "receipt_id": _strict_text(
            receipt["receipt_id"], f"fetch_receipts[{index}].receipt_id"
        ),
        "provider_id": provider_id,
        "endpoint_id": endpoint_id,
        "provider_version": provider_version,
        "redacted_parameters": dict(sorted(canonical_parameters.items())),
        "request_fingerprint_version": MARKET_REQUEST_FINGERPRINT_VERSION,
        "request_fingerprint": fingerprint,
        "guard_audit_at": guard_audit_at,
        "started_at": started_at,
        "completed_at": completed_at,
        "fetched_at": fetched_at,
        "system_observed_at": system_observed_at,
        "response_status": response_status,
        "attempt_count": attempt_count,
        "attempt_count_status": attempt_count_status,
        "budget_charged_attempts": budget_charged_attempts,
        "raw_content_sha256": raw_hash,
        "normalized_content_sha256": normalized_hash,
        "cache_entry_refs": cache_entry_refs,
        "cache_lineage": cache_lineage,
    }
    identity_material = dict(canonical)
    identity_material["receipt_id"] = ""
    expected_receipt_id = "market_fetch_receipt_v2_" + hashlib.sha256(
        canonical_json_bytes(identity_material)
    ).hexdigest()
    if canonical["receipt_id"] != expected_receipt_id:
        raise ModelValidationError("v2 market fetch receipt identity drift")
    return canonical


def _canonical_market_fallback_v2(
    value: object,
    *,
    perspective: str,
) -> dict[str, Any]:
    item = _closed_object(
        value,
        name="market_fallback",
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
    if item["policy_version"] != MARKET_FALLBACK_POLICY_VERSION_V2:
        raise ModelValidationError("Unsupported v2 market fallback policy version")
    if item["public_information_policy_version"] != PUBLIC_INFORMATION_POLICY_VERSION:
        raise ModelValidationError("Unsupported public information policy version")
    fallback_perspective = _enum_text(
        item["perspective"],
        name="market_fallback.perspective",
        allowed=_PERSPECTIVES,
    )
    if fallback_perspective != perspective:
        raise ModelValidationError(
            "market_fallback perspective must match the checkpoint"
        )
    if item["allowlist_version"] != MARKET_PROVIDER_ALLOWLIST_VERSION:
        raise ModelValidationError("v2 market fallback allowlist version drift")
    if item["allowlist_sha256"] != MARKET_PROVIDER_ALLOWLIST_SHA256:
        raise ModelValidationError("v2 market fallback allowlist hash drift")
    limits = _closed_object(
        item["limits"],
        name="market_fallback.limits",
        required={
            "timeout_seconds",
            "max_retries",
            "max_concurrency",
            "max_requests_per_run",
        },
    )
    expected_limits = {
        "timeout_seconds": 20,
        "max_retries": 2,
        "max_concurrency": 2,
        "max_requests_per_run": 20,
    }
    if limits != expected_limits:
        raise ModelValidationError("v2 market fallback frozen limits drift")
    allowlist = _string_set(item["allowlist"], name="market_fallback.allowlist")
    if frozenset(allowlist) != MARKET_PROVIDER_ALLOWLIST:
        raise ModelValidationError("v2 market fallback frozen allowlist drift")
    offline = _closed_object(
        item["offline_consumers"],
        name="market_fallback.offline_consumers",
        required={"renderer", "source_replay", "api", "ui"},
    )
    if any(value is not False for value in offline.values()):
        raise ModelValidationError("v2 market fallback consumers must remain offline")
    coverage_before = _enum_text(
        item["coverage_before"],
        name="market_fallback.coverage_before",
        allowed=_MARKET_COVERAGE_STATES,
    )
    coverage_after = _enum_text(
        item["coverage_after"],
        name="market_fallback.coverage_after",
        allowed=_MARKET_COVERAGE_STATES,
    )
    status = _enum_text(
        item["status"],
        name="market_fallback.status",
        allowed=_MARKET_FALLBACK_STATUSES_V2,
    )
    limitation_code = item["limitation_code"]
    if limitation_code is not None:
        limitation_code = _enum_text(
            limitation_code,
            name="market_fallback.limitation_code",
            allowed=_MARKET_LIMITATION_CODES_V2,
        )
    guard_audit_at = (
        None
        if item["guard_audit_at"] is None
        else _aware_utc(item["guard_audit_at"], name="market_fallback.guard_audit_at")
    )
    receipts_input = item["fetch_receipts"]
    if not isinstance(receipts_input, (list, tuple)) or len(receipts_input) > 20:
        raise ModelValidationError("v2 market fallback receipts must be a bounded array")
    receipts = sorted(
        (
            _canonical_market_receipt_v2(raw_receipt, index=index)
            for index, raw_receipt in enumerate(receipts_input)
        ),
        key=lambda receipt: receipt["receipt_id"],
    )
    receipt_refs = _string_set(
        item["fetch_receipt_refs"], name="market_fallback.fetch_receipt_refs"
    )
    if receipt_refs != [receipt["receipt_id"] for receipt in receipts]:
        raise ModelValidationError(
            "v2 market fallback receipt refs must bind embedded receipts"
        )
    request_count = item["request_count"]
    verified_attempt_count = sum(
        receipt["attempt_count"]
        for receipt in receipts
        if receipt["attempt_count_status"] == "verified"
    )
    unverified_attempt_upper_bound = item["unverified_attempt_upper_bound"]
    expected_unverified_upper_bound = sum(
        receipt["budget_charged_attempts"]
        for receipt in receipts
        if receipt["attempt_count_status"] == "unknown"
    )
    if (
        isinstance(request_count, bool)
        or not isinstance(request_count, int)
        or request_count != verified_attempt_count
        or isinstance(unverified_attempt_upper_bound, bool)
        or not isinstance(unverified_attempt_upper_bound, int)
        or unverified_attempt_upper_bound != expected_unverified_upper_bound
        or request_count + unverified_attempt_upper_bound
        > expected_limits["max_requests_per_run"]
    ):
        raise ModelValidationError("v2 market fallback request count drift")
    request_count_status = _enum_text(
        item["request_count_status"],
        name="market_fallback.request_count_status",
        allowed=frozenset({"verified", "bounded_unknown"}),
    )
    expected_request_count_status = (
        "bounded_unknown" if expected_unverified_upper_bound else "verified"
    )
    if request_count_status != expected_request_count_status:
        raise ModelValidationError("v2 market fallback request count status drift")
    cache_refs = _string_set(item["cache_refs"], name="market_fallback.cache_refs")
    successful = [
        receipt for receipt in receipts if receipt["response_status"] == "succeeded"
    ]
    successful_cache_refs = {
        cache_ref for receipt in successful for cache_ref in receipt["cache_entry_refs"]
    }
    if not successful_cache_refs.issubset(set(cache_refs)):
        raise ModelValidationError(
            "v2 market fallback cache refs omit successful receipt evidence"
        )
    if expected_unverified_upper_bound:
        expected_limitation = "provider_attempt_count_unknown"
    else:
        expected_limitation = {
            "provider_unavailable": "provider_unavailable",
            "withheld_by_cutoff": "withheld_by_cutoff",
            "budget_exhausted": "budget_exhausted",
        }.get(status)
    if limitation_code != expected_limitation:
        raise ModelValidationError("v2 market fallback limitation/status drift")
    zero_statuses = {
        "not_needed",
        "provider_unavailable",
        "withheld_by_cutoff",
        "budget_exhausted",
    }
    if status in zero_statuses and request_count != 0:
        raise ModelValidationError("zero-request v2 fallback contains HTTP attempts")
    if status == "not_needed":
        if coverage_before != "satisfied" or coverage_after != "satisfied":
            raise ModelValidationError("v2 not_needed requires satisfied local coverage")
        if receipts or guard_audit_at is not None or not cache_refs:
            raise ModelValidationError(
                "v2 not_needed requires only frozen local source references"
            )
    elif status in {"provider_unavailable", "withheld_by_cutoff", "budget_exhausted"}:
        if (
            coverage_before not in _FALLBACK_TRIGGER_STATES
            or coverage_after != coverage_before
        ):
            raise ModelValidationError(
                "v2 zero-request limitation cannot change coverage"
            )
        if status == "withheld_by_cutoff" and perspective != "system":
            raise ModelValidationError(
                "withheld_by_cutoff is restricted to system perspective"
            )
        if (
            guard_audit_at is None
            or len(receipts) != 1
            or receipts[0]["response_status"] != status
            or receipts[0]["guard_audit_at"] != guard_audit_at
        ):
            raise ModelValidationError(
                "v2 zero-request limitation requires one matching guard receipt"
            )
    else:
        if guard_audit_at is not None or coverage_before not in _FALLBACK_TRIGGER_STATES:
            raise ModelValidationError("attempted v2 fallback has invalid trigger/guard")
        if status == "succeeded" and (not successful or request_count == 0):
            raise ModelValidationError(
                "successful v2 fallback requires a successful attempted receipt"
            )
        if status == "failed" and (
            not receipts
            or successful
            or request_count + unverified_attempt_upper_bound == 0
            or coverage_after != coverage_before
        ):
            raise ModelValidationError(
                "failed v2 fallback requires attempted receipts and no success"
            )
    return {
        "policy_version": MARKET_FALLBACK_POLICY_VERSION_V2,
        "public_information_policy_version": PUBLIC_INFORMATION_POLICY_VERSION,
        "perspective": fallback_perspective,
        "allowlist_version": MARKET_PROVIDER_ALLOWLIST_VERSION,
        "allowlist_sha256": MARKET_PROVIDER_ALLOWLIST_SHA256,
        "coverage_before": coverage_before,
        "coverage_after": coverage_after,
        "status": status,
        "limitation_code": limitation_code,
        "guard_audit_at": guard_audit_at,
        "request_count": request_count,
        "request_count_status": request_count_status,
        "unverified_attempt_upper_bound": unverified_attempt_upper_bound,
        "limits": expected_limits,
        "allowlist": allowlist,
        "cache_refs": cache_refs,
        "fetch_receipt_refs": receipt_refs,
        "fetch_receipts": receipts,
        "offline_consumers": {
            "renderer": False,
            "source_replay": False,
            "api": False,
            "ui": False,
        },
    }


def _canonical_operation_anchor_ordering_key(
    value: object,
    *,
    event_id: str,
    anchor_at: str,
) -> list[Any]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ModelValidationError(
            "operation_anchor_ordering_key must contain exactly four fields"
        )
    ordering_at = _aware_utc(value[0], name="operation_anchor_ordering_key[0]")
    sequence_rank = value[1]
    if isinstance(sequence_rank, bool) or not isinstance(sequence_rank, int):
        raise ModelValidationError(
            "operation_anchor_ordering_key[1] must be an integer"
        )
    sequence_value = _strict_text(
        value[2], "operation_anchor_ordering_key[2]"
    )
    closing_event_id = _strict_text(
        value[3], "operation_anchor_ordering_key[3]"
    )
    if ordering_at != anchor_at or closing_event_id != event_id:
        raise ModelValidationError(
            "operation anchor ordering key must close over anchor time and event ID"
        )
    return [ordering_at, sequence_rank, sequence_value, closing_event_id]


@dataclass(frozen=True)
class OperationCheckpointRecordV2:
    """Closed v2 checkpoint with explicit operation and information-time identity."""

    payload: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "OperationCheckpointRecordV2":
        root = _closed_object(
            value,
            name="operation checkpoint v2",
            required={
                "schema_version",
                "episode_id",
                "position_case_id",
                "review_kind",
                "checkpoint_type",
                "perspective",
                "operation_anchor_event_id",
                "operation_anchor_at",
                "operation_anchor_ordering_key",
                "as_of",
                "knowledge_cutoff",
                "information_time_policy_version",
                "time_provenance",
                "status_axes",
                "market_fallback",
                "gaps",
                "source_refs",
                "governance",
            },
            optional={
                "checkpoint_id",
                "checkpoint_key",
                "content_id",
            },
        )
        if root["schema_version"] != OPERATION_CHECKPOINT_SCHEMA_VERSION_V2:
            raise ModelValidationError("Unsupported operation checkpoint v2 schema")
        if root["information_time_policy_version"] != PUBLIC_INFORMATION_POLICY_VERSION:
            raise ModelValidationError("Unsupported operation information-time policy")

        perspective = _enum_text(
            root["perspective"], name="perspective", allowed=_PERSPECTIVES
        )
        anchor_event_id = _strict_text(
            root["operation_anchor_event_id"], "operation_anchor_event_id"
        )
        anchor_at = _aware_utc(root["operation_anchor_at"], name="operation_anchor_at")
        anchor_ordering_key = _canonical_operation_anchor_ordering_key(
            root["operation_anchor_ordering_key"],
            event_id=anchor_event_id,
            anchor_at=anchor_at,
        )
        as_of = _aware_utc(root["as_of"], name="as_of")
        knowledge_cutoff = _aware_utc(
            root["knowledge_cutoff"], name="knowledge_cutoff"
        )
        ensure_known_not_before_occurred(anchor_at, as_of)
        ensure_known_not_before_occurred(as_of, knowledge_cutoff)

        axes_input = _closed_object(
            root["status_axes"],
            name="status_axes",
            required=set(REVIEWABILITY_STATUS_AXES),
        )
        market_axis = _canonical_market_axis_v2(
            axes_input["market"],
            perspective=perspective,
            operation_anchor_at=anchor_at,
        )
        fallback = _canonical_market_fallback_v2(
            root["market_fallback"], perspective=perspective
        )

        sentinel_ref = "market:v2-common-validation"
        shadow_axes = dict(axes_input)
        shadow_axes["market"] = {
            "status": "available",
            "temporal_role": "system_known_at_decision",
            "effective_at": anchor_at,
            "publicly_available_at": None,
            "publicly_available_basis": "unknown",
            "fetched_at": None,
            "system_observed_at": anchor_at,
            "source_refs": [sentinel_ref],
        }
        shadow_fallback = {
            "policy_version": MARKET_FALLBACK_POLICY_VERSION,
            "allowlist_version": MARKET_PROVIDER_ALLOWLIST_VERSION,
            "allowlist_sha256": MARKET_PROVIDER_ALLOWLIST_SHA256,
            "coverage_before": "satisfied",
            "coverage_after": "satisfied",
            "status": "not_needed",
            "request_count": 0,
            "limits": {
                "timeout_seconds": 20,
                "max_retries": 2,
                "max_concurrency": 2,
                "max_requests_per_run": 20,
            },
            "allowlist": sorted(MARKET_PROVIDER_ALLOWLIST),
            "cache_refs": [sentinel_ref],
            "fetch_receipt_refs": [],
            "fetch_receipts": [],
            "offline_consumers": {
                "renderer": False,
                "source_replay": False,
                "api": False,
                "ui": False,
            },
        }
        shadow_gaps = [
            gap
            for gap in root["gaps"]
            if not isinstance(gap, Mapping) or gap.get("axis") != "market"
        ]
        shadow_source_refs = sorted(
            set(_string_set(root["source_refs"], name="source_refs"))
            | {sentinel_ref}
        )
        shadow = {
            "schema_version": OPERATION_CHECKPOINT_SCHEMA_VERSION,
            "episode_id": root["episode_id"],
            "position_case_id": root["position_case_id"],
            "review_kind": root["review_kind"],
            "checkpoint_type": root["checkpoint_type"],
            "perspective": perspective,
            "as_of": as_of,
            "knowledge_cutoff": knowledge_cutoff,
            "time_provenance": root["time_provenance"],
            "status_axes": shadow_axes,
            "market_fallback": shadow_fallback,
            "gaps": shadow_gaps,
            "source_refs": shadow_source_refs,
            "governance": root["governance"],
        }
        common = OperationCheckpointRecord.from_mapping(shadow).to_dict()
        if common["time_provenance"]["effective_at"]["value"] != anchor_at:
            raise ModelValidationError(
                "operation anchor time must equal anchor event effective time"
            )

        gaps = _canonical_gaps(root["gaps"])
        status_axes = dict(common["status_axes"])
        status_axes["market"] = market_axis
        coverage_market_states = {
            "satisfied": frozenset({"available"}),
            "missing": frozenset({"missing", "failed"}),
            "stale": frozenset({"stale", "failed"}),
            "insufficient": frozenset(
                {"insufficient", "partial", "failed"}
            ),
        }
        if market_axis["status"] not in coverage_market_states[fallback["coverage_after"]]:
            raise ModelValidationError(
                "market axis status is inconsistent with perspective coverage_after"
            )
        if not set(fallback["cache_refs"]).issubset(set(market_axis["source_refs"])):
            raise ModelValidationError(
                "market source refs must include every frozen fallback cache ref"
            )
        blocking_status = {
            "operation": "blocked",
            "decision": "blocked",
            "snapshot_cash_valuation": "blocked",
            "market": "failed",
            "lifecycle": "ambiguous",
            "outcome": "missing",
        }
        blocked_gap_axes = {gap["axis"] for gap in gaps if gap["blocks_axis"]}
        for gap in gaps:
            if gap["blocks_axis"] and (
                gap["severity"] != "blocker"
                or not gap["source_refs"]
                or status_axes[gap["axis"]]["status"]
                != blocking_status[gap["axis"]]
            ):
                raise ModelValidationError(
                    "axis-blocking gaps require blocker severity, evidence and a blocked axis state"
                )
            if gap["severity"] == "blocker" and not gap["blocks_axis"]:
                raise ModelValidationError(
                    "blocker severity must explicitly block its axis"
                )
        for axis, blocked_state in blocking_status.items():
            if status_axes[axis]["status"] == blocked_state and axis not in blocked_gap_axes:
                raise ModelValidationError(
                    f"blocked {axis} axis requires an explicit blocker gap"
                )

        episode_id = _strict_text(root["episode_id"], "episode_id")
        position_case_id = _strict_text(root["position_case_id"], "position_case_id")
        review_kind = common["review_kind"]
        checkpoint_type = common["checkpoint_type"]
        source_refs = _string_set(root["source_refs"], name="source_refs")
        if not source_refs:
            raise ModelValidationError(
                "operation checkpoint requires root source references"
            )
        identity_material = {
            "episode_id": episode_id,
            "review_kind": review_kind,
            "checkpoint_type": checkpoint_type,
            "perspective": perspective,
            "operation_anchor_event_id": anchor_event_id,
            "operation_anchor_at": anchor_at,
            "operation_anchor_ordering_key": anchor_ordering_key,
            "as_of": as_of,
            "knowledge_cutoff": knowledge_cutoff,
            "information_time_policy_version": PUBLIC_INFORMATION_POLICY_VERSION,
        }
        identity_digest = hashlib.sha256(
            canonical_json_bytes(identity_material)
        ).hexdigest()
        checkpoint_key = f"review_checkpoint_key_{identity_digest}"
        if root.get("checkpoint_key") not in (None, checkpoint_key):
            raise ModelValidationError(
                "checkpoint_key does not match canonical v2 semantic identity"
            )
        normalized: dict[str, Any] = {
            "schema_version": OPERATION_CHECKPOINT_SCHEMA_VERSION_V2,
            "checkpoint_key": checkpoint_key,
            "episode_id": episode_id,
            "position_case_id": position_case_id,
            "review_kind": review_kind,
            "checkpoint_type": checkpoint_type,
            "perspective": perspective,
            "operation_anchor_event_id": anchor_event_id,
            "operation_anchor_at": anchor_at,
            "operation_anchor_ordering_key": anchor_ordering_key,
            "as_of": as_of,
            "knowledge_cutoff": knowledge_cutoff,
            "information_time_policy_version": PUBLIC_INFORMATION_POLICY_VERSION,
            "time_provenance": common["time_provenance"],
            "status_axes": status_axes,
            "market_fallback": fallback,
            "gaps": gaps,
            "source_refs": source_refs,
            "governance": common["governance"],
        }
        checkpoint_id = "review_checkpoint_" + identity_digest[:32]
        if root.get("checkpoint_id") not in (None, checkpoint_id):
            raise ModelValidationError("checkpoint_id does not match canonical v2 identity")
        normalized["checkpoint_id"] = checkpoint_id
        content_id = "sha256:" + hashlib.sha256(
            canonical_json_bytes(normalized)
        ).hexdigest()
        if root.get("content_id") not in (None, content_id):
            raise ModelValidationError("content_id does not match canonical v2 content")
        normalized["content_id"] = content_id
        detached = json.loads(canonical_json_bytes(normalized).decode("utf-8"))
        return cls(payload=detached)

    @property
    def checkpoint_id(self) -> str:
        return str(self.payload["checkpoint_id"])

    @property
    def checkpoint_key(self) -> str:
        return str(self.payload["checkpoint_key"])

    @property
    def content_id(self) -> str:
        return str(self.payload["content_id"])

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.canonical_bytes.decode("utf-8"))


OperationCheckpointRecordAny = OperationCheckpointRecord | OperationCheckpointRecordV2


def operation_checkpoint_from_mapping(
    value: Mapping[str, Any],
) -> OperationCheckpointRecordAny:
    """Dispatch without allowing either schema to reinterpret the other."""

    schema_version = value.get("schema_version", OPERATION_CHECKPOINT_SCHEMA_VERSION)
    if schema_version == OPERATION_CHECKPOINT_SCHEMA_VERSION:
        return OperationCheckpointRecord.from_mapping(value)
    if schema_version == OPERATION_CHECKPOINT_SCHEMA_VERSION_V2:
        return OperationCheckpointRecordV2.from_mapping(value)
    raise ModelValidationError("Unsupported operation checkpoint schema")
