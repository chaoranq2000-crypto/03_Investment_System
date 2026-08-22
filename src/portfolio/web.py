from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import webbrowser
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.utils.tushare_client import get_tushare_pro, load_env_file
from src.investment_review.periodic_runner import (
    PeriodicReportAutomationCoordinator,
    periodic_automation_config,
)

from .industries import IndustryFetchError, TushareIndustryProvider
from .intraday import (
    IntradayFetchError,
    IntradayService,
    build_intraday_provider,
    build_live_intraday_provider,
)
from .kline import (
    KlineFetchError,
    KlineNotFoundError,
    KlineRefreshBusyError,
    KlineService,
    TushareKlineProvider,
)
from .models import decimal_to_text
from .prices import PriceFetchError, TushareCloseProvider
from .realtime import FallbackRealtimeProvider, RealtimeQuote
from .review_integration import (
    ReviewAutomationCoordinator,
    configured_review_database,
    review_automation_config,
)
from .runtime import repository_root
from .store import PortfolioStore
from .investment_review_service import (
    InvestmentReviewServiceError,
    InvestmentReviewWebService,
)


WEB_ASSET_DIR = Path(__file__).with_name("web_assets")
DASHBOARD_API_VERSION = 3
DASHBOARD_CAPABILITIES = (
    "daily-kline",
    "refresh-intraday",
    "live-intraday-1m",
    "auto-performance-history",
)
STATIC_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
REVIEW_ACCEPTANCE_TASK_ID = "investment_review_local_acceptance_readiness_v1"


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return decimal_to_text(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_iso_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field}必须是 YYYY-MM-DD: {value!r}") from exc


class ReviewHTTPError(ValueError):
    """Bounded HTTP failure for the local investment-review API."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = int(status)
        self.code = code


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReviewHTTPError(
                HTTPStatus.BAD_REQUEST,
                "duplicate_json_key",
                f"JSON 字段重复: {key}",
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ReviewHTTPError(
        HTTPStatus.BAD_REQUEST,
        "invalid_json_number",
        f"JSON 不允许非有限数值: {value}",
    )


class DashboardApplication:
    def __init__(
        self,
        store: PortfolioStore,
        *,
        account_id: str = "default",
        env_file: str | Path = ".env.local",
        realtime_provider: FallbackRealtimeProvider | None = None,
        live_intraday_provider: Any | None = None,
        realtime_cache_seconds: int = 55,
        investment_review_service: InvestmentReviewWebService | None = None,
        investment_review_error: ReviewHTTPError | None = None,
        review_acceptance_read_only: bool = False,
        review_candidate_sha256: str | None = None,
        review_artifact_root: str | Path | None = None,
    ) -> None:
        self.store = store
        self.account_id = account_id
        self.env_file = str(env_file)
        self.refresh_lock = threading.Lock()
        self.realtime_lock = threading.Lock()
        self.review_acceptance_read_only = bool(review_acceptance_read_only)
        self.review_candidate_sha256 = review_candidate_sha256
        self.review_artifact_root = (
            str(Path(review_artifact_root).resolve(strict=False))
            if review_artifact_root is not None
            else None
        )
        self.realtime_provider = (
            None
            if self.review_acceptance_read_only
            else (realtime_provider or FallbackRealtimeProvider())
        )
        self.live_intraday_provider = (
            None
            if self.review_acceptance_read_only
            else (live_intraday_provider or build_live_intraday_provider())
        )
        self.realtime_cache_seconds = realtime_cache_seconds
        self.investment_review_service = investment_review_service
        self.investment_review_error = investment_review_error
        self._realtime_cache: tuple[float, dict[str, Any]] | None = None
        self._performance_cache: tuple[tuple[Any, ...], dict[str, Any]] | None = None

    def portfolio_payload(
        self,
        as_of: date | None = None,
        *,
        quote_overrides: dict[str, RealtimeQuote] | None = None,
        market_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        positions, summary = self.store.position_report(self.account_id, as_of)
        closed_positions, clearance_summary = self.store.closed_position_report(
            self.account_id, as_of
        )
        closed_position_groups = self._closed_position_groups(closed_positions)
        metadata = dict(self.store.dashboard_metadata(self.account_id))
        live_quotes = quote_overrides or {}
        for position in positions:
            position["price_mode"] = "closing"
            position["quote_time"] = None
            position["is_live"] = False
            quote = live_quotes.get(position["ts_code"]) if as_of is None else None
            if quote is None:
                continue
            position["close"] = quote.price
            position["price_date"] = quote.quote_time[:10] or date.today().isoformat()
            position["price_source"] = quote.source
            position["pct_chg"] = quote.pct_chg
            position["market_value"] = quote.price * position["quantity"]
            position["unrealized_pnl"] = (
                position["market_value"] - position["remaining_cost"]
            )
            position["return_pct"] = (
                position["unrealized_pnl"]
                / position["remaining_cost"]
                * Decimal("100")
                if position["remaining_cost"] != 0
                else None
            )
            position["price_mode"] = "intraday"
            position["quote_time"] = quote.quote_time
            position["is_live"] = True

        remaining_cost = sum((item["remaining_cost"] for item in positions), Decimal("0"))
        missing_prices = [item["ts_code"] for item in positions if item["close"] is None]
        fully_priced = not missing_prices
        priced = [item for item in positions if item["market_value"] is not None]
        market_value = sum((item["market_value"] for item in priced), Decimal("0"))
        unrealized_pnl = sum((item["unrealized_pnl"] for item in priced), Decimal("0"))
        realized_pnl = summary["realized_pnl"]
        summary = {
            **summary,
            "remaining_cost": remaining_cost,
            "market_value": market_value if fully_priced else None,
            "total_assets": (
                market_value + summary["cash_balance"] if fully_priced else None
            ),
            "unrealized_pnl": unrealized_pnl if fully_priced else None,
            "unrealized_return_pct": (
                unrealized_pnl / remaining_cost * Decimal("100")
                if fully_priced and remaining_cost != 0
                else None
            ),
            "total_pnl_lifetime": (
                unrealized_pnl + realized_pnl if fully_priced else None
            ),
            "missing_prices": missing_prices,
            "latest_price_date": max(
                (item["price_date"] for item in positions if item["price_date"]),
                default=None,
            ),
        }
        total_assets = summary["total_assets"]
        enriched: list[dict[str, Any]] = []
        for position in positions:
            item = dict(position)
            item["weight_pct"] = (
                position["market_value"] / total_assets * Decimal("100")
                if position["market_value"] is not None
                and total_assets not in (None, Decimal("0"))
                else None
            )
            enriched.append(item)

        priced = [item for item in positions if item["unrealized_pnl"] is not None]
        summary = {
            **summary,
            "gain_count": sum(item["unrealized_pnl"] > 0 for item in priced),
            "loss_count": sum(item["unrealized_pnl"] < 0 for item in priced),
            "flat_count": sum(item["unrealized_pnl"] == 0 for item in priced),
            "equity_count": sum(item["asset_type"] == "equity" for item in positions),
            "etf_count": sum(item["asset_type"] == "etf" for item in positions),
            "cash_weight_pct": (
                summary["cash_balance"] / total_assets * Decimal("100")
                if total_assets not in (None, Decimal("0"))
                else None
            ),
        }
        industry_groups, industry_summary = self._industry_payload(
            enriched, summary["total_assets"]
        )
        pnl_performance = self._performance_payload(
            as_of,
            metadata,
            summary["total_pnl_lifetime"],
        )
        metadata["market_data"] = market_data or {
            "mode": "closing",
            "providers": sorted(
                {
                    item["price_source"]
                    for item in positions
                    if item["price_source"]
                }
            ),
            "live_quote_count": 0,
            "requested_count": len(positions),
            "missing": [],
            "errors": [],
            "quote_time": None,
            "fetched_at": metadata.get("last_tushare_fetch_at"),
            "refresh_interval_seconds": None,
        }
        return _json_ready(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "positions": enriched,
                "summary": summary,
                "industries": industry_groups,
                "industry_summary": industry_summary,
                "closed_positions": closed_positions,
                "closed_position_groups": closed_position_groups,
                "clearance_summary": clearance_summary,
                "pnl_performance": pnl_performance,
                "metadata": metadata,
                "boundary": "台账负责记录与核算；investment-review 可单独提供买卖与仓位建议，但不会自动下单。",
            }
        )

    def _performance_payload(
        self,
        as_of: date | None,
        metadata: dict[str, Any],
        current_total_pnl: Decimal | None,
    ) -> dict[str, Any]:
        target_date = as_of or date.today()
        cache_key = (
            target_date.isoformat(),
            metadata.get("ledger_count"),
            metadata.get("cost_rebase_count"),
            metadata.get("close_price_count"),
            metadata.get("last_price_fetch_at"),
        )
        if self._performance_cache is None or self._performance_cache[0] != cache_key:
            base_payload = self.store.performance_report(self.account_id, target_date)
            self._performance_cache = (cache_key, base_payload)
        else:
            base_payload = self._performance_cache[1]

        payload = deepcopy(base_payload)
        periods = payload.get("periods", {})
        lifetime_period = periods.get("all")
        base_total_pnl = lifetime_period.get("pnl") if lifetime_period else None
        if current_total_pnl is None or base_total_pnl is None:
            return payload
        delta = current_total_pnl - base_total_pnl

        def apply_current_delta(period: dict[str, Any]) -> None:
            if period.get("pnl") is None:
                return
            period["pnl"] += delta
            series = period.get("series", [])
            current_point = {"date": target_date, "pnl": period["pnl"]}
            if series and series[-1]["date"] == target_date:
                series[-1] = current_point
            else:
                series.append(current_point)

        for period in periods.values():
            apply_current_delta(period)
        for period in payload.get("recent_ranges", []):
            if period.get("end_date") == target_date:
                apply_current_delta(period)
        return payload

    def realtime_portfolio_payload(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._realtime_cache is not None:
            cached_at, cached_payload = self._realtime_cache
            if now - cached_at < self.realtime_cache_seconds:
                return cached_payload
        if not self.realtime_lock.acquire(blocking=False):
            if self._realtime_cache is not None:
                return self._realtime_cache[1]
            payload = self.portfolio_payload()
            payload["metadata"]["market_data"].update(
                {
                    "mode": "closing_fallback",
                    "errors": ["盘中行情刷新正在进行"],
                    "refresh_interval_seconds": 60,
                }
            )
            return payload
        try:
            instruments = self.store.instruments_for_open_positions(self.account_id)
            result = self.realtime_provider.fetch_many(instruments)
            quote_times = [
                quote.quote_time for quote in result.quotes.values() if quote.quote_time
            ]
            live_count = len(result.quotes)
            requested_count = len(instruments)
            mode = (
                "intraday"
                if live_count == requested_count and requested_count > 0
                else "mixed"
                if live_count > 0
                else "closing_fallback"
            )
            market_data = {
                "mode": mode,
                "providers": result.providers,
                "live_quote_count": live_count,
                "requested_count": requested_count,
                "missing": result.missing,
                "errors": result.errors,
                "quote_time": max(quote_times, default=None),
                "fetched_at": result.fetched_at,
                "refresh_interval_seconds": 60,
            }
            payload = self.portfolio_payload(
                quote_overrides=result.quotes,
                market_data=market_data,
            )
            self._realtime_cache = (time.monotonic(), payload)
            return payload
        finally:
            self.realtime_lock.release()

    @staticmethod
    def _closed_position_groups(
        cycles: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for cycle in cycles:
            ts_code = cycle["ts_code"]
            group = grouped.setdefault(
                ts_code,
                {
                    "group_id": f"security:{ts_code}",
                    "ts_code": ts_code,
                    "name": cycle["name"],
                    "asset_type": cycle["asset_type"],
                    "industry_name": cycle["industry_name"],
                    "industry_source": cycle["industry_source"],
                    "cycle_count": 0,
                    "opened_on": cycle["opened_on"],
                    "closed_on": cycle["closed_on"],
                    "sold_quantity": Decimal("0"),
                    "cost_basis": Decimal("0"),
                    "net_sale_proceeds": Decimal("0"),
                    "realized_pnl": Decimal("0"),
                    "sell_count": 0,
                    "cycles": [],
                },
            )
            group["cycle_count"] += 1
            group["opened_on"] = min(group["opened_on"], cycle["opened_on"])
            group["closed_on"] = max(group["closed_on"], cycle["closed_on"])
            group["sold_quantity"] += cycle["sold_quantity"]
            group["cost_basis"] += cycle["cost_basis"]
            group["net_sale_proceeds"] += cycle["net_sale_proceeds"]
            group["realized_pnl"] += cycle["realized_pnl"]
            group["sell_count"] += cycle["sell_count"]
            group["cycles"].append(cycle)

        result = list(grouped.values())
        for group in result:
            group["return_pct"] = (
                group["realized_pnl"] / group["cost_basis"] * Decimal("100")
                if group["cost_basis"] != 0
                else None
            )
            group["cycles"].sort(
                key=lambda item: (item["closed_on"], item["cycle_number"]),
                reverse=True,
            )
        result.sort(key=lambda item: (item["closed_on"], item["ts_code"]), reverse=True)
        return result

    @staticmethod
    def _industry_payload(
        positions: list[dict[str, Any]], total_market_value: Decimal | None
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        def is_reliably_classified(position: dict[str, Any]) -> bool:
            return bool(position["industry_classified"]) and not str(
                position["industry_name"]
            ).startswith("未分类")

        grouped: dict[str, dict[str, Any]] = {}
        for position in positions:
            industry_name = position["industry_name"]
            group = grouped.setdefault(
                industry_name,
                {
                    "industry_name": industry_name,
                    "position_count": 0,
                    "etf_count": 0,
                    "classified_position_count": 0,
                    "remaining_cost": Decimal("0"),
                    "market_value": Decimal("0"),
                    "unrealized_pnl": Decimal("0"),
                    "fully_priced": True,
                    "members": [],
                    "sources": set(),
                },
            )
            group["position_count"] += 1
            group["etf_count"] += int(position["asset_type"] == "etf")
            group["classified_position_count"] += int(is_reliably_classified(position))
            group["remaining_cost"] += position["remaining_cost"]
            if position["market_value"] is None or position["unrealized_pnl"] is None:
                group["fully_priced"] = False
            else:
                group["market_value"] += position["market_value"]
                group["unrealized_pnl"] += position["unrealized_pnl"]
            group["members"].append(
                {
                    "ts_code": position["ts_code"],
                    "name": position["name"],
                    "asset_type": position["asset_type"],
                    "industry_source": position["industry_source"],
                }
            )
            if position["industry_source"]:
                group["sources"].add(position["industry_source"])

        industries: list[dict[str, Any]] = []
        for group in grouped.values():
            market_value = group["market_value"] if group["fully_priced"] else None
            unrealized_pnl = group["unrealized_pnl"] if group["fully_priced"] else None
            remaining_cost = group["remaining_cost"]
            industries.append(
                {
                    "industry_name": group["industry_name"],
                    "position_count": group["position_count"],
                    "etf_count": group["etf_count"],
                    "classified": (
                        group["classified_position_count"] == group["position_count"]
                    ),
                    "remaining_cost": remaining_cost,
                    "market_value": market_value,
                    "unrealized_pnl": unrealized_pnl,
                    "return_pct": (
                        unrealized_pnl / remaining_cost * Decimal("100")
                        if unrealized_pnl is not None and remaining_cost != 0
                        else None
                    ),
                    "weight_pct": (
                        market_value / total_market_value * Decimal("100")
                        if market_value is not None
                        and total_market_value not in (None, Decimal("0"))
                        else None
                    ),
                    "members": group["members"],
                    "sources": sorted(group["sources"]),
                }
            )
        industries.sort(
            key=lambda item: (
                item["market_value"] is not None,
                item["market_value"] or Decimal("0"),
            ),
            reverse=True,
        )
        classified_positions = sum(
            int(is_reliably_classified(position)) for position in positions
        )
        classified_market_value = sum(
            (
                position["market_value"]
                for position in positions
                if is_reliably_classified(position) and position["market_value"] is not None
            ),
            Decimal("0"),
        )
        weights = [
            item["weight_pct"]
            for item in industries
            if item["classified"] and item["weight_pct"] is not None
        ]
        classified_industries = [item for item in industries if item["classified"]]
        summary = {
            "industry_count": sum(item["classified"] for item in industries),
            "classified_position_count": classified_positions,
            "unclassified_position_count": len(positions) - classified_positions,
            "position_coverage_pct": (
                Decimal(classified_positions) / Decimal(len(positions)) * Decimal("100")
                if positions
                else Decimal("0")
            ),
            "market_value_coverage_pct": (
                classified_market_value / total_market_value * Decimal("100")
                if total_market_value not in (None, Decimal("0"))
                else None
            ),
            "top_industry": (
                classified_industries[0]["industry_name"] if classified_industries else None
            ),
            "top_industry_weight_pct": weights[0] if weights else None,
            "top3_weight_pct": sum(weights[:3], Decimal("0")),
            "classification_note": (
                "股票按归一行业分类；主题 ETF 使用经复核的代码与跟踪指数映射，"
                "宽基或未复核 ETF 保留跨行业或未分类。"
            ),
        }
        return industries, summary

    def refresh_prices(
        self,
        *,
        as_of: date | None = None,
        lookback_days: int = 60,
    ) -> dict[str, Any]:
        if lookback_days < 1 or lookback_days > 3660:
            raise ValueError("lookback_days 必须在 1 到 3660 之间")
        target = as_of or date.today()
        if not self.refresh_lock.acquire(blocking=False):
            raise RuntimeError("已有一个行情刷新任务正在运行")
        try:
            instruments = self.store.instruments_for_open_positions(self.account_id, target)
            if not instruments:
                return {
                    "requested_as_of": target.isoformat(),
                    "fetched": 0,
                    "new_observations": 0,
                    "missing": [],
                }
            pro = get_tushare_pro(self.env_file)
            prices, missing = TushareCloseProvider(pro).fetch_many(
                instruments,
                as_of=target,
                lookback_days=lookback_days,
            )
            if missing:
                raise PriceFetchError(
                    "以下证券没有找到可用收盘价，未写入任何行情: " + ", ".join(missing)
                )
            inserted = self.store.add_close_prices(prices)
            self._performance_cache = None
            self._realtime_cache = None
            return _json_ready(
                {
                    "requested_as_of": target.isoformat(),
                    "fetched": len(prices),
                    "new_observations": inserted,
                    "missing": [],
                    "latest_trade_date": max(
                        (item.trade_date for item in prices), default=None
                    ),
                }
            )
        finally:
            self.refresh_lock.release()

    def refresh_performance_prices(
        self,
        *,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        """增量补齐盈亏曲线所需的历史收盘价。"""

        target_date = as_of or date.today()
        if not self.refresh_lock.acquire(blocking=False):
            raise RuntimeError("已有一个数据刷新任务正在运行")
        try:
            targets = self.store.performance_price_targets(
                self.account_id, target_date
            )
            if not targets:
                return {
                    "requested_as_of": target_date.isoformat(),
                    "security_count": 0,
                    "requested_range_count": 0,
                    "fetched_observations": 0,
                    "new_observations": 0,
                    "updated_security_count": 0,
                    "already_covered_count": 0,
                    "errors": [],
                }

            provider = TushareCloseProvider(get_tushare_pro(self.env_file))
            requested_range_count = 0
            fetched_observations = 0
            new_observations = 0
            updated_codes: set[str] = set()
            already_covered_count = 0
            errors: list[dict[str, str]] = []

            for item in targets:
                ts_code = item["ts_code"]
                start_date = item["start_date"]
                end_date = item["end_date"]
                coverage = self.store.performance_price_coverage(
                    self.account_id, ts_code
                )
                ranges: list[tuple[date, date]] = []
                if coverage is None:
                    ranges.append((start_date, end_date))
                else:
                    if start_date < coverage["start_date"]:
                        ranges.append(
                            (start_date, coverage["start_date"] - timedelta(days=1))
                        )
                    if end_date > coverage["end_date"]:
                        ranges.append(
                            (coverage["end_date"] + timedelta(days=1), end_date)
                        )
                if not ranges:
                    already_covered_count += 1
                    continue

                for range_start, range_end in ranges:
                    requested_range_count += 1
                    try:
                        prices = provider.fetch_range(
                            item["instrument"],
                            start_date=range_start,
                            end_date=range_end,
                        )
                    except PriceFetchError as exc:
                        errors.append(
                            {
                                "ts_code": ts_code,
                                "range": (
                                    f"{range_start.isoformat()}..{range_end.isoformat()}"
                                ),
                                "error": str(exc),
                            }
                        )
                        continue

                    # 短区间可能全部是周末或休市日，仍记录已请求范围；
                    # 较长区间完全无数据时保留为待重试，避免永久掩盖代码或接口异常。
                    if not prices and (range_end - range_start).days > 7:
                        errors.append(
                            {
                                "ts_code": ts_code,
                                "range": (
                                    f"{range_start.isoformat()}..{range_end.isoformat()}"
                                ),
                                "error": "Tushare 未返回任何收盘价",
                            }
                        )
                        continue

                    fetched_observations += len(prices)
                    new_observations += self.store.add_close_prices(prices)
                    self.store.record_performance_price_coverage(
                        self.account_id,
                        ts_code,
                        range_start,
                        range_end,
                    )
                    updated_codes.add(ts_code)

            if new_observations:
                self._performance_cache = None
                self._realtime_cache = None
            return _json_ready(
                {
                    "requested_as_of": target_date.isoformat(),
                    "security_count": len(targets),
                    "requested_range_count": requested_range_count,
                    "fetched_observations": fetched_observations,
                    "new_observations": new_observations,
                    "updated_security_count": len(updated_codes),
                    "already_covered_count": already_covered_count,
                    "errors": errors,
                }
            )
        finally:
            self.refresh_lock.release()

    def refresh_industries(self) -> dict[str, Any]:
        if not self.refresh_lock.acquire(blocking=False):
            raise RuntimeError("已有一个数据刷新任务正在运行")
        try:
            instruments = self.store.instruments_for_open_positions(self.account_id)
            if not instruments:
                return {"fetched": 0, "updated": 0, "missing": [], "classifications": []}
            pro = get_tushare_pro(self.env_file)
            classifications, missing = TushareIndustryProvider(pro).fetch_many(instruments)
            updated = self.store.set_industries(classifications)
            return _json_ready(
                {
                    "fetched": len(classifications),
                    "updated": updated,
                    "missing": missing,
                    "classifications": [
                        {
                            "ts_code": item.ts_code,
                            "industry_name": item.industry_name,
                            "source": item.source,
                            "method": item.method,
                            "source_date": item.source_date,
                            "confidence": item.confidence,
                        }
                        for item in classifications
                    ],
                }
            )
        finally:
            self.refresh_lock.release()

    def kline_payload(
        self,
        ts_code: str,
        *,
        range_key: str = "3m",
        cycle_id: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        return _json_ready(
            KlineService(self.store, account_id=self.account_id).get_payload(
                ts_code,
                range_key=range_key,
                cycle_id=cycle_id,
                as_of=as_of,
            )
        )

    def refresh_kline(
        self,
        ts_code: str,
        *,
        range_key: str = "3m",
        cycle_id: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        if not self.refresh_lock.acquire(blocking=False):
            raise KlineRefreshBusyError("已有一个数据刷新任务正在运行")
        try:
            provider = TushareKlineProvider(get_tushare_pro(self.env_file))
            return _json_ready(
                KlineService(self.store, account_id=self.account_id).refresh(
                    provider,
                    ts_code,
                    range_key=range_key,
                    cycle_id=cycle_id,
                    as_of=as_of,
                )
            )
        finally:
            self.refresh_lock.release()

    def intraday_payload(
        self,
        ts_code: str,
        *,
        trade_date: date | None = None,
        cycle_id: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        return _json_ready(
            IntradayService(self.store, account_id=self.account_id).get_payload(
                ts_code,
                trade_date=trade_date,
                cycle_id=cycle_id,
                as_of=as_of,
            )
        )

    def refresh_intraday(
        self,
        ts_code: str,
        *,
        trade_date: date,
        cycle_id: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        if not self.refresh_lock.acquire(blocking=False):
            raise KlineRefreshBusyError("已有一个数据刷新任务正在运行")
        try:
            return _json_ready(
                IntradayService(self.store, account_id=self.account_id).refresh(
                    build_intraday_provider(self.env_file),
                    ts_code,
                    trade_date=trade_date,
                    cycle_id=cycle_id,
                    as_of=as_of,
                )
            )
        finally:
            self.refresh_lock.release()

    def live_intraday(
        self,
        ts_code: str,
        *,
        trade_date: date,
        cycle_id: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        if not self.refresh_lock.acquire(blocking=False):
            raise KlineRefreshBusyError("已有一个数据刷新任务正在运行")
        try:
            return _json_ready(
                IntradayService(self.store, account_id=self.account_id).refresh_live(
                    self.live_intraday_provider,
                    ts_code,
                    trade_date=trade_date,
                    cycle_id=cycle_id,
                    as_of=as_of,
                )
            )
        finally:
            self.refresh_lock.release()


class DashboardHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], app: DashboardApplication) -> None:
        super().__init__(server_address, DashboardRequestHandler)
        self.dashboard_app = app


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server: DashboardHTTPServer

    def log_message(self, format_string: str, *args: Any) -> None:
        return

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'",
        )

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(_json_ready(payload), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_asset(self, path: str) -> None:
        asset = STATIC_ASSETS.get(path)
        if asset is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_name, content_type = asset
        file_path = WEB_ASSET_DIR / file_name
        if not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_review_error(
        self,
        error: ReviewHTTPError | InvestmentReviewServiceError,
    ) -> None:
        self._send_json(
            int(error.status),
            {
                "error": str(error),
                "code": error.code,
            },
        )

    def _health_payload(self) -> dict[str, Any]:
        app = self.server.dashboard_app
        payload: dict[str, Any] = {
            "status": "ok",
            "api_version": DASHBOARD_API_VERSION,
            "capabilities": list(DASHBOARD_CAPABILITIES),
        }
        if app.review_acceptance_read_only:
            payload.update(
                {
                    "review_acceptance_read_only": True,
                    "acceptance_task_id": REVIEW_ACCEPTANCE_TASK_ID,
                    "review_candidate_sha256": app.review_candidate_sha256,
                    "review_artifact_root": app.review_artifact_root,
                    "automation_enabled": False,
                    "external_network_allowed": False,
                    "human_product_acceptance": "pending",
                    "production_released": False,
                }
            )
        return payload

    def _send_acceptance_read_only(self) -> None:
        self._send_json(
            HTTPStatus.FORBIDDEN,
            {
                "error": "人工验收模式只允许读取投资复盘",
                "code": "review_acceptance_read_only",
            },
        )

    def _review_service(self) -> InvestmentReviewWebService:
        service = self.server.dashboard_app.investment_review_service
        if service is None:
            configured_error = (
                self.server.dashboard_app.investment_review_error
            )
            if configured_error is not None:
                raise configured_error
            raise ReviewHTTPError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "investment_review_unavailable",
                "本地投资复盘服务未配置",
            )
        if not service.read_only_acceptance:
            sync_service = service.sync_service
            if sync_service is None:
                raise ReviewHTTPError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "investment_review_unavailable",
                    "本地投资复盘映射缺失、未审核或来源绑定已失效",
                )
            try:
                # Reuse the strict sync preflight on every Review request so a
                # mapping removed or invalidated after startup closes all read
                # and write endpoints before stale sidecar content is exposed.
                sync_service.status()
            except Exception as exc:
                raise ReviewHTTPError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "investment_review_unavailable",
                    "本地投资复盘映射缺失、未审核或来源绑定已失效",
                ) from exc
        return service

    @staticmethod
    def _review_query(
        query_text: str,
        *,
        allowed: set[str],
        required: set[str] = frozenset(),
    ) -> dict[str, str]:
        query = parse_qs(query_text, keep_blank_values=True)
        unknown = sorted(set(query) - allowed)
        if unknown:
            raise ReviewHTTPError(
                HTTPStatus.BAD_REQUEST,
                "unexpected_query_field",
                "不支持的查询字段: " + ", ".join(unknown),
            )
        duplicate = sorted(key for key, values in query.items() if len(values) != 1)
        if duplicate:
            raise ReviewHTTPError(
                HTTPStatus.BAD_REQUEST,
                "duplicate_query_field",
                "查询字段必须且只能出现一次: " + ", ".join(duplicate),
            )
        result = {key: values[0] for key, values in query.items()}
        missing = sorted(key for key in required if not result.get(key))
        if missing:
            raise ReviewHTTPError(
                HTTPStatus.BAD_REQUEST,
                "missing_query_field",
                "缺少查询字段: " + ", ".join(missing),
            )
        return result

    def _review_get(self, parsed: Any) -> bool:
        routes = {
            "/api/investment-review/reviews",
            "/api/investment-review/review",
            "/api/investment-review/timeline",
            "/api/investment-review/context",
            "/api/investment-review/evidence",
            "/api/investment-review/health",
            "/api/investment-review/periodic-reports",
            "/api/investment-review/periodic-report",
        }
        if parsed.path not in routes:
            return False
        self._validate_review_host()
        service = self._review_service()
        if parsed.path == "/api/investment-review/health":
            if parsed.query:
                self._review_query(parsed.query, allowed=set())
            payload = service.get_health()
        elif parsed.path == "/api/investment-review/reviews":
            query = self._review_query(
                parsed.query,
                allowed={"scope", "status", "limit"},
            )
            try:
                limit = int(query.get("limit", "100"))
            except ValueError as exc:
                raise ReviewHTTPError(
                    HTTPStatus.BAD_REQUEST,
                    "invalid_limit",
                    "limit 必须是整数",
                ) from exc
            payload = service.list_reviews(
                scope=query.get("scope"),
                status=query.get("status"),
                limit=limit,
            )
        elif parsed.path == "/api/investment-review/periodic-reports":
            query = self._review_query(
                parsed.query,
                allowed={
                    "subject_type",
                    "subject_id",
                    "period_type",
                    "limit",
                },
            )
            try:
                limit = int(query.get("limit", "100"))
            except ValueError as exc:
                raise ReviewHTTPError(
                    HTTPStatus.BAD_REQUEST,
                    "invalid_limit",
                    "limit 必须是整数",
                ) from exc
            payload = service.list_periodic_reports(
                subject_type=query.get("subject_type"),
                subject_id=query.get("subject_id"),
                period_type=query.get("period_type"),
                limit=limit,
            )
        elif parsed.path == "/api/investment-review/periodic-report":
            query = self._review_query(
                parsed.query,
                allowed={"report_id"},
                required={"report_id"},
            )
            payload = service.get_periodic_report(query["report_id"])
        else:
            query = self._review_query(
                parsed.query,
                allowed={"run_id", "review_id"},
                required={"run_id", "review_id"},
            )
            arguments = (query["run_id"], query["review_id"])
            method = {
                "/api/investment-review/review": service.get_review_detail,
                "/api/investment-review/timeline": service.get_timeline,
                "/api/investment-review/context": service.get_context,
                "/api/investment-review/evidence": service.get_evidence,
            }[parsed.path]
            payload = method(*arguments)
        self._send_json(HTTPStatus.OK, payload)
        return True

    def _read_review_json(self) -> dict[str, Any]:
        transfer_encoding = self.headers.get("Transfer-Encoding")
        if transfer_encoding and transfer_encoding.lower() != "identity":
            raise ReviewHTTPError(
                HTTPStatus.BAD_REQUEST,
                "unsupported_transfer_encoding",
                "复盘接口不接受分块请求体",
            )
        content_type = self.headers.get("Content-Type", "")
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            raise ReviewHTTPError(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "unsupported_media_type",
                "复盘接口只接受 application/json",
            )
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ReviewHTTPError(
                HTTPStatus.BAD_REQUEST,
                "content_length_required",
                "复盘接口要求 Content-Length",
            )
        try:
            content_length = int(raw_length)
        except ValueError as exc:
            raise ReviewHTTPError(
                HTTPStatus.BAD_REQUEST,
                "invalid_content_length",
                "Content-Length 必须是非负整数",
            ) from exc
        if content_length < 0:
            raise ReviewHTTPError(
                HTTPStatus.BAD_REQUEST,
                "invalid_content_length",
                "Content-Length 必须是非负整数",
            )
        if content_length > 65536:
            raise ReviewHTTPError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "request_body_too_large",
                "复盘请求体不能超过 65536 字节",
            )
        raw = self.rfile.read(content_length)
        if len(raw) != content_length:
            raise ReviewHTTPError(
                HTTPStatus.BAD_REQUEST,
                "incomplete_request_body",
                "复盘请求体长度不完整",
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ReviewHTTPError(
                HTTPStatus.BAD_REQUEST,
                "invalid_utf8",
                "复盘请求体必须是 UTF-8",
            ) from exc
        try:
            payload = json.loads(
                text,
                object_pairs_hook=_unique_json_object,
                parse_constant=_reject_json_constant,
            )
        except ReviewHTTPError:
            raise
        except json.JSONDecodeError as exc:
            raise ReviewHTTPError(
                HTTPStatus.BAD_REQUEST,
                "invalid_json",
                "复盘请求体不是有效 JSON",
            ) from exc
        if not isinstance(payload, dict):
            raise ReviewHTTPError(
                HTTPStatus.BAD_REQUEST,
                "json_object_required",
                "复盘请求体必须是 JSON 对象",
            )
        return payload

    def _validate_review_host(self) -> None:
        raw_host = self.headers.get("Host", "").strip()
        try:
            parsed = urlparse("//" + raw_host)
            hostname = (parsed.hostname or "").lower()
            _ = parsed.port
        except ValueError as exc:
            raise ReviewHTTPError(
                HTTPStatus.FORBIDDEN,
                "host_not_allowed",
                "复盘接口只接受本机回环 Host",
            ) from exc
        if (
            not raw_host
            or parsed.username is not None
            or parsed.password is not None
            or hostname not in {"127.0.0.1", "localhost", "::1"}
        ):
            raise ReviewHTTPError(
                HTTPStatus.FORBIDDEN,
                "host_not_allowed",
                "复盘接口只接受本机回环 Host",
            )

    def _validate_review_origin(self) -> None:
        origin = self.headers.get("Origin")
        if not origin:
            return
        parsed = urlparse(origin)
        host = self.headers.get("Host", "")
        if (
            parsed.scheme != "http"
            or not parsed.netloc
            or parsed.netloc.lower() != host.lower()
        ):
            raise ReviewHTTPError(
                HTTPStatus.FORBIDDEN,
                "origin_not_allowed",
                "复盘写入只接受同源本地请求",
            )

    def _review_post(self, parsed: Any) -> bool:
        actions = {
            "/api/investment-review/decision": (
                "decision",
                "create_decision",
            ),
            "/api/investment-review/link": (
                "link",
                "link_decision",
            ),
            "/api/investment-review/fee-correction": (
                "fee-correction",
                "correct_fee",
            ),
            "/api/investment-review/review-correction": (
                "review-correction",
                "correct_review",
            ),
        }
        route = actions.get(parsed.path)
        if route is None:
            return False
        self._validate_review_host()
        service = self._review_service()
        if parsed.query or parsed.fragment:
            raise ReviewHTTPError(
                HTTPStatus.BAD_REQUEST,
                "unexpected_route_parameters",
                "复盘写入接口不接受查询参数或片段",
            )
        expected_action, method_name = route
        if self.headers.get("X-Investment-Review-Action") != expected_action:
            raise ReviewHTTPError(
                HTTPStatus.FORBIDDEN,
                "review_action_required",
                "缺少本地复盘写入确认头",
            )
        self._validate_review_origin()
        payload = self._read_review_json()
        result = getattr(service, method_name)(payload)
        self._send_json(HTTPStatus.OK, result)
        return True

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        try:
            if self.server.dashboard_app.review_acceptance_read_only:
                if parsed.path == "/health":
                    self._send_json(HTTPStatus.OK, self._health_payload())
                    return
                if parsed.path.startswith("/api/investment-review"):
                    if self._review_get(parsed):
                        return
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                if parsed.path.startswith("/api/"):
                    self._send_acceptance_read_only()
                    return
                self._send_asset(parsed.path)
                return
            if self._review_get(parsed):
                return
            if parsed.path == "/health":
                self._send_json(HTTPStatus.OK, self._health_payload())
                return
            if parsed.path == "/api/portfolio":
                query = parse_qs(parsed.query)
                as_of = _parse_iso_date(query.get("as_of", [None])[0], "as_of")
                self._send_json(
                    HTTPStatus.OK,
                    self.server.dashboard_app.portfolio_payload(as_of),
                )
                return
            if parsed.path == "/api/realtime-portfolio":
                self._send_json(
                    HTTPStatus.OK,
                    self.server.dashboard_app.realtime_portfolio_payload(),
                )
                return
            if parsed.path == "/api/kline":
                query = parse_qs(parsed.query)
                ts_code = query.get("ts_code", [""])[0].strip()
                if not ts_code:
                    raise ValueError("ts_code 不能为空")
                as_of = _parse_iso_date(query.get("as_of", [None])[0], "as_of")
                range_key = query.get("range", ["3m"])[0]
                cycle_id = query.get("cycle_id", [None])[0]
                try:
                    payload = self.server.dashboard_app.kline_payload(
                        ts_code,
                        range_key=range_key,
                        cycle_id=cycle_id,
                        as_of=as_of,
                    )
                except KlineNotFoundError as exc:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                    return
                self._send_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/intraday":
                query = parse_qs(parsed.query)
                ts_code = query.get("ts_code", [""])[0].strip()
                if not ts_code:
                    raise ValueError("ts_code 不能为空")
                try:
                    payload = self.server.dashboard_app.intraday_payload(
                        ts_code,
                        trade_date=_parse_iso_date(
                            query.get("trade_date", [None])[0], "trade_date"
                        ),
                        cycle_id=query.get("cycle_id", [None])[0],
                        as_of=_parse_iso_date(
                            query.get("as_of", [None])[0], "as_of"
                        ),
                    )
                except KlineNotFoundError as exc:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                    return
                self._send_json(HTTPStatus.OK, payload)
                return
            if parsed.path in {"/api/ledger", "/api/reconciliations"}:
                query = parse_qs(parsed.query)
                limit = int(query.get("limit", ["100"])[0])
                if limit < 1 or limit > 1000:
                    raise ValueError("limit 必须在 1 到 1000 之间")
                rows = (
                    self.server.dashboard_app.store.recent_ledger(
                        self.server.dashboard_app.account_id, limit
                    )
                    if parsed.path == "/api/ledger"
                    else self.server.dashboard_app.store.recent_reconciliations(
                        self.server.dashboard_app.account_id, limit
                    )
                )
                self._send_json(HTTPStatus.OK, {"rows": rows})
                return
            self._send_asset(parsed.path)
        except (ReviewHTTPError, InvestmentReviewServiceError) as exc:
            self._send_review_error(exc)
        except (ValueError, RuntimeError) as exc:
            if parsed.path.startswith("/api/investment-review"):
                self._send_review_error(
                    ReviewHTTPError(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        "investment_review_internal_error",
                        "本地投资复盘服务暂时不可用",
                    )
                )
                return
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception:
            if parsed.path.startswith("/api/investment-review"):
                self._send_review_error(
                    ReviewHTTPError(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        "investment_review_internal_error",
                        "本地投资复盘服务暂时不可用",
                    )
                )
                return
            raise

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        if self.server.dashboard_app.review_acceptance_read_only:
            self._send_acceptance_read_only()
            return
        try:
            if self._review_post(parsed):
                return
        except (ReviewHTTPError, InvestmentReviewServiceError) as exc:
            self._send_review_error(exc)
            return
        except Exception:
            if parsed.path.startswith("/api/investment-review"):
                self._send_review_error(
                    ReviewHTTPError(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        "investment_review_internal_error",
                        "本地投资复盘服务暂时不可用",
                    )
                )
                return
            raise
        actions = {
            "/api/refresh-prices": "refresh-prices",
            "/api/refresh-performance": "refresh-performance",
            "/api/refresh-industries": "refresh-industries",
            "/api/refresh-kline": "refresh-kline",
            "/api/refresh-intraday": "refresh-intraday",
            "/api/live-intraday": "live-intraday",
        }
        expected_action = actions.get(parsed.path)
        if expected_action is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if self.headers.get("X-Portfolio-Action") != expected_action:
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "缺少本地刷新确认头"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length > 65536:
                raise ValueError("请求体过大")
            raw = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("请求体必须是 JSON 对象")
            if parsed.path == "/api/refresh-prices":
                as_of = _parse_iso_date(payload.get("as_of"), "as_of")
                lookback_days = int(payload.get("lookback_days", 60))
                result = self.server.dashboard_app.refresh_prices(
                    as_of=as_of,
                    lookback_days=lookback_days,
                )
            elif parsed.path == "/api/refresh-performance":
                result = self.server.dashboard_app.refresh_performance_prices(
                    as_of=_parse_iso_date(payload.get("as_of"), "as_of")
                )
            elif parsed.path == "/api/refresh-industries":
                result = self.server.dashboard_app.refresh_industries()
            elif parsed.path == "/api/refresh-kline":
                ts_code = str(payload.get("ts_code", "")).strip()
                if not ts_code:
                    raise ValueError("ts_code 不能为空")
                result = self.server.dashboard_app.refresh_kline(
                    ts_code,
                    range_key=str(payload.get("range", "3m")),
                    cycle_id=(
                        str(payload["cycle_id"]) if payload.get("cycle_id") else None
                    ),
                    as_of=_parse_iso_date(payload.get("as_of"), "as_of"),
                )
            elif parsed.path == "/api/refresh-intraday":
                ts_code = str(payload.get("ts_code", "")).strip()
                if not ts_code:
                    raise ValueError("ts_code 不能为空")
                trade_date = _parse_iso_date(payload.get("trade_date"), "trade_date")
                if trade_date is None:
                    raise ValueError("trade_date 不能为空")
                result = self.server.dashboard_app.refresh_intraday(
                    ts_code,
                    trade_date=trade_date,
                    cycle_id=(
                        str(payload["cycle_id"]) if payload.get("cycle_id") else None
                    ),
                    as_of=_parse_iso_date(payload.get("as_of"), "as_of"),
                )
            else:
                ts_code = str(payload.get("ts_code", "")).strip()
                if not ts_code:
                    raise ValueError("ts_code 不能为空")
                trade_date = _parse_iso_date(payload.get("trade_date"), "trade_date")
                if trade_date is None:
                    raise ValueError("trade_date 不能为空")
                result = self.server.dashboard_app.live_intraday(
                    ts_code,
                    trade_date=trade_date,
                    cycle_id=(
                        str(payload["cycle_id"]) if payload.get("cycle_id") else None
                    ),
                    as_of=_parse_iso_date(payload.get("as_of"), "as_of"),
                )
            self._send_json(HTTPStatus.OK, result)
        except KlineNotFoundError as exc:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
        except KlineRefreshBusyError as exc:
            self._send_json(HTTPStatus.CONFLICT, {"error": str(exc)})
        except KlineFetchError as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        except IntradayFetchError as exc:
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {"error": str(exc), "provider_attempts": exc.provider_attempts},
            )
        except (
            ValueError,
            RuntimeError,
            PriceFetchError,
            IndustryFetchError,
            json.JSONDecodeError,
        ) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})


def _configured_investment_review_service(
    store: PortfolioStore,
    *,
    env_file: str | Path,
    explicit_review_db: str | Path | None = None,
    artifact_root: str | Path | None = None,
    read_only_acceptance: bool = False,
) -> tuple[InvestmentReviewWebService | None, ReviewHTTPError | None]:
    """Build the opt-in review service without creating or upgrading a sidecar."""

    try:
        if read_only_acceptance:
            if explicit_review_db is None or artifact_root is None:
                raise ValueError(
                    "acceptance mode requires explicit review DB and artifact root"
                )
            review_db = configured_review_database(
                explicit_path=explicit_review_db,
                environ={},
            )
        else:
            values = {**load_env_file(env_file), **os.environ}
            review_db = configured_review_database(
                explicit_path=explicit_review_db,
                environ=values,
            )
    except (OSError, UnicodeError, ValueError):
        return None, ReviewHTTPError(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "investment_review_configuration_invalid",
            "本地投资复盘配置无效",
        )
    if review_db is None:
        return None, None
    try:
        if not review_db.is_file():
            return None, ReviewHTTPError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "investment_review_configuration_invalid",
                "本地投资复盘配置无效",
            )
        service = InvestmentReviewWebService(
            review_db=review_db,
            portfolio_db=store.path,
            artifact_root=artifact_root,
            repo_root=repository_root(),
            read_only_acceptance=read_only_acceptance,
        )
    except Exception:  # review configuration must not prevent the portfolio page
        return None, ReviewHTTPError(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "investment_review_configuration_invalid",
            "本地投资复盘配置无效",
        )
    return service, None


def create_dashboard_server(
    store: PortfolioStore,
    *,
    account_id: str = "default",
    env_file: str | Path = ".env.local",
    host: str = "127.0.0.1",
    port: int = 8765,
    investment_review_service: InvestmentReviewWebService | None = None,
    investment_review_db: str | Path | None = None,
    investment_review_artifact_root: str | Path | None = None,
    review_acceptance_read_only: bool = False,
    expected_review_candidate_sha256: str | None = None,
) -> DashboardHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Dashboard 只允许绑定本机回环地址")
    if review_acceptance_read_only and host != "127.0.0.1":
        raise ValueError("复盘人工验收模式只允许显式绑定 127.0.0.1")
    actual_candidate_sha256: str | None = None
    if review_acceptance_read_only:
        if investment_review_db is None or investment_review_artifact_root is None:
            raise ValueError("复盘人工验收模式要求显式数据库与产物目录")
        candidate = configured_review_database(
            explicit_path=investment_review_db,
            environ={},
        )
        if candidate is None or not candidate.is_file():
            raise ValueError("复盘人工验收候选数据库不存在")
        expected = str(expected_review_candidate_sha256 or "").strip().lower()
        if len(expected) != 64 or any(
            character not in "0123456789abcdef" for character in expected
        ):
            raise ValueError("复盘人工验收模式要求精确候选 SHA-256")
        actual_candidate_sha256 = _sha256_file(candidate)
        if actual_candidate_sha256 != expected:
            raise ValueError("复盘人工验收候选数据库 SHA-256 不匹配")
    investment_review_error: ReviewHTTPError | None = None
    if investment_review_service is None:
        (
            investment_review_service,
            investment_review_error,
        ) = _configured_investment_review_service(
            store,
            env_file=env_file,
            explicit_review_db=investment_review_db,
            artifact_root=investment_review_artifact_root,
            read_only_acceptance=review_acceptance_read_only,
        )
    if review_acceptance_read_only and investment_review_service is None:
        raise ValueError("复盘人工验收服务未能建立")
    if review_acceptance_read_only and (
        getattr(investment_review_service, "read_only_acceptance", False)
        is not True
    ):
        raise ValueError("复盘人工验收服务未锁定为只读")
    app = DashboardApplication(
        store,
        account_id=account_id,
        env_file=env_file,
        investment_review_service=investment_review_service,
        investment_review_error=investment_review_error,
        review_acceptance_read_only=review_acceptance_read_only,
        review_candidate_sha256=actual_candidate_sha256,
        review_artifact_root=investment_review_artifact_root,
    )
    return DashboardHTTPServer((host, port), app)


def serve_dashboard(
    store: PortfolioStore,
    *,
    account_id: str = "default",
    env_file: str | Path = ".env.local",
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    investment_review_service: InvestmentReviewWebService | None = None,
    review_automation: bool | None = None,
    investment_review_db: str | Path | None = None,
    investment_review_artifact_root: str | Path | None = None,
    review_acceptance_read_only: bool = False,
    expected_review_candidate_sha256: str | None = None,
) -> None:
    if review_acceptance_read_only and review_automation is not False:
        raise ValueError("复盘人工验收模式必须显式关闭自动运行")
    service_was_injected = investment_review_service is not None
    server = create_dashboard_server(
        store,
        account_id=account_id,
        env_file=env_file,
        host=host,
        port=port,
        investment_review_service=investment_review_service,
        investment_review_db=investment_review_db,
        investment_review_artifact_root=investment_review_artifact_root,
        review_acceptance_read_only=review_acceptance_read_only,
        expected_review_candidate_sha256=expected_review_candidate_sha256,
    )
    automation: ReviewAutomationCoordinator | None = None
    periodic_automation: PeriodicReportAutomationCoordinator | None = None
    review_service = server.dashboard_app.investment_review_service
    configure_automation = (
        not review_acceptance_read_only
        and review_service is not None
        and (
            not service_was_injected
            or review_automation is not None
        )
    )
    if configure_automation and review_service is not None:
        try:
            values = {**load_env_file(env_file), **os.environ}
            config = review_automation_config(
                environ=values,
                enabled_override=(
                    False if review_automation is False else None
                ),
            )
            sync_service = review_service.sync_service
            automation = ReviewAutomationCoordinator(
                portfolio_db=store.path,
                review_db=review_service.store.path,
                mapping_path=(
                    sync_service.mapping_path
                    if sync_service is not None
                    else None
                ),
                artifact_root=review_service.catalog.runner.artifact_root,
                repo_root=repository_root(),
                config=config,
                sync_service=sync_service,
                store=review_service.store,
            )
            review_service.set_automation_status_provider(automation.status)
            automation.start()
        except Exception as exc:
            error_type = type(exc).__name__
            failed_at = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z")
            review_service.set_automation_status_provider(
                lambda: {
                    "enabled": review_automation is not False,
                    "state": "failed",
                    "worker_alive": False,
                    "queue_depth": 0,
                    "run_count": 0,
                    "latest": None,
                    "last_success": None,
                    "last_failure": {
                        "status": "failed",
                        "error_type": error_type,
                        "status_occurred_at": failed_at,
                    },
                }
            )
            print("复盘自动运行未启动；健康页已记录配置或启动失败。")
    periodic_status_setter = (
        getattr(review_service, "set_periodic_automation_status_provider", None)
        if review_service is not None
        else None
    )
    if configure_automation and callable(periodic_status_setter):
        try:
            values = {**load_env_file(env_file), **os.environ}
            periodic_config = periodic_automation_config(
                environ=values,
                enabled_override=(
                    False if review_automation is False else None
                ),
            )
            periodic_automation = PeriodicReportAutomationCoordinator(
                portfolio_db=store.path,
                review_db=review_service.store.path,
                repo_root=repository_root(),
                account_id=account_id,
                config=periodic_config,
            )
            periodic_status_setter(periodic_automation.status)
            periodic_automation.start()
        except Exception as exc:
            error_type = type(exc).__name__
            failed_at = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z")
            periodic_status_setter(
                lambda: {
                    "enabled": review_automation is not False,
                    "state": "failed",
                    "latest": None,
                    "last_success": None,
                    "last_failure": {
                        "status": "failed",
                        "error_type": error_type,
                        "completed_at": failed_at,
                    },
                    "os_scheduler_installed": False,
                }
            )
            print("周期报告自动运行未启动；健康页已记录配置或启动失败。")
    actual_host, actual_port = server.server_address[:2]
    url = f"http://{actual_host}:{actual_port}/"
    if review_acceptance_read_only:
        print(f"交易复盘只读验收页面: {url}")
    else:
        print(f"持仓可视化页面: {url}")
    print("按 Ctrl+C 停止本地服务。")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        if automation is not None:
            stopped = automation.stop(timeout=30.0)
            if stopped.get("worker_alive") is True:
                print(
                    "复盘自动运行仍在完成当前原子步骤；进程退出后不会安装或保留系统任务。"
                )
        if periodic_automation is not None:
            stopped = periodic_automation.stop(timeout=30.0)
            if stopped.get("worker_alive") is True:
                print(
                    "周期报告自动运行仍在完成当前幂等生成；"
                    "进程退出后不会安装或保留系统任务。"
                )
        server.server_close()
