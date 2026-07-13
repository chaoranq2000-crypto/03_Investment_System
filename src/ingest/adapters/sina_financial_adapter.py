from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from src.ingest.adapters.adapter_runtime import AdapterSpec, EndpointContract, FetchResult, adapter_main
from src.ingest.adapters.public_http import market_prefix, request_public


SPEC = AdapterSpec(
    adapter_id="sina_financial_adapter",
    source_name="sina_finance",
    source_group="structured_database_fallback",
    source_type="structured_financial_data",
    publisher="Sina Finance",
    reliability_rank="C",
    material_claim_allowed="metric_only",
    allowed_claim_types="metric_snapshot",
    default_endpoint_hint="financial_statements",
    endpoints={
        "financial_statements": EndpointContract(
            expected_fields=("stock_code", "report_type", "period", "metric_name", "value"),
            metric_fields={"value": "source_reported_unit"},
            claim_boundary="metric_only",
        )
    },
    stale_after="90d",
)


def _statement_rows(stock_code: str, report_type: str, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    report_list = (((payload.get("result") or {}).get("data") or {}).get("report_list") or {})
    rows: list[dict[str, Any]] = []
    if not isinstance(report_list, Mapping):
        return rows
    for period in sorted(report_list, reverse=True)[:8]:
        obj = report_list.get(period) or {}
        for item in obj.get("data") or []:
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("item_title") or "").strip()
            value = item.get("item_value")
            if not name or value in (None, ""):
                continue
            rows.append(
                {
                    "stock_code": stock_code,
                    "report_type": report_type,
                    "period": f"{period[:4]}-{period[4:6]}-{period[6:8]}",
                    "metric_name": name,
                    "value": value,
                    "yoy": item.get("item_tongbi"),
                }
            )
    return rows


def fetch_live(args: Any) -> FetchResult:
    all_payloads: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
    source_urls: list[str] = []
    total_attempts = 0
    transport = "inherit"
    for report_type in ("fzb", "lrb", "llb"):
        response = request_public(
            url="https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022",
            source_name="sina_finance",
            capability="financial_statements",
            params={
                "paperCode": f"{market_prefix(args.stock_code)}{args.stock_code}",
                "source": report_type,
                "type": "0",
                "page": "1",
                "num": str(max(1, min(args.limit, 8))),
            },
            min_interval_seconds=0.5,
        )
        payload = json.loads(response.body.decode("utf-8-sig"))
        all_payloads[report_type] = payload
        all_rows.extend(_statement_rows(args.stock_code, report_type, payload))
        source_urls.append(response.url)
        total_attempts += response.attempts
        transport = response.transport
    return FetchResult(
        raw_payload=all_payloads,
        rows=all_rows,
        source_url=source_urls[0] if source_urls else "https://quotes.sina.cn/",
        http_status=200,
        attempts=total_attempts,
        transport=transport,
        notes=(
            "Metric-only convenience source; official filing tables control reported facts; "
            f"statement_endpoint_count={len(source_urls)}."
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    return adapter_main(argv, spec=SPEC, live_fetcher=fetch_live, description="Archive Sina financial statements.")


if __name__ == "__main__":
    raise SystemExit(main())
