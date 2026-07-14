from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .economic_archetypes import ArchetypeRegistry, ContractError


@dataclass(frozen=True)
class SegmentResult:
    segment_id: str
    archetype_id: str
    method_tier: str
    scenario: str
    period: str
    revenue: float
    gross_profit: float
    operating_cost: float
    financial_expense: float
    proxy_revenue: float
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "archetype_id": self.archetype_id,
            "method_tier": self.method_tier,
            "scenario": self.scenario,
            "period": self.period,
            "revenue": round(self.revenue, 6),
            "gross_profit": round(self.gross_profit, 6),
            "operating_cost": round(self.operating_cost, 6),
            "financial_expense": round(self.financial_expense, 6),
            "proxy_revenue": round(self.proxy_revenue, 6),
            "notes": list(self.notes),
        }


def build_operating_driver_pack(
    plan: Mapping[str, Any],
    registry: ArchetypeRegistry,
    *,
    periods: list[str],
    scenarios: list[str],
    maximum_proxy_revenue_share: float = 0.45,
    reconciliation_tolerance: float = 1e-6,
) -> dict[str, Any]:
    results: list[SegmentResult] = []
    issues: list[dict[str, Any]] = []

    for segment in plan.get("segments", []):
        segment_id = str(segment.get("segment_id", "")).strip()
        archetype_id = str(segment.get("archetype_id", "")).strip()
        method_tier = str(segment.get("method_tier", "")).strip()
        if not segment_id or not archetype_id:
            issues.append(_issue("SEGMENT_ID_OR_ARCHETYPE_MISSING", "critical", segment_id or "unknown"))
            continue
        spec = registry.get(archetype_id)
        for scenario in scenarios:
            for period in periods:
                try:
                    result = _evaluate_segment(segment, spec.equation, scenario, period)
                except ContractError as exc:
                    issues.append(_issue("SEGMENT_EVALUATION_FAILED", "critical", segment_id, str(exc), scenario=scenario, period=period))
                    continue
                results.append(result)

    consolidated: list[dict[str, Any]] = []
    for scenario in scenarios:
        for period in periods:
            rows = [r for r in results if r.scenario == scenario and r.period == period]
            revenue = sum(r.revenue for r in rows)
            gross_profit = sum(r.gross_profit for r in rows)
            operating_cost = sum(r.operating_cost for r in rows)
            financial_expense = sum(r.financial_expense for r in rows)
            proxy_revenue = sum(r.proxy_revenue for r in rows)
            proxy_share = proxy_revenue / revenue if revenue else 0.0
            if proxy_share > maximum_proxy_revenue_share + reconciliation_tolerance:
                issues.append(
                    _issue(
                        "PROXY_REVENUE_SHARE_EXCEEDED",
                        "high",
                        "company",
                        f"{scenario}/{period}: {proxy_share:.4f} > {maximum_proxy_revenue_share:.4f}",
                        scenario=scenario,
                        period=period,
                    )
                )
            consolidated.append(
                {
                    "scenario": scenario,
                    "period": period,
                    "revenue": round(revenue, 6),
                    "gross_profit": round(gross_profit, 6),
                    "gross_margin": round(gross_profit / revenue, 8) if revenue else None,
                    "operating_cost": round(operating_cost, 6),
                    "financial_expense": round(financial_expense, 6),
                    "proxy_revenue": round(proxy_revenue, 6),
                    "proxy_revenue_share": round(proxy_share, 8),
                    "segment_count": len(rows),
                }
            )

    decision = "pass" if not any(i["severity"] in {"critical", "high"} for i in issues) else "needs_research_backflow"
    return {
        "schema_version": 1,
        "artifact_type": "r5_bundle11r_operating_driver_pack",
        "decision": decision,
        "periods": periods,
        "scenarios": scenarios,
        "segments": [r.as_dict() for r in results],
        "consolidated": consolidated,
        "issues": issues,
    }


def _evaluate_segment(segment: Mapping[str, Any], equation: str, scenario: str, period: str) -> SegmentResult:
    segment_id = str(segment["segment_id"])
    archetype_id = str(segment["archetype_id"])
    method_tier = str(segment.get("method_tier", "proxy"))
    notes: list[str] = []
    if method_tier == "proxy":
        revenue = _matrix_value(segment.get("proxy_revenue", {}), scenario, period, "proxy_revenue")
        gross_margin = _matrix_value(segment.get("proxy_gross_margin", {}), scenario, period, "proxy_gross_margin")
        if not segment.get("proxy_reason"):
            raise ContractError(f"{segment_id}: proxy_reason required")
        notes.append(f"proxy:{segment.get('proxy_reason')}")
        return SegmentResult(segment_id, archetype_id, method_tier, scenario, period, revenue, revenue * gross_margin, revenue * (1 - gross_margin), 0.0, revenue, tuple(notes))

    values = {key: _matrix_value(matrix, scenario, period, key) for key, matrix in segment.get("driver_values", {}).items()}
    gross_margin = _optional_matrix_value(segment.get("gross_margin"), scenario, period)
    unit_cost = values.get("unit_cost", values.get("cost_per_unit"))
    financial_expense = 0.0

    if equation == "volume_price_mix":
        revenue = values["volume"] * values["unit_price"] * values.get("mix_factor", 1.0)
        operating_cost = values["volume"] * unit_cost if unit_cost is not None else revenue * (1 - _required_margin(gross_margin, segment_id))
    elif equation == "capacity_utilization_price":
        revenue = values["installed_capacity"] * values["utilization"] * values["unit_revenue"]
        operating_cost = revenue * (1 - _required_margin(gross_margin, segment_id))
    elif equation == "backlog_conversion_recognition":
        revenue = values["backlog"] * values["conversion_rate"] * values["recognition_rate"]
        operating_cost = revenue * (1 - _required_margin(gross_margin, segment_id))
    elif equation == "project_unit_value_acceptance":
        revenue = values["project_count"] * values["unit_value"] * values["acceptance_rate"]
        operating_cost = revenue * (1 - _required_margin(gross_margin, segment_id))
    elif equation == "commodity_volume_recovery_cost":
        revenue = values["ore_or_sale_volume"] * values["commodity_price"] * values.get("recovery_rate", 1.0)
        operating_cost = values["ore_or_sale_volume"] * values["unit_cash_cost"]
    elif equation == "idc_capacity_utilization_unit_revenue":
        revenue = values["installed_capacity"] * values["utilization"] * values["unit_revenue"]
        power_cost = values.get("power_cost_per_unit", 0.0) * values["installed_capacity"] * values["utilization"]
        other_cost = revenue * values.get("other_cost_ratio", 0.0)
        operating_cost = power_cost + other_cost
    elif equation == "acquisition_consolidation_financing":
        revenue = values["target_revenue"] * values["consolidation_fraction"]
        operating_cost = revenue * (1 - values["target_gross_margin"])
        financial_expense = values.get("debt_funding", 0.0) * values.get("interest_rate", 0.0)
    elif equation == "customers_arpu":
        revenue = values["customers"] * values["arpu"]
        operating_cost = revenue * (1 - _required_margin(gross_margin, segment_id))
    else:
        raise ContractError(f"unsupported equation: {equation}")

    gross_profit = revenue - operating_cost
    return SegmentResult(segment_id, archetype_id, method_tier, scenario, period, revenue, gross_profit, operating_cost, financial_expense, 0.0, tuple(notes))


def _required_margin(value: float | None, segment_id: str) -> float:
    if value is None:
        raise ContractError(f"{segment_id}: gross_margin required when unit cost is unavailable")
    return value


def _matrix_value(matrix: Mapping[str, Any], scenario: str, period: str, name: str) -> float:
    try:
        value = matrix[scenario][period]
    except (KeyError, TypeError) as exc:
        raise ContractError(f"missing {name}[{scenario}][{period}]") from exc
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"non-numeric {name}[{scenario}][{period}]={value!r}") from exc
    if result != result or result in {float("inf"), float("-inf")}:
        raise ContractError(f"non-finite {name}[{scenario}][{period}]")
    return result


def _optional_matrix_value(matrix: Any, scenario: str, period: str) -> float | None:
    if not isinstance(matrix, Mapping):
        return None
    return _matrix_value(matrix, scenario, period, "gross_margin")


def _issue(code: str, severity: str, scope: str, message: str = "", **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "severity": severity, "scope": scope, "message": message}
    result.update(extra)
    return result
