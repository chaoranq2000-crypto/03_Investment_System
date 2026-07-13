from __future__ import annotations

import json
import threading
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from src.portfolio.importer import parse_opening_snapshot, parse_statement
from src.portfolio.models import IndustryClassification
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
    assert payload["summary"]["unrealized_pnl"] == "200"
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
                {"ts_code": "600000.SH", "name": "浦发银行", "asset_type": "equity"}
            ],
            "sources": ["tushare.stock_basic.industry"],
        }
    ]
    assert payload["industry_summary"]["top_industry"] == "银行"
    assert payload["industry_summary"]["top3_weight_pct"] == "100"
    assert payload["closed_positions"] == []
    assert payload["clearance_summary"]["cycle_count"] == 0
    assert payload["clearance_summary"]["total_realized_pnl"] == "0"
    assert payload["metadata"]["baseline_date"] == "2026-07-10"
    assert "不构成" in payload["boundary"]


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
            "calculation_source": "ledger_entries.moving_average_cost",
        }
    ]
    assert payload["clearance_summary"]["total_realized_pnl"] == "298"
    assert payload["clearance_summary"]["return_pct"] == "29.8"
    assert payload["clearance_summary"]["win_rate_pct"] == "100"
    assert payload["clearance_summary"]["latest_close_date"] == "2026-07-11"


def test_dashboard_http_endpoints_and_local_action_guard(tmp_path):
    store = _build_store(tmp_path)
    server = create_dashboard_server(store, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    base = f"http://{host}:{port}"
    try:
        with urlopen(f"{base}/health", timeout=5) as response:
            assert json.load(response) == {"status": "ok"}

        with urlopen(f"{base}/", timeout=5) as response:
            html = response.read().decode("utf-8")
            assert "持仓账本" in html
            assert response.headers["X-Frame-Options"] == "DENY"

        with urlopen(f"{base}/api/portfolio", timeout=5) as response:
            payload = json.load(response)
            assert payload["positions"][0]["name"] == "浦发银行"

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
    assert 'id="industryList"' in html
    assert 'id="industryRefreshButton"' in html
    assert 'id="clearancePnl"' in html
    assert 'id="clearanceBody"' in html
    assert 'id="clearanceEmpty"' in html
    assert "@media (max-width: 840px)" in css
    assert 'api("/api/refresh-prices"' in javascript
    assert 'api("/api/refresh-industries"' in javascript
    assert 'api("/api/realtime-portfolio"' in javascript
    assert "60_000" in javascript
    assert "最新价" in html
    assert "renderAllocation" in javascript
    assert "renderIndustries" in javascript
    assert "renderClearance" in javascript
    assert 'content: "••••••"' in css
    assert 'content: "金额已隐藏"' in css
    assert "-webkit-text-fill-color: transparent !important" in css
    assert "text-shadow: none !important" in css
    assert "text-shadow: 0 0 11px" not in css
    assert "git-common-dir" in launcher
    assert '"--db"' in launcher
    assert '"--env-file"' in launcher
