from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from src.investment_review.strategy_drawdown_pipeline import _fee_profile


def test_fee_profile_stops_at_report_cutoff(tmp_path: Path) -> None:
    database = tmp_path / "portfolio.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute(
        """
        CREATE TABLE ledger_entries (
            account_id TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_type TEXT NOT NULL,
            gross_amount TEXT NOT NULL,
            fees TEXT NOT NULL,
            cash_amount TEXT NOT NULL
        )
        """
    )
    connection.executemany(
        "INSERT INTO ledger_entries VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("default", "2026-07-15", "BUY", "1000", "2", "0"),
            ("default", "2026-07-16", "SELL", "500", "1", "0"),
            ("default", "2026-07-16", "CASH_FEE", "0", "0", "4"),
            ("default", "2026-07-17", "BUY", "9000", "90", "0"),
            ("other", "2026-07-16", "BUY", "8000", "80", "0"),
        ],
    )
    connection.commit()
    connection.close()

    profile = _fee_profile(database, "default", date(2026, 7, 16))

    assert profile["gross_turnover"] == 1500
    assert profile["trade_fees"] == 3
    assert profile["cash_fees"] == 4
    assert profile["all_recorded_or_backfilled_fees"] == 7
    assert profile["observed_trade_fee_rate"] == pytest.approx(0.002)
