from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode

from src.ingest.adapters.adapter_runtime import AdapterSpec, EndpointContract, FetchResult, adapter_main
from src.ingest.adapters.public_http import request_public


SPEC = AdapterSpec(
    adapter_id="cninfo_irm_adapter",
    source_name="cninfo_ir",
    source_group="company_source",
    source_type="company_ir_product",
    publisher="CNINFO IRM",
    reliability_rank="C",
    material_claim_allowed="false",
    allowed_claim_types="management_comment;company_claim",
    default_endpoint_hint="irm_interaction",
    endpoints={
        "irm_interaction": EndpointContract(
            expected_fields=("question", "answer", "ask_time", "source_url"),
            claim_fields=("answer",),
            claim_type="management_comment",
            claim_boundary="management_comment_only",
            empty_result_allowed=True,
        )
    },
    raw_bucket="company_ir_product",
    stale_after="30d",
)


def _date(value: Any) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
    return str(value or "")


def fetch_live(args: Any) -> FetchResult:
    first = request_public(
        url="https://irm.cninfo.com.cn/newircs/index/queryKeyboardInfo",
        source_name="cninfo_ir",
        capability="irm_interaction",
        method="POST",
        body=urlencode({"keyWord": args.stock_code}).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        referer="https://irm.cninfo.com.cn/",
        min_interval_seconds=0.5,
    )
    first_payload = json.loads(first.body.decode("utf-8-sig"))
    candidates = first_payload.get("data") or []
    if not candidates:
        payload = {"lookup": first_payload, "questions": {"rows": []}}
        return FetchResult(
            raw_payload=payload,
            rows=[],
            source_url=first.url,
            http_status=first.status,
            attempts=first.attempts,
            transport=first.transport,
            notes="No issuer match returned; explicit acquisition gap.",
        )
    org_id = str((candidates[0] or {}).get("secid") or "")
    params = {
        "_t": "1",
        "stockcode": args.stock_code,
        "orgId": org_id,
        "pageSize": str(max(1, min(args.page_size, 100))),
        "pageNum": "1",
        "keyWord": args.keyword,
        "startDay": args.begin_date,
        "endDay": args.end_date,
    }
    second = request_public(
        url="https://irm.cninfo.com.cn/newircs/company/question",
        source_name="cninfo_ir",
        capability="irm_interaction",
        params=params,
        method="POST",
        body=b"",
        referer="https://irm.cninfo.com.cn/",
        min_interval_seconds=0.5,
    )
    second_payload = json.loads(second.body.decode("utf-8-sig"))
    rows = []
    for item in second_payload.get("rows") or []:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "stock_code": str(item.get("stockCode") or args.stock_code),
                "company": str(item.get("companyShortName") or ""),
                "question": str(item.get("mainContent") or ""),
                "answer": str(item.get("attachedContent") or ""),
                "answerer": str(item.get("attachedAuthor") or ""),
                "ask_time": _date(item.get("pubDate")),
                "source_url": "https://irm.cninfo.com.cn/ircs/company/companyDetail?stockcode=" + args.stock_code,
            }
        )
    return FetchResult(
        raw_payload={"lookup": first_payload, "questions": second_payload},
        rows=rows,
        source_url=second.url,
        http_status=second.status,
        attempts=first.attempts + second.attempts,
        transport=second.transport,
        notes="Company answers are management comments and never issuer-reported segment revenue by themselves.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    return adapter_main(argv, spec=SPEC, live_fetcher=fetch_live, description="Archive CNINFO investor-interaction evidence.")


if __name__ == "__main__":
    raise SystemExit(main())
