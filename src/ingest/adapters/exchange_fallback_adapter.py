from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from src.ingest.adapters.adapter_runtime import AdapterSpec, EndpointContract, FetchResult, adapter_main
from src.ingest.adapters.public_http import request_public


SPEC = AdapterSpec(
    adapter_id="exchange_fallback_adapter",
    source_name="szse",
    source_group="official_disclosure",
    source_type="official_disclosure",
    publisher="Shenzhen Stock Exchange",
    reliability_rank="A",
    material_claim_allowed="true",
    allowed_claim_types="fact_after_extraction_and_review;management_comment",
    default_endpoint_hint="announcement_official",
    endpoints={
        "announcement_official": EndpointContract(
            expected_fields=("title", "publish_date", "pdf_url", "source_url"),
            claim_boundary="material_fact_after_review",
            empty_result_allowed=True,
        ),
        "dragon_tiger_official": EndpointContract(
            expected_fields=("stock_code", "period", "reason"),
            claim_boundary="market_context_only",
            empty_result_allowed=True,
        ),
    },
    raw_bucket="announcements",
    stale_after="30d",
)


def fetch_live(args: Any) -> FetchResult:
    if str(args.endpoint_hint) != "announcement_official":
        raise ValueError("this forward-close implementation enables announcement_official only")
    if not args.stock_code.startswith(("0", "3")):
        raise ValueError("live exchange fallback currently verified for SZSE-listed securities")
    request_body = {
        "channelCode": ["listedNotice_disc"],
        "pageSize": max(1, min(args.page_size, 100)),
        "pageNum": 1,
        "stock": [args.stock_code],
    }
    response = request_public(
        url="https://www.szse.cn/api/disc/announcement/annList",
        source_name="szse",
        capability="announcement_official",
        method="POST",
        body=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        referer="https://www.szse.cn/disclosure/listed/notice/index.html",
        min_interval_seconds=0.5,
    )
    payload = json.loads(response.body.decode("utf-8-sig"))
    rows = []
    for item in payload.get("data") or []:
        if not isinstance(item, Mapping):
            continue
        attach = str(item.get("attachPath") or "")
        pdf_url = f"https://disc.static.szse.cn/download{attach}" if attach else ""
        rows.append(
            {
                "stock_code": args.stock_code,
                "title": str(item.get("title") or ""),
                "publish_date": str(item.get("publishTime") or "")[:10],
                "pdf_url": pdf_url,
                "source_url": pdf_url or response.url,
            }
        )
    return FetchResult(
        raw_payload=payload,
        rows=rows,
        source_url=response.url,
        http_status=response.status,
        attempts=response.attempts,
        transport=response.transport,
        notes="Official exchange fallback; claims still require document extraction and review.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    return adapter_main(argv, spec=SPEC, live_fetcher=fetch_live, description="Archive official exchange announcement fallback evidence.")


if __name__ == "__main__":
    raise SystemExit(main())
