from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any

from .cross_market import (
    EastmoneyHongKongIndustryProvider,
    SinaHongKongCloseProvider,
)
from .models import IndustryClassification, Instrument


class IndustryFetchError(RuntimeError):
    """行业分类接口不可用或返回格式异常。"""


UNCLASSIFIED_ETF = "未分类（ETF持仓覆盖不足）"
CROSS_INDUSTRY_ETF = "跨行业ETF"
TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "config" / "portfolio_industry_taxonomy.json"
CASH_PLACEHOLDER_KEYWORDS = ("申赎现金", "现金替代", "现金差额", "必须现金")


@dataclass(frozen=True)
class ThemeAggregation:
    theme: str
    corroborating_index_keywords: tuple[str, ...]
    compatible_industries: frozenset[str]
    minimum_share: Decimal


@dataclass(frozen=True)
class IndustryTaxonomy:
    taxonomy_id: str
    minimum_classified_weight_coverage: Decimal
    minimum_constituent_count_coverage: Decimal
    single_industry_high_confidence: Decimal
    single_industry_medium_confidence: Decimal
    theme_aggregations: tuple[ThemeAggregation, ...]
    aliases: dict[str, str]


@dataclass(frozen=True)
class _EtfEvidence:
    endpoint: str
    source_date: str
    weight_method: str
    rows: tuple[tuple[str, Decimal], ...]
    constituent_count: int
    constituent_industry_source: str
    close_price_source: str


_DEFAULT_PROVIDER = object()


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


def _decimal(value: Any) -> Decimal | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _date_text(value: Any) -> str:
    raw = _clean_text(value).replace("-", "")
    return raw if len(raw) == 8 and raw.isdigit() else ""


def _ratio_text(value: Decimal | None) -> str:
    if value is None:
        return "MISSING"
    return f"{value * Decimal('100'):.1f}%"


@lru_cache(maxsize=1)
def load_industry_taxonomy(path: str | Path = TAXONOMY_PATH) -> IndustryTaxonomy:
    config_path = Path(path)
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndustryFetchError(f"行业归一化配置读取失败: {config_path}: {exc}") from exc
    try:
        return IndustryTaxonomy(
            taxonomy_id=str(payload["taxonomy_id"]),
            minimum_classified_weight_coverage=Decimal(
                str(payload["minimum_classified_weight_coverage"])
            ),
            minimum_constituent_count_coverage=Decimal(
                str(payload["minimum_constituent_count_coverage"])
            ),
            single_industry_high_confidence=Decimal(
                str(payload["single_industry_high_confidence"])
            ),
            single_industry_medium_confidence=Decimal(
                str(payload["single_industry_medium_confidence"])
            ),
            theme_aggregations=tuple(
                ThemeAggregation(
                    theme=str(item["theme"]),
                    corroborating_index_keywords=tuple(
                        str(keyword) for keyword in item["corroborating_index_keywords"]
                    ),
                    compatible_industries=frozenset(
                        str(industry) for industry in item["compatible_industries"]
                    ),
                    minimum_share=Decimal(str(item["minimum_share"])),
                )
                for item in payload.get("theme_aggregations", [])
            ),
            aliases={str(key): str(value) for key, value in payload["aliases"].items()},
        )
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise IndustryFetchError(f"行业归一化配置字段无效: {config_path}: {exc}") from exc


def normalize_industry(raw_industry: str, taxonomy: IndustryTaxonomy | None = None) -> str:
    raw = _clean_text(raw_industry)
    if not raw:
        return ""
    rules = taxonomy or load_industry_taxonomy()
    return rules.aliases.get(raw, raw)


def _is_cash_placeholder(row: dict[str, Any]) -> bool:
    name = _clean_text(row.get("con_name") or row.get("name"))
    return any(keyword in name for keyword in CASH_PLACEHOLDER_KEYWORDS)


class TushareIndustryProvider:
    """股票按归一化行业分类，ETF 按可追溯成分篮子及权重智能分类。"""

    def __init__(
        self,
        pro: Any,
        *,
        taxonomy: IndustryTaxonomy | None = None,
        hk_industry_provider: Any = _DEFAULT_PROVIDER,
        hk_close_provider: Any = _DEFAULT_PROVIDER,
    ) -> None:
        self.pro = pro
        self.taxonomy = taxonomy or load_industry_taxonomy()
        self._daily_price_cache: dict[str, dict[str, Decimal]] = {}
        self.hk_industry_provider = (
            EastmoneyHongKongIndustryProvider()
            if hk_industry_provider is _DEFAULT_PROVIDER
            else hk_industry_provider
        )
        self.hk_close_provider = (
            SinaHongKongCloseProvider()
            if hk_close_provider is _DEFAULT_PROVIDER
            else hk_close_provider
        )
        self._hk_raw_industries: dict[str, str] = {}
        self._hk_prices: dict[str, dict[str, Decimal]] = {}

    def _stock_industries(self) -> tuple[dict[str, str], dict[str, str]]:
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
        raw_by_code: dict[str, str] = {}
        normalized_by_code: dict[str, str] = {}
        for row in _records(frame):
            ts_code = _clean_text(row.get("ts_code"))
            raw = _clean_text(row.get("industry"))
            if not ts_code or not raw:
                continue
            normalized = normalize_industry(raw, self.taxonomy)
            raw_by_code[ts_code] = raw
            normalized_by_code[ts_code] = normalized
            symbol = ts_code.split(".", 1)[0]
            raw_by_code.setdefault(symbol, raw)
            normalized_by_code.setdefault(symbol, normalized)
        return raw_by_code, normalized_by_code

    def _daily_prices(self, trade_date: str) -> dict[str, Decimal]:
        if trade_date in self._daily_price_cache:
            return self._daily_price_cache[trade_date]
        try:
            frame = self.pro.daily(
                trade_date=trade_date,
                fields="ts_code,close",
            )
        except Exception:
            self._daily_price_cache[trade_date] = {}
            return {}
        prices: dict[str, Decimal] = {}
        for row in _records(frame):
            code = _clean_text(row.get("ts_code"))
            close = _decimal(row.get("close"))
            if code and close is not None and close > 0:
                prices[code] = close
        self._daily_price_cache[trade_date] = prices
        return prices

    def _load_hk_industries(
        self,
        codes: set[str],
        normalized_by_code: dict[str, str],
    ) -> bool:
        missing = codes - self._hk_raw_industries.keys()
        if missing and self.hk_industry_provider is not None:
            try:
                self._hk_raw_industries.update(self.hk_industry_provider.fetch_many(missing))
            except Exception:
                pass
        for code in codes:
            raw = self._hk_raw_industries.get(code, "")
            if raw:
                normalized_by_code[code] = normalize_industry(raw, self.taxonomy)
        return any(code in normalized_by_code for code in codes)

    def _load_hk_prices(self, codes: set[str], trade_date: str) -> dict[str, Decimal]:
        cached = self._hk_prices.setdefault(trade_date, {})
        missing = codes - cached.keys()
        if missing and self.hk_close_provider is not None:
            try:
                cached.update(self.hk_close_provider.fetch_many(missing, trade_date))
            except Exception:
                pass
        return cached

    def _basket_evidence(
        self,
        instrument: Instrument,
        normalized_by_code: dict[str, str],
    ) -> _EtfEvidence | None:
        endpoint_name = "etf_sh_cons" if instrument.exchange == "SH" else "etf_sz_cons"
        endpoint = getattr(self.pro, endpoint_name, None)
        if endpoint is None:
            return None
        try:
            rows = _records(endpoint(ts_code=instrument.ts_code))
        except Exception:
            return None
        latest_date = max((_date_text(row.get("trade_date")) for row in rows), default="")
        if not latest_date:
            return None
        constituents = [
            row
            for row in rows
            if _date_text(row.get("trade_date")) == latest_date and not _is_cash_placeholder(row)
        ]
        constituent_codes = {
            _clean_text(row.get("con_code")) for row in constituents
        }
        hk_codes = {code for code in constituent_codes if code.endswith(".HK")}
        hk_industries_available = self._load_hk_industries(hk_codes, normalized_by_code)
        prices = self._daily_prices(latest_date)
        hk_prices = self._load_hk_prices(hk_codes, latest_date)
        weighted_rows: list[tuple[str, Decimal]] = []
        for row in constituents:
            code = _clean_text(row.get("con_code"))
            quantity = _decimal(row.get("qty"))
            close = prices.get(code) or hk_prices.get(code)
            if code and quantity is not None and quantity > 0 and close is not None:
                weighted_rows.append((code, quantity * close))
        if not constituents:
            return None
        return _EtfEvidence(
            endpoint=f"tushare.{endpoint_name}",
            source_date=latest_date,
            weight_method="quantity_close",
            rows=tuple(weighted_rows),
            constituent_count=len(constituents),
            constituent_industry_source="+".join(
                filter(
                    None,
                    (
                        "tushare.stock_basic.industry"
                        if any(code.endswith((".SH", ".SZ", ".BJ")) for code in constituent_codes)
                        else "",
                        getattr(self.hk_industry_provider, "source", "hk_industry_fallback")
                        if hk_industries_available and self.hk_industry_provider is not None
                        else "",
                    ),
                )
            ),
            close_price_source="+".join(
                filter(
                    None,
                    (
                        "tushare.daily"
                        if any(code in prices for code in constituent_codes)
                        else "",
                        getattr(self.hk_close_provider, "source", "hk_close_fallback")
                        if any(code in hk_prices for code in hk_codes)
                        and self.hk_close_provider is not None
                        else "",
                    ),
                )
            ),
        )

    def _portfolio_evidence(self, instrument: Instrument) -> _EtfEvidence | None:
        endpoint = getattr(self.pro, "fund_portfolio", None)
        if endpoint is None:
            return None
        try:
            rows = _records(endpoint(ts_code=instrument.ts_code))
        except Exception:
            return None
        latest_period = max((_date_text(row.get("end_date")) for row in rows), default="")
        if not latest_period:
            return None
        period_rows = [row for row in rows if _date_text(row.get("end_date")) == latest_period]
        weighted_rows: list[tuple[str, Decimal]] = []
        market_value_available = any(
            (_decimal(row.get("mkv")) or Decimal("0")) > 0 for row in period_rows
        )
        weight_field = "mkv" if market_value_available else "stk_mkv_ratio"
        for row in period_rows:
            code = _clean_text(row.get("symbol"))
            weight = _decimal(row.get(weight_field))
            if code and weight is not None and weight > 0:
                weighted_rows.append((code, weight))
        if not period_rows:
            return None
        return _EtfEvidence(
            endpoint="tushare.fund_portfolio",
            source_date=latest_period,
            weight_method=weight_field,
            rows=tuple(weighted_rows),
            constituent_count=len(period_rows),
            constituent_industry_source="tushare.stock_basic.industry",
            close_price_source="disclosed_market_value",
        )

    def _index_name(self, instrument: Instrument) -> str:
        endpoint = getattr(self.pro, "etf_basic", None)
        if endpoint is None:
            return ""
        try:
            rows = _records(
                endpoint(ts_code=instrument.ts_code, fields="ts_code,index_code,index_name")
            )
        except Exception:
            return ""
        return _clean_text(rows[0].get("index_name")) if rows else ""

    def _theme_aggregation(
        self,
        index_name: str,
        industry_weights: dict[str, Decimal],
        classified_weight: Decimal,
    ) -> tuple[str, Decimal]:
        if not index_name or classified_weight <= 0:
            return "", Decimal("0")
        for rule in self.taxonomy.theme_aggregations:
            if not any(keyword in index_name for keyword in rule.corroborating_index_keywords):
                continue
            compatible_weight = sum(
                (
                    weight
                    for industry, weight in industry_weights.items()
                    if industry in rule.compatible_industries
                ),
                Decimal("0"),
            )
            share = compatible_weight / classified_weight
            if share >= rule.minimum_share:
                return rule.theme, share
        return "", Decimal("0")

    def _classify_etf(
        self,
        instrument: Instrument,
        normalized_by_code: dict[str, str],
        now: str,
    ) -> tuple[IndustryClassification, bool]:
        evidence = self._basket_evidence(
            instrument, normalized_by_code
        ) or self._portfolio_evidence(instrument)
        index_name = self._index_name(instrument)
        if evidence is None:
            source = "holdings_unavailable"
            if index_name:
                source += f"|index={index_name}|index_role=corroboration_only"
            return (
                IndustryClassification(
                    instrument.ts_code,
                    UNCLASSIFIED_ETF,
                    source,
                    now,
                    method="holdings_unavailable",
                    confidence="unverified",
                ),
                False,
            )

        industry_weights: defaultdict[str, Decimal] = defaultdict(Decimal)
        total_weight = sum((weight for _, weight in evidence.rows), Decimal("0"))
        classified_weight = Decimal("0")
        classified_count = 0
        for code, weight in evidence.rows:
            industry = normalized_by_code.get(code)
            if not industry:
                continue
            industry_weights[industry] += weight
            classified_weight += weight
            classified_count += 1

        weight_coverage = (
            classified_weight / total_weight if total_weight > 0 else Decimal("0")
        )
        count_coverage = (
            Decimal(classified_count) / Decimal(evidence.constituent_count)
            if evidence.constituent_count
            else Decimal("0")
        )
        top_industry = ""
        top_share = Decimal("0")
        if industry_weights and classified_weight > 0:
            top_industry, top_weight = max(industry_weights.items(), key=lambda item: item[1])
            top_share = top_weight / classified_weight
        aggregated_theme, aggregated_share = self._theme_aggregation(
            index_name, industry_weights, classified_weight
        )

        sufficient = (
            weight_coverage >= self.taxonomy.minimum_classified_weight_coverage
            and count_coverage >= self.taxonomy.minimum_constituent_count_coverage
        )
        if not sufficient:
            industry_name = UNCLASSIFIED_ETF
            confidence = "unverified"
        elif aggregated_theme:
            industry_name = aggregated_theme
            top_industry = aggregated_theme
            top_share = aggregated_share
            confidence = (
                "high"
                if aggregated_share >= self.taxonomy.single_industry_high_confidence
                else "medium"
            )
        elif top_share >= self.taxonomy.single_industry_high_confidence:
            industry_name = top_industry
            confidence = "high"
        elif top_share >= self.taxonomy.single_industry_medium_confidence:
            industry_name = top_industry
            confidence = "medium"
        else:
            industry_name = CROSS_INDUSTRY_ETF
            confidence = "mixed"

        source_parts = [
            evidence.endpoint,
            f"as_of={evidence.source_date}",
            f"weight={evidence.weight_method}",
            f"industry_source={evidence.constituent_industry_source or 'MISSING'}",
            f"price_source={evidence.close_price_source or 'MISSING'}",
            f"coverage={_ratio_text(weight_coverage)}",
            f"count_coverage={_ratio_text(count_coverage)}",
            f"top={top_industry or 'MISSING'}:{_ratio_text(top_share)}",
            f"confidence={confidence}",
            f"taxonomy={self.taxonomy.taxonomy_id}",
        ]
        if index_name:
            source_parts.extend(
                (
                    f"index={index_name}",
                    (
                        "index_role=theme_aggregation_selector"
                        if aggregated_theme
                        else "index_role=corroboration_only"
                    ),
                )
            )
        return (
            IndustryClassification(
                ts_code=instrument.ts_code,
                industry_name=industry_name,
                source="|".join(source_parts),
                classified_at=now,
                method=evidence.weight_method,
                source_date=evidence.source_date,
                confidence=confidence,
                classified_weight_coverage=weight_coverage,
                constituent_count_coverage=count_coverage,
                top_industry_weight=top_share,
            ),
            sufficient,
        )

    def fetch_many(
        self, instruments: list[Instrument]
    ) -> tuple[list[IndustryClassification], list[str]]:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        classifications: list[IndustryClassification] = []
        missing: list[str] = []
        raw_by_code, normalized_by_code = self._stock_industries()

        for instrument in instruments:
            if instrument.asset_type == "equity":
                raw = raw_by_code.get(instrument.ts_code, "")
                industry_name = normalized_by_code.get(instrument.ts_code, "")
                if not industry_name:
                    missing.append(instrument.ts_code)
                    continue
                source = "tushare.stock_basic.industry"
                if industry_name != raw:
                    source += (
                        f"|raw={raw}|normalized={industry_name}"
                        f"|taxonomy={self.taxonomy.taxonomy_id}"
                    )
                classifications.append(
                    IndustryClassification(
                        ts_code=instrument.ts_code,
                        industry_name=industry_name,
                        source=source,
                        classified_at=now,
                        method="stock_basic_normalized",
                        confidence="high",
                    )
                )
            elif instrument.asset_type == "etf":
                classification, sufficient = self._classify_etf(
                    instrument, normalized_by_code, now
                )
                classifications.append(classification)
                if not sufficient:
                    missing.append(instrument.ts_code)
            else:
                missing.append(instrument.ts_code)
        return classifications, missing
