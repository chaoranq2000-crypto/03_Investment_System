from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
import sqlite3

import pytest

from src.portfolio.accounting import (
    AccountingError,
    build_closed_position_cycles,
    build_position_states,
)
from src.portfolio.importer import parse_opening_snapshot, parse_statement
from src.portfolio.industries import TushareIndustryProvider
from src.portfolio.models import IndustryClassification, Instrument
from src.portfolio.prices import TushareCloseProvider
from src.portfolio.realtime import (
    FallbackRealtimeProvider,
    RealtimeFetchError,
    RealtimeQuote,
    parse_sina_response,
    parse_tencent_response,
)
from src.portfolio.store import PortfolioStore


def _row(
    event_type: str,
    *,
    event_date: str = "2026-07-11",
    quantity: str = "0",
    price: str = "0",
    gross: str = "0",
    fees: str = "0",
    total_cost: str = "0",
    cash: str = "0",
) -> dict[str, str]:
    return {
        "event_date": event_date,
        "event_type": event_type,
        "ts_code": "600000.SH",
        "quantity": quantity,
        "price": price,
        "gross_amount": gross,
        "fees": fees,
        "total_cost": total_cost,
        "cash_amount": cash,
    }


def test_realtime_quote_parsers_cover_tencent_and_sina():
    instrument = Instrument("002558.SZ", "巨人网络", "equity")
    symbol_map = {"sz002558": instrument}

    tencent_values = [""] * 53
    tencent_values[1] = "巨人网络"
    tencent_values[3] = "28.45"
    tencent_values[4] = "29.56"
    tencent_values[30] = "20260713140257"
    tencent_values[32] = "-3.76"
    tencent_payload = "~".join(tencent_values)
    tencent = parse_tencent_response(
        f'v_sz002558="{tencent_payload}";', symbol_map
    )["002558.SZ"]
    assert tencent.price == Decimal("28.45")
    assert tencent.pct_chg == Decimal("-3.76")
    assert tencent.quote_time == "2026-07-13T14:02:57+08:00"
    assert tencent.source == "tencent.quote"

    sina_values = [""] * 33
    sina_values[0] = "巨人网络"
    sina_values[2] = "29.56"
    sina_values[3] = "28.34"
    sina_values[30] = "2026-07-13"
    sina_values[31] = "14:04:45"
    sina_payload = ",".join(sina_values)
    sina = parse_sina_response(
        f'var hq_str_sz002558="{sina_payload}";', symbol_map
    )["002558.SZ"]
    assert sina.price == Decimal("28.34")
    assert sina.pct_chg.quantize(Decimal("0.01")) == Decimal("-4.13")
    assert sina.quote_time == "2026-07-13T14:04:45+08:00"
    assert sina.source == "sina.quote"


def test_realtime_provider_falls_back_after_primary_error():
    instrument = Instrument("002558.SZ", "巨人网络", "equity")

    class BrokenProvider:
        name = "broken"

        def fetch_many(self, instruments):
            raise RealtimeFetchError("unavailable")

    class BackupProvider:
        name = "backup"

        def fetch_many(self, instruments):
            return {
                "002558.SZ": RealtimeQuote(
                    ts_code="002558.SZ",
                    name="巨人网络",
                    price=Decimal("28.45"),
                    pre_close=Decimal("29.56"),
                    pct_chg=Decimal("-3.76"),
                    quote_time="2026-07-13T14:02:57+08:00",
                    source="backup",
                )
            }

    result = FallbackRealtimeProvider([BrokenProvider(), BackupProvider()]).fetch_many(
        [instrument]
    )
    assert result.missing == []
    assert result.providers == ["backup"]
    assert result.quotes["002558.SZ"].price == Decimal("28.45")
    assert result.errors and result.errors[0].startswith("broken:")


def test_moving_average_cost_realized_pnl_and_cash_items():
    states = build_position_states(
        [
            _row("OPENING", quantity="100", total_cost="1000"),
            _row("BUY", quantity="100", gross="1200", fees="5"),
            _row("SELL", quantity="50", gross="650", fees="2"),
            _row("DIVIDEND", cash="10"),
            _row("CASH_FEE", cash="2"),
        ]
    )

    state = states["600000.SH"]
    assert state.quantity == Decimal("150")
    assert state.remaining_cost == Decimal("1653.75")
    assert state.average_cost == Decimal("11.025")
    assert state.realized_trading_pnl == Decimal("96.75")
    assert state.realized_pnl == Decimal("104.75")


def test_accounting_rejects_oversell():
    with pytest.raises(AccountingError, match="超过当时持仓"):
        build_position_states(
            [
                _row("OPENING", quantity="100", total_cost="1000"),
                _row("SELL", quantity="101", gross="1200"),
            ]
        )


def test_closed_position_cycles_require_full_clearance_and_support_reopening():
    cycles = build_closed_position_cycles(
        [
            _row("OPENING", event_date="2026-07-10", quantity="100", total_cost="1000"),
            _row(
                "SELL",
                event_date="2026-07-11",
                quantity="40",
                price="12",
                gross="480",
                fees="2",
            ),
            _row("DIVIDEND", event_date="2026-07-12", cash="10"),
            _row(
                "SELL",
                event_date="2026-07-13",
                quantity="60",
                price="11",
                gross="660",
                fees="3",
            ),
            _row(
                "BUY",
                event_date="2026-07-14",
                quantity="50",
                price="8",
                gross="400",
                fees="1",
            ),
            _row(
                "SELL",
                event_date="2026-07-15",
                quantity="50",
                price="9",
                gross="450",
                fees="1",
            ),
        ]
    )

    assert [cycle.cycle_number for cycle in cycles] == [2, 1]
    newest, first = cycles
    assert newest.cost_basis == Decimal("401")
    assert newest.net_sale_proceeds == Decimal("449")
    assert newest.realized_pnl == Decimal("48")
    assert newest.return_pct == Decimal("4800") / Decimal("401")
    assert first.opened_on == date(2026, 7, 10)
    assert first.closed_on == date(2026, 7, 13)
    assert first.sold_quantity == Decimal("100")
    assert first.cost_basis == Decimal("1000")
    assert first.net_sale_proceeds == Decimal("1135")
    assert first.trading_pnl == Decimal("135")
    assert first.cash_income == Decimal("10")
    assert first.realized_pnl == Decimal("145")
    assert first.return_pct == Decimal("14.5")
    assert first.sell_count == 2


def test_partial_sale_is_not_reported_as_closed_cycle():
    cycles = build_closed_position_cycles(
        [
            _row("OPENING", quantity="100", total_cost="1000"),
            _row("SELL", quantity="40", price="12", gross="480", fees="2"),
        ]
    )
    assert cycles == []


def test_opening_snapshot_and_statement_are_idempotent(tmp_path):
    opening_path = tmp_path / "opening.csv"
    opening_path.write_text(
        "as_of_date,ts_code,name,asset_type,quantity,total_cost,last_close,market_value,unrealized_pnl\n"
        "2026-07-10,600000.SH,浦发银行,equity,100,1000,12,1200,200\n",
        encoding="utf-8",
    )
    statement_path = tmp_path / "statement.csv"
    statement_path.write_text(
        "券商导出文件\n"
        "成交日期,成交时间,证券代码,证券名称,买卖标志,成交价格,成交数量,成交金额,手续费,发生金额\n"
        "2026-07-11,09:31:02,600000,浦发银行,买入,13,100,1300,5,-1305\n"
        "2026-07-12,10:01:03,600000,浦发银行,卖出,14,50,700,2,698\n",
        encoding="utf-8",
    )

    store = PortfolioStore(tmp_path / "portfolio.sqlite3")
    store.initialize()
    opening = parse_opening_snapshot(opening_path, account_id="default")
    assert not opening.errors
    store.apply_opening_snapshot(
        account_id="default",
        instruments=opening.instruments.values(),
        entries=opening.entries,
        prices=opening.prices,
        source_name=opening.source_name,
        source_sha256=opening.source_sha256,
        total_rows=opening.total_rows,
    )

    statement = parse_statement(statement_path, account_id="default", broker="test")
    assert not statement.errors
    assert [entry.fees for entry in statement.entries] == [Decimal("5"), Decimal("2")]
    preview = store.preview_statement("default", statement.entries)
    assert preview == {"accepted_entries": 2, "duplicate_entries": 0}
    outcome = store.apply_statement(
        account_id="default",
        instruments=statement.instruments.values(),
        entries=statement.entries,
        broker="test",
        source_name=statement.source_name,
        source_sha256=statement.source_sha256,
        total_rows=statement.total_rows,
        skipped_rows=statement.skipped_rows,
    )
    assert outcome["inserted_entries"] == 2

    second_preview = store.preview_statement("default", statement.entries)
    assert second_preview == {"accepted_entries": 0, "duplicate_entries": 2}
    positions, summary = store.position_report("default")
    assert positions[0]["quantity"] == Decimal("150")
    assert positions[0]["remaining_cost"] == Decimal("1728.75")
    assert positions[0]["realized_pnl"] == Decimal("121.75")
    assert summary["position_count"] == 1


def test_store_closed_position_report_supports_historical_as_of(tmp_path):
    opening_path = tmp_path / "opening.csv"
    opening_path.write_text(
        "as_of_date,ts_code,name,asset_type,quantity,total_cost,last_close\n"
        "2026-07-10,600000.SH,浦发银行,equity,100,1000,12\n",
        encoding="utf-8",
    )
    statement_path = tmp_path / "sell_out.csv"
    statement_path.write_text(
        "成交日期,成交时间,证券代码,证券名称,买卖标志,成交价格,成交数量,成交金额,手续费\n"
        "2026-07-11,09:31:02,600000,浦发银行,卖出,12,40,480,2\n"
        "2026-07-12,10:01:03,600000,浦发银行,卖出,11,60,660,3\n",
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

    earlier_cycles, earlier_summary = store.closed_position_report(
        "default", date(2026, 7, 11)
    )
    assert earlier_cycles == []
    assert earlier_summary["cycle_count"] == 0
    assert earlier_summary["realized_pnl_outside_closed_cycles"] == Decimal("78")

    cycles, summary = store.closed_position_report("default")
    assert len(cycles) == 1
    assert cycles[0]["name"] == "浦发银行"
    assert cycles[0]["cost_basis"] == Decimal("1000")
    assert cycles[0]["net_sale_proceeds"] == Decimal("1135")
    assert cycles[0]["realized_pnl"] == Decimal("135")
    assert cycles[0]["return_pct"] == Decimal("13.5")
    assert summary["total_realized_pnl"] == Decimal("135")
    assert summary["realized_pnl_outside_closed_cycles"] == Decimal("0")
    assert summary["latest_close_date"] == date(2026, 7, 12)


def test_prebaseline_statement_must_be_reconciled_without_changing_position(tmp_path):
    opening_path = tmp_path / "opening.csv"
    opening_path.write_text(
        "as_of_date,ts_code,name,quantity,total_cost,last_close\n"
        "2026-07-10,600000,浦发银行,900,9000,12\n",
        encoding="utf-8",
    )
    statement_path = tmp_path / "included.csv"
    statement_path.write_text(
        "成交日期,成交时间,证券代码,证券名称,买卖标志,成交价格,成交数量,成交金额,手续费\n"
        "2026-07-09,10:00:00,600000,浦发银行,买入,11,800,8800,5\n",
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
    statement = parse_statement(statement_path, account_id="default")

    with pytest.raises(ValueError, match="不晚于期初基准日"):
        store.preview_statement("default", statement.entries)

    preview = store.preview_included_statement("default", statement.entries)
    assert preview["accepted_entries"] == 1
    outcome = store.record_included_statement(
        account_id="default",
        instruments=statement.instruments.values(),
        entries=statement.entries,
        broker="test",
        source_name=statement.source_name,
        source_sha256=statement.source_sha256,
        total_rows=statement.total_rows,
        skipped_rows=statement.skipped_rows,
    )
    assert outcome["recorded_entries"] == 1
    assert len(store.recent_reconciliations("default")) == 1
    positions, _ = store.position_report("default")
    assert positions[0]["quantity"] == Decimal("900")
    assert positions[0]["remaining_cost"] == Decimal("9000")


class _Frame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        assert orient == "records"
        return self.rows


class _FakePro:
    def daily(self, **kwargs):
        return _Frame(
            [
                {
                    "ts_code": kwargs["ts_code"],
                    "trade_date": "20260710",
                    "close": 12.34,
                    "pre_close": 12.00,
                    "pct_chg": 2.8333,
                }
            ]
        )

    def fund_daily(self, **kwargs):
        return _Frame(
            [
                {
                    "ts_code": kwargs["ts_code"],
                    "trade_date": "20260710",
                    "close": 0.73,
                    "pre_close": 0.708,
                    "pct_chg": 3.11,
                }
            ]
        )

    def stock_basic(self, **kwargs):
        assert kwargs["fields"] == "ts_code,name,industry"
        return _Frame(
            [
                {
                    "ts_code": "600000.SH",
                    "name": "浦发银行",
                    "industry": "银行",
                }
            ]
        )


def test_tushare_provider_routes_equity_and_etf():
    provider = TushareCloseProvider(_FakePro())
    prices, missing = provider.fetch_many(
        [
            Instrument("600000.SH", "浦发银行", "equity"),
            Instrument("159892.SZ", "示例ETF", "etf"),
        ],
        as_of=date(2026, 7, 13),
    )
    assert not missing
    assert [(item.ts_code, item.close, item.source) for item in prices] == [
        ("600000.SH", Decimal("12.34"), "tushare.daily"),
        ("159892.SZ", Decimal("0.73"), "tushare.fund_daily"),
    ]


def test_industry_provider_uses_equity_field_and_explicit_etf_theme():
    classifications, missing = TushareIndustryProvider(_FakePro()).fetch_many(
        [
            Instrument("600000.SH", "浦发银行", "equity"),
            Instrument("159892.SZ", "恒生医药ETF华夏", "etf"),
            Instrument("159919.SZ", "沪深300ETF", "etf"),
        ]
    )

    assert [(item.ts_code, item.industry_name, item.source) for item in classifications] == [
        ("600000.SH", "银行", "tushare.stock_basic.industry"),
        ("159892.SZ", "医药生物", "instrument_name.theme"),
    ]
    assert missing == ["159919.SZ"]


def test_store_migrates_v1_database_and_persists_industry(tmp_path):
    database = tmp_path / "portfolio.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO metadata(key, value) VALUES ('schema_version', '1');
        CREATE TABLE instruments (
            ts_code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            exchange TEXT NOT NULL,
            currency TEXT NOT NULL DEFAULT 'CNY',
            updated_at TEXT NOT NULL
        );
        INSERT INTO instruments(ts_code, name, asset_type, exchange, currency, updated_at)
        VALUES ('600000.SH', '浦发银行', 'equity', 'SH', 'CNY', '2026-07-10T00:00:00+00:00');
        """
    )
    connection.commit()
    connection.close()

    store = PortfolioStore(database)
    store.initialize()
    assert store.set_industries(
        [IndustryClassification("600000.SH", "银行", "manual.test")]
    ) == 1

    with store.connect() as migrated:
        version = migrated.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        ).fetchone()["value"]
        row = migrated.execute(
            "SELECT industry_name, industry_source FROM instruments WHERE ts_code = '600000.SH'"
        ).fetchone()
    assert version == "2"
    assert dict(row) == {"industry_name": "银行", "industry_source": "manual.test"}


def test_portfolio_runtime_is_isolated_from_research_workflow():
    source_root = Path("src/portfolio")
    runtime_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(source_root.glob("*.py"))
    )

    for forbidden in (
        "src.research",
        "src.ingest",
        "research_orchestrator",
        "reports/workflow_runs",
        "data/manifests",
    ):
        assert forbidden not in runtime_text
