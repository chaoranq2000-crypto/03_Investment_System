"""Deterministic portfolio context for evidence-first investment reviews.

The module keeps pre-decision facts separate from post-event observations.  It
does not infer motives, score decisions, or produce trading instructions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any, Iterable, Mapping

from .models import ModelValidationError, SourceDefinition, canonical_json, parse_decimal, sha256_text
from .time_utils import parse_datetime, utc_iso


def _required_decimal(value: object, field_name: str) -> Decimal:
    parsed = parse_decimal(value, field_name=field_name)
    if parsed is None:
        raise ModelValidationError(f"{field_name} is required")
    return parsed


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if value == 0:
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _exact_sum(values: Iterable[Decimal]) -> Decimal:
    items = tuple(values)
    if not items:
        return Decimal("0")
    maximum_adjusted = max(item.adjusted() for item in items if item != 0) if any(items) else 0
    minimum_exponent = min(item.as_tuple().exponent for item in items)
    carry_digits = len(str(len(items))) + 2
    with localcontext() as context:
        context.prec = max(28, maximum_adjusted - minimum_exponent + carry_digits)
        return sum(items, Decimal("0"))


def _ratio(value: Decimal, denominator: Decimal) -> Decimal | None:
    return None if denominator == 0 else value / denominator


def _ratio_text(value: Decimal, denominator: Decimal) -> str | None:
    return _decimal_text(_ratio(value, denominator))


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    quantity: Decimal
    observed_at: str
    known_at: str
    source_id: str
    price: Decimal | None = None
    cost_basis: Decimal | None = None
    market_value: Decimal | None = None
    currency: str = "CNY"
    fx_rate_to_base: Decimal | None = None
    market: str | None = None
    industry: str | None = None
    labels: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not self.symbol.strip():
            raise ModelValidationError("Position symbol is required")
        if not self.source_id.strip():
            raise ModelValidationError("Position source_id is required")
        if self.price is not None and self.price < 0:
            raise ModelValidationError("Position price cannot be negative")
        if self.cost_basis is not None and self.cost_basis < 0:
            raise ModelValidationError("Position cost_basis cannot be negative")
        if self.fx_rate_to_base is not None and self.fx_rate_to_base <= 0:
            raise ModelValidationError("fx_rate_to_base must be positive")
        observed = parse_datetime(self.observed_at, "UTC")
        known = parse_datetime(self.known_at, "UTC")
        if known < observed:
            raise ModelValidationError("Position known_at cannot be earlier than observed_at")

    @property
    def position_key(self) -> str:
        return f"{self.symbol}|{self.market or ''}"

    def value_in_base(self, base_currency: str) -> Decimal | None:
        value = self.market_value
        if value is None and self.price is not None:
            value = self.quantity * self.price
        if value is None:
            return None
        if self.currency == base_currency:
            return value
        if self.fx_rate_to_base is None:
            return None
        return value * self.fx_rate_to_base

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "market": self.market,
            "quantity": _decimal_text(self.quantity),
            "cost_basis": _decimal_text(self.cost_basis),
            "price": _decimal_text(self.price),
            "market_value": _decimal_text(self.market_value),
            "currency": self.currency,
            "fx_rate_to_base": _decimal_text(self.fx_rate_to_base),
            "industry": self.industry,
            "labels": list(self.labels),
            "source_id": self.source_id,
            "observed_at": self.observed_at,
            "known_at": self.known_at,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        *,
        source_id: str,
        observed_at: str,
        known_at: str,
        timezone: str = "Asia/Shanghai",
    ) -> "PositionSnapshot":
        position = cls(
            symbol=str(payload.get("symbol", "")).strip().upper(),
            market=str(payload["market"]).strip().upper() if payload.get("market") else None,
            quantity=_required_decimal(payload.get("quantity"), "quantity"),
            cost_basis=parse_decimal(payload.get("cost_basis"), field_name="cost_basis"),
            price=parse_decimal(payload.get("price"), field_name="price"),
            market_value=parse_decimal(payload.get("market_value"), field_name="market_value"),
            currency=str(payload.get("currency") or "CNY").strip().upper(),
            fx_rate_to_base=parse_decimal(
                payload.get("fx_rate_to_base"), field_name="fx_rate_to_base"
            ),
            industry=str(payload["industry"]).strip() if payload.get("industry") else None,
            labels=tuple(sorted({str(item).strip() for item in payload.get("labels", []) if str(item).strip()})),
            source_id=str(payload.get("source_id") or source_id).strip(),
            observed_at=utc_iso(payload.get("observed_at") or observed_at, timezone),
            known_at=utc_iso(payload.get("known_at") or known_at, timezone),
        )
        position.validate()
        return position


@dataclass(frozen=True)
class PortfolioSnapshot:
    source_id: str
    source_path: str
    observed_at: str
    known_at: str
    cash: Decimal
    total_assets: Decimal
    net_asset_value: Decimal
    financing: Decimal
    positions: tuple[PositionSnapshot, ...]
    base_currency: str = "CNY"
    account: str | None = None
    source_record_id: str | None = None
    snapshot_id: str | None = None

    def validate(self) -> None:
        if not self.source_id.strip():
            raise ModelValidationError("Portfolio source_id is required")
        if not self.source_path.strip():
            raise ModelValidationError("Portfolio source_path is required")
        observed = parse_datetime(self.observed_at, "UTC")
        known = parse_datetime(self.known_at, "UTC")
        if known < observed:
            raise ModelValidationError("Portfolio known_at cannot be earlier than observed_at")
        keys: set[str] = set()
        for position in self.positions:
            position.validate()
            if position.source_id != self.source_id:
                raise ModelValidationError(
                    f"Position {position.position_key} source_id does not match portfolio source"
                )
            if parse_datetime(position.observed_at, "UTC") > observed:
                raise ModelValidationError(
                    f"Position {position.position_key} occurred after its portfolio snapshot"
                )
            if parse_datetime(position.known_at, "UTC") > known:
                raise ModelValidationError(
                    f"Position {position.position_key} became known after its portfolio snapshot"
                )
            if position.position_key in keys:
                raise ModelValidationError(f"Duplicate position key: {position.position_key}")
            keys.add(position.position_key)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_path": self.source_path,
            "source_record_id": self.source_record_id,
            "account": self.account,
            "observed_at": self.observed_at,
            "known_at": self.known_at,
            "cash": _decimal_text(self.cash),
            "total_assets": _decimal_text(self.total_assets),
            "net_asset_value": _decimal_text(self.net_asset_value),
            "financing": _decimal_text(self.financing),
            "base_currency": self.base_currency,
            "positions": [item.to_dict() for item in sorted(self.positions, key=lambda x: x.position_key)],
        }

    @property
    def resolved_snapshot_id(self) -> str:
        return self.snapshot_id or f"snap_{sha256_text(canonical_json(self.identity_payload()))[:32]}"

    @property
    def payload_sha256(self) -> str:
        return sha256_text(canonical_json(self.identity_payload()))

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_id": self.resolved_snapshot_id, **self.identity_payload()}

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        *,
        default_source_id: str | None = None,
        timezone: str = "Asia/Shanghai",
    ) -> "PortfolioSnapshot":
        source_id = str(payload.get("source_id") or default_source_id or "").strip()
        observed_at = utc_iso(payload.get("observed_at"), timezone)
        known_at = utc_iso(payload.get("known_at"), timezone)
        raw_positions = payload.get("positions", [])
        if not isinstance(raw_positions, list):
            raise ModelValidationError("positions must be a list")
        snapshot = cls(
            source_id=source_id,
            source_path=str(payload.get("source_path", "")).strip(),
            source_record_id=(
                str(payload["source_record_id"]).strip() if payload.get("source_record_id") else None
            ),
            account=str(payload["account"]).strip() if payload.get("account") else None,
            observed_at=observed_at,
            known_at=known_at,
            cash=_required_decimal(payload.get("cash"), "cash"),
            total_assets=_required_decimal(payload.get("total_assets"), "total_assets"),
            net_asset_value=_required_decimal(payload.get("net_asset_value"), "net_asset_value"),
            financing=_required_decimal(payload.get("financing", "0"), "financing"),
            base_currency=str(payload.get("base_currency") or "CNY").strip().upper(),
            positions=tuple(
                PositionSnapshot.from_dict(
                    item,
                    source_id=source_id,
                    observed_at=observed_at,
                    known_at=known_at,
                    timezone=timezone,
                )
                for item in raw_positions
            ),
            snapshot_id=str(payload["snapshot_id"]).strip() if payload.get("snapshot_id") else None,
        )
        snapshot.validate()
        return snapshot


@dataclass(frozen=True)
class PortfolioWarning:
    """A deterministic warning attached to one or more portfolio metrics."""

    code: str
    scope: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "scope": self.scope, "message": self.message}


@dataclass(frozen=True)
class MetricEvidence:
    """Traceable snapshot and position references used by a derived metric."""

    source_id: str
    source_path: str
    snapshot_id: str
    observed_at: str
    available_at: str
    position_keys: tuple[str, ...] = field(default_factory=tuple)

    @property
    def evidence_id(self) -> str:
        material = {
            "source_id": self.source_id,
            "source_path": self.source_path,
            "snapshot_id": self.snapshot_id,
            "observed_at": self.observed_at,
            "available_at": self.available_at,
            "position_keys": list(self.position_keys),
        }
        return f"metric_evidence_{sha256_text(canonical_json(material))[:24]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "source_path": self.source_path,
            "snapshot_id": self.snapshot_id,
            "observed_at": self.observed_at,
            "available_at": self.available_at,
            "position_keys": list(self.position_keys),
        }


@dataclass(frozen=True)
class PortfolioMetric:
    """One observed or derived portfolio metric with evidence and uncertainty."""

    metric_name: str
    value: str | None
    unit: str
    calculation_method: str
    as_of: str
    available_at: str
    status: str
    source_refs: tuple[MetricEvidence, ...]
    warnings: tuple[PortfolioWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status not in {"observed", "derived", "unavailable"}:
            raise ModelValidationError(f"Unsupported portfolio metric status: {self.status}")
        if self.status == "unavailable" and self.value is not None:
            raise ModelValidationError("Unavailable portfolio metrics must not expose a value")
        if not self.source_refs:
            raise ModelValidationError("Portfolio metrics require at least one source reference")

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "unit": self.unit,
            "method": portfolio_metric_method_ref(self.metric_name),
            "calculation_method": self.calculation_method,
            "as_of": self.as_of,
            "available_at": self.available_at,
            "status": self.status,
            "source_refs": [item.to_dict() for item in self.source_refs],
            "warnings": [item.to_dict() for item in self.warnings],
        }


def snapshot_document(payload: Mapping[str, Any]) -> tuple[SourceDefinition, PortfolioSnapshot]:
    source_payload = payload.get("source")
    snapshot_payload = payload.get("snapshot")
    if not isinstance(source_payload, Mapping) or not isinstance(snapshot_payload, Mapping):
        raise ModelValidationError("Snapshot document requires source and snapshot objects")
    source = SourceDefinition(
        name=str(source_payload.get("name", "")).strip(),
        kind=str(source_payload.get("kind", "")).strip(),
        uri=str(source_payload.get("uri", "")).strip(),
        timezone=str(source_payload.get("timezone") or "Asia/Shanghai").strip(),
        read_only=bool(source_payload.get("read_only", True)),
        identity_key=(
            str(source_payload["identity_key"]).strip() if source_payload.get("identity_key") else None
        ),
        config=dict(source_payload.get("config") or {}),
    )
    source.validate()
    if not source.read_only:
        raise ModelValidationError("Portfolio snapshot source must be read-only")
    snapshot = PortfolioSnapshot.from_dict(
        snapshot_payload,
        default_source_id=source.source_id,
        timezone=source.timezone,
    )
    if snapshot.source_id != source.source_id:
        raise ModelValidationError("Snapshot source_id does not match source definition")
    return source, snapshot


def load_snapshot_document(path: str | Path) -> tuple[SourceDefinition, PortfolioSnapshot]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ModelValidationError("Snapshot document root must be an object")
    return snapshot_document(payload)


def _quality_flags(snapshot: PortfolioSnapshot) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if snapshot.net_asset_value == 0:
        flags.append({"code": "ZERO_NAV", "scope": "portfolio"})
    for position in sorted(snapshot.positions, key=lambda item: item.position_key):
        scope = position.position_key
        if position.market_value is None and position.price is None:
            flags.append({"code": "MISSING_PRICE", "scope": scope})
        if position.price == 0 and position.quantity != 0:
            flags.append({"code": "ZERO_PRICE", "scope": scope})
        if position.quantity < 0:
            flags.append({"code": "NEGATIVE_QUANTITY_INTERPRETED_AS_SHORT", "scope": scope})
        if not position.industry:
            flags.append({"code": "UNKNOWN_INDUSTRY", "scope": scope})
        if position.currency != snapshot.base_currency and position.fx_rate_to_base is None:
            flags.append({"code": "CURRENCY_NOT_CONVERTED", "scope": scope})
        if (
            position.market_value is not None
            and position.quantity != 0
            and (position.market_value > 0) != (position.quantity > 0)
        ):
            flags.append({"code": "QUANTITY_VALUE_SIGN_MISMATCH", "scope": scope})
    return flags


def calculate_portfolio_metrics(snapshot: PortfolioSnapshot) -> dict[str, Any]:
    """Calculate stable single-snapshot metrics without filling missing values."""

    snapshot.validate()
    values: dict[str, Decimal] = {}
    industries: dict[str, list[Decimal]] = {}
    labels: dict[str, list[Decimal]] = {}
    excluded: list[str] = []
    for position in sorted(snapshot.positions, key=lambda item: item.position_key):
        value = position.value_in_base(snapshot.base_currency)
        if value is None:
            excluded.append(position.position_key)
            continue
        values[position.position_key] = value
        industries.setdefault(position.industry or "UNKNOWN", []).append(value)
        for label in position.labels:
            labels.setdefault(label, []).append(value)

    gross = sum((abs(value) for value in values.values()), Decimal("0"))
    net = sum(values.values(), Decimal("0"))
    nav = snapshot.net_asset_value
    absolute_weights = sorted((abs(value) for value in values.values()), reverse=True)
    weights = {
        key: _ratio_text(value, nav)
        for key, value in sorted(values.items())
    }
    concentration_weights = [value / gross for value in absolute_weights] if gross else []
    industry_exposure = {
        key: {
            "net_ratio": _ratio_text(sum(group, Decimal("0")), nav),
            "gross_ratio": _ratio_text(sum((abs(value) for value in group), Decimal("0")), nav),
        }
        for key, group in sorted(industries.items())
    }
    label_exposure = {
        key: {
            "net_ratio": _ratio_text(sum(group, Decimal("0")), nav),
            "gross_ratio": _ratio_text(sum((abs(value) for value in group), Decimal("0")), nav),
        }
        for key, group in sorted(labels.items())
    }
    balance_gap = snapshot.net_asset_value - (snapshot.cash + net - snapshot.financing)
    flags = _quality_flags(snapshot)
    if balance_gap != 0:
        flags.append({"code": "NAV_RECONCILIATION_GAP", "scope": "portfolio"})
    return {
        "snapshot_id": snapshot.resolved_snapshot_id,
        "base_currency": snapshot.base_currency,
        "cash_ratio": _ratio_text(snapshot.cash, nav),
        "total_position_ratio": _ratio_text(gross, nav),
        "gross_exposure": _ratio_text(gross, nav),
        "net_exposure": _ratio_text(net, nav),
        "gross_market_value": _decimal_text(gross),
        "net_market_value": _decimal_text(net),
        "position_weights": weights,
        "top1_concentration": _decimal_text(sum(concentration_weights[:1], Decimal("0"))),
        "top5_concentration": _decimal_text(sum(concentration_weights[:5], Decimal("0"))),
        "hhi_concentration": _decimal_text(
            sum((weight * weight for weight in concentration_weights), Decimal("0"))
        ),
        "industry_exposure": industry_exposure,
        "label_exposure": label_exposure,
        "balance_gap": _decimal_text(balance_gap),
        "excluded_position_keys": excluded,
        "data_quality_flags": flags,
        "metric_definitions": {
            "gross_exposure": "sum(abs(base_market_value)) / net_asset_value",
            "net_exposure": "sum(base_market_value) / net_asset_value",
            "top_concentration": "largest gross position values / gross_market_value",
            "hhi_concentration": "sum((abs(position_value) / gross_market_value)^2)",
        },
    }


def _metric_source_ref(
    snapshot: PortfolioSnapshot,
    position_keys: Iterable[str] = (),
) -> MetricEvidence:
    return MetricEvidence(
        source_id=snapshot.source_id,
        source_path=snapshot.source_path,
        snapshot_id=snapshot.resolved_snapshot_id,
        observed_at=snapshot.observed_at,
        available_at=snapshot.known_at,
        position_keys=tuple(sorted(set(position_keys))),
    )


PORTFOLIO_METRIC_REGISTRY_VERSION = "p2e2.portfolio_metric_registry.v1"
"""Version of the public P2E-2 portfolio metric method registry."""

_INDUSTRY_WEIGHT_REGISTRY_KEY = "industry_weight::*"

PORTFOLIO_METRIC_METHOD_REGISTRY: dict[str, dict[str, str]] = {
    "nav": {
        "method_id": "nav",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "snapshot.net_asset_value input",
    },
    "cash_value": {
        "method_id": "cash_value",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "snapshot.cash input",
    },
    "cash_weight": {
        "method_id": "cash_weight",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "cash_value / nav",
    },
    "long_market_value": {
        "method_id": "long_market_value",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "sum(positive base_market_value)",
    },
    "short_market_value": {
        "method_id": "short_market_value",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "sum(abs(negative base_market_value))",
    },
    "gross_market_value": {
        "method_id": "gross_market_value",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "long_market_value + short_market_value",
    },
    "net_market_value": {
        "method_id": "net_market_value",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "long_market_value - short_market_value",
    },
    "long_exposure": {
        "method_id": "long_exposure",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "long_market_value / nav",
    },
    "short_exposure": {
        "method_id": "short_exposure",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "short_market_value / nav",
    },
    "gross_exposure": {
        "method_id": "gross_exposure",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "gross_market_value / nav",
    },
    "net_exposure": {
        "method_id": "net_exposure",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "net_market_value / nav",
    },
    "position_count": {
        "method_id": "position_count",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "count(snapshot.positions)",
    },
    "valued_position_count": {
        "method_id": "valued_position_count",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "count(positions with reviewed base_market_value)",
    },
    "unpriced_position_count": {
        "method_id": "unpriced_position_count",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "count(positions in the explicit missing valuation set)",
    },
    "valuation_coverage": {
        "method_id": "valuation_coverage",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "valued_position_count / position_count",
    },
    "unpriced_position_ratio": {
        "method_id": "unpriced_position_ratio",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "unpriced_position_count / position_count",
    },
    "missing_valuation_amount": {
        "method_id": "missing_valuation_amount",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "zero only when coverage is complete; otherwise unavailable",
    },
    "stale_position_count": {
        "method_id": "stale_position_count",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "count(position_keys explicitly marked stale)",
    },
    "stale_position_ratio": {
        "method_id": "stale_position_ratio",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "stale_position_count / position_count",
    },
    "target_position_value": {
        "method_id": "target_position_value",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "sum(target_symbol base_market_value)",
    },
    "target_position_weight": {
        "method_id": "target_position_weight",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "target_position_value / nav",
    },
    "max_position_weight": {
        "method_id": "max_position_weight",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "max(abs(base_market_value)) / gross_market_value",
    },
    "top3_concentration": {
        "method_id": "top3_concentration",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "sum(top 3 abs(base_market_value)) / gross_market_value",
    },
    "top5_concentration": {
        "method_id": "top5_concentration",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "sum(top 5 abs(base_market_value)) / gross_market_value",
    },
    "hhi": {
        "method_id": "hhi",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "sum((abs(base_market_value) / gross_market_value)^2)",
    },
    _INDUSTRY_WEIGHT_REGISTRY_KEY: {
        "method_id": "industry_weight",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "industry gross_market_value / gross_market_value",
    },
    "max_industry_weight": {
        "method_id": "max_industry_weight",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "max(industry gross_market_value / gross_market_value)",
    },
    "unclassified_industry_weight": {
        "method_id": "unclassified_industry_weight",
        "method_version": PORTFOLIO_METRIC_REGISTRY_VERSION,
        "calculation_method": "UNKNOWN industry gross_market_value / gross_market_value",
    },
}
"""Stable metric IDs, versions and formulas exported for P2E-3 consumers."""

_PORTFOLIO_METRIC_SEMANTIC_GROUPS: tuple[
    tuple[tuple[str, ...], str, str], ...
] = (
    (
        ("nav", "cash_value", "net_market_value", "target_position_value"),
        "base_currency",
        "signed",
    ),
    (
        ("long_market_value", "short_market_value", "gross_market_value"),
        "base_currency",
        "nonnegative",
    ),
    (("missing_valuation_amount",), "base_currency", "zero_if_numeric"),
    (
        ("cash_weight", "net_exposure", "target_position_weight"),
        "ratio_to_nav",
        "signed",
    ),
    (
        ("long_exposure", "short_exposure", "gross_exposure"),
        "ratio_to_nav",
        "nonnegative",
    ),
    (
        (
            "position_count",
            "valued_position_count",
            "unpriced_position_count",
            "stale_position_count",
        ),
        "count",
        "nonnegative_integer",
    ),
    (
        (
            "valuation_coverage",
            "unpriced_position_ratio",
            "stale_position_ratio",
        ),
        "position_count_ratio",
        "unit_interval",
    ),
    (
        (
            "max_position_weight",
            "top3_concentration",
            "top5_concentration",
            "hhi",
            _INDUSTRY_WEIGHT_REGISTRY_KEY,
            "max_industry_weight",
            "unclassified_industry_weight",
        ),
        "gross_share",
        "unit_interval",
    ),
)

for _metric_names, _unit_kind, _value_domain in _PORTFOLIO_METRIC_SEMANTIC_GROUPS:
    for _metric_name in _metric_names:
        PORTFOLIO_METRIC_METHOD_REGISTRY[_metric_name].update(
            {"unit_kind": _unit_kind, "value_domain": _value_domain}
        )

if any(
    "unit_kind" not in spec or "value_domain" not in spec
    for spec in PORTFOLIO_METRIC_METHOD_REGISTRY.values()
):
    raise RuntimeError("portfolio metric semantic registry is incomplete")

_METRIC_CALCULATION_METHODS = {
    metric_name: spec["calculation_method"]
    for metric_name, spec in PORTFOLIO_METRIC_METHOD_REGISTRY.items()
}


def _metric_registry_key(metric_name: str) -> str:
    return (
        _INDUSTRY_WEIGHT_REGISTRY_KEY
        if metric_name.startswith("industry_weight::")
        else metric_name
    )


def portfolio_metric_method_ref(metric_name: str) -> dict[str, str]:
    """Return the stable method identity for one public portfolio metric."""

    registry_key = _metric_registry_key(metric_name)
    try:
        spec = PORTFOLIO_METRIC_METHOD_REGISTRY[registry_key]
    except KeyError as exc:
        raise ModelValidationError(f"Missing metric method registration: {metric_name}") from exc
    return {
        "method_id": spec["method_id"],
        "method_version": spec["method_version"],
    }


def _metric_calculation_method(metric_name: str) -> str:
    try:
        return _METRIC_CALCULATION_METHODS[_metric_registry_key(metric_name)]
    except KeyError as exc:
        raise ModelValidationError(f"Missing calculation method for metric: {metric_name}") from exc


def _portfolio_metric(
    snapshot: PortfolioSnapshot,
    *,
    metric_name: str,
    value: Decimal | int | None,
    unit: str,
    status: str,
    position_keys: Iterable[str] = (),
    warnings: Iterable[PortfolioWarning] = (),
) -> PortfolioMetric:
    rendered_value: str | None
    if value is None:
        rendered_value = None
    elif isinstance(value, Decimal):
        rendered_value = _decimal_text(value)
    else:
        rendered_value = str(value)
    ordered_warnings = tuple(
        sorted(warnings, key=lambda item: (item.code, item.scope, item.message))
    )
    return PortfolioMetric(
        metric_name=metric_name,
        value=rendered_value,
        unit=unit,
        calculation_method=_metric_calculation_method(metric_name),
        as_of=snapshot.observed_at,
        available_at=snapshot.known_at,
        status=status,
        source_refs=(_metric_source_ref(snapshot, position_keys),),
        warnings=ordered_warnings,
    )


def calculate_portfolio_evidence_metrics(
    snapshot: PortfolioSnapshot,
    *,
    target_symbol: str | None = None,
    stale_position_keys: Iterable[str] | None = None,
) -> tuple[PortfolioMetric, ...]:
    """Build deterministic, source-bound metrics for one reviewed snapshot.

    Missing prices and FX rates remain outside valued aggregates.  Metrics based
    on the available subset retain explicit warnings, while an unknown missing
    valuation amount is never filled with zero.
    """

    snapshot.validate()
    all_positions = sorted(snapshot.positions, key=lambda item: item.position_key)
    all_keys = tuple(item.position_key for item in all_positions)
    all_key_set = set(all_keys)
    normalized_target_symbol: str | None = None
    if target_symbol is not None:
        normalized_target_symbol = str(target_symbol).strip().upper()
        if not normalized_target_symbol:
            raise ModelValidationError("target_symbol cannot be blank")

    normalized_stale_keys: tuple[str, ...] | None = None
    if stale_position_keys is not None:
        raw_stale_keys = (
            (stale_position_keys,)
            if isinstance(stale_position_keys, str)
            else stale_position_keys
        )
        stale_key_set: set[str] = set()
        for raw_key in raw_stale_keys:
            key = str(raw_key).strip()
            if not key:
                raise ModelValidationError("stale_position_keys cannot contain a blank key")
            stale_key_set.add(key)
        unknown_stale_keys = sorted(stale_key_set - all_key_set)
        if unknown_stale_keys:
            raise ModelValidationError(
                "stale_position_keys are not present in the snapshot: "
                + ", ".join(unknown_stale_keys)
            )
        normalized_stale_keys = tuple(sorted(stale_key_set))

    valued: list[tuple[PositionSnapshot, Decimal]] = []
    valued_by_key: dict[str, Decimal] = {}
    missing: list[PositionSnapshot] = []
    detail_warnings: list[PortfolioWarning] = []
    for position in all_positions:
        value = position.value_in_base(snapshot.base_currency)
        if position.quantity < 0:
            detail_warnings.append(
                PortfolioWarning(
                    code="NEGATIVE_QUANTITY_INTERPRETED_AS_SHORT",
                    scope=position.position_key,
                    message="Negative quantity is included as a short position in gross and net exposure.",
                )
            )
        if (
            position.market_value is not None
            and position.quantity != 0
            and (position.market_value > 0) != (position.quantity > 0)
        ):
            detail_warnings.append(
                PortfolioWarning(
                    code="QUANTITY_VALUE_SIGN_MISMATCH",
                    scope=position.position_key,
                    message="Quantity and explicit market value have inconsistent signs.",
                )
            )
        zero_valuation = (
            value == 0
            and position.quantity != 0
            and (position.price == 0 or position.market_value == 0)
        )
        if value is None or zero_valuation:
            missing.append(position)
            if position.currency != snapshot.base_currency and position.fx_rate_to_base is None:
                detail_warnings.append(
                    PortfolioWarning(
                        code="MISSING_FX",
                        scope=position.position_key,
                        message="Non-base-currency valuation has no reviewed FX rate.",
                    )
                )
            elif zero_valuation:
                detail_warnings.append(
                    PortfolioWarning(
                        code="ZERO_VALUATION",
                        scope=position.position_key,
                        message="A non-zero position has a zero valuation and is excluded.",
                    )
                )
            else:
                detail_warnings.append(
                    PortfolioWarning(
                        code="MISSING_PRICE",
                        scope=position.position_key,
                        message="Position has neither a reviewed market value nor price.",
                    )
                )
            continue
        valued.append((position, value))
        valued_by_key[position.position_key] = value

    valued.sort(key=lambda item: (-abs(item[1]), item[0].position_key))
    valued_keys = tuple(item.position_key for item, _ in valued)
    missing_keys = tuple(item.position_key for item in missing)
    long_value = _exact_sum(value for _, value in valued if value > 0)
    short_value = _exact_sum(-value for _, value in valued if value < 0)
    gross_value = _exact_sum((long_value, short_value))
    net_value = _exact_sum((long_value, -short_value))
    nav = snapshot.net_asset_value
    reconciliation_gap = _exact_sum(
        (nav, -snapshot.cash, -net_value, snapshot.financing)
    )
    if reconciliation_gap != 0:
        detail_warnings.append(
            PortfolioWarning(
                code="NAV_RECONCILIATION_GAP",
                scope="portfolio",
                message="NAV does not reconcile to cash plus net valued positions less financing.",
            )
        )
    nav_warning = PortfolioWarning(
        code="NON_POSITIVE_NAV",
        scope="portfolio",
        message="NAV is not positive; weights and exposure ratios are unavailable.",
    )
    partial_warning = PortfolioWarning(
        code="PARTIAL_VALUATION_COVERAGE",
        scope="portfolio",
        message="Valuation-based metrics use only positions with reviewed price and FX inputs.",
    )
    valuation_warnings: tuple[PortfolioWarning, ...] = tuple(
        [*(detail_warnings), *([partial_warning] if missing else [])]
    )

    stale_metadata_warning = PortfolioWarning(
        code="STALE_POSITION_METADATA_UNAVAILABLE",
        scope="portfolio",
        message="No reviewed stale-position metadata was supplied for this snapshot.",
    )
    stale_warnings: tuple[PortfolioWarning, ...]
    if normalized_stale_keys is None:
        stale_warnings = (stale_metadata_warning,)
        stale_count: int | None = None
        stale_ratio: Decimal | None = None
    else:
        stale_warnings = tuple(
            PortfolioWarning(
                code="STALE_POSITION",
                scope=position_key,
                message="The position was explicitly marked stale by reviewed metadata.",
            )
            for position_key in normalized_stale_keys
        )
        stale_count = len(normalized_stale_keys)
        stale_ratio = (
            Decimal(stale_count) / Decimal(len(all_positions))
            if all_positions
            else Decimal("0")
        )

    target_keys: tuple[str, ...] = ()
    target_value: Decimal | None = None
    target_warnings: tuple[PortfolioWarning, ...] = ()
    if normalized_target_symbol is not None:
        target_positions = tuple(
            position
            for position in all_positions
            if position.symbol == normalized_target_symbol
        )
        target_keys = tuple(position.position_key for position in target_positions)
        target_missing_keys = tuple(
            position_key for position_key in target_keys if position_key in set(missing_keys)
        )
        if not target_positions:
            target_value = Decimal("0")
        elif target_missing_keys:
            target_value = None
            target_warning_items = [
                warning
                for warning in detail_warnings
                if warning.scope in set(target_missing_keys)
            ]
            target_warning_items.append(
                PortfolioWarning(
                    code="TARGET_POSITION_UNPRICED",
                    scope=normalized_target_symbol,
                    message="At least one target position lacks a reviewed base-currency valuation.",
                )
            )
            target_warnings = tuple(target_warning_items)
        else:
            target_value = _exact_sum(valued_by_key[position_key] for position_key in target_keys)

    def nav_ratio_metric(
        metric_name: str,
        numerator: Decimal,
        *,
        position_keys: Iterable[str] = (),
        warnings: Iterable[PortfolioWarning] = (),
    ) -> PortfolioMetric:
        if nav <= 0:
            return _portfolio_metric(
                snapshot,
                metric_name=metric_name,
                value=None,
                unit="ratio_to_nav",
                status="unavailable",
                position_keys=position_keys,
                warnings=(*warnings, nav_warning),
            )
        return _portfolio_metric(
            snapshot,
            metric_name=metric_name,
            value=numerator / nav,
            unit="ratio_to_nav",
            status="derived",
            position_keys=position_keys,
            warnings=warnings,
        )

    metrics: list[PortfolioMetric] = [
        _portfolio_metric(
            snapshot,
            metric_name="nav",
            value=nav,
            unit=snapshot.base_currency,
            status="observed",
        ),
        _portfolio_metric(
            snapshot,
            metric_name="cash_value",
            value=snapshot.cash,
            unit=snapshot.base_currency,
            status="observed",
        ),
        nav_ratio_metric("cash_weight", snapshot.cash),
        _portfolio_metric(
            snapshot,
            metric_name="long_market_value",
            value=long_value,
            unit=snapshot.base_currency,
            status="derived",
            position_keys=valued_keys,
            warnings=valuation_warnings,
        ),
        _portfolio_metric(
            snapshot,
            metric_name="short_market_value",
            value=short_value,
            unit=snapshot.base_currency,
            status="derived",
            position_keys=valued_keys,
            warnings=valuation_warnings,
        ),
        _portfolio_metric(
            snapshot,
            metric_name="gross_market_value",
            value=gross_value,
            unit=snapshot.base_currency,
            status="derived",
            position_keys=valued_keys,
            warnings=valuation_warnings,
        ),
        _portfolio_metric(
            snapshot,
            metric_name="net_market_value",
            value=net_value,
            unit=snapshot.base_currency,
            status="derived",
            position_keys=valued_keys,
            warnings=valuation_warnings,
        ),
        nav_ratio_metric(
            "long_exposure", long_value, position_keys=valued_keys, warnings=valuation_warnings
        ),
        nav_ratio_metric(
            "short_exposure", short_value, position_keys=valued_keys, warnings=valuation_warnings
        ),
        nav_ratio_metric(
            "gross_exposure", gross_value, position_keys=valued_keys, warnings=valuation_warnings
        ),
        nav_ratio_metric(
            "net_exposure", net_value, position_keys=valued_keys, warnings=valuation_warnings
        ),
        _portfolio_metric(
            snapshot,
            metric_name="position_count",
            value=len(all_positions),
            unit="count",
            status="observed",
            position_keys=all_keys,
        ),
        _portfolio_metric(
            snapshot,
            metric_name="valued_position_count",
            value=len(valued),
            unit="count",
            status="derived",
            position_keys=all_keys,
            warnings=valuation_warnings,
        ),
        _portfolio_metric(
            snapshot,
            metric_name="unpriced_position_count",
            value=len(missing),
            unit="count",
            status="derived",
            position_keys=missing_keys,
            warnings=valuation_warnings,
        ),
        _portfolio_metric(
            snapshot,
            metric_name="valuation_coverage",
            value=(
                Decimal(len(valued)) / Decimal(len(all_positions))
                if all_positions
                else Decimal("1")
            ),
            unit="position_count_ratio",
            status="derived",
            position_keys=all_keys,
            warnings=valuation_warnings,
        ),
        _portfolio_metric(
            snapshot,
            metric_name="unpriced_position_ratio",
            value=(
                Decimal(len(missing)) / Decimal(len(all_positions))
                if all_positions
                else Decimal("0")
            ),
            unit="position_count_ratio",
            status="derived",
            position_keys=all_keys,
            warnings=valuation_warnings,
        ),
        _portfolio_metric(
            snapshot,
            metric_name="missing_valuation_amount",
            value=None if missing else Decimal("0"),
            unit=snapshot.base_currency,
            status="unavailable" if missing else "derived",
            position_keys=(item.position_key for item in missing),
            warnings=(
                *valuation_warnings,
                *(
                    (
                        PortfolioWarning(
                            code="MISSING_VALUATION_AMOUNT_UNKNOWN",
                            scope="portfolio",
                            message="Missing price or FX inputs prevent a base-currency amount.",
                        ),
                    )
                    if missing
                    else ()
                ),
            ),
        ),
        _portfolio_metric(
            snapshot,
            metric_name="stale_position_count",
            value=stale_count,
            unit="count",
            status="unavailable" if stale_count is None else "derived",
            position_keys=(
                all_keys if normalized_stale_keys is None else normalized_stale_keys
            ),
            warnings=stale_warnings,
        ),
        _portfolio_metric(
            snapshot,
            metric_name="stale_position_ratio",
            value=stale_ratio,
            unit="position_count_ratio",
            status="unavailable" if stale_ratio is None else "derived",
            position_keys=all_keys,
            warnings=stale_warnings,
        ),
    ]

    if normalized_target_symbol is not None:
        target_status = "unavailable" if target_value is None else "derived"
        metrics.append(
            _portfolio_metric(
                snapshot,
                metric_name="target_position_value",
                value=target_value,
                unit=snapshot.base_currency,
                status=target_status,
                position_keys=target_keys,
                warnings=target_warnings,
            )
        )
        if target_value is None:
            metrics.append(
                _portfolio_metric(
                    snapshot,
                    metric_name="target_position_weight",
                    value=None,
                    unit="ratio_to_nav",
                    status="unavailable",
                    position_keys=target_keys,
                    warnings=target_warnings,
                )
            )
        else:
            metrics.append(
                nav_ratio_metric(
                    "target_position_weight",
                    target_value,
                    position_keys=target_keys,
                    warnings=target_warnings,
                )
            )

    concentration_warning_items = valuation_warnings
    if nav <= 0:
        concentration_warning_items = (*concentration_warning_items, nav_warning)

    def gross_share_metric(metric_name: str, numerator: Decimal) -> PortfolioMetric:
        if nav <= 0:
            return _portfolio_metric(
                snapshot,
                metric_name=metric_name,
                value=None,
                unit="gross_share",
                status="unavailable",
                position_keys=valued_keys,
                warnings=concentration_warning_items,
            )
        return _portfolio_metric(
            snapshot,
            metric_name=metric_name,
            value=(numerator / gross_value if gross_value else Decimal("0")),
            unit="gross_share",
            status="derived",
            position_keys=valued_keys,
            warnings=valuation_warnings,
        )

    absolute_values = [abs(value) for _, value in valued]
    metrics.extend(
        [
            gross_share_metric(
                "max_position_weight", absolute_values[0] if absolute_values else Decimal("0")
            ),
            gross_share_metric("top3_concentration", _exact_sum(absolute_values[:3])),
            gross_share_metric("top5_concentration", _exact_sum(absolute_values[:5])),
            gross_share_metric(
                "hhi",
                (
                    _exact_sum(value * value for value in absolute_values)
                    / gross_value
                    if gross_value
                    else Decimal("0")
                ),
            ),
        ]
    )

    industries: dict[str, list[tuple[str, Decimal]]] = {}
    for position, value in valued:
        industries.setdefault(position.industry or "UNKNOWN", []).append(
            (position.position_key, abs(value))
        )
    industry_warning = PortfolioWarning(
        code="UNCLASSIFIED_INDUSTRY",
        scope="portfolio",
        message="At least one valued position has no reviewed industry classification.",
    )
    industry_shares: list[tuple[str, Decimal, tuple[str, ...]]] = []
    for industry, rows in sorted(industries.items()):
        amount = _exact_sum(value for _, value in rows)
        keys = tuple(key for key, _ in rows)
        share = amount / gross_value if gross_value else Decimal("0")
        industry_shares.append((industry, share, keys))
        warnings = [*valuation_warnings]
        if industry == "UNKNOWN":
            warnings.append(industry_warning)
        if nav <= 0:
            warnings.append(nav_warning)
        metrics.append(
            _portfolio_metric(
                snapshot,
                metric_name=f"industry_weight::{industry}",
                value=None if nav <= 0 else share,
                unit="gross_share",
                status="unavailable" if nav <= 0 else "derived",
                position_keys=keys,
                warnings=warnings,
            )
        )

    max_industry = max(
        industry_shares,
        key=lambda item: (item[1], item[0]),
        default=("", Decimal("0"), ()),
    )
    unknown_rows = next(
        (item for item in industry_shares if item[0] == "UNKNOWN"),
        ("UNKNOWN", Decimal("0"), ()),
    )
    summary_industry_warnings = [*valuation_warnings]
    if unknown_rows[1] > 0:
        summary_industry_warnings.append(industry_warning)
    if nav <= 0:
        summary_industry_warnings.append(nav_warning)
    metrics.extend(
        [
            _portfolio_metric(
                snapshot,
                metric_name="max_industry_weight",
                value=None if nav <= 0 else max_industry[1],
                unit="gross_share",
                status="unavailable" if nav <= 0 else "derived",
                position_keys=max_industry[2],
                warnings=summary_industry_warnings,
            ),
            _portfolio_metric(
                snapshot,
                metric_name="unclassified_industry_weight",
                value=None if nav <= 0 else unknown_rows[1],
                unit="gross_share",
                status="unavailable" if nav <= 0 else "derived",
                position_keys=unknown_rows[2],
                warnings=summary_industry_warnings,
            ),
        ]
    )
    return tuple(metrics)


def deterministic_portfolio_evidence_json(
    snapshot: PortfolioSnapshot,
    *,
    target_symbol: str | None = None,
    stale_position_keys: Iterable[str] | None = None,
) -> str:
    return json.dumps(
        [
            metric.to_dict()
            for metric in calculate_portfolio_evidence_metrics(
                snapshot,
                target_symbol=target_symbol,
                stale_position_keys=stale_position_keys,
            )
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _target_position(snapshot: PortfolioSnapshot, symbol: str) -> tuple[Decimal, Decimal | None]:
    quantity = Decimal("0")
    value = Decimal("0")
    complete = True
    found = False
    for position in snapshot.positions:
        if position.symbol != symbol:
            continue
        found = True
        quantity += position.quantity
        base_value = position.value_in_base(snapshot.base_currency)
        if base_value is None:
            complete = False
        else:
            value += base_value
    if not found:
        return Decimal("0"), Decimal("0")
    return quantity, value if complete else None


@dataclass(frozen=True)
class PortfolioContext:
    reference_type: str
    reference_id: str
    reference_symbol: str
    reference_occurred_at: str
    before_snapshot: PortfolioSnapshot
    after_snapshot: PortfolioSnapshot | None = None

    def validate(self) -> None:
        if self.reference_type not in {"decision", "trade_episode"}:
            raise ModelValidationError(f"Unsupported context reference_type: {self.reference_type}")
        if not self.reference_id.strip() or not self.reference_symbol.strip():
            raise ModelValidationError("Portfolio context reference ID and symbol are required")
        reference_time = parse_datetime(self.reference_occurred_at, "UTC")
        if parse_datetime(self.before_snapshot.observed_at, "UTC") > reference_time:
            raise ModelValidationError("Before snapshot occurred after the review reference")
        if parse_datetime(self.before_snapshot.known_at, "UTC") > reference_time:
            raise ModelValidationError("Before snapshot was not known at the review reference time")
        if self.after_snapshot and parse_datetime(self.after_snapshot.observed_at, "UTC") < reference_time:
            raise ModelValidationError("After snapshot occurred before the review reference")

    @property
    def context_id(self) -> str:
        material = {
            "reference_type": self.reference_type,
            "reference_id": self.reference_id,
            "reference_symbol": self.reference_symbol,
            "reference_occurred_at": self.reference_occurred_at,
            "before_snapshot_id": self.before_snapshot.resolved_snapshot_id,
            "after_snapshot_id": (
                self.after_snapshot.resolved_snapshot_id if self.after_snapshot else None
            ),
        }
        return f"ctx_{sha256_text(canonical_json(material))[:32]}"

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        before_metrics = calculate_portfolio_metrics(self.before_snapshot)
        after_metrics = (
            calculate_portfolio_metrics(self.after_snapshot) if self.after_snapshot else None
        )
        before_quantity, before_value = _target_position(
            self.before_snapshot, self.reference_symbol
        )
        delta: dict[str, Any] | None = None
        if self.after_snapshot:
            after_quantity, after_value = _target_position(
                self.after_snapshot, self.reference_symbol
            )
            delta = {
                "symbol": self.reference_symbol,
                "before_quantity": _decimal_text(before_quantity),
                "after_quantity": _decimal_text(after_quantity),
                "quantity_change": _decimal_text(after_quantity - before_quantity),
                "before_value_base": _decimal_text(before_value),
                "after_value_base": _decimal_text(after_value),
                "value_change_base": (
                    _decimal_text(after_value - before_value)
                    if before_value is not None and after_value is not None
                    else None
                ),
                "status": (
                    "COMPLETE"
                    if before_value is not None and after_value is not None
                    else "MISSING_OR_UNCONVERTED_VALUE"
                ),
            }
        provenance = {
            "reference_type": self.reference_type,
            "reference_id": self.reference_id,
            "reference_occurred_at": self.reference_occurred_at,
            "before": {
                "snapshot_id": self.before_snapshot.resolved_snapshot_id,
                "source_id": self.before_snapshot.source_id,
                "source_path": self.before_snapshot.source_path,
                "observed_at": self.before_snapshot.observed_at,
                "known_at": self.before_snapshot.known_at,
                "payload_sha256": self.before_snapshot.payload_sha256,
            },
            "after": (
                {
                    "snapshot_id": self.after_snapshot.resolved_snapshot_id,
                    "source_id": self.after_snapshot.source_id,
                    "source_path": self.after_snapshot.source_path,
                    "observed_at": self.after_snapshot.observed_at,
                    "known_at": self.after_snapshot.known_at,
                    "payload_sha256": self.after_snapshot.payload_sha256,
                }
                if self.after_snapshot
                else None
            ),
        }
        return {
            "context_id": self.context_id,
            "portfolio_facts_available_at_reference": {
                "snapshot": self.before_snapshot.to_dict(),
                "metrics": before_metrics,
                "metric_evidence": [
                    item.to_dict()
                    for item in calculate_portfolio_evidence_metrics(self.before_snapshot)
                ],
            },
            "post_event_observation": (
                {
                    "snapshot": self.after_snapshot.to_dict(),
                    "metrics": after_metrics,
                    "target_position_change": delta,
                    "hindsight_boundary": "not_available_at_reference_time",
                }
                if self.after_snapshot
                else None
            ),
            "interpretation_candidates": [
                {
                    "claim_type": "interpretation",
                    "text": "组合指标只描述当时仓位结构，不能单独证明个股观点或交易动机。",
                }
            ],
            "alternative_explanations": [
                {
                    "claim_type": "alternative_explanation",
                    "text": "目标标的权重变化也可能由价格波动、现金流或其他持仓变化造成。",
                }
            ],
            "uncertainty": {
                "before_data_quality_flags": before_metrics["data_quality_flags"],
                "after_data_quality_flags": (
                    after_metrics["data_quality_flags"] if after_metrics else []
                ),
                "missing_after_snapshot": self.after_snapshot is None,
            },
            "provenance": provenance,
        }


def render_portfolio_context_markdown(context: Mapping[str, Any]) -> str:
    facts = context["portfolio_facts_available_at_reference"]
    metrics = facts["metrics"]
    provenance = context["provenance"]
    lines = [
        "## 组合仓位分析",
        "",
        "### 组合事实（决策时点可见）",
        "",
        f"- 快照：`{provenance['before']['snapshot_id']}`",
        f"- 事实时点：`{provenance['before']['observed_at']}`",
        f"- 系统可见时点：`{provenance['before']['known_at']}`",
        f"- 现金比例：`{metrics['cash_ratio']}`",
        f"- Gross / Net exposure：`{metrics['gross_exposure']}` / `{metrics['net_exposure']}`",
        f"- Top 1 / Top 5：`{metrics['top1_concentration']}` / `{metrics['top5_concentration']}`",
        f"- HHI：`{metrics['hhi_concentration']}`",
        "",
        "### 确定性指标与事后观察",
        "",
    ]
    post = context.get("post_event_observation")
    if post:
        change = post["target_position_change"]
        lines.append(
            f"- {change['symbol']} 数量变化：`{change['before_quantity']}` → "
            f"`{change['after_quantity']}`（`{change['quantity_change']}`）"
        )
        lines.append("- 事后快照明确隔离，未用于决策时点事实。")
    else:
        lines.append("- `MISSING`：尚无事后快照，无法计算目标标的仓位变化。")
    lines.extend([
        "",
        "### 解释候选与不确定性",
        "",
        "- 组合指标只描述仓位结构，不能单独证明个股观点或交易动机。",
        "- 替代解释：权重变化可能来自价格、现金流或其他持仓变化。",
        f"- 数据质量标记：`{len(context['uncertainty']['before_data_quality_flags'])}` 项。",
        "",
        "### 来源",
        "",
        f"- source_id：`{provenance['before']['source_id']}`",
        f"- source_path：`{provenance['before']['source_path']}`",
        f"- payload_sha256：`{provenance['before']['payload_sha256']}`",
        "",
    ])
    return "\n".join(lines)


def deterministic_context_json(context: PortfolioContext) -> str:
    return json.dumps(
        context.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def aggregate_flags(metrics: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Return a deterministic union for callers composing several contexts."""

    items = {
        (str(flag["code"]), str(flag["scope"]))
        for metric in metrics
        for flag in metric.get("data_quality_flags", [])
    }
    return [{"code": code, "scope": scope} for code, scope in sorted(items)]
