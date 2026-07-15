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
