from __future__ import annotations

import json
import threading
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from src.portfolio.importer import parse_opening_snapshot, parse_statement
from src.portfolio.intraday import IntradayFetchError
from src.portfolio.kline import KlineFetchError, KlineRefreshBusyError
from src.portfolio.models import ClosePrice, IndustryClassification
from src.portfolio.realtime import RealtimeFetchResult, RealtimeQuote
from src.portfolio.store import PortfolioStore
from src.portfolio.web import DashboardApplication, WEB_ASSET_DIR, create_dashboard_server


def _build_store(tmp_path: Path) -> PortfolioStore:
    opening_path = tmp_path / "opening.csv"
    opening_path.write_text(
        "as_of_date,ts_code,name,asset_type,quantity,total_cost,last_close,market_value,unrealized_pnl\n"
        "2026-07-10,600000.SH,浦发银行,equity,100,1000,12,1200,200\n",
        encoding="utf-8",
    )
    store = PortfolioStore(tmp_path / "portfolio.sqlite3")
    store.initialize()
    opening = parse_opening_snapshot(opening_path, account_id="default")
    store.apply_opening_snapshot(
        account_id="default",
        instruments=opening.instruments.values(),
        entries=opening.entries,
        prices=opening.prices,
        source_name=opening.source_name,
        source_sha256=opening.source_sha256,
        total_rows=opening.total_rows,
    )
    return store


def test_dashboard_payload_uses_real_store_values(tmp_path):
    store = _build_store(tmp_path)
    store.set_industries(
        [IndustryClassification("600000.SH", "银行", "tushare.stock_basic.industry")]
    )
    payload = DashboardApplication(store).portfolio_payload()

    assert payload["summary"]["market_value"] == "1200"
    assert payload["summary"]["cash_balance"] == "0"
    assert payload["summary"]["total_assets"] == "1200"
    assert payload["summary"]["unrealized_pnl"] == "200"
    assert payload["summary"]["realized_pnl"] == "0"
    assert "realized_pnl_since_baseline" not in payload["summary"]
    assert payload["summary"]["gain_count"] == 1
    assert payload["positions"][0]["weight_pct"] == "100"
    assert payload["positions"][0]["price_source"] == "opening_snapshot"
    assert payload["positions"][0]["industry_name"] == "银行"
    assert payload["industries"] == [
        {
            "industry_name": "银行",
            "position_count": 1,
            "etf_count": 0,
            "classified": True,
            "remaining_cost": "1000",
            "market_value": "1200",
            "unrealized_pnl": "200",
            "return_pct": "20",
            "weight_pct": "100",
                "members": [
                    {
                        "ts_code": "600000.SH",
                        "name": "浦发银行",
                        "asset_type": "equity",
                        "industry_source": "tushare.stock_basic.industry",
                    }
                ],
            "sources": ["tushare.stock_basic.industry"],
        }
    ]
    assert payload["industry_summary"]["top_industry"] == "银行"
    assert payload["industry_summary"]["top3_weight_pct"] == "100"
    assert payload["closed_positions"] == []
    assert payload["clearance_summary"]["cycle_count"] == 0
    assert payload["clearance_summary"]["total_realized_pnl"] == "0"
    assert payload["pnl_performance"]["periods"]["month"]["status"] == "partial_history"
    assert payload["pnl_performance"]["periods"]["month"]["pnl"] is None
    three_months = payload["pnl_performance"]["recent_ranges"][1]
    assert three_months["key"] == "3m"
    assert three_months["pnl"] == "0"
    assert three_months["status"] == "partial_history"
    assert three_months["series"][0] == {"date": "2026-07-10", "pnl": "0"}
    assert payload["metadata"]["baseline_date"] == "2026-07-10"
    assert "不构成" in payload["boundary"]


def test_dashboard_payload_includes_cash_in_total_assets_and_weights(tmp_path):
    store = _build_store(tmp_path)
    store.set_cash_balance(
        "default",
        Decimal("300"),
        date(2026, 7, 14),
        note="用户确认当前现金余额",
    )

    payload = DashboardApplication(store).portfolio_payload()

    assert payload["summary"]["market_value"] == "1200"
    assert payload["summary"]["cash_balance"] == "300"
    assert payload["summary"]["cash_as_of"] == "2026-07-14"
    assert payload["summary"]["cash_source"] == "user_provided"
    assert payload["summary"]["total_assets"] == "1500"
    assert payload["summary"]["cash_weight_pct"] == "20"
    assert payload["positions"][0]["weight_pct"] == "80"


def test_dashboard_payload_includes_month_year_and_lifetime_pnl_curves(tmp_path):
    opening_path = tmp_path / "opening.csv"
    opening_path.write_text(
        "as_of_date,ts_code,name,quantity,total_cost,last_close\n"
        "2025-12-31,600000,浦发银行,100,1000,10\n",
        encoding="utf-8",
    )
    store = PortfolioStore(tmp_path / "portfolio.sqlite3")
    store.initialize()
    opening = parse_opening_snapshot(opening_path, account_id="default")
    store.apply_opening_snapshot(
        account_id="default",
        instruments=opening.instruments.values(),
        entries=opening.entries,
        prices=opening.prices,
        source_name=opening.source_name,
        source_sha256=opening.source_sha256,
        total_rows=opening.total_rows,
    )
    store.add_close_prices(
        [
            ClosePrice("600000.SH", date(2026, 1, 2), Decimal("11"), "test"),
            ClosePrice("600000.SH", date(2026, 6, 30), Decimal("12"), "test"),
            ClosePrice("600000.SH", date(2026, 7, 1), Decimal("13"), "test"),
            ClosePrice("600000.SH", date(2026, 7, 15), Decimal("14"), "test"),
        ]
    )

    payload = DashboardApplication(store).portfolio_payload(date(2026, 7, 15))

    periods = payload["pnl_performance"]["periods"]
    assert periods["month"]["label"] == "本月盈亏"
    assert periods["month"]["pnl"] == "200"
    assert periods["month"]["series"][0] == {
        "date": "2026-06-30",
        "pnl": "0",
    }
    assert periods["year"]["label"] == "今年盈亏"
    assert periods["year"]["pnl"] == "400"
    assert periods["all"]["label"] == "投资以来盈亏"
    assert periods["all"]["pnl"] == "400"
    assert periods["all"]["series"][-1] == {
        "date": "2026-07-15",
        "pnl": "400",
    }
    recent_ranges = payload["pnl_performance"]["recent_ranges"]
    assert [period["key"] for period in recent_ranges] == [
        "1m",
        "3m",
        "6m",
        "12m",
        "24m",
    ]
    assert recent_ranges[0]["label"] == "近1个月盈亏"
    assert recent_ranges[0]["requested_start_date"] == "2026-06-15"
    assert recent_ranges[0]["pnl"] == "300"
    assert recent_ranges[1]["requested_start_date"] == "2026-04-15"
    assert recent_ranges[1]["pnl"] == "300"
    assert recent_ranges[3]["start_date"] == "2025-12-31"
    assert recent_ranges[3]["pnl"] == "400"
    assert recent_ranges[3]["status"] == "partial_history"
    assert "账户基准日" in recent_ranges[3]["coverage_note"]
    assert recent_ranges[4]["label"] == "近24个月盈亏"
    assert recent_ranges[4]["requested_start_date"] == "2024-07-15"


def test_performance_price_refresh_is_incremental_and_rebuilds_curves(
    tmp_path, monkeypatch
):
    store = _build_store(tmp_path)
    calls = []
    rows = [
        {
            "ts_code": "600000.SH",
            "trade_date": trade_date,
            "close": close,
            "pre_close": pre_close,
            "pct_chg": pct_chg,
        }
        for trade_date, close, pre_close, pct_chg in [
            ("20260710", 12, 11.5, 4.35),
            ("20260711", 12.5, 12, 4.17),
            ("20260714", 13, 12.5, 4),
            ("20260715", 14, 13, 7.69),
        ]
    ]

    class HistoryPro:
        def daily(self, **kwargs):
            calls.append((kwargs["start_date"], kwargs["end_date"]))
            return [
                row
                for row in rows
                if kwargs["start_date"] <= row["trade_date"] <= kwargs["end_date"]
            ]

    monkeypatch.setattr("src.portfolio.web.get_tushare_pro", lambda _: HistoryPro())
    application = DashboardApplication(store)

    # 先建立缓存，再验证历史行情写入后会自动失效并重算。
    application.portfolio_payload(date(2026, 7, 14))
    first = application.refresh_performance_prices(as_of=date(2026, 7, 14))
    assert calls == [("20260710", "20260714")]
    assert first["new_observations"] == 3
    assert first["errors"] == []

    second = application.refresh_performance_prices(as_of=date(2026, 7, 15))
    assert calls[-1] == ("20260715", "20260715")
    assert second["requested_range_count"] == 1
    assert second["new_observations"] == 1

    third = application.refresh_performance_prices(as_of=date(2026, 7, 15))
    assert third["requested_range_count"] == 0
    assert third["already_covered_count"] == 1
    assert len(calls) == 2
    assert store.performance_price_coverage("default", "600000.SH") == {
        "start_date": date(2026, 7, 10),
        "end_date": date(2026, 7, 15),
        "updated_at": store.performance_price_coverage(
            "default", "600000.SH"
        )["updated_at"],
    }

    payload = application.portfolio_payload(date(2026, 7, 15))
    assert payload["pnl_performance"]["periods"]["all"]["pnl"] == "400"
    assert payload["pnl_performance"]["periods"]["all"]["series"][-1] == {
        "date": "2026-07-15",
        "pnl": "400",
    }


def test_dashboard_payload_can_overlay_intraday_quotes_without_persisting(tmp_path):
    store = _build_store(tmp_path)
    quote = RealtimeQuote(
        ts_code="600000.SH",
        name="浦发银行",
        price=Decimal("13.5"),
        pre_close=Decimal("12"),
        pct_chg=Decimal("12.5"),
        quote_time="2026-07-13T14:10:00+08:00",
        source="tencent.quote",
    )
    payload = DashboardApplication(store).portfolio_payload(
        quote_overrides={"600000.SH": quote},
        market_data={
            "mode": "intraday",
            "providers": ["tencent.quote"],
            "live_quote_count": 1,
            "requested_count": 1,
            "missing": [],
            "errors": [],
            "quote_time": quote.quote_time,
            "fetched_at": quote.quote_time,
            "refresh_interval_seconds": 60,
        },
    )

    position = payload["positions"][0]
    assert position["close"] == "13.5"
    assert position["market_value"] == "1350"
    assert position["unrealized_pnl"] == "350"
    assert position["price_source"] == "tencent.quote"
    assert position["is_live"] is True
    assert payload["summary"]["market_value"] == "1350"
    assert payload["metadata"]["market_data"]["refresh_interval_seconds"] == 60

    closing_payload = DashboardApplication(store).portfolio_payload()
    assert closing_payload["positions"][0]["close"] == "12"
    assert closing_payload["positions"][0]["price_source"] == "opening_snapshot"


def test_realtime_dashboard_falls_back_to_closing_prices_when_sources_fail(tmp_path):
    store = _build_store(tmp_path)

    class EmptyProvider:
        def fetch_many(self, instruments):
            return RealtimeFetchResult(
                quotes={},
                missing=[item.ts_code for item in instruments],
                errors=["tencent.quote unavailable", "sina.quote unavailable"],
                providers=[],
                fetched_at="2026-07-13T06:10:00+00:00",
            )

    payload = DashboardApplication(
        store,
        realtime_provider=EmptyProvider(),
        realtime_cache_seconds=0,
    ).realtime_portfolio_payload()

    assert payload["metadata"]["market_data"]["mode"] == "closing_fallback"
    assert payload["metadata"]["market_data"]["missing"] == ["600000.SH"]
    assert payload["positions"][0]["close"] == "12"
    assert payload["positions"][0]["is_live"] is False


def test_dashboard_payload_includes_closed_position_cycles(tmp_path):
    store = _build_store(tmp_path)
    statement_path = tmp_path / "sell_out.csv"
    statement_path.write_text(
        "成交日期,成交时间,证券代码,证券名称,买卖标志,成交价格,成交数量,成交金额,手续费\n"
        "2026-07-11,10:01:03,600000,浦发银行,卖出,13,100,1300,2\n",
        encoding="utf-8",
    )
    statement = parse_statement(statement_path, account_id="default", broker="test")
    store.apply_statement(
        account_id="default",
        instruments=statement.instruments.values(),
        entries=statement.entries,
        broker="test",
        source_name=statement.source_name,
        source_sha256=statement.source_sha256,
        total_rows=statement.total_rows,
        skipped_rows=statement.skipped_rows,
    )

    payload = DashboardApplication(store).portfolio_payload()
    assert payload["positions"] == []
    assert payload["closed_positions"] == [
        {
            "cycle_id": "600000.SH:1",
            "ts_code": "600000.SH",
            "name": "浦发银行",
            "asset_type": "equity",
            "industry_name": "未分类",
            "industry_source": "",
            "cycle_number": 1,
            "opened_on": "2026-07-10",
            "closed_on": "2026-07-11",
            "opening_event_type": "OPENING",
            "holding_days": 1,
            "acquired_quantity": "100",
            "sold_quantity": "100",
            "cost_basis": "1000",
            "net_sale_proceeds": "1298",
            "trading_pnl": "298",
            "cash_income": "0",
            "cash_fees": "0",
            "realized_pnl": "298",
            "return_pct": "29.8",
            "close_price": "13",
            "buy_count": 0,
            "sell_count": 1,
            "calculation_source": "ledger_entries.end_of_day_diluted_cost",
        }
    ]
    assert payload["clearance_summary"]["total_realized_pnl"] == "298"
    assert payload["clearance_summary"]["return_pct"] == "29.8"
    assert payload["clearance_summary"]["win_rate_pct"] == "100"
    assert payload["clearance_summary"]["latest_close_date"] == "2026-07-11"


def test_dashboard_groups_repeated_clearances_by_security(tmp_path):
    store = _build_store(tmp_path)
    statement_path = tmp_path / "two_cycles.csv"
    statement_path.write_text(
        "成交日期,成交时间,证券代码,证券名称,买卖标志,成交价格,成交数量,成交金额,手续费\n"
        "2026-07-11,10:01:03,600000,浦发银行,卖出,13,100,1300,2\n"
        "2026-07-12,10:01:03,600000,浦发银行,买入,10,50,500,1\n"
        "2026-07-13,10:01:03,600000,浦发银行,卖出,12,50,600,1\n",
        encoding="utf-8",
    )
    statement = parse_statement(statement_path, account_id="default", broker="test")
    store.apply_statement(
        account_id="default",
        instruments=statement.instruments.values(),
        entries=statement.entries,
        broker="test",
        source_name=statement.source_name,
        source_sha256=statement.source_sha256,
        total_rows=statement.total_rows,
        skipped_rows=statement.skipped_rows,
    )

    payload = DashboardApplication(store).portfolio_payload()

    assert len(payload["closed_position_groups"]) == 1
    group = payload["closed_position_groups"][0]
    assert group["ts_code"] == "600000.SH"
    assert group["cycle_count"] == 2
    assert group["sold_quantity"] == "150"
    assert group["cost_basis"] == "1501"
    assert group["net_sale_proceeds"] == "1897"
    assert group["realized_pnl"] == "396"
    assert [item["cycle_number"] for item in group["cycles"]] == [2, 1]


def test_dashboard_http_endpoints_and_local_action_guard(tmp_path):
    store = _build_store(tmp_path)
    server = create_dashboard_server(store, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    base = f"http://{host}:{port}"
    try:
        with urlopen(f"{base}/health", timeout=5) as response:
            assert json.load(response) == {
                "status": "ok",
                "api_version": 2,
                "capabilities": [
                    "daily-kline",
                    "refresh-intraday",
                    "auto-performance-history",
                ],
            }

        with urlopen(f"{base}/", timeout=5) as response:
            html = response.read().decode("utf-8")
            assert "持仓账本" in html
            assert response.headers["X-Frame-Options"] == "DENY"
            assert response.headers["Content-Security-Policy"] == (
                "default-src 'self'; style-src 'self'; script-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
                "form-action 'none'"
            )

        with urlopen(f"{base}/api/portfolio", timeout=5) as response:
            payload = json.load(response)
            assert payload["positions"][0]["name"] == "浦发银行"

        with urlopen(
            f"{base}/api/kline?ts_code=600000.SH&range=3m&as_of=2026-07-10",
            timeout=5,
        ) as response:
            payload = json.load(response)
            assert payload["status"] == "missing"
            assert payload["cycle"]["cycle_id"] == "600000.SH:1"
            assert payload["operation_groups"][0]["event_type"] == "OPENING"
            assert payload["technical_indicators"]["default_selected"] == ["VOL"]
            assert payload["technical_indicators"]["calculation"]["mode"] == "client_side"

        with urlopen(
            f"{base}/api/intraday?ts_code=600000.SH&trade_date=2026-07-10&as_of=2026-07-10",
            timeout=5,
        ) as response:
            payload = json.load(response)
            assert payload["view"] == "intraday"
            assert payload["status"] == "missing"
            assert payload["bars"] == []
            assert payload["operation_mapping"] == {
                "status": "none",
                "mapped_count": 0,
                "unlocated_count": 0,
            }

        with urlopen(
            f"{base}/api/intraday?ts_code=600000.SH&trade_date=2026-05-29&as_of=2026-07-10",
            timeout=5,
        ) as response:
            payload = json.load(response)
            assert payload["trade_date"] == "2026-05-29"
            assert payload["date_scope"] == "pre_open_context"
            assert payload["operation_groups"] == []

        with pytest.raises(HTTPError) as missing_cycle:
            urlopen(
                f"{base}/api/kline?ts_code=600000.SH&range=3m&cycle_id=600000.SH%3A99",
                timeout=5,
            )
        assert missing_cycle.value.code == 404

        server.dashboard_app.realtime_portfolio_payload = lambda: {
            "metadata": {"market_data": {"mode": "intraday"}}
        }
        with urlopen(f"{base}/api/realtime-portfolio", timeout=5) as response:
            payload = json.load(response)
            assert payload["metadata"]["market_data"]["mode"] == "intraday"

        with pytest.raises(HTTPError) as exc_info:
            urlopen(
                Request(
                    f"{base}/api/refresh-prices",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                ),
                timeout=5,
            )
        assert exc_info.value.code == 403

        with pytest.raises(HTTPError) as industry_exc:
            urlopen(
                Request(
                    f"{base}/api/refresh-industries",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                ),
                timeout=5,
            )
        assert industry_exc.value.code == 403

        with pytest.raises(HTTPError) as kline_exc:
            urlopen(
                Request(
                    f"{base}/api/refresh-kline",
                    data=json.dumps({"ts_code": "600000.SH"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                ),
                timeout=5,
            )
        assert kline_exc.value.code == 403

        with pytest.raises(HTTPError) as intraday_exc:
            urlopen(
                Request(
                    f"{base}/api/refresh-intraday",
                    data=json.dumps(
                        {"ts_code": "600000.SH", "trade_date": "2026-07-10"}
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                ),
                timeout=5,
            )
        assert intraday_exc.value.code == 403

        server.dashboard_app.refresh_prices = lambda **_: {
            "fetched": 1,
            "new_observations": 0,
            "latest_trade_date": "2026-07-10",
        }
        with urlopen(
            Request(
                f"{base}/api/refresh-prices",
                data=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "X-Portfolio-Action": "refresh-prices",
                },
                method="POST",
            ),
            timeout=5,
        ) as response:
            payload = json.load(response)
            assert payload["fetched"] == 1

        server.dashboard_app.refresh_performance_prices = lambda **_: {
            "requested_range_count": 1,
            "new_observations": 4,
            "errors": [],
        }
        with urlopen(
            Request(
                f"{base}/api/refresh-performance",
                data=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "X-Portfolio-Action": "refresh-performance",
                },
                method="POST",
            ),
            timeout=5,
        ) as response:
            payload = json.load(response)
            assert payload["new_observations"] == 4

        server.dashboard_app.refresh_industries = lambda: {
            "fetched": 1,
            "updated": 1,
            "missing": [],
        }
        with urlopen(
            Request(
                f"{base}/api/refresh-industries",
                data=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "X-Portfolio-Action": "refresh-industries",
                },
                method="POST",
            ),
            timeout=5,
        ) as response:
            payload = json.load(response)
            assert payload["updated"] == 1

        server.dashboard_app.refresh_kline = lambda *_args, **_kwargs: {
            "status": "ready",
            "refresh": {"fetched_bars": 10},
        }
        with urlopen(
            Request(
                f"{base}/api/refresh-kline",
                data=json.dumps(
                    {"ts_code": "600000.SH", "range": "3m", "as_of": "2026-07-10"}
                ).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-Portfolio-Action": "refresh-kline",
                },
                method="POST",
            ),
            timeout=5,
        ) as response:
            payload = json.load(response)
            assert payload["refresh"]["fetched_bars"] == 10

        server.dashboard_app.refresh_intraday = lambda *_args, **_kwargs: {
            "status": "ready",
            "period": {"span": 5},
            "refresh": {"fetched_bars": 48},
        }
        with urlopen(
            Request(
                f"{base}/api/refresh-intraday",
                data=json.dumps(
                    {
                        "ts_code": "600000.SH",
                        "trade_date": "2026-07-10",
                        "as_of": "2026-07-10",
                    }
                ).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-Portfolio-Action": "refresh-intraday",
                },
                method="POST",
            ),
            timeout=5,
        ) as response:
            payload = json.load(response)
            assert payload["period"]["span"] == 5
            assert payload["refresh"]["fetched_bars"] == 48

        server.dashboard_app.refresh_intraday = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            IntradayFetchError(
                "分钟行情源均不可用",
                [
                    {
                        "provider": "tushare.1m",
                        "status": "failed",
                        "reason": "permission_denied",
                    }
                ],
            )
        )
        with pytest.raises(HTTPError) as intraday_provider_failure:
            urlopen(
                Request(
                    f"{base}/api/refresh-intraday",
                    data=json.dumps(
                        {"ts_code": "600000.SH", "trade_date": "2026-07-10"}
                    ).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "X-Portfolio-Action": "refresh-intraday",
                    },
                    method="POST",
                ),
                timeout=5,
            )
        assert intraday_provider_failure.value.code == 502
        error_payload = json.loads(intraday_provider_failure.value.read().decode("utf-8"))
        assert error_payload["provider_attempts"][0]["reason"] == "permission_denied"

        def fail_kline(*_args, **_kwargs):
            raise KlineFetchError("provider unavailable")

        server.dashboard_app.refresh_kline = fail_kline
        with pytest.raises(HTTPError) as provider_failure:
            urlopen(
                Request(
                    f"{base}/api/refresh-kline",
                    data=json.dumps({"ts_code": "600000.SH"}).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "X-Portfolio-Action": "refresh-kline",
                    },
                    method="POST",
                ),
                timeout=5,
            )
        assert provider_failure.value.code == 502

        def busy_kline(*_args, **_kwargs):
            raise KlineRefreshBusyError("refresh busy")

        server.dashboard_app.refresh_kline = busy_kline
        with pytest.raises(HTTPError) as refresh_conflict:
            urlopen(
                Request(
                    f"{base}/api/refresh-kline",
                    data=json.dumps({"ts_code": "600000.SH"}).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "X-Portfolio-Action": "refresh-kline",
                    },
                    method="POST",
                ),
                timeout=5,
            )
        assert refresh_conflict.value.code == 409
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_dashboard_assets_are_self_contained_and_have_required_controls():
    html = (WEB_ASSET_DIR / "index.html").read_text(encoding="utf-8")
    css = (WEB_ASSET_DIR / "app.css").read_text(encoding="utf-8")
    javascript = (WEB_ASSET_DIR / "app.js").read_text(encoding="utf-8")
    launcher = (WEB_ASSET_DIR.parents[2] / "scripts" / "start_portfolio_dashboard.ps1").read_text(
        encoding="utf-8"
    )

    assert "https://" not in html
    assert 'id="refreshButton"' in html
    assert 'id="privacyButton"' in html
    assert 'id="holdingsBody"' in html
    assert 'id="holdingsStickyHeader"' in html
    assert 'id="clearanceStickyHeader"' in html
    assert 'id="industryList"' in html
    assert 'id="industryRefreshButton"' in html
    assert 'id="industryPie"' in html
    assert 'id="industryPieSegments"' in html
    assert 'id="industryPieLegend"' in html
    assert 'id="clearancePnl"' in html
    assert 'id="clearanceBody"' in html
    assert 'data-clearance-sort="realized_pnl"' in html
    assert 'id="performanceChart"' in html
    assert 'data-performance-range="month"' in html
    assert 'data-performance-range="year"' in html
    assert 'data-performance-range="all"' in html
    assert 'data-performance-range="lookback"' in html
    assert 'id="performanceLookbackSelect"' in html
    assert '<option value="3" selected>近 3 个月</option>' in html
    assert '<option value="24">近 2 年</option>' in html
    assert 'id="clearanceEmpty"' in html
    assert 'id="cashBalance"' in html
    assert html.count("data-collapsible=") == 6
    assert 'aria-controls="industryContent"' in html
    assert 'aria-controls="holdingsContent"' in html
    assert "@media (max-width: 840px)" in css
    assert 'api("/api/refresh-prices"' in javascript
    assert 'api("/api/refresh-industries"' in javascript
    assert 'api("/api/realtime-portfolio"' in javascript
    assert 'api("/api/refresh-performance"' in javascript
    assert '"X-Portfolio-Action": "refresh-performance"' in javascript
    assert 'state.payload = await api("/api/portfolio")' in javascript
    assert "正在抓取历史收盘价并重算曲线" in javascript
    assert "window.setInterval(refreshRealtime, 6e4)" in javascript
    assert "最新价" in html
    assert "renderAllocation" in javascript
    assert "renderIndustries" in javascript
    assert "renderIndustryPie" in javascript
    assert "pieSlicePath" in javascript
    assert "renderClearance" in javascript
    assert "renderPerformance" in javascript
    assert "performance.recent_ranges" in javascript
    assert "portfolioPerformanceLookbackMonths" in javascript
    assert "closed_position_groups" in javascript
    assert "expandedClearanceGroups" in javascript
    assert "summary.total_assets" in javascript
    assert 'name: "现金"' in javascript
    assert "industry.members || []" in javascript
    assert "industry-position-row" in javascript
    assert "portfolioCollapsedModules" in javascript
    assert "initializeCollapsibleModules" in javascript
    assert "/api/kline?" in javascript
    assert 'api("/api/refresh-kline"' in javascript
    assert "/api/intraday?" in javascript
    assert 'api("/api/refresh-intraday"' in javascript
    assert 'name: "portfolioOperation"' in javascript
    assert "chart.setDataLoader" in javascript
    assert 'chart.subscribeAction("onCandleBarClick"' in javascript
    assert "openIntradayForTradeDate" in javascript
    assert "openIntradayForLatestTradeDate" in javascript
    assert "autoRefreshTradeDate" in javascript
    assert "automatic: true" in javascript
    assert "intradayBarSpaceLimit" in javascript
    assert "intradayFitBarSpace" in javascript
    assert "适应全日" in javascript
    assert "chart.createOverlay" in javascript
    assert "chart.createIndicator" in javascript
    assert "portfolioKlineIndicators" in javascript
    assert "portfolioIntradayIndicators" in javascript
    assert "INTRADAY_AVG" in javascript
    assert "隐藏全部" in javascript
    assert "technical_indicator_" in javascript
    assert "width: min(1040px, 96vw)" in css
    assert ".kline-chart" in css
    assert ".kline-indicator-picker" in css
    assert ".operation-group" in css
    assert ".collapsible-content[hidden]" in css
    assert ".industry-position-list" in css
    assert ".industry-pie-segment" in css
    assert ".industry-pie-legend" in css
    assert ".sticky-table-header.is-visible" in css
    assert ".performance-chart-plot" in css
    assert ".performance-lookback-picker" in css
    assert ".clearance-cycle-row" in css
    assert "initializeStickyTableHeaders" in javascript
    assert "--muted: oklch(0.84 0.012 245)" in css
    assert "--dim: oklch(0.74 0.01 245)" in css
    assert 'content: "••••••"' in css
    assert 'content: "金额已隐藏"' in css
    assert "-webkit-text-fill-color: transparent !important" in css
    assert "text-shadow: none !important" in css
    assert "text-shadow: 0 0 11px" not in css
    assert "git-common-dir" in launcher
    assert 'Join-Path $projectRoot ".git"' in launcher
    assert "Get-Content -LiteralPath $gitPointerPath" in launcher
    assert '"--db"' in launcher
    assert '"--env-file"' in launcher
    assert '"--app=$Url"' in launcher
    assert '"explorer.exe"' in launcher
    assert "无法打开页面" in launcher
    assert '$requiredApiVersion = 2' in launcher
    assert '$requiredCapability = "refresh-intraday"' in launcher
    assert "Stop-IncompatiblePortfolioDashboard" in launcher
