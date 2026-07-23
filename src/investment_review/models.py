"""Canonical objects used by the Phase 1 review data layer."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .time_utils import ensure_known_not_before_occurred, utc_iso


class ModelValidationError(ValueError):
    """Raised when canonical data violates the review contract."""


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


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
