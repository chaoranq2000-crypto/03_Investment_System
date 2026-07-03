from __future__ import annotations

from typing import Mapping


def build_business_breakdown(claims: list[Mapping[str, str]]) -> dict[str, object]:
    exposure_claims = [
        row
        for row in claims
        if row.get("claim_type") in {"fact", "management_comment"}
        and any(keyword in row.get("claim_text", "") + row.get("quote_or_excerpt", "") for keyword in ["液冷", "数据中心", "温控", "热管理"])
    ]
    claim_ids = [row.get("claim_id", "") for row in exposure_claims if row.get("claim_id")]
    return {
        "business_lines": [
            {
                "name": "数据中心/机房温控及液冷相关解决方案",
                "revenue": "MISSING_DISCLOSURE",
                "revenue_pct": "MISSING_DISCLOSURE",
                "gross_margin": "MISSING_DISCLOSURE",
                "growth_driver": "AI算力与数据中心热管理需求，仍需订单/分产品收入证据确认兑现强度。",
                "claim_ids": claim_ids,
                "confidence": "medium" if claim_ids else "low",
                "notes": "产品/业务线索可支持 product/narrative exposure，不支持收入占比。",
            }
        ],
        "segment_links": [
            {
                "segment_id": "ai_server_liquid_cooling",
                "exposure_type": "product",
                "exposure_score": 3 if claim_ids else 1,
                "claim_ids": claim_ids,
                "confidence": "medium" if claim_ids else "low",
            }
        ],
        "missing_disclosures": [
            "MISSING_DISCLOSURE: 液冷收入占比",
            "MISSING_DISCLOSURE: 液冷毛利率",
            "MISSING_DISCLOSURE: 客户/订单/产能表格化证据",
        ],
    }
