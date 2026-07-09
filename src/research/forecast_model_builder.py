from __future__ import annotations

import re
from typing import Any, Mapping

FORBIDDEN_ADVICE = re.compile(
    r"买入|卖出|持有|仓位|目标价|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing",
    re.IGNORECASE,
)


def _number(value: str) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    if isinstance(value, Mapping):
        return "\n".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    return value if isinstance(value, str) else ""


def _periods_include(raw_periods: Any, period: str) -> bool:
    if isinstance(raw_periods, list):
        return period in {str(item) for item in raw_periods}
    return str(raw_periods) == period


def _validate_reviewed_assumption(row: Mapping[str, Any]) -> None:
    if row.get("review_status") != "reviewed":
        return
    if not (row.get("supporting_evidence_ids") or row.get("supporting_metric_ids")):
        raise ValueError("reviewed forecast assumptions require evidence or metric anchors")
    if row.get("scope") in {"segment", "product"} and not row.get("business_disclosure_evidence_ids"):
        raise ValueError("segment/product forecast assumptions require reviewed business disclosure evidence")
    if FORBIDDEN_ADVICE.search(_text(row)):
        raise ValueError("forecast assumptions contain direct trading language")


def _registry_growth_rate(reviewed_assumptions: Mapping[str, Any], period: str) -> float | None:
    assumptions = reviewed_assumptions.get("assumptions")
    if not isinstance(assumptions, list):
        return None
    for row in assumptions:
        if not isinstance(row, Mapping):
            continue
        _validate_reviewed_assumption(row)
        if row.get("review_status") != "reviewed":
            continue
        if row.get("scenario") != "base":
            continue
        metric_name = str(row.get("metric_name", row.get("assumption_id", ""))).lower()
        if "revenue_growth" not in metric_name:
            continue
        if not _periods_include(row.get("periods"), period):
            continue
        try:
            return float(row.get("value"))
        except (TypeError, ValueError):
            return None
    return None


def _reviewed_growth_rate(reviewed_assumptions: Mapping[str, Any] | None, period: str) -> float | None:
    if not reviewed_assumptions:
        return None
    registry_growth = _registry_growth_rate(reviewed_assumptions, period)
    if registry_growth is not None:
        return registry_growth
    growth = reviewed_assumptions.get("revenue_growth")
    if not isinstance(growth, Mapping):
        return None
    value = growth.get(period)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_forecast_model(
    metrics: list[Mapping[str, str]],
    reviewed_assumptions: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    if reviewed_assumptions and FORBIDDEN_ADVICE.search(_text(reviewed_assumptions)):
        raise ValueError("forecast assumptions contain direct trading language")
    revenue_rows = [row for row in metrics if row.get("metric_name") in {"total_revenue", "revenue"}]
    latest_revenue = sorted(revenue_rows, key=lambda row: row.get("period", ""))[-1] if revenue_rows else {}
    base = _number(latest_revenue.get("value", ""))
    metric_id = latest_revenue.get("metric_id", latest_revenue.get("metric_candidate_id", "TODO_METRIC_REQUIRED"))
    periods = ["2026E", "2027E", "2028E"]
    revenue_forecast = []
    current = base
    has_reviewed_revenue_assumptions = False
    for period in periods:
        growth = _reviewed_growth_rate(reviewed_assumptions, period)
        value = "TODO_MODEL_INPUT"
        assumption = "TODO_MODEL_INPUT: reviewed revenue growth assumption is required"
        if current is not None and growth is not None:
            current = current * (1 + growth)
            value = round(current, 2)
            assumption = f"reviewed revenue growth assumption {growth:.2%}"
            has_reviewed_revenue_assumptions = True
        revenue_forecast.append(
            {
                "period": period,
                "value": value,
                "unit": latest_revenue.get("unit", "CNY"),
                "claim_type": "estimate",
                "supporting_metric_ids": [metric_id],
                "assumption": assumption,
            }
        )
    return {
        "periods": periods,
        "revenue_forecast": revenue_forecast,
        "margin_forecast": [
            {
                "period": period,
                "value": "TODO_MODEL_INPUT",
                "claim_type": "estimate",
                "supporting_metric_ids": [metric_id],
            }
            for period in periods
        ],
        "net_profit_forecast": [
            {
                "period": period,
                "value": "TODO_MODEL_INPUT",
                "claim_type": "estimate",
                "supporting_metric_ids": [metric_id],
            }
            for period in periods
        ],
        "key_assumptions": [
            {
                "assumption_id": "TODO_REVIEWED_REVENUE_GROWTH",
                "description": "公司层面历史收入只作为 anchor；缺 reviewed assumptions 时不得生成数字化收入预测。",
                "supporting_metric_ids": [metric_id],
                "claim_type": "unknown" if not has_reviewed_revenue_assumptions else "estimate",
            }
        ],
        "sensitivity": [
            {
                "variable": "revenue_growth",
                "bear": "TODO_MODEL_INPUT",
                "base": "TODO_MODEL_INPUT",
                "bull": "TODO_MODEL_INPUT",
            }
        ],
        "historical_metric_anchors": [
            {
                "metric_name": latest_revenue.get("metric_name", "revenue"),
                "period": latest_revenue.get("period"),
                "value": base,
                "unit": latest_revenue.get("unit", "CNY"),
                "metric_id": metric_id,
                "use_in_model": "historical_anchor_only",
                "claim_type": "metric_snapshot",
            }
        ]
        if latest_revenue
        else [],
        "reviewed_assumptions": {
            "status": "ready" if has_reviewed_revenue_assumptions else "TODO_MODEL_INPUT",
            "source": "reviewed_assumption_registry" if isinstance((reviewed_assumptions or {}).get("assumptions"), list) else "legacy_mapping_or_none",
            "items": (reviewed_assumptions or {}).get("assumptions", []),
        },
        "forecast_outputs": {
            "revenue_forecast": "ready" if has_reviewed_revenue_assumptions else "TODO_MODEL_INPUT",
            "margin_forecast": "TODO_MODEL_INPUT",
            "net_profit_forecast": "TODO_MODEL_INPUT",
            "eps_forecast": "TODO_MODEL_INPUT",
        },
        "limitations": [
            "Historical metric anchors are not forecast assumptions.",
            "Segment attribution remains blocked without reviewed business disclosure evidence.",
        ],
        "model_input_status": {
            "revenue_forecast": "ready" if has_reviewed_revenue_assumptions else "TODO_MODEL_INPUT",
            "margin_forecast": "TODO_MODEL_INPUT",
            "net_profit_forecast": "TODO_MODEL_INPUT",
            "eps_forecast": "TODO_MODEL_INPUT",
            "market_valuation_inputs": "TODO_MARKET_DATA",
            "peer_inputs": "TODO_PEER_DATA",
        },
        "no_advice_boundary": True,
    }
