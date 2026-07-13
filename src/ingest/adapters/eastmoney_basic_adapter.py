from __future__ import annotations

from typing import Any, Sequence

from src.ingest.adapters.adapter_runtime import (
    AdapterSpec,
    EndpointContract,
    FetchResult,
    adapter_main,
)
from src.ingest.adapters.public_http import request_public, secid


SPEC = AdapterSpec(
    adapter_id="eastmoney_basic_adapter",
    source_name="eastmoney_push2",
    source_group="market_data_adapter",
    source_type="structured_market_data",
    publisher="Eastmoney",
    reliability_rank="C",
    material_claim_allowed="metric_only",
    allowed_claim_types="metric_snapshot;classification_context",
    default_endpoint_hint="stock_info",
    endpoints={
        "stock_info": EndpointContract(
            expected_fields=("stock_code", "name", "industry", "total_shares", "mcap", "price"),
            metric_fields={
                "total_shares": "shares",
                "float_shares": "shares",
                "mcap": "CNY",
                "float_mcap": "CNY",
                "price": "CNY",
            },
        ),
        "concept_blocks": EndpointContract(
            expected_fields=("stock_code", "industry"),
            claim_boundary="classification_context",
        ),
    },
    stale_after="30d",
)


def fetch_live(args: Any) -> FetchResult:
    response = request_public(
        url="https://push2.eastmoney.com/api/qt/stock/get",
        source_name="eastmoney_push2",
        capability=str(args.endpoint_hint),
        params={
            "fltt": "2",
            "invt": "2",
            "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
            "secid": secid(args.stock_code),
        },
        referer="https://quote.eastmoney.com/",
        min_interval_seconds=1.1,
    )
    import json

    payload = json.loads(response.body.decode("utf-8-sig"))
    data = payload.get("data") or {}
    row = {
        "stock_code": str(data.get("f57") or args.stock_code),
        "name": data.get("f58"),
        "industry": data.get("f127"),
        "total_shares": data.get("f84"),
        "float_shares": data.get("f85"),
        "mcap": data.get("f116"),
        "float_mcap": data.get("f117"),
        "list_date": str(data.get("f189") or ""),
        "price": data.get("f43"),
        "as_of_date": args.as_of_date,
    }
    return FetchResult(
        raw_payload=payload,
        rows=[row],
        source_url=response.url,
        http_status=response.status,
        attempts=response.attempts,
        transport=response.transport,
        notes="Metric/classification context only; not evidence of segment exposure.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    return adapter_main(argv, spec=SPEC, live_fetcher=fetch_live, description="Archive Eastmoney stock information.")


if __name__ == "__main__":
    raise SystemExit(main())
