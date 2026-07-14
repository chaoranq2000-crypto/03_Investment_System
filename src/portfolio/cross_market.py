from __future__ import annotations

import importlib
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


class CrossMarketFetchError(RuntimeError):
    """跨市场成分行业或历史行情接口不可用。"""


HK_CODE_PATTERN = re.compile(r"^\d{5}\.HK$")


def _records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if isinstance(frame, list):
        return [dict(item) for item in frame]
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict(orient="records"))
    raise CrossMarketFetchError(f"无法识别跨市场接口返回类型: {type(frame).__name__}")


def _chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


class EastmoneyHongKongIndustryProvider:
    """批量读取东方财富港股 F10 的公司所属行业。"""

    source = "eastmoney.RPT_HKF10_INFO_ORGPROFILE.BELONG_INDUSTRY"
    url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"

    def __init__(self, requester: Any | None = None) -> None:
        self.requester = requester

    def fetch_many(self, ts_codes: Iterable[str]) -> dict[str, str]:
        codes = sorted({code for code in ts_codes if HK_CODE_PATTERN.fullmatch(code)})
        if not codes:
            return {}
        requester = self.requester or importlib.import_module("requests")
        industries: dict[str, str] = {}
        for batch in _chunks(codes, 100):
            quoted = ",".join(f'"{code}"' for code in batch)
            params = {
                "reportName": "RPT_HKF10_INFO_ORGPROFILE",
                "columns": "SECUCODE,SECURITY_CODE,ORG_NAME,BELONG_INDUSTRY",
                "quoteColumns": "",
                "filter": f"(SECUCODE in ({quoted}))",
                "pageNumber": "1",
                "pageSize": "200",
                "source": "F10",
                "client": "PC",
            }
            try:
                response = requester.get(
                    self.url,
                    params=params,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": "https://emweb.securities.eastmoney.com/",
                    },
                    timeout=30,
                )
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                raise CrossMarketFetchError(
                    f"东方财富港股行业抓取失败: {type(exc).__name__}: {exc}"
                ) from exc
            if payload.get("success") is not True:
                raise CrossMarketFetchError(
                    f"东方财富港股行业接口返回失败: {payload.get('message') or 'unknown'}"
                )
            rows = ((payload.get("result") or {}).get("data") or [])
            for row in rows:
                code = str(row.get("SECUCODE") or "").strip()
                industry = str(row.get("BELONG_INDUSTRY") or "").strip()
                if code and industry:
                    industries[code] = industry
        return industries


class SinaHongKongCloseProvider:
    """通过 AKShare 的新浪港股历史行情适配器读取指定日期收盘价。"""

    source = "sina.stock_hk_daily.close"

    def __init__(self, akshare_module: Any | None = None) -> None:
        self.akshare_module = akshare_module

    def fetch_many(self, ts_codes: Iterable[str], trade_date: str) -> dict[str, Decimal]:
        if len(trade_date) != 8 or not trade_date.isdigit():
            raise CrossMarketFetchError(f"港股行情日期无效: {trade_date!r}")
        target = date.fromisoformat(
            f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
        )
        akshare = self.akshare_module or importlib.import_module("akshare")
        prices: dict[str, Decimal] = {}
        for code in sorted({item for item in ts_codes if HK_CODE_PATTERN.fullmatch(item)}):
            try:
                rows = _records(akshare.stock_hk_daily(symbol=code.split(".", 1)[0], adjust=""))
            except Exception:
                continue
            for row in rows:
                row_date = row.get("date")
                if str(row_date) != target.isoformat():
                    continue
                try:
                    close = Decimal(str(row.get("close")))
                except (InvalidOperation, TypeError):
                    continue
                if close > 0:
                    prices[code] = close
                break
        return prices
