from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from src.ingest.adapters.adapter_runtime import (
    AdapterSpec,
    EndpointContract,
    FetchResult,
    adapter_main,
)
from src.ingest.adapters.public_http import request_public


SPEC = AdapterSpec(
    adapter_id="eastmoney_industry_report_adapter",
    source_name="eastmoney_push2",
    source_group="third_party_analysis",
    source_type="third_party_research",
    publisher="Eastmoney reportapi",
    reliability_rank="C",
    material_claim_allowed="false",
    allowed_claim_types="analyst_view;estimate",
    default_endpoint_hint="industry_reportapi_metadata",
    endpoints={
        "industry_reportapi_metadata": EndpointContract(
            expected_fields=("title", "publisher", "publish_date", "info_code", "industry_name"),
            claim_fields=("title",),
            claim_type="analyst_view",
            claim_boundary="analyst_view_only",
        )
    },
    raw_bucket="industry_reports",
    stale_after="30d",
)


def _normalize(payload: Mapping[str, Any], keyword: str, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    needle = keyword.strip().lower()
    for item in payload.get("data") or []:
        if not isinstance(item, Mapping):
            continue
        title = str(item.get("title") or "")
        industry = str(item.get("industryName") or item.get("indvInduName") or "")
        if needle and needle not in f"{title} {industry}".lower():
            continue
        rows.append(
            {
                "title": title,
                "publisher": str(item.get("orgSName") or item.get("orgName") or ""),
                "publish_date": str(item.get("publishDate") or "")[:10],
                "info_code": str(item.get("infoCode") or ""),
                "industry_name": industry,
                "industry_code": str(item.get("industryCode") or ""),
                "rating": str(item.get("emRatingName") or ""),
                "report_type": str(item.get("reportType") or ""),
                "attach_pages": item.get("attachPages"),
                "attach_size_kb": item.get("attachSize"),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def fetch_live(args: Any) -> FetchResult:
    response = request_public(
        url="https://reportapi.eastmoney.com/report/list",
        source_name="eastmoney_push2",
        capability="industry_reportapi_metadata",
        params={
            "industryCode": args.industry_code or "*",
            "pageSize": str(max(1, min(args.page_size, 100))),
            "industry": "*",
            "rating": "*",
            "ratingChange": "*",
            "beginTime": args.begin_date or "2024-01-01",
            "endTime": args.end_date or args.as_of_date,
            "pageNo": "1",
            "fields": "",
            "qType": "1",
        },
        referer="https://data.eastmoney.com/report/",
        min_interval_seconds=1.1,
        timeout_seconds=30,
    )
    payload = json.loads(response.body.decode("utf-8-sig"))
    rows = _normalize(payload, args.keyword, max(1, args.limit))
    return FetchResult(
        raw_payload=payload,
        rows=rows,
        source_url=response.url,
        http_status=response.status,
        attempts=response.attempts,
        transport=response.transport,
        notes="Industry report titles are analyst views; PDF provenance is handled separately.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    return adapter_main(
        argv,
        spec=SPEC,
        live_fetcher=fetch_live,
        description="Archive Eastmoney industry-research metadata.",
    )


if __name__ == "__main__":
    raise SystemExit(main())
