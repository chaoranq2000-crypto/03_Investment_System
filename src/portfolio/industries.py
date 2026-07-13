from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import IndustryClassification, Instrument


class IndustryFetchError(RuntimeError):
    """行业分类接口不可用或返回格式异常。"""


ETF_THEME_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("医药", "医疗", "创新药", "生物科技"), "医药生物"),
    (("互联网",), "互联网"),
    (("半导体", "芯片"), "半导体"),
    (("证券",), "证券"),
    (("银行",), "银行"),
    (("军工",), "国防军工"),
    (("新能源", "光伏", "风电"), "新能源"),
    (("消费",), "消费"),
    (("白酒", "啤酒"), "食品饮料"),
    (("家电",), "家用电器"),
    (("传媒",), "传媒"),
    (("软件", "计算机", "人工智能"), "计算机"),
    (("汽车",), "汽车"),
)


def _records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if isinstance(frame, list):
        return [dict(item) for item in frame]
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict(orient="records"))
    raise IndustryFetchError(f"无法识别 Tushare 返回类型: {type(frame).__name__}")


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"nan", "none"} else text


def classify_etf_name(name: str) -> str | None:
    normalized = "".join(name.upper().split())
    for keywords, industry_name in ETF_THEME_RULES:
        if any(keyword.upper() in normalized for keyword in keywords):
            return industry_name
    return None


class TushareIndustryProvider:
    """股票使用 Tushare 行业字段，主题 ETF 使用名称中的明确行业属性。"""

    def __init__(self, pro: Any) -> None:
        self.pro = pro

    def fetch_many(
        self, instruments: list[Instrument]
    ) -> tuple[list[IndustryClassification], list[str]]:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        classifications: list[IndustryClassification] = []
        missing: list[str] = []

        equities = {item.ts_code: item for item in instruments if item.asset_type == "equity"}
        equity_industries: dict[str, str] = {}
        if equities:
            try:
                frame = self.pro.stock_basic(
                    exchange="",
                    list_status="L",
                    fields="ts_code,name,industry",
                )
            except Exception as exc:  # Tushare SDK 统一抛出 Exception
                raise IndustryFetchError(
                    f"stock_basic 行业分类抓取失败: {type(exc).__name__}: {exc}"
                ) from exc
            for row in _records(frame):
                ts_code = _clean_text(row.get("ts_code"))
                industry_name = _clean_text(row.get("industry"))
                if ts_code in equities and industry_name:
                    equity_industries[ts_code] = industry_name

        for instrument in instruments:
            if instrument.asset_type == "equity":
                industry_name = equity_industries.get(instrument.ts_code)
                source = "tushare.stock_basic.industry"
            elif instrument.asset_type == "etf":
                industry_name = classify_etf_name(instrument.name)
                source = "instrument_name.theme"
            else:
                industry_name = None
                source = ""

            if not industry_name:
                missing.append(instrument.ts_code)
                continue
            classifications.append(
                IndustryClassification(
                    ts_code=instrument.ts_code,
                    industry_name=industry_name,
                    source=source,
                    classified_at=now,
                )
            )
        return classifications, missing
