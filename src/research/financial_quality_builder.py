from __future__ import annotations

from collections import defaultdict
from typing import Mapping


def latest_metrics_by_name(metrics: list[Mapping[str, str]]) -> dict[str, Mapping[str, str]]:
    by_name: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in metrics:
        by_name[row.get("metric_name", "")].append(row)
    latest = {}
    for name, rows in by_name.items():
        latest[name] = sorted(rows, key=lambda item: item.get("period", ""))[-1]
    return latest


def build_financial_quality(metrics: list[Mapping[str, str]]) -> dict[str, object]:
    latest = latest_metrics_by_name(metrics)
    selected_names = [
        "total_revenue",
        "net_profit_attributable",
        "n_income_attr_p",
        "gross_margin",
        "grossprofit_margin",
        "net_profit_margin",
        "netprofit_margin",
        "debt_to_assets",
        "net_operating_cash_flow",
        "n_cashflow_act",
        "accounts_receivable",
        "accounts_receiv",
        "inventories",
    ]
    ratios = []
    for name in selected_names:
        row = latest.get(name)
        if row:
            ratios.append(
                {
                    "metric_name": name,
                    "period": row.get("period", ""),
                    "value": row.get("value", ""),
                    "unit": row.get("unit", ""),
                    "metric_id": row.get("metric_id", row.get("metric_candidate_id", "")),
                    "source_evidence_id": row.get("source_evidence_id", ""),
                }
            )
    return {
        "summary": "公司层面财务指标已结构化；这些指标不直接证明具体业务或液冷收入暴露。",
        "income_statement": [item for item in ratios if item["metric_name"] in {"total_revenue", "net_profit_attributable", "n_income_attr_p"}],
        "cashflow": [item for item in ratios if item["metric_name"] in {"net_operating_cash_flow", "n_cashflow_act"}],
        "balance_sheet": [item for item in ratios if item["metric_name"] in {"debt_to_assets", "accounts_receivable", "accounts_receiv", "inventories"}],
        "ratios": ratios,
        "non_recurring_adjustments": "TODO_SOURCE_REQUIRED",
        "red_flags": ["MISSING: 分业务收入和液冷收入占比仍需官方表格或公告支持"],
    }
