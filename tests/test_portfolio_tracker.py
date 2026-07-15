from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

import pytest

from src.portfolio.accounting import (
    AccountingError,
    build_closed_position_cycles,
    build_ledger_cycles,
    build_position_states,
)
from src.portfolio.cli import build_parser
from src.portfolio.importer import parse_opening_snapshot, parse_statement
from src.portfolio.industries import TushareIndustryProvider
from src.portfolio.intraday import (
    FallbackIntradayProvider,
    IntradayFetchBatch,
    IntradayFetchError,
    IntradayService,
    TushareIntradayProvider,
)
from src.portfolio.kline import KlineFetchError, KlineService, TushareKlineProvider
from src.portfolio.models import (
    AdjustmentFactorObservation,
    ClosePrice,
    DailyBarObservation,
    IndustryClassification,
    Instrument,
    LedgerEntry,
    MinuteBarObservation,
)
from src.portfolio.prices import TushareCloseProvider
from src.portfolio.realtime import (
    FallbackRealtimeProvider,
    RealtimeFetchError,
    RealtimeQuote,
    parse_sina_response,
    parse_tencent_response,
)
from src.portfolio.store import SCHEMA_VERSION, PortfolioStore


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


def test_cash_balance_snapshots_are_append_only_and_support_historical_as_of(tmp_path):
    store = PortfolioStore(tmp_path / "portfolio.sqlite3")
    store.initialize()

    first = store.set_cash_balance(
        "default",
        Decimal("10000"),
        date(2026, 7, 13),
        note="用户确认",
    )
    second = store.set_cash_balance(
        "default",
        Decimal("12345.67"),
        date(2026, 7, 14),
        note="用户确认当前现金余额",
    )

    assert first["snapshot_id"] != second["snapshot_id"]
    assert store.cash_balance("default")["amount"] == Decimal("12345.67")
    assert store.cash_balance("default", date(2026, 7, 13))["amount"] == Decimal("10000")
    assert store.cash_balance("default", date(2026, 7, 12)) is None
    assert [row["amount"] for row in store.cash_history("default")] == ["12345.67", "10000"]

    _, latest_summary = store.position_report("default")
    _, historical_summary = store.position_report("default", date(2026, 7, 13))
    assert latest_summary["cash_balance"] == Decimal("12345.67")
    assert latest_summary["total_assets"] == Decimal("12345.67")
    assert historical_summary["cash_balance"] == Decimal("10000")


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


def test_internal_transfer_reconciliation_is_idempotent_and_has_no_ledger_effect(tmp_path):
    statement_path = tmp_path / "statement.csv"
    statement_path.write_text(
        "成交日期,证券代码,证券名称,买卖标志,成交价格,成交数量,成交金额,手续费\n"
        "2026-02-09,600900,长江电力,买入,26.39,200,5278,0\n",
        encoding="utf-8",
    )
    store = PortfolioStore(tmp_path / "portfolio.sqlite3")
    store.initialize()
    statement = parse_statement(statement_path, account_id="default")
    store.apply_statement(
        account_id="default",
        instruments=statement.instruments.values(),
        entries=statement.entries,
        broker="guangfa",
        source_name=statement.source_name,
        source_sha256=statement.source_sha256,
        total_rows=statement.total_rows,
        skipped_rows=statement.skipped_rows,
    )
    transfer = {
        "ts_code": "600900.SH",
        "quantity": "200",
        "transfer_out_date": "2026-02-25",
        "transfer_in_date": "2026-02-27",
        "from_broker": "guangfa",
        "to_broker": "huatai",
        "reference_price": "26.04",
        "out_source_name": "guangfa.pdf",
        "in_source_name": "huatai.xls",
    }

    first = store.record_internal_transfers("default", [transfer])
    second = store.record_internal_transfers("default", [transfer])

    assert first == {"inserted_transfers": 1, "duplicate_transfers": 0}
    assert second == {"inserted_transfers": 0, "duplicate_transfers": 1}
    assert store.recent_internal_transfers("default")[0]["status"] == "reconciled_internal"
    positions, _ = store.position_report("default")
    assert positions[0]["quantity"] == Decimal("200")
    assert positions[0]["remaining_cost"] == Decimal("5278")


def test_historical_closed_statement_is_replayable_without_changing_baseline_pnl(tmp_path):
    opening_path = tmp_path / "opening.csv"
    opening_path.write_text(
        "as_of_date,ts_code,name,quantity,total_cost,last_close\n"
        "2026-07-07,600000,浦发银行,100,1000,12\n",
        encoding="utf-8",
    )
    historical_path = tmp_path / "historical_closed.csv"
    historical_path.write_text(
        "成交日期,证券代码,证券名称,买卖标志,成交价格,成交数量,成交金额,手续费,资金流水号\n"
        "2026-06-01,000001,平安银行,买入,10,100,1000,5,hist-buy\n"
        "2026-06-02,000001,平安银行,卖出,12,100,1200,6,hist-sell\n",
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
    statement = parse_statement(historical_path, account_id="default", broker="test")

    preview = store.preview_historical_closed_statement("default", statement.entries)
    assert preview["accepted_entries"] == 2
    assert preview["closed_codes"] == ["000001.SZ"]
    outcome = store.apply_historical_closed_statement(
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

    positions, summary = store.position_report("default")
    assert positions[0]["ts_code"] == "600000.SH"
    assert positions[0]["quantity"] == Decimal("100")
    assert summary["realized_pnl_since_baseline"] == Decimal("0")
    cycles, cycle_summary = store.closed_position_report("default")
    assert len(cycles) == 1
    assert cycles[0]["ts_code"] == "000001.SZ"
    assert cycles[0]["realized_pnl"] == Decimal("189")
    assert cycle_summary["total_realized_pnl"] == Decimal("189")
    second = store.preview_historical_closed_statement("default", statement.entries)
    assert second["accepted_entries"] == 0
    assert second["duplicate_entries"] == 2


def test_historical_closed_statement_rejects_incomplete_or_postbaseline_batches(tmp_path):
    opening_path = tmp_path / "opening.csv"
    opening_path.write_text(
        "as_of_date,ts_code,name,quantity,total_cost,last_close\n"
        "2026-07-07,600000,浦发银行,100,1000,12\n",
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

    incomplete_path = tmp_path / "incomplete.csv"
    incomplete_path.write_text(
        "成交日期,证券代码,证券名称,买卖标志,成交价格,成交数量,成交金额,手续费\n"
        "2026-06-01,000001,平安银行,买入,10,100,1000,5\n",
        encoding="utf-8",
    )
    incomplete = parse_statement(incomplete_path, account_id="default")
    with pytest.raises(ValueError, match="最终归零"):
        store.preview_historical_closed_statement("default", incomplete.entries)

    later_path = tmp_path / "later.csv"
    later_path.write_text(
        "成交日期,证券代码,证券名称,买卖标志,成交价格,成交数量,成交金额,手续费\n"
        "2026-07-08,000001,平安银行,买入,10,100,1000,5\n"
        "2026-07-09,000001,平安银行,卖出,12,100,1200,6\n",
        encoding="utf-8",
    )
    later = parse_statement(later_path, account_id="default")
    with pytest.raises(ValueError, match="晚于期初基准日"):
        store.preview_historical_closed_statement("default", later.entries)


def test_new_bond_allotment_is_supported_as_unknown_asset_buy(tmp_path):
    path = tmp_path / "bond.csv"
    path.write_text(
        "成交日期,证券代码,证券名称,买卖标志,成交价格,成交数量,成交金额,手续费\n"
        "2026-03-16,127115,长高转债,新债入账,100,10,1000,0\n"
        "2026-03-31,127115,长高转债,卖出,146.785,10,1467.85,0.08\n",
        encoding="utf-8",
    )
    parsed = parse_statement(path, account_id="default")
    assert not parsed.errors
    assert [entry.event_type for entry in parsed.entries] == ["BUY", "SELL"]
    assert parsed.instruments["127115.SZ"].asset_type == "unknown"


def test_gbk_tsv_disguised_as_xls_and_excel_text_codes_are_supported(tmp_path):
    path = tmp_path / "broker_export.xls"
    path.write_bytes(
        (
            "成交日期\t成交时间\t证券代码\t证券名称\t业务名称\t成交价格\t"
            "成交数量\t成交金额\t成交编号\n"
            '20260305\t14:51:59\t="159792"\t港股通互联网ETF富国\t证券买入\t'
            '0.714\t14000\t9996.00\t="0104000075848146"\n'
        ).encode("gb18030")
    )

    parsed = parse_statement(path, account_id="default", broker="huatai")

    assert not parsed.errors
    assert len(parsed.entries) == 1
    assert parsed.entries[0].ts_code == "159792.SZ"
    assert parsed.entries[0].external_id == "0104000075848146"
    assert parsed.entries[0].quantity == Decimal("14000")


def test_broker_dividend_account_character_variant_is_supported(tmp_path):
    path = tmp_path / "dividend.csv"
    path.write_text(
        "成交日期,证券代码,证券名称,业务名称,成交金额\n"
        "2026-06-25,600030,中信证券,股息入帐,120.50\n",
        encoding="utf-8",
    )

    parsed = parse_statement(path, account_id="default", broker="huatai")

    assert not parsed.errors
    assert parsed.entries[0].event_type == "DIVIDEND"
    assert parsed.entries[0].cash_amount == Decimal("120.50")


class _Frame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        assert orient == "records"
        return self.rows


class _FakePro:
    def daily(self, **kwargs):
        if kwargs.get("trade_date"):
            return _Frame(
                [
                    {"ts_code": "000001.SZ", "close": 10},
                    {"ts_code": "000002.SZ", "close": 20},
                    {"ts_code": "000003.SZ", "close": 10},
                ]
            )
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
                },
                {"ts_code": "000001.SZ", "name": "示例制药", "industry": "化学制药"},
                {"ts_code": "000002.SZ", "name": "示例生物", "industry": "生物医药"},
                {"ts_code": "000003.SZ", "name": "示例证券", "industry": "证券"},
            ]
        )

    def etf_sz_cons(self, **kwargs):
        baskets = {
            "159892.SZ": [
                {
                    "trade_date": "20260710",
                    "con_code": "159900.SZ",
                    "con_name": "申赎现金",
                    "qty": 0,
                },
                {
                    "trade_date": "20260710",
                    "con_code": "000001.SZ",
                    "con_name": "示例制药",
                    "qty": 100,
                },
                {
                    "trade_date": "20260710",
                    "con_code": "000002.SZ",
                    "con_name": "示例生物",
                    "qty": 50,
                },
            ],
            "159919.SZ": [
                {
                    "trade_date": "20260710",
                    "con_code": "000001.SZ",
                    "con_name": "示例制药",
                    "qty": 100,
                },
                {
                    "trade_date": "20260710",
                    "con_code": "000003.SZ",
                    "con_name": "示例证券",
                    "qty": 100,
                },
            ],
            "159999.SZ": [
                {
                    "trade_date": "20260710",
                    "con_code": "00013.HK",
                    "con_name": "未复核港股",
                    "qty": 100,
                }
            ],
        }
        return _Frame(baskets.get(kwargs["ts_code"], []))

    def fund_portfolio(self, **kwargs):
        return _Frame([])

    def etf_basic(self, **kwargs):
        return _Frame(
            [
                {
                    "ts_code": kwargs["ts_code"],
                    "index_code": "TEST.IDX",
                    "index_name": "测试指数",
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


def test_tushare_kline_provider_routes_equity_and_etf_with_factors():
    class KlinePro:
        def __init__(self):
            self.calls = []

        def daily(self, **kwargs):
            self.calls.append("daily")
            return _Frame(
                [
                    {
                        "ts_code": kwargs["ts_code"],
                        "trade_date": "20260710",
                        "open": 10,
                        "high": 12,
                        "low": 9,
                        "close": 11,
                        "vol": 100,
                        "amount": 110,
                    }
                ]
            )

        def adj_factor(self, **kwargs):
            self.calls.append("adj_factor")
            return _Frame(
                [{"ts_code": kwargs["ts_code"], "trade_date": "20260710", "adj_factor": 2}]
            )

        def fund_daily(self, **kwargs):
            self.calls.append("fund_daily")
            return _Frame(
                [
                    {
                        "ts_code": kwargs["ts_code"],
                        "trade_date": "20260710",
                        "open": 1,
                        "high": 1.2,
                        "low": 0.9,
                        "close": 1.1,
                        "vol": 200,
                        "amount": 220,
                    }
                ]
            )

        def fund_adj(self, **kwargs):
            self.calls.append("fund_adj")
            return _Frame(
                [{"ts_code": kwargs["ts_code"], "trade_date": "20260710", "adj_factor": 1.5}]
            )

    pro = KlinePro()
    provider = TushareKlineProvider(pro)
    equity = provider.fetch(
        Instrument("600000.SH", "浦发银行", "equity"),
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 10),
    )
    etf = provider.fetch(
        Instrument("159892.SZ", "示例ETF", "etf"),
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 10),
    )

    assert pro.calls == ["daily", "adj_factor", "fund_daily", "fund_adj"]
    assert equity.bar_source == "tushare.daily"
    assert equity.factor_source == "tushare.adj_factor"
    assert equity.bars[0].volume_lots == Decimal("100")
    assert etf.bar_source == "tushare.fund_daily"
    assert etf.factor_source == "tushare.fund_adj"

    class MissingFactorPro(KlinePro):
        def adj_factor(self, **kwargs):
            return _Frame([])

    with pytest.raises(KlineFetchError, match="缺少 1 个交易日的复权因子"):
        TushareKlineProvider(MissingFactorPro()).fetch(
            Instrument("600000.SH", "浦发银行", "equity"),
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 10),
        )


def test_kline_store_qfq_operations_idempotency_and_historical_cutoff(tmp_path):
    opening_path = tmp_path / "opening.csv"
    opening_path.write_text(
        "as_of_date,ts_code,name,asset_type,quantity,total_cost,last_close,market_value,unrealized_pnl\n"
        "2026-07-10,600000.SH,浦发银行,equity,100,1000,10,1000,0\n",
        encoding="utf-8",
    )
    statement_path = tmp_path / "buys.csv"
    statement_path.write_text(
        "成交日期,成交时间,证券代码,证券名称,买卖标志,成交价格,成交数量,成交金额,手续费\n"
        "2026-07-11,09:31:00,600000,浦发银行,买入,12,10,120,1\n"
        "2026-07-11,10:15:00,600000,浦发银行,买入,14,10,140,1\n",
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

    batch_id = "batch-test"
    fetched_at = "2026-07-12T08:00:00+00:00"
    raw = [
        (date(2026, 7, 9), "9", "10", "8", "9", "1"),
        (date(2026, 7, 10), "10", "11", "9", "10", "1"),
        (date(2026, 7, 11), "12", "14", "11", "13", "1.5"),
        (date(2026, 7, 12), "13", "15", "12", "14", "2"),
    ]
    bars = [
        DailyBarObservation(
            ts_code="600000.SH",
            trade_date=trade_day,
            open=Decimal(open_price),
            high=Decimal(high),
            low=Decimal(low),
            close=Decimal(close),
            volume_lots=Decimal("100"),
            amount_k_cny=Decimal("1000"),
            source="tushare.daily",
            refresh_batch_id=batch_id,
            dedupe_key=f"bar-{trade_day}",
            fetched_at=fetched_at,
        )
        for trade_day, open_price, high, low, close, _ in raw
    ]
    factors = [
        AdjustmentFactorObservation(
            ts_code="600000.SH",
            trade_date=trade_day,
            adj_factor=Decimal(factor),
            source="tushare.adj_factor",
            refresh_batch_id=batch_id,
            dedupe_key=f"factor-{trade_day}",
            fetched_at=fetched_at,
        )
        for trade_day, _, _, _, _, factor in raw
    ]
    assert store.add_kline_batch(bars, factors) == {
        "new_bar_observations": 4,
        "new_factor_observations": 4,
    }
    assert store.add_kline_batch(bars, factors) == {
        "new_bar_observations": 0,
        "new_factor_observations": 0,
    }

    cycles = build_ledger_cycles(store.ledger("default"))
    assert [(item.cycle_id, len(item.entries), item.closed_on) for item in cycles] == [
        ("600000.SH:1", 3, None)
    ]
    position, _ = store.position_report("default")
    assert position[0]["cycle_id"] == "600000.SH:1"

    payload = KlineService(store).get_payload(
        "600000.SH", range_key="3m", as_of=date(2026, 7, 12)
    )
    assert payload["status"] == "ready"
    assert payload["adjustment"]["anchor_date"] == "2026-07-12"
    assert payload["bars"][1]["trade_date"] == "2026-07-10"
    assert payload["bars"][1]["close"] == 5.0
    indicator_profile = payload["technical_indicators"]
    assert indicator_profile["default_selected"] == ["VOL"]
    assert len(indicator_profile["available"]) == 27
    assert {"MACD", "KDJ", "RSI", "BOLL", "EMV", "AVP"}.issubset(
        indicator_profile["available"]
    )
    assert indicator_profile["calculation"] == {
        "mode": "client_side",
        "engine": "klinecharts",
        "engine_version": "10.0.0",
        "parameter_profile": "library_defaults",
        "input_period": "1d",
        "input_price_adjustment": "qfq",
        "input_fields": ["open", "high", "low", "close", "volume", "turnover"],
        "persisted": False,
    }
    assert "不是交易信号" in indicator_profile["boundary"]
    opening_group, buy_group = payload["operation_groups"]
    assert opening_group["actual_price"] == "10"
    assert opening_group["adjusted_price"] == 5.0
    assert buy_group["entry_count"] == 2
    assert buy_group["actual_price"] == "13"
    assert buy_group["adjusted_price"] == 9.75

    historical = KlineService(store).get_payload(
        "600000.SH", range_key="3m", as_of=date(2026, 7, 11)
    )
    assert historical["coverage"]["last_trade_date"] == "2026-07-11"
    assert all(item["trade_date"] <= "2026-07-11" for item in historical["bars"])

    class BrokenProvider:
        def fetch(self, *_args, **_kwargs):
            raise KlineFetchError("simulated upstream failure")

    with pytest.raises(KlineFetchError, match="simulated upstream failure"):
        KlineService(store).refresh(
            BrokenProvider(),
            "600000.SH",
            range_key="3m",
            as_of=date(2026, 7, 12),
        )
    retained = KlineService(store).get_payload(
        "600000.SH", range_key="3m", as_of=date(2026, 7, 12)
    )
    assert retained["bars"] == payload["bars"]


def test_non_trading_day_opening_maps_to_previous_bar():
    cycle = build_ledger_cycles(
        [
            _row(
                "OPENING",
                event_date="2026-07-11",
                quantity="100",
                total_cost="1000",
            )
        ]
    )[0]
    groups, gaps = KlineService._operation_groups(
        cycle,
        [{"trade_date": date(2026, 7, 10)}],
        {date(2026, 7, 10): Decimal("2")},
        Decimal("2"),
        date(2026, 4, 10),
        date(2026, 7, 10),
    )
    assert gaps == []
    assert groups[0]["mapping_status"] == "mapped_previous_bar"
    assert groups[0]["mapped_trade_date"] == "2026-07-10"
    assert groups[0]["adjusted_price"] == 10.0


def test_kline_payload_refuses_to_draw_raw_bars_when_factor_is_missing(tmp_path):
    opening_path = tmp_path / "opening.csv"
    opening_path.write_text(
        "as_of_date,ts_code,name,asset_type,quantity,total_cost,last_close,market_value,unrealized_pnl\n"
        "2026-07-10,600000.SH,浦发银行,equity,100,1000,10,1000,0\n",
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
    bar = DailyBarObservation(
        ts_code="600000.SH",
        trade_date=date(2026, 7, 10),
        open=Decimal("10"),
        high=Decimal("11"),
        low=Decimal("9"),
        close=Decimal("10"),
        volume_lots=Decimal("100"),
        amount_k_cny=Decimal("1000"),
        source="tushare.daily",
        refresh_batch_id="partial",
        dedupe_key="partial-bar",
        fetched_at="2026-07-10T08:00:00+00:00",
    )
    store.add_kline_batch([bar], [])

    payload = KlineService(store).get_payload(
        "600000.SH", range_key="3m", as_of=date(2026, 7, 10)
    )
    assert payload["status"] == "incomplete"
    assert payload["bars"] == []
    assert payload["coverage"]["missing_factor_dates"] == ["2026-07-10"]


def test_refresh_kline_cli_contract():
    args = build_parser().parse_args(
        [
            "refresh-kline",
            "--code",
            "600000.SH",
            "--range",
            "cycle",
            "--cycle-id",
            "600000.SH:1",
            "--as-of",
            "2026-07-12",
        ]
    )
    assert args.code == "600000.SH"
    assert args.range == "cycle"
    assert args.cycle_id == "600000.SH:1"


def _build_intraday_store(tmp_path) -> PortfolioStore:
    opening_path = tmp_path / "intraday_opening.csv"
    opening_path.write_text(
        "as_of_date,ts_code,name,asset_type,quantity,total_cost,last_close,market_value,unrealized_pnl\n"
        "2026-07-10,600000.SH,浦发银行,equity,100,1000,10,1000,0\n",
        encoding="utf-8",
    )
    statement_path = tmp_path / "intraday_statement.csv"
    statement_path.write_text(
        "成交日期,成交时间,证券代码,证券名称,买卖标志,成交价格,成交数量,成交金额,手续费\n"
        "2026-07-14,09:30:01,600000,浦发银行,买入,10,10,100,1\n"
        "2026-07-14,09:34:59,600000,浦发银行,买入,11,20,220,1\n"
        "2026-07-14,09:34:30,600000,浦发银行,卖出,12,5,60,1\n"
        "2026-07-14,11:31:00,600000,浦发银行,买入,13,1,13,0\n"
        "2026-07-14,,600000,浦发银行,买入,14,1,14,0\n",
        encoding="utf-8",
    )
    store = PortfolioStore(tmp_path / "intraday.sqlite3")
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
    return store


def _minute_bar(
    *,
    bar_time: datetime,
    close: str,
    batch_id: str,
    dedupe_key: str,
    fetched_at: str,
) -> MinuteBarObservation:
    return MinuteBarObservation(
        ts_code="600000.SH",
        bar_time=bar_time,
        frequency_minutes=5,
        open=Decimal("10"),
        high=max(Decimal("12"), Decimal(close)),
        low=Decimal("9"),
        close=Decimal(close),
        volume_shares=Decimal("100"),
        amount_cny=Decimal("1100"),
        source="baostock.history_k_data_plus",
        refresh_batch_id=batch_id,
        dedupe_key=dedupe_key,
        fetched_at=fetched_at,
    )


def test_intraday_provider_uses_tushare_1m_and_falls_back_after_etf_permission():
    class MinutePro:
        def stk_mins(self, **kwargs):
            assert kwargs["freq"] == "1min"
            return _Frame(
                [
                    {
                        "ts_code": kwargs["ts_code"],
                        "trade_time": "2026-07-14 09:31:00",
                        "open": 10,
                        "high": 11,
                        "low": 9,
                        "close": 10.5,
                        "vol": 100,
                        "amount": 1050,
                    }
                ]
            )

    batch = TushareIntradayProvider(MinutePro()).fetch(
        Instrument("600000.SH", "浦发银行", "equity"),
        trade_date=date(2026, 7, 14),
    )
    assert batch.frequency_minutes == 1
    assert batch.source == "tushare.stk_mins"
    assert batch.bars[0].bar_time.isoformat() == "2026-07-14T09:31:00+08:00"

    class DuplicateMinutePro(MinutePro):
        def stk_mins(self, **kwargs):
            row = super().stk_mins(**kwargs).to_dict(orient="records")[0]
            return _Frame([row, row])

    with pytest.raises(ValueError, match="重复结束时间"):
        TushareIntradayProvider(DuplicateMinutePro()).fetch(
            Instrument("600000.SH", "浦发银行", "equity"),
            trade_date=date(2026, 7, 14),
        )

    class PermissionDenied:
        def fetch(self, *_args, **_kwargs):
            raise RuntimeError("没有接口权限")

    class BaoBackup:
        def fetch(self, instrument, *, trade_date):
            return IntradayFetchBatch(
                bars=batch.bars,
                frequency_minutes=5,
                source="baostock.history_k_data_plus",
                refresh_batch_id="fallback",
                fetched_at="2026-07-14T08:00:00+00:00",
            )

    fallback = FallbackIntradayProvider(
        [("tushare.1m", PermissionDenied()), ("baostock.5m", BaoBackup())]
    ).fetch(Instrument("159892.SZ", "示例ETF", "etf"), trade_date=date(2026, 7, 14))
    assert fallback.frequency_minutes == 5
    assert list(fallback.provider_attempts) == [
        {"provider": "tushare.1m", "status": "failed", "reason": "permission_denied"},
        {"provider": "baostock.5m", "status": "success"},
    ]


def test_intraday_store_latest_observation_mapping_and_cache_retention(tmp_path):
    store = _build_intraday_store(tmp_path)
    zone = ZoneInfo("Asia/Shanghai")
    first_batch = [
        _minute_bar(
            bar_time=datetime(2026, 7, 14, 9, 35, tzinfo=zone),
            close="10.5",
            batch_id="minute-1",
            dedupe_key="minute-0935-v1",
            fetched_at="2026-07-14T08:00:00+00:00",
        ),
        _minute_bar(
            bar_time=datetime(2026, 7, 14, 9, 40, tzinfo=zone),
            close="11",
            batch_id="minute-1",
            dedupe_key="minute-0940-v1",
            fetched_at="2026-07-14T08:00:00+00:00",
        ),
    ]
    kwargs = {
        "trade_date": date(2026, 7, 14),
        "frequency_minutes": 5,
        "source": "baostock.history_k_data_plus",
        "refresh_batch_id": "minute-1",
        "provider_attempts": [
            {"provider": "tushare.1m", "status": "failed", "reason": "permission_denied"},
            {"provider": "baostock.5m", "status": "success"},
        ],
        "fetched_at": "2026-07-14T08:00:00+00:00",
    }
    assert store.add_minute_batch(first_batch, **kwargs) == {
        "new_refresh_batches": 1,
        "new_minute_observations": 2,
    }
    assert store.add_minute_batch(first_batch, **kwargs) == {
        "new_refresh_batches": 0,
        "new_minute_observations": 0,
    }

    updated = _minute_bar(
        bar_time=datetime(2026, 7, 14, 9, 35, tzinfo=zone),
        close="11.5",
        batch_id="minute-2",
        dedupe_key="minute-0935-v2",
        fetched_at="2026-07-14T08:05:00+00:00",
    )
    store.add_minute_batch(
        [updated],
        trade_date=date(2026, 7, 14),
        frequency_minutes=5,
        source=updated.source,
        refresh_batch_id="minute-2",
        provider_attempts=[{"provider": "baostock.5m", "status": "success"}],
        fetched_at=updated.fetched_at,
    )
    rows, metadata = store.latest_minute_bars("600000.SH", date(2026, 7, 14))
    assert [item["close_price"] for item in rows] == [Decimal("11.5"), Decimal("11")]
    assert metadata["refresh_batch_id"] == "minute-2"

    payload = IntradayService(store).get_payload(
        "600000.SH", as_of=date(2026, 7, 14)
    )
    assert payload["trade_date"] == "2026-07-14"
    assert payload["date_scope"] == "cycle"
    assert payload["period"]["span"] == 5
    assert [(item["event_type"], item["entry_count"]) for item in payload["operation_groups"]] == [
        ("BUY", 2),
        ("SELL", 1),
    ]
    assert payload["operation_groups"][0]["mapping_status"] == "mapped_5m_bucket"
    assert payload["operation_groups"][0]["actual_price"] == "10.66666666666666666666666667"
    assert {item["reason"] for item in payload["unlocated_operations"]} == {
        "missing_event_time",
        "outside_session",
    }
    retained_bars = payload["bars"]

    context_payload = IntradayService(store).get_payload(
        "600000.SH",
        trade_date=date(2026, 5, 29),
        as_of=date(2026, 7, 14),
    )
    assert context_payload["trade_date"] == "2026-05-29"
    assert context_payload["date_scope"] == "pre_open_context"
    assert context_payload["operation_groups"] == []
    assert context_payload["unlocated_operations"] == []

    with pytest.raises(ValueError, match="不能晚于 as_of"):
        IntradayService(store).get_payload(
            "600000.SH",
            trade_date=date(2026, 7, 15),
            as_of=date(2026, 7, 14),
        )

    class BothSourcesFail:
        def fetch(self, *_args, **_kwargs):
            raise IntradayFetchError(
                "分钟行情源均不可用",
                [{"provider": "tushare.1m", "status": "failed", "reason": "network_error"}],
            )

    with pytest.raises(IntradayFetchError):
        IntradayService(store).refresh(
            BothSourcesFail(),
            "600000.SH",
            trade_date=date(2026, 7, 14),
            as_of=date(2026, 7, 14),
        )
    assert IntradayService(store).get_payload(
        "600000.SH", trade_date=date(2026, 7, 14), as_of=date(2026, 7, 14)
    )["bars"] == retained_bars


def test_refresh_intraday_cli_contract():
    args = build_parser().parse_args(
        [
            "refresh-intraday",
            "--code",
            "600000.SH",
            "--date",
            "2026-07-14",
            "--cycle-id",
            "600000.SH:1",
            "--as-of",
            "2026-07-14",
        ]
    )
    assert args.code == "600000.SH"
    assert args.date == "2026-07-14"
    assert args.cycle_id == "600000.SH:1"


def test_intraday_unknown_asset_is_explicitly_unsupported_without_fetch(tmp_path):
    store = PortfolioStore(tmp_path / "unknown-asset.sqlite3")
    store.initialize()
    instrument = Instrument("000001.XX", "未知资产", "unknown")
    opening = LedgerEntry(
        "default",
        date(2026, 7, 10),
        "OPENING",
        instrument.ts_code,
        quantity=Decimal("1"),
        total_cost=Decimal("10"),
        dedupe_key="unknown-opening",
    )
    store.apply_opening_snapshot(
        account_id="default",
        instruments=[instrument],
        entries=[opening],
        prices=[
            ClosePrice(
                instrument.ts_code,
                date(2026, 7, 10),
                Decimal("10"),
                "smoke",
            )
        ],
        source_name="unknown-opening",
        source_sha256="unknown-opening",
        total_rows=1,
    )

    class MustNotFetch:
        def fetch(self, *_args, **_kwargs):
            raise AssertionError("unsupported 资产不应调用行情源")

    payload = IntradayService(store).refresh(
        MustNotFetch(),
        instrument.ts_code,
        trade_date=date(2026, 7, 14),
        as_of=date(2026, 7, 14),
    )
    assert payload["status"] == "unsupported"
    assert payload["bars"] == []


def test_industry_provider_normalizes_equity_and_classifies_etf_from_holdings():
    classifications, missing = TushareIndustryProvider(
        _FakePro(),
        hk_industry_provider=None,
        hk_close_provider=None,
    ).fetch_many(
        [
            Instrument("600000.SH", "浦发银行", "equity"),
            Instrument("000001.SZ", "示例制药", "equity"),
            Instrument("159892.SZ", "恒生医药ETF华夏", "etf"),
            Instrument("159919.SZ", "沪深300ETF", "etf"),
            Instrument("159999.SZ", "医药名字不能替代持仓证据ETF", "etf"),
        ]
    )

    by_code = {item.ts_code: item for item in classifications}
    assert by_code["600000.SH"].industry_name == "银行"
    assert by_code["600000.SH"].source == "tushare.stock_basic.industry"
    assert by_code["000001.SZ"].industry_name == "医药生物"
    assert "raw=化学制药" in by_code["000001.SZ"].source
    assert by_code["159892.SZ"].industry_name == "医药生物"
    assert by_code["159892.SZ"].confidence == "high"
    assert by_code["159892.SZ"].classified_weight_coverage == Decimal("1")
    assert "tushare.etf_sz_cons" in by_code["159892.SZ"].source
    assert "index_role=corroboration_only" in by_code["159892.SZ"].source
    assert by_code["159919.SZ"].industry_name == "跨行业ETF"
    assert by_code["159999.SZ"].industry_name == "未分类（ETF持仓覆盖不足）"
    assert by_code["159999.SZ"].confidence == "unverified"
    assert missing == ["159999.SZ"]


def test_industry_provider_classifies_hk_etf_with_reviewed_industry_and_same_day_close():
    class HongKongIndustryProvider:
        source = "eastmoney.test.BELONG_INDUSTRY"

        def fetch_many(self, ts_codes):
            assert set(ts_codes) == {"00013.HK"}
            return {"00013.HK": "药品及生物科技"}

    class HongKongCloseProvider:
        source = "sina.test.close"

        def fetch_many(self, ts_codes, trade_date):
            assert set(ts_codes) == {"00013.HK"}
            assert trade_date == "20260710"
            return {"00013.HK": Decimal("10")}

    classifications, missing = TushareIndustryProvider(
        _FakePro(),
        hk_industry_provider=HongKongIndustryProvider(),
        hk_close_provider=HongKongCloseProvider(),
    ).fetch_many([Instrument("159999.SZ", "名称不参与判断ETF", "etf")])

    assert missing == []
    assert classifications[0].industry_name == "医药生物"
    assert classifications[0].confidence == "high"
    assert classifications[0].source_date == "20260710"
    assert "industry_source=eastmoney.test.BELONG_INDUSTRY" in classifications[0].source
    assert "price_source=sina.test.close" in classifications[0].source


def test_industry_provider_uses_reviewed_theme_aggregation_only_after_holdings_pass():
    class InternetEtfPro(_FakePro):
        def etf_sz_cons(self, **kwargs):
            return _Frame(
                [
                    {
                        "trade_date": "20260710",
                        "con_code": "00700.HK",
                        "con_name": "示例软件平台",
                        "qty": 60,
                    },
                    {
                        "trade_date": "20260710",
                        "con_code": "09988.HK",
                        "con_name": "示例电商平台",
                        "qty": 40,
                    },
                ]
            )

        def etf_basic(self, **kwargs):
            return _Frame([{"index_name": "港股通互联网"}])

    class HongKongIndustryProvider:
        source = "eastmoney.test.BELONG_INDUSTRY"

        def fetch_many(self, ts_codes):
            assert set(ts_codes) == {"00700.HK", "09988.HK"}
            return {"00700.HK": "软件服务", "09988.HK": "专业零售"}

    class HongKongCloseProvider:
        source = "sina.test.close"

        def fetch_many(self, ts_codes, trade_date):
            return {"00700.HK": Decimal("10"), "09988.HK": Decimal("10")}

    classifications, missing = TushareIndustryProvider(
        InternetEtfPro(),
        hk_industry_provider=HongKongIndustryProvider(),
        hk_close_provider=HongKongCloseProvider(),
    ).fetch_many([Instrument("159792.SZ", "名称不参与判断ETF", "etf")])

    assert missing == []
    assert classifications[0].industry_name == "互联网"
    assert classifications[0].confidence == "high"
    assert classifications[0].top_industry_weight == Decimal("1")
    assert "index_role=theme_aggregation_selector" in classifications[0].source


def test_industry_provider_uses_latest_fund_portfolio_when_basket_is_unavailable():
    class PortfolioOnlyPro(_FakePro):
        def etf_sz_cons(self, **kwargs):
            return _Frame([])

        def fund_portfolio(self, **kwargs):
            return _Frame(
                [
                    {
                        "end_date": "20260331",
                        "symbol": "000001.SZ",
                        "mkv": 800,
                        "stk_mkv_ratio": 0,
                    },
                    {
                        "end_date": "20260331",
                        "symbol": "000003.SZ",
                        "mkv": 200,
                        "stk_mkv_ratio": 0,
                    },
                    {
                        "end_date": "20251231",
                        "symbol": "000003.SZ",
                        "mkv": 1000,
                        "stk_mkv_ratio": 0,
                    },
                ]
            )

    classifications, missing = TushareIndustryProvider(PortfolioOnlyPro()).fetch_many(
        [Instrument("159892.SZ", "不能按名称判断ETF", "etf")]
    )

    assert missing == []
    assert classifications[0].industry_name == "医药生物"
    assert classifications[0].confidence == "high"
    assert classifications[0].method == "mkv"
    assert classifications[0].source_date == "20260331"


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
    assert version == SCHEMA_VERSION
    assert dict(row) == {"industry_name": "银行", "industry_source": "manual.test"}
    with store.connect() as migrated:
        tables = {
            item["name"]
            for item in migrated.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert "cash_balance_snapshots" in tables
    assert "daily_bar_observations" in tables
    assert "adjustment_factor_observations" in tables
    assert len(list(tmp_path.glob("portfolio.sqlite3-v1-backup-*"))) == 1


@pytest.mark.parametrize("legacy_version", ["2", "3", "4", "5", "6"])
def test_store_migrates_legacy_databases_to_current_version_with_backup(
    tmp_path, legacy_version
):
    database = tmp_path / "portfolio.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        f"""
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO metadata(key, value) VALUES ('schema_version', '{legacy_version}');
        """
    )
    connection.commit()
    connection.close()

    store = PortfolioStore(database)
    store.initialize()
    with store.connect() as migrated:
        version = migrated.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        ).fetchone()["value"]
        tables = {
            item["name"]
            for item in migrated.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert version == SCHEMA_VERSION
    assert "daily_bar_observations" in tables
    assert "adjustment_factor_observations" in tables
    assert "minute_refresh_batches" in tables
    assert "minute_bar_observations" in tables
    assert "internal_transfer_reconciliations" in tables
    assert "portfolio_snapshots" in tables
    assert "position_snapshots" in tables
    assert len(list(tmp_path.glob(f"portfolio.sqlite3-v{legacy_version}-backup-*"))) == 1


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
