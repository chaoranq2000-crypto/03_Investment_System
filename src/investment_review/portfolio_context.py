"""Deterministic portfolio context for evidence-first investment reviews.

The module keeps pre-decision facts separate from post-event observations.  It
does not infer motives, score decisions, or produce trading instructions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
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
    return format(value.normalize(), "f")


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
