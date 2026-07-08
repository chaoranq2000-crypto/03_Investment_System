from __future__ import annotations

from typing import Any, Mapping


def _number(value: str) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _reviewed_growth_rate(reviewed_assumptions: Mapping[str, Any] | None, period: str) -> float | None:
    if not reviewed_assumptions:
        return None
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
