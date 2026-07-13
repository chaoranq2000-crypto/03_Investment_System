from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from src.ingest.adapters.adapter_runtime import (
    AdapterSpec,
    EndpointContract,
    FetchResult,
    adapter_main,
)
from src.ingest.adapters.public_http import request_public, secid


SPEC = AdapterSpec(
    adapter_id="eastmoney_capital_adapter",
    source_name="eastmoney_push2",
    source_group="market_signal_adapter",
    source_type="structured_market_data",
    publisher="Eastmoney",
    reliability_rank="C",
    material_claim_allowed="metric_only",
    allowed_claim_types="metric_snapshot;clue",
    default_endpoint_hint="holder_count",
    endpoints={
        "lockup_expiry": EndpointContract(
            expected_fields=("event_date", "event_type", "shares"),
            metric_fields={"shares": "shares", "free_ratio": "percent"},
            claim_boundary="event_metric_only",
            empty_result_allowed=True,
        ),
        "holder_count": EndpointContract(
            expected_fields=("period", "holder_num"),
            metric_fields={
                "holder_num": "accounts",
                "change_num": "accounts",
                "change_ratio": "percent",
                "avg_shares": "shares_per_holder",
            },
            claim_boundary="metric_only_with_official_reconciliation",
        ),
        "dividend_history": EndpointContract(
            expected_fields=("event_date", "plan"),
            metric_fields={
                "bonus_rmb": "CNY_per_share",
                "transfer_ratio": "shares_per_10",
                "bonus_ratio": "shares_per_10",
            },
            claim_boundary="metric_only_with_official_reconciliation",
            empty_result_allowed=True,
        ),
        "margin_trading": EndpointContract(
            expected_fields=("period", "margin_balance"),
            metric_fields={"margin_balance": "CNY", "margin_purchase": "CNY"},
        ),
        "block_trade": EndpointContract(
            expected_fields=("period", "deal_price", "deal_amount"),
            metric_fields={"deal_price": "CNY", "deal_amount": "CNY"},
            empty_result_allowed=True,
        ),
        "fund_flow": EndpointContract(
            expected_fields=("period", "source_name"),
            metric_fields={
                "main_net": "CNY",
                "small_net": "CNY",
                "medium_net": "CNY",
                "large_net": "CNY",
                "super_large_net": "CNY",
            },
            claim_boundary="clue_only",
            empty_result_allowed=True,
        ),
    },
    stale_after="7d",
)


_DATACENTER = "https://datacenter-web.eastmoney.com/api/data/v1/get"


def _datacenter(args: Any, report_name: str, filter_text: str, sort: str) -> tuple[dict[str, Any], Any]:
    response = request_public(
        url=_DATACENTER,
        source_name="eastmoney_push2",
        capability=str(args.endpoint_hint),
        params={
            "reportName": report_name,
            "columns": "ALL",
            "filter": filter_text,
            "pageNumber": "1",
            "pageSize": str(max(1, min(args.page_size, 100))),
            "sortColumns": sort,
            "sortTypes": "-1",
            "source": "WEB",
            "client": "WEB",
        },
        referer="https://data.eastmoney.com/",
        min_interval_seconds=1.1,
    )
    return json.loads(response.body.decode("utf-8-sig")), response


def _rows_for(endpoint: str, data: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in data:
        if endpoint == "lockup_expiry":
            rows.append(
                {
                    "event_date": str(item.get("FREE_DATE") or "")[:10],
                    "event_type": item.get("FREE_SHARES_TYPE") or item.get("LIMITED_STOCK_TYPE") or "",
                    "shares": item.get("FREE_SHARES"),
                    "free_ratio": item.get("FREE_RATIO"),
                }
            )
        elif endpoint == "holder_count":
            rows.append(
                {
                    "period": str(item.get("END_DATE") or "")[:10],
                    "holder_num": item.get("HOLDER_NUM"),
                    "change_num": item.get("HOLDER_NUM_CHANGE"),
                    "change_ratio": item.get("HOLDER_NUM_RATIO"),
                    "avg_shares": item.get("AVG_FREE_SHARES"),
                }
            )
        elif endpoint == "dividend_history":
            rows.append(
                {
                    "event_date": str(item.get("EX_DIVIDEND_DATE") or item.get("NOTICE_DATE") or "")[:10],
                    "bonus_rmb": item.get("PRETAX_BONUS_RMB"),
                    "transfer_ratio": item.get("TRANSFER_RATIO"),
                    "bonus_ratio": item.get("BONUS_RATIO"),
                    "plan": item.get("ASSIGN_PROGRESS") or "",
                }
            )
        elif endpoint == "margin_trading":
            rows.append(
                {
                    "period": str(item.get("DATE") or "")[:10],
                    "margin_balance": item.get("RZYE"),
                    "margin_purchase": item.get("RZMRE"),
                    "short_balance": item.get("RQYE"),
                }
            )
        elif endpoint == "block_trade":
            rows.append(
                {
                    "period": str(item.get("TRADE_DATE") or "")[:10],
                    "deal_price": item.get("DEAL_PRICE"),
                    "deal_amount": item.get("DEAL_AMT"),
                    "buyer": item.get("BUYER_NAME") or "",
                    "seller": item.get("SELLER_NAME") or "",
                }
            )
    return rows


def fetch_live(args: Any) -> FetchResult:
    endpoint = str(args.endpoint_hint)
    if endpoint == "fund_flow":
        response = request_public(
            url="https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
            source_name="eastmoney_push2",
            capability=endpoint,
            params={
                "secid": secid(args.stock_code),
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63",
                "klt": "101",
                "lmt": str(max(1, min(args.limit, 120))),
            },
            referer="https://quote.eastmoney.com/",
            min_interval_seconds=1.1,
        )
        payload = json.loads(response.body.decode("utf-8-sig"))
        klines = ((payload.get("data") or {}).get("klines") or [])
        rows = []
        for line in klines:
            values = str(line).split(",")
            if len(values) < 6:
                continue
            rows.append(
                {
                    "period": values[0],
                    "main_net": values[1],
                    "small_net": values[2],
                    "medium_net": values[3],
                    "large_net": values[4],
                    "super_large_net": values[5],
                    "source_name": "eastmoney_push2",
                }
            )
    else:
        mapping = {
            "lockup_expiry": ("RPT_LIFT_STAGE", f'(SECURITY_CODE="{args.stock_code}")', "FREE_DATE"),
            "holder_count": ("RPT_HOLDERNUMLATEST", f'(SECURITY_CODE="{args.stock_code}")', "END_DATE"),
            "dividend_history": ("RPT_SHAREBONUS_DET", f'(SECURITY_CODE="{args.stock_code}")', "EX_DIVIDEND_DATE"),
            "margin_trading": ("RPTA_WEB_RZRQ_GGMX", f'(SCODE="{args.stock_code}")', "DATE"),
            "block_trade": ("RPT_DATA_BLOCKTRADE", f'(SECURITY_CODE="{args.stock_code}")', "TRADE_DATE"),
        }
        if endpoint not in mapping:
            raise ValueError(f"unsupported endpoint: {endpoint}")
        report, filter_text, sort = mapping[endpoint]
        payload, response = _datacenter(args, report, filter_text, sort)
        data = ((payload.get("result") or {}).get("data") or [])
        rows = _rows_for(endpoint, data)
    return FetchResult(
        raw_payload=payload,
        rows=rows,
        source_url=response.url,
        http_status=response.status,
        attempts=response.attempts,
        transport=response.transport,
        notes="Market/event snapshot only; official reconciliation remains required where declared.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    return adapter_main(argv, spec=SPEC, live_fetcher=fetch_live, description="Archive Eastmoney capital/event evidence.")


if __name__ == "__main__":
    raise SystemExit(main())
