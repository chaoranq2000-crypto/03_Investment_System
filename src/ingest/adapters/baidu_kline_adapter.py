from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from src.ingest.adapters.adapter_runtime import AdapterSpec, EndpointContract, FetchResult, adapter_main
from src.ingest.adapters.public_http import request_public


SPEC = AdapterSpec(
    adapter_id="baidu_kline_adapter",
    source_name="baidu_finance",
    source_group="market_data_adapter",
    source_type="structured_market_data",
    publisher="Baidu Finance",
    reliability_rank="C",
    material_claim_allowed="metric_only",
    allowed_claim_types="metric_snapshot",
    default_endpoint_hint="kline_with_ma",
    endpoints={
        "kline_with_ma": EndpointContract(
            expected_fields=("trade_date", "open", "high", "low", "close", "volume"),
            metric_fields={
                "open": "CNY", "high": "CNY", "low": "CNY", "close": "CNY",
                "volume": "shares", "amount": "CNY", "ma5": "CNY",
                "ma10": "CNY", "ma20": "CNY",
            },
        )
    },
    stale_after="1d",
)


def _key_name(item: Any) -> str:
    if isinstance(item, Mapping):
        return str(item.get("key") or item.get("name") or item.get("field") or "")
    return str(item)


def _rows(payload: Mapping[str, Any], stock_code: str) -> list[dict[str, Any]]:
    market = ((payload.get("Result") or {}).get("newMarketData") or {})
    keys = [_key_name(item) for item in market.get("keys", [])]
    raw_rows = market.get("marketData") or []
    if isinstance(raw_rows, str):
        raw_rows = [line.split(",") for line in raw_rows.split(";") if line.strip()]
    result: list[dict[str, Any]] = []
    for raw in raw_rows if isinstance(raw_rows, list) else []:
        if isinstance(raw, Mapping):
            item = dict(raw)
        elif isinstance(raw, list):
            item = dict(zip(keys, raw, strict=False))
        else:
            continue
        result.append(
            {
                "stock_code": stock_code,
                "trade_date": str(item.get("time") or item.get("date") or item.get("datetime") or "")[:10],
                "open": item.get("open"),
                "high": item.get("high"),
                "low": item.get("low"),
                "close": item.get("close"),
                "volume": item.get("volume") or item.get("vol"),
                "amount": item.get("amount"),
                "ma5": item.get("ma5avgprice") or item.get("ma5"),
                "ma10": item.get("ma10avgprice") or item.get("ma10"),
                "ma20": item.get("ma20avgprice") or item.get("ma20"),
                "adjustment_policy": "source_reported_unknown",
            }
        )
    return result


def fetch_live(args: Any) -> FetchResult:
    response = request_public(
        url="https://finance.pae.baidu.com/selfselect/getstockquotation",
        source_name="baidu_finance",
        capability="kline_with_ma",
        params={
            "all": "1", "isIndex": "false", "isBk": "false", "isBlock": "false",
            "isFutures": "false", "isStock": "true", "newFormat": "1",
            "group": "quotation_kline_ab", "finClientType": "pc", "code": args.stock_code,
            "start_time": args.begin_date.replace("-", ""), "ktype": "1",
        },
        referer="https://gushitong.baidu.com/",
        headers={"Accept": "application/vnd.finance-web.v1+json", "Origin": "https://gushitong.baidu.com"},
        min_interval_seconds=0.8,
    )
    payload = json.loads(response.body.decode("utf-8-sig"))
    rows = _rows(payload, args.stock_code)
    if not rows:
        raise ValueError("Baidu K-line response contained no marketData rows")
    return FetchResult(
        raw_payload=payload,
        rows=rows[-max(1, min(int(args.limit), 250)):],
        source_url=response.url,
        http_status=response.status,
        attempts=response.attempts,
        transport=response.transport,
        notes="Independent K-line enhancement; adjustment convention requires source reconciliation.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    return adapter_main(argv, spec=SPEC, live_fetcher=fetch_live, description="Archive Baidu K-line evidence.")


if __name__ == "__main__":
    raise SystemExit(main())
