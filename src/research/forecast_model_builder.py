from __future__ import annotations

from typing import Mapping


def _number(value: str) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def build_forecast_model(metrics: list[Mapping[str, str]]) -> dict[str, object]:
    revenue_rows = [row for row in metrics if row.get("metric_name") in {"total_revenue", "revenue"}]
    latest_revenue = sorted(revenue_rows, key=lambda row: row.get("period", ""))[-1] if revenue_rows else {}
    base = _number(latest_revenue.get("value", ""))
    metric_id = latest_revenue.get("metric_id", latest_revenue.get("metric_candidate_id", "TODO_METRIC_REQUIRED"))
    periods = ["2026E", "2027E", "2028E"]
    growth_rates = [0.08, 0.10, 0.10]
    revenue_forecast = []
    current = base
    for period, growth in zip(periods, growth_rates, strict=True):
        value = "TODO_MODEL_INPUT"
        if current is not None:
            current = current * (1 + growth)
            value = round(current, 2)
        revenue_forecast.append(
            {
                "period": period,
                "value": value,
                "unit": latest_revenue.get("unit", "CNY"),
                "claim_type": "estimate",
                "supporting_metric_ids": [metric_id],
                "assumption": f"base scenario revenue growth {growth:.0%}; estimate, not fact",
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
                "assumption_id": "assumption_revenue_growth_base",
                "description": "收入预测以公司层面历史收入为基准，暂不把公司收入归因到液冷业务。",
                "supporting_metric_ids": [metric_id],
                "claim_type": "estimate",
            }
        ],
        "sensitivity": [
            {
                "variable": "revenue_growth",
                "bear": "base - 5pct",
                "base": "see revenue_forecast",
                "bull": "base + 5pct",
            }
        ],
    }
