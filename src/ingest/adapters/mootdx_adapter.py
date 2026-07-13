from __future__ import annotations

import socket
from typing import Any, Sequence

from src.ingest.adapters.adapter_runtime import (
    AdapterSpec,
    EndpointContract,
    FetchResult,
    adapter_main,
)


_SERVERS = (
    ("119.97.185.59", 7709),
    ("124.70.133.119", 7709),
    ("116.205.183.150", 7709),
    ("123.60.73.44", 7709),
    ("116.205.163.254", 7709),
    ("121.36.225.169", 7709),
)

SPEC = AdapterSpec(
    adapter_id="mootdx_adapter",
    source_name="mootdx",
    source_group="market_data_adapter",
    source_type="structured_market_data",
    publisher="TongdaXin via mootdx",
    reliability_rank="B",
    material_claim_allowed="metric_only",
    allowed_claim_types="metric_snapshot",
    default_endpoint_hint="daily_bar",
    endpoints={
        "daily_bar": EndpointContract(
            expected_fields=("trade_date", "open", "high", "low", "close", "volume"),
            metric_fields={
                "open": "CNY",
                "high": "CNY",
                "low": "CNY",
                "close": "CNY",
                "volume": "shares",
                "amount": "CNY",
            },
        ),
        "historical_daily_bar": EndpointContract(
            expected_fields=("trade_date", "open", "high", "low", "close", "volume"),
            metric_fields={
                "open": "CNY",
                "high": "CNY",
                "low": "CNY",
                "close": "CNY",
                "volume": "shares",
                "amount": "CNY",
            },
        ),
        "finance_snapshot": EndpointContract(
            expected_fields=("stock_code", "report_date"),
            claim_boundary="metric_only",
            empty_result_allowed=True,
        ),
        "f10": EndpointContract(
            expected_fields=("stock_code", "section", "text"),
            claim_fields=("text",),
            claim_type="clue",
            claim_boundary="clue_only_unless_official_archived",
            empty_result_allowed=True,
        ),
    },
    stale_after="1d",
)


def _reachable(ip: str, port: int, timeout: float = 0.8) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def _records(frame: Any, stock_code: str, server: str) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if hasattr(frame, "reset_index"):
        frame = frame.reset_index()
    records = frame.to_dict(orient="records") if hasattr(frame, "to_dict") else list(frame)
    rows: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "stock_code": stock_code,
                "trade_date": str(item.get("datetime") or item.get("date") or "")[:10],
                "open": item.get("open"),
                "high": item.get("high"),
                "low": item.get("low"),
                "close": item.get("close"),
                "volume": item.get("vol") if item.get("vol") is not None else item.get("volume"),
                "amount": item.get("amount"),
                "adjustment_policy": "none",
                "source_server": server,
            }
        )
    return rows


def fetch_live(args: Any) -> FetchResult:
    from mootdx.quotes import Quotes

    selected = next(((ip, port) for ip, port in _SERVERS if _reachable(ip, port)), None)
    if selected is None:
        raise RuntimeError("no configured TongdaXin TCP server is reachable")
    client = Quotes.factory(market="std", server=selected)
    try:
        endpoint_hint = str(args.endpoint_hint)
        if endpoint_hint in {"daily_bar", "historical_daily_bar"}:
            offset = max(10, min(int(args.limit or 120), 800))
            frame = client.bars(symbol=args.stock_code, frequency=9, offset=offset)
            rows = _records(frame, args.stock_code, f"{selected[0]}:{selected[1]}")
        elif endpoint_hint == "finance_snapshot":
            frame = client.finance(symbol=args.stock_code)
            records = frame.to_dict(orient="records") if hasattr(frame, "to_dict") else []
            rows = [
                {"stock_code": args.stock_code, "report_date": args.as_of_date, **dict(item)}
                for item in records
                if isinstance(item, dict)
            ]
        elif endpoint_hint == "f10":
            text = client.F10(symbol=args.stock_code, name="最新提示")
            rows = [{"stock_code": args.stock_code, "section": "最新提示", "text": str(text or "")}]
        else:
            raise ValueError(f"unsupported endpoint: {endpoint_hint}")
    finally:
        inner = getattr(client, "client", None)
        disconnect = getattr(inner, "disconnect", None)
        if callable(disconnect):
            disconnect()
    return FetchResult(
        raw_payload={"rows": rows, "server": f"{selected[0]}:{selected[1]}"},
        rows=rows,
        source_url="",
        transport="tcp",
        notes=(
            "Unadjusted TongdaXin prices; no research inference; "
            f"transport_endpoint=tdx://{selected[0]}:{selected[1]}/{args.stock_code}"
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    return adapter_main(
        argv,
        spec=SPEC,
        live_fetcher=fetch_live,
        description="Archive mootdx market/F10 evidence with operational receipts.",
    )


if __name__ == "__main__":
    raise SystemExit(main())
