from __future__ import annotations

import json
import threading
import time
import webbrowser
from datetime import date, datetime, timezone
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.utils.tushare_client import get_tushare_pro

from .industries import IndustryFetchError, TushareIndustryProvider
from .intraday import IntradayFetchError, IntradayService, build_intraday_provider
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
from .store import PortfolioStore


WEB_ASSET_DIR = Path(__file__).with_name("web_assets")
DASHBOARD_API_VERSION = 2
DASHBOARD_CAPABILITIES = ("daily-kline", "refresh-intraday")
STATIC_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


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


def _parse_iso_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field}必须是 YYYY-MM-DD: {value!r}") from exc


class DashboardApplication:
    def __init__(
        self,
        store: PortfolioStore,
        *,
        account_id: str = "default",
        env_file: str | Path = ".env.local",
        realtime_provider: FallbackRealtimeProvider | None = None,
        realtime_cache_seconds: int = 55,
    ) -> None:
        self.store = store
        self.account_id = account_id
        self.env_file = str(env_file)
        self.refresh_lock = threading.Lock()
        self.realtime_lock = threading.Lock()
        self.realtime_provider = realtime_provider or FallbackRealtimeProvider()
        self.realtime_cache_seconds = realtime_cache_seconds
        self._realtime_cache: tuple[float, dict[str, Any]] | None = None

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
        realized_pnl = summary["realized_pnl_since_baseline"]
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
            "total_pnl_since_baseline": (
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
                "clearance_summary": clearance_summary,
                "metadata": metadata,
                "boundary": "记录与核算工具，不构成买入、卖出、持有或仓位建议。",
            }
        )

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
                "股票按可合并一级行业归一；ETF 按交易所篮子、结构化成分行业与同日价格分类，"
                "跨市场接口和季报持仓仅作可追溯回退；覆盖不足时明确保留未分类。"
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
                            "classified_weight_coverage": item.classified_weight_coverage,
                            "constituent_count_coverage": item.constituent_count_coverage,
                            "top_industry_weight": item.top_industry_weight,
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

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/health":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "status": "ok",
                        "api_version": DASHBOARD_API_VERSION,
                        "capabilities": list(DASHBOARD_CAPABILITIES),
                    },
                )
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
        except (ValueError, RuntimeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        actions = {
            "/api/refresh-prices": "refresh-prices",
            "/api/refresh-industries": "refresh-industries",
            "/api/refresh-kline": "refresh-kline",
            "/api/refresh-intraday": "refresh-intraday",
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
            else:
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


def create_dashboard_server(
    store: PortfolioStore,
    *,
    account_id: str = "default",
    env_file: str | Path = ".env.local",
    host: str = "127.0.0.1",
    port: int = 8765,
) -> DashboardHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Dashboard 只允许绑定本机回环地址")
    app = DashboardApplication(store, account_id=account_id, env_file=env_file)
    return DashboardHTTPServer((host, port), app)


def serve_dashboard(
    store: PortfolioStore,
    *,
    account_id: str = "default",
    env_file: str | Path = ".env.local",
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    server = create_dashboard_server(
        store,
        account_id=account_id,
        env_file=env_file,
        host=host,
        port=port,
    )
    actual_host, actual_port = server.server_address[:2]
    url = f"http://{actual_host}:{actual_port}/"
    print(f"持仓可视化页面: {url}")
    print("按 Ctrl+C 停止本地服务。")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
