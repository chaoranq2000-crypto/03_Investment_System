from __future__ import annotations

from typing import Mapping


def build_catalyst_calendar(claims: list[Mapping[str, str]], as_of_date: str) -> dict[str, object]:
    claim_ids = [row.get("claim_id", "") for row in claims[:3] if row.get("claim_id")]
    return {
        "as_of_date": as_of_date,
        "events": [
            {
                "date_window": "next_reporting_window",
                "event": "下一期定期报告或经营更新",
                "impact_variable": "收入增速、毛利率、现金流、分业务披露",
                "upside_condition": "分业务或订单证据改善",
                "downside_risk": "收入兑现或现金流质量弱于模型假设",
                "evidence_ids_or_claim_ids": claim_ids or ["TODO_SOURCE_REQUIRED"],
                "claim_type": "estimate",
            }
        ],
    }
