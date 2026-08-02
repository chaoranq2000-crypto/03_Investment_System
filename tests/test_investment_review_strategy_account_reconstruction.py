from __future__ import annotations

import hashlib
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.investment_review.strategy_account_reconstruction import (
    CashAnchor,
    ledger_cash_delta,
    open_formal_portfolio_read_only,
    reconstruct_account_history,
    sqlite_read_only_uri,
)


def _database(path: Path) -> Path:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE instruments (
            ts_code TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE ledger_entries (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_time TEXT NOT NULL DEFAULT '',
            event_type TEXT NOT NULL,
            ts_code TEXT NOT NULL,
            quantity TEXT NOT NULL DEFAULT '0',
            price TEXT NOT NULL DEFAULT '0',
            gross_amount TEXT NOT NULL DEFAULT '0',
            fees TEXT NOT NULL DEFAULT '0',
            cash_amount TEXT NOT NULL DEFAULT '0',
            note TEXT NOT NULL DEFAULT '',
            import_batch_id TEXT
        );
        CREATE TABLE close_prices (
            observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            close TEXT NOT NULL,
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE cash_balance_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            amount TEXT NOT NULL,
            source TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            recorded_at TEXT NOT NULL
        );
        CREATE TABLE position_cost_rebases (
            rebase_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            ts_code TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            target_quantity TEXT NOT NULL,
            status TEXT NOT NULL,
            source_path TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        );
        """
    )
    connection.execute("INSERT INTO instruments VALUES ('AAA.SZ', '甲公司')")
    connection.commit()
    connection.close()
    return path


def _entry(
    path: Path,
    event_date: str,
    event_type: str,
    *,
    quantity: str = "0",
    price: str = "0",
    gross: str = "0",
    fees: str = "0",
    cash: str = "0",
    note: str = "",
    code: str = "AAA.SZ",
) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """
        INSERT INTO ledger_entries(
            account_id, event_date, event_type, ts_code, quantity, price,
            gross_amount, fees, cash_amount, note
        ) VALUES ('default', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (event_date, event_type, code, quantity, price, gross, fees, cash, note),
    )
    connection.commit()
    connection.close()


def _price(path: Path, trade_date: str, close: str, *, code: str = "AAA.SZ") -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """
        INSERT INTO close_prices(ts_code, trade_date, close, source, fetched_at)
        VALUES (?, ?, ?, 'test_market', ?)
        """,
        (code, trade_date, close, trade_date + "T16:00:00+08:00"),
    )
    connection.commit()
    connection.close()


def _result(
    path: Path,
    *,
    anchor_date: str,
    anchor_amount: str,
    shift: str = "200",
    trusted_start: str = "2025-01-02",
):
    return reconstruct_account_history(
        path,
        account_id="default",
        cash_anchor=CashAnchor(date.fromisoformat(anchor_date), Decimal(anchor_amount), "test"),
        constant_cash_shift=shift,
        trusted_window_start=trusted_start,
    )


@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        ("BUY", Decimal("-101")),
        ("SELL", Decimal("99")),
        ("DIVIDEND", Decimal("7")),
        ("CASH_FEE", Decimal("-7")),
        ("OPENING", Decimal("0")),
    ],
)
def test_ledger_cash_delta_uses_contractual_signs(
    event_type: str,
    expected: Decimal,
) -> None:
    assert (
        ledger_cash_delta(
            event_type,
            gross_amount="100",
            fees="1",
            cash_amount="7",
        )
        == expected
    )


def test_anchor_backsolve_daily_nav_snapshots_and_rebase_audit(tmp_path: Path) -> None:
    path = _database(tmp_path / "portfolio.sqlite3")
    _entry(
        path,
        "2025-01-02",
        "BUY",
        quantity="10",
        price="10",
        gross="100",
        fees="1",
        note="fee_backfilled_exact=historical_statement.csv:2",
    )
    _entry(path, "2025-01-03", "DIVIDEND", cash="5")
    _entry(
        path,
        "2025-01-04",
        "SELL",
        quantity="5",
        price="12",
        gross="60",
        fees="2",
        note="fee_source=broker_actual",
    )
    _entry(path, "2025-01-04", "CASH_FEE", cash="2")
    for day, close in (("2025-01-02", "10"), ("2025-01-03", "11"), ("2025-01-04", "12")):
        _price(path, day, close)
    connection = sqlite3.connect(path)
    connection.executemany(
        "INSERT INTO cash_balance_snapshots VALUES (?, 'default', ?, ?, 'test', '', ?)",
        [
            ("cash-1", "2025-01-02", "899", "2025-01-02T18:00:00+08:00"),
            ("cash-2", "2025-01-04", "960", "2025-01-04T18:00:00+08:00"),
        ],
    )
    connection.execute(
        """
        INSERT INTO position_cost_rebases VALUES (
            'rebase-1', 'default', 'AAA.SZ', '2025-01-03', '11',
            'reviewed', 'fixture.csv', '2025-01-03T18:00:00+08:00'
        )
        """
    )
    connection.commit()
    connection.close()

    result = _result(
        path,
        anchor_date="2025-01-04",
        anchor_amount="960",
        trusted_start="2025-01-03",
    )
    raw = result.by_name("anchored_raw")

    assert result.audit.inferred_cash_before_first_ledger_event == Decimal("1000")
    assert [row.cash for row in raw.daily] == [Decimal("899"), Decimal("904"), Decimal("960")]
    assert [row.nav for row in raw.daily] == [Decimal("999"), Decimal("1014"), Decimal("1020")]
    assert raw.daily[0].gross_trade_amount == Decimal("100")
    assert raw.daily[0].actual_fees == Decimal("1")
    assert raw.daily[-1].actual_fees == Decimal("4")
    assert all(check.difference == 0 for check in result.audit.cash_snapshot_checks)
    assert result.audit.rebase_quantity_checks[0].difference == Decimal("-1")
    assert result.audit.holdings_before_output_start == ()
    assert result.audit.holdings_at_output_start[0].quantity == Decimal("10")
    assert result.audit.final_holdings[0].quantity == Decimal("5")
    assert [scenario.name for scenario in result.scenarios] == [
        "anchored_raw",
        "constant_cash_shift",
        "trusted_window",
    ]
    assert all("not_fact" in scenario.epistemic_status for scenario in result.scenarios)
    assert result.by_name("trusted_window").daily[0].daily_return is None


def test_never_uses_a_future_close_and_marks_cost_proxy_as_non_market(tmp_path: Path) -> None:
    path = _database(tmp_path / "portfolio.sqlite3")
    _entry(
        path,
        "2025-01-02",
        "BUY",
        quantity="10",
        price="10",
        gross="100",
        fees="1",
        note="fee_source=broker_actual",
    )
    _price(path, "2025-01-03", "11")

    result = _result(path, anchor_date="2025-01-03", anchor_amount="899")
    raw = result.by_name("anchored_raw")
    first, second = raw.daily

    assert first.trade_date == date(2025, 1, 2)
    assert first.price_marks[0].method == "subscription_cost_proxy_non_market"
    assert first.price_marks[0].unit_price == Decimal("10")
    assert first.price_marks[0].is_market_price is False
    assert {gap.code for gap in first.gaps} >= {"market_price_missing_cost_proxy_used"}
    assert second.price_marks[0].method == "market_close"
    assert second.price_marks[0].price_date == date(2025, 1, 3)


def test_missing_past_price_remains_incomplete_when_proxy_is_disabled(tmp_path: Path) -> None:
    path = _database(tmp_path / "portfolio.sqlite3")
    _entry(path, "2025-01-02", "BUY", quantity="10", price="10", gross="100")
    _price(path, "2025-01-03", "11")

    result = reconstruct_account_history(
        path,
        account_id="default",
        cash_anchor=CashAnchor(date(2025, 1, 3), Decimal("900")),
        constant_cash_shift="0",
        trusted_window_start="2025-01-02",
        allow_subscription_cost_proxy=False,
    )

    first = result.by_name("anchored_raw").daily[0]
    assert first.market_value is None
    assert first.nav is None
    assert first.daily_return is None
    assert {gap.code for gap in first.gaps} >= {"market_price_missing"}


def test_negative_cash_is_visible_and_shift_is_only_a_sensitivity(tmp_path: Path) -> None:
    path = _database(tmp_path / "portfolio.sqlite3")
    _entry(path, "2025-01-02", "BUY", quantity="20", price="10", gross="200")
    _entry(path, "2025-01-03", "SELL", quantity="20", price="12.5", gross="250")
    _price(path, "2025-01-02", "10")
    _price(path, "2025-01-03", "12.5")

    result = _result(path, anchor_date="2025-01-03", anchor_amount="100")
    raw = result.by_name("anchored_raw")
    shifted = result.by_name("constant_cash_shift")

    assert result.audit.inferred_cash_before_first_ledger_event == Decimal("50")
    assert raw.daily[0].cash == Decimal("-150")
    assert raw.diagnostics.negative_cash_dates == (date(2025, 1, 2),)
    assert shifted.daily[0].cash == Decimal("50")
    assert shifted.diagnostics.negative_cash_dates == ()
    assert shifted.cash_shift == Decimal("200")
    assert shifted.epistemic_status == "sensitivity_scenario_not_fact"


def test_source_database_is_opened_by_read_only_immutable_query_only_uri(tmp_path: Path) -> None:
    path = _database(tmp_path / "portfolio.sqlite3")
    uri = sqlite_read_only_uri(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    assert uri.endswith("?mode=ro&immutable=1")
    with open_formal_portfolio_read_only(path) as connection:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("CREATE TABLE forbidden_write(value TEXT)")

    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_reconstruction_is_deterministic_and_json_ready(tmp_path: Path) -> None:
    path = _database(tmp_path / "portfolio.sqlite3")
    _entry(
        path,
        "2025-01-02",
        "BUY",
        quantity="10",
        price="10",
        gross="100",
        fees="1",
        note="fee_rule=historical_fee_rule_v1; fee_backfilled_rule=true",
    )
    _price(path, "2025-01-02", "10")

    first = _result(path, anchor_date="2025-01-02", anchor_amount="899")
    second = _result(path, anchor_date="2025-01-02", anchor_amount="899")

    assert first == second
    assert first.to_dict() == second.to_dict()
    row = first.by_name("anchored_raw").daily[0]
    assert row.actual_fees is None
    assert row.ledger_fees_used_in_cash == Decimal("1")
    assert row.estimated_or_unverified_fees == Decimal("1")
    assert first.to_dict()["scenarios"][0]["daily"][0]["trade_date"] == "2025-01-02"
