from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Mapping, Sequence

from src.ingest.adapters.adapter_runtime import AdapterSpec, EndpointContract, FetchResult, adapter_main
from src.ingest.adapters.public_http import request_public


SPEC = AdapterSpec(
    adapter_id="cls_telegraph_adapter",
    source_name="cls_market",
    source_group="clue",
    source_type="news_social_clue",
    publisher="Cailianpress",
    reliability_rank="D",
    material_claim_allowed="false",
    allowed_claim_types="clue",
    default_endpoint_hint="telegraph",
    endpoints={
        "telegraph": EndpointContract(
            expected_fields=("title", "publish_date", "source_url"),
            claim_fields=("title",),
            claim_type="clue",
            claim_boundary="clue_only",
            empty_result_allowed=True,
        )
    },
    raw_bucket="web_snapshots",
    stale_after="1d",
)


def _signature(params: Mapping[str, str]) -> str:
    query = "&".join(f"{key}={params[key]}" for key in sorted(params))
    sha1_text = hashlib.sha1(query.encode("utf-8")).hexdigest()
    return hashlib.md5(sha1_text.encode("ascii")).hexdigest()


def fetch_live(args: Any) -> FetchResult:
    params = {
        "appName": "CailianpressWeb",
        "os": "web",
        "sv": "7.7.5",
        "last_time": "",
        "refresh_type": "1",
        "rn": str(max(1, min(args.page_size, 100))),
    }
    params["sign"] = _signature(params)
    response = request_public(
        url="https://www.cls.cn/v1/roll/get_roll_list",
        source_name="cls_market",
        capability="telegraph",
        params=params,
        referer="https://www.cls.cn/",
        min_interval_seconds=0.8,
    )
    payload = json.loads(response.body.decode("utf-8-sig"))
    raw_items = ((payload.get("data") or {}).get("roll_data") or [])
    keyword = str(args.keyword or "").strip().lower()
    rows: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, Mapping):
            continue
        title = str(item.get("title") or item.get("brief") or "")
        content = str(item.get("content") or item.get("brief") or "")
        if keyword and keyword not in f"{title} {content}".lower():
            continue
        timestamp = item.get("ctime")
        publish_date = ""
        if timestamp:
            publish_date = datetime.fromtimestamp(int(timestamp)).astimezone().isoformat(timespec="seconds")
        item_id = str(item.get("id") or item.get("roll_id") or "")
        rows.append(
            {
                "title": title,
                "content_excerpt": content[:500],
                "publish_date": publish_date,
                "source_url": f"https://www.cls.cn/detail/{item_id}" if item_id else "https://www.cls.cn/telegraph",
            }
        )
    return FetchResult(
        raw_payload=payload,
        rows=rows,
        source_url=response.url,
        http_status=response.status,
        attempts=response.attempts,
        transport=response.transport,
        notes="Global rolling-news clue only; keyword filtering does not establish a material company fact.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    return adapter_main(argv, spec=SPEC, live_fetcher=fetch_live, description="Archive CLS telegraph clues.")


if __name__ == "__main__":
    raise SystemExit(main())
