from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping


def build_valuation_model(
    *,
    metrics: list[Mapping[str, str]],
    output_peer_csv: Path,
    as_of_date: str,
) -> dict[str, object]:
    eps_rows = [row for row in metrics if row.get("metric_name") in {"basic_eps", "eps"}]
    eps = sorted(eps_rows, key=lambda row: row.get("period", ""))[-1] if eps_rows else {}
    peer_rows = [
        {
            "company": "英维克",
            "code": "002837",
            "business_relevance": "subject_company",
            "pe_ttm": "TODO_MARKET_DATA",
            "2026E_PE": "TODO_MODEL_INPUT",
            "2027E_PE": "TODO_MODEL_INPUT",
            "notes": "估值表存在，但实时估值字段需结构化行情快照补齐。",
        }
    ]
    output_peer_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_peer_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(peer_rows[0].keys()))
        writer.writeheader()
        writer.writerows(peer_rows)
    return {
        "as_of_date": as_of_date,
        "static_valuation": {
            "status": "TODO_MARKET_DATA",
            "supporting_metric_ids": [eps.get("metric_id", "TODO_METRIC_REQUIRED")],
        },
        "dynamic_valuation": {
            "status": "scenario_model_only",
            "claim_type": "inference",
            "no_target_price_instruction": True,
        },
        "peer_comparison": str(output_peer_csv),
        "scenarios": [
            {"scenario": "bear", "description": "收入增速低于 base，估值只保留场景区间口径。"},
            {"scenario": "base", "description": "基于历史收入的温和增长估计。"},
            {"scenario": "bull", "description": "收入增速高于 base，需订单和分业务证据验证。"},
        ],
        "conclusion": "当前仅形成场景估值框架，不形成交易动作或价格指令。",
    }
