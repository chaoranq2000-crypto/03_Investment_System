"""Deterministic, evidence-preserving fee projections.

This module intentionally implements one small method only.  A source fee is
``actual`` only when the caller explicitly marks it as such and its amount is
positive.  Missing or zero source fees are never silently promoted to actual
fees.  They may be projected from confirmed actual observations, while the
source value remains unchanged in the returned projection.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence


FEE_METHOD = "historical_median_rate"
FEE_METHOD_VERSION = "historical_median_rate_v1"
SOURCE_ACTUAL_METHOD = "source_fee"
SOURCE_ACTUAL_METHOD_VERSION = "source_fee_actual_v1"
MIN_SAMPLE_COUNT = 5
MONEY_QUANTUM = Decimal("0.01")
SUPPORTED_ASSET_TYPES = frozenset({"equity", "etf"})
SUPPORTED_SIDES = frozenset({"BUY", "SELL"})
SUPPORTED_CURRENCY = "CNY"


class FeeEstimationError(ValueError):
    """Raised when fee inputs do not have stable identities or conflict."""


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        number = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            number = Decimal(text)
        except (InvalidOperation, ValueError):
            return None
    return number if number.is_finite() else None


def _decimal_text(value: Decimal) -> str:
    """Return a stable, non-exponent Decimal representation."""

    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _money_text(value: Decimal) -> str:
    return format(value, ".2f")


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    # Round-trip through canonical JSON so nested Decimal and tuple values are
    # safe for persistence and caller-owned nested containers cannot mutate a
    # projection after its identity has been calculated.
    safe_value = json.loads(_canonical_json(dict(value or {})))
    return MappingProxyType(safe_value)


def _require_fixed_sample_count(value: int) -> None:
    if value != MIN_SAMPLE_COUNT:
        raise FeeEstimationError(
            f"{FEE_METHOD_VERSION} requires min_sample_count={MIN_SAMPLE_COUNT}"
        )


@dataclass(frozen=True)
class FeeObservation:
    """The minimum evidence needed to classify or project one trade fee.

    ``source_fee_actual`` must be supplied explicitly.  It is deliberately not
    inferred merely because ``source_fees`` is non-zero.
    """

    event_id: str
    account_id: str | None
    asset_type: str | None
    side: str
    gross_amount: Decimal | None
    source_fees: Decimal | None
    source_fee_actual: bool = False
    currency: str = SUPPORTED_CURRENCY
    source_fee_provenance: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        *,
        event_id: object,
        account_id: object | None,
        asset_type: object | None,
        side: object,
        gross_amount: object | None,
        source_fees: object | None,
        source_fee_actual: bool = False,
        currency: object = SUPPORTED_CURRENCY,
        source_fee_provenance: Mapping[str, Any] | None = None,
    ) -> "FeeObservation":
        normalized_event_id = str(event_id or "").strip()
        if not normalized_event_id:
            raise FeeEstimationError("event_id is required for fee provenance")
        if not isinstance(source_fee_actual, bool):
            raise FeeEstimationError("source_fee_actual must be an explicit boolean")
        account = str(account_id).strip() if account_id not in (None, "") else None
        asset = str(asset_type).strip().lower() if asset_type not in (None, "") else None
        return cls(
            event_id=normalized_event_id,
            account_id=account,
            asset_type=asset,
            side=str(side or "").strip().upper(),
            gross_amount=_decimal_or_none(gross_amount),
            source_fees=_decimal_or_none(source_fees),
            source_fee_actual=source_fee_actual,
            currency=str(currency or SUPPORTED_CURRENCY).strip().upper(),
            source_fee_provenance=_freeze_mapping(source_fee_provenance),
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FeeObservation":
        """Build from a store/source row without guessing actual-fee status."""

        event_id = value.get("event_id", value.get("record_id", value.get("source_record_id")))
        explicit_status = value.get("source_fee_status", value.get("fee_status"))
        explicit_flag = value.get("source_fee_actual", False)
        if explicit_status is not None:
            status_is_actual = str(explicit_status).strip().lower() == "actual"
            if explicit_flag not in (False, status_is_actual):
                raise FeeEstimationError("source fee status and actual flag conflict")
            explicit_flag = status_is_actual
        return cls.build(
            event_id=event_id,
            account_id=value.get("account_id", value.get("account")),
            asset_type=value.get("asset_type"),
            side=value.get("side", value.get("event_type")),
            gross_amount=value.get("gross_amount"),
            source_fees=value.get("source_fees", value.get("fees")),
            source_fee_actual=explicit_flag,
            currency=value.get("currency", SUPPORTED_CURRENCY),
            source_fee_provenance=value.get("source_fee_provenance"),
        )

    @property
    def record_id(self) -> str:
        """Alias used by the read-only portfolio mapping contract."""

        return self.event_id

    def identity_payload(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "account_id": self.account_id,
            "asset_type": self.asset_type,
            "side": self.side,
            "gross_amount": (
                _decimal_text(self.gross_amount) if self.gross_amount is not None else None
            ),
            "source_fees": (
                _decimal_text(self.source_fees) if self.source_fees is not None else None
            ),
            "source_fee_actual": self.source_fee_actual,
            "currency": self.currency,
            "source_fee_provenance": dict(self.source_fee_provenance),
        }


@dataclass(frozen=True)
class FeeProfile:
    """A deterministic median-rate profile backed by confirmed samples."""

    profile_id: str
    profile_key: str
    method: str
    method_version: str
    sample_count: int
    rate: Decimal
    fallback_level: str
    sample_event_ids: tuple[str, ...]
    sample_identity_sha256: str
    currency: str = SUPPORTED_CURRENCY

    @property
    def version(self) -> str:
        """Backward-friendly alias; persisted output uses method_version."""

        return self.method_version

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_key": self.profile_key,
            "method": self.method,
            "method_version": self.method_version,
            "sample_count": self.sample_count,
            "rate": _decimal_text(self.rate),
            "fallback_level": self.fallback_level,
            "currency": self.currency,
            "provenance": {
                "sample_event_ids": list(self.sample_event_ids),
                "sample_identity_sha256": self.sample_identity_sha256,
            },
        }


@dataclass(frozen=True)
class FeeProjection:
    """A separate projection that never mutates the source fee value."""

    event_id: str
    status: str
    amount: Decimal | None
    currency: str
    source_fees: Decimal | None
    method: str
    method_version: str
    sample_count: int
    profile_id: str | None
    reason_code: str | None
    provenance: Mapping[str, Any]

    @property
    def record_id(self) -> str:
        return self.event_id

    @property
    def version(self) -> str:
        return self.method_version

    @property
    def projection_id(self) -> str:
        material = self.to_dict(include_projection_id=False)
        return f"feeprj_{_sha256(material)[:32]}"

    def to_dict(self, *, include_projection_id: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if include_projection_id:
            result["projection_id"] = self.projection_id
        result.update(
            {
                "event_id": self.event_id,
                "status": self.status,
                "amount": (
                    (
                        _decimal_text(self.amount)
                        if self.status == "actual"
                        else _money_text(self.amount)
                    )
                    if self.amount is not None
                    else None
                ),
                "currency": self.currency,
                "source_fees": (
                    _decimal_text(self.source_fees) if self.source_fees is not None else None
                ),
                "method": self.method,
                "method_version": self.method_version,
                "sample_count": self.sample_count,
                "profile_id": self.profile_id,
                "reason_code": self.reason_code,
                "provenance": dict(self.provenance),
            }
        )
        return result


def _coerce_observation(value: FeeObservation | Mapping[str, Any]) -> FeeObservation:
    if isinstance(value, FeeObservation):
        # Normalize direct construction too; callers should get identical
        # behavior whether they use build(), mappings, or Decimal inputs.
        return FeeObservation.build(
            event_id=value.event_id,
            account_id=value.account_id,
            asset_type=value.asset_type,
            side=value.side,
            gross_amount=value.gross_amount,
            source_fees=value.source_fees,
            source_fee_actual=value.source_fee_actual,
            currency=value.currency,
            source_fee_provenance=value.source_fee_provenance,
        )
    if isinstance(value, Mapping):
        return FeeObservation.from_mapping(value)
    raise FeeEstimationError(f"unsupported fee observation: {type(value).__name__}")


def _normalize_observations(
    values: Iterable[FeeObservation | Mapping[str, Any]],
) -> tuple[FeeObservation, ...]:
    by_id: dict[str, FeeObservation] = {}
    payload_by_id: dict[str, str] = {}
    for raw in values:
        item = _coerce_observation(raw)
        payload = _canonical_json(item.identity_payload())
        prior = payload_by_id.get(item.event_id)
        if prior is not None and prior != payload:
            raise FeeEstimationError(f"conflicting fee observation for event_id={item.event_id!r}")
        by_id[item.event_id] = item
        payload_by_id[item.event_id] = payload
    return tuple(by_id[event_id] for event_id in sorted(by_id))


def _is_valid_actual_sample(item: FeeObservation) -> bool:
    return bool(
        item.side in SUPPORTED_SIDES
        and item.asset_type in SUPPORTED_ASSET_TYPES
        and item.currency == SUPPORTED_CURRENCY
        and item.source_fee_actual
        and item.source_fees is not None
        and item.source_fees > 0
        and item.gross_amount is not None
        and item.gross_amount > 0
    )


def _median(values: Sequence[Decimal]) -> Decimal:
    if not values:
        raise FeeEstimationError("cannot calculate a fee median without samples")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _profile_key(
    *, account_id: str | None, asset_type: str, side: str, fallback_level: str
) -> str:
    parts = []
    if fallback_level == "account_asset_type_side":
        parts.append(f"account_id={account_id}")
    parts.extend((f"asset_type={asset_type}", f"side={side}", f"currency={SUPPORTED_CURRENCY}"))
    return "|".join(parts)


def _make_profile(samples: Sequence[FeeObservation], *, fallback_level: str) -> FeeProfile:
    if not samples:
        raise FeeEstimationError("cannot build an empty fee profile")
    ordered = tuple(sorted(samples, key=lambda item: item.event_id))
    rates = [item.source_fees / item.gross_amount for item in ordered]  # type: ignore[operator]
    rate = _median(rates)
    first = ordered[0]
    profile_key = _profile_key(
        account_id=first.account_id,
        asset_type=str(first.asset_type),
        side=first.side,
        fallback_level=fallback_level,
    )
    sample_material = [
        {
            "event_id": item.event_id,
            "fees": _decimal_text(item.source_fees),  # type: ignore[arg-type]
            "gross_amount": _decimal_text(item.gross_amount),  # type: ignore[arg-type]
            "rate": _decimal_text(item.source_fees / item.gross_amount),  # type: ignore[operator]
        }
        for item in ordered
    ]
    sample_identity_sha256 = _sha256(sample_material)
    profile_material = {
        "profile_key": profile_key,
        "method": FEE_METHOD,
        "method_version": FEE_METHOD_VERSION,
        "sample_count": len(ordered),
        "rate": _decimal_text(rate),
        "fallback_level": fallback_level,
        "sample_identity_sha256": sample_identity_sha256,
        "currency": SUPPORTED_CURRENCY,
    }
    return FeeProfile(
        profile_id=f"feeprof_{_sha256(profile_material)[:32]}",
        profile_key=profile_key,
        method=FEE_METHOD,
        method_version=FEE_METHOD_VERSION,
        sample_count=len(ordered),
        rate=rate,
        fallback_level=fallback_level,
        sample_event_ids=tuple(item.event_id for item in ordered),
        sample_identity_sha256=sample_identity_sha256,
    )


def build_fee_profile(
    observations: Iterable[FeeObservation | Mapping[str, Any]],
    *,
    account_id: object | None,
    asset_type: object,
    side: object,
    min_sample_count: int = MIN_SAMPLE_COUNT,
) -> FeeProfile | None:
    """Build the account-specific profile, then the fixed broader fallback.

    ``None`` means neither level has enough valid, explicitly actual samples.
    """

    _require_fixed_sample_count(min_sample_count)
    normalized = _normalize_observations(observations)
    account = str(account_id).strip() if account_id not in (None, "") else None
    asset = str(asset_type or "").strip().lower()
    normalized_side = str(side or "").strip().upper()
    eligible = tuple(
        item
        for item in normalized
        if _is_valid_actual_sample(item)
        and item.asset_type == asset
        and item.side == normalized_side
    )
    account_samples = (
        tuple(item for item in eligible if item.account_id == account) if account else ()
    )
    if len(account_samples) >= min_sample_count:
        return _make_profile(account_samples, fallback_level="account_asset_type_side")
    if len(eligible) >= min_sample_count:
        return _make_profile(eligible, fallback_level="asset_type_side")
    return None


def _unknown_projection(
    target: FeeObservation,
    *,
    reason_code: str,
    sample_count: int = 0,
    min_sample_count: int = MIN_SAMPLE_COUNT,
    provenance: Mapping[str, Any] | None = None,
) -> FeeProjection:
    details = {
        "kind": "unavailable",
        "reason_code": reason_code,
        "minimum_sample_count": min_sample_count,
        **dict(provenance or {}),
    }
    return FeeProjection(
        event_id=target.event_id,
        status="unknown",
        amount=None,
        currency=target.currency,
        source_fees=target.source_fees,
        method=FEE_METHOD,
        method_version=FEE_METHOD_VERSION,
        sample_count=sample_count,
        profile_id=None,
        reason_code=reason_code,
        provenance=_freeze_mapping(details),
    )


def estimate_fee(
    target: FeeObservation | Mapping[str, Any],
    historical_actuals: Iterable[FeeObservation | Mapping[str, Any]] = (),
    *,
    min_sample_count: int = MIN_SAMPLE_COUNT,
) -> FeeProjection:
    """Classify an actual fee or derive one median-rate projection.

    The caller owns temporal eligibility: ``historical_actuals`` must contain
    only confirmed observations available for the intended review cutoff.
    """

    _require_fixed_sample_count(min_sample_count)
    item = _coerce_observation(target)
    if item.side not in SUPPORTED_SIDES:
        return _unknown_projection(item, reason_code="UNSUPPORTED_SIDE")
    if item.currency != SUPPORTED_CURRENCY:
        return _unknown_projection(item, reason_code="UNSUPPORTED_CURRENCY")
    if item.source_fee_actual and item.source_fees is not None and item.source_fees > 0:
        return FeeProjection(
            event_id=item.event_id,
            status="actual",
            amount=item.source_fees,
            currency=item.currency,
            source_fees=item.source_fees,
            method=SOURCE_ACTUAL_METHOD,
            method_version=SOURCE_ACTUAL_METHOD_VERSION,
            sample_count=0,
            profile_id=None,
            reason_code=None,
            provenance=_freeze_mapping(
                {
                    "kind": "source_fee",
                    "source_event_id": item.event_id,
                    "source_fee_actual": True,
                    "source_fee_provenance": dict(item.source_fee_provenance),
                    "source_fee_preserved": _decimal_text(item.source_fees),
                }
            ),
        )
    if item.asset_type not in SUPPORTED_ASSET_TYPES:
        return _unknown_projection(item, reason_code="UNRECOGNIZED_ASSET_TYPE")
    if item.gross_amount is None or item.gross_amount <= 0:
        return _unknown_projection(item, reason_code="INVALID_GROSS_AMOUNT")

    observations = _normalize_observations(historical_actuals)
    eligible = tuple(
        sample
        for sample in observations
        if _is_valid_actual_sample(sample)
        and sample.asset_type == item.asset_type
        and sample.side == item.side
    )
    account_samples = (
        tuple(sample for sample in eligible if sample.account_id == item.account_id)
        if item.account_id
        else ()
    )
    profile: FeeProfile | None = None
    if len(account_samples) >= min_sample_count:
        profile = _make_profile(account_samples, fallback_level="account_asset_type_side")
    elif len(eligible) >= min_sample_count:
        profile = _make_profile(eligible, fallback_level="asset_type_side")
    if profile is None:
        return _unknown_projection(
            item,
            reason_code="INSUFFICIENT_ACTUAL_SAMPLES",
            sample_count=len(eligible),
            min_sample_count=min_sample_count,
            provenance={
                "account_sample_count": len(account_samples),
                "fallback_sample_count": len(eligible),
                "requested_account_id": item.account_id,
                "requested_asset_type": item.asset_type,
                "requested_side": item.side,
            },
        )

    amount = (item.gross_amount * profile.rate).quantize(
        MONEY_QUANTUM, rounding=ROUND_HALF_UP
    )
    return FeeProjection(
        event_id=item.event_id,
        status="estimated",
        amount=amount,
        currency=item.currency,
        source_fees=item.source_fees,
        method=profile.method,
        method_version=profile.method_version,
        sample_count=profile.sample_count,
        profile_id=profile.profile_id,
        reason_code=None,
        provenance=_freeze_mapping(
            {
                "kind": "derived_fee",
                "profile_key": profile.profile_key,
                "fallback_level": profile.fallback_level,
                "median_rate": _decimal_text(profile.rate),
                "sample_event_ids": list(profile.sample_event_ids),
                "sample_identity_sha256": profile.sample_identity_sha256,
                "minimum_sample_count": min_sample_count,
                "rounding": "0.01_CNY_ROUND_HALF_UP",
                "source_fee_preserved": (
                    _decimal_text(item.source_fees) if item.source_fees is not None else None
                ),
            }
        ),
    )


def project_fees(
    observations: Iterable[FeeObservation | Mapping[str, Any]],
    historical_actuals: Iterable[FeeObservation | Mapping[str, Any]] | None = None,
    *,
    min_sample_count: int = MIN_SAMPLE_COUNT,
) -> tuple[FeeProjection, ...]:
    """Project a deterministic, event-id-sorted batch.

    When a separate sample collection is not supplied, confirmed actual rows
    from ``observations`` form the profile pool.  Exact duplicate event IDs are
    collapsed; content drift for one identity is rejected.
    """

    targets = _normalize_observations(observations)
    samples = (
        targets
        if historical_actuals is None
        else _normalize_observations(historical_actuals)
    )
    return tuple(
        estimate_fee(target, samples, min_sample_count=min_sample_count) for target in targets
    )


__all__ = [
    "FEE_METHOD",
    "FEE_METHOD_VERSION",
    "MIN_SAMPLE_COUNT",
    "MONEY_QUANTUM",
    "SOURCE_ACTUAL_METHOD",
    "SOURCE_ACTUAL_METHOD_VERSION",
    "SUPPORTED_ASSET_TYPES",
    "SUPPORTED_CURRENCY",
    "SUPPORTED_SIDES",
    "FeeEstimationError",
    "FeeObservation",
    "FeeProfile",
    "FeeProjection",
    "build_fee_profile",
    "estimate_fee",
    "project_fees",
]
