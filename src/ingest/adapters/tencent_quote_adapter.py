from __future__ import annotations

import re
from typing import Any, Sequence

from src.ingest.adapters.adapter_runtime import (
    AdapterSpec,
    EndpointContract,
    FetchResult,
    adapter_main,
)
from src.ingest.adapters.public_http import market_prefix, request_public


QUOTE_FIELDS = {
    "price": "CNY",
    "last_close": "CNY",
    "open": "CNY",
    "high": "CNY",
    "low": "CNY",
    "volume": "shares",
    "amount_wan": "CNY_10k",
    "turnover_pct": "percent",
    "pe_ttm": "multiple",
    "mcap_yi": "CNY_100m",
    "float_mcap_yi": "CNY_100m",
    "pb": "multiple",
    "limit_up": "CNY",
    "limit_down": "CNY",
}

SPEC = AdapterSpec(
    adapter_id="tencent_quote_adapter",
    source_name="tencent_finance",
    source_group="market_data_adapter",
    source_type="structured_market_data",
    publisher="Tencent Finance",
    reliability_rank="B",
    material_claim_allowed="metric_only",
    allowed_claim_types="metric_snapshot",
    default_endpoint_hint="quote_and_valuation",
    endpoints={
        "quote_and_valuation": EndpointContract(
            expected_fields=("as_of_date", "price", "mcap_yi", "pe_ttm", "pb"),
            metric_fields=QUOTE_FIELDS,
        ),
        "quote_or_kline": EndpointContract(
            expected_fields=("trade_date", "open", "high", "low", "close", "volume"),
            metric_fields=QUOTE_FIELDS,
        ),
    },
    stale_after="1d",
)


def _number(values: list[str], index: int) -> float | None:
    if index >= len(values) or values[index] == "":
        return None
    try:
        return float(values[index])
    except ValueError:
        return None


def fetch_live(args: Any) -> FetchResult:
    stock_code = re.sub(r"\D", "", args.stock_code)
    symbol = f"{market_prefix(stock_code)}{stock_code}"
    response = request_public(
        url=f"https://qt.gtimg.cn/q={symbol}",
        source_name="tencent_finance",
        capability=str(args.endpoint_hint),
        headers={"Accept": "text/plain,*/*"},
        timeout_seconds=15,
        min_interval_seconds=0.2,
    )
    text = response.body.decode("gbk", errors="replace")
    match = re.search(r'="(.*?)"', text)
    if not match:
        raise ValueError("Tencent quote response lacks a delimited payload")
    values = match.group(1).split("~")
    if len(values) < 53:
        raise ValueError(f"Tencent quote field count drifted: {len(values)}")
    row = {
        "stock_code": stock_code,
        "name": values[1],
        "as_of_date": args.as_of_date,
        "trade_date": args.as_of_date,
        "price": _number(values, 3),
        "close": _number(values, 3),
        "last_close": _number(values, 4),
        "open": _number(values, 5),
        "volume": _number(values, 36),
        "change_amount": _number(values, 31),
        "change_pct": _number(values, 32),
        "high": _number(values, 33),
        "low": _number(values, 34),
        "amount_wan": _number(values, 37),
        "turnover_pct": _number(values, 38),
        "pe_ttm": _number(values, 39),
        "amplitude_pct": _number(values, 43),
        "mcap_yi": _number(values, 44),
        "float_mcap_yi": _number(values, 45),
        "pb": _number(values, 46),
        "limit_up": _number(values, 47),
        "limit_down": _number(values, 48),
        "volume_ratio": _number(values, 49),
        "pe_static": _number(values, 52),
    }
    return FetchResult(
        raw_payload={"rows": [row], "raw_field_count": len(values)},
        rows=[row],
        source_url=response.url,
        http_status=response.status,
        attempts=response.attempts,
        transport=response.transport,
        notes="Tencent field 43 is amplitude; PB is field 46.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    return adapter_main(
        argv,
        spec=SPEC,
        live_fetcher=fetch_live,
        description="Archive Tencent quote and valuation evidence.",
    )


if __name__ == "__main__":
    raise SystemExit(main())
