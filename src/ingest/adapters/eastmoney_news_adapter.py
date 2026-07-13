from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence

from src.ingest.adapters.adapter_runtime import AdapterSpec, EndpointContract, FetchResult, adapter_main
from src.ingest.adapters.public_http import decode_json, request_public


SPEC = AdapterSpec(
    adapter_id="eastmoney_news_adapter",
    source_name="eastmoney_push2",
    source_group="clue",
    source_type="news_social_clue",
    publisher="Eastmoney search",
    reliability_rank="D",
    material_claim_allowed="false",
    allowed_claim_types="clue",
    default_endpoint_hint="news_clue",
    endpoints={
        "news_clue": EndpointContract(
            expected_fields=("title", "publish_date", "source_url"),
            claim_fields=("title",),
            claim_type="clue",
            claim_boundary="clue_only",
            empty_result_allowed=True,
        ),
        "stock_news": EndpointContract(
            expected_fields=("title", "publish_date", "source_url"),
            claim_fields=("title",),
            claim_type="clue",
            claim_boundary="clue_only",
            empty_result_allowed=True,
        ),
    },
    raw_bucket="web_snapshots",
    stale_after="1d",
)


def fetch_live(args: Any) -> FetchResult:
    inner = json.dumps(
        {
            "uid": "",
            "keyword": args.stock_code,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "default",
                    "sort": "default",
                    "pageIndex": 1,
                    "pageSize": max(1, min(args.page_size, 50)),
                    "preTag": "",
                    "postTag": "",
                }
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    response = request_public(
        url="https://search-api-web.eastmoney.com/search/jsonp",
        source_name="eastmoney_push2",
        capability="news_clue",
        params={"cb": "jQuery_bundle8r", "param": inner},
        referer="https://so.eastmoney.com/",
        min_interval_seconds=1.1,
    )
    payload = decode_json(response.body)
    articles = ((payload.get("result") or {}).get("cmsArticleWebOld") or [])
    rows = []
    for item in articles:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "title": re.sub(r"<[^>]+>", "", str(item.get("title") or "")),
                "content_excerpt": re.sub(r"<[^>]+>", "", str(item.get("content") or ""))[:300],
                "publish_date": str(item.get("date") or "")[:10],
                "media_name": str(item.get("mediaName") or ""),
                "source_url": str(item.get("url") or ""),
            }
        )
    return FetchResult(
        raw_payload=payload,
        rows=rows,
        source_url=response.url,
        http_status=response.status,
        attempts=response.attempts,
        transport=response.transport,
        notes="D-rank clue only; never promoted directly to a material company fact.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    return adapter_main(argv, spec=SPEC, live_fetcher=fetch_live, description="Archive Eastmoney news clues.")


if __name__ == "__main__":
    raise SystemExit(main())
